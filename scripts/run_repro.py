#!/usr/bin/env python3
"""
run_repro.py - Reproduction Execution Module

Executes reproduction tasks based on execution plan, supporting:
- Command whitelist validation
- Virtual environment creation and management
- stdout/stderr capture
- Execution log saving
- Execution status tracking
- Observability enhancement
- Circuit breaker and fault tolerance
- Bilingual output (Chinese/English) based on user input language

Input:
- step4_plan.json (execution plan)
- config/project.conf (project config)

Output:
- step5_execution.json (execution record)
- execution_status.json (real-time status)
- logs/*.log (structured logs)

Usage:
    python run_repro.py --plan <PLAN_JSON> --project_dir <DIR> [--step <STEP_NUM>]
    python run_repro.py --plan step4_plan.json --project_dir . --lang zh
"""

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Import observability module
try:
    from observability import StructuredLogger, ResourceMonitor, ExecutionTracker
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

# Import circuit breaker module
try:
    from circuit_breaker import CircuitBreaker, RetryableExecutor, RetryPolicy, RollbackManager
    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False


# Internationalized strings
STRINGS = {
    "en": {
        "whitelist_warning": "Warning: Whitelist file not found",
        "empty_command": "Empty command",
        "command_matches_forbidden": "Command matches forbidden pattern",
        "invalid_command": "Invalid command",
        "not_in_whitelist": "Command not in whitelist",
        "user_stop": "User requested stop",
        "cancelled": "Cancelled",
        "stopped": "Stopped (user request)",
        "no_command": "No command",
        "whitelist_reject": "Whitelist rejected",
        "step_cancelled": "Cancelled (user request)",
        "success": "Success",
        "failed": "Failed",
        "env_create": "Creating virtual environment",
        "env_created": "Virtual environment created",
        "env_create_fail": "Failed to create virtual environment",
        "install_deps": "Installing dependencies",
        "deps_installed": "Dependencies installed",
        "deps_install_fail": "Failed to install dependencies",
        "no_req": "requirements.txt not found",
        "execution_record": "Execution record saved",
        "execution_summary": "Execution Summary",
        "execution_id": "Execution ID",
        "status": "Status",
        "step_label": "Step",
        "duration_sec": "s",
        "env_info": "Environment",
        "python_version": "Python",
        "cuda_available": "CUDA",
        "cuda_yes": "Available",
        "cuda_no": "Not available",
        "gpu_info": "GPU",
    },
    "zh": {
        "whitelist_warning": "警告: 白名单文件不存在",
        "empty_command": "空命令",
        "command_matches_forbidden": "命令匹配禁止模式",
        "invalid_command": "无效命令",
        "not_in_whitelist": "命令不在白名单中",
        "user_stop": "用户请求停止",
        "cancelled": "已取消",
        "stopped": "已停止（用户请求）",
        "no_command": "无命令",
        "whitelist_reject": "白名单拒绝",
        "step_cancelled": "已取消（用户请求停止）",
        "success": "成功",
        "failed": "失败",
        "env_create": "创建虚拟环境",
        "env_created": "虚拟环境创建成功",
        "env_create_fail": "创建虚拟环境失败",
        "install_deps": "安装依赖",
        "deps_installed": "依赖安装成功",
        "deps_install_fail": "安装依赖失败",
        "no_req": "requirements.txt 不存在",
        "execution_record": "执行记录已保存",
        "execution_summary": "执行摘要",
        "execution_id": "执行 ID",
        "status": "状态",
        "step_label": "步骤",
        "duration_sec": "秒",
        "env_info": "环境",
        "python_version": "Python",
        "cuda_available": "CUDA",
        "cuda_yes": "可用",
        "cuda_no": "不可用",
        "gpu_info": "GPU",
    }
}


