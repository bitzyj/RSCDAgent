#!/usr/bin/env python3
"""
generate_patch.py - Patch Generation and Recording Module

Generates configuration modification patches based on reproduction plan,
with bilingual support (Chinese/English) based on user input language.

Features:
- Analyze configuration fields that need modification
- Generate diff format patches
- Verify patches don't involve sensitive modifications
- Record all changes to claude_outputs/

Usage:
    python generate_patch.py --plan <PLAN_JSON> --repo_path <REPO_PATH> --output_dir <DIR>
    python generate_patch.py --repo_path . --output_dir ./claude_outputs --lang zh
"""

import argparse
import json
import os
import re
import sys
import difflib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


# Internationalized strings
STRINGS = {
    "en": {
        "patch_generator": "Patch Generator",
        "file_not_found": "File not found",
        "forbidden_field": "Forbidden to modify sensitive field",
        "forbidden_dir": "Forbidden to modify system directory",
        "not_in_allowed_dir": "File not in allowed directory",
        "safe": "Safe",
        "pending": "Pending",
        "approved": "Approved",
        "rejected": "Rejected",
        "applied": "Applied",
        "approve": "Approve",
        "reject": "Reject",
        "apply": "Apply",
        "patch_list": "Patch List",
        "field_label": "Field",
        "modification": "Modification",
        "reason_label": "Reason",
        "audit_reminder": "After audit, you can execute:",
        "generated_patches": "Generated {count} patches",
        "saved_to": "Saved to",
        "patch_approved": "Patch approved",
        "patch_rejected": "Patch rejected",
        "patch_applied": "Patch applied",
        "error_not_found": "Patch not found",
        "error_not_approved": "Patch not approved",
        "error_apply_failed": "Failed to apply patch",
        "status_ok": "[OK]",
        "status_fail": "[FAIL]",
    },
    "zh": {
        "patch_generator": "Patch 生成器",
        "file_not_found": "文件不存在",
        "forbidden_field": "禁止修改敏感字段",
        "forbidden_dir": "禁止修改系统目录",
        "not_in_allowed_dir": "文件不在允许目录内",
        "safe": "安全",
        "pending": "待审核",
        "approved": "已批准",
        "rejected": "已拒绝",
        "applied": "已应用",
        "approve": "批准",
        "reject": "拒绝",
        "apply": "应用",
        "patch_list": "Patch 列表",
        "field_label": "字段",
        "modification": "修改",
        "reason_label": "原因",
        "audit_reminder": "审核后可以执行:",
        "generated_patches": "生成 {count} 个 patch",
        "saved_to": "保存位置",
        "patch_approved": "Patch 已批准",
        "patch_rejected": "Patch 已拒绝",
        "patch_applied": "Patch 已应用",
        "error_not_found": "Patch not found",
        "error_not_approved": "Patch not approved",
        "error_apply_failed": "Failed to apply patch",
        "status_ok": "[成功]",
        "status_fail": "[失败]",
    }
}


