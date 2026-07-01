# Telegram Subscriber Period Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-subscriber Telegram delivery with auto-registration, `/period N` command handling, subscriber-specific send cadence, and one-shot Docker-friendly execution.

**Architecture:** Reintroduce lightweight SQLite-backed state, but only for subscriber and Telegram update tracking. A single scheduled batch command will read Telegram updates, mutate subscriber settings, collect one digest, send it to eligible subscribers, persist send state, and exit.

**Tech Stack:** Python 3.12, pytest, SQLAlchemy, httpx, Typer, Telegram Bot API, SQLite, Docker

---

## Current Workspace Sync

The current codebase already has:

- source collection and normalization
- digest ranking and rendering
- Telegram send client for a single configured chat id
- CLI entrypoints for `collect` and `publish`
- existing SQLAlchemy support files that are no longer used by the live publish path

This plan extends the current project instead of rebuilding it.

## File Structure

Modify this structure:

- `src/aitrendigest/config.py`
  - add timezone and default subscriber period settings
- `src/aitrendigest/types.py`
  - add subscriber and Telegram update dataclasses if needed
- `src/aitrendigest/models.py`
  - add subscriber and Telegram state ORM tables
- `src/aitrendigest/db.py`
  - keep session/bootstrap helpers aligned with the new tables
- `src/aitrendigest/repository.py`
  - add subscriber repository and Telegram state repository methods
- `src/aitrendigest/telegram.py`
  - extend publisher to send to arbitrary chat ids and add update polling client methods
- `src/aitrendigest/pipeline.py`
  - add command parsing, eligibility checks, and batch run orchestration
- `src/aitrendigest/cli.py`
  - add one-shot scheduled command
- `tests/test_config.py`
  - cover new settings defaults
- `tests/test_repository.py`
  - cover subscriber persistence and Telegram offset state
- `tests/test_pipeline.py`
  - cover `/period N`, auto-registration, eligibility, and multi-subscriber delivery
- `tests/test_telegram.py`
  - cover Telegram update fetch and arbitrary chat send behavior
- `Dockerfile`
  - batch runtime image
- `.dockerignore`
  - slim build context
- `docs/superpowers/plans/2026-07-01-telegram-subscriber-period.md`
  - this plan
- `docs/operations/telegram-subscriber-period.md`
  - Linux cron and Docker deployment instructions

## Task 1: Extend Settings For Subscriber Scheduling

**Files:**
- Modify: `src/aitrendigest/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing settings test**

```python
from aitrendigest.config import Settings


