import unittest
from unittest.mock import patch, Mock
import os
import tempfile
from services.provider_factory import ProviderFactory, provider_manager
from config import Config
from utils.provider_errors import ProviderError


class TestConfiguration(unittest.TestCase):
    """配置兼容性测试"""
    
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
        
        # 重置提供者管理器
        provider_manager.reset_providers()
    
    def test_openai_only_configuration(self):
        """测试仅OpenAI配置"""
        with patch('services.provider_factory.Config') as mock_config:
            mock_config.STT_PROVIDER = "openai"
            mock_config.TTS_PROVIDER = "openai"
            mock_config.TRANSLATION_PROVIDER = "openai"
            mock_config.OPENAI_API_KEY = "test_openai_key"
            
            # 验证配置
            validation_result = ProviderFactory.validate_configuration()
            
            # 所有配置应该有效（假设提供者创建成功）
            with patch.object(ProviderFactory, 'create_stt_provider', return_value=Mock()):
                with patch.object(ProviderFactory, 'create_tts_provider', return_value=Mock()):
                    with patch.object(ProviderFactory, 'create_translation_provider', return_value=Mock()):
                        validation_result = ProviderFactory.validate_configuration()
                        
                        self.assertTrue(validation_result["stt"]["valid"])
                        self.assertTrue(validation_result["tts"]["valid"])
                        self.assertTrue(validation_result["translation"]["valid"])
                        self.assertEqual(validation_result["stt"]["provider"], "openai")
                        self.assertEqual(validation_result["tts"]["provider"], "openai")
                        self.assertEqual(validation_result["translation"]["provider"], "openai")
    
    def test_volcengine_only_configuration(self):
        """测试仅火山云配置"""
        with patch('services.provider_factory.Config') as mock_config:
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
            
            with patch.object(ProviderFactory, 'create_stt_provider', return_value=Mock()):
                with patch.object(ProviderFactory, 'create_tts_provider', return_value=Mock()):
                    with patch.object(ProviderFactory, 'create_translation_provider', return_value=Mock()):
                        validation_result = ProviderFactory.validate_configuration()
                        
                        self.assertTrue(validation_result["stt"]["valid"])
                        self.assertTrue(validation_result["tts"]["valid"])
                        self.assertTrue(validation_result["translation"]["valid"])
                        self.assertEqual(validation_result["stt"]["provider"], "volcengine")
                        self.assertEqual(validation_result["tts"]["provider"], "volcengine")
                        self.assertEqual(validation_result["translation"]["provider"], "doubao")
    
    def test_mixed_provider_configuration(self):
        """测试混合提供者配置"""
        with patch('services.provider_factory.Config') as mock_config:
            # STT使用火山云，TTS使用OpenAI，翻译使用豆包
            mock_config.STT_PROVIDER = "volcengine"
            mock_config.TTS_PROVIDER = "openai"
            mock_config.TRANSLATION_PROVIDER = "doubao"
            
            # 设置所有必要的配置
            mock_config.VOLCENGINE_ASR_APP_ID = "test_app_id"
            mock_config.VOLCENGINE_ASR_ACCESS_TOKEN = "test_token"
            mock_config.OPENAI_API_KEY = "test_openai_key"
            mock_config.DOUBAO_API_KEY = "test_doubao_key"
            mock_config.DOUBAO_BASE_URL = "https://test.api.com"
            mock_config.DOUBAO_MODEL = "test-model"
            
            with patch.object(ProviderFactory, 'create_stt_provider', return_value=Mock()):
                with patch.object(ProviderFactory, 'create_tts_provider', return_value=Mock()):
                    with patch.object(ProviderFactory, 'create_translation_provider', return_value=Mock()):
                        validation_result = ProviderFactory.validate_configuration()
                        
                        self.assertTrue(validation_result["stt"]["valid"])
                        self.assertTrue(validation_result["tts"]["valid"])
                        self.assertTrue(validation_result["translation"]["valid"])
                        self.assertEqual(validation_result["stt"]["provider"], "volcengine")
                        self.assertEqual(validation_result["tts"]["provider"], "openai")
                        self.assertEqual(validation_result["translation"]["provider"], "doubao")
    
    def test_invalid_configuration_missing_keys(self):
        """测试无效配置 - 缺少密钥"""
        with patch('services.provider_factory.Config') as mock_config:
            mock_config.STT_PROVIDER = "openai"
            mock_config.TTS_PROVIDER = "openai"
            mock_config.TRANSLATION_PROVIDER = "openai"
            mock_config.OPENAI_API_KEY = ""  # 空密钥
            
            validation_result = ProviderFactory.validate_configuration()
            
            # 所有配置应该无效
            self.assertFalse(validation_result["stt"]["valid"])
            self.assertFalse(validation_result["tts"]["valid"])
            self.assertFalse(validation_result["translation"]["valid"])
            self.assertIn("API密钥", validation_result["stt"]["error"])
    
    def test_invalid_configuration_unsupported_provider(self):
        """测试无效配置 - 不支持的提供者"""
        with patch('services.provider_factory.Config') as mock_config:
            mock_config.STT_PROVIDER = "unsupported"
            mock_config.TTS_PROVIDER = "unsupported"
            mock_config.TRANSLATION_PROVIDER = "unsupported"
            
            validation_result = ProviderFactory.validate_configuration()
            
            self.assertFalse(validation_result["stt"]["valid"])
            self.assertFalse(validation_result["tts"]["valid"])
            self.assertFalse(validation_result["translation"]["valid"])
            self.assertIn("不支持", validation_result["stt"]["error"])
    
    def test_environment_variable_handling(self):
        """测试环境变量处理"""
        # 设置环境变量
        os.environ['STT_PROVIDER'] = 'openai'
        os.environ['TTS_PROVIDER'] = 'volcengine'
        os.environ['TRANSLATION_PROVIDER'] = 'doubao'
        os.environ['OPENAI_API_KEY'] = 'test_openai_key'
        os.environ['VOLCENGINE_TTS_APP_ID'] = 'test_tts_app_id'
        os.environ['VOLCENGINE_TTS_ACCESS_TOKEN'] = 'test_tts_token'
        os.environ['DOUBAO_API_KEY'] = 'test_doubao_key'
        os.environ['DOUBAO_BASE_URL'] = 'https://test.api.com'
        os.environ['DOUBAO_MODEL'] = 'test-model'
        
        # 创建配置实例
        config = Config()
        
        # 验证环境变量被正确读取
        self.assertEqual(config.STT_PROVIDER, 'openai')
        self.assertEqual(config.TTS_PROVIDER, 'volcengine')
        self.assertEqual(config.TRANSLATION_PROVIDER, 'doubao')
        self.assertEqual(config.OPENAI_API_KEY, 'test_openai_key')
        self.assertEqual(config.VOLCENGINE_TTS_APP_ID, 'test_tts_app_id')
        self.assertEqual(config.DOUBAO_API_KEY, 'test_doubao_key')
    
    def test_default_configuration_fallback(self):
        """测试默认配置回退"""
        # 不设置任何环境变量
        config = Config()
        
        # 验证默认值
        self.assertIsNotNone(config.STT_PROVIDER)
        self.assertIsNotNone(config.TTS_PROVIDER)
        self.assertIsNotNone(config.TRANSLATION_PROVIDER)
        
        # 默认应该是openai
        self.assertEqual(config.STT_PROVIDER, "openai")
        self.assertEqual(config.TTS_PROVIDER, "openai")
        self.assertEqual(config.TRANSLATION_PROVIDER, "openai")
    
    def test_provider_info_retrieval(self):
        """测试提供者信息获取"""
        # 测试STT提供者信息
        stt_info = ProviderFactory.get_provider_info("stt")
        self.assertIn("available", stt_info)
        self.assertIn("config_keys", stt_info)
        self.assertIn("openai", stt_info["available"])
        self.assertIn("volcengine", stt_info["available"])
        
        # 测试TTS提供者信息
        tts_info = ProviderFactory.get_provider_info("tts")
        self.assertIn("available", tts_info)
        self.assertIn("config_keys", tts_info)
        
        # 测试翻译提供者信息
        translation_info = ProviderFactory.get_provider_info("translation")
        self.assertIn("available", translation_info)
        self.assertIn("config_keys", translation_info)
        self.assertIn("openai", translation_info["available"])
        self.assertIn("doubao", translation_info["available"])
    
    def test_invalid_provider_info_request(self):
        """测试无效提供者信息请求"""
        with self.assertRaises(ProviderError) as context:
            ProviderFactory.get_provider_info("invalid")
        
        self.assertIn("无效的提供者类型", str(context.exception))
    
    def test_get_available_providers(self):
        """测试获取可用提供者列表"""
        providers = ProviderFactory.get_available_providers()
        
        # 验证返回的结构
        self.assertIn("stt", providers)
        self.assertIn("tts", providers)
        self.assertIn("translation", providers)
        
        # 验证每个类型的提供者列表
        self.assertIn("openai", providers["stt"])
        self.assertIn("volcengine", providers["stt"])
        self.assertIn("openai", providers["tts"])
        self.assertIn("volcengine", providers["tts"])
        self.assertIn("openai", providers["translation"])
        self.assertIn("doubao", providers["translation"])
    
    def test_configuration_file_handling(self):
        """测试配置文件处理"""
        # 创建临时配置文件
        config_content = """
STT_PROVIDER=volcengine
TTS_PROVIDER=openai
TRANSLATION_PROVIDER=doubao
OPENAI_API_KEY=test_openai_key
VOLCENGINE_ASR_APP_ID=test_app_id
VOLCENGINE_ASR_ACCESS_TOKEN=test_token
DOUBAO_API_KEY=test_doubao_key
DOUBAO_BASE_URL=https://test.api.com
DOUBAO_MODEL=test-model
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as temp_file:
            temp_file.write(config_content.strip())
            temp_file_path = temp_file.name
        
        try:
            # 模拟从配置文件加载（这里简化为手动设置环境变量）
            lines = config_content.strip().split('\n')
            for line in lines:
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
            
            config = Config()
            
            # 验证配置被正确加载
            self.assertEqual(config.STT_PROVIDER, 'volcengine')
            self.assertEqual(config.TTS_PROVIDER, 'openai')
            self.assertEqual(config.TRANSLATION_PROVIDER, 'doubao')
            self.assertEqual(config.OPENAI_API_KEY, 'test_openai_key')
            
        finally:
            os.unlink(temp_file_path)
    
    def test_partial_configuration_validation(self):
        """测试部分配置验证"""
        with patch('services.provider_factory.Config') as mock_config:
            # 只配置STT，其他使用默认或无效配置
            mock_config.STT_PROVIDER = "openai"
            mock_config.TTS_PROVIDER = "openai"
            mock_config.TRANSLATION_PROVIDER = "openai"
            mock_config.OPENAI_API_KEY = "test_key"
            
            # 模拟STT配置有效，但TTS和翻译配置无效
            with patch.object(ProviderFactory, 'create_stt_provider', return_value=Mock()):
                with patch.object(ProviderFactory, 'create_tts_provider', side_effect=ProviderError("TTS错误")):
                    with patch.object(ProviderFactory, 'create_translation_provider', side_effect=ProviderError("翻译错误")):
                        validation_result = ProviderFactory.validate_configuration()
                        
                        self.assertTrue(validation_result["stt"]["valid"])
                        self.assertFalse(validation_result["tts"]["valid"])
                        self.assertFalse(validation_result["translation"]["valid"])
                        self.assertEqual(validation_result["tts"]["error"], "TTS错误")
                        self.assertEqual(validation_result["translation"]["error"], "翻译错误")


if __name__ == '__main__':
    unittest.main()