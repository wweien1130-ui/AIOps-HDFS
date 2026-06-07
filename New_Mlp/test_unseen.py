"""
用未参与训练的日志文件验证模型泛化能力。
用法: python test_unseen.py <日志文件路径>
示例: python test_unseen.py ../HDFS_Test/1776693395_HDFS11.log
"""

import csv
import re
import os
import sys
import joblib
import numpy as np
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
PATTERNS = [(eid, re.compile(p)) for eid, p in TEMPLATES]


def main():
    if len(sys.argv) < 2:
        print("用法: python test_unseen.py <日志文件路径>")
        return

    log_file = sys.argv[1]
    label_file = os.path.join(BASE_DIR, '..', 'HDFS_v1', 'preprocessed', 'anomaly_label.csv')

    # 加载标签
    labels = {}
    if os.path.exists(label_file):
        with open(label_file, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                labels[row['BlockId']] = row['Label']

    # 处理日志
    print(f"处理: {log_file}")
    block_events = defaultdict(lambda: defaultdict(int))
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for i, line in enumerate(f, 1):
            if i % 200000 == 0:
                print(f"  {i} 行...")
            for eid, pattern in PATTERNS:
                m = pattern.search(line)
                if m:
                    block_events[m.group(1)][eid.rstrip('b')] += 1
                    break

    # 构建特征矩阵
    event_cols = [f'E{i}' for i in range(1, 30)]
    X, y, block_ids = [], [], []
    for block_id, events in block_events.items():
        label = labels.get(block_id)
        if label is None:
            continue
        X.append([events.get(col, 0) for col in event_cols])
        y.append(0 if label == 'Normal' else 1)
        block_ids.append(block_id)

    X = np.array(X)
    y = np.array(y)
    print(f"有标签的 Block: {len(y)} (Normal={( y==0).sum()}, Anomaly={(y==1).sum()})")

    # 加载模型并预测
    model = joblib.load(os.path.join(BASE_DIR, 'block_anomaly_model.pkl'))
    scaler = joblib.load(os.path.join(BASE_DIR, 'scaler.pkl'))

    X_scaled = scaler.transform(X)
    y_proba = model.predict_proba(X_scaled)[:, 1]

    # 用最优阈值评估
    for t in [0.5, 0.6, 0.7]:
        preds = (y_proba > t).astype(int)
        tp = ((preds == 1) & (y == 1)).sum()
        fp = ((preds == 1) & (y == 0)).sum()
        fn = ((preds == 0) & (y == 1)).sum()
        tn = ((preds == 0) & (y == 0)).sum()
        p = tp / (tp + fp) if (tp + fp) > 0 else 0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        print(f"threshold={t:.1f}: P={p:.3f} R={r:.3f} F1={f1:.3f} TP={tp} FP={fp} FN={fn} TN={tn}")


if __name__ == '__main__':
    main()
