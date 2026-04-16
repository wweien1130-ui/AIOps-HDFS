import os
import sys
import subprocess
from langchain_core.tools import tool

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
SCRIPT_DIR = os.path.join(PROJECT_ROOT, "Test_kraft_connect", "Fix_File")


@tool(description="第三步：训练MLP异常检测模型。")
def train_model(epochs: int = 50) -> str:
    """
    运行 train_conbine.py 训练模型
    """
    script_path = os.path.join(SCRIPT_DIR, "train_conbine.py")

    if not os.path.exists(script_path):
        return f"❌ 错误：找不到 train_conbine.py 脚本，路径: {script_path}"

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=SCRIPT_DIR
        )

        if result.returncode == 0:
            return f"✅ 模型训练成功！\n{result.stdout}"
        else:
            return f"❌ 模型训练失败：\n{result.stderr}"

    except subprocess.TimeoutExpired:
        return "❌ 训练超时（超过10分钟）"
    except Exception as e:
        return f"❌ 执行失败: {str(e)}"