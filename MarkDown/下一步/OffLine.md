# 离线批处理模块

## 3.1 Kafka Topic

**名称**：`hdfs-logs-offline`

**消息格式**：`batch_id\t原始日志行`，其中 `batch_id` 为文件上传开始时的 Unix 时间戳（同一个文件内固定）。

## 3.2 ClickHouse 离线库 (offline)

### 3.2.1 创建数据库

```sql
CREATE DATABASE IF NOT EXISTS offline;
```

### 3.2.2 Kafka 引擎表

```sql
CREATE TABLE offline.kafka_hdfs_logs (
    raw_log String
) ENGINE = Kafka
SETTINGS kafka_broker_list = '192.168.115.129:9092',
         kafka_topic_list = 'hdfs-logs-offline',
         kafka_group_name = 'clickhouse_offline_consumer',
         kafka_format = 'RawBLOB';
```

### 3.2.3 原始日志表（带 batch_id）

```sql
CREATE TABLE offline.hdfs_logs (
    batch_id UInt64,
    raw_log String,
    _timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(_timestamp)
ORDER BY (batch_id, _timestamp);
```

### 3.2.4 物化视图：拆分 batch_id 和日志内容

```sql
CREATE MATERIALIZED VIEW offline.mv_hdfs_logs TO offline.hdfs_logs AS
SELECT 
    toUInt64(splitByChar('\t', raw_log)[1]) AS batch_id,
    splitByChar('\t', raw_log)[2] AS raw_log
FROM offline.kafka_hdfs_logs;
```

### 3.2.5 统计表（带 batch_id）

```sql
CREATE TABLE offline.block_event_stats (
    batch_id UInt64,
    block_id String,
    event_id String,
    cnt UInt64,
    last_updated DateTime DEFAULT now()
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMMDD(last_updated)
ORDER BY (batch_id, block_id, event_id);
```

### 3.2.6 统计物化视图（提取事件，传递 batch_id）

```sql
CREATE MATERIALIZED VIEW offline.mv_block_stats TO offline.block_event_stats AS
SELECT 
    batch_id,
    extract(raw_log, '(blk[-_]?-?\\d+)') AS block_id,
    CASE 
        WHEN raw_log LIKE '%Adding an already existing block%' THEN 'E1'
        WHEN raw_log LIKE '%Verification succeeded for%' THEN 'E2'
        -- ... 其余 27 个 WHEN 条件（同在线）...
        ELSE NULL
    END AS event_id,
    1 AS cnt
FROM offline.hdfs_logs
WHERE block_id != '' AND event_id IS NOT NULL;
```

### 3.2.7 离线异常结果表（带 batch_id，长期保留）

```sql
CREATE TABLE offline.anomaly_blocks (
    batch_id UInt64,
    block_id String,
    E1 Int32, E2 Int32, E3 Int32, E4 Int32, E5 Int32,
    E6 Int32, E7 Int32, E8 Int32, E9 Int32, E10 Int32,
    E11 Int32, E12 Int32, E13 Int32, E14 Int32, E15 Int32,
    E16 Int32, E17 Int32, E18 Int32, E19 Int32, E20 Int32,
    E21 Int32, E22 Int32, E23 Int32, E24 Int32, E25 Int32,
    E26 Int32, E27 Int32, E28 Int32, E29 Int32,
    anomaly_score Float32,
    detected_at DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(detected_at)
ORDER BY (batch_id, block_id);
```

## 3.3 离线处理流程

### 3.3.1 数据流入

生产者读取文件，为每行添加相同的 `batch_id`（如 `1700000000`），发送到 `hdfs-logs-offline`。

ClickHouse 自动消费并填充 `offline.hdfs_logs` 和 `offline.block_event_stats`。

### 3.3.2 离线预测脚本（每小时或按批次触发）

```python
import clickhouse_connect
import pandas as pd
import joblib

client = clickhouse_connect.get_client(host='localhost', port=9000, username='default', password='')
model = joblib.load('block_anomaly_model.pkl')
scaler = joblib.load('scaler.pkl')

# 获取未处理的 batch_id（例如从记录表或直接扫描）
query_batches = """
SELECT DISTINCT batch_id
FROM offline.block_event_stats
WHERE batch_id NOT IN (SELECT DISTINCT batch_id FROM offline.anomaly_blocks)
"""
batches = client.query_df(query_batches)['batch_id'].tolist()

for batch_id in batches:
    # 获取该批次的所有 block 特征
    query_features = f"""
    SELECT 
        block_id,
        sumIf(cnt, event_id='E1') AS E1,
        sumIf(cnt, event_id='E2') AS E2,
        ...,
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
```

### 3.3.3 导出 CSV 并清理（按批次）

```bash
#!/bin/bash
BATCH_ID=$1   # 从外部传入，如 1700000000

clickhouse-client --query "
SELECT block_id, E1, E2, ..., E29, anomaly_score
FROM offline.anomaly_blocks FINAL
WHERE batch_id = $BATCH_ID
FORMAT CSV" > anomaly_batch_${BATCH_ID}.csv

# 可选：删除该批次的所有数据
clickhouse-client --query "ALTER TABLE offline.hdfs_logs DELETE WHERE batch_id = $BATCH_ID"
clickhouse-client --query "ALTER TABLE offline.block_event_stats DELETE WHERE batch_id = $BATCH_ID"
clickhouse-client --query "ALTER TABLE offline.anomaly_blocks DELETE WHERE batch_id = $BATCH_ID"
```

## 3.4 定时任务建议

- **预测脚本**：每小时运行一次，扫描未处理的 batch_id。
- **导出/清理**：可在预测完成后立即执行，或单独调度。