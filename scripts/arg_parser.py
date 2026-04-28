#!/usr/bin/env python3
"""
arg_parser.py - RSCDAgent 参数解析模块

提供命令行参数解析和配置管理功能。
"""

import argparse
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any


class RSCDArgParser:
    """RSCDAgent 参数解析器"""

    def __init__(self, description: str = "RSCDAgent - 遥感变化检测论文复现Agent"):
        self.parser = argparse.ArgumentParser(
            description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
示例:
  python arg_parser.py --project_dir ./my_repro \\
                       --github_url https://github.com/xxx/yyy \\
                       --paper ./paper.pdf \\
                       --dataset ./data/LEVIR-CD \\
                       --target "Table 2"
            """
        )
        self._add_arguments()

    def _add_arguments(self):
        """添加所有参数"""

        # 必需参数组
        required = self.parser.add_argument_group('必需参数')
        required.add_argument(
            '--project_dir',
            required=True,
            help='项目根目录'
        )
        required.add_argument(
            '--github_url',
            required=True,
            help='目标仓库URL'
        )
        required.add_argument(
            '--paper',
            required=True,
            help='论文PDF路径或URL'
        )
        required.add_argument(
            '--dataset',
            required=True,
            help='数据集路径'
        )
        required.add_argument(
            '--target',
            required=True,
            help='目标指标（如论文中的Table编号）'
        )

        # 可选参数组
        optional = self.parser.add_argument_group('可选参数')
        optional.add_argument(
            '--benchmark',
            default='LEVIR-CD',
            help='评测基准 (default: LEVIR-CD)'
        )
        optional.add_argument(
            '--api',
            default='',
            help='私有仓库API密钥'
        )
        optional.add_argument(
            '--repo_name',
            default='',
            help='仓库名称（自动从URL提取，可手动指定）'
        )

        # 执行模式组
        exec_group = self.parser.add_argument_group('执行模式')
        exec_group.add_argument(
            '--step',
            choices=['1', '2', '3', '4', '5', '6', 'all'],
            default='all',
            help='执行特定步骤 (default: all)'
        )
        exec_group.add_argument(
            '--dry_run',
            action='store_true',
            help='仅验证参数，不执行'
        )
        exec_group.add_argument(
            '--skip_clone',
            action='store_true',
            help='跳过仓库克隆'
        )

    def parse_args(self, args: Optional[list] = None) -> argparse.Namespace:
        """解析参数"""
        return self.parser.parse_args(args)

    def validate_args(self, args: argparse.Namespace) -> tuple[bool, str]:
        """
        验证参数合法性
        返回: (is_valid, error_message)
        """
        # 检查项目目录
        if not args.project_dir:
            return False, "项目目录不能为空"

        # 检查论文文件（如果是本地路径）
        if not args.paper.startswith('http') and not os.path.exists(args.paper):
            return False, f"论文文件不存在: {args.paper}"

        # 检查数据集路径
        if not os.path.isdir(args.dataset):
            return False, f"数据集路径不存在: {args.dataset}"

        # 检查GitHub URL格式
        if not self._is_valid_github_url(args.github_url):
            return False, f"GitHub URL格式无效: {args.github_url}"

        return True, ""

    def _is_valid_github_url(self, url: str) -> bool:
        """验证GitHub URL格式"""
        if not url:
            return False
        patterns = [
            'https://github.com/',
            'http://github.com/',
            'git@github.com:'
        ]
        return any(url.startswith(p) for p in patterns)


def extract_repo_name(github_url: str) -> str:
    """从GitHub URL提取仓库名"""
    import re

    # 处理 git@github.com:user/repo.git 格式
    match = re.search(r':([^/]+)/([^/]+?)(?:\.git)?$', github_url)
    if match:
        return match.group(2)

    # 处理 https://github.com/user/repo 格式
    match = re.search(r'github\.com/[^/]+/([^/]+)', github_url)
    if match:
        repo_name = match.group(1)
        return repo_name.replace('.git', '')

    return ""


def create_project_config(args: argparse.Namespace, config_path: str) -> Dict[str, Any]:
    """创建项目配置字典"""

    repo_name = args.repo_name if args.repo_name else extract_repo_name(args.github_url)

    config = {
        "project": {
            "project_dir": os.path.abspath(args.project_dir),
            "repo_name": repo_name,
            "benchmark": args.benchmark
        },
        "inputs": {
            "github_url": args.github_url,
            "paper": os.path.abspath(args.paper) if not args.paper.startswith('http') else args.paper,
            "dataset": os.path.abspath(args.dataset),
            "target": args.target
        },
        "paths": {
            "repo_dir": os.path.join(os.path.abspath(args.project_dir), "repo", repo_name),
            "src_dir": os.path.join(os.path.abspath(args.project_dir), "src"),
            "env_dir": os.path.join(os.path.abspath(args.project_dir), "env"),
            "outputs_dir": os.path.join(os.path.abspath(args.project_dir), "claude_outputs"),
            "reports_dir": os.path.join(os.path.abspath(args.project_dir), "reports")
        },
        "execution": {
            "step": args.step,
            "dry_run": args.dry_run,
            "skip_clone": args.skip_clone
        }
    }

    return config


def save_config(config: Dict[str, Any], config_path: str):
    """保存配置到JSON文件"""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_config(config_path: str) -> Dict[str, Any]:
    """从JSON文件加载配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_config_summary(config: Dict[str, Any]):
    """打印配置摘要"""
    print("\n" + "=" * 50)
    print("         RSCDAgent 配置摘要")
    print("=" * 50)
    print(f"项目目录:  {config['project']['project_dir']}")
    print(f"仓库名:   {config['project']['repo_name']}")
    print(f"评测基准:  {config['project']['benchmark']}")
    print(f"仓库URL:  {config['inputs']['github_url']}")
    print(f"论文:     {config['inputs']['paper']}")
    print(f"数据集:   {config['inputs']['dataset']}")
    print(f"目标指标:  {config['inputs']['target']}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    # 测试用
    parser = RSCDArgParser()
    args = parser.parse_args([
        '--project_dir', './test_project',
        '--github_url', 'https://github.com/xxx/yyy',
        '--paper', './paper.pdf',
        '--dataset', './data/LEVIR-CD',
        '--target', 'Table 2'
    ])

    print("解析的参数:")
    print(f"  project_dir: {args.project_dir}")
    print(f"  github_url: {args.github_url}")
    print(f"  paper: {args.paper}")
    print(f"  dataset: {args.dataset}")
    print(f"  target: {args.target}")
    print(f"  benchmark: {args.benchmark}")
    print(f"  step: {args.step}")
    print(f"  dry_run: {args.dry_run}")

    # 验证
    is_valid, error = parser.validate_args(args)
    print(f"\n验证结果: {'通过' if is_valid else f'失败 - {error}'}")

    # 创建配置
    config = create_project_config(args, './test_config.json')
    print_config_summary(config)
