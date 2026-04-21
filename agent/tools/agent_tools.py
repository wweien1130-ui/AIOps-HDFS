import os
import re
import sys
from langchain_core.tools import tool

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from utils.path_tool import get_abs_path

KNOWLEDGE_DIR = get_abs_path("hdfs_knowledge")
HDFS_BASE_DIR = get_abs_path("BackUp")

# 从 data_preparator.py 导入 prepare_training_data（多级降级策略）
from data_preparator import prepare_training_data

# 从 realtime_query.py 导入实时异常查询
from realtime_query import query_realtime_anomalies


@tool(description="处理离线批次：从ClickHouse查询指定batch_id的数据，进行异常检测")
def process_offline_batch(batch_id: str) -> str:
    """
    处理离线批次数据：
    1. 从ClickHouse的offline.block_event_stats查询指定batch_id
    2. 用MLP模型预测异常
    3. 结果存入offline.anomaly_blocks
    """
    import subprocess
    import os

    script_path = get_abs_path("scripts/offline/predictor.py")

    if not os.path.exists(script_path):
        return f"❌ 脚本不存在: {script_path}"

    try:
        # 设置环境变量传递batch_id
        env = os.environ.copy()
        env['OFFLINE_BATCH_ID'] = batch_id

        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            env=env,
            timeout=300
        )

        if result.returncode == 0:
            return f"✅ 批次 {batch_id} 处理完成！\n{result.stdout}"
        else:
            return f"❌ 处理失败: {result.stderr}"
    except subprocess.TimeoutExpired:
        return f"❌ 处理超时"
    except Exception as e:
        return f"❌ 执行失败: {str(e)}"


@tool(description="查询所有离线批次列表")
def list_offline_batches() -> str:
    """查询ClickHouse中所有离线批次"""
    import clickhouse_connect
    import yaml

    config_dir = get_abs_path("config")
    ch_config_path = os.path.join(config_dir, "clickhouse.yaml")
    with open(ch_config_path, 'r', encoding='utf-8') as f:
        ch_config = yaml.safe_load(f)['clickhouse']['offline']

    client = clickhouse_connect.get_client(
        host=ch_config['host'],
        port=ch_config.get('http_port', 8123),
        username=ch_config.get('username', 'default'),
        password=ch_config.get('password', '')
    )

    query = """
    SELECT batch_id, count() as block_count
    FROM offline.block_event_stats
    GROUP BY batch_id
    ORDER BY batch_id DESC
    LIMIT 10
    """
    result = client.query_df(query)

    if result.empty:
        return "⚠️ 暂无离线批次数据"

    output = ["📊 **离线批次列表**\n"]
    for _, row in result.iterrows():
        output.append(f"- **批次 {row['batch_id']}**: {row['block_count']} 个Block")

    return "\n".join(output)


