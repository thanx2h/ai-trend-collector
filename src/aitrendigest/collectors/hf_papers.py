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
