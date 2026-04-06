from abc import abstractmethod, ABC
from typing import Optional

from langchain_community.chat_models import ChatTongyi
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from utils.config_handler import rag_config

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self)->Optional[ Embeddings | BaseChatModel]:
        pass

class ChatModelFactory(BaseModelFactory):
    def generator(self) ->Optional[ Embeddings | BaseChatModel]:
        return ChatTongyi(model = rag_config["vector_store"]["chat_model"])

class EmbeddingsFactory(BaseModelFactory):
    def generator(self) ->Optional[ Embeddings | BaseChatModel]:
        return DashScopeEmbeddings(model=rag_config["vector_store"]["embedding"]["model"])


chat_models = ChatModelFactory().generator()
embedding_models = EmbeddingsFactory().generator()