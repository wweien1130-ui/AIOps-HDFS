import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
import joblib
import os
from typing import List, Dict
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score


class MLP(nn.Module):
    def __init__(self, input_dim: int):
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

    def predict_proba(self, x: np.ndarray) -> float:
        self.eval()
        with torch.no_grad():
            x_tensor = torch.tensor(x, dtype=torch.float32).unsqueeze(0)
            output = self(x_tensor)
            proba = torch.sigmoid(output).item()
        return proba

    def predict(self, x: np.ndarray, threshold: float = 0.5) -> int:
        proba = self.predict_proba(x)
        return 1 if proba > threshold else 0


def load_mlp_model(model_path: str, input_dim: int, device: str = None) -> MLP:
    """加载训练好的 MLP 模型"""
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'

    model = MLP(input_dim)
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def detect_anomalies(
        model: MLP,
        scaler,
        data_file: str,
        threshold: float = 0.8,
        template_file: str = None
) -> List[Dict]:
    """使用训练好的模型检测异常"""
    data = pd.read_csv(data_file)
    X = data.iloc[:, 3:].values
    X = scaler.transform(X)

    templates = {}
    if template_file and os.path.exists(template_file):
        template_data = pd.read_csv(template_file)
        for _, row in template_data.iterrows():
            templates[row['EventId']] = row['EventTemplate']

    results = []
    for i in range(len(X)):
        block_id = data.iloc[i]['BlockId']
        features = X[i]

        probability = model.predict_proba(features)

        if probability > threshold:
            event_details = []
            for event_id, count in zip(data.columns[3:], data.iloc[i, 3:].values):
                if count > 0:
                    template = templates.get(event_id, 'Unknown')
                    event_details.append({
                        'event_id': event_id,
                        'template': template,
                        'count': int(count)
                    })

            results.append({
                'block_id': block_id,
                'probability': probability,
                'events': event_details
            })

    return results


def train_mlp(
        data_file: str,
        epochs: int = 50,
        model_out: str = None,
        scaler_out: str = None
) -> tuple:
    """
    训练 MLP 模型

    Args:
        data_file: 事件出现矩阵 CSV 文件路径
        epochs: 训练轮数
        model_out: 模型输出路径
        scaler_out: scaler 输出路径

    Returns:
        (model_path, scaler_path, f1_score)
    """
    data = pd.read_csv(data_file)

    X = data.iloc[:, 3:].values
    y = data['Label'].map({'Success': 0, 'Fail': 1}).values
    y = y.astype(int)

    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    except Exception:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

    X_train = torch.tensor(X_train, dtype=torch.float32)
    y_train = torch.tensor(y_train, dtype=torch.float32).unsqueeze(1)
    X_test = torch.tensor(X_test, dtype=torch.float32)
    y_test = torch.tensor(y_test, dtype=torch.float32).unsqueeze(1)

    y_train_np = y_train.numpy().flatten().astype(int)
    class_counts = np.bincount(y_train_np, minlength=2)
    if class_counts[1] == 0 or class_counts[0] == 0:
        pos_weight = torch.tensor(1.0, dtype=torch.float32)
    else:
        pos_weight = torch.tensor(class_counts[0] / class_counts[1], dtype=torch.float32)

    input_dim = X_train.shape[1]
    model = MLP(input_dim)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    batch_size = 512
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

    model.eval()
    with torch.no_grad():
        y_pred = model(X_test)
        y_pred = torch.sigmoid(y_pred)
        y_pred = (y_pred > 0.5).float()
        f1 = f1_score(y_test.numpy().flatten(), y_pred.numpy().flatten())

    if model_out:
        os.makedirs(os.path.dirname(model_out), exist_ok=True)
        torch.save(model.state_dict(), model_out)

    if scaler_out:
        os.makedirs(os.path.dirname(scaler_out), exist_ok=True)
        joblib.dump(scaler, scaler_out)

    return model_out, scaler_out, f1