from __future__ import annotations

import logging
import re
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx
from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    title: str = Field(min_length=3)
    summary: str
    link: str = Field(min_length=5)
    published_at: Optional[datetime] = None


@dataclass(frozen=True)
class NewsSource:
    name: str
    url: str


class NewsService:
    _TAG_RE = re.compile(r"<[^>]+>")

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        logger: logging.Logger,
        keywords: list[str],
        timeout_seconds: float,
    ) -> None:
        self._http_client = http_client
        self._logger = logger
        self._keywords = [kw.lower() for kw in keywords]
        self._timeout_seconds = timeout_seconds
        self._sources: tuple[NewsSource, ...] = (
            NewsSource(name="HackerNews", url="https://news.ycombinator.com/rss"),
            NewsSource(name="TechCrunch AI", url="https://techcrunch.com/category/artificial-intelligence/feed/"),
        )

    async def fetch_latest_news(self, limit: int = 10) -> list[NewsItem]:
        responses = await self._fetch_all_sources()
        raw_items: list[NewsItem] = []

        for source_name, feed_content in responses:
            feed = feedparser.parse(feed_content)
            for entry in feed.entries:
                title = str(getattr(entry, "title", "")).strip()
                link = str(getattr(entry, "link", "")).strip()
                raw_summary = str(getattr(entry, "summary", "") or getattr(entry, "description", "")).strip()
                summary = self._clean_summary(raw_summary)

                if not title or not link:
                    continue

                if not self._matches_keywords(title=title, summary=summary):
                    continue

                published_at = self._extract_published_at(entry)
                raw_items.append(
                    NewsItem(
                        title=title,
                        summary=summary,
                        link=link,
                        published_at=published_at,
                    )
                )

            self._logger.info("Loaded feed items from %s", source_name)

        unique: dict[str, NewsItem] = {}
        for item in raw_items:
            if item.link not in unique:
                unique[item.link] = item

        sorted_items = sorted(
            unique.values(),
            key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

        return sorted_items[:limit]

    async def _fetch_all_sources(self) -> list[tuple[str, str]]:
        tasks = [self._fetch_source(source) for source in self._sources]
        raw_results = await asyncio.gather(*tasks)
        return [result for result in raw_results if result[1]]

    async def _fetch_source(self, source: NewsSource) -> tuple[str, str]:
        try:
            response = await self._http_client.get(source.url, timeout=self._timeout_seconds)
            response.raise_for_status()
            return source.name, response.text
        except httpx.HTTPError as exc:
            self._logger.error("Failed to fetch source %s: %s", source.name, exc)
            return source.name, ""

    def _matches_keywords(self, title: str, summary: str) -> bool:
        haystack = f"{title} {summary}".lower()
        return any(keyword in haystack for keyword in self._keywords)

    def _clean_summary(self, summary: str) -> str:
        normalized = self._TAG_RE.sub(" ", summary)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized[:600]

    def _extract_published_at(self, entry: feedparser.FeedParserDict) -> Optional[datetime]:
        published = str(getattr(entry, "published", "") or getattr(entry, "updated", "")).strip()
        if not published:
            return None
        try:
            dt = parsedate_to_datetime(published)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
