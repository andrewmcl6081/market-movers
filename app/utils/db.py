from typing import Callable, TypeVar
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
import logging
import os

T = TypeVar("T")

logger = logging.getLogger(__name__)

def db_safe_execute(db: Session, operation: Callable[[], T], commit: bool = True) -> T:
  """
  Wraps DB operation in try/except with rollback and safe HTTP response.
  Pass `commit=False` to skip db.commit() (for read-only queries).
  Returns detailed error if ENVIRONMENT is 'development' or 'test'.
  """
  
  try:
    result = operation()
    if commit:
      db.commit()
    return result
  except SQLAlchemyError as e:
    db.rollback()
    logger.error(f"Database error: {e}")
    
    # Use safe message in production, full error in dev/test
    environment = os.getenv("ENVIRONMENT", "production")
    show_error = environment in ("development", "test")
    
    raise HTTPException(status_code=500, detail=(str(e) if show_error else "A database error occured. Please try again later."))