"""
Fiber 测试框架智能等待工具模块

提供统一的等待接口，支持条件等待、指数退避、超时控制等功能。
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Callable, TypeVar, Optional, Any, List, Union

from framework.constants import Timeout

T = TypeVar('T')
logger = logging.getLogger(__name__)


@dataclass
class WaitConfig:
    """等待配置"""
    
    timeout: int = Timeout.MEDIUM
    """超时时间（秒）"""
    
    interval: float = Timeout.POLL_INTERVAL
    """轮询间隔（秒）"""
    
    exponential_backoff: bool = False
    """是否启用指数退避"""
    
    max_interval: float = 10.0
    """最大轮询间隔（秒），仅在指数退避时有效"""
    
    backoff_factor: float = 2.0
    """退避因子，仅在指数退避时有效"""
    
    raise_on_timeout: bool = True
    """超时时是否抛出异常"""
    
    log_progress: bool = False
    """是否记录等待进度日志"""


class WaitTimeoutError(TimeoutError):
    """等待超时异常"""
    
    def __init__(self, message: str, elapsed: float, last_value: Any = None):
        super().__init__(message)
        self.elapsed = elapsed
        self.last_value = last_value


class Waiter:
    """统一的等待工具类"""
    
    @staticmethod
    def wait_until(
        condition: Callable[[], bool],
        config: Optional[WaitConfig] = None,
        error_message: str = "Condition not met within timeout"
    ) -> bool:
        """
        等待条件满足
        
        Args:
            condition: 条件函数，返回 True 表示条件满足
            config: 等待配置
            error_message: 超时错误消息
            
        Returns:
            条件是否满足
            
        Raises:
            WaitTimeoutError: 超时时抛出（如果配置了 raise_on_timeout）
            
        Example:
            >>> Waiter.wait_until(
            ...     lambda: channel.state == "CHANNEL_READY",
            ...     WaitConfig(timeout=120)
            ... )
        """
        if config is None:
            config = WaitConfig()
            
        start_time = time.time()
        current_interval = config.interval
        
        while True:
            try:
                if condition():
                    return True
            except Exception as e:
                if config.log_progress:
                    logger.debug(f"Condition check raised exception: {e}")
            
            elapsed = time.time() - start_time
            
            if elapsed >= config.timeout:
                if config.raise_on_timeout:
                    raise WaitTimeoutError(
                        f"{error_message} (timeout: {config.timeout}s, elapsed: {elapsed:.1f}s)",
                        elapsed
                    )
                return False
            
            if config.log_progress:
                logger.debug(f"Waiting... elapsed: {elapsed:.1f}s / {config.timeout}s")
            
            time.sleep(current_interval)
            
            # 指数退避
            if config.exponential_backoff:
                current_interval = min(
                    current_interval * config.backoff_factor,
                    config.max_interval
                )
    
    @staticmethod
    def wait_for_value(
        getter: Callable[[], T],
        expected: Union[T, List[T]],
        config: Optional[WaitConfig] = None,
        error_message: str = "Value did not reach expected"
    ) -> T:
        """
        等待值达到期望
        
        Args:
            getter: 获取当前值的函数
            expected: 期望的值，可以是单个值或值列表
            config: 等待配置
            error_message: 超时错误消息
            
        Returns:
            最终获取到的值
            
        Raises:
            WaitTimeoutError: 超时时抛出
            
        Example:
            >>> Waiter.wait_for_value(
            ...     lambda: payment.status,
            ...     ["Success", "Failed"],
            ...     WaitConfig(timeout=360)
            ... )
        """
        if config is None:
            config = WaitConfig()
            
        start_time = time.time()
        current_interval = config.interval
        last_value = None
        expected_list = expected if isinstance(expected, list) else [expected]
        
        while True:
            try:
                last_value = getter()
                if last_value in expected_list:
                    return last_value
            except Exception as e:
                if config.log_progress:
                    logger.debug(f"Getter raised exception: {e}")
            
            elapsed = time.time() - start_time
            
            if elapsed >= config.timeout:
                if config.raise_on_timeout:
                    raise WaitTimeoutError(
                        f"{error_message}: expected {expected}, got {last_value} "
                        f"(timeout: {config.timeout}s, elapsed: {elapsed:.1f}s)",
                        elapsed,
                        last_value
                    )
                return last_value
            
            if config.log_progress:
                logger.debug(
                    f"Waiting for value... current: {last_value}, "
                    f"expected: {expected}, elapsed: {elapsed:.1f}s"
                )
            
            time.sleep(current_interval)
            
            if config.exponential_backoff:
                current_interval = min(
                    current_interval * config.backoff_factor,
                    config.max_interval
                )
    
    @staticmethod
    def wait_for_predicate(
        getter: Callable[[], T],
        predicate: Callable[[T], bool],
        config: Optional[WaitConfig] = None,
        error_message: str = "Predicate not satisfied"
    ) -> T:
        """
        等待谓词条件满足
        
        Args:
            getter: 获取当前值的函数
            predicate: 谓词函数，接收当前值，返回是否满足条件
            config: 等待配置
            error_message: 超时错误消息
            
        Returns:
            满足条件时的值
            
        Example:
            >>> Waiter.wait_for_predicate(
            ...     lambda: client.list_channels({}),
            ...     lambda channels: len(channels['channels']) > 0
            ... )
        """
        if config is None:
            config = WaitConfig()
            
        start_time = time.time()
        current_interval = config.interval
        last_value = None
        
        while True:
            try:
                last_value = getter()
                if predicate(last_value):
                    return last_value
            except Exception as e:
                if config.log_progress:
                    logger.debug(f"Check raised exception: {e}")
            
            elapsed = time.time() - start_time
            
            if elapsed >= config.timeout:
                if config.raise_on_timeout:
                    raise WaitTimeoutError(
                        f"{error_message} (timeout: {config.timeout}s, elapsed: {elapsed:.1f}s)",
                        elapsed,
                        last_value
                    )
                return last_value
            
            if config.log_progress:
                logger.debug(f"Waiting for predicate... elapsed: {elapsed:.1f}s")
            
            time.sleep(current_interval)
            
            if config.exponential_backoff:
                current_interval = min(
                    current_interval * config.backoff_factor,
                    config.max_interval
                )
    
    @staticmethod
    def retry(
        func: Callable[[], T],
        max_retries: int = 5,
        retry_interval: float = 1.0,
        exceptions: tuple = (Exception,),
        on_retry: Optional[Callable[[Exception, int], None]] = None
    ) -> T:
        """
        重试执行函数
        
        Args:
            func: 要执行的函数
            max_retries: 最大重试次数
            retry_interval: 重试间隔（秒）
            exceptions: 需要重试的异常类型
            on_retry: 重试时的回调函数，接收异常和重试次数
            
        Returns:
            函数返回值
            
        Raises:
            最后一次尝试的异常
            
        Example:
            >>> Waiter.retry(
            ...     lambda: client.send_payment(params),
            ...     max_retries=3,
            ...     retry_interval=2.0
            ... )
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    if on_retry:
                        on_retry(e, attempt + 1)
                    elif logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            f"Retry {attempt + 1}/{max_retries} after error: {e}"
                        )
                    time.sleep(retry_interval)
        
        raise last_exception


