from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings

from eventflow.config import Settings, get_settings
from eventflow.core.nodes.base import Node
from eventflow.core.task import TaskContext


class ModelProvider(str, Enum):
    GROQ = "groq"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"
    GOOGLE_GEMINI = "google_gemini"
    OLLAMA = "ollama"


class MissingProviderKeyError(RuntimeError):
    pass


@dataclass
class AgentConfig:
    model_provider: ModelProvider = ModelProvider.GROQ
    model_name: str | None = None
    output_type: Any = str
    instructions: str | None = None
    deps_type: type[Any] | None = None
    name: str | None = None
    model_settings: ModelSettings | None = None
    retries: int = 2
    tools: list[Any] = field(default_factory=list)
    model: Model | None = None


def _secret(settings: Settings, field_name: str, provider: ModelProvider) -> str:
    value = getattr(settings, field_name)
    if value is None:
        raise MissingProviderKeyError(
            f"{field_name.upper()} is required for provider {provider.value}"
        )
    return value.get_secret_value()


def build_model(provider: ModelProvider, model_name: str, settings: Settings) -> Model:
    if provider is ModelProvider.GROQ:
        from pydantic_ai.models.groq import GroqModel
        from pydantic_ai.providers.groq import GroqProvider

        api_key = _secret(settings, "groq_api_key", provider)
        return GroqModel(model_name, provider=GroqProvider(api_key=api_key))

    if provider is ModelProvider.OPENAI:
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = _secret(settings, "openai_api_key", provider)
        return OpenAIResponsesModel(model_name, provider=OpenAIProvider(api_key=api_key))

    if provider is ModelProvider.AZURE_OPENAI:
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.azure import AzureProvider

        if not settings.azure_openai_endpoint:
            raise MissingProviderKeyError("AZURE_OPENAI_ENDPOINT is required for azure_openai")
        azure = AzureProvider(
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            api_key=_secret(settings, "azure_openai_api_key", provider),
        )
        return OpenAIResponsesModel(model_name, provider=azure)

    if provider is ModelProvider.ANTHROPIC:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        api_key = _secret(settings, "anthropic_api_key", provider)
        return AnthropicModel(model_name, provider=AnthropicProvider(api_key=api_key))

    if provider is ModelProvider.GOOGLE_GEMINI:
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        api_key = _secret(settings, "google_api_key", provider)
        return GoogleModel(model_name, provider=GoogleProvider(api_key=api_key))

    if provider is ModelProvider.OLLAMA:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.ollama import OllamaProvider

        return OpenAIChatModel(
            model_name, provider=OllamaProvider(base_url=settings.ollama_base_url)
        )

    raise ValueError(f"Unsupported model provider: {provider}")


class AgentNode(Node, ABC):
    class DepsType(BaseModel):
        pass

    class OutputType(BaseModel):
        pass

    model_override: Model | None = None

    def __init__(self, task_context: TaskContext | None = None):
        super().__init__(task_context=task_context)
        config = self.get_agent_config()
        self.agent = Agent(
            model=self._resolve_model(config),
            output_type=config.output_type,
            instructions=config.instructions,
            deps_type=config.deps_type or type(None),
            name=config.name or self.node_name,
            model_settings=config.model_settings,
            retries=config.retries,
            tools=config.tools,
        )

    @abstractmethod
    def get_agent_config(self) -> AgentConfig:
        raise NotImplementedError

    @abstractmethod
    async def process(self, task_context: TaskContext) -> TaskContext:
        raise NotImplementedError

    def _resolve_model(self, config: AgentConfig) -> Model:
        override = type(self).model_override or AgentNode.model_override
        if override is not None:
            return override
        if config.model is not None:
            return config.model
        settings = get_settings()
        model_name = config.model_name or settings.default_model_name
        return build_model(config.model_provider, model_name, settings)
