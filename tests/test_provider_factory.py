import unittest
from unittest.mock import patch, Mock
import os
from services.provider_factory import ProviderFactory, ProviderManager
from services.providers.openai_stt import OpenAISpeechToText
from services.providers.openai_tts import OpenAITextToSpeech
from services.providers.openai_translation import OpenAITranslation
from services.providers.volcengine_stt import VolcengineSpeechToText
from services.providers.volcengine_tts import VolcengineTextToSpeech
from services.providers.doubao_translation import DoubaoTranslation
from utils.provider_errors import ProviderError


class TestProviderFactory(unittest.TestCase):
    
    def setUp(self):
        """设置测试环境"""
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
            if var in os.environ:
                del os.environ[var]
    
    def tearDown(self):
        """清理测试环境"""
        # 恢复原始环境变量
        for var, value in self.original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]
    
    @patch('services.provider_factory.Config')
    def test_create_stt_provider_openai(self, mock_config):
        """测试创建OpenAI STT提供者"""
        mock_config.STT_PROVIDER = "openai"
        mock_config.OPENAI_API_KEY = "test_openai_key"
        
        provider = ProviderFactory.create_stt_provider()
        
        self.assertIsInstance(provider, OpenAISpeechToText)
    
    @patch('services.provider_factory.Config')
    def test_create_stt_provider_volcengine(self, mock_config):
        """测试创建火山云STT提供者"""
        mock_config.STT_PROVIDER = "volcengine"
        mock_config.VOLCENGINE_ASR_APP_ID = "test_app_id"
        mock_config.VOLCENGINE_ASR_ACCESS_TOKEN = "test_token"
        
        provider = ProviderFactory.create_stt_provider()
        
        self.assertIsInstance(provider, VolcengineSpeechToText)
    
    @patch('services.provider_factory.Config')
    def test_create_stt_provider_openai_missing_key(self, mock_config):
        """测试创建OpenAI STT提供者时缺少API密钥"""
        mock_config.STT_PROVIDER = "openai"
        mock_config.OPENAI_API_KEY = ""
        
        with self.assertRaises(ProviderError) as context:
            ProviderFactory.create_stt_provider()
        
        self.assertIn("OpenAI API密钥未设置", str(context.exception))
    
    @patch('services.provider_factory.Config')
    def test_create_stt_provider_volcengine_missing_config(self, mock_config):
        """测试创建火山云STT提供者时缺少配置"""
        mock_config.STT_PROVIDER = "volcengine"
        mock_config.VOLCENGINE_ASR_APP_ID = ""
        mock_config.VOLCENGINE_ASR_ACCESS_TOKEN = "test_token"
        
        with self.assertRaises(ProviderError) as context:
            ProviderFactory.create_stt_provider()
        
        self.assertIn("火山云ASR配置不完整", str(context.exception))
    
    @patch('services.provider_factory.Config')
    def test_create_stt_provider_unsupported(self, mock_config):
        """测试创建不支持的STT提供者"""
        mock_config.STT_PROVIDER = "unsupported"
        
        with self.assertRaises(ProviderError) as context:
            ProviderFactory.create_stt_provider()
        
        self.assertIn("不支持的STT提供者", str(context.exception))
    
    @patch('services.provider_factory.Config')
    def test_create_tts_provider_openai(self, mock_config):
        """测试创建OpenAI TTS提供者"""
        mock_config.TTS_PROVIDER = "openai"
        mock_config.OPENAI_API_KEY = "test_openai_key"
        
        provider = ProviderFactory.create_tts_provider()
        
        self.assertIsInstance(provider, OpenAITextToSpeech)
    
    @patch('services.provider_factory.Config')
    def test_create_tts_provider_volcengine(self, mock_config):
        """测试创建火山云TTS提供者"""
        mock_config.TTS_PROVIDER = "volcengine"
        mock_config.VOLCENGINE_TTS_APP_ID = "test_app_id"
        mock_config.VOLCENGINE_TTS_ACCESS_TOKEN = "test_token"
        
        provider = ProviderFactory.create_tts_provider()
        
        self.assertIsInstance(provider, VolcengineTextToSpeech)
    
    @patch('services.provider_factory.Config')
    def test_create_translation_provider_openai(self, mock_config):
        """测试创建OpenAI翻译提供者"""
        mock_config.TRANSLATION_PROVIDER = "openai"
        mock_config.OPENAI_API_KEY = "test_openai_key"
        
        provider = ProviderFactory.create_translation_provider()
        
        self.assertIsInstance(provider, OpenAITranslation)
    
    @patch('services.provider_factory.Config')
    def test_create_translation_provider_doubao(self, mock_config):
        """测试创建豆包翻译提供者"""
        mock_config.TRANSLATION_PROVIDER = "doubao"
        mock_config.DOUBAO_API_KEY = "test_doubao_key"
        mock_config.DOUBAO_BASE_URL = "https://test.api.com"
        mock_config.DOUBAO_MODEL = "test-model"
        
        provider = ProviderFactory.create_translation_provider()
        
        self.assertIsInstance(provider, DoubaoTranslation)
    
    @patch('services.provider_factory.Config')
    def test_create_translation_provider_doubao_missing_config(self, mock_config):
        """测试创建豆包翻译提供者时缺少配置"""
        mock_config.TRANSLATION_PROVIDER = "doubao"
        mock_config.DOUBAO_API_KEY = ""
        mock_config.DOUBAO_BASE_URL = "https://test.api.com"
        mock_config.DOUBAO_MODEL = "test-model"
        
        with self.assertRaises(ProviderError) as context:
            ProviderFactory.create_translation_provider()
        
        self.assertIn("豆包API密钥未设置", str(context.exception))
    
    def test_get_available_providers(self):
        """测试获取可用提供者列表"""
        providers = ProviderFactory.get_available_providers()
        
        expected_providers = {
            "stt": ["openai", "volcengine"],
            "tts": ["openai", "volcengine"],
            "translation": ["openai", "doubao"]
        }
        
        self.assertEqual(providers, expected_providers)
    
    @patch('services.provider_factory.Config')
    def test_validate_configuration_all_valid(self, mock_config):
        """测试验证配置 - 全部有效"""
        # 模拟有效配置
        mock_config.STT_PROVIDER = "openai"
        mock_config.TTS_PROVIDER = "openai"
        mock_config.TRANSLATION_PROVIDER = "openai"
        mock_config.OPENAI_API_KEY = "test_key"
        
        with patch.object(ProviderFactory, 'create_stt_provider', return_value=Mock()):
            with patch.object(ProviderFactory, 'create_tts_provider', return_value=Mock()):
                with patch.object(ProviderFactory, 'create_translation_provider', return_value=Mock()):
                    results = ProviderFactory.validate_configuration()
        
        self.assertTrue(results["stt"]["valid"])
        self.assertTrue(results["tts"]["valid"])
        self.assertTrue(results["translation"]["valid"])
        self.assertIsNone(results["stt"]["error"])
        self.assertIsNone(results["tts"]["error"])
        self.assertIsNone(results["translation"]["error"])
    
    @patch('services.provider_factory.Config')
    def test_validate_configuration_with_errors(self, mock_config):
        """测试验证配置 - 包含错误"""
        mock_config.STT_PROVIDER = "openai"
        mock_config.TTS_PROVIDER = "openai"
        mock_config.TRANSLATION_PROVIDER = "openai"
        
        with patch.object(ProviderFactory, 'create_stt_provider', side_effect=ProviderError("STT错误")):
            with patch.object(ProviderFactory, 'create_tts_provider', return_value=Mock()):
                with patch.object(ProviderFactory, 'create_translation_provider', side_effect=ProviderError("翻译错误")):
                    results = ProviderFactory.validate_configuration()
        
        self.assertFalse(results["stt"]["valid"])
        self.assertTrue(results["tts"]["valid"])
        self.assertFalse(results["translation"]["valid"])
        self.assertEqual(results["stt"]["error"], "STT错误")
        self.assertIsNone(results["tts"]["error"])
        self.assertEqual(results["translation"]["error"], "翻译错误")
    
    @patch('services.provider_factory.Config')
    def test_get_provider_info_stt(self, mock_config):
        """测试获取STT提供者信息"""
        mock_config.STT_PROVIDER = "openai"
        
        info = ProviderFactory.get_provider_info("stt")
        
        expected_info = {
            "current": "openai",
            "available": ["openai", "volcengine"],
            "config_keys": {
                "openai": ["OPENAI_API_KEY"],
                "volcengine": ["VOLCENGINE_ASR_APP_ID", "VOLCENGINE_ASR_ACCESS_TOKEN"]
            }
        }
        
        self.assertEqual(info, expected_info)
    
    def test_get_provider_info_invalid_type(self):
        """测试获取无效类型的提供者信息"""
        with self.assertRaises(ProviderError) as context:
            ProviderFactory.get_provider_info("invalid")
        
        self.assertIn("无效的提供者类型", str(context.exception))


