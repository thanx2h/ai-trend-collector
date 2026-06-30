import re

from bs4 import BeautifulSoup

from aitrendigest.types import TrendItemInput


_NUMBER_RE = re.compile(r"\d[\d,]*")


def _parse_int(text: str) -> int:
    match = _NUMBER_RE.search(text or "")
    if not match:
        return 0
    return int(match.group(0).replace(",", ""))


def parse_github_trending_html(html: str) -> list[TrendItemInput]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[TrendItemInput] = []
    for rank, article in enumerate(soup.select("article.Box-row"), start=1):
        link = article.select_one("h2 a")
        if link is None:
            continue
        href = link.get("href", "").strip("/")
        if not href:
            continue
        star_link = article.select_one("a[href$='/stargazers']") or article.select_one("a[href*='/stargazers']")
        stars_text = star_link.get_text(strip=True) if star_link is not None else "0"
        title = " ".join(link.get_text(" ", strip=True).split()) or href
        items.append(
            TrendItemInput(
                source_type="github_trending",
                source_name="GitHub Trending",
                source_item_id=href,
                title=title,
                url=f"https://github.com/{href}",
                author=href.split("/")[0],
                published_at=None,
                raw_popularity_signal={"rank": rank, "stars": _parse_int(stars_text)},
                summary=None,
            )
        )
    return items
