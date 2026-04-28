#!/usr/bin/env python3
"""
parse_paper.py - Paper Parsing Module

Parses remote sensing change detection papers from PDF or URL to extract:
- Paper info (title, authors, year, venue)
- Model info (architecture, backbone, input size, framework)
- Training config (epoch, batch size, optimizer, learning rate, etc.)
- Dataset info
- Target metrics (from Table)
- Execution commands

Output:
- claude_outputs/step1_paper_parse.json
- reports/paper_summary.md

Usage:
    python parse_paper.py --paper <PAPER_PATH_OR_URL> --output_dir <DIR>
"""

import argparse
import json
import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# PDF parsing libraries
try:
    import pdfplumber
    PDF_BACKEND = "pdfplumber"
except ImportError:
    try:
        import PyPDF2
        PDF_BACKEND = "PyPDF2"
    except ImportError:
        PDF_BACKEND = None

try:
    import requests
    from bs4 import BeautifulSoup
    WEB_BACKEND = True
except ImportError:
    WEB_BACKEND = False


class PaperParser:
    """Paper parser"""

    # Known remote sensing change detection datasets
    KNOWN_DATASETS = [
        "LEVIR-CD", "LEVIR", "CDD", "Seasonal Variation CDD",
        "SysU-CD", "WHU-CD", "Google Dataset", "S2Looking",
        "Synthetic Dataset", "AIRS", "Bitwise"
    ]

    # Common optimizer patterns
    OPTIMIZER_PATTERNS = [
        r"(?:SGD|Adam|AdamW|RMSprop|Adagrad|Adadelta)[^\d]*([\d.e-]+)?",
        r"optimizer[:\s]+([A-Za-z]+)",
    ]

    # Common metric patterns
    METRIC_PATTERNS = [
        r"(?:F1|F1-score|F1 Score)[:\s]+([\d.]+)",
        r"(?:Precision|Recall|IoU|MAE)[:\s]+([\d.]+)",
        r"(?:OA|mF1|kappa|Kappa)[:\s]+([\d.]+)",
    ]

    def __init__(self, paper_path: str):
        self.paper_path = paper_path
        self.text = ""
        self.warnings: List[str] = []
        self.parse_errors: List[str] = []

        # Parse results
        self.result: Dict[str, Any] = {
            "step": "paper_parse",
            "status": "partial",
            "paper_info": {},
            "model_info": {},
            "training_config": {},
            "dataset_info": {},
            "target_metrics": {},
            "execution_commands": {},
            "warnings": [],
            "parse_errors": [],
            "timestamp": datetime.now().isoformat()
        }

    def parse(self) -> Dict[str, Any]:
        """Execute parsing"""
        if self._is_url(self.paper_path):
            self._parse_from_url()
        else:
            self._parse_from_pdf()

        self._extract_paper_info()
        self._extract_model_info()
        self._extract_training_config()
        self._extract_dataset_info()
        self._extract_target_metrics()
        self._extract_execution_commands()

        # Set status
        if not self.result["paper_info"].get("title"):
            self.result["status"] = "failed"
            self.result["parse_errors"].append("Cannot extract paper title")
        elif not self.result["target_metrics"].get("metrics"):
            self.result["status"] = "partial"
            self.warnings.append("Target metrics not found, please confirm manually")
        else:
            self.result["status"] = "success"

        self.result["warnings"] = self.warnings
        self.result["parse_errors"] = self.parse_errors

        return self.result

    def _is_url(self, path: str) -> bool:
        return path.startswith("http://") or path.startswith("https://")

    def _parse_from_pdf(self):
        """Parse text from PDF"""
        if not os.path.exists(self.paper_path):
            self.parse_errors.append(f"PDF file not found: {self.paper_path}")
            return

        if PDF_BACKEND == "pdfplumber":
            self._parse_with_pdfplumber()
        elif PDF_BACKEND == "PyPDF2":
            self._parse_with_pypdf2()
        else:
            self.parse_errors.append("PDF parsing library not installed. Run: pip install pdfplumber")
            # Try to extract text
            try:
                result = subprocess.run(
                    ["pdftotext", self.paper_path, "-"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    self.text = result.stdout
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.parse_errors.append("Cannot extract PDF text")

    def _parse_with_pdfplumber(self):
        """Parse using pdfplumber"""
        try:
            with pdfplumber.open(self.paper_path) as pdf:
                self.text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        self.text += page_text + "\n"

                if not self.text.strip():
                    self.warnings.append("PDF text extraction is empty, trying table extraction")
                    self._extract_tables_from_pdfplumber(pdf)
        except Exception as e:
            self.parse_errors.append(f"pdfplumber parsing failed: {str(e)}")

    def _extract_tables_from_pdfplumber(self, pdf):
        """Extract tables from pdfplumber"""
        try:
            for i, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table in tables:
                    self._process_table(table, page_num=i)
        except Exception as e:
            self.warnings.append(f"Table extraction failed: {str(e)}")

    def _parse_with_pypdf2(self):
        """Parse using PyPDF2"""
        try:
            with open(self.paper_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                self.text = ""
                for page in reader.pages:
                    self.text += page.extract_text() + "\n"
        except Exception as e:
            self.parse_errors.append(f"PyPDF2 parsing failed: {str(e)}")

    def _parse_from_url(self):
        """Parse from URL"""
        if not WEB_BACKEND:
            self.parse_errors.append("Web parsing library not installed. Run: pip install requests beautifulsoup4")
            return

        try:
            response = requests.get(self.paper_path, timeout=30)
            response.raise_for_status()

            # Try to parse as PDF
            content_type = response.headers.get("Content-Type", "")
            if "pdf" in content_type or self.paper_path.endswith(".pdf"):
                # Save to temp file and parse
                temp_pdf = "/tmp/temp_paper.pdf"
                with open(temp_pdf, "wb") as f:
                    f.write(response.content)
                self._parse_from_pdf()
                os.remove(temp_pdf)
                return

            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")
            self.text = soup.get_text()

            # Try to extract paper info
            title = soup.find("title") or soup.find("h1")
            if title:
                self.result["paper_info"]["title"] = title.get_text().strip()

        except requests.RequestException as e:
            self.parse_errors.append(f"URL request failed: {str(e)}")

    def _process_table(self, table: List[List[str]], page_num: int = 0):
        """Process extracted tables to find metrics table"""
        if not table or len(table) < 2:
            return

        # Check if it's a metrics table (contains F1, IoU, etc.)
        header = " ".join(str(cell) for cell in table[0] if cell).lower()
        metric_keywords = ["f1", "iou", "precision", "recall", "oa", "kappa", "mae"]

        if any(kw in header for kw in metric_keywords):
            # This is a metrics table
            metrics = []
            for row in table[1:]:
                if not row or len(row) < 2:
                    continue

                for i, cell in enumerate(row):
                    cell_lower = str(cell).lower()
                    if any(kw in cell_lower for kw in metric_keywords):
                        # Found metric name
                        metric_name = self._extract_metric_name(cell_lower, metric_keywords)
                        # Try to get value from same row
                        value = None
                        for j in [1, 2, 3] if i < len(row) else [1]:
                            try:
                                val_str = str(row[j]).strip()
                                val = float(re.search(r"[\d.]+", val_str).group())
                                value = val
                                break
                            except (ValueError, IndexError):
                                continue

                        if value is not None:
                            metrics.append({
                                "metric_name": metric_name,
                                "value": value,
                                "dataset": str(row[0]).strip() if row[0] else "Unknown",
                                "note": None
                            })

            if metrics:
                if not self.result["target_metrics"].get("metrics"):
                    self.result["target_metrics"]["metrics"] = []
                self.result["target_metrics"]["metrics"].extend(metrics)
                self.result["target_metrics"]["table_id"] = f"Table from page {page_num + 1}"

    def _extract_metric_name(self, cell_text: str, keywords: List[str]) -> str:
        """Extract metric name"""
        for kw in keywords:
            if kw in cell_text:
                if kw == "f1":
                    return "F1"
                elif kw == "iou":
                    return "IoU"
                elif kw == "oa":
                    return "OA"
                elif kw == "mae":
                    return "MAE"
                else:
                    return kw.capitalize()
        return cell_text.strip()

    def _extract_paper_info(self):
        """Extract paper basic info"""
        if not self.text:
            return

        # Title (usually the first large text)
        title_match = re.search(r"^#\s+(.+)$", self.text, re.MULTILINE)
        if not title_match:
            # Try first line as title
            lines = [l.strip() for l in self.text.split("\n") if l.strip()]
            if lines:
                self.result["paper_info"]["title"] = lines[0][:200]

        # Year
        year_match = re.search(r"\b(20\d{2})\b", self.text[:1000])
        if year_match:
            self.result["paper_info"]["year"] = int(year_match.group(1))

        # Authors (usually after title)
        author_match = re.search(r"(?:Authors?:|by\s+)(.+?)(?:\n|$)", self.text[:500], re.I)
        if author_match:
            authors_text = author_match.group(1)
            authors = [a.strip() for a in re.split(r"[,，;；\n]", authors_text) if a.strip()]
            self.result["paper_info"]["authors"] = authors[:10]  # Limit count

        # Try to get from URL
        if self._is_url(self.paper_path):
            url_parts = self.paper_path.split("/")
            for part in url_parts:
                if re.match(r"^\d{4}\.\d+\.html?$", part):
                    try:
                        self.result["paper_info"]["year"] = int(part[:4])
                    except ValueError:
                        pass

    def _extract_model_info(self):
        """Extract model info"""
        if not self.text:
            return

        text_lower = self.text.lower()

        # Architecture - common change detection architectures
        architectures = [
            (r"(?:FC-)?EF(?:usion)?", "Early Fusion"),
            (r"Siam(?:ese)?-?(?:FCN|network|concatenation)", "Siamese-FCN"),
            (r"UNet", "U-Net"),
            (r"DeepLab", "DeepLabV3"),
            (r"ResNet", "ResNet-based"),
            (r"STANet", "STANet"),
            (r"DSAMNet", "DSAMNet"),
            (r"Bi(?:t)?-?temporal", "Bi-temporal"),
        ]

        for pattern, arch_name in architectures:
            if re.search(pattern, text_lower, re.I):
                self.result["model_info"]["architecture"] = arch_name
                break

        # Backbone
        backbone_patterns = [
            (r"ResNet[_-]?(\d+)", lambda m: f"ResNet{m.group(1)}"),
            (r"VGG[_-]?(\d+)", lambda m: f"VGG{m.group(1)}"),
            (r"(?:EfficientNet|efficientnet)", "EfficientNet"),
        ]

        for pattern, extractor in backbone_patterns:
            match = re.search(pattern, text_lower, re.I)
            if match:
                try:
                    self.result["model_info"]["backbone"] = extractor(match)
                except:
                    self.result["model_info"]["backbone"] = pattern
                break

        # Input size
        input_match = re.search(r"(?:input|image)\s*size[:\s]*(\d+)\s*[x×]\s*(\d+)", text_lower)
        if input_match:
            self.result["model_info"]["input_size"] = [
                int(input_match.group(1)),
                int(input_match.group(2))
            ]

        # Framework
        if "pytorch" in text_lower or "torch" in text_lower:
            self.result["model_info"]["framework"] = "PyTorch"
        elif "tensorflow" in text_lower:
            self.result["model_info"]["framework"] = "TensorFlow"

    def _extract_training_config(self):
        """Extract training config"""
        if not self.text:
            return

        text_lower = self.text.lower()

        # Epochs
        epoch_match = re.search(r"epoch[s]?[:\s]+(\d+)", text_lower)
        if epoch_match:
            self.result["training_config"]["epochs"] = int(epoch_match.group(1))

        # Batch size
        batch_match = re.search(r"batch[_\s]?size[:\s]+(\d+)", text_lower)
        if batch_match:
            self.result["training_config"]["batch_size"] = int(batch_match.group(1))

        # Learning rate
        lr_match = re.search(r"(?:lr|learning[_\s]?rate)[:\s]+([\d.e-]+)", text_lower)
        if lr_match:
            try:
                self.result["training_config"]["learning_rate"] = float(lr_match.group(1))
            except ValueError:
                pass

        # Optimizer
        if re.search(r"\badamw?\b", text_lower):
            self.result["training_config"]["optimizer"] = "AdamW"
        elif re.search(r"\badam\b", text_lower):
            self.result["training_config"]["optimizer"] = "Adam"
        elif re.search(r"\bsgd\b", text_lower):
            self.result["training_config"]["optimizer"] = "SGD"

        # Weight decay
        wd_match = re.search(r"(?:weight[_\s]?decay)[:\s]+([\d.e-]+)", text_lower)
        if wd_match:
            try:
                self.result["training_config"]["weight_decay"] = float(wd_match.group(1))
            except ValueError:
                pass

        # Loss function
        loss_patterns = [
            (r"binary[_\s]?cross[_\s]?entropy", "BCE"),
            (r"(?:dice[_\s]?loss?|dice)", "Dice Loss"),
            (r"(?:focal[_\s]?loss?|focal)", "Focal Loss"),
            (r"(?:iou[_\s]?loss?|iou)", "IoU Loss"),
        ]

        for pattern, loss_name in loss_patterns:
            if re.search(pattern, text_lower):
                self.result["training_config"]["loss_function"] = loss_name
                break

        # Scheduler
        if re.search(r"(?:cosine[_\s]?annealing)", text_lower):
            self.result["training_config"]["scheduler"] = "Cosine Annealing"
        elif re.search(r"(?:step[_\s]?lr)", text_lower):
            self.result["training_config"]["scheduler"] = "Step LR"

    def _extract_dataset_info(self):
        """Extract dataset info"""
        if not self.text:
            return

        text_lower = self.text.lower()

        # Detect dataset name
        for dataset in self.KNOWN_DATASETS:
            if dataset.lower() in text_lower:
                self.result["dataset_info"]["dataset_name"] = dataset
                break

        # Sample counts
        sample_patterns = [
            r"(\d+)\s*(?:train(?:ing)?\s+)?samples?",
            r"(\d+)\s*(?:images?|pairs?)",
        ]

        counts = []
        for pattern in sample_patterns:
            matches = re.findall(pattern, text_lower)
            counts.extend([int(m) for m in matches if int(m) > 100])

        if counts:
            # Assume first large number is training samples
            self.result["dataset_info"]["train_samples"] = counts[0]
            if len(counts) > 1:
                self.result["dataset_info"]["test_samples"] = counts[1]
            if len(counts) > 2:
                self.result["dataset_info"]["val_samples"] = counts[2]

        # Image size
        img_match = re.search(r"(?:image\s*size|size)[:\s]*(\d+)\s*[x×]\s*(\d+)", text_lower)
        if img_match:
            self.result["dataset_info"]["image_size"] = [
                int(img_match.group(1)),
                int(img_match.group(2))
            ]

        # Band count
        bands_match = re.search(r"(\d+)\s*(?:band|channel)s?", text_lower)
        if bands_match:
            self.result["dataset_info"]["bands"] = int(bands_match.group(1))
        else:
            # Default RGB
            self.result["dataset_info"]["bands"] = 3

    def _extract_target_metrics(self):
        """Extract target metrics"""
        if not self.text:
            return

        metrics = []

        # Find Table
        table_pattern = r"(?:Table\s*\d+[^:]*|Results?[^:]*)\s*\n\s*((?:.+\n){3,20})"
        tables = re.findall(table_pattern, self.text, re.I)

        for table_text in tables:
            # Extract values
            metric_lines = re.findall(
                r"(?:[\d.]+)\s+(?:[\d.]+\s+)?(?:[\d.]+\s+)?([\d.]+)",
                table_text
            )
            for val_str in metric_lines:
                try:
                    val = float(val_str)
                    if 0 < val < 1.5:  # Reasonable metric range
                        metrics.append({
                            "metric_name": "F1",  # Default assume F1
                            "value": val,
                            "dataset": "Unknown",
                            "note": None
                        })
                except ValueError:
                    continue

        # Find common metric formats
        metric_formats = [
            (r"F1[:\s]+([\d.]+)", "F1"),
            (r"F1[- ]Score[:\s]+([\d.]+)", "F1"),
            (r"IoU[:\s]+([\d.]+)", "IoU"),
            (r"mIoU[:\s]+([\d.]+)", "mIoU"),
            (r"OA[:\s]+([\d.]+)", "OA"),
            (r"Precision[:\s]+([\d.]+)", "Precision"),
            (r"Recall[:\s]+([\d.]+)", "Recall"),
        ]

        for pattern, metric_name in metric_formats:
            matches = re.findall(pattern, self.text, re.I)
            for val_str in matches[:5]:  # Limit count
                try:
                    val = float(val_str)
                    metrics.append({
                        "metric_name": metric_name,
                        "value": val,
                        "dataset": "Paper",
                        "note": None
                    })
                except ValueError:
                    continue

        # Deduplicate
        seen = set()
        unique_metrics = []
        for m in metrics:
            key = (m["metric_name"], m["value"])
            if key not in seen:
                seen.add(key)
                unique_metrics.append(m)

        if unique_metrics:
            self.result["target_metrics"]["metrics"] = unique_metrics
            self.result["target_metrics"]["table_id"] = "Extracted from paper"

    def _extract_execution_commands(self):
        """Extract execution commands"""
        if not self.text:
            return

        # Find training commands
        train_patterns = [
            r"python\s+train\.py[^\n]*",
            r"bash\s+train\.sh[^\n]*",
            r"python\s+main\.py[^\n]*--[^\n]+train[^\n]*",
        ]

        for pattern in train_patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                self.result["execution_commands"]["train_command"] = match.group(0).strip()
                break

        # Find test commands
        test_patterns = [
            r"python\s+test\.py[^\n]*",
            r"bash\s+test\.sh[^\n]*",
            r"python\s+eval\.py[^\n]*",
        ]

        for pattern in test_patterns:
            match = re.search(pattern, self.text, re.I)
            if match:
                self.result["execution_commands"]["test_command"] = match.group(0).strip()
                break


def generate_markdown_report(data: Dict[str, Any], output_path: str):
    """使用 Jinja2 模板生成 Markdown 报告"""
    try:
        from jinja2 import Template
    except ImportError:
        print("Warning: Jinja2 not installed, skipping markdown report")
        return

    template_path = os.path.join(
        os.path.dirname(__file__),
        "..", "templates", "paper_summary.md.j2"
    )

    if not os.path.exists(template_path):
        # 内联简单模板
        template_str = open(os.path.join(
            os.path.dirname(__file__),
            "..", "templates", "paper_summary.md.j2"
        ), encoding="utf-8").read() if os.path.exists(template_path) else get_inline_template()

    with open(template_path, "r", encoding="utf-8") as f:
        template_str = f.read()

    template = Template(template_str)

    # 准备模板变量
    paper_info = data.get("paper_info", {})
    model_info = data.get("model_info", {})
    training_config = data.get("training_config", {})
    dataset_info = data.get("dataset_info", {})
    target_metrics = data.get("target_metrics", {})
    exec_commands = data.get("execution_commands", {})

    # 格式化输入尺寸
    input_size = model_info.get("input_size")
    if input_size and isinstance(input_size, list):
        input_size = f"{input_size[0]}x{input_size[1]}"

    # 格式化图像尺寸
    image_size = dataset_info.get("image_size")
    if image_size and isinstance(image_size, list):
        image_size = f"{image_size[0]}x{image_size[1]}"

    context = {
        "title": paper_info.get("title", "Unknown"),
        "authors": ", ".join(paper_info.get("authors", [])),
        "year": paper_info.get("year", "N/A"),
        "venue": paper_info.get("venue", "N/A"),
        "model_name": model_info.get("model_name", "Unknown"),
        "architecture": model_info.get("architecture", "Unknown"),
        "backbone": model_info.get("backbone", "N/A"),
        "input_size": input_size or "N/A",
        "framework": model_info.get("framework", "Unknown"),
        "epochs": training_config.get("epochs", "N/A"),
        "batch_size": training_config.get("batch_size", "N/A"),
        "optimizer": training_config.get("optimizer", "Unknown"),
        "learning_rate": training_config.get("learning_rate", "N/A"),
        "weight_decay": training_config.get("weight_decay", "N/A"),
        "loss_function": training_config.get("loss_function", "Unknown"),
        "scheduler": training_config.get("scheduler", "N/A"),
        "dataset_name": dataset_info.get("dataset_name", "Unknown"),
        "train_samples": dataset_info.get("train_samples", "N/A"),
        "val_samples": dataset_info.get("val_samples", "N/A"),
        "test_samples": dataset_info.get("test_samples", "N/A"),
        "image_size": image_size or "N/A",
        "bands": dataset_info.get("bands", "N/A"),
        "target_table_id": target_metrics.get("table_id", "N/A"),
        "target_metrics": target_metrics.get("metrics", []),
        "train_command": exec_commands.get("train_command", "N/A"),
        "test_command": exec_commands.get("test_command", "N/A"),
        "inference_command": exec_commands.get("inference_command", "N/A"),
        "warnings": data.get("warnings", []),
        "parse_errors": data.get("parse_errors", []),
        "timestamp": data.get("timestamp", datetime.now().isoformat()),
    }

    report = template.render(**context)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)


def get_inline_template() -> str:
    """当模板文件不存在时的内联模板"""
    return """# 论文摘要: {{ title }}

## 基本信息
- **标题**: {{ title }}
- **作者**: {{ authors }}
- **年份**: {{ year }}
- **Venue**: {{ venue }}

## 模型信息
- **架构**: {{ architecture }}
- **Backbone**: {{ backbone }}
- **输入尺寸**: {{ input_size }}
- **框架**: {{ framework }}

## 训练配置
- **Epochs**: {{ epochs }}
- **Batch Size**: {{ batch_size }}
- **Optimizer**: {{ optimizer }}
- **Learning Rate**: {{ learning_rate }}
- **Loss**: {{ loss_function }}

## 目标指标
{% for metric in target_metrics %}
- {{ metric.metric_name }}: {{ metric.value }} ({{ metric.dataset }})
{% endfor %}

*由 RSCDAgent 生成*
"""


def main():
    parser = argparse.ArgumentParser(
        description="RSCDAgent - Paper Parsing Module"
    )
    parser.add_argument(
        "--paper", "-p",
        required=True,
        help="Paper PDF file path or URL"
    )
    parser.add_argument(
        "--output_dir", "-o",
        default="./claude_outputs",
        help="Output directory (default: ./claude_outputs)"
    )
    parser.add_argument(
        "--reports_dir", "-r",
        default="./reports",
        help="Reports directory (default: ./reports)"
    )
    parser.add_argument(
        "--target", "-t",
        default="",
        help="Target table ID (e.g., 'Table 2')"
    )

    args = parser.parse_args()

    print(f"Parsing paper: {args.paper}")
    print(f"PDF parsing backend: {PDF_BACKEND or 'not installed'}")

    # Parse paper
    paper_parser = PaperParser(args.paper)
    result = paper_parser.parse()

    # Save JSON output
    json_path = os.path.join(args.output_dir, "step1_paper_parse.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"JSON output: {json_path}")

    # Generate Markdown report
    md_path = os.path.join(args.reports_dir, "paper_summary.md")
    generate_markdown_report(result, md_path)

    if os.path.exists(md_path):
        print(f"Markdown report: {md_path}")

    # Print summary
    print("\n" + "=" * 50)
    print("Parsing Summary")
    print("=" * 50)

    if result["paper_info"].get("title"):
        print(f"Title: {result['paper_info']['title'][:60]}...")
    if result["model_info"].get("architecture"):
        print(f"Architecture: {result['model_info']['architecture']}")
    if result["training_config"].get("epochs"):
        print(f"Epochs: {result['training_config']['epochs']}")
    if result["target_metrics"].get("metrics"):
        print(f"Target metrics: {len(result['target_metrics']['metrics'])}")
    else:
        print("Target metrics not found")

    print(f"\nStatus: {result['status']}")
    if result["warnings"]:
        print(f"Warnings: {len(result['warnings'])}")
    if result["parse_errors"]:
        print(f"Errors: {len(result['parse_errors'])}")

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
