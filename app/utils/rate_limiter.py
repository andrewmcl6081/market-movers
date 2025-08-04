import time
import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

class RateLimiter:
  def __init__(self, calls_per_minute: int = 55):
    self.calls_per_minute = calls_per_minute
    self.rate_limit_seconds = 60.0 / calls_per_minute
    self.last_call_time = 0
    self.call_count = 0
    self.total_wait_time = 0
    
    logger.info(f"Rate limiter initialized: {calls_per_minute} calls/minute ({self.rate_limit_seconds:.3f}s between calls)")
    
  def rate_limited_request(self, func: Callable) -> Callable:
    """Decorator to rate limit function calls"""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
      elapsed = time.time() - self.last_call_time
      
      if elapsed < self.rate_limit_seconds:
        wait_time = self.rate_limit_seconds - elapsed
        self.total_wait_time += wait_time
        self.call_count += 1
        
        logger.debug(
          f"Rate limit wait: {wait_time:.3f}s | "
          f"Call #{self.call_count} | "
          f"Total wait: {self.total_wait_time:.1f}s"
        )
        
        time.sleep(wait_time)
      else:
        self.call_count += 1
        logger.debug(f"No wait needed | Call #{self.call_count} | Elapsed: {elapsed:.3f}s")
      
      # Log every 10th call or when significant wait time
      if self.call_count % 10 == 0:
        avg_wait = self.total_wait_time / self.call_count if self.call_count > 0 else 0
        logger.info(
          f"Rate limiter stats - Calls: {self.call_count}, "
          f"Total wait: {self.total_wait_time:.1f}s, "
          f"Avg wait: {avg_wait:.3f}s"
        )
      
      start_time = time.time()
      
      try:
        func_name = f"{func.__module__}.{func.__name__}" if hasattr(func, '__module__') else func.__name__
        logger.debug(f"Calling: {func_name}")
        
        result = func(*args, **kwargs)
        
        # Log successful completion
        api_time = time.time() - start_time
        logger.debug(f"API call completed in {api_time:.3f}s")
        
        self.last_call_time = time.time()
        return result
      
      except Exception as e:
        logger.error(f"API call failed: {type(e).__name__}: {str(e)}")
        self.last_call_time = time.time()
        raise
    
    return wrapper
  
  def get_stats(self) -> dict:
    return {
      "total_calls": self.call_count,
      "total_wait_time": round(self.total_wait_time, 2),
      "average_wait_time": round(self.total_wait_time / self.call_count, 3) if self.call_count > 0 else 0,
      "calls_per_minute": self.calls_per_minute,
      "seconds_between_calls": round(self.rate_limit_seconds, 3)
    }
  
  def reset_stats(self):
    self.call_count = 0
    self.total_wait_time = 0
    logger.info("Rate limiter statistics reset")

finnhub_limiter = RateLimiter(calls_per_minute=30)
rate_limited = finnhub_limiter.rate_limited_request