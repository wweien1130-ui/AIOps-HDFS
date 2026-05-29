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


print(f"✅ Redis: {redis_config['host']}:{redis_config['port']}")
print(f"✅ ClickHouse: {ch_config['host']}:{ch_config.get('http_port', 8123)}")


key_prefix = redis_config.get('key_prefix', 'anomaly:')
last_sync = r.get(key_prefix + redis_config['keys']['sync_time'])
if last_sync is None:
    last_sync = '1970-01-01 00:00:00'

while True:
    print("🔄 查询 anomaly_blocks...")
    print(f"   last_sync = {last_sync}")
    query = f"""
    SELECT 
    block_id, 
    any(E1) AS E1, any(E2) AS E2, any(E3) AS E3, any(E4) AS E4, any(E5) AS E5, 
    any(E6) AS E6, any(E7) AS E7, any(E8) AS E8, any(E9) AS E9, any(E10) AS E10,
    any(E11) AS E11, any(E12) AS E12, any(E13) AS E13, any(E14) AS E14, any(E15) AS E15, 
    any(E16) AS E16, any(E17) AS E17, any(E18) AS E18, any(E19) AS E19, any(E20) AS E20,
    any(E21) AS E21, any(E22) AS E22, any(E23) AS E23, any(E24) AS E24, any(E25) AS E25, 
    any(E26) AS E26, any(E27) AS E27, any(E28) AS E28, any(E29) AS E29,
    max(anomaly_score) AS anomaly_score, 
    max(detected_at) AS detected_at
FROM online.anomaly_blocks
WHERE block_id IN (
    SELECT block_id FROM online.anomaly_blocks WHERE detected_at > '{last_sync}'
)
GROUP BY block_id
    """
    df = client.query_df(query)
    if not df.empty:
        pipe = r.pipeline()
        for _, row in df.iterrows():
            block_id = str(row['block_id'])
            score = float(row['anomaly_score'])

            # 存储Top N排序集
            pipe.zadd(key_prefix + redis_config['keys']['top'], {block_id: score})

            # 存储详情Hash，确保E1-E29转换为整数
            detail = {}
            for i in range(1, 30):
                e_col = f'E{i}'
                detail[e_col] = int(row.get(e_col, 0))
            detail['anomaly_score'] = score

            pipe.hset(key_prefix + redis_config['keys']['detail'] + block_id, mapping=detail)

        pipe.zremrangebyrank(key_prefix + redis_config['keys']['top'], 0, -11)
        pipe.execute()
        new_sync = df['detected_at'].max()
        r.set(key_prefix + redis_config['keys']['sync_time'], str(new_sync))
        last_sync = new_sync
    time.sleep(5)
