# agent/tools/data_preparator.py

import os
import shutil
import pandas as pd
from langchain_core.tools import tool

# 预设的备份目录 (Ubuntu 路径)
BACKUP_DIR = "/root/backup"

# 本地目标目录
LOCAL_DIR = os.path.abspath(os.path.dirname(__file__))


@tool(description="准备训练数据，检查并复制必要文件到本地")
def prepare_training_data() -> str:
    """
    多级降级策略：
    1. 优先使用官方 Event_occurrence_matrix.csv
    2. 其次使用 training_data.csv
    3. 最后使用 block_features.csv + Event.csv 合并
    """
    results = []

    # 目标文件路径
    official_matrix = os.path.join(LOCAL_DIR, "Event_occurrence_matrix.csv")
    training_data = os.path.join(LOCAL_DIR, "training_data.csv")
    block_features = os.path.join(LOCAL_DIR, "block_features.csv")
    event_labels = os.path.join(LOCAL_DIR, "Event.csv")

    # ===== 优先级1: 官方 Event_occurrence_matrix.csv =====
    source_official = os.path.join(BACKUP_DIR, "Event_occurrence_matrix.csv")

    if os.path.exists(source_official) and os.path.getsize(source_official) > 0:
        try:
            # 验证文件完整性
            df = pd.read_csv(source_official)
            required_cols = ['BlockId', 'Label'] + [f'E{i}' for i in range(1, 30)]
            if all(col in df.columns for col in required_cols):
                shutil.copy(source_official, official_matrix)
                results.append("✅ 优先级1: 成功复制官方 Event_occurrence_matrix.csv")
                return "\n".join(results)
            else:
                results.append("⚠️ 优先级1: 文件列不完整，降级到优先级2")
        except Exception as e:
            results.append(f"⚠️ 优先级1: 文件损坏，降级到优先级2 ({str(e)})")
    else:
        results.append("⚠️ 优先级1: 文件不存在，降级到优先级2")

    # ===== 优先级2: training_data.csv =====
    source_training = os.path.join(BACKUP_DIR, "training_data.csv")

    if os.path.exists(source_training) and os.path.getsize(source_training) > 0:
        try:
            df = pd.read_csv(source_training)
            if 'BlockId' in df.columns and 'target' in df.columns:
                shutil.copy(source_training, training_data)
                results.append("✅ 优先级2: 成功复制 training_data.csv")
                return "\n".join(results)
        except Exception as e:
            results.append(f"⚠️ 优先级2: 文件损坏，降级到优先级3 ({str(e)})")
    else:
        results.append("⚠️ 优先级2: 文件不存在，降级到优先级3")

    # ===== 优先级3: block_features.csv + Event.csv =====
    source_features = os.path.join(BACKUP_DIR, "block_features.csv")
    source_event = os.path.join(BACKUP_DIR, "Event.csv")

    if os.path.exists(source_features) and os.path.exists(source_event):
        try:
            shutil.copy(source_features, block_features)
            shutil.copy(source_event, event_labels)

            # 执行合并
            features = pd.read_csv(block_features)
            labels = pd.read_csv(event_labels)

            df = features.merge(labels, on='BlockId', how='inner')
            df['target'] = df['Label'].map({'Success': 0, 'Fail': 1})

            feature_cols = [f'E{i}' for i in range(1, 30)]
            new_order = ['BlockId', 'Label', 'target'] + feature_cols
            df = df[new_order]

            df.to_csv(training_data, index=False)
            results.append("✅ 优先级3: 成功通过 combine 生成 training_data.csv")

            return "\n".join(results)
        except Exception as e:
            return "❌ 所有优先级都失败: " + str(e)
    else:
        return "❌ 降级失败: 找不到 block_features.csv 或 Event.csv"