from langchain.agents import create_agent
from model.factory import chat_models
from agent.tools.agent_tools import (
    rag_retrieve, get_current_time, calculate,
    preprocess_hdfs_logs, train_mlp_model, detect_anomaly
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
                preprocess_hdfs_logs, train_mlp_model, detect_anomaly
            ],
            middleware=[monitor_tool, log_before_model, report_prompt_switch]
        )

    def execute_stream(self, query: str):
        input_dict = {"messages": [{"role": "user", "content": query}]}

        for chunk in self.agent.stream(input_dict, stream_mode="values"):
            latest_message = chunk["messages"][-1]
            # 核心修正：只有当最后一条消息是 AI 发出的，且有内容时才返回
            if latest_message.type == "ai" and latest_message.content:
                yield latest_message.content.strip()

if __name__ == "__main__":
    agent = ReactAgent()
    for chunk in agent.execute_stream("blk_12345 not found 错误怎么解决"):
        print(chunk,end="",flush=True)