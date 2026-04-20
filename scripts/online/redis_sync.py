import redis
import clickhouse_connect
import time
import yaml
import os

config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')

# ClickHouse 配置
with open(os.path.join(config_dir, 'clickhouse.yaml'), 'r', encoding='utf-8') as f:
    ch_config = yaml.safe_load(f)['clickhouse']['online']
client = clickhouse_connect.get_client(
    host=ch_config['host'],
    port=ch_config.get('http_port', 8123),  # 使用HTTP端口
    username=ch_config.get('username', 'default'),
    password=ch_config.get('password', '')
)

# Redis 配置
with open(os.path.join(config_dir, 'redis.yaml'), 'r', encoding='utf-8') as f:
    redis_config = yaml.safe_load(f)['redis']
r = redis.Redis(
    host=redis_config['host'],
    port=redis_config['port'],
    db=redis_config.get('db', 0),
    password=redis_config.get('password'),
    decode_responses=True
)

key_prefix = redis_config.get('key_prefix', 'anomaly:')
last_sync = r.get(key_prefix + redis_config['keys']['sync_time'])
if last_sync is None:
    last_sync = '1970-01-01 00:00:00'

while True:
    query = f"""
    SELECT 
        block_id, E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
        E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
        E21, E22, E23, E24, E25, E26, E27, E28, E29,
        anomaly_score, max(detected_at) as detected_at
    FROM online.anomaly_blocks
    WHERE block_id IN (
        SELECT block_id FROM online.anomaly_blocks WHERE detected_at > '{last_sync}'
    )    GROUP BY block_id
    """
    df = client.query_df(query)
    if not df.empty:
        pipe = r.pipeline()
        for _, row in df.iterrows():
            pipe.zadd(key_prefix + redis_config['keys']['top'], {row['block_id']: row['anomaly_score']})
            pipe.hset(key_prefix + redis_config['keys']['detail'] + row['block_id'], mapping={
                **{f'E{i}': row[f'E{i}'] for i in range(1,30)},
                'anomaly_score': row['anomaly_score']
            })
        pipe.zremrangebyrank(key_prefix + redis_config['keys']['top'], 0, -11)
        pipe.execute()
        new_sync = df['detected_at'].max()
        r.set(key_prefix + redis_config['keys']['sync_time'], str(new_sync))
        last_sync = new_sync
    time.sleep(10)