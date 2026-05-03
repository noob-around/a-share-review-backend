from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StockOperationBase(BaseModel):
    stock_code: str = Field(..., min_length=1, max_length=20, examples=["600519"])
    stock_name: str | None = Field(default=None, max_length=80, examples=["贵州茅台"])
    trade_date: date
    action: str = Field(..., min_length=1, max_length=30, examples=["买入"])
    selection_reason: str | None = None
    buy_reason: str | None = None
    hold_reason: str | None = None
    sell_reason: str | None = None
    price: Decimal | None = None
    quantity: Decimal | None = None
    profit_loss: Decimal | None = None
    lessons: str | None = None
    notes: str | None = None


class StockOperationCreate(StockOperationBase):
    pass


class StockOperationRead(StockOperationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class DailyReviewRequest(BaseModel):
    trade_date: date | None = Field(default=None, description="缺省时使用 Asia/Shanghai 当前日期")
    refresh: bool = Field(default=False, description="是否强制重新抓取并生成总结")
    include_operations: bool = Field(default=True, description="是否纳入当日股票操作记录")
    async_mode: bool = Field(default=False, description="是否后台生成复盘，避免线上长请求超时")


class DailyReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_date: date
    market_snapshot: dict[str, Any]
    summary: dict[str, Any]
    model_name: str
    prompt_version: str
    status: str
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
