import pytest
import tempfile
import os
from unittest.mock import Mock, patch
from utils.error_handler import (
    ErrorHandler, ErrorCategory, ErrorSeverity, ErrorContext, ProcessedError,
    get_error_handler, handle_error
)


class TestErrorHandler:
    
    def setup_method(self):
        # 为每个测试创建新的错误处理器
        with tempfile.NamedTemporaryFile(delete=False) as log_file:
            self.log_path = log_file.name
        
        self.handler = ErrorHandler(self.log_path)
    
    def teardown_method(self):
        # 清理日志文件
        try:
            os.unlink(self.log_path)
        except:
            pass
    
    def test_initialization(self):
        """测试错误处理器初始化"""
        assert self.handler.error_counter == 0
        assert len(self.handler.error_history) == 0
        assert self.handler.logger is not None
        assert len(self.handler.error_mapping_rules) > 0
        assert len(self.handler.user_message_templates) > 0
        assert len(self.handler.recovery_suggestions) > 0
    
    def test_handle_file_not_found_error(self):
        """测试文件未找到错误的处理"""
        exception = FileNotFoundError("文件不存在: /path/to/file.txt")
        context = ErrorContext(
            user_id="user123",
            job_id="job456",
            file_path="/path/to/file.txt",
            operation="read_file"
        )
        
        result = self.handler.handle_error(exception, context)
        
        assert isinstance(result, ProcessedError)
        assert result.category == ErrorCategory.FILE_OPERATION
        assert result.severity in [ErrorSeverity.MEDIUM, ErrorSeverity.LOW]
        assert "文件操作失败" in result.user_message
        assert result.context.user_id == "user123"
        assert result.context.job_id == "job456"
        assert result.recovery_possible is True
        assert len(result.suggested_actions) > 0
    
    def test_handle_permission_error(self):
        """测试权限错误的处理"""
        exception = PermissionError("权限被拒绝")
        
        result = self.handler.handle_error(exception)
        
        assert result.category == ErrorCategory.PERMISSION
        assert result.severity == ErrorSeverity.HIGH
        assert "权限不足" in result.user_message
        assert result.recovery_possible is False
    
    def test_handle_value_error(self):
        """测试值错误的处理"""
        exception = ValueError("无效的输入值")
        
        result = self.handler.handle_error(exception)
        
        assert result.category == ErrorCategory.INPUT_VALIDATION
        assert result.severity == ErrorSeverity.LOW
        assert "输入的文件或参数不符合要求" in result.user_message
        assert result.recovery_possible is True
    
    def test_handle_connection_error(self):
        """测试连接错误的处理"""
        exception = ConnectionError("网络连接超时")
        
        result = self.handler.handle_error(exception)
        
        assert result.category == ErrorCategory.NETWORK
        assert result.severity == ErrorSeverity.MEDIUM
        assert "网络连接出现问题" in result.user_message
        assert "检查网络连接" in result.suggested_actions
    
    def test_handle_custom_category(self):
        """测试自定义错误分类"""
        exception = RuntimeError("自定义错误")
        custom_category = ErrorCategory.API_SERVICE
        
        result = self.handler.handle_error(exception, custom_category=custom_category)
        
        assert result.category == ErrorCategory.API_SERVICE
        assert result.severity == ErrorSeverity.HIGH
        assert "外部服务暂时不可用" in result.user_message
    
    def test_categorize_error_file_operations(self):
        """测试文件操作错误分类"""
        file_error = FileNotFoundError("No such file")
        category = self.handler._categorize_error(file_error)
        assert category == ErrorCategory.FILE_OPERATION
    
    def test_categorize_error_network(self):
        """测试网络错误分类"""
        network_error = Exception("Connection timeout")
        category = self.handler._categorize_error(network_error)
        assert category == ErrorCategory.NETWORK
    
    def test_categorize_error_validation(self):
        """测试验证错误分类"""
        validation_error = ValueError("Invalid input format")
        category = self.handler._categorize_error(validation_error)
        assert category == ErrorCategory.INPUT_VALIDATION
    
    def test_categorize_error_unknown(self):
        """测试未知错误分类"""
        unknown_error = Exception("随机错误消息")
        category = self.handler._categorize_error(unknown_error)
        assert category == ErrorCategory.UNKNOWN
    
    def test_determine_severity_by_category(self):
        """测试基于分类的严重程度判断"""
        # 配置错误应该是严重的
        config_error = Exception("配置错误")
        severity = self.handler._determine_severity(config_error, ErrorCategory.CONFIGURATION)
        assert severity == ErrorSeverity.CRITICAL
        
        # 输入验证错误应该是低严重程度
        validation_error = ValueError("验证错误")
        severity = self.handler._determine_severity(validation_error, ErrorCategory.INPUT_VALIDATION)
        assert severity == ErrorSeverity.LOW
    
    def test_determine_severity_by_keywords(self):
        """测试基于关键词的严重程度判断"""
        critical_error = Exception("Critical system failure")
        severity = self.handler._determine_severity(critical_error, ErrorCategory.PROCESSING)
        assert severity == ErrorSeverity.CRITICAL
        
        fatal_error = Exception("Fatal error occurred")
        severity = self.handler._determine_severity(fatal_error, ErrorCategory.PROCESSING)
        assert severity == ErrorSeverity.CRITICAL
    
    def test_generate_user_message(self):
        """测试用户友好消息生成"""
        exception = FileNotFoundError("/path/file.txt not found")
        message = self.handler._generate_user_message(exception, ErrorCategory.FILE_OPERATION)
        
        assert "文件操作失败" in message
        assert len(message) > 0
        assert message != str(exception)  # 应该是友好消息，不是原始异常
    
    def test_generate_technical_message(self):
        """测试技术消息生成"""
        exception = ValueError("Invalid input")
        message = self.handler._generate_technical_message(exception)
        
        assert "ValueError" in message
        assert "Invalid input" in message
    
    def test_get_suggested_actions_file_not_found(self):
        """测试文件未找到的建议行动"""
        exception = FileNotFoundError("file not found")
        actions = self.handler._get_suggested_actions(ErrorCategory.FILE_OPERATION, exception)
        
        assert "请检查文件路径是否正确" in actions
        assert len(actions) > 0
    
    def test_get_suggested_actions_permission(self):
        """测试权限错误的建议行动"""
        exception = PermissionError("permission denied")
        actions = self.handler._get_suggested_actions(ErrorCategory.PERMISSION, exception)
        
        assert "请检查文件访问权限" in actions
    
    def test_get_suggested_actions_network(self):
        """测试网络错误的建议行动"""
        exception = ConnectionError("network error")
        actions = self.handler._get_suggested_actions(ErrorCategory.NETWORK, exception)
        
        assert "请检查网络连接状态" in actions
    
    def test_is_recovery_possible_unrecoverable_categories(self):
        """测试不可恢复的错误分类"""
        exception = Exception("配置错误")
        
        assert not self.handler._is_recovery_possible(ErrorCategory.CONFIGURATION, exception)
        assert not self.handler._is_recovery_possible(ErrorCategory.PERMISSION, exception)
        assert not self.handler._is_recovery_possible(ErrorCategory.AUTHENTICATION, exception)
    
    def test_is_recovery_possible_recoverable_categories(self):
        """测试可恢复的错误分类"""
        exception = Exception("处理错误")
        
        assert self.handler._is_recovery_possible(ErrorCategory.PROCESSING, exception)
        assert self.handler._is_recovery_possible(ErrorCategory.NETWORK, exception)
        assert self.handler._is_recovery_possible(ErrorCategory.FILE_OPERATION, exception)
    
    def test_is_recovery_possible_unrecoverable_keywords(self):
        """测试基于关键词的不可恢复判断"""
        corrupt_error = Exception("文件损坏")
        assert not self.handler._is_recovery_possible(ErrorCategory.FILE_OPERATION, corrupt_error)
        
        format_error = Exception("invalid format")
        assert not self.handler._is_recovery_possible(ErrorCategory.INPUT_VALIDATION, format_error)
    
    def test_sanitize_error_message_path_removal(self):
        """测试错误消息中路径的清理"""
        message = "Error reading /home/user/secret/file.txt"
        sanitized = self.handler._sanitize_error_message(message)
        
        assert "/home/user/secret/" not in sanitized
        assert ".../" in sanitized
        assert "file.txt" in sanitized
    
    def test_sanitize_error_message_token_removal(self):
        """测试错误消息中令牌的清理"""
        message = "API error with token abc123def456ghi789jkl012mno345pqr678"
        sanitized = self.handler._sanitize_error_message(message)
        
        assert "abc123def456ghi789jkl012mno345pqr678" not in sanitized
        assert "[REDACTED]" in sanitized
    
    def test_sanitize_error_message_length_limit(self):
        """测试错误消息长度限制"""
        long_message = "A" * 300
        sanitized = self.handler._sanitize_error_message(long_message)
        
        assert len(sanitized) <= 200
        assert sanitized.endswith("...")
    
    def test_error_history_management(self):
        """测试错误历史记录管理"""
        # 添加一些错误
        for i in range(5):
            exception = Exception(f"测试错误 {i}")
            self.handler.handle_error(exception)
        
        assert len(self.handler.error_history) == 5
        
        # 测试错误计数器
        assert self.handler.error_counter == 5
    
    def test_error_history_size_limit(self):
        """测试错误历史记录大小限制"""
        # 模拟大量错误以测试大小限制
        original_limit = 1000
        
        # 创建超过限制的错误数量
        with patch.object(self.handler, 'error_history', [Mock() for _ in range(1200)]):
            exception = Exception("新错误")
            self.handler.handle_error(exception)
            
            # 检查历史记录是否被截断到500个
            assert len(self.handler.error_history) <= 500
    
    def test_get_error_statistics_empty(self):
        """测试空错误历史的统计信息"""
        stats = self.handler.get_error_statistics()
        
        assert stats["total_errors"] == 0
        assert stats["by_category"] == {}
        assert stats["by_severity"] == {}
        assert stats["recent_errors"] == []
    
    def test_get_error_statistics_with_errors(self):
        """测试有错误的统计信息"""
        # 添加不同类型的错误
        errors = [
            FileNotFoundError("文件错误1"),
            FileNotFoundError("文件错误2"),
            ValueError("验证错误1"),
            ConnectionError("网络错误1")
        ]
        
        for error in errors:
            self.handler.handle_error(error)
        
        stats = self.handler.get_error_statistics()
        
        assert stats["total_errors"] == 4
        assert "file_operation" in stats["by_category"]
        assert stats["by_category"]["file_operation"] == 2
        assert "input_validation" in stats["by_category"]
        assert "network" in stats["by_category"]
        assert len(stats["recent_errors"]) == 4
    
    @patch('utils.error_handler.logging')
    def test_logging_configuration(self, mock_logging):
        """测试日志配置"""
        with tempfile.NamedTemporaryFile() as temp_log:
            ErrorHandler(temp_log.name)
            mock_logging.basicConfig.assert_called_once()
    
    def test_fallback_error_creation(self):
        """测试后备错误创建"""
        original_exception = Exception("原始错误")
        context = ErrorContext(user_id="test_user")
        
        fallback_error = self.handler._create_fallback_error(original_exception, context)
        
        assert fallback_error.category == ErrorCategory.UNKNOWN
        assert fallback_error.severity == ErrorSeverity.CRITICAL
        assert fallback_error.recovery_possible is False
        assert "系统遇到了严重问题" in fallback_error.user_message
        assert "ErrorHandler失败" in fallback_error.technical_message
        assert fallback_error.context.user_id == "test_user"
    
    def test_error_handler_internal_error(self):
        """测试错误处理器内部错误的处理"""
        # 模拟内部错误
        with patch.object(self.handler, '_categorize_error', side_effect=Exception("内部错误")):
            exception = ValueError("测试错误")
            result = self.handler.handle_error(exception)
            
            # 应该返回后备错误
            assert result.error_id.startswith("FALLBACK_")
            assert result.severity == ErrorSeverity.CRITICAL


