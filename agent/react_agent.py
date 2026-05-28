"""
ReActAgent - 基于 LangGraph Supervisor 的多智能体系统

架构:
  Supervisor (LLM意图分类) → Router (纯Python路由) → 子Agent (领域执行)
                                                       ↓
                                                 Validator (结果检查)
                                                       ↓
                                               ErrorHandler (纠错重试 → 降级)
"""

import re
import traceback
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from model.factory import chat_models
from agent.tools.agent_tools import (
    rag_retrieve, get_current_time, calculate,
    preprocess_hdfs_logs, train_mlp_model, detect_anomaly, check_model_readiness,
    list_offline_batches, list_offline_anomalies, process_offline_batch,
    get_realtime_anomalies, start_realtime_service, stop_realtime_service,
)
from utils.prompt_loader import (
    load_system_prompts,
    load_supervisor_prompt,
    load_diagnosis_prompt,
    load_data_prompt,
)
from utils.logger_handler import logger


# ============================================================
# State Schema
# ============================================================

class SupervisorState(TypedDict):
    """多智能体 Supervisor 图的全局状态。"""
    messages:             Annotated[list, add_messages]
    intent:               str
    confidence:           float
    retry_count:          int
    error_type:           str
    next_agent_override:  str


# ============================================================
# ReactAgent
# ============================================================

