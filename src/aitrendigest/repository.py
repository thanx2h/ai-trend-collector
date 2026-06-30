from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Iterable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from aitrendigest.models import TrendItemRecord
from aitrendigest.types import TrendItemInput


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
        record.fetched_at = datetime.now(timezone.utc)

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
                fetched_at=datetime.now(timezone.utc),
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
