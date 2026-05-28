import os
import sys
import time
import streamlit as st

os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "true"
os.environ["HF_HOME"] = ""

from agent.react_agent import ReactAgent

st.set_page_config(page_title="HDFS异常检测机器人", layout="wide")

# ============================================================
# Session State 初始化
# ============================================================

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()
if "message" not in st.session_state:
    st.session_state["message"] = []
if "monitoring" not in st.session_state:
    st.session_state["monitoring"] = False
if "monitor_data" not in st.session_state:
    st.session_state["monitor_data"] = ""
if "processing" not in st.session_state:
    st.session_state["processing"] = False

# ============================================================
# 侧边栏 - 监控状态
# ============================================================

with st.sidebar:
    st.title("HDFS 诊断机器人")
    st.divider()

    if st.session_state.monitoring:
        st.success("🔴 实时监控运行中")
        st.caption(f"自动刷新 · 每 5 秒")
    else:
        st.info("⚪ 监控未启动")

    st.divider()
    st.caption("输入「开启在线模式」启动实时监控")
    st.caption("输入「关闭在线模式」停止实时监控")
    st.caption("输入「查询实时异常」查看最新数据")

# ============================================================
# 主区域标题
# ============================================================

st.title("自动化日志异常检测机器人")
st.divider()

# ============================================================
# 监控面板（仅在线模式时显示）
# ============================================================

if st.session_state.monitoring:
    with st.container():
        st.subheader("📊 实时监控面板")

        # 获取实时数据
        try:
            from agent.tools.agent_tools import get_realtime_anomalies
            raw = get_realtime_anomalies(limit=10)
            st.session_state["monitor_data"] = raw
        except Exception as e:
            raw = st.session_state.get("monitor_data", "暂无数据")

        col1, col2, col3 = st.columns(3)

        # 从结果中解析数字
        import re
        block_count = len(re.findall(r'Block:', raw)) if raw else 0
        high_risk = len(re.findall(r'异常分数: \*\*(\d\.\d{4})\*\*', raw))

        with col1:
            st.metric("异常 Block 数", block_count)
        with col2:
            st.metric("高风险 Block", high_risk)
        with col3:
            st.metric("刷新时间", time.strftime("%H:%M:%S"))

        with st.expander("异常详情", expanded=True):
            if raw and "暂无" not in raw:
                st.markdown(raw)
            else:
                st.info("暂无实时异常数据，等待日志上传...")

        st.divider()

# ============================================================
# 聊天消息展示
# ============================================================

for message in st.session_state["message"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ============================================================
# 聊天输入
# ============================================================

prompt = st.chat_input(disabled=st.session_state.processing)

if prompt:
    st.session_state.processing = True

    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    with st.spinner("机器人思考中..."):
        full_response = ""
        response_placeholder = st.chat_message("assistant")

        try:
            for chunk in st.session_state["agent"].execute_stream(prompt):
                if chunk:
                    full_response += chunk
            response_placeholder.markdown(full_response)

            # 根据回复内容判断监控状态变化
            if any(kw in prompt for kw in ["开启在线", "启动实时", "开启实时", "在线模式"]):
                st.session_state.monitoring = True
            elif any(kw in prompt for kw in ["关闭在线", "停止实时", "关闭实时"]):
                st.session_state.monitoring = False

        except Exception as e:
            response_placeholder.error(f"生成响应时出错: {str(e)}")
            full_response = f"生成响应时出错: {str(e)}"

    st.session_state["message"].append({"role": "assistant", "content": full_response})
    st.session_state.processing = False

# ============================================================
# 自动刷新（仅在线模式）
# ============================================================

if st.session_state.monitoring and not st.session_state.processing:
    time.sleep(5)
    st.rerun()
