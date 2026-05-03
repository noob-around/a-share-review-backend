from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from app.config import get_settings
from app.models import StockOperation


PROMPT_VERSION = "daily-review-v1"


class DeepSeekSummarizer:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def model_name(self) -> str:
        if self.settings.should_mock_deepseek:
            return f"{self.settings.deepseek_model}:mock"
        return self.settings.deepseek_model

    def summarize(self, market_snapshot: dict[str, Any], operations: list[StockOperation]) -> dict[str, Any]:
        payload = {
            "market_snapshot": market_snapshot,
            "operations": [self._operation_payload(operation) for operation in operations],
        }
        if self.settings.should_mock_deepseek:
            return self._post_process(self._mock_summary(payload), market_snapshot)

        try:
            return self._post_process(self._call_deepseek(payload), market_snapshot)
        except Exception as exc:
            fallback = self._mock_summary(payload)
            fallback["data_quality"]["warnings"].append(f"DeepSeek 调用失败，已使用本地模板总结: {exc}")
            return self._post_process(fallback, market_snapshot)

    def _call_deepseek(self, payload: dict[str, Any]) -> dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.deepseek_api_key, base_url=self.settings.deepseek_base_url)
        response = client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是A股复盘助手。只做交易记录复盘和风险提示，不给出确定性投资建议。"
                        "必须输出合法JSON，不要输出Markdown。所有字符串字段必须使用简体中文。"
                    ),
                },
                {"role": "user", "content": self._prompt(payload)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=4096,
            extra_body={"thinking": {"type": "disabled"}},
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return self._ensure_shape(parsed)

    def _prompt(self, payload: dict[str, Any]) -> str:
        return (
            "请基于以下JSON生成每日复盘，输出字段必须包含："
            "market_direction, daily_hotspots, limit_up_count, limit_down_count, rising_count, "
            "falling_count, operation_reviews, lessons, risk_notes, disclaimer。\n"
            "market_direction 必须是简体中文短句，例如“大盘整体上涨，市场赚钱效应较强”。\n"
            "operation_reviews 每项包含 stock_code, stock_name, action, selection_reason_review, "
            "buy_reason_review, hold_reason_review, sell_reason_review, profit_loss_review, lessons。\n"
            f"输入JSON：{json.dumps(payload, ensure_ascii=False, default=str)}"
        )

    def _mock_summary(self, payload: dict[str, Any]) -> dict[str, Any]:
        market = payload["market_snapshot"]
        breadth = market.get("breadth", {})
        limit_stats = market.get("limit_stats", {})
        indexes = market.get("indexes", [])
        sh_index = next((item for item in indexes if item.get("name") == "上证指数"), indexes[0] if indexes else {})
        pct_change = sh_index.get("pct_change")
        direction = "震荡"
        if isinstance(pct_change, (int, float)):
            direction = "上涨" if pct_change > 0 else "下跌" if pct_change < 0 else "平盘"

        operation_reviews = []
        for operation in payload.get("operations", []):
            operation_reviews.append(
                {
                    "stock_code": operation.get("stock_code"),
                    "stock_name": operation.get("stock_name"),
                    "action": operation.get("action"),
                    "selection_reason_review": operation.get("selection_reason") or "未记录选股理由。",
                    "buy_reason_review": operation.get("buy_reason") or "未记录买入理由。",
                    "hold_reason_review": operation.get("hold_reason") or "未记录持股理由。",
                    "sell_reason_review": operation.get("sell_reason") or "未记录卖出理由。",
                    "profit_loss_review": f"记录盈亏：{operation.get('profit_loss')}" if operation.get("profit_loss") is not None else "未记录盈亏。",
                    "lessons": operation.get("lessons") or "建议补充盘前计划、盘中执行和盘后偏差。",
                }
            )

        return self._ensure_shape(
            {
                "market_direction": f"大盘整体{direction}",
                "daily_hotspots": market.get("hot_sectors", []),
                "limit_up_count": limit_stats.get("limit_up_count", 0),
                "limit_down_count": limit_stats.get("limit_down_count", 0),
                "rising_count": breadth.get("rising_count", 0),
                "falling_count": breadth.get("falling_count", 0),
                "operation_reviews": operation_reviews,
                "lessons": "复盘重点应放在计划一致性、仓位控制、止损纪律和热点持续性验证。",
                "risk_notes": "AKShare 免费数据可能存在延迟或字段变动；AI总结仅供复盘记录，不构成投资建议。",
                "disclaimer": "本内容仅用于个人交易复盘和学习记录，不构成任何买卖建议。",
                "data_quality": {"warnings": []},
            }
        )

    def _ensure_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        data.setdefault("market_direction", "")
        data.setdefault("daily_hotspots", [])
        data.setdefault("limit_up_count", 0)
        data.setdefault("limit_down_count", 0)
        data.setdefault("rising_count", 0)
        data.setdefault("falling_count", 0)
        data.setdefault("operation_reviews", [])
        data.setdefault("lessons", "")
        data.setdefault("risk_notes", "")
        data.setdefault("disclaimer", "本内容仅用于复盘记录，不构成投资建议。")
        data.setdefault("data_quality", {"warnings": []})
        data["data_quality"].setdefault("warnings", [])
        return data

    def _post_process(self, data: dict[str, Any], market_snapshot: dict[str, Any]) -> dict[str, Any]:
        data = self._ensure_shape(data)
        breadth = market_snapshot.get("breadth", {})
        limit_stats = market_snapshot.get("limit_stats", {})
        data["limit_up_count"] = self._coalesce_int(data.get("limit_up_count"), limit_stats.get("limit_up_count"))
        data["limit_down_count"] = self._coalesce_int(data.get("limit_down_count"), limit_stats.get("limit_down_count"))
        data["rising_count"] = self._coalesce_int(data.get("rising_count"), breadth.get("rising_count"))
        data["falling_count"] = self._coalesce_int(data.get("falling_count"), breadth.get("falling_count"))

        market_direction = str(data.get("market_direction") or "").strip()
        if not self._contains_cjk(market_direction):
            data["market_direction"] = self._derive_market_direction(market_snapshot)
            data["data_quality"]["warnings"].append("AI返回的大盘判断不是中文，已按指数涨跌幅自动修正。")
        return data

    def _coalesce_int(self, preferred: Any, fallback: Any) -> int:
        for value in (preferred, fallback, 0):
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return 0

    def _contains_cjk(self, value: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in value)

    def _derive_market_direction(self, market_snapshot: dict[str, Any]) -> str:
        indexes = market_snapshot.get("indexes", [])
        main_index = next((item for item in indexes if item.get("name") == "上证指数"), indexes[0] if indexes else {})
        pct_change = main_index.get("pct_change")
        try:
            pct = float(pct_change)
        except (TypeError, ValueError):
            return "大盘方向不明，需结合指数和涨跌家数继续确认。"
        if pct > 0:
            return "大盘整体上涨，市场情绪偏强。"
        if pct < 0:
            return "大盘整体下跌，市场情绪偏弱。"
        return "大盘整体平盘震荡，市场分歧较明显。"

    def _operation_payload(self, operation: StockOperation) -> dict[str, Any]:
        return {
            "id": operation.id,
            "stock_code": operation.stock_code,
            "stock_name": operation.stock_name,
            "trade_date": operation.trade_date.isoformat(),
            "action": operation.action,
            "selection_reason": operation.selection_reason,
            "buy_reason": operation.buy_reason,
            "hold_reason": operation.hold_reason,
            "sell_reason": operation.sell_reason,
            "price": self._decimal_to_float(operation.price),
            "quantity": self._decimal_to_float(operation.quantity),
            "profit_loss": self._decimal_to_float(operation.profit_loss),
            "lessons": operation.lessons,
            "notes": operation.notes,
        }

    def _decimal_to_float(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None
