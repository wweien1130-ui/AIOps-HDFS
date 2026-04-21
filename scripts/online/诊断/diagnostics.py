# diagnostics.py
# 请在Python环境中运行此脚本检查数据

import clickhouse_connect
import yaml
import os
import sys

# 获取项目根目录（scripts/online/诊断 上两级）
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))

# 读取配置
config_dir = os.path.join(project_root, 'config')
with open(os.path.join(config_dir, 'clickhouse.yaml'), 'r', encoding='utf-8') as f:
    ch_config = yaml.safe_load(f)['clickhouse']['online']

client = clickhouse_connect.get_client(
    host=ch_config['host'],
    port=ch_config.get('http_port', 8123),
    username=ch_config.get('username', 'default'),
    password=ch_config.get('password', '')
)

print("=" * 50)
print("1. 检查 block_event_stats 表数据")
print("=" * 50)
query1 = """
SELECT block_id, event_id, cnt 
FROM online.block_event_stats 
LIMIT 10
"""
result1 = client.query_df(query1)
print(result1)

# 获取第一个block_id进行精确检查
if not result1.empty:
    first_block_id = result1.iloc[0]['block_id']
    print(f"\n精确检查 block_id: {first_block_id}")

    query_exact = f"""
    SELECT 
        block_id,
        sumIf(cnt, event_id='E1') AS E1,
        sumIf(cnt, event_id='E2') AS E2,
        sumIf(cnt, event_id='E3') AS E3,
        sumIf(cnt, event_id='E4') AS E4,
        sumIf(cnt, event_id='E5') AS E5,
        sumIf(cnt, event_id='E21') AS E21,
        sumIf(cnt, event_id='E23') AS E23
    FROM online.block_event_stats
    WHERE block_id = '{first_block_id}'
    GROUP BY block_id
    """
    result_exact = client.query_df(query_exact)
    print("精确查询结果:")
    print(result_exact)

print("\n" + "=" * 50)
print("2. 检查 anomaly_blocks 表数据（使用第一个block_id）")
print("=" * 50)
if not result1.empty:
    first_block_id = result1.iloc[0]['block_id']
    query3 = f"""
    SELECT block_id, E1, E2, E3, E4, E5, E21, E23, anomaly_score
    FROM online.anomaly_blocks
    WHERE block_id = '{first_block_id}'
    LIMIT 5
    """
    result3 = client.query_df(query3)
    print(result3)# diagnostics.py
# 请在Python环境中运行此脚本检查数据

import clickhouse_connect
import yaml
import os
import sys

# 获取项目根目录（scripts/online/诊断 上两级）
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))

# 读取配置
config_dir = os.path.join(project_root, 'config')
with open(os.path.join(config_dir, 'clickhouse.yaml'), 'r', encoding='utf-8') as f:
    ch_config = yaml.safe_load(f)['clickhouse']['online']

client = clickhouse_connect.get_client(
    host=ch_config['host'],
    port=ch_config.get('http_port', 8123),
    username=ch_config.get('username', 'default'),
    password=ch_config.get('password', '')
)

print("=" * 50)
print("1. 检查 block_event_stats 表数据")
print("=" * 50)
query1 = """
SELECT block_id, event_id, cnt 
FROM online.block_event_stats 
LIMIT 10
"""
result1 = client.query_df(query1)
print(result1)

# 获取第一个block_id进行精确检查
if not result1.empty:
    first_block_id = result1.iloc[0]['block_id']
    print(f"\n精确检查 block_id: {first_block_id}")

    query_exact = f"""
    SELECT 
        block_id,
        sumIf(cnt, event_id='E1') AS E1,
        sumIf(cnt, event_id='E2') AS E2,
        sumIf(cnt, event_id='E3') AS E3,
        sumIf(cnt, event_id='E4') AS E4,
        sumIf(cnt, event_id='E5') AS E5,
        sumIf(cnt, event_id='E21') AS E21,
        sumIf(cnt, event_id='E23') AS E23
    FROM online.block_event_stats
    WHERE block_id = '{first_block_id}'
    GROUP BY block_id
    """
    result_exact = client.query_df(query_exact)
    print("精确查询结果:")
    print(result_exact)

print("\n" + "=" * 50)
print("2. 检查 anomaly_blocks 表数据（使用第一个block_id）")
print("=" * 50)
if not result1.empty:
    first_block_id = result1.iloc[0]['block_id']
    query3 = f"""
    SELECT block_id, E1, E2, E3, E4, E5, E21, E23, anomaly_score
    FROM online.anomaly_blocks
    WHERE block_id = '{first_block_id}'
    LIMIT 5
    """
    result3 = client.query_df(query3)
    print(result3)