# producer_fixed.py
import time
import argparse
from kafka import KafkaProducer


class LogProducer:
    def __init__(self, bootstrap_servers, topic='hdfs-logs'):
        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v.encode('utf-8'),
            # 修复：使用 acks=1 确保消息送达
            acks=1,  # 等待 leader 确认
            retries=3,  # 失败重试
            # batch_size=32768,  # 增大批次
            # linger_ms=50,  # 等待50ms凑批
            batch_size=65536,  # 64KB 批次
            linger_ms=10,  # 等待10ms凑批
            buffer_memory=67108864,  # 64MB 缓冲

            compression_type='gzip',
            max_in_flight_requests_per_connection=5
        )
        self.total_sent = 0

    # def send_message(self, message):
    #     """发送单条消息（异步）"""
    #     self.producer.send(self.topic, value=message)
    #     self.total_sent += 1

    # 在 send_message 中每 10000 条 flush 一次
    def send_message(self, message):
        self.producer.send(self.topic, value=message)
        self.total_sent += 1
        if self.total_sent % 10000 == 0:
            self.producer.flush()  # 定期刷新，释放内存



    # def send_message(self, message):
    #     future = self.producer.send(self.topic, value=message)
    #     try:
    #         record_metadata = future.get(timeout=10)
    #         self.total_sent += 1
    #         if self.total_sent % 1000 == 0:
    #             print(f"已确认 {self.total_sent} 条，分区 {record_metadata.partition}, offset {record_metadata.offset}")
    #     except Exception as e:
    #         print(f"发送失败: {e}")
    #         raise


    def send_batch(self, messages):
        """批量发送"""
        for msg in messages:
            self.producer.send(self.topic, value=msg)
        self.producer.flush()
        self.total_sent += len(messages)

    def close(self):
        """关闭连接"""
        self.producer.flush()
        self.producer.close()


def main():
    parser = argparse.ArgumentParser(description='Kafka 生产者测试')
    parser.add_argument('--host', default='192.168.115.129:9092', help='Kafka地址')
    parser.add_argument('--topic', default='hdfs-logs', help='Topic')
    parser.add_argument('--count', type=int, default=100, help='发送数量')


    parser.add_argument('--file', default='../HDFS_v1/HDFS.log')
    parser.add_argument('--max', type=int, default=None)


    args = parser.parse_args()

    producer = LogProducer(args.host, args.topic)

    print(f"\n开始发送 {args.count} 条消息到 {args.topic}...")
    print(f"Kafka: {args.host}")
    print("-" * 50)

    start_time = time.time()

    # 发送测试消息
    # for i in range(args.count):
    #     message = f"Test message {i}: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    #     producer.send_message(message)

    # 新增：从文件读取日志
    print(f"\n开始流式发送 {args.file}...")

    with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            producer.send_message(line)

            if args.max and i >= args.max:
                break

            # if (i + 1) % 1000 == 0:
        # print(f"已发送: {i + 1} 条...")



        # if (i + 1) % 100 == 0:
        #     print(f"已发送: {i + 1} 条")

    producer.close()

    elapsed = time.time() - start_time
    print("-" * 50)
    print(f"✅ 完成! 发送 {producer.total_sent} 条")
    print(f"   耗时: {elapsed:.2f} 秒")
    print(f"   速率: {producer.total_sent / elapsed:.0f} 条/秒")


if __name__ == "__main__":
    main()