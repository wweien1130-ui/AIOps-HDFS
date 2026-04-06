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
batch_size = 16  # 进一步减小批次大小以减少内存使用
losses = []

for epoch in range(epochs):
    model.train()
    epoch_loss = 0
    for i in range(0, len(X_train), batch_size):
        batch_X = X_train[i:i+batch_size]
        batch_y = y_train[i:i+batch_size]
        
        optimizer.zero_grad()
        outputs = model(batch_X)
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer.step()
        
        epoch_loss += loss.item()
    
    avg_loss = epoch_loss / (len(X_train) // batch_size)
    losses.append(avg_loss)
    
    if (epoch + 1) % 10 == 0:
        print(f'Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}')

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
