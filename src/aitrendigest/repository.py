from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from aitrendigest.models import SubscriberRecord, TelegramStateRecord, TrendItemRecord
from aitrendigest.types import TrendItemInput


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ItemRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _find_existing(self, session: Session, item: TrendItemInput) -> TrendItemRecord | None:
        return session.execute(
            select(TrendItemRecord).where(
                TrendItemRecord.source_type == item.source_type,
                TrendItemRecord.source_item_id == item.source_item_id,
            )
        ).scalar_one_or_none()

    @staticmethod
    def _apply_item(record: TrendItemRecord, item: TrendItemInput) -> None:
        record.source_name = item.source_name
        record.title = item.title
        record.url = item.url
        record.author = item.author
        record.published_at = item.published_at
        record.raw_popularity_signal = item.raw_popularity_signal
        record.summary = item.summary
        record.fetched_at = _utcnow()

    def upsert_item(self, item: TrendItemInput) -> int:
        with self._session_factory() as session:
            existing = self._find_existing(session, item)
            if existing is not None:
                self._apply_item(existing, item)
                session.commit()
                return existing.id

            record = TrendItemRecord(
                source_type=item.source_type,
                source_name=item.source_name,
                source_item_id=item.source_item_id,
                title=item.title,
                url=item.url,
                author=item.author,
                published_at=item.published_at,
                fetched_at=_utcnow(),
                raw_popularity_signal=item.raw_popularity_signal,
                summary=item.summary,
                send_status="new",
            )
            session.add(record)

            try:
                session.commit()
                return record.id
            except IntegrityError:
                session.rollback()
                existing = self._find_existing(session, item)
                if existing is None:
                    raise

                self._apply_item(existing, item)
                session.commit()
                return existing.id

    def count_items(self) -> int:
        with self._session_factory() as session:
            return session.execute(select(func.count(TrendItemRecord.id))).scalar_one()

    def list_items(self, send_status: str | None = None, limit: int | None = None) -> list[TrendItemRecord]:
        with self._session_factory() as session:
            query = select(TrendItemRecord).order_by(
                TrendItemRecord.fetched_at.desc(),
                TrendItemRecord.id.desc(),
            )
            if send_status is not None:
                query = query.where(TrendItemRecord.send_status == send_status)
            if limit is not None:
                query = query.limit(limit)
            return list(session.execute(query).scalars().all())

    def mark_items_sent(self, item_ids: Iterable[int]) -> None:
        ids = list(item_ids)
        if not ids:
            return

        with self._session_factory() as session:
            session.execute(
                update(TrendItemRecord)
                .where(TrendItemRecord.id.in_(ids))
                .values(send_status="sent")
            )
            session.commit()


class SubscriberRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def register_if_missing(self, chat_id: str, default_period_days: int, anchor_date: date) -> SubscriberRecord:
        now = _utcnow()
        with self._session_factory() as session:
            record = session.get(SubscriberRecord, chat_id)
            if record is not None:
                return record

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

            try:
                session.commit()
                session.refresh(record)
                return record
            except IntegrityError:
                session.rollback()
                existing = session.get(SubscriberRecord, chat_id)
                if existing is None:
                    raise
                return existing

    def get_last_update_id(self) -> int | None:
        with self._session_factory() as session:
            record = session.get(TelegramStateRecord, "last_update_id")
            if record is None:
                return None
            return int(record.value)

    def set_last_update_id(self, update_id: int) -> None:
        with self._session_factory() as session:
            record = session.get(TelegramStateRecord, "last_update_id")
            if record is None:
                record = TelegramStateRecord(key="last_update_id", value=str(update_id))
                session.add(record)
                try:
                    session.commit()
                    return
                except IntegrityError:
                    session.rollback()
                    record = session.get(TelegramStateRecord, "last_update_id")
                    if record is None:
                        raise
            record.value = str(update_id)
            session.commit()
