from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database import Base


JSONType = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StockOperation(TimestampMixin, Base):
    __tablename__ = "stock_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    action: Mapped[str] = mapped_column(String(30), index=True)
    selection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    buy_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sell_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    profit_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    lessons: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_stock_operations_trade_date_action", "trade_date", "action"),)


class DailyReview(TimestampMixin, Base):
    __tablename__ = "daily_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    market_snapshot: Mapped[dict] = mapped_column(JSONType, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONType, nullable=False)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (UniqueConstraint("trade_date", name="uq_daily_reviews_trade_date"),)
