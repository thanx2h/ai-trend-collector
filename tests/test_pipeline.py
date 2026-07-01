from datetime import date

from aitrendigest.pipeline import (
    build_daily_digest,
    build_digest_sections,
    is_subscriber_due_today,
    parse_now_command,
    parse_period_command,
    process_telegram_updates,
    publish_new_items,
    run_once_for_scheduler,
    run_scheduled_delivery,
)


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

    def send_message(self, message: str, chat_id: str | None = None) -> None:
        self.messages.append((chat_id, message))


from aitrendigest.config import Settings
from aitrendigest.telegram import TelegramPublisher


CORE_TITLE = "AI 엔지니어링 핵심 5"
ADJACENT_TITLE = "인접/참고 2"


def test_telegram_publisher_posts_message():
    client = DummyClient()
    publisher = TelegramPublisher(client, "token", "12345")

    publisher.send_message("hello")

    assert len(client.requests) == 1
    assert client.requests[0]["url"].endswith("/sendMessage")


def test_build_digest_sections_preserves_adjacent_section_when_core_is_full():
    items = [
        {
            "title": "core repo design.md",
            "url": "https://example.com/core-1",
            "summary": "AI coding agent design guide",
            "raw_popularity_signal": {"rank": 1},
            "source_type": "github_trending",
        },
        {
            "title": "agent eval harness repo",
            "url": "https://example.com/core-2",
            "summary": "Tool calling eval harness",
            "raw_popularity_signal": {"rank": 2},
            "source_type": "github_trending",
        },
        {
            "title": "rag benchmark toolkit",
            "url": "https://example.com/core-3",
            "summary": "RAG benchmark and retrieval workflows",
            "raw_popularity_signal": {"rank": 3},
            "source_type": "github_trending",
        },
        {
            "title": "inference serving stack",
            "url": "https://example.com/core-4",
            "summary": "LLM serving and inference stack",
            "raw_popularity_signal": {"rank": 4},
            "source_type": "github_trending",
        },
        {
            "title": "browser agent workflow repo",
            "url": "https://example.com/core-5",
            "summary": "Agent workflow and orchestration",
            "raw_popularity_signal": {"rank": 5},
            "source_type": "github_trending",
        },
        {
            "title": "xbtlin / ai-berkshire",
            "url": "https://example.com/adjacent-1",
            "summary": "Claude Code based investing agent workflow",
            "raw_popularity_signal": {"rank": 6},
            "source_type": "github_trending",
        },
    ]

    sections = build_digest_sections(items)

    assert sections[0].title == CORE_TITLE
    assert len(sections[0].entries) == 5
    assert sections[1].title == ADJACENT_TITLE
    assert [entry.title for entry in sections[1].entries] == ["xbtlin / ai-berkshire"]


def test_build_digest_sections_backfills_when_core_pool_is_small():
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

    assert [entry.title for entry in sections[0].entries] == [
        "google-labs-code / design.md",
        "xbtlin / ai-berkshire",
        "simplex-chat / simplex-chat",
    ]


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
    paper_count = sum(1 for entry in core_entries if "Paper" in entry.title or entry.title == "hf agent paper")

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

    assert CORE_TITLE in message
    assert "AI 엔지니어링 적합도" not in message
    assert "AI coding agent design guide" in message
    assert len(publisher.messages) == 1


def test_is_subscriber_due_today_for_every_third_day():
    assert is_subscriber_due_today(
        anchor_date=date(2026, 7, 1),
        period_days=3,
        today=date(2026, 7, 4),
        last_sent_on=None,
    ) is True


def test_is_subscriber_due_today_blocks_duplicate_same_day_send():
    assert is_subscriber_due_today(
        anchor_date=date(2026, 7, 1),
        period_days=1,
        today=date(2026, 7, 1),
        last_sent_on=date(2026, 7, 1),
    ) is False


def test_parse_period_command_accepts_positive_integer():
    assert parse_period_command("/period 3") == 3


def test_parse_period_command_rejects_invalid_input():
    assert parse_period_command("/period abc") is None


def test_parse_now_command_accepts_exact_command():
    assert parse_now_command("/now") is True
    assert parse_now_command("/now please") is False


def test_run_once_for_scheduler_sends_now_digest_even_when_not_due():
    from aitrendigest.db import create_schema, create_session_factory, dispose_engine
    from aitrendigest.repository import SubscriberRepository

    class DummyTelegramClient:
        def get_updates(self, offset=None):
            return [{"update_id": 70, "message": {"chat": {"id": 2001}, "text": "/now"}}]

    database_url = "sqlite+pysqlite:///file:run-once-now?mode=memory&cache=shared&uri=true"
    try:
        session_factory = create_session_factory(database_url)
        create_schema(session_factory)
        repository = SubscriberRepository(session_factory)
        repository.register_if_missing("2001", default_period_days=7, anchor_date=date(2026, 6, 25))
        publisher = DummyPublisher()
        items = [
            {
                "title": "agent eval harness",
                "url": "https://example.com/repo-1",
                "summary": "Tool calling evaluation repository",
                "raw_popularity_signal": {"rank": 1},
                "source_type": "github_trending",
            }
        ]

        result = run_once_for_scheduler(
            database_url=database_url,
            telegram_client=DummyTelegramClient(),
            publisher=publisher,
            today=date(2026, 7, 1),
            source_items=items,
            default_period_days=1,
        )

        assert result == "Sent digest to 0 subscribers. Sent 1 on-demand digests."
        assert [chat_id for chat_id, _ in publisher.messages] == ["2001"]
        assert repository.get_subscriber("2001").last_sent_on == date(2026, 7, 1)
    finally:
        dispose_engine(database_url)


