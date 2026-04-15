import time
import argparse
import csv
import re
from kafka import KafkaProducer

# ========== 1. 事件匹配器（从消费者复制） ==========
class LogMatcher:
    def __init__(self, templates_csv_path):
        self.templates = self._load_templates(templates_csv_path)
        print(f"[Producer] 已加载 {len(self.templates)} 个事件模板")

    def _load_templates(self, csv_path):
        templates = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = row['EventId']
                template = row['EventTemplate']
                pattern = re.escape(template).replace(r'\[\*\]', '(.*?)')
                templates.append((eid, re.compile(pattern)))
        return templates

    def match(self, log_line):
        for eid, regex in self.templates:
            if regex.search(log_line):
                return eid
        return None

# ========== 2. Kafka 生产者 ==========
class LogProducer:
    def __init__(self, bootstrap_servers, topic='hdfs-logs', templates_path='../../HDFS_v1/preprocessed/HDFS.log_templates.csv'):
        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v.encode('utf-8'),
            acks=1,
            retries=3,
            batch_size=65536,
            linger_ms=10,
            buffer_memory=67108864,
            compression_type='gzip',
            max_in_flight_requests_per_connection=5
        )
        self.matcher = LogMatcher(templates_path)
        self.filtered_out = 0
        self.total_sent = 0

    def send_message(self, message):
        # 筛选：只发送匹配已知事件模板的日志
        if self.matcher.match(message) is None:
            self.filtered_out += 1
            return
        self.producer.send(self.topic, value=message)
        self.total_sent += 1
        if self.total_sent % 10000 == 0:
            self.producer.flush()

    def send_batch(self, messages):
        for msg in messages:
            if self.matcher.match(msg) is not None:
                self.producer.send(self.topic, value=msg)
                self.total_sent += 1
        self.producer.flush()

    def close(self):
        self.producer.flush()
        self.producer.close()

def main():
    parser = argparse.ArgumentParser(description='Kafka 生产者测试')
    parser.add_argument('--host', default='192.168.115.129:9092')
    parser.add_argument('--topic', default='hdfs-logs')
    parser.add_argument('--file', default='../HDFS_v1/HDFS.log')
    parser.add_argument('--max', type=int, default=None)
    parser.add_argument('--templates', default='../../HDFS_v1/preprocessed/HDFS.log_templates.csv',
                        help='事件模板CSV文件路径')
    args = parser.parse_args()

    producer = LogProducer(args.host, args.topic, args.templates)

    print(f"\n开始流式发送 {args.file}...")
    start_time = time.time()

    with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            producer.send_message(line)
            if args.max and i >= args.max:
                break
            if (i + 1) % 1000 == 0:
                print(f"已发送: {i + 1} 条...")

    producer.close()
    elapsed = time.time() - start_time
    print("-" * 50)
    print(f"✅ 完成! 发送 {producer.total_sent} 条")
    print(f"   筛选丢弃: {producer.filtered_out} 条（不匹配任何事件）")
    print(f"   耗时: {elapsed:.2f} 秒")
    print(f"   速率: {producer.total_sent / elapsed:.0f} 条/秒")

if __name__ == "__main__":
    main()