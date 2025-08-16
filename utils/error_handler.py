import os
import time
import traceback
import logging
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime


class ErrorCategory(Enum):
    """错误分类"""
    INPUT_VALIDATION = "input_validation"      # 输入验证错误
    FILE_OPERATION = "file_operation"         # 文件操作错误
    API_SERVICE = "api_service"               # API服务错误
    PROCESSING = "processing"                 # 处理逻辑错误
    SYSTEM_RESOURCE = "system_resource"       # 系统资源错误
    NETWORK = "network"                       # 网络错误
    AUTHENTICATION = "authentication"         # 认证错误
    PERMISSION = "permission"                 # 权限错误
    CONFIGURATION = "configuration"           # 配置错误
    UNKNOWN = "unknown"                       # 未知错误


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"           # 低：不影响主要功能
    MEDIUM = "medium"     # 中：影响部分功能
    HIGH = "high"         # 高：影响主要功能
    CRITICAL = "critical" # 严重：系统无法正常运行


@dataclass
class ErrorContext:
    """错误上下文信息"""
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    file_path: Optional[str] = None
    operation: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class ProcessedError:
    """处理后的错误信息"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    user_message: str
    technical_message: str
    timestamp: datetime
    context: ErrorContext
    traceback_info: Optional[str] = None
    suggested_actions: List[str] = None
    recovery_possible: bool = True


class ErrorHandler:
    """
    统一错误处理系统
    
    实现错误分类和处理策略，
    创建用户友好的错误消息，
    实现详细错误日志记录。
    """
    
    def __init__(self, log_file_path: Optional[str] = None):
        """初始化错误处理器"""
        self.error_counter = 0
        self.error_history: List[ProcessedError] = []
        
        # 配置日志记录
        self.setup_logging(log_file_path)
        
        # 错误映射规则
        self.error_mapping_rules = self._initialize_error_mapping()
        
        # 用户友好消息模板
        self.user_message_templates = self._initialize_user_messages()
        
        # 恢复建议
        self.recovery_suggestions = self._initialize_recovery_suggestions()
    
    def setup_logging(self, log_file_path: Optional[str] = None):
        """设置日志配置"""
        if not log_file_path:
            log_file_path = "logs/error_handler.log"
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        
        # 配置日志格式
        logging.basicConfig(
            level=logging.ERROR,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file_path, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('ErrorHandler')
    
    def handle_error(self, 
                    exception: Exception,
                    context: Optional[ErrorContext] = None,
                    custom_category: Optional[ErrorCategory] = None) -> ProcessedError:
        """
        处理错误并返回处理结果
        
        Args:
            exception: 捕获的异常
            context: 错误上下文
            custom_category: 自定义错误分类
            
        Returns:
            ProcessedError: 处理后的错误信息
        """
        try:
            # 生成错误ID
            self.error_counter += 1
            error_id = f"ERR_{int(time.time())}_{self.error_counter:04d}"
            
            # 分类错误
            category = custom_category or self._categorize_error(exception)
            
            # 确定严重程度
            severity = self._determine_severity(exception, category)
            
            # 生成用户友好消息
            user_message = self._generate_user_message(exception, category)
            
            # 生成技术消息
            technical_message = self._generate_technical_message(exception)
            
            # 获取建议行动
            suggested_actions = self._get_suggested_actions(category, exception)
            
            # 判断是否可恢复
            recovery_possible = self._is_recovery_possible(category, exception)
            
            # 获取堆栈跟踪
            traceback_info = traceback.format_exc()
            
            # 创建处理后的错误对象
            processed_error = ProcessedError(
                error_id=error_id,
                category=category,
                severity=severity,
                user_message=user_message,
                technical_message=technical_message,
                timestamp=datetime.now(),
                context=context or ErrorContext(),
                traceback_info=traceback_info,
                suggested_actions=suggested_actions,
                recovery_possible=recovery_possible
            )
            
            # 记录错误
            self._log_error(processed_error)
            
            # 添加到历史记录
            self.error_history.append(processed_error)
            
            # 限制历史记录大小
            if len(self.error_history) > 1000:
                self.error_history = self.error_history[-500:]
            
            return processed_error
            
        except Exception as e:
            # 处理错误处理器本身的错误
            self.logger.critical(f"错误处理器内部错误: {str(e)}")
            return self._create_fallback_error(exception, context)
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        if not self.error_history:
            return {
                "total_errors": 0,
                "by_category": {},
                "by_severity": {},
                "recent_errors": []
            }
        
        # 按分类统计
        by_category = {}
        for error in self.error_history:
            category = error.category.value
            by_category[category] = by_category.get(category, 0) + 1
        
        # 按严重程度统计
        by_severity = {}
        for error in self.error_history:
            severity = error.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        # 最近的错误
        recent_errors = [
            {
                "error_id": error.error_id,
                "category": error.category.value,
                "severity": error.severity.value,
                "user_message": error.user_message,
                "timestamp": error.timestamp.isoformat()
            }
            for error in self.error_history[-10:]
        ]
        
        return {
            "total_errors": len(self.error_history),
            "by_category": by_category,
            "by_severity": by_severity,
            "recent_errors": recent_errors
        }
    
    def _categorize_error(self, exception: Exception) -> ErrorCategory:
        """根据异常类型和消息对错误进行分类"""
        exception_type = type(exception).__name__
        exception_message = str(exception).lower()
        
        # 检查映射规则
        for rule in self.error_mapping_rules:
            if rule["condition"](exception_type, exception_message):
                return rule["category"]
        
        return ErrorCategory.UNKNOWN
    
    def _determine_severity(self, exception: Exception, category: ErrorCategory) -> ErrorSeverity:
        """确定错误的严重程度"""
        # 基于错误分类的默认严重程度
        category_severity_map = {
            ErrorCategory.INPUT_VALIDATION: ErrorSeverity.LOW,
            ErrorCategory.FILE_OPERATION: ErrorSeverity.MEDIUM,
            ErrorCategory.API_SERVICE: ErrorSeverity.HIGH,
            ErrorCategory.PROCESSING: ErrorSeverity.MEDIUM,
            ErrorCategory.SYSTEM_RESOURCE: ErrorSeverity.HIGH,
            ErrorCategory.NETWORK: ErrorSeverity.MEDIUM,
            ErrorCategory.AUTHENTICATION: ErrorSeverity.HIGH,
            ErrorCategory.PERMISSION: ErrorSeverity.HIGH,
            ErrorCategory.CONFIGURATION: ErrorSeverity.CRITICAL,
            ErrorCategory.UNKNOWN: ErrorSeverity.MEDIUM
        }
        
        base_severity = category_severity_map.get(category, ErrorSeverity.MEDIUM)
        
        # 根据异常类型调整严重程度
        exception_message = str(exception).lower()
        
        # 提升严重程度的关键词
        critical_keywords = ['critical', 'fatal', 'emergency', '严重', '致命']
        high_keywords = ['failed', 'error', 'exception', '失败', '错误']
        
        if any(keyword in exception_message for keyword in critical_keywords):
            return ErrorSeverity.CRITICAL
        elif any(keyword in exception_message for keyword in high_keywords) and base_severity == ErrorSeverity.LOW:
            return ErrorSeverity.MEDIUM
        
        return base_severity
    
    def _generate_user_message(self, exception: Exception, category: ErrorCategory) -> str:
        """生成用户友好的错误消息"""
        template = self.user_message_templates.get(category)
        if not template:
            return "系统遇到了一个问题，请稍后重试。"
        
        # 尝试提取具体信息
        exception_message = str(exception)
        
        # 替换模板变量
        try:
            return template.format(
                error_details=self._sanitize_error_message(exception_message)
            )
        except:
            return template
    
    def _generate_technical_message(self, exception: Exception) -> str:
        """生成技术错误消息"""
        return f"{type(exception).__name__}: {str(exception)}"
    
    def _get_suggested_actions(self, category: ErrorCategory, exception: Exception) -> List[str]:
        """获取建议的恢复行动"""
        suggestions = self.recovery_suggestions.get(category, [])
        
        # 根据具体异常添加特定建议
        exception_message = str(exception).lower()
        
        if "file not found" in exception_message or "文件不存在" in exception_message:
            suggestions.append("请检查文件路径是否正确")
        elif "permission" in exception_message or "权限" in exception_message:
            suggestions.append("请检查文件访问权限")
        elif "network" in exception_message or "网络" in exception_message:
            suggestions.append("请检查网络连接状态")
        
        return suggestions
    
    def _is_recovery_possible(self, category: ErrorCategory, exception: Exception) -> bool:
        """判断错误是否可以恢复"""
        # 不可恢复的错误类型
        unrecoverable_categories = {
            ErrorCategory.CONFIGURATION,
            ErrorCategory.PERMISSION,
            ErrorCategory.AUTHENTICATION
        }
        
        if category in unrecoverable_categories:
            return False
        
        # 检查异常消息中的不可恢复关键词
        exception_message = str(exception).lower()
        unrecoverable_keywords = ['corrupt', 'invalid format', '格式不支持', '文件损坏']
        
        if any(keyword in exception_message for keyword in unrecoverable_keywords):
            return False
        
        return True
    
    def _log_error(self, error: ProcessedError):
        """记录详细的错误日志"""
        log_message = (
            f"错误ID: {error.error_id} | "
            f"分类: {error.category.value} | "
            f"严重程度: {error.severity.value} | "
            f"用户消息: {error.user_message} | "
            f"技术消息: {error.technical_message}"
        )
        
        if error.context:
            context_info = []
            if error.context.user_id:
                context_info.append(f"用户ID: {error.context.user_id}")
            if error.context.job_id:
                context_info.append(f"作业ID: {error.context.job_id}")
            if error.context.file_path:
                context_info.append(f"文件路径: {error.context.file_path}")
            if error.context.operation:
                context_info.append(f"操作: {error.context.operation}")
            
            if context_info:
                log_message += f" | 上下文: {' | '.join(context_info)}"
        
        # 根据严重程度选择日志级别
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        # 记录堆栈跟踪（仅对高严重程度错误）
        if error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] and error.traceback_info:
            self.logger.error(f"堆栈跟踪 (错误ID: {error.error_id}):\n{error.traceback_info}")
    
    def _create_fallback_error(self, original_exception: Exception, context: Optional[ErrorContext]) -> ProcessedError:
        """创建后备错误对象（当错误处理器本身出错时）"""
        return ProcessedError(
            error_id=f"FALLBACK_{int(time.time())}",
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.CRITICAL,
            user_message="系统遇到了严重问题，请联系技术支持。",
            technical_message=f"ErrorHandler失败: {str(original_exception)}",
            timestamp=datetime.now(),
            context=context or ErrorContext(),
            recovery_possible=False
        )
    
    def _sanitize_error_message(self, message: str) -> str:
        """清理错误消息，移除敏感信息"""
        # 移除文件路径中的敏感信息
        import re
        
        # 移除绝对路径，只保留文件名
        message = re.sub(r'/[^\s]*/', '.../', message)
        
        # 移除可能的API密钥或令牌
        message = re.sub(r'[A-Za-z0-9]{32,}', '[REDACTED]', message)
        
        # 限制消息长度
        if len(message) > 200:
            message = message[:197] + "..."
        
        return message
    
    def _initialize_error_mapping(self) -> List[Dict]:
        """初始化错误映射规则"""
        return [
            {
                "condition": lambda exc_type, msg: "filenotfound" in exc_type.lower() or "no such file" in msg,
                "category": ErrorCategory.FILE_OPERATION
            },
            {
                "condition": lambda exc_type, msg: "permission" in exc_type.lower() or "permission" in msg,
                "category": ErrorCategory.PERMISSION
            },
            {
                "condition": lambda exc_type, msg: "validation" in exc_type.lower() or "invalid" in msg,
                "category": ErrorCategory.INPUT_VALIDATION
            },
            {
                "condition": lambda exc_type, msg: "connection" in msg or "network" in msg or "timeout" in msg,
                "category": ErrorCategory.NETWORK
            },
            {
                "condition": lambda exc_type, msg: "api" in msg or "401" in msg or "403" in msg,
                "category": ErrorCategory.API_SERVICE
            },
            {
                "condition": lambda exc_type, msg: "memory" in msg or "disk" in msg or "space" in msg,
                "category": ErrorCategory.SYSTEM_RESOURCE
            },
            {
                "condition": lambda exc_type, msg: "config" in msg or "setting" in msg,
                "category": ErrorCategory.CONFIGURATION
            },
            {
                "condition": lambda exc_type, msg: "auth" in msg or "token" in msg or "unauthorized" in msg,
                "category": ErrorCategory.AUTHENTICATION
            }
        ]
    
    def _initialize_user_messages(self) -> Dict[ErrorCategory, str]:
        """初始化用户友好消息模板"""
        return {
            ErrorCategory.INPUT_VALIDATION: "输入的文件或参数不符合要求，请检查文件格式和内容。",
            ErrorCategory.FILE_OPERATION: "文件操作失败，请检查文件是否存在且可访问。",
            ErrorCategory.API_SERVICE: "外部服务暂时不可用，请稍后重试。",
            ErrorCategory.PROCESSING: "处理过程中遇到问题，请检查输入文件或重试。",
            ErrorCategory.SYSTEM_RESOURCE: "系统资源不足，请释放一些空间或内存后重试。",
            ErrorCategory.NETWORK: "网络连接出现问题，请检查网络设置。",
            ErrorCategory.AUTHENTICATION: "身份验证失败，请检查API密钥或登录状态。",
            ErrorCategory.PERMISSION: "权限不足，请检查文件访问权限。",
            ErrorCategory.CONFIGURATION: "系统配置错误，请联系管理员。",
            ErrorCategory.UNKNOWN: "遇到未知问题，请重试或联系技术支持。"
        }
    
    def _initialize_recovery_suggestions(self) -> Dict[ErrorCategory, List[str]]:
        """初始化恢复建议"""
        return {
            ErrorCategory.INPUT_VALIDATION: [
                "验证输入文件格式是否正确",
                "检查文件是否完整且未损坏",
                "确认参数值在有效范围内"
            ],
            ErrorCategory.FILE_OPERATION: [
                "检查文件路径是否正确",
                "确认文件权限设置",
                "尝试将文件移动到其他位置"
            ],
            ErrorCategory.API_SERVICE: [
                "稍后重试操作",
                "检查API密钥是否有效",
                "确认网络连接正常"
            ],
            ErrorCategory.PROCESSING: [
                "使用更简单的输入文件重试",
                "检查系统资源使用情况",
                "尝试重启应用程序"
            ],
            ErrorCategory.SYSTEM_RESOURCE: [
                "释放磁盘空间",
                "关闭其他应用程序释放内存",
                "等待系统负载降低"
            ],
            ErrorCategory.NETWORK: [
                "检查网络连接",
                "尝试使用VPN或更换网络",
                "联系网络管理员"
            ],
            ErrorCategory.AUTHENTICATION: [
                "检查API密钥配置",
                "重新登录账户",
                "联系服务提供商"
            ],
            ErrorCategory.PERMISSION: [
                "以管理员权限运行",
                "修改文件权限",
                "联系系统管理员"
            ],
            ErrorCategory.CONFIGURATION: [
                "检查配置文件",
                "重置为默认配置",
                "联系技术支持"
            ],
            ErrorCategory.UNKNOWN: [
                "重新启动应用程序",
                "检查系统日志",
                "联系技术支持团队"
            ]
        }


# 全局错误处理器实例
_global_error_handler = None

def get_error_handler() -> ErrorHandler:
    """获取全局错误处理器实例"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler

def handle_error(exception: Exception, 
                context: Optional[ErrorContext] = None,
                custom_category: Optional[ErrorCategory] = None) -> ProcessedError:
    """便捷函数：处理错误"""
    return get_error_handler().handle_error(exception, context, custom_category)