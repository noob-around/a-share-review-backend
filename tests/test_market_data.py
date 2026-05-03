import pandas as pd

from app.services.market_data import AKShareMarketDataService


def test_breadth_and_fallback_limit_stats_from_spot_dataframe():
    service = AKShareMarketDataService()
    df = pd.DataFrame(
        [
            {"代码": "600001", "名称": "上涨股", "最新价": 10.0, "涨跌幅": 10.01},
            {"代码": "600002", "名称": "下跌股", "最新价": 9.0, "涨跌幅": -10.02},
            {"代码": "600003", "名称": "平盘股", "最新价": 8.0, "涨跌幅": 0.0},
            {"代码": "600004", "名称": "无效股", "最新价": None, "涨跌幅": 2.0},
        ]
    )

    breadth = service._build_breadth(df)
    assert breadth["total_count"] == 3
    assert breadth["rising_count"] == 1
    assert breadth["falling_count"] == 1
    assert breadth["flat_count"] == 1

    limit_stats = service._fallback_limit_stats(df)
    assert limit_stats["limit_up_count"] == 1
    assert limit_stats["limit_down_count"] == 1
    assert limit_stats["source"] == "spot_pct_threshold_fallback"


def test_hot_sectors_from_limit_up_pool():
    service = AKShareMarketDataService()
    df = pd.DataFrame(
        [
            {"代码": "1", "名称": "A", "所属行业": "人工智能"},
            {"代码": "2", "名称": "B", "所属行业": "人工智能"},
            {"代码": "3", "名称": "C", "所属行业": "机器人"},
        ]
    )

    sectors = service._build_hot_sectors(df)
    assert sectors[0]["sector"] == "人工智能"
    assert sectors[0]["limit_up_count"] == 2
    assert sectors[0]["sample_stocks"] == ["A", "B"]
