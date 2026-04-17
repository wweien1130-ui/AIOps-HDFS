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
    data_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")

    if not os.path.exists(data_file):
        return "训练失败：找不到矩阵文件，请先执行 preprocess_hdfs_logs。"

    try:
        from model.mlp_model import train_mlp

        # model_out = get_abs_path("LogMLP_Model.pth")
        model_out = get_abs_path("block_anomaly_model.pkl")
        scaler_out = get_abs_path("scaler.pkl")

        model_path, scaler_path, f1 = train_mlp(
            data_file=data_file,
            epochs=epochs,
            model_out=model_out,
            scaler_out=scaler_out
        )

        return f"MLP模型训练成功！F1-Score: {f1:.4f}。模型已保存到: {model_path}。接下来可以执行 detect_anomaly 了。"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"模型训练崩溃，原因: {str(e)}"


@tool(description="使用训练好的MLP模型对HDFS日志进行异常检测。该工具会自动读取预处理后的特征矩阵进行推理。")
def detect_anomaly(threshold: float = 0.3) -> str:
    """
    核心异常检测工具。
    使用 sklearn 的 MLPClassifier 模型 (block_anomaly_model.pkl)
    """
    # 1. 强制路径锁定
    matrix_file = os.path.join(TOOLS_DIR, "training_data.csv")
    model_path = os.path.join(TOOLS_DIR, "block_anomaly_model.pkl")
    scaler_path = os.path.join(TOOLS_DIR, "scaler.pkl")
    template_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "HDFS.log_templates.csv")

    # 2. 物理检查
    if not os.path.exists(matrix_file):
        return "检测中断：特征矩阵(training_data.csv)不存在。请先执行 preprocess_hdfs_logs 预处理日志。"
    if not os.path.exists(model_path):
        return "检测中断：模型文件(block_anomaly_model.pkl)缺失。请先执行 train_mlp_model 训练模型。"
    if not os.path.exists(scaler_path):
        return "检测中断：标准化器(scaler.pkl)缺失。请先执行 train_mlp_model 训练模型。"

    try:
        import joblib
        import pandas as pd

        # 3. 加载数据
        df = pd.read_csv(matrix_file)
        feature_cols = [f'E{i}' for i in range(1, 30)]
        X = df[feature_cols].fillna(0)

        # 4. 加载 sklearn 模型和标准化器
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)

        # 5. 预测
        X_scaled = scaler.transform(X)
        preds = model.predict(X_scaled)
        probs = model.predict_proba(X_scaled)[:, 1]  #异常概率

        # 6. 整理结果
        df['prediction'] = ['Fail' if p == 1 else 'Success' for p in preds]
        df['anomaly_prob'] = probs

        anomalies = df[df['prediction'] == 'Fail'].sort_values('anomaly_prob', ascending=False)
        total_anomalies = len(anomalies)

        if total_anomalies == 0:
            return f"检测完成：在 {len(df)} 条记录中未发现异常（当前阈值 {threshold}）。系统状态正常。"

        # ===== 自动查询解决方案 =====
        anomaly_blocks = anomalies.head(10)
        solutions = []

        for _, row in anomaly_blocks.iterrows():
            block_id = row['BlockId']
            # 调用 rag_retrieve 获取解决方案
            try:
                from agent_tools import rag_retrieve
                solution = rag_retrieve.invoke(f"HDFS BlockId {block_id} 异常解决方案")
            except:
                solution = "未找到解决方案"

            solutions.append({
                'block_id': block_id,
                'probability': row['anomaly_prob'],
                'label': row['Label'],
                'solution': solution
            })

        # 构建完整报告
        output = f"### 🔍 异常检测摘要报告\n\n"
        output += f"- **总检测块数**: {len(df)}\n"
        output += f"- **发现异常块**: {total_anomalies}\n"
        output += f"- **异常比例**: {(total_anomalies / len(df)):.2%}\n"
        output += f"- **当前判定阈值**: {threshold}\n"
        output += f"\n---\n\n"
        output += f"#### 🚨 前 10 条高危异常及解决方案:\n\n"

        for i, s in enumerate(solutions, 1):
            output += f"**{i}. BlockID**: `{s['block_id']}` | **异常概率**: `{s['probability']:.4f}` | **标签**: {s['label']}\n"
            output += f"**解决方案**: {s['solution']}\n\n"

        if total_anomalies > 10:
            output += f"---\n\n"
            output += f"> **提示**: 还有 {total_anomalies - 10} 条异常记录未在此列出。您可以继续询问解决方案。"

        return output

    except Exception as e:
        import traceback
        error_msg = f"异常检测运行时发生崩溃: {str(e)}\n{traceback.format_exc()}"
        return error_msg