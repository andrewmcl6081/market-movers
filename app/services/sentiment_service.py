import torch
import logging
from app.config import get_config
from functools import lru_cache
from transformers import pipeline

logger = logging.getLogger(__name__)

class SentimentModel:
  def __init__(self):
    self.pipeline = None
    self._initialized = False
    self._error = None
    self._model_name = "ProsusAI/finbert"
  
  def initialize(self):
    if self._initialized:
      return
    
    try:
      logger.info(f"Loading {self._model_name} model...")
      device = 0 if torch.cuda.is_available() else -1
      
      self.pipeline = pipeline(
        "sentiment-analysis",
        model=self._model_name,
        device=device
      )
      
      # Warm up test
      test_result = self.pipeline("Test", truncation=True, max_length=512)
      logger.info(f"Model test result: {test_result}")
      
      self._initialized = True
      self._error = None
      logger.info(f"{self._model_name} loaded successfully")
    
    except Exception as e:
      self._error = str(e)
      logger.error(f"Error loading {self._model_name}: {str(e)}")
      raise
  
  def get_status(self) -> dict:
    return {
      "initialized": self._initialized,
      "model_name": self._model_name,
      "error": self._error
    }

@lru_cache()
def get_sentiment_model():
  model = SentimentModel()
  model.initialize()
  
  return model