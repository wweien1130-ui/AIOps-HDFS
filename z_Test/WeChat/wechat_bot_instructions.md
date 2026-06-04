# 微信 ClawBot 指令解析逻辑

## 指令映射表

| 用户输入 | 意图识别 | 工具调用 | 参数 | 说明 |
|----------|----------|----------|------|------|
| `健康度` | system_health | get_system_health | - | 查询系统健康度 |
| `查询健康度` | system_health | get_system_health | - | 查询系统健康度 |
| `系统状态` | system_health | get_system_health | - | 查询系统状态 |
| `过去2小时` | recent_anomalies | get_recent_anomalies | hours=2 | 查询过去2小时异常 |
| `查询过去2小时` | recent_anomalies | get_recent_anomalies | hours=2 | 查询过去2小时异常 |
| `过去30分钟` | recent_anomalies | get_recent_anomalies | minutes=30 | 查询过去30分钟异常 |
| `查询过去30分钟` | recent_anomalies | get_recent_anomalies | minutes=30 | 查询过去30分钟异常 |
| `Top 10` | top_anomalies | get_top_anomalies | limit=10 | 查询Top 10异常 |
| `异常列表` | top_anomalies | get_top_anomalies | limit=10 | 查询异常列表 |
| `异常分布` | event_distribution | get_event_distribution | - | 查询异常类型分布 |
| `导出数据` | export_data | export_anomalies | - | 导出异常数据 |
| `帮助` | help | - | - | 显示帮助信息 |

## 指令解析逻辑

### 1. 简单指令匹配

```javascript
// 指令关键词映射
const commandMap = {
  // 健康度查询
  '健康度': { tool: 'get_system_health', params: {} },
  '查询健康度': { tool: 'get_system_health', params: {} },
  '系统状态': { tool: 'get_system_health', params: {} },
  
  // 时间范围查询
  '过去2小时': { tool: 'get_recent_anomalies', params: { hours: 2 } },
  '查询过去2小时': { tool: 'get_recent_anomalies', params: { hours: 2 } },
  '过去30分钟': { tool: 'get_recent_anomalies', params: { minutes: 30 } },
  '查询过去30分钟': { tool: 'get_recent_anomalies', params: { minutes: 30 } },
  
  // Top N 查询
  'Top 10': { tool: 'get_top_anomalies', params: { limit: 10 } },
  '异常列表': { tool: 'get_top_anomalies', params: { limit: 10 } },
  
  // 分布查询
  '异常分布': { tool: 'get_event_distribution', params: {} },
  
  // 导出数据
  '导出数据': { tool: 'export_anomalies', params: {} },
  
  // 帮助
  '帮助': { tool: null, action: 'show_help' }
}
```

### 2. 自然语言解析

```javascript
// 解析用户输入的自然语言
function parseUserInput(message) {
  const text = message.trim().toLowerCase()
  
  // 1. 检查简单指令匹配
  for (const [keyword, command] of Object.entries(commandMap)) {
    if (text.includes(keyword.toLowerCase())) {
      return command
    }
  }
  
  // 2. 解析时间范围（如 "查询过去2小时"）
  const timeMatch = text.match(/过去(\d+)(小时|分钟|秒|天)/)
  if (timeMatch) {
    const value = parseInt(timeMatch[1])
    const unit = timeMatch[2]
    
    let params = {}
    if (unit === '小时') params.hours = value
    else if (unit === '分钟') params.minutes = value
    else if (unit === '秒') params.seconds = value
    else if (unit === '天') params.days = value
    
    return {
      tool: 'get_recent_anomalies',
      params: params
    }
  }
  
  // 3. 解析 Top N（如 "查询Top 5异常"）
  const topMatch = text.match(/(top|前)(\d+)/i)
  if (topMatch) {
    const limit = parseInt(topMatch[2])
    return {
      tool: 'get_top_anomalies',
      params: { limit: limit }
    }
  }
  
  // 默认返回帮助
  return { tool: null, action: 'show_help' }
}
```

### 3. 工具调用逻辑

