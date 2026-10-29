"""LLM Model factory and configuration for Pydantic AI.

Encapsulates Pydantic AI model provider initialization and client injection,
supporting both OpenAI and Ollama (local or remote GPU) inference backends.
"""

from typing import Optional
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.ollama import OllamaProvider
from aurascribe.utils.config import Settings, get_settings
from aurascribe.utils.errors import ConfigurationError


def get_llm_model(
    model_name: Optional[str] = None,
    settings: Optional[Settings] = None,
    openai_client: Optional[AsyncOpenAI] = None,
) -> OpenAIChatModel:
    """Creates a configured OpenAIChatModel instance for Pydantic AI agents.

    Supports OpenAI and Ollama models (e.g. 'qwen3.5:9b-q8_0', 'gemma4:12b-it-q4_K_M', 'gpt-4o-mini').

    Args:
        model_name: Optional override for the target model.
        settings: Application settings instance.
        openai_client: Optional custom AsyncOpenAI client (e.g. for mock testing).

    Returns:
        OpenAIChatModel: Ready-to-use Pydantic AI model adapter.
    """
    cfg = settings or get_settings()
    target_model = model_name or cfg.llm_model

    if openai_client:
        provider = OpenAIProvider(openai_client=openai_client)
        return OpenAIChatModel(target_model, provider=provider)

    provider_type = (getattr(cfg, "llm_provider", "openai") or "openai").lower().strip()

    if provider_type == "ollama":
        base_url = (getattr(cfg, "ollama_base_url", "http://localhost:11434/v1") or "http://localhost:11434/v1").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        provider = OllamaProvider(base_url=base_url, api_key=cfg.ollama_api_key)
        return OpenAIChatModel(target_model, provider=provider)

    if provider_type in ("llama_cpp", "llamacpp"):
        base_url = (getattr(cfg, "llama_cpp_base_url", "http://localhost:8080/v1") or "http://localhost:8080/v1").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        custom_client = AsyncOpenAI(
            base_url=base_url,
            api_key="llama-cpp-not-needed",
            timeout=cfg.request_timeout_seconds,
        )
        provider = OpenAIProvider(openai_client=custom_client)
        return OpenAIChatModel(target_model, provider=provider)

    if provider_type in ("custom", "openai_compatible"):
        base_url = getattr(cfg, "custom_base_url", None)
        if not base_url:
            raise ConfigurationError(
                "AURASCRIBE_CUSTOM_BASE_URL must be configured when AURASCRIBE_LLM_PROVIDER is 'custom'."
            )
        custom_client = AsyncOpenAI(
            base_url=base_url,
            api_key=cfg.custom_api_key or "custom-key-not-required",
            timeout=cfg.request_timeout_seconds,
        )
        provider = OpenAIProvider(openai_client=custom_client)
        return OpenAIChatModel(target_model, provider=provider)

    api_key = cfg.openai_api_key
    if not api_key:
        raise ConfigurationError(
            "OPENAI_API_KEY must be configured when AURASCRIBE_LLM_PROVIDER is 'openai'. "
            "Set AURASCRIBE_LLM_PROVIDER=ollama to use a local or remote Ollama model."
        )

    custom_client = AsyncOpenAI(
        api_key=api_key,
        timeout=cfg.request_timeout_seconds,
    )
    provider = OpenAIProvider(openai_client=custom_client)
    return OpenAIChatModel(target_model, provider=provider)


# Backward compatibility alias
get_openai_model = get_llm_model


