#!/usr/bin/env python3
"""
模拟发送实时日志到Kafka
"""
import yaml
import os
import time

config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
with open(os.path.join(config_dir, 'kafka.yml'), 'r') as f:
    kafka_config = yaml.safe_load(f)['kafka']

from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=kafka_config['bootstrap_servers'],
    value_serializer=lambda v: v.encode('utf-8'),
    acks=1
)

topic = kafka_config['topics'].get('online', 'hdfs-logs-online')
batch_id = f"online_{int(time.time())}"

sample_logs = [
    "081109 203520 145 INFO dfs.DataNode$DataXceiver: Receiving block blk_123456 src: /10.250.19.102:34232 dest: /10.250.19.102:50010",
    "081109 203521 144 INFO dfs.DataNode$DataXceiver: Receiving block blk_123457 src: /10.250.71.16:51590 dest: /10.250.71.16:50010",
    "081109 203519 145 INFO dfs.FSNamesystem: BLOCK* NameSystem.addStoredBlock: blockMap updated: 10.250.10.6:50010 is added to blk_123458 size 91178",
    "081109 203519 147 INFO dfs.DataNode$PacketResponder: Received block blk_123458 of size 91178 from /10.250.14.224",
    "081109 203521 145 INFO dfs.DataNode$DataXceiver: Receiving block blk_123459 src: /10.250.19.102:39325 dest: /10.250.19.102:50010",
]

print(f"发送 {len(sample_logs)} 条日志到 topic: {topic}")

for log in sample_logs:
    message = f"{batch_id}\t{log}"
    producer.send(topic, value=message)
    print(f"  发送: {log[:50]}...")

producer.flush()
producer.close()

print(f"\n✅ 发送完成！批次ID: {batch_id}")
print(f"   Topic: {topic}")
print(f"   请查看ClickHouse: SELECT * FROM online.block_event_stats")