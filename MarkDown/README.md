# 基于深度学习(MLP)与LLM Agent的自动化日志异常检测系统

## 项目概述

本项目旨在利用机器学习（深度学习分类）与大语言模型（Agent）技术，解决工业界大规模系统日志监控的痛点。通过神经网络（MLP）实时识别日志流中的异常模式，并调用Agent结合知识库进行自动化故障诊断。

## 核心技术栈

- **编程语言**：Python 3.9+
- **深度学习**：PyTorch（用于构建 MLP 分类器）
- **特征提取**：Regex / Drain 算法 (日志模板化)
- **智能体框架**：Hugging Face Transformers (用于调用LLM)
- **推理依据**：GPT-2 (本地运行) 或其他LLM API

## 项目结构

```
├── HDFS_v1/                # HDFS日志数据集
│   ├── HDFS.log             # 原始日志文件
│   ├── README.md            # 数据集说明
│   └── preprocessed/        # 预处理后的数据
│       ├── Event_occurrence_matrix.csv  # 事件出现矩阵
│       ├── HDFS.log_templates.csv     # 日志模板
│       └── anomaly_label.csv          # 异常标签
├── train_mlp.py            # MLP模型训练脚本
├── log_preprocessor.py      # 日志预处理器脚本
├── Agent_System.py          # Agent系统脚本
├── LogMLP_Model.pth         # 训练好的模型权重（训练后生成）
└── loss_curve.png           # 训练损失曲线（训练后生成）
```

## 使用方法

### 1. 数据预处理

如果需要重新预处理日志文件，可以运行：

```bash
python log_preprocessor.py
```

### 2. 模型训练

运行以下命令训练MLP模型：

```bash
python train_mlp.py
```

训练完成后，会生成以下文件：
- `LogMLP_Model.pth`：训练好的模型权重
- `loss_curve.png`：训练损失曲线

### 3. 异常检测与故障诊断

运行以下命令启动Agent系统，进行异常检测和故障诊断：

```bash
python Agent_System.py
```

## 工作流程

1. **数据预处理**：将原始日志转换为模板，生成事件出现矩阵
2. **模型训练**：使用MLP模型学习正常和异常日志模式
3. **异常检测**：使用训练好的模型实时检测异常日志
4. **故障诊断**：当检测到异常时，调用LLM生成故障诊断和排查建议

## 注意事项

- 训练过程可能需要较长时间，取决于硬件性能
- 可以根据实际需求调整MLP模型的超参数
- 可以替换LLM为其他模型，如Llama 3或DeepSeek API
