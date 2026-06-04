#!/usr/bin/env python3
"""
微信 ClawBot Python 示例代码
基于 OpenClaw 微信插件

功能：通过微信查询 HDFS 系统监控数据
"""

import requests
import re
from typing import Dict, Any, Optional


class WeChatHDFSBot:
    """微信 HDFS 监控机器人"""

    def __init__(self, api_base_url: str = "http://localhost:8000/api"):
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

        # 指令映射表
        self.command_map = {
            # 健康度查询
            '健康度': {'tool': 'get_system_health', 'params': {}},
            '查询健康度': {'tool': 'get_system_health', 'params': {}},
            '系统状态': {'tool': 'get_system_health', 'params': {}},
            'health': {'tool': 'get_system_health', 'params': {}},

            # 时间范围查询
            '过去2小时': {'tool': 'get_recent_anomalies', 'params': {'hours': 2}},
            '查询过去2小时': {'tool': 'get_recent_anomalies', 'params': {'hours': 2}},
            '过去30分钟': {'tool': 'get_recent_anomalies', 'params': {'minutes': 30}},
            '查询过去30分钟': {'tool': 'get_recent_anomalies', 'params': {'minutes': 30}},
            '过去1小时': {'tool': 'get_recent_anomalies', 'params': {'hours': 1}},

            # Top N 查询
            'Top 10': {'tool': 'get_top_anomalies', 'params': {'limit': 10}},
            '异常列表': {'tool': 'get_top_anomalies', 'params': {'limit': 10}},
            'top10': {'tool': 'get_top_anomalies', 'params': {'limit': 10}},

            # 分布查询
            '异常分布': {'tool': 'get_event_distribution', 'params': {}},
            '分布': {'tool': 'get_event_distribution', 'params': {}},

            # 导出数据
            '导出数据': {'tool': 'export_anomalies', 'params': {}},
            '导出': {'tool': 'export_anomalies', 'params': {}},

            # 帮助
            '帮助': {'tool': None, 'action': 'show_help'},
            'help': {'tool': None, 'action': 'show_help'},
            '?': {'tool': None, 'action': 'show_help'}
        }

    def parse_user_input(self, message: str) -> Dict[str, Any]:
        """解析用户输入的自然语言"""
        text = message.strip().lower()

        # 1. 检查简单指令匹配
        for keyword, command in self.command_map.items():
            if keyword.lower() in text:
                return command

        # 2. 解析时间范围（如 "查询过去2小时"）
        time_match = re.search(r'过去(\d+)(小时|分钟|秒|天)', text)
        if time_match:
            value = int(time_match.group(1))
            unit = time_match.group(2)

            params = {}
            if unit == '小时':
                params['hours'] = value
            elif unit == '分钟':
                params['minutes'] = value
            elif unit == '秒':
                params['seconds'] = value
            elif unit == '天':
                params['days'] = value

            return {
                'tool': 'get_recent_anomalies',
                'params': params
            }

        # 3. 解析 Top N（如 "查询Top 5异常"）
        top_match = re.search(r'(top|前)(\d+)', text, re.IGNORECASE)
        if top_match:
            limit = int(top_match.group(2))
            return {
                'tool': 'get_top_anomalies',
                'params': {'limit': limit}
            }

        # 默认返回帮助
        return {'tool': None, 'action': 'show_help'}

    def get_system_health(self) -> Dict[str, Any]:
        """获取系统健康度"""
        try:
            response = self.session.get(f"{self.api_base_url}/realtime/total")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取系统健康度失败: {e}")
            raise

    def get_recent_anomalies(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """查询最近异常数据"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/anomalies/query",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"查询异常数据失败: {e}")
            raise

    def get_top_anomalies(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取 Top N 异常"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/anomalies/query",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取Top异常失败: {e}")
            raise

    def get_event_distribution(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取异常类型分布"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/anomalies/query",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"获取异常分布失败: {e}")
            raise

    def export_anomalies(self) -> Dict[str, Any]:
        """导出异常数据"""
        try:
            response = self.session.get(f"{self.api_base_url}/export")
            response.raise_for_status()
            return {"message": "异常数据已导出"}
        except Exception as e:
            print(f"导出数据失败: {e}")
            raise

    def format_health_reply(self, data: Dict[str, Any]) -> str:
        """格式化系统健康度回复"""
        total_blocks = data.get('total_blocks', 0)
        anomaly_count = data.get('anomaly_count', 0)
        health_percent = ((1 - (anomaly_count / total_blocks)) * 100) if total_blocks > 0 else 100
        health_percent = round(health_percent, 1)

        if health_percent < 80:
            status = '❌ 需关注'
        elif health_percent < 95:
            status = '⚠️ 良好'
        else:
            status = '✅ 优秀'

        return f"""📊 系统健康度: {health_percent}%
• 总Block数: {total_blocks}
• 异常数量: {anomaly_count}
• 健康状态: {status}"""

    def format_anomalies_reply(self, data: Dict[str, Any]) -> str:
        """格式化异常列表回复"""
        anomalies = data.get('anomalies', [])
        if not anomalies:
            return '暂无异常数据'

        reply = f"📋 Top {len(anomalies)} 异常Block:\n\n"
        for index, item in enumerate(anomalies, 1):
            events = item.get('events', [])
            event_str = ', '.join([f"{e['event_id']}:{e['count']}" for e in events[:3]])
            reply += f"{index}. {item['block_id']}\n"
            reply += f"   异常分数: {item.get('probability', 0) * 100:.1f}%\n"
            if event_str:
                reply += f"   主要事件: {event_str}\n"
            reply += '\n'

        return reply

    def format_distribution_reply(self, data: Dict[str, Any]) -> str:
        """格式化异常分布回复"""
        event_dist = data.get('event_distribution', {})
        events = sorted(event_dist.items(), key=lambda x: x[1], reverse=True)[:8]

        if not events:
            return '暂无异常类型数据'

        reply = "📊 异常类型分布:\n\n"
        for event_id, count in events:
            reply += f"{event_id}: {count} 次\n"

        return reply

    def show_help(self) -> str:
        """显示帮助信息"""
        return """🤖 HDFS系统监控助手

可用指令:
• 健康度 / 查询健康度 - 查询系统健康状态
• 过去X小时 / 过去X分钟 - 查询指定时间范围异常
• Top N / 异常列表 - 查询Top N异常Block
• 异常分布 - 查询异常类型分布
• 导出数据 - 导出异常数据为CSV
• 帮助 - 显示此帮助信息

示例:
• "查询健康度"
• "过去2小时"
• "Top 10"
• "异常分布"

    def handle_message(self, message: str) -> str:
        """处理用户消息"""
        try:
            # 解析用户意图
            command = self.parse_user_input(message)

            # 处理帮助指令
            if command.get('action') == 'show_help':
                return self.show_help()

            # 调用对应工具
            tool = command.get('tool')
            params = command.get('params', {})

            if tool == 'get_system_health':
                data = self.get_system_health()
                # 需要同时获取异常数量
                anomalies_data = self.get_recent_anomalies({'hours': 1, 'limit': 10})
                data['anomaly_count'] = anomalies_data.get('anomaly_count', 0)
                return self.format_health_reply(data)

            elif tool == 'get_recent_anomalies':
                data = self.get_recent_anomalies(params)
                return self.format_anomalies_reply(data)

            elif tool == 'get_top_anomalies':
                data = self.get_top_anomalies(params)
                return self.format_anomalies_reply(data)

            elif tool == 'get_event_distribution':
                data = self.get_event_distribution(params)
                return self.format_distribution_reply(data)

            elif tool == 'export_anomalies':
                self.export_anomalies()
                return '异常数据已导出，可下载CSV文件'

            else:
                return self.show_help()

        except Exception as e:
            print(f"处理消息失败: {e}")
            return '抱歉，暂时无法获取数据，请稍后重试'

    def wechat_bot_handler(self, wechat_message: Dict[str, Any]) -> str:
        """微信 ClawBot 消息处理入口"""
        user_message = wechat_message.get('content', '')
        print(f"收到微信消息: {user_message}")

        reply = self.handle_message(user_message)
        print(f"回复消息: {reply}")

        return reply


# 创建机器人实例
bot = WeChatHDFSBot()


def wechat_message_handler(wechat_message: Dict[str, Any]) -> str:
    """
    微信消息处理函数
    供 OpenClaw 微信插件调用

    Args:
        wechat_message: 微信消息对象，包含 content 字段

    Returns:
        回复内容
    """
    return bot.wechat_bot_handler(wechat_message)


if __name__ == "__main__":
    print("=== 微信 ClawBot Python 版测试 ===\n")

    test_messages = [
        '查询健康度',
        '过去2小时',
        'Top 10',
        '异常分布',
        '帮助'
    ]

    for msg in test_messages:
        print(f"用户: {msg}")
        reply = bot.handle_message(msg)
        print(f"机器人: {reply}\n")
