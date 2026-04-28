#!/usr/bin/env python3
"""
inspect_repo.py - 仓库解析模块

解析 GitHub 仓库结构，提取：
- 入口脚本（训练、测试、推理）
- 配置文件位置
- 数据集配置
- checkpoint 下载信息
- 指标计算逻辑
- 依赖信息

输出: claude_outputs/step2_repo_parse.json

用法:
    python inspect_repo.py --repo_path <REPO_PATH> --output_dir <DIR>
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class RepoInspector:
    """仓库解析器"""

    # 常见的训练入口文件
    TRAIN_PATTERNS = [
        "train.py",
        "train.py",
        "main.py",
        "run_train.py",
        "training/train.py",
        "scripts/train.py",
    ]

    # 常见的测试入口文件
    TEST_PATTERNS = [
        "test.py",
        "eval.py",
        "evaluate.py",
        "validation.py",
        "scripts/test.py",
        "scripts/eval.py",
    ]

    # 常见的推理入口文件
    INFERENCE_PATTERNS = [
        "inference.py",
        "predict.py",
        "demo.py",
        "forward.py",
    ]

    # 配置文件类型
    CONFIG_EXTENSIONS = [".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"]

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.warnings: List[str] = []
        self.parse_errors: List[str] = []

        self.result: Dict[str, Any] = {
            "step": "repo_parse",
            "status": "partial",
            "repo_info": {},
            "entry_points": {"train": {}, "test": {}, "inference": {}},
            "config_files": [],
            "dataset_config": {},
            "checkpoint_info": {},
            "metrics_calculation": {},
            "dependencies": {},
            "warnings": [],
            "parse_errors": [],
            "timestamp": datetime.now().isoformat()
        }

    def inspect(self) -> Dict[str, Any]:
        """执行仓库解析"""
        if not self.repo_path.exists():
            self.parse_errors.append(f"仓库路径不存在: {self.repo_path}")
            self.result["status"] = "failed"
            return self.result

        if not self.repo_path.is_dir():
            self.parse_errors.append(f"仓库路径不是目录: {self.repo_path}")
            self.result["status"] = "failed"
            return self.result

        # 提取仓库基本信息
        self._extract_repo_info()

        # 查找入口脚本
        self._find_entry_points()

        # 查找配置文件
        self._find_config_files()

        # 查找数据集配置
        self._find_dataset_config()

        # 查找 checkpoint 信息
        self._find_checkpoint_info()

        # 查找指标计算逻辑
        self._find_metrics_calculation()

        # 查找依赖信息
        self._find_dependencies()

        # 设置状态
        if not self.result["entry_points"]["train"].get("path"):
            self.warnings.append("未找到训练入口脚本")
        if not self.result["config_files"]:
            self.warnings.append("未找到配置文件")

        self.result["status"] = "success" if self.result["entry_points"]["train"].get("path") else "partial"
        self.result["warnings"] = self.warnings
        self.result["parse_errors"] = self.parse_errors

        return self.result

    def _run_git_command(self, args: List[str]) -> Tuple[str, int]:
        """运行 git 命令"""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout.strip(), result.returncode
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return "", -1

    def _extract_repo_info(self):
        """提取仓库基本信息"""
        # 仓库名
        self.result["repo_info"]["name"] = self.repo_path.name

        # 从 .git/config 获取远程 URL
        config_path = self.repo_path / ".git" / "config"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
                url_match = re.search(r"url\s*=\s*(.+)", content)
                if url_match:
                    self.result["repo_info"]["url"] = url_match.group(1).strip()

        # 本地路径
        self.result["repo_info"]["local_path"] = str(self.repo_path.resolve())

        # 默认分支
        branch, code = self._run_git_command(["branch", "--show-current"])
        if code == 0 and branch:
            self.result["repo_info"]["default_branch"] = branch
        else:
            self.result["repo_info"]["default_branch"] = "main"

        # 编程语言
        lang_map = self._detect_language()
        if lang_map:
            self.result["repo_info"]["language"] = lang_map
        else:
            self.result["repo_info"]["language"] = "Unknown"

    def _detect_language(self) -> Optional[str]:
        """检测主要编程语言"""
        # 检查常见文件
        for ext, lang in [
            (".py", "Python"),
            (".cpp", "C++"),
            (".cu", "CUDA"),
            (".sh", "Shell"),
        ]:
            files = list(self.repo_path.rglob(f"*{ext}"))
            if len(files) > 5:
                return lang
        return None

    def _find_entry_points(self):
        """查找入口脚本"""
        # 训练入口
        train_path = self._search_entry_file(self.TRAIN_PATTERNS)
        if train_path:
            self.result["entry_points"]["train"] = {
                "path": str(train_path.relative_to(self.repo_path)),
                "main_file": train_path.name,
                "config_required": self._requires_config(train_path)
            }

        # 测试入口
        test_path = self._search_entry_file(self.TEST_PATTERNS)
        if test_path:
            self.result["entry_points"]["test"] = {
                "path": str(test_path.relative_to(self.repo_path)),
                "main_file": test_path.name
            }

        # 推理入口
        inference_path = self._search_entry_file(self.INFERENCE_PATTERNS)
        if inference_path:
            self.result["entry_points"]["inference"] = {
                "path": str(inference_path.relative_to(self.repo_path)),
                "main_file": inference_path.name
            }

    def _search_entry_file(self, patterns: List[str]) -> Optional[Path]:
        """搜索入口文件"""
        # 1. 优先在根目录查找
        for name in patterns:
            path = self.repo_path / name
            if path.exists() and path.is_file():
                return path

        # 2. 在子目录查找
        for pattern in patterns:
            matches = list(self.repo_path.rglob(pattern))
            if matches:
                # 返回第一个非测试目录的匹配
                for m in matches:
                    if "test" not in str(m).lower() and "__pycache__" not in str(m):
                        return m

        return None

    def _requires_config(self, file_path: Path) -> bool:
        """检查文件是否需要配置文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                return "--config" in content or "argparse" in content
        except Exception:
            return False

    def _find_config_files(self):
        """查找配置文件"""
        config_files = []

        # 查找所有配置文件
        for ext in self.CONFIG_EXTENSIONS:
            for config_path in self.repo_path.rglob(f"*{ext}"):
                # 忽略隐藏文件和测试文件
                if config_path.name.startswith(".") or "test" in str(config_path).lower():
                    continue
                if "__pycache__" in str(config_path):
                    continue

                # 确定配置类型
                config_type = self._classify_config(config_path)
                purpose = self._get_config_purpose(config_path)

                config_files.append({
                    "path": str(config_path.relative_to(self.repo_path)),
                    "type": config_type,
                    "purpose": purpose
                })

        # 按目录优先级排序
        priority_dirs = ["configs", "config", "options", "settings"]
        config_files.sort(key=lambda x: self._config_priority(x["path"], priority_dirs))

        self.result["config_files"] = config_files[:20]  # 限制数量

    def _classify_config(self, config_path: Path) -> str:
        """分类配置文件类型"""
        ext = config_path.suffix.lower()
        if ext in [".yaml", ".yml"]:
            return "yaml"
        elif ext == ".json":
            return "json"
        elif ext == ".toml":
            return "toml"
        elif ext in [".ini", ".cfg"]:
            return "ini"
        return "unknown"

    def _get_config_purpose(self, config_path: Path) -> str:
        """推断配置文件的用途"""
        name_lower = config_path.stem.lower()
        path_lower = str(config_path).lower()

        # 数据集相关
        if any(kw in path_lower for kw in ["data", "dataset", "dataloader"]):
            return "dataset"
        # 训练相关
        if any(kw in path_lower for kw in ["train", "model", "network"]):
            return "training"
        # 评测相关
        if any(kw in path_lower for kw in ["test", "eval", "benchmark"]):
            return "evaluation"
        # 模型相关
        if "bit" in name_lower or "transformer" in name_lower:
            return "model"
        # 默认
        return "general"

    def _config_priority(self, path: str, priority_dirs: List[str]) -> int:
        """计算配置优先级"""
        for i, priority_dir in enumerate(priority_dirs):
            if priority_dir in path:
                return i
        return len(priority_dirs)

    def _find_dataset_config(self):
        """查找数据集配置"""
        # 查找数据集相关文件
        dataset_patterns = [
            "dataset.py",
            "datasets.py",
            "data_loader.py",
            "dataloaders.py",
        ]

        # 查找 train/val/test 划分配置
        split_files = []
        for pattern in ["*train*.txt", "*val*.txt", "*test*.txt", "*.lst"]:
            split_files.extend(list(self.repo_path.rglob(pattern)))

        if split_files:
            self.result["dataset_config"]["split_files"] = [
                str(f.relative_to(self.repo_path)) for f in split_files[:10]
            ]

        # 从配置文件推断数据集路径
        config_files = self.result.get("config_files", [])
        for cfg in config_files:
            if cfg["purpose"] == "dataset":
                self.result["dataset_config"]["config_path"] = cfg["path"]
                break

    def _find_checkpoint_info(self):
        """查找 checkpoint 下载信息"""
        self.result["checkpoint_info"] = {
            "download_url": None,
            "alternative_url": None,
            "format": "pth"
        }

        # 从 README 查找
        readme_files = ["README.md", "README.txt", "README"]
        for readme_name in readme_files:
            readme_path = self.repo_path / readme_name
            if readme_path.exists():
                with open(readme_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    # 查找 checkpoint 下载链接
                    url_patterns = [
                        r"(https?://[^\s]+checkpoint[^\s]+)",
                        r"(https?://[^\s]+\.pth[^\s]+)",
                        r"(https?://[^\s]+\.pt[^\s]+)",
                        r"(https?://[^\s]+\.ckpt[^\s]+)",
                    ]
                    for pattern in url_patterns:
                        matches = re.findall(pattern, content, re.I)
                        if matches:
                            self.result["checkpoint_info"]["download_url"] = matches[0]
                            break

        # 检查 checkpoints 目录
        checkpoints_dir = self.repo_path / "checkpoints"
        if checkpoints_dir.exists():
            checkpoints = list(checkpoints_dir.glob("*.pth")) + list(checkpoints_dir.glob("*.pt"))
            if checkpoints:
                self.result["checkpoint_info"]["local_checkpoints"] = [
                    str(cp.relative_to(self.repo_path)) for cp in checkpoints
                ]

    def _find_metrics_calculation(self):
        """查找指标计算逻辑"""
        metrics_files = []

        # 查找指标相关文件
        for pattern in ["metric", "eval", "score"]:
            for py_file in self.repo_path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                if pattern in py_file.name.lower():
                    metrics_files.append(py_file)

        if metrics_files:
            self.result["metrics_calculation"]["metrics_file"] = str(
                metrics_files[0].relative_to(self.repo_path)
            )

        # 常见的指标名称
        common_metrics = ["F1", "IoU", "Precision", "Recall", "OA", "kappa", "MAE"]
        found_metrics = []

        for py_file in self.repo_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    for metric in common_metrics:
                        if re.search(rf"\b{metric}\b", content, re.I):
                            if metric not in found_metrics:
                                found_metrics.append(metric)
            except Exception:
                continue

        self.result["metrics_calculation"]["implemented_metrics"] = found_metrics

    def _find_dependencies(self):
        """查找依赖信息"""
        # requirements.txt
        req_files = list(self.repo_path.rglob("requirements*.txt"))
        if req_files:
            req_file = req_files[0]
            try:
                with open(req_file, "r", encoding="utf-8") as f:
                    deps = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    self.result["dependencies"]["requirements_file"] = str(
                        req_file.relative_to(self.repo_path)
                    )
                    self.result["dependencies"]["dependencies"] = deps
            except Exception:
                pass

        # setup.py
        setup_files = list(self.repo_path.glob("setup.py"))
        if setup_files:
            self.result["dependencies"]["setup_file"] = "setup.py"

        # environment.yml
        env_files = list(self.repo_path.rglob("environment*.yml"))
        if env_files:
            self.result["dependencies"]["environment_file"] = str(
                env_files[0].relative_to(self.repo_path)
            )


def main():
    parser = argparse.ArgumentParser(
        description="RSCDAgent - 仓库解析模块"
    )
    parser.add_argument(
        "--repo_path", "-r",
        required=True,
        help="仓库本地路径"
    )
    parser.add_argument(
        "--output_dir", "-o",
        default="./claude_outputs",
        help="输出目录 (default: ./claude_outputs)"
    )
    parser.add_argument(
        "--github_url", "-u",
        default="",
        help="GitHub URL (可选，用于补充仓库信息)"
    )

    args = parser.parse_args()

    print(f"正在解析仓库: {args.repo_path}")

    # 解析仓库
    inspector = RepoInspector(args.repo_path)
    result = inspector.inspect()

    # 如果提供了 GitHub URL，补充信息
    if args.github_url and not result["repo_info"].get("url"):
        result["repo_info"]["url"] = args.github_url

    # 保存 JSON 输出
    json_path = os.path.join(args.output_dir, "step2_repo_parse.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✓ JSON 输出: {json_path}")

    # 打印摘要
    print("\n" + "=" * 50)
    print("仓库解析摘要")
    print("=" * 50)

    repo_info = result.get("repo_info", {})
    if repo_info.get("name"):
        print(f"仓库名: {repo_info['name']}")
    if repo_info.get("language"):
        print(f"语言: {repo_info['language']}")

    entry_points = result.get("entry_points", {})
    if entry_points.get("train", {}).get("path"):
        print(f"训练入口: {entry_points['train']['path']}")
    if entry_points.get("test", {}).get("path"):
        print(f"测试入口: {entry_points['test']['path']}")

    config_files = result.get("config_files", [])
    print(f"配置文件数: {len(config_files)}")

    metrics = result.get("metrics_calculation", {}).get("implemented_metrics", [])
    if metrics:
        print(f"实现的指标: {', '.join(metrics)}")

    print(f"\n状态: {result['status']}")

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
