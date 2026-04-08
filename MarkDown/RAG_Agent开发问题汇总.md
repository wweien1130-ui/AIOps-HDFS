# RAG + Agent 开发问题汇总

本文档记录了 HDFS 日志异常检测系统中 RAG + Agent 模块开发过程中遇到的问题及解决方案。

---

## 问题一：相对导入错误

### 错误信息

```
ImportError: attempted relative import with no known parent package
```

### 发生场景

直接运行 `utils/prompt_loader.py` 文件时：

```bash
python utils/prompt_loader.py
```

### 问题原因

代码中使用了相对导入（Relative Import）：

```python
# 错误的导入方式（相对导入）
from .path_tool import get_abs_path
from .config_handler import prompts_config
from .logger_handler import logger
```

当直接运行文件时，Python无法识别父包，导致导入失败。

### 解决方案

改为绝对导入，并动态添加项目路径：

```python
import sys
import os

# 获取项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 使用绝对导入
from utils.path_tool import get_abs_path
from utils.config_handler import prompts_config
from utils.logger_handler import logger
```

### 代码解释

| 代码 | 作用 |
|------|------|
| `__file__` | 获取当前文件路径 |
| `os.path.dirname()` | 获取上级目录 |
| `os.path.abspath()` | 转换为绝对路径 |
| `sys.path.insert(0, path)` | 将项目根目录添加到Python搜索路径 |

---

## 问题二：字典访问错误

### 错误信息

```
AttributeError: 'dict' object has no attribute 'messages'
During task with name 'log_before_model.before_model'
```

### 发生场景

在 `middleware.py` 的 `log_before_model` 函数中

### 问题原因

错误地将 `state` 当作对象访问，使用了点语法：

```python
# 错误的写法
logger.info(f"[log_before_model]即将调用模型，带有{len(state.messages)}个消息")
```

实际上 `state` 是字典类型，需要用键访问：

```python
# 正确的写法
messages = state.get("messages", [])
logger.info(f"[log_before_model]即将调用模型，带有{len(messages)}个消息")
```

### 解决方案

```python
@before_model
def log_before_model(state: AgentState, runtime: Runtime):
    # state是字典类型，需要用state["messages"]访问
    messages = state.get("messages", [])  # 使用get方法安全获取
    logger.info(f"[log_before_model]即将调用模型，带有{len(messages)}个消息")
    
    if messages:
        logger.debug(f"[log_before_model]{type(messages[-1]).__name__} | {messages[-1].content.strip()}")
    
    return None
```

### 代码解释

| 代码 | 作用 |
|------|------|
| `state.get("messages", [])` | 安全获取键值，若不存在返回空列表 |
| `len(messages)` | 获取消息数量 |
| `messages[-1]` | 获取最后一条消息 |
| `.content.strip()` | 获取内容并去除首尾空格 |

---

## 问题三：Agent不调用RAG工具

### 错误现象

Agent 始终返回通用回复，不调用 RAG 检索工具：

```
请提供具体的HDFS异常日志信息或相关问题描述，我将为您进行诊断分析。
```

输入具体问题如 `"blk_12345 not found 错误怎么解决"` 也不会触发工具。

### 问题原因

RAG 提示词文件 `prompts/rag_summarize.txt` 格式不正确。

原来的文件是完整的 Markdown 说明文档格式，但代码试图将其作为 Jinja2 模板使用，导致 `{input}` 和 `{context}` 占位符无法替换。

### 错误格式（修改前）

```markdown
# 资料搜索员工作指南 - RAG检索专家

## 角色定义

你是**HDFS知识检索专家**，负责从知识库中搜索与异常日志相关的技术资料。

## 检索策略
...
```

### 解决方案

将提示词改为 Jinja2 模板格式：

```markdown
# 资料搜索员工作指南

你是HDFS知识检索专家。根据用户问题，从知识库中检索相关信息。

用户问题：{input}

检索到的相关知识：
{context}

请基于以上检索结果，用中文回答用户问题。如果知识不足，请说明需要更多信息。
```

### 代码关联

在 `rag/rag_service.py` 中使用该提示词：

