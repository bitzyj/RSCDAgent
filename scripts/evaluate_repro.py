#!/usr/bin/env python3
"""
evaluate_repro.py - Reproduction Result Evaluation Module

Compares paper target metrics with actual reproduction results, generating gap analysis.
Supports bilingual output (Chinese/English) based on user input language.

Input:
- step1_paper_parse.json   (paper target metrics)
- step5_execution.json     (actual execution results)
- step3_dataset_check.json (optional, dataset status)

Output:
- step6_evaluation.json (evaluation results)
- reports/reproduction_report.md (human-readable report)

Usage:
    python evaluate_repro.py --inputs_dir <DIR> --output_dir <DIR> --reports_dir <DIR>
    python evaluate_repro.py --inputs_dir . --output_dir ./claude_outputs --reports_dir ./reports --lang zh
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class ReproEvaluator:
    """Reproduction result evaluator with bilingual support"""

    # Standardized metric name mapping (for unifying different codebases' naming)
    METRIC_NAME_MAPPING = {
        "F1": ["F1", "f1", "F1-score", "mF1", "mf1", "macro_f1", "dice"],
        "IoU": ["IoU", "iou", "Jaccard", "jaccard", "mIoU", "miou"],
        "OA": ["OA", "oa", "accuracy", " Accuracy", "overall_accuracy"],
        "Precision": ["Precision", "precision", " PRE", "pre"],
        "Recall": ["Recall", "recall", "SEN", "sensitivity"],
        "Kappa": ["Kappa", "kappa", "KAPPA"],
    }

    # Internationalized strings
    STRINGS = {
        "en": {
            "status_ok": "PASS", "status_fail": "FAIL", "status_warn": "WARN",
            "metric_target": "Target", "metric_achieved": "Achieved", "metric_gap": "Gap",
            "acceptable": "acceptable", "mild_deviation": "mild deviation",
            "significant_deviation": "significant deviation", "exceeded": "exceeded",
            "critical": "critical",
            "msg_fully_reproduced": "Reproduction successful, metrics meet paper targets",
            "msg_partially_reproduced": "Partially reproduced, some metrics below target",
            "msg_failed_reproduction": "Reproduction failed",
            "msg_recommendation_testonly": "Use test-only mode to verify pretrained weights",
            "msg_code_execution_failed": "Code execution failed",
            "msg_dataset_unavailable": "Dataset unavailable",
            "msg_investigate": "Investigate {metric} deviation reason",
            "msg_check_config": "Check configuration and dataset",
            "msg_view_logs": "View execution logs for details",
        },
        "zh": {
            "status_ok": "通过", "status_fail": "失败", "status_warn": "警告",
            "metric_target": "目标", "metric_achieved": "实际", "metric_gap": "差距",
            "acceptable": "可接受", "mild_deviation": "轻微偏差",
            "significant_deviation": "显著偏差", "exceeded": "超出预期",
            "critical": "严重偏差",
            "msg_fully_reproduced": "复现成功，指标达到论文水平",
            "msg_partially_reproduced": "部分指标未达标，建议检查配置和数据集",
            "msg_failed_reproduction": "复现失败，建议检查代码和环境配置",
            "msg_recommendation_testonly": "使用 test-only 模式验证预训练权重是否正确加载",
            "msg_code_execution_failed": "代码执行失败",
            "msg_dataset_unavailable": "数据集不可用",
            "msg_investigate": "建议调查 {metric} 偏差过大的原因",
            "msg_check_config": "查看执行日志定位具体问题",
            "msg_view_logs": "建议检查代码和环境配置",
        }
    }

    def __init__(self, inputs_dir: str, lang: str = "en"):
        self.inputs_dir = Path(inputs_dir)
        self.lang = lang if lang in ["en", "zh"] else "en"
        self.STRINGS = self.STRINGS[self.lang]
        self.paper_info: Dict[str, Any] = {}
        self.execution_result: Dict[str, Any] = {}
        self.dataset_check: Dict[str, Any] = {}

        self.result: Dict[str, Any] = {
            "step": "evaluation",
            "status": "completed",
            "evaluation_id": str(uuid.uuid4())[:8],
            "target_metrics": {
                "source": "",
                "paper_url": None,
                "metrics": []
            },
            "achieved_metrics": {
                "metrics": []
            },
            "gap_analysis": [],
            "reproduction_status": {
                "overall": "partially_reproduced",
                "metrics_match": None,
                "code_runs": False,
                "data_available": False,
                "issues": []
            },
            "detailed_report_path": "",
            "timestamp": datetime.now().isoformat(),
            "metrics_calculation_method": "cm2score_confusion_matrix"
        }

    def load_inputs(self) -> bool:
        """Load input files"""
        # Paper targets
        step1 = self.inputs_dir / "step1_paper_parse.json"
        if step1.exists():
            with open(step1, "r", encoding="utf-8") as f:
                self.paper_info = json.load(f)

        # Execution results
        step5 = self.inputs_dir / "step5_execution.json"
        if step5.exists():
            with open(step5, "r", encoding="utf-8") as f:
                self.execution_result = json.load(f)

        # Dataset check
        step3 = self.inputs_dir / "step3_dataset_check.json"
        if step3.exists():
            with open(step3, "r", encoding="utf-8") as f:
                self.dataset_check = json.load(f)

        return bool(self.paper_info and self.execution_result)

    def evaluate(self) -> Dict[str, Any]:
        """Execute evaluation"""
        # Extract target metrics
        self._extract_target_metrics()

        # Extract actual metrics
        self._extract_achieved_metrics()

        # Compute gap
        self._compute_gap_analysis()

        # Determine reproduction status
        self._determine_reproduction_status()

        return self.result

    def _extract_target_metrics(self):
        """Extract paper target metrics"""
        target = self.paper_info.get("target_metrics", {})
        self.result["target_metrics"] = {
            "source": target.get("table_id", "Unknown"),
            "paper_url": self.paper_info.get("paper_info", {}).get("url"),
            "metrics": target.get("metrics", [])
        }

    def _extract_achieved_metrics(self):
        """Extract actual metrics from execution results"""
        achieved = []

        # Extract metrics from step5 stdout
        steps = self.execution_result.get("steps_executed", [])
        for step in steps:
            if step.get("action") in ["评估与对比", "Test-only", "test"]:
                stdout = step.get("stdout", "")
                metrics = self._parse_metrics_from_output(stdout)
                achieved.extend(metrics)

        # Default if not found
        if not achieved:
            achieved = [
                {"metric_name": "F1", "achieved_value": None, "dataset": "LEVIR-CD", "source_file": None}
            ]

        self.result["achieved_metrics"]["metrics"] = achieved

    def _parse_metrics_from_output(self, stdout: str) -> List[Dict[str, Any]]:
        """Parse metrics from stdout using standardized cm2score method"""
        metrics = []

        # Common metric patterns - flexible matching
        patterns = {
            "F1": r"(?:mF1|F1|f1|macro.?F1|dice)[=\s:]+([\d.]+)",
            "IoU": r"(?:mIoU|IoU|iou|Jaccard)[=\s:]+([\d.]+)",
            "OA": r"(?:OA|oa|accuracy|overall.?accuracy)[=\s:]+([\d.]+)",
            "Precision": r"(?:precision|PRE|prec)[=\s:]+([\d.]+)",
            "Recall": r"(?:recall|SEN|sensitivity)[=\s:]+([\d.]+)",
            "Kappa": r"(?:Kappa|kappa|KAPPA)[=\s:]+([\d.]+)",
        }

        for metric_name, pattern in patterns.items():
            import re
            match = re.search(pattern, stdout, re.I)
            if match:
                try:
                    value = float(match.group(1))
                    metrics.append({
                        "metric_name": metric_name,
                        "achieved_value": value,
                        "dataset": "LEVIR-CD",
                        "source_file": None,
                        "calculation_method": "cm2score"
                    })
                except ValueError:
                    pass

        return metrics

    def _compute_gap_analysis(self):
        """Compute gap analysis using cm2score standardized metrics"""
        target_metrics = self.result["target_metrics"]["metrics"]
        achieved_metrics = self.result["achieved_metrics"]["metrics"]

        # Build mapping (compatible with different naming conventions)
        achieved_map = {}
        for m in achieved_metrics:
            name = m["metric_name"]
            achieved_map[name] = m

        gap_analysis = []
        for target in target_metrics:
            metric_name = target.get("metric_name", "")
            target_value = target.get("value")
            achieved_entry = achieved_map.get(metric_name)
            achieved_value = achieved_entry.get("achieved_value") if achieved_entry else None

            # Compute gap
            gap = None
            gap_percentage = None
            assessment = "acceptable"

            if achieved_value is not None and target_value:
                gap = achieved_value - target_value
                if target_value != 0:
                    gap_percentage = (gap / target_value) * 100

                # Assess gap based on cm2score metrics
                abs_gap = abs(gap_percentage) if gap_percentage is not None else abs(gap)
                if abs_gap < 1.0:  # < 1%
                    assessment = "acceptable"
                elif abs_gap < 2.0:  # < 2%
                    assessment = "mild_deviation"
                elif abs_gap < 5.0:  # < 5%
                    assessment = "significant_deviation"
                else:
                    assessment = "exceeded" if gap > 0 else "critical"

            gap_analysis.append({
                "metric_name": metric_name,
                "target": target_value,
                "achieved": achieved_value,
                "gap": gap,
                "gap_percentage": gap_percentage,
                "assessment": assessment,
                "calculation_method": "cm2score"
            })

        self.result["gap_analysis"] = gap_analysis

    def _determine_reproduction_status(self):
        """Determine reproduction status"""
        status = self.result["reproduction_status"]

        # Check if code runs
        steps = self.execution_result.get("steps_executed", [])
        code_runs = any(s.get("status") == "success" for s in steps)
        status["code_runs"] = code_runs

        # Check data availability
        if self.dataset_check:
            status["data_available"] = self.dataset_check.get("summary", {}).get("reproducible", False)
        else:
            status["data_available"] = True  # Default assume available

        # Check metrics match
        gap_analysis = self.result["gap_analysis"]
        if gap_analysis:
            acceptable_count = sum(
                1 for g in gap_analysis
                if g.get("achieved") is not None and g.get("assessment") in ["acceptable", "mild_deviation"]
            )
            total_count = len([g for g in gap_analysis if g.get("achieved") is not None])
            status["metrics_match"] = acceptable_count == total_count if total_count > 0 else None

        # Determine overall status
        if not code_runs:
            status["overall"] = "failed_reproduction"
        elif not status["data_available"]:
            status["overall"] = "failed_reproduction"
            status["issues"].append(self.STRINGS["msg_dataset_unavailable"])
        elif status["metrics_match"] is True:
            status["overall"] = "fully_reproduced"
        elif status["metrics_match"] is False:
            status["overall"] = "partially_reproduced"
        else:
            status["overall"] = "partially_reproduced"

        # Add issues
        if not code_runs:
            status["issues"].append(self.STRINGS["msg_code_execution_failed"])

        gaps = self.result["gap_analysis"]
        critical_gaps = [g["metric_name"] for g in gaps if g.get("assessment") == "critical"]
        if critical_gaps:
            status["issues"].append(self.STRINGS["msg_investigate"].format(metric=", ".join(critical_gaps)))


def generate_markdown_report(evaluation: Dict[str, Any], paper_info: Dict[str, Any],
                              execution: Dict[str, Any], dataset_check: Dict[str, Any],
                              output_path: str, lang: str = "en"):
    """Generate Markdown report with bilingual support"""
    from jinja2 import Template

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..", "templates", "reproduction_report.md.j2"
    )

    if not os.path.exists(template_path):
        print("Warning: Template not found")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template_str = f.read()

    template = Template(template_str)

    # Prepare context
    repo_info = paper_info.get("repo_info", {}) if isinstance(paper_info, dict) and "repo_info" in paper_info else {}

    context = {
        "paper_title": paper_info.get("paper_info", {}).get("title", "Unknown") if isinstance(paper_info, dict) else "Unknown",
        "repo_url": repo_info.get("url", "Unknown") if repo_info else "Unknown",
        "reproduction_date": datetime.now().strftime("%Y-%m-%d"),
        "overall_status": evaluation.get("reproduction_status", {}).get("overall", "unknown"),
        "target_source": evaluation.get("target_metrics", {}).get("source", "Unknown"),
        "gap_analysis": evaluation.get("gap_analysis", []),
        "data_available": evaluation.get("reproduction_status", {}).get("data_available", False),
        "code_runs": evaluation.get("reproduction_status", {}).get("code_runs", False),
        "steps_executed": execution.get("steps_executed", []),
        "python_version": execution.get("env_state", {}).get("python_version", "Unknown"),
        "cuda_available": execution.get("env_state", {}).get("cuda_available", False),
        "gpu_info": execution.get("env_state", {}).get("gpu_info"),
        "modifications_made": execution.get("modifications_made", []),
        "issues": evaluation.get("reproduction_status", {}).get("issues", []),
        "critical_risks": [],
        "recommendations": _generate_recommendations(evaluation, lang),
        "timestamp": evaluation.get("timestamp", datetime.now().isoformat()),
        "lang": lang
    }

    report = template.render(**context)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)


def _generate_recommendations(evaluation: Dict[str, Any], lang: str = "en") -> List[str]:
    """Generate recommendations in the specified language"""
    strings = ReproEvaluator.STRINGS[lang]
    recommendations = []
    status = evaluation.get("reproduction_status", {})
    gap_analysis = evaluation.get("gap_analysis", [])

    if status.get("overall") == "fully_reproduced":
        recommendations.append(strings["msg_fully_reproduced"])
        recommendations.append("Continue with more experiments or parameter tuning" if lang == "en" else "可以继续进行更多实验或参数调优")
    elif status.get("overall") == "partially_reproduced":
        recommendations.append(strings["msg_partially_reproduced"])
        for gap in gap_analysis:
            if gap.get("assessment") in ["significant_deviation", "critical"]:
                rec = strings["msg_investigate"].format(metric=gap['metric_name'])
                recommendations.append(rec)
    else:
        recommendations.append(strings["msg_failed_reproduction"])
        recommendations.append("Check code and environment configuration" if lang == "en" else "建议检查代码和环境配置")
        recommendations.append("View execution logs for details" if lang == "en" else strings["msg_view_logs"])

    recommendations.append(strings["msg_recommendation_testonly"])

    return recommendations


def main():
    parser = argparse.ArgumentParser(description="RSCDAgent - Evaluation Module")
    parser.add_argument("--inputs_dir", "-i", default="./claude_outputs",
                        help="Input directory (contains step1, step3, step5 JSON)")
    parser.add_argument("--output_dir", "-o", default="./claude_outputs",
                        help="Output directory")
    parser.add_argument("--reports_dir", "-r", default="./reports",
                        help="Reports directory")
    parser.add_argument("--lang", "-l", default="en", choices=["en", "zh"],
                        help="Output language (en/zh)")

    args = parser.parse_args()

    strings = ReproEvaluator.STRINGS[args.lang]

    print("=" * 50)
    print("RSCDAgent Evaluation Module" if args.lang == "en" else "RSCDAgent 评测模块")
    print("=" * 50)

    # Evaluation
    evaluator = ReproEvaluator(args.inputs_dir, args.lang)
    if not evaluator.load_inputs():
        print("Error: Failed to load required input files" if args.lang == "en" else "错误: 未能加载必要的输入文件")
        return 1

    result = evaluator.evaluate()

    # Save evaluation results
    json_path = os.path.join(args.output_dir, "step6_evaluation.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"{strings['status_ok']} Evaluation result: {json_path}")

    # Generate report
    md_path = os.path.join(args.reports_dir, "reproduction_report.md")
    generate_markdown_report(
        result,
        evaluator.paper_info,
        evaluator.execution_result,
        evaluator.dataset_check,
        md_path,
        args.lang
    )

    if os.path.exists(md_path):
        print(f"{strings['status_ok']} Report: {md_path}")

    # Export Excel comparison
    try:
        excel_path = os.path.join(args.reports_dir, "metrics_comparison.xlsx")
        excel_script = os.path.join(os.path.dirname(__file__), "export_excel.py")
        if os.path.exists(excel_script):
            import subprocess
            result_export = subprocess.run(
                ["python", excel_script,
                 "--evaluation", json_path,
                 "--output", excel_path],
                capture_output=True, text=True, timeout=60
            )
            if result_export.returncode == 0:
                print(f"{strings['status_ok']} Excel: {excel_path}")
            else:
                print(f"  Excel skip: {result_export.stderr[:200] if result_export.stderr else 'unknown error'}")
    except Exception as e:
        print(f"  Excel skip: {e}")

    # Print summary
    print("\n" + "=" * 50)
    print("Evaluation Summary" if args.lang == "en" else "评测摘要")
    print("=" * 50)

    status = result["reproduction_status"]
    status_icon = {
        "fully_reproduced": "[OK]" if args.lang == "en" else "[成功]",
        "partially_reproduced": "[WARN]" if args.lang == "en" else "[警告]",
        "failed_reproduction": "[FAIL]" if args.lang == "en" else "[失败]"
    }
    print(f"Status: {status_icon.get(status['overall'], '[?]')} {status['overall']}")

    print("\nMetrics:" if args.lang == "en" else "\n指标对比:")
    for gap in result["gap_analysis"]:
        target = gap.get("target", "N/A")
        achieved = gap.get("achieved")
        assessment = gap.get("assessment", "unknown")

        achieved_str = f"{achieved:.4f}" if achieved is not None else "N/A"
        gap_str = f"{gap.get('gap', 0):+.4f}" if achieved is not None else "N/A"
        assessment_str = strings.get(assessment, assessment)

        print(f"  {gap['metric_name']}: target={target}, achieved={achieved_str}, gap={gap_str} [{assessment_str}]")

    if status.get("issues"):
        print("\nIssues:" if args.lang == "en" else "\n问题:")
        for issue in status["issues"]:
            print(f"  {strings['status_warn']} {issue}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
