import pandas as pd

# 读取 ClickHouse 导出的特征
features = pd.read_csv('block_features.csv')

# 读取标签映射
labels = pd.read_csv('Event.csv')  # 列: BlockId, Label

# 合并
df = features.merge(labels, on='BlockId', how='inner')

# 将标签编码为 0/1
df['target'] = df['Label'].map({'Success': 0, 'Fail': 1})

# 调整列顺序：BlockId, Label, target, E1~E29
feature_cols = [f'E{i}' for i in range(1, 30)]
new_order = ['BlockId', 'Label', 'target'] + feature_cols
df = df[new_order]

# 保存
df.to_csv('training_data.csv', index=False)
print(f"训练集大小: {len(df)}")
print(f"列顺序: {list(df.columns)}")