import os
import re
import sys
from langchain_core.tools import tool

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(TOOLS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.path_tool import get_abs_path

KNOWLEDGE_DIR = get_abs_path("hdfs_knowledge")
HDFS_BASE_DIR = get_abs_path("HDFS_v1")


def search_local_files(query: str):
    """从本地txt文件中硬核检索匹配内容"""
    results = []
    # 提取查询中的核心词，如 blk_, E1, DataNode 等
    keywords = re.findall(r'[a-zA-Z0-9_]+', query)

    if not os.path.exists(KNOWLEDGE_DIR):
        return f"错误：找不到知识库目录 {KNOWLEDGE_DIR}"

    for file_name in os.listdir(KNOWLEDGE_DIR):
        if file_name.endswith(".txt"):
            path = os.path.join(KNOWLEDGE_DIR, file_name)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 简单的关键词命中逻辑
                if any(kw.lower() in content.lower() for kw in keywords):
                    # 提取包含关键词的那一部分段落（前后各200字）
                    results.append(f"--- 来自文件: {file_name} ---\n{content}")
    return "\n\n".join(results)


@tool(description="【核心工具】检索HDFS知识库，获取错误码E1-E30的具体定义和修复指令")
def rag_retrieve(query: str) -> str:
    """
    当用户询问具体的HDFS报错（如blk_not found, E1, 心跳超时等）时，必须调用此工具获取原始资料。
    """
    # 1. 先尝试你原有的向量检索（如果它有效的话）
    try:
        from rag.rag_service import RagSummarizerService
        rag = RagSummarizerService()
        docs = rag.retriever_docs(query)
        if docs and len(docs) > 0:
            return "\n\n".join([d.page_content for d in docs])
    except Exception as e:
        print(f"向量检索失效，切换到本地文件搜索: {e}")

    # 2. 向量检索没结果或报错，直接暴力搜索本地txt文件
    local_data = search_local_files(query)
    if local_data:
        return local_data

    return "在知识库中未找到关于该问题的直接描述，请尝试更换关键词（如直接搜索错误码E1）。"


# 保留原有的时间计算工具
@tool(description="获取当前时间")
def get_current_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool(description="计算数学表达式")
def calculate(expression: str) -> str:
    try:
        # 简单安全评估
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except:
        return "计算错误"


@tool(description="预处理HDFS日志文件，生成事件出现矩阵。默认使用：HDFS_v1/HDFS.log 和 HDFS_v1/preprocessed/HDFS.log_templates.csv")
def preprocess_hdfs_logs(
        log_file: str = None,
        template_file: str = None,
        output_file: str = None
) -> str:
    """
    预处理HDFS日志文件，生成事件出现矩阵。

    参数:
        log_file: 原始日志文件路径（可选，默认：HDFS_v1/HDFS.log）
        template_file: 日志模板文件路径（可选，默认：HDFS_v1/preprocessed/HDFS.log_templates.csv）
        output_file: 输出CSV文件路径（可选，默认：HDFS_v1/preprocessed/Event_occurrence_matrix_new.csv）
    """
    if log_file is None:
        log_file = os.path.join(HDFS_BASE_DIR, "HDFS.log")
    if template_file is None:
        template_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "HDFS.log_templates.csv")
    if output_file is None:
        output_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix_new.csv")
    try:
        from log_preprocessor import LogPreprocessor

        preprocessor = LogPreprocessor()
        preprocessor.load_templates(template_file)
        preprocessor.preprocess_log(log_file, output_file)

        return f"日志预处理完成！事件出现矩阵已保存到: {output_file}"
    except Exception as e:
        return f"日志预处理失败: {str(e)}"