@tool(description="查询指定批次的异常详情")
def list_offline_anomalies(batch_id: str) -> str:
    """
    查询指定batch_id的异常详情，包括每个block的E1-E29事件分布和异常分数。
    用于获取具体异常信息，以便给出针对性的解决方案。
    """
    import clickhouse_connect
    import yaml
    config_dir = get_abs_path("config")
    ch_config_path = os.path.join(config_dir, "clickhouse.yaml")
    with open(ch_config_path, 'r', encoding='utf-8') as f:
        ch_config = yaml.safe_load(f)['clickhouse']['offline']
    client = clickhouse_connect.get_client(
        host=ch_config['host'],
        port=ch_config.get('http_port', 8123),
        username=ch_config.get('username', 'default'),
        password=ch_config.get('password', '')
    )
    query = f"""
    SELECT 
        block_id,
        E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
        E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
        E21, E22, E23, E24, E25, E26, E27, E28, E29,
        anomaly_score
    FROM offline.anomaly_blocks
    WHERE batch_id = {batch_id}
    ORDER BY anomaly_score DESC
    """
    result = client.query_df(query)
    if result.empty:
        return f"⚠️ 批次 {batch_id} 暂无异常数据"
    # E1-E29事件含义映射
    event_meanings = {
        'E1': 'Adding an already existing block',
        'E2': 'Verification succeeded',
        'E3': 'Served block to',
        'E4': 'Got exception while serving',
        'E5': 'Receiving block src:dest:',
        'E6': 'Received block src:dest:of size',
        'E7': 'writeBlock received exception',
        'E8': 'PacketResponder for block Interrupted',
        'E9': 'Received block of size from',
        'E10': 'PacketResponder Exception',
        'E11': 'PacketResponder for block terminating',
        'E12': 'Exception writing block to mirror',
        'E13': 'Receiving empty packet for block',
        'E14': 'Exception in receiveBlock for block',
        'E15': 'Changing block file offset',
        'E16': 'Transmitted block to',
        'E17': 'Failed to transfer to',
        'E18': 'Starting thread to transfer block',
        'E19': 'Reopen Block',
        'E20': 'Unexpected error deleting block',
        'E21': 'Deleting block file',
        'E22': 'allocateBlock:',
        'E23': 'delete: is added to invalidSet',
        'E24': 'Removing block from neededReplications',
        'E25': 'ask to replicate to',
        'E26': 'addStoredBlock: blockMap updated',
        'E27': 'addStoredBlock: Redundant request',
        'E28': 'addStoredBlock: Block not in any file',
        'E29': 'PendingReplicationMonitor timeout'
    }
    output = [f"📊 **批次 {batch_id} 异常详情** (共 {len(result)} 个异常)\n"]
    output.append("=" * 80)
    for idx, row in result.iterrows():
        output.append(f"\n### Block: **{row['block_id']}** (异常分数: {row['anomaly_score']:.4f})")

        # 找出非零的事件
        nonzero_events = []
        for i in range(1, 30):
            e_col = f'E{i}'
            if row[e_col] > 0:
                nonzero_events.append((e_col, row[e_col], event_meanings.get(e_col, 'Unknown')))

        if nonzero_events:
            output.append("事件统计:")
            for e, cnt, meaning in sorted(nonzero_events, key=lambda x: x[1], reverse=True):
                output.append(f"  - {e} ({meaning}): {cnt} 次")
        else:
            output.append("  无事件统计")
    return "\n".join(output)





@tool(description="检查异常检测模型和特征矩阵是否准备就绪。")
def check_model_readiness() -> str:
    """
    专门给 Agent 调用的‘眼睛’，返回模型和数据的物理存在状态。
    """
    # model_path = get_abs_path("LogMLP_Model.pth")
    model_path = os.path.join(HDFS_BASE_DIR, "Preprocess_File", "block_anomaly_model.pkl")
    scaler_path = os.path.join(HDFS_BASE_DIR, "Preprocess_File", "scaler.pkl")
    matrix_path = os.path.join(HDFS_BASE_DIR, "File", "Event_occurrence_matrix.csv")

    status = []
    status.append(f"模型文件: {'✅ 已存在' if os.path.exists(model_path) else '❌ 缺失'}")
    status.append(f"标准化器: {'✅ 已存在' if os.path.exists(scaler_path) else '❌ 缺失'}")
    status.append(f"特征矩阵: {'✅ 已存在' if os.path.exists(matrix_path) else '❌ 缺失'}")

    if all(os.path.exists(p) for p in [model_path, scaler_path, matrix_path]):
        return "\n".join(status) + "\n\n结论：所有组件已就绪，可以直接执行 detect_anomaly。"
    else:
        return "\n".join(status) + "\n\n结论：组件不全，需要先执行预处理或训练。"


def search_local_files(query: str):
    results = []
    keywords = re.findall(r'[a-zA-Z0-9_]+', query)

    if not os.path.exists(KNOWLEDGE_DIR):
        return f"错误：找不到知识库目录 {KNOWLEDGE_DIR}"

    for file_name in os.listdir(KNOWLEDGE_DIR):
        if file_name.endswith(".txt"):
            path = os.path.join(KNOWLEDGE_DIR, file_name)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if any(kw.lower() in content.lower() for kw in keywords):
                    results.append(f"--- 来自文件: {file_name} ---\n{content}")
    return "\n\n".join(results)


