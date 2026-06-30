import feedparser

from aitrendigest.types import TrendItemInput


def _normalize_arxiv_url(entry) -> str:
    entry_id = getattr(entry, "id", "")
    if isinstance(entry_id, str) and entry_id.startswith("oai:arXiv.org:"):
        return f"https://arxiv.org/abs/{entry_id.split(':', 2)[2]}"
    if isinstance(entry_id, str) and entry_id.startswith("http://"):
        return entry_id.replace("http://", "https://", 1)
    if isinstance(entry_id, str) and entry_id.startswith("https://"):
        return entry_id

    link = getattr(entry, "link", None)
    if isinstance(link, str) and link.startswith("oai:arXiv.org:"):
        return f"https://arxiv.org/abs/{link.split(':', 2)[2]}"
    if isinstance(link, str) and link:
        return link.replace("http://", "https://", 1)

    return f"https://arxiv.org/abs/{entry_id}"


def parse_arxiv_feed(xml_text: str) -> list[TrendItemInput]:
    parsed = feedparser.parse(xml_text)
    return [
        TrendItemInput(
            source_type="arxiv",
            source_name="arXiv",
            source_item_id=entry.id,
            title=entry.title.strip(),
            url=_normalize_arxiv_url(entry),
            author=None,
            published_at=None,
            raw_popularity_signal={},
            summary=getattr(entry, "summary", None),
        )
        for entry in parsed.entries
    ]
