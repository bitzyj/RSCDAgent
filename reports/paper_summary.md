# 论文摘要: Remote Sensing Image Change Detection with Transformers

## 基本信息

| 字段 | 值 |
|------|-----|
| **标题** | Remote Sensing Image Change Detection with Transformers |
| **作者** | Hao Chen, Zhenwei Shi |
| **年份** | 2021 |
| **会议/期刊** | IEEE Geoscience and Remote Sensing Letters |

## 模型信息

| 字段 | 值 |
|------|-----|
| **模型名称** | BIT (Bitemporal Image Transformer) |
| **架构** | Siamese CNN + Transformer |
| **Backbone** | ResNet18 (改进版) |
| **输入尺寸** | 256x256 |
| **框架** | PyTorch |

## 训练配置

| 字段 | 值 |
|------|-----|
| **Epochs** | 200 |
| **Batch Size** | 16 |
| **Optimizer** | Adam |
| **学习率** | 0.0003 |
| **Weight Decay** | 0.0005 |
| **Loss Function** | BCE + Dice Loss |
| **Scheduler** | Step LR (step_size=50, gamma=0.5) |

## 数据集信息

| 字段 | 值 |
|------|-----|
| **数据集名称** | LEVIR-CD |
| **训练样本数** | 445 |
| **验证样本数** | 64 |
| **测试样本数** | 128 |
| **图像尺寸** | 256x256 |
| **波段数** | 3 |

## 目标指标

**来源**: Table II

| 数据集 | 指标 | 值 | 备注 |
|--------|------|-----|------|
| LEVIR-CD | F1 | 0.8988 | Best |
| LEVIR-CD | Precision | 0.9037 | - |
| LEVIR-CD | Recall | 0.8941 | - |
| LEVIR-CD | OA | 0.9841 | - |
| LEVIR-CD | IoU | 0.8149 | - |
| CDD | F1 | 0.7891 | Seasonally-varying |
| CDD | OA | 0.9581 | - |

## 执行命令

| 类型 | 命令 |
|------|------|
| **训练** | `python train.py --config configs/BIT-LEVIR.yaml` |
| **测试** | `python test.py --config configs/BIT-LEVIR.yaml --checkpoint checkpoints/BIT_LEVIR.pth` |
| **推理** | `python inference.py --img1 A.png --img2 B.png --output change_map.png` |

## 解析警告

- ⚠️ 论文未明确说明 train/val/test 划分比例，从代码仓库推断
- ⚠️ Scheduler 参数从 "step_size=50" 推断

## 解析错误

✓ 无错误

---

*报告生成时间: 2026-04-23T10:30:00*
*由 RSCDAgent 生成*