@tool(description="训练HDFS异常检测MLP模型")
def train_mlp_model(
        data_file: str = None,
        epochs: int = 100
) -> str:
    if data_file is None:
        data_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")
    """
    训练MLP模型用于HDFS异常检测。

    参数:
        data_file: 事件出现矩阵CSV文件路径
        epochs: 训练轮数，默认100
    """
    try:
        import numpy as np
        import pandas as pd
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import f1_score
        import joblib

        # 加载数据
        data = pd.read_csv(data_file)

        # 提取特征和标签
        X = data.iloc[:, 3:].values
        y = data['Label'].map({'Success': 0, 'Fail': 1}).values

        # 数据归一化
        scaler = StandardScaler()
        X = scaler.fit_transform(X)

        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # 转换为PyTorch张量
        X_train = torch.tensor(X_train, dtype=torch.float32)
        y_train = torch.tensor(y_train, dtype=torch.float32).unsqueeze(1)
        X_test = torch.tensor(X_test, dtype=torch.float32)
        y_test = torch.tensor(y_test, dtype=torch.float32).unsqueeze(1)

        # 计算类别权重
        class_counts = np.bincount(y_train.numpy().flatten().astype(int))
        class_weights = 1.0 / class_counts
        class_weights = torch.tensor(class_weights, dtype=torch.float32)

        # 定义MLP模型
        class MLP(nn.Module):
            def __init__(self, input_dim):
                super(MLP, self).__init__()
                self.fc1 = nn.Linear(input_dim, 128)
                self.relu1 = nn.ReLU()
                self.fc2 = nn.Linear(128, 32)
                self.relu2 = nn.ReLU()
                self.fc3 = nn.Linear(32, 1)

            def forward(self, x):
                x = self.fc1(x)
                x = self.relu1(x)
                x = self.fc2(x)
                x = self.relu2(x)
                x = self.fc3(x)
                return x

        # 初始化模型
        input_dim = X_train.shape[1]
        model = MLP(input_dim)
        criterion = nn.BCEWithLogitsLoss(pos_weight=class_weights[1])
        optimizer = optim.Adam(model.parameters(), lr=0.001)

        # 训练模型
        batch_size = 16
        for epoch in range(epochs):
            model.train()
            for i in range(0, len(X_train), batch_size):
                batch_X = X_train[i:i + batch_size]
                batch_y = y_train[i:i + batch_size]

                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

            if (epoch + 1) % 20 == 0:
                print(f'Epoch [{epoch + 1}/{epochs}]')

        # 评估模型
        model.eval()
        with torch.no_grad():
            y_pred = model(X_test)
            y_pred = torch.sigmoid(y_pred)
            y_pred = (y_pred > 0.5).float()
            f1 = f1_score(y_test.numpy(), y_pred.numpy())

        # 保存模型和scaler
        torch.save(model.state_dict(), 'LogMLP_Model.pth')
        joblib.dump(scaler, 'scaler.pkl')

        return f"MLP模型训练完成！F1-Score: {f1:.4f}\n模型已保存到: LogMLP_Model.pth\nScaler已保存到: scaler.pkl"
    except Exception as e:
        return f"模型训练失败: {str(e)}"


@tool(description="使用MLP模型对HDFS日志进行异常检测和故障诊断")
def detect_anomaly(
        model_path: str = None,
        template_file: str = None,
        log_file: str = None,
        threshold: float = 0.8
) -> str:
    if model_path is None:
        model_path = get_abs_path("LogMLP_Model.pth")
    if template_file is None:
        template_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "HDFS.log_templates.csv")
    if log_file is None:
        log_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")
    """
    使用训练好的MLP模型对HDFS日志进行异常检测，并生成故障诊断。

    参数:
        model_path: 模型文件路径
        template_file: 日志模板文件路径
        log_file: 事件出现矩阵文件路径
        threshold: 异常概率阈值，默认0.8
    """
    try:
        import torch
        import pandas as pd
        import numpy as np
        import joblib
        from collections import defaultdict

        # 定义MLP模型
        class MLP(torch.nn.Module):
            def __init__(self, input_dim):
                super(MLP, self).__init__()
                self.fc1 = torch.nn.Linear(input_dim, 128)
                self.relu1 = torch.nn.ReLU()
                self.fc2 = torch.nn.Linear(128, 32)
                self.relu2 = torch.nn.ReLU()
                self.fc3 = torch.nn.Linear(32, 1)

            def forward(self, x):
                x = self.fc1(x)
                x = self.relu1(x)
                x = self.fc2(x)
                x = self.relu2(x)
                x = self.fc3(x)
                return x

        # 加载模板
        template_data = pd.read_csv(template_file)
        templates = {}
        for _, row in template_data.iterrows():
            event_id = row['EventId']
            template = row['EventTemplate']
            templates[event_id] = template

        # 加载模型
        data = pd.read_csv(log_file)
        input_dim = data.shape[1] - 3
        model = MLP(input_dim)
        model.load_state_dict(torch.load(model_path))
        model.eval()

        # 加载scaler
        scaler = joblib.load('scaler.pkl')

        # 检测异常
        X = data.iloc[:, 3:].values
        X = scaler.transform(X)

        results = []
        for i, features in enumerate(X):
            block_id = data.iloc[i]['BlockId']

            with torch.no_grad():
                features_tensor = torch.tensor(features, dtype=torch.float32)
                prediction = model(features_tensor)
                probability = torch.sigmoid(prediction).item()

            if probability > threshold:
                anomaly_logs = []
                for event_id, count in zip(data.columns[3:], features):
                    if count > 0:
                        template = templates.get(event_id, 'Unknown')
                        anomaly_logs.append(f"  - {event_id}: {template} (出现 {int(count)} 次)")

                results.append(f"\n【异常块】{block_id} | 异常概率: {probability:.4f}\n" +
                               "\n".join(anomaly_logs))

        if results:
            return f"检测到 {len(results)} 个异常块:\n" + "\n".join(results)
        else:
            return f"未检测到异常块（阈值: {threshold}）"

    except Exception as e:
        return f"异常检测失败: {str(e)}"