```javascript
// 调用 OpenClaw 工具
async function callTool(toolName, params) {
  const toolConfig = toolsConfig.find(t => t.name === toolName)
  if (!toolConfig) {
    throw new Error(`工具 ${toolName} 不存在`)
  }
  
  // 构建 API 请求
  let url = toolConfig.api.endpoint
  const queryParams = new URLSearchParams(params).toString()
  if (queryParams) {
    url += '?' + queryParams
  }
  
  const response = await fetch(url, {
    method: toolConfig.api.method,
    headers: toolConfig.api.headers
  })
  
  if (!response.ok) {
    throw new Error(`API 请求失败: ${response.status}`)
  }
  
  return await response.json()
}
```

### 4. 回复格式化

```javascript
// 格式化系统健康度回复
function formatHealthReply(data) {
  const totalBlocks = data.total_blocks || 0
  const anomalyCount = data.anomaly_count || 0
  const healthPercent = ((1 - (anomalyCount / totalBlocks)) * 100).toFixed(1)
  
  return `📊 系统健康度: ${healthPercent}%
• 总Block数: ${totalBlocks}
• 异常数量: ${anomalyCount}
• 健康状态: ${healthPercent > 95 ? '✅ 优秀' : healthPercent > 80 ? '⚠️ 良好' : '❌ 需关注'}`
}

// 格式化异常列表回复
function formatAnomaliesReply(data) {
  const anomalies = data.anomalies || []
  if (anomalies.length === 0) {
    return '暂无异常数据'
  }
  
  let reply = `📋 Top ${anomalies.length} 异常Block:\n\n`
  anomalies.forEach((item, index) => {
    const events = item.events || []
    const eventStr = events.slice(0, 3).map(e => `${e.event_id}:${e.count}`).join(', ')
    reply += `${index + 1}. ${item.block_id}\n`
    reply += `   异常分数: ${(item.probability * 100).toFixed(1)}%\n`
    if (eventStr) {
      reply += `   主要事件: ${eventStr}\n`
    }
    reply += '\n'
  })
  
  return reply
}

// 格式化异常分布回复
function formatDistributionReply(data) {
  const eventDist = data.event_distribution || {}
  const events = Object.entries(eventDist)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
  
  if (events.length === 0) {
    return '暂无异常类型数据'
  }
  
  let reply = `📊 异常类型分布:\n\n`
  events.forEach(([eventId, count]) => {
    reply += `${eventId}: ${count} 次\n`
  })
  
  return reply
}
```

## 微信消息处理流程

```
用户发送消息
  ↓
微信 ClawBot 接收消息
  ↓
解析用户意图
  ↓
调用对应工具
  ↓
获取 API 数据
  ↓
格式化回复内容
  ↓
发送消息给用户
```

## 错误处理

```javascript
// 错误处理逻辑
function handleError(error) {
  console.error('处理错误:', error)
  
  if (error.message.includes('API 请求失败')) {
    return '抱歉，暂时无法获取数据，请稍后重试'
  } else if (error.message.includes('工具不存在')) {
    return '抱歉，该功能暂不可用'
  } else {
    return '抱歉，处理消息时出现错误'
  }
}
```

## 使用示例

### 示例 1: 查询系统健康度
```
用户: 查询健康度
微信机器人: 📊 系统健康度: 98.9%
           • 总Block数: 920
           • 异常数量: 10
           • 健康状态: ✅ 优秀
```

### 示例 2: 查询过去2小时异常
```
用户: 过去2小时
微信机器人: 📋 Top 10 异常Block:
           
           1. Block_12345
              异常分数: 95.2%
              主要事件: E5:150, E9:100
           
           2. Block_67890
              异常分数: 88.5%
              主要事件: E11:80, E5:60
```

### 示例 3: 查询异常分布
```
用户: 异常分布
微信机器人: 📊 异常类型分布:
           
           E5: 150 次
           E9: 100 次
           E11: 80 次
           E2: 50 次
```

### 示例 4: 帮助信息
```
用户: 帮助
微信机器人: 🤖 HDFS系统监控助手
            
            可用指令:
            • 健康度 / 查询健康度 - 查询系统健康状态
            • 过去X小时 / 过去X分钟 - 查询指定时间范围异常
            • Top N / 异常列表 - 查询Top N异常Block
            • 异常分布 - 查询异常类型分布
            • 导出数据 - 导出异常数据为CSV
            • 帮助 - 显示此帮助信息
```
