import os
import yaml


def get_config_dir():
    """获取配置目录（与 scripts 中保持一致）"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')


def load_config():
    """加载配置文件"""
    config = {}
    config_dir = get_config_dir()

    ch_path = os.path.join(config_dir, 'clickhouse.yaml')
    if os.path.exists(ch_path):
        with open(ch_path, 'r', encoding='utf-8') as f:
            config['clickhouse'] = yaml.safe_load(f)['clickhouse']['online']

    redis_path = os.path.join(config_dir, 'redis.yaml')
    if os.path.exists(redis_path):
        with open(redis_path, 'r', encoding='utf-8') as f:
            config['redis'] = yaml.safe_load(f)['redis']

    return config


def query_from_redis(limit: int = 10) -> str:
    config = load_config()
    if 'redis' not in config:
        return ""

    try:
        import redis
        r = redis.Redis(host=config['redis']['host'], port=config['redis']['port'], db=config['redis']['db'])
        key_prefix = config['redis'].get('key_prefix', 'anomaly:')

        top_anomalies = r.zrevrange(key_prefix + config['redis']['keys']['top'], 0, limit - 1, withscores=True)

        if not top_anomalies:
            return ""

        results = ["📊 **实时异常（来自Redis）**", ""]
        for block_id, score in top_anomalies:
            block_id_str = block_id.decode() if isinstance(block_id, bytes) else block_id
            results.append(f"- **{block_id_str}** (异常分数: {score:.4f})")

        return "\n".join(results)
    except Exception as e:
        return f"⚠️ Redis查询失败: {e}"


def query_from_clickhouse(limit: int = 10) -> str:
    config = load_config()
    if 'clickhouse' not in config:
        return ""

    try:
        import clickhouse_connect
        client = clickhouse_connect.get_client(
            host=config['clickhouse']['host'],
            port=config['clickhouse']['port'],
            username=config['clickhouse'].get('username', 'default'),
            password=config['clickhouse'].get('password', '')
        )

        query = f"""
        SELECT block_id, anomaly_score, detected_at
        FROM {config['clickhouse']['database']}.anomaly_blocks
        ORDER BY anomaly_score DESC
        LIMIT {limit}
        """
        df = client.query_df(query)

        if df.empty:
            return ""

        results = ["📊 **实时异常（来自ClickHouse）**", ""]
        for _, row in df.iterrows():
            results.append(f"- **{row['block_id']}** (异常分数: {row['anomaly_score']:.4f})")

        return "\n".join(results)
    except Exception as e:
        return f"⚠️ ClickHouse查询失败: {e}"


def query_realtime_anomalies(limit: int = 10) -> str:
    redis_result = query_from_redis(limit)
    if redis_result:
        return redis_result

    ch_result = query_from_clickhouse(limit)
    if ch_result:
        return ch_result

    return "暂无可用的实时异常数据"