def test_process_telegram_updates_auto_registers_unknown_chat():
    from aitrendigest.db import create_schema, create_session_factory, dispose_engine
    from aitrendigest.repository import SubscriberRepository

    database_url = "sqlite+pysqlite:///file:process-updates-auto-register?mode=memory&cache=shared&uri=true"
    try:
        session_factory = create_session_factory(database_url)
        create_schema(session_factory)
        repository = SubscriberRepository(session_factory)

        updates = [{"update_id": 10, "message": {"chat": {"id": 1001}, "text": "hello"}}]

        process_telegram_updates(repository, updates, today=date(2026, 7, 1), default_period_days=1)

        subscriber = repository.get_subscriber("1001")
        assert subscriber is not None
        assert subscriber.period_days == 1
        assert subscriber.anchor_date == date(2026, 7, 1)
        assert repository.get_last_update_id() == 10
    finally:
        dispose_engine(database_url)


def test_process_telegram_updates_applies_period_only_to_sender():
    from aitrendigest.db import create_schema, create_session_factory, dispose_engine
    from aitrendigest.repository import SubscriberRepository

    database_url = "sqlite+pysqlite:///file:process-updates-period?mode=memory&cache=shared&uri=true"
    try:
        session_factory = create_session_factory(database_url)
        create_schema(session_factory)
        repository = SubscriberRepository(session_factory)

        repository.register_if_missing("1001", default_period_days=1, anchor_date=date(2026, 7, 1))
        repository.register_if_missing("1002", default_period_days=1, anchor_date=date(2026, 7, 1))

        updates = [{"update_id": 11, "message": {"chat": {"id": 1001}, "text": "/period 3"}}]

        process_telegram_updates(repository, updates, today=date(2026, 7, 2), default_period_days=1)

        assert repository.get_subscriber("1001").period_days == 3
        assert repository.get_subscriber("1001").anchor_date == date(2026, 7, 2)
        assert repository.get_subscriber("1002").period_days == 1
        assert repository.get_last_update_id() == 11
    finally:
        dispose_engine(database_url)


def test_run_scheduled_delivery_sends_only_to_due_subscribers():
    from aitrendigest.db import create_schema, create_session_factory, dispose_engine
    from aitrendigest.repository import SubscriberRepository

    database_url = "sqlite+pysqlite:///file:scheduled-delivery?mode=memory&cache=shared&uri=true"
    try:
        session_factory = create_session_factory(database_url)
        create_schema(session_factory)
        repository = SubscriberRepository(session_factory)
        publisher = DummyPublisher()

        repository.register_if_missing("1001", default_period_days=1, anchor_date=date(2026, 7, 1))
        repository.register_if_missing("1002", default_period_days=3, anchor_date=date(2026, 7, 2))

        items = [
            {
                "title": "agent eval harness",
                "url": "https://example.com/repo-1",
                "summary": "Tool calling evaluation repository",
                "raw_popularity_signal": {"rank": 1},
                "source_type": "github_trending",
            }
        ]

        message = run_scheduled_delivery(
            repository=repository,
            publisher=publisher,
            items=items,
            today=date(2026, 7, 3),
        )

        assert [chat_id for chat_id, _ in publisher.messages] == ["1001"]
        assert repository.get_subscriber("1001").last_sent_on == date(2026, 7, 3)
        assert repository.get_subscriber("1002").last_sent_on is None
        assert "1 subscribers" in message
    finally:
        dispose_engine(database_url)


def test_run_once_for_scheduler_processes_updates_then_sends():
    from aitrendigest.db import create_schema, create_session_factory, dispose_engine

    class DummyTelegramClient:
        def __init__(self):
            self.calls = []

        def get_updates(self, offset=None):
            self.calls.append(offset)
            return [
                {"update_id": 50, "message": {"chat": {"id": 2001}, "text": "hello"}},
                {"update_id": 51, "message": {"chat": {"id": 2001}, "text": "/period 7"}},
            ]

    database_url = "sqlite+pysqlite:///file:run-once-scheduler?mode=memory&cache=shared&uri=true"
    try:
        session_factory = create_session_factory(database_url)
        create_schema(session_factory)
        telegram_client = DummyTelegramClient()
        publisher = DummyPublisher()

        result = run_once_for_scheduler(
            database_url=database_url,
            telegram_client=telegram_client,
            publisher=publisher,
            today=date(2026, 7, 1),
            source_items=[],
            default_period_days=1,
        )

        assert "Sent digest to 1 subscribers." == result
        assert telegram_client.calls == [None]
        assert publisher.messages
    finally:
        dispose_engine(database_url)
