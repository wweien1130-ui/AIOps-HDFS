import os
import re
import sys
from langchain_core.tools import tool
from datetime import datetime

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

    output = ["📋 ═══ 离线批次列表 ═══"]
    output.append("\n")

    total_blocks = 0
    for idx, row in result.iterrows():
        try:
            batch_time = datetime.fromtimestamp(int(row['batch_id'])).strftime('%Y-%m-%d %H:%M')
        except:
            batch_time = "未知"
        block_count = row['block_count']
        total_blocks += block_count
        # 根据block数量显示不同的状态
        if block_count > 50:
            status = "🔴 高风险"
        elif block_count > 20:
            status = "🟡 中风险"
        else:
            status = "🟢 正常"
        output.append(f"┌─ 📦 批次: `{row['batch_id']}`")
        output.append(f"│  ├─ 时间: {batch_time}")
        output.append(f"│  ├─ Block数: {block_count}")
        output.append(f"│  └─ 状态: {status}")

    output.append("\n" + "─" * 40)
    output.append(f"📊 统计: 共 **{len(result)}** 个批次 | **{total_blocks}** 个Block")

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

    # 去重：只保留每个block_id分数最高的记录
    result = result.drop_duplicates(subset=['block_id'], keep='first')

    # E1-E29事件含义映射（中文）
    event_meanings = {
        'E1': '重复块添加',
        'E2': '块校验成功',
        'E3': '块服务请求',
        'E4': '块服务异常',
        'E5': '块接收中',
        'E6': '块接收完成',
        'E7': '写块异常',
        'E8': '数据包中断',
        'E9': '接收成功',
        'E10': '数据包异常',
        'E11': '响应器终止',
        'E12': '镜像写异常',
        'E13': '空数据包',
        'E14': '接收异常',
        'E15': '偏移变更',
        'E16': '传输完成',
        'E17': '传输失败',
        'E18': '启动传输',
        'E19': '重新打开块',
        'E20': '删除元数据错误',
        'E21': '删除块文件',
        'E22': '分配块',
        'E23': '标记无效',
        'E24': '移除复制',
        'E25': '请求复制',
        'E26': '块映射更新',
        'E27': '重复请求',
        'E28': '块不在文件',
        'E29': '复制超时'
    }

    output = [f"🎯 **批次 {batch_id} 异常分析报告**"]
    output.append(f"📊 异常Block数量: **{len(result)}** 个\n")
    output.append("=" * 70)

    for idx, row in result.iterrows():
        # 找出非零的事件
        nonzero_events = []
        for i in range(1, 30):
            e_col = f'E{i}'
            if row[e_col] > 0:
                nonzero_events.append((e_col, int(row[e_col]), event_meanings.get(e_col, 'Unknown')))

        # 按次数排序
        sorted_events = sorted(nonzero_events, key=lambda x: x[1], reverse=True)
        max_cnt = max([e[1] for e in sorted_events]) if sorted_events else 1

        output.append(f"\n🔴 Block: `{row['block_id']}`")
        output.append(f"   异常分数: **{row['anomaly_score']:.4f}**")

        if sorted_events:
            output.append("   📈 事件分布:")
            for e, cnt, meaning in sorted_events[:5]:
                bar_len = int(cnt / max_cnt * 10)
                bar = "▓" * bar_len + "░" * (10 - bar_len)
                output.append(f"      {e} {meaning}: {cnt:3d} │{bar}│")

    output.append("\n" + "=" * 70)
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

    优先级1: 从备份目录复制官方 Event_occurrence_matrix.csv(从data_preparator获得)
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


    from model.inference import predict_anomaly, format_anomaly_report

    # 调用预测函数
    result = predict_anomaly(
        model_path=model_path,
        scaler_path=scaler_path,
        matrix_file=matrix_file,
        threshold=threshold
    )
        # 格式化报告
    return format_anomaly_report(result)

@tool(description="查询当前实时异常（从Redis/ClickHouse获取）。如无实时数据则返回提示。")
def get_realtime_anomalies(limit: int = 10) -> str:
    """
    查询实时异常数据：
    1. 优先从 Redis 获取 Top N 异常
    2. 如果 Redis 无数据，从 ClickHouse 查询
    3. 如果都无数据，返回提示
    """
    return query_realtime_anomalies(limit)


