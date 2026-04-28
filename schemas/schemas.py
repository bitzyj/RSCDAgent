#!/usr/bin/env python3
"""
schemas.py - RSCDAgent JSON Schema 定义与校验模块

提供所有步骤产物的 JSON Schema 定义和校验功能。
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime


# ============ Schema 定义 ============

STEP1_PAPER_PARSE_SCHEMA = {
    "type": "object",
    "required": ["step", "status", "paper_info", "timestamp"],
    "properties": {
        "step": {"const": "paper_parse"},
        "status": {"enum": ["success", "failed", "partial"]},
        "paper_info": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "authors": {"type": "array", "items": {"type": "string"}},
                "year": {"type": "integer"},
                "venue": {"type": "string"}
            },
            "required": ["title", "authors", "year"]
        },
        "model_info": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "architecture": {"type": "string"},
                "backbone": {"type": "string"},
                "input_size": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                "framework": {"type": "string"}
            }
        },
        "training_config": {
            "type": "object",
            "properties": {
                "epochs": {"type": "integer"},
                "batch_size": {"type": "integer"},
                "optimizer": {"type": "string"},
                "learning_rate": {"type": "number"},
                "weight_decay": {"type": "number"},
                "loss_function": {"type": "string"},
                "scheduler": {"type": ["string", "null"]}
            }
        },
        "dataset_info": {
            "type": "object",
            "properties": {
                "dataset_name": {"type": "string"},
                "train_samples": {"type": "integer"},
                "val_samples": {"type": "integer"},
                "test_samples": {"type": "integer"},
                "image_size": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                "bands": {"type": "integer"}
            }
        },
        "target_metrics": {
            "type": "object",
            "properties": {
                "table_id": {"type": "string"},
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric_name": {"type": "string"},
                            "value": {"type": "number"},
                            "dataset": {"type": "string"},
                            "note": {"type": ["string", "null"]}
                        },
                        "required": ["metric_name", "value", "dataset"]
                    }
                }
            }
        },
        "execution_commands": {
            "type": "object",
            "properties": {
                "train_command": {"type": ["string", "null"]},
                "test_command": {"type": ["string", "null"]},
                "inference_command": {"type": ["string", "null"]}
            }
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
        "parse_errors": {"type": "array", "items": {"type": "string"}},
        "timestamp": {"type": "string", "format": "date-time"}
    }
}

STEP2_REPO_PARSE_SCHEMA = {
    "type": "object",
    "required": ["step", "status", "repo_info", "timestamp"],
    "properties": {
        "step": {"const": "repo_parse"},
        "status": {"enum": ["success", "failed", "partial"]},
        "repo_info": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "url": {"type": "string", "format": "uri"},
                "local_path": {"type": "string"},
                "default_branch": {"type": "string"},
                "language": {"type": "string"},
                "stars": {"type": ["integer", "null"]}
            },
            "required": ["name", "url", "local_path"]
        },
        "entry_points": {
            "type": "object",
            "properties": {
                "train": {
                    "type": "object",
                    "properties": {
                        "path": {"type": ["string", "null"]},
                        "main_file": {"type": ["string", "null"]},
                        "config_required": {"type": "boolean"}
                    }
                },
                "test": {
                    "type": "object",
                    "properties": {
                        "path": {"type": ["string", "null"]},
                        "main_file": {"type": ["string", "null"]}
                    }
                },
                "inference": {
                    "type": "object",
                    "properties": {
                        "path": {"type": ["string", "null"]},
                        "main_file": {"type": ["string", "null"]}
                    }
                }
            }
        },
        "config_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "type": {"enum": ["yaml", "json", "py", "toml"]},
                    "purpose": {"type": "string"}
                }
            }
        },
        "dataset_config": {
            "type": "object",
            "properties": {
                "config_path": {"type": ["string", "null"]},
                "train_split": {"type": ["string", "null"]},
                "val_split": {"type": ["string", "null"]},
                "test_split": {"type": ["string", "null"]}
            }
        },
        "checkpoint_info": {
            "type": "object",
            "properties": {
                "download_url": {"type": ["string", "null"]},
                "alternative_url": {"type": ["string", "null"]},
                "format": {"enum": ["pth", "pt", "ckpt", "h5", None]}
            }
        },
        "metrics_calculation": {
            "type": "object",
            "properties": {
                "metrics_file": {"type": ["string", "null"]},
                "implemented_metrics": {"type": "array", "items": {"type": "string"}}
            }
        },
        "dependencies": {
            "type": "object",
            "properties": {
                "requirements_file": {"type": ["string", "null"]},
                "dependencies": {"type": "array", "items": {"type": "string"}}
            }
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
        "parse_errors": {"type": "array", "items": {"type": "string"}},
        "timestamp": {"type": "string", "format": "date-time"}
    }
}

STEP3_DATASET_CHECK_SCHEMA = {
    "type": "object",
    "required": ["step", "status", "dataset_path", "summary", "timestamp"],
    "properties": {
        "step": {"const": "dataset_check"},
        "status": {"enum": ["pass", "warning", "fail"]},
        "dataset_path": {"type": "string"},
        "dataset_type": {"type": "string"},
        "split_analysis": {
            "type": "object",
            "properties": {
                "train": {
                    "type": "object",
                    "properties": {
                        "exists": {"type": "boolean"},
                        "a_count": {"type": "integer"},
                        "b_count": {"type": "integer"},
                        "label_count": {"type": "integer"}
                    }
                },
                "val": {
                    "type": "object",
                    "properties": {
                        "exists": {"type": "boolean"},
                        "a_count": {"type": "integer"},
                        "b_count": {"type": "integer"},
                        "label_count": {"type": "integer"}
                    }
                },
                "test": {
                    "type": "object",
                    "properties": {
                        "exists": {"type": "boolean"},
                        "a_count": {"type": "integer"},
                        "b_count": {"type": "integer"},
                        "label_count": {"type": "integer"}
                    }
                }
            }
        },
        "pairing_checks": {
            "type": "object",
            "properties": {
                "a_b_matched": {"type": "boolean"},
                "a_label_matched": {"type": "boolean"},
                "b_label_matched": {"type": "boolean"},
                "mismatched_files": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "filename": {"type": "string"},
                            "reason": {"type": "string"}
                        }
                    }
                }
            }
        },
        "image_checks": {
            "type": "object",
            "properties": {
                "size_consistency": {
                    "type": "object",
                    "properties": {
                        "consistent": {"type": "boolean"},
                        "mismatches": {"type": "array"}
                    }
                },
                "bit_depth": {"type": ["integer", "null"]},
                "format": {"type": "string"}
            }
        },
        "label_checks": {
            "type": "object",
            "properties": {
                "value_range": {
                    "type": "object",
                    "properties": {
                        "min": {"type": "integer"},
                        "max": {"type": "integer"}
                    }
                },
                "binary": {"type": "boolean"},
                "valid_values": {"type": "array", "items": {"type": "integer"}},
                "invalid_pixels": {"type": "number"}
            }
        },
        "tif_metadata": {
            "type": "object",
            "properties": {
                "has_geoinfo": {"type": "boolean"},
                "projection": {"type": ["string", "null"]},
                "resolution": {"type": ["array", "null"]}
            }
        },
        "temporal_checks": {
            "type": "object",
            "properties": {
                "has_timestamp": {"type": "boolean"},
                "time_gap_days": {"type": ["integer", "null"]},
                "offset_risk": {"enum": ["none", "low", "high"]}
            }
        },
        "anomalies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"enum": ["error", "warning", "info"]},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "affected_files": {"type": ["array", "null"]}
                }
            }
        },
        "summary": {
            "type": "object",
            "properties": {
                "total_errors": {"type": "integer"},
                "total_warnings": {"type": "integer"},
                "reproducible": {"type": "boolean"},
                "blocking_issues": {"type": "array", "items": {"type": "string"}}
            }
        },
        "timestamp": {"type": "string", "format": "date-time"}
    }
}

STEP4_PLAN_SCHEMA = {
    "type": "object",
    "required": ["step", "status", "plan_id", "recommended_steps", "timestamp"],
    "properties": {
        "step": {"const": "generate_plan"},
        "status": {"enum": ["success", "failed"]},
        "plan_id": {"type": "string"},
        "recommended_steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer"},
                    "action": {"type": "string"},
                    "command": {"type": ["string", "null"]},
                    "config_modifications": {"type": "array"},
                    "expected_output": {"type": "string"},
                    "risk_level": {"enum": ["low", "medium", "high"]},
                    "stop_condition": {"type": ["string", "null"]},
                    "retry_condition": {"type": ["string", "null"]},
                    "estimated_time": {"type": "string"}
                }
            }
        },
        "execution_order": {"type": "array", "items": {"type": "integer"}},
        "critical_risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "risk": {"type": "string"},
                    "mitigation": {"type": "string"},
                    "fallback": {"type": "string"}
                }
            }
        },
        "required_modifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "field": {"type": "string"},
                    "reason": {"type": "string"}
                }
            }
        },
        "estimated_total_time": {"type": "string"},
        "dry_run_recommended": {"type": "boolean"},
        "test_only_mode": {
            "type": "object",
            "properties": {
                "supported": {"type": "boolean"},
                "command": {"type": ["string", "null"]},
                "limitations": {"type": ["array", "null"]}
            }
        },
        "timestamp": {"type": "string", "format": "date-time"}
    }
}

STEP5_EXECUTION_SCHEMA = {
    "type": "object",
    "required": ["step", "status", "execution_id", "plan_reference", "timestamp"],
    "properties": {
        "step": {"const": "execution"},
        "status": {"enum": ["success", "failed", "partial"]},
        "execution_id": {"type": "string"},
        "plan_reference": {"type": "string"},
        "steps_executed": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_number": {"type": "integer"},
                    "action": {"type": "string"},
                    "command": {"type": ["string", "null"]},
                    "start_time": {"type": "string", "format": "date-time"},
                    "end_time": {"type": "string", "format": "date-time"},
                    "duration_seconds": {"type": "number"},
                    "exit_code": {"type": ["integer", "null"]},
                    "status": {"enum": ["success", "failed", "skipped"]},
                    "stdout": {"type": ["string", "null"]},
                    "stderr": {"type": ["string", "null"]},
                    "error_message": {"type": ["string", "null"]},
                    "artifacts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"enum": ["checkpoint", "log", "config", "output"]},
                                "path": {"type": "string"},
                                "size_bytes": {"type": ["integer", "null"]}
                            }
                        }
                    }
                }
            }
        },
        "modifications_made": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "original_content": {"type": "string"},
                    "new_content": {"type": "string"},
                    "reason": {"type": "string"},
                    "approved": {"type": "boolean"}
                }
            }
        },
        "env_state": {
            "type": "object",
            "properties": {
                "python_version": {"type": "string"},
                "cuda_available": {"type": "boolean"},
                "gpu_info": {"type": ["string", "null"]},
                "installed_packages": {"type": "array", "items": {"type": "string"}}
            }
        },
        "timestamp": {"type": "string", "format": "date-time"}
    }
}

STEP6_EVALUATION_SCHEMA = {
    "type": "object",
    "required": ["step", "status", "evaluation_id", "target_metrics", "achieved_metrics", "gap_analysis", "timestamp"],
    "properties": {
        "step": {"const": "evaluation"},
        "status": {"const": "completed"},
        "evaluation_id": {"type": "string"},
        "target_metrics": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "paper_url": {"type": ["string", "null"]},
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric_name": {"type": "string"},
                            "target_value": {"type": "number"},
                            "dataset": {"type": "string"}
                        }
                    }
                }
            }
        },
        "achieved_metrics": {
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric_name": {"type": "string"},
                            "achieved_value": {"type": ["number", "null"]},
                            "dataset": {"type": "string"},
                            "source_file": {"type": ["string", "null"]}
                        }
                    }
                }
            }
        },
        "gap_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric_name": {"type": "string"},
                    "target": {"type": "number"},
                    "achieved": {"type": ["number", "null"]},
                    "gap": {"type": ["number", "null"]},
                    "gap_percentage": {"type": ["number", "null"]},
                    "assessment": {"enum": ["acceptable", "mild_deviation", "significant_deviation", "critical"]}
                }
            }
        },
        "reproduction_status": {
            "type": "object",
            "properties": {
                "overall": {"enum": ["fully_reproduced", "partially_reproduced", "failed_reproduction"]},
                "metrics_match": {"type": ["boolean", "null"]},
                "code_runs": {"type": "boolean"},
                "data_available": {"type": "boolean"},
                "issues": {"type": ["array", "null"]}
            }
        },
        "detailed_report_path": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"}
    }
}


# ============ Schema Registry ============

SCHEMAS = {
    "step1_paper_parse": STEP1_PAPER_PARSE_SCHEMA,
    "step2_repo_parse": STEP2_REPO_PARSE_SCHEMA,
    "step3_dataset_check": STEP3_DATASET_CHECK_SCHEMA,
    "step4_plan": STEP4_PLAN_SCHEMA,
    "step5_execution": STEP5_EXECUTION_SCHEMA,
    "step6_evaluation": STEP6_EVALUATION_SCHEMA,
}


# ============ 校验函数 ============

def validate_json(data: Dict[str, Any], schema_name: str) -> Tuple[bool, List[str]]:
    """
    校验 JSON 数据是否符合 Schema

    Args:
        data: 要校验的 JSON 数据
        schema_name: Schema 名称 (如 "step1_paper_parse")

    Returns:
        (is_valid, error_messages)
    """
    import jsonschema
    from jsonschema import Draft7Validator

    if schema_name not in SCHEMAS:
        return False, [f"Unknown schema: {schema_name}"]

    schema = SCHEMAS[schema_name]
    validator = Draft7Validator(schema)
    errors = []

    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.path) if error.path else "root"
        errors.append(f"{path}: {error.message}")

    return len(errors) == 0, errors


def validate_file(file_path: str, schema_name: str) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    校验 JSON 文件是否符合 Schema

    Args:
        file_path: JSON 文件路径
        schema_name: Schema 名称

    Returns:
        (is_valid, error_messages, loaded_data)
    """
    if not os.path.exists(file_path):
        return False, [f"File not found: {file_path}"], {}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"JSON parse error: {e.msg} at line {e.lineno}"], {}

    is_valid, errors = validate_json(data, schema_name)
    return is_valid, errors, data


