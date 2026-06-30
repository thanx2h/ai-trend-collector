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
