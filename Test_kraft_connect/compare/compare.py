import pandas as pd

# 文件路径
yours = pd.read_csv('E:\BaiduNetdiskDownload\\block_features.csv')
official = pd.read_csv('E:\\private_project\\AI_application\\HDFS_v1\\preprocessed\\Event_occurrence_matrix.csv')

print(f"你的 block_features.csv block_id 数量: {len(yours)}")
print(f"官方 Event_occurrence_matrix.csv block_id 数量: {len(official)}")

# 合并对比
feature_cols = [f'E{i}' for i in range(1, 30)]
merged = yours.merge(
    official[['BlockId'] + feature_cols],
    on='BlockId',
    how='inner',
    suffixes=('_mine', '_official')
)

print(f"\n两者共同拥有的 block_id 数量: {len(merged)}")

# 检查每个特征的差异
print("\n检查每个特征的差异数量:")
total_diff = 0
for col in feature_cols:
    diff_count = (merged[f'{col}_mine'] != merged[f'{col}_official']).sum()
    if diff_count > 0:
        print(f"  ⚠️ {col}: {diff_count} 处差异")
        total_diff += diff_count
    else:
        print(f"  ✅ {col}: 完全一致")

print(f"\n总计差异数量: {total_diff}")
