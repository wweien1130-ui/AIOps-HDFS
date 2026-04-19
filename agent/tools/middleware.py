from langchain.agents.middleware import wrap_tool_call, before_model, Runtime, dynamic_prompt,ModelRequest

from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langchain.agents import AgentState


from typing import Callable, Union
from langgraph.types import Command
from utils.logger_handler import logger
from utils.prompt_loader import load_report_prompts, load_system_prompts

@wrap_tool_call
def monitor_tool(
        request:ToolCallRequest,
        handler: Callable[[ToolCallRequest],ToolMessage | Command],
)-> ToolMessage | Command:
    logger.info(f"[tool monitor]执行工具:{request.tool_call['name']}")
    logger.info(f"[tool monitor]执行工具:{request.tool_call['args']}")

    try:
        result = handler(request)
        logger.info(f"[tool monitor]工具{request.tool_call['name']}执行成功")
        return result
    except Exception as e:
        logger.error(f"[tool monitor]工具{request.tool_call['name']}执行失败:{e}")
        raise e

@before_model
def log_before_model(
        state: AgentState,
        runtime: Runtime,
):
    messages = state.get("messages", [])
    logger.info(f"[log_before_model]即将调用模型，带有{len(messages)}个消息")
    return None


@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    return load_system_prompts()