def test_settings_load_subscriber_schedule_defaults(monkeypatch):
    monkeypatch.setenv("AIDIGEST_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("AIDIGEST_TELEGRAM_CHAT_ID", "bootstrap-chat")

    settings = Settings.from_env()

    assert settings.default_period_days == 1
    assert settings.timezone_name == "Asia/Seoul"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_settings_load_subscriber_schedule_defaults -v`
Expected: FAIL with `AttributeError` for missing `default_period_days` or `timezone_name`

- [ ] **Step 3: Add the minimal settings fields**

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIDIGEST_",
        case_sensitive=False,
        populate_by_name=True,
        env_file=".env",
        extra="ignore",
    )

    telegram_bot_token: str = Field(min_length=1)
    telegram_chat_id: str = Field(min_length=1)
    enabled_sources_raw: str = Field(
        default="github_trending,hf_models,hf_papers,arxiv",
        validation_alias="AIDIGEST_ENABLED_SOURCES",
    )
    digest_send_time: str = "09:00"
    default_period_days: int = 1
    timezone_name: str = "Asia/Seoul"

    @property
    def enabled_sources(self) -> list[str]:
        return [
            value.strip()
            for value in self.enabled_sources_raw.split(",")
            if value.strip()
        ]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls()
```

- [ ] **Step 4: Run the targeted test**

Run: `pytest tests/test_config.py::test_settings_load_subscriber_schedule_defaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aitrendigest/config.py tests/test_config.py
git commit -m "feat: add subscriber schedule settings"
```

## Task 2: Add Subscriber And Telegram State Tables

**Files:**
- Modify: `src/aitrendigest/models.py`
- Modify: `src/aitrendigest/repository.py`
- Modify: `tests/test_repository.py`

- [ ] **Step 1: Write the failing repository tests**

```python
from datetime import date

from aitrendigest.db import create_schema, create_session_factory
from aitrendigest.repository import SubscriberRepository


def test_subscriber_repository_registers_new_chat(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'digest.db'}"
    session_factory = create_session_factory(database_url)
    create_schema(session_factory)
    repository = SubscriberRepository(session_factory)

    subscriber = repository.register_if_missing("1001", default_period_days=1, anchor_date=date(2026, 7, 1))

    assert subscriber.chat_id == "1001"
    assert subscriber.period_days == 1
    assert subscriber.anchor_date == date(2026, 7, 1)
    assert subscriber.last_sent_on is None


def test_subscriber_repository_tracks_last_update_id(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'digest.db'}"
    session_factory = create_session_factory(database_url)
    create_schema(session_factory)
    repository = SubscriberRepository(session_factory)

    assert repository.get_last_update_id() is None

    repository.set_last_update_id(42)

    assert repository.get_last_update_id() == 42
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_repository.py -v`
Expected: FAIL with missing `SubscriberRepository` or missing methods

- [ ] **Step 3: Add the new ORM models**

```python
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SubscriberRecord(Base):
    __tablename__ = "subscribers"

    chat_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelegramStateRecord(Base):
    __tablename__ = "telegram_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
```

- [ ] **Step 4: Add the minimal subscriber repository**

```python
from datetime import date, datetime, timezone

from sqlalchemy import select

from aitrendigest.models import SubscriberRecord, TelegramStateRecord


class SubscriberRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def register_if_missing(self, chat_id: str, default_period_days: int, anchor_date: date) -> SubscriberRecord:
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            record = session.get(SubscriberRecord, chat_id)
            if record is None:
                record = SubscriberRecord(
                    chat_id=chat_id,
                    is_active=True,
                    period_days=default_period_days,
                    anchor_date=anchor_date,
                    last_sent_on=None,
                    created_at=now,
                    updated_at=now,
                )
                session.add(record)
                session.commit()
                session.refresh(record)
            return record

    def get_last_update_id(self) -> int | None:
        with self._session_factory() as session:
            record = session.get(TelegramStateRecord, "last_update_id")
            return int(record.value) if record else None

    def set_last_update_id(self, update_id: int) -> None:
        with self._session_factory() as session:
            record = session.get(TelegramStateRecord, "last_update_id")
            if record is None:
                record = TelegramStateRecord(key="last_update_id", value=str(update_id))
                session.add(record)
            else:
                record.value = str(update_id)
            session.commit()
```

- [ ] **Step 5: Run repository tests**

Run: `pytest tests/test_repository.py -v`
Expected: PASS for the new subscriber and offset tests

- [ ] **Step 6: Commit**

```bash
git add src/aitrendigest/models.py src/aitrendigest/repository.py tests/test_repository.py
git commit -m "feat: add subscriber state storage"
```

## Task 3: Add Subscriber Mutation And Eligibility Logic

**Files:**
- Modify: `src/aitrendigest/repository.py`
- Modify: `src/aitrendigest/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing cadence tests**

```python
from datetime import date

from aitrendigest.pipeline import is_subscriber_due_today


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with missing `is_subscriber_due_today`

- [ ] **Step 3: Add the schedule function**

```python
from datetime import date


def is_subscriber_due_today(
    *,
    anchor_date: date,
    period_days: int,
    today: date,
    last_sent_on: date | None,
) -> bool:
    if period_days <= 0:
        return False
    if last_sent_on == today:
        return False
    days_since_anchor = (today - anchor_date).days
    if days_since_anchor < 0:
        return False
    return days_since_anchor % period_days == 0
```

- [ ] **Step 4: Add repository update helpers**

```python
from datetime import date, datetime, timezone


def update_period(self, chat_id: str, period_days: int, anchor_date: date) -> SubscriberRecord:
    now = datetime.now(timezone.utc)
    with self._session_factory() as session:
        record = session.get(SubscriberRecord, chat_id)
        if record is None:
            raise KeyError(chat_id)
        record.period_days = period_days
        record.anchor_date = anchor_date
        record.updated_at = now
        session.commit()
        session.refresh(record)
        return record


def mark_sent_on(self, chat_id: str, sent_on: date) -> None:
    now = datetime.now(timezone.utc)
    with self._session_factory() as session:
        record = session.get(SubscriberRecord, chat_id)
        if record is None:
            raise KeyError(chat_id)
        record.last_sent_on = sent_on
        record.updated_at = now
        session.commit()
```

- [ ] **Step 5: Run the targeted tests**

Run: `pytest tests/test_pipeline.py::test_is_subscriber_due_today_for_every_third_day tests/test_pipeline.py::test_is_subscriber_due_today_blocks_duplicate_same_day_send -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/aitrendigest/repository.py src/aitrendigest/pipeline.py tests/test_pipeline.py
git commit -m "feat: add subscriber delivery cadence logic"
```

## Task 4: Add Telegram Update Fetching And `/period` Parsing

**Files:**
- Modify: `src/aitrendigest/telegram.py`
- Modify: `src/aitrendigest/pipeline.py`
- Create: `tests/test_telegram.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing Telegram update client test**

```python
from aitrendigest.telegram import TelegramPublisher


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.is_success = True

    def json(self):
        return self._payload


class DummyClient:
    def get(self, url, params, timeout):
        return DummyResponse(
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 100,
                        "message": {
                            "chat": {"id": 555},
                            "text": "/period 3",
                        },
                    }
                ],
            }
        )


