import pytest
import time
import threading
from unittest.mock import Mock, patch
from concurrent.futures import Future
from utils.fault_tolerance import (
    FaultToleranceManager, RetryManager, CircuitBreaker, BulkheadIsolation,
    FaultToleranceStrategy, CircuitState, RetryConfig, CircuitBreakerConfig, BulkheadConfig,
    FaultToleranceConfig, CircuitBreakerOpenError, BulkheadIsolationError,
    fault_tolerant, with_retry, with_circuit_breaker, with_bulkhead,
    get_fault_tolerance_manager, create_default_config
)


class TestRetryManager:
    
    def setup_method(self):
        self.config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,  # 短延迟用于测试
            max_delay=1.0,
            exponential_base=2.0,
            jitter=False  # 禁用抖动以便测试可预测
        )
        self.retry_manager = RetryManager(self.config)
    
    def test_successful_execution_no_retry(self):
        """测试成功执行不需要重试"""
        mock_func = Mock(return_value="success")
        
        result = self.retry_manager.execute_with_retry(mock_func, "arg1", key="value")
        
        assert result == "success"
        assert mock_func.call_count == 1
        mock_func.assert_called_with("arg1", key="value")
    
    def test_retry_after_failures(self):
        """测试失败后的重试机制"""
        mock_func = Mock(side_effect=[Exception("失败1"), Exception("失败2"), "成功"])
        
        result = self.retry_manager.execute_with_retry(mock_func)
        
        assert result == "成功"
        assert mock_func.call_count == 3
    
    def test_all_retries_exhausted(self):
        """测试所有重试都失败的情况"""
        mock_func = Mock(side_effect=Exception("一直失败"))
        
        with pytest.raises(Exception, match="一直失败"):
            self.retry_manager.execute_with_retry(mock_func)
        
        assert mock_func.call_count == 3
    
    def test_exponential_backoff_calculation(self):
        """测试指数退避延迟计算"""
        delay_0 = self.retry_manager._calculate_delay(0)
        delay_1 = self.retry_manager._calculate_delay(1)
        delay_2 = self.retry_manager._calculate_delay(2)
        
        assert delay_0 == 0.1  # base_delay
        assert delay_1 == 0.2  # base_delay * 2^1
        assert delay_2 == 0.4  # base_delay * 2^2
    
    def test_linear_backoff_calculation(self):
        """测试线性退避延迟计算"""
        self.config.backoff_strategy = "linear"
        
        delay_0 = self.retry_manager._calculate_delay(0)
        delay_1 = self.retry_manager._calculate_delay(1)
        delay_2 = self.retry_manager._calculate_delay(2)
        
        assert delay_0 == 0.1  # base_delay * 1
        assert delay_1 == 0.2  # base_delay * 2
        assert delay_2 == 0.3  # base_delay * 3
    
    def test_fixed_backoff_calculation(self):
        """测试固定延迟计算"""
        self.config.backoff_strategy = "fixed"
        
        delay_0 = self.retry_manager._calculate_delay(0)
        delay_1 = self.retry_manager._calculate_delay(1)
        delay_2 = self.retry_manager._calculate_delay(2)
        
        assert delay_0 == 0.1  # base_delay
        assert delay_1 == 0.1  # base_delay
        assert delay_2 == 0.1  # base_delay
    
    def test_max_delay_limit(self):
        """测试最大延迟限制"""
        # 设置会超过最大延迟的参数
        self.config.max_delay = 0.5
        
        delay_10 = self.retry_manager._calculate_delay(10)  # 会非常大
        
        assert delay_10 <= 0.5
    
    def test_jitter_enabled(self):
        """测试启用抖动的延迟计算"""
        self.config.jitter = True
        
        delays = [self.retry_manager._calculate_delay(1) for _ in range(10)]
        
        # 启用抖动后，延迟应该有变化
        assert len(set(delays)) > 1


