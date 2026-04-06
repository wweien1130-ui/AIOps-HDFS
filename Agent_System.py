import torch
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import joblib
# 注释掉pipeline导入，因为我们将使用Ollama或DeepSeek API
# from transformers import pipeline

# 定义MLP模型
class MLP(torch.nn.Module):
    def __init__(self, input_dim):
        super(MLP, self).__init__()
        self.fc1 = torch.nn.Linear(input_dim, 256)
        self.relu1 = torch.nn.ReLU()
        self.fc2 = torch.nn.Linear(256, 64)
        self.relu2 = torch.nn.ReLU()
        self.fc3 = torch.nn.Linear(64, 1)
    
    def forward(self, x):
        x = self.fc1(x)
        x = self.relu1(x)
        x = self.fc2(x)
        x = self.relu2(x)
        x = self.fc3(x)
        return x

class AgentSystem:
    def __init__(self, model_path, template_file, scaler_path='scaler.pkl'):
        # 加载模型
        self.model = self.load_model(model_path)
        # 加载模板
        self.templates = self.load_templates(template_file)
        # 加载scaler
        self.scaler = joblib.load(scaler_path)
        # 初始化LLM - 使用Ollama API（需要安装ollama包）
        # 这里使用占位符，实际使用时需要安装ollama包并调用其API
        self.llm_type = 'ollama'
        print('AgentSystem initialized with Ollama API')
    
    def load_model(self, model_path):
        """加载训练好的MLP模型"""
        # 先加载数据获取输入维度
        data = pd.read_csv('HDFS_v1/preprocessed/Event_occurrence_matrix.csv')
        input_dim = data.shape[1] - 3  # 减去BlockId, Label, Type列
        
        model = MLP(input_dim)
        model.load_state_dict(torch.load(model_path))
        model.eval()
        return model
    
    def load_templates(self, template_file):
        """加载日志模板"""
        data = pd.read_csv(template_file)
        templates = {}
        for _, row in data.iterrows():
            event_id = row['EventId']
            template = row['EventTemplate']
            templates[event_id] = template
        return templates
    
    def predict(self, features):
        """使用模型进行预测"""
        with torch.no_grad():
            features = torch.tensor(features, dtype=torch.float32)
            prediction = self.model(features)
            probability = torch.sigmoid(prediction).item()  # 添加Sigmoid获取概率
            return probability
    
    def generate_diagnosis(self, anomaly_logs):
        """生成故障诊断"""
        # 构建提示词
        prompt = f"你是一位SRE专家，请分析以下异常日志，并给出三个排查建议：\n\n{anomaly_logs}\n\n排查建议："
        
        # 调用LLM
        if self.llm_type == 'ollama':
            # 使用Ollama API（需要安装ollama包）
            # 示例代码：
            # import ollama
            # response = ollama.generate(model='llama3', prompt=prompt)
            # return response['response']
            # 由于Ollama可能未安装，这里返回占位符
            return f"[Ollama诊断结果] 分析异常日志：{anomaly_logs}\n1. 检查系统资源使用情况\n2. 查看相关服务日志\n3. 验证网络连接状态"
        else:
            # 使用DeepSeek API（需要API密钥）
            # 示例代码：
            # import requests
            # headers = {'Authorization': 'Bearer YOUR_API_KEY'}
            # data = {'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': prompt}]}
            # response = requests.post('https://api.deepseek.com/v1/chat/completions', headers=headers, json=data)
            # return response.json()['choices'][0]['message']['content']
            # 由于API密钥可能未配置，这里返回占位符
            return f"[DeepSeek诊断结果] 分析异常日志：{anomaly_logs}\n1. 检查系统资源使用情况\n2. 查看相关服务日志\n3. 验证网络连接状态"
    
    def process_logs(self, log_file):
        """处理日志并进行异常检测"""
        # 加载数据
        data = pd.read_csv(log_file)
        
        # 提取特征
        X = data.iloc[:, 3:].values
        
        # 数据归一化 - 使用训练时保存的scaler
        X = self.scaler.transform(X)
        
        # 对每条记录进行预测
        for i, features in enumerate(X):
            block_id = data.iloc[i]['BlockId']
            label = data.iloc[i]['Label']
            
            # 预测异常概率
            probability = self.predict(features)
            
            # 如果概率大于0.8，触发Agent
            if probability > 0.8:
                print(f'Block {block_id} 被检测为异常，概率: {probability:.4f}')
                
                # 提取该块的日志模板
                anomaly_logs = []
                for event_id, count in zip(data.columns[3:], features):
                    if count > 0:
                        template = self.templates.get(event_id, 'Unknown')
                        anomaly_logs.append(f'{event_id}: {template} (出现 {count} 次)')
                
                # 生成诊断
                diagnosis = self.generate_diagnosis('\n'.join(anomaly_logs))
                print('故障诊断:')
                print(diagnosis)
                print('-' * 80)

if __name__ == '__main__':
    agent = AgentSystem('LogMLP_Model.pth', 'HDFS_v1/preprocessed/HDFS.log_templates.csv')
    agent.process_logs('HDFS_v1/preprocessed/Event_occurrence_matrix.csv')
