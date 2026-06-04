#!/bin/bash

# 验证 OpenClaw 与后端 API 连接的脚本
# 在 WSL 中运行此脚本

echo "=== OpenClaw 连接验证脚本 ==="
echo ""

# 1. 检查后端 API 是否可访问
echo "1. 测试后端 API 连接..."
echo "   尝试访问 http://localhost:8000/api/health"

# 在 WSL 中，localhost 指向 WSL 自己，需要访问 Windows 主机
# 尝试使用 host.docker.internal 或 Windows 主机 IP
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "   ✅ WSL localhost:8000 可访问"
else
    echo "   ❌ WSL localhost:8000 不可访问"
    echo "   尝试使用 host.docker.internal..."
    if curl -s http://host.docker.internal:8000/api/health > /dev/null 2>&1; then
        echo "   ✅ host.docker.internal:8000 可访问"
        echo "   请在 OpenClaw 配置中使用 host.docker.internal 替换 localhost"
    else
        echo "   ❌ host.docker.internal:8000 不可访问"
        echo "   尝试获取 Windows 主机 IP..."
        # 获取 Windows 主机 IP
        WINDOWS_IP=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}' | head -1)
        if [ -n "$WINDOWS_IP" ]; then
            echo "   Windows 主机 IP: $WINDOWS_IP"
            if curl -s http://$WINDOWS_IP:8000/api/health > /dev/null 2>&1; then
                echo "   ✅ Windows 主机 IP:8000 可访问"
                echo "   请在 OpenClaw 配置中使用 $WINDOWS_IP 替换 localhost"
            else
                echo "   ❌ Windows 主机 IP:8000 不可访问"
                echo "   请检查防火墙设置和后端 API 是否运行"
            fi
        else
            echo "   ❌ 无法获取 Windows 主机 IP"
        fi
    fi
fi

echo ""

# 2. 测试 API 端点
echo "2. 测试 API 端点..."
echo "   测试系统健康度 API..."
curl -s http://localhost:8000/api/realtime/total 2>/dev/null | head -c 100
echo ""
echo "   测试异常查询 API..."
curl -s "http://localhost:8000/api/anomalies/query?hours=1&limit=5" 2>/dev/null | head -c 200
echo ""

echo ""

# 3. 检查 OpenClaw 配置
echo "3. 检查 OpenClaw 配置..."
OPENCLAW_CONFIG="$HOME/.openclaw/config/tools.json"
if [ -f "$OPENCLAW_CONFIG" ]; then
    echo "   ✅ 找到 OpenClaw 配置文件: $OPENCLAW_CONFIG"
    echo "   检查 API 端点配置..."
    grep -o '"endpoint": "[^"]*"' "$OPENCLAW_CONFIG" | head -5
else
    echo "   ❌ 未找到 OpenClaw 配置文件"
    echo "   请确保 OpenClaw 已正确安装和配置"
fi

echo ""

# 4. 检查 OpenClaw 日志
echo "4. 检查 OpenClaw 日志..."
OPENCLAW_LOGS="$HOME/.openclaw/logs"
if [ -d "$OPENCLAW_LOGS" ]; then
    echo "   ✅ 找到 OpenClaw 日志目录: $OPENCLAW_LOGS"
    echo "   最近日志文件:"
    ls -lt "$OPENCLAW_LOGS" | head -10
    echo ""
    echo "   检查最近的错误日志..."
    if [ -f "$OPENCLAW_LOGS/error.log" ]; then
        echo "   错误日志内容 (最近10行):"
        tail -10 "$OPENCLAW_LOGS/error.log"
    else
        echo "   未找到 error.log 文件"
    fi
else
    echo "   ❌ 未找到 OpenClaw 日志目录"
fi

echo ""

# 5. 测试微信机器人代码
echo "5. 测试微信机器人代码..."
if [ -f "wechat_bot_python.py" ]; then
    echo "   ✅ 找到微信机器人 Python 代码"
    echo "   运行测试..."
    python wechat_bot_python.py --test 2>&1 | head -20
else
    echo "   ❌ 未找到微信机器人代码"
fi

echo ""
echo "=== 验证完成 ==="
echo ""
echo "下一步操作："
echo "1. 如果 API 不可访问，请检查后端 API 是否运行"
echo "2. 如果 WSL 无法访问 localhost，请使用 host.docker.internal 或 Windows 主机 IP"
echo "3. 更新 OpenClaw 配置中的 API 端点"
echo "4. 重启 OpenClaw 服务"
echo "5. 在微信中发送 '帮助' 指令测试连接"