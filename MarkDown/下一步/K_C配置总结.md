## 📦 当前 Kafka + ClickHouse 完整配置与数据链路总结

### 1️⃣ 容器环境总览

| 容器名 | 镜像 | 状态 | 端口映射（宿主机→容器） |
|--------|------|------|------------------------|
| `kafka` | `apache/kafka:3.7.0` | Up | `9092→9092` (broker), `9093→9093` (controller) |
| `clickhouse` | `clickhouse/clickhouse-server:latest` | Up | `8123→8123` (HTTP), `9000→9000` (Native) |

---

### 2️⃣ Kafka 容器详细配置

#### 启动命令（推断）
```bash
docker run -d --name kafka \
  -p 9092:9092 -p 9093:9093 \
  -e KAFKA_NODE_ID=1 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://192.168.115.129:9092 \
  -e KAFKA_LOG_DIRS=/tmp/kraft-combined-logs \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -e KAFKA_DELETE_TOPIC_ENABLE=true \
  -e KAFKA_PROCESS_ROLES=broker,controller \
  -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:9093 \
  -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093 \
  -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT \
  apache/kafka:3.7.0
```

#### 环境变量
- `KAFKA_NODE_ID=1`
- `KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://192.168.115.129:9092`
- `KAFKA_LOG_DIRS=/tmp/kraft-combined-logs`
- `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1`
- `KAFKA_DELETE_TOPIC_ENABLE=true`
- `KAFKA_PROCESS_ROLES=broker,controller`
- `KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:9093`
- `KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER`
- `KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093`
- `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT`

#### 数据卷挂载
无持久化卷（日志存储在容器内 `/tmp/kraft-combined-logs`，容器删除会丢失）

#### 网络
使用默认 bridge 网络，宿主机端口映射 `9092` 和 `9093`。

---

### 3️⃣ ClickHouse 容器详细配置

#### 启动命令（推断）
```bash
docker run -d --name clickhouse \
  -p 8123:8123 -p 9000:9000 \
  -v /data/clickhouse/data:/var/lib/clickhouse \
  -v /data/clickhouse/log:/var/log/clickhouse-server \
  --ulimit nofile=262144:262144 \
  -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \
  clickhouse/clickhouse-server:latest
```

#### 环境变量
- `CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1`

#### 数据卷挂载
- `/data/clickhouse/data` → `/var/lib/clickhouse`（数据持久化）
- `/data/clickhouse/log` → `/var/log/clickhouse-server`（日志持久化）

#### 网络
默认 bridge 网络，宿主机端口映射 `8123`（HTTP）和 `9000`（Native）。

---

### 4️⃣ Kafka Topics

| Topic | 说明 |
|-------|------|
| `hdfs-logs` | 原始实时日志（无 batch_id） |
| `hdfs-logs-offline` | 离线批次日志（格式：`batch_id\t原始日志`） |
| `__consumer_offsets` | Kafka 内部 topic |

---

### 5️⃣ ClickHouse 数据库结构

#### 📁 数据库列表
- `default`：实时处理数据库
- `offline`：离线批处理数据库
- `system`、`INFORMATION_SCHEMA` 等系统库

---

#### 📁 `default` 数据库

##### 表：`hdfs_logs`
```sql
CREATE TABLE default.hdfs_logs
(
    `raw_log` String,
    `_timestamp` DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY _timestamp
```

##### 表：`kafka_hdfs_logs`（Kafka 引擎）
```sql
CREATE TABLE default.kafka_hdfs_logs
(
    `raw_log` String
)
ENGINE = Kafka
SETTINGS kafka_broker_list = '192.168.115.129:9092',
         kafka_topic_list = 'hdfs-logs',
         kafka_group_name = 'clickhouse_consumer',
         kafka_format = 'RawBLOB'
```

##### 物化视图：`mv_hdfs_logs`
```sql
CREATE MATERIALIZED VIEW default.mv_hdfs_logs TO default.hdfs_logs AS
SELECT raw_log FROM default.kafka_hdfs_logs
```

##### 表：`block_event_stats`
```sql
CREATE TABLE default.block_event_stats
(
    `block_id` String,
    `event_id` String,
    `cnt` UInt64,
    `last_updated` DateTime DEFAULT now()
)
ENGINE = SummingMergeTree
ORDER BY (block_id, event_id)
```

