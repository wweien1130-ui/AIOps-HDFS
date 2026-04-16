# ClickHouse 实时数据处理管道配置指南

## 1. 创建 Kafka 引擎表（实时数据管道）

Kafka 引擎表负责从 Kafka 主题拉取数据，不存储数据，只作为流式数据的入口。

```sql
CREATE TABLE kafka_hdfs_logs (
    raw_log String
) ENGINE = Kafka
SETTINGS 
    kafka_broker_list = '192.168.115.129:9092',   -- Kafka broker 地址
    kafka_topic_list = 'hdfs-logs',                -- 主题名称
    kafka_group_name = 'clickhouse_consumer',      -- 消费者组
    kafka_format = 'RawBLOB';                      -- 格式：RawBLOB 直接接收原始字节（纯文本）
```

**注意：**
- 使用 RawBLOB 格式可避免 CSV/JSON 解析问题，直接存储整行消息
- 如果消息包含换行符，RawBLOB 会保留原样

## 2. 创建原始日志存储表（MergeTree）

该表永久存储所有原始日志，用于后续统计和历史回溯。

```sql
CREATE TABLE hdfs_logs (
    raw_log String,
    _timestamp DateTime DEFAULT now()   -- 自动记录插入时间
) ENGINE = MergeTree()
ORDER BY _timestamp;                    -- 按时间排序
```

## 3. 创建物化视图：自动将 Kafka 数据写入存储表

物化视图会在新消息到达 kafka_hdfs_logs 时自动触发，将数据写入 hdfs_logs。

```sql
CREATE MATERIALIZED VIEW mv_hdfs_logs TO hdfs_logs AS
SELECT raw_log FROM kafka_hdfs_logs;
```

执行后，Kafka 中的数据会持续流入 hdfs_logs，无需手动干预。

## 4. 创建事件统计表（SummingMergeTree）

该表存储每个 BlockId 下每个事件（E1~E29）的累计出现次数。

```sql
CREATE TABLE block_event_stats (
    block_id String,
    event_id String,
    cnt UInt64,
    last_updated DateTime DEFAULT now()
) ENGINE = SummingMergeTree()           -- 自动合并相同 block_id+event_id 的 cnt
ORDER BY (block_id, event_id);          -- 排序键，加速 GROUP BY 查询
```

## 5. 创建统计物化视图：实时提取事件并更新统计表

该视图从 hdfs_logs 中读取新写入的日志，提取 block_id，匹配事件模板（E1~E29），并将计数 1 写入 block_event_stats。

```sql
CREATE MATERIALIZED VIEW mv_block_stats TO block_event_stats AS
SELECT block_id, event_id, cnt
FROM (
    SELECT 
        extract(raw_log, '(blk[-_]?-?\\d+)') AS block_id,   -- 支持 blk_123 和 blk_-123 格式
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
    FROM hdfs_logs
)
WHERE block_id != '' AND event_id IS NOT NULL;
```

**说明：**
- `extract(raw_log, '(blk[-_]?-?\\d+)')` 可提取类似 blk_123、blk_-456 的 BlockId
- CASE WHEN 使用 LIKE 模式匹配事件，按需调整关键词
- 外层 WHERE 过滤掉无效数据

## 6. 验证数据流与查询输出

### 6.1 检查原始日志是否已写入

```sql
SELECT COUNT(*) FROM hdfs_logs;
```

### 6.2 查看统计表数据（按你要求的格式）

```sql
SELECT 
    block_id,
    event_id,
    sum(cnt) AS total_cnt
FROM block_event_stats
GROUP BY block_id, event_id
ORDER BY block_id, event_id
LIMIT 20;
```

**输出示例：**

```text
┌─block_id────────────────┬─event_id─┬─total_cnt─┐
│ blk_7503483334202473044 │ E11      │         3 │
│ blk_7503483334202473044 │ E22      │         1 │
└─────────────────────────┴──────────┴───────────┘
```

### 6.3 实时监控 Kafka 消费进度

```sql
SELECT * FROM system.kafka_consumers WHERE table = 'kafka_hdfs_logs'\G
```

## 7. 常见问题与维护

### 清空统计表（保留表结构）

```sql
TRUNCATE TABLE block_event_stats;
```

### 清空原始日志表

```sql
TRUNCATE TABLE hdfs_logs;
```

### 重建物化视图（例如修改匹配规则）

```sql
DROP TABLE mv_block_stats;
-- 重新执行第 5 步的 CREATE MATERIALIZED VIEW
```

### 重置 Kafka 消费者组 offset

删除 Kafka 表并重新创建（使用新的 kafka_group_name）：

```sql
DROP TABLE kafka_hdfs_logs;
-- 重新执行第 1 步，修改 kafka_group_name 为新值
```

## 总结

通过上述步骤，你建立了一个完整的实时数据处理管道：

**Kafka 表 消费消息 → 物化视图 写入原始表 → 第二个物化视图 提取特征并更新统计表 → 查询统计表 获取每个 BlockId 的事件频次**

该架构可轻松扩展至其他日志分析场景，只需调整事件匹配规则和统计维度。现在你可以运行 Python 预测脚本，从 block_event_stats 读取特征并调用训练好的模型进行异常判断。