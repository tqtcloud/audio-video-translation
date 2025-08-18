from typing import Optional
from config import Config
from utils.provider_errors import ProviderError

# OpenAI 提供者
from services.providers.openai_stt import OpenAISpeechToText
from services.providers.openai_tts import OpenAITextToSpeech
from services.providers.openai_translation import OpenAITranslation

# 火山云提供者（注释掉旧的导入，避免websocket-client依赖）
# from services.providers.volcengine_stt import VolcengineSpeechToText
# from services.providers.volcengine_stt_binary import VolcengineSpeechToTextBinary
# from services.providers.volcengine_stt_official import VolcengineSpeechToTextOfficial
# from services.providers.volcengine_tts import VolcengineTextToSpeech
from services.providers.doubao_translation import DoubaoTranslation

# 抽象基类
from services.providers import SpeechToTextProvider, TextToSpeechProvider, TranslationProvider


class ProviderFactory:
    """提供者工厂类，根据配置创建相应的服务提供者"""
    
    @staticmethod
    def create_stt_provider() -> SpeechToTextProvider:
        """
        创建语音转文字提供者
        
        Returns:
            SpeechToTextProvider: 语音转文字提供者实例
            
        Raises:
            ProviderError: 配置错误或创建失败
        """
        provider = Config.STT_PROVIDER.lower()
        
        if provider == "volcengine":
            app_id = Config.VOLCENGINE_ASR_APP_ID
            access_token = Config.VOLCENGINE_ASR_ACCESS_TOKEN
            
            if not app_id or not access_token:
                raise ProviderError("火山云ASR配置不完整，请检查 VOLCENGINE_ASR_APP_ID 和 VOLCENGINE_ASR_ACCESS_TOKEN")
            
            # 使用异步HTTP API实现（基于官方文档）
            from services.providers.volcengine_asr_async import VolcengineAsyncASR
            return VolcengineAsyncASR(
                app_id=app_id,
                access_token=access_token
            )
            
        elif provider == "openai":
            api_key = Config.OPENAI_API_KEY
            
            if not api_key:
                # 使用本地Whisper模型
                from services.providers.local_whisper_stt import LocalWhisperSpeechToText
                return LocalWhisperSpeechToText(model_size="base")
            
            return OpenAISpeechToText(api_key=api_key)
            
        elif provider == "whisper" or provider == "local":
            # 本地Whisper模型
            from services.providers.local_whisper_stt import LocalWhisperSpeechToText
            return LocalWhisperSpeechToText(model_size="base")
            
        else:
            raise ProviderError(f"不支持的STT提供者: {provider}，支持的提供者：openai, volcengine, whisper")
    
    @staticmethod
    def create_tts_provider() -> TextToSpeechProvider:
        """
        创建文字转语音提供者
        
        Returns:
            TextToSpeechProvider: 文字转语音提供者实例
            
        Raises:
            ProviderError: 配置错误或创建失败
        """
        provider = Config.TTS_PROVIDER.lower()
        
        if provider == "volcengine":
            app_id = Config.VOLCENGINE_TTS_APP_ID
            access_token = Config.VOLCENGINE_TTS_ACCESS_TOKEN
            
            if not app_id or not access_token:
                raise ProviderError("火山云TTS配置不完整，请检查 VOLCENGINE_TTS_APP_ID 和 VOLCENGINE_TTS_ACCESS_TOKEN")
            
            # 使用修复版二进制WebSocket实现
            from services.providers.volcengine_tts_fixed import VolcengineTextToSpeech as VolcengineTTSFixed
            return VolcengineTTSFixed(
                app_id=app_id,
                access_token=access_token
            )
            
        elif provider == "openai":
            api_key = Config.OPENAI_API_KEY
            
            if not api_key:
                raise ProviderError("OpenAI API密钥未设置，请检查 OPENAI_API_KEY")
            
            return OpenAITextToSpeech(api_key=api_key)
            
        else:
            raise ProviderError(f"不支持的TTS提供者: {provider}，支持的提供者：openai, volcengine")
    
    @staticmethod
    def create_translation_provider() -> TranslationProvider:
        """
        创建翻译提供者
        
        Returns:
            TranslationProvider: 翻译提供者实例
            
        Raises:
            ProviderError: 配置错误或创建失败
        """
        provider = Config.TRANSLATION_PROVIDER.lower()
        
        if provider == "doubao":
            api_key = Config.DOUBAO_API_KEY
            base_url = Config.DOUBAO_BASE_URL
            model = Config.DOUBAO_MODEL
            
            if not api_key:
                raise ProviderError("豆包API密钥未设置，请检查 DOUBAO_API_KEY")
            
            if not model:
                raise ProviderError("豆包模型未设置，请检查 DOUBAO_MODEL")
            
            return DoubaoTranslation(
                api_key=api_key,
                base_url=base_url,
                model=model
            )
            
        elif provider == "openai":
            api_key = Config.OPENAI_API_KEY
            
            if not api_key:
                raise ProviderError("OpenAI API密钥未设置，请检查 OPENAI_API_KEY")
            
            return OpenAITranslation(api_key=api_key)
            
        else:
            raise ProviderError(f"不支持的翻译提供者: {provider}，支持的提供者：openai, doubao")
    
    @staticmethod
    def get_available_providers() -> dict:
        """
        获取所有可用的提供者列表
        
        Returns:
            dict: 提供者类型到可用提供者列表的映射
        """
        return {
            "stt": ["openai", "volcengine"],
            "tts": ["openai", "volcengine"],
            "translation": ["openai", "doubao"]
        }
    
    @staticmethod
    def validate_configuration() -> dict:
        """
        验证当前配置是否完整
        
        Returns:
            dict: 验证结果，包含各个提供者的配置状态
        """
        results = {
            "stt": {"provider": Config.STT_PROVIDER, "valid": False, "error": None},
            "tts": {"provider": Config.TTS_PROVIDER, "valid": False, "error": None},
            "translation": {"provider": Config.TRANSLATION_PROVIDER, "valid": False, "error": None}
        }
        
        # 验证STT配置
        try:
            ProviderFactory.create_stt_provider()
            results["stt"]["valid"] = True
        except ProviderError as e:
            results["stt"]["error"] = str(e)
        
        # 验证TTS配置
        try:
            ProviderFactory.create_tts_provider()
            results["tts"]["valid"] = True
        except ProviderError as e:
            results["tts"]["error"] = str(e)
        
        # 验证翻译配置
        try:
            ProviderFactory.create_translation_provider()
            results["translation"]["valid"] = True
        except ProviderError as e:
            results["translation"]["error"] = str(e)
        
        return results
    
    @staticmethod
    def get_provider_info(provider_type: str) -> dict:
        """
        获取指定类型提供者的详细信息
        
        Args:
            provider_type: 提供者类型 (stt, tts, translation)
            
        Returns:
            dict: 提供者信息
            
        Raises:
            ProviderError: 无效的提供者类型
        """
        if provider_type == "stt":
            return {
                "current": Config.STT_PROVIDER,
                "available": ["openai", "volcengine"],
                "config_keys": {
                    "openai": ["OPENAI_API_KEY"],
                    "volcengine": ["VOLCENGINE_ASR_APP_ID", "VOLCENGINE_ASR_ACCESS_TOKEN"]
                }
            }
        elif provider_type == "tts":
            return {
                "current": Config.TTS_PROVIDER,
                "available": ["openai", "volcengine"],
                "config_keys": {
                    "openai": ["OPENAI_API_KEY"],
                    "volcengine": ["VOLCENGINE_TTS_APP_ID", "VOLCENGINE_TTS_ACCESS_TOKEN"]
                }
            }
        elif provider_type == "translation":
            return {
                "current": Config.TRANSLATION_PROVIDER,
                "available": ["openai", "doubao"],
                "config_keys": {
                    "openai": ["OPENAI_API_KEY"],
                    "doubao": ["DOUBAO_API_KEY", "DOUBAO_BASE_URL", "DOUBAO_MODEL"]
                }
            }
        else:
            raise ProviderError(f"无效的提供者类型: {provider_type}，支持的类型：stt, tts, translation")


