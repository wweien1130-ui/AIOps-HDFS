import clickhouse_connect
import joblib
import pandas as pd

client = clickhouse_connect.get_client(host='localhost', port=8123)
model = joblib.load('block_anomaly_model.pkl')

# 查询新 BlockId 的特征（假设尚未预测过的）
query = """
SELECT 
    block_id,
    sumIf(cnt, event_id = 'E1') AS E1,
    ... (同上)
FROM block_event_stats
GROUP BY block_id
HAVING block_id NOT IN (SELECT DISTINCT block_id FROM predicted_blocks)  -- 可选
"""
df_new = client.query_df(query)
if not df_new.empty:
    X_new = df_new[[f'E{i}' for i in range(1, 30)]]
    preds = model.predict(X_new)
    df_new['predicted_label'] = ['Fail' if p == 1 else 'Success' for p in preds]
    print(df_new[['block_id', 'predicted_label']])
    # 可将结果存入另一张表或发送到 Agent