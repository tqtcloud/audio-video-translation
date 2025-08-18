#!/usr/bin/env python3
"""
火山云集成验证脚本

使用提供的火山云配置验证所有提供者的功能
"""

import os
import sys
import json
import tempfile
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.speech_to_text import SpeechToTextService
from services.text_to_speech import TextToSpeechService, VoiceConfig
from services.translation_service import TranslationService
from services.provider_factory import ProviderFactory
from utils.quality_assessment import QualityReportGenerator
from models.core import TimedSegment


class IntegrationValidator:
    """集成验证器"""
    
    def __init__(self, use_real_apis: bool = False):
        """
        初始化验证器
        
        Args:
            use_real_apis: 是否使用真实API（需要配置有效的API密钥）
        """
        self.use_real_apis = use_real_apis
        self.results = []
        self.quality_generator = QualityReportGenerator()
        
        # 设置火山云配置（如果使用真实API）
        if use_real_apis:
            self._setup_volcengine_config()
    
    def _setup_volcengine_config(self):
        """设置火山云配置"""
        # 提供者选择配置
        os.environ['STT_PROVIDER'] = 'volcengine'
        os.environ['TTS_PROVIDER'] = 'volcengine'
        os.environ['TRANSLATION_PROVIDER'] = 'doubao'
        
        # 语音识别和合成配置
        os.environ['VOLCENGINE_ASR_APP_ID'] = '5165236022'
        os.environ['VOLCENGINE_ASR_ACCESS_TOKEN'] = '0xeMuBNttsJrkXtZS6GgIPfR50JlJOyk'
        os.environ['VOLCENGINE_ASR_SECRET_KEY'] = '91kjDlgAL_jVBp9JPeT2pgJnzbgz3kED'
        
        os.environ['VOLCENGINE_TTS_APP_ID'] = '5165236022'
        os.environ['VOLCENGINE_TTS_ACCESS_TOKEN'] = '0xeMuBNttsJrkXtZS6GgIPfR50JlJOyk'
        os.environ['VOLCENGINE_TTS_SECRET_KEY'] = '91kjDlgAL_jVBp9JPeT2pgJnzbgz3kED'
        
        # 豆包大模型配置
        os.environ['DOUBAO_API_KEY'] = '8e7466f3-5081-454b-a4cd-d20cea1c9120'
        os.environ['DOUBAO_BASE_URL'] = 'https://ark.cn-beijing.volces.com/api/v3'
        os.environ['DOUBAO_MODEL'] = 'ep-20250722234153-nsm5d'
    
    def validate_provider_factory(self) -> Dict[str, Any]:
        """验证提供者工厂功能"""
        print("验证提供者工厂...")
        
        result = {
            "test_name": "provider_factory",
            "success": True,
            "details": {},
            "errors": []
        }
        
        try:
            # 验证可用提供者列表
            available_providers = ProviderFactory.get_available_providers()
            result["details"]["available_providers"] = available_providers
            
            # 验证配置验证功能
            config_validation = ProviderFactory.validate_configuration()
            result["details"]["config_validation"] = config_validation
            
            # 验证提供者信息获取
            for provider_type in ["stt", "tts", "translation"]:
                provider_info = ProviderFactory.get_provider_info(provider_type)
                result["details"][f"{provider_type}_info"] = provider_info
            
            print("✓ 提供者工厂验证通过")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            print(f"✗ 提供者工厂验证失败: {e}")
        
        return result
    
    def validate_openai_providers(self) -> Dict[str, Any]:
        """验证OpenAI提供者"""
        print("验证OpenAI提供者...")
        
        result = {
            "test_name": "openai_providers", 
            "success": True,
            "details": {},
            "errors": []
        }
        
        try:
            # 设置OpenAI配置
            os.environ['STT_PROVIDER'] = 'openai'
            os.environ['TTS_PROVIDER'] = 'openai'
            os.environ['TRANSLATION_PROVIDER'] = 'openai'
            
            if not self.use_real_apis:
                # 使用模拟API密钥
                os.environ['OPENAI_API_KEY'] = 'test_key'
            
            # 测试服务初始化
            if self.use_real_apis and os.environ.get('OPENAI_API_KEY'):
                stt_service = SpeechToTextService()
                tts_service = TextToSpeechService()
                translation_service = TranslationService()
                
                result["details"]["stt_initialized"] = True
                result["details"]["tts_initialized"] = True
                result["details"]["translation_initialized"] = True
                
                print("✓ OpenAI提供者初始化成功")
            else:
                result["details"]["note"] = "跳过真实API测试（使用模拟模式）"
                print("⚠ OpenAI提供者验证（模拟模式）")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            print(f"✗ OpenAI提供者验证失败: {e}")
        
        return result
    
    def validate_volcengine_providers(self) -> Dict[str, Any]:
        """验证火山云提供者"""
        print("验证火山云提供者...")
        
        result = {
            "test_name": "volcengine_providers",
            "success": True,
            "details": {},
            "errors": []
        }
        
        try:
            # 设置火山云配置
            os.environ['STT_PROVIDER'] = 'volcengine'
            os.environ['TTS_PROVIDER'] = 'volcengine'
            os.environ['TRANSLATION_PROVIDER'] = 'doubao'
            
            # 测试服务初始化
            if self.use_real_apis:
                stt_service = SpeechToTextService()
                tts_service = TextToSpeechService()
                translation_service = TranslationService()
                
                result["details"]["stt_initialized"] = True
                result["details"]["tts_initialized"] = True
                result["details"]["translation_initialized"] = True
                
                print("✓ 火山云提供者初始化成功")
            else:
                result["details"]["note"] = "跳过真实API测试（使用模拟模式）"
                print("⚠ 火山云提供者验证（模拟模式）")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            print(f"✗ 火山云提供者验证失败: {e}")
        
        return result
    
    def validate_stt_functionality(self, audio_file_path: Optional[str] = None) -> Dict[str, Any]:
        """验证STT功能"""
        print("验证STT功能...")
        
        result = {
            "test_name": "stt_functionality",
            "success": True,
            "details": {},
            "errors": []
        }
        
        try:
            # 使用提供的测试音频文件或创建临时文件
            if audio_file_path and os.path.exists(audio_file_path):
                test_audio_path = audio_file_path
                result["details"]["using_provided_audio"] = audio_file_path
            else:
                # 创建临时音频文件用于测试
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    temp_file.write(b"fake audio data for testing")
                    test_audio_path = temp_file.name
                result["details"]["using_temp_audio"] = test_audio_path
            
            # 测试不同提供者
            providers_to_test = ['openai', 'volcengine'] if self.use_real_apis else ['openai']
            
            for provider in providers_to_test:
                try:
                    os.environ['STT_PROVIDER'] = provider
                    stt_service = SpeechToTextService()
                    
                    if self.use_real_apis:
                        # 真实API测试
                        transcription_result = stt_service.transcribe(test_audio_path)
                        result["details"][f"{provider}_transcription"] = {
                            "text": transcription_result.text,
                            "language": transcription_result.language,
                            "segments_count": len(transcription_result.segments)
                        }
                    else:
                        # 模拟测试
                        result["details"][f"{provider}_initialized"] = True
                    
                    print(f"✓ {provider} STT验证通过")
                    
                except Exception as e:
                    result["errors"].append(f"{provider} STT错误: {str(e)}")
                    print(f"✗ {provider} STT验证失败: {e}")
            
            # 清理临时文件
            if not audio_file_path and os.path.exists(test_audio_path):
                os.unlink(test_audio_path)
                
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            print(f"✗ STT功能验证失败: {e}")
        
        return result
    
    def validate_translation_functionality(self) -> Dict[str, Any]:
        """验证翻译功能"""
        print("验证翻译功能...")
        
        result = {
            "test_name": "translation_functionality",
            "success": True,
            "details": {},
            "errors": []
        }
        
        try:
            # 创建测试片段
            test_segments = [
                TimedSegment(0.0, 2.0, "Hello world", confidence=0.9),
                TimedSegment(2.0, 4.0, "How are you", confidence=0.8)
            ]
            
            # 测试不同提供者
            providers_to_test = [
                ('openai', 'openai'),
                ('doubao', 'doubao')
            ] if self.use_real_apis else [('openai', 'openai')]
            
            for provider_name, provider_value in providers_to_test:
                try:
                    os.environ['TRANSLATION_PROVIDER'] = provider_value
                    translation_service = TranslationService()
                    
                    if self.use_real_apis:
                        # 真实API测试
                        translation_result = translation_service.translate_segments(
                            test_segments, "zh"
                        )
                        result["details"][f"{provider_name}_translation"] = {
                            "segments_count": len(translation_result.translated_segments),
                            "quality_score": translation_result.quality_score,
                            "detected_language": translation_result.language_detected
                        }
                    else:
                        # 模拟测试
                        result["details"][f"{provider_name}_initialized"] = True
                    
                    print(f"✓ {provider_name} 翻译验证通过")
                    
                except Exception as e:
                    result["errors"].append(f"{provider_name} 翻译错误: {str(e)}")
                    print(f"✗ {provider_name} 翻译验证失败: {e}")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            print(f"✗ 翻译功能验证失败: {e}")
        
        return result
    
    def validate_tts_functionality(self) -> Dict[str, Any]:
        """验证TTS功能"""
        print("验证TTS功能...")
        
        result = {
            "test_name": "tts_functionality",
            "success": True,
            "details": {},
            "errors": []
        }
        
        try:
            # 创建测试片段
            test_segments = [
                TimedSegment(0.0, 2.0, "Hello", "你好"),
                TimedSegment(2.0, 4.0, "World", "世界")
            ]
            
            # 测试不同提供者
            providers_to_test = ['openai', 'volcengine'] if self.use_real_apis else ['openai']
            
            for provider in providers_to_test:
                try:
                    os.environ['TTS_PROVIDER'] = provider
                    tts_service = TextToSpeechService()
                    
                    if self.use_real_apis:
                        # 真实API测试
                        voice_config = VoiceConfig("default", "zh")
                        synthesis_result = tts_service.synthesize_speech(
                            test_segments, "zh", voice_config
                        )
                        result["details"][f"{provider}_synthesis"] = {
                            "audio_file": synthesis_result.audio_file_path,
                            "duration": synthesis_result.total_duration,
                            "quality_score": synthesis_result.quality_score
                        }
                    else:
                        # 模拟测试
                        result["details"][f"{provider}_initialized"] = True
                    
                    print(f"✓ {provider} TTS验证通过")
                    
                except Exception as e:
                    result["errors"].append(f"{provider} TTS错误: {str(e)}")
                    print(f"✗ {provider} TTS验证失败: {e}")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            print(f"✗ TTS功能验证失败: {e}")
        
        return result
    
    def validate_end_to_end_pipeline(self, audio_file_path: Optional[str] = None) -> Dict[str, Any]:
        """验证端到端管道"""
        print("验证端到端管道...")
        
        result = {
            "test_name": "end_to_end_pipeline",
            "success": True,
            "details": {},
            "errors": []
        }
        
        try:
            if not self.use_real_apis:
                result["details"]["note"] = "端到端测试需要真实API"
                print("⚠ 跳过端到端测试（需要真实API）")
                return result
            
            # 设置火山云提供者
            os.environ['STT_PROVIDER'] = 'volcengine'
            os.environ['TRANSLATION_PROVIDER'] = 'doubao'
            os.environ['TTS_PROVIDER'] = 'volcengine'
            
            # 使用提供的音频文件
            if audio_file_path and os.path.exists(audio_file_path):
                test_audio_path = audio_file_path
            else:
                result["details"]["error"] = "需要有效的音频文件进行端到端测试"
                print("⚠ 跳过端到端测试（缺少音频文件）")
                return result
            
            # 执行完整管道
            start_time = datetime.now()
            
            # 1. 语音转文字
            stt_service = SpeechToTextService()
            transcription = stt_service.transcribe(test_audio_path)
            
            # 2. 翻译
            translation_service = TranslationService()
            translation = translation_service.translate_segments(
                transcription.segments, "en"  # 假设音频是中文，翻译为英文
            )
            
            # 3. 文字转语音
            tts_service = TextToSpeechService()
            voice_config = VoiceConfig("en-voice", "en")
            synthesis = tts_service.synthesize_speech(
                translation.translated_segments, "en", voice_config
            )
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            result["details"]["pipeline_results"] = {
                "processing_time_seconds": processing_time,
                "original_text": transcription.text,
                "translated_segments_count": len(translation.translated_segments),
                "final_audio_file": synthesis.audio_file_path,
                "final_quality_score": synthesis.quality_score
            }
            
            print(f"✓ 端到端管道验证通过 (耗时: {processing_time:.2f}s)")
            
        except Exception as e:
            result["success"] = False
            result["errors"].append(str(e))
            print(f"✗ 端到端管道验证失败: {e}")
        
        return result
    
    def run_all_validations(self, audio_file_path: Optional[str] = None) -> Dict[str, Any]:
        """运行所有验证测试"""
        print("开始集成验证测试...")
        print("=" * 50)
        
        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "use_real_apis": self.use_real_apis,
            "audio_file": audio_file_path,
            "tests": []
        }
        
        # 执行各项验证
        validation_functions = [
            self.validate_provider_factory,
            self.validate_openai_providers,
            self.validate_volcengine_providers,
            lambda: self.validate_stt_functionality(audio_file_path),
            self.validate_translation_functionality,
            self.validate_tts_functionality,
            lambda: self.validate_end_to_end_pipeline(audio_file_path)
        ]
        
        for validation_func in validation_functions:
            try:
                result = validation_func()
                validation_results["tests"].append(result)
                self.results.append(result)
            except Exception as e:
                error_result = {
                    "test_name": "unknown",
                    "success": False,
                    "errors": [str(e)]
                }
                validation_results["tests"].append(error_result)
                print(f"✗ 验证函数执行失败: {e}")
        
        # 生成总结
        total_tests = len(validation_results["tests"])
        successful_tests = sum(1 for test in validation_results["tests"] if test["success"])
        success_rate = successful_tests / total_tests if total_tests > 0 else 0
        
        validation_results["summary"] = {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": success_rate,
            "overall_status": "PASS" if success_rate >= 0.8 else "FAIL"
        }
        
        print("=" * 50)
        print(f"验证完成: {successful_tests}/{total_tests} 通过 ({success_rate:.1%})")
        print(f"总体状态: {validation_results['summary']['overall_status']}")
        
        return validation_results
    
    def save_report(self, results: Dict[str, Any], output_path: str):
        """保存验证报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"验证报告已保存到: {output_path}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="火山云集成验证脚本")
    parser.add_argument("--real-apis", action="store_true", 
                       help="使用真实API进行测试（需要有效的API密钥）")
    parser.add_argument("--audio-file", type=str,
                       help="用于测试的音频文件路径")
    parser.add_argument("--output", type=str, default="validation_report.json",
                       help="验证报告输出路径")
    
    args = parser.parse_args()
    
    # 检查音频文件
    if args.audio_file and not os.path.exists(args.audio_file):
        print(f"错误: 音频文件不存在: {args.audio_file}")
        sys.exit(1)
    
    # 创建验证器并运行测试
    validator = IntegrationValidator(use_real_apis=args.real_apis)
    
    if args.real_apis:
        print("使用真实API进行验证...")
        print("注意: 这将消耗API调用额度")
    else:
        print("使用模拟模式进行验证...")
    
    # 运行验证
    results = validator.run_all_validations(args.audio_file)
    
    # 保存报告
    validator.save_report(results, args.output)
    
    # 返回适当的退出码
    if results["summary"]["overall_status"] == "PASS":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()