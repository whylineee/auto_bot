from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field


class StoredLinkedInAccount(BaseModel):
    access_token: str = Field(min_length=10)
    expires_at_epoch: int
    person_id: str = Field(min_length=2)
    refresh_token: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None


class LinkedInAccountsStore(BaseModel):
    users: Dict[str, StoredLinkedInAccount] = {}


class LinkedInTokenRepository:
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path

    async def get_user(self, telegram_user_id: int) -> Optional[StoredLinkedInAccount]:
        store = await self._load_store()
        return store.users.get(str(telegram_user_id))

    async def save_user(self, telegram_user_id: int, account: StoredLinkedInAccount) -> None:
        store = await self._load_store()
        store.users[str(telegram_user_id)] = account
        await self._save_store(store)

    async def delete_user(self, telegram_user_id: int) -> None:
        store = await self._load_store()
        key = str(telegram_user_id)
        if key not in store.users:
            return
        del store.users[key]
        await self._save_store(store)

    async def _load_store(self) -> LinkedInAccountsStore:
        if not self._storage_path.exists():
            return LinkedInAccountsStore(users={})

        payload = await asyncio.to_thread(self._storage_path.read_text, "utf-8")
        if not payload.strip():
            return LinkedInAccountsStore(users={})

        data = json.loads(payload)

        # Backward compatibility: legacy single-token schema.
        if isinstance(data, dict) and "users" not in data and "access_token" in data:
            return LinkedInAccountsStore(users={})

        return LinkedInAccountsStore.model_validate(data)

    async def _save_store(self, store: LinkedInAccountsStore) -> None:
        await asyncio.to_thread(self._ensure_parent_dir)
        serialized = store.model_dump_json(indent=2)
        await asyncio.to_thread(self._storage_path.write_text, serialized, "utf-8")

    def _ensure_parent_dir(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