```python
class RagSummarizerService(object):
    def __init__(self):
        self.prompt_text = load_rag_prompts()  # 加载提示词
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)  # 创建模板
        self.chain = self.prompt_template | self.model | StrOutputParser()  # 构建链

    def summarize(self, query: str) -> str:
        context_docs = self.retriever_docs(query)  # 检索文档
        context = "\n\n".join([f"[参考资料{i}]: {doc.page_content}" 
                               for i, doc in enumerate(context_docs, 1)])
        
        return self.chain.invoke({
            "input": query,
            "context": context
        })
```

### 模板变量说明

| 变量 | 说明 | 来源 |
|------|------|------|
| `{input}` | 用户输入的问题 | 用户查询 |
| `{context}` | 检索到的相关知识 | RAG向量数据库 |

---

## 问题四：模块导入问题

### 错误现象

运行时报错：

```
ModuleNotFoundError: No module named 'agent'
```

### 问题原因

Python 包目录缺少 `__init__.py` 文件，导致无法作为模块导入。

### 解决方案

在以下目录创建空的 `__init__.py` 文件：

```bash
touch agent/__init__.py
touch agent/tools/__init__.py
touch rag/__init__.py
touch model/__init__.py
touch config/__init__.py
```

或者手动创建这些文件：

```python
# agent/__init__.py
# agent package
```

```python
# agent/tools/__init__.py
# agent tools package
```

### `__init__.py` 的作用

- 告诉 Python 该目录是一个包
- 可以在包级别执行初始化代码
- 控制模块的导入行为

---

## 问题五：配置加载问题

### 注意事项

配置文件中的路径建议使用**相对路径**，并通过 `get_abs_path()` 函数转换为绝对路径：

```yaml
# config/llm.yml
ollama:
  base_url: "http://localhost:11434"
  model: "llama3"
```

```python
# utils/path_tool.py
def get_abs_path(relative_path: str) -> str:
    """获取绝对路径"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, relative_path)
```

---

## 问题六：Ollama 连接问题

### 错误信息

```
USER_AGENT environment variable not set, consider setting it to identify your requests.
```

### 说明

这是一个警告信息，不是错误。可以忽略，或者设置环境变量：

```bash
export USER_AGENT="my-app/1.0"
```

---

## 总结

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 相对导入错误 | 直接运行文件 | 改为绝对导入 |
| 字典访问错误 | state是dict不是object | 使用 `state.get()` |
| Agent不调用工具 | 提示词格式错误 | 改为Jinja2模板格式 |
| 模块导入失败 | 缺少__init__.py | 创建空文件 |

---

## 调试技巧

### 1. 开启日志调试

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. 打印中间变量

```python
# 在关键位置打印变量
print(f"state: {state}")
print(f"messages: {messages}")
```

### 3. 检查提示词是否正确加载

```python
prompt = load_rag_prompts()
print(prompt)  # 检查是否包含 {input} 和 {context}
```

### 4. 测试RAG单独功能

```python
# 单独测试RAG检索
from rag.rag_service import RagSummarizerService
rag = RagSummarizerService()
result = rag.summarize("blk_12345 not found 怎么办")
print(result)
```

---

## 附录：文件结构参考

```
AI_application/
├── agent/
│   ├── __init__.py
│   ├── react_agent.py          # Agent主入口
│   └── tools/
│       ├── __init__.py
│       ├── agent_tools.py      # 工具定义
│       └── middleware.py       # 中间件
├── rag/
│   ├── __init__.py
│   ├── rag_service.py          # RAG服务
│   └── vector_store.py         # 向量存储
├── utils/
│   ├── __init__.py
│   ├── prompt_loader.py        # 提示词加载
│   ├── config_handler.py       # 配置加载
│   ├── logger_handler.py       # 日志
│   └── path_tool.py            # 路径工具
├── config/
│   ├── __init__.py
│   ├── base.yml
│   ├── llm.yml
│   ├── rag.yml
│   ├── chroma.yml
│   ├── agent.yml
│   └── prompts.yml
├── prompts/
│   ├── main_prompt.txt         # 岗位说明书
│   ├── rag_summarize.txt       # RAG提示词
│   └── report_prompt.txt       # 报告模板
├── hdfs_knowledge/             # 知识库
│   ├── hdfs_intro.txt
│   ├── hdfs_faq.txt
│   ├── hdfs_error_codes.txt
│   └── troubleshooting.txt
└── vector_store/               # 向量数据库存储
```

---

*文档创建日期：2026-04-07*