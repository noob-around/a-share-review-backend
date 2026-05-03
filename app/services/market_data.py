from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any


class MarketDataError(RuntimeError):
    pass


class AKShareMarketDataService:
    index_symbols = (
        {"code": "sh000001", "name": "上证指数"},
        {"code": "sz399001", "name": "深证成指"},
        {"code": "sz399006", "name": "创业板指"},
    )

    def fetch_market_snapshot(self, trade_date: date) -> dict[str, Any]:
        ak = self._load_akshare()
        warnings: list[str] = []
        spot_df = self._safe_call(ak.stock_zh_a_spot_em, "A股实时行情")

        breadth = self._build_breadth(spot_df)
        indexes = self._build_indexes(ak, trade_date, warnings)
        limit_up_df, limit_down_df, limit_warning = self._fetch_limit_pools(ak, trade_date)
        if limit_warning:
            warnings.append(limit_warning)

        if limit_up_df is None or limit_down_df is None:
            limit_stats = self._fallback_limit_stats(spot_df)
        else:
            limit_stats = {
                "limit_up_count": self._row_count(limit_up_df),
                "limit_down_count": self._row_count(limit_down_df),
                "source": "akshare_limit_pool",
            }

        snapshot = {
            "trade_date": trade_date.isoformat(),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "indexes": indexes,
            "breadth": breadth,
            "limit_stats": limit_stats,
            "hot_sectors": self._build_hot_sectors(limit_up_df),
            "sample_limit_up": self._sample_stocks(limit_up_df),
            "sample_limit_down": self._sample_stocks(limit_down_df),
            "data_quality": {
                "source": "AKShare",
                "warnings": warnings,
            },
        }
        return self._json_safe(snapshot)

    def _load_akshare(self) -> Any:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - exercised in environments without deps
            raise MarketDataError("AKShare is not installed or cannot be imported.") from exc
        return ak

    def _safe_call(self, fn: Any, label: str, **kwargs: Any) -> Any:
        try:
            return fn(**kwargs)
        except Exception as exc:
            raise MarketDataError(f"{label} 获取失败: {exc}") from exc

    def _build_indexes(self, ak: Any, trade_date: date, warnings: list[str]) -> list[dict[str, Any]]:
        indexes: list[dict[str, Any]] = []
        for item in self.index_symbols:
            try:
                df = ak.stock_zh_index_daily_em(symbol=item["code"])
                row = self._last_row_on_or_before(df, trade_date)
                if row:
                    indexes.append(
                        {
                            "code": item["code"],
                            "name": item["name"],
                            "date": self._first_value(row, "日期", "date"),
                            "open": self._first_value(row, "开盘", "open"),
                            "close": self._first_value(row, "收盘", "close"),
                            "high": self._first_value(row, "最高", "high"),
                            "low": self._first_value(row, "最低", "low"),
                            "volume": self._first_value(row, "成交量", "volume"),
                            "amount": self._first_value(row, "成交额", "amount"),
                            "pct_change": self._first_value(row, "涨跌幅", "pct_chg", "change_pct"),
                        }
                    )
                    continue
                warnings.append(f"{item['name']} 未找到 {trade_date.isoformat()} 或之前的指数日线数据。")
            except Exception as exc:
                warnings.append(f"{item['name']} 指数日线获取失败: {exc}")

        if indexes:
            return indexes

        try:
            spot = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
            for item in self.index_symbols:
                row = self._find_spot_index(spot, item)
                if row:
                    indexes.append(
                        {
                            "code": item["code"],
                            "name": item["name"],
                            "date": trade_date.isoformat(),
                            "open": self._first_value(row, "今开"),
                            "close": self._first_value(row, "最新价"),
                            "high": self._first_value(row, "最高"),
                            "low": self._first_value(row, "最低"),
                            "volume": self._first_value(row, "成交量"),
                            "amount": self._first_value(row, "成交额"),
                            "pct_change": self._first_value(row, "涨跌幅"),
                        }
                    )
            warnings.append("指数日线不可用，已使用实时指数行情降级。")
        except Exception as exc:
            warnings.append(f"指数实时行情降级也失败: {exc}")
        return indexes

    def _build_breadth(self, df: Any) -> dict[str, Any]:
        rows = self._records(df)
        valid = [row for row in rows if self._to_float(self._first_value(row, "最新价", "latest_price")) is not None]
        pct_rows = [row for row in valid if self._to_float(self._first_value(row, "涨跌幅", "pct_change")) is not None]
        pct_values = [self._to_float(self._first_value(row, "涨跌幅", "pct_change")) for row in pct_rows]
        return {
            "total_count": len(valid),
            "rising_count": sum(1 for value in pct_values if value is not None and value > 0),
            "falling_count": sum(1 for value in pct_values if value is not None and value < 0),
            "flat_count": sum(1 for value in pct_values if value == 0),
            "source": "stock_zh_a_spot_em",
        }

    def _fetch_limit_pools(self, ak: Any, trade_date: date) -> tuple[Any | None, Any | None, str | None]:
        date_str = trade_date.strftime("%Y%m%d")
        try:
            return ak.stock_zt_pool_em(date=date_str), ak.stock_zt_pool_dtgc_em(date=date_str), None
        except Exception as exc:
            return None, None, f"涨跌停池接口不可用，已使用涨跌幅阈值降级统计: {exc}"

    def _fallback_limit_stats(self, spot_df: Any) -> dict[str, Any]:
        rows = self._records(spot_df)
        pct_values = [self._to_float(self._first_value(row, "涨跌幅", "pct_change")) for row in rows]
        return {
            "limit_up_count": sum(1 for value in pct_values if value is not None and value >= 9.8),
            "limit_down_count": sum(1 for value in pct_values if value is not None and value <= -9.8),
            "source": "spot_pct_threshold_fallback",
        }

    def _build_hot_sectors(self, limit_up_df: Any | None) -> list[dict[str, Any]]:
        if limit_up_df is None or self._row_count(limit_up_df) == 0:
            return []
        rows = self._records(limit_up_df)
        sector_col = self._first_existing_column(rows, "所属行业", "行业", "板块", "主题", "概念")
        if not sector_col:
            return []
        counts = Counter(str(row.get(sector_col) or "").strip() for row in rows)
        counts.pop("", None)
        result = []
        for sector, count in counts.most_common(5):
            names = [
                str(self._first_value(row, "名称", "name", "股票简称") or "")
                for row in rows
                if str(row.get(sector_col) or "").strip() == sector
            ]
            result.append({"sector": sector, "limit_up_count": count, "sample_stocks": [name for name in names[:5] if name]})
        return result

    def _sample_stocks(self, df: Any | None, limit: int = 10) -> list[dict[str, Any]]:
        if df is None:
            return []
        result = []
        for row in self._records(df)[:limit]:
            result.append(
                {
                    "code": self._first_value(row, "代码", "股票代码", "code"),
                    "name": self._first_value(row, "名称", "name", "股票简称"),
                    "pct_change": self._first_value(row, "涨跌幅", "pct_change"),
                    "industry": self._first_value(row, "所属行业", "行业", "板块"),
                    "reason": self._first_value(row, "涨停原因", "原因", "主题"),
                }
            )
        return result

    def _last_row_on_or_before(self, df: Any, target: date) -> dict[str, Any] | None:
        rows = self._records(df)
        candidates = []
        for row in rows:
            row_date = self._parse_date(self._first_value(row, "日期", "date"))
            if row_date and row_date <= target:
                candidates.append((row_date, row))
        if not candidates:
            return None
        candidates.sort(key=lambda pair: pair[0])
        return candidates[-1][1]

    def _find_spot_index(self, df: Any, item: dict[str, str]) -> dict[str, Any] | None:
        short_code = item["code"][2:]
        for row in self._records(df):
            code = str(self._first_value(row, "代码", "code") or "")
            name = str(self._first_value(row, "名称", "name") or "")
            if code == short_code or name == item["name"]:
                return row
        return None

    def _records(self, df: Any) -> list[dict[str, Any]]:
        if df is None:
            return []
        if isinstance(df, list):
            return [dict(row) for row in df]
        if hasattr(df, "to_dict"):
            return df.to_dict(orient="records")
        return []

    def _row_count(self, df: Any) -> int:
        if df is None:
            return 0
        try:
            return len(df)
        except TypeError:
            return 0

    def _first_existing_column(self, rows: list[dict[str, Any]], *names: str) -> str | None:
        if not rows:
            return None
        columns = set(rows[0].keys())
        return next((name for name in names if name in columns), None)

    def _first_value(self, row: dict[str, Any], *names: str) -> Any:
        for name in names:
            if name in row:
                return row[name]
        return None

    def _parse_date(self, value: Any) -> date | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value)
        for fmt in ("%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt).date()
            except ValueError:
                continue
        return None

    def _to_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            if value != value:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._json_safe(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if hasattr(value, "item"):
            return self._json_safe(value.item())
        if value != value:
            return None
        return value
