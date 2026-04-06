from langchain_core.tools import tool
from rag.rag_service import RagSummarizerService


@tool(description="从向量存储中检索参考资料，用于回答用户问题")
def rag_summarize(query: str) -> str:
    """
    从RAG知识库中检索相关信息并生成回答
    
    Args:
        query: 用户的问题或查询内容
        
    Returns:
        str: 基于知识库生成的回答
    """
    rag = RagSummarizerService()
    return rag.summarize(query)


@tool(description="仅检索向量存储中的相关文档，不生成回答")
def rag_retrieve(query: str, top_k: int = 3) -> str:
    """
    从RAG知识库中检索相关文档
    
    Args:
        query: 用户的问题或查询内容
        top_k: 返回最相关的文档数量，默认3
        
    Returns:
        str: 检索到的相关文档内容
    """
    rag = RagSummarizerService()
    docs = rag.retriever_docs(query)
    
    results = []
    for i, doc in enumerate(docs[:top_k], 1):
        results.append(f"[参考资料{i}]: {doc.page_content}")
    
    return "\n\n".join(results) if results else "未找到相关信息"


@tool(description="获取当前时间")
def get_current_time() -> str:
    """
    获取当前时间
    
    Returns:
        str: 当前的日期和时间
    """
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool(description="计算数学表达式")
def calculate(expression: str) -> str:
    """
    计算数学表达式
    
    Args:
        expression: 数学表达式，如 "2+2" 或 "sqrt(16)"
        
    Returns:
        str: 计算结果
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"计算错误: {str(e)}"

