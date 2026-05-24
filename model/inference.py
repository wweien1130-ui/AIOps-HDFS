import joblib
import pandas as pd
import os


def predict_anomaly(
    model_path: str,
    scaler_path: str,
    matrix_file: str,
    threshold: float = 0.3,
    max_samples: int = 10000
) -> dict:
    """
    使用训练好的模型进行异常预测
    
    Returns:
        dict: 包含预测结果的字典
    """
    # 加载数据
    print(f"[predict_anomaly] 加载数据: {matrix_file}")
    df = pd.read_csv(matrix_file)
    
    if len(df) > max_samples:
        print(f"[predict_anomaly] 数据量过大({len(df)}条)，采样前{max_samples}条")
        df = df.head(max_samples)
    
    # 提取特征
    feature_cols = [f'E{i}' for i in range(1, 30)]
    X = df[feature_cols].fillna(0)
    
    # 加载模型和标准化器
    print(f"[predict_anomaly] 加载模型: {model_path}")
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    
    # 预测
    print(f"[predict_anomaly] 执行预测...")
    X_scaled = scaler.transform(X)
    preds = model.predict(X_scaled)
    probs = model.predict_proba(X_scaled)[:, 1]
    
    # 整理结果
    df['prediction'] = ['Fail' if p == 1 else 'Success' for p in preds]
    df['anomaly_prob'] = probs
    
    anomalies = df[df['prediction'] == 'Fail'].sort_values('anomaly_prob', ascending=False)
    
    return {
        'df': df,
        'anomalies': anomalies,
        'total_anomalies': len(anomalies),
        'threshold': threshold
    }


def format_anomaly_report(result: dict) -> str:
    """格式化异常检测报告"""
    df = result['df']
    anomalies = result['anomalies']
    total_anomalies = result['total_anomalies']
    threshold = result['threshold']
    
    if total_anomalies == 0:
        return f"检测完成：在 {len(df)} 条记录中未发现异常（当前阈值 {threshold}）。系统状态正常。"
    
    anomaly_blocks = anomalies.head(10)
    
    output = f"### 🔍 异常检测摘要报告\n\n"
    output += f"- **总检测块数**: {len(df)}\n"
    output += f"- **发现异常块**: {total_anomalies}\n"
    output += f"- **异常比例**: {(total_anomalies / len(df)):.2%}\n"
    output += f"- **当前判定阈值**: {threshold}\n\n"
    output += f"---\n\n#### 🚨 前 10 条高危异常:\n\n"
    
    for i, (_, row) in enumerate(anomaly_blocks.iterrows(), 1):
        events_str = ""
        for j in range(1, 30):
            col = f'E{j}'
            if col in row and row[col] > 0:
                events_str += f"{col}:{int(row[col])} "
        output += f"**{i}. BlockID**: `{row['BlockId']}` | **异常概率**: `{row['anomaly_prob']:.4f}` | **标签**: {row['Label']} | **事件**: {events_str}\n"
    
    if total_anomalies > 10:
        output += f"\n> **提示**: 还有 {total_anomalies - 10} 条异常记录未在此列出。"
    
    return output
