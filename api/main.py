import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json

from utils.path_tool import get_abs_path

app = FastAPI(title="AI Application API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    threshold: float = 0.3


class AnalyzeResponse(BaseModel):
    total_blocks: int
    anomaly_count: int
    anomaly_ratio: float
    top_anomalies: List[Dict[str, Any]]


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
    """
    from model.mlp_model import detect_anomalies, load_mlp_model
    import joblib

    matrix_file = get_abs_path("HDFS_v1/preprocessed/Event_occurrence_matrix.csv")
    model_path = get_abs_path("LogMLP_Model.pth")
    scaler_path = get_abs_path("scaler.pkl")
    template_file = get_abs_path("HDFS_v1/preprocessed/HDFS.log_templates.csv")

    if not os.path.exists(matrix_file):
        raise HTTPException(status_code=400, detail="特征矩阵文件不存在，请先执行预处理")
    if not os.path.exists(model_path):
        raise HTTPException(status_code=400, detail="模型文件不存在，请先训练模型")
    if not os.path.exists(scaler_path):
        raise HTTPException(status_code=400, detail="标准化器文件不存在")

    try:
        scaler = joblib.load(scaler_path)
        model = load_mlp_model(model_path, input_dim=128)

        results = detect_anomalies(
            model=model,
            scaler=scaler,
            data_file=matrix_file,
            threshold=request.threshold,
            template_file=template_file
        )

        total_blocks = 0
        import pandas as pd
        data = pd.read_csv(matrix_file)
        total_blocks = len(data)

        anomaly_count = len(results)
        anomaly_ratio = anomaly_count / total_blocks if total_blocks > 0 else 0

        top_anomalies = sorted(results, key=lambda x: x['probability'], reverse=True)[:10]

        return AnalyzeResponse(
            total_blocks=total_blocks,
            anomaly_count=anomaly_count,
            anomaly_ratio=round(anomaly_ratio, 4),
            top_anomalies=top_anomalies
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    与LangGraph Agent对话，支持流式输出
    """
    from sse_starlette.sse import EventSourceResponse
    from agent.react_agent import ReactAgent
    import asyncio

    async def generate():
        try:
            agent = ReactAgent()
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
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
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