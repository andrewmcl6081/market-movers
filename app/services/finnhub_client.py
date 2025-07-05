import finnhub
from app.config import get_config
from functools import lru_cache

@lru_cache()
def get_finnhub_client() -> finnhub.Client:
  config = get_config()
  return finnhub.Client(api_key=config.FINNHUB_API_KEY)