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

from model.factory import chat_models, ollama_model
from agent.tools.agent_tools import (
    rag_retrieve, get_current_time, calculate,
    preprocess_hdfs_logs, train_mlp_model, detect_anomaly, check_model_readiness,
    list_offline_batches, list_offline_anomalies, process_offline_batch,
    get_realtime_anomalies, start_realtime_service, stop_realtime_service,
    # 运维工具
    check_system_status, view_system_config, cleanup_redis_data,
    check_service_status, restart_service, delete_offline_batch, delete_all_offline_batches,
    # 模型管理工具
    list_available_models, switch_model,
)
from utils.prompt_loader import (
    load_system_prompts,    #系统提示词
    load_supervisor_prompt,  #调度器
    load_diagnosis_prompt,   #诊断器
    load_data_prompt,        #数据处理器
    load_ops_prompt,         #运维处理器
)
from utils.logger_handler import logger
from utils.config_handler import llm_config


def _clean_messages_for_cloud(messages: list) -> list:
    """过滤消息，移除 tool 消息和 tool_calls，适配 DashScope API"""
    cleaned = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", "")
            content = msg.get("content", "")
        else:
            role = getattr(msg, "type", "")
            content = getattr(msg, "content", "")

        # 跳过 tool 消息和空的 ai 消息
        if role == "tool":
            continue
        if role in ("ai", "assistant") and not content:
            continue

        # 构造干净的消息
        if role in ("user", "human"):
            cleaned.append(HumanMessage(content=content))
        elif role in ("ai", "assistant"):
            cleaned.append(AIMessage(content=content))

    return cleaned


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

        # 当前模型模式（由 execute_stream 设置）
        self._current_model_mode = "auto"
        # 持久化模型模式（通过对话切换后保存，跨请求生效）
        self._persisted_model_mode = ""
        # 子Agent 默认模型引用（用于 dynamic swap）
        self._default_ollama = ollama_model
        self._default_cloud = chat_models

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
            model=ollama_model,
            system_prompt="""你是一个专业的HDFS智能助手的中枢调度员。

                            你的职责：
                            1. 回答关于时间、数学计算等通用问题
                            2. 当用户询问你的身份时，回答：
                            "我是HDFS智能诊断系统，集成了异常检测、知识检索、实时监控等功能。
                                如果需要检测异常或查询知识，请直接告诉我您的需求。"
                            3. 如果用户的问题涉及HDFS，主动引导到对应功能
                            4. 处理模型管理请求（查看/切换模型）

                            可用工具：
                            - get_current_time: 获取当前时间
                            - calculate: 数学计算
                            - list_available_models: 查看所有可用的本地和云端模型
                            - switch_model: 切换模型（需要二次确认）
                            """,
            tools=[get_current_time, calculate, list_available_models, switch_model],
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
                delete_all_offline_batches,
            ],
        )

        # 存储待确认的操作
        self.pending_ops = {}

        # --- 构建 Supervisor 图 ---
        logger.info("[ReactAgent] 构建 Supervisor 状态图...")
        self.graph = self._build_graph()

        logger.info("[ReactAgent] 多智能体系统初始化完成")

    # ============================================================
    # 模型解析
    # ============================================================

    def _resolve_model(self, agent_type: str = "default"):
        """根据当前 model_mode 和 agent 类型返回对应的模型实例。

        agent_type: "supervisor" | "simple" | "complex"
          - supervisor/simple: auto 模式下用本地模型
          - complex: auto 模式下用云端模型

        model_mode 格式:
          - "auto"                  → 使用默认本地 + 默认云端
          - "auto:qwen3:8b:qwen-max" → 指定本地 + 云端
          - "ollama"                → 全部用默认本地
          - "cloud"                 → 全部用默认云端
          - "qwen3.5:9b"            → 全部用指定模型
        """
        from model.registry import registry
        mode = self._current_model_mode
        logger.info(f"[ModelSwitch] _resolve_model called: mode={mode!r} agent_type={agent_type}")

        if mode.startswith("auto"):
            # 格式: "auto|qwen3:8b|qwen3.6-plus"（用 | 分隔，避免模型名中的 : 冲突）
            parts = mode.split("|")
            logger.info(f"[ModelSwitch] auto parts={parts}")
            if len(parts) == 3:
                local_name, cloud_name = parts[1], parts[2]
            else:
                local_name = llm_config.get("ollama", {}).get("models", {}).get("default", "qwen3:8b")
                cloud_name = llm_config.get("qwen", {}).get("models", {}).get("default", "")
            chosen = local_name if agent_type in ("supervisor", "simple") else cloud_name
            logger.info(f"[ModelSwitch] mode=auto agent={agent_type} → {chosen}")
            if agent_type in ("supervisor", "simple"):
                return registry.get_model(local_name)
            return registry.get_model(cloud_name)
        elif mode == "ollama":
            logger.info(f"[ModelSwitch] mode=ollama agent={agent_type} → ollama default")
            return registry.get_ollama_model()
        elif mode == "cloud":
            logger.info(f"[ModelSwitch] mode=cloud agent={agent_type} → cloud default")
            return registry.get_cloud_model()
        else:
            logger.info(f"[ModelSwitch] mode=single agent={agent_type} → {mode}")
            return registry.get_model(mode)

    # ============================================================
    # 图构建
    # ============================================================

    def _build_graph(self):
        builder = StateGraph(SupervisorState)

        # 注册所有节点
        builder.add_node("supervisor",       self._supervisor_node)
        builder.add_node("diagnosis_agent",  self._make_agent_node(self.diagnosis_agent, "Diagnosis", "complex"))
        builder.add_node("data_agent",       self._make_agent_node(self.data_agent, "Data", "complex"))
        builder.add_node("monitor_agent",    self._monitor_node)
        builder.add_node("general_agent",    self._make_agent_node(self.general_agent, "General", "simple"))
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

        # ===== Python 关键词预分类（快速、准确，避免 LLM 误判）=====
        fast_intent = self._fast_classify(last_user_content)
        if fast_intent:
            logger.info(f"[Supervisor] 关键词快速分类: {fast_intent}")
            return {"intent": fast_intent, "confidence": 1.0, "next_agent_override": ""}

        logger.info(f"[Supervisor] 分析意图: {last_user_content[:60]}...")

        try:
            sup_model = self._resolve_model("supervisor")
            response = sup_model.invoke([
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
    def _fast_classify(text: str) -> str:
        """Python 关键词快速分类——在 LLM 之前执行，处理明确的意图。
        返回空字符串表示无法快速分类，需要走 LLM。"""
        t = text.strip()

        # MONITOR: 开启/关闭/启动/停止 + 在线/实时/监控/模式
        monitor_patterns = [
            "开启在线", "关闭在线", "启动在线", "停止在线",
            "开启实时", "关闭实时", "启动实时", "停止实时",
            "开启监控", "关闭监控", "启动监控", "停止监控",
            "在线模式", "实时模式", "监控模式",
            "在线检测", "实时监控",
        ]
        if any(p in t for p in monitor_patterns):
            return "monitor"

        # MODEL: 切换模型、模型相关
        model_patterns = [
            "切换模型", "模型切换", "模型管理", "查看模型",
            "可用模型", "当前模型", "模型列表", "本地模型",
            "云端模型", "混合模式",
        ]
        if any(p in t for p in model_patterns):
            return "model"

        # OPS: 系统状态、配置、清理等（排除在线/实时/监控相关）
        ops_patterns = ["系统状态", "查看配置", "清理数据", "清理redis"]
        if any(p in t for p in ops_patterns):
            return "ops"

        # 无法快速分类，交给 LLM
        return ""

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
            "MODEL":     "model",
        }
        intent = intent_map.get(raw, "")
        if intent:
            return intent, confidence

        # 回退：关键词匹配（顺序重要，更具体的放前面）
        t = text.lower()
        if any(kw in t for kw in ["切换模型", "模型切换", "模型管理", "查看模型", "可用模型", "当前模型", "模型列表", "本地模型", "云端模型"]):
            return "model", 0.7
        if any(kw in t for kw in ["diagnosis", "诊断", "检测", "异常", "错误", "blk_"]):
            return "diagnosis", 0.6
        if any(kw in t for kw in ["data", "数据", "训练", "预处理", "批次", "batch"]):
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
            "model":     "general_agent",  # 模型管理由 General Agent 处理
        }
        target = route_map.get(intent, "fallback")
        logger.info(f"[Router] {intent} → {target}")
        return target

    # ============================================================
    # 子Agent 节点工厂 —— 用闭包为每个子Agent创建节点函数
    # ============================================================

    def _make_agent_node(self, agent, name: str, agent_type: str = "complex"):
        """返回一个 LangGraph 节点函数，内部调用子Agent并返回增量消息。
        agent_type: "simple" | "complex" — 用于动态模型选择。"""
        def node_fn(state: SupervisorState) -> dict:
            logger.info(f"[{name}Agent] 开始执行...")
            try:
                # 动态替换模型
                resolved = self._resolve_model(agent_type)
                agent.model = resolved
                # 云端模型需要过滤 tool 消息，本地模型不需要
                from langchain_community.chat_models import ChatTongyi
                if isinstance(resolved, ChatTongyi):
                    msgs = _clean_messages_for_cloud(state["messages"])
                else:
                    msgs = state["messages"]
                result = agent.invoke({"messages": msgs})
                existing_count = len(msgs)
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
        # 动态替换模型
        resolved = self._resolve_model("complex")
        self.ops_agent.model = resolved
        from langchain_community.chat_models import ChatTongyi
        _is_cloud = isinstance(resolved, ChatTongyi)
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
                clean_msgs = _clean_messages_for_cloud(messages) if _is_cloud else messages
                result = self.ops_agent.invoke({"messages": clean_msgs})
                existing_count = len(clean_msgs)
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
            clean_msgs = _clean_messages_for_cloud(state["messages"]) if _is_cloud else state["messages"]
            result = self.ops_agent.invoke({"messages": clean_msgs})
            existing_count = len(clean_msgs)
            all_msgs = result.get("messages", [])
            new_msgs = all_msgs[existing_count:]

            # 检查是否需要记录待确认的操作
            # 通过分析所有新消息来判断（包括工具消息）
            needs_confirmation = False
            for msg in new_msgs:
                if isinstance(msg, dict):
                    msg_type = msg.get("type", "")
                    msg_content = msg.get("content", "")
                else:
                    msg_type = getattr(msg, "type", "")
                    msg_content = getattr(msg, "content", "")

                # 检查工具消息或AI消息中是否包含确认关键词
                if msg_type in ["tool", "ai"] and ("确认" in msg_content or "confirm" in msg_content.lower()):
                    needs_confirmation = True
                    break

            if needs_confirmation:
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

        # 只检查最后一条 AI 消息（最终结果），忽略中间的工具调用消息
        # 避免工具调用过程中的临时错误（如 Connection refused）被误判为最终失败
        ERROR_PATTERNS = [
            ("找不到矩阵文件",    "data_not_ready"),
            ("矩阵文件不存在",    "data_not_ready"),
            ("找不到模型文件",    "model_not_ready"),
            ("模型文件不存在",    "model_not_ready"),
            ("训练失败",          "model_not_ready"),
            ("模型缺失",          "model_not_ready"),
            ("文件缺失",          "data_not_ready"),
            ("组件不全",          "data_not_ready"),
        ]

        # 找到最后一条 AI 类型的消息
        last_ai_content = ""
        for msg in reversed(messages):
            msg_type = ""
            content = ""
            if isinstance(msg, dict):
                msg_type = msg.get("type", "")
                content = msg.get("content", "")
            else:
                msg_type = getattr(msg, "type", "")
                content = getattr(msg, "content", "") or ""

            if msg_type == "ai" and content:
                last_ai_content = str(content)
                break

        if last_ai_content:
            for pattern, err_type in ERROR_PATTERNS:
                if pattern.lower() in last_ai_content.lower():
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

    def execute_stream(self, query: str, model_mode: str = "auto"):
        # 前端发送的 model_mode 只有在明确选择了具体模型时才覆盖持久化
        # "auto:local:cloud" 格式 = 前端明确选择了模型组合，应覆盖持久化
        if model_mode != "auto" and self._persisted_model_mode:
            logger.info(f"[execute_stream] 前端覆盖持久化: {self._persisted_model_mode} → {model_mode}")
            self._persisted_model_mode = ""
        # 优先使用持久化的模型模式（通过对话切换设置）
        effective_mode = self._persisted_model_mode if self._persisted_model_mode else model_mode
        logger.info(f"[execute_stream] 开始处理: {query} (model_mode={effective_mode}, persisted={'yes' if self._persisted_model_mode else 'no'})")
        self._current_model_mode = effective_mode

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
                        text = msg_content.strip()
                        # 检测模型切换指令
                        switch_match = re.search(r'\[MODEL_SWITCH:(.+?)\]', text)
                        if switch_match:
                            switch_value = switch_match.group(1)
                            # 输出结构化事件（前端解析）
                            yield json.dumps({"event": "model_switch", "model": switch_value})
                            # 输出纯文本（去掉标记）
                            text = re.sub(r'\[MODEL_SWITCH:.+?\]', '', text).strip()
                        if text:
                            yield text
                    elif msg_type == "tool":
                        content_str = str(msg_content) if msg_content else ""
                        # 工具输出也可能包含切换指令
                        switch_match = re.search(r'\[MODEL_SWITCH:(.+?)\]', content_str)
                        if switch_match:
                            switch_value = switch_match.group(1)
                            yield json.dumps({"event": "model_switch", "model": switch_value})
                            content_str = re.sub(r'\[MODEL_SWITCH:.+?\]', '', content_str).strip()
                        if content_str:
                            yield content_str
                        elif not switch_match:
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
