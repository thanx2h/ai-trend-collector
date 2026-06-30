from aitrendigest.pipeline import build_daily_digest, build_digest_sections, publish_new_items


class DummyResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300


class DummyClient:
    def __init__(self):
        self.requests = []

    def post(self, url, json, timeout):
        self.requests.append({"url": url, "json": json, "timeout": timeout})
        return DummyResponse(200)


class DummyPublisher:
    def __init__(self):
        self.messages = []

    def send_message(self, message: str) -> None:
        self.messages.append(message)


from aitrendigest.config import Settings
from aitrendigest.telegram import TelegramPublisher


def test_telegram_publisher_posts_message():
    client = DummyClient()
    publisher = TelegramPublisher(client, "token", "12345")

    publisher.send_message("hello")

    assert len(client.requests) == 1
    assert client.requests[0]["url"].endswith("/sendMessage")


def test_build_digest_sections_splits_core_and_adjacent_items():
    items = [
        {
            "title": "google-labs-code / design.md",
            "url": "https://example.com/a",
            "summary": "AI coding agent design guide",
            "raw_popularity_signal": {"rank": 1},
            "source_type": "github_trending",
        },
        {
            "title": "xbtlin / ai-berkshire",
            "url": "https://example.com/b",
            "summary": "Claude Code based investing agent workflow",
            "raw_popularity_signal": {"rank": 2},
            "source_type": "github_trending",
        },
        {
            "title": "simplex-chat / simplex-chat",
            "url": "https://example.com/c",
            "summary": "Privacy messenger",
            "raw_popularity_signal": {"rank": 3},
            "source_type": "github_trending",
        },
    ]

    sections = build_digest_sections(items)

    assert sections[0].title == "AI 엔지니어링 핵심 5"
    assert [entry.title for entry in sections[0].entries] == ["google-labs-code / design.md"]
    assert sections[1].title == "인접/참고 2"
    assert [entry.title for entry in sections[1].entries] == ["xbtlin / ai-berkshire"]


def test_build_digest_sections_limits_paper_heavy_results():
    items = [
        {
            "title": f"Paper {index} benchmark for agents",
            "url": f"https://example.com/paper-{index}",
            "summary": "RAG benchmark evaluation for agent workflows",
            "raw_popularity_signal": {},
            "source_type": "arxiv",
        }
        for index in range(4)
    ] + [
        {
            "title": "design.md for coding agents",
            "url": "https://example.com/design",
            "summary": "AI coding agent design guide",
            "raw_popularity_signal": {"rank": 1},
            "source_type": "github_trending",
        },
        {
            "title": "browser agent workflow repo",
            "url": "https://example.com/browser-agent",
            "summary": "Tool calling workflow and eval harness",
            "raw_popularity_signal": {"rank": 2},
            "source_type": "github_trending",
        },
        {
            "title": "hf agent paper",
            "url": "https://example.com/hf-paper",
            "summary": "Agent evaluation paper",
            "raw_popularity_signal": {},
            "source_type": "hf_papers",
        },
    ]

    sections = build_digest_sections(items)
    core_entries = sections[0].entries
    paper_count = sum(1 for entry in core_entries if "Paper" in entry.title or "hf agent paper" == entry.title)

    assert paper_count <= 2
    assert any(entry.title == "design.md for coding agents" for entry in core_entries)
    assert any(entry.title == "browser agent workflow repo" for entry in core_entries)


def test_build_daily_digest_returns_ranked_entries():
    items = [
        {
            "title": "Agent evaluation harness",
            "url": "https://example.com/a",
            "summary": "Tool calling evals with demo repo",
            "raw_popularity_signal": {"rank": 1},
            "source_type": "github_trending",
        },
        {
            "title": "Old opinion post",
            "url": "https://example.com/b",
            "summary": "General thoughts only",
            "raw_popularity_signal": {},
            "source_type": "rss_blog",
        },
    ]

    entries = build_daily_digest(items)

    assert entries[0].title == "Agent evaluation harness"


def test_publish_new_items_renders_live_digest_without_db():
    settings = Settings(telegram_bot_token="token", telegram_chat_id="12345")
    publisher = DummyPublisher()
    items = [
        {
            "title": "google-labs-code / design.md",
            "url": "https://example.com/a",
            "summary": "AI coding agent design guide",
            "raw_popularity_signal": {"rank": 1},
            "source_type": "github_trending",
        }
    ]

    message = publish_new_items(settings, publisher=publisher, dry_run=False, items=items)

    assert "AI 엔지니어링 핵심 5" in message
    assert "AI 엔지니어링 적합도" not in message
    assert len(publisher.messages) == 1
