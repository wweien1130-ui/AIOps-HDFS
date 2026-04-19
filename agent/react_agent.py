from langchain.agents import create_agent
from model.factory import chat_models
from agent.tools.agent_tools import (
    rag_retrieve, get_current_time, calculate,
    preprocess_hdfs_logs, train_mlp_model, detect_anomaly, check_model_readiness
)
from utils.prompt_loader import load_system_prompts
from utils.logger_handler import logger
import traceback


class ReactAgent:
    def __init__(self):
        logger.info("[ReactAgent] 初始化 Agent...")
        logger.info(f"[ReactAgent] 模型类型: {type(chat_models)}")

        self.agent = create_agent(
            model=chat_models,
            system_prompt=load_system_prompts(),
            tools=[
                rag_retrieve, get_current_time, calculate,
                preprocess_hdfs_logs, train_mlp_model, detect_anomaly, check_model_readiness
            ]
        )
        logger.info("[ReactAgent] Agent 初始化完成")

    def execute_stream(self, query: str):
        logger.info(f"[execute_stream] 开始处理查询: {query}")
        input_dict = {"messages": [{"role": "user", "content": query}]}

        try:
            for chunk in self.agent.stream(input_dict, stream_mode="values"):
                if not isinstance(chunk, dict) or "messages" not in chunk:
                    continue

                messages = chunk.get("messages", [])
                if not messages:
                    continue

                latest_message = messages[-1]

                # 安全获取属性
                msg_type = getattr(latest_message, "type", None)
                msg_content = getattr(latest_message, "content", None)

                logger.info(f"[execute_stream] 消息类型: {msg_type}, 内容: {str(msg_content)[:50]}")

                if msg_type == "ai" and msg_content:
                    yield msg_content.strip()
                elif msg_type == "tool":
                    tool_name = getattr(latest_message, "name", "tool")
                    # 输出工具的实际返回内容
                    if msg_content:
                        yield msg_content
                    else:
                        yield f"\n[{tool_name} 执行完成]\n"
                else:
                    # 其他类型也打印出来
                    logger.info(f"[execute_stream] 未处理的消息类型: {msg_type}")

        except Exception as e:
            logger.error(f"[execute_stream] 执行出错: {e}")
            yield f"执行出错: {str(e)}"


if __name__ == "__main__":
    agent = ReactAgent()
    for chunk in agent.execute_stream("blk_12345 not found 错误怎么解决"):
        print(chunk, end="", flush=True)