class PatchGenerator:
    """Patch generator with bilingual support"""

    def __init__(self, repo_path: str, lang: str = "en"):
        self.repo_path = Path(repo_path)
        self.lang = lang if lang in ["en", "zh"] else "en"
        self.strings = STRINGS[self.lang]
        self.allowed_fields = {
            "data_root", "data_dir", "dataset_path",
            "batch_size", "epochs", "learning_rate", "lr",
            "optimizer", "weight_decay",
            "checkpoint", "pretrained_path",
            "num_workers", "prefetch",
            "log_interval", "save_interval",
            "test_epoch", "val_epoch"
        }
        self.forbidden_fields = {
            "password", "token", "api_key", "secret",
            "credential", "auth", "private_key"
        }
        self.allowed_directories = {
            "configs/", "config/", "options/",
            "scripts/", "utils/", "tools/"
        }
        self.forbidden_directories = {
            "/etc/", "/usr/", "/bin/", "/sbin/",
            "~/.ssh/", "~/.aws/", ".git/"
        }

        self.patches: List[Dict[str, Any]] = []

    def generate_from_plan(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate patches from execution plan"""
        modifications = []

        for step in plan.get("recommended_steps", []):
            for mod in step.get("config_modifications", []):
                if mod:
                    modifications.append(mod)

        # Generate patches
        patches = []
        for mod in modifications:
            patch = self._create_patch(mod)
            if patch:
                patches.append(patch)

        self.patches = patches
        return patches

    def generate_from_dict(self, modifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate patches directly from modification suggestions"""
        patches = []
        for mod in modifications:
            patch = self._create_patch(mod)
            if patch:
                patches.append(patch)

        self.patches = patches
        return patches

    def _create_patch(self, mod: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a single patch"""
        file_path = mod.get("file", "")
        field = mod.get("field", "")
        new_value = mod.get("recommended_value", "")

        # Security check
        is_safe, reason = self._is_safe_modification(file_path, field)
        if not is_safe:
            return None

        # Read original file
        full_path = self.repo_path / file_path
        if not full_path.exists():
            return {
                "file": file_path,
                "status": "file_not_found",
                "error": f"{self.strings['file_not_found']}: {file_path}"
            }

        # Generate patch
        patch = {
            "id": f"patch_{len(self.patches) + 1}",
            "timestamp": datetime.now().isoformat(),
            "file": file_path,
            "field": field,
            "original_value": mod.get("current_value", "<not_found>"),
            "new_value": new_value,
            "reason": mod.get("reason", ""),
            "approved": False,  # Requires audit
            "status": "pending"
        }

        # Generate diff
        if full_path.suffix in [".yaml", ".yml", ".json", ".toml"]:
            diff = self._generate_config_diff(full_path, field, new_value)
            patch["diff"] = diff
            patch["diff_type"] = "inline"  # or "unified"
        else:
            patch["diff"] = self._generate_simple_diff(full_path, new_value)

        return patch

    def _is_safe_modification(self, file_path: str, field: str) -> Tuple[bool, str]:
        """Check if modification is safe"""

        # Check field name
        field_lower = field.lower()
        for forbidden in self.forbidden_fields:
            if forbidden in field_lower:
                return False, f"{self.strings['forbidden_field']}: {field}"

        # Check file path
        for forbidden in self.forbidden_directories:
            if forbidden in file_path:
                return False, f"{self.strings['forbidden_dir']}: {file_path}"

        # Check if in allowed directory
        allowed = False
        for allowed_dir in self.allowed_directories:
            if allowed_dir in file_path:
                allowed = True
                break

        if not allowed:
            return False, f"{self.strings['not_in_allowed_dir']}: {file_path}"

        return True, self.strings["safe"]

    def _generate_config_diff(self, file_path: Path, field: str, new_value: str) -> str:
        """生成配置文件 diff"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 简单实现：生成修改后的内容片段
            lines = content.split("\n")
            new_lines = []
            modified = False

            for line in lines:
                # 尝试匹配配置行
                if re.match(rf"\s*{field}\s*[=:]\s*", line):
                    indent = len(line) - len(line.lstrip())
                    indent_str = " " * indent
                    # 简单替换
                    new_line = f"{indent_str}{field}: {new_value}"
                    new_lines.append(new_line)
                    modified = True
                else:
                    new_lines.append(line)

            if not modified:
                # 添加新行
                new_lines.append(f"{field}: {new_value}")

            # 生成 diff 风格的输出
            diff_output = f"--- {file_path.name}\n+++ {file_path.name}\n"
            for i, (old, new) in enumerate(zip(lines, new_lines)):
                if old != new:
                    diff_output += f"@@ -{i+1} +{i+1} @@\n"
                    diff_output += f"-{old}\n+{new}\n"

            if not modified:
                diff_output += f"@@ -{len(lines)} +{len(lines)+1} @@\n"
                diff_output += f"+{field}: {new_value}\n"

            return diff_output

        except Exception as e:
            return f"Error generating diff: {str(e)}"

    def _generate_simple_diff(self, file_path: Path, new_value: str) -> str:
        """生成简单文件 diff"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            return f"""--- {file_path.name}
+++ {file_path.name}
@@ ... @@
[文件内容已修改]
建议修改: {new_value}
[完整 diff 需要文件系统访问]
"""
        except Exception as e:
            return f"Error: {str(e)}"

    def approve_patch(self, patch_id: str) -> bool:
        """Approve patch"""
        for patch in self.patches:
            if patch.get("id") == patch_id:
                patch["approved"] = True
                patch["status"] = "approved"
                patch["approved_at"] = datetime.now().isoformat()
                return True
        return False

    def reject_patch(self, patch_id: str, reason: str = "") -> bool:
        """Reject patch"""
        for patch in self.patches:
            if patch.get("id") == patch_id:
                patch["approved"] = False
                patch["status"] = "rejected"
                patch["rejected_at"] = datetime.now().isoformat()
                patch["reject_reason"] = reason
                return True
        return False

    def apply_patch(self, patch_id: str) -> Tuple[bool, str]:
        """Apply patch"""
        patch = None
        for p in self.patches:
            if p.get("id") == patch_id:
                patch = p
                break

        if not patch:
            return False, self.strings["error_not_found"]

        if not patch.get("approved"):
            return False, self.strings["error_not_approved"]

        file_path = self.repo_path / patch["file"]
        field = patch["field"]
        new_value = patch["new_value"]

        try:
            # Read file
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Modify
            lines = content.split("\n")
            new_lines = []
            modified = False

            for line in lines:
                if re.match(rf"\s*{field}\s*[=:]\s*", line):
                    indent = len(line) - len(line.lstrip())
                    new_lines.append(f"{' ' * indent}{field}: {new_value}")
                    modified = True
                else:
                    new_lines.append(line)

            if not modified:
                new_lines.append(f"{field}: {new_value}")

            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))

            patch["status"] = "applied"
            patch["applied_at"] = datetime.now().isoformat()

            return True, self.strings["patch_applied"]

        except Exception as e:
            return False, f"{self.strings['error_apply_failed']}: {str(e)}"

    def save_patches(self, output_dir: str) -> str:
        """Save patch records"""
        output_path = os.path.join(output_dir, "patches.json")

        data = {
            "generated_at": datetime.now().isoformat(),
            "total_patches": len(self.patches),
            "pending": len([p for p in self.patches if p.get("status") == "pending"]),
            "approved": len([p for p in self.patches if p.get("approved")]),
            "rejected": len([p for p in self.patches if p.get("status") == "rejected"]),
            "applied": len([p for p in self.patches if p.get("status") == "applied"]),
            "patches": self.patches
        }

        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return output_path


def main():
    parser = argparse.ArgumentParser(description="RSCDAgent - Patch Generation Module")
    parser.add_argument("--repo_path", "-r", required=True, help="Repository path")
    parser.add_argument("--plan", "-p", help="Execution plan JSON (optional)")
    parser.add_argument("--output_dir", "-o", default="./claude_outputs", help="Output directory")
    parser.add_argument("--lang", "-l", default="en", choices=["en", "zh"],
                        help="Output language (en/zh)")

    args = parser.parse_args()

    s = STRINGS[args.lang]

    print("=" * 50)
    print(f"RSCDAgent {s['patch_generator']}")
    print("=" * 50)

    generator = PatchGenerator(args.repo_path, args.lang)

    # Generate from plan or use defaults
    if args.plan and os.path.exists(args.plan):
        with open(args.plan, "r") as f:
            plan = json.load(f)
        patches = generator.generate_from_plan(plan)
    else:
        # Demo default modifications
        modifications = [
            {
                "file": "configs/BIT-LEVIR.yaml",
                "field": "data_root",
                "current_value": "./datasets",
                "recommended_value": "./datasets/LEVIR",
                "reason": "Need to specify correct dataset path"
            },
            {
                "file": "configs/BIT-LEVIR.yaml",
                "field": "batch_size",
                "current_value": 16,
                "recommended_value": 8,
                "reason": "Reduce memory usage"
            }
        ]
        patches = generator.generate_from_dict(modifications)

    # Save
    output_path = generator.save_patches(args.output_dir)

    print(f"\n{s['status_ok']} {s['generated_patches'].format(count=len(patches))}")
    print(f"  {s['saved_to']}: {output_path}")

    # Print summary
    print(f"\n{s['patch_list']}:")
    status_icon = {
        "pending": "[PENDING]",
        "approved": "[OK]",
        "rejected": "[FAIL]",
        "applied": "[APPLIED]"
    }
    for patch in patches:
        icon = status_icon.get(patch.get("status"), "[?]")

        print(f"\n  {icon} [{patch['id']}] {patch['file']}")
        print(f"      {s['field_label']}: {patch['field']}")
        print(f"      {s['modification']}: {patch['original_value']} -> {patch['new_value']}")
        print(f"      {s['reason_label']}: {patch['reason']}")

    print(f"\n{s['audit_reminder']}")
    print("  python generate_patch.py --approve <patch_id>")
    print("  python generate_patch.py --apply <patch_id>")

    return 0


if __name__ == "__main__":
    sys.exit(main())
