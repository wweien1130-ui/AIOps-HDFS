# ClickHouse 连接失败解决方案：重新创建容器

## 问题描述

这是一个非常直接且干净的解决方案。删除旧容器并重新创建一个新的 ClickHouse 容器，可以彻底清除之前混乱的配置文件（比如 users.d 里限制网络访问的规则），让你从零开始，确保密码为空且网络可访问。

## 解决方案步骤

### 一、备份旧容器中的数据（如果重要）

如果 `block_event_stats` 表里有重要数据，请先导出：

```bash
docker exec 62a7a90fa233 clickhouse-client --query "SELECT * FROM block_event_stats FORMAT CSV" > backup.csv
```

如果数据不重要，可以跳过这一步。

### 二、停止并删除旧容器

```bash
docker stop 62a7a90fa233
docker rm 62a7a90fa233
```

### 三、重新创建 ClickHouse 容器（配置空密码 + 开放网络）

执行以下命令，它会：
- 映射 8123 (HTTP) 和 9000 (Native) 端口
- 明确设置 `CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1` 允许用户管理
- 不设置任何密码环境变量 → default 用户密码为空
- 允许所有 IP 访问（通过 --network=host 或默认配置）

```bash
docker run -d \
  --name clickhouse \
  -p 8123:8123 \
  -p 9000:9000 \
  -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \
  clickhouse/clickhouse-server
```

**注意：** 如果你需要持久化数据，加上 `-v clickhouse-data:/var/lib/clickhouse`，但新容器会使用空数据卷，原来的数据就丢失了。如果需要保留数据，请先备份。

### 四、在 Windows 11 上编写测试脚本

你可以用 Python 或 curl 快速测试连接。

#### 方法1：Python 测试脚本（使用 HTTP 端口 8123）

创建 `test_clickhouse.py`：

```python
import requests

url = "http://192.168.115.129:8123/"
query = "SELECT 1"
auth = ('default', '')  # 空密码

try:
    r = requests.post(url, params={'query': query}, auth=auth)
    print("状态码:", r.status_code)
    print("返回内容:", r.text)
    if r.text.strip() == '1':
        print("✅ 连接成功，空密码有效")
    else:
        print("❌ 返回异常")
except Exception as e:
    print("❌ 连接失败:", e)
```

运行：

```bash
python test_clickhouse.py
```

#### 方法2：curl 测试（命令行）

```bash
curl -X POST "http://192.168.115.129:8123/?query=SELECT%201" --user default:
```

如果返回 `1`，说明连接成功。

## 验证连接成功后的操作

1. **检查容器状态**：
   ```bash
   docker ps
   ```

2. **查看容器日志**：
   ```bash
   docker logs clickhouse
   ```

3. **进入容器内部测试**：
   ```bash
   docker exec -it clickhouse clickhouse-client
   ```

## 注意事项

- 确保防火墙允许 8123 和 9000 端口访问
- 如果使用 Docker Desktop，确保 WSL2 正常运行
- 如果连接仍然失败，检查网络配置和防火墙设置

## 总结

通过重新创建容器，可以彻底解决因配置错误导致的连接问题。这种方法简单直接，适合快速恢复 ClickHouse 服务。