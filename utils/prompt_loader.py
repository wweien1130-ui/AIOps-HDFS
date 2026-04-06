
from utils.path_tool import get_abs_path
from utils.config_handler import prompts_config
from utils.logger_handler import logger

def load_system_prompts():
    try:
        system_prompt_path = get_abs_path(prompts_config["prompt_files"]["main_prompt"])
    except KeyError as e:
        logger.error(f"[load_system_prompts] 在yaml配置中缺少main_prompt路径: {e}")
        return None

    try:
        with open(system_prompt_path,"r",encoding="utf-8") as f:
            content = f.read()
        logger.info(f"[load_system_prompts] 成成功加载岗位说明书提示词: {system_prompt_path}")
        return content
    except FileNotFoundError as e:
        logger.error(f"[load_system_prompts] 提示词文件不存在: {system_prompt_path}")
        return None


def load_rag_prompts():
    try:
        rag_prompt_path = get_abs_path(prompts_config["prompt_files"]["rag_summarize"])
    except KeyError as e:
        logger.error(f"[load_rag_prompts] 在yaml配置中缺少rag_summarize路径: {e}")
        return None

    try:
        with open(rag_prompt_path,"r",encoding="utf-8") as f:
            content = f.read()
        logger.info(f"[load_rag_prompts] 成成功加载rag_summarize提示词: {rag_prompt_path}")
        return content
    except FileNotFoundError as e:
        logger.error(f"[load_rag_prompts] 提示词文件不存在 {rag_prompt_path}")
        return None

def load_report_prompts():
    try:
        report_prompt_path = get_abs_path(prompts_config["prompt_files"]["report_prompt"])
    except KeyError as e:
        logger.error(f"[load_report_prompts] 在yaml配置中缺少report_prompt路径: {e}")
        return None

    try:
       with open(report_prompt_path ,"r",encoding="utf-8") as f:
           content = f.read()
           logger.info(f"[load_report_prompts] 成成功加载report_prompt提示词: {report_prompt_path}")
           return content
    except FileNotFoundError as e:
        logger.error(f"[load_report_prompts] 提示词文件不存在 {report_prompt_path}")
        return None


if __name__ == "__main__":
    print(load_rag_prompts())