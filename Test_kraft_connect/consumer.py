import time
import re
import csv
import argparse
from kafka import KafkaConsumer


# ============================================================
# 1. 加载事件模板并转换为正则
# ============================================================
def load_templates(csv_path):
    templates = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row['EventId']
            template = row['EventTemplate']
            pattern = re.escape(template).replace(r'\[\*\]', '(.*?)')
            templates.append((eid, re.compile(pattern)))
    return templates


# ============================================================
# 2. 异常事件白名单
# ============================================================
ANOMALY_EVENTS = {
    'E1', 'E4', 'E7', 'E8', 'E10', 'E12', 'E13', 'E14', 'E17',
    'E20', 'E23', 'E24', 'E27', 'E28', 'E29'
}

# ============================================================
# 3. 提取 BlockId
# ============================================================
BLOCK_ID_PAT = re.compile(r'(blk[-_]?-?\d+)')

def extract_block_id(log_line):
    match = BLOCK_ID_PAT.search(log_line)
    return match.group(1) if match else 'unknown'


# ============================================================
# 4. 事件匹配器
# ============================================================
class LogMatcher:
    def __init__(self, templates_csv_path):
        self.templates = load_templates(templates_csv_path)
        print(f"已加载 {len(self.templates)} 个事件模板")

    def match(self, log_line):
        for eid, regex in self.templates:
            if regex.search(log_line):
                return eid
        return None


# ============================================================
# 5. Kafka 消费者
# ============================================================
class HdfsLogConsumer:
    def __init__(self, bootstrap_servers, topic='hdfs-logs', group_id='hdfs-agent',
                 templates_path='../HDFS_v1/preprocessed/HDFS.log_templates.csv'):
        self.topic = topic
        self.matcher = LogMatcher(templates_path)

        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: m,
        )

        self.stats = {'total': 0, 'matched': 0, 'anomaly': 0, 'normal': 0}

    def process_log(self, log_line):
        self.stats['total'] += 1
        # 确保是字符串类型
        if isinstance(log_line, bytes):
            log_line = log_line.decode('utf-8', errors='ignore')

        event_id = self.matcher.match(log_line)

        if event_id:
            self.stats['matched'] += 1
            if event_id in ANOMALY_EVENTS:
                self.stats['anomaly'] += 1
                block_id = extract_block_id(log_line)
                return {'type': 'anomaly', 'event_id': event_id, 'block_id': block_id, 'raw': log_line}
            else:
                self.stats['normal'] += 1
                return {'type': 'normal', 'event_id': event_id}
        return {'type': 'unknown', 'raw': log_line}

    def start_consuming(self, max_messages=None):
        print(f"\n开始消费 HDFS 日志 | Topic: {self.topic} | Group: {self.consumer.config['group_id']}\n")

        start_time = time.time()
        try:
            for i, message in enumerate(self.consumer):
                result = self.process_log(message.value)

                if result['type'] == 'anomaly':
                    print(f"🚨 异常事件 {result['event_id']} | Block: {result['block_id']}")
                    print(f"   {result['raw'][:10000]}...")

                if (i + 1) % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = self.stats['total'] / elapsed
                    print(f"📊 总计: {self.stats['total']:,} | 异常: {self.stats['anomaly']:,} | 速率: {rate:.0f}/秒",
                          end='\r')

                if max_messages and i >= max_messages - 1:
                    break
        except KeyboardInterrupt:
            print("\n\n⏹️ 停止")

        elapsed = time.time() - start_time
        print(
            f"\n\n✅ 完成! 总: {self.stats['total']:,} | 匹配: {self.stats['matched']:,} | 异常: {self.stats['anomaly']:,} | 耗时: {elapsed:.1f}秒")


def main():
    parser = argparse.ArgumentParser(description='HDFS日志消费者')
    parser.add_argument('--host', default='192.168.115.129:9092')
    parser.add_argument('--topic', default='hdfs-logs')
    parser.add_argument('--group', default='hdfs-agent')
    parser.add_argument('--templates', default='../HDFS_v1/preprocessed/HDFS.log_templates.csv')
    parser.add_argument('--max', type=int, default=None)
    args = parser.parse_args()

    consumer = HdfsLogConsumer(args.host, args.topic, args.group, args.templates)
    consumer.start_consuming(max_messages=args.max)


if __name__ == "__main__":
    main()