class ReactAgent:

    def __init__(self):
        logger.info("[ReactAgent] 初始化多智能体 Supervisor 系统...")

        # --- 加载提示词 ---
        diagnosis_prompt = load_diagnosis_prompt()
        data_prompt = load_data_prompt()
        fallback_prompt = load_system_prompts()

        # --- 构建四个子智能体 ---
        logger.info("[ReactAgent] 构建 Diagnosis 子Agent...")
        self.diagnosis_agent = create_agent(
            model=chat_models,
            system_prompt=diagnosis_prompt or fallback_prompt,
            tools=[rag_retrieve, detect_anomaly, check_model_readiness,
                   list_offline_anomalies,
                   preprocess_hdfs_logs, train_mlp_model],
        )

        logger.info("[ReactAgent] 构建 Data 子Agent...")
        self.data_agent = create_agent(
            model=chat_models,
            system_prompt=data_prompt or fallback_prompt,
            tools=[preprocess_hdfs_logs, train_mlp_model,
                   process_offline_batch, list_offline_batches],
        )

        logger.info("[ReactAgent] 构建 Monitor 子Agent（纯Python，零LLM延迟）...")
        # MonitorAgent 不需要 LLM — 直接根据关键词执行工具，避免 LLM 调用卡住聊天
        self._monitor_tools = {
            "start": start_realtime_service,
            "stop": stop_realtime_service,
            "query": get_realtime_anomalies,
        }

        logger.info("[ReactAgent] 构建 General 子Agent...")
        self.general_agent = create_agent(
            model=chat_models,
            system_prompt="你是一个通用助手。",
            tools=[get_current_time, calculate],
        )

        # --- 构建 Supervisor 图 ---
        logger.info("[ReactAgent] 构建 Supervisor 状态图...")
        self.graph = self._build_graph()

        logger.info("[ReactAgent] 多智能体系统初始化完成")

    # ============================================================
    # 图构建
    # ============================================================

    def _build_graph(self):
        builder = StateGraph(SupervisorState)

        # 注册所有节点
        builder.add_node("supervisor",       self._supervisor_node)
        builder.add_node("diagnosis_agent",  self._make_agent_node(self.diagnosis_agent, "Diagnosis"))
        builder.add_node("data_agent",       self._make_agent_node(self.data_agent, "Data"))
        builder.add_node("monitor_agent",    self._monitor_node)
        builder.add_node("general_agent",    self._make_agent_node(self.general_agent, "General"))
        builder.add_node("result_validator", self._validate_result)
        builder.add_node("error_handler",    self._handle_error)
        builder.add_node("fallback",         self._fallback_node)

        # 边：START → Supervisor
        builder.add_edge(START, "supervisor")

        # 条件边：Supervisor → 子Agent 或 Fallback
        builder.add_conditional_edges("supervisor", self._route_intent, {
            "diagnosis_agent": "diagnosis_agent",
            "data_agent":      "data_agent",
            "monitor_agent":   "monitor_agent",
            "general_agent":   "general_agent",
            "fallback":        "fallback",
        })

        # 所有子Agent → Validator
        for name in ["diagnosis_agent", "data_agent", "monitor_agent", "general_agent"]:
            builder.add_edge(name, "result_validator")

        # 条件边：Validator → END 或 ErrorHandler
        builder.add_conditional_edges("result_validator", self._check_result, {
            "ok":    END,
            "error": "error_handler",
        })

        # 条件边：ErrorHandler → Supervisor（重试）或 Fallback
        builder.add_conditional_edges("error_handler", self._decide_retry, {
            "retry":    "supervisor",
            "fallback": "fallback",
        })

        # Fallback → END
        builder.add_edge("fallback", END)

        return builder.compile()

    # ============================================================
    # Supervisor 节点 —— 唯一调用 LLM 做意图分发的节点
    # ============================================================

    def _supervisor_node(self, state: SupervisorState) -> dict:
        # 提取最新的用户消息内容
        last_user_content = ""
        for msg in reversed(state["messages"]):
            role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "type", "")
            if role in ("user", "human"):
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                last_user_content = content
                break

        if not last_user_content:
            logger.warning("[Supervisor] 未找到用户消息，回退到 general")
            return {"intent": "general", "confidence": 0.5, "next_agent_override": ""}

        logger.info(f"[Supervisor] 分析意图: {last_user_content[:60]}...")

        try:
            response = chat_models.invoke([
                SystemMessage(content=load_supervisor_prompt()),
                HumanMessage(content=last_user_content),
            ])
            intent, confidence = self._parse_intent(response.content)
        except Exception as e:
            logger.error(f"[Supervisor] LLM调用失败: {e}")
            intent, confidence = "general", 0.5

        logger.info(f"[Supervisor] 意图={intent}  置信度={confidence:.2f}")
        return {"intent": intent, "confidence": confidence, "next_agent_override": ""}

    @staticmethod
    def _parse_intent(text: str) -> tuple:
        """从 LLM 响应中解析意图标签和置信度。"""
        text = text.strip()

        # 标准格式: INTENT: DIAGNOSIS | CONFIDENCE: 0.95
        match = re.search(r'INTENT:\s*(\w+)', text, re.IGNORECASE)
        raw = match.group(1).upper() if match else ""

        conf_match = re.search(r'CONFIDENCE:\s*([\d.]+)', text)
        try:
            confidence = float(conf_match.group(1)) if conf_match else 0.7
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.7

        intent_map = {
            "DIAGNOSIS": "diagnosis",
            "DATA":      "data",
            "MONITOR":   "monitor",
            "GENERAL":   "general",
        }
        intent = intent_map.get(raw, "")
        if intent:
            return intent, confidence

        # 回退：关键词匹配
        t = text.lower()
        if any(kw in t for kw in ["diagnosis", "诊断", "检测", "异常", "错误", "blk_"]):
            return "diagnosis", 0.6
        if any(kw in t for kw in ["data", "数据", "训练", "预处理", "模型", "批次", "batch"]):
            return "data", 0.6
        if any(kw in t for kw in ["monitor", "监控", "实时", "在线", "启动服务", "停止服务"]):
            return "monitor", 0.6
        return "general", 0.5

    # ============================================================
    # Router —— 纯 Python 路由（可包含 ErrorHandler 强制覆盖）
    # ============================================================

    @staticmethod
    def _route_intent(state: SupervisorState) -> str:
        override = state.get("next_agent_override", "")
        if override:
            logger.info(f"[Router] ★ ErrorHandler 强制路由 → {override}")
            return override

        intent = state.get("intent", "general")
        route_map = {
            "diagnosis": "diagnosis_agent",
            "data":      "data_agent",
            "monitor":   "monitor_agent",
            "general":   "general_agent",
        }
        target = route_map.get(intent, "fallback")
        logger.info(f"[Router] {intent} → {target}")
        return target

    # ============================================================
    # 子Agent 节点工厂 —— 用闭包为每个子Agent创建节点函数
    # ============================================================

    @staticmethod
    def _make_agent_node(agent, name: str):
        """返回一个 LangGraph 节点函数，内部调用子Agent并返回增量消息。"""
        def node_fn(state: SupervisorState) -> dict:
            logger.info(f"[{name}Agent] 开始执行...")
            try:
                result = agent.invoke({"messages": state["messages"]})
                existing_count = len(state["messages"])
                all_msgs = result.get("messages", [])
                new_msgs = all_msgs[existing_count:]
                logger.info(f"[{name}Agent] 完成，新增 {len(new_msgs)} 条消息")
                return {"messages": new_msgs}
            except Exception as e:
                logger.error(f"[{name}Agent] 执行失败: {e}")
                return {"messages": [AIMessage(
                    content=f"{name}Agent 执行出错: {str(e)}"
                )]}

        return node_fn

    # ============================================================
    # MonitorAgent 节点 —— 纯Python，不走LLM，零延迟
    # ============================================================

    def _monitor_node(self, state: SupervisorState) -> dict:
        """监控操作（开启/关闭/查询）直接执行工具，不经过 LLM。
        因为监控意图已经由 Supervisor 确认，执行层面只需关键词匹配即可。"""
        last_content = ""
        for msg in reversed(state["messages"]):
            role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "type", "")
            if role in ("user", "human"):
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                last_content = content
                break

        logger.info(f"[MonitorAgent] 直接执行: {last_content[:60]}...")

        if any(kw in last_content for kw in ["开启", "启动", "在线模式", "在线监测", "实时监控"]):
            result_str = self._monitor_tools["start"].invoke({})
        elif any(kw in last_content for kw in ["关闭", "停止"]):
            result_str = self._monitor_tools["stop"].invoke({})
        else:
            # 默认为查询
            result_str = self._monitor_tools["query"].invoke({"limit": 10})

        logger.info(f"[MonitorAgent] 完成，结果长度={len(str(result_str))}")
        return {"messages": [AIMessage(content=str(result_str))]}

    # ============================================================
    # Result Validator —— 纯 Python 错误检测
    # ============================================================

    @staticmethod
    def _validate_result(state: SupervisorState) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return {"error_type": ""}

        last_msg = messages[-1]
        content = ""
        if isinstance(last_msg, dict):
            content = last_msg.get("content", "")
        else:
            content = getattr(last_msg, "content", "") or ""

        content_str = str(content)

        ERROR_PATTERNS = [
            ("模型文件不存在",    "model_not_ready"),
            ("矩阵文件不存在",    "data_not_ready"),
            ("文件缺失",          "data_not_ready"),
            ("组件不全",          "data_not_ready"),
            ("Connection refused", "connection_failed"),
            ("连接失败",          "connection_failed"),
            ("timeout",           "timeout"),
            ("超时",              "timeout"),
            ("FileNotFoundError", "file_missing"),
        ]

        for pattern, err_type in ERROR_PATTERNS:
            if pattern.lower() in content_str.lower():
                logger.warning(f"[Validator] 检测到错误 → {err_type}")
                return {"error_type": err_type}

        return {"error_type": ""}

    @staticmethod
    def _check_result(state: SupervisorState) -> str:
        return "error" if state.get("error_type", "") else "ok"

    # ============================================================
    # Error Handler —— 纠错重试机制
    # ============================================================

    @staticmethod
    def _handle_error(state: SupervisorState) -> dict:
        retry = state.get("retry_count", 0) + 1
        error_type = state.get("error_type", "unknown")
        logger.warning(f"[ErrorHandler] 第 {retry} 次重试  错误类型={error_type}")

        # 数据/模型缺失 → 强制路由到 Data Agent
        reroute_map = {
            "model_not_ready":   "data_agent",
            "data_not_ready":    "data_agent",
            "file_missing":      "data_agent",
        }
        next_agent = reroute_map.get(error_type, "")

        return {
            "retry_count":          retry,
            "error_type":           "",
            "next_agent_override":  next_agent,
        }

    @staticmethod
    def _decide_retry(state: SupervisorState) -> str:
        if state.get("retry_count", 0) >= 3:
            logger.warning("[ErrorHandler] 已达最大重试次数 → fallback")
            return "fallback"
        return "retry"

    # ============================================================
    # Fallback
    # ============================================================

    @staticmethod
    def _fallback_node(_state: SupervisorState) -> dict:
        logger.info("[Fallback] 执行降级处理")
        return {"messages": [AIMessage(
            content="抱歉，我暂时无法完成这个请求。请尝试：\n"
                    "1. 换个方式描述您的问题\n"
                    "2. 检查系统组件（ClickHouse / Redis / Ollama）是否正常运行\n"
                    "3. 联系管理员查看系统日志"
        )]}

    # ============================================================
    # 流式执行 —— 接口完全兼容 app.py
    # ============================================================

    def execute_stream(self, query: str):
        logger.info(f"[execute_stream] 开始处理: {query}")

        input_dict = {
            "messages":             [{"role": "user", "content": query}],
            "intent":               "",
            "confidence":           0.0,
            "retry_count":          0,
            "error_type":           "",
            "next_agent_override":  "",
        }

        yielded_count = 1  # 用户消息已算一条，跳过

        try:
            for chunk in self.graph.stream(input_dict, stream_mode="values"):
                if not isinstance(chunk, dict):
                    continue
                if "messages" not in chunk:
                    continue

                messages = chunk.get("messages", [])
                if len(messages) <= yielded_count:
                    continue

                # 逐条输出新增消息
                for msg in messages[yielded_count:]:
                    if msg is None:
                        continue

                    if isinstance(msg, dict):
                        msg_type = msg.get("type")
                        msg_content = msg.get("content", "")
                        tool_name = msg.get("name", "tool")
                    else:
                        msg_type = getattr(msg, "type", None)
                        msg_content = getattr(msg, "content", "") or ""
                        tool_name = getattr(msg, "name", "tool")

                    if msg_type == "ai" and msg_content:
                        yield msg_content.strip()
                    elif msg_type == "tool":
                        if msg_content:
                            yield str(msg_content)
                        else:
                            yield f"\n[{tool_name} 执行完成]\n"

                yielded_count = len(messages)

        except Exception as e:
            logger.error(f"[execute_stream] 执行出错: {e}")
            logger.error(f"[execute_stream] {traceback.format_exc()}")
            yield f"执行出错: {str(e)}"


# ============================================================
# 自测
# ============================================================

if __name__ == "__main__":
    agent = ReactAgent()
    print("=" * 60)
    print("多智能体 Supervisor 系统测试")
    print("=" * 60)

    for q in ["帮我检测HDFS异常", "现在几点"]:
        print(f"\n>>> 用户: {q}")
        print("---")
        for chunk in agent.execute_stream(q):
            print(chunk, end="", flush=True)
        print()
