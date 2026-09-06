"""Search-provider adapters with an explicit offline fixture mode."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping
from typing import Any, Protocol

from offerlens_agent.config import Settings
from offerlens_agent.domain.models import ResearchTask, Source


class SearchProvider(Protocol):
    """Minimal search contract consumed by the research agents."""

    async def search(self, task: ResearchTask, max_results: int = 5) -> list[Source]: ...


def _source_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


class FixtureSearchProvider:
    """Deterministic sources that make the entire product demoable without keys."""

    async def search(self, task: ResearchTask, max_results: int = 5) -> list[Source]:
        templates = {
            "company": [
                "演示数据：公司公开信息调研应覆盖产品、客户、商业模式与近期变化。",
                "演示数据：面试前需要用公司官网和可信新闻源交叉验证关键信息。",
            ],
            "role": [
                "演示数据：Agent 工程岗位通常同时考察编排、检索、评测和工程化能力。",
                "演示数据：可观测性、失败恢复和结构化输出是生产级 Agent 的常见要求。",
            ],
            "interview": [
                "演示数据：面试题应追问状态管理、工具调用、幻觉控制与评测设计。",
                "演示数据：项目讲解需要区分开源底座与候选人独立完成的改造。",
            ],
            "market": [
                "演示数据：岗位要求会随地区、级别和业务方向变化，不能将样例当作实时市场结论。",
            ],
        }
        return [
            Source(
                id=_source_id("fixture", f"{task.id}-{index}-{snippet}"),
                title=f"OfferLens 离线演示资料：{task.topic} {index}",
                snippet=snippet,
                source_type="fixture",
            )
            for index, snippet in enumerate(templates.get(task.topic, templates["role"]), start=1)
        ][:max_results]


class TavilySearchProvider:
    """Tavily adapter imported lazily so core demo mode stays lightweight."""

    def __init__(self, api_key: str | None = None) -> None:
        from tavily import AsyncTavilyClient  # type: ignore[import-not-found,import-untyped]

        self._client = AsyncTavilyClient(api_key=api_key)

    async def search(self, task: ResearchTask, max_results: int = 5) -> list[Source]:
        response = await self._client.search(task.query, max_results=max_results, search_depth="advanced")
        rows = response.get("results", []) if isinstance(response, Mapping) else []
        return [_row_to_source(row, task.id, index) for index, row in enumerate(rows, start=1)]


class DuckDuckGoSearchProvider:
    """Key-free live web search adapter."""

    async def search(self, task: ResearchTask, max_results: int = 5) -> list[Source]:
        from ddgs import DDGS  # type: ignore[import-not-found]

        rows = await asyncio.to_thread(lambda: list(DDGS().text(task.query, max_results=max_results)))
        return [_row_to_source(row, task.id, index) for index, row in enumerate(rows, start=1)]


def _row_to_source(row: Mapping[str, Any], task_id: str, index: int) -> Source:
    url = str(row.get("url") or row.get("href") or "").strip() or None
    title = str(row.get("title") or f"Search result {index}").strip()
    snippet = str(row.get("content") or row.get("body") or row.get("snippet") or "").strip()
    return Source(
        id=_source_id("web", url or f"{task_id}-{index}-{title}"),
        title=title[:300],
        url=url,
        snippet=snippet[:3000],
        source_type="web",
    )


def build_search_provider(settings: Settings) -> SearchProvider:
    """Create the configured provider and fail clearly for missing extras."""
    if settings.search_provider == "fixture":
        return FixtureSearchProvider()
    if settings.search_provider == "tavily":
        return TavilySearchProvider()
    return DuckDuckGoSearchProvider()
