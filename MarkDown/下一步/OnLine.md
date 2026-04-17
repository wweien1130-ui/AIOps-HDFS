
# 在线：
## kafka: 
- 将数据发送给hdfs-logs-online
## clickhouse: 
- 创建对应于hdfs-logs-online的3表+2视图

### -- 在线表

```sql  
CREATE TABLE online.hdfs_logs ...;
CREATE TABLE online.block_event_stats ...;
```


### 在线模式（实时流）
- 生产者持续发送日志（不附加 batch_id，或附加固定的 batch_id = 0 表示实时流）。

- ClickHouse 写入 online 数据库的表中，不设置 batch_id 或按小时分区。

- 轮询脚本持续查询 online.block_event_stats 中的增量数据（利用 last_updated 字段），实时预测并告警。

- 不需要导出 CSV，也不删除数据（或定期按时间分区清理旧数据，例如保留最近 7 天）。