class ProviderManager:
    """提供者管理器，用于管理提供者实例的生命周期"""
    
    def __init__(self):
        self._stt_provider: Optional[SpeechToTextProvider] = None
        self._tts_provider: Optional[TextToSpeechProvider] = None
        self._translation_provider: Optional[TranslationProvider] = None
        
        # 记录当前配置，用于检测配置变化
        self._current_config = {
            "stt": Config.STT_PROVIDER,
            "tts": Config.TTS_PROVIDER,
            "translation": Config.TRANSLATION_PROVIDER
        }
    
    def get_stt_provider(self) -> SpeechToTextProvider:
        """获取STT提供者实例（单例模式）"""
        if self._stt_provider is None or self._current_config["stt"] != Config.STT_PROVIDER:
            self._stt_provider = ProviderFactory.create_stt_provider()
            self._current_config["stt"] = Config.STT_PROVIDER
        
        return self._stt_provider
    
    def get_tts_provider(self) -> TextToSpeechProvider:
        """获取TTS提供者实例（单例模式）"""
        if self._tts_provider is None or self._current_config["tts"] != Config.TTS_PROVIDER:
            self._tts_provider = ProviderFactory.create_tts_provider()
            self._current_config["tts"] = Config.TTS_PROVIDER
        
        return self._tts_provider
    
    def get_translation_provider(self) -> TranslationProvider:
        """获取翻译提供者实例（单例模式）"""
        if self._translation_provider is None or self._current_config["translation"] != Config.TRANSLATION_PROVIDER:
            self._translation_provider = ProviderFactory.create_translation_provider()
            self._current_config["translation"] = Config.TRANSLATION_PROVIDER
        
        return self._translation_provider
    
    def reset_providers(self):
        """重置所有提供者实例，强制重新创建"""
        self._stt_provider = None
        self._tts_provider = None
        self._translation_provider = None
    
    def reset_provider(self, provider_type: str):
        """重置指定类型的提供者实例"""
        if provider_type == "stt":
            self._stt_provider = None
        elif provider_type == "tts":
            self._tts_provider = None
        elif provider_type == "translation":
            self._translation_provider = None
        else:
            raise ProviderError(f"无效的提供者类型: {provider_type}")


# 全局提供者管理器实例
provider_manager = ProviderManager()