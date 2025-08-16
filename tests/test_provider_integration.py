import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from models.core import TimedSegment
from services.speech_to_text import SpeechToTextService
from services.text_to_speech import TextToSpeechService, VoiceConfig
from services.translation_service import TranslationService
from services.provider_factory import ProviderFactory, provider_manager
from utils.provider_errors import ProviderError


class TestProviderIntegration(unittest.TestCase):
    """提供者集成测试"""
    
    def setUp(self):
        """设置测试环境"""
        # 重置提供者管理器
        provider_manager.reset_providers()
        
        # 保存原始环境变量
        self.original_env = {}
        env_vars = [
            'STT_PROVIDER', 'TTS_PROVIDER', 'TRANSLATION_PROVIDER',
            'OPENAI_API_KEY', 'VOLCENGINE_ASR_APP_ID', 'VOLCENGINE_ASR_ACCESS_TOKEN',
            'VOLCENGINE_TTS_APP_ID', 'VOLCENGINE_TTS_ACCESS_TOKEN',
            'DOUBAO_API_KEY', 'DOUBAO_BASE_URL', 'DOUBAO_MODEL'
        ]
        
        for var in env_vars:
            self.original_env[var] = os.environ.get(var)
    
    def tearDown(self):
        """清理测试环境"""
        # 恢复原始环境变量
        for var, value in self.original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]
        
        # 重置提供者管理器
        provider_manager.reset_providers()
    
    @patch('services.provider_factory.Config')
    def test_end_to_end_openai_pipeline(self, mock_config):
        """测试端到端OpenAI管道"""
        # 设置OpenAI配置
        mock_config.STT_PROVIDER = "openai"
        mock_config.TTS_PROVIDER = "openai"
        mock_config.TRANSLATION_PROVIDER = "openai"
        mock_config.OPENAI_API_KEY = "test_openai_key"
        
        # 创建测试音频文件
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(b"fake audio data")
            audio_path = temp_file.name
        
        try:
            # 模拟提供者
            with patch.object(ProviderFactory, 'create_stt_provider') as mock_stt_factory:
                with patch.object(ProviderFactory, 'create_tts_provider') as mock_tts_factory:
                    with patch.object(ProviderFactory, 'create_translation_provider') as mock_trans_factory:
                        
                        # 设置STT提供者mock
                        mock_stt_provider = Mock()
                        mock_stt_provider.transcribe.return_value = Mock(
                            text="Hello world",
                            language="en",
                            segments=[TimedSegment(0.0, 2.0, "Hello world")]
                        )
                        mock_stt_factory.return_value = mock_stt_provider
                        
                        # 设置翻译提供者mock
                        mock_trans_provider = Mock()
                        mock_trans_provider.translate_segments.return_value = Mock(
                            translated_segments=[
                                TimedSegment(0.0, 2.0, "Hello world", "你好世界")
                            ],
                            quality_score=0.9
                        )
                        mock_trans_factory.return_value = mock_trans_provider
                        
                        # 设置TTS提供者mock
                        mock_tts_provider = Mock()
                        mock_tts_provider.synthesize_speech.return_value = Mock(
                            audio_file_path="/tmp/output.mp3",
                            quality_score=0.8
                        )
                        mock_tts_factory.return_value = mock_tts_provider
                        
                        # 执行端到端测试
                        # 1. 语音转文字
                        stt_service = SpeechToTextService()
                        transcription_result = stt_service.transcribe(audio_path)
                        
                        # 2. 翻译
                        translation_service = TranslationService()
                        translation_result = translation_service.translate_segments(
                            transcription_result.segments, "zh"
                        )
                        
                        # 3. 文字转语音
                        tts_service = TextToSpeechService()
                        voice_config = VoiceConfig("zh-voice", "zh")
                        synthesis_result = tts_service.synthesize_speech(
                            translation_result.translated_segments, "zh", voice_config
                        )
                        
                        # 验证结果
                        self.assertEqual(transcription_result.text, "Hello world")
                        self.assertEqual(len(translation_result.translated_segments), 1)
                        self.assertEqual(
                            translation_result.translated_segments[0].translated_text, 
                            "你好世界"
                        )
                        self.assertIsNotNone(synthesis_result.audio_file_path)
                        
                        # 验证调用次数
                        mock_stt_provider.transcribe.assert_called_once()
                        mock_trans_provider.translate_segments.assert_called_once()
                        mock_tts_provider.synthesize_speech.assert_called_once()
        
        finally:
            os.unlink(audio_path)
    
    @patch('services.provider_factory.Config')
    def test_end_to_end_volcengine_pipeline(self, mock_config):
        """测试端到端火山云管道"""
        # 设置火山云配置
        mock_config.STT_PROVIDER = "volcengine"
        mock_config.TTS_PROVIDER = "volcengine"
        mock_config.TRANSLATION_PROVIDER = "doubao"
        mock_config.VOLCENGINE_ASR_APP_ID = "test_app_id"
        mock_config.VOLCENGINE_ASR_ACCESS_TOKEN = "test_token"
        mock_config.VOLCENGINE_TTS_APP_ID = "test_tts_app_id"
        mock_config.VOLCENGINE_TTS_ACCESS_TOKEN = "test_tts_token"
        mock_config.DOUBAO_API_KEY = "test_doubao_key"
        mock_config.DOUBAO_BASE_URL = "https://test.api.com"
        mock_config.DOUBAO_MODEL = "test-model"
        
        # 创建测试音频文件
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_file.write(b"fake audio data")
            audio_path = temp_file.name
        
        try:
            # 模拟提供者
            with patch.object(ProviderFactory, 'create_stt_provider') as mock_stt_factory:
                with patch.object(ProviderFactory, 'create_tts_provider') as mock_tts_factory:
                    with patch.object(ProviderFactory, 'create_translation_provider') as mock_trans_factory:
                        
                        # 设置提供者mocks
                        mock_stt_provider = Mock()
                        mock_stt_provider.transcribe.return_value = Mock(
                            text="你好世界",
                            language="zh",
                            segments=[TimedSegment(0.0, 2.0, "你好世界")]
                        )
                        mock_stt_factory.return_value = mock_stt_provider
                        
                        mock_trans_provider = Mock()
                        mock_trans_provider.translate_segments.return_value = Mock(
                            translated_segments=[
                                TimedSegment(0.0, 2.0, "你好世界", "Hello world")
                            ],
                            quality_score=0.9
                        )
                        mock_trans_factory.return_value = mock_trans_provider
                        
                        mock_tts_provider = Mock()
                        mock_tts_provider.synthesize_speech.return_value = Mock(
                            audio_file_path="/tmp/output.mp3",
                            quality_score=0.8
                        )
                        mock_tts_factory.return_value = mock_tts_provider
                        
                        # 执行端到端测试
                        stt_service = SpeechToTextService()
                        transcription_result = stt_service.transcribe(audio_path)
                        
                        translation_service = TranslationService()
                        translation_result = translation_service.translate_segments(
                            transcription_result.segments, "en"
                        )
                        
                        tts_service = TextToSpeechService()
                        voice_config = VoiceConfig("en-voice", "en")
                        synthesis_result = tts_service.synthesize_speech(
                            translation_result.translated_segments, "en", voice_config
                        )
                        
                        # 验证结果
                        self.assertEqual(transcription_result.text, "你好世界")
                        self.assertEqual(
                            translation_result.translated_segments[0].translated_text, 
                            "Hello world"
                        )
                        self.assertIsNotNone(synthesis_result.audio_file_path)
        
        finally:
            os.unlink(audio_path)
    
    @patch('services.provider_factory.Config')
    def test_provider_switching(self, mock_config):
        """测试提供者切换功能"""
        # 初始设置为OpenAI
        mock_config.STT_PROVIDER = "openai"
        mock_config.OPENAI_API_KEY = "test_openai_key"
        
        with patch.object(ProviderFactory, 'create_stt_provider') as mock_factory:
            mock_openai_provider = Mock()
            mock_openai_provider.transcribe.return_value = Mock(text="OpenAI result")
            
            mock_volcengine_provider = Mock()
            mock_volcengine_provider.transcribe.return_value = Mock(text="Volcengine result")
            
            # 第一次调用返回OpenAI提供者
            mock_factory.return_value = mock_openai_provider
            
            # 创建服务并测试
            stt_service = SpeechToTextService()
            result1 = stt_service.transcribe("test.mp3")
            self.assertEqual(result1.text, "OpenAI result")
            
            # 切换到火山云
            mock_config.STT_PROVIDER = "volcengine"
            mock_config.VOLCENGINE_ASR_APP_ID = "test_app_id"
            mock_config.VOLCENGINE_ASR_ACCESS_TOKEN = "test_token"
            mock_factory.return_value = mock_volcengine_provider
            
            # 重置提供者管理器以触发重新创建
            provider_manager.reset_provider("stt")
            
            # 再次调用应该使用新提供者
            result2 = stt_service.transcribe("test.mp3")
            self.assertEqual(result2.text, "Volcengine result")
    
    @patch('services.provider_factory.Config')
    def test_provider_error_handling(self, mock_config):
        """测试提供者错误处理"""
        mock_config.STT_PROVIDER = "openai"
        mock_config.OPENAI_API_KEY = "invalid_key"
        
        with patch.object(ProviderFactory, 'create_stt_provider') as mock_factory:
            # 模拟提供者创建失败
            mock_factory.side_effect = ProviderError("API密钥无效")
            
            # 验证服务初始化失败
            with self.assertRaises(Exception) as context:
                SpeechToTextService()
            
            self.assertIn("初始化语音转文字提供者失败", str(context.exception))
    
    @patch('services.provider_factory.Config')
    def test_mixed_provider_configuration(self, mock_config):
        """测试混合提供者配置"""
        # 设置混合配置：STT使用OpenAI，翻译使用豆包，TTS使用火山云
        mock_config.STT_PROVIDER = "openai"
        mock_config.TRANSLATION_PROVIDER = "doubao"
        mock_config.TTS_PROVIDER = "volcengine"
        mock_config.OPENAI_API_KEY = "test_openai_key"
        mock_config.DOUBAO_API_KEY = "test_doubao_key"
        mock_config.DOUBAO_BASE_URL = "https://test.api.com"
        mock_config.DOUBAO_MODEL = "test-model"
        mock_config.VOLCENGINE_TTS_APP_ID = "test_tts_app_id"
        mock_config.VOLCENGINE_TTS_ACCESS_TOKEN = "test_tts_token"
        
        with patch.object(ProviderFactory, 'create_stt_provider') as mock_stt_factory:
            with patch.object(ProviderFactory, 'create_tts_provider') as mock_tts_factory:
                with patch.object(ProviderFactory, 'create_translation_provider') as mock_trans_factory:
                    
                    # 设置不同的提供者实例
                    mock_openai_stt = Mock()
                    mock_doubao_trans = Mock()
                    mock_volcengine_tts = Mock()
                    
                    mock_stt_factory.return_value = mock_openai_stt
                    mock_trans_factory.return_value = mock_doubao_trans
                    mock_tts_factory.return_value = mock_volcengine_tts
                    
                    # 创建服务实例
                    stt_service = SpeechToTextService()
                    translation_service = TranslationService()
                    tts_service = TextToSpeechService()
                    
                    # 验证使用了不同的提供者
                    self.assertIs(stt_service.provider, mock_openai_stt)
                    self.assertIs(translation_service.provider, mock_doubao_trans)
                    self.assertIs(tts_service.provider, mock_volcengine_tts)
    
    def test_data_flow_consistency(self):
        """测试数据流一致性"""
        # 创建测试数据
        original_segments = [
            TimedSegment(0.0, 2.0, "Hello"),
            TimedSegment(2.0, 4.0, "world")
        ]
        
        translated_segments = [
            TimedSegment(0.0, 2.0, "Hello", "你好"),
            TimedSegment(2.0, 4.0, "world", "世界")
        ]
        
        # 验证时间信息保持一致
        for orig, trans in zip(original_segments, translated_segments):
            self.assertEqual(orig.start_time, trans.start_time)
            self.assertEqual(orig.end_time, trans.end_time)
            self.assertEqual(orig.original_text, trans.original_text)
            self.assertIsNotNone(trans.translated_text)
        
        # 验证数据结构完整性
        for segment in translated_segments:
            self.assertIsInstance(segment.start_time, float)
            self.assertIsInstance(segment.end_time, float)
            self.assertIsInstance(segment.original_text, str)
            self.assertIsInstance(segment.translated_text, str)
            self.assertGreaterEqual(segment.end_time, segment.start_time)


if __name__ == '__main__':
    unittest.main()