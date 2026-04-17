
# 离线：
## kafka: 
- 将数据发送给hdfs-logs-offline
## clickhouse: 
- 创建对应于hdfs-logs-offline的3表+2视图

### -- 离线表
```shell
CREATE TABLE offline.hdfs_logs ...;
CREATE TABLE offline.block_event_stats ...;
```



<!-- ### 结合时间分区和批次标记（推荐）
对于离线批量上传，你可以：
```
在上传文件时，生成一个唯一的 batch_id（如文件上传开始的 Unix 时间戳）。

在 ClickHouse 中创建按日期分区 + 按 batch_id 排序的表。

导出 CSV 时，使用 WHERE batch_id = 指定值 过滤。

导出完成后，删除该批次的分区或数据。
```


示例表结构：
```shell
```sql
CREATE TABLE hdfs_logs (
    batch_id UInt64,
    raw_log String,
    _timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(_timestamp)   -- 按天分区，便于整体清理
ORDER BY (batch_id, _timestamp);
这样既可以利用分区快速删除整批数据，又可以用 batch_id 精确查询。
``` -->


### 并发上传多个日志：
- 1.使用 UUID（推荐，最简单）
```bash
import uuid
batch_id = str(uuid.uuid4())   # 例如 '550e8400-e29b-41d4-a716-446655440000'
```

- 2.为每个文件生成唯一的 batch_id（例如不同的时间戳或递增序号）。

- 3.生产者发送时，为每条日志添加该文件的 batch_id。

- 4.ClickHouse 中存储 batch_id 列。

- 5.导出时，对每个 batch_id 分别执行 SELECT ... WHERE batch_id = ... INTO OUTFILE。

这样三个文件的数据在 Kafka 和 ClickHouse 中虽然混合存储，但通过 batch_id 严格隔离，导出时互不干扰。
```
时间戳（微秒）：batch_id = int(time.time() * 1000000)，保证不同文件 ID 不同。

文件名哈希 + 时间戳：batch_id = hash(filename) ^ timestamp。

```

### 1.全局递增计数器（需持久化存储，如 Redis、文件）。
```shell
import time
batch_id_1 = int(time.time() * 1000)        # 毫秒级时间戳，例如 1713379200000
batch_id_2 = batch_id_1 + 1                # 简单递增（确保唯一）
batch_id_3 = batch_id_1 + 2
```

### 2.生产者：为每条日志添加 batch_id
- 对每个文件，创建独立的生产者循环，发送时拼接 batch_id 和日志行。
```python
def send_file(file_path, batch_id):
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            message = f"{batch_id}\t{line}"
            producer.send('hdfs-logs-offline', value=message)
    producer.flush()
```
- 然后并发调用（使用线程或异步）
```python
from threading import Thread

Thread(target=send_file, args=('file1.log', batch_id_1)).start()
Thread(target=send_file, args=('file2.log', batch_id_2)).start()
Thread(target=send_file, args=('file3.log', batch_id_3)).start()
```
- 注意：同一个 Kafka topic 可以混合三个文件的消息，因为 batch_id 会区分它们。

### 3. ClickHouse 表结构
- 确保 offline.hdfs_logs 和 offline.block_event_stats 都包含 batch_id 列
```sql
CREATE TABLE offline.hdfs_logs (
    batch_id UInt64,
    raw_log String,
    _timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(_timestamp)
ORDER BY (batch_id, _timestamp);

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
- 物化视图解析消息时，提取 batch_id 和 raw_log：

```sql
CREATE MATERIALIZED VIEW mv_offline_hdfs_logs TO offline.hdfs_logs AS
SELECT 
    toUInt64(splitByChar('\t', raw_log)[1]) AS batch_id,
    splitByChar('\t', raw_log)[2] AS raw_log
FROM kafka_hdfs_logs_offline;
```
### 4. 分别导出三个 CSV 文件

- 对每个 batch_id，执行导出命令（可以用脚本循环）：

``` bash
for BATCH_ID in 1713379200000 1713379200001 1713379200002; do
    docker exec -it clickhouse-server clickhouse-client \
        --query "SELECT raw_log FROM offline.hdfs_logs WHERE batch_id = $BATCH_ID FORMAT CSV" \
        > "file_${BATCH_ID}.csv"
done
```
- 如果导出的是统计结果（每个 BlockId 的事件频次）：
``` bash
docker exec -it clickhouse-server clickhouse-client \
    --query "SELECT block_id, event_id, sum(cnt) FROM offline.block_event_stats WHERE batch_id = $BATCH_ID GROUP BY block_id, event_id FORMAT CSV" \
    > "stats_${BATCH_ID}.csv"
```
### 5. 导出后清理（可选）

- 导出完成后，可以删除对应 batch_id 的数据：
```bash
ALTER TABLE offline.hdfs_logs DELETE WHERE batch_id IN (1713379200000, 1713379200001, 1713379200002);
ALTER TABLE offline.block_event_stats DELETE WHERE batch_id IN (...);
```




