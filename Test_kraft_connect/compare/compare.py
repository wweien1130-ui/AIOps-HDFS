import pandas as pd

yours = pd.read_csv('E:\\private_project\\AI_application\\Test_kraft_connect\\Train_Event\\training_data.csv')
official = pd.read_csv('E:\\private_project\\AI_application\\HDFS_v1\\preprocessed\\Event_occurrence_matrix.csv')

feature_cols = [f'E{i}' for i in range(1, 30)]
merged = yours.merge(official[['BlockId'] + feature_cols], on='BlockId', suffixes=('_mine', '_official'))

# 找出 E5 差异最大的几个 block_id
merged['E5_diff'] = abs(merged['E5_mine'] - merged['E5_official'])
top_diff = merged[merged['E5_diff'] > 0].nlargest(5, 'E5_diff')
print("E5 差异最大的 block_id:")
print(top_diff[['BlockId', 'E5_mine', 'E5_official', 'E5_diff']])