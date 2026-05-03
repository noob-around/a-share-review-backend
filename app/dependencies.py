from app.services.deepseek import DeepSeekSummarizer
from app.services.market_data import AKShareMarketDataService


def get_market_data_service() -> AKShareMarketDataService:
    return AKShareMarketDataService()


def get_summarizer() -> DeepSeekSummarizer:
    return DeepSeekSummarizer()
