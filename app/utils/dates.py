import pytz
from datetime import datetime
from app.config import get_config

def get_market_date():
  config = get_config()
  return datetime.now(pytz.timezone(config.TIMEZONE)).date()