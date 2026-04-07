import torch
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import joblib

from rag.rag_service import RagSummarizerService


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


class AgentSystem:
    def __init__(self, model_path, template_file, scaler_path='scaler.pkl', use_rag=True):
        self.model, self.device = self.load_model(model_path)
        self.templates = self.load_templates(template_file)
        self.scaler = joblib.load(scaler_path)
        self.llm_type = 'ollama'
        self.use_rag = use_rag

        if use_rag:
            try:
                self.rag_service = RagSummarizerService()
                print(f'AgentSystem initialized with RAG, device: {self.device}')
            except Exception as e:
                print(f'RAG初始化失败: {e}，将使用基础诊断模式')
                self.rag_service = None
        else:
            self.rag_service = None
            print(f'AgentSystem initialized (no RAG), device: {self.device}')

    def load_model(self, model_path):
        data = pd.read_csv('HDFS_v1/preprocessed/Event_occurrence_matrix.csv')
        input_dim = data.shape[1] - 3

        model = MLP(input_dim)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.to(device)
        model.eval()
        return model, device

    def load_templates(self, template_file):
        data = pd.read_csv(template_file)
        templates = {}
        for _, row in data.iterrows():
            event_id = row['EventId']
            template = row['EventTemplate']
            templates[event_id] = template
        return templates

    def predict(self, features):
        with torch.no_grad():
            features = torch.tensor(features, dtype=torch.float32).to(self.device)
            prediction = self.model(features)
            probability = torch.sigmoid(prediction).item()
            return probability

    def generate_diagnosis(self, anomaly_logs, block_id):
        prompt = f"你是一位HDFS故障诊断专家。请分析以下异常日志，给出故障原因和3个排查建议。\n\n异常块ID: {block_id}\n\n异常日志:\n{anomaly_logs}"

        if self.use_rag and self.rag_service:
            try:
                # 直接使用RAG服务，不要传入query，而是让RAG检索后生成
                context_query = f"HDFS异常: {anomaly_logs}"
                docs = self.rag_service.retriever_docs(context_query)

                # 构建上下文
                context = ""
                for i, doc in enumerate(docs[:3]):
                    context += f"\n[{i + 1}] {doc.page_content}"

                # 使用简单prompt直接调用大模型
                final_prompt = f"基于以下知识库内容和我对HDFS日志的分析，给出诊断建议。\n\n知识库:\n{context}\n\n异常日志:\n{anomaly_logs}\n\n诊断建议:"

                # 简单调用RAG的model
                from langchain_core.messages import HumanMessage
                result = self.rag_service.model.invoke([HumanMessage(content=final_prompt)])

                if result and hasattr(result, 'content'):
                    return result.content
                elif result and len(result) > 50:
                    return str(result)
            except Exception as e:
                print(f'RAG调用失败: {e}')

        return f"[本地诊断结果]\n异常块ID: {block_id}\n\n异常日志:\n{anomaly_logs}\n\n建议:\n1. 检查DataNode状态\n2. 验证block副本完整性\n3. 查看namenode日志"

    def process_logs(self, log_file, max_samples=10000):
        data = pd.read_csv(log_file)
        total = len(data)

        # 限制处理的数据量
        if total > max_samples:
            data = data.head(max_samples)
            print(f'数据量限制: 只处理前 {max_samples} 条 (原数据: {total} 条)')
        else:
            print(f'数据总量: {total} 条')

        X = data.iloc[:, 3:].values
        X = self.scaler.transform(X)

        for i in range(len(X)):
            block_id = data.iloc[i]['BlockId']
            features = X[i]

            probability = self.predict(features)

            if probability > 0.8:
                print(f'Block {block_id} 被检测为异常，概率: {probability:.4f}')

                anomaly_logs = []
                original_features = data.iloc[i, 3:].values
                for event_id, count in zip(data.columns[3:], original_features):
                    if count > 0:
                        template = self.templates.get(event_id, 'Unknown')
                        anomaly_logs.append(f'{event_id}: {template} (出现 {count} 次)')

                diagnosis = self.generate_diagnosis('\n'.join(anomaly_logs), block_id)
                print('故障诊断:')
                print(diagnosis)
                print('-' * 80)

            if (i + 1) % 1000 == 0:
                print(f'进度: {i + 1}/{len(X)}', end='\r')

        print(f'\n处理完成! 共处理 {len(X)} 条数据')


if __name__ == '__main__':
    agent = AgentSystem('LogMLP_Model.pth', 'HDFS_v1/preprocessed/HDFS.log_templates.csv', use_rag=True)
    agent.process_logs('HDFS_v1/preprocessed/Event_occurrence_matrix.csv')