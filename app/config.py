from typing import List, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import validator

class Settings(BaseSettings):
  # General
  API_V1_STR: str = "/api/v1"
  PROJECT_NAME: str = "Market Movers Daily"
  ENVIRONMENT: str = "development"
  
  # Database
  POSTGRES_USER: str
  POSTGRES_PASSWORD: str
  POSTGRES_DB: str
  POSTGRES_HOST: str
  POSTGRES_PORT: str = "5432"
  
  # Constructed DATABASE_URL
  DATABASE_URL: Optional[str] = None
  
  @validator("DATABASE_URL", pre=True)
  def assemble_db_connections(cls, v, values):
    if isinstance(v, str):
      return v
    
    return f"postgresql://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_HOST')}:{values.get('POSTGRES_PORT')}/{values.get('POSTGRES_DB')}"
  
  # Models
  HF_TOKEN: Optional[str] = None
  MODEL_CACHE_DIR: str = "./model_cache"
  
  # API KEYS
  FINNHUB_API_KEY: str
  NEWS_API_KEY: Optional[str] = None
  
  # Email configuration
  SENDGRID_API_KEY: Optional[str] = None
  EMAIL_FROM: str = "marketmovers@yourdomain.com"
  EMAIL_RECIPIENTS: List[str] = []
  
  # Report Settings
  REPORT_TIME: str = "16:05"
  TIMEZONE: str = "America/New_York"
  TOP_MOVERS_COUNT: int = 5
  
  # Index Configuration
  INDEX_SYMBOL: str = "^GSPC"
  INDEX_NAME: str = "S&P 500"
  
  # News Settings
  NEWS_LOOKBACK_HOURS: int = 8
  MAX_HEADLINES_PER_STOCK: int = 20
  
  # Security
  SECRET_KEY: str
  
  @validator("FINNHUB_API_KEY", "NEWSAPI_KEY")
  def validate_api_keys(cls, v, field):
    if v and v.startswith("your_"):
      raise ValueError(f"{field.name} contains placeholder value. Please set a real API key.")
    return v
  
  @validator("EMAIL_RECIPIENTS", pre=True)
  def parse_email_recipients(cls, v):
    if isinstance(v, str):
      return [email.strip() for email in v.split(",")]
    return v
  
  class Config:
    env_file = ".env"
    env_file_encoding = "utf-8"
    case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
  try:
    return Settings()
  except Exception as e:
    print(f"Error loading settings: {e}")
    print("Make sure all required environment variables are set in .env file")
    raise