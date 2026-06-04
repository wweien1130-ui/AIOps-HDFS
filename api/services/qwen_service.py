"""
Qwen（阿里云百炼）AI 服务层

直接调用阿里云百炼 DashScope API（OpenAI 兼容格式），绕过 OpenClaw agent 层。
"""

import os
import json
import httpx
from typing import Optional

# DashScope API 配置
DASHSCOPE_API_KEY = os.getenv(
    "DASHSCOPE_API_KEY",
    "sk-358b05cf8c1a467ab7eca5b3e0583fa0",
)
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

# 可用的模型列表
AVAILABLE_MODELS = {
    "qwen-plus": "通义千问 Plus（推荐）",
    "qwen3.5-plus": "Qwen3.5 Plus",
    "qwen3.6-plus": "Qwen3.6 Plus",
    "qwen-turbo": "通义千问 Turbo（快速）",
    "qwen-max": "通义千问 Max（最强）",
}

# HTTP 客户端（连接池）
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=DASHSCOPE_BASE_URL,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
    return _client


async def chat_completion(
    messages: list[dict],
    *,
    model: str = QWEN_MODEL,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float = 0.9,
) -> str:
    """直接调用阿里云百炼 Qwen API 获取 AI 回复。

    Args:
        messages: OpenAI 格式的消息列表。
        model: 模型名称。
        max_tokens: 最大生成 token 数。
        temperature: 温度参数。
        top_p: Top-P 采样参数。

    Returns:
        AI 回复文本。
    """
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }

    client = _get_client()
    try:
        resp = await client.post("/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content or ""
    except httpx.TimeoutException:
        return "抱歉，AI 服务响应超时，请稍后重试。"
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("error", {}).get("message", "")
            return f"AI 服务暂时不可用（{e.response.status_code}）: {detail}"
        except Exception:
            return f"AI 服务暂时不可用（{e.response.status_code}），请稍后重试。"
    except Exception as e:
        return f"AI 服务调用失败: {e}"


async def chat_stream(
    messages: list[dict],
    *,
    model: str = QWEN_MODEL,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    top_p: float = 0.9,
):
    """流式调用 Qwen API。

    用法:
        async for chunk in chat_stream(messages):
            yield chunk
    """
    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": True,
    }

    client = _get_client()
    try:
        async with client.stream(
            "POST", "/chat/completions", headers=headers, json=payload
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line.removeprefix("data: ").strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta
                    except json.JSONDecodeError:
                        continue
    except Exception:
        yield "抱歉，AI 服务响应出错。"


async def close_client():
    """关闭 HTTP 客户端连接池"""
    global _client
    if _client:
        await _client.aclose()
        _client = None
