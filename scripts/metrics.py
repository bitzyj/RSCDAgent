#!/usr/bin/env python3
"""
metrics.py - 变化检测指标计算模块

提供标准化的变化检测指标计算方式，基于混淆矩阵计算：
- Kappa
- IoU
- F1
- OA (Overall Accuracy)
- Recall
- Precision
- Pre

用法:
    from metrics import cm2score
    score_dict = cm2score(confusion_matrix)
"""

import numpy as np
from typing import Dict, Any, Optional


def cm2score(confusion_matrix: np.ndarray) -> Dict[str, float]:
    """
    根据混淆矩阵计算所有变化检测指标

    Args:
        confusion_matrix: 2x2 混淆矩阵
                         [[TN, FP],
                          [FN, TP]]

    Returns:
        包含以下指标的字典:
        - Kappa: Cohen's Kappa 系数
        - IoU: Intersection over Union (Jaccard Index)
        - F1: F1 Score
        - OA: Overall Accuracy
        - recall: Recall (Sensitivity)
        - precision: Precision
        - Pre: Expected accuracy (用于 Kappa 计算)
    """
    hist = confusion_matrix
    tp = hist[1, 1]
    fn = hist[1, 0]
    fp = hist[0, 1]
    tn = hist[0, 0]

    # Overall Accuracy
    oa = (tp + tn) / (tp + fn + fp + tn + np.finfo(np.float32).eps)

    # Recall (Sensitivity, True Positive Rate)
    recall = tp / (tp + fn + np.finfo(np.float32).eps)

    # Precision
    precision = tp / (tp + fp + np.finfo(np.float32).eps)

    # F1 Score
    f1 = 2 * recall * precision / (recall + precision + np.finfo(np.float32).eps)

    # IoU (Jaccard Index)
    iou = tp / (tp + fp + fn + np.finfo(np.float32).eps)

    # Expected accuracy (用于 Kappa 计算)
    # Pre = ((TP+FN) * (TP+FP) + (TN+FP) * (TN+FN)) / (TP+FP+TN+FN)^2
    pre = ((tp + fn) * (tp + fp) + (tn + fp) * (tn + fn)) / (tp + fp + tn + fn) ** 2

    # Kappa
    kappa = (oa - pre) / (1 - pre)

    score_dict = {
        'Kappa': kappa,
        'IoU': iou,
        'F1': f1,
        'OA': oa,
        'recall': recall,
        'precision': precision,
        'Pre': pre
    }

    return score_dict


def confusion_matrix_from_predictions(y_true: np.ndarray, y_pred: np.ndarray,
                                      n_class: int = 2) -> np.ndarray:
    """
    从预测结果和真实标签构建混淆矩阵

    Args:
        y_true: 真实标签 (H, W) 或 (N,)
        y_pred: 预测标签 (H, W) 或 (N,)
        n_class: 类别数量

    Returns:
        n_class x n_class 混淆矩阵
    """
    if y_true.ndim > 1:
        y_true = y_true.flatten()
    if y_pred.ndim > 1:
        y_pred = y_pred.flatten()

    # 构建混淆矩阵
    mask = (y_true >= 0) & (y_true < n_class)
    indices = n_class * y_true[mask].astype(int) + y_pred[mask].astype(int)
    hist = np.bincount(indices, minlength=n_class * n_class).reshape(n_class, n_class)

    return hist


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                      n_class: int = 2) -> Dict[str, float]:
    """
    从预测结果和真实标签直接计算所有指标

    Args:
        y_true: 真实标签
        y_pred: 预测标签
        n_class: 类别数量

    Returns:
        包含所有指标的字典
    """
    cm = confusion_matrix_from_predictions(y_true, y_pred, n_class)
    return cm2score(cm)


def metrics_to_dict(metrics: Dict[str, float],
                   prefix: str = "",
                   precision: int = 4) -> Dict[str, Any]:
    """
    将指标字典转换为可序列化的格式

    Args:
        metrics: 指标字典
        prefix: 前缀 (如 "train_" 或 "val_")
        precision: 小数精度

    Returns:
        格式化后的字典
    """
    result = {}
    for key, value in metrics.items():
        new_key = f"{prefix}{key}" if prefix else key
        result[new_key] = round(float(value), precision)
    return result


# ============ CLI 测试 ============

if __name__ == "__main__":
    # 测试用例
    print("=" * 50)
    print("变化检测指标计算测试")
    print("=" * 50)

    # 示例: 二分类混淆矩阵
    # [[TN, FP],
    #  [FN, TP]]
    test_cm = np.array([
        [900, 10],
        [20, 70]
    ])

    print("\n测试混淆矩阵:")
    print(test_cm)
    print()

    scores = cm2score(test_cm)

    print("计算结果:")
    for name, value in scores.items():
        print(f"  {name}: {value:.4f}")

    # 验证计算
    print("\n手动验证:")
    tp, fn, fp, tn = 70, 20, 10, 900
    oa = (tp + tn) / (tp + fn + fp + tn)
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    f1 = 2 * recall * precision / (recall + precision)
    iou = tp / (tp + fp + fn)
    print(f"  OA: {oa:.4f} (验证: {scores['OA']:.4f})")
    print(f"  Recall: {recall:.4f} (验证: {scores['recall']:.4f})")
    print(f"  Precision: {precision:.4f} (验证: {scores['precision']:.4f})")
    print(f"  F1: {f1:.4f} (验证: {scores['F1']:.4f})")
    print(f"  IoU: {iou:.4f} (验证: {scores['IoU']:.4f})")
