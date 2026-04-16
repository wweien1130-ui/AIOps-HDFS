# predict_new_blocks.py
import clickhouse_connect
import joblib
import pandas as pd

# 加载模型和标准化器
model = joblib.load('block_anomaly_model.pkl')
scaler = joblib.load('scaler.pkl')

# 连接 ClickHouse
client = clickhouse_connect.get_client(
    host='192.168.115.129',
    port=8123,          # 改回 HTTP 端口
    username='default',
    password='',
    database='default'  # 如果表在 default 库中可以省略
)
# 查询所有 BlockId 的特征
query = """
SELECT 
    block_id,
    sumIf(cnt, event_id = 'E1') AS E1,
    sumIf(cnt, event_id = 'E2') AS E2,
    sumIf(cnt, event_id = 'E3') AS E3,
    sumIf(cnt, event_id = 'E4') AS E4,
    sumIf(cnt, event_id = 'E5') AS E5,
    sumIf(cnt, event_id = 'E6') AS E6,
    sumIf(cnt, event_id = 'E7') AS E7,
    sumIf(cnt, event_id = 'E8') AS E8,
    sumIf(cnt, event_id = 'E9') AS E9,
    sumIf(cnt, event_id = 'E10') AS E10,
    sumIf(cnt, event_id = 'E11') AS E11,
    sumIf(cnt, event_id = 'E12') AS E12,
    sumIf(cnt, event_id = 'E13') AS E13,
    sumIf(cnt, event_id = 'E14') AS E14,
    sumIf(cnt, event_id = 'E15') AS E15,
    sumIf(cnt, event_id = 'E16') AS E16,
    sumIf(cnt, event_id = 'E17') AS E17,
    sumIf(cnt, event_id = 'E18') AS E18,
    sumIf(cnt, event_id = 'E19') AS E19,
    sumIf(cnt, event_id = 'E20') AS E20,
    sumIf(cnt, event_id = 'E21') AS E21,
    sumIf(cnt, event_id = 'E22') AS E22,
    sumIf(cnt, event_id = 'E23') AS E23,
    sumIf(cnt, event_id = 'E24') AS E24,
    sumIf(cnt, event_id = 'E25') AS E25,
    sumIf(cnt, event_id = 'E26') AS E26,
    sumIf(cnt, event_id = 'E27') AS E27,
    sumIf(cnt, event_id = 'E28') AS E28,
    sumIf(cnt, event_id = 'E29') AS E29
FROM block_event_stats
GROUP BY block_id
"""
df = client.query_df(query)
feature_cols = [f'E{i}' for i in range(1, 30)]
X = df[feature_cols].fillna(0)
X_scaled = scaler.transform(X)

# 预测
preds = model.predict(X_scaled)
probs = model.predict_proba(X_scaled)[:, 1]  # 异常概率

df['prediction'] = ['Success' if p == 0 else 'Fail' for p in preds]
df['anomaly_prob'] = probs

# 输出异常 BlockId
anomalies = df[df['prediction'] == 'Fail']
print(f"发现 {len(anomalies)} 个异常 BlockId")
print(anomalies[['block_id', 'anomaly_prob']].head(10))