import os
import re
from langchain_core.tools import tool

# 假设你的知识库路径如下，请根据实际情况修改
KNOWLEDGE_DIR = r"E:\private_project\AI_application\hdfs_knowledge"


def search_local_files(query: str):
    """从本地txt文件中硬核检索匹配内容"""
    results = []
    # 提取查询中的核心词，如 blk_, E1, DataNode 等
    keywords = re.findall(r'[a-zA-Z0-9_]+', query)

    if not os.path.exists(KNOWLEDGE_DIR):
        return f"错误：找不到知识库目录 {KNOWLEDGE_DIR}"

    for file_name in os.listdir(KNOWLEDGE_DIR):
        if file_name.endswith(".txt"):
            path = os.path.join(KNOWLEDGE_DIR, file_name)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 简单的关键词命中逻辑
                if any(kw.lower() in content.lower() for kw in keywords):
                    # 提取包含关键词的那一部分段落（前后各200字）
                    results.append(f"--- 来自文件: {file_name} ---\n{content}")
    return "\n\n".join(results)


@tool(description="【核心工具】检索HDFS知识库，获取错误码E1-E30的具体定义和修复指令")
def rag_retrieve(query: str) -> str:
    """
    当用户询问具体的HDFS报错（如blk_not found, E1, 心跳超时等）时，必须调用此工具获取原始资料。
    """
    # 1. 先尝试你原有的向量检索（如果它有效的话）
    try:
        from rag.rag_service import RagSummarizerService
        rag = RagSummarizerService()
        docs = rag.retriever_docs(query)
        if docs and len(docs) > 0:
            return "\n\n".join([d.page_content for d in docs])
    except Exception as e:
        print(f"向量检索失效，切换到本地文件搜索: {e}")

    # 2. 向量检索没结果或报错，直接暴力搜索本地txt文件
    local_data = search_local_files(query)
    if local_data:
        return local_data

    return "在知识库中未找到关于该问题的直接描述，请尝试更换关键词（如直接搜索错误码E1）。"


# 保留原有的时间计算工具
@tool(description="获取当前时间")
def get_current_time() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool(description="计算数学表达式")
def calculate(expression: str) -> str:
    try:
        # 简单安全评估
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except:
        return "计算错误"