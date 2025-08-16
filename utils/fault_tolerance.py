import time
import random
import threading
import functools
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, Future
import logging


class FaultToleranceStrategy(Enum):
    """容错策略"""
    FAIL_FAST = "fail_fast"           # 快速失败
    RETRY = "retry"                   # 重试
    CIRCUIT_BREAKER = "circuit_breaker"  # 断路器
    FALLBACK = "fallback"             # 回退
    BULKHEAD = "bulkhead"             # 舱壁隔离


class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"       # 关闭（正常）
    OPEN = "open"          # 开启（故障）
    HALF_OPEN = "half_open"  # 半开（测试）


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    backoff_strategy: str = "exponential"  # "exponential", "linear", "fixed"


@dataclass
class CircuitBreakerConfig:
    """断路器配置"""
    failure_threshold: int = 5       # 失败阈值
    timeout: float = 60.0           # 超时时间（秒）
    success_threshold: int = 2       # 成功阈值（半开状态）
    monitor_window: float = 300.0    # 监控窗口（秒）


@dataclass
class BulkheadConfig:
    """舱壁隔离配置"""
    max_concurrent_calls: int = 10
    queue_size: int = 100
    timeout: float = 30.0


@dataclass
class FaultToleranceConfig:
    """容错配置"""
    strategy: FaultToleranceStrategy
    retry_config: Optional[RetryConfig] = None
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    bulkhead_config: Optional[BulkheadConfig] = None
    fallback_function: Optional[Callable] = None
    enabled: bool = True


class RetryManager:
    """重试管理器"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.logger = logging.getLogger('RetryManager')
    
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """执行带重试的函数"""
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                self.logger.debug(f"尝试执行 {func.__name__}，第 {attempt + 1} 次")
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(f"函数 {func.__name__} 在第 {attempt + 1} 次尝试后成功")
                
                return result
                
            except Exception as e:
                last_exception = e
                self.logger.warning(f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {str(e)}")
                
                # 如果不是最后一次尝试，则等待后重试
                if attempt < self.config.max_attempts - 1:
                    delay = self._calculate_delay(attempt)
                    self.logger.debug(f"等待 {delay:.2f} 秒后重试")
                    time.sleep(delay)
        
        # 所有重试都失败了
        self.logger.error(f"函数 {func.__name__} 所有重试都失败，最后错误: {str(last_exception)}")
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if self.config.backoff_strategy == "exponential":
            delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        elif self.config.backoff_strategy == "linear":
            delay = self.config.base_delay * (attempt + 1)
        else:  # fixed
            delay = self.config.base_delay
        
        # 限制最大延迟
        delay = min(delay, self.config.max_delay)
        
        # 添加抖动
        if self.config.jitter:
            jitter_factor = random.uniform(0.5, 1.5)
            delay *= jitter_factor
        
        return delay


class CircuitBreaker:
    """断路器"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.call_history: List[Dict] = []
        self._lock = threading.RLock()
        self.logger = logging.getLogger('CircuitBreaker')
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """通过断路器调用函数"""
        with self._lock:
            current_time = time.time()
            
            # 清理过期的调用历史
            self._cleanup_call_history(current_time)
            
            # 检查断路器状态
            if self.state == CircuitState.OPEN:
                if current_time - self.last_failure_time > self.config.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    self.logger.info("断路器切换到半开状态")
                else:
                    self.logger.warning("断路器开启，拒绝调用")
                    raise CircuitBreakerOpenError("断路器开启，服务不可用")
            
            # 尝试调用函数
            try:
                result = func(*args, **kwargs)
                self._record_success(current_time)
                return result
                
            except Exception as e:
                self._record_failure(current_time)
                raise e
    
    def _record_success(self, timestamp: float):
        """记录成功调用"""
        self.call_history.append({"timestamp": timestamp, "success": True})
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.logger.info("断路器关闭，服务恢复正常")
        elif self.state == CircuitState.CLOSED:
            # 在正常状态下的成功可以减少失败计数
            self.failure_count = max(0, self.failure_count - 1)
    
    def _record_failure(self, timestamp: float):
        """记录失败调用"""
        self.call_history.append({"timestamp": timestamp, "success": False})
        self.failure_count += 1
        self.last_failure_time = timestamp
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                self.logger.warning(f"断路器开启，失败次数达到阈值: {self.failure_count}")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.logger.warning("半开状态下调用失败，断路器重新开启")
    
    def _cleanup_call_history(self, current_time: float):
        """清理过期的调用历史"""
        cutoff_time = current_time - self.config.monitor_window
        self.call_history = [call for call in self.call_history if call["timestamp"] > cutoff_time]
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取断路器指标"""
        with self._lock:
            current_time = time.time()
            self._cleanup_call_history(current_time)
            
            total_calls = len(self.call_history)
            successful_calls = sum(1 for call in self.call_history if call["success"])
            failed_calls = total_calls - successful_calls
            
            return {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "total_calls_in_window": total_calls,
                "successful_calls_in_window": successful_calls,
                "failed_calls_in_window": failed_calls,
                "success_rate": successful_calls / total_calls if total_calls > 0 else 0,
                "time_since_last_failure": current_time - self.last_failure_time if self.last_failure_time > 0 else None
            }


class BulkheadIsolation:
    """舱壁隔离"""
    
    def __init__(self, config: BulkheadConfig):
        self.config = config
        self.executor = ThreadPoolExecutor(
            max_workers=config.max_concurrent_calls,
            thread_name_prefix="Bulkhead"
        )
        self.active_calls = 0
        self.rejected_calls = 0
        self._lock = threading.RLock()
        self.logger = logging.getLogger('BulkheadIsolation')
    
    def submit(self, func: Callable, *args, **kwargs) -> Future:
        """提交任务到舱壁隔离的线程池"""
        with self._lock:
            if self.active_calls >= self.config.max_concurrent_calls:
                self.rejected_calls += 1
                self.logger.warning(f"舱壁隔离拒绝调用，当前活跃调用数: {self.active_calls}")
                raise BulkheadIsolationError("舱壁隔离：并发调用数量超限")
            
            self.active_calls += 1
        
        def wrapped_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            finally:
                with self._lock:
                    self.active_calls -= 1
        
        try:
            future = self.executor.submit(wrapped_func, *args, **kwargs)
            self.logger.debug(f"任务提交到舱壁隔离线程池，当前活跃调用数: {self.active_calls}")
            return future
        except Exception as e:
            with self._lock:
                self.active_calls -= 1
            raise e
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """同步执行任务"""
        future = self.submit(func, *args, **kwargs)
        return future.result(timeout=self.config.timeout)
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取舱壁隔离指标"""
        with self._lock:
            return {
                "active_calls": self.active_calls,
                "rejected_calls": self.rejected_calls,
                "max_concurrent_calls": self.config.max_concurrent_calls,
                "utilization": self.active_calls / self.config.max_concurrent_calls
            }
    
    def shutdown(self):
        """关闭线程池"""
        self.executor.shutdown(wait=True)


