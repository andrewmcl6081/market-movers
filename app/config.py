import os
import json
import boto3
import logging
from typing import Optional
from functools import lru_cache
from botocore.exceptions import ClientError
from pydantic import field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

class Config(BaseSettings):
  # General
  ENVIRONMENT: str
  PROJECT_NAME: str = "Market Movers Daily"
  API_V1_STR: str = "/api/v1"
  
  TEST_MODE: bool = False
  TEST_STOCK_COUNT: int = 10
  
  # AWS / S3
  AWS_PROFILE: Optional[str] = None
  AWS_REGION: str
  S3_BUCKET: str
  
  # Database
  DATABASE_URL: str
  
  # Models
  HF_TOKEN: Optional[str] = None
  
  # API KEYS
  FINNHUB_API_KEY: str
  NEWS_API_KEY: str
  
  # Email configuration
  SENDGRID_API_KEY: str
  EMAIL_FROM: str
  ADMIN_EMAIL: str
  
  # Report Settings
  REPORT_TIME: str
  TIMEZONE: str
  TOP_MOVERS_COUNT: int
  
  # News Settings
  NEWS_LOOKBACK_HOURS: int
  MAX_HEADLINES_PER_STOCK: int
  
  @field_validator("FINNHUB_API_KEY", "NEWS_API_KEY")
  def validate_api_keys(cls, v: str, info: ValidationInfo) -> str:
    if v and v.startswith("your_"):
      raise ValueError(f"{info.field_name} contains placeholder value. Please set a real API key.")
    return v
  
  model_config = SettingsConfigDict(
    env_file_encoding="utf-8",
    case_sensitive=True,
    extra="ignore"
  )

@lru_cache()
def get_config() -> Config:
  env = os.getenv("ENVIRONMENT")
  
  if env == "production":
    logger.info("Loading config from AWS Secrets Manager")
    try:
      region_name = os.getenv("AWS_REGION")
      rds_secret_name = os.getenv("RDS_SECRET_NAME")
      app_secret_name = os.getenv("APP_CONFIG_SECRET_NAME")
      
      if not rds_secret_name or not app_secret_name:
        raise RuntimeError("Missing RDS_SECRET_NAME or APP_CONFIG_SECRET_NAME environment variables")
      
      session = boto3.session.Session()
      client = session.client(service_name="secretsmanager", region_name=region_name)
      
      def fetch_secret(name):
        try:
          response = client.get_secret_value(SecretId=name)
          return json.loads(response["SecretString"])
        except ClientError as e:
          logger.error(f"Failed to retrieve secret {name}: {e}")
          raise
      
      
      rds_secret = fetch_secret(rds_secret_name)
      app_secret = fetch_secret(app_secret_name)
      
      # Set environment variables from app config
      for key, value in app_secret.items():
        os.environ[key] = str(value)
      
      os.environ["DATABASE_URL"] = (
        f"postgresql://{rds_secret['username']}:{rds_secret['password']}"
        f"@{app_secret['POSTGRES_HOST']}:{app_secret['POSTGRES_PORT']}/{app_secret['POSTGRES_DB']}"
      )
      
      return Config()
    except Exception as e:
      logger.error(f"Failed to load production secrets: {e}")
      raise
  
  # Dev environment: use .env or compose
  return Config()