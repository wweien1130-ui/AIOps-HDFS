# kafka_consumer.py
import time
import argparse
from kafka import KafkaConsumer


class LogConsumer:
    def __init__(self, bootstrap_servers, topic='hdfs-logs', group_id='test-group'):
        self.topic = topic
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: m.decode('utf-8'),
            consumer_timeout_ms=10000,  # 改为30秒，等待消息
            max_poll_records=500
        )
        self.received_count = 0

    def consume(self, max_messages=None):
        """消费消息"""
        print(f"\n开始消费 {self.topic}...")
        print(f"Kafka: {self.consumer.config['bootstrap_servers']}")
        print(f"Group: {self.consumer.config['group_id']}")
        print("-" * 50)
        print("等待消息... (30秒超时)")
        print("-" * 50)

        start_time = time.time()

        try:
            for message in self.consumer:
                print(f"[{self.received_count + 1}] {message.value}")
                self.received_count += 1

                if max_messages and self.received_count >= max_messages:
                    break

                if self.received_count % 10 == 0:
                    elapsed = time.time() - start_time
                    print(f"   📊 已接收: {self.received_count} 条, 速率: {self.received_count/elapsed:.0f}/秒")

        except KeyboardInterrupt:
            print("\n\n⏹️ 手动停止")

        elapsed = time.time() - start_time
        print("-" * 50)
        print(f"✅ 完成! 接收 {self.received_count} 条")
        if elapsed > 0:
            print(f"   耗时: {elapsed:.2f} 秒")
            print(f"   速率: {self.received_count / elapsed:.0f} 条/秒")
        print("-" * 50)

    def close(self):
        self.consumer.close()


def main():
    parser = argparse.ArgumentParser(description='Kafka 消费者测试')
    parser.add_argument('--host', default='192.168.115.129:9092', help='Kafka地址')
    parser.add_argument('--topic', default='hdfs-logs', help='Topic')
    parser.add_argument('--group', default='test-group', help='消费者组')
    parser.add_argument('--count', type=int, default=None, help='接收数量')
    args = parser.parse_args()

    consumer = LogConsumer(args.host, args.topic, args.group)
    consumer.consume(max_messages=args.count)
    consumer.close()


if __name__ == "__main__":
    main()