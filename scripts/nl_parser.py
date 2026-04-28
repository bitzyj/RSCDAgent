#!/usr/bin/env python3
"""
nl_parser.py - 自然语言解析模块

将用户的自然语言转换为系统可识别的参数：

模式映射:
- "完整训练" / "full training" / "full" / "200 epochs" / "全部训练" -> "full"
- "短训练" / "short training" / "short" / "20 epochs" / "小规模训练" -> "short"
- "只测试" / "test only" / "testonly" / "预训练" / "test-only" -> "testonly"
- "跳过训练" / "skip training" / "skip" / "仅解析" -> "skip"

用法:
    python nl_parser.py --input "完整训练200轮"
    python nl_parser.py --interactive
"""

import argparse
import re
import sys
from typing import Dict, Optional, Tuple


class NLParser:
    """自然语言解析器"""

    # 模式映射规则
    MODE_PATTERNS = {
        "full": [
            r"完整训练",
            r"完整地?训练",
            r"full\s*training",
            r"full$",
            r"200\s*epochs?",
            r"全部训练",
            r"全部地?训练",
            r"长时间训练",
            r"充分训练",
        ],
        "short": [
            r"短训练",
            r"短时间?训练",
            r"short\s*training",
            r"short$",
            r"20\s*epochs?",
            r"小规模训练",
            r"少量训练",
            r"快速训练",
            r"简短训练",
        ],
        "testonly": [
            r"只测试",
            r"仅测试",
            r"test\s*only",
            r"testonly",
            r"test-only",
            r"预训练",
            r"预训练模型",
            r"pretrained",
            r"使用预训练",
            r"有预训练权重",
        ],
        "skip": [
            r"跳过训练",
            r"skip\s*training",
            r"skip$",
            r"仅解析",
            r"不训练",
            r"无训练",
        ],
    }

    # 数据集类型映射
    DATASET_PATTERNS = {
        "LEVIR-CD": [
            r"levir",
            r"levir-cd",
            r"LEVIR",
        ],
        "CDD": [
            r"cdd",
            r"change detection dataset",
        ],
        "DSIFN": [
            r"dsifn",
            r"dsi-fn",
        ],
        "WHU-CD": [
            r"whu",
            r"whu-cd",
        ],
        "SysU-CD": [
            r"sysu",
            r"sysu-cd",
        ],
    }

    # 评估指标映射
    METRIC_PATTERNS = {
        "F1": [
            r"f1\s*score?",
            r"f1$",
            r"dice",
        ],
        "IoU": [
            r"iou",
            r"intersection\s*over\s*union",
            r"jaccard",
        ],
        "OA": [
            r"oa$",
            r"overall\s*accuracy",
            r"准确率",
            r"精度",
        ],
        "Precision": [
            r"precision",
            r"prec",
            r"精确率",
        ],
        "Recall": [
            r"recall",
            r"sensitivity",
            r"召回率",
        ],
        "Kappa": [
            r"kappa",
            r"κ",
        ],
    }

    def __init__(self):
        self.mode_mapping = self._compile_patterns(self.MODE_PATTERNS)
        self.dataset_mapping = self._compile_patterns(self.DATASET_PATTERNS)
        self.metric_mapping = self._compile_patterns(self.METRIC_PATTERNS)

    def _compile_patterns(self, patterns: Dict[str, list]) -> Dict[str, re.Pattern]:
        """编译正则表达式"""
        compiled = {}
        for key, pattern_list in patterns.items():
            for pattern in pattern_list:
                compiled.setdefault(key, []).append(re.compile(pattern, re.I))
        return compiled

    def parse_mode(self, text: str) -> Optional[str]:
        """
        从自然语言解析执行模式

        Args:
            text: 用户输入的自然语言

        Returns:
            模式字符串: "full", "short", "testonly", "skip", 或 None
        """
        text = text.lower().strip()

        for mode, patterns in self.mode_mapping.items():
            for pattern in patterns:
                if pattern.search(text):
                    return mode

        return None

    def parse_dataset(self, text: str) -> Optional[str]:
        """
        从自然语言解析数据集类型

        Args:
            text: 用户输入的自然语言

        Returns:
            数据集类型字符串，或 None
        """
        text = text.lower().strip()

        for dataset, patterns in self.dataset_mapping.items():
            for pattern in patterns:
                if pattern.search(text):
                    return dataset

        return None

    def parse_metrics(self, text: str) -> list:
        """
        从自然语言解析评估指标

        Args:
            text: 用户输入的自然语言

        Returns:
            指标列表
        """
        text = text.lower().strip()
        found = []

        for metric, patterns in self.metric_mapping.items():
            for pattern in patterns:
                if pattern.search(text):
                    if metric not in found:
                        found.append(metric)
                    break

        return found

    def parse_all(self, text: str) -> Dict[str, Optional[str]]:
        """
        解析所有可能的参数

        Args:
            text: 用户输入的自然语言

        Returns:
            包含所有解析结果的字典
        """
        return {
            "mode": self.parse_mode(text),
            "dataset": self.parse_dataset(text),
            "metrics": self.parse_metrics(text),
        }


def interactive_mode():
    """交互模式"""
    parser = NLParser()

    print("=" * 50)
    print("自然语言解析器 - 交互模式")
    print("=" * 50)
    print("输入自然语言描述，我将解析出对应的参数")
    print("输入 'quit' 退出")
    print()

    while True:
        try:
            text = input("\n> ").strip()

            if text.lower() in ["quit", "exit", "q"]:
                break

            if not text:
                continue

            result = parser.parse_all(text)

            print("\n解析结果:")
            print(f"  执行模式: {result['mode'] or '未知'}")
            print(f"  数据集类型: {result['dataset'] or '未知'}")
            print(f"  评估指标: {', '.join(result['metrics']) if result['metrics'] else '未知'}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"解析错误: {e}")

    print("\n再见!")


def main():
    parser_cli = argparse.ArgumentParser(description="自然语言解析器")
    parser_cli.add_argument("--input", "-i", help="要解析的文本")
    parser_cli.add_argument("--interactive", action="store_true", help="交互模式")
    parser_cli.add_argument("--mode_only", action="store_true", help="仅解析模式")

    args = parser_cli.parse_args()

    if args.interactive:
        interactive_mode()
        return 0

    if not args.input:
        parser_cli.print_help()
        return 1

    parser = NLParser()
    result = parser.parse_all(args.input)

    if args.mode_only:
        print(result["mode"] or "")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    import json
    sys.exit(main())
