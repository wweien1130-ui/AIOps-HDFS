# consumer_fixed.py
import time
import argparse
import re
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from kafka import TopicPartition


class FixedLogStreamConsumer:
    def __init__(self, bootstrap_servers, topic='hdfs-logs', group_id='hdfs-agent'):
        self.topic = topic
        self.bootstrap_servers = bootstrap_servers

        print(f"正在连接 Kafka: {bootstrap_servers}")
        print(f"主题: {topic}")
        print(f"消费者组: {group_id}")

        # 方式1：使用 subscribe（推荐）
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: m.decode('utf-8'),
            consumer_timeout_ms=5000,  # 5秒超时
            max_poll_records=100,
            request_timeout_ms=30000,
            session_timeout_ms=10000,
            heartbeat_interval_ms=3000
        )

        # 验证连接 - 不调用 assign，只查看分区信息
        try:
            partitions = self.consumer.partitions_for_topic(topic)
            print(f"✅ 连接成功! 分区数: {len(partitions) if partitions else 0}")

            # 获取每个分区的偏移量信息（使用 consumer 的 end_offsets 方法）
            if partitions:
                # 创建 TopicPartition 对象列表
                topic_partitions = [TopicPartition(topic, p) for p in partitions]
                # 获取结束偏移量
                end_offsets = self.consumer.end_offsets(topic_partitions)
                # 获取开始偏移量
                beginning_offsets = self.consumer.beginning_offsets(topic_partitions)

                for partition in partitions:
                    tp = TopicPartition(topic, partition)
                    beginning = beginning_offsets[tp]
                    end = end_offsets[tp]
                    print(f"   分区 {partition}: 偏移量 {beginning} - {end} (共 {end - beginning} 条)")

        except Exception as e:
            print(f"⚠️ 获取分区信息失败: {e}")

        self.stats = {
            'total': 0,
            'critical': 0,
            'normal': 0,
        }

    def is_critical_log(self, log_str):
        log_upper = log_str.upper()

        CRITICAL_LEVELS = ['ERROR', 'FATAL', 'CRITICAL']
        WARNING_LEVELS = ['WARN', 'WARNING']
        CRITICAL_PATTERNS = [
            r'\bERROR\b', r'\bFATAL\b', r'\bCRITICAL\b', r'\bEXCEPTION\b',
            r'blk_\d+.*not found', r'block.*corrupt', r'failed\s+to',
            r'timeout', r'DataNode.*failed', r'NameNode.*error',
            r'Unsafe\s+mode', r'replica.*missing',
        ]

        if any(level in log_upper for level in CRITICAL_LEVELS):
            return True
        if any(level in log_upper for level in WARNING_LEVELS):
            return True
        for pattern in CRITICAL_PATTERNS:
            if re.search(pattern, log_str, re.IGNORECASE):
                return True
        return False

    def start_consuming(self, max_messages=None):
        print(f"\n{'=' * 60}")
        print(f"开始消费日志")
        print(f"  Topic: {self.topic}")
        print(f"  Kafka: {self.bootstrap_servers}")
        print(f"  Group: {self.consumer.config['group_id']}")
        print(f"{'=' * 60}\n")

        start_time = time.time()

        try:
            for i, message in enumerate(self.consumer):
                # 处理消息
                log_value = message.value
                self.stats['total'] += 1

                # 判断是否为关键日志
                is_critical = self.is_critical_log(log_value)
                if is_critical:
                    self.stats['critical'] += 1
                    print(f"\n🚨 [{i}] 异常日志: {log_value[:150]}...")
                else:
                    self.stats['normal'] += 1
                    if self.stats['total'] % 100 == 0:
                        print(f"📊 已处理: {self.stats['total']} 条 (异常: {self.stats['critical']})", end='\r')

                if max_messages and i >= max_messages - 1:
                    break

        except KeyboardInterrupt:
            print("\n\n⏹️ 手动停止消费")
        except Exception as e:
            print(f"\n❌ 消费错误: {e}")

        elapsed = time.time() - start_time
        print(f"\n\n{'=' * 60}")
        print(f"✅ 消费完成!")
        print(f"   总处理: {self.stats['total']:,} 条")
        print(f"   异常日志: {self.stats['critical']:,} 条")
        print(f"   正常日志: {self.stats['normal']:,} 条")
        print(f"   总耗时: {elapsed:.1f} 秒")
        if elapsed > 0:
            print(f"   平均速率: {self.stats['total'] / elapsed:.0f} 条/秒")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description='从Kafka消费HDFS日志')
    parser.add_argument('--host', default='192.168.115.129:9092', help='Kafka地址')
    parser.add_argument('--topic', default='hdfs-logs', help='Kafka Topic')
    parser.add_argument('--group', default='hdfs-agent', help='消费者组')
    parser.add_argument('--max', type=int, default=None, help='最大处理条数')
    args = parser.parse_args()

    consumer = FixedLogStreamConsumer(
        bootstrap_servers=args.host,
        topic=args.topic,
        group_id=args.group
    )
    consumer.start_consuming(max_messages=args.max)


if __name__ == "__main__":
    main()