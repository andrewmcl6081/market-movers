import os
from typing import List, Optional
from functools import lru_cache
from pydantic import Field, field_validator, model_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
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
  
  @model_validator(mode="before")
  @classmethod
  def assemble_db_connections(cls, values):
    if values.get("DATABASE_URL"):
      return values
    
    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORT")
    if all(values.get(k) for k in required):
      values["DATABASE_URL"] = (
        f"postgresql://{values['POSTGRES_USER']}:{values['POSTGRES_PASSWORD']}@"
        f"{values['POSTGRES_HOST']}:{values['POSTGRES_PORT']}/{values['POSTGRES_DB']}"
      )
    return values
  
  # Models
  HF_TOKEN: Optional[str] = None
  MODEL_CACHE_DIR: str = "./model_cache"
  
  # API KEYS
  FINNHUB_API_KEY: str
  NEWS_API_KEY: str
  MK_API_KEY: str
  
  # Email configuration
  SENDGRID_API_KEY: str
  EMAIL_FROM: str
  EMAIL_RECIPIENTS: str
  
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
  
  @field_validator("FINNHUB_API_KEY", "NEWS_API_KEY")
  @classmethod
  def validate_api_keys(cls, v: str, info: ValidationInfo) -> str:
    if v and v.startswith("your_"):
      raise ValueError(f"{info.field_name} contains placeholder value. Please set a real API key.")
    return v
  
  @field_validator("EMAIL_RECIPIENTS", mode="before")
  @classmethod
  def parse_email_recipients(cls, v, info: ValidationInfo):
    if isinstance(v, str):
      return [email.strip() for email in v.split(",")]
    return v
  
  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=True
  )

@lru_cache()
def get_config() -> Config:
  env = os.getenv("ENVIRONMENT", "development")
  
  try:
    if env == "test":
      return Config(_env_file=".env.test")
    return Config()
  except Exception as e:
    print(f"Error loading settings: {e}")
    print("Make sure all required environment variables are set in .env file")
    raise