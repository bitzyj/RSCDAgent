#!/usr/bin/env python3
"""
env_manager.py - Conda 环境管理模块

功能:
1. 检测现有 conda 环境，找出符合复现需求的环境
2. 如果环境缺少 <=5 个包且不影响整体环境，则安装缺少的包
3. 如果没有符合要求的环境，创建新环境（避免 C 盘）
4. 支持 Linux 服务器

用法:
    python env_manager.py --check --repo_path <PATH> --requirements <FILE>
    python env_manager.py --create --name <NAME> --requirements <FILE> --env_path <PATH>
"""

import argparse
import json
import os
import subprocess
import sys
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CondaEnv:
    """Conda 环境信息"""
    name: str
    path: str
    python_version: str
    packages: Set[str]
    has_gpu: bool = False


@dataclass
class EnvCheckResult:
    """环境检查结果"""
    suitable_env: Optional[CondaEnv]
    missing_packages: List[str]
    can_use_existing: bool
    recommendation: str


class CondaEnvManager:
    """Conda 环境管理器"""

    # 核心包列表（必须有）
    CORE_PACKAGES = {"python", "pip", "numpy", "setuptools"}

    # 可选包（检测 GPU 支持）
    GPU_PACKAGES = {"torch", "tensorflow", "cupy"}

    def __init__(self):
        self.conda_cmd = self._find_conda_cmd()

    def _find_conda_cmd(self) -> Optional[str]:
        """查找 conda 命令"""
        for cmd in ["conda", "conda.exe"]:
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    return cmd
            except:
                continue
        return None

    def list_environments(self) -> List[CondaEnv]:
        """列出所有 conda 环境"""
        if not self.conda_cmd:
            return []

        try:
            result = subprocess.run(
                [self.conda_cmd, "env", "list", "--json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return []

            data = json.loads(result.stdout)
            envs = []

            for env_info in data.get("envs", []):
                env_path = Path(env_info)
                env_name = env_path.name if env_path.parent.name == "envs" else env_path.stem

                # 跳过系统环境
                if env_name in ["base", "system", "root"]:
                    continue

                # 获取环境详情
                env = self._get_env_details(env_name, str(env_path))
                if env:
                    envs.append(env)

            return envs
        except Exception as e:
            print(f"警告: 无法列出环境: {e}")
            return []

    def _get_env_details(self, name: str, path: str) -> Optional[CondaEnv]:
        """获取环境详情"""
        try:
            # 获取包列表
            result = subprocess.run(
                [self.conda_cmd, "list", "-n", name, "--json"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return None

            packages = set()
            for pkg in json.loads(result.stdout):
                pkg_name = pkg.get("name", "").lower()
                packages.add(pkg_name)

            # 获取 Python 版本
            python_ver = ""
            for pkg in json.loads(result.stdout):
                if pkg.get("name") == "python":
                    python_ver = pkg.get("version", "")
                    break

            # 检测 GPU 支持
            has_gpu = bool(packages & self.GPU_PACKAGES)

            return CondaEnv(
                name=name,
                path=path,
                python_version=python_ver,
                packages=packages,
                has_gpu=has_gpu
            )
        except:
            return None

    def check_requirements(self, requirements_path: str) -> Set[str]:
        """解析 requirements 文件，提取包名"""
        required = set()

        if not os.path.exists(requirements_path):
            return required

        with open(requirements_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith("#"):
                    continue
                # 提取包名（去掉版本号）
                pkg_name = re.split(r"[=<>!]", line)[0].strip().lower()
                if pkg_name:
                    required.add(pkg_name)

        return required

    def find_suitable_environment(self, requirements_path: str,
                                 min_gpu: bool = True) -> EnvCheckResult:
        """
        查找符合要求的环境

        Args:
            requirements_path: requirements.txt 路径
            min_gpu: 是否需要 GPU 支持

        Returns:
            EnvCheckResult: 检查结果
        """
        required = self.check_requirements(requirements_path)
        if not required:
            return EnvCheckResult(
                suitable_env=None,
                missing_packages=[],
                can_use_existing=False,
                recommendation="无法解析 requirements 文件"
            )

        # 移除核心包（认为已有）
        required = required - self.CORE_PACKAGES

        envs = self.list_environments()
        best_env = None
        best_missing = None
        best_missing_count = float('inf')

        for env in envs:
            # 检查 GPU 要求
            if min_gpu and not env.has_gpu:
                continue

            # 计算缺少的包
            missing = required - env.packages

            if len(missing) <= 5 and len(missing) < best_missing_count:
                best_env = env
                best_missing = list(missing)
                best_missing_count = len(missing)

        if best_env:
            if len(best_missing) == 0:
                return EnvCheckResult(
                    suitable_env=best_env,
                    missing_packages=[],
                    can_use_existing=True,
                    recommendation=f"环境 '{best_env.name}' 满足所有要求，可直接使用"
                )
            else:
                return EnvCheckResult(
                    suitable_env=best_env,
                    missing_packages=best_missing,
                    can_use_existing=True,
                    recommendation=f"环境 '{best_env.name}' 缺少 {len(best_missing)} 个包: {', '.join(best_missing)}"
                )

        return EnvCheckResult(
            suitable_env=None,
            missing_packages=list(required),
            can_use_existing=False,
            recommendation="没有找到符合要求的环境，将创建新环境"
        )

    def install_packages(self, env_name: str, packages: List[str]) -> bool:
        """在指定环境中安装包"""
        if not packages:
            return True

        print(f"在环境 '{env_name}' 中安装包: {', '.join(packages)}")

        try:
            result = subprocess.run(
                [self.conda_cmd, "install", "-n", env_name, "-y"] + packages,
                capture_output=True, text=True, timeout=300
            )
            return result.returncode == 0
        except Exception as e:
            print(f"安装失败: {e}")
            return False

    def create_environment(self, name: str, env_path: Optional[str] = None,
                          python_version: str = "3.9") -> Tuple[bool, str]:
        """
        创建新 conda 环境

        Args:
            name: 环境名称
            env_path: 环境存储路径（避免 C 盘）
            python_version: Python 版本

        Returns:
            (success, python_path)
        """
        # 如果提供了自定义路径，使用 --prefix
        if env_path:
            # 确保路径不在 C 盘（Windows）
            env_path = Path(env_path)
            if sys.platform == "win32" and env_path.drive.endswith(":"):
                c_drive = Path("C:/")
                if env_path.resolve().drive == c_drive.resolve().drive:
                    # 尝试使用 D 盘
                    alt_path = Path("D:/conda_envs")
                    alt_path.mkdir(parents=True, exist_ok=True)
                    env_path = alt_path / name
                    print(f"警告: 避免使用 C 盘，已切换到 {env_path}")

            env_path.mkdir(parents=True, exist_ok=True)

            cmd = [
                self.conda_cmd, "create",
                "--prefix", str(env_path),
                f"python={python_version}",
                "-y"
            ]
        else:
            cmd = [
                self.conda_cmd, "create",
                "-n", name,
                f"python={python_version}",
                "-y"
            ]

        try:
            print(f"创建环境: {name}")
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                if env_path:
                    python_path = env_path / "python.exe" if sys.platform == "win32" else env_path / "bin" / "python"
                else:
                    python_path = Path(sys.prefix).parent / "envs" / name / "python.exe" if sys.platform == "win32" else Path(sys.prefix).parent / "envs" / name / "bin" / "python"
                return True, str(python_path)
            else:
                print(f"创建失败: {result.stderr[:500]}")
                return False, ""
        except Exception as e:
            print(f"创建失败: {e}")
            return False, ""

    def install_requirements_in_env(self, env_name: str, requirements_path: str,
                                   env_path: Optional[str] = None) -> bool:
        """在环境中安装 requirements"""
        prefix = ["-n", env_name] if not env_path else ["--prefix", str(env_path)]

        try:
            result = subprocess.run(
                [self.conda_cmd, "install"] + prefix +
                ["-c", "pytorch", "-c", "conda-forge", "-y"] +
                ["pytorch", "torchvision", "torchaudio"] +
                ["--file", requirements_path],
                capture_output=True, text=True, timeout=600
            )
            return result.returncode == 0
        except Exception as e:
            print(f"安装 requirements 失败: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Conda 环境管理器")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # check 命令
    check_parser = subparsers.add_parser("check", help="检查现有环境")
    check_parser.add_argument("--repo_path", required=True, help="仓库路径")
    check_parser.add_argument("--requirements", default="requirements.txt", help="requirements 文件")
    check_parser.add_argument("--no_gpu", action="store_true", help="不需要 GPU")

    # create 命令
    create_parser = subparsers.add_parser("create", help="创建新环境")
    create_parser.add_argument("--name", required=True, help="环境名称")
    create_parser.add_argument("--requirements", required=True, help="requirements 文件")
    create_parser.add_argument("--env_path", help="环境存储路径（避免 C 盘）")
    create_parser.add_argument("--python", default="3.9", help="Python 版本")

    # install 命令
    install_parser = subparsers.add_parser("install", help="在环境中安装包")
    install_parser.add_argument("--env", required=True, help="环境名称")
    install_parser.add_argument("--packages", nargs="+", required=True, help="包名")

    args = parser.parse_args()

    manager = CondaEnvManager()

    if not manager.conda_cmd:
        print("错误: 未找到 conda 命令")
        return 1

    if args.command == "check":
        repo_req = os.path.join(args.repo_path, args.requirements)
        result = manager.find_suitable_environment(repo_req, min_gpu=not args.no_gpu)

        print("=" * 50)
        print("环境检查结果")
        print("=" * 50)
        print(f"推荐: {result.recommendation}")

        if result.suitable_env:
            print(f"\n环境名称: {result.suitable_env.name}")
            print(f"环境路径: {result.suitable_env.path}")
            print(f"Python 版本: {result.suitable_env.python_version}")
            print(f"GPU 支持: {'是' if result.suitable_env.has_gpu else '否'}")

        if result.missing_packages:
            print(f"\n缺少的包 ({len(result.missing_packages)}):")
            for pkg in result.missing_packages:
                print(f"  - {pkg}")

        return 0

    elif args.command == "create":
        repo_req = args.requirements
        result = manager.find_suitable_environment(repo_req)

        if result.can_use_existing and result.suitable_env:
            print(f"使用现有环境: {result.suitable_env.name}")
            if result.missing_packages:
                manager.install_packages(result.suitable_env.name, result.missing_packages)
            print(f"环境路径: {result.suitable_env.path}")
            return 0

        success, python_path = manager.create_environment(
            args.name, args.env_path, args.python
        )

        if success:
            print(f"✅ 环境创建成功: {python_path}")

            # 安装 requirements
            if os.path.exists(args.requirements):
                print("安装 requirements...")
                manager.install_requirements_in_env(args.name, args.requirements)
            return 0
        else:
            print("❌ 环境创建失败")
            return 1

    elif args.command == "install":
        success = manager.install_packages(args.env, args.packages)
        return 0 if success else 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
