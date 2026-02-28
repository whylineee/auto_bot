from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


class AppConfig(BaseModel):
    telegram_bot_token: str = Field(min_length=10)
    qwen_api_key: str = Field(min_length=10)
    qwen_api_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    qwen_model: str = "qwen-plus"

    linkedin_access_token: str = ""
    linkedin_person_id: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = ""
    linkedin_scopes: list[str] = ["openid", "profile", "w_member_social"]
    linkedin_token_store_path: Path = Path(".data/linkedin_token.json")
    autopost_settings_path: Path = Path(".data/autopost_settings.json")
    autopost_default_interval_minutes: int = 120
    autopost_default_style: str = "analytical"

    http_timeout_seconds: float = 20.0
    ai_request_timeout_seconds: float = 90.0
    ai_max_retries: int = 3
    ai_retry_backoff_seconds: float = 1.5
    log_level: str = "INFO"

    news_limit: int = 10
    news_keywords: list[str] = ["ai", "programming", "startup", "open source"]


_REQUIRED_KEYS: tuple[str, ...] = (
    "TELEGRAM_BOT_TOKEN",
)


def _missing_keys(keys: Iterable[str]) -> list[str]:
    return [key for key in keys if not os.getenv(key)]


def _clean_placeholder(value: str) -> str:
    normalized = value.strip()
    lowered = normalized.lower()
    if not normalized:
        return ""
    if lowered.startswith("your_"):
        return ""
    if "your-domain.com" in lowered:
        return ""
    return normalized


def load_config() -> AppConfig:
    load_dotenv()

    missing = _missing_keys(_REQUIRED_KEYS)
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    llm_api_key = (
        os.getenv("QWEN_API_KEY", "").strip()
        or os.getenv("NVIDIA_API_KEY", "").strip()
    )
    if not llm_api_key:
        raise ValueError("Missing LLM API key: set QWEN_API_KEY or NVIDIA_API_KEY")

    default_api_url = (
        "https://integrate.api.nvidia.com/v1/chat/completions"
        if os.getenv("NVIDIA_API_KEY")
        else "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
    )
    default_model = (
        "qwen/qwen2-7b-instruct"
        if os.getenv("NVIDIA_API_KEY")
        else "qwen-plus"
    )

    keywords = os.getenv("NEWS_KEYWORDS", "ai,programming,startup,open source")
    parsed_keywords = [item.strip().lower() for item in keywords.split(",") if item.strip()]
    parsed_scopes = [item.strip() for item in os.getenv("LINKEDIN_SCOPES", "openid,profile,w_member_social").split(",") if item.strip()]
    linkedin_person_id = _clean_placeholder(os.getenv("LINKEDIN_PERSON_ID", ""))

    try:
        return AppConfig(
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            qwen_api_key=llm_api_key,
            qwen_api_url=os.getenv(
                "QWEN_API_URL",
                default_api_url,
            ),
            qwen_model=os.getenv("QWEN_MODEL", default_model),
            linkedin_access_token=_clean_placeholder(os.getenv("LINKEDIN_ACCESS_TOKEN", "")),
            linkedin_person_id=linkedin_person_id,
            linkedin_client_id=_clean_placeholder(os.getenv("LINKEDIN_CLIENT_ID", "")),
            linkedin_client_secret=_clean_placeholder(os.getenv("LINKEDIN_CLIENT_SECRET", "")),
            linkedin_redirect_uri=_clean_placeholder(os.getenv("LINKEDIN_REDIRECT_URI", "")),
            linkedin_scopes=parsed_scopes,
            linkedin_token_store_path=Path(
                os.getenv("LINKEDIN_TOKEN_STORE_PATH", ".data/linkedin_token.json")
            ),
            autopost_settings_path=Path(
                os.getenv("AUTOPOST_SETTINGS_PATH", ".data/autopost_settings.json")
            ),
            autopost_default_interval_minutes=int(
                os.getenv("AUTOPOST_DEFAULT_INTERVAL_MINUTES", "120")
            ),
            autopost_default_style=os.getenv("AUTOPOST_DEFAULT_STYLE", "analytical"),
            http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
            ai_request_timeout_seconds=float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "90")),
            ai_max_retries=int(os.getenv("AI_MAX_RETRIES", "3")),
            ai_retry_backoff_seconds=float(os.getenv("AI_RETRY_BACKOFF_SECONDS", "1.5")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            news_limit=int(os.getenv("NEWS_LIMIT", "10")),
            news_keywords=parsed_keywords,
        )
    except ValidationError as exc:
        raise ValueError(f"Invalid configuration: {exc}") from exc
