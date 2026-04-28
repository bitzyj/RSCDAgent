#!/usr/bin/env python3
"""
mcp.py - RSCDAgent MCP Server

An automated paper reproduction system for remote sensing change detection.
Supports bilingual output (Chinese/English) based on user input language.

Usage:
    # Install as Claude Code MCP Server
    fastmcp install claude-code src/mcp.py --python .venv/bin/python

    # Or run directly for testing
    python src/mcp.py
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np


# ============== Standard Metrics Calculation (cm2score) ==============

def cm2score(confusion_matrix):
    """
    Calculate change detection metrics based on confusion matrix

    Args:
        confusion_matrix: 2x2 confusion matrix [[TN, FP], [FN, TP]]

    Returns:
        Dictionary containing Kappa, IoU, F1, OA, Recall, Precision, Pre
    """
    hist = confusion_matrix
    tp = hist[1, 1]
    fn = hist[1, 0]
    fp = hist[0, 1]
    tn = hist[0, 0]

    oa = (tp + tn) / (tp + fn + fp + tn + np.finfo(np.float32).eps)
    recall = tp / (tp + fn + np.finfo(np.float32).eps)
    precision = tp / (tp + fp + np.finfo(np.float32).eps)
    f1 = 2 * recall * precision / (recall + precision + np.finfo(np.float32).eps)
    iou = tp / (tp + fp + fn + np.finfo(np.float32).eps)
    pre = ((tp + fn) * (tp + fp) + (tn + fp) * (tn + fn)) / (tp + fp + tn + fn) ** 2
    kappa = (oa - pre) / (1 - pre)

    return {
        'Kappa': kappa, 'IoU': iou, 'F1': f1, 'OA': oa,
        'recall': recall, 'precision': precision, 'Pre': pre
    }


# MCP Server base class
try:
    from mcp.server import MCPServer
    from mcp.types import Tool, ToolInputSchema
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("Warning: MCP SDK not installed. Install with: pip install mcp")


# ============== Configuration ==============

PROJECT_CONFIG = {
    "project_name": "",   # Set by RSCDAgent.sh
    "repo_url": "",       # Set by RSCDAgent.sh
    "paper_title": "",    # Set by RSCDAgent.sh
    "dataset_type": "",   # Set by RSCDAgent.sh
    "target_metrics": {},
    "model_config": {}
}

# Path configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = Path(__file__).parent.parent
CLAUDE_OUTPUTS_DIR = PROJECT_DIR / "claude_outputs"
REPORTS_DIR = PROJECT_DIR / "reports"
SCRIPTS_DIR = PROJECT_DIR / "scripts"


# ============== Tool Implementation ==============

def _load_step_json(step_num: int) -> Dict[str, Any]:
    """Load step JSON file"""
    step_file = CLAUDE_OUTPUTS_DIR / f"step{step_num}_*.json"
    # Find matching file
    for f in CLAUDE_OUTPUTS_DIR.glob(f"step{step_num}_*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return {}


class RSCDTools:
    """RSCDAgent tool collection with bilingual support"""

    # Internationalized messages
    STRINGS = {
        "en": {
            "file_not_exist": "File does not exist",
            "path_not_exist": "Path does not exist",
            "no_logs": "No logs available",
            "report_not_exist": "Report does not exist",
            "stop_recorded": "Stop request recorded",
            "stop_action": "Execution will stop at next checkpoint"
        },
        "zh": {
            "file_not_exist": "文件不存在",
            "path_not_exist": "路径不存在",
            "no_logs": "暂无日志",
            "report_not_exist": "报告不存在",
            "stop_recorded": "停止请求已记录",
            "stop_action": "下一个检查点将停止执行"
        }
    }

    @staticmethod
    def parse_paper(paper_path: str) -> Dict[str, Any]:
        """
        Parse paper PDF and extract experimental configuration

        Args:
            paper_path: Paper PDF file path or URL

        Returns:
            Dictionary containing paper parsing results
        """
        if not os.path.exists(paper_path) and not paper_path.startswith("http"):
            return {
                "status": "error",
                "message": f"Paper file does not exist: {paper_path}"
            }

        # Actually call parse_paper.py
        return _load_step_json(1)

    @staticmethod
    def inspect_repo(repo_path: str) -> Dict[str, Any]:
        """
        Inspect GitHub repository structure

        Args:
            repo_path: Repository local path

        Returns:
            Dictionary containing repository parsing results
        """
        if not os.path.exists(repo_path):
            return {
                "status": "error",
                "message": f"Repository path does not exist: {repo_path}"
            }

        return _load_step_json(2)

    @staticmethod
    def check_dataset(dataset_path: str, dataset_type: str = "LEVIR-CD") -> Dict[str, Any]:
        """
        Check remote sensing change detection dataset

        Args:
            dataset_path: Dataset root directory
            dataset_type: Dataset type (LEVIR-CD, CDD, SysU-CD)

        Returns:
            Dictionary containing dataset check results
        """
        if not os.path.exists(dataset_path):
            return {
                "status": "error",
                "message": f"Dataset path does not exist: {dataset_path}"
            }

        return _load_step_json(3)

    @staticmethod
    def generate_plan(target: str = "Table 2", mode: str = "testonly") -> Dict[str, Any]:
        """
        Generate reproduction execution plan

        Args:
            target: Target metrics table (e.g., "Table 2")
            mode: Execution mode (testonly / short / full / skip)

        Returns:
            Dictionary containing execution plan
        """
        return _load_step_json(4)

    @staticmethod
    def run_repro(start_step: int = 1) -> Dict[str, Any]:
        """
        Execute reproduction task

        Args:
            start_step: Starting step number

        Returns:
            Dictionary containing execution results
        """
        return _load_step_json(5)

    @staticmethod
    def evaluate_repro() -> Dict[str, Any]:
        """
        Evaluate reproduction results

        Returns:
            Dictionary containing evaluation results
        """
        return _load_step_json(6)

    @staticmethod
    def get_status() -> Dict[str, Any]:
        """
        Get current reproduction status

        Returns:
            Dictionary containing real-time status
        """
        status_file = CLAUDE_OUTPUTS_DIR / "execution_status.json"
        if status_file.exists():
            with open(status_file, "r", encoding="utf-8") as f:
                return {"status": "success", "data": json.load(f)}

        return {
            "status": "success",
            "data": {
                "current_step": -1,
                "steps": [],
                "overall_status": "no_execution"
            }
        }

    @staticmethod
    def stop_repro() -> Dict[str, Any]:
        """
        Stop current reproduction task

        Returns:
            Dictionary containing stop operation results
        """
        stop_marker = CLAUDE_OUTPUTS_DIR / ".stop_requested"

        try:
            with open(stop_marker, "w") as f:
                f.write(__import__("datetime").datetime.now().isoformat())

            return {
                "status": "success",
                "message": RSCDTools.STRINGS["en"]["stop_recorded"],
                "stop_marker": str(stop_marker),
                "action": RSCDTools.STRINGS["en"]["stop_action"]
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Stop request failed: {str(e)}"
            }

    @staticmethod
    def get_logs(lines: int = 100) -> Dict[str, Any]:
        """
        Get execution logs

        Args:
            lines: Number of log lines to return

        Returns:
            Dictionary containing log content
        """
        log_dir = CLAUDE_OUTPUTS_DIR / "logs"
        if not log_dir.exists():
            return {
                "status": "success",
                "logs": [],
                "message": RSCDTools.STRINGS["en"]["no_logs"]
            }

        logs = []
        for log_file in sorted(log_dir.glob("*.jsonl"))[-3:]:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line))
                    except:
                        pass

        logs = logs[-lines:] if len(logs) > lines else logs
        return {
            "status": "success",
            "logs": logs,
            "count": len(logs)
        }

    @staticmethod
    def get_report(report_type: str = "reproduction") -> Dict[str, Any]:
        """
        Get reproduction report

        Args:
            report_type: Report type (reproduction / paper / dataset)

        Returns:
            Dictionary containing report content
        """
        report_map = {
            "reproduction": "reproduction_report.md",
            "paper": "paper_summary.md",
            "dataset": "dataset_check.md"
        }

        report_file = REPORTS_DIR / report_map.get(report_type, "reproduction_report.md")

        if not report_file.exists():
            return {
                "status": "error",
                "message": f"Report does not exist: {report_type}"
            }

        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "status": "success",
            "report_type": report_type,
            "content": content,
            "file": str(report_file)
        }

    @staticmethod
    def cm2score_from_matrix(matrix: List[List[int]]) -> Dict[str, float]:
        """
        Calculate metrics from confusion matrix

        Args:
            matrix: 2x2 confusion matrix [[TN, FP], [FN, TP]]

        Returns:
            Dictionary containing calculation results
        """
        matrix = np.array(matrix)
        return cm2score(matrix)


# ============== MCP Server ==============

if MCP_AVAILABLE:
    class RSCDAgentServer(MCPServer):
        """RSCDAgent MCP Server"""

        def __init__(self, name: str = "RSCDAgent"):
            super().__init__(name)
            self._register_tools()

        def _register_tools(self):
            """Register all tools"""
            self.add_tool(
                Tool(
                    name="parse_paper",
                    description="Parse paper PDF and extract experimental configuration, target metrics",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "paper_path": {"type": "string", "description": "Paper PDF path"}
                        },
                        "required": ["paper_path"]
                    }
                )
            )

            self.add_tool(
                Tool(
                    name="inspect_repo",
                    description="Inspect GitHub repository structure",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "repo_path": {"type": "string", "description": "Repository local path"}
                        },
                        "required": ["repo_path"]
                    }
                )
            )

            self.add_tool(
                Tool(
                    name="check_dataset",
                    description="Check remote sensing change detection dataset",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "dataset_path": {"type": "string", "description": "Dataset root directory"},
                            "dataset_type": {"type": "string", "description": "Dataset type"}
                        },
                        "required": ["dataset_path"]
                    }
                )
            )

            self.add_tool(
                Tool(
                    name="generate_plan",
                    description="Generate reproduction execution plan",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "target": {"type": "string", "description": "Target metrics table"},
                            "mode": {"type": "string", "description": "Execution mode"}
                        }
                    }
                )
            )

            self.add_tool(
                Tool(
                    name="run_repro",
                    description="Execute reproduction task",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "start_step": {"type": "integer", "description": "Starting step number"}
                        }
                    }
                )
            )

            self.add_tool(
                Tool(
                    name="evaluate_repro",
                    description="Evaluate reproduction results",
                    input_schema={"type": "object", "properties": {}}
                )
            )

            self.add_tool(
                Tool(
                    name="get_status",
                    description="Get current reproduction status",
                    input_schema={"type": "object", "properties": {}}
                )
            )

            self.add_tool(
                Tool(
                    name="stop_repro",
                    description="Stop current reproduction task",
                    input_schema={"type": "object", "properties": {}}
                )
            )

            self.add_tool(
                Tool(
                    name="get_logs",
                    description="Get execution logs",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "lines": {"type": "integer", "description": "Number of log lines"}
                        }
                    }
                )
            )

            self.add_tool(
                Tool(
                    name="get_report",
                    description="Get reproduction report",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "report_type": {"type": "string", "description": "Report type"}
                        }
                    }
                )
            )


def main():
    """Main function - Start MCP Server"""
    print("=" * 50)
    print("RSCDAgent MCP Server")
    print("=" * 50)
    print(f"Project: {PROJECT_CONFIG['paper_title'] or 'RSCDAgent'}")
    print(f"Repo: {PROJECT_CONFIG['repo_url'] or 'N/A'}")
    print(f"Dataset: {PROJECT_CONFIG['dataset_type'] or 'N/A'}")
    print("=" * 50)

    if MCP_AVAILABLE:
        print("\nStarting MCP Server...")
        server = RSCDAgentServer()
        server.run()
    else:
        print("\nMCP SDK not installed.")
        print("Install with: pip install mcp")
        print("\nYou can still test tools directly:")
        print("  python -c 'from mcp import RSCDTools; print(RSCDTools.get_status())'")


if __name__ == "__main__":
    main()