class FaultToleranceManager:
    """容错管理器"""
    
    def __init__(self):
        self.retry_managers: Dict[str, RetryManager] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.bulkhead_isolations: Dict[str, BulkheadIsolation] = {}
        self.configurations: Dict[str, FaultToleranceConfig] = {}
        self.logger = logging.getLogger('FaultToleranceManager')
    
    def register_service(self, service_name: str, config: FaultToleranceConfig):
        """注册服务的容错配置"""
        self.configurations[service_name] = config
        
        if config.strategy == FaultToleranceStrategy.RETRY and config.retry_config:
            self.retry_managers[service_name] = RetryManager(config.retry_config)
        
        if config.strategy == FaultToleranceStrategy.CIRCUIT_BREAKER and config.circuit_breaker_config:
            self.circuit_breakers[service_name] = CircuitBreaker(config.circuit_breaker_config)
        
        if config.strategy == FaultToleranceStrategy.BULKHEAD and config.bulkhead_config:
            self.bulkhead_isolations[service_name] = BulkheadIsolation(config.bulkhead_config)
        
        self.logger.info(f"已注册服务 '{service_name}' 的容错配置: {config.strategy.value}")
    
    def execute_with_fault_tolerance(self, 
                                   service_name: str,
                                   func: Callable,
                                   *args, **kwargs) -> Any:
        """使用容错机制执行函数"""
        if service_name not in self.configurations:
            self.logger.warning(f"服务 '{service_name}' 未注册容错配置，直接执行")
            return func(*args, **kwargs)
        
        config = self.configurations[service_name]
        
        if not config.enabled:
            self.logger.debug(f"服务 '{service_name}' 容错机制已禁用，直接执行")
            return func(*args, **kwargs)
        
        try:
            if config.strategy == FaultToleranceStrategy.FAIL_FAST:
                return func(*args, **kwargs)
            
            elif config.strategy == FaultToleranceStrategy.RETRY:
                retry_manager = self.retry_managers[service_name]
                return retry_manager.execute_with_retry(func, *args, **kwargs)
            
            elif config.strategy == FaultToleranceStrategy.CIRCUIT_BREAKER:
                circuit_breaker = self.circuit_breakers[service_name]
                return circuit_breaker.call(func, *args, **kwargs)
            
            elif config.strategy == FaultToleranceStrategy.BULKHEAD:
                bulkhead = self.bulkhead_isolations[service_name]
                return bulkhead.execute(func, *args, **kwargs)
            
            elif config.strategy == FaultToleranceStrategy.FALLBACK:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if config.fallback_function:
                        self.logger.info(f"主功能失败，执行回退功能: {str(e)}")
                        return config.fallback_function(*args, **kwargs)
                    else:
                        raise e
            
            else:
                self.logger.error(f"未知的容错策略: {config.strategy}")
                return func(*args, **kwargs)
                
        except Exception as e:
            self.logger.error(f"服务 '{service_name}' 容错执行失败: {str(e)}")
            raise e
    
    def get_service_metrics(self, service_name: str) -> Dict[str, Any]:
        """获取服务的容错指标"""
        if service_name not in self.configurations:
            return {"error": "Service not registered"}
        
        config = self.configurations[service_name]
        metrics = {
            "service_name": service_name,
            "strategy": config.strategy.value,
            "enabled": config.enabled
        }
        
        if service_name in self.circuit_breakers:
            metrics["circuit_breaker"] = self.circuit_breakers[service_name].get_metrics()
        
        if service_name in self.bulkhead_isolations:
            metrics["bulkhead"] = self.bulkhead_isolations[service_name].get_metrics()
        
        return metrics
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有服务的容错指标"""
        return {
            service_name: self.get_service_metrics(service_name)
            for service_name in self.configurations.keys()
        }
    
    def enable_service(self, service_name: str):
        """启用服务的容错机制"""
        if service_name in self.configurations:
            self.configurations[service_name].enabled = True
            self.logger.info(f"已启用服务 '{service_name}' 的容错机制")
    
    def disable_service(self, service_name: str):
        """禁用服务的容错机制"""
        if service_name in self.configurations:
            self.configurations[service_name].enabled = False
            self.logger.info(f"已禁用服务 '{service_name}' 的容错机制")
    
    def shutdown(self):
        """关闭所有资源"""
        for bulkhead in self.bulkhead_isolations.values():
            bulkhead.shutdown()
        
        self.logger.info("容错管理器已关闭")


# 自定义异常
class FaultToleranceError(Exception):
    """容错机制基础异常"""
    pass


class CircuitBreakerOpenError(FaultToleranceError):
    """断路器开启异常"""
    pass


class BulkheadIsolationError(FaultToleranceError):
    """舱壁隔离异常"""
    pass


class RetryExhaustedError(FaultToleranceError):
    """重试耗尽异常"""
    pass


# 装饰器
def fault_tolerant(service_name: str, 
                  strategy: FaultToleranceStrategy = FaultToleranceStrategy.RETRY,
                  **config_kwargs):
    """容错装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 获取或创建容错管理器
            manager = get_fault_tolerance_manager()
            
            # 如果服务未注册，自动注册默认配置
            if service_name not in manager.configurations:
                config = create_default_config(strategy, **config_kwargs)
                manager.register_service(service_name, config)
            
            return manager.execute_with_fault_tolerance(service_name, func, *args, **kwargs)
        
        return wrapper
    return decorator


