class ProviderError(Exception):
    """基础提供者错误"""
    pass


class ProviderAuthError(ProviderError):
    """认证错误"""
    pass


class ProviderQuotaError(ProviderError):
    """配额错误"""
    pass


class ProviderNetworkError(ProviderError):
    """网络错误"""
    pass


class ProviderTimeoutError(ProviderError):
    """超时错误"""
    pass


class ProviderRateLimitError(ProviderError):
    """请求频率限制错误"""
    pass


def map_volcengine_error(volcengine_error_code: str, error_message: str = "") -> ProviderError:
    """
    将火山云错误代码映射为标准提供者错误
    
    Args:
        volcengine_error_code: 火山云错误代码
        error_message: 错误消息
        
    Returns:
        ProviderError: 标准提供者错误
    """
    error_mapping = {
        "1001": ProviderAuthError(f"认证失败: {error_message}"),
        "1002": ProviderQuotaError(f"配额不足: {error_message}"),
        "1003": ProviderRateLimitError(f"请求频率超限: {error_message}"),
        "1004": ProviderNetworkError(f"网络错误: {error_message}"),
        "1005": ProviderTimeoutError(f"请求超时: {error_message}"),
        "4001": ProviderAuthError(f"API密钥无效: {error_message}"),
        "4003": ProviderAuthError(f"访问权限不足: {error_message}"),
        "4029": ProviderRateLimitError(f"请求过于频繁: {error_message}"),
        "5000": ProviderNetworkError(f"服务器内部错误: {error_message}"),
        "5003": ProviderNetworkError(f"服务不可用: {error_message}"),
    }
    
    return error_mapping.get(volcengine_error_code, ProviderError(f"未知错误 {volcengine_error_code}: {error_message}"))


def map_openai_error(error_type: str, error_message: str = "") -> ProviderError:
    """
    将OpenAI错误映射为标准提供者错误
    
    Args:
        error_type: OpenAI错误类型
        error_message: 错误消息
        
    Returns:
        ProviderError: 标准提供者错误
    """
    error_mapping = {
        "authentication_error": ProviderAuthError(f"OpenAI认证失败: {error_message}"),
        "permission_error": ProviderAuthError(f"OpenAI权限不足: {error_message}"),
        "rate_limit_error": ProviderRateLimitError(f"OpenAI请求频率超限: {error_message}"),
        "quota_exceeded": ProviderQuotaError(f"OpenAI配额不足: {error_message}"),
        "api_connection_error": ProviderNetworkError(f"OpenAI连接错误: {error_message}"),
        "timeout": ProviderTimeoutError(f"OpenAI请求超时: {error_message}"),
        "server_error": ProviderNetworkError(f"OpenAI服务器错误: {error_message}"),
    }
    
    return error_mapping.get(error_type, ProviderError(f"OpenAI未知错误: {error_message}"))