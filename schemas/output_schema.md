# RSCDAgent 输出规范文档

> 定义每个步骤的输入、输出格式，以及报告结构。
> 参考 Paper2Agent 的 `claude_outputs/step*.json` 模式。

---

## 1. 步骤产物 (claude_outputs/)

每个步骤完成后生成一个 JSON 文件，保存在 `claude_outputs/` 目录。

### step1_paper_parse.json

**输入**: 论文 PDF/URL
**输出**: 论文结构化信息

```json
{
  "step": "paper_parse",
  "status": "success|failed|partial",
  "paper_info": {
    "title": "string",
    "authors": ["string"],
    "year": "int",
    "venue": "string"
  },
  "model_info": {
    "model_name": "string",
    "architecture": "string",
    "backbone": "string",
    "input_size": ["int", "int"],
    "framework": "string (PyTorch/TensorFlow)"
  },
  "training_config": {
    "epochs": "int",
    "batch_size": "int",
    "optimizer": "string (Adam/SGD)",
    "learning_rate": "float",
    "weight_decay": "float",
    "loss_function": "string",
    "scheduler": "string|null"
  },
  "dataset_info": {
    "dataset_name": "string",
    "train_samples": "int",
    "val_samples": "int",
    "test_samples": "int",
    "image_size": ["int", "int"],
    "bands": "int"
  },
  "target_metrics": {
    "table_id": "string (e.g., Table 2)",
    "metrics": [
      {
        "metric_name": "string (e.g., F1)",
        "value": "float",
        "dataset": "string",
        "note": "string|null"
      }
    ]
  },
  "execution_commands": {
    "train_command": "string|null",
    "test_command": "string|null",
    "inference_command": "string|null"
  },
  "warnings": ["string"],
  "parse_errors": ["string"],
  "timestamp": "ISO8601"
}
```

---

### step2_repo_parse.json

**输入**: GitHub URL
**输出**: 仓库结构化信息

```json
{
  "step": "repo_parse",
  "status": "success|failed|partial",
  "repo_info": {
    "name": "string",
    "url": "string",
    "local_path": "string",
    "default_branch": "string",
    "language": "string",
    "stars": "int|null"
  },
  "entry_points": {
    "train": {
      "path": "string|null",
      "main_file": "string|null",
      "config_required": "bool"
    },
    "test": {
      "path": "string|null",
      "main_file": "string|null"
    },
    "inference": {
      "path": "string|null",
      "main_file": "string|null"
    }
  },
  "config_files": [
    {
      "path": "string",
      "type": "yaml|json|py|toml",
      "purpose": "string"
    }
  ],
  "dataset_config": {
    "config_path": "string|null",
    "train_split": "string|null",
    "val_split": "string|null",
    "test_split": "string|null"
  },
  "checkpoint_info": {
    "download_url": "string|null",
    "alternative_url": "string|null",
    "format": "pth|pt|ckpt|h5"
  },
  "metrics_calculation": {
    "metrics_file": "string|null",
    "implemented_metrics": ["string"]
  },
  "dependencies": {
    "requirements_file": "string|null",
    "dependencies": ["string"]
  },
  "warnings": ["string"],
  "parse_errors": ["string"],
  "timestamp": "ISO8601"
}
```

---

### step3_dataset_check.json

**输入**: 本地数据集路径
**输出**: 数据检查结果 [领域壁垒]