class TestCircuitBreaker:
    
    def setup_method(self):
        self.config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout=1.0,  # 短超时用于测试
            success_threshold=2,
            monitor_window=10.0
        )
        self.circuit_breaker = CircuitBreaker(self.config)
    
    def test_successful_calls_keep_circuit_closed(self):
        """测试成功调用保持断路器关闭"""
        mock_func = Mock(return_value="success")
        
        for _ in range(5):
            result = self.circuit_breaker.call(mock_func)
            assert result == "success"
        
        assert self.circuit_breaker.state == CircuitState.CLOSED
        assert mock_func.call_count == 5
    
    def test_circuit_opens_after_failures(self):
        """测试失败后断路器开启"""
        mock_func = Mock(side_effect=Exception("失败"))
        
        # 前几次失败
        for i in range(self.config.failure_threshold):
            with pytest.raises(Exception):
                self.circuit_breaker.call(mock_func)
        
        assert self.circuit_breaker.state == CircuitState.OPEN
        
        # 断路器开启后应该拒绝调用
        with pytest.raises(CircuitBreakerOpenError):
            self.circuit_breaker.call(mock_func)
    
    def test_circuit_transitions_to_half_open(self):
        """测试断路器转换到半开状态"""
        mock_func = Mock(side_effect=Exception("失败"))
        
        # 触发断路器开启
        for _ in range(self.config.failure_threshold):
            with pytest.raises(Exception):
                self.circuit_breaker.call(mock_func)
        
        assert self.circuit_breaker.state == CircuitState.OPEN
        
        # 等待超时
        time.sleep(self.config.timeout + 0.1)
        
        # 下次调用应该转换到半开状态
        mock_func.side_effect = "success"
        result = self.circuit_breaker.call(mock_func)
        
        assert result == "success"
        assert self.circuit_breaker.state == CircuitState.HALF_OPEN
    
    def test_circuit_closes_after_successful_half_open_calls(self):
        """测试半开状态下成功调用后断路器关闭"""
        # 先让断路器开启
        self.circuit_breaker.state = CircuitState.OPEN
        self.circuit_breaker.last_failure_time = time.time() - self.config.timeout - 1
        
        mock_func = Mock(return_value="success")
        
        # 执行足够的成功调用
        for _ in range(self.config.success_threshold):
            result = self.circuit_breaker.call(mock_func)
            assert result == "success"
        
        assert self.circuit_breaker.state == CircuitState.CLOSED
    
    def test_circuit_reopens_on_failure_in_half_open(self):
        """测试半开状态下失败重新开启断路器"""
        # 设置为半开状态
        self.circuit_breaker.state = CircuitState.HALF_OPEN
        
        mock_func = Mock(side_effect=Exception("失败"))
        
        with pytest.raises(Exception):
            self.circuit_breaker.call(mock_func)
        
        assert self.circuit_breaker.state == CircuitState.OPEN
    
    def test_get_metrics(self):
        """测试获取断路器指标"""
        mock_func = Mock(return_value="success")
        
        # 执行一些调用
        for _ in range(3):
            self.circuit_breaker.call(mock_func)
        
        metrics = self.circuit_breaker.get_metrics()
        
        assert metrics["state"] == CircuitState.CLOSED.value
        assert metrics["total_calls_in_window"] == 3
        assert metrics["successful_calls_in_window"] == 3
        assert metrics["failed_calls_in_window"] == 0
        assert metrics["success_rate"] == 1.0
    
    def test_call_history_cleanup(self):
        """测试调用历史清理"""
        mock_func = Mock(return_value="success")
        
        # 模拟旧的调用记录
        old_time = time.time() - self.config.monitor_window - 1
        self.circuit_breaker.call_history = [
            {"timestamp": old_time, "success": True},
            {"timestamp": old_time, "success": False}
        ]
        
        # 执行新调用
        self.circuit_breaker.call(mock_func)
        
        # 检查旧记录是否被清理
        assert len(self.circuit_breaker.call_history) == 1
        assert self.circuit_breaker.call_history[0]["success"] is True


