"""
用 Event_occurrence_matrix.csv 训练异常检测模型（Random Forest）。
用法: python train_mlp.py
"""

import numpy as np
import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, classification_report, confusion_matrix

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    data_file = os.path.join(BASE_DIR, 'Event_occurrence_matrix.csv')
    model_out = os.path.join(BASE_DIR, 'block_anomaly_model.pkl')
    scaler_out = os.path.join(BASE_DIR, 'scaler.pkl')

    print("=" * 60)
    print("Random Forest 异常检测模型训练")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/4] 加载数据...")
    data = pd.read_csv(data_file)
    print(f"  总样本数: {len(data)}")

    X = data.iloc[:, 2:].values
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

    # 4. 训练 Random Forest
    print("\n[3/4] 训练 Random Forest...")
    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # 5. 评估 - 自动搜索最优阈值
    print("\n[4/4] 评估模型...")
    y_proba = model.predict_proba(X_test)[:, 1]
    print(f"  概率分布: min={y_proba.min():.4f}, max={y_proba.max():.4f}, mean={y_proba.mean():.4f}")

    best_f1, best_t = 0, 0.5
    for t in np.arange(0.1, 0.9, 0.05):
        preds = (y_proba > t).astype(int)
        f1 = f1_score(y_test, preds, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, t

    print(f"\n  最优阈值: {best_t:.2f}")
    y_pred = (y_proba > best_t).astype(int)

    print(f"  F1-Score: {best_f1:.4f}")
    print(f"\n  分类报告:")
    print(classification_report(y_test, y_pred, target_names=['Normal', 'Anomaly']))

    cm = confusion_matrix(y_test, y_pred)
    print(f"  混淆矩阵:")
    print(f"    TN={cm[0][0]}  FP={cm[0][1]}")
    print(f"    FN={cm[1][0]}  TP={cm[1][1]}")

    # 6. 特征重要性
    feature_cols = [f'E{i}' for i in range(1, 30)]
    importances = model.feature_importances_
    top_idx = np.argsort(importances)[::-1][:10]
    print(f"\n  Top 10 重要特征:")
    for i in top_idx:
        print(f"    {feature_cols[i]}: {importances[i]:.4f}")

    # 7. 保存模型
    joblib.dump(model, model_out)
    joblib.dump(scaler, scaler_out)
    print(f"\n  模型已保存: {model_out}")
    print(f"  Scaler已保存: {scaler_out}")


if __name__ == '__main__':
    main()
