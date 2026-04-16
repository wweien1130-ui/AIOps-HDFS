import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import joblib

# ========== 1. 加载数据 ==========
df = pd.read_csv('training_data.csv')

# 特征列（E1 到 E29）
feature_cols = [f'E{i}' for i in range(1, 30)]
X = df[feature_cols].fillna(0)   # 填充缺失值为0
y = df['target']                  # 0=Success, 1=Fail

print(f"数据集大小: {len(df)}")
print(f"特征维度: {X.shape[1]}")
print(f"类别分布:\n{y.value_counts()}")

# ========== 2. 划分训练集和测试集 ==========
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ========== 3. 标准化（重要：MLP对特征尺度敏感）==========
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ========== 4. 训练 MLP 分类器 ==========
model = MLPClassifier(
    hidden_layer_sizes=(64, 32),   # 两个隐藏层：第一层64个神经元，第二层32个
    activation='relu',             # 激活函数
    solver='adam',                 # 优化器
    max_iter=500,                  # 最大迭代次数
    random_state=42,
    early_stopping=True,           # 早停，防止过拟合
    validation_fraction=0.1
)

print("\n开始训练...")
model.fit(X_train_scaled, y_train)

# ========== 5. 评估模型 ==========
# y_pred = model.predict(X_test_scaled)
# 预测
y_pred = model.predict(X_test_scaled)

# 与原始 label 对比
y_actual = y_test  # 原始 target

# 计算准确率
accuracy = (y_pred == y_actual).mean()
print(f"准确率: {accuracy:.4f}")

print(f"\n准确率: {accuracy_score(y_test, y_pred):.4f}")
print("\n分类报告:")
print(classification_report(y_test, y_pred, target_names=['Success', 'Fail']))
print("混淆矩阵:")
print(confusion_matrix(y_test, y_pred))

# ========== 6. 保存模型和标准化器 ==========
joblib.dump(model, 'block_anomaly_model.pkl')
joblib.dump(scaler, 'scaler.pkl')
print("\n✅ 模型已保存为 block_anomaly_model.pkl")
print("✅ 标准化器已保存为 scaler.pkl")

# ========== 7. （可选）特征重要性分析 ==========
# 对于 MLP，没有直接的特征重要性，可以查看第一个隐藏层的权重
# 这里简单输出各特征在模型中的平均绝对权重（仅供参考）
if hasattr(model, 'coefs_'):
    first_layer_weights = model.coefs_[0]
    importance = abs(first_layer_weights).mean(axis=1)
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': importance
    }).sort_values('importance', ascending=False)
    print("\n特征重要性（基于第一层权重）:")
    print(feature_importance.head(10))