def create_default_config(strategy: FaultToleranceStrategy, **kwargs) -> FaultToleranceConfig:
    """创建默认容错配置"""
    config = FaultToleranceConfig(strategy=strategy)
    
    if strategy == FaultToleranceStrategy.RETRY:
        config.retry_config = RetryConfig(**kwargs)
    elif strategy == FaultToleranceStrategy.CIRCUIT_BREAKER:
        config.circuit_breaker_config = CircuitBreakerConfig(**kwargs)
    elif strategy == FaultToleranceStrategy.BULKHEAD:
        config.bulkhead_config = BulkheadConfig(**kwargs)
    
    return config


# 全局容错管理器
_global_fault_tolerance_manager = None

def get_fault_tolerance_manager() -> FaultToleranceManager:
    """获取全局容错管理器实例"""
    global _global_fault_tolerance_manager
    if _global_fault_tolerance_manager is None:
        _global_fault_tolerance_manager = FaultToleranceManager()
    return _global_fault_tolerance_manager


# 便捷函数
def with_retry(max_attempts: int = 3, 
               base_delay: float = 1.0,
               backoff_strategy: str = "exponential"):
    """重试装饰器"""
    return fault_tolerant(
        service_name="default_retry",
        strategy=FaultToleranceStrategy.RETRY,
        max_attempts=max_attempts,
        base_delay=base_delay,
        backoff_strategy=backoff_strategy
    )


def with_circuit_breaker(failure_threshold: int = 5,
                        timeout: float = 60.0):
    """断路器装饰器"""
    return fault_tolerant(
        service_name="default_circuit_breaker",
        strategy=FaultToleranceStrategy.CIRCUIT_BREAKER,
        failure_threshold=failure_threshold,
        timeout=timeout
    )


def with_bulkhead(max_concurrent_calls: int = 10):
    """舱壁隔离装饰器"""
    return fault_tolerant(
        service_name="default_bulkhead",
        strategy=FaultToleranceStrategy.BULKHEAD,
        max_concurrent_calls=max_concurrent_calls
    )