class TestGlobalErrorHandler:
    
    def test_get_error_handler_singleton(self):
        """测试全局错误处理器单例模式"""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is handler2
        assert isinstance(handler1, ErrorHandler)
    
    def test_handle_error_convenience_function(self):
        """测试便捷错误处理函数"""
        exception = ValueError("测试错误")
        context = ErrorContext(user_id="test_user")
        
        result = handle_error(exception, context)
        
        assert isinstance(result, ProcessedError)
        assert result.context.user_id == "test_user"


class TestErrorContext:
    
    def test_error_context_creation(self):
        """测试错误上下文创建"""
        context = ErrorContext(
            user_id="user123",
            job_id="job456",
            file_path="/path/to/file.txt",
            operation="process_file",
            additional_data={"key": "value"}
        )
        
        assert context.user_id == "user123"
        assert context.job_id == "job456"
        assert context.file_path == "/path/to/file.txt"
        assert context.operation == "process_file"
        assert context.additional_data["key"] == "value"
    
    def test_error_context_defaults(self):
        """测试错误上下文默认值"""
        context = ErrorContext()
        
        assert context.user_id is None
        assert context.job_id is None
        assert context.file_path is None
        assert context.operation is None
        assert context.additional_data is None


class TestProcessedError:
    
    def test_processed_error_creation(self):
        """测试处理后错误对象创建"""
        from datetime import datetime
        
        error = ProcessedError(
            error_id="ERR_001",
            category=ErrorCategory.FILE_OPERATION,
            severity=ErrorSeverity.MEDIUM,
            user_message="用户友好消息",
            technical_message="技术消息",
            timestamp=datetime.now(),
            context=ErrorContext(user_id="test"),
            suggested_actions=["行动1", "行动2"],
            recovery_possible=True
        )
        
        assert error.error_id == "ERR_001"
        assert error.category == ErrorCategory.FILE_OPERATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.user_message == "用户友好消息"
        assert error.technical_message == "技术消息"
        assert error.context.user_id == "test"
        assert len(error.suggested_actions) == 2
        assert error.recovery_possible is True