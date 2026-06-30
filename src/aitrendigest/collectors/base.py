from collections.abc import Iterable
from typing import Protocol

from aitrendigest.types import TrendItemInput


class Collector(Protocol):
    source_name: str
    source_type: str

    async def collect(self) -> Iterable[TrendItemInput]:
        raise NotImplementedError
