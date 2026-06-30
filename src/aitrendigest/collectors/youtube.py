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
