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
from langgraph.types import Command
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from model.factory import chat_models
from agent.tools.agent_tools import (
    rag_retrieve, get_current_time, calculate,
    preprocess_hdfs_logs, train_mlp_model, detect_anomaly, check_model_readiness,
    list_offline_batches, list_offline_anomalies, process_offline_batch,
    get_realtime_anomalies, start_realtime_service, stop_realtime_service,
    # 运维工具
    check_system_status, view_system_config, cleanup_redis_data,
    check_service_status, restart_service, delete_offline_batch,
)
from utils.prompt_loader import (
    load_system_prompts,    #系统提示词
    load_supervisor_prompt,  #调度器
    load_diagnosis_prompt,   #诊断器
    load_data_prompt,        #数据处理器
    load_ops_prompt,         #运维处理器
)
from utils.logger_handler import logger


# ============================================================
# State Schema
# ============================================================

class SupervisorState(TypedDict):
    """多智能体 Supervisor 图的全局状态。"""
    messages:             Annotated[list, add_messages]  #消息列表
    intent:               str    #意图
    confidence:           float  #置信度
    retry_count:          int    #重试次数
    error_type:           str    #错误类型
    next_agent_override:  str    #下一个智能体覆盖
    pending_operation:    str    #待确认的操作
    pending_params:       dict   #待确认的操作参数


# ============================================================
# ReactAgent
# ============================================================

