#!/usr/bin/env python3
"""
generate_plan.py - 实验计划生成模块

根据论文解析、仓库解析、数据集检查结果，生成复现执行计划。

输入:
- step1_paper_parse.json  (论文信息)
- step2_repo_parse.json   (仓库信息)
- step3_dataset_check.json (数据集检查结果)

输出:
- step4_plan.json (执行计划)

用法:
    python generate_plan.py --inputs_dir <DIR> --output_dir <DIR>
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class PlanGenerator:
    """复现计划生成器"""

    def __init__(self, inputs_dir: str):
        self.inputs_dir = Path(inputs_dir)
        self.paper_info: Dict[str, Any] = {}
        self.repo_info: Dict[str, Any] = {}
        self.dataset_check: Dict[str, Any] = {}

        self.result: Dict[str, Any] = {
            "step": "generate_plan",
            "status": "success",
            "plan_id": str(uuid.uuid4())[:8],
            "recommended_steps": [],
            "execution_order": [],
            "critical_risks": [],
            "required_modifications": [],
            "estimated_total_time": "unknown",
            "dry_run_recommended": True,
            "test_only_mode": {
                "supported": True,
                "command": None,
                "limitations": None
            },
            "timestamp": datetime.now().isoformat()
        }

    def load_inputs(self) -> bool:
        """加载输入文件"""
        # 加载论文解析结果
        step1_path = self.inputs_dir / "step1_paper_parse.json"
        if step1_path.exists():
            with open(step1_path, "r", encoding="utf-8") as f:
                self.paper_info = json.load(f)
        else:
            print(f"警告: 未找到 {step1_path}")

        # 加载仓库解析结果
        step2_path = self.inputs_dir / "step2_repo_parse.json"
        if step2_path.exists():
            with open(step2_path, "r", encoding="utf-8") as f:
                self.repo_info = json.load(f)
        else:
            print(f"警告: 未找到 {step2_path}")

        # 加载数据集检查结果
        step3_path = self.inputs_dir / "step3_dataset_check.json"
        if step3_path.exists():
            with open(step3_path, "r", encoding="utf-8") as f:
                self.dataset_check = json.load(f)
        else:
            print(f"警告: 未找到 {step3_path}")

        return bool(self.paper_info and self.repo_info)

    def generate(self) -> Dict[str, Any]:
        """生成执行计划"""
        if not self.paper_info:
            self.result["status"] = "failed"
            self.result["critical_risks"].append({
                "risk": "论文信息不可用",
                "mitigation": "请先运行 parse_paper.py",
                "fallback": "手动提供论文信息"
            })
            return self.result

        # 分析输入
        self._analyze_paper()
        self._analyze_repo()
        self._analyze_dataset()

        # 生成步骤
        self._generate_steps()

        # 计算估计时间
        self._estimate_time()

        # 设置 test-only 模式
        self._setup_test_only()

        return self.result

    def _analyze_paper(self):
        """分析论文信息"""
        self.model_name = self.paper_info.get("model_info", {}).get("model_name", "Unknown")
        self.epochs = self.paper_info.get("training_config", {}).get("epochs", 200)
        self.batch_size = self.paper_info.get("training_config", {}).get("batch_size", 16)
        self.target_metrics = self.paper_info.get("target_metrics", {}).get("metrics", [])

    def _analyze_repo(self):
        """分析仓库信息"""
        self.train_entry = self.repo_info.get("entry_points", {}).get("train", {})
        self.test_entry = self.repo_info.get("entry_points", {}).get("test", {})
        self.config_files = self.repo_info.get("config_files", [])
        self.checkpoint_info = self.repo_info.get("checkpoint_info", {})
        self.has_checkpoints = bool(self.checkpoint_info.get("download_url") or
                                     self.checkpoint_info.get("local_checkpoints"))

    def _analyze_dataset(self):
        """分析数据集检查结果"""
        self.dataset_reproducible = self.dataset_check.get("summary", {}).get("reproducible", True)
        self.dataset_status = self.dataset_check.get("status", "unknown")
        self.pairing_ok = self.dataset_check.get("pairing_checks", {}).get("a_b_matched", False)

    def _generate_steps(self):
        """生成执行步骤"""
        steps = []
        step_num = 1

        # Step 1: 环境准备
        steps.append(self._create_step(
            step_num,
            "准备环境",
            "创建 Python 虚拟环境并安装依赖",
            f"python -m venv env && source env/bin/activate && pip install -r requirements.txt",
            "venv 目录创建成功，依赖安装完成",
            "low"
        ))
        step_num += 1

        # Step 2: 数据准备
        if not self.dataset_reproducible:
            steps.append(self._create_step(
                step_num,
                "修复数据集问题",
                "根据数据集检查结果修复问题",
                None,
                "数据集问题已解决",
                "high"
            ))
            step_num += 1

        steps.append(self._create_step(
            step_num,
            "准备数据集",
            "链接或复制数据集到正确位置",
            f"mkdir -p datasets && ln -s <dataset_path> datasets/LEVIR",
            "数据集路径配置正确",
            "low"
        ))
        step_num += 1

        # Step 3: Dry-run 验证
        config_path = self._find_config()
        dry_run_cmd = f"python {self.train_entry.get('main_file', 'train.py')} --config {config_path} --dry_run"
        steps.append(self._create_step(
            step_num,
            "Dry-run 验证",
            "验证代码和配置可以正常加载",
            dry_run_cmd,
            "配置文件加载成功，模型可以初始化",
            "low"
        ))
        step_num += 1

        # Step 4: Test-only (如果有 checkpoint)
        if self.has_checkpoints:
            checkpoint_path = self.checkpoint_info.get("local_checkpoints", ["checkpoints/BIT_LEVIR.pth"])[0]
            test_cmd = f"python {self.test_entry.get('main_file', 'test.py')} --config {config_path} --checkpoint {checkpoint_path}"
            steps.append(self._create_step(
                step_num,
                "Test-only 模式",
                "使用预训练权重快速验证",
                test_cmd,
                "测试完成，输出预测结果",
                "low"
            ))
            step_num += 1

        # Step 5: 完整训练 (可选)
        train_cmd = f"python {self.train_entry.get('main_file', 'train.py')} --config {config_path}"
        steps.append(self._create_step(
            step_num,
            "完整训练",
            "训练模型直到收敛或达到目标 epochs",
            train_cmd,
            "训练完成，模型收敛",
            "medium",
            stop_condition="loss 不下降超过 10 个 epoch",
            retry_condition="调整学习率或 batch size"
        ))
        step_num += 1

        # Step 6: 评估
        eval_cmd = f"python {self.test_entry.get('main_file', 'test.py')} --config {config_path} --checkpoint checkpoints/best.pth"
        steps.append(self._create_step(
            step_num,
            "评估与对比",
            "在测试集上评估并与论文目标对比",
            eval_cmd,
            "评估完成，输出指标对比表",
            "low"
        ))

        self.result["recommended_steps"] = steps
        self.result["execution_order"] = list(range(1, len(steps) + 1))

    def _create_step(self, step_number: int, action: str, description: str,
                     command: Optional[str], expected_output: str,
                     risk_level: str, stop_condition: Optional[str] = None,
                     retry_condition: Optional[str] = None) -> Dict[str, Any]:
        """创建单个步骤"""
        step = {
            "step_number": step_number,
            "action": action,
            "description": description,
            "command": command,
            "config_modifications": [],
            "expected_output": expected_output,
            "risk_level": risk_level,
            "stop_condition": stop_condition,
            "retry_condition": retry_condition,
            "estimated_time": self._estimate_step_time(action)
        }

        # 检查是否需要配置修改
        if "config" in action.lower() or "train" in action.lower():
            config_path = self._find_config()
            if config_path:
                step["config_modifications"].append({
                    "file": config_path,
                    "field": "data_root",
                    "current_value": "unknown",
                    "recommended_value": "<dataset_path>",
                    "reason": "需要指定正确的本地数据集路径"
                })

        return step

    def _find_config(self) -> Optional[str]:
        """查找配置文件路径"""
        for cfg in self.config_files:
            if cfg.get("purpose") == "training":
                return cfg.get("path", "configs/BIT-LEVIR.yaml")
        return "configs/BIT-LEVIR.yaml"

    def _estimate_step_time(self, action: str) -> str:
        """估算单步时间"""
        if "环境" in action:
            return "5-10min"
        elif "数据集" in action:
            return "1-5min"
        elif "Dry-run" in action:
            return "1-2min"
        elif "Test-only" in action:
            return "5-10min"
        elif "完整训练" in action:
            return f"{self.epochs * 2 // 60}h-{self.epochs * 5 // 60}h"
        elif "评估" in action:
            return "5-10min"
        return "unknown"

    def _estimate_time(self):
        """估算总时间"""
        if "完整训练" in [s["action"] for s in self.result["recommended_steps"]]:
            self.result["estimated_total_time"] = f"{self.epochs * 3 // 60}h"
        else:
            self.result["estimated_total_time"] = "10-30min"

    def _setup_test_only(self):
        """设置 test-only 模式"""
        if self.has_checkpoints:
            config_path = self._find_config()
            checkpoint_path = self.checkpoint_info.get("local_checkpoints", ["checkpoints/BIT_LEVIR.pth"])[0]
            self.result["test_only_mode"] = {
                "supported": True,
                "command": f"python {self.test_entry.get('main_file', 'test.py')} --config {config_path} --checkpoint {checkpoint_path}",
                "limitations": ["需要下载预训练权重"]
            }
        else:
            self.result["test_only_mode"] = {
                "supported": False,
                "command": None,
                "limitations": ["无预训练权重，需完整训练"]
            }

        # 添加关键风险
        if not self.dataset_reproducible:
            self.result["critical_risks"].append({
                "risk": "数据集存在问题",
                "mitigation": "先修复数据集问题",
                "fallback": "使用其他数据集或手动整理"
            })

        if not self.has_checkpoints and self.epochs > 100:
            self.result["critical_risks"].append({
                "risk": "无预训练权重，需要完整训练",
                "mitigation": "准备 GPU 资源",
                "fallback": "使用小规模数据验证流程"
            })


def main():
    parser = argparse.ArgumentParser(description="RSCDAgent - 计划生成模块")
    parser.add_argument("--inputs_dir", "-i", default="./claude_outputs",
                        help="输入目录 (包含 step1-3 JSON)")
    parser.add_argument("--output_dir", "-o", default="./claude_outputs",
                        help="输出目录")
    parser.add_argument("--paper_json", "-p", default=None,
                        help="论文解析结果 JSON (可选)")
    parser.add_argument("--repo_json", "-r", default=None,
                        help="仓库解析结果 JSON (可选)")
    parser.add_argument("--dataset_json", "-d", default=None,
                        help="数据集检查结果 JSON (可选)")

    args = parser.parse_args()

    # 如果提供了单独的文件路径，更新 inputs_dir
    if args.paper_json or args.repo_json or args.dataset_json:
        # 使用临时合并逻辑
        combined = {}
        if args.paper_json and os.path.exists(args.paper_json):
            with open(args.paper_json, "r") as f:
                combined["step1"] = json.load(f)
        if args.repo_json and os.path.exists(args.repo_json):
            with open(args.repo_json, "r") as f:
                combined["step2"] = json.load(f)
        if args.dataset_json and os.path.exists(args.dataset_json):
            with open(args.dataset_json, "r") as f:
                combined["step3"] = json.load(f)

        import tempfile
        temp_dir = tempfile.mkdtemp()
        for key, data in combined.items():
            path = os.path.join(temp_dir, f"{key}_paper_parse.json" if key == "step1" else f"{key}_repo_parse.json" if key == "step2" else f"{key}_dataset_check.json")
            with open(path, "w") as f:
                json.dump(data, f)
        inputs_dir = temp_dir
    else:
        inputs_dir = args.inputs_dir

    print(f"从 {inputs_dir} 加载输入...")

    # 生成计划
    generator = PlanGenerator(inputs_dir)
    if not generator.load_inputs():
        print("错误: 未能加载必要的输入文件")
        return 1

    result = generator.generate()

    # 保存
    output_path = os.path.join(args.output_dir, "step4_plan.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✓ 计划已保存: {output_path}")
    print(f"  计划 ID: {result['plan_id']}")
    print(f"  步骤数: {len(result['recommended_steps'])}")
    print(f"  估计时间: {result['estimated_total_time']}")
    print(f"  Test-only: {'支持' if result['test_only_mode']['supported'] else '不支持'}")

    if result["critical_risks"]:
        print("\n关键风险:")
        for risk in result["critical_risks"]:
            print(f"  - {risk['risk']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
