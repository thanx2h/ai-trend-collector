from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
import logging
import ssl

from aitrendigest.collectors.arxiv import parse_arxiv_feed
from aitrendigest.collectors.github_trending import parse_github_trending_html
from aitrendigest.collectors.hf_models import parse_hf_trending_models_html
from aitrendigest.collectors.hf_papers import parse_hf_trending_papers_html
from aitrendigest.collectors.rss import parse_rss_feed
from aitrendigest.digest import DigestEntry, DigestSection, render_digest_message
from aitrendigest.models import TrendItemRecord
from aitrendigest.repository import ItemRepository
from aitrendigest.scoring import assess_ai_engineering_fit
from aitrendigest.tagging import infer_tags
from aitrendigest.telegram import TelegramPublisher
from aitrendigest.types import TrendItemInput

logger = logging.getLogger(__name__)

DEFAULT_SOURCE_URLS: dict[str, str] = {
    "github_trending": "https://github.com/trending?since=daily",
    "hf_models": "https://huggingface.co/models?sort=trending",
    "hf_papers": "https://huggingface.co/papers/trending",
    "arxiv": "http://arxiv.org/rss/cs.AI",
}

CORE_SECTION_TITLE = "AI 엔지니어링 핵심 5"
ADJACENT_SECTION_TITLE = "인접/참고 2"


class SourceFetchError(RuntimeError):
    pass


def _fetch_text(url: str, timeout_seconds: float = 20.0) -> str:
    request = Request(url, headers={"User-Agent": "ai-trend-digest/0.1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds, context=ssl._create_unverified_context()) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except URLError as exc:
        raise SourceFetchError(f"failed to fetch {url}: {exc}") from exc


def _source_items_from_html(source_type: str, html: str) -> list[TrendItemInput]:
    if source_type == "github_trending":
        return parse_github_trending_html(html)
    if source_type == "hf_models":
        return parse_hf_trending_models_html(html)
    if source_type == "hf_papers":
        return parse_hf_trending_papers_html(html)
    raise ValueError(f"unsupported html source: {source_type}")


def _source_items_from_feed(source_type: str, feed_text: str) -> list[TrendItemInput]:
    if source_type == "arxiv":
        return parse_arxiv_feed(feed_text)
    return parse_rss_feed(feed_text, source_name=source_type, source_type=source_type)


def fetch_enabled_sources(enabled_sources: list[str]) -> list[TrendItemInput]:
    collected: list[TrendItemInput] = []
    for source_type in enabled_sources:
        url = DEFAULT_SOURCE_URLS.get(source_type)
        if url is None:
            logger.info("Skipping unsupported source: %s", source_type)
            continue
        try:
            raw_text = _fetch_text(url)
            if source_type in {"github_trending", "hf_models", "hf_papers"}:
                collected.extend(_source_items_from_html(source_type, raw_text))
            else:
                collected.extend(_source_items_from_feed(source_type, raw_text))
        except SourceFetchError as exc:
            logger.warning("%s", exc)
    return collected


def collect_enabled_sources(settings, repository: ItemRepository) -> int:
    collected_items = fetch_enabled_sources(settings.enabled_sources)
    for item in collected_items:
        repository.upsert_item(item)
    return len(collected_items)


def _record_to_dict(record: TrendItemRecord) -> dict[str, Any]:
    return {
        "title": record.title,
        "url": record.url,
        "summary": record.summary,
        "raw_popularity_signal": record.raw_popularity_signal or {},
        "source_type": record.source_type,
    }


@dataclass(slots=True)
class _ScoredItem:
    title: str
    tags: list[str]
    ai_engineering_fit: int
    url: str
    section: str


def _score_item(item: dict[str, Any]) -> _ScoredItem:
    text = f"{item['title']} {item.get('summary') or ''}"
    tags = infer_tags(text)
    assessment = assess_ai_engineering_fit(
        title=item["title"],
        summary=item.get("summary"),
        url=item["url"],
        tags=tags,
        source_type=item["source_type"],
        signals=item.get("raw_popularity_signal", {}),
    )
    return _ScoredItem(
        title=item["title"],
        tags=tags,
        ai_engineering_fit=assessment.score,
        url=item["url"],
        section=assessment.section,
    )


def _rank_scored_items(items: list[dict[str, Any]]) -> list[_ScoredItem]:
    scored = [_score_item(item) for item in items]
    return sorted(scored, key=lambda row: (row.ai_engineering_fit, row.title), reverse=True)


def build_digest_sections(items: list[dict[str, Any]]) -> list[DigestSection]:
    scored_items = _rank_scored_items(items)
    core_items = [item for item in scored_items if item.section == "core"][:5]
    adjacent_items = [item for item in scored_items if item.section == "adjacent"][:2]

    sections: list[DigestSection] = []
    if core_items:
        sections.append(
            DigestSection(
                title=CORE_SECTION_TITLE,
                entries=[
                    DigestEntry(
                        title=item.title,
                        tags=item.tags,
                        ai_engineering_fit=item.ai_engineering_fit,
                        url=item.url,
                    )
                    for item in core_items
                ],
            )
        )
    if adjacent_items:
        sections.append(
            DigestSection(
                title=ADJACENT_SECTION_TITLE,
                entries=[
                    DigestEntry(
                        title=item.title,
                        tags=item.tags,
                        ai_engineering_fit=item.ai_engineering_fit,
                        url=item.url,
                    )
                    for item in adjacent_items
                ],
            )
        )
    return sections


def build_daily_digest(items: list[dict]) -> list[DigestEntry]:
    sections = build_digest_sections(items)
    return [entry for section in sections for entry in section.entries]


def publish_new_items(settings, repository: ItemRepository, publisher: TelegramPublisher | None = None, dry_run: bool = False) -> str:
    records = repository.list_items(send_status="new")
    if not records:
        return "No new items to publish."

    sections = build_digest_sections([_record_to_dict(record) for record in records])
    message = render_digest_message(date.today().isoformat(), sections, ["Try the highest-scoring item today."])

    if dry_run:
        return message

    if publisher is None:
        publisher = TelegramPublisher(None, settings.telegram_bot_token, settings.telegram_chat_id)

    publisher.send_message(message)
    repository.mark_items_sent(record.id for record in records)
    return message

