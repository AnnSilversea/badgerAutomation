"""
Retry utilities for Drake automation
"""
import time
from DrakeAutomation.ui.logger import setup_logger

log = setup_logger("utils.retry")


def retry_action(func, max_retries=3, delay=0.5, desc="action"):
    """
    Retry an action with exponential backoff.
    
    Args:
        func: Callable to execute
        max_retries: Maximum number of attempts
        delay: Initial delay between retries (seconds)
        desc: Description for logging
        
    Returns:
        Result of func() if successful
        
    Raises:
        Exception: If all retries exhausted
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            log.info(f"Attempt {attempt + 1}/{max_retries}: {desc}")
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt)  # Exponential backoff
                log.warning(f"Failed attempt {attempt + 1}: {e}")
                log.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                log.error(f"All {max_retries} attempts failed: {e}")
    
    raise last_error