class CommandValidator:
    """Command whitelist validator"""

    def __init__(self, whitelist_path: str):
        self.allowed_commands: List[str] = []
        self.forbidden_patterns: List[str] = []
        self._load_whitelist(whitelist_path)

    def _load_whitelist(self, path: str):
        """Load whitelist"""
        if not os.path.exists(path):
            print(f"{STRINGS['en']['whitelist_warning']}: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.allowed_commands = data.get("allowed_commands", [])
        self.forbidden_patterns = data.get("forbidden_patterns", [])

    def is_allowed(self, command: str) -> Tuple[bool, str]:
        """
        Validate if command is in whitelist
        Returns: (is_allowed, reason)
        """
        if not command:
            return False, STRINGS["en"]["empty_command"]

        # Check forbidden patterns
        for pattern in self.forbidden_patterns:
            if re.search(pattern, command, re.I):
                return False, f"{STRINGS['en']['command_matches_forbidden']}: {pattern}"

        # Check whitelist
        command_parts = command.split()
        if not command_parts:
            return False, STRINGS["en"]["invalid_command"]

        # Allow by prefix matching
        for allowed in self.allowed_commands:
            if command.startswith(allowed) or command == allowed:
                return True, "Whitelist allowed"

        # Allow standard script commands
        base_command = command_parts[0]
        if base_command in ["python", "python3", "bash", "sh"]:
            if len(command_parts) >= 2:
                next_part = command_parts[1]
                if next_part in ["train.py", "test.py", "eval.py", "inference.py",
                                 "preprocess.py", "prepare_data.py", "setup.py"]:
                    return True, "Standard script command"

        return False, f"{STRINGS['en']['not_in_whitelist']}: {command[:50]}..."


class ReproExecutor:
    """Reproduction executor with observability and circuit breaker protection"""

    def __init__(self, project_dir: str, whitelist_path: str, lang: str = "en"):
        self.project_dir = Path(project_dir)
        self.lang = lang if lang in ["en", "zh"] else "en"
        self.strings = STRINGS[self.lang]
        self.validator = CommandValidator(whitelist_path)
        self.env_dir = self.project_dir / "env"
        self.venv_python = self._detect_venv_python()

        # Initialize observability components
        self.logs_dir = self.project_dir / "claude_outputs" / "logs"
        self.logger: Optional[StructuredLogger] = None
        self.monitor: Optional[ResourceMonitor] = None
        self.tracker: Optional[ExecutionTracker] = None

        if OBSERVABILITY_AVAILABLE:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            self.logger = StructuredLogger(str(self.logs_dir), "run_repro")
            self.tracker = ExecutionTracker(str(self.project_dir / "claude_outputs"))
            self.monitor = ResourceMonitor(interval_seconds=5.0)

            # Add resource monitoring callback
            if self.tracker:
                self.monitor.add_callback(self.tracker.add_resource_snapshot)

        # Initialize circuit breaker
        self.circuit_breaker = None
        self.retry_executor = None
        self.rollback_manager = RollbackManager()

        if CIRCUIT_BREAKER_AVAILABLE:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0
            )
            self.retry_executor = RetryableExecutor(
                RetryPolicy(max_attempts=3, exponential_backoff=True)
            )

        self.result: Dict[str, Any] = {
            "step": "execution",
            "status": "partial",
            "execution_id": str(uuid.uuid4())[:8],
            "plan_reference": "",
            "steps_executed": [],
            "modifications_made": [],
            "env_state": {
                "python_version": "",
                "cuda_available": False,
                "gpu_info": None,
                "installed_packages": []
            },
            "timestamp": datetime.now().isoformat()
        }

    def _detect_venv_python(self) -> Optional[str]:
        """Detect virtual environment Python"""
        venv_python = self.env_dir / "Scripts" / "python.exe"  # Windows
        if venv_python.exists():
            return str(venv_python)

        venv_python = self.env_dir / "bin" / "python"  # Linux/Mac
        if venv_python.exists():
            return str(venv_python)

        return None

    def execute_plan(self, plan_path: str, start_step: int = 1) -> Dict[str, Any]:
        """Execute plan with observability and circuit breaker protection"""
        # Load plan
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)

        self.result["plan_reference"] = plan.get("plan_id", "unknown")

        if self.logger:
            self.logger.info("Starting plan execution", {
                "plan_id": plan.get("plan_id"),
                "start_step": start_step,
                "total_steps": len(plan.get("recommended_steps", []))
            })

        # Collect environment info
        self._collect_env_info()

        # Execute steps
        steps = plan.get("recommended_steps", [])
        for step in steps:
            # Check stop request
            if self._check_stop_requested():
                if self.logger:
                    self.logger.warning("Plan execution stopped by user request")
                self.result["status"] = "cancelled"
                break

            step_num = step.get("step_number", 0)
            if step_num < start_step:
                self.result["steps_executed"].append({
                    "step_number": step_num,
                    "action": step.get("action"),
                    "status": "skipped",
                    "command": None,
                    "skip_reason": "start_step"
                })
                continue

            self._execute_step(step)

            # Check if should stop
            last_status = self.result["steps_executed"][-1].get("status")
            if last_status == "failed" or last_status == "cancelled":
                break

        # Set final status
        executed = [s for s in self.result["steps_executed"] if s.get("status") not in ["skipped", "cancelled"]]
        if self.result["status"] == "cancelled":
            pass  # Keep cancelled status
        elif not executed:
            self.result["status"] = "failed"
        else:
            failed_count = sum(1 for s in executed if s.get("status") == "failed")
            if failed_count == 0:
                self.result["status"] = "success"
            elif failed_count == len(executed):
                self.result["status"] = "failed"
            else:
                self.result["status"] = "partial"

        if self.logger:
            self.logger.info("Plan execution completed", {
                "status": self.result["status"],
                "steps_executed": len(executed),
                "failed": sum(1 for s in executed if s.get("status") == "failed")
            })

        return self.result

    def _execute_step(self, step: Dict[str, Any]):
        """Execute single step with observability and circuit breaker protection"""
        step_num = step.get("step_number", 0)
        action = step.get("action", "unknown")
        command = step.get("command")

        # Check stop request
        if self._check_stop_requested():
            step_result = {
                "step_number": step_num,
                "action": action,
                "command": command,
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_seconds": 0,
                "exit_code": None,
                "status": "cancelled",
                "stdout": "",
                "stderr": "",
                "error_message": self.strings["user_stop"],
                "artifacts": []
            }
            self.result["steps_executed"].append(step_result)
            self.result["status"] = "cancelled"
            print(f"\n[Step {step_num}] {action} - {self.strings['step_cancelled']}")
            return

        print(f"\n[Step {step_num}] {action}")

        # Start resource monitoring
        if self.monitor:
            self.monitor.start()

        # Start tracking
        if self.tracker:
            self.tracker.start_step(f"step_{step_num}", step_num, action)

        step_result = {
            "step_number": step_num,
            "action": action,
            "command": command,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "duration_seconds": 0,
            "exit_code": None,
            "status": "failed",
            "stdout": "",
            "stderr": "",
            "error_message": None,
            "artifacts": []
        }

        if not command:
            step_result["status"] = "skipped"
            step_result["error_message"] = self.strings["no_command"]
            self.result["steps_executed"].append(step_result)
            return

        # Validate command
        is_allowed, reason = self.validator.is_allowed(command)
        if not is_allowed:
            step_result["error_message"] = f"Command not approved by whitelist: {reason}"
            print(f"  [REJECT] Whitelist: {reason}")
            if self.logger:
                self.logger.warning(f"Command rejected by whitelist", {"command": command[:50], "reason": reason})
            self.result["steps_executed"].append(step_result)
            return

        # Execute command with circuit breaker and retry
        start_time = datetime.now()
        exec_success = False
        try:
            # Use virtual environment Python if available
            exec_command = command
            if self.venv_python and ("pip install" in command or "python " in command):
                if "pip install" in command:
                    exec_command = f"{self.venv_python} -m pip install" + command.split("pip install")[1]
                elif command.startswith("python "):
                    exec_command = command.replace("python ", f"{self.venv_python} ")

            # Use retry executor
            if self.retry_executor:
                cb_result = self.retry_executor.execute(
                    self._run_command,
                    exec_command,
                    cwd=str(self.project_dir / "repo")
                )
                if cb_result.success:
                    proc_returncode, proc_stdout, proc_stderr = cb_result.result
                    exec_success = True
                else:
                    step_result["error_message"] = cb_result.error
                    if self.logger:
                        self.logger.error(f"Command failed after {cb_result.attempts} attempts", {"error": cb_result.error})
            else:
                # Direct execution
                proc_returncode, proc_stdout, proc_stderr = self._run_command(
                    exec_command,
                    cwd=str(self.project_dir / "repo")
                )
                exec_success = (proc_returncode == 0)

            step_result["exit_code"] = proc_returncode
            step_result["stdout"] = proc_stdout[:10000] if proc_stdout else ""
            step_result["stderr"] = proc_stderr[:5000] if proc_stderr else ""

            if exec_success:
                step_result["status"] = "success"
                print(f"  [OK] Success ({proc_returncode})")
                if self.logger:
                    self.logger.info(f"Step {step_num} succeeded", {"action": action, "duration": step_result["duration_seconds"]})
            else:
                step_result["status"] = "failed"
                step_result["error_message"] = f"Command failed: exit code {proc_returncode}"
                print(f"  [FAIL] Exit code {proc_returncode}")

        except Exception as e:
            step_result["error_message"] = f"Execution exception: {str(e)}"
            print(f"  [ERROR] {str(e)}")
            if self.logger:
                self.logger.error(f"Step {step_num} exception", {"error": str(e), "action": action})

        # Stop resource monitoring
        if self.monitor:
            self.monitor.stop()

        # Complete tracking
        if self.tracker:
            self.tracker.complete_step(
                status=step_result["status"],
                error_message=step_result.get("error_message")
            )

        end_time = datetime.now()
        step_result["end_time"] = end_time.isoformat()
        step_result["duration_seconds"] = (end_time - start_time).total_seconds()

        self.result["steps_executed"].append(step_result)

    def _run_command(self, command: str, cwd: str) -> Tuple[int, str, str]:
        """Run command and return results"""
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        return proc.returncode, proc.stdout, proc.stderr

    def _check_stop_requested(self) -> bool:
        """Check if stop is requested"""
        stop_file = self.project_dir / "claude_outputs" / ".stop_requested"
        return stop_file.exists()

    def _collect_env_info(self):
        """Collect environment information"""
        # Python version
        try:
            result = subprocess.run(
                ["python", "--version"],
                capture_output=True, text=True
            )
            self.result["env_state"]["python_version"] = result.stdout.strip()
        except:
            pass

        # CUDA availability
        try:
            result = subprocess.run(
                ["python", "-c", "import torch; print(torch.cuda.is_available())"],
                capture_output=True, text=True
            )
            self.result["env_state"]["cuda_available"] = "True" in result.stdout
        except:
            pass

        # GPU info
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.result["env_state"]["gpu_info"] = result.stdout.strip()
        except:
            pass

    def create_venv(self) -> bool:
        """Create virtual environment"""
        print(f"\n[{self.strings['env_create']}]...")

        try:
            # Create virtual environment
            result = subprocess.run(
                ["python", "-m", "venv", str(self.env_dir)],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode == 0:
                print(f"  [OK] {self.strings['env_created']}")
                self.venv_python = self._detect_venv_python()
                return True
            else:
                print(f"  [FAIL] {self.strings['env_create_fail']}: {result.stderr}")
                return False

        except Exception as e:
            print(f"  [FAIL] {self.strings['env_create_fail']}: {str(e)}")
            return False

    def install_requirements(self, requirements_path: str = "requirements.txt") -> bool:
        """Install dependencies"""
        repo_req = self.project_dir / "repo" / requirements_path

        if not repo_req.exists():
            print(f"  {self.strings['no_req']}: {repo_req}")
            return False

        print(f"\n[{self.strings['install_deps']}]...")

        try:
            pip_cmd = f"{self.venv_python} -m pip install -r {repo_req}"
            result = subprocess.run(
                pip_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes
            )

            if result.returncode == 0:
                print(f"  [OK] {self.strings['deps_installed']}")
                # Record installed packages
                self.result["env_state"]["installed_packages"] = [
                    line.strip() for line in result.stdout.split("\n")
                    if "Successfully installed" in line
                ]
                return True
            else:
                print(f"  [FAIL] {self.strings['deps_install_fail']}: {result.stderr[:500]}")
                return False

        except Exception as e:
            print(f"  [FAIL] {self.strings['deps_install_fail']}: {str(e)}")
            return False


def main():
    parser = argparse.ArgumentParser(description="RSCDAgent - Reproduction Execution Module")
    parser.add_argument("--plan", "-p", required=True, help="Execution plan JSON path")
    parser.add_argument("--project_dir", "-d", required=True, help="Project root directory")
    parser.add_argument("--whitelist", "-w", default="./config/allowed_commands.yaml",
                        help="Command whitelist file")
    parser.add_argument("--step", "-s", type=int, default=1,
                        help="Starting step number (default: 1)")
    parser.add_argument("--output_dir", "-o", default="./claude_outputs",
                        help="Output directory")
    parser.add_argument("--lang", "-l", default="en", choices=["en", "zh"],
                        help="Output language (en/zh)")

    args = parser.parse_args()

    s = STRINGS[args.lang]

    print("=" * 50)
    print("RSCDAgent Reproduction Executor" if args.lang == "en" else "RSCDAgent 复现执行器")
    print("=" * 50)

    # Initialize executor
    executor = ReproExecutor(args.project_dir, args.whitelist, args.lang)

    # Optional: create venv and install dependencies
    if args.step <= 1:
        executor.create_venv()
        executor.install_requirements()

    # Execute plan
    result = executor.execute_plan(args.plan, args.step)

    # Save results
    output_path = os.path.join(args.output_dir, "step5_execution.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] {s['execution_record']}: {output_path}")

    # Print summary
    print("\n" + "=" * 50)
    print(s['execution_summary'])
    print("=" * 50)
    print(f"{s['execution_id']}: {result['execution_id']}")
    print(f"{s['status']}: {result['status']}")

    status_icon = {"success": "[OK]", "failed": "[FAIL]", "skipped": "[SKIP]", "partial": "[PARTIAL]", "cancelled": "[CANCEL]"}
    for step in result["steps_executed"]:
        icon = status_icon.get(step.get("status"), "[?]")
        duration = step.get('duration_seconds', 0)
        print(f"  {icon} {s['step_label']} {step['step_number']}: {step['action']} ({duration:.1f}{s['duration_sec']})")

    print(f"\n{s['env_info']}:")
    print(f"  {s['python_version']}: {result['env_state']['python_version']}")
    cuda_status = s['cuda_yes'] if result['env_state']['cuda_available'] else s['cuda_no']
    print(f"  {s['cuda_available']}: {cuda_status}")
    if result['env_state']['gpu_info']:
        print(f"  {s['gpu_info']}: {result['env_state']['gpu_info']}")

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
