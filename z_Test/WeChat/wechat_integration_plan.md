# 微信 ClawBot 与前端系统集成方案

## 1. 系统架构

```
微信用户 → 微信 ClawBot → OpenClaw → 后端 API (FastAPI) → ClickHouse/Redis
```

## 2. 实现目标

### 2.1 简单文本查询功能
- ✅ 查询系统健康度
- ✅ 查询异常数量（支持时间范围）
- ✅ 查询 Top 10 异常 Block
- ✅ 帮助指令

### 2.2 交互体验测试
- ✅ 指令响应速度
- ✅ 回复格式清晰度
- ✅ 错误处理机制

## 3. 详细实现步骤

### 3.1 配置 OpenClaw 工具调用

#### 3.1.1 创建工具配置文件
位置：OpenClaw 配置目录下的 `tools.json`

```json
{
  "tools": [
    {
      "name": "get_system_health",
      "description": "获取系统健康度和总Block数",
      "parameters": {
        "type": "object",
        "properties": {}
      },
      "api": {
        "endpoint": "http://localhost:8000/api/realtime/total",
        "method": "GET"
      }
    },
    {
      "name": "get_recent_anomalies",
      "description": "查询最近异常数据，支持时间范围",
      "parameters": {
        "type": "object",
        "properties": {
          "hours": {"type": "integer", "description": "过去多少小时"},
          "minutes": {"type": "integer", "description": "过去多少分钟"},
          "limit": {"type": "integer", "description": "返回数量限制", "default": 10}
        }
      },
      "api": {
        "endpoint": "http://localhost:8000/api/anomalies/query",
        "method": "GET"
      }
    }
  ]
}
```

#### 3.1.2 配置 API 认证
在 OpenClaw 配置中添加 API Key：

```yaml
# OpenClaw 配置
api_keys:
  - key: "your-api-key-here"
    services:
      - "backend-api"
```

### 3.2 设计微信指令解析

#### 3.2.1 指令映射表

| 用户输入 | 意图识别 | 工具调用 | 参数 | 回复格式 |
|----------|----------|----------|------|----------|
| "查询健康度" | system_health | get_system_health | {} | 健康度: XX% |
| "查询过去X小时" | recent_anomalies | get_recent_anomalies | hours=X | 异常数量: X |
| "查询过去X分钟" | recent_anomalies | get_recent_anomalies | minutes=X | 异常数量: X |
| "Top 10" | top_anomalies | get_recent_anomalies | hours=1, limit=10 | Top 10 列表 |
| "帮助" | help | - | - | 指令列表 |

#### 3.2.2 自然语言解析规则
```javascript
// 指令解析逻辑
if (text.includes("健康度") || text.includes("系统状态")) {
  return { intent: "system_health" };
}
if (text.includes("过去") && text.includes("小时")) {
  const hours = extractNumber(text);
  return { intent: "recent_anomalies", hours };
}
if (text.includes("Top") || text.includes("前10")) {
  return { intent: "top_anomalies", hours: 1, limit: 10 };
}
```

### 3.3 消息格式设计

#### 3.3.1 系统健康度回复
```
📊 系统健康度报告
─────────────────
总 Block 数: 920
异常 Block 数: 10
健康度: 98.9%
更新时间: 14:30:25
```

#### 3.3.2 异常列表回复
```
🚨 Top 10 异常 Block
─────────────────
1. Block_12345 (异常分数: 0.95)
   E5: 150, E9: 100, E11: 80

2. Block_67890 (异常分数: 0.88)
   E5: 120, E9: 80, E11: 60
...
─────────────────
共 10 个异常 (过去1小时)
```

#### 3.3.3 帮助回复
```
🤖 HDFS 异常检测机器人
─────────────────
可用指令:
• 查询健康度 - 查看系统健康状态
• 查询过去X小时 - 查看指定时间范围的异常
• Top 10 - 查看最近10个异常
• 帮助 - 显示此帮助信息
```

### 3.4 错误处理机制

#### 3.4.1 API 调用失败
```
⚠️ 系统提示
─────────────────
抱歉，暂时无法获取数据。
请稍后重试或联系管理员。
```

#### 3.4.2 无效指令
```
⚠️ 指令提示
─────────────────
抱歉，无法理解您的指令。
请输入"帮助"查看可用指令。
```

## 4. 测试计划

### 4.1 单元测试
- [ ] 测试工具调用是否正常
- [ ] 测试指令解析是否准确
- [ ] 测试消息格式是否清晰

### 4.2 集成测试
- [ ] 测试微信消息接收
- [ ] 测试 API 调用链路
- [ ] 测试回复发送

### 4.3 用户体验测试
- [ ] 响应速度测试（< 3秒）
- [ ] 消息长度测试（< 1000汉字）
- [ ] 错误处理测试

## 5. 实施时间表

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| 1 | 配置 OpenClaw 工具 | 1小时 |
| 2 | 设计指令解析逻辑 | 1小时 |
| 3 | 实现消息格式化 | 1小时 |
| 4 | 测试与优化 | 2小时 |
| **总计** | | **5小时** |

## 6. 注意事项

1. **API 认证**：确保 OpenClaw 配置正确的 API Key
2. **消息长度**：微信文本消息限制约 1000 汉字
3. **响应速度**：API 调用应在 3 秒内完成
4. **错误处理**：网络异常时提供友好提示

## 7. 后续优化方向

1. 支持更多查询维度（按 Block ID 查询）
2. 支持图表生成（发送图片消息）
3. 支持定时推送异常告警
4. 支持多用户权限管理
