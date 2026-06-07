"""
从多个拆分日志文件合并生成 Event_occurrence_matrix.csv。
用法: python generate_multi_matrix.py
"""

import csv
import re
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 模板正则（来自 HDFS.log_templates.csv）
TEMPLATES = [
    ("E1",  r'Adding an already existing block (blk_-?\d+)'),
    ("E2",  r'Verification succeeded for (blk_-?\d+)'),
    ("E3",  r'Served block (blk_-?\d+) to'),
    ("E4",  r'Got exception while serving (blk_-?\d+) to'),
    ("E5",  r'Receiving block (blk_-?\d+) src:'),
    ("E6",  r'Received block (blk_-?\d+) src:.*dest:.*of size'),
    ("E7",  r'writeBlock (blk_-?\d+) received exception'),
    ("E7b", r'writeBlock.* received exception.* (blk_-?\d+)'),
    ("E8",  r'PacketResponder.* for block (blk_-?\d+) Interrupted'),
    ("E9",  r'Received block (blk_-?\d+) of size.* from'),
    ("E10", r'PacketResponder.* (blk_-?\d+) Exception'),
    ("E11", r'PacketResponder.* for block (blk_-?\d+) terminating'),
    ("E12", r':Exception writing block (blk_-?\d+) to mirror'),
    ("E13", r'Receiving empty packet for block (blk_-?\d+)'),
    ("E14", r'Exception in receiveBlock for block (blk_-?\d+)'),
    ("E15", r'Changing block file offset of block (blk_-?\d+)'),
    ("E16", r':Transmitted block (blk_-?\d+) to'),
    ("E17", r':Failed to transfer (blk_-?\d+) to'),
    ("E18", r'Starting thread to transfer block (blk_-?\d+) to'),
    ("E19", r'Reopen Block (blk_-?\d+)'),
    ("E20", r'Unexpected error trying to delete block (blk_-?\d+)'),
    ("E21", r'Deleting block (blk_-?\d+) file'),
    ("E22", r'BLOCK\* NameSystem.*allocateBlock:.* (blk_-?\d+)'),
    ("E23", r'BLOCK\* NameSystem.*delete: (blk_-?\d+) is added to invalidSet'),
    ("E24", r'BLOCK\* Removing block (blk_-?\d+) from neededReplications'),
    ("E25", r'BLOCK\* ask.* to replicate (blk_-?\d+) to'),
    ("E26", r'BLOCK\* NameSystem.*addStoredBlock: blockMap updated:.* is added to (blk_-?\d+)'),
    ("E27", r'BLOCK\* NameSystem.*addStoredBlock: Redundant addStoredBlock request received for (blk_-?\d+)'),
    ("E28", r'BLOCK\* NameSystem.*addStoredBlock: addStoredBlock request received for (blk_-?\d+)'),
    ("E29", r'PendingReplicationMonitor timed out block (blk_-?\d+)'),
]
PATTERNS = [(eid, re.compile(pattern)) for eid, pattern in TEMPLATES]


def process_log_file(filepath):
    block_events = defaultdict(lambda: defaultdict(int))
    total, matched = 0, 0
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total += 1
            if total % 200000 == 0:
                print(f"    {os.path.basename(filepath)}: {total} 行 (匹配 {matched})")
            for eid, pattern in PATTERNS:
                m = pattern.search(line)
                if m:
                    block_events[m.group(1)][eid.rstrip('b')] += 1
                    matched += 1
                    break
    print(f"    {os.path.basename(filepath)}: 完成 {total} 行, 匹配 {matched}, Block {len(block_events)}")
    return block_events


def main():
    train_dir = os.path.join(BASE_DIR, 'HDFS_log_Train')
    log_files = sorted([
        os.path.join(train_dir, f)
        for f in os.listdir(train_dir)
        if f.endswith('.log')
    ])
    if not log_files:
        print(f"[错误] HDFS_log_Train 目录下没有 .log 文件: {train_dir}")
        return
    print(f"扫描到 {len(log_files)} 个日志文件")

    label_file = os.path.join(BASE_DIR, '..', 'HDFS_v1', 'preprocessed', 'anomaly_label.csv')
    output_file = os.path.join(BASE_DIR, 'Event_occurrence_matrix.csv')

    # 1. 加载标签
    print("[1/3] 加载标签...")
    labels = {}
    if os.path.exists(label_file):
        with open(label_file, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                labels[row['BlockId']] = row['Label']
        print(f"  加载 {len(labels)} 个标签")

    # 2. 处理所有日志文件
    print(f"\n[2/3] 处理 {len(log_files)} 个日志文件...")
    merged = defaultdict(lambda: defaultdict(int))
    for f in log_files:
        print(f"  处理: {os.path.basename(f)}")
        block_events = process_log_file(f)
        for block_id, events in block_events.items():
            for eid, cnt in events.items():
                merged[block_id][eid] += cnt

    # 3. 写入矩阵
    print(f"\n[3/3] 写入矩阵...")
    event_cols = [f'E{i}' for i in range(1, 30)]
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['BlockId', 'Label'] + event_cols)
        for block_id, events in sorted(merged.items()):
            label = labels.get(block_id, 'Unknown')
            row = [block_id, label] + [events.get(col, 0) for col in event_cols]
            writer.writerow(row)

    # 统计
    total_blocks = len(merged)
    normal = sum(1 for b in merged if labels.get(b) == 'Normal')
    anomaly = sum(1 for b in merged if labels.get(b) == 'Anomaly')
    print(f"\n完成: {total_blocks} 个 Block (Normal={normal}, Anomaly={anomaly})")
    print(f"输出: {output_file}")


if __name__ == '__main__':
    main()
