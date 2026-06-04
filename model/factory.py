from abc import abstractmethod, ABC
from typing import Optional

from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from utils.config_handler import rag_config, llm_config


def _build_ollama_model() -> BaseChatModel:
    """构建本地 Ollama 模型（用于简单任务：Supervisor 路由、General、Monitor）"""
    from langchain_ollama import ChatOllama
    base_url = llm_config["ollama"]["base_url"]
    model_name = llm_config["ollama"]["models"]["default"]
    return ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.7,
        num_predict=1024,
    )


def _build_cloud_model() -> BaseChatModel:
    """构建云端 Qwen 模型（用于复杂任务：Diagnosis、Data、Ops）"""
    model_name = llm_config["qwen"]["models"]["default"]
    return ChatTongyi(model=model_name)


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return _build_cloud_model()


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        return DashScopeEmbeddings(model=rag_config["vector_store"]["embedding"]["model"])


# 云端模型（复杂任务）
chat_models = ChatModelFactory().generator()
# 本地 Ollama 模型（简单任务）
ollama_model = _build_ollama_model()
# Embedding 模型
embedding_models = EmbeddingsFactory().generator()

# 模型注册表（动态切换）
from model.registry import registry

def get_model(name: str) -> BaseChatModel:
    return registry.get_model(name)
