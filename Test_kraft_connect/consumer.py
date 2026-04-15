# consumer.py
import time
import re
import csv
import os
import argparse
from kafka import KafkaConsumer

# ========== 1. 加载模板 ==========
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

# ========== 2. 异常白名单 + 关键词兜底 ==========
ANOMALY_EVENTS = {
    'E1', 'E4', 'E7', 'E8', 'E10', 'E12', 'E13', 'E14', 'E17',
    'E20', 'E23', 'E24', 'E27', 'E28', 'E29'
}
FALLBACK_KEYWORDS = re.compile(
    r'ERROR|FATAL|CRITICAL|Exception|Failed|Corrupt|timeout|unavailable|invalid',
    re.IGNORECASE
)

# ========== 3. 提取 BlockId ==========
BLOCK_ID_PAT = re.compile(r'(blk[-_]?-?\d+)')
def extract_block_id(log_line):
    match = BLOCK_ID_PAT.search(log_line)
    return match.group(1) if match else 'unknown'

# ========== 4. 事件匹配器 ==========
class LogMatcher:
    def __init__(self, templates_csv_path):
        self.templates = load_templates(templates_csv_path)
        print(f"[PID {os.getpid()}] 已加载 {len(self.templates)} 个事件模板")

    def match(self, log_line):
        for eid, regex in self.templates:
            if regex.search(log_line):
                return eid, 'template'
        if FALLBACK_KEYWORDS.search(log_line):
            return 'E_UNKNOWN_ERR', 'keyword_fallback'
        return None, 'unknown'

# ========== 5. Kafka 消费者 ==========
class HdfsLogConsumer:
    def __init__(self, bootstrap_servers, topic='hdfs-logs', group_id='hdfs-agent',
                 templates_path='../HDFS_v1/preprocessed/HDFS.log_templates.csv',
                 unknown_log_dir='unknown_logs'):
        self.topic = topic
        self.matcher = LogMatcher(templates_path)
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: m.decode('utf-8', errors='ignore'),
            max_poll_records=2000,
            fetch_max_bytes=52428800,
        )
        # 每个进程独立的未知日志文件
        os.makedirs(unknown_log_dir, exist_ok=True)
        self.unknown_log_file = os.path.join(unknown_log_dir, f'unknown_patterns_{os.getpid()}.log')
        print(f"[PID {os.getpid()}] 未知日志将写入: {self.unknown_log_file}")

        self.stats = {'total': 0, 'template': 0, 'keyword_fallback': 0,
                      'anomaly': 0, 'normal': 0, 'unknown': 0}
        self.start_time = time.time()
        self.last_report = self.start_time

    def process_log(self, log_line):
        self.stats['total'] += 1
        event_id, match_type = self.matcher.match(log_line)

        if match_type == 'template':
            self.stats['template'] += 1
            if event_id in ANOMALY_EVENTS:
                self.stats['anomaly'] += 1
                block_id = extract_block_id(log_line)
                return {'type': 'anomaly', 'event_id': event_id, 'block_id': block_id}
            else:
                self.stats['normal'] += 1
                return {'type': 'normal', 'event_id': event_id}

        elif match_type == 'keyword_fallback':
            self.stats['keyword_fallback'] += 1
            self.stats['anomaly'] += 1
            block_id = extract_block_id(log_line)
            with open(self.unknown_log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
            return {'type': 'anomaly', 'event_id': 'E_UNKNOWN_ERR', 'block_id': block_id}

        else:  # unknown
            self.stats['unknown'] += 1
            with open(self.unknown_log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
            return {'type': 'unknown'}

    def start_consuming(self, max_messages=None):
        print(f"[PID {os.getpid()}] 开始消费 {self.topic} | Group: {self.consumer.config['group_id']}\n")
        try:
            for i, message in enumerate(self.consumer):
                result = self.process_log(message.value)
                if result.get('type') == 'anomaly':
                    print(f"🚨 异常 {result.get('event_id')} | Block: {result.get('block_id','N/A')}")

                now = time.time()
                if (now - self.last_report) >= 5.0 or (i+1) % 1000 == 0:
                    elapsed = now - self.start_time
                    rate = self.stats['total'] / elapsed if elapsed > 0 else 0
                    print(f"📊 [PID {os.getpid()}] 总计: {self.stats['total']:,} | "
                          f"异常: {self.stats['anomaly']:,} | 速率: {rate:.0f}/秒")
                    self.last_report = now

                if max_messages and (i+1) >= max_messages:
                    break
        except KeyboardInterrupt:
            print(f"\n[PID {os.getpid()}] 手动停止")
        finally:
            elapsed = time.time() - self.start_time
            print(f"\n[PID {os.getpid()}] ✅ 完成 | 总: {self.stats['total']:,} | "
                  f"异常: {self.stats['anomaly']:,} | 耗时: {elapsed:.1f}秒")
            self.consumer.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='192.168.115.129:9092')
    parser.add_argument('--topic', default='hdfs-logs')
    parser.add_argument('--group', default='hdfs-agent')
    parser.add_argument('--templates', default='../HDFS_v1/preprocessed/HDFS.log_templates.csv')
    parser.add_argument('--max', type=int, default=None)
    parser.add_argument('--unknown-dir', default='unknown_logs')
    args = parser.parse_args()

    consumer = HdfsLogConsumer(
        bootstrap_servers=args.host,
        topic=args.topic,
        group_id=args.group,
        templates_path=args.templates,
        unknown_log_dir=args.unknown_dir
    )
    consumer.start_consuming(max_messages=args.max)

if __name__ == "__main__":
    main()