class TestBulkheadIsolation:
    
    def setup_method(self):
        self.config = BulkheadConfig(
            max_concurrent_calls=2,
            queue_size=10,
            timeout=1.0
        )
        self.bulkhead = BulkheadIsolation(self.config)
    
    def teardown_method(self):
        self.bulkhead.shutdown()
    
    def test_concurrent_execution_within_limit(self):
        """测试在限制内的并发执行"""
        def slow_function(duration):
            time.sleep(duration)
            return f"completed after {duration}s"
        
        # 提交两个任务（在限制内）
        future1 = self.bulkhead.submit(slow_function, 0.1)
        future2 = self.bulkhead.submit(slow_function, 0.1)
        
        result1 = future1.result()
        result2 = future2.result()
        
        assert "completed after 0.1s" in result1
        assert "completed after 0.1s" in result2
    
    def test_rejection_when_exceeding_limit(self):
        """测试超过限制时的拒绝"""
        def slow_function():
            time.sleep(0.5)
            return "completed"
        
        # 提交最大数量的任务
        futures = []
        for _ in range(self.config.max_concurrent_calls):
            future = self.bulkhead.submit(slow_function)
            futures.append(future)
        
        # 再提交一个应该被拒绝
        with pytest.raises(BulkheadIsolationError):
            self.bulkhead.submit(slow_function)
        
        # 等待所有任务完成
        for future in futures:
            future.result()
    
    def test_synchronous_execution(self):
        """测试同步执行"""
        def simple_function(x):
            return x * 2
        
        result = self.bulkhead.execute(simple_function, 5)
        
        assert result == 10
    
    def test_get_metrics(self):
        """测试获取舱壁隔离指标"""
        def slow_function():
            time.sleep(0.2)
            return "completed"
        
        # 提交一个任务
        future = self.bulkhead.submit(slow_function)
        
        # 获取指标
        metrics = self.bulkhead.get_metrics()
        
        assert metrics["active_calls"] == 1
        assert metrics["max_concurrent_calls"] == 2
        assert metrics["utilization"] == 0.5
        
        # 等待任务完成
        future.result()
        
        # 再次获取指标
        metrics = self.bulkhead.get_metrics()
        assert metrics["active_calls"] == 0
        assert metrics["utilization"] == 0.0