def load_step_output(outputs_dir: str, step_name: str) -> Optional[Dict[str, Any]]:
    """
    加载步骤产物 JSON 文件

    Args:
        outputs_dir: claude_outputs 目录路径
        step_name: 步骤名 (如 "step1_paper_parse")

    Returns:
        加载的 JSON 数据，失败返回 None
    """
    file_path = os.path.join(outputs_dir, f"{step_name}.json")
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def save_step_output(outputs_dir: str, step_name: str, data: Dict[str, Any]) -> str:
    """
    保存步骤产物 JSON 文件

    Args:
        outputs_dir: claude_outputs 目录路径
        step_name: 步骤名
        data: 要保存的数据

    Returns:
        保存的文件路径
    """
    os.makedirs(outputs_dir, exist_ok=True)
    file_path = os.path.join(outputs_dir, f"{step_name}.json")

    # 添加 timestamp
    if "timestamp" not in data:
        data["timestamp"] = datetime.now().isoformat()

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return file_path


def get_step_status(outputs_dir: str, step_name: str) -> Optional[str]:
    """获取步骤状态"""
    data = load_step_output(outputs_dir, step_name)
    if data:
        return data.get("status")
    return None


def is_step_completed(outputs_dir: str, step_name: str) -> bool:
    """判断步骤是否已完成"""
    status = get_step_status(outputs_dir, step_name)
    return status in ["success", "partial", "pass"]


