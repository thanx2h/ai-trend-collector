from aitrendigest.dedup import build_topic_fingerprint
from aitrendigest.types import TrendItemInput


def test_build_topic_fingerprint_prefers_repo_identity():
    item = TrendItemInput(
        source_type="github_trending",
        source_name="GitHub Trending",
        source_item_id="owner/repo",
        title="owner/repo",
        url="https://github.com/owner/repo",
        author="owner",
        published_at=None,
        raw_popularity_signal={"rank": 1, "stars": 100},
        summary="Agent evaluation harness",
    )

    assert build_topic_fingerprint(item) == "github:owner/repo"
