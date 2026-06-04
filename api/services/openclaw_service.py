"""
OpenClaw AI 服务层

提供两种方式调用 OpenClaw：
1. CLI 子进程方式（主要，验证可靠）
2. HTTP API 方式（备选）

CLI 方式通过 WSL 调用 openclaw agent 命令，返回结构化 JSON。
"""

import os
import json
import asyncio
from typing import Optional

# OpenClaw 配置
OPENCLAW_AGENT_ID = os.getenv("OPENCLAW_AGENT_ID", "api-agent")
OPENCLAW_CLI_TIMEOUT = int(os.getenv("OPENCLAW_CLI_TIMEOUT", "60"))

# WSL 中 OpenClaw 的路径
WSL_OPENCLAW_PATH = "/home/ubunto/.npm-global/bin/openclaw"
WSL_BASH = "wsl"


def _escape_message(msg: str) -> str:
    """转义消息中的特殊字符，确保安全的 shell 传递"""
    return msg.replace("'", "'\\''")


async def call_cli(
    message: str,
    *,
    agent_id: str = OPENCLAW_AGENT_ID,
    session_key: Optional[str] = None,
) -> str:
    """通过 WSL 调用 openclaw agent CLI 获取 AI 回复。

    Args:
        message: 用户消息。
        agent_id: 目标 Agent ID。
        session_key: 会话 key（用于保持多轮对话上下文）。

    Returns:
        AI 回复文本。
    """
    # 构建命令
    cmd_parts = [
        f"export PATH=\"{os.path.dirname(WSL_OPENCLAW_PATH)}:$PATH\"",
        f"openclaw agent --agent {agent_id} --message '{_escape_message(message)}' --json",
    ]
    if session_key:
        cmd_parts[1] = (
            f"openclaw agent --agent {agent_id} "
            f"--session-key '{_escape_message(session_key)}' "
            f"--message '{_escape_message(message)}' --json"
        )

    full_cmd = [WSL_BASH, "bash", "-c", " && ".join(cmd_parts)]

    try:
        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=OPENCLAW_CLI_TIMEOUT
        )

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            return f"AI 服务调用失败（退出码 {proc.returncode}）"

        # 解析 JSON 输出
        output = stdout.decode("utf-8", errors="replace").strip()
        data = json.loads(output)

        # 提取回复文本
        payloads = data.get("result", {}).get("payloads", [])
        if payloads:
            text = payloads[0].get("text", "")
            return text or ""

        return ""

    except asyncio.TimeoutError:
        return "AI 服务响应超时，请稍后重试。"
    except json.JSONDecodeError:
        return "AI 服务返回格式异常。"
    except FileNotFoundError:
        return "AI 服务（WSL/OpenClaw）不可用，请检查环境配置。"
    except Exception as e:
        return f"AI 服务调用异常: {e}"


async def chat_completion(
    messages: list[dict],
    *,
    agent_id: str = OPENCLAW_AGENT_ID,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    session_key: Optional[str] = None,
) -> str:
    """获取 AI 回复。

    将消息列表合并为一条完整提示发送给 OpenClaw CLI。
    如果消息列表只有一条 user 消息，直接发送；
    如果有多条（多轮对话），将历史拼接为带上下文的提示。

    Args:
        messages: OpenAI 格式的消息列表。
        agent_id: 目标 Agent ID。
        max_tokens: 最大生成 token 数。
        temperature: 温度参数。
        session_key: 会话 key。

    Returns:
        AI 回复文本。
    """
    # 取最后一条 user 消息作为直接输入
    # 历史上下文通过 session_key 由 OpenClaw 管理
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    if not last_user_msg:
        return ""

    return await call_cli(
        message=last_user_msg,
        agent_id=agent_id,
        session_key=session_key,
    )


async def chat_stream(
    messages: list[dict],
    *,
    agent_id: str = OPENCLAW_AGENT_ID,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    session_key: Optional[str] = None,
):
    """流式接口（当前暂时返回完整文本，后续可升级为真正的流式）"""
    text = await chat_completion(
        messages=messages,
        agent_id=agent_id,
        max_tokens=max_tokens,
        temperature=temperature,
        session_key=session_key,
    )
    if text:
        yield text
