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
PAPER_SOURCES = {"arxiv", "hf_papers"}
CORE_PAPER_LIMIT = 2
ADJACENT_PAPER_LIMIT = 1


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


@dataclass(slots=True)
class _ScoredItem:
    title: str
    tags: list[str]
    ai_engineering_fit: int
    url: str
    section: str
    source_type: str


def _item_to_dict(item: TrendItemInput | dict[str, Any]) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    return {
        "title": item.title,
        "url": item.url,
        "summary": item.summary,
        "raw_popularity_signal": item.raw_popularity_signal or {},
        "source_type": item.source_type,
    }


def _score_item(item: TrendItemInput | dict[str, Any]) -> _ScoredItem:
    item_dict = _item_to_dict(item)
    text = f"{item_dict['title']} {item_dict.get('summary') or ''}"
    tags = infer_tags(text)
    assessment = assess_ai_engineering_fit(
        title=item_dict["title"],
        summary=item_dict.get("summary"),
        url=item_dict["url"],
        tags=tags,
        source_type=item_dict["source_type"],
        signals=item_dict.get("raw_popularity_signal", {}),
    )
    return _ScoredItem(
        title=item_dict["title"],
        tags=tags,
        ai_engineering_fit=assessment.score,
        url=item_dict["url"],
        section=assessment.section,
        source_type=item_dict["source_type"],
    )


def _rank_scored_items(items: list[TrendItemInput | dict[str, Any]]) -> list[_ScoredItem]:
    scored = [_score_item(item) for item in items]
    return sorted(scored, key=lambda row: (row.ai_engineering_fit, row.title), reverse=True)


def _take_section_items(scored_items: list[_ScoredItem], section: str, limit: int, paper_limit: int) -> list[_ScoredItem]:
    selected: list[_ScoredItem] = []
    paper_count = 0

    for item in scored_items:
        if item.section != section:
            continue
        if item.source_type in PAPER_SOURCES and paper_count >= paper_limit:
            continue
        selected.append(item)
        if item.source_type in PAPER_SOURCES:
            paper_count += 1
        if len(selected) == limit:
            break

    return selected


def build_digest_sections(items: list[TrendItemInput | dict[str, Any]]) -> list[DigestSection]:
    scored_items = _rank_scored_items(items)
    core_items = _take_section_items(scored_items, section="core", limit=5, paper_limit=CORE_PAPER_LIMIT)
    adjacent_items = _take_section_items(scored_items, section="adjacent", limit=2, paper_limit=ADJACENT_PAPER_LIMIT)

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


def build_daily_digest(items: list[dict[str, Any]]) -> list[DigestEntry]:
    sections = build_digest_sections(items)
    return [entry for section in sections for entry in section.entries]


def build_digest_message(items: list[TrendItemInput | dict[str, Any]], date_label: str | None = None) -> str:
    sections = build_digest_sections(items)
    label = date_label or date.today().isoformat()
    return render_digest_message(label, sections, ["Try the highest-scoring item today."])


def collect_enabled_sources(settings) -> list[TrendItemInput]:
    return fetch_enabled_sources(settings.enabled_sources)


def publish_new_items(settings, publisher: TelegramPublisher | None = None, dry_run: bool = False, items: list[TrendItemInput | dict[str, Any]] | None = None) -> str:
    source_items = items if items is not None else collect_enabled_sources(settings)
    if not source_items:
        return "No items to publish."

    message = build_digest_message(source_items)

    if dry_run:
        return message

    if publisher is None:
        publisher = TelegramPublisher(None, settings.telegram_bot_token, settings.telegram_chat_id)

    publisher.send_message(message)
    return message
