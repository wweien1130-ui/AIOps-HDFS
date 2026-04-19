import clickhouse_connect
import pandas as pd
import joblib
import yaml
import os

config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')

with open(os.path.join(config_dir, 'clickhouse.yaml'), 'r') as f:
    ch_config = yaml.safe_load(f)['clickhouse']['offline']
client = clickhouse_connect.get_client(
    host=ch_config['host'],
    port=ch_config['port'],
    username=ch_config.get('username', 'default'),
    password=ch_config.get('password', '')
)

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
model = joblib.load(os.path.join(project_root, 'agent', 'tools', 'block_anomaly_model.pkl'))
scaler = joblib.load(os.path.join(project_root, 'agent', 'tools', 'scaler.pkl'))

query_batches = """
SELECT DISTINCT batch_id
FROM offline.block_event_stats
WHERE batch_id NOT IN (SELECT DISTINCT batch_id FROM offline.anomaly_blocks)
"""
batches = client.query_df(query_batches)['batch_id'].tolist()

for batch_id in batches:
    query_features = f"""
    SELECT 
        block_id,
        sumIf(cnt, event_id='E1') AS E1,
        sumIf(cnt, event_id='E2') AS E2,
        sumIf(cnt, event_id='E3') AS E3,
        sumIf(cnt, event_id='E4') AS E4,
        sumIf(cnt, event_id='E5') AS E5,
        sumIf(cnt, event_id='E6') AS E6,
        sumIf(cnt, event_id='E7') AS E7,
        sumIf(cnt, event_id='E8') AS E8,
        sumIf(cnt, event_id='E9') AS E9,
        sumIf(cnt, event_id='E10') AS E10,
        sumIf(cnt, event_id='E11') AS E11,
        sumIf(cnt, event_id='E12') AS E12,
        sumIf(cnt, event_id='E13') AS E13,
        sumIf(cnt, event_id='E14') AS E14,
        sumIf(cnt, event_id='E15') AS E15,
        sumIf(cnt, event_id='E16') AS E16,
        sumIf(cnt, event_id='E17') AS E17,
        sumIf(cnt, event_id='E18') AS E18,
        sumIf(cnt, event_id='E19') AS E19,
        sumIf(cnt, event_id='E20') AS E20,
        sumIf(cnt, event_id='E21') AS E21,
        sumIf(cnt, event_id='E22') AS E22,
        sumIf(cnt, event_id='E23') AS E23,
        sumIf(cnt, event_id='E24') AS E24,
        sumIf(cnt, event_id='E25') AS E25,
        sumIf(cnt, event_id='E26') AS E26,
        sumIf(cnt, event_id='E27') AS E27,
        sumIf(cnt, event_id='E28') AS E28,
        sumIf(cnt, event_id='E29') AS E29
    FROM offline.block_event_stats
    WHERE batch_id = {batch_id}
    GROUP BY block_id
    """
    df = client.query_df(query_features)
    if df.empty:
        continue
    X = df[[f'E{i}' for i in range(1,30)]].fillna(0)
    X_scaled = scaler.transform(X)
    scores = model.predict_proba(X_scaled)[:, 1]
    anomalies = []
    for idx, row in df.iterrows():
        if scores[idx] > 0.5:
            row_dict = {
                'batch_id': batch_id,
                'block_id': row['block_id'],
                **{f'E{i}': row[f'E{i}'] for i in range(1,30)},
                'anomaly_score': scores[idx]
            }
            anomalies.append(row_dict)
    if anomalies:
        client.insert_df('offline.anomaly_blocks', pd.DataFrame(anomalies))
    print(f"批次 {batch_id} 处理完成，发现 {len(anomalies)} 个异常")