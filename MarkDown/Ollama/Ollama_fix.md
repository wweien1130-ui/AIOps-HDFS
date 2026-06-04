# Ollama（Windows）与 WSL 互通问题及解决方案

## 问题现象

Ollama 安装在 Windows 上，OpenClaw 运行在 WSL（Ubuntu）中。从 WSL 无法访问 Windows 上的 Ollama API。

```bash
# Windows 本地测试：正常
curl http://localhost:11434/api/tags
# → 返回模型列表 ✅

# WSL 中测试：超时
curl http://172.21.64.1:11434/api/tags
# → Failed to connect: Timeout was reached ❌
```

其中 `172.21.64.1` 是 WSL 访问 Windows 主机的网关 IP（通过 `ip route | grep default` 确认）。

---

## 根因分析

Ollama 默认只监听 `127.0.0.1`（本地回环地址），拒绝来自其他网络接口的连接。

```
> netstat -ano | findstr ":11434"

  TCP    127.0.0.1:11434        0.0.0.0:0              LISTENING       18620
         ^^^^^^^^^
         只绑定了本地回环，WSL 从 172.21.64.1 这个外部接口进来时被拒绝
```

WSL 本质上是一个独立的网络命名空间，它通过虚拟网卡与 Windows 通信。从 WSL 发起的连接对于 Windows 来说是从 `172.21.64.x` 网段来的"外部"连接，因此被 `127.0.0.1` 的绑定拒绝。

---

## 解决方案

### 步骤 1：设置环境变量

让 Ollama 监听所有网络接口（`0.0.0.0`）而非仅 `127.0.0.1`：

```cmd
setx OLLAMA_HOST 0.0.0.0
```

`setx` 将环境变量写入注册表，对新启动的进程永久生效。当前正在运行的 Ollama 不受影响。

### 步骤 2：重启 Ollama

Ollama 通常以普通进程运行（非 Windows 服务），由托盘程序 `ollama app.exe` 守护。直接 kill 后托盘程序会自动重启，但使用的是旧环境变量。

**正确的做法**：

```cmd
# 1. 杀掉 Ollama 服务器进程和托盘程序
taskkill /F /IM "ollama app.exe"
taskkill /F /IM "ollama.exe"

# 2. 确认端口已释放
netstat -ano | findstr ":11434"
# 应无输出

# 3. 带新环境变量手动启动
set OLLAMA_HOST=0.0.0.0
ollama serve
```

或在 Bash（Git Bash / WSL Bash 调用 Windows 程序）中：

```bash
export OLLAMA_HOST=0.0.0.0
ollama serve &
```

### 步骤 3：验证

```bash
# 确认监听在 0.0.0.0
netstat -ano | findstr ":11434"
# 应显示: TCP  0.0.0.0:11434  0.0.0.0:0  LISTENING

# 从 WSL 测试
wsl bash -c 'curl -s http://172.21.64.1:11434/api/tags'
# → 返回模型列表 ✅
```

---

## 验证结果

| 测试 | 修复前 | 修复后 |
|------|:---:|:---:|
| Windows `localhost:11434` | ✅ | ✅ |
| WSL `172.21.64.1:11434` | ❌ Timeout | ✅ 正常返回 |
| OpenAI 兼容端点 `/v1/models` | ❌ | ✅ |
| 聊天补全 `/v1/chat/completions` | ❌ | ✅ |

---

## 关键要点

1. **Ollama 默认安全策略**：只绑 `127.0.0.1` 是 Ollama 的默认行为，防止局域网内其他设备访问
2. **WSL 是独立网络**：WSL 通过 Hyper-V 虚拟网卡与 Windows 通信，对 Windows 来说是"外部"连接
3. **`setx` 不作用于当前进程**：需手动 kill 托盘程序后，带环境变量重启
4. **如果开了 Windows 防火墙**：需额外放行端口 11434（本次环境中防火墙未拦截）

---

## 相关配置速查

```
Ollama API 地址（Windows 本地）：  http://localhost:11434
Ollama API 地址（从 WSL 访问）：   http://172.21.64.1:11434
OpenAI 兼容端点：                   http://172.21.64.1:11434/v1
WSL → Windows 网关 IP 查询方式：    wsl bash -c 'ip route | grep default'
Ollama 监听地址验证：               netstat -ano | findstr ":11434"
```
