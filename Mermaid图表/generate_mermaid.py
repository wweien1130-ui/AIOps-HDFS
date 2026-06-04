"""
从 LangGraph 生成 Mermaid 图的 Python 脚本
支持条件边（虚线）和 retry 逻辑显示
"""

import sys
import os
import re

# 切到项目根目录
sys.path.insert(0, r"E:\private_project\AI_application")
os.chdir(r"E:\private_project\AI_application")

from agent.react_agent import ReactAgent


def generate_mermaid_code(langgraph):
    """从 LangGraph 生成 Mermaid 代码，支持条件边（虚线）"""
    graph_obj = langgraph.get_graph()

    # 开始构建 Mermaid 代码
    mermaid_lines = [
        "---",
        "config:",
        "  flowchart:",
        "    curve: linear",
        "---",
        "graph TD"
    ]

    # 添加节点定义
    for node_id, node in graph_obj.nodes.items():
        node_name = node.name if hasattr(node, 'name') else node_id
        if node_id == "__start__":
            mermaid_lines.append(f"    {node_id}([<{node_name}>]):::first")
        elif node_id == "__end__":
            mermaid_lines.append(f"    {node_id}([<{node_name}>]):::last")
        else:
            mermaid_lines.append(f"    {node_id}({node_name})")

    # 确定条件路由节点
    conditional_source_nodes = set()

    for edge in graph_obj.edges:
        out_edges_count = sum(1 for e in graph_obj.edges if e.source == edge.source)
        if edge.source != '__start__' and edge.source != '__end__' and out_edges_count > 1:
            conditional_source_nodes.add(edge.source)

    # 添加边定义，根据是否为条件边选择实线或虚线
    for edge in graph_obj.edges:
        if edge.source in conditional_source_nodes:
            mermaid_lines.append(f"    {edge.source} -.-> {edge.target}")
        else:
            mermaid_lines.append(f"    {edge.source} --> {edge.target}")

    # 添加样式定义
    mermaid_lines.extend([
        "",
        "classDef default fill:#4A90E2,color:#ffffff,stroke:#000000,stroke-width:2px,line-height:1.2",
        "classDef first fill:#00AA00,color:#ffffff,stroke:#000000,stroke-width:2px,fill-opacity:0.8",
        "classDef last fill:#FF4444,color:#ffffff,stroke:#000000,stroke-width:2px,fill-opacity:0.8"
    ])

    return "\n".join(mermaid_lines)


def main():
    """主函数：生成并显示 Mermaid 图"""
    print("正在初始化 Agent...")
    agent = ReactAgent()
    print("Agent 初始化完成")

    # 1. 用 LangGraph 生成基础 Mermaid，然后清洗
    base = agent.graph.get_graph().draw_mermaid()

    # 去掉 HTML 实体（VS Code 渲染器不认 &nbsp;）
    base = base.replace("&nbsp;", " ")
    base = re.sub(r'-\..*?\.->', lambda m: m.group().replace(' ', ''), base)
    # 也清理多余的 classDef
    base = re.sub(r'classDef default.*', '', base)
    base = re.sub(r'classDef first.*', '', base)
    base = re.sub(r'classDef last.*', '', base)

    # 2. 手动添加 retry 逻辑的边（方案2：分析 Command 跳转逻辑）
    # 从 react_agent.py 的 _handle_error 方法中提取逻辑：
    # - retry < 3: 根据 error_type 跳转到 data_agent 或 fallback
    # - retry >= 3: 直接跳转到 fallback
    retry_edges = """
# Retry 逻辑边（虚线表示条件跳转）
error_handler -.-> data_agent : retry < 3 && error_type in [model_not_ready, data_not_ready, file_missing]
error_handler -.-> fallback : retry < 3 && error_type not in reroute_map
error_handler --> fallback : retry >= 3
"""

    # 3. 鲜艳配色 + 加粗
    STYLES = """
classDef default fill:#1a1a2e,color:#fff,stroke:#e94560,stroke-width:2px,font-weight:bold
classDef first fill:#00b894,color:#fff,stroke:#00b894,stroke-width:2px,font-weight:bold
classDef last fill:#e17055,color:#fff,stroke:#e17055,stroke-width:2px,font-weight:bold
classDef supervisor fill:#6c5ce7,color:#fff,stroke:#a29bfe,stroke-width:3px,font-weight:bold
classDef agent fill:#0984e3,color:#fff,stroke:#74b9ff,stroke-width:2px,font-weight:bold
classDef validator fill:#fdcb6e,color:#1a1a2e,stroke:#f39c12,stroke-width:2px,font-weight:bold
classDef error fill:#d63031,color:#fff,stroke:#ff7675,stroke-width:3px,font-weight:bold
classDef fallback fill:#636e72,color:#fff,stroke:#b2bec3,stroke-width:2px,font-weight:bold
class supervisor supervisor
class diagnosis_agent,data_agent,monitor_agent,general_agent agent
class result_validator validator
class error_handler error
class fallback fallback"""

    mermaid = base + retry_edges + STYLES

    # 输出 Mermaid 代码
    print("\n" + "="*60)
    print("Mermaid 图代码：")
    print("="*60)
    print(mermaid)
    print("="*60)

    # 输出说明
    print("\n说明：")
    print("🟣 紫色 = Supervisor")
    print("🔵 蓝色 = 子Agent")
    print("🟡 黄色 = Validator")
    print("🔴 红色 = ErrorHandler")
    print("⚫ 灰色 = Fallback")
    print("🔄 虚线边表示 retry 逻辑（retry < 3 时跳转回 data_agent）")


if __name__ == "__main__":
    main()
