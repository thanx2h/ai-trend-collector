from __future__ import annotations

from dataclasses import dataclass

CORE_KEYWORDS = (
    "design.md",
    "evaluation",
    "eval",
    "benchmark",
    "harness",
    "tool calling",
    "function calling",
    "orchestrator",
    "prompt",
    "rag",
    "retrieval",
    "inference",
    "serving",
    "sdk",
    "framework",
    "context",
    "memory",
    "ocr",
    "multimodal",
)

ADJACENT_KEYWORDS = (
    "openpilot",
    "robotics",
    "robot",
    "autonomous",
    "driving",
    "finance",
    "investment",
    "research",
    "claude code",
    "assistant",
    "platform",
    "desktop",
    "browser",
)

CORE_TAG_WEIGHTS = {
    "agent": 0.08,
    "eval": 0.18,
    "rag": 0.12,
    "serving": 0.12,
    "tooling": 0.10,
    "skill": 0.10,
}

ADJACENT_TAG_WEIGHTS = {
    "multimodal": 0.10,
    "infra": 0.08,
}


@dataclass(slots=True)
class EngineeringFit:
    section: str
    score: int


def normalize_rank_score(rank: int, max_rank: int = 20) -> float:
    bounded_rank = min(max(rank, 1), max_rank)
    return (max_rank - bounded_rank + 1) / max_rank


def compute_final_score(
    freshness: float,
    source_popularity: float,
    practical_value: float,
    cross_source_mentions: float,
) -> float:
    return (
        0.30 * freshness
        + 0.25 * source_popularity
        + 0.25 * practical_value
        + 0.20 * cross_source_mentions
    )


def score_source_popularity(source_type: str, signals: dict) -> float:
    rank = signals.get("rank")
    if isinstance(rank, int):
        return normalize_rank_score(rank)
    likes = signals.get("likes")
    if isinstance(likes, int) and likes > 0:
        return min(likes / 500.0, 1.0)
    return 0.2


def score_practical_value(title: str, summary: str | None, url: str) -> float:
    text = f"{title} {summary or ''} {url}".lower()
    positive_keywords = ["github", "demo", "tutorial", "eval", "harness", "tool", "sdk", "inference"]
    matches = sum(1 for keyword in positive_keywords if keyword in text)
    return min(0.2 + matches * 0.15, 1.0)


def _count_keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _weighted_tag_bonus(tags: list[str], weights: dict[str, float]) -> float:
    return sum(weights.get(tag, 0.0) for tag in tags)


def assess_ai_engineering_fit(
    title: str,
    summary: str | None,
    url: str,
    tags: list[str],
    source_type: str,
    signals: dict,
) -> EngineeringFit:
    text = f"{title} {summary or ''} {url}".lower()
    core_hits = _count_keyword_hits(text, CORE_KEYWORDS)
    adjacent_hits = _count_keyword_hits(text, ADJACENT_KEYWORDS)
    practical_value = score_practical_value(title, summary, url)
    source_popularity = score_source_popularity(source_type, signals)

    core_strength = (
        0.18
        + core_hits * 0.11
        + _weighted_tag_bonus(tags, CORE_TAG_WEIGHTS)
        + 0.16 * practical_value
        + 0.08 * source_popularity
    )
    adjacent_strength = (
        0.10
        + adjacent_hits * 0.11
        + _weighted_tag_bonus(tags, ADJACENT_TAG_WEIGHTS)
        + 0.10 * practical_value
        + 0.06 * source_popularity
    )

    if core_strength >= 0.38 and core_strength >= adjacent_strength + 0.05:
        return EngineeringFit("core", min(round(core_strength * 100), 100))
    if adjacent_strength >= 0.28:
        return EngineeringFit("adjacent", min(round(adjacent_strength * 100), 100))
    return EngineeringFit("exclude", min(round(max(core_strength, adjacent_strength) * 100), 100))
