from typing import Dict, List, Any, Optional
from models.core import TimedSegment
from services.providers import TranscriptionResult, SpeechSynthesisResult, TranslationResult


class VolcengineSTTAdapter:
    """火山云语音识别响应适配器"""
    
    @staticmethod
    def adapt_response(volcengine_response: Dict[str, Any]) -> TranscriptionResult:
        """
        将火山云ASR响应转换为标准格式
        
        Args:
            volcengine_response: 火山云API响应
            
        Returns:
            TranscriptionResult: 标准转录结果
        """
        # 火山云响应格式示例：
        # {
        #     "message": "success",
        #     "result": {
        #         "text": "转录文本",
        #         "language": "zh",
        #         "duration": 10.5,
        #         "utterances": [
        #             {
        #                 "text": "片段文本",
        #                 "start_time": 0.0,
        #                 "end_time": 2.5,
        #                 "confidence": 0.95
        #             }
        #         ]
        #     }
        # }
        
        result = volcengine_response.get("result", {})
        text = result.get("text", "")
        language = result.get("language", "")
        duration = result.get("duration", 0.0)
        
        segments = []
        utterances = result.get("utterances", [])
        
        for i, utterance in enumerate(utterances):
            segment = TimedSegment(
                start_time=utterance.get("start_time", 0.0),
                end_time=utterance.get("end_time", 0.0),
                original_text=utterance.get("text", ""),
                confidence=utterance.get("confidence", 0.0),
                speaker_id=f"speaker_{i % 2}"  # 简单的说话人分配
            )
            segments.append(segment)
        
        return TranscriptionResult(
            text=text,
            language=language,
            duration=duration,
            segments=segments
        )


class VolcengineTTSAdapter:
    """火山云语音合成请求适配器"""
    
    @staticmethod
    def adapt_request(segments: List[TimedSegment], language: str, voice_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        将标准请求转换为火山云TTS格式
        
        Args:
            segments: 时序片段列表
            language: 语言代码
            voice_config: 语音配置
            
        Returns:
            Dict: 火山云TTS请求格式
        """
        voice_config = voice_config or {}
        
        # 火山云TTS请求格式
        request_data = {
            "app": {
                "appid": "",  # 将由具体实现填充
                "cluster": "volcano_tts",
                "token": ""   # 将由具体实现填充
            },
            "user": {
                "uid": "audio_translation_user"
            },
            "audio": {
                "voice_type": voice_config.get("voice_id", "zh_female_shuangkuaixiaofang_moon_bigtts"),
                "encoding": "mp3",
                "speed_ratio": voice_config.get("speed", 1.0),
                "volume_ratio": voice_config.get("volume", 1.0),
                "pitch_ratio": voice_config.get("pitch", 1.0)
            },
            "request": {
                "reqid": "",  # 将由具体实现生成
                "text": "",   # 将由具体实现填充
                "text_type": "plain",
                "operation": "query"
            }
        }
        
        return request_data
    
    @staticmethod
    def adapt_voice_mapping(language: str) -> Dict[str, str]:
        """
        获取火山云语音映射
        
        Args:
            language: 语言代码
            
        Returns:
            Dict: 语音类型映射
        """
        voice_mapping = {
            'zh': {
                'male': 'zh_male_jingqiangxiaoming_moon_bigtts',
                'female': 'zh_female_shuangkuaixiaofang_moon_bigtts',
                'default': 'zh_female_shuangkuaixiaofang_moon_bigtts'
            },
            'en': {
                'male': 'en_male_adam_basic',
                'female': 'en_female_sara_basic', 
                'default': 'en_female_sara_basic'
            }
        }
        
        return voice_mapping.get(language, voice_mapping['en'])


class DoubaoAdapter:
    """豆包大模型适配器"""
    
    @staticmethod
    def adapt_translation_request(text: str, source_language: str, target_language: str) -> Dict[str, Any]:
        """
        将翻译请求转换为豆包API格式（OpenAI兼容）
        
        Args:
            text: 待翻译文本
            source_language: 源语言
            target_language: 目标语言
            
        Returns:
            Dict: 豆包API请求格式
        """
        language_names = {
            'en': 'English',
            'zh': 'Chinese', 
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German'
        }
        
        source_lang_name = language_names.get(source_language, source_language)
        target_lang_name = language_names.get(target_language, target_language)
        
        prompt = f"请将以下{source_lang_name}文本翻译成{target_lang_name}，保持原意准确，语言自然流畅：\n\n{text}"
        
        return {
            "model": "",  # 将由具体实现填充
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的翻译助手，专门提供准确、自然的翻译服务。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }
    
    @staticmethod
    def adapt_batch_translation_request(segments: List[TimedSegment], source_language: str, target_language: str) -> Dict[str, Any]:
        """
        将批处理翻译请求转换为豆包API格式
        
        Args:
            segments: 时序片段列表
            source_language: 源语言
            target_language: 目标语言
            
        Returns:
            Dict: 豆包API请求格式
        """
        language_names = {
            'en': 'English',
            'zh': 'Chinese',
            'es': 'Spanish', 
            'fr': 'French',
            'de': 'German'
        }
        
        source_lang_name = language_names.get(source_language, source_language)
        target_lang_name = language_names.get(target_language, target_language)
        
        # 创建编号文本列表
        numbered_texts = []
        for i, segment in enumerate(segments):
            numbered_texts.append(f"{i+1}. {segment.original_text}")
        
        combined_text = "\n".join(numbered_texts)
        
        prompt = f"""请将以下{source_lang_name}文本翻译成{target_lang_name}。保持原有的编号，每行一个翻译：

{combined_text}

翻译要求：
1. 保持原意准确
2. 语言自然流畅
3. 保持编号格式
4. 每行对应一个翻译结果"""
        
        return {
            "model": "",  # 将由具体实现填充
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的翻译助手，专门提供准确、自然的翻译服务。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }