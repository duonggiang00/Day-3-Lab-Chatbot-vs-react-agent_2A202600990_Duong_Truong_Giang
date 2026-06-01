"""
Khởi tạo LLM provider theo biến môi trường.
Hỗ trợ: mimo | openai | google | local
"""
import os
from typing import Tuple

from dotenv import load_dotenv

from src.core.llm_provider import LLMProvider
from src.core.openai_provider import OpenAIProvider
from src.core.local_provider import LocalProvider

MIMO_PAYG_BASE_URL = "https://api.xiaomimimo.com/v1"
# Token Plan: lấy Base URL từ https://platform.xiaomimimo.com → Subscription
MIMO_TOKEN_PLAN_BASE_URL = "https://token-plan-sgp.xiaomimimo.com/v1"


def _resolve_mimo_base_url(api_key: str) -> str:
    """Key tp-* dùng Token Plan URL; key sk-* dùng pay-as-you-go URL."""
    configured = os.getenv("MIMO_BASE_URL", "").strip()
    if configured:
        return configured
    if api_key.startswith("tp-"):
        return MIMO_TOKEN_PLAN_BASE_URL
    return MIMO_PAYG_BASE_URL


def get_llm_provider() -> Tuple[LLMProvider, str, str]:
    """
    Returns:
        (provider_instance, provider_name, model_name)
    Raises:
        ValueError: thiếu cấu hình hoặc provider không hỗ trợ
    """
    load_dotenv(override=True)
    provider_name = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    model_name = os.getenv("DEFAULT_MODEL", "gpt-4o")

    if provider_name == "mimo":
        api_key = os.getenv("MIMO_API_KEY")
        if not api_key or api_key == "your_mimo_api_key_here":
            raise ValueError("MIMO_API_KEY is not configured in .env")
        base_url = _resolve_mimo_base_url(api_key)
        provider = OpenAIProvider(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
            provider_id="mimo",
        )
        return provider, provider_name, model_name

    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key_here":
            raise ValueError("OPENAI_API_KEY is not configured in .env")
        provider = OpenAIProvider(model_name=model_name, api_key=api_key)
        return provider, provider_name, model_name

    if provider_name == "google":
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not api_key or api_key == "your_gemini_api_key_here":
            raise ValueError("GEMINI_API_KEY is not configured in .env")
        from src.core.gemini_provider import GeminiProvider

        provider = GeminiProvider(model_name=model_name, api_key=api_key)
        return provider, provider_name, model_name

    if provider_name == "local":
        model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
        if not os.path.exists(model_path):
            raise ValueError(f"Local model not found at {model_path}")
        provider = LocalProvider(model_path=model_path)
        return provider, provider_name, model_name

    raise ValueError(
        f"Unsupported provider '{provider_name}'. "
        "Use one of: mimo, openai, google, local"
    )
