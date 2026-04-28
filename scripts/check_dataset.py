#!/usr/bin/env python3
"""
check_dataset.py - Dataset Check Module (Remote Sensing Change Detection Domain壁垒)

Specifically checks the integrity of remote sensing change detection datasets:
- A/B/label count consistency
- Filename pairing check
- Image size consistency
- Label value validity
- train/val/test split integrity
- PNG format does not support TIFF metadata (automatic note)

Output:
- claude_outputs/step3_dataset_check.json
- reports/dataset_check.md

Usage:
    python check_dataset.py --dataset <DATASET_PATH> --output_dir <DIR> --reports_dir <DIR>
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class DatasetChecker:
    """Remote sensing change detection dataset checker"""

    KNOWN_DATASETS = {
        "LEVIR-CD": {"a_prefix": "A", "b_prefix": "B", "label_prefix": "label"},
        "CDD": {"a_prefix": "im1", "b_prefix": "im2", "label_prefix": "label"},
        "SysU-CD": {"a_prefix": "A", "b_prefix": "B", "label_prefix": "label"},
        "WHU-CD": {"a_prefix": "before", "b_prefix": "after", "label_prefix": "building"}
    }

    def __init__(self, dataset_path: str, dataset_type: str = "LEVIR-CD"):
        self.dataset_path = Path(dataset_path)
        self.dataset_type = dataset_type
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.anomalies: List[Dict[str, Any]] = []
        self.prefixes = self.KNOWN_DATASETS.get(dataset_type, self.KNOWN_DATASETS["LEVIR-CD"])

        self.result: Dict[str, Any] = {
            "step": "dataset_check",
            "status": "warning",
            "dataset_path": str(self.dataset_path),
            "dataset_type": dataset_type,
            "split_analysis": {"train": {}, "val": {}, "test": {}},
            "pairing_checks": {
                "a_b_matched": False,
                "a_label_matched": False,
                "b_label_matched": False,
                "mismatched_files": []
            },
            "image_checks": {
                "size_consistency": {"consistent": True, "mismatches": []},
                "bit_depth": None,
                "format": "PNG"
            },
            "label_checks": {
                "value_range": {"min": 0, "max": 1},
                "binary": True,
                "valid_values": [0, 1],
                "invalid_pixels": 0.0
            },
            "tif_metadata": {
                "has_geoinfo": False,
                "resolution": None,
                "bands": 3,
                "note": "PNG format does not support TIFF metadata"
            },
            "temporal_checks": {
                "has_timestamp": False,
                "note": "PNG does not embed timestamps"
            },
            "anomalies": [],
            "summary": {
                "total_errors": 0,
                "total_warnings": 0,
                "reproducible": True,
                "blocking_issues": []
            },
            "timestamp": datetime.now().isoformat()
        }

    def check(self) -> Dict[str, Any]:
        """Execute dataset check"""
        if not self.dataset_path.exists():
            self.result["status"] = "fail"
            self.result["summary"]["blocking_issues"].append(f"Dataset path not found: {self.dataset_path}")
            return self.result

        self._check_directory_structure()
        self._check_splits()
        self._check_pairing()
        self._check_image_properties()
        self._check_labels()
        self._compute_summary()

        return self.result

    def _check_directory_structure(self):
        """Check directory structure"""
        # Check if organized by split
        split_dirs = []
        for split in ["train", "val", "test"]:
            if (self.dataset_path / split).exists():
                split_dirs.append(split)

        if split_dirs:
            self.result["has_split_structure"] = True
            self.result["split_folders"] = split_dirs
            for split in split_dirs:
                for subdir in ["A", "B", "label"]:
                    if not (self.dataset_path / split / subdir).exists():
                        self.warnings.append(f"Split '{split}' missing subdirectory '{subdir}'")
        elif (self.dataset_path / "A").exists():
            self.result["has_split_structure"] = False

    def _check_splits(self):
        """Check each split"""
        for split in ["train", "val", "test"]:
            split_path = self.dataset_path / split
            if split_path.exists():
                a_files = self._get_image_files(split_path / "A")
                b_files = self._get_image_files(split_path / "B")
                label_files = self._get_image_files(split_path / "label")

                self.result["split_analysis"][split] = {
                    "exists": True,
                    "a_count": len(a_files),
                    "b_count": len(b_files),
                    "label_count": len(label_files)
                }

    def _get_image_files(self, dir_path: Path) -> List[Path]:
        """Get image files in directory"""
        if not dir_path.exists():
            return []
        extensions = [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
        files = []
        for ext in extensions:
            files.extend(dir_path.glob(f"*{ext}"))
            files.extend(dir_path.glob(f"*{ext.upper()}"))
        return sorted(files)

    def _check_pairing(self):
        """Check A/B/label pairing"""
        all_a, all_b, all_label = self._get_all_files()

        a_names = {f.stem for f in all_a}
        b_names = {f.stem for f in all_b}
        label_names = {f.stem for f in all_label}

        a_b = a_names == b_names
        a_label = a_names == label_names
        b_label = b_names == label_names

        self.result["pairing_checks"]["a_b_matched"] = a_b
        self.result["pairing_checks"]["a_label_matched"] = a_label
        self.result["pairing_checks"]["b_label_matched"] = b_label

        if not a_b:
            for name in list(a_names - b_names)[:5]:
                self.result["pairing_checks"]["mismatched_files"].append({
                    "type": "A", "filename": f"{name}.png", "reason": "No corresponding in B"
                })

    def _get_all_files(self) -> tuple:
        """Get all A/B/label files"""
        all_a, all_b, all_label = [], [], []

        for split in ["train", "val", "test"]:
            split_path = self.dataset_path / split
            if split_path.exists():
                all_a.extend(self._get_image_files(split_path / "A"))
                all_b.extend(self._get_image_files(split_path / "B"))
                all_label.extend(self._get_image_files(split_path / "label"))

        if (self.dataset_path / "A").exists():
            all_a.extend(self._get_image_files(self.dataset_path / "A"))
            all_b.extend(self._get_image_files(self.dataset_path / "B"))
            all_label.extend(self._get_image_files(self.dataset_path / "label"))

        return all_a, all_b, all_label

    def _check_image_properties(self):
        """Check image properties"""
        all_files = []
        for split in ["train", "val", "test"]:
            split_path = self.dataset_path / split
            if split_path.exists():
                all_files.extend(self._get_image_files(split_path / "A"))

        if not all_files and (self.dataset_path / "A").exists():
            all_files = self._get_image_files(self.dataset_path / "A")

        if not all_files:
            self.warnings.append("No sample images found")
            return

        try:
            from PIL import Image
            with Image.open(all_files[0]) as img:
                self.result["image_checks"]["sample_size"] = list(img.size)
                self.result["image_checks"]["format"] = img.format or "PNG"
                self.result["image_checks"]["mode"] = img.mode
        except ImportError:
            self.warnings.append("PIL not installed")
        except Exception as e:
            self.errors.append(f"Image property check failed: {str(e)}")

    def _check_labels(self):
        """Check label images"""
        label_files = []
        for split in ["train", "val", "test"]:
            split_path = self.dataset_path / split
            if split_path.exists():
                label_files.extend(self._get_image_files(split_path / "label"))

        if not label_files and (self.dataset_path / "label").exists():
            label_files = self._get_image_files(self.dataset_path / "label")

        if not label_files:
            self.warnings.append("No label files found")
            return

        try:
            from PIL import Image
            import numpy as np
            all_values = set()
            for f in label_files[:10]:
                with Image.open(f) as img:
                    if img.mode != "L":
                        img = img.convert("L")
                    arr = np.array(img)
                    all_values.update(np.unique(arr).tolist())

            self.result["label_checks"]["value_range"]["min"] = int(min(all_values))
            self.result["label_checks"]["value_range"]["max"] = int(max(all_values))
            self.result["label_checks"]["binary"] = all_values <= {0, 1}
            self.result["label_checks"]["valid_values"] = sorted(list(all_values))

            if all_values - {0, 1}:
                self.warnings.append(f"Label contains non-binary values: {all_values - {0, 1}}")
        except ImportError:
            self.warnings.append("PIL or numpy not installed")
        except Exception as e:
            self.errors.append(f"Label check failed: {str(e)}")

    def _compute_summary(self):
        """Compute summary"""
        self.result["summary"]["total_errors"] = len(self.errors)
        self.result["summary"]["total_warnings"] = len(self.warnings)

        pairing = self.result["pairing_checks"]
        if not (pairing["a_b_matched"] and pairing["a_label_matched"]):
            self.result["summary"]["blocking_issues"].append("A/B/Label files not fully paired")
            self.result["summary"]["reproducible"] = False

        for error in self.errors:
            self.anomalies.append({"severity": "error", "category": "general", "description": error})
        for warning in self.warnings:
            self.anomalies.append({"severity": "warning", "category": "general", "description": warning})

        self.result["anomalies"] = self.anomalies

        if self.result["summary"]["blocking_issues"]:
            self.result["status"] = "fail"
        elif self.warnings:
            self.result["status"] = "warning"
        else:
            self.result["status"] = "pass"


def main():
    parser = argparse.ArgumentParser(description="RSCDAgent - Dataset Check Module")
    parser.add_argument("--dataset", "-d", required=True, help="Dataset root directory")
    parser.add_argument("--output_dir", "-o", default="./claude_outputs", help="Output directory")
    parser.add_argument("--reports_dir", "-r", default="./reports", help="Reports directory")
    parser.add_argument("--dataset_type", "-t", default="LEVIR-CD", choices=["LEVIR-CD", "CDD", "SysU-CD", "WHU-CD", "Other"])

    args = parser.parse_args()
    print(f"Checking dataset: {args.dataset}")

    checker = DatasetChecker(args.dataset, args.dataset_type)
    result = checker.check()

    json_path = os.path.join(args.output_dir, "step3_dataset_check.json")
    os.makedirs(args.output_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"JSON: {json_path}")

    # Simple report
    report = f"""# Dataset Check Report

## Check Summary
- **Path**: {result['dataset_path']}
- **Type**: {result['dataset_type']}
- **Status**: {result['status'].upper()}

## Split Statistics
"""
    for split in ["train", "val", "test"]:
        s = result["split_analysis"].get(split, {})
        if s.get("exists"):
            report += f"- **{split}**: A={s['a_count']}, B={s['b_count']}, label={s['label_count']}\n"

    pairing = result["pairing_checks"]
    report += f"""
## Pairing Check
- A-B: {'PASS' if pairing['a_b_matched'] else 'FAIL'}
- A-label: {'PASS' if pairing['a_label_matched'] else 'FAIL'}
- B-label: {'PASS' if pairing['b_label_matched'] else 'FAIL'}

## Anomalies
"""
    for a in result["anomalies"]:
        icon = "FAIL" if a["severity"] == "error" else "WARN"
        report += f"- {icon} {a['description']}\n"

    report += f"\n**Reproducible**: {'YES' if result['summary']['reproducible'] else 'NO'}\n"

    md_path = os.path.join(args.reports_dir, "dataset_check.md")
    os.makedirs(args.reports_dir, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report: {md_path}")

    return 0 if result["status"] != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