def get_expected_outputs() -> List[str]:
    """获取所有期望的输出文件名"""
    return [
        "step1_paper_parse.json",
        "step2_repo_parse.json",
        "step3_dataset_check.json",
        "step4_plan.json",
        "step5_execution.json",
        "step6_evaluation.json",
    ]


# ============ 报告模板变量提取 ============

def extract_paper_info(data: Dict[str, Any]) -> Dict[str, Any]:
    """从 step1_paper_parse.json 提取报告需要的字段"""
    return {
        "title": data.get("paper_info", {}).get("title", "Unknown"),
        "authors": ", ".join(data.get("paper_info", {}).get("authors", [])),
        "year": data.get("paper_info", {}).get("year", "N/A"),
        "venue": data.get("paper_info", {}).get("venue", "N/A"),
        "model_name": data.get("model_info", {}).get("model_name", "Unknown"),
        "architecture": data.get("model_info", {}).get("architecture", "Unknown"),
        "epochs": data.get("training_config", {}).get("epochs", "N/A"),
        "batch_size": data.get("training_config", {}).get("batch_size", "N/A"),
        "optimizer": data.get("training_config", {}).get("optimizer", "Unknown"),
        "learning_rate": data.get("training_config", {}).get("learning_rate", "N/A"),
        "target_metrics": data.get("target_metrics", {}).get("metrics", []),
    }


