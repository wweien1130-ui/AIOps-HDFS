# 在线实时分析模块

## 2.1 Kafka Topic

**名称**：`hdfs-logs-online`

**消息格式**：原始日志行（纯文本），不附加任何批次标识。

## 2.2 ClickHouse 在线库 (online)

### 2.2.1 创建数据库

```sql
CREATE DATABASE IF NOT EXISTS online;
```

### 2.2.2 Kafka 引擎表

```sql
CREATE TABLE online.kafka_hdfs_logs (
    raw_log String
) ENGINE = Kafka
SETTINGS kafka_broker_list = '192.168.115.129:9092',
         kafka_topic_list = 'hdfs-logs-online',
         kafka_group_name = 'clickhouse_online_consumer',
         kafka_format = 'RawBLOB';
```

### 2.2.3 原始日志存储表

```sql
CREATE TABLE online.hdfs_logs (
    raw_log String,
    _timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY _timestamp;
```

### 2.2.4 物化视图：写入原始日志

```sql
CREATE MATERIALIZED VIEW online.mv_hdfs_logs TO online.hdfs_logs AS
SELECT raw_log FROM online.kafka_hdfs_logs;
```

### 2.2.5 统计表（事件频次）

```sql
CREATE TABLE online.block_event_stats (
    block_id String,
    event_id String,
    cnt UInt64,
    last_updated DateTime DEFAULT now()
) ENGINE = SummingMergeTree()
ORDER BY (block_id, event_id);
```

### 2.2.6 统计物化视图（提取事件）

```sql
CREATE MATERIALIZED VIEW online.mv_block_stats TO online.block_event_stats AS
SELECT 
    extract(raw_log, '(blk[-_]?-?\\d+)') AS block_id,
    CASE 
        WHEN raw_log LIKE '%Adding an already existing block%' THEN 'E1'
        WHEN raw_log LIKE '%Verification succeeded for%' THEN 'E2'
        WHEN raw_log LIKE '%Served block%to%' THEN 'E3'
        WHEN raw_log LIKE '%Got exception while serving%to%' THEN 'E4'
        WHEN raw_log LIKE '%Receiving block%src:%dest:%' THEN 'E5'
        WHEN raw_log LIKE '%Received block%src:%dest:%of size%' THEN 'E6'
        WHEN raw_log LIKE '%writeBlock%received exception%' THEN 'E7'
        WHEN raw_log LIKE '%PacketResponder%for block%Interrupted%' THEN 'E8'
        WHEN raw_log LIKE '%Received block%of size%from%' THEN 'E9'
        WHEN raw_log LIKE '%PacketResponder%Exception%' THEN 'E10'
        WHEN raw_log LIKE '%PacketResponder%for block%terminating%' THEN 'E11'
        WHEN raw_log LIKE '%Exception writing block%to mirror%' THEN 'E12'
        WHEN raw_log LIKE '%Receiving empty packet for block%' THEN 'E13'
        WHEN raw_log LIKE '%Exception in receiveBlock for block%' THEN 'E14'
        WHEN raw_log LIKE '%Changing block file offset of block%from%to%meta file offset to%' THEN 'E15'
        WHEN raw_log LIKE '%:Transmitted block%to%' THEN 'E16'
        WHEN raw_log LIKE '%:Failed to transfer%to%got%' THEN 'E17'
        WHEN raw_log LIKE '%Starting thread to transfer block%to%' THEN 'E18'
        WHEN raw_log LIKE '%Reopen Block%' THEN 'E19'
        WHEN raw_log LIKE '%Unexpected error trying to delete block%BlockInfo not found in volumeMap%' THEN 'E20'
        WHEN raw_log LIKE '%Deleting block%file%' THEN 'E21'
        WHEN raw_log LIKE '%allocateBlock:%' THEN 'E22'
        WHEN raw_log LIKE '%delete:%is added to invalidSet of%' THEN 'E23'
        WHEN raw_log LIKE '%Removing block%from neededReplications%does not belong to any file%' THEN 'E24'
        WHEN raw_log LIKE '%ask%to replicate%to%' THEN 'E25'
        WHEN raw_log LIKE '%addStoredBlock: blockMap updated:%is added to%size%' THEN 'E26'
        WHEN raw_log LIKE '%addStoredBlock: Redundant addStoredBlock request received for%on%size%' THEN 'E27'
        WHEN raw_log LIKE '%addStoredBlock: addStoredBlock request received for%on%size%But it does not belong to any file%' THEN 'E28'
        WHEN raw_log LIKE '%PendingReplicationMonitor timed out block%' THEN 'E29'
        ELSE NULL
    END AS event_id,
    1 AS cnt
FROM online.hdfs_logs
WHERE block_id != '' AND event_id IS NOT NULL;
```

