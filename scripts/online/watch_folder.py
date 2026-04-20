#!/usr/bin/env python3
"""
自动监控文件夹，读取日志文件发送到Kafka（限速版）
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

import yaml
import time
import glob
from kafka import KafkaProducer

config_dir = os.path.join(PROJECT_ROOT, 'config')
with open(os.path.join(config_dir, 'kafka.yml'), 'r') as f:
    kafka_config = yaml.safe_load(f)['kafka']

WATCH_DIR = os.path.join(PROJECT_ROOT, 'HDFS_Test')
PROCESSED_DIR = os.path.join(WATCH_DIR, 'processed')
os.makedirs(WATCH_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

SEND_RATE = 50  # 每秒发送的行数
SEND_INTERVAL = 1.0 / SEND_RATE  # 每次发送的间隔时间（秒）
MAX_LINES = 1000  # 测试时限制只发送1000行

producer = KafkaProducer(
    bootstrap_servers=kafka_config['bootstrap_servers'],
    value_serializer=lambda v: v.encode('utf-8'),
    acks=1
)

topic = kafka_config['topics'].get('online', 'hdfs-logs-online')

def send_file_to_kafka(file_path):
    batch_id = f"online_{int(time.time())}"
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    total_lines = min(len([l for l in lines if l.strip()]), MAX_LINES)
    count = 0
    start_time = time.time()
    
    for line in lines:
        if line.strip() and count < MAX_LINES:
            message = f"{batch_id}\t{line.strip()}"
            producer.send(topic, value=message)
            count += 1
        elif count >= MAX_LINES:
            break
            
            # 限速：每发送一行后等待
            time.sleep(SEND_INTERVAL)
            
            if count % 100 == 0:
                elapsed = time.time() - start_time
                print(f"  进度: {count}/{total_lines} 行 ({count/elapsed:.1f} 行/秒)")
    
    producer.flush()
    elapsed = time.time() - start_time
    print(f"[{time.strftime('%H:%M:%S')}] 发送 {count} 条日志 from {os.path.basename(file_path)} ({count/elapsed:.1f} 行/秒)")
    return count

def main():
    print(f"📁 监控文件夹: {WATCH_DIR}")
    print(f"   Topic: {topic}")
    print(f"   限速: {SEND_RATE} 行/秒")
    print(f"   处理完的文件移动到: {PROCESSED_DIR}")
    print("-" * 50)
    
    processed_files = set()
    
    while True:
        try:
            files = glob.glob(os.path.join(WATCH_DIR, "*.log"))
            files += glob.glob(os.path.join(WATCH_DIR, "*.txt"))
            
            for file_path in files:
                if file_path in processed_files:
                    continue
                
                print(f"发现新文件: {os.path.basename(file_path)}")
                count = send_file_to_kafka(file_path)
                
                # 移动到已处理目录
                filename = os.path.basename(file_path)
                processed_path = os.path.join(PROCESSED_DIR, f"{int(time.time())}_{filename}")
                os.rename(file_path, processed_path)
                processed_files.add(file_path)
                print(f"  → 已移动到: {processed_path}")
                
        except Exception as e:
            print(f"错误: {e}")
        
        time.sleep(2)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n停止监控")
        producer.close()