@tool(description="启动实时监控服务：先启动监控进程，再切分日志模拟实时上传")
def start_realtime_service() -> str:
    """
    启动实时监控服务（按用户要求顺序）：
    1. 先启动 predictor.py, redis_sync.py, watch_folder.py（进入监听状态）
    2. 再启动 split_log.py 切分日志（模拟实时上传到 HDFS_Test/）
    这样 watch_folder 能实时检测到所有切分后的 .log 文件
    """
    import subprocess
    import os
    import sys
    import time
    import psutil

    scripts_dir = get_abs_path("scripts/online")
    hdfs_test_dir = get_abs_path("HDFS_Test")

    predictor_script = os.path.join(scripts_dir, "predictor.py")
    redis_sync_script = os.path.join(scripts_dir, "redis_sync.py")
    watch_folder_script = os.path.join(scripts_dir, "watch_folder.py")
    split_log_script = os.path.join(hdfs_test_dir, "split_log.py")

    if not os.path.exists(predictor_script):
        return f"❌ 找不到预测脚本: {predictor_script}"
    if not os.path.exists(redis_sync_script):
        return f"❌ 找不到同步脚本: {redis_sync_script}"
    if not os.path.exists(split_log_script):
        return f"❌ 找不到切分脚本: {split_log_script}"

    def is_script_running(script_name: str) -> list:
        """检查同名脚本是否已经在运行，返回运行中的进程列表"""
        running = []
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline).lower()
                if script_name.lower() in cmdline_str and 'python' in cmdline_str:
                    running.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return running

    try:
        import logging
        logging.basicConfig(level=logging.INFO)

        running_pids = []
        new_started = []

        # 检查并启动 predictor.py
        running = is_script_running("predictor.py")
        if running:
            running_pids.append(f"predictor.py (已有 pid={running[0]})")
        else:
            proc1 = subprocess.Popen(
                [sys.executable, predictor_script],
                cwd=scripts_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            time.sleep(0.5)
            if proc1.poll() is not None:
                return f"❌ predictor.py 启动后立即退出"
            new_started.append(f"predictor.py (pid={proc1.pid})")
            logging.info(f"启动predictor: pid={proc1.pid}")

        # 检查并启动 redis_sync.py
        running = is_script_running("redis_sync.py")
        if running:
            running_pids.append(f"redis_sync.py (已有 pid={running[0]})")
        else:
            proc2 = subprocess.Popen(
                [sys.executable, redis_sync_script],
                cwd=scripts_dir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            time.sleep(0.5)
            if proc2.poll() is not None:
                _, stderr = proc2.communicate()
                return f"❌ redis_sync.py 启动失败:\n{stderr.decode()}"
            new_started.append(f"redis_sync.py (pid={proc2.pid})")
            logging.info(f"启动redis_sync: pid={proc2.pid}")

        # 检查并启动 watch_folder.py
        running = is_script_running("watch_folder.py")
        if running:
            running_pids.append(f"watch_folder.py (已有 pid={running[0]})")
        else:
            proc3 = subprocess.Popen(
                [sys.executable, watch_folder_script],
                cwd=scripts_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            new_started.append(f"watch_folder.py (pid={proc3.pid})")
            logging.info(f"启动watch_folder: pid={proc3.pid}")

        # 检查并启动 split_log.py
        running = is_script_running("split_log.py")
        if running:
            running_pids.append(f"split_log.py (已有 pid={running[0]})")
        else:
            proc4 = subprocess.Popen(
                [sys.executable, split_log_script],
                cwd=hdfs_test_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            new_started.append(f"split_log.py (pid={proc4.pid})")
            logging.info(f"启动split_log: pid={proc4.pid}")

        status_parts = []
        if running_pids:
            status_parts.append(f"⏭️  已运行中（共{len(running_pids)}个）：\n  " + "\n  ".join(running_pids))
        if new_started:
            status_parts.append(f"✅ 新启动（共{len(new_started)}个）：\n  " + "\n  ".join(new_started))

        return f"""✅ 实时监控服务状态：

{chr(10).join(status_parts)}

监控文件夹: {hdfs_test_dir}"""
    except Exception as e:
        return f"❌ 启动失败: {str(e)}"


@tool(description="停止实时监控服务：先停止日志切分，再停止监控进程")
def stop_realtime_service() -> str:
    """
    停止实时监控服务（按用户要求顺序）：
    1. 先停止 split_log.py（日志切分）
    2. 再停止 predictor.py, redis_sync.py, watch_folder.py（监控服务）
    """
    import psutil

    stopped = []
    errors = []

    # 按顺序停止：先切分，再监控
    scripts = ['split_log.py', 'predictor.py', 'redis_sync.py', 'watch_folder.py']

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any(script in ' '.join(cmdline) for script in scripts):
                proc.terminate()
                stopped.append(' '.join(cmdline))
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            errors.append(str(e))

    if stopped:
        return f"✅ 已停止实时监控服务！\n\n停止顺序：日志切分 → 监控服务\n停止的进程: {len(stopped)}个"
    else:
        return "⚠️ 没有正在运行的实时监控服务"
  
  
# ============================================================
# 运维管理工具
# ============================================================

@tool(description="检查系统组件连接状态（ClickHouse、Redis、Kafka）")
def check_system_status() -> str:
    """
    检查系统所有组件的连接状态：
    1. ClickHouse 连接状态
    2. Redis 连接状态
    3. Kafka 连接状态
    """
    import yaml

    config_dir = get_abs_path("config")
    status_list = ["📊 **系统组件状态检查**", ""]

    # 检查 ClickHouse
    try:
        import clickhouse_connect
        ch_path = os.path.join(config_dir, 'clickhouse.yaml')
        with open(ch_path, 'r', encoding='utf-8') as f:
            ch_config = yaml.safe_load(f)['clickhouse']['online']

        client = clickhouse_connect.get_client(
            host=ch_config['host'],
            port=ch_config.get('http_port', 8123),
            username=ch_config.get('username', 'default'),
            password=ch_config.get('password', '')
        )
        client.ping()
        status_list.append(f"✅ ClickHouse: {ch_config['host']}:{ch_config.get('http_port', 8123)}")
    except ImportError:
        status_list.append("⚠️ ClickHouse: 未安装 clickhouse_connect 模块")
    except Exception as e:
        status_list.append(f"❌ ClickHouse 连接失败: {str(e)}")

    # 检查 Redis
    try:
        import redis
        redis_path = os.path.join(config_dir, 'redis.yaml')
        with open(redis_path, 'r', encoding='utf-8') as f:
            redis_config = yaml.safe_load(f)['redis']

        r = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            db=redis_config.get('db', 0),
            password=redis_config.get('password'),
            decode_responses=True
        )
        r.ping()
        status_list.append(f"✅ Redis: {redis_config['host']}:{redis_config['port']}")
    except ImportError:
        status_list.append("⚠️ Redis: 未安装 redis 模块")
    except Exception as e:
        status_list.append(f"❌ Redis 连接失败: {str(e)}")

    # 检查 Kafka
    try:
        from kafka import KafkaConsumer
        kafka_path = os.path.join(config_dir, 'kafka.yml')
        with open(kafka_path, 'r', encoding='utf-8') as f:
            kafka_config = yaml.safe_load(f)['kafka']

        consumer = KafkaConsumer(
            bootstrap_servers=kafka_config['bootstrap_servers'],
            group_id='status_check'
        )
        consumer.close()
        status_list.append(f"✅ Kafka: {kafka_config['bootstrap_servers']}")
    except ImportError:
        status_list.append("⚠️ Kafka: 未安装 kafka-python 模块")
    except Exception as e:
        status_list.append(f"❌ Kafka 连接失败: {str(e)}")

    return "\n".join(status_list)


@tool(description="查看系统配置信息（需要二次确认）")
def view_system_config(confirm: bool = False) -> str:
    """
    查看系统配置信息，包括：
    - ClickHouse 配置
    - Redis 配置
    - Kafka 配置

    参数：
    confirm: 必须为 True 才能查看配置（二次确认机制）
    """
    if not confirm:
        return "⚠️ 查看配置需要确认！请回复 'confirm' 或设置 confirm=True"

    import yaml

    config_dir = get_abs_path("config")
    result = ["📋 **系统配置信息**", ""]

    # ClickHouse 配置
    try:
        ch_path = os.path.join(config_dir, 'clickhouse.yaml')
        with open(ch_path, 'r', encoding='utf-8') as f:
            ch_config = yaml.safe_load(f)['clickhouse']
        result.append("### ClickHouse 配置")
        result.append(f"- Online Host: {ch_config['online']['host']}:{ch_config['online'].get('http_port', 8123)}")
        result.append(f"- Offline Host: {ch_config['offline']['host']}:{ch_config['offline'].get('http_port', 8123)}")
        result.append(f"- Database: online={ch_config['online']['database']}, offline={ch_config['offline']['database']}")
        result.append("")
    except Exception as e:
        result.append(f"❌ 读取 ClickHouse 配置失败: {str(e)}")
        result.append("")

    # Redis 配置
    try:
        redis_path = os.path.join(config_dir, 'redis.yaml')
        with open(redis_path, 'r', encoding='utf-8') as f:
            redis_config = yaml.safe_load(f)['redis']
        result.append("### Redis 配置")
        result.append(f"- Host: {redis_config['host']}:{redis_config['port']}")
        result.append(f"- DB: {redis_config.get('db', 0)}")
        result.append(f"- Key Prefix: {redis_config.get('key_prefix', 'anomaly:')}")
        result.append("")
    except Exception as e:
        result.append(f"❌ 读取 Redis 配置失败: {str(e)}")
        result.append("")

    # Kafka 配置
    try:
        kafka_path = os.path.join(config_dir, 'kafka.yml')
        with open(kafka_path, 'r', encoding='utf-8') as f:
            kafka_config = yaml.safe_load(f)['kafka']
        result.append("### Kafka 配置")
        result.append(f"- Bootstrap Servers: {kafka_config['bootstrap_servers']}")
        result.append(f"- Topics: online={kafka_config['topics']['online']}, offline={kafka_config['topics']['offline']}")
        result.append("")
    except Exception as e:
        result.append(f"❌ 读取 Kafka 配置失败: {str(e)}")
        result.append("")

    return "\n".join(result)


@tool(description="清理Redis中的过期异常数据（需要二次确认）")
def cleanup_redis_data(confirm: bool = False) -> str:
    """
    清理Redis中的过期异常数据

    参数：
    confirm: 必须为 True 才能执行清理（二次确认机制）
    """
    if not confirm:
        return "⚠️ 清理数据需要确认！请回复 'confirm' 或设置 confirm=True"

    import yaml
    import redis

    config_dir = get_abs_path("config")

    try:
        redis_path = os.path.join(config_dir, 'redis.yaml')
        with open(redis_path, 'r', encoding='utf-8') as f:
            redis_config = yaml.safe_load(f)['redis']

        r = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            db=redis_config.get('db', 0),
            password=redis_config.get('password'),
            decode_responses=True
        )

        key_prefix = redis_config.get('key_prefix', 'anomaly:')

        # 清理 Top 异常排序集
        r.delete(key_prefix + redis_config['keys']['top'])

        # 清理异常详情 Hash
        detail_keys = r.keys(key_prefix + redis_config['keys']['detail'] + "*")
        if detail_keys:
            r.delete(*detail_keys)

        # 清理同步时间
        r.delete(key_prefix + redis_config['keys']['sync_time'])

        return f"✅ Redis 数据清理完成！\n\n已清理：\n- Top 异常排序集\n- 异常详情 Hash ({len(detail_keys)} 个)\n- 同步时间"
    except Exception as e:
        return f"❌ Redis 数据清理失败: {str(e)}"


@tool(description="查看服务运行状态（需要二次确认）")
def check_service_status(confirm: bool = False) -> str:
    """
    查看实时监控服务的运行状态

    参数：
    confirm: 必须为 True 才能查看状态（二次确认机制）
    """
    if not confirm:
        return "⚠️ 查看服务状态需要确认！请回复 'confirm' 或设置 confirm=True"

    import psutil

    scripts = ['predictor.py', 'redis_sync.py', 'watch_folder.py', 'split_log.py']
    running_services = []

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any(script in ' '.join(cmdline) for script in scripts):
                cmdline_str = ' '.join(cmdline)
                for script in scripts:
                    if script in cmdline_str:
                        running_services.append(f"- {script} (PID: {proc.info['pid']})")
                        break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if running_services:
        return "✅ **运行中的服务**\n\n" + "\n".join(running_services)
    else:
        return "⚠️ 没有正在运行的监控服务"


@tool(description="重启指定服务（需要二次确认）")
def restart_service(service_name: str, confirm: bool = False) -> str:
    """
    重启指定的监控服务

    参数：
    service_name: 服务名称 (predictor, redis_sync, watch_folder, all)
    confirm: 必须为 True 才能执行重启（二次确认机制）
    """
    if not confirm:
        return f"⚠️ 重启 {service_name} 服务需要确认！请回复 'confirm' 或设置 confirm=True"

    import subprocess
    import sys
    import os
    import psutil

    scripts_dir = get_abs_path("scripts/online")

    service_map = {
        'predictor': 'predictor.py',
        'redis_sync': 'redis_sync.py',
        'watch_folder': 'watch_folder.py',
        'all': 'all'
    }

    if service_name not in service_map:
        return f"❌ 未知的服务名称: {service_name}。可选: predictor, redis_sync, watch_folder, all"

    # 先停止相关服务
    target_scripts = []
    if service_name == 'all':
        target_scripts = ['predictor.py', 'redis_sync.py', 'watch_folder.py']
    else:
        target_scripts = [service_map[service_name]]

    stopped = []
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any(script in ' '.join(cmdline) for script in target_scripts):
                proc.terminate()
                stopped.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # 等待进程停止
    import time
    time.sleep(2)

    # 启动服务
    started = []
    for script in target_scripts:
        script_path = os.path.join(scripts_dir, script)
        if os.path.exists(script_path):
            proc = subprocess.Popen(
                [sys.executable, script_path],
                cwd=scripts_dir,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            started.append(f"{script} (PID: {proc.pid})")

    result = []
    if stopped:
        result.append(f"✅ 已停止 {len(stopped)} 个进程")
    if started:
        result.append(f"✅ 已启动 {len(started)} 个服务")
        result.append("")
        result.append("启动的服务:")
        result.extend(started)

    return "\n".join(result) if result else "⚠️ 没有找到可操作的服务"


# ============================================================
# 数据删除管理工具
# ============================================================

@tool(description="删除ClickHouse offline指定批次的数据（需要二次确认）")
def delete_offline_batch(batch_id: str, confirm: bool = False) -> str:
    """
    删除ClickHouse offline库中指定批次的数据

    参数：
    batch_id: 要删除的批次ID
    confirm: 必须为 True 才能执行删除（二次确认机制）
    """
    if not confirm:
        return f"⚠️ 删除批次 {batch_id} 需要确认！请回复 'confirm' 或设置 confirm=True"

    import yaml
    import clickhouse_connect

    config_dir = get_abs_path("config")

    try:
        ch_path = os.path.join(config_dir, 'clickhouse.yaml')
        with open(ch_path, 'r', encoding='utf-8') as f:
            ch_config = yaml.safe_load(f)['clickhouse']['offline']

        client = clickhouse_connect.get_client(
            host=ch_config['host'],
            port=ch_config.get('http_port', 8123),
            username=ch_config.get('username', 'default'),
            password=ch_config.get('password', '')
        )

        # 删除相关数据
        queries = [
            f"DELETE FROM offline.block_event_stats WHERE batch_id = {batch_id}",
            f"DELETE FROM offline.anomaly_blocks WHERE batch_id = {batch_id}",
            f"DELETE FROM offline.hdfs_logs WHERE batch_id = {batch_id}"
        ]

        for query in queries:
            client.execute(query)

        return f"✅ 批次 {batch_id} 数据已删除！"
    except Exception as e:
        return f"❌ 删除失败: {str(e)}" 
