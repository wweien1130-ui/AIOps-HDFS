"""
模型注册表 — 按名称管理所有可用 LLM 模型，支持动态构建和缓存。

模型来源：
  - config/llm.yml → ollama.models.options（本地 Ollama 模型）
  - config/llm.yml → qwen.models.options（云端 DashScope 模型）
"""

from langchain_core.language_models import BaseChatModel
from utils.config_handler import llm_config
from utils.logger_handler import logger


class ModelRegistry:

    def __init__(self):
        self._cache: dict[str, BaseChatModel] = {}
        self._ollama_base_url = llm_config.get("ollama", {}).get("base_url", "http://localhost:11434")
        self._ollama_models: list[str] = llm_config.get("ollama", {}).get("models", {}).get("options", [])
        self._cloud_models: list[str] = llm_config.get("qwen", {}).get("models", {}).get("options", [])
        self._cloud_default: str = llm_config.get("qwen", {}).get("models", {}).get("default", "")

    def get_model(self, name: str) -> BaseChatModel:
        if name not in self._cache:
            self._cache[name] = self._build(name)
        return self._cache[name]

    def get_ollama_model(self) -> BaseChatModel:
        default = llm_config.get("ollama", {}).get("models", {}).get("default", "qwen3:8b")
        return self.get_model(default)

    def get_cloud_model(self) -> BaseChatModel:
        return self.get_model(self._cloud_default)

    def list_models(self) -> dict:
        ollama_default = llm_config.get("ollama", {}).get("models", {}).get("default", "")
        local = [{"name": m, "label": m, "provider": "ollama", "is_default": m == ollama_default} for m in self._ollama_models]
        cloud = [{"name": m, "label": m, "provider": "dashscope", "is_default": m == self._cloud_default} for m in self._cloud_models]
        return {
            "local": local,
            "cloud": cloud,
            "defaults": {"local": ollama_default, "cloud": self._cloud_default},
        }

    def _build(self, name: str) -> BaseChatModel:
        if name in self._ollama_models:
            return self._build_ollama(name)
        return self._build_cloud(name)

    def _build_ollama(self, model_name: str) -> BaseChatModel:
        from langchain_ollama import ChatOllama
        logger.info(f"[ModelRegistry] 构建 Ollama 模型: {model_name}")
        return ChatOllama(
            model=model_name,
            base_url=self._ollama_base_url,
            temperature=0.7,
            num_predict=1024,
        )

    def _build_cloud(self, model_name: str) -> BaseChatModel:
        from langchain_community.chat_models import ChatTongyi
        logger.info(f"[ModelRegistry] 构建云端模型: {model_name}")
        return ChatTongyi(model=model_name)


registry = ModelRegistry()