def test_telegram_publisher_fetches_updates():
    publisher = TelegramPublisher(DummyClient(), "token", "bootstrap")

    updates = publisher.get_updates(offset=99)

    assert updates[0]["update_id"] == 100
    assert updates[0]["message"]["text"] == "/period 3"
```

- [ ] **Step 2: Write the failing command parser test**

```python
from aitrendigest.pipeline import parse_period_command


def test_parse_period_command_accepts_positive_integer():
    assert parse_period_command("/period 3") == 3


def test_parse_period_command_rejects_invalid_input():
    assert parse_period_command("/period abc") is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_telegram.py tests/test_pipeline.py -v`
Expected: FAIL with missing `get_updates` or `parse_period_command`

- [ ] **Step 4: Add Telegram polling support**

```python
def get_updates(self, offset: int | None = None) -> list[dict]:
    url = f"https://api.telegram.org/bot{self._bot_token}/getUpdates"
    params = {"timeout": 5}
    if offset is not None:
        params["offset"] = offset
    response = self._client.get(url, params=params, timeout=10.0)
    if not response.is_success:
        raise RuntimeError(f"telegram getUpdates failed: {response.status_code}")
    payload = response.json()
    return payload.get("result", [])
```

- [ ] **Step 5: Add the command parser**

```python
import re

_PERIOD_PATTERN = re.compile(r"^/period\s+(\d+)$")


def parse_period_command(text: str | None) -> int | None:
    if not text:
        return None
    match = _PERIOD_PATTERN.match(text.strip())
    if not match:
        return None
    period_days = int(match.group(1))
    return period_days if period_days > 0 else None
```

- [ ] **Step 6: Run the new tests**

Run: `pytest tests/test_telegram.py tests/test_pipeline.py -v`
Expected: PASS for update fetch and parser coverage

- [ ] **Step 7: Commit**

```bash
git add src/aitrendigest/telegram.py src/aitrendigest/pipeline.py tests/test_telegram.py tests/test_pipeline.py
git commit -m "feat: add telegram update polling"
```

## Task 5: Process Updates Into Subscriber State

**Files:**
- Modify: `src/aitrendigest/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing update-processing tests**

```python
from datetime import date

from aitrendigest.db import create_schema, create_session_factory
from aitrendigest.repository import SubscriberRepository
from aitrendigest.pipeline import process_telegram_updates


def test_process_telegram_updates_auto_registers_unknown_chat(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'digest.db'}"
    session_factory = create_session_factory(database_url)
    create_schema(session_factory)
    repository = SubscriberRepository(session_factory)

    updates = [{"update_id": 10, "message": {"chat": {"id": 1001}, "text": "hello"}}]

    process_telegram_updates(repository, updates, today=date(2026, 7, 1), default_period_days=1)

    subscriber = repository.get_subscriber("1001")
    assert subscriber is not None
    assert subscriber.period_days == 1
    assert repository.get_last_update_id() == 10


def test_process_telegram_updates_applies_period_only_to_sender(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'digest.db'}"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with missing `process_telegram_updates` or `get_subscriber`

- [ ] **Step 3: Add the missing repository reader**

```python
def get_subscriber(self, chat_id: str) -> SubscriberRecord | None:
    with self._session_factory() as session:
        return session.get(SubscriberRecord, chat_id)
```

- [ ] **Step 4: Add update processing**

```python
def process_telegram_updates(repository, updates: list[dict], *, today: date, default_period_days: int) -> None:
    for update in updates:
        update_id = update["update_id"]
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id"))
        text = message.get("text")
        if not chat_id:
            repository.set_last_update_id(update_id)
            continue

        repository.register_if_missing(chat_id, default_period_days=default_period_days, anchor_date=today)
        period_days = parse_period_command(text)
        if period_days is not None:
            repository.update_period(chat_id, period_days=period_days, anchor_date=today)
        repository.set_last_update_id(update_id)
