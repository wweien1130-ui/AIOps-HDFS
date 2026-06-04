"""
Qwen（阿里云百炼）AI 聊天路由

提供 /api/openclaw/chat 等端点供前端调用。
底层直接调用阿里云百炼 DashScope API，绕过 OpenClaw agent 层。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from sse_starlette.sse import EventSourceResponse
import json

from api.services.qwen_service import (
    chat_completion,
    chat_stream,
    AVAILABLE_MODELS,
    QWEN_MODEL,
)

router = APIRouter(prefix="/api/openclaw", tags=["openclaw"])


class ChatRequest(BaseModel):
    messages: list[dict]
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7


class ChatResponse(BaseModel):
    content: str


class SimpleChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    max_tokens: int = 1024
    temperature: float = 0.7


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """与 AI 对话（非流式，直接调用通义千问 API）"""
    content = await chat_completion(
        messages=request.messages,
        model=request.model or QWEN_MODEL,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    if not content:
        raise HTTPException(status_code=503, detail="AI 服务未返回有效回复")
    return ChatResponse(content=content)


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """与 AI 对话（流式 SSE）"""

    async def generate():
        try:
            async for chunk in chat_stream(
                messages=request.messages,
                model=request.model or QWEN_MODEL,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            ):
                if chunk:
                    yield {"event": "message", "data": json.dumps({"content": chunk})}
            yield {"event": "done", "data": json.dumps({"status": "complete"})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(generate())


@router.post("/simple")
async def chat_simple(body: SimpleChatRequest):
    """简化的单轮对话接口（前端快速集成用）

    请求: {"message": "你好"}
    返回: {"content": "AI 回复..."}
    """
    content = await chat_completion(
        messages=[{"role": "user", "content": body.message}],
        model=body.model or QWEN_MODEL,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
    )
    return {"content": content}


@router.get("/models")
async def list_models():
    """列出可用的通义千问模型"""
    models = [
        {"id": mid, "name": name}
        for mid, name in AVAILABLE_MODELS.items()
    ]
    return {"models": models, "default": QWEN_MODEL}
