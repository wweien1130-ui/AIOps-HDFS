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
    从ClickHouse获取异常检测数据，返回结构化JSON数据
    所有数据基于ClickHouse在线库，不再使用本地MLP模型
    """
    import yaml
    import clickhouse_connect

    config_dir = get_abs_path("config")
    ch_config_path = os.path.join(config_dir, "clickhouse.yaml")

    try:
        # 读取ClickHouse配置
        with open(ch_config_path, 'r', encoding='utf-8') as f:
            ch_config = yaml.safe_load(f)['clickhouse']['online']

        # 连接ClickHouse
        client = clickhouse_connect.get_client(
            host=ch_config['host'],
            port=ch_config.get('http_port', 8123),
            username=ch_config.get('username', 'default'),
            password=ch_config.get('password', '')
        )

        # 查询所有Block总数（从block_event_stats表）
        total_query = """
        SELECT COUNT(DISTINCT block_id) as total_blocks
        FROM online.block_event_stats
        """
        total_result = client.query_df(total_query)
        total_blocks = int(total_result.iloc[0]['total_blocks']) if not total_result.empty else 0

        # 查询异常Block（从anomaly_blocks表，过去1小时）
        anomaly_query = """
        SELECT
            block_id,
            anomaly_score,
            detected_at,
            E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
            E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
            E21, E22, E23, E24, E25, E26, E27, E28, E29
        FROM online.anomaly_blocks
        WHERE detected_at >= now() - INTERVAL 1 HOUR
        ORDER BY anomaly_score DESC
        LIMIT 100
        """
        anomalies_df = client.query_df(anomaly_query)

        anomaly_count = len(anomalies_df)
        anomaly_ratio = anomaly_count / total_blocks if total_blocks > 0 else 0

        # 计算E事件分布（从block_event_stats表）
        event_query = """
        SELECT
            event_id,
            SUM(cnt) as total_count
        FROM online.block_event_stats
        GROUP BY event_id
        ORDER BY total_count DESC
        """
        event_df = client.query_df(event_query)

        event_distribution = {}
        if not event_df.empty:
            for _, row in event_df.iterrows():
                event_distribution[row['event_id']] = int(row['total_count'])

        # 构建Top 10异常Block数据
        top_anomalies = []
        for idx, (_, row) in enumerate(anomalies_df.head(10).iterrows()):
            events = []
            for i in range(1, 30):
                col = f'E{i}'
                if col in row and row[col] > 0:
                    events.append({'event_id': col, 'count': int(row[col])})

            # 按count降序排列
            events.sort(key=lambda x: x['count'], reverse=True)

            top_anomalies.append({
                'block_id': row.get('block_id', ''),
                'probability': float(row['anomaly_score']),
                'label': '异常' if row['anomaly_score'] > 0.5 else '正常',
                'events': events
            })

        print(f"[api/analyze] 从ClickHouse查询完成: 总Block={total_blocks}, 异常={anomaly_count}")

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


@app.get("/api/realtime/total")
async def get_total_blocks():
    """
    获取ClickHouse中总Block数
    """
    import yaml
    import clickhouse_connect

    config_dir = get_abs_path("config")
    ch_config_path = os.path.join(config_dir, "clickhouse.yaml")

    try:
        with open(ch_config_path, 'r', encoding='utf-8') as f:
            ch_config = yaml.safe_load(f)['clickhouse']['online']

        client = clickhouse_connect.get_client(
            host=ch_config['host'],
            port=ch_config.get('http_port', 8123),
            username=ch_config.get('username', 'default'),
            password=ch_config.get('password', '')
        )

        query = """
        SELECT COUNT(DISTINCT block_id) as total_blocks
        FROM online.block_event_stats
        """
        result = client.query_df(query)
        total_blocks = int(result.iloc[0]['total_blocks']) if not result.empty else 0

        return {"total_blocks": total_blocks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/anomalies/recent")
async def get_recent_anomalies(hours: int = 1, limit: int = 100):
    """
    查询过去N小时内的异常数据
    """
    import yaml
    import clickhouse_connect

    config_dir = get_abs_path("config")
    ch_config_path = os.path.join(config_dir, "clickhouse.yaml")

    try:
        with open(ch_config_path, 'r', encoding='utf-8') as f:
            ch_config = yaml.safe_load(f)['clickhouse']['online']

        client = clickhouse_connect.get_client(
            host=ch_config['host'],
            port=ch_config.get('http_port', 8123),
            username=ch_config.get('username', 'default'),
            password=ch_config.get('password', '')
        )

        # 查询过去N小时的异常数据
        query = f"""
        SELECT
            block_id,
            anomaly_score,
            detected_at,
            E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
            E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
            E21, E22, E23, E24, E25, E26, E27, E28, E29
        FROM online.anomaly_blocks
        WHERE detected_at >= now() - INTERVAL {hours} HOUR
        ORDER BY anomaly_score DESC
        LIMIT {limit}
        """
        df = client.query_df(query)

        if df.empty:
            return {
                "success": True,
                "hours": hours,
                "anomaly_count": 0,
                "anomalies": [],
                "message": f"过去{hours}小时内没有异常数据"
            }

        # 构建返回数据
        anomalies = []
        for _, row in df.iterrows():
            events = []
            for i in range(1, 30):
                col = f'E{i}'
                if col in row and row[col] > 0:
                    events.append({'event_id': col, 'count': int(row[col])})

            anomalies.append({
                'block_id': row['block_id'],
                'anomaly_score': float(row['anomaly_score']),
                'detected_at': str(row['detected_at']),
                'events': events
            })

        return {
            "success": True,
            "hours": hours,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "message": f"查询到过去{hours}小时内的{len(anomalies)}个异常"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/anomalies/query")
async def query_anomalies(
    limit: int = 100,
    hours: int = None,
    minutes: int = None,
    seconds: int = None,
    days: int = None
):
    """
    查询异常数据（支持灵活的时间范围）

    参数说明：
    - limit: 返回结果数量限制
    - hours: 过去N小时
    - minutes: 过去N分钟
    - seconds: 过去N秒
    - days: 过去N天

    时间优先级：seconds > minutes > hours > days
    如果多个时间参数同时指定，使用最小的时间范围
    """
    import yaml
    import clickhouse_connect

    config_dir = get_abs_path("config")
    ch_config_path = os.path.join(config_dir, "clickhouse.yaml")

    try:
        with open(ch_config_path, 'r', encoding='utf-8') as f:
            ch_config = yaml.safe_load(f)['clickhouse']['online']

        client = clickhouse_connect.get_client(
            host=ch_config['host'],
            port=ch_config.get('http_port', 8123),
            username=ch_config.get('username', 'default'),
            password=ch_config.get('password', '')
        )

        # 构建时间过滤条件
        time_conditions = []
        if seconds is not None:
            time_conditions.append(f"detected_at >= now() - INTERVAL {seconds} SECOND")
        elif minutes is not None:
            time_conditions.append(f"detected_at >= now() - INTERVAL {minutes} MINUTE")
        elif hours is not None:
            time_conditions.append(f"detected_at >= now() - INTERVAL {hours} HOUR")
        elif days is not None:
            time_conditions.append(f"detected_at >= now() - INTERVAL {days} DAY")
        else:
            # 默认过去1小时
            time_conditions.append("detected_at >= now() - INTERVAL 1 HOUR")

        time_filter = " AND ".join(time_conditions)

        # 查询异常数据
        query = f"""
        SELECT
            block_id,
            anomaly_score,
            detected_at,
            E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
            E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
            E21, E22, E23, E24, E25, E26, E27, E28, E29
        FROM {ch_config['database']}.anomaly_blocks
        WHERE {time_filter}
        ORDER BY anomaly_score DESC
        LIMIT {limit}
        """
        anomalies_df = client.query_df(query)

        # 查询事件分布统计
        event_query = f"""
        SELECT
            event_id,
            sum(cnt) as total_count
        FROM {ch_config['database']}.block_event_stats
        WHERE last_updated >= now() - INTERVAL 1 HOUR
        GROUP BY event_id
        ORDER BY total_count DESC
        """
        event_df = client.query_df(event_query)

        event_distribution = {}
        if not event_df.empty:
            for _, row in event_df.iterrows():
                event_distribution[row['event_id']] = int(row['total_count'])

        # 构建返回数据
        anomalies = []
        for _, row in anomalies_df.iterrows():
            events = []
            for i in range(1, 30):
                col = f'E{i}'
                if col in row and row[col] > 0:
                    events.append({'event_id': col, 'count': int(row[col])})

            anomalies.append({
                'block_id': row['block_id'],
                'anomaly_score': float(row['anomaly_score']),
                'detected_at': str(row['detected_at']),
                'events': events
            })

        return {
            "success": True,
            "source": "clickhouse",
            "time_range": time_filter,
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "event_distribution": event_distribution
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@app.get("/api/realtime/anomalies")
async def get_realtime_anomalies(limit: int = 10, hours: int = None):
    """
    获取实时异常数据（从Redis/ClickHouse），包含事件分布统计
    支持时间过滤：hours参数指定查询过去N小时的数据
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
        if hours:
            # 如果指定了时间范围，只统计该时间范围内的事件
            event_query = f"""
            SELECT
                event_id,
                sum(cnt) as total_count
            FROM {ch_config['database']}.block_event_stats
            WHERE last_updated >= now() - INTERVAL {hours} HOUR
            GROUP BY event_id
            ORDER BY total_count DESC
            """
        else:
            # 否则统计所有事件
            event_query = f"""
            SELECT
                event_id,
                sum(cnt) as total_count
            FROM {ch_config['database']}.block_event_stats
            GROUP BY event_id
            ORDER BY total_count DESC
            """

        event_df = client.query_df(event_query)

        event_distribution = {}
        if not event_df.empty:
            for _, row in event_df.iterrows():
                event_distribution[row['event_id']] = int(row['total_count'])

        # 优先从Redis获取（仅当没有时间过滤时）
        if not hours:
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

        # 从ClickHouse获取（支持时间过滤）
        if hours:
            query = f"""
                SELECT
                block_id,
                anomaly_score,
                detected_at,
                E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
                E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
                E21, E22, E23, E24, E25, E26, E27, E28, E29
                FROM {ch_config['database']}.anomaly_blocks
                WHERE detected_at >= now() - INTERVAL {hours} HOUR
                ORDER BY anomaly_score DESC
                LIMIT {limit}
            """
        else:
            query = f"""
                SELECT
                block_id,
                anomaly_score,
                detected_at,
                E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
                E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
                E21, E22, E23, E24, E25, E26, E27, E28, E29
                FROM {ch_config['database']}.anomaly_blocks
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
            "message": "暂无异常数据"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取异常失败: {str(e)}")


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
