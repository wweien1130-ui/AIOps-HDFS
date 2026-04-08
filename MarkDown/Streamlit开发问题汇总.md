# Streamlit + Agent 开发问题汇总

本文档记录了在开发 HDFS 智能诊断 Agent 过程中遇到的问题及解决方案。

---

## 问题一：Agent 无法识别用户输入

### 现象
无论输入什么内容，Agent 始终回复："请提供具体的HDFS异常日志信息或相关问题描述"

### 原因
`react_agent.py` 中使用了错误的键名 `"message"`（单数），应该使用 `"messages"`（复数）。

### 解决方法
修改 `agent/react_agent.py` 第 20 行：

```python
# 错误代码
input_dict = {
    "message": [
        {"role": "user", "content": query}
    ]
}

# 正确代码
input_dict = {
    "messages": [
        {"role": "user", "content": query}
    ]
}
```

---

## 问题二：Streamlit 重复显示回复

### 现象
用户输入一次问题，界面显示两次相同的回复。

### 原因
Streamlit 在每次交互后会重新运行脚本，导致响应被多次渲染。

### 解决方法
添加 `processing` 标志位防止重复执行：

```python
if "processing" not in st.session_state:
    st.session_state["processing"] = False

if prompt and not st.session_state.get("processing", False):
    st.session_state["processing"] = True
    # ... 处理逻辑 ...
    st.session_state["processing"] = False
```

---

## 问题三：流式输出导致 DOM 冲突

### 现象
使用打字机效果时，浏览器控制台报错：
```
Failed to execute 'removeChild' on 'Node': The node to be removed is not a child of this node.
```

### 原因
频繁调用 `markdown()` 更新 DOM，导致 Streamlit 前端 React 组件冲突。

### 解决方法
简化流式输出，移除逐字打印效果：

```python
# 简化后的代码
with st.spinner("智能客服思考中..."):
    full_response = ""
    response_placeholder = st.chat_message("assistant")
    
    for chunk in st.session_state["agent"].execute_stream(prompt):
        if chunk:
            full_response += chunk
    response_placeholder.markdown(full_response)
```

---

## 问题四："NoneType" 对象没有属性 "get"

### 现象
调用 `detect_anomaly` 工具时报错：`"'NoneType' object has no attribute 'get'"`

### 原因
1. `load_system_prompts()` 在文件不存在时返回 `None`
2. `request.runtime.context` 可能为 `None`

### 解决方法

**1. 修改 `utils/prompt_loader.py`：**

```python
def load_system_prompts():
    # ... 原有代码 ...
    if content is None:
        return "你是一位HDFS诊断专家。"  # 返回默认值
    return content
```

**2. 修改 `agent/tools/middleware.py`：**

```python
@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    runtime_context = getattr(request.runtime, 'context', None) or {}
    is_report = runtime_context.get("report", False)
    # ... 后续代码 ...
```

---

## 问题五：Agent 无法识别默认参数

### 现象
调用 `train_mlp_model` 时，Agent 询问用户要提供文件路径，而不是使用默认参数。

### 原因
LangChain Agent 没有识别到工具的默认参数值。

### 解决方法
在工具描述中明确说明默认参数：

```python
@tool(description="训练HDFS异常检测MLP模型。默认使用：HDFS_v1/preprocessed/Event_occurrence_matrix.csv，epochs默认100")
def train_mlp_model(data_file: str = None, epochs: int = 100) -> str:
    if data_file is None:
        data_file = os.path.join(HDFS_BASE_DIR, "preprocessed", "Event_occurrence_matrix.csv")
    # ... 后续代码 ...
```

---

## 问题六：路径解析问题

### 现象
Agent 传入 `log_file="HDFS.log"`，系统找不到文件。

### 原因
传入的只是文件名，不是完整路径。

### 解决方法
当传入的参数只是文件名时，自动使用默认的完整路径：

```python
def preprocess_hdfs_logs(log_file: str = None) -> str:
    # 如果只是文件名，使用默认路径
    if not log_file or os.path.basename(log_file) == log_file:
        log_file = os.path.join(HDFS_BASE_DIR, "HDFS.log")
    # ... 后续代码 ...
```

---

## 问题七：transformers 库警告

### 现象
控制台输出一堆类似 `Accessing __path__ from .models.xxx` 的警告。

### 解决方法
在应用开头设置环境变量：

```python
import os
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "true"
os.environ["HF_HOME"] = ""
```

---

## 问题八：Edge 浏览器翻译错误

### 现象
浏览器控制台报错：
```
net::ERR_CONNECTION_RESET
```

### 说明
这是 Edge 浏览器的翻译服务问题，与应用本身无关，可以直接忽略。

---

## 项目结构参考

```
E:\private_project\AI_application\
├── agent\
│   ├── react_agent.py          # Agent 主入口
│   └── tools\
│       ├── agent_tools.py       # 工具定义
│       └── middleware.py       # 中间件
├── app.py                      # Streamlit 前端
├── HDFS_v1\                    # HDFS 日志数据
│   ├── HDFS.log               # 原始日志
│   └── preprocessed\
│       ├── Event_occurrence_matrix.csv
│       └── HDFS.log_templates.csv
├── utils\
│   ├── path_tool.py           # 路径工具
│   └── prompt_loader.py       # 提示词加载
└── MarkDown\                   # 文档目录
```

---

## 核心功能说明

| 工具函数 | 功能 | 默认路径 |
|----------|------|----------|
| `preprocess_hdfs_logs` | 预处理日志生成事件矩阵 | HDFS_v1/HDFS.log |
| `train_mlp_model` | 训练 MLP 异常检测模型 | HDFS_v1/preprocessed/Event_occurrence_matrix.csv |
| `detect_anomaly` | 使用模型检测异常 | LogMLP_Model.pth + 事件矩阵 |
| `rag_retrieve` | 检索 HDFS 知识库 | hdfs_knowledge/ |

---

*文档创建日期：2026-04-07*