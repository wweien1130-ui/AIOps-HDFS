#!/usr/bin/env python3
"""
实时异常预测服务
从 ClickHouse online.block_event_stats 增量读取 block 特征，
调用 MLP 模型预测异常概率，将结果写入 online.anomaly_blocks，
并更新 Redis 中的 Top N 异常缓存。
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'agent', 'tools'))

import time
import logging
import argparse
from datetime import datetime, timedelta

import yaml
import redis
import clickhouse_connect
import pandas as pd
import joblib

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
config_dir = os.path.join(project_root, 'config')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('realtime_predictor')


def load_config():
    config = {}

    ch_path = os.path.join(config_dir, 'clickhouse.yaml')
    if os.path.exists(ch_path):
        with open(ch_path, 'r', encoding='utf-8') as f:
            ch = yaml.safe_load(f)['clickhouse']['online']
            config['clickhouse'] = {
                'host': ch['host'],
                'port': ch.get('http_port', 8123),  # 使用HTTP端口
                'username': ch.get('username', 'default'),
                'password': ch.get('password', ''),
                'db': ch.get('database', 'online')
            }

    redis_path = os.path.join(config_dir, 'redis.yaml')
    if os.path.exists(redis_path):
        with open(redis_path, 'r', encoding='utf-8') as f:
            r = yaml.safe_load(f)['redis']
            config['redis'] = {
                'host': r['host'],
                'port': r['port'],
                'db': r.get('db', 0),
                'password': r.get('password')
            }

    model_base = os.path.join(project_root, 'BackUp', 'Preprocess_File')
    config['model_path'] = os.path.join(model_base, 'block_anomaly_model.pkl')
    config['scaler_path'] = os.path.join(model_base, 'scaler.pkl')

    config['predict_interval'] =  5
    config['anomaly_threshold'] = 0.5
    config['top_n'] = 10

    return config


class RealtimePredictor:
    def __init__(self, config):
        self.config = config
        self.ch_client = None
        self.redis_client = None
        self.model = None
        self.scaler = None

    def connect_clickhouse(self):
        self.ch_client = clickhouse_connect.get_client(
            host=self.config['clickhouse']['host'],
            port=self.config['clickhouse'].get('http_port', 8123),
            username=self.config['clickhouse'].get('username', 'default'),
            password=self.config['clickhouse'].get('password', '')
        )
        logger.info(
            f"ClickHouse 连接成功: {self.config['clickhouse']['host']}:{self.config['clickhouse'].get('http_port', 8123)}")

    def connect_redis(self):
        try:
            self.redis_client = redis.Redis(
                host=self.config['redis']['host'],
                port=self.config['redis']['port'],
                db=self.config['redis'].get('db', 0),
                password=self.config['redis'].get('password'),
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            self.redis_client = None

    def load_model(self):
        self.model = joblib.load(self.config['model_path'])
        self.scaler = joblib.load(self.config['scaler_path'])
        logger.info("模型和标准化器加载完成")

    def get_last_predict_time(self):
        state_file = os.path.join(script_dir, '.last_predict_time')
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                return f.read().strip()
        return (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

    def save_last_predict_time(self, ts):
        state_file = os.path.join(script_dir, '.last_predict_time')
        with open(state_file, 'w') as f:
            f.write(str(ts))

    def fetch_incremental_blocks(self, last_ts):
        query = f"""
        SELECT 
            block_id,
            sumIf(cnt, event_id='E1') AS E1,
            sumIf(cnt, event_id='E2') AS E2,
            sumIf(cnt, event_id='E3') AS E3,
            sumIf(cnt, event_id='E4') AS E4,
            sumIf(cnt, event_id='E5') AS E5,
            sumIf(cnt, event_id='E6') AS E6,
            sumIf(cnt, event_id='E7') AS E7,
            sumIf(cnt, event_id='E8') AS E8,
            sumIf(cnt, event_id='E9') AS E9,
            sumIf(cnt, event_id='E10') AS E10,
            sumIf(cnt, event_id='E11') AS E11,
            sumIf(cnt, event_id='E12') AS E12,
            sumIf(cnt, event_id='E13') AS E13,
            sumIf(cnt, event_id='E14') AS E14,
            sumIf(cnt, event_id='E15') AS E15,
            sumIf(cnt, event_id='E16') AS E16,
            sumIf(cnt, event_id='E17') AS E17,
            sumIf(cnt, event_id='E18') AS E18,
            sumIf(cnt, event_id='E19') AS E19,
            sumIf(cnt, event_id='E20') AS E20,
            sumIf(cnt, event_id='E21') AS E21,
            sumIf(cnt, event_id='E22') AS E22,
            sumIf(cnt, event_id='E23') AS E23,
            sumIf(cnt, event_id='E24') AS E24,
            sumIf(cnt, event_id='E25') AS E25,
            sumIf(cnt, event_id='E26') AS E26,
            sumIf(cnt, event_id='E27') AS E27,
            sumIf(cnt, event_id='E28') AS E28,
            sumIf(cnt, event_id='E29') AS E29,
            max(last_updated) AS last_updated
        FROM online.block_event_stats
        WHERE block_id IN (
            SELECT block_id FROM online.block_event_stats WHERE last_updated > '{last_ts}'
        )
        GROUP BY block_id
        """
        df = self.ch_client.query_df(query)
        return df

    def predict_and_insert(self, df):
        if df.empty:
            return []

        feature_cols = [f'E{i}' for i in range(1, 30)]
        X = df[feature_cols].fillna(0).astype(float)
        X_scaled = self.scaler.transform(X)
        probs = self.model.predict_proba(X_scaled)[:, 1]

        anomalies = []
        for idx, row in df.iterrows():
            score = probs[idx]
            if score > self.config['anomaly_threshold']:
                record = {
                    'block_id': str(row['block_id']),
                }
                # 确保E1-E29转换为整数
                for i in range(1, 30):
                    e_col = f'E{i}'
                    record[e_col] = int(row.get(e_col, 0) or 0)
                record['anomaly_score'] = float(score)
                record['detected_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                anomalies.append(record)

        if anomalies:
            self.ch_client.insert_df('online.anomaly_blocks', pd.DataFrame(anomalies))
            logger.info(f"插入 {len(anomalies)} 条异常记录")

        return anomalies

    def update_redis(self, anomalies):
        if not self.redis_client or not anomalies:
            return

        pipe = self.redis_client.pipeline()
        for rec in anomalies:
            block_id = rec['block_id']
            score = rec['anomaly_score']
            pipe.zadd('anomaly:top', {block_id: score})

            detail = {f'E{i}': rec[f'E{i}'] for i in range(1, 30)}
            detail['anomaly_score'] = score
            pipe.hset(f'anomaly:detail:{block_id}', mapping=detail)
            pipe.expire(f'anomaly:detail:{block_id}', 3600)

        pipe.zremrangebyrank('anomaly:top', 0, -(self.config['top_n'] + 1))
        pipe.execute()
        logger.info(f"Redis Top {self.config['top_n']} 异常更新完成")

    def run(self):
        logger.info("实时预测服务启动")
        self.connect_clickhouse()
        self.connect_redis()
        self.load_model()

        while True:
            try:
                last_ts = self.get_last_predict_time()
                logger.info(f"查询增量数据，上次处理时间: {last_ts}")

                df = self.fetch_incremental_blocks(last_ts)
                if not df.empty:
                    logger.info(f"获取到 {len(df)} 个 block 的新特征")
                    anomalies = self.predict_and_insert(df)
                    if anomalies:
                        self.update_redis(anomalies)

                    new_last_ts = df['last_updated'].max()
                    self.save_last_predict_time(new_last_ts)
                    logger.info(f"更新最后处理时间为: {new_last_ts}")
                else:
                    logger.info("无新数据")

            except Exception as e:
                logger.exception(f"预测循环出错: {e}")

            time.sleep(self.config['predict_interval'])


if __name__ == '__main__':
    config = load_config()
    predictor = RealtimePredictor(config)
    predictor.run()