@tool(description="【核心工具】检索HDFS知识库，获取错误码E1-E30的具体定义和修复指令")
def rag_retrieve(query: str) -> str:
    try:
        from rag.rag_service import RagSummarizerService
        rag = RagSummarizerService()
        docs = rag.retriever_docs(query)
        if docs and len(docs) > 0:
            return "\n\n".join([d.page_content for d in docs])
    except Exception as e:
        print(f"向量检索失效，切换到本地文件搜索: {e}")

    local_data = search_local_files(query)
    if local_data:
        return local_data

    return "在知识库中未找到关于该问题的直接描述，请尝试更换关键词（如直接搜索错误码E1）。"


@tool(description="获取当前时间")
def get_current_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool(description="计算数学表达式")
def calculate(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except:
        return "计算错误"


@tool(description="第一步：预处理HDFS日志（多级降级策略）")
def preprocess_hdfs_logs(log_file: str = None) -> str:
    """
    预处理HDFS日志 - 多级降级策略：

    优先级1: 从备份目录复制官方 Event_occurrence_matrix.csv
    优先级2: 从备份目录复制 training_data.csv
    优先级3: 从备份目录复制 block_features.csv + Event.csv 并合并
    兜底方案: 使用 log_preprocessor.py 本地解析日志文件（最慢）
    """
    # 尝试使用 data_preparator (快速)
    try:
        from data_preparator import prepare_training_data
        result = prepare_training_data()

        # 检查是否成功
        if "✅" in result:
            return f"✅ 预处理成功（快速路径）！\n{result}\n\n现在可以调用 train_mlp_model 进行训练了。"
        elif "❌" in result:
            # 所有优先级都失败了，使用兜底方案
            pass
        else:
            return f"✅ 预处理成功！\n{result}\n\n现在可以调用 train_mlp_model 进行训练了。"
    except Exception as e:
        print(f"data_preparator 调用失败，使用兜底方案: {e}")

    # 兜底方案: 使用 log_preprocessor.py 本地解析（最慢但最可靠）
    if not log_file or os.path.basename(log_file) == log_file:
        log_file = os.path.join(HDFS_BASE_DIR, "HDFS.log")

    matrix_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")
    template_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "HDFS.log_templates.csv")

    try:
        from log_preprocessor import LogPreprocessor
        preprocessor = LogPreprocessor()
        preprocessor.load_templates(template_file)
        preprocessor.preprocess_log(log_file, matrix_file)

        return f"✅ 预处理成功（兜底方案）！已生成特征矩阵文件：{matrix_file}。现在可以调用 train_mlp_model 进行训练了。"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ 预处理最终失败: {str(e)}"


@tool(description="第二步：使用'Event_occurrence_matrix.csv'训练MLP模型。")
def train_mlp_model(epochs: int = 50) -> str:
    """
    训练MLP模型。如果模型文件已存在，直接返回，不会重复训练。
    """
    print("[train_mlp_model] 开始执行...")

    data_file = os.path.join(HDFS_BASE_DIR, "File", "Event_occurrence_matrix.csv")
    model_out = os.path.join(HDFS_BASE_DIR, "Preprocess_File", "block_anomaly_model.pkl")
    scaler_out = os.path.join(HDFS_BASE_DIR, "Preprocess_File", "scaler.pkl")

    print(f"[train_mlp_model] 检查模型是否存在: {model_out}")
    print(f"[train_mlp_model] 模型文件存在: {os.path.exists(model_out)}")
    print(f"[train_mlp_model] Scaler文件存在: {os.path.exists(scaler_out)}")

    # 如果模型已存在，直接返回
    if os.path.exists(model_out) and os.path.exists(scaler_out):
        print(f"[train_mlp_model] 模型已存在，跳过训练")
        return f"模型已存在！无需重复训练。文件位置: {model_out}。请直接调用 detect_anomaly 进行检测。"

    if not os.path.exists(data_file):
        return "训练失败：找不到矩阵文件，请先执行 preprocess_hdfs_logs。"

    try:
        from model.mlp_model import train_mlp

        print(f"[train_mlp_model] 开始训练...")
        model_path, scaler_path, f1 = train_mlp(
            data_file=data_file,
            epochs=epochs,
            model_out=model_out,
            scaler_out=scaler_out
        )
        print(f"[train_mlp_model] 训练完成，F1: {f1}")
        print(f"[train_mlp_model] 返回结果...")

        return f"MLP模型训练成功！F1-Score: {f1:.4f}。模型已保存到: {model_path}。接下来可以执行 detect_anomaly 了。"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"模型训练崩溃，原因: {str(e)}"


