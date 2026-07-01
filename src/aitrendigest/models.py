from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TrendItemRecord(Base):
    __tablename__ = "trend_items"
    __table_args__ = (
        UniqueConstraint("source_type", "source_item_id", name="uq_source_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_popularity_signal: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    normalized_popularity_score: Mapped[float | None]
    summary: Mapped[str | None] = mapped_column(Text())
    why_it_matters: Mapped[str | None] = mapped_column(Text())
    tags: Mapped[str | None] = mapped_column(String(255))
    topic_fingerprint: Mapped[str | None] = mapped_column(String(255))
    duplicate_group_id: Mapped[str | None] = mapped_column(String(255))
    final_score: Mapped[float | None]
    send_status: Mapped[str] = mapped_column(String(30), default="new", nullable=False)


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
