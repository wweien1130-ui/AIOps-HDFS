import os
import re
import sys
from langchain_core.tools import tool

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.path_tool import get_abs_path

KNOWLEDGE_DIR = get_abs_path("hdfs_knowledge")
HDFS_BASE_DIR = get_abs_path("HDFS_v1")


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


@tool(description="第一步：预处理HDFS日志，必须先生成'Event_occurrence_matrix.csv'。")
def preprocess_hdfs_logs(log_file: str = None) -> str:
    if not log_file or os.path.basename(log_file) == log_file:
        log_file = os.path.join(HDFS_BASE_DIR, "HDFS.log")

    matrix_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")
    template_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "HDFS.log_templates.csv")

    try:
        from log_preprocessor import LogPreprocessor
        preprocessor = LogPreprocessor()
        preprocessor.load_templates(template_file)
        preprocessor.preprocess_log(log_file, matrix_file)

        return f"预处理成功！已生成特征矩阵文件：{matrix_file}。现在可以调用 train_mlp_model 进行训练了。"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"预处理失败，请检查原始日志格式: {str(e)}"


@tool(description="第二步：使用'Event_occurrence_matrix.csv'训练MLP模型。")
def train_mlp_model(epochs: int = 50) -> str:
    data_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")

    if not os.path.exists(data_file):
        return "训练失败：找不到矩阵文件，请先执行 preprocess_hdfs_logs。"

    try:
        from model.mlp_model import train_mlp

        model_out = get_abs_path("LogMLP_Model.pth")
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


@tool(description="使用MLP模型对HDFS日志进行异常检测和故障诊断")
def detect_anomaly(
        model_path: str = None,
        template_file: str = None,
        log_file: str = None,
        threshold: float = 0.3   #默认阈值
) -> str:
    if model_path is None:
        model_path = get_abs_path("LogMLP_Model.pth")
    scaler_path = get_abs_path("scaler.pkl")

    if template_file is None:
        template_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "HDFS.log_templates.csv")

    if log_file is None:
        log_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")

    try:
        import joblib
        from model.mlp_model import load_mlp_model, detect_anomalies
        import pandas as pd

        data = pd.read_csv(log_file)
        input_dim = data.shape[1] - 3

        model = load_mlp_model(model_path, input_dim)
        scaler = joblib.load(scaler_path)

        results = detect_anomalies(
            model=model,
            scaler=scaler,
            data_file=log_file,
            threshold=threshold,
            template_file=template_file
        )

        if results:
            output = f"检测到 {len(results)} 个异常块:\n"
            for r in results:
                output += f"\n【异常块】{r['block_id']} | 异常概率: {r['probability']:.4f}\n"
                for event in r['events']:
                    output += f"  - {event['event_id']}: {event['template']} (出现 {event['count']} 次)\n"
            return output
        else:
            return f"未检测到异常块（阈值: {threshold}）"

    except FileNotFoundError as e:
        return f"文件未找到: {str(e)}。请先运行 train_mlp_model 训练模型。"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"异常检测失败: {str(e)}"