"""Utilities for handling retries and error recovery."""
from typing import TypeVar, Callable, Optional, List, Any
from functools import wraps
import time
from exceptions import DatabaseManagerError
from utils import RED, YELLOW, BLUE, NC, ICONS, SpinnerProgress

T = TypeVar('T')

def with_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """Decorator for retrying operations with exponential backoff."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            current_delay = delay
            
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < retries:
                        print(f"{YELLOW}{ICONS['warning']} Attempt {attempt + 1} failed, "
                              f"retrying in {current_delay:.1f} seconds...{NC}")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        print(f"{RED}{ICONS['times']} All retry attempts failed{NC}")
                        if last_exception:
                            raise DatabaseManagerError(
                                f"Operation failed after {retries} retries"
                            ) from last_exception
                        raise
            
            # This should never be reached due to the raise in the loop
            assert False, "Unreachable code"
            
        return wrapper
    return decorator


class RetryContext:
    """Context manager for retry operations with progress tracking."""
    
    def __init__(
        self,
        operation: str,
        retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,)
    ):
        self.operation = operation
        self.retries = retries
        self.delay = delay
        self.backoff = backoff
        self.exceptions = exceptions
        self.progress: Optional[SpinnerProgress] = None
        self.attempt = 0
        self.successful = False
        
    def __enter__(self) -> 'RetryContext':
        if self.progress:
            self.progress.stop(False)
        self.progress = SpinnerProgress(f"{self.operation} (Attempt {self.attempt + 1})")
        self.progress.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if exc_type is None:
                self.successful = True
                self.progress.stop(True)
                return True

            self.progress.stop(False)
            
            if exc_type in self.exceptions and self.attempt < self.retries:
                self.attempt += 1
                time.sleep(self.delay)
                self.delay *= self.backoff
                self._within_context = False
                raise exc_val
        finally:
            self.progress = None
            
        return False  # Don't suppress the final exception


def collect_errors(operations: List[Callable[[], Any]]) -> List[Exception]:
    """Execute multiple operations and collect errors."""
    errors: List[Exception] = []
    
    for operation in operations:
        try:
            operation()
        except Exception as e:
            errors.append(e)
            print(f"{YELLOW}{ICONS['warning']} Operation failed: {str(e)}{NC}")
            
    return errors