import time
from typing import List, Callable, Any
from loguru import logger

class FailureRecovery:
    """Intelligently executes calls with fallback mechanisms and exponential retry intervals."""

    def execute_with_fallback(self, primary_fn: Callable[[], Any], fallbacks: List[Callable[[], Any]], max_retries: int = 2) -> Any:
        """
        Executes a primary function. If it raises an exception, retries up to max_retries.
        If all retries fail, iterates through the list of fallback functions.
        """
        # 1. Try Primary with retries
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying primary function (attempt {attempt}/{max_retries})...")
                    time.sleep(attempt * 0.5)  # Backoff
                return primary_fn()
            except Exception as e:
                logger.warning(f"Primary execution attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    logger.warning("All primary retries exhausted. Moving to fallback pipeline.")

        # 2. Iterate through fallbacks
        for idx, fallback_fn in enumerate(fallbacks):
            try:
                logger.info(f"Executing fallback pipeline step {idx+1}/{len(fallbacks)}: '{fallback_fn.__name__}'")
                return fallback_fn()
            except Exception as fe:
                logger.warning(f"Fallback step {idx+1} '{fallback_fn.__name__}' failed: {fe}")

        raise RuntimeError("Primary execution and all fallback pipeline routes failed.")
