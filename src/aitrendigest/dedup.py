import re


def build_topic_fingerprint(item) -> str:
    if item.source_type == "github_trending":
        return f"github:{item.source_item_id.lower()}"
    if "arxiv.org/abs/" in item.url:
        return f"paper:{item.url.split('/abs/')[-1].split('v')[0]}"
    normalized = re.sub(r"[^a-z0-9]+", "-", item.title.lower()).strip("-")
    return f"title:{normalized}"