##### 物化视图：`mv_block_stats`（简版，仅 E1/E2）
```sql
CREATE MATERIALIZED VIEW default.mv_block_stats TO default.block_event_stats AS
SELECT 
    extract(raw_log, '(blk[-_]?-?\\d+)') AS block_id,
    multiIf(raw_log LIKE '%Adding an already existing block%', 'E1',
            raw_log LIKE '%Verification succeeded for%', 'E2', NULL) AS event_id,
    1 AS cnt
FROM default.hdfs_logs
WHERE block_id != '' AND event_id IS NOT NULL
```

---

#### 📁 `offline` 数据库（离线批处理核心）

##### 表：`hdfs_logs`（带物化列）
```sql
CREATE TABLE offline.hdfs_logs
(
    `raw_log` String,
    `_timestamp` DateTime DEFAULT now(),
    `batch_id` UInt64 MATERIALIZED toUInt64OrZero(splitByChar('\t', raw_log)[1]),
    `block_id` String MATERIALIZED extract(raw_log, 'blk_[-?[0-9]+]')   -- 注意正则可能不标准
)
ENGINE = MergeTree
ORDER BY _timestamp
```
> ⚠️ `block_id` 正则 `'blk_[-?[0-9]+]'` 写法有误，应为 `'blk_-?\\d+'`。但物化视图中已用正确正则覆盖。

##### 表：`kafka_hdfs_logs`（Kafka 引擎）
```sql
CREATE TABLE offline.kafka_hdfs_logs
(
    `raw_log` String
)
ENGINE = Kafka
SETTINGS kafka_broker_list = '192.168.115.129:9092',
         kafka_topic_list = 'hdfs-logs-offline',
         kafka_group_name = 'consumer_group_new_v100',
         kafka_format = 'LineAsString'   -- 注意此处是 LineAsString，不是 RawBLOB
```

##### 物化视图：`mv_hdfs_logs`
```sql
CREATE MATERIALIZED VIEW offline.mv_hdfs_logs TO offline.hdfs_logs AS
SELECT raw_log FROM offline.kafka_hdfs_logs
```

##### 表：`block_event_stats`（含 batch_id 分区）
```sql
CREATE TABLE offline.block_event_stats
(
    `batch_id` UInt64,
    `block_id` String,
    `event_id` String,
    `cnt` UInt64,
    `last_updated` DateTime DEFAULT now()
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMMDD(last_updated)
ORDER BY (batch_id, block_id, event_id)
```

##### 物化视图：`mv_block_stats`（完整 29 种事件）
```sql
CREATE MATERIALIZED VIEW offline.mv_block_stats TO offline.block_event_stats AS
SELECT 
    batch_id,
    extract(raw_log, 'blk_-?\\d+') AS block_id,
    multiIf(
        raw_log LIKE '%Adding an already existing block%', 'E1',
        raw_log LIKE '%Verification succeeded for%', 'E2',
        raw_log LIKE '%Served block%to%', 'E3',
        raw_log LIKE '%Got exception while serving%to%', 'E4',
        raw_log LIKE '%Receiving block%src:%dest:%', 'E5',
        raw_log LIKE '%Received block%src:%dest:%of size%', 'E6',
        raw_log LIKE '%writeBlock%received exception%', 'E7',
        raw_log LIKE '%PacketResponder%for block%Interrupted%', 'E8',
        raw_log LIKE '%Received block%of size%from%', 'E9',
        raw_log LIKE '%PacketResponder%Exception%', 'E10',
        raw_log LIKE '%PacketResponder%for block%terminating%', 'E11',
        raw_log LIKE '%Exception writing block%to mirror%', 'E12',
        raw_log LIKE '%Receiving empty packet for block%', 'E13',
        raw_log LIKE '%Exception in receiveBlock for block%', 'E14',
        raw_log LIKE '%Changing block file offset of block%from%to%meta file offset to%', 'E15',
        raw_log LIKE '%Transmitted block%to%', 'E16',
        raw_log LIKE '%Failed to transfer%to%got%', 'E17',
        raw_log LIKE '%Starting thread to transfer block%to%', 'E18',
        raw_log LIKE '%Reopen Block%', 'E19',
        raw_log LIKE '%Unexpected error trying to delete block%BlockInfo not found in volumeMap%', 'E20',
        raw_log LIKE '%Deleting block%file%', 'E21',
        raw_log LIKE '%BLOCK* NameSystem%allocateBlock:%', 'E22',
        raw_log LIKE '%BLOCK* NameSystem%delete:%is added to invalidSet of%', 'E23',
        raw_log LIKE '%BLOCK* Removing block%from neededReplications as it does not belong to any file%', 'E24',
        raw_log LIKE '%BLOCK* ask%to replicate%to%', 'E25',
        raw_log LIKE '%BLOCK* NameSystem%addStoredBlock: blockMap updated:%is added to%size%', 'E26',
        raw_log LIKE '%BLOCK* NameSystem%addStoredBlock: Redundant addStoredBlock request received for%on%size%', 'E27',
        raw_log LIKE '%BLOCK* NameSystem%addStoredBlock: addStoredBlock request received for%on%size%But it does not belong to any file%', 'E28',
        raw_log LIKE '%PendingReplicationMonitor timed out block%', 'E29',
        NULL
    ) AS event_id,
    1 AS cnt
FROM offline.hdfs_logs
WHERE block_id != '' AND event_id IS NOT NULL
```