class TestFaultToleranceManager:
    
    def setup_method(self):
        self.manager = FaultToleranceManager()
    
    def teardown_method(self):
        self.manager.shutdown()
    
    def test_register_retry_service(self):
        """测试注册重试服务"""
        config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.RETRY,
            retry_config=RetryConfig(max_attempts=3)
        )
        
        self.manager.register_service("test_service", config)
        
        assert "test_service" in self.manager.configurations
        assert "test_service" in self.manager.retry_managers
    
    def test_register_circuit_breaker_service(self):
        """测试注册断路器服务"""
        config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.CIRCUIT_BREAKER,
            circuit_breaker_config=CircuitBreakerConfig()
        )
        
        self.manager.register_service("test_service", config)
        
        assert "test_service" in self.manager.configurations
        assert "test_service" in self.manager.circuit_breakers
    
    def test_register_bulkhead_service(self):
        """测试注册舱壁隔离服务"""
        config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.BULKHEAD,
            bulkhead_config=BulkheadConfig()
        )
        
        self.manager.register_service("test_service", config)
        
        assert "test_service" in self.manager.configurations
        assert "test_service" in self.manager.bulkhead_isolations
    
    def test_execute_with_retry_strategy(self):
        """测试使用重试策略执行"""
        config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.RETRY,
            retry_config=RetryConfig(max_attempts=3, base_delay=0.01)
        )
        self.manager.register_service("retry_service", config)
        
        mock_func = Mock(side_effect=[Exception("失败"), "成功"])
        
        result = self.manager.execute_with_fault_tolerance("retry_service", mock_func)
        
        assert result == "成功"
        assert mock_func.call_count == 2
    
    def test_execute_with_fallback_strategy(self):
        """测试使用回退策略执行"""
        fallback_func = Mock(return_value="fallback_result")
        config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.FALLBACK,
            fallback_function=fallback_func
        )
        self.manager.register_service("fallback_service", config)
        
        mock_func = Mock(side_effect=Exception("主功能失败"))
        
        result = self.manager.execute_with_fault_tolerance("fallback_service", mock_func)
        
        assert result == "fallback_result"
        fallback_func.assert_called_once()
    
    def test_execute_unregistered_service(self):
        """测试执行未注册的服务"""
        mock_func = Mock(return_value="success")
        
        result = self.manager.execute_with_fault_tolerance("unknown_service", mock_func)
        
        assert result == "success"
        mock_func.assert_called_once()
    
    def test_execute_disabled_service(self):
        """测试执行已禁用的服务"""
        config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.RETRY,
            retry_config=RetryConfig(),
            enabled=False
        )
        self.manager.register_service("disabled_service", config)
        
        mock_func = Mock(return_value="success")
        
        result = self.manager.execute_with_fault_tolerance("disabled_service", mock_func)
        
        assert result == "success"
        mock_func.assert_called_once()
    
    def test_enable_disable_service(self):
        """测试启用/禁用服务"""
        config = FaultToleranceConfig(strategy=FaultToleranceStrategy.FAIL_FAST)
        self.manager.register_service("test_service", config)
        
        assert self.manager.configurations["test_service"].enabled is True
        
        self.manager.disable_service("test_service")
        assert self.manager.configurations["test_service"].enabled is False
        
        self.manager.enable_service("test_service")
        assert self.manager.configurations["test_service"].enabled is True
    
    def test_get_service_metrics(self):
        """测试获取服务指标"""
        config = FaultToleranceConfig(strategy=FaultToleranceStrategy.FAIL_FAST)
        self.manager.register_service("test_service", config)
        
        metrics = self.manager.get_service_metrics("test_service")
        
        assert metrics["service_name"] == "test_service"
        assert metrics["strategy"] == "fail_fast"
        assert metrics["enabled"] is True
    
    def test_get_all_metrics(self):
        """测试获取所有服务指标"""
        config1 = FaultToleranceConfig(strategy=FaultToleranceStrategy.FAIL_FAST)
        config2 = FaultToleranceConfig(strategy=FaultToleranceStrategy.RETRY, retry_config=RetryConfig())
        
        self.manager.register_service("service1", config1)
        self.manager.register_service("service2", config2)
        
        all_metrics = self.manager.get_all_metrics()
        
        assert "service1" in all_metrics
        assert "service2" in all_metrics
        assert all_metrics["service1"]["strategy"] == "fail_fast"
        assert all_metrics["service2"]["strategy"] == "retry"


class TestDecorators:
    
    def test_fault_tolerant_decorator_with_retry(self):
        """测试容错装饰器与重试"""
        @fault_tolerant("test_service", FaultToleranceStrategy.RETRY, max_attempts=3, base_delay=0.01)
        def failing_function():
            failing_function.call_count += 1
            if failing_function.call_count < 3:
                raise Exception("失败")
            return "成功"
        
        failing_function.call_count = 0
        
        result = failing_function()
        
        assert result == "成功"
        assert failing_function.call_count == 3
    
    def test_with_retry_decorator(self):
        """测试重试装饰器"""
        @with_retry(max_attempts=2, base_delay=0.01)
        def failing_function():
            failing_function.call_count += 1
            if failing_function.call_count < 2:
                raise Exception("失败")
            return "成功"
        
        failing_function.call_count = 0
        
        result = failing_function()
        
        assert result == "成功"
        assert failing_function.call_count == 2
    
    def test_with_circuit_breaker_decorator(self):
        """测试断路器装饰器"""
        @with_circuit_breaker(failure_threshold=2, timeout=0.1)
        def failing_function():
            raise Exception("一直失败")
        
        # 前两次失败
        for _ in range(2):
            with pytest.raises(Exception):
                failing_function()
        
        # 第三次应该被断路器拒绝
        with pytest.raises(CircuitBreakerOpenError):
            failing_function()
    
    def test_with_bulkhead_decorator(self):
        """测试舱壁隔离装饰器"""
        @with_bulkhead(max_concurrent_calls=1)
        def slow_function():
            time.sleep(0.1)
            return "completed"
        
        # 在单独线程中执行以测试并发限制
        import threading
        
        results = []
        exceptions = []
        
        def call_function():
            try:
                result = slow_function()
                results.append(result)
            except Exception as e:
                exceptions.append(e)
        
        # 启动多个线程
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=call_function)
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 应该有一些调用成功，一些被拒绝
        assert len(results) + len(exceptions) == 3
        assert len(exceptions) > 0  # 应该有一些调用被拒绝


