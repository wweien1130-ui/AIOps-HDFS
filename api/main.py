import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from utils.path_tool import get_abs_path
from agent.react_agent import ReactAgent

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
    """启动时预加载模型和数据（不强制要求模型存在）"""
    import joblib
    from model.mlp_model import load_mlp_model

    print("🚀 正在加载模型和数据，请稍候...")

    matrix_file = get_abs_path("HDFS_v1/preprocessed/Event_occurrence_matrix.csv")
    model_path = get_abs_path("LogMLP_Model.pth")
    scaler_path = get_abs_path("scaler.pkl")
    template_file = get_abs_path("HDFS_v1/preprocessed/HDFS.log_templates.csv")

    try:
        # 加载特征矩阵（必须）
        if os.path.exists(matrix_file):
            data = pd.read_csv(matrix_file)
            model_cache["data"] = data
            print(f"✅ 特征矩阵加载完成: {len(data)} 行")
        else:
            print("⚠️ 特征矩阵文件不存在，将在检测时预处理")

        # 加载标准化器（可选）
        if os.path.exists(scaler_path):
            model_cache["scaler"] = joblib.load(scaler_path)
            print("✅ 标准化器加载完成")
        else:
            print("⚠️ 标准化器不存在，将在首次检测时训练")

        # 加载日志模板（可选）
        if os.path.exists(template_file):
            model_cache["templates"] = pd.read_csv(template_file)
            print("✅ 日志模板加载完成")
        else:
            print("⚠️ 日志模板文件不存在")

        print("🎉 基础资源加载完毕！")
    except Exception as e:
        print(f"⚠️ 启动时部分资源加载失败: {e}")
        print("💡 系统仍可运行，检测时会自动训练模型")


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


@app.get("/")
async def root():
    return {"message": "AI Application API", "version": "1.0.0"}


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

    model_path = get_abs_path("block_anomaly_model.pkl")
    scaler_path = get_abs_path("scaler.pkl")
    matrix_file = get_abs_path("HDFS_v1/preprocessed/Event_occurrence_matrix.csv")

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

        # 筛选异常
        anomalies = data[data['prediction'] == 'Fail'].sort_values('anomaly_prob', ascending=False)

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
    上传原始日志文件，进行预处理和检测
    """
    import tempfile
    import shutil

    # 保存上传的文件
    upload_dir = get_abs_path("HDFS_v1")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)

    try:
        contents = await file.read()
        with open(file_path, 'wb') as f:
            f.write(contents)

        return {
            "success": True,
            "message": f"文件 {file.filename} 上传成功",
            "file_path": file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@app.get("/api/export")
async def export_anomalies_csv():
    """
    导出异常日志为CSV文件
    """
    import io
    from fastapi.responses import StreamingResponse

    if model_cache["model"] is None or model_cache["scaler"] is None:
        raise HTTPException(status_code=503, detail="模型尚未加载")

    try:
        from model.mlp_model import detect_anomalies

        results = detect_anomalies(
            model=model_cache["model"],
            scaler=model_cache["scaler"],
            data_file=None,
            threshold=0.3,
            template_file=None,
            data=model_cache["data"]
        )

        # 创建CSV
        df = pd.DataFrame(results)

        # 添加解决方案（从RAG获取）
        from agent.tools.agent_tools import rag_retrieve
        solutions = []
        for _, row in df.head(10).iterrows():
            try:
                solution = rag_retrieve.invoke(f"HDFS BlockId {row['block_id']} 异常解决方案")
                solutions.append(str(solution)[:200] if solution else "无")
            except:
                solutions.append("无")

        # 补齐解决方案列表
        while len(solutions) < len(df):
            solutions.append("")

        df['solution'] = solutions

        # 生成CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')

        csv_buffer.seek(0)

        return StreamingResponse(
            iter([csv_buffer.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=anomalies_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")