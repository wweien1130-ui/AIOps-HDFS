# 微信 ClawBot 安装和配置指南

## 概述

本指南介绍如何配置微信 ClawBot 与 HDFS 监控系统的集成，实现通过微信查询系统监控数据。

## 系统架构

```
微信用户 → 微信 ClawBot → OpenClaw → 后端 API (FastAPI) → ClickHouse/Redis
```

## 安装步骤

### 第一步：安装 OpenClaw 微信插件

```bash
# 安装官方微信插件
npm install -g @tencent-weixin/openclaw-weixin-cli

# 或者使用 yarn
yarn global add @tencent-weixin/openclaw-weixin-cli
```

### 第二步：配置 OpenClaw 工具

1. 将 `openclaw_tools_config.json` 复制到 OpenClaw 配置目录
2. 修改配置文件中的 API 地址和认证信息

```bash
# 复制配置文件
cp openclaw_tools_config.json /path/to/openclaw/config/tools.json
```

3. 编辑配置文件，添加 API 认证信息（如果需要）：

```json
{
  "api": {
    "endpoint": "http://localhost:8000/api/realtime/total",
    "method": "GET",
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer YOUR_API_KEY"
    }
  }
}
```

### 第三步：配置微信 ClawBot

1. 启动 OpenClaw 服务
2. 执行微信插件安装命令

```bash
# 启动 OpenClaw
openclaw start

# 配置微信插件
openclaw-weixin setup
```

3. 扫码授权完成绑定

### 第四步：部署微信机器人代码

#### Node.js 版本

```bash
# 安装依赖
npm install axios

# 复制代码
cp wechat_bot_example.js /path/to/your/project/

# 测试代码
node wechat_bot_example.js
```

#### Python 版本

```bash
# 安装依赖
pip install requests

# 复制代码
cp wechat_bot_python.py /path/to/your/project/

# 测试代码
python wechat_bot_python.py
```

## 配置说明

### 1. 后端 API 配置

在微信机器人代码中配置后端 API 地址：

**Node.js 版本**：
```javascript
const API_CONFIG = {
  baseURL: 'http://localhost:8000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
};
```

**Python 版本**：
```python
def __init__(self, api_base_url: str = "http://localhost:8000/api"):
    self.api_base_url = api_base_url
```

### 2. API 认证配置

如果后端 API 需要认证，在请求头中添加：

```javascript
headers: {
  'Content-Type': 'application/json',
  'Authorization': 'Bearer YOUR_API_KEY'
}
```

### 3. 指令映射配置

在 `commandMap` 中配置微信指令到 API 的映射：

```javascript
const commandMap = {
  '健康度': { tool: 'get_system_health', params: {} },
  '过去2小时': { tool: 'get_recent_anomalies', params: { hours: 2 } },
  'Top 10': { tool: 'get_top_anomalies', params: { limit: 10 } },
  // ... 其他指令
};
```

## 使用说明

### 微信指令列表

| 指令 | 功能 | 示例 |
|------|------|------|
| `健康度` | 查询系统健康度 | "查询健康度" |
| `过去X小时` | 查询指定时间范围异常 | "过去2小时" |
| `过去X分钟` | 查询指定时间范围异常 | "过去30分钟" |
| `Top N` | 查询Top N异常Block | "Top 10" |
| `异常分布` | 查询异常类型分布 | "异常分布" |
| `导出数据` | 导出异常数据为CSV | "导出数据" |
| `帮助` | 显示帮助信息 | "帮助" |

### 使用示例

#### 示例 1: 查询系统健康度
```
用户: 查询健康度
微信机器人: 📊 系统健康度: 98.9%
           • 总Block数: 920
           • 异常数量: 10
           • 健康状态: ✅ 优秀
```

#### 示例 2: 查询过去2小时异常
```
用户: 过去2小时
微信机器人: 📋 Top 10 异常Block:
           
           1. Block_12345
              异常分数: 95.2%
              主要事件: E5:150, E9:100
```

#### 示例 3: 查询异常分布
```
用户: 异常分布
微信机器人: 📊 异常类型分布:
           
           E5: 150 次
           E9: 100 次
           E11: 80 次
```

## 测试验证

### 1. 测试后端 API

```bash
# 测试系统健康度 API
curl http://localhost:8000/api/realtime/total

# 测试异常查询 API
curl "http://localhost:8000/api/anomalies/query?hours=1&limit=10"
```

### 2. 测试微信机器人代码

**Node.js 版本**：
```bash
node wechat_bot_example.js
```

**Python 版本**：
```bash
python wechat_bot_python.py
```

### 3. 测试微信消息

在微信中发送以下指令测试：

1. `帮助` - 应显示帮助信息
2. `查询健康度` - 应显示系统健康度
3. `过去2小时` - 应显示过去2小时的异常数据

## 故障排除

### 问题 1: 微信机器人无法连接后端 API

**解决方案**：
1. 检查后端 API 是否运行：`curl http://localhost:8000/api/health`
2. 检查防火墙设置
3. 检查 API 地址配置是否正确

### 问题 2: 微信消息无响应

**解决方案**：
1. 检查 OpenClaw 微信插件是否正常运行
2. 检查微信授权是否有效
3. 查看日志文件排查错误

### 问题 3: 消息长度超限

**解决方案**：
1. 减少返回的异常数量（修改 `limit` 参数）
2. 简化回复格式
3. 分段发送消息

## 高级配置

### 1. 自定义指令

在 `commandMap` 中添加新指令：

```javascript
'自定义指令': { tool: 'get_custom_data', params: { custom: 'value' } }
```

### 2. 消息格式定制

修改 `formatHealthReply`、`formatAnomaliesReply` 等函数来自定义回复格式。

### 3. 定时推送

使用定时任务定期推送异常告警：

```javascript
// 每小时推送一次异常报告
setInterval(async () => {
  const data = await getRecentAnomalies({ hours: 1 });
  if (data.anomaly_count > 0) {
    // 发送告警消息到微信
  }
}, 3600000);
```

## 安全注意事项

1. **API 认证**：生产环境必须使用 API Key 或 Token 认证
2. **消息过滤**：对用户输入进行过滤，防止恶意指令
3. **访问控制**：限制可访问的 API 端点
4. **日志记录**：记录所有操作日志以便审计

## 下一步

1. 完成安装和配置
2. 测试基本功能
3. 根据需求定制指令和回复格式
4. 部署到生产环境

## 相关文档

- OpenClaw 官方文档: https://docs.openclaw.ai
- 微信插件文档: https://docs.openclaw.ai/weixin
- 后端 API 文档: http://localhost:8000/docs
