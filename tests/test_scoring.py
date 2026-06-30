from aitrendigest.scoring import assess_ai_engineering_fit, compute_final_score, normalize_rank_score
from aitrendigest.tagging import infer_tags


def test_infer_tags_finds_agent_and_eval_keywords():
    tags = infer_tags("Agent evaluation harness for tool calling workflows")
    assert "agent" in tags
    assert "eval" in tags


def test_compute_final_score_weights_dimensions():
    score = compute_final_score(
        freshness=1.0,
        source_popularity=0.8,
        practical_value=0.6,
        cross_source_mentions=0.4,
    )
    assert round(score, 2) == 0.73


def test_assess_ai_engineering_fit_classifies_core_and_adjacent_items():
    core = assess_ai_engineering_fit(
        title="google-labs-code / design.md",
        summary="AI coding agent design guide",
        url="https://example.com/core",
        tags=["agent", "tooling"],
        source_type="github_trending",
        signals={"rank": 1},
    )
    adjacent = assess_ai_engineering_fit(
        title="xbtlin / ai-berkshire",
        summary="Claude Code based investing agent workflow",
        url="https://example.com/adjacent",
        tags=["agent"],
        source_type="github_trending",
        signals={"rank": 2},
    )
    excluded = assess_ai_engineering_fit(
        title="simplex-chat / simplex-chat",
        summary="Privacy messenger",
        url="https://example.com/excluded",
        tags=[],
        source_type="github_trending",
        signals={"rank": 3},
    )

    assert core.section == "core"
    assert adjacent.section == "adjacent"
    assert excluded.section == "exclude"
