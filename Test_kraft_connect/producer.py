# producer_fast.py
import time
import argparse
from kafka import KafkaProducer
from pathlib import Path


class FastProducer:
    def __init__(self, bootstrap_servers, topic='hdfs-logs'):
        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v.encode('utf-8'),
            # 关键优化配置
            acks=0,  # 不等待确认（最快）
            retries=0,
            batch_size=65536,  # 64KB 批次
            linger_ms=100,  # 等待100ms凑批
            buffer_memory=134217728,  # 128MB 缓冲
            compression_type='gzip',
            max_in_flight_requests_per_connection=10
        )
        self.total_sent = 0

    def stream_file(self, file_path, max_lines=None):
        print(f"\n{'=' * 60}")
        print(f"开始流式传输 (高速模式)")
        print(f"  Topic: {self.topic}")
        print(f"  Kafka: {self.producer.config['bootstrap_servers']}")
        print(f"  acks=0 (不等待确认)")
        print(f"{'=' * 60}\n")

        start_time = time.time()

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # 异步发送，不等待
                self.producer.send(self.topic, value=line)
                self.total_sent += 1

                if max_lines and self.total_sent >= max_lines:
                    break

                # 每1000条显示一次进度
                if self.total_sent % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = self.total_sent / elapsed if elapsed > 0 else 0
                    print(f"  📤 已发送: {self.total_sent:,} 条 | 速率: {rate:.0f} 条/秒")

        # 最后刷新缓冲区
        print("  等待消息发送完成...")
        self.producer.flush()

        elapsed = time.time() - start_time
        print(f"\n{'=' * 60}")
        print(f"✅ 传输完成!")
        print(f"   总发送: {self.total_sent:,} 条")
        print(f"   总耗时: {elapsed:.2f} 秒")
        print(f"   平均速率: {self.total_sent / elapsed:,.0f} 条/秒")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='192.168.115.129:9092')
    parser.add_argument('--file', default='../HDFS_v1/HDFS.log')
    parser.add_argument('--topic', default='hdfs-logs')
    parser.add_argument('--max', type=int, default=1000)
    args = parser.parse_args()

    producer = FastProducer(args.host, args.topic)
    producer.stream_file(args.file, args.max)


if __name__ == "__main__":
    main()