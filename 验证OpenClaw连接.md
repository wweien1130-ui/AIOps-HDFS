# 验证微信 OpenClaw 与后端 API 连接

## 概述

本文档提供验证微信中登录的 OpenClaw 是否能与后端 API 产生联系的步骤。

## 系统架构

```
微信用户 → 微信 ClawBot → OpenClaw (WSL) → 后端 API (Windows) → ClickHouse/Redis
```

## 验证步骤

### 步骤 1: 检查后端 API 状态

在 Windows 命令行中运行：

```bash
# 检查端口 8000 是否监听
netstat -ano | findstr :8000

# 测试 API 健康检查
curl http://localhost:8000/api/health
```

**预期结果**: 
- 端口 8000 应处于 LISTENING 状态
- API 应返回 `{"status":"healthy"}`

### 步骤 2: 在 WSL 中测试 API 连接

打开 WSL 终端（Ubuntu），运行以下命令：

```bash
# 测试 WSL localhost 连接
curl http://localhost:8000/api/health

# 如果失败，尝试使用 host.docker.internal
curl http://host.docker.internal:8000/api/health

# 如果还是失败，获取 Windows 主机 IP
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
# 然后使用该 IP 测试
curl http://<WINDOWS_IP>:8000/api/health
```

**关键点**: 
- WSL 中的 `localhost` 指向 WSL 自己，不是 Windows 主机
- 需要使用 `host.docker.internal` 或 Windows 主机 IP 访问

### 步骤 3: 检查 OpenClaw 配置

在 WSL 中运行：

```bash
# 查看 OpenClaw 配置文件
cat ~/.openclaw/config/tools.json | grep endpoint
```

**检查要点**:
- API 端点是否正确（应使用 `host.docker.internal` 或 Windows IP）
- 如果配置中使用的是 `localhost`，需要修改为可访问的地址

### 步骤 4: 查看 OpenClaw 日志

在 WSL 中运行：

```bash
# 查看 OpenClaw 日志目录
ls -la ~/.openclaw/logs/

# 查看错误日志
tail -50 ~/.openclaw/logs/error.log

# 查看运行日志
tail -50 ~/.openclaw/logs/openclaw.log
```

**检查要点**:
- 是否有连接错误
- 是否有 API 调用失败的记录

### 步骤 5: 测试微信机器人代码

在 WSL 中运行：

```bash
# 测试 Python 版本微信机器人
python wechat_bot_python.py --test

# 或者运行 Node.js 版本
node wechat_bot_example.js
```

### 步骤 6: 在微信中测试

在微信中发送以下指令：

1. `帮助` - 应显示帮助信息
2. `查询健康度` - 应显示系统健康度
3. `过去2小时` - 应显示过去2小时的异常数据

## 常见问题及解决方案

### 问题 1: WSL 无法访问 localhost:8000

**原因**: WSL 中的 localhost 指向 WSL 自己，不是 Windows 主机。

**解决方案**:
1. 使用 `host.docker.internal` 替换 `localhost`
2. 或者使用 Windows 主机 IP（通过 `cat /etc/resolv.conf` 获取）

**修改 OpenClaw 配置**:
```bash
# 编辑配置文件
vim ~/.openclaw/config/tools.json

# 将所有 "http://localhost:8000" 替换为 "http://host.docker.internal:8000"
```

### 问题 2: 微信消息无响应

**检查步骤**:
1. 确认 OpenClaw 服务正在运行
2. 检查微信授权是否有效
3. 查看 OpenClaw 日志中的错误信息

### 问题 3: API 调用失败

**检查步骤**:
1. 确认后端 API 正在运行
2. 检查防火墙设置（Windows 防火墙可能阻止 WSL 访问）
3. 测试 API 端点是否可访问

### 问题 4: 消息长度超限

**解决方案**:
1. 减少返回的异常数量（修改 `limit` 参数）
2. 简化回复格式
3. 分段发送消息

## 自动化验证脚本

项目中提供了自动化验证脚本 `verify_openclaw_connection.sh`：

```bash
# 在 WSL 中运行
chmod +x verify_openclaw_connection.sh
./verify_openclaw_connection.sh
```

该脚本会自动：
1. 测试 API 连接
2. 检查 OpenClaw 配置
3. 查看 OpenClaw 日志
4. 测试微信机器人代码

## 下一步操作

1. **如果连接成功**: 
   - 在微信中发送指令测试功能
   - 监控日志确保稳定运行

2. **如果连接失败**:
   - 根据错误信息排查问题
   - 检查网络配置和防火墙设置
   - 重新配置 OpenClaw 并重启服务

## 相关文件

- `openclaw_tools_config.json` - OpenClaw 工具配置
- `wechat_bot_python.py` - 微信机器人 Python 版本
- `wechat_bot_example.js` - 微信机器人 Node.js 版本
- `wechat_bot_setup_guide.md` - 详细安装指南
- `verify_openclaw_connection.sh` - 自动化验证脚本