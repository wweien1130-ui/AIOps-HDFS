# ClickHouse

### 2. 创建正确的 users.d 目录和空密码配置文件

```bash
bash
mkdir -p /data/clickhouse/users.d
cat > /data/clickhouse/users.d/empty-password.xml <<EOF
<clickhouse>
    <users>
        <default>
            <password></password>
            <networks>
                <ip>::/0</ip>
            </networks>
        </default>
    </users>
</clickhouse>
EOF
```

### 3. 重新启动 ClickHouse 容器（挂载 users.d 和 config.d）

```bash
bash
docker run -d \
  --name clickhouse \
  -p 8123:8123 -p 9000:9000 \
  -v /data/clickhouse/data:/var/lib/clickhouse \
  -v /data/clickhouse/log:/var/log/clickhouse-server \
  -v /data/clickhouse/users.d:/etc/clickhouse-server/users.d \
  -v /data/clickhouse/config.d:/etc/clickhouse-server/config.d \
  --ulimit nofile=262144:262144 \
  clickhouse/clickhouse-server:latest
```


### 4.进入 ClickHouse 客户端
```bash
docker exec -it clickhouse clickhouse-client
```

### 5.  创建数据库
```bash
CREATE DATABASE IF NOT EXISTS online;
CREATE DATABASE IF NOT EXISTS offline;
```


### 6.  在线库（实时流）

- 3.1 Kafka 引擎表

```sql
CREATE TABLE online.kafka_hdfs_logs (
    raw_log String
) ENGINE = Kafka
SETTINGS kafka_broker_list = '192.168.115.129:9092',
         kafka_topic_list = 'hdfs-logs-online',
         kafka_group_name = 'clickhouse_online_consumer',
         kafka_format = 'RawBLOB';
```

- 3.2 原始日志表

```sql
CREATE TABLE online.hdfs_logs (
    raw_log String,
    _timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY _timestamp;
```

- 3.3 物化视图：写入原始表

```sql
CREATE MATERIALIZED VIEW online.mv_hdfs_logs TO online.hdfs_logs AS
SELECT raw_log FROM online.kafka_hdfs_logs;
```

- 3.4 事件统计表
 
 ```sql
 CREATE TABLE online.block_event_stats (
    block_id String,
    event_id String,
    cnt UInt64,
    last_updated DateTime DEFAULT now()
) ENGINE = SummingMergeTree()
ORDER BY (block_id, event_id);
 ```

- 3.5 统计物化视图（提取 E1~E29）

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

- 3.6 在线异常结果表（TTL 7天）

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

### 7. 离线库（批处理，带 batch_id）

- 4.1 Kafka 引擎表

```sql
CREATE TABLE offline.kafka_hdfs_logs (
    raw_log String
) ENGINE = Kafka
SETTINGS kafka_broker_list = '192.168.115.129:9092',
         kafka_topic_list = 'hdfs-logs-offline',
         kafka_group_name = 'clickhouse_offline_consumer',
         kafka_format = 'RawBLOB';
```


- 4.2 原始日志表（带 batch_id）

```sql
CREATE TABLE offline.hdfs_logs (
    batch_id UInt64,
    raw_log String,
    _timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(_timestamp)
ORDER BY (batch_id, _timestamp);
```

- 4.3 物化视图：拆分 batch_id

```sql
CREATE MATERIALIZED VIEW offline.mv_hdfs_logs TO offline.hdfs_logs AS
SELECT 
    toUInt64(splitByChar('\t', raw_log)[1]) AS batch_id,
    splitByChar('\t', raw_log)[2] AS raw_log
FROM offline.kafka_hdfs_logs;
```

- 4.4 统计表（带 batch_id）

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

- 4.5 统计物化视图

```sql
CREATE MATERIALIZED VIEW offline.mv_block_stats TO offline.block_event_stats AS
SELECT 
    batch_id,
    extract(raw_log, '(blk[-_]?-?\\d+)') AS block_id,
    CASE 
        WHEN raw_log LIKE '%Adding an already existing block%' THEN 'E1'
        WHEN raw_log LIKE '%Verification succeeded for%' THEN 'E2'
        -- 其他 27 个 WHEN 同在线库（可复制上面完整 CASE）
        ELSE NULL
    END AS event_id,
    1 AS cnt
FROM offline.hdfs_logs
WHERE block_id != '' AND event_id IS NOT NULL;
```

- 4.6 离线异常表（长期保留）

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


### 8.验证数据流


- 1. 发送测试消息（在线）

```sql
echo "081109 203519 INFO dfs.DataNode: Receiving block blk_123" | \
docker exec -i kafka /opt/kafka/bin/kafka-console-producer.sh \
  --broker-list 192.168.115.129:9092 --topic hdfs-logs-online
```


- 2. 查询在线表

```sql
SELECT COUNT(*) FROM online.hdfs_logs;
SELECT block_id, event_id, cnt FROM online.block_event_stats LIMIT 10;
```

- 3. 发送离线消息（带 batch_id）

```sql
echo "1700000000 081109 203519 INFO dfs.DataNode: Receiving block blk_456" | \
docker exec -i kafka /opt/kafka/bin/kafka-console-producer.sh \
  --broker-list 192.168.115.129:9092 --topic hdfs-logs-offline
```


- 4. 查询离线表

```sql
SELECT COUNT(*) FROM offline.hdfs_logs;
SELECT batch_id, block_id, event_id FROM offline.block_event_stats LIMIT 10;
```


### 9.清空数据（保留表结构）

```sql
TRUNCATE TABLE online.hdfs_logs;
TRUNCATE TABLE online.block_event_stats;
TRUNCATE TABLE online.anomaly_blocks;
-- 同样操作 offline 库
```
