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
HDFS_BASE_DIR = get_abs_path("HDFS_v1")

# 从 data_preparator.py 导入 prepare_training_data（多级降级策略）
from data_preparator import prepare_training_data

# 从 realtime_query.py 导入实时异常查询
from realtime_query import query_realtime_anomalies


@tool(description="检查异常检测模型和特征矩阵是否准备就绪。")
def check_model_readiness() -> str:
    """
    专门给 Agent 调用的‘眼睛’，返回模型和数据的物理存在状态。
    """
    # model_path = get_abs_path("LogMLP_Model.pth")
    model_path = get_abs_path("block_anomaly_model.pkl")
    scaler_path = get_abs_path("scaler.pkl")
    matrix_path = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")

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

    data_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")
    model_out = get_abs_path("block_anomaly_model.pkl")
    scaler_out = get_abs_path("scaler.pkl")

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
    model_path = get_abs_path("block_anomaly_model.pkl")
    scaler_path = get_abs_path("scaler.pkl")
    matrix_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")
    template_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "HDFS.log_templates.csv")

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