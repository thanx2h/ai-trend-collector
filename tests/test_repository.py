from datetime import datetime, timezone
from time import sleep
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from aitrendigest.db import create_schema, create_session_factory, dispose_engine
from aitrendigest.models import TrendItemRecord
from aitrendigest.repository import ItemRepository
from aitrendigest.types import TrendItemInput


def _database_url() -> str:
    return f"sqlite+pysqlite:///file:{uuid4()}?mode=memory&cache=shared&uri=true"


def test_repository_upserts_item_by_source_identity():
    database_url = _database_url()
    try:
        session_factory = create_session_factory(database_url)
        create_schema(database_url)
        repository = ItemRepository(session_factory)

        item = TrendItemInput(
            source_type='github_trending',
            source_name='GitHub Trending',
            source_item_id='owner/repo',
            title='owner/repo',
            url='https://github.com/owner/repo',
            author='owner',
            published_at=None,
            raw_popularity_signal={'rank': 1, 'stars': 1200},
            summary=None,
        )

        first_id = repository.upsert_item(item)
        second_id = repository.upsert_item(item)

        assert first_id == second_id
        assert repository.count_items() == 1
    finally:
        dispose_engine(database_url)


def test_repository_upsert_update_persists_changed_fields():
    database_url = _database_url()
    try:
        session_factory = create_session_factory(database_url)
        create_schema(session_factory)
        repository = ItemRepository(session_factory)

        original = TrendItemInput(
            source_type='github_trending',
            source_name='GitHub Trending',
            source_item_id='owner/repo',
            title='owner/repo',
            url='https://github.com/owner/repo',
            author='owner',
            published_at=None,
            raw_popularity_signal={'rank': 1, 'stars': 1200},
            summary=None,
        )

        record_id = repository.upsert_item(original)
        with session_factory() as session:
            created = session.execute(
                select(TrendItemRecord).where(TrendItemRecord.id == record_id)
            ).scalar_one()
            created_fetched_at = created.fetched_at

        sleep(0.01)

        updated = TrendItemInput(
            source_type='github_trending',
            source_name='GitHub Trending',
            source_item_id='owner/repo',
            title='owner/repo-renamed',
            url='https://github.com/owner/repo-renamed',
            author='owner',
            published_at=None,
            raw_popularity_signal={'rank': 2, 'stars': 2400},
            summary='New summary',
        )

        updated_id = repository.upsert_item(updated)

        with session_factory() as session:
            persisted = session.execute(
                select(TrendItemRecord).where(TrendItemRecord.id == record_id)
            ).scalar_one()

        assert updated_id == record_id
        assert persisted.title == updated.title
        assert persisted.url == updated.url
        assert persisted.summary == updated.summary
        assert persisted.raw_popularity_signal == updated.raw_popularity_signal
        assert persisted.fetched_at > created_fetched_at
        assert repository.count_items() == 1
    finally:
        dispose_engine(database_url)


def test_repository_upsert_recovers_from_integrity_error_race():
    item = TrendItemInput(
        source_type='github_trending',
        source_name='GitHub Trending',
        source_item_id='owner/repo',
        title='owner/repo-renamed',
        url='https://github.com/owner/repo-renamed',
        author='owner',
        published_at=None,
        raw_popularity_signal={'rank': 2, 'stars': 2400},
        summary='New summary',
    )
    existing = TrendItemRecord(
        id=7,
        source_type=item.source_type,
        source_name='Old Source',
        source_item_id=item.source_item_id,
        title='old-title',
        url='https://github.com/owner/repo',
        author='owner',
        published_at=None,
        fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        raw_popularity_signal={'rank': 1, 'stars': 1200},
        summary=None,
        send_status='new',
    )

    class FakeResult:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class FakeSession:
        def __init__(self):
            self.lookup_results = [None, existing]
            self.commit_calls = 0
            self.rollback_calls = 0
            self.added_record = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement):
            return FakeResult(self.lookup_results.pop(0))

        def add(self, record):
            self.added_record = record

        def commit(self):
            self.commit_calls += 1
            if self.commit_calls == 1:
                raise IntegrityError('insert', {}, Exception('race'))

        def rollback(self):
            self.rollback_calls += 1

    fake_session = FakeSession()

    class FakeSessionFactory:
        def __call__(self):
            return fake_session

    repository = ItemRepository(FakeSessionFactory())

    record_id = repository.upsert_item(item)

    assert record_id == existing.id
    assert fake_session.rollback_calls == 1
    assert fake_session.added_record is not None
    assert existing.title == item.title
    assert existing.url == item.url
    assert existing.summary == item.summary
    assert existing.raw_popularity_signal == item.raw_popularity_signal
    assert existing.fetched_at > datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_create_schema_accepts_session_factory_bind():
    database_url = _database_url()
    try:
        session_factory = create_session_factory(database_url)

        create_schema(session_factory)

        with session_factory() as session:
            session.add(
                TrendItemRecord(
                    source_type='github_trending',
                    source_name='GitHub Trending',
                    source_item_id='owner/repo',
                    title='owner/repo',
                    url='https://github.com/owner/repo',
                    author='owner',
                    published_at=None,
                    fetched_at=datetime.now(timezone.utc),
                    raw_popularity_signal={'rank': 1},
                    summary=None,
                    send_status='new',
                )
            )
            session.commit()

        repository = ItemRepository(session_factory)
        assert repository.count_items() == 1
    finally:
        dispose_engine(database_url)


def test_dispose_engine_replaces_cached_engine_instance():
    database_url = _database_url()
    try:
        first_session_factory = create_session_factory(database_url)
        first_engine = first_session_factory.kw['bind']

        dispose_engine(database_url)

        second_session_factory = create_session_factory(database_url)
        second_engine = second_session_factory.kw['bind']

        assert first_engine is not second_engine
    finally:
        dispose_engine(database_url)
