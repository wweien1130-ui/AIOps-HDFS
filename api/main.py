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

app = FastAPI(title="AI Application API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model_cache = {
    "scaler": None,
    "model": None,
    "data": None,
    "templates": None
}

@app.on_event("startup")
async def startup_event():
    """启动时预加载模型和数据"""
    import joblib
    from model.mlp_model import load_mlp_model
    
    print("🚀 正在加载模型和数据，请稍候...")
    
    matrix_file = get_abs_path("HDFS_v1/preprocessed/Event_occurrence_matrix.csv")
    model_path = get_abs_path("LogMLP_Model.pth")
    scaler_path = get_abs_path("scaler.pkl")
    template_file = get_abs_path("HDFS_v1/preprocessed/HDFS.log_templates.csv")
    
    try:
        model_cache["scaler"] = joblib.load(scaler_path)
        print("✅ 标准化器加载完成")
        
        data = pd.read_csv(matrix_file)
        model_cache["data"] = data
        print(f"✅ 特征矩阵加载完成: {len(data)} 行")
        
        input_dim = data.shape[1] - 3
        model_cache["model"] = load_mlp_model(model_path, input_dim)
        print("✅ MLP模型加载完成")
        
        model_cache["templates"] = pd.read_csv(template_file)
        print("✅ 日志模板加载完成")
        
        print("🎉 所有资源加载完毕！")
    except Exception as e:
        print(f"❌ 启动时加载失败: {e}")
        raise


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
    使用预加载的模型和数据
    """
    from model.mlp_model import detect_anomalies
    
    if model_cache["model"] is None or model_cache["scaler"] is None:
        raise HTTPException(status_code=503, detail="模型尚未加载，请等待服务启动完成")

    try:
        results = detect_anomalies(
            model=model_cache["model"],
            scaler=model_cache["scaler"],
            data_file=None,
            threshold=request.threshold,
            template_file=None,
            data=model_cache["data"]
        )

        total_blocks = len(model_cache["data"])

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
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


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