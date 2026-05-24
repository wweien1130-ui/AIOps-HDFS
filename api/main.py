import sys
import os
import json

# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from utils.path_tool import get_abs_path
from agent.react_agent import ReactAgent


HDFS_BASE_DIR = get_abs_path("BackUp/Preprocess_File")

app = FastAPI(title="AI Application API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent 单例（保持对话记忆）
_agent_instance = None


def get_agent():
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReactAgent()
    return _agent_instance


model_cache = {
    "scaler": None,
    "model": None,
    "data": None,
    "templates": None
}


@app.on_event("startup")
async def startup_event():
    """只加载预测必需的模型和标准化器"""
    import joblib

    model_path = os.path.normpath(os.path.join(HDFS_BASE_DIR, "block_anomaly_model.pkl"))
    scaler_path = os.path.normpath(os.path.join(HDFS_BASE_DIR, "scaler.pkl"))
  
    print(f"scaler_path = {scaler_path}")
    print(f"文件存在: {os.path.exists(scaler_path)}")
    


    try:
        # 只加载预测必须的
        if os.path.exists(model_path):
            model_cache["model"] = joblib.load(model_path)
            print("✅ 模型加载完成")
        else:
            print("⚠️ 模型不存在，将在首次检测时训练")

        if os.path.exists(scaler_path):
            model_cache["scaler"] = joblib.load(scaler_path)
            print("✅ 标准化器加载完成")
        else:
            print("⚠️ 标准化器不存在，将在首次检测时训练")

        print("🎉 启动完成！")
    except Exception as e:
        print(f"⚠️ 启动加载失败: {e}")


class AnalyzeRequest(BaseModel):
    threshold: float = 0.3


class AnalyzeResponse(BaseModel):
    total_blocks: int
    anomaly_count: int
    anomaly_ratio: float
    top_anomalies: List[Dict[str, Any]]
    event_distribution: Dict[str, int] = {}


class ChatRequest(BaseModel):
    message: str


class OCRResponse(BaseModel):
    success: bool
    text: str
    confidence: Optional[float] = None
    error: Optional[str] = None


# @app.get("/")
# async def root():
#     return {"message": "AI Application API", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_logs(request: AnalyzeRequest):
    """
    执行MLP异常检测，返回结构化JSON数据
    使用sklearn模型
    """
    import joblib

    model_path = get_abs_path("BackUp/Preprocess_File/block_anomaly_model.pkl")
    scaler_path = get_abs_path("BackUp/Preprocess_File/scaler.pkl")
    matrix_file = get_abs_path("BackUp/File/Event_occurrence_matrix.csv")

    # 如果模型不存在，自动训练
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        print("[/api/analyze] 模型不存在，开始自动训练...")

        from model.mlp_model import train_mlp

        model_out, scaler_out, f1 = train_mlp(
            data_file=matrix_file,
            epochs=50,
            model_out=model_path,
            scaler_out=scaler_path
        )

        print(f"[api/analyze] 自动训练完成，F1: {f1}")

    # 加载sklearn模型
    try:
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        data = pd.read_csv(matrix_file)

        # 提取特征
        feature_cols = [f'E{i}' for i in range(1, 30)]
        X = data[feature_cols].fillna(0)

        # 预测
        X_scaled = scaler.transform(X)
        preds = model.predict(X_scaled)
        probs = model.predict_proba(X_scaled)[:, 1]

        data['prediction'] = ['Fail' if p == 1 else 'Success' for p in preds]
        data['anomaly_prob'] = probs

        # 筛选异常 - 按E事件总数降序排序，这样能看到更多不同的E模式
        anomalies = data[data['prediction'] == 'Fail'].copy()
        anomalies['total_events'] = anomalies[[f'E{i}' for i in range(1, 30)]].sum(axis=1)
        anomalies = anomalies.sort_values('total_events', ascending=False)

        total_blocks = len(data)
        anomaly_count = len(anomalies)
        anomaly_ratio = anomaly_count / total_blocks if total_blocks > 0 else 0

        # 计算异常块的E事件分布
        event_distribution = {f'E{i}': 0 for i in range(1, 30)}
        for _, row in anomalies.iterrows():
            for i in range(1, 30):
                col = f'E{i}'
                if col in row:
                    event_distribution[col] += int(row[col])

        # 打印前10个异常块的实际E值
        print(f"[api/analyze] 前10个异常的E值(按概率排序):")
        for idx, (_, row) in enumerate(anomalies.head(10).iterrows()):
            e5 = row.get('E5', 0)
            e9 = row.get('E9', 0)
            prob = row.get('anomaly_prob', 0)
            print(f"  [{idx}] Block={row.get('BlockId')}, prob={prob:.4f}, E5={e5}, E9={e9}, E11={row.get('E11', 0)}")

        # 返回前10个异常，包含E事件详情
        top_anomalies = []
        for idx, (_, row) in enumerate(anomalies.head(10).iterrows()):
            print(f"[api/analyze] 处理第{idx}个异常: {row.get('BlockId', '')}")
            events = []
            for i in range(1, 30):
                col = f'E{i}'
                if col in row and row[col] > 0:
                    events.append({'event_id': col, 'count': int(row[col])})
            # 按count降序排列
            events.sort(key=lambda x: x['count'], reverse=True)
            print(f"[api/analyze] 事件: {events[:5]}")

            top_anomalies.append({
                'block_id': row.get('BlockId', ''),
                'probability': float(row['anomaly_prob']),
                'label': row.get('Label', 'Unknown'),
                'events': events
            })

        return AnalyzeResponse(
            total_blocks=total_blocks,
            anomaly_count=anomaly_count,
            anomaly_ratio=round(anomaly_ratio, 4),
            top_anomalies=top_anomalies,
            event_distribution=event_distribution
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    与LangGraph Agent对话，支持流式输出（使用单例保持记忆）
    """
    from sse_starlette.sse import EventSourceResponse
    import asyncio

    async def generate():
        try:
            agent = get_agent()  # 使用单例，保持对话记忆
            for chunk in agent.execute_stream(request.message):
                if chunk:
                    yield {"event": "message", "data": json.dumps({"content": chunk})}
            yield {"event": "done", "data": json.dumps({"status": "complete"})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(generate())


@app.post("/api/ocr", response_model=OCRResponse)
async def ocr_image(file: UploadFile = File(...)):
    """
    使用EasyOCR或PaddleOCR提取图片中的文字
    """
    import tempfile
    import numpy as np
    from PIL import Image
    import io

    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        if image.mode != 'RGB':
            image = image.convert('RGB')

        image_array = np.array(image)

        ocr_text = ""
        confidence = None

        try:
            import easyocr
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=True)
            results = reader.readtext(image_array)

            if results:
                ocr_text = "\n".join([result[1] for result in results])
                confidence = sum([result[2] for result in results]) / len(results)
        except ImportError:
            pass

        if not ocr_text:
            try:
                from paddleocr import PaddleOCR
                ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
                result = ocr.ocr(image_array, cls=True)

                if result and result[0]:
                    lines = []
                    for line in result[0]:
                        if line and len(line) >= 2:
                            lines.append(line[1][0])
                    ocr_text = "\n".join(lines)
            except ImportError:
                pass

        if not ocr_text:
            return OCRResponse(
                success=False,
                text="",
                error="请安装 EasyOCR 或 PaddleOCR 库"
            )

        return OCRResponse(
            success=True,
            text=ocr_text,
            confidence=confidence
        )

    except Exception as e:
        return OCRResponse(
            success=False,
            text="",
            error=str(e)
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


@app.post("/api/upload")
async def upload_log_file(file: UploadFile = File(...)):
    """
    上传原始日志文件(离线批次)：
    - CSV文件：发送到Kafka offline topic
    - 其他文件：直接保存
    """
    import yaml
    import time
    import json
    import pandas as pd
    from io import StringIO
    from kafka import KafkaProducer

    # 读取Kafka配置
    config_dir = get_abs_path("config")
    kafka_config_path = os.path.join(config_dir, "kafka.yml")
    with open(kafka_config_path, 'r') as f:
        kafka_config = yaml.safe_load(f)['kafka']

    """ upload_dir = get_abs_path("HDFS_v1")  
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename) """

    try:
        contents = await file.read()
        filename_lower = file.filename.lower()

        # csv文件的处理方式 - 发送到Kafka offline topic
        if filename_lower.endswith('.csv'):
            # CSV: 发送到Kafka offline topic
            df = pd.read_csv(StringIO(contents.decode('utf-8')))
            batch_id = str(int(time.time()))

            producer = KafkaProducer(
                bootstrap_servers=kafka_config['bootstrap_servers'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks=1
            )
            topic = kafka_config['topics'].get('offline', 'hdfs-logs-offline')

            print(f"[Upload] Kafka连接: {kafka_config['bootstrap_servers']}, Topic: {topic}")
            print(f"[Upload] 开始发送 {len(df)} 条记录...")

            for _, row in df.iterrows():
                record = {'batch_id': batch_id, 'block_id': str(row.get('BlockId', row.get('block_id', '')))}
                for i in range(1, 30):
                    e_col = f'E{i}'
                    if e_col in row:
                        record[e_col] = int(row[e_col])
                producer.send(topic, value=record)

            producer.flush()
            print(f"[Upload] 发送完成")
            producer.close()

            return {
                "success": True,
                "message": f"CSV已发送到Kafka，批次: {batch_id}，共 {len(df)} 条",
                "batch_id": batch_id,
                "total_rows": len(df),
                "topic": topic
            }
        else:
            # 文本文件：直接发送到Kafka
            text_content = contents.decode('utf-8')
            batch_id = str(int(time.time()))

            producer = KafkaProducer(
                bootstrap_servers=kafka_config['bootstrap_servers'],
                value_serializer=lambda v: v.encode('utf-8'),
                acks=1
            )

            topic = kafka_config['topics'].get('offline', 'hdfs-logs-offline')
            print(f"[Upload] 文本文件发送到Kafka: {kafka_config['bootstrap_servers']}, Topic: {topic}")

            # 逐行发送到Kafka，格式：batch_id\t日志内容
            lines = text_content.strip().split('\n')
            for line in lines:
                if line.strip():
                    # 添加batch_id前缀，方便ClickHouse提取
                    message = f"{batch_id}\t{line}"
                    producer.send(topic, value=message)

            producer.flush()
            print(f"[Upload] 文本发送完成，共 {len(lines)} 行")
            producer.close()

            return {
                "success": True,
                "message": f"文本文件已发送到Kafka，批次: {batch_id}，共 {len(lines)} 行",
                "batch_id": batch_id,
                "total_rows": len(lines),
                "topic": topic
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


# @app.get("/api/offline/batches")
# async def get_offline_batches():
#     """
#     获取所有离线批次列表
#     """
#     import yaml
#     import clickhouse_connect

#     config_dir = get_abs_path("config")
#     ch_config_path = os.path.join(config_dir, "clickhouse.yaml")
#     with open(ch_config_path, 'r') as f:
#         ch_config = yaml.safe_load(f)['clickhouse']['offline']

#     try:
#         client = clickhouse_connect.get_client(
#             host=ch_config['host'],
#             port=ch_config.get('http_port', 8123),
#             username=ch_config.get('username', 'default'),
#             password=ch_config.get('password', '')
#         )

#         # 查询所有批次
#         query = """
#         SELECT batch_id, count() as block_count, min(detected_at) as first_seen, max(detected_at) as last_seen
#         FROM offline.block_event_stats
#         GROUP BY batch_id
#         ORDER BY batch_id DESC
#         LIMIT 20
#         """
#         result = client.query_df(query)
#         batches = result.to_dict('records')

#         # 查询每个批次的异常数量
#         anomaly_query = """
#         SELECT batch_id, count() as anomaly_count
#         FROM offline.anomaly_blocks
#         GROUP BY batch_id
#         """
#         anomaly_result = client.query_df(anomaly_query)
#         anomaly_counts = dict(zip(anomaly_result['batch_id'], anomaly_result['anomaly_count']))

#         for b in batches:
#             b['anomaly_count'] = anomaly_counts.get(b['batch_id'], 0)

#         return {"success": True, "batches": batches}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/realtime/anomalies")
async def get_realtime_anomalies(limit: int = 10):
    """
    获取实时异常数据（从Redis/ClickHouse），包含事件分布统计
    """
    import yaml
    import clickhouse_connect
    import redis

    config_dir = get_abs_path("config")

    # ClickHouse配置
    ch_config_path = os.path.join(config_dir, "clickhouse.yaml")
    with open(ch_config_path, 'r', encoding='utf-8') as f:
        ch_config = yaml.safe_load(f)['clickhouse']['online']

    # Redis配置
    redis_config_path = os.path.join(config_dir, "redis.yaml")
    with open(redis_config_path, 'r', encoding='utf-8') as f:
        redis_config = yaml.safe_load(f)['redis']

    try:
        # 连接ClickHouse获取事件分布统计
        client = clickhouse_connect.get_client(
            host=ch_config['host'],
            port=ch_config.get('http_port', 8123),
            username=ch_config.get('username', 'default'),
            password=ch_config.get('password', '')
        )

        # 获取事件分布统计（从block_event_stats表）
        event_query = """
        SELECT 
            event_id,
            sum(cnt) as total_count
        FROM {db}.block_event_stats
        GROUP BY event_id
        ORDER BY total_count DESC
        """.format(db=ch_config['database'])
        event_df = client.query_df(event_query)

        event_distribution = {}
        if not event_df.empty:
            for _, row in event_df.iterrows():
                event_distribution[row['event_id']] = int(row['total_count'])

        # 优先从Redis获取
        r = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            db=redis_config.get('db', 0),
            password=redis_config.get('password'),
            decode_responses=True
        )

        key_prefix = redis_config.get('key_prefix', 'anomaly:')
        top_key = key_prefix + redis_config['keys']['top']

        # 从Redis获取Top N
        top_anomalies = r.zrevrange(top_key, 0, limit - 1, withscores=True)

        if top_anomalies:
            results = []
            for block_id, score in top_anomalies:
                detail_key = key_prefix + redis_config['keys']['detail'] + block_id
                detail = r.hgetall(detail_key)
                results.append({
                    'block_id': block_id,
                    'anomaly_score': score,
                    **detail
                })
            return {
                "source": "redis",
                "anomalies": results,
                "event_distribution": event_distribution
            }

        # Redis无数据，从ClickHouse获取
        query = f"""
            SELECT 
            block_id, 
            anomaly_score, 
            detected_at,
            E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
            E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
            E21, E22, E23, E24, E25, E26, E27, E28, E29        FROM {ch_config['database']}.anomaly_blocks
        ORDER BY anomaly_score DESC
        LIMIT {limit}
        """
        df = client.query_df(query)

        if not df.empty:
            return {
                "source": "clickhouse",
                "anomalies": df.to_dict('records'),
                "event_distribution": event_distribution
            }

        return {
            "source": "none",
            "anomalies": [],
            "event_distribution": event_distribution,
            "message": "暂无实时异常数据"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实时异常失败: {str(e)}")


# @app.post("/api/offline/process/{batch_id}")
# async def process_offline_batch(batch_id: str):
#     """
#     处理指定batch_id的离线数据（运行预测）
#     """
#     import subprocess
#     import threading

#     def run_predictor():
#         try:
#             # 调用离线预测脚本
#             script_path = get_abs_path("scripts/offline/predictor.py")
#             subprocess.run(['python', script_path], check=True)
#         except Exception as e:
#             print(f"离线预测失败: {e}")

#     # 异步执行
#     threading.Thread(target=run_predictor, daemon=True).start()

#     return {
#         "success": True,
#         "message": f"开始处理批次 {batch_id}，请稍后查询结果"
#     }


@app.get("/api/export")
async def export_anomalies_csv():
    """
    导出异常日志为CSV文件
    """
    import io
    import yaml
    import clickhouse_connect
    import redis
    from fastapi.responses import StreamingResponse

    try:
        config_dir = get_abs_path("config")

        # ClickHouse配置
        with open(os.path.join(config_dir, "clickhouse.yaml"), 'r', encoding='utf-8') as f:
            ch_config = yaml.safe_load(f)['clickhouse']['online']

        # Redis配置
        with open(os.path.join(config_dir, "redis.yaml"), 'r', encoding='utf-8') as f:
            redis_config = yaml.safe_load(f)['redis']

        # 连接Redis获取Top 10异常
        r = redis.Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            db=redis_config.get('db', 0),
            password=redis_config.get('password'),
            decode_responses=True
        )

        key_prefix = redis_config.get('key_prefix', 'anomaly:')
        top_key = key_prefix + redis_config['keys']['top']
        top_anomalies = r.zrevrange(top_key, 0, 9, withscores=True)

        if top_anomalies:
            results = []
            for block_id, score in top_anomalies:
                detail_key = key_prefix + redis_config['keys']['detail'] + block_id
                detail = r.hgetall(detail_key)
                row = {
                    'block_id': block_id,
                    'anomaly_score': score,
                    **detail
                }
                results.append(row)
            df = pd.DataFrame(results)
        else:
            # Redis无数据，从ClickHouse获取
            client = clickhouse_connect.get_client(
                host=ch_config['host'],
                port=ch_config.get('http_port', 8123),
                username=ch_config.get('username', 'default'),
                password=ch_config.get('password', '')
            )
            query = f"""
            SELECT block_id, anomaly_score, detected_at,
                E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
                E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
                E21, E22, E23, E24, E25, E26, E27, E28, E29
            FROM {ch_config['database']}.anomaly_blocks
            ORDER BY anomaly_score DESC
            LIMIT 100
            """
            df = client.query_df(query)

        # 确保所有E事件列为数值类型
        for i in range(1, 30):
            e_col = f'E{i}'
            if e_col in df.columns:
                df[e_col] = pd.to_numeric(df[e_col], errors='coerce').fillna(0).astype(int)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        csv_content = csv_buffer.getvalue()

        # 添加UTF-8 BOM，确保Windows Excel正确识别中文
        bom = '\ufeff'
        csv_content = bom + csv_content

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename=anomalies_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
