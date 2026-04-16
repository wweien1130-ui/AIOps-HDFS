#使用 Pandas 合并特征和标签，生成训练集：



import pandas as pd

# 读取 ClickHouse 导出的特征
features = pd.read_csv('block_features.csv')

# 读取标签映射
labels = pd.read_csv('Event.csv')  # 列: block_id, label

# 合并
df = features.merge(labels, on='block_id', how='inner')

# 将标签编码为 0/1
df['target'] = df['label'].map({'Success': 0, 'Fail': 1})

# 特征列 (E1~E29)
feature_cols = [f'E{i}' for i in range(1, 30)]
X = df[feature_cols]
y = df['target']

# 保存为训练用 CSV
df.to_csv('training_data.csv', index=False)
print(f"训练集大小: {len(df)}")