# 便捷函数
def wait_until(
    condition: Callable[[], bool],
    timeout: int = Timeout.MEDIUM,
    interval: float = Timeout.POLL_INTERVAL,
    error_message: str = "Condition not met"
) -> bool:
    """
    等待条件满足（便捷函数）
    
    Args:
        condition: 条件函数
        timeout: 超时时间
        interval: 轮询间隔
        error_message: 错误消息
    """
    return Waiter.wait_until(
        condition,
        WaitConfig(timeout=timeout, interval=interval),
        error_message
    )


def wait_for_value(
    getter: Callable[[], T],
    expected: Union[T, List[T]],
    timeout: int = Timeout.MEDIUM,
    interval: float = Timeout.POLL_INTERVAL,
    error_message: str = "Value not reached"
) -> T:
    """
    等待值达到期望（便捷函数）
    
    Args:
        getter: 获取值的函数
        expected: 期望的值
        timeout: 超时时间
        interval: 轮询间隔
        error_message: 错误消息
    """
    return Waiter.wait_for_value(
        getter,
        expected,
        WaitConfig(timeout=timeout, interval=interval),
        error_message
    )


def retry(
    func: Callable[[], T],
    max_retries: int = 5,
    retry_interval: float = 1.0
) -> T:
    """
    重试执行函数（便捷函数）
    """
    return Waiter.retry(func, max_retries, retry_interval)


__all__ = [
    'WaitConfig',
    'WaitTimeoutError',
    'Waiter',
    'wait_until',
    'wait_for_value',
    'retry',
]
