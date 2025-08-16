import re
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from models.core import TimedSegment
from config import Config
from services.provider_factory import provider_manager
from services.providers import TranslationResult
from utils.provider_errors import ProviderError


class TranslationServiceError(Exception):
    """文本翻译服务错误"""
    pass


# TranslationResult 现在从 providers 模块导入


class TranslationService:
    """
    文本翻译服务
    
    集成多提供者翻译功能，支持OpenAI GPT-4和豆包大模型，
    支持英语、中文、西班牙语、法语、德语。
    实现时序标记保持功能，确保翻译后文本段落与原始时序对应。
    """
    
    def __init__(self, provider_type: Optional[str] = None):
        """
        初始化翻译服务
        
        Args:
            provider_type: 指定提供者类型，如果为None则使用配置中的默认值
        """
        self.config = Config()
        
        # 如果指定了提供者类型，临时设置配置
        if provider_type:
            original_provider = self.config.TRANSLATION_PROVIDER
            self.config.TRANSLATION_PROVIDER = provider_type
        
        try:
            self.provider = provider_manager.get_translation_provider()
        except ProviderError as e:
            raise TranslationServiceError(f"初始化翻译提供者失败: {str(e)}")
        finally:
            # 恢复原始配置
            if provider_type:
                self.config.TRANSLATION_PROVIDER = original_provider
    
    def translate_segments(self, segments: List[TimedSegment], 
                          target_language: str,
                          source_language: Optional[str] = None) -> TranslationResult:
        """
        翻译时序片段
        
        Args:
            segments: 输入片段列表
            target_language: 目标语言代码
            source_language: 源语言代码（可选，将自动检测）
            
        Returns:
            TranslationResult: 翻译结果
            
        Raises:
            TranslationServiceError: 翻译失败
        """
        try:
            return self.provider.translate_segments(segments, target_language, source_language)
        except ProviderError as e:
            raise TranslationServiceError(f"翻译失败: {str(e)}")
        except Exception as e:
            raise TranslationServiceError(f"翻译失败: {str(e)}")
    
    def translate_text(self, text: str, target_language: str,
                      source_language: Optional[str] = None) -> str:
        """
        翻译单个文本
        
        Args:
            text: 待翻译文本
            target_language: 目标语言代码
            source_language: 源语言代码（可选）
            
        Returns:
            str: 翻译后的文本
            
        Raises:
            TranslationServiceError: 翻译失败
        """
        try:
            return self.provider.translate_text(text, target_language, source_language)
        except ProviderError as e:
            raise TranslationServiceError(f"文本翻译失败: {str(e)}")
        except Exception as e:
            raise TranslationServiceError(f"文本翻译失败: {str(e)}")
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        获取支持的语言列表
        
        Returns:
            Dict[str, str]: 语言代码到语言名称的映射
        """
        try:
            return self.provider.get_supported_languages()
        except Exception:
            # 如果提供者没有实现，返回默认列表
            return {
                'en': 'English',
                'zh': 'Chinese',
                'es': 'Spanish', 
                'fr': 'French',
                'de': 'German'
            }
    
    def validate_translation_quality(self, original_segments: List[TimedSegment],
                                   translated_segments: List[TimedSegment]) -> Dict[str, float]:
        """
        验证翻译质量
        
        Args:
            original_segments: 原始片段
            translated_segments: 翻译片段
            
        Returns:
            Dict[str, float]: 质量指标
        """
        try:
            # 委托给提供者处理（如果支持）
            if hasattr(self.provider, 'validate_translation_quality'):
                return self.provider.validate_translation_quality(original_segments, translated_segments)
            
            # 简单的后备实现
            if len(original_segments) != len(translated_segments):
                return {
                    'timing_accuracy': 0.0,
                    'length_consistency': 0.0,
                    'overall_score': 0.0
                }
            
            return {
                'timing_accuracy': 0.8,
                'length_consistency': 0.8,
                'overall_score': 0.8
            }
            
        except Exception:
            return {
                'timing_accuracy': 0.0,
                'length_consistency': 0.0,
                'overall_score': 0.0
            }
    
    # 以下方法现在由提供者处理，不需要在这里实现