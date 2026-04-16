import os
import sys
import subprocess
from langchain_core.tools import tool

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
SCRIPT_DIR = os.path.join(PROJECT_ROOT, "Test_kraft_connect", "Fix_File")


@tool(description="第一步：将HDFS日志发送到Kafka。需要在Kafka和ClickHouse正常运行后才能执行。")
def send_logs_to_kafka(
        host: str = "192.168.115.129:9092",
        topic: str = "hdfs-logs",
        log_file: str = None,
        max_lines: int = None
) -> str:
    """
    发送HDFS日志到Kafka。
    """
    script_path = os.path.join(SCRIPT_DIR, "kafka_producer.py")

    if not os.path.exists(script_path):
        return f"❌ 错误：找不到 kafka_producer.py 脚本，路径: {script_path}"

    if log_file is None:
        log_file = os.path.join(PROJECT_ROOT, "HDFS_v1", "HDFS.log")

    if not os.path.exists(log_file):
        return f"❌ 错误：找不到日志文件: {log_file}"

    try:
        cmd = [
            sys.executable,
            script_path,
            "--host", host,
            "--topic", topic,
            "--file", log_file
        ]

        if max_lines:
            cmd.extend(["--max", str(max_lines)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            return f"✅ 日志发送成功！\n{result.stdout}"
        else:
            return f"❌ 日志发送失败：\n{result.stderr}"

    except subprocess.TimeoutExpired:
        return "❌ 日志发送超时（超过5分钟）"
    except Exception as e:
        return f"❌ 执行失败: {str(e)}"