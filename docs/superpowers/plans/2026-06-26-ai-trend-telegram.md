# AI Trend Telegram Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python service that collects AI trend items from curated sources, stores and deduplicates them, ranks them, and sends one Telegram digest per day with direct source links.

**Architecture:** Use a small Python package with focused modules for config, storage, collectors, ranking, digest formatting, Telegram delivery, and CLI entrypoints. Persist all collected items in SQLite, compute rule-based scores from normalized source signals, and publish the digest from stored records rather than live fetch results.

**Tech Stack:** Python 3.12, pytest, SQLAlchemy, httpx, feedparser, BeautifulSoup, Typer, Telegram Bot API, SQLite

---

## Current Sync Status (2026-06-27)

This section reflects the current workspace state against the plan.

- Task 1: implemented and verified
  - `tests/test_config.py` passes
- Task 2: implemented and verified
  - repository/storage layer exists
  - `tests/test_repository.py` passes
- Task 3: implemented and verified
  - collector modules exist
  - `tests/test_collectors.py` passes
- Task 4: implemented and verified
  - `dedup.py`, `tagging.py`, `scoring.py` exist
  - targeted unit tests pass
- Task 5: implemented and verified
  - `digest.py` exists
  - `tests/test_digest.py` passes
- Task 6: implemented and verified
  - `telegram.py` exists
  - `tests/test_pipeline.py` passes
- Task 7: implemented and verified
  - `pipeline.py`, `cli.py`, `tests/test_pipeline.py` exist
  - `build_daily_digest()` passes targeted tests
  - CLI commands now run the collect/publish wiring
- Task 8: partially verified
  - live collect flow works against public sources in-process
  - dry-run publish renders a digest from stored items
  - actual Telegram send with a real bot token/chat id is still pending

Latest known local verification:

- `tests/test_config.py`, `tests/test_repository.py`, `tests/test_collectors.py`, `tests/test_dedup.py`, `tests/test_scoring.py`, `tests/test_digest.py`, `tests/test_pipeline.py`: passing
- full `pytest tests` run: passing, `17 passed`
- manual live collect + dry-run publish: passing in a single process, collected `417` items and rendered a digest

## File Structure

Create this structure before writing feature code:

- `pyproject.toml`
  - dependency and test configuration
- `.env.example`
  - environment variable template
- `src/aitrendigest/__init__.py`
  - package marker
- `src/aitrendigest/config.py`
  - environment-backed settings
- `src/aitrendigest/logging.py`
  - application logger setup
- `src/aitrendigest/types.py`
  - shared dataclasses for normalized items and digest entries
- `src/aitrendigest/db.py`
  - SQLAlchemy engine, session factory, schema bootstrap
- `src/aitrendigest/models.py`
  - ORM tables
- `src/aitrendigest/repository.py`
  - item persistence and query operations
- `src/aitrendigest/collectors/base.py`
  - collector protocol and helpers
- `src/aitrendigest/collectors/github_trending.py`
  - GitHub Trending adapter
- `src/aitrendigest/collectors/hf_models.py`
  - Hugging Face trending models adapter
- `src/aitrendigest/collectors/hf_papers.py`
  - Hugging Face trending papers adapter
- `src/aitrendigest/collectors/arxiv.py`
  - arXiv feed adapter
- `src/aitrendigest/collectors/rss.py`
  - generic RSS blog/newsletter adapter
- `src/aitrendigest/collectors/youtube.py`
  - YouTube feed adapter
- `src/aitrendigest/dedup.py`
  - duplicate grouping
- `src/aitrendigest/scoring.py`
  - freshness, popularity, practical-value, cross-source scoring
- `src/aitrendigest/tagging.py`
  - rule-based tagging
- `src/aitrendigest/digest.py`
  - digest entry construction and message rendering
- `src/aitrendigest/telegram.py`
  - Telegram publishing client
- `src/aitrendigest/pipeline.py`
  - collect and publish orchestration
- `src/aitrendigest/cli.py`
  - Typer commands
- `tests/test_config.py`
- `tests/test_repository.py`
- `tests/test_collectors.py`
- `tests/test_dedup.py`
- `tests/test_scoring.py`
- `tests/test_digest.py`
- `tests/test_pipeline.py`

## Task 1: Project Skeleton And Settings

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/aitrendigest/__init__.py`
- Create: `src/aitrendigest/config.py`
- Create: `src/aitrendigest/logging.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing settings test**

