from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class AutopostSettings(BaseModel):
    enabled: bool = False
    chat_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    interval_minutes: int = Field(default=120, ge=30, le=1440)
    style: str = "analytical"
    last_posted_news_link: Optional[str] = None
    last_run_epoch: Optional[int] = None


class AutopostSettingsRepository:
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path

    async def get(self) -> AutopostSettings:
        if not self._storage_path.exists():
            return AutopostSettings()

        raw = await asyncio.to_thread(self._storage_path.read_text, "utf-8")
        if not raw.strip():
            return AutopostSettings()

        data = json.loads(raw)
        return AutopostSettings.model_validate(data)

    async def save(self, settings: AutopostSettings) -> None:
        await asyncio.to_thread(self._ensure_parent)
        serialized = settings.model_dump_json(indent=2)
        await asyncio.to_thread(self._storage_path.write_text, serialized, "utf-8")

    def _ensure_parent(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