@tool(
    description="【必须执行】使用MLP模型对HDFS日志进行异常检测，直接加载模型和数据进行预测，输出异常BlockId列表。不需要任何参数！")
def detect_anomaly(threshold: float = 0.3) -> str:
    """
    核心异常检测工具。
    使用 sklearn 的 MLPClassifier 模型 (block_anomaly_model.pkl)

    ⚠️ 如果模型不存在，会自动训练！
    """
    print("[detect_anomaly] 开始执行异常检测...")

    # 1. 使用正确的项目根目录路径
    model_path = os.path.join(HDFS_BASE_DIR, "Preprocess_File", "block_anomaly_model.pkl")
    scaler_path = os.path.join(HDFS_BASE_DIR, "Preprocess_File", "scaler.pkl")
    matrix_file = os.path.join(HDFS_BASE_DIR, "File", "Event_occurrence_matrix.csv")
    template_file = os.path.join(HDFS_BASE_DIR, "File", "HDFS.log_templates.csv")

    # 检查模型是否存在，不存在则自动训练
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        print("[detect_anomaly] 模型文件不存在，开始自动训练...")

        # 确保矩阵文件存在
        if not os.path.exists(matrix_file):
            return "错误：特征矩阵文件不存在，请先执行预处理！"

        # 调用训练函数
        try:
            from model.mlp_model import train_mlp

            model_path, scaler_path, f1 = train_mlp(
                data_file=matrix_file,
                epochs=50,
                model_out=model_path,
                scaler_out=scaler_path
            )
            print(f"[detect_anomaly] 自动训练完成，F1: {f1}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"自动训练失败：{str(e)}"

    # 加载模型并检测
    try:
        import joblib
        import pandas as pd

        # 加载数据
        print(f"[detect_anomaly] 加载数据: {matrix_file}")
        df = pd.read_csv(matrix_file)

        # 如果数据量太大，进行采样（只处理前10000条）
        MAX_SAMPLES = 10000
        if len(df) > MAX_SAMPLES:
            print(f"[detect_anomaly] 数据量过大({len(df)}条)，采样前{MAX_SAMPLES}条")
            df = df.head(MAX_SAMPLES)

        feature_cols = [f'E{i}' for i in range(1, 30)]
        X = df[feature_cols].fillna(0)
        print(f"[detect_anomaly] 数据加载完成，共 {len(df)} 条")

        # 加载 sklearn 模型和标准化器
        print(f"[detect_anomaly] 加载模型: {model_path}")
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        print(f"[detect_anomaly] 模型加载完成，开始预测...")

        # 预测
        print(f"[detect_anomaly] 标准化数据...")
        X_scaled = scaler.transform(X)
        print(f"[detect_anomaly] 执行预测...")
        preds = model.predict(X_scaled)
        print(f"[detect_anomaly] 计算概率...")
        probs = model.predict_proba(X_scaled)[:, 1]  # 异常概率
        print(f"[detect_anomaly] 预测完成")

        # 6. 整理结果
        df['prediction'] = ['Fail' if p == 1 else 'Success' for p in preds]
        df['anomaly_prob'] = probs

        anomalies = df[df['prediction'] == 'Fail'].sort_values('anomaly_prob', ascending=False)
        total_anomalies = len(anomalies)

        print(f"[detect_anomaly] 检测完成，发现 {total_anomalies} 个异常")

        if total_anomalies == 0:
            return f"检测完成：在 {len(df)} 条记录中未发现异常（当前阈值 {threshold}）。系统状态正常。"

        # 简化输出，跳过 RAG 查询（太慢）
        anomaly_blocks = anomalies.head(10)

        # 构建完整报告
        output = f"### 🔍 异常检测摘要报告\n\n"
        output += f"- **总检测块数**: {len(df)}\n"
        output += f"- **发现异常块**: {total_anomalies}\n"
        output += f"- **异常比例**: {(total_anomalies / len(df)):.2%}\n"
        output += f"- **当前判定阈值**: {threshold}\n"
        output += f"\n---\n\n"
        output += f"#### 🚨 前 10 条高危异常:\n\n"

        for i, (_, row) in enumerate(anomaly_blocks.iterrows(), 1):
            # 获取E事件详情
            events_str = ""
            for j in range(1, 30):
                col = f'E{j}'
                if col in row and row[col] > 0:
                    events_str += f"{col}:{int(row[col])} "
            output += f"**{i}. BlockID**: `{row['BlockId']}` | **异常概率**: `{row['anomaly_prob']:.4f}` | **标签**: {row['Label']} | **事件**: {events_str}\n"

        if total_anomalies > 10:
            output += f"---\n\n"
            output += f"> **提示**: 还有 {total_anomalies - 10} 条异常记录未在此列出。"

        return output

    except Exception as e:
        import traceback
        print(f"[detect_anomaly] 发生错误: {e}")
        traceback.print_exc()
        error_msg = f"异常检测运行时发生崩溃: {str(e)}"
        return error_msg


@tool(description="查询当前实时异常（从Redis/ClickHouse获取）。如无实时数据则返回提示。")
def get_realtime_anomalies(limit: int = 10) -> str:
    """
    查询实时异常数据：
    1. 优先从 Redis 获取 Top N 异常
    2. 如果 Redis 无数据，从 ClickHouse 查询
    3. 如果都无数据，返回提示
    """
    return query_realtime_anomalies(limit)


@tool(description="启动实时监控服务（自动检测在线日志异常）")
def start_realtime_service() -> str:
    """
    启动实时监控服务：
    1. 启动 predictor.py - 预测异常写入ClickHouse
    2. 启动 redis_sync.py - 同步到Redis
    启动后，Agent会自动处理在线日志的异常检测
    """
    import subprocess
    import os
    import sys
    
    scripts_dir = get_abs_path("scripts/online")
    
    predictor_script = os.path.join(scripts_dir, "predictor.py")
    redis_sync_script = os.path.join(scripts_dir, "redis_sync.py")
    watch_folder_script = os.path.join(scripts_dir, "watch_folder.py")
    
    if not os.path.exists(predictor_script):
        return f"❌ 找不到预测脚本: {predictor_script}"
    if not os.path.exists(redis_sync_script):
        return f"❌ 找不到同步脚本: {redis_sync_script}"
    
    try:
        import logging
        logging.basicConfig(level=logging.INFO)
        
        proc1 = subprocess.Popen(
            [sys.executable, predictor_script],
            cwd=scripts_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        logging.info(f"启动predictor: pid={proc1.pid}")
        
        proc2 = subprocess.Popen(
            [sys.executable, redis_sync_script],
            cwd=scripts_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        logging.info(f"启动redis_sync: pid={proc2.pid}")
        
        proc3 = subprocess.Popen(
            [sys.executable, watch_folder_script],
            cwd=scripts_dir,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        logging.info(f"启动watch_folder: pid={proc3.pid}")
        
        watch_dir = get_abs_path("HDFS_Test")
        
        return f"""✅ 实时监控服务已启动！

服务说明：
1. predictor.py - 定时检测 online.block_event_stats，写入异常到 anomaly_blocks
2. redis_sync.py - 同步异常到Redis，供快速查询
3. watch_folder.py - 监控文件夹自动读取日志

监控文件夹: {watch_dir}

现在可以：
- 把日志文件复制到监控文件夹，系统会自动读取并检测
- 查询实时异常数据"""
    except Exception as e:
        return f"❌ 启动失败: {str(e)}"


@tool(description="停止实时监控服务")
def stop_realtime_service() -> str:
    """
    停止实时监控服务：
    1. 停止 predictor.py
    2. 停止 redis_sync.py
    3. 停止 watch_folder.py
    """
    import psutil
    
    stopped = []
    errors = []
    
    scripts = ['predictor.py', 'redis_sync.py', 'watch_folder.py']
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any(script in ' '.join(cmdline) for script in scripts):
                proc.terminate()
                stopped.append(cmdline)
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            errors.append(str(e))
    
    if stopped:
        return f"✅ 已停止实时监控服务！\n\n停止的进程: {len(stopped)}个"
    else:
        return "⚠️ 没有正在运行的实时监控服务"