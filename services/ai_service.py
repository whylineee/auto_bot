from __future__ import annotations

import asyncio
import logging
import re
from enum import Enum
from typing import List, Optional

import httpx

from services.news_service import NewsItem


class AIServiceError(Exception):
    pass


class AIValidationError(AIServiceError):
    pass


class PostStyle(str, Enum):
    EXPERT = "expert"
    PROVOCATIVE = "provocative"
    ANALYTICAL = "analytical"
    SHORT = "short"


class AIService:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        logger: logging.Logger,
        api_key: str,
        api_url: str,
        model: str,
        timeout_seconds: float,
        max_retries: int,
        retry_backoff_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._logger = logger
        self._api_key = api_key
        self._api_url = api_url
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds

    async def generate_post(self, news: NewsItem, style: PostStyle) -> str:
        last_error: Optional[Exception] = None

        model_candidates = self._build_model_candidates(self._model)

        for attempt in range(1, self._max_retries + 1):
            try:
                for model in model_candidates:
                    response_text = await self._request_generation(news=news, style=style, model=model)
                    normalized = self._normalize_post(post=response_text, style=style)
                    return normalized
            except (httpx.HTTPError, AIValidationError, KeyError, ValueError) as exc:
                last_error = exc
                self._logger.warning(
                    "AI generation attempt %s/%s failed: %s",
                    attempt,
                    self._max_retries,
                    repr(exc),
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_backoff_seconds * attempt)

        raise AIServiceError(f"AI generation failed after retries: {last_error}")

    async def _request_generation(self, news: NewsItem, style: PostStyle, model: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ти senior tech-копірайтер для LinkedIn. Пишеш українською, додаєш аналітику, "
                        "практичні висновки та не робиш сухий переказ новини."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(news=news, style=style),
                },
            ],
            "temperature": 0.7,
            "max_tokens": 700 if style == PostStyle.SHORT else 1200,
        }

        response = await self._http_client.post(
            self._api_url,
            json=payload,
            headers=headers,
            timeout=self._timeout_seconds,
        )
        if response.status_code == 404:
            raise ValueError(
                "NVIDIA endpoint returned 404. Usually this means model id is unavailable for your key. "
                "Try model with provider prefix (e.g. qwen/qwen3.5-397b-a17b) and verify via GET /v1/models."
            )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Empty AI response content")

        return content.strip()

    def _build_prompt(self, news: NewsItem, style: PostStyle) -> str:
        style_map = {
            PostStyle.EXPERT: (
                "Стиль: експертний. Тон впевнений, практичний, з фокусом на застосування в бізнесі та розробці."
            ),
            PostStyle.PROVOCATIVE: (
                "Стиль: провокаційний. Тон сміливий, дискусійний, але без токсичності чи образ."
            ),
            PostStyle.ANALYTICAL: (
                "Стиль: аналітичний. Використай структуру: сигнал, наслідки, висновок, наступний крок."
            ),
            PostStyle.SHORT: (
                "Стиль: короткий. Стисла, енергійна версія з чіткою думкою без води."
            ),
        }

        length_rule = (
            "Довжина: 300-600 символів."
            if style == PostStyle.SHORT
            else "Довжина: 800-1200 символів."
        )

        return (
            "Згенеруй пост для LinkedIn за новиною:\n"
            f"Заголовок: {news.title}\n"
            f"Короткий опис: {news.summary}\n"
            f"Посилання: {news.link}\n\n"
            f"{style_map[style]}\n"
            f"{length_rule}\n"
            "Обов'язково:\n"
            "1) Українська мова.\n"
            "2) Додай 3-5 хештегів наприкінці.\n"
            "3) Пост має завершуватись питанням.\n"
            "4) Дай аналітику і практичний кут.\n"
            "5) Не роби сухий переказ новини.\n"
            "Поверни лише готовий текст поста, без пояснень."
        )

    def _normalize_post(self, post: str, style: PostStyle) -> str:
        cleaned = post.strip()
        length = len(cleaned)

        if style == PostStyle.SHORT:
            if length < 180:
                raise AIValidationError("Short style post is too short")
            if length > 900:
                cleaned = cleaned[:900].rstrip()
        else:
            # Keep quality guardrails but avoid dropping useful outputs from real models.
            if length < 550:
                raise AIValidationError("Post is too short for non-short style")
            if length > 1600:
                cleaned = cleaned[:1600].rstrip()

        hashtags = re.findall(r"#\w+", cleaned, flags=re.UNICODE)
        if len(hashtags) < 3:
            missing = 3 - len(hashtags)
            default_tags = ["#AI", "#Tech", "#LinkedIn", "#Innovation", "#Startup"]
            cleaned = f"{cleaned}\n" + " ".join(default_tags[:missing])

        if not cleaned.endswith("?"):
            cleaned = f"{cleaned}\n\nЩо ви про це думаєте?"

        if "\n" not in cleaned:
            midpoint = len(cleaned) // 2
            cleaned = f"{cleaned[:midpoint].rstrip()}\n\n{cleaned[midpoint:].lstrip()}"

        return cleaned

    def _build_model_candidates(self, model: str) -> List[str]:
        model_name = model.strip()
        if not model_name:
            return [model_name]

        if "integrate.api.nvidia.com" not in self._api_url:
            return [model_name]

        if "/" in model_name:
            return [model_name]

        lowered = model_name.lower()
        if lowered.startswith("qwen"):
            return [f"qwen/{model_name}", model_name]

        return [model_name]