```

- [ ] **Step 5: Run the targeted tests**

Run: `pytest tests/test_pipeline.py::test_process_telegram_updates_auto_registers_unknown_chat tests/test_pipeline.py::test_process_telegram_updates_applies_period_only_to_sender -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/aitrendigest/repository.py src/aitrendigest/pipeline.py tests/test_pipeline.py
git commit -m "feat: process subscriber period commands"
```

## Task 6: Send Digest To Eligible Subscribers In One Batch Run

**Files:**
- Modify: `src/aitrendigest/repository.py`
- Modify: `src/aitrendigest/telegram.py`
- Modify: `src/aitrendigest/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing batch publish test**

```python
from datetime import date

from aitrendigest.db import create_schema, create_session_factory
from aitrendigest.pipeline import run_scheduled_delivery
from aitrendigest.repository import SubscriberRepository
from aitrendigest.types import TrendItemInput


class DummyPublisher:
    def __init__(self):
        self.messages = []

    def send_message(self, message: str, chat_id: str | None = None) -> None:
        self.messages.append((chat_id, message))


def test_run_scheduled_delivery_sends_only_to_due_subscribers(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'digest.db'}"
    session_factory = create_session_factory(database_url)
    create_schema(session_factory)
    repository = SubscriberRepository(session_factory)
    publisher = DummyPublisher()

    repository.register_if_missing("1001", default_period_days=1, anchor_date=date(2026, 7, 1))
    repository.register_if_missing("1002", default_period_days=3, anchor_date=date(2026, 7, 2))

    items = [
        TrendItemInput(
            source_type="github_trending",
            source_name="GitHub",
            source_item_id="repo-1",
            title="agent eval harness",
            url="https://example.com/repo-1",
            author=None,
            published_at=None,
            raw_popularity_signal={"rank": 1},
            summary="Tool calling evaluation repository",
        )
    ]

    run_scheduled_delivery(
        repository=repository,
        publisher=publisher,
        items=items,
        today=date(2026, 7, 3),
    )

    assert [chat_id for chat_id, _ in publisher.messages] == ["1001"]
    assert repository.get_subscriber("1001").last_sent_on == date(2026, 7, 3)
    assert repository.get_subscriber("1002").last_sent_on is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with missing `run_scheduled_delivery` or `send_message` signature mismatch

- [ ] **Step 3: Extend the subscriber repository and publisher**

```python
def list_active_subscribers(self) -> list[SubscriberRecord]:
    with self._session_factory() as session:
        return list(session.scalars(select(SubscriberRecord).where(SubscriberRecord.is_active.is_(True))))
```

```python
def send_message(self, message: str, chat_id: str | None = None) -> None:
    target_chat_id = chat_id or self._chat_id
    url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
    payload = {"chat_id": target_chat_id, "text": message}
    # keep the existing retry loop, but post payload with target_chat_id
```

- [ ] **Step 4: Add the batch delivery function**

```python
def run_scheduled_delivery(*, repository, publisher, items, today: date) -> str:
    subscribers = repository.list_active_subscribers()
    if not subscribers:
        return "No subscribers to notify."

    message = build_digest_message(items, date_label=today.isoformat())
    sent_count = 0
    for subscriber in subscribers:
        if not is_subscriber_due_today(
            anchor_date=subscriber.anchor_date,
            period_days=subscriber.period_days,
            today=today,
            last_sent_on=subscriber.last_sent_on,
        ):
            continue
        publisher.send_message(message, chat_id=subscriber.chat_id)
        repository.mark_sent_on(subscriber.chat_id, today)
        sent_count += 1
    return f"Sent digest to {sent_count} subscribers."
```

- [ ] **Step 5: Run the batch publish test**

Run: `pytest tests/test_pipeline.py::test_run_scheduled_delivery_sends_only_to_due_subscribers -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/aitrendigest/repository.py src/aitrendigest/telegram.py src/aitrendigest/pipeline.py tests/test_pipeline.py
git commit -m "feat: add multi-subscriber digest delivery"
```

## Task 7: Add A One-Shot CLI Command For Cron And Docker

**Files:**
- Modify: `src/aitrendigest/cli.py`
- Modify: `src/aitrendigest/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing orchestration test**