##### 表：`anomaly_blocks`（模型预测结果存储）
```sql
CREATE TABLE offline.anomaly_blocks
(
    `batch_id` UInt64,
    `block_id` String,
    `E1` Int32, `E2` Int32, ..., `E29` Int32,
    `anomaly_score` Float32,
    `detected_at` DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(detected_at)
ORDER BY (batch_id, block_id)
```

---

### 6️⃣ 数据流链路

#### 实时链路（`default` 数据库）
```
Kafka topic 'hdfs-logs' → default.kafka_hdfs_logs (Kafka引擎) 
    → default.mv_hdfs_logs (物化视图) → default.hdfs_logs 
    → default.mv_block_stats (简版事件统计) → default.block_event_stats
```

#### 离线链路（`offline` 数据库）
```
Kafka topic 'hdfs-logs-offline' → offline.kafka_hdfs_logs (Kafka引擎) 
    → offline.mv_hdfs_logs (物化视图) → offline.hdfs_logs 
        → 物化列自动计算 batch_id, block_id
    → offline.mv_block_stats (完整事件分类) → offline.block_event_stats
    → (Python 预测脚本) → offline.anomaly_blocks
```

---

### 7️⃣ 后端配置文件（FastAPI）

#### `config/clickhouse.yaml`
```yaml
clickhouse:
  online:
    host: "192.168.115.129"
    port: 9000
    http_port: 8123
    username: "default"
    password: ""
    database: "online"
  offline:
    host: "192.168.115.129"
    port: 9000
    http_port: 8123
    username: "default"
    password: ""
    database: "offline"
```

#### `config/kafka.yml`
```yaml
kafka:
  bootstrap_servers: "192.168.115.129:9092"
  topics:
    online: "hdfs-logs-online"
    offline: "hdfs-logs-offline"
  producer:
    acks: 1
    retries: 3
    batch_size: 65536
    linger_ms: 10
    compression_type: "gzip"
```

---

### 8️⃣ Python 消费者（离线）

建议使用独立的 Python 脚本替代 ClickHouse Kafka 引擎，以避免不稳定。示例脚本 `kafka_to_ch.py` 已提供，负责从 `hdfs-logs-offline` 消费消息并写入 `offline.hdfs_logs`。

---

### 9️⃣ 关键注意事项

- **ClickHouse 端口**：HTTP 8123，Native 9000。Agent 配置中 `http_port` 必须为 **8123**（之前错误用了 8124 导致连接失败）。
- **Kafka 广告地址**：`192.168.115.129:9092`，确保外部可访问。
- **消费者组**：`offline.kafka_hdfs_logs` 使用 `consumer_group_new_v100`；`default.kafka_hdfs_logs` 使用 `clickhouse_consumer`。
- **数据格式**：离线消息必须包含 `\t` 分隔符（`batch_id\traw_log`），否则物化列解析失败。
- **正则表达式**：`block_id` 提取使用 `'blk_-?\\d+'`（匹配 `blk_123` 或 `blk_-456`）。

---

### 🎯 总结

以上涵盖了当前运行中的所有 Kafka/ClickHouse 配置、表结构、数据流和关键文件。这份文档可用于系统重建、故障排查或新人交接。如需导出为 Markdown 文件，直接保存即可。