class TestProviderManager(unittest.TestCase):
    
    def setUp(self):
        """设置测试环境"""
        self.manager = ProviderManager()
    
    @patch('services.provider_factory.Config')
    @patch.object(ProviderFactory, 'create_stt_provider')
    def test_get_stt_provider_singleton(self, mock_create_stt, mock_config):
        """测试STT提供者单例模式"""
        mock_config.STT_PROVIDER = "openai"
        mock_provider = Mock()
        mock_create_stt.return_value = mock_provider
        
        # 第一次调用
        provider1 = self.manager.get_stt_provider()
        
        # 第二次调用
        provider2 = self.manager.get_stt_provider()
        
        # 应该返回同一个实例
        self.assertIs(provider1, provider2)
        
        # 工厂方法只应该被调用一次
        mock_create_stt.assert_called_once()
    
    @patch('services.provider_factory.Config')
    @patch.object(ProviderFactory, 'create_stt_provider')
    def test_get_stt_provider_config_change(self, mock_create_stt, mock_config):
        """测试配置变化时重新创建提供者"""
        # 初始配置
        mock_config.STT_PROVIDER = "openai"
        mock_provider1 = Mock()
        mock_create_stt.return_value = mock_provider1
        
        # 第一次调用
        provider1 = self.manager.get_stt_provider()
        
        # 更改配置
        mock_config.STT_PROVIDER = "volcengine"
        mock_provider2 = Mock()
        mock_create_stt.return_value = mock_provider2
        
        # 第二次调用
        provider2 = self.manager.get_stt_provider()
        
        # 应该返回不同的实例
        self.assertIsNot(provider1, provider2)
        
        # 工厂方法应该被调用两次
        self.assertEqual(mock_create_stt.call_count, 2)
    
    def test_reset_providers(self):
        """测试重置所有提供者"""
        # 设置一些模拟提供者
        self.manager._stt_provider = Mock()
        self.manager._tts_provider = Mock()
        self.manager._translation_provider = Mock()
        
        # 重置
        self.manager.reset_providers()
        
        # 验证所有提供者都被重置
        self.assertIsNone(self.manager._stt_provider)
        self.assertIsNone(self.manager._tts_provider)
        self.assertIsNone(self.manager._translation_provider)
    
    def test_reset_provider_stt(self):
        """测试重置特定类型的提供者"""
        # 设置一些模拟提供者
        self.manager._stt_provider = Mock()
        self.manager._tts_provider = Mock()
        self.manager._translation_provider = Mock()
        
        # 重置STT提供者
        self.manager.reset_provider("stt")
        
        # 验证只有STT提供者被重置
        self.assertIsNone(self.manager._stt_provider)
        self.assertIsNotNone(self.manager._tts_provider)
        self.assertIsNotNone(self.manager._translation_provider)
    
    def test_reset_provider_invalid_type(self):
        """测试重置无效类型的提供者"""
        with self.assertRaises(ProviderError) as context:
            self.manager.reset_provider("invalid")
        
        self.assertIn("无效的提供者类型", str(context.exception))


if __name__ == '__main__':
    unittest.main()