```python
from datetime import date

from aitrendigest.pipeline import run_once_for_scheduler


class DummyPublisher:
    def __init__(self):
        self.messages = []

    def send_message(self, message: str, chat_id: str | None = None) -> None:
        self.messages.append((chat_id, message))


class DummyTelegramClient:
    def get_updates(self, offset=None):
        return [
            {"update_id": 50, "message": {"chat": {"id": 2001}, "text": "hello"}},
            {"update_id": 51, "message": {"chat": {"id": 2001}, "text": "/period 7"}},
        ]


def test_run_once_for_scheduler_processes_updates_then_sends(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'digest.db'}"
    result = run_once_for_scheduler(
        database_url=database_url,
        telegram_client=DummyTelegramClient(),
        publisher=DummyPublisher(),
        today=date(2026, 7, 1),
        source_items=[],
        default_period_days=1,
    )

    assert "Sent digest to" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL with missing `run_once_for_scheduler`

- [ ] **Step 3: Add one-shot orchestration**

```python
def run_once_for_scheduler(
    *,
    database_url: str,
    telegram_client,
    publisher,
    today: date,
    source_items,
    default_period_days: int,
) -> str:
    session_factory = create_session_factory(database_url)
    create_schema(session_factory)
    repository = SubscriberRepository(session_factory)

    last_update_id = repository.get_last_update_id()
    offset = last_update_id + 1 if last_update_id is not None else None
    updates = telegram_client.get_updates(offset=offset)
    process_telegram_updates(
        repository,
        updates,
        today=today,
        default_period_days=default_period_days,
    )
    return run_scheduled_delivery(
        repository=repository,
        publisher=publisher,
        items=source_items,
        today=today,
    )
```

- [ ] **Step 4: Add the CLI command**

```python
@app.command("run-once")
def run_once() -> None:
    configure_logging()
    settings = Settings.from_env()
    publisher = TelegramPublisher(None, settings.telegram_bot_token, settings.telegram_chat_id)
    message = run_once_for_scheduler(
        database_url=settings.database_url,
        telegram_client=publisher,
        publisher=publisher,
        today=date.today(),
        source_items=collect_enabled_sources(settings),
        default_period_days=settings.default_period_days,
    )
    typer.echo(message)
```

- [ ] **Step 5: Run the targeted test**

Run: `pytest tests/test_pipeline.py::test_run_once_for_scheduler_processes_updates_then_sends -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/aitrendigest/cli.py src/aitrendigest/pipeline.py tests/test_pipeline.py
git commit -m "feat: add scheduled batch command"
```

## Task 8: Add Docker Runtime And Linux Operations Docs

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docs/operations/telegram-subscriber-period.md`

- [ ] **Step 1: Add the Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

CMD ["python", "-m", "aitrendigest.cli", "run-once"]
```

- [ ] **Step 2: Add the Docker ignore file**

```text
.git
.venv
__pycache__
.pytest_cache
*.pyc
.env
*.db
```

- [ ] **Step 3: Add the Linux deployment notes**

```markdown
# Telegram Subscriber Period Operations

## Build

```bash
docker build -t ai-trendigest:latest .
```

## Manual run

```bash
docker run --rm --env-file /opt/ai-trend/.env ai-trendigest:latest
```

## Cron

```cron
0 9 * * * docker run --rm --env-file /opt/ai-trend/.env ai-trendigest:latest >> /opt/ai-trend/run.log 2>&1
```
```

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore docs/operations/telegram-subscriber-period.md
git commit -m "docs: add docker and cron runtime guide"
```

## Task 9: Full Verification Pass

**Files:**
- Verify only; no file changes expected unless failures are found

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: PASS with the existing suite plus the new subscriber tests

- [ ] **Step 2: Run a local one-shot dry validation**

Run: `python -m aitrendigest.cli run-once`
Expected: command completes, processes Telegram updates, and prints a subscriber send summary

- [ ] **Step 3: Build the Docker image**

Run: `docker build -t ai-trendigest:latest .`
Expected: image builds successfully

- [ ] **Step 4: Commit any final verification-only doc or test fixes**

```bash
git add .
git commit -m "test: verify subscriber period delivery flow"
```

## Self-Review

Spec coverage check:

- auto-registration: Task 5
- `/period N` updates: Task 4 and Task 5
- per-subscriber cadence and anchor date: Task 3
- batch send to eligible subscribers only: Task 6
- one-shot cron-friendly command: Task 7
- Docker and Linux cron operations: Task 8
- duplicate command prevention with `last_update_id`: Task 2 and Task 5

Placeholder scan:

- no `TODO`, `TBD`, or implicit "handle this somehow" steps remain
- every code-changing task includes concrete snippets and commands

Type consistency check:

- `SubscriberRepository`, `is_subscriber_due_today`, `parse_period_command`, `process_telegram_updates`, `run_scheduled_delivery`, and `run_once_for_scheduler` are introduced before later tasks rely on them
- `last_sent_on` and `anchor_date` consistently use `date`
- Telegram update offset handling consistently uses `last_update_id`