def extract_dataset_check_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """从 step3_dataset_check.json 提取摘要"""
    summary = data.get("summary", {})
    split = data.get("split_analysis", {})

    return {
        "dataset_path": data.get("dataset_path", "Unknown"),
        "dataset_type": data.get("dataset_type", "Unknown"),
        "status": data.get("status", "unknown"),
        "total_errors": summary.get("total_errors", 0),
        "total_warnings": summary.get("total_warnings", 0),
        "reproducible": summary.get("reproducible", False),
        "train_count": split.get("train", {}).get("a_count", 0),
        "val_count": split.get("val", {}).get("a_count", 0),
        "test_count": split.get("test", {}).get("a_count", 0),
        "blocking_issues": summary.get("blocking_issues", []),
    }


def extract_evaluation_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """从 step6_evaluation.json 提取摘要"""
    status = data.get("reproduction_status", {})

    return {
        "evaluation_id": data.get("evaluation_id", "Unknown"),
        "overall_status": status.get("overall", "unknown"),
        "metrics_match": status.get("metrics_match"),
        "code_runs": status.get("code_runs", False),
        "data_available": status.get("data_available", False),
        "issues": status.get("issues", []),
        "gap_analysis": data.get("gap_analysis", []),
    }


# ============ CLI ============

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python schemas.py <command> <args...>")
        print("Commands:")
        print("  validate <file> <schema_name>")
        print("  check-outputs <outputs_dir>")
        print("  list-schemas")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "validate":
        file_path = sys.argv[2]
        schema_name = sys.argv[3] if len(sys.argv) > 3 else None

        if not schema_name:
            print("Error: schema_name required")
            sys.exit(1)

        is_valid, errors, data = validate_file(file_path, schema_name)
        if is_valid:
            print(f"✓ {file_path} is valid against {schema_name}")
        else:
            print(f"✗ {file_path} validation failed:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)

    elif cmd == "check-outputs":
        outputs_dir = sys.argv[2] if len(sys.argv) > 2 else "."
        expected = get_expected_outputs()

        print("Checking outputs in:", outputs_dir)
        print()
        all_ok = True
        for exp in expected:
            file_path = os.path.join(outputs_dir, exp)
            if os.path.exists(file_path):
                print(f"✓ {exp}")
            else:
                print(f"✗ {exp} (missing)")
                all_ok = False

        if all_ok:
            print("\n✓ All expected outputs present")
        else:
            print("\n✗ Some outputs missing")

    elif cmd == "list-schemas":
        print("Available schemas:")
        for name in SCHEMAS:
            print(f"  - {name}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