### 2.2.7 在线异常结果表（带 TTL 7 天）

```sql
CREATE TABLE online.anomaly_blocks (
    block_id String,
    E1 Int32, E2 Int32, E3 Int32, E4 Int32, E5 Int32,
    E6 Int32, E7 Int32, E8 Int32, E9 Int32, E10 Int32,
    E11 Int32, E12 Int32, E13 Int32, E14 Int32, E15 Int32,
    E16 Int32, E17 Int32, E18 Int32, E19 Int32, E20 Int32,
    E21 Int32, E22 Int32, E23 Int32, E24 Int32, E25 Int32,
    E26 Int32, E27 Int32, E28 Int32, E29 Int32,
    anomaly_score Float32,
    detected_at DateTime64(3) DEFAULT now()
) ENGINE = ReplacingMergeTree(detected_at)
PARTITION BY toYYYYMMDD(detected_at)
ORDER BY block_id
TTL detected_at + INTERVAL 7 DAY DELETE;
```

## 2.3 在线预测脚本（Python）

定期（如每 30 秒）从 `online.block_event_stats` 中增量读取新特征，调用模型，将异常写入 `online.anomaly_blocks`。

```python
import clickhouse_connect
import joblib
import time

client = clickhouse_connect.get_client(host='localhost', port=9000, username='default', password='')
model = joblib.load('block_anomaly_model.pkl')
scaler = joblib.load('scaler.pkl')

last_predict_time = get_last_predict_time()   # 从 Redis 或文件读取

while True:
    query = f"""
    SELECT 
        block_id,
        sumIf(cnt, event_id='E1') AS E1,
        sumIf(cnt, event_id='E2') AS E2,
        ...
        sumIf(cnt, event_id='E29') AS E29,
        max(last_updated) AS last_updated
    FROM online.block_event_stats
    WHERE last_updated > '{last_predict_time}'
    GROUP BY block_id
    """
    df = client.query_df(query)
    if not df.empty:
        feature_cols = [f'E{i}' for i in range(1, 30)]
        X = df[feature_cols].fillna(0)
        X_scaled = scaler.transform(X)
        scores = model.predict_proba(X_scaled)[:, 1]   # 异常概率
        for idx, row in df.iterrows():
            if scores[idx] > 0.5:   # 阈值可调
                insert_row = {
                    'block_id': row['block_id'],
                    **{f'E{i}': row[f'E{i}'] for i in range(1,30)},
                    'anomaly_score': scores[idx]
                }
                client.insert_df('online.anomaly_blocks', pd.DataFrame([insert_row]))
        last_predict_time = df['last_updated'].max()
        save_last_predict_time(last_predict_time)
    time.sleep(30)
```

## 2.4 Redis 增量同步脚本（每 10 秒）

从 `online.anomaly_blocks` 中查询新异常，更新 Redis 的 Top 10 Sorted Set 和详情 Hash。

```python
import redis
import clickhouse_connect

r = redis.Redis(host='localhost', port=6379, db=0)
client = clickhouse_connect.get_client(host='localhost', port=9000, username='default', password='')

last_sync = r.get('anomaly:last_sync_time')
if last_sync is None:
    last_sync = '1970-01-01 00:00:00'
else:
    last_sync = last_sync.decode()

while True:
    query = f"""
    SELECT 
        block_id, E1, E2, ..., E29, anomaly_score, max(detected_at) as detected_at
    FROM online.anomaly_blocks
    WHERE detected_at > '{last_sync}'
    GROUP BY block_id
    """
    df = client.query_df(query)
    if not df.empty:
        pipe = r.pipeline()
        for _, row in df.iterrows():
            pipe.zadd('anomaly:top', {row['block_id']: row['anomaly_score']})
            pipe.hset(f'anomaly:detail:{row["block_id"]}', mapping={
                **{f'E{i}': row[f'E{i}'] for i in range(1,30)},
                'anomaly_score': row['anomaly_score']
            })
        pipe.zremrangebyrank('anomaly:top', 0, -11)   # 保留前10
        pipe.execute()
        new_sync = df['detected_at'].max()
        r.set('anomaly:last_sync_time', str(new_sync))
        last_sync = new_sync
    time.sleep(10)
```

## 2.5 在线查询接口

- **Top 10 异常**：`redis.zrevrange('anomaly:top', 0, 9, withscores=True)`
- **异常详情**：优先从 Redis Hash 获取，未命中则查 ClickHouse
- **分页/时间范围查询**：直接查 ClickHouse（如 `WHERE detected_at >= now() - INTERVAL 1 HOUR`）