#!/usr/bin/env python3
"""
微信 ClawBot 简化版 Python 示例
"""

import requests
import re


class WeChatHDFSBot:
    """微信 HDFS 监控机器人"""

    def __init__(self, api_base_url: str = "http://localhost:8000/api"):
        self.api_base_url = api_base_url
        self.session = requests.Session()

    def handle_message(self, message: str) -> str:
        """处理用户消息"""
        text = message.strip().lower()

        # 1. 查询健康度
        if "健康度" in text or "health" in text:
            return self.get_system_health()

        # 2. 查询过去X小时
        match = re.search(r"过去(\d+)小时", text)
        if match:
            hours = int(match.group(1))
            return self.get_anomalies_by_time(hours=hours)

        # 3. Top N 查询
        if "top" in text or "前10" in text:
            return self.get_top_anomalies()

        # 4. 异常分布
        if "分布" in text:
            return self.get_event_distribution()

        # 5. 帮助
        if "帮助" in text or "help" in text:
            return self.show_help()

        return self.show_help()

    def get_system_health(self) -> str:
        """获取系统健康度"""
        try:
            # 获取总 Block 数
            response = self.session.get(f"{self.api_base_url}/realtime/total", timeout=5)
            response.raise_for_status()
            data = response.json()
            total_blocks = data.get("total_blocks", 0)

            # 获取异常数量
            anomalies_response = self.session.get(
                f"{self.api_base_url}/anomalies/query?hours=1&limit=100",
                timeout=5
            )
            anomalies_response.raise_for_status()
            anomalies_data = anomalies_response.json()
            anomaly_count = anomalies_data.get("anomaly_count", 0)

            # 计算健康度
            health = ((1 - anomaly_count / total_blocks) * 100) if total_blocks > 0 else 0

            return f"系统健康度: {health:.1f}%\n总Block: {total_blocks}, 异常: {anomaly_count}"

        except Exception as e:
            return f"获取系统健康度失败: {str(e)}"

    def get_anomalies_by_time(self, hours: int = 1) -> str:
        """按时间范围查询异常"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/anomalies/query",
                params={"hours": hours, "limit": 10},
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            anomaly_count = data.get("anomaly_count", 0)
            anomalies = data.get("anomalies", [])

            result = f"过去{hours}小时异常: {anomaly_count}个\n"
            for i, item in enumerate(anomalies[:5], 1):
                result += f"{i}. {item.get('block_id', 'N/A')} - {item.get('anomaly_score', 0)*100:.1f}%\n"

            return result

        except Exception as e:
            return f"查询异常失败: {str(e)}"

    def get_top_anomalies(self) -> str:
        """获取 Top 10 异常"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/anomalies/query?hours=1&limit=10",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            anomalies = data.get("anomalies", [])
            if not anomalies:
                return "暂无异常数据"

            result = "Top 10 异常Block:\n"
            for i, item in enumerate(anomalies, 1):
                result += f"{i}. {item.get('block_id', 'N/A')} - {item.get('anomaly_score', 0)*100:.1f}%\n"

            return result

        except Exception as e:
            return f"获取Top异常失败: {str(e)}"

    def get_event_distribution(self) -> str:
        """获取异常类型分布"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/anomalies/query?hours=1",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            event_dist = data.get("event_distribution", {})
            if not event_dist:
                return "暂无异常类型数据"

            result = "异常类型分布:\n"
            for event_id, count in sorted(event_dist.items(), key=lambda x: x[1], reverse=True)[:8]:
                result += f"{event_id}: {count}次\n"

            return result

        except Exception as e:
            return f"获取异常分布失败: {str(e)}"

    def show_help(self) -> str:
        """显示帮助信息"""
        return """可用指令:
- 健康度: 查询系统健康状态
- 过去X小时: 查询指定时间范围异常
- Top 10: 查询Top 10异常Block
- 分布: 查询异常类型分布
- 帮助: 显示此帮助信息"""


if __name__ == "__main__":
    bot = WeChatHDFSBot()

    print("=== 微信 ClawBot 测试 ===\n")

    test_messages = [
        "查询健康度",
        "过去2小时",
        "Top 10",
        "异常分布",
        "帮助"
    ]

    for msg in test_messages:
        print(f"用户: {msg}")
        reply = bot.handle_message(msg)
        print(f"机器人: {reply}\n")
