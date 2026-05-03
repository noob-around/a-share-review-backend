from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.dependencies import get_market_data_service, get_summarizer
from app.models import DailyReview, StockOperation
from app.schemas import DailyReviewRead, DailyReviewRequest
from app.security import require_app_token
from app.services.deepseek import PROMPT_VERSION, DeepSeekSummarizer
from app.services.excel_exporter import build_review_workbook
from app.services.market_data import AKShareMarketDataService, MarketDataError

router = APIRouter(prefix="/api/reviews", tags=["reviews"], dependencies=[Depends(require_app_token)])


@router.post("/daily", response_model=DailyReviewRead, status_code=201)
def create_daily_review(
    payload: DailyReviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    market_data: AKShareMarketDataService = Depends(get_market_data_service),
    summarizer: DeepSeekSummarizer = Depends(get_summarizer),
) -> DailyReview:
    settings = get_settings()
    trade_date = payload.trade_date or datetime.now(settings.tzinfo).date()

    existing = db.scalar(select(DailyReview).where(DailyReview.trade_date == trade_date))
    if existing and not payload.refresh:
        return existing

    if payload.async_mode:
        review = _upsert_pending_review(db, existing, trade_date, summarizer.model_name)
        background_tasks.add_task(_generate_review_background, review.id, trade_date, payload.include_operations)
        return review

    operations = _operations_for_date(db, trade_date) if payload.include_operations else []
    try:
        market_snapshot = market_data.fetch_market_snapshot(trade_date)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    summary = summarizer.summarize(market_snapshot, operations)

    if existing:
        existing.market_snapshot = market_snapshot
        existing.summary = summary
        existing.model_name = summarizer.model_name
        existing.prompt_version = PROMPT_VERSION
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    review = DailyReview(
        trade_date=trade_date,
        market_snapshot=market_snapshot,
        summary=summary,
        model_name=summarizer.model_name,
        prompt_version=PROMPT_VERSION,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/{review_id}", response_model=DailyReviewRead)
def get_daily_review(review_id: int, db: Session = Depends(get_db)) -> DailyReview:
    review = db.get(DailyReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    return review


@router.get("/{review_id}/excel")
def download_daily_review_excel(review_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    review = db.get(DailyReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    if review.status != "completed":
        raise HTTPException(status_code=409, detail=f"Review is {review.status}; Excel is available after completion.")
    operations = _operations_for_date(db, review.trade_date)
    workbook = build_review_workbook(review, operations)
    filename = f"a_share_daily_review_{review.trade_date.strftime('%Y%m%d')}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


def _operations_for_date(db: Session, trade_date) -> list[StockOperation]:
    stmt = (
        select(StockOperation)
        .where(StockOperation.trade_date == trade_date)
        .order_by(StockOperation.id.asc())
    )
    return list(db.scalars(stmt).all())


def _upsert_pending_review(
    db: Session,
    existing: DailyReview | None,
    trade_date,
    model_name: str,
) -> DailyReview:
    pending_snapshot = {
        "trade_date": trade_date.isoformat(),
        "data_quality": {"source": "pending", "warnings": ["复盘正在后台生成。"]},
    }
    pending_summary = {
        "market_direction": "复盘正在后台生成。",
        "daily_hotspots": [],
        "limit_up_count": 0,
        "limit_down_count": 0,
        "rising_count": 0,
        "falling_count": 0,
        "operation_reviews": [],
        "lessons": "",
        "risk_notes": "",
        "disclaimer": "本内容仅用于复盘记录，不构成投资建议。",
        "data_quality": {"warnings": ["复盘正在后台生成。"]},
    }
    if existing:
        existing.market_snapshot = pending_snapshot
        existing.summary = pending_summary
        existing.model_name = model_name
        existing.prompt_version = PROMPT_VERSION
        existing.status = "generating"
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    review = DailyReview(
        trade_date=trade_date,
        market_snapshot=pending_snapshot,
        summary=pending_summary,
        model_name=model_name,
        prompt_version=PROMPT_VERSION,
        status="generating",
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def _generate_review_background(review_id: int, trade_date, include_operations: bool) -> None:
    db = SessionLocal()
    market_data = AKShareMarketDataService()
    summarizer = DeepSeekSummarizer()
    try:
        review = db.get(DailyReview, review_id)
        if not review:
            return
        operations = _operations_for_date(db, trade_date) if include_operations else []
        market_snapshot = market_data.fetch_market_snapshot(trade_date)
        summary = summarizer.summarize(market_snapshot, operations)
        review.market_snapshot = market_snapshot
        review.summary = summary
        review.model_name = summarizer.model_name
        review.prompt_version = PROMPT_VERSION
        review.status = "completed"
        db.add(review)
        db.commit()
    except Exception as exc:
        review = db.get(DailyReview, review_id)
        if review:
            review.status = "failed"
            review.summary = {
                "market_direction": "复盘生成失败。",
                "daily_hotspots": [],
                "limit_up_count": 0,
                "limit_down_count": 0,
                "rising_count": 0,
                "falling_count": 0,
                "operation_reviews": [],
                "lessons": "",
                "risk_notes": "",
                "disclaimer": "本内容仅用于复盘记录，不构成投资建议。",
                "data_quality": {"warnings": [f"后台生成失败: {exc}"]},
            }
            db.add(review)
            db.commit()
    finally:
        db.close()
