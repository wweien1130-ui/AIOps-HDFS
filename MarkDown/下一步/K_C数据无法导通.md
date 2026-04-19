这次排查 ClickHouse 对接 Kafka 的过程非常典型，我们经历了从“链路不通”到“数据静默丢失”再到“表结构冲突”的完整过程。

以下是针对你这次 HDFS 日志项目的**复盘总结**：

---

## 1. 链路不通：Unknown format String
* **问题现象**：报错 `UNKNOWN_FORMAT`，ClickHouse 无法识别 `kafka_format = 'String'`。
* **根本原因**：在 ClickHouse 中，`String` 是**数据类型**，而不是**解析格式**。
* **解决方法**：将 `kafka_format` 改为 **`LineAsString`**。这告诉 ClickHouse 将 Kafka 的每一条消息整行读取为一个字符串字段。

## 2. 消息接收不到：Topic 名称不对齐
* **问题现象**：Kafka 生产者发送了数据，但 ClickHouse 目标表始终为空。
* **根本原因**：生产者发送的 Topic 是 `hdfs-logs-offline`，但 ClickHouse Kafka 引擎表监听的 Topic 是 `hdfs-logs`。
* **解决方法**：重新创建 Kafka 引擎表，确保 `kafka_topic_list` 与实际发送的 Topic **完全一致**。

## 3. 无法直接查询：Code 620 报错
* **问题现象**：`SELECT * FROM kafka_hdfs_logs` 报错 `Cannot read from StorageKafka with attached materialized views`。
* **根本原因**：ClickHouse 为了防止物化视图（MV）漏掉数据，默认禁止用户直接从已被视图“消费”的 Kafka 管道表中读取数据。
* **解决方法**：直接查询**目标落地表**（如 `offline.hdfs_logs`），或者临时停止物化视图（不推荐）。

## 4. 解析失败导致数据丢失：MV 逻辑过于严格
* **问题现象**：测试数据（如 `999\tTest`）发送后，目标表没有任何更新。
* **根本原因**：物化视图中写了复杂的解析代码（如 `splitByChar` 取第 5 位）。当测试数据格式不符时，解析器报错，导致该条数据在搬运过程中被静默丢弃。
* **解决方法**：采用“**原始日志入库 + 自动字段分离**”的架构，降低视图的复杂度，确保数据先“落袋为安”。

## 5. 视图创建失败：THERE_IS_NO_COLUMN
* **问题现象**：创建视图时报错找不到 `batch_id` 字段。
* **根本原因**：目标表中的 `batch_id` 和 `block_id` 被定义成了 **`MATERIALIZED`（物化列）**。物化列是自动计算的，不接受外部 SELECT 语句的显式写入。
* **解决方法**：简化物化视图，仅 `SELECT raw_log`。ClickHouse 会根据表结构中定义的表达式，自动从 `raw_log` 里拆分出 `batch_id` 和 `block_id`。

---

## 🏆 最终成功架构总结

| 组件 | 名称 | 核心职责 | 关键配置 |
| :--- | :--- | :--- | :--- |
| **管道** | `kafka_hdfs_logs` | 从 Kafka 实时拉取原始流 | `LineAsString` 格式 |
| **搬运工**| `mv_hdfs_logs` | 触发器，将数据导向目标 | 只传 `raw_log`，不做复杂计算 |
| **终点站**| `hdfs_logs` | 存储并**自动解析**数据 | 使用 `MATERIALIZED` 自动分离字段 |

### 现在的优势：
* **极高容错性**：即使日志格式变了，`raw_log` 也能存下来，不会丢数据。
* **维护简单**：想改解析逻辑？直接 `ALTER TABLE` 修改物化列定义即可，不需要重建视图或管道。

**恭喜你！现在你的 HDFS 日志实时采集系统已经非常健壮了。下一步是要开始针对 `block_id` 进行异常检测分析了吗？**