```python
from aitrendigest.config import Settings


def test_settings_load_enabled_sources_from_env(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setenv("AIDIGEST_DATABASE_URL", "sqlite:///digest.db")
    monkeypatch.setenv("AIDIGEST_ENABLED_SOURCES", "github_trending,hf_models,arxiv")

    settings = Settings.from_env()

    assert settings.telegram_bot_token == "token"
    assert settings.telegram_chat_id == "12345"
    assert settings.database_url == "sqlite:///digest.db"
    assert settings.enabled_sources == ["github_trending", "hf_models", "arxiv"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`  
Expected: FAIL with `ModuleNotFoundError` or missing `Settings`

- [ ] **Step 3: Add project metadata and dependencies**

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-trend-digest"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "beautifulsoup4>=4.12",
  "feedparser>=6.0",
  "httpx>=0.28",
  "pydantic>=2.8",
  "pydantic-settings>=2.3",
  "sqlalchemy>=2.0",
  "typer>=0.12",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AIDIGEST_", case_sensitive=False)

    telegram_bot_token: str
    telegram_chat_id: str
    database_url: str = "sqlite:///ai_trend_digest.db"
    enabled_sources_raw: str = "github_trending,hf_models,hf_papers,arxiv"
    digest_send_time: str = "09:00"

    @property
    def enabled_sources(self) -> list[str]:
        return [value.strip() for value in self.enabled_sources_raw.split(",") if value.strip()]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
```

```text
AIDIGEST_TELEGRAM_BOT_TOKEN=
AIDIGEST_TELEGRAM_CHAT_ID=
AIDIGEST_DATABASE_URL=sqlite:///ai_trend_digest.db
AIDIGEST_ENABLED_SOURCES=github_trending,hf_models,hf_papers,arxiv
AIDIGEST_DIGEST_SEND_TIME=09:00
```

- [ ] **Step 4: Add lightweight logging setup**

```python
import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example src/aitrendigest/__init__.py src/aitrendigest/config.py src/aitrendigest/logging.py tests/test_config.py
git commit -m "chore: scaffold ai trend digest project"
```

If the repository is still not initialized, run this once first:

```bash
git init
git add .
git commit -m "chore: bootstrap ai trend digest"
```

## Task 2: Shared Types, Database, And Repository

**Files:**
- Create: `src/aitrendigest/types.py`
- Create: `src/aitrendigest/db.py`
- Create: `src/aitrendigest/models.py`
- Create: `src/aitrendigest/repository.py`
- Test: `tests/test_repository.py`

- [ ] **Step 1: Write the failing repository test**

```python
from aitrendigest.db import create_session_factory, create_schema
from aitrendigest.repository import ItemRepository
from aitrendigest.types import TrendItemInput


def test_repository_upserts_item_by_source_identity(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'digest.db'}"
    session_factory = create_session_factory(database_url)
    create_schema(database_url)
    repository = ItemRepository(session_factory)

    item = TrendItemInput(
        source_type="github_trending",
        source_name="GitHub Trending",
        source_item_id="owner/repo",
        title="owner/repo",
        url="https://github.com/owner/repo",
        author="owner",
        published_at=None,
        raw_popularity_signal={"rank": 1, "stars": 1200},
        summary=None,
    )

    first_id = repository.upsert_item(item)
    second_id = repository.upsert_item(item)

    assert first_id == second_id
    assert repository.count_items() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repository.py -v`  
Expected: FAIL because repository or types do not exist

- [ ] **Step 3: Create shared types and ORM schema**

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TrendItemInput:
    source_type: str
    source_name: str
    source_item_id: str
    title: str
    url: str
    author: str | None
    published_at: datetime | None
    raw_popularity_signal: dict[str, int | float | str | None]
    summary: str | None
```

```python
from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime


class Base(DeclarativeBase):
    pass


class TrendItemRecord(Base):
    __tablename__ = "trend_items"
    __table_args__ = (
        UniqueConstraint("source_type", "source_item_id", name="uq_source_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime())
    fetched_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    raw_popularity_signal: Mapped[dict] = mapped_column(JSON, nullable=False)
    normalized_popularity_score: Mapped[float | None]
    summary: Mapped[str | None] = mapped_column(Text())
    why_it_matters: Mapped[str | None] = mapped_column(Text())
    tags: Mapped[str | None] = mapped_column(String(255))
    topic_fingerprint: Mapped[str | None] = mapped_column(String(255))
    duplicate_group_id: Mapped[str | None] = mapped_column(String(255))
    final_score: Mapped[float | None]
    send_status: Mapped[str] = mapped_column(String(30), default="new", nullable=False)
```

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aitrendigest.models import Base


