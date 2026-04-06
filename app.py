import os

os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "true"
os.environ["HF_HOME"] = ""

import streamlit as st
from agent.react_agent import ReactAgent

st.title("智扫通机器人智能客服")
st.divider()

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "message" not in st.session_state:
    st.session_state["message"] = []

for message in st.session_state["message"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input()

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    with st.spinner("智能客服思考中..."):
        full_response = ""
        response_placeholder = st.chat_message("assistant")

        try:
            for chunk in st.session_state["agent"].execute_stream(prompt):
                if chunk:
                    full_response += chunk
            response_placeholder.markdown(full_response)
        except Exception as e:
            response_placeholder.error(f"生成响应时出错: {str(e)}")
            full_response = f"生成响应时出错: {str(e)}"

    st.session_state["message"].append({"role": "assistant", "content": full_response})