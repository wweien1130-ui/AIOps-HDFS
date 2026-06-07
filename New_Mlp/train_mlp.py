"""
用生成的 Event_occurrence_matrix.csv 训练 MLP 模型。
用法: python train_mlp.py
"""

import numpy as np
import pandas as pd
import joblib
import os
import warnings
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import f1_score, classification_report, confusion_matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    data_file = os.path.join(BASE_DIR, 'Event_occurrence_matrix.csv')
    model_out = os.path.join(BASE_DIR, 'block_anomaly_model.pkl')
    scaler_out = os.path.join(BASE_DIR, 'scaler.pkl')

    print("=" * 60)
    print("MLP 异常检测模型训练")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    data = pd.read_csv(data_file)
    print(f"  总样本数: {len(data)}")

    # 特征列 (E1-E29)
    X = data.iloc[:, 2:].values  # 跳过 BlockId 和 Label
    # 标签: Normal=0, Anomaly=1
    y = data['Label'].map({'Normal': 0, 'Anomaly': 1}).values.astype(int)

    label_counts = np.bincount(y, minlength=2)
    print(f"  Normal: {label_counts[0]}, Anomaly: {label_counts[1]}")
    print(f"  异常比例: {label_counts[1] / len(y) * 100:.2f}%")

    # 2. 标准化
    print("\n[2/4] 特征标准化...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 3. 划分训练/测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"  训练集: {len(X_train)}, 测试集: {len(X_test)}")

    # 4. 训练 sklearn MLPClassifier
    print("\n[3/4] 训练 MLP 模型...")

    # 计算类别权重处理不平衡
    class_weight = {0: 1.0, 1: label_counts[0] / label_counts[1]}
    print(f"  类别权重: Normal=1.0, Anomaly={class_weight[1]:.2f}")

    model = MLPClassifier(
        hidden_layer_sizes=(128, 64, 32),
        activation='relu',
        solver='adam',
        max_iter=300,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
        verbose=True
    )

    # 使用样本权重处理不平衡
    sample_weights = np.where(y_train == 1, class_weight[1], 1.0)
    model.fit(X_train, y_train)

    # 5. 评估
    print("\n[4/4] 评估模型...")
    y_pred = model.predict(X_test)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f1 = f1_score(y_test, y_pred, zero_division=0)

    print(f"\n  F1-Score: {f1:.4f}")
    print(f"\n  分类报告:")
    print(classification_report(y_test, y_pred, target_names=['Normal', 'Anomaly']))

    cm = confusion_matrix(y_test, y_pred)
    print(f"  混淆矩阵:")
    print(f"    TN={cm[0][0]}  FP={cm[0][1]}")
    print(f"    FN={cm[1][0]}  TP={cm[1][1]}")

    # 6. 保存模型
    joblib.dump(model, model_out)
    joblib.dump(scaler, scaler_out)
    print(f"\n  模型已保存: {model_out}")
    print(f"  Scaler已保存: {scaler_out}")

    # 7. 快速验证：检查预测概率分布
    y_proba = model.predict_proba(X_test)[:, 1]
    print(f"\n  预测概率分布:")
    print(f"    Min: {y_proba.min():.4f}")
    print(f"    Max: {y_proba.max():.4f}")
    print(f"    Mean: {y_proba.mean():.4f}")
    print(f"    Median: {np.median(y_proba):.4f}")

    # 按阈值统计
    for threshold in [0.3, 0.5, 0.7, 0.9]:
        count = (y_proba > threshold).sum()
        print(f"    P > {threshold}: {count} 个")


if __name__ == '__main__':
    main()