def create_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, future=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_schema(database_url: str) -> None:
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
```

- [ ] **Step 4: Implement repository operations**

```python
from datetime import datetime, timezone
from sqlalchemy import select, func

from aitrendigest.models import TrendItemRecord


class ItemRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def upsert_item(self, item):
        with self._session_factory() as session:
            existing = session.execute(
                select(TrendItemRecord).where(
                    TrendItemRecord.source_type == item.source_type,
                    TrendItemRecord.source_item_id == item.source_item_id,
                )
            ).scalar_one_or_none()
            if existing:
                existing.title = item.title
                existing.url = item.url
                existing.author = item.author
                existing.published_at = item.published_at
                existing.raw_popularity_signal = item.raw_popularity_signal
                existing.summary = item.summary
                existing.fetched_at = datetime.now(timezone.utc)
                session.commit()
                return existing.id

            record = TrendItemRecord(
                source_type=item.source_type,
                source_name=item.source_name,
                source_item_id=item.source_item_id,
                title=item.title,
                url=item.url,
                author=item.author,
                published_at=item.published_at,
                fetched_at=datetime.now(timezone.utc),
                raw_popularity_signal=item.raw_popularity_signal,
                summary=item.summary,
                send_status="new",
            )
            session.add(record)
            session.commit()
            return record.id

    def count_items(self) -> int:
        with self._session_factory() as session:
            return session.execute(select(func.count(TrendItemRecord.id))).scalar_one()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_repository.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/aitrendigest/types.py src/aitrendigest/db.py src/aitrendigest/models.py src/aitrendigest/repository.py tests/test_repository.py
git commit -m "feat: add storage and repository layer"
```

## Task 3: Collector Interfaces And Core Source Adapters

**Files:**
- Create: `src/aitrendigest/collectors/base.py`
- Create: `src/aitrendigest/collectors/github_trending.py`
- Create: `src/aitrendigest/collectors/hf_models.py`
- Create: `src/aitrendigest/collectors/hf_papers.py`
- Create: `src/aitrendigest/collectors/arxiv.py`
- Create: `src/aitrendigest/collectors/rss.py`
- Create: `src/aitrendigest/collectors/youtube.py`
- Test: `tests/test_collectors.py`

- [ ] **Step 1: Write failing normalization tests for collectors**

```python
from aitrendigest.collectors.github_trending import parse_github_trending_html
from aitrendigest.collectors.arxiv import parse_arxiv_feed


def test_parse_github_trending_html_returns_normalized_item():
    html = """
    <article class="Box-row">
      <h2><a href="/owner/repo"> owner / repo </a></h2>
      <a href="/owner/repo/stargazers">1,234</a>
    </article>
    """

    items = parse_github_trending_html(html)

    assert len(items) == 1
    assert items[0].source_item_id == "owner/repo"
    assert items[0].raw_popularity_signal["stars"] == 1234


