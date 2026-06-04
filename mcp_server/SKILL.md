---
name: hdfs-monitor
description: "HDFS 系统监控工具，查询系统健康度、异常 Block、事件分布等实时数据。需要从 Windows 后端 API 获取数据。"
metadata:
  openclaw:
    emoji: ":bar_chart:"
    requires:
      bins: ["curl"]
---

# HDFS 系统监控

用于查询 HDFS 系统的健康状态、异常 Block、事件分布等实时监控数据。

**重要**：后端 API 运行在 Windows 主机上，WSL 中可以通过 `curl http://172.21.64.1:8000/api/...` 访问。

## 可用工具

### 1. get_system_health - 查询系统健康度

查询当前 HDFS 系统的总 Block 数量和健康状态。

调用方式：
```
curl -s "http://172.21.64.1:8000/api/realtime/total"
```

返回示例：
```
{"total_blocks": 12345}
```

回复格式：根据返回数据，向用户报告系统健康度。total_blocks 大于 0 表示系统正常运行。

### 2. get_recent_anomalies - 查询最近异常数据

查询指定时间范围内的异常 Block 列表。

参数：
- hours: 过去多少小时（可选，默认 1）
- minutes: 过去多少分钟（可选）
- limit: 返回数量（可选，默认 10）

调用方式：
```
curl -s "http://172.21.64.1:8000/api/anomalies/query?hours=1&limit=10"
```

返回示例：
```
{"anomaly_count":5,"anomalies":[{"block_id":"block_001","anomaly_score":0.85}],"event_distribution":{"E1":100,"E2":50}}
```

回复格式：报告异常数量，列出每个异常 Block 的分数和主要事件。

### 3. get_top_anomalies - Top N 异常 Block

获取异常分数最高的 Block 列表。

参数：
- limit: 返回数量（可选，默认 10）
- hours: 过去多少小时（可选，默认 1）

调用方式：
```
curl -s "http://172.21.64.1:8000/api/anomalies/query?hours=1&limit=10"
```

### 4. get_event_distribution - 异常类型分布

统计各 E 事件（E1~E29）的发生次数和占比。

参数：
- hours: 过去多少小时（可选，默认 1）

调用方式：
```
curl -s "http://172.21.64.1:8000/api/anomalies/query?hours=1&limit=1"
```

从返回的 event_distribution 字段获取分布数据。

回复格式：按次数降序列出各事件类型及其占比。

## 注意事项

- API 返回的分数范围是 0~1，越高越异常
- 如果返回的 anomaly_count 为 0 或 anomalies 为空数组，表示没有异常数据
- event_distribution 对象包含所有事件的统计计数
- 调用失败时告知用户"暂时无法获取数据，请稍后重试"
- 所有 curl 命令需要添加 -s 参数静默执行，并使用 http://172.21.64.1:8000 作为 API 地址
