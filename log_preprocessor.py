import os
import re
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score
import matplotlib.pyplot as plt
import joblib


class LogPreprocessor:
    def __init__(self):
        self.templates = {}
        self.template_regexes = {}

    def load_templates(self, template_file: str):
        """加载日志模板文件"""
        data = pd.read_csv(template_file)
        for _, row in data.iterrows():
            event_id = row['EventId']
            template = row['EventTemplate']
            self.templates[event_id] = template
            regex_pattern = self._template_to_regex(template)
            self.template_regexes[event_id] = regex_pattern
        print(f"已加载 {len(self.templates)} 个日志模板")

    def _template_to_regex(self, template: str) -> re.Pattern:
        """将日志模板转换为正则表达式"""
        pattern = template
        pattern = pattern.replace('[*]', '([^\\s]+)')
        return re.compile(pattern)

    def _parse_log_line(self, line: str) -> tuple:
        """解析单行日志，提取 BlockId 和事件类型"""
        block_match = re.search(r'(blk_[\-0-9]+)', line)
        block_id = block_match.group(1) if block_match else None

        matched_events = []
        for event_id, regex in self.template_regexes.items():
            if regex.search(line):
                matched_events.append(event_id)

        return block_id, matched_events

    def preprocess_log(self, log_file: str, output_file: str):
        """预处理日志文件，生成事件出现矩阵"""
        print(f"开始预处理日志文件: {log_file}")

        block_events = {}

        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                block_id, matched_events = self._parse_log_line(line)

                if block_id:
                    if block_id not in block_events:
                        block_events[block_id] = []
                    block_events[block_id].extend(matched_events)

        print(f"共发现 {len(block_events)} 个 Block")

        event_ids = sorted(self.templates.keys(), key=lambda x: int(x[1:]))

        rows = []
        for block_id, events in block_events.items():
            event_counts = {eid: 0 for eid in event_ids}
            for eid in events:
                if eid in event_counts:
                    event_counts[eid] += 1

            row = {
                'BlockId': block_id,
                'Label': '',
                'Type': '',
                **event_counts
            }
            rows.append(row)

        df = pd.DataFrame(rows)

        anomaly_labels = self._load_anomaly_labels()
        for idx, row in df.iterrows():
            block_id = row['BlockId']
            if block_id in anomaly_labels:
                label = anomaly_labels[block_id]
                if label == 'Anomaly':
                    df.at[idx, 'Label'] = 'Fail'
                    anomaly_type = self._detect_anomaly_type(events)
                    df.at[idx, 'Type'] = anomaly_type
                else:
                    df.at[idx, 'Label'] = 'Success'

        for idx, row in df.iterrows():
            if row['Label'] == '':
                df.at[idx, 'Label'] = 'Success'

        df = df.sort_values('BlockId').reset_index(drop=True)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        df.to_csv(output_file, index=False)
        print(f"事件出现矩阵已保存到: {output_file}")

    def _load_anomaly_labels(self) -> dict:
        """加载异常标签"""
        label_file = 'HDFS_v1/preprocessed/anomaly_label.csv'
        if not os.path.exists(label_file):
            return {}

        labels = {}
        df = pd.read_csv(label_file)
        for _, row in df.iterrows():
            labels[row['BlockId']] = row['Label']
        return labels

    def _detect_anomaly_type(self, events: list) -> int:
        """检测异常类型"""
        event_set = set(events)

        if 'E7' in event_set:
            return 7
        elif 'E21' in event_set:
            return 21
        elif 'E5' in event_set:
            return 5
        elif 'E4' in event_set:
            return 4
        else:
            return 0


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Using device: {device}')

if __name__ == '__main__':
    # 加载数据
    data = pd.read_csv('HDFS_v1/preprocessed/Event_occurrence_matrix.csv')

    # 提取特征和标签
    X = data.iloc[:, 3:].values  # 从第4列开始是特征
    # 将标签转换为0和1
    y = data['Label'].map({'Success': 0, 'Fail': 1}).values

    # 数据归一化
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    # 划分训练集和测试集
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    # 转换为PyTorch张量
    X_train = torch.tensor(X_train, dtype=torch.float32)
    y_train = torch.tensor(y_train, dtype=torch.float32).unsqueeze(1)
    X_test = torch.tensor(X_test, dtype=torch.float32)
    y_test = torch.tensor(y_test, dtype=torch.float32).unsqueeze(1)

    # 计算类别权重，处理数据不平衡
    class_counts = np.bincount(y_train.numpy().flatten().astype(int))
    class_weights = 1.0 / class_counts
    class_weights = torch.tensor(class_weights, dtype=torch.float32)


    # 定义MLP模型
    class MLP(nn.Module):
        def __init__(self, input_dim):
            super(MLP, self).__init__()
            self.fc1 = nn.Linear(input_dim, 128)  # 减少隐藏层大小
            self.relu1 = nn.ReLU()
            self.fc2 = nn.Linear(128, 32)  # 减少隐藏层大小
            self.relu2 = nn.ReLU()
            self.fc3 = nn.Linear(32, 1)

        def forward(self, x):
            x = self.fc1(x)
            x = self.relu1(x)
            x = self.fc2(x)
            x = self.relu2(x)
            x = self.fc3(x)
            return x


    # 初始化模型、损失函数和优化器
    input_dim = X_train.shape[1]
    model = MLP(input_dim)
    criterion = nn.BCEWithLogitsLoss(pos_weight=class_weights[1])
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # 训练模型
    epochs = 100
    batch_size = 16
    losses = []

    best_loss = float('inf')
    patience = 10
    no_improve_count = 0
    best_model_state = None

    for epoch in range(epochs):
        model.train()
        epoch_loss = 0
        for i in range(0, len(X_train), batch_size):
            batch_X = X_train[i:i + batch_size]
            batch_y = y_train[i:i + batch_size]

            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()

        avg_loss = epoch_loss / (len(X_train) // batch_size)
        losses.append(avg_loss)

        if avg_loss < best_loss:
            best_loss = avg_loss
            no_improve_count = 0
            best_model_state = model.state_dict().copy()
        else:
            no_improve_count += 1

        if (epoch + 1) % 10 == 0:
            print(f'Epoch [{epoch + 1}/{epochs}], Loss: {avg_loss:.4f}, Best Loss: {best_loss:.4f}')

        if no_improve_count >= patience:
            print(f'Early stopping at epoch {epoch + 1}! No improvement for {patience} epochs.')
            break

    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        print(f'Loaded best model with loss: {best_loss:.4f}')

    # 评估模型
    model.eval()
    with torch.no_grad():
        y_pred = model(X_test)
        y_pred = torch.sigmoid(y_pred)  # 添加Sigmoid获取概率
        y_pred = (y_pred > 0.5).float()
        f1 = f1_score(y_test.numpy(), y_pred.numpy())
        print(f'F1-Score: {f1:.4f}')

    # 保存模型权重和scaler
    torch.save(model.state_dict(), 'LogMLP_Model.pth')
    joblib.dump(scaler, 'scaler.pkl')
    print('Model saved to LogMLP_Model.pth')
    print('Scaler saved to scaler.pkl')

    # 绘制损失曲线
    plt.plot(losses)
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.title('Training Loss')
    plt.savefig('loss_curve.png')
    print('Loss curve saved to loss_curve.png')