class ReactAgent:

    def __init__(self):
        logger.info("[ReactAgent] 初始化多智能体 Supervisor 系统...")

        # 存储对话状态
        self.conversation_state = {
            "messages": [],
            "pending_operation": "",
            "pending_params": {}
        }

        # --- 加载提示词 ---
        diagnosis_prompt = load_diagnosis_prompt()
        data_prompt = load_data_prompt()
        ops_prompt = load_ops_prompt()
        fallback_prompt = load_system_prompts()

        # --- 构建四个子智能体 ---
        logger.info("[ReactAgent] 构建 Diagnosis 子Agent...")
        self.diagnosis_agent = create_agent(
            model=chat_models,
            system_prompt=diagnosis_prompt or fallback_prompt,
            tools=[
                # 离线批次相关（补充完整）
                list_offline_batches,
                list_offline_anomalies,
                process_offline_batch,
                # 核心检测
                detect_anomaly,
                # 知识检索
                rag_retrieve,
                # 预处理/训练/状态检查
                preprocess_hdfs_logs,
                train_mlp_model,
                check_model_readiness,
    ],
)
        logger.info("[ReactAgent] 构建 Data 子Agent...")
        self.data_agent = create_agent(
            model=chat_models,
            system_prompt=data_prompt or fallback_prompt,
            tools=[
                # 数据处理
                preprocess_hdfs_logs,
                train_mlp_model,
                # 批次管理
                process_offline_batch,
                list_offline_batches,
                # 异常查询（补充）
                list_offline_anomalies,
    ],
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
            system_prompt="""你是一个专业的HDFS智能助手的中枢调度员。

                            你的职责：
                            1. 回答关于时间、数学计算等通用问题
                            2. 当用户询问你的身份时，回答：
                            "我是HDFS智能诊断系统，集成了异常检测、知识检索、实时监控等功能。
                                如果需要检测异常或查询知识，请直接告诉我您的需求。"
                            3. 如果用户的问题涉及HDFS，主动引导到对应功能

                            可用工具：
                            - get_current_time: 获取当前时间
                            - calculate: 数学计算
                            """,
            tools=[get_current_time, calculate],
        )

        logger.info("[ReactAgent] 构建 Ops 子Agent...")
        self.ops_agent = create_agent(
            model=chat_models,
            system_prompt=ops_prompt or fallback_prompt,
            tools=[
                # 系统状态检查
                check_system_status,
                # 配置查看（需要确认）
                view_system_config,
                # 数据清理（需要确认）
                cleanup_redis_data,
                # 服务管理（需要确认）
                check_service_status,
                restart_service,
                # 数据删除（需要确认）
                delete_offline_batch,
            ],
        )

        # 存储待确认的操作
        self.pending_ops = {}

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
        builder.add_node("ops_agent",        self._ops_agent_node)
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
            "ops_agent":       "ops_agent",
            "fallback":        "fallback",
        })

        # 所有子Agent → Validator
        for name in ["diagnosis_agent", "data_agent", "monitor_agent", "general_agent", "ops_agent"]:
            builder.add_edge(name, "result_validator")

        # 条件边：Validator → END 或 ErrorHandler
        builder.add_conditional_edges("result_validator", self._check_result, {
            "ok":    END,
            "error": "error_handler",
        })

        # ErrorHandler 内部用 Command(goto=...) 直接跳转，此处仅兜底
        builder.add_edge("error_handler", "fallback")

        # Fallback → END
        builder.add_edge("fallback", END)

        return builder.compile()

    # ============================================================
    # Supervisor 节点 —— 唯一调用 LLM 做意图分发的节点
    # ============================================================

    def _supervisor_node(self, state: SupervisorState) -> dict:
        next_agent = state.get("next_agent_override", "")
        if next_agent:
            return {"intent": next_agent, "confidence": 1.0, "next_agent_override": ""}

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

        # 检查用户消息是否是确认词
        is_confirm = last_user_content.strip().lower() in ["confirm", "确认", "是", "yes", "y"]

        # 检查是否有待确认的操作（从历史消息中查找）
        pending_operation = state.get("pending_operation", "")
        if not pending_operation:
            # 从历史消息中查找是否有待确认的操作提示
            logger.info(f"[Supervisor] 检查历史消息，共 {len(state['messages'])} 条")
            for i, msg in enumerate(reversed(state["messages"])):
                # 检查消息类型
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                else:
                    role = getattr(msg, "type", "")
                    content = getattr(msg, "content", "")

                logger.info(f"[Supervisor] 检查消息 {i}: role={role}, content={content[:50]}...")

                if role == "ai" or role == "assistant":
                    if "确认" in content or "confirm" in content.lower():
                        logger.info(f"[Supervisor] 找到确认消息: {content[:50]}...")
                        # 提取操作类型
                        if "配置" in content:
                            pending_operation = "view_config"
                        elif "清理" in content or "Redis" in content:
                            pending_operation = "cleanup_data"
                        elif "服务状态" in content or "服务" in content:
                            pending_operation = "check_service"
                        elif "重启" in content:
                            pending_operation = "restart_service"
                        elif "删除" in content:
                            pending_operation = "delete_batch"
                        break

        if is_confirm and pending_operation:
            logger.info(f"[Supervisor] 用户确认操作: {pending_operation}")
            return {"intent": "ops", "confidence": 1.0, "next_agent_override": "ops_agent"}

        # 如果是确认词但没有待确认操作，当作通用问题处理
        if is_confirm:
            logger.info(f"[Supervisor] 确认词但无待确认操作，当作通用问题")
            return {"intent": "general", "confidence": 0.8, "next_agent_override": ""}

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
            "OPS":       "ops",
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
        if any(kw in t for kw in ["运维", "系统状态", "配置", "清理", "重启服务", "检查状态", "服务管理"]):
            return "ops", 0.6
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
            "ops":       "ops_agent",
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

        if any(kw in last_content for kw in ["关闭", "停止"]):
            result_str = self._monitor_tools["stop"].invoke({})
        elif any(kw in last_content for kw in ["开启", "启动", "在线模式", "在线监测", "实时监控"]):
            result_str = self._monitor_tools["start"].invoke({})
        else:
            result_str = self._monitor_tools["query"].invoke({"limit": 10})

        logger.info(f"[MonitorAgent] 完成，结果长度={len(str(result_str))}")
        return {"messages": [AIMessage(content=str(result_str))]}

    # ============================================================
    # OpsAgent 节点 —— 运维操作，支持二次确认
    # ============================================================

    def _ops_agent_node(self, state: SupervisorState) -> dict:
        """处理运维操作，支持二次确认机制"""
        # 获取最新的用户消息
        last_content = ""
        for msg in reversed(state["messages"]):
            role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "type", "")
            if role in ("user", "human"):
                content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
                last_content = content
                break

        logger.info(f"[OpsAgent] 处理请求: {last_content[:60]}...")

        # 检查是否有待确认的操作
        pending_operation = state.get("pending_operation", "")

        # 如果用户输入的是确认词，且有待确认的操作
        is_confirm = last_content.strip().lower() in ["confirm", "确认", "是", "yes", "y"]
        if is_confirm and pending_operation:
            logger.info(f"[OpsAgent] 执行待确认操作: {pending_operation}")

            # 执行待确认的操作 - 需要修改消息内容为实际的操作命令
            # 创建新的消息列表，将确认词替换为实际的操作
            messages = state["messages"].copy()
            # 找到用户的消息并替换内容
            for i in range(len(messages) - 1, -1, -1):
                msg = messages[i]
                role = msg.get("role", "") if isinstance(msg, dict) else getattr(msg, "type", "")
                if role in ("user", "human"):
                    # 根据操作类型生成相应的命令
                    if pending_operation == "view_config":
                        new_content = "查看系统配置 confirm=True"
                    elif pending_operation == "cleanup_data":
                        new_content = "清理Redis数据 confirm=True"
                    elif pending_operation == "check_service":
                        new_content = "查看服务状态 confirm=True"
                    elif pending_operation == "restart_service":
                        new_content = "重启预测服务 confirm=True"
                    elif pending_operation == "delete_batch":
                        new_content = "删除批次 confirm=True"
                    else:
                        new_content = last_content + " confirm=True"

                    if isinstance(msg, dict):
                        messages[i] = {"role": role, "content": new_content}
                    else:
                        msg.content = new_content
                    break

            try:
                result = self.ops_agent.invoke({"messages": messages})
                existing_count = len(messages)
                all_msgs = result.get("messages", [])
                new_msgs = all_msgs[existing_count:]

                # 清除待确认状态
                return {
                    "messages": new_msgs,
                    "pending_operation": "",
                    "pending_params": {}
                }
            except Exception as e:
                logger.error(f"[OpsAgent] 执行失败: {e}")
                return {
                    "messages": [AIMessage(content=f"操作执行失败: {str(e)}")],
                    "pending_operation": "",
                    "pending_params": {}
                }

        # 正常处理运维请求
        try:
            result = self.ops_agent.invoke({"messages": state["messages"]})
            existing_count = len(state["messages"])
            all_msgs = result.get("messages", [])
            new_msgs = all_msgs[existing_count:]

            # 检查是否需要记录待确认的操作
            # 通过分析最后一条AI消息来判断
            if new_msgs:
                last_ai_msg = new_msgs[-1]
                msg_content = getattr(last_ai_msg, "content", "") if hasattr(last_ai_msg, "content") else str(last_ai_msg)

                # 如果消息中包含"确认"关键词，说明需要确认
                if "确认" in msg_content or "confirm" in msg_content.lower():
                    # 从用户消息中提取操作类型
                    operation = self._extract_operation_type(last_content)
                    logger.info(f"[OpsAgent] 记录待确认操作: {operation}")
                    return {
                        "messages": new_msgs,
                        "pending_operation": operation,
                        "pending_params": {}
                    }

            return {"messages": new_msgs}
        except Exception as e:
            logger.error(f"[OpsAgent] 执行失败: {e}")
            return {"messages": [AIMessage(content=f"OpsAgent 执行出错: {str(e)}")]}

    def _extract_operation_type(self, user_content: str) -> str:
        """从用户消息中提取操作类型"""
        user_content_lower = user_content.lower()

        if "配置" in user_content or "config" in user_content_lower:
            return "view_config"
        elif "清理" in user_content or "clean" in user_content_lower:
            return "cleanup_data"
        elif "服务状态" in user_content or "service" in user_content_lower:
            return "check_service"
        elif "重启" in user_content or "restart" in user_content_lower:
            return "restart_service"
        elif "删除" in user_content or "delete" in user_content_lower:
            return "delete_batch"
        else:
            return "unknown"

    # ============================================================
    # Result Validator —— 纯 Python 错误检测
    # ============================================================

    @staticmethod
    def _validate_result(state: SupervisorState) -> dict:
        messages = state.get("messages", [])
        if not messages:
            return {"error_type": ""}

        # 检查所有消息（不止最后一条），因为 LLM 可能把错误信息包装在前面的 tool 消息里
        ERROR_PATTERNS = [
            ("找不到矩阵文件",    "data_not_ready"),
            ("矩阵文件不存在",    "data_not_ready"),
            ("找不到模型文件",    "model_not_ready"),
            ("模型文件不存在",    "model_not_ready"),
            ("训练失败",          "model_not_ready"),
            ("模型缺失",          "model_not_ready"),
            ("文件缺失",          "data_not_ready"),
            ("组件不全",          "data_not_ready"),
            ("Connection refused", "connection_failed"),
            ("连接失败",          "connection_failed"),
            ("timeout",           "timeout"),
            ("超时",              "timeout"),
            ("FileNotFoundError", "file_missing"),
        ]

        # 从后往前扫最近 10 条消息，避免漏掉
        for msg in reversed(messages[-10:]):
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content", "")
            else:
                content = getattr(msg, "content", "") or ""
            content_str = str(content)

            for pattern, err_type in ERROR_PATTERNS:
                if pattern.lower() in content_str.lower():
                    logger.warning(f"[Validator] 检测到错误 → {err_type}  (匹配: {pattern})")
                    return {"error_type": err_type}

        return {"error_type": ""}

    @staticmethod
    def _check_result(state: SupervisorState) -> str:
        return "error" if state.get("error_type", "") else "ok"

    # ============================================================
    # Error Handler —— 纠错重试机制
    # ============================================================

    @staticmethod
    def _handle_error(state: SupervisorState):
        retry = state.get("retry_count", 0) + 1
        error_type = state.get("error_type", "unknown")
        logger.warning(f"[ErrorHandler] 第 {retry} 次重试  错误类型={error_type}")

        reroute_map = {
            "model_not_ready":   "data_agent",
            "data_not_ready":    "data_agent",
            "file_missing":      "data_agent",
        }
        target = reroute_map.get(error_type, "fallback")

        if retry >= 3:
            logger.warning("[ErrorHandler] 已达最大重试次数 -> fallback")
            return Command(goto="fallback", update={"retry_count": retry})

        logger.info(f"[ErrorHandler] 直接跳转 -> {target} (绕过 Supervisor)")
        return Command(goto=target, update={
            "retry_count": retry,
            "error_type": "",
        })

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

        # 合并之前的对话状态
        messages = self.conversation_state["messages"].copy()
        messages.append({"role": "user", "content": query})

        input_dict = {
            "messages":             messages,
            "intent":               "",
            "confidence":           0.0,
            "retry_count":          0,
            "error_type":           "",
            "next_agent_override":  "",
            "pending_operation":    self.conversation_state["pending_operation"],
            "pending_params":       self.conversation_state["pending_params"],
        }

        yielded_count = len(messages)  # 跳过已有的消息

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

                # 保存最新的状态（每次迭代都保存）
                self.conversation_state["messages"] = chunk.get("messages", [])
                if "pending_operation" in chunk:
                    self.conversation_state["pending_operation"] = chunk.get("pending_operation", "")
                if "pending_params" in chunk:
                    self.conversation_state["pending_params"] = chunk.get("pending_params", {})

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
