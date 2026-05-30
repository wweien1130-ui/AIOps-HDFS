from utils.path_tool import get_abs_path
from utils.config_handler import prompts_config
from utils.logger_handler import logger


def _load_prompt_file(key: str, fallback: str = "") -> str:
    """通用提示词加载器，统一处理异常和空内容回退。"""
    try:
        path = get_abs_path(prompts_config["prompt_files"][key])
    except KeyError:
        logger.error(f"[prompt_loader] 配置中缺少键: {key}")
        return fallback

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if not content:
            logger.warning(f"[prompt_loader] 提示词文件为空: {path}")
            return fallback
        logger.info(f"[prompt_loader] 成功加载: {path}")
        return content
    except FileNotFoundError:
        logger.error(f"[prompt_loader] 提示词文件不存在: {path}")
        return fallback


def load_system_prompts() -> str:
    return _load_prompt_file("main_prompt", "你是一位HDFS诊断专家。")


def load_rag_prompts() -> str:
    return _load_prompt_file("rag_summarize", "")


def load_report_prompts() -> str:
    return _load_prompt_file("report_prompt", "")


def load_supervisor_prompt() -> str:
    return _load_prompt_file("supervisor_prompt", "你是意图路由分发器，分析用户输入并输出意图标签。")


def load_diagnosis_prompt() -> str:
    return _load_prompt_file("diagnosis_prompt", load_system_prompts())


def load_data_prompt() -> str:
    return _load_prompt_file("data_prompt", load_system_prompts())


def load_monitor_prompt() -> str:
    return _load_prompt_file("monitor_prompt", "")


def load_ops_prompt() -> str:
    return _load_prompt_file("ops_prompt", load_system_prompts())


if __name__ == "__main__":
    print("=== Supervisor ===")
    print(load_supervisor_prompt())
    print("\n=== Diagnosis ===")
    print(load_diagnosis_prompt())
    print("\n=== Data ===")
    print(load_data_prompt())
    print("\n=== Monitor ===")
    print(load_monitor_prompt())
