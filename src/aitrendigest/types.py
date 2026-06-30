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
