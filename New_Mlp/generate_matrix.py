"""
从拆分的 HDFS 日志文件生成 Event_occurrence_matrix.csv。
用法: python generate_matrix.py <日志文件路径> [输出路径]
示例: python generate_matrix.py ../HDFS_Test/1776695197_HDFS1.log
"""

import csv
import re
import sys
import os
from collections import defaultdict

# ─── 模板定义 ───────────────────────────────────────────────────
# 从 HDFS.log_templates.csv 解析，[*] 作为通配符
# 每个模板关联一个提取 block_id 的正则
TEMPLATES = [
    ("E1",  r'Adding an already existing block (blk_-?\d+)'),
    ("E2",  r'Verification succeeded for (blk_-?\d+)'),
    ("E3",  r'Served block (blk_-?\d+) to'),
    ("E4",  r'Got exception while serving (blk_-?\d+) to'),
    ("E5",  r'Receiving block (blk_-?\d+) src:'),
    ("E6",  r'Received block (blk_-?\d+) src:.*dest:.*of size'),
    ("E7",  r'writeBlock (blk_-?\d+) received exception'),
    ("E7b", r'writeBlock.* received exception.* (blk_-?\d+)'),  # block_id 可能在后面
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

# 编译正则
PATTERNS = [(eid, re.compile(pattern)) for eid, pattern in TEMPLATES]


def match_line(line):
    """匹配一行日志，返回 (event_id, block_id) 或 None。"""
    for eid, pattern in PATTERNS:
        m = pattern.search(line)
        if m:
            block_id = m.group(1)
            real_eid = eid.rstrip('b')  # E7b -> E7
            return real_eid, block_id
    return None


def process_log_file(filepath):
    """处理日志文件，返回 {block_id: {E1: count, E2: count, ...}}。"""
    block_events = defaultdict(lambda: defaultdict(int))
    total_lines = 0
    matched_lines = 0

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            total_lines += 1
            if total_lines % 100000 == 0:
                print(f"  已处理 {total_lines} 行 (匹配 {matched_lines})...", flush=True)
            result = match_line(line)
            if result:
                eid, block_id = result
                block_events[block_id][eid] += 1
                matched_lines += 1

    print(f"  完成: 共 {total_lines} 行, 匹配 {matched_lines} 行, 去重 Block {len(block_events)} 个")
    return block_events


def load_labels(label_file):
    """加载 anomaly_label.csv，返回 {block_id: 'Normal'/'Anomaly'}。"""
    labels = {}
    with open(label_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            labels[row['BlockId']] = row['Label']
    return labels


def write_matrix(block_events, labels, output_file):
    """写入 Event_occurrence_matrix.csv。"""
    event_cols = [f'E{i}' for i in range(1, 30)]

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['BlockId', 'Label'] + event_cols)

        for block_id, events in sorted(block_events.items()):
            label = labels.get(block_id, 'Unknown')
            row = [block_id, label]
            for col in event_cols:
                row.append(events.get(col, 0))
            writer.writerow(row)


def main():
    if len(sys.argv) < 2:
        print("用法: python generate_matrix.py <日志文件路径> [输出目录]")
        print("示例: python generate_matrix.py ../HDFS_Test/1776695197_HDFS1.log")
        sys.exit(1)

    log_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))

    # 路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    label_file = os.path.join(base_dir, '..', 'HDFS_v1', 'preprocessed', 'anomaly_label.csv')
    output_file = os.path.join(output_dir, 'Event_occurrence_matrix.csv')

    print(f"日志文件: {log_file}")
    print(f"标签文件: {label_file}")
    print(f"输出文件: {output_file}")
    print()

    # 1. 加载标签
    print("[1/3] 加载标签文件...")
    if os.path.exists(label_file):
        labels = load_labels(label_file)
        print(f"  加载了 {len(labels)} 个 Block 标签")
    else:
        print(f"  [警告] 标签文件不存在: {label_file}")
        print(f"  将生成无标签的矩阵（Label 列为空）")
        labels = {}

    # 2. 处理日志
    print(f"\n[2/3] 处理日志文件...")
    block_events = process_log_file(log_file)

    # 3. 写入矩阵
    print(f"\n[3/3] 写入矩阵...")
    write_matrix(block_events, labels, output_file)
    total_blocks = len(block_events)
    labeled = sum(1 for b in block_events if b in labels)
    print(f"  完成: {total_blocks} 个 Block, 其中 {labeled} 个有标签")
    print(f"  输出: {output_file}")


if __name__ == '__main__':
    main()