class TestUtilityFunctions:
    
    def test_create_default_config_retry(self):
        """测试创建默认重试配置"""
        config = create_default_config(
            FaultToleranceStrategy.RETRY,
            max_attempts=5,
            base_delay=2.0
        )
        
        assert config.strategy == FaultToleranceStrategy.RETRY
        assert config.retry_config.max_attempts == 5
        assert config.retry_config.base_delay == 2.0
    
    def test_create_default_config_circuit_breaker(self):
        """测试创建默认断路器配置"""
        config = create_default_config(
            FaultToleranceStrategy.CIRCUIT_BREAKER,
            failure_threshold=10,
            timeout=120.0
        )
        
        assert config.strategy == FaultToleranceStrategy.CIRCUIT_BREAKER
        assert config.circuit_breaker_config.failure_threshold == 10
        assert config.circuit_breaker_config.timeout == 120.0
    
    def test_get_fault_tolerance_manager_singleton(self):
        """测试全局容错管理器单例"""
        manager1 = get_fault_tolerance_manager()
        manager2 = get_fault_tolerance_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, FaultToleranceManager)


class TestIntegrationScenarios:
    
    def setup_method(self):
        self.manager = FaultToleranceManager()
    
    def teardown_method(self):
        self.manager.shutdown()
    
    def test_api_service_with_circuit_breaker_and_fallback(self):
        """测试API服务结合断路器和回退的集成场景"""
        # 模拟API调用和回退函数
        api_call_count = 0
        fallback_call_count = 0
        
        def api_call():
            nonlocal api_call_count
            api_call_count += 1
            raise Exception("API不可用")
        
        def fallback():
            nonlocal fallback_call_count
            fallback_call_count += 1
            return "缓存数据"
        
        # 注册断路器服务
        circuit_config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.CIRCUIT_BREAKER,
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=2, timeout=0.1)
        )
        self.manager.register_service("api_service", circuit_config)
        
        # 注册回退服务
        fallback_config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.FALLBACK,
            fallback_function=fallback
        )
        self.manager.register_service("fallback_service", fallback_config)
        
        # 先通过断路器调用API
        for _ in range(2):
            with pytest.raises(Exception):
                self.manager.execute_with_fault_tolerance("api_service", api_call)
        
        # 断路器应该已开启，现在使用回退服务
        result = self.manager.execute_with_fault_tolerance("fallback_service", api_call)
        
        assert result == "缓存数据"
        assert api_call_count == 2  # 断路器阻止了进一步的API调用
        assert fallback_call_count == 1
    
    def test_data_processing_with_retry_and_bulkhead(self):
        """测试数据处理结合重试和舱壁隔离的集成场景"""
        # 注册重试服务
        retry_config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.RETRY,
            retry_config=RetryConfig(max_attempts=3, base_delay=0.01)
        )
        self.manager.register_service("data_processing", retry_config)
        
        # 注册舱壁隔离服务
        bulkhead_config = FaultToleranceConfig(
            strategy=FaultToleranceStrategy.BULKHEAD,
            bulkhead_config=BulkheadConfig(max_concurrent_calls=2)
        )
        self.manager.register_service("parallel_processing", bulkhead_config)
        
        # 模拟数据处理函数
        call_count = 0
        
        def process_data(data):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("临时错误")
            return f"processed: {data}"
        
        # 测试重试功能
        result = self.manager.execute_with_fault_tolerance("data_processing", process_data, "test_data")
        assert result == "processed: test_data"
        assert call_count == 2
        
        # 测试舱壁隔离
        def simple_process(data):
            return f"processed: {data}"
        
        result = self.manager.execute_with_fault_tolerance("parallel_processing", simple_process, "test_data")
        assert result == "processed: test_data"