def test_parse_arxiv_feed_returns_entry_title_and_url():
    feed = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/1234.5678v1</id>
        <title>Agent Evaluation Systems</title>
      </entry>
    </feed>
    """

    items = parse_arxiv_feed(feed)

    assert items[0].title == "Agent Evaluation Systems"
    assert items[0].url == "http://arxiv.org/abs/1234.5678v1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_collectors.py -v`  
Expected: FAIL because parser functions do not exist

- [ ] **Step 3: Add collector protocol and GitHub/arXiv parsers**

```python
from collections.abc import Iterable
from typing import Protocol

from aitrendigest.types import TrendItemInput


class Collector(Protocol):
    source_name: str
    source_type: str

    async def collect(self) -> Iterable[TrendItemInput]:
        raise NotImplementedError
```

```python
from bs4 import BeautifulSoup

from aitrendigest.types import TrendItemInput


def parse_github_trending_html(html: str) -> list[TrendItemInput]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[TrendItemInput] = []
    for rank, article in enumerate(soup.select("article.Box-row"), start=1):
        href = article.select_one("h2 a")["href"].strip("/")
        stars_text = article.select("a")[-1].get_text(strip=True).replace(",", "")
        items.append(
            TrendItemInput(
                source_type="github_trending",
                source_name="GitHub Trending",
                source_item_id=href,
                title=href,
                url=f"https://github.com/{href}",
                author=href.split("/")[0],
                published_at=None,
                raw_popularity_signal={"rank": rank, "stars": int(stars_text)},
                summary=None,
            )
        )
    return items
```

```python
import feedparser

from aitrendigest.types import TrendItemInput


def parse_arxiv_feed(xml_text: str) -> list[TrendItemInput]:
    parsed = feedparser.parse(xml_text)
    return [
        TrendItemInput(
            source_type="arxiv",
            source_name="arXiv",
            source_item_id=entry.id,
            title=entry.title.strip(),
            url=entry.id,
            author=None,
            published_at=None,
            raw_popularity_signal={},
            summary=getattr(entry, "summary", None),
        )
        for entry in parsed.entries
    ]
```

- [ ] **Step 4: Add remaining adapters with the same normalized output contract**

```python
from bs4 import BeautifulSoup

from aitrendigest.types import TrendItemInput


def parse_hf_trending_models_html(html: str) -> list[TrendItemInput]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[TrendItemInput] = []
    for rank, link in enumerate(soup.select("a[href^='/'][href*='/']"), start=1):
        href = link.get("href", "").strip("/")
        if not href or href.count("/") != 1:
            continue
        title = " ".join(link.get_text(" ", strip=True).split()) or href
        items.append(
            TrendItemInput(
                source_type="hf_models",
                source_name="Hugging Face Trending Models",
                source_item_id=href,
                title=title,
                url=f"https://huggingface.co/{href}",
                author=href.split("/")[0],
                published_at=None,
                raw_popularity_signal={"rank": rank},
                summary=None,
            )
        )
        if len(items) >= 20:
            break
    return items
```

```python
from bs4 import BeautifulSoup

from aitrendigest.types import TrendItemInput


def parse_hf_trending_papers_html(html: str) -> list[TrendItemInput]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[TrendItemInput] = []
    for rank, link in enumerate(soup.select("a[href^='/papers/']"), start=1):
        href = link.get("href", "")
        title = " ".join(link.get_text(" ", strip=True).split())
        if not href or not title:
            continue
        items.append(
            TrendItemInput(
                source_type="hf_papers",
                source_name="Hugging Face Trending Papers",
                source_item_id=href,
                title=title,
                url=f"https://huggingface.co{href}",
                author=None,
                published_at=None,
                raw_popularity_signal={"rank": rank},
                summary=None,
            )
        )
    return items
```

```python
import feedparser

from aitrendigest.types import TrendItemInput


def parse_rss_feed(xml_text: str, source_name: str, source_type: str) -> list[TrendItemInput]:
    parsed = feedparser.parse(xml_text)
    items: list[TrendItemInput] = []
    for entry in parsed.entries:
        items.append(
            TrendItemInput(
                source_type=source_type,
                source_name=source_name,
                source_item_id=entry.link,
                title=entry.title.strip(),
                url=entry.link,
                author=getattr(entry, "author", None),
                published_at=None,
                raw_popularity_signal={},
                summary=getattr(entry, "summary", None),
            )
        )
    return items
```

```python
import feedparser

from aitrendigest.types import TrendItemInput


def parse_youtube_feed(xml_text: str) -> list[TrendItemInput]:
    parsed = feedparser.parse(xml_text)
    items: list[TrendItemInput] = []
    for entry in parsed.entries:
        items.append(
            TrendItemInput(
                source_type="youtube",
                source_name="YouTube",
                source_item_id=entry.yt_videoid,
                title=entry.title.strip(),
                url=entry.link,
                author=getattr(entry, "author", None),
                published_at=None,
                raw_popularity_signal={},
                summary=getattr(entry, "summary", None),
            )
        )
    return items
```

- [ ] **Step 5: Add one generic RSS collector class and reuse it for blogs and newsletters**

```python
import httpx

from aitrendigest.collectors.base import Collector
from aitrendigest.types import TrendItemInput


class RSSCollector(Collector):
    def __init__(self, client: httpx.AsyncClient, source_name: str, source_type: str, feed_url: str):
        self.source_name = source_name
        self.source_type = source_type
        self._client = client
        self._feed_url = feed_url

    async def collect(self) -> list[TrendItemInput]:
        response = await self._client.get(self._feed_url, timeout=20.0)
        response.raise_for_status()
        return parse_rss_feed(response.text, self.source_name, self.source_type)
```

- [ ] **Step 6: Run tests to verify the collector contract passes**

Run: `pytest tests/test_collectors.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/aitrendigest/collectors tests/test_collectors.py
git commit -m "feat: add core source collectors"
```

## Task 4: Deduplication, Tagging, And Scoring

**Files:**
- Create: `src/aitrendigest/dedup.py`
- Create: `src/aitrendigest/tagging.py`
- Create: `src/aitrendigest/scoring.py`
- Test: `tests/test_dedup.py`
- Test: `tests/test_scoring.py`

- [ ] **Step 1: Write failing dedup and scoring tests**

```python
from aitrendigest.scoring import normalize_rank_score, compute_final_score
from aitrendigest.tagging import infer_tags
from aitrendigest.types import TrendItemInput
from aitrendigest.dedup import build_topic_fingerprint


def test_build_topic_fingerprint_prefers_repo_identity():
    item = TrendItemInput(
        source_type="github_trending",
        source_name="GitHub Trending",
        source_item_id="owner/repo",
        title="owner/repo",
        url="https://github.com/owner/repo",
        author="owner",
        published_at=None,
        raw_popularity_signal={"rank": 1, "stars": 100},
        summary="Agent evaluation harness",
    )

    assert build_topic_fingerprint(item) == "github:owner/repo"


def test_infer_tags_finds_agent_and_eval_keywords():
    tags = infer_tags("Agent evaluation harness for tool calling workflows")
    assert "agent" in tags
    assert "eval" in tags


def test_compute_final_score_weights_dimensions():
    score = compute_final_score(
        freshness=1.0,
        source_popularity=0.8,
        practical_value=0.6,
        cross_source_mentions=0.4,
    )
    assert round(score, 2) == 0.72
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dedup.py tests/test_scoring.py -v`  
Expected: FAIL because functions are not implemented

- [ ] **Step 3: Implement deterministic fingerprinting and tags**

```python
import re


def build_topic_fingerprint(item) -> str:
    if item.source_type == "github_trending":
        return f"github:{item.source_item_id.lower()}"
    if "arxiv.org/abs/" in item.url:
        return f"paper:{item.url.split('/abs/')[-1].split('v')[0]}"
    normalized = re.sub(r"[^a-z0-9]+", "-", item.title.lower()).strip("-")
    return f"title:{normalized}"
```

```python
TAG_KEYWORDS = {
    "agent": ["agent", "tool calling", "workflow", "orchestrator"],
    "eval": ["eval", "evaluation", "benchmark", "harness"],
    "rag": ["rag", "retrieval"],
    "infra": ["infra", "platform", "stack"],
    "multimodal": ["multimodal", "vision", "ocr", "image", "video", "audio"],
    "serving": ["serving", "inference", "vllm", "llama.cpp", "ollama"],
    "tooling": ["sdk", "framework", "tooling"],
    "skill": ["prompt", "fine-tuning", "alignment", "post-training"],
}


def infer_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = [
        tag
        for tag, keywords in TAG_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    return sorted(set(tags))
```

- [ ] **Step 4: Implement normalized score helpers**

```python
def normalize_rank_score(rank: int, max_rank: int = 20) -> float:
    bounded_rank = min(max(rank, 1), max_rank)
    return (max_rank - bounded_rank + 1) / max_rank


def compute_final_score(
    freshness: float,
    source_popularity: float,
    practical_value: float,
    cross_source_mentions: float,
) -> float:
    return (
        0.30 * freshness
        + 0.25 * source_popularity
        + 0.25 * practical_value
        + 0.20 * cross_source_mentions
    )
```

- [ ] **Step 5: Add source-popularity and practical-value scoring**

```python
def score_source_popularity(source_type: str, signals: dict) -> float:
    rank = signals.get("rank")
    if isinstance(rank, int):
        return normalize_rank_score(rank)
    likes = signals.get("likes")
    if isinstance(likes, int) and likes > 0:
        return min(likes / 500.0, 1.0)
    return 0.2


def score_practical_value(title: str, summary: str | None, url: str) -> float:
    text = f"{title} {summary or ''} {url}".lower()
    positive_keywords = ["github", "demo", "tutorial", "eval", "harness", "tool", "sdk", "inference"]
    matches = sum(1 for keyword in positive_keywords if keyword in text)
    return min(0.2 + matches * 0.15, 1.0)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_dedup.py tests/test_scoring.py -v`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/aitrendigest/dedup.py src/aitrendigest/tagging.py src/aitrendigest/scoring.py tests/test_dedup.py tests/test_scoring.py
git commit -m "feat: add deduplication and ranking"
```

## Task 5: Digest Builder

**Files:**
- Create: `src/aitrendigest/digest.py`
- Test: `tests/test_digest.py`

- [ ] **Step 1: Write the failing digest rendering test**

```python
from aitrendigest.digest import DigestEntry, render_digest_message


def test_render_digest_message_formats_entries_and_links():
    entries = [
        DigestEntry(
            title="Agent evaluation harness",
            tags=["agent", "eval"],
            why_it_matters="Useful for validating tool-calling workflows.",
            url="https://example.com/post",
        )
    ]

    message = render_digest_message("2026-06-26", entries, ["Try the demo repo."])

    assert "[AI Trend Digest | 2026-06-26]" in message
    assert "Tag: agent, eval" in message
    assert "Link: https://example.com/post" in message
    assert "Try This Today" in message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_digest.py -v`  
Expected: FAIL because digest helpers do not exist

- [ ] **Step 3: Implement digest entry and renderer**

```python
from dataclasses import dataclass


@dataclass(slots=True)
class DigestEntry:
    title: str
    tags: list[str]
    why_it_matters: str
    url: str


def render_digest_message(date_label: str, entries: list[DigestEntry], experiments: list[str]) -> str:
    lines = [f"[AI Trend Digest | {date_label}]", ""]
    for index, entry in enumerate(entries, start=1):
        lines.extend(
            [
                f"{index}. {entry.title}",
                f"Tag: {', '.join(entry.tags)}",
                f"Why: {entry.why_it_matters}",
                f"Link: {entry.url}",
                "",
            ]
        )
    lines.append("Try This Today")
    for experiment in experiments:
        lines.append(f"- {experiment}")
    return "\n".join(lines).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_digest.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aitrendigest/digest.py tests/test_digest.py
git commit -m "feat: add digest rendering"
```

## Task 6: Telegram Delivery

**Files:**
- Create: `src/aitrendigest/telegram.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing Telegram client test**

```python
import httpx

from aitrendigest.telegram import TelegramPublisher


class MockTransport(httpx.MockTransport):
    def __init__(self):
        super().__init__(self._handler)
        self.requests = []

    def _handler(self, request):
        self.requests.append(request)
        return httpx.Response(200, json={"ok": True})


def test_telegram_publisher_posts_message():
    transport = MockTransport()
    client = httpx.Client(transport=transport)
    publisher = TelegramPublisher(client, "token", "12345")

    publisher.send_message("hello")

    assert len(transport.requests) == 1
    assert transport.requests[0].url.path.endswith("/sendMessage")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`  
Expected: FAIL because `TelegramPublisher` does not exist

- [ ] **Step 3: Implement Telegram publisher with simple retry**

```python
import httpx


class TelegramPublisher:
    def __init__(self, client: httpx.Client, bot_token: str, chat_id: str):
        self._client = client
        self._bot_token = bot_token
        self._chat_id = chat_id

    def send_message(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": message}
        last_error = None
        for _ in range(2):
            response = self._client.post(url, json=payload, timeout=20.0)
            if response.is_success:
                return
            last_error = RuntimeError(f"telegram send failed: {response.status_code}")
        raise last_error if last_error else RuntimeError("telegram send failed")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aitrendigest/telegram.py tests/test_pipeline.py
git commit -m "feat: add telegram publisher"
```

## Task 7: Pipeline And CLI Commands

**Files:**
- Create: `src/aitrendigest/pipeline.py`
- Create: `src/aitrendigest/cli.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Extend pipeline test for collect and publish flow**

```python
from aitrendigest.pipeline import build_daily_digest


def test_build_daily_digest_returns_ranked_entries():
    items = [
        {
            "title": "Agent evaluation harness",
            "url": "https://example.com/a",
            "summary": "Tool calling evals with demo repo",
            "raw_popularity_signal": {"rank": 1},
            "source_type": "github_trending",
        },
        {
            "title": "Old opinion post",
            "url": "https://example.com/b",
            "summary": "General thoughts only",
            "raw_popularity_signal": {},
            "source_type": "rss_blog",
        },
    ]

    entries = build_daily_digest(items)

    assert entries[0].title == "Agent evaluation harness"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`  
Expected: FAIL because pipeline functions do not exist

- [ ] **Step 3: Implement pipeline helpers**

```python
from aitrendigest.digest import DigestEntry
from aitrendigest.scoring import compute_final_score, score_practical_value, score_source_popularity
from aitrendigest.tagging import infer_tags


def build_daily_digest(items: list[dict]) -> list[DigestEntry]:
    ranked = []
    for item in items:
        text = f"{item['title']} {item.get('summary') or ''}"
        tags = infer_tags(text)
        score = compute_final_score(
            freshness=1.0,
            source_popularity=score_source_popularity(item["source_type"], item.get("raw_popularity_signal", {})),
            practical_value=score_practical_value(item["title"], item.get("summary"), item["url"]),
            cross_source_mentions=0.2,
        )
        ranked.append(
            (
                score,
                DigestEntry(
                    title=item["title"],
                    tags=tags or ["tooling"],
                    why_it_matters=(item.get("summary") or "Timely AI engineering signal.")[:160],
                    url=item["url"],
                ),
            )
        )
    ranked.sort(key=lambda row: row[0], reverse=True)
    return [entry for _, entry in ranked[:7]]
```

- [ ] **Step 4: Add CLI commands for collect and publish**

```python
import typer

app = typer.Typer()


@app.command()
def collect() -> None:
    """Fetch items from enabled sources and store them."""


@app.command()
def publish() -> None:
    """Build the daily digest from stored items and send it to Telegram."""


if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pipeline.py -v`  
Expected: PASS

- [ ] **Step 6: Run the full test suite**

Run: `pytest -v`  
Expected: PASS for all tests

- [ ] **Step 7: Commit**

```bash
git add src/aitrendigest/pipeline.py src/aitrendigest/cli.py tests/test_pipeline.py
git commit -m "feat: add orchestration and cli"
```

## Task 8: Manual End-To-End Verification

**Files:**
- Modify: `.env.example`
- Verify: local SQLite database file created at runtime

- [ ] **Step 1: Create a real local config file from the example**

```bash
copy .env.example .env
```

- [ ] **Step 2: Fill in the real Telegram bot token and chat id**

Edit `.env` so the two empty values contain the actual bot token and actual chat id:

```text
AIDIGEST_TELEGRAM_BOT_TOKEN=
AIDIGEST_TELEGRAM_CHAT_ID=
```

- [ ] **Step 3: Run one manual collect pass**

Run: `python -m aitrendigest.cli collect`  
Expected: INFO logs showing enabled sources and persisted items

- [ ] **Step 4: Run one manual publish pass**

Run: `python -m aitrendigest.cli publish`  
Expected: one Telegram message with 3 to 7 items, tags, and direct links

- [ ] **Step 5: Run publish again to verify duplicate send prevention**

Run: `python -m aitrendigest.cli publish`  
Expected: no duplicate digest for already-sent item set

- [ ] **Step 6: Commit**

```bash
git add .env.example
git commit -m "docs: add runtime verification notes"
```

## Spec Coverage Check

- Daily Telegram digest:
  - covered by Task 5, Task 6, Task 7, Task 8
- Multiple collection runs and stored history:
  - covered by Task 2, Task 3, Task 7
- Deduplication:
  - covered by Task 4
- Rule-based scoring with source-native popularity:
  - covered by Task 4 and Task 7
- Direct links and concise explanation:
  - covered by Task 5
- Curated source adapters including GitHub, Hugging Face, arXiv, blogs, YouTube:
  - covered by Task 3
- Basic observability and reliability:
  - covered by Task 1 logging plus Task 6 and Task 8 verification

## Placeholder Scan

This plan intentionally avoids `TBD`, `TODO`, and abstract "handle edge cases" instructions. Every task names exact files, test entrypoints, commands, and minimum code shapes to implement.

## Type Consistency Check

- normalized collected item type stays `TrendItemInput`
- rendered message item type stays `DigestEntry`
- score function name stays `compute_final_score`
- dedup identity function name stays `build_topic_fingerprint`



