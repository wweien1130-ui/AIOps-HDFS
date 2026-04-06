import yaml

from utils.path_tool import get_abs_path

def load_agent_config(config_path:str = get_abs_path("config/agent.yml"),encoding="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_base_config(config_path:str = get_abs_path("config/base.yml"),encoding="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_chroma_config(config_path:str = get_abs_path("config/chroma.yml"),encoding="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_llm_config(config_path:str = get_abs_path("config/llm.yml"),encoding="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_prompts_config(config_path:str = get_abs_path("config/prompts.yml"),encoding="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)

def load_rag_config(config_path:str = get_abs_path("config/rag.yml"),encoding="utf-8"):
    with open(config_path,"r",encoding=encoding) as f:
        return yaml.load(f,Loader=yaml.FullLoader)


agent_conf = load_agent_config()
base_config = load_base_config()
chroma_config = load_chroma_config()
llm_config = load_llm_config()
prompts_config = load_prompts_config()
rag_config = load_rag_config()




