import clickhouse_connect
import joblib
import time
import pandas as pd
import yaml
import os

# 读取配置
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'clickhouse.yaml')
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

ch = config['clickhouse']['online']
client = clickhouse_connect.get_client(
    host=ch['host'],
    port=ch['port'],
    username=ch.get('username', 'default'),
    password=ch.get('password', '')
)

# 模型路径
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
model = joblib.load(os.path.join(project_root, 'agent', 'tools', 'block_anomaly_model.pkl'))
scaler = joblib.load(os.path.join(project_root, 'agent', 'tools', 'scaler.pkl'))

# 状态文件
state_file = os.path.join(script_dir, '.last_predict_time')

def get_last_predict_time():
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            return f.read().strip()
    return '1970-01-01 00:00:00'

def save_last_predict_time(timestamp):
    with open(state_file, 'w') as f:
        f.write(str(timestamp))

last_predict_time = get_last_predict_time()

# ... 后续代码保持不变