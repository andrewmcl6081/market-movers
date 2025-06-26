from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import logging
from typing import Generator

from config import get_settings
from db.base import Base

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_engine(
  settings.DATABASE_URL,
  pool_pre_ping=True,
  echo=False
)

# Create SessionLocal Class
SessionLocal = sessionmaker(
  autocommit=False,
  autoflush=False,
  bind=engine
)

def get_db() -> Generator[Session, None, None]:
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()

def init_db():
  try:
    from db import models
    
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
  except Exception as e:
    logger.error(f"Error creating database tables: {e}")
    raise

def test_connection():
  try:
    with engine.connect() as conn:
      result = conn.execute("SELECT 1")
      logger.info("Database connection successful")
      return True
  except Exception as e:
    logger.error(f"Database connection failed: {e}")
    return False