```json
{
  "step": "dataset_check",
  "status": "pass|warning|fail",
  "dataset_path": "string",
  "dataset_type": "LEVIR-CD|CDD|SysU|WHU|Other",
  "split_analysis": {
    "train": {
      "exists": "bool",
      "a_count": "int",
      "b_count": "int",
      "label_count": "int"
    },
    "val": {
      "exists": "bool",
      "a_count": "int",
      "b_count": "int",
      "label_count": "int"
    },
    "test": {
      "exists": "bool",
      "a_count": "int",
      "b_count": "int",
      "label_count": "int"
    }
  },
  "pairing_checks": {
    "a_b_matched": "bool",
    "a_label_matched": "bool",
    "b_label_matched": "bool",
    "mismatched_files": [
      {
        "type": "a|b|label",
        "filename": "string",
        "reason": "string"
      }
    ]
  },
  "image_checks": {
    "size_consistency": {
      "consistent": "bool",
      "mismatches": [
        {
          "filename": "string",
          "expected_size": ["int", "int"],
          "actual_size": ["int", "int"]
        }
      ]
    },
    "bit_depth": "int|null",
    "format": "TIFF|JPG|PNG|Other"
  },
  "label_checks": {
    "value_range": {
      "min": "int",
      "max": "int"
    },
    "binary": "bool",
    "valid_values": ["int"],
    "invalid_pixels": "float (percentage)"
  },
  "tif_metadata": {
    "has_geoinfo": "bool",
    "projection": "string|null",
    "resolution": ["float", "float"]|null
  },
  "temporal_checks": {
    "has_timestamp": "bool",
    "time_gap_days": "int|null",
    "offset_risk": "none|low|high"
  },
  "anomalies": [
    {
      "severity": "error|warning|info",
      "category": "string",
      "description": "string",
      "affected_files": ["string"]|null
    }
  ],
  "summary": {
    "total_errors": "int",
    "total_warnings": "int",
    "reproducible": "bool",
    "blocking_issues": ["string"]
  },
  "timestamp": "ISO8601"
}
```

---

### step4_plan.json

**输入**: step1 + step2 + step3
**输出**: 复现执行计划

```json
{
  "step": "generate_plan",
  "status": "success|failed",
  "plan_id": "string (uuid)",
  "recommended_steps": [
    {
      "step_number": "int",
      "action": "string",
      "command": "string|null",
      "config_modifications": [
        {
          "file": "string",
          "field": "string",
          "current_value": "any",
          "recommended_value": "any",
          "reason": "string"
        }
      ],
      "expected_output": "string",
      "risk_level": "low|medium|high",
      "stop_condition": "string|null",
      "retry_condition": "string|null",
      "estimated_time": "string (e.g., 10min)"
    }
  ],
  "execution_order": ["int"],
  "critical_risks": [
    {
      "risk": "string",
      "mitigation": "string",
      "fallback": "string"
    }
  ],
  "required_modifications": [
    {
      "file": "string",
      "field": "string",
      "reason": "string"
    }
  ],
  "estimated_total_time": "string",
  "dry_run_recommended": "bool",
  "test_only_mode": {
    "supported": "bool",
    "command": "string|null",
    "limitations": ["string"]|null
  },
  "timestamp": "ISO8601"
}
```

---

### step5_execution.json

**输入**: step4_plan.json
**输出**: 执行结果

```json
{
  "step": "execution",
  "status": "success|failed|partial",
  "execution_id": "string (uuid)",
  "plan_reference": "string (plan_id)",
  "steps_executed": [
    {
      "step_number": "int",
      "action": "string",
      "command": "string|null",
      "start_time": "ISO8601",
      "end_time": "ISO8601",
      "duration_seconds": "float",
      "exit_code": "int|null",
      "status": "success|failed|skipped",
      "stdout": "string|null",
      "stderr": "string|null",
      "error_message": "string|null",
      "artifacts": [
        {
          "type": "checkpoint|log|config|output",
          "path": "string",
          "size_bytes": "int|null"
        }
      ]
    }
  ],
  "modifications_made": [
    {
      "file": "string",
      "original_content": "string",
      "new_content": "string",
      "reason": "string",
      "approved": "bool"
    }
  ],
  "env_state": {
    "python_version": "string",
    "cuda_available": "bool",
    "gpu_info": "string|null",
    "installed_packages": ["string"]
  },
  "timestamp": "ISO8601"
}
```

---

### step6_evaluation.json

**输入**: step5_execution.json + target metrics
**输出**: 评测结果

```json
{
  "step": "evaluation",
  "status": "completed",
  "evaluation_id": "string (uuid)",
  "metrics_calculation_method": "cm2score_confusion_matrix",
  "target_metrics": {
    "source": "string (Table ID)",
    "paper_url": "string|null",
    "metrics": [
      {
        "metric_name": "string",
        "target_value": "float",
        "dataset": "string"
      }
    ]
  },
  "achieved_metrics": {
    "metrics": [
      {
        "metric_name": "string",
        "achieved_value": "float|null",
        "dataset": "string",
        "source_file": "string|null",
        "calculation_method": "cm2score"
      }
    ]
  },
  "gap_analysis": [
    {
      "metric_name": "string",
      "target": "float",
      "achieved": "float|null",
      "gap": "float",
      "gap_percentage": "float",
      "assessment": "acceptable|mild_deviation|significant_deviation|critical|exceeded",
      "calculation_method": "cm2score"
    }
  ],
  "reproduction_status": {
    "overall": "fully_reproduced|partially_reproduced|failed_reproduction",
    "metrics_match": "bool|null",
    "code_runs": "bool",
    "data_available": "bool",
    "issues": ["string"]|null
  },
  "metrics_calculation": {
    "method": "cm2score",
    "formula": {
      "OA": "(TP+TN)/(TP+FN+FP+TN)",
      "Recall": "TP/(TP+FN)",
      "Precision": "TP/(TP+FP)",
      "F1": "2*Recall*Precision/(Recall+Precision)",
      "IoU": "TP/(TP+FP+FN)",
      "Kappa": "(OA-Pre)/(1-Pre)"
    }
  },
  "detailed_report_path": "reports/reproduction_report.md",
  "timestamp": "ISO8601"
}
```

---

## 2. 报告文件 (reports/)

### paper_summary.md

论文摘要报告（给人看）。

```markdown
# 论文摘要: {title}

## 基本信息
- **作者**: {authors}
- **年份**: {year}
- **会议/期刊**: {venue}

## 模型信息
- **模型名称**: {model_name}
- **架构**: {architecture}
- **Backbone**: {backbone}
- **输入尺寸**: {W}x{H}
- **框架**: {framework}

## 训练配置
- **Epochs**: {epochs}
- **Batch Size**: {batch_size}
- **Optimizer**: {optimizer}
- **学习率**: {lr}
- **Loss**: {loss_function}

## 目标指标
| 数据集 | 指标 | 值 |
|--------|------|-----|

## 复现建议
{建议}
```

### dataset_check.md

数据检查报告（给人看）。

```markdown
# 数据集检查报告

## 检查概要
- **数据集路径**: {path}
- **数据集类型**: {type}
- **检查状态**: PASS/WARNING/FAIL

## Split 统计
| Split | A数量 | B数量 | Label数量 | 状态 |
|-------|-------|-------|-----------|------|
| Train | ... | ... | ... | ✓/✗ |
| Val   | ... | ... | ... | ✓/✗ |
| Test  | ... | ... | ... | ✓/✗ |

## 问题汇总
{问题列表}

## 结论
{结论}
```

### reproduction_report.md

最终复现报告（给人看）。

```markdown
# 遥感变化检测论文复现报告

## 基本信息
- **论文**: {title}
- **仓库**: {repo_url}
- **复现日期**: {date}
- **复现状态**: {status}

## 执行摘要
{执行摘要}

## 指标对比
| 指标 | 论文目标 | 实际复现 | 差距 | 评估 |
|------|----------|----------|------|------|

## Gap Analysis
{gap分析}

## 问题与风险
{问题列表}

## 建议
{建议}
```

### final_assessment.json

最终评估（给程序读）。

```json
{
  "assessment_id": "string",
  "paper": {
    "title": "string",
    "url": "string|null"
  },
  "repo": {
    "name": "string",
    "url": "string"
  },
  "reproduction": {
    "status": "fully_reproduced|partially_reproduced|failed",
    "reproducible_as_test_only": "bool",
    "requires_modifications": ["string"]|null,
    "blocking_issues": ["string"]|null
  },
  "metrics_comparison": [
    {
      "metric": "string",
      "target": "float",
      "achieved": "float|null",
      "gap": "float|null",
      "pass": "bool"
    }
  ],
  "data_quality": {
    "status": "pass|warning|fail",
    "issues": ["string"]|null
  },
  "recommendations": ["string"],
  "timestamp": "ISO8601"
}
```

---

## 3. 文件命名规范

| 类型 | 命名格式 | 示例 |
|------|----------|------|
| 步骤产物 | `step{N}_{name}.json` | `step1_paper_parse.json` |
| 报告 | `{name}.md` | `paper_summary.md` |
| 模板 | `{name}.j2` | `paper_summary.md.j2` |
| 评估 | `final_assessment.json` | `final_assessment.json` |

---

## 4. 状态字段枚举

| 步骤状态 | 值 | 说明 |
|----------|-----|------|
| step status | `success`, `failed`, `partial`, `skipped` | 步骤执行状态 |
| dataset_check status | `pass`, `warning`, `fail` | 数据检查状态 |
| reproduction status | `fully_reproduced`, `partially_reproduced`, `failed_reproduction` | 复现状态 |
| gap assessment | `acceptable`, `mild_deviation`, `significant_deviation`, `critical`, `exceeded` | 差距评估 |

---

## 5. 标准指标计算 (cm2score)

### 计算方法

所有变化检测指标统一使用 **cm2score** 方法，基于混淆矩阵计算：

```python
def cm2score(confusion_matrix):
    """
    基于混淆矩阵计算变化检测指标
    confusion_matrix: 2x2 矩阵 [[TN, FP], [FN, TP]]
    """
    tp = confusion_matrix[1, 1]
    fn = confusion_matrix[1, 0]
    fp = confusion_matrix[0, 1]
    tn = confusion_matrix[0, 0]

    oa = (tp + tn) / (tp + fn + fp + tn)
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    f1 = 2 * recall * precision / (recall + precision)
    iou = tp / (tp + fp + fn)
    pre = ((tp+fn)*(tp+fp) + (tn+fp)*(tn+fn)) / (tp+fp+tn+fn)**2
    kappa = (oa - pre) / (1 - pre)

    return {'Kappa': kappa, 'IoU': iou, 'F1': f1, 'OA': oa,
            'recall': recall, 'precision': precision, 'Pre': pre}
```

### 指标公式

| 指标 | 公式 | 说明 |
|------|------|------|
| **OA** | (TP+TN)/(TP+FN+FP+TN) | 总体准确率 |
| **Recall** | TP/(TP+FN) | 召回率 (Sensitivity) |
| **Precision** | TP/(TP+FP) | 精确率 |
| **F1** | 2×Recall×Precision/(Recall+Precision) | F1 分数 |
| **IoU** | TP/(TP+FP+FN) | 交并比 (Jaccard Index) |
| **Kappa** | (OA-Pre)/(1-Pre) | Cohen's Kappa 系数 |
| **Pre** | 期望准确率 | 用于 Kappa 计算 |

### Gap Assessment 标准

| 差距范围 | 评估结果 |
|----------|----------|
| < 1% | acceptable |
| 1-2% | mild_deviation |
| 2-5% | significant_deviation |
| >= 5% (正差距) | exceeded |
| >= 5% (负差距) | critical |

### 评估结果状态

| 状态 | 说明 |
|------|------|
| fully_reproduced | 所有指标差距 < 2% |
| partially_reproduced | 部分指标达标 |
| failed_reproduction | 代码执行失败或数据不可用 |
