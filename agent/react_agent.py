from langchain.agents import create_agent
from model.factory import chat_models
from agent.tools.agent_tools import (
    rag_retrieve, get_current_time, calculate,
    preprocess_hdfs_logs, train_mlp_model, detect_anomaly,check_model_readiness
)
from agent.tools.middleware import (monitor_tool, log_before_model, report_prompt_switch)
from utils.prompt_loader import load_system_prompts
class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_models,
            system_prompt=load_system_prompts(),
            tools=[
                rag_retrieve, get_current_time, calculate,
                preprocess_hdfs_logs, train_mlp_model, detect_anomaly,check_model_readiness
            ],
            middleware=[monitor_tool, log_before_model, report_prompt_switch]
        )

    def execute_stream(self, query: str):
        input_dict = {"messages": [{"role": "user", "content": query}]}

        # 使用 values 模式会返回每个步骤的完整 state
        for chunk in self.agent.stream(input_dict, stream_mode="values"):
            # 1. 彻底防线：检查 chunk 是否为有效字典，且包含 messages 键
            if not isinstance(chunk, dict) or "messages" not in chunk:
                continue

            messages = chunk.get("messages", [])
            if not messages:
                continue

            # 2. 获取最后一条消息
            latest_message = messages[-1]

            # 3. 严格类型检查：确保是 AI 消息且有内容
            # 使用 getattr 安全获取 type 和 content，防止对象属性缺失
            msg_type = getattr(latest_message, "type", None)
            msg_content = getattr(latest_message, "content", "")

            if msg_type == "ai" and msg_content:
                # 💡 只在有内容时 yield，避免 Streamlit 渲染空行
                yield msg_content.strip()

if __name__ == "__main__":
    agent = ReactAgent()
    for chunk in agent.execute_stream("blk_12345 not found 错误怎么解决"):
        print(chunk,end="",flush=True)