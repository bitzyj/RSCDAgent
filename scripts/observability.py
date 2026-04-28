#!/usr/bin/env python3
"""
observability.py - 可观测性模块

提供：
- 结构化日志输出
- 执行状态实时追踪
- 资源消耗监控

用法:
    from observability import Logger, Monitor, ExecutionTracker
"""

import json
import os
import psutil
import time
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str
    level: str
    component: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class ResourceSnapshot:
    """资源快照"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    gpu_used_mb: float = 0.0
    gpu_percent: float = 0.0


@dataclass
class StepExecution:
    """步骤执行记录"""
    step_id: str
    step_number: int
    action: str
    status: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    retry_count: int = 0
    error_message: Optional[str] = None
    resource_snapshots: List[Dict] = field(default_factory=list)


class StructuredLogger:
    """结构化日志记录器"""

    def __init__(self, log_dir: str, component: str = "RSCDAgent"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.component = component
        self.trace_id: Optional[str] = None
        self._lock = threading.Lock()

        # 创建日志文件
        self.log_file = self.log_dir / f"{component}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    def set_trace_id(self, trace_id: str):
        """设置追踪ID"""
        self.trace_id = trace_id

    def _write(self, level: LogLevel, message: str, data: Dict = None):
        """写入日志"""
        entry = LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level.value,
            component=self.component,
            message=message,
            data=data or {},
            trace_id=self.trace_id
        )

        with self._lock:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")

    def debug(self, message: str, data: Dict = None):
        self._write(LogLevel.DEBUG, message, data)

    def info(self, message: str, data: Dict = None):
        self._write(LogLevel.INFO, message, data)

    def warning(self, message: str, data: Dict = None):
        self._write(LogLevel.WARNING, message, data)

    def error(self, message: str, data: Dict = None):
        self._write(LogLevel.ERROR, message, data)

    def critical(self, message: str, data: Dict = None):
        self._write(LogLevel.CRITICAL, message, data)


class ResourceMonitor:
    """资源消耗监控器"""

    def __init__(self, interval_seconds: float = 5.0):
        self.interval = interval_seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._snapshots: List[ResourceSnapshot] = []
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[ResourceSnapshot], None]] = []

    def start(self):
        """启动监控"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    def add_callback(self, callback: Callable[[ResourceSnapshot], None]):
        """添加监控回调"""
        self._callbacks.append(callback)

    def get_snapshots(self) -> List[ResourceSnapshot]:
        """获取所有快照"""
        with self._lock:
            return list(self._snapshots)

    def get_current_snapshot(self) -> ResourceSnapshot:
        """获取当前资源状态"""
        return self._take_snapshot()

    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            snapshot = self._take_snapshot()

            with self._lock:
                self._snapshots.append(snapshot)

            # 调用回调
            for callback in self._callbacks:
                try:
                    callback(snapshot)
                except Exception:
                    pass

            time.sleep(self.interval)

    def _take_snapshot(self) -> ResourceSnapshot:
        """采集资源快照"""
        # CPU 和内存
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)

        # GPU (如果可用)
        gpu_used_mb = 0.0
        gpu_percent = 0.0
        try:
            import torch
            if torch.cuda.is_available():
                gpu_memory = torch.cuda.memory_allocated() / (1024 * 1024)
                gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
                gpu_used_mb = gpu_memory
                gpu_percent = (gpu_memory / gpu_total * 100) if gpu_total > 0 else 0
        except:
            pass

        return ResourceSnapshot(
            timestamp=datetime.now().isoformat(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            gpu_used_mb=gpu_used_mb,
            gpu_percent=gpu_percent
        )


class ExecutionTracker:
    """执行状态追踪器"""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.output_dir / "execution_status.json"
        self.steps: List[StepExecution] = []
        self.current_step_index: int = -1
        self._lock = threading.Lock()
        self._load_status()

    def _load_status(self):
        """加载已有状态"""
        if self.status_file.exists():
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.steps = [StepExecution(**s) for s in data.get("steps", [])]
                    self.current_step_index = data.get("current_step_index", -1)
            except:
                pass

    def _save_status(self):
        """保存状态"""
        data = {
            "current_step_index": self.current_step_index,
            "updated_at": datetime.now().isoformat(),
            "steps": [asdict(s) for s in self.steps]
        }
        with open(self.status_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def start_step(self, step_id: str, step_number: int, action: str):
        """开始步骤"""
        with self._lock:
            step = StepExecution(
                step_id=step_id,
                step_number=step_number,
                action=action,
                status=ExecutionStatus.RUNNING.value,
                start_time=datetime.now().isoformat()
            )
            self.steps.append(step)
            self.current_step_index = len(self.steps) - 1
            self._save_status()

    def complete_step(self, status: str = ExecutionStatus.SUCCESS.value, error_message: str = None):
        """完成步骤"""
        with self._lock:
            if self.current_step_index >= 0 and self.current_step_index < len(self.steps):
                step = self.steps[self.current_step_index]
                step.status = status
                step.end_time = datetime.now().isoformat()
                step.error_message = error_message
                if step.start_time:
                    start = datetime.fromisoformat(step.start_time)
                    step.duration_seconds = (datetime.now() - start).total_seconds()
                self._save_status()

    def retry_step(self):
        """重试步骤"""
        with self._lock:
            if self.current_step_index >= 0 and self.current_step_index < len(self.steps):
                step = self.steps[self.current_step_index]
                step.status = ExecutionStatus.RETRYING.value
                step.retry_count += 1
                self._save_status()

    def add_resource_snapshot(self, snapshot: ResourceSnapshot):
        """添加资源快照"""
        with self._lock:
            if self.current_step_index >= 0 and self.current_step_index < len(self.steps):
                self.steps[self.current_step_index].resource_snapshots.append(asdict(snapshot))

    def get_current_status(self) -> Dict:
        """获取当前状态"""
        with self._lock:
            if self.current_step_index >= 0 and self.current_step_index < len(self.steps):
                step = self.steps[self.current_step_index]
                return {
                    "status": step.status,
                    "action": step.action,
                    "step_number": step.step_number,
                    "duration_seconds": step.duration_seconds,
                    "retry_count": step.retry_count
                }
            return {"status": ExecutionStatus.PENDING.value, "action": None, "step_number": -1}

    def get_all_steps(self) -> List[Dict]:
        """获取所有步骤"""
        with self._lock:
            return [asdict(s) for s in self.steps]


# CLI 工具函数
def get_tracker_status(output_dir: str) -> Dict:
    """获取追踪状态"""
    tracker = ExecutionTracker(output_dir)
    return {
        "current": tracker.get_current_status(),
        "steps": tracker.get_all_steps()
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python observability.py <output_dir>")
        sys.exit(1)

    # 测试
    tracker = ExecutionTracker(sys.argv[1])

    print("开始测试...")
    tracker.start_step("step_1", 1, "准备环境")

    monitor = ResourceMonitor(interval_seconds=1.0)
    monitor.start()

    import time
    time.sleep(3)

    monitor.stop()
    tracker.complete_step()

    print(json.dumps(get_tracker_status(sys.argv[1]), indent=2, ensure_ascii=False))
