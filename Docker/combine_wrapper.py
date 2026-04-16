import os
import sys
import subprocess
from langchain_core.tools import tool

TOOLS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(TOOLS_DIR))
SCRIPT_DIR = os.path.join(PROJECT_ROOT, "Test_kraft_connect", "Fix_File")


@tool(description="第二步：合并特征文件和标签文件，生成训练数据。")
def combine_training_data() -> str:
    """
    运行 combine.py，合并 block_features.csv 和 Event.csv
    """
    script_path = os.path.join(SCRIPT_DIR, "combine.py")

    if not os.path.exists(script_path):
        return f"❌ 错误：找不到 combine.py 脚本，路径: {script_path}"

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=SCRIPT_DIR
        )

        if result.returncode == 0:
            return f"✅ 数据合并成功！\n{result.stdout}"
        else:
            return f"❌ 数据合并失败：\n{result.stderr}"

    except Exception as e:
        return f"❌ 执行失败: {str(e)}"