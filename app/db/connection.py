from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from functools import lru_cache
from typing import Generator, Optional
import logging

from app.config import get_config
from app.db.base import Base

logger = logging.getLogger(__name__)

@lru_cache()
def get_engine():
  config = get_config()
  return create_engine(config.DATABASE_URL, pool_pre_ping=True, echo=(config.ENVIRONMENT != "production"))

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()

def init_db():
  Base.metadata.create_all(bind=engine)
  logger.info("Database tables created successfully")

def test_connection(engine: Optional[Engine] = None) -> bool:
  try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Database connection successful")
    return True
  except Exception as e:
    logger.error(f"Database connection failed: {e}")
    return False