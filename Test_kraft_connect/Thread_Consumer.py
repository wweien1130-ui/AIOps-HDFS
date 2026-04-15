import time
import re
import csv
import argparse
from kafka import KafkaConsumer
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
import threading

# ============================================================
# 1. 加载事件模板并转换为正则（保持不变）
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
# 2. 异常事件白名单（保持不变）
# ============================================================
ANOMALY_EVENTS = {
    'E1', 'E4', 'E7', 'E8', 'E10', 'E12', 'E13', 'E14', 'E17',
    'E20', 'E23', 'E24', 'E27', 'E28', 'E29'
}

# ============================================================
# 3. 提取 BlockId（保持不变）
# ============================================================
BLOCK_ID_PAT = re.compile(r'(blk[-_]?-?\d+)')
def extract_block_id(log_line):
    match = BLOCK_ID_PAT.search(log_line)
    return match.group(1) if match else 'unknown'

# ============================================================
# 4. 事件匹配器（保持不变，但可稍后优化合并正则）
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
# 5. 多线程消费者
# ============================================================
class HdfsLogConsumer:
    def __init__(self, bootstrap_servers, topic='hdfs-logs', group_id='hdfs-agent',
                 templates_path='../HDFS_v1/preprocessed/HDFS.log_templates.csv',
                 max_workers=8, batch_size=1000):
        self.topic = topic
        self.matcher = LogMatcher(templates_path)
        self.max_workers = max_workers
        self.batch_size = batch_size

        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=False,          # 改为手动提交，确保线程安全
            max_poll_records=batch_size,       # 一次拉取多条
            value_deserializer=lambda m: m.decode('utf-8', errors='ignore')
        )

        self.stats = {'total': 0, 'matched': 0, 'anomaly': 0, 'normal': 0}
        self.stats_lock = threading.Lock()     # 统计变量需要加锁
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def process_one_log(self, log_line):
        """线程池执行的单个日志处理函数"""
        event_id = self.matcher.match(log_line)
        if event_id:
            if event_id in ANOMALY_EVENTS:
                block_id = extract_block_id(log_line)
                return ('anomaly', event_id, block_id, log_line)
            else:
                return ('normal', event_id, None, None)
        return ('unknown', None, None, log_line)

    def start_consuming(self, max_messages=None):
        print(f"\n开始消费 HDFS 日志 | Topic: {self.topic} | Group: {self.consumer.config['group_id']}")
        print(f"线程数: {self.max_workers} | 批量拉取: {self.batch_size}\n")

        start_time = time.time()
        total_processed = 0

        try:
            while True:
                # 拉取一批消息
                msg_pack = self.consumer.poll(timeout_ms=1000, max_records=self.batch_size)
                if not msg_pack:
                    if max_messages and total_processed >= max_messages:
                        break
                    continue

                # 收集这一批的所有日志行
                logs_batch = []
                for tp, messages in msg_pack.items():
                    for msg in messages:
                        logs_batch.append(msg.value)
                        if max_messages and len(logs_batch) + total_processed >= max_messages:
                            break
                    if max_messages and len(logs_batch) + total_processed >= max_messages:
                        break

                if not logs_batch:
                    continue

                # 提交所有任务到线程池
                futures = [self.executor.submit(self.process_one_log, line) for line in logs_batch]

                # 收集结果并更新统计
                for future in as_completed(futures):
                    result = future.result()
                    with self.stats_lock:
                        self.stats['total'] += 1
                        if result[0] == 'anomaly':
                            self.stats['anomaly'] += 1
                            self.stats['matched'] += 1
                            # 打印异常（可选）
                            print(f"🚨 异常事件 {result[1]} | Block: {result[2]}")
                            print(f"   {result[3][:200]}...")
                        elif result[0] == 'normal':
                            self.stats['normal'] += 1
                            self.stats['matched'] += 1
                        else:
                            pass  # unknown

                # 手动提交 offset（同步，确保已处理完这批）
                self.consumer.commit()

                total_processed += len(logs_batch)
                elapsed = time.time() - start_time
                rate = self.stats['total'] / elapsed if elapsed > 0 else 0
                print(f"📊 总计: {self.stats['total']:,} | 异常: {self.stats['anomaly']:,} | 速率: {rate:.0f}/秒", end='\r')

                if max_messages and total_processed >= max_messages:
                    break

        except KeyboardInterrupt:
            print("\n\n⏹️ 停止")
        finally:
            self.executor.shutdown(wait=True)
            self.consumer.close()

        elapsed = time.time() - start_time
        print(f"\n\n✅ 完成! 总: {self.stats['total']:,} | 匹配: {self.stats['matched']:,} | 异常: {self.stats['anomaly']:,} | 耗时: {elapsed:.1f}秒")


def main():
    parser = argparse.ArgumentParser(description='HDFS日志消费者（多线程版）')
    parser.add_argument('--host', default='192.168.115.129:9092')
    parser.add_argument('--topic', default='hdfs-logs')
    parser.add_argument('--group', default='hdfs-agent')
    parser.add_argument('--templates', default='../HDFS_v1/preprocessed/HDFS.log_templates.csv')
    parser.add_argument('--max', type=int, default=None)
    parser.add_argument('--workers', type=int, default=8, help='线程数')
    parser.add_argument('--batch', type=int, default=1000, help='每批拉取条数')
    args = parser.parse_args()

    consumer = HdfsLogConsumer(args.host, args.topic, args.group,
                               args.templates, args.workers, args.batch)
    consumer.start_consuming(max_messages=args.max)


if __name__ == "__main__":
    main()