import os
import tempfile
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("APP_TOKEN", "test-token")
os.environ.setdefault("DEEPSEEK_MOCK", "true")
os.environ.setdefault("AUTO_CREATE_TABLES", "true")

db_path = Path(tempfile.gettempdir()) / "a_share_review_test.db"
if db_path.exists():
    db_path.unlink()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.dependencies import get_market_data_service, get_summarizer
from app.main import app


class FakeMarketDataService:
    def fetch_market_snapshot(self, trade_date):
        return {
            "trade_date": trade_date.isoformat(),
            "indexes": [
                {
                    "code": "sh000001",
                    "name": "上证指数",
                    "date": trade_date.isoformat(),
                    "close": 3100.12,
                    "pct_change": 0.86,
                }
            ],
            "breadth": {
                "total_count": 5,
                "rising_count": 3,
                "falling_count": 1,
                "flat_count": 1,
                "source": "stock_zh_a_spot_em",
            },
            "limit_stats": {
                "limit_up_count": 2,
                "limit_down_count": 1,
                "source": "akshare_limit_pool",
            },
            "hot_sectors": [{"sector": "人工智能", "limit_up_count": 2, "sample_stocks": ["测试A", "测试B"]}],
            "sample_limit_up": [],
            "sample_limit_down": [],
            "data_quality": {"source": "AKShare", "warnings": []},
        }


class FakeSummarizer:
    model_name = "deepseek-v4-pro:fake"

    def summarize(self, market_snapshot, operations):
        return {
            "market_direction": "大盘整体上涨",
            "daily_hotspots": market_snapshot["hot_sectors"],
            "limit_up_count": 2,
            "limit_down_count": 1,
            "rising_count": 3,
            "falling_count": 1,
            "operation_reviews": [
                {
                    "stock_code": operation.stock_code,
                    "stock_name": operation.stock_name,
                    "action": operation.action,
                    "selection_reason_review": "选股逻辑清晰。",
                    "buy_reason_review": "买入理由可复盘。",
                    "hold_reason_review": "持股理由待补充。",
                    "sell_reason_review": "卖出理由待补充。",
                    "profit_loss_review": "记录盈亏：100.0000",
                    "lessons": "注意仓位。",
                }
                for operation in operations
            ],
            "lessons": "保持计划交易。",
            "risk_notes": "注意市场波动。",
            "disclaimer": "仅供复盘记录。",
            "data_quality": {"warnings": []},
        }


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    app.dependency_overrides[get_market_data_service] = lambda: FakeMarketDataService()
    app.dependency_overrides[get_summarizer] = lambda: FakeSummarizer()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"X-App-Token": "test-token"}
