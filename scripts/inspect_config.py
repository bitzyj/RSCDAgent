#!/usr/bin/env python3
"""
inspect_config.py - 配置文件解析模块

解析训练配置文件，提取：
- 数据集路径和参数
- 模型超参数
- 训练策略
- 评估参数

用法:
    python inspect_config.py --config <CONFIG_PATH> --config_type <TYPE>

支持格式: YAML, JSON, TOML
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Union


class ConfigInspector:
    """配置文件解析器"""

    def __init__(self, config_path: str, config_type: Optional[str] = None):
        self.config_path = Path(config_path)
        self.config_type = config_type or self._detect_type()
        self.config_data: Dict[str, Any] = {}
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def _detect_type(self) -> str:
        """检测配置文件类型"""
        ext = self.config_path.suffix.lower()
        if ext in [".yaml", ".yml"]:
            return "yaml"
        elif ext == ".json":
            return "json"
        elif ext == ".toml":
            return "toml"
        elif ext == ".py":
            return "python"
        return "unknown"

    def parse(self) -> Dict[str, Any]:
        """解析配置文件"""
        if not self.config_path.exists():
            self.errors.append(f"配置文件不存在: {self.config_path}")
            return {"error": str(self.errors)}

        try:
            if self.config_type == "yaml":
                self._parse_yaml()
            elif self.config_type == "json":
                self._parse_json()
            elif self.config_type == "toml":
                self._parse_toml()
            elif self.config_type == "python":
                self._parse_python()
            else:
                self.errors.append(f"不支持的配置文件类型: {self.config_type}")
        except Exception as e:
            self.errors.append(f"解析失败: {str(e)}")

        return self.get_structured_config()

    def _parse_yaml(self):
        """解析 YAML 文件"""
        try:
            import yaml
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = yaml.safe_load(f) or {}
        except ImportError:
            # 简单解析
            self._simple_yaml_parse()
        except Exception as e:
            self.errors.append(f"YAML 解析失败: {str(e)}")

    def _simple_yaml_parse(self):
        """简单 YAML 解析（无 pyyaml 库时）"""
        with open(self.config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        data = {}
        current_key = None
        current_list = []
        indent_level = 0

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # 列表项
            if stripped.startswith("-"):
                value = stripped[1:].strip()
                if current_key:
                    if current_key not in data:
                        data[current_key] = []
                    try:
                        data[current_key].append(self._parse_value(value))
                    except:
                        data[current_key].append(value)
                continue

            # 键值对
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()

                if value:
                    try:
                        data[key] = self._parse_value(value)
                    except:
                        data[key] = value
                else:
                    current_key = key
                    data[key] = {}

        self.config_data = data

    def _parse_value(self, value: str) -> Union[str, int, float, bool]:
        """解析 YAML 值"""
        value = value.strip()

        # 布尔值
        if value.lower() in ["true", "yes", "on"]:
            return True
        if value.lower() in ["false", "no", "off"]:
            return False

        # 数字
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # 字符串（去除引号）
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]

        return value

    def _parse_json(self):
        """解析 JSON 文件"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON 解析失败: {str(e)}")

    def _parse_toml(self):
        """解析 TOML 文件"""
        try:
            import toml
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config_data = toml.load(f)
        except ImportError:
            self.errors.append("未安装 toml 库")
        except Exception as e:
            self.errors.append(f"TOML 解析失败: {str(e)}")

    def _parse_python(self):
        """解析 Python 配置文件"""
        import sys
        import importlib.util

        try:
            spec = importlib.util.spec_from_file_location("config", self.config_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules["config"] = module
                spec.loader.exec_module(module)

                # 提取配置变量
                for name in dir(module):
                    if not name.startswith("_"):
                        value = getattr(module, name)
                        if not callable(value):
                            self.config_data[name] = value
        except Exception as e:
            self.errors.append(f"Python 配置解析失败: {str(e)}")

    def get_structured_config(self) -> Dict[str, Any]:
        """获取结构化配置"""
        config = {
            "config_path": str(self.config_path),
            "config_type": self.config_type,
            "dataset": {},
            "model": {},
            "training": {},
            "evaluation": {},
            "others": {}
        }

        if self.errors:
            config["errors"] = self.errors
            return config

        # 提取数据集配置
        config["dataset"] = self._extract_dataset_config()

        # 提取模型配置
        config["model"] = self._extract_model_config()

        # 提取训练配置
        config["training"] = self._extract_training_config()

        # 提取评估配置
        config["evaluation"] = self._extract_evaluation_config()

        # 其他配置
        all_keys = set()
        for section in ["dataset", "model", "training", "evaluation"]:
            all_keys.update(config[section].keys())

        for key, value in self.config_data.items():
            if key not in all_keys:
                config["others"][key] = value

        config["warnings"] = self.warnings
        return config

    def _extract_dataset_config(self) -> Dict[str, Any]:
        """提取数据集配置"""
        dataset_keys = [
            "dataset_name", "dataset", "data_root", "data_dir", "root",
            "train_data", "val_data", "test_data", "train_dir", "val_dir", "test_dir",
            "train_list", "val_list", "test_list",
            "num_classes", "classes", "bands", "input_size", "crop_size",
            "batch_size", "num_workers", "prefetch",
        ]

        dataset_config = {}
        for key in dataset_keys:
            if key in self.config_data:
                dataset_config[key] = self.config_data[key]

        # 规范化键名
        if "data_root" in self.config_data:
            dataset_config["data_root"] = self.config_data["data_root"]
        if "root" in self.config_data:
            dataset_config["data_root"] = self.config_data.get("root", self.config_data["root"])

        return dataset_config

    def _extract_model_config(self) -> Dict[str, Any]:
        """提取模型配置"""
        model_keys = [
            "model", "model_name", "architecture", "backbone", "encoder",
            "in_channels", "input_channels", "bands", "num_classes", "classes",
            "pretrained", "pretrained_path", "checkpoint",
            "embed_dim", "depth", "num_heads", "mlp_ratio",
            "dropout", "drop_path_rate",
        ]

        model_config = {}
        for key in model_keys:
            if key in self.config_data:
                model_config[key] = self.config_data[key]

        return model_config

    def _extract_training_config(self) -> Dict[str, Any]:
        """提取训练配置"""
        training_keys = [
            "epochs", "epoch", "max_epochs",
            "batch_size", "batch_size_per_gpu",
            "optimizer", "lr", "learning_rate", "init_lr",
            "weight_decay", "momentum",
            "scheduler", "lr_scheduler", "lr_schedule",
            "step_size", "gamma", "milestones",
            "loss", "loss_function", "criterion",
            "warmup", "warmup_epochs",
            "seed", "random_seed",
            "logging", "log_interval", "print_freq",
            "save_interval", "save_freq",
        ]

        training_config = {}
        for key in training_keys:
            if key in self.config_data:
                training_config[key] = self.config_data[key]

        # 规范化
        if "epoch" in self.config_data and "epochs" not in self.config_data:
            training_config["epochs"] = self.config_data["epoch"]
        if "init_lr" in self.config_data and "lr" not in self.config_data:
            training_config["lr"] = self.config_data["init_lr"]

        return training_config

    def _extract_evaluation_config(self) -> Dict[str, Any]:
        """提取评估配置"""
        eval_keys = [
            "test", "testing", "eval", "evaluation",
            "test_epoch", "test_interval",
            "metrics", "metric", "score",
            "visualize", "vis", "save_vis",
            "output_dir", "result_dir", "save_dir",
        ]

        eval_config = {}
        for key in eval_keys:
            if key in self.config_data:
                eval_config[key] = self.config_data[key]

        return eval_config

    def extract_commands(self) -> Dict[str, Optional[str]]:
        """从配置中提取推荐命令"""
        commands = {
            "train_command": None,
            "test_command": None,
        }

        # 构建训练命令
        train_parts = ["python", "train.py"]

        # 添加配置参数
        config_name = self.config_path.name
        if self.config_type == "yaml":
            train_parts.append(f"--config {config_name}")
        elif self.config_type == "json":
            train_parts.append(f"--config {config_name}")

        # 检查是否有其他必要参数
        if "data_root" in self.config_data:
            pass  # 可能在配置文件中指定了

        commands["train_command"] = " ".join(train_parts)

        # 构建测试命令
        test_parts = ["python", "test.py"]
        if self.config_type == "yaml":
            test_parts.append(f"--config {config_name}")
        elif self.config_type == "json":
            test_parts.append(f"--config {config_name}")

        if "checkpoint" in self.config_data:
            test_parts.append(f"--checkpoint {self.config_data['checkpoint']}")

        commands["test_command"] = " ".join(test_parts)

        return commands


def main():
    parser = argparse.ArgumentParser(
        description="RSCDAgent - 配置文件解析模块"
    )
    parser.add_argument(
        "--config", "-c",
        required=True,
        help="配置文件路径"
    )
    parser.add_argument(
        "--config_type", "-t",
        choices=["yaml", "json", "toml", "python", "auto"],
        default="auto",
        help="配置文件类型 (default: auto)"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径 (可选)"
    )

    args = parser.parse_args()

    # 解析配置
    inspector = ConfigInspector(args.config, args.config_type if args.config_type != "auto" else None)
    result = inspector.parse()

    # 提取推荐命令
    commands = inspector.extract_commands()
    result["recommended_commands"] = commands

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✓ 输出: {args.output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
