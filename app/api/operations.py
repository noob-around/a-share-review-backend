from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StockOperation
from app.schemas import StockOperationCreate, StockOperationRead
from app.security import require_app_token

router = APIRouter(prefix="/api/operations", tags=["operations"], dependencies=[Depends(require_app_token)])


@router.post("", response_model=StockOperationRead, status_code=201)
def create_operation(payload: StockOperationCreate, db: Session = Depends(get_db)) -> StockOperation:
    operation = StockOperation(**payload.model_dump())
    db.add(operation)
    db.commit()
    db.refresh(operation)
    return operation


@router.get("", response_model=list[StockOperationRead])
def list_operations(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[StockOperation]:
    stmt = select(StockOperation).order_by(StockOperation.trade_date.desc(), StockOperation.id.desc())
    if start_date:
        stmt = stmt.where(StockOperation.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(StockOperation.trade_date <= end_date)
    return list(db.scalars(stmt).all())
