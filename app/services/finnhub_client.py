import finnhub
import logging
from functools import lru_cache
from app.config import get_config
from app.utils.rate_limiter import rate_limited

logger = logging.getLogger(__name__)

class FinnhubClient:
  def __init__(self, api_key: str):
    self._client = finnhub.Client(api_key=api_key)
    logger.info("Initialized rate-limited Finnhub client")
  
  @rate_limited
  def quote(self, symbol: str):
    return self._client.quote(symbol)
  
  @rate_limited
  def company_news(self, symbol: str, _from: str, to: str):
    return self._client.company_news(symbol, _from, to)
  
  @rate_limited
  def market_status(self, exchange: str):
    return self._client.market_status(exchange)
  
  @rate_limited
  def company_profile2(self, symbol: str):
    return self._client.company_profile2(symbol=symbol)

@lru_cache()
def get_finnhub_client() -> FinnhubClient:
  config = get_config()
  return FinnhubClient(api_key=config.FINNHUB_API_KEY)