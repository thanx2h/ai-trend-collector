import feedparser
from typing import Any

from aitrendigest.collectors.base import Collector
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


class RSSCollector(Collector):
    def __init__(self, client: Any, source_name: str, source_type: str, feed_url: str):
        self.source_name = source_name
        self.source_type = source_type
        self._client = client
        self._feed_url = feed_url

    async def collect(self) -> list[TrendItemInput]:
        response = await self._client.get(self._feed_url, timeout=20.0)
        response.raise_for_status()
        return parse_rss_feed(response.text, self.source_name, self.source_type)
