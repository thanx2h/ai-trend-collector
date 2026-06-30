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
