import re
import time
import requests
import json
from typing import List, Optional
from models.core import TimedSegment
from services.providers import TranslationProvider, TranslationResult
from models.adapters import DoubaoAdapter
from utils.provider_errors import ProviderError, map_volcengine_error


class DoubaoTranslation(TranslationProvider):
    """豆包大模型翻译提供者"""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        if not api_key or not base_url or not model:
            raise ProviderError("豆包API配置参数不完整")
        
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # 语言映射
        self.language_map = {
            'en': 'English',
            'zh': 'Chinese',
            'es': 'Spanish', 
            'fr': 'French',
            'de': 'German'
        }
        
        # API 请求配置
        self.max_retries = 3
        self.retry_delay = 1.0
        self.max_tokens_per_request = 4000
        self.temperature = 0.3
        self.request_timeout = 60
    
    def translate_segments(self, segments: List[TimedSegment], 
                          target_language: str,
                          source_language: Optional[str] = None) -> TranslationResult:
        """翻译时序片段"""
        if not segments:
            raise ProviderError("输入片段列表为空")
        
        if target_language not in self.language_map:
            raise ProviderError(f"不支持的目标语言: {target_language}")
        
        start_time = time.time()
        
        try:
            # 检测源语言
            if not source_language:
                source_language = self._detect_language(segments)
            
            # 验证源语言
            if source_language not in self.language_map:
                raise ProviderError(f"不支持的源语言: {source_language}")
            
            # 如果源语言和目标语言相同，直接返回
            if source_language == target_language:
                translated_segments = [
                    TimedSegment(
                        start_time=seg.start_time,
                        end_time=seg.end_time,
                        original_text=seg.original_text,
                        translated_text=seg.original_text,
                        confidence=seg.confidence,
                        speaker_id=seg.speaker_id
                    ) for seg in segments
                ]
                
                return TranslationResult(
                    original_segments=segments,
                    translated_segments=translated_segments,
                    total_characters=sum(len(seg.original_text) for seg in segments),
                    processing_time=time.time() - start_time,
                    language_detected=source_language,
                    quality_score=1.0
                )
            
            # 分批翻译
            translated_segments = []
            total_characters = 0
            
            batches = self._batch_segments(segments)
            
            for batch in batches:
                batch_result = self._translate_batch(
                    batch, source_language, target_language
                )
                translated_segments.extend(batch_result)
                total_characters += sum(len(seg.original_text) for seg in batch)
            
            # 计算翻译质量分数
            quality_score = self._calculate_quality_score(segments, translated_segments)
            
            processing_time = time.time() - start_time
            
            return TranslationResult(
                original_segments=segments,
                translated_segments=translated_segments,
                total_characters=total_characters,
                processing_time=processing_time,
                language_detected=source_language,
                quality_score=quality_score
            )
            
        except Exception as e:
            if isinstance(e, ProviderError):
                raise e
            raise ProviderError(f"豆包翻译失败: {str(e)}")
    
    def translate_text(self, text: str, target_language: str,
                      source_language: Optional[str] = None) -> str:
        """翻译单个文本"""
        if not text.strip():
            return ""
        
        if target_language not in self.language_map:
            raise ProviderError(f"不支持的目标语言: {target_language}")
        
        try:
            # 检测源语言
            if not source_language:
                source_language = self._detect_text_language(text)
            
            # 如果源语言和目标语言相同，直接返回
            if source_language == target_language:
                return text
            
            # 调用翻译API
            translated_text = self._call_doubao_api(text, source_language, target_language)
            
            return translated_text
            
        except Exception as e:
            if isinstance(e, ProviderError):
                raise e
            raise ProviderError(f"豆包文本翻译失败: {str(e)}")
    
    def _detect_language(self, segments: List[TimedSegment]) -> str:
        """检测片段语言"""
        sample_text = " ".join([
            seg.original_text for seg in segments[:5]
        ])
        
        return self._detect_text_language(sample_text)
    
    def _detect_text_language(self, text: str) -> str:
        """检测文本语言"""
        text = text.lower()
        
        # 中文检测
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        if len(chinese_chars) > len(text) * 0.3:
            return 'zh'
        
        # 西班牙语检测
        spanish_chars = re.findall(r'[ñáéíóúü¿¡]', text)
        spanish_words = ['hola', 'cómo', 'estás', 'muy', 'bien', 'gracias', 'el', 'la', 'los', 'las', 'y', 'es', 'una', 'de']
        spanish_score = len(spanish_chars) + sum(1 for word in spanish_words if word in text)
        
        # 法语检测
        french_chars = re.findall(r'[àáâäçéèêëïîôùûüÿ]', text)
        french_words = ['comment', 'allez', 'vous', 'très', 'bien', 'le', 'la', 'les', 'et', 'est', 'une', 'des']
        french_score = len(french_chars) + sum(1 for word in french_words if word in text)
        
        # 德语检测
        german_chars = re.findall(r'[äöüß]', text)
        german_words = ['wie', 'geht', 'heute', 'schön', 'der', 'die', 'das', 'und', 'ist', 'ein', 'eine']
        german_score = len(german_chars) + sum(1 for word in german_words if word in text)
        
        # 英语检测
        english_words = ['hello', 'world', 'how', 'are', 'you', 'today', 'the', 'and', 'is', 'a', 'an']
        english_score = sum(1 for word in english_words if word in text)
        
        # 比较得分
        scores = {
            'es': spanish_score,
            'fr': french_score,
            'de': german_score,
            'en': english_score
        }
        
        max_score = max(scores.values())
        if max_score == 0:
            return 'en'
        
        for lang, score in scores.items():
            if score == max_score:
                return lang
        
        return 'en'
    
    def _batch_segments(self, segments: List[TimedSegment]) -> List[List[TimedSegment]]:
        """将片段分批处理"""
        batches = []
        current_batch = []
        current_length = 0
        
        for segment in segments:
            segment_length = len(segment.original_text)
            
            if current_length + segment_length > self.max_tokens_per_request and current_batch:
                batches.append(current_batch)
                current_batch = [segment]
                current_length = segment_length
            else:
                current_batch.append(segment)
                current_length += segment_length
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _translate_batch(self, segments: List[TimedSegment],
                        source_language: str, target_language: str) -> List[TimedSegment]:
        """翻译批次片段"""
        # 使用适配器构建请求
        request_data = DoubaoAdapter.adapt_batch_translation_request(
            segments, source_language, target_language
        )
        request_data["model"] = self.model
        
        # 调用API进行翻译
        translated_text = self._call_doubao_api_with_retry(request_data)
        
        # 解析翻译结果
        translated_lines = translated_text.strip().split('\n')
        translated_segments = []
        
        for i, segment in enumerate(segments):
            # 查找对应的翻译行
            translated_line = ""
            if i < len(translated_lines):
                line = translated_lines[i].strip()
                # 移除编号前缀
                match = re.match(r'^\d+\.\s*(.*)', line)
                if match:
                    translated_line = match.group(1)
                else:
                    translated_line = line
            
            # 如果没有找到翻译，使用原文
            if not translated_line:
                translated_line = segment.original_text
            
            # 创建翻译片段
            translated_segment = TimedSegment(
                start_time=segment.start_time,
                end_time=segment.end_time,
                original_text=segment.original_text,
                translated_text=translated_line,
                confidence=segment.confidence,
                speaker_id=segment.speaker_id
            )
            
            translated_segments.append(translated_segment)
        
        return translated_segments
    
    def _call_doubao_api(self, text: str, source_language: str, target_language: str) -> str:
        """调用豆包API进行单文本翻译"""
        request_data = DoubaoAdapter.adapt_translation_request(text, source_language, target_language)
        request_data["model"] = self.model
        
        return self._call_doubao_api_with_retry(request_data)
    
    def _call_doubao_api_with_retry(self, request_data: dict) -> str:
        """带重试的豆包API调用"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=request_data,
                    timeout=self.request_timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if "choices" in result and len(result["choices"]) > 0:
                        content = result["choices"][0]["message"]["content"]
                        return content.strip()
                    else:
                        raise ProviderError("豆包API响应格式错误")
                        
                elif response.status_code == 401:
                    raise ProviderError("豆包API认证失败，请检查API密钥")
                elif response.status_code == 429:
                    raise ProviderError("豆包API请求频率超限")
                elif response.status_code >= 500:
                    raise ProviderError(f"豆包API服务器错误: {response.status_code}")
                else:
                    try:
                        error_info = response.json()
                        error_msg = error_info.get("error", {}).get("message", "未知错误")
                        error_code = error_info.get("error", {}).get("code", "unknown")
                        raise map_volcengine_error(str(error_code), error_msg)
                    except json.JSONDecodeError:
                        raise ProviderError(f"豆包API请求失败: HTTP {response.status_code}")
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
        
        if isinstance(last_error, ProviderError):
            raise last_error
        raise ProviderError(f"豆包API调用失败，已重试{self.max_retries}次: {str(last_error)}")
    
    def _calculate_quality_score(self, original_segments: List[TimedSegment],
                               translated_segments: List[TimedSegment]) -> float:
        """计算翻译质量分数"""
        if not original_segments or not translated_segments:
            return 0.0
        
        if len(original_segments) != len(translated_segments):
            return 0.5
        
        # 基于长度比例的质量评估
        length_scores = []
        for orig, trans in zip(original_segments, translated_segments):
            orig_len = len(orig.original_text)
            trans_len = len(trans.translated_text)
            
            if orig_len == 0:
                continue
            
            # 翻译长度应该在原文的50%-200%之间较为合理
            ratio = trans_len / orig_len
            if 0.5 <= ratio <= 2.0:
                score = 1.0 - abs(ratio - 1.0) * 0.5
            else:
                score = 0.3
            
            length_scores.append(score)
        
        # 检查是否有空翻译
        empty_translations = sum(1 for seg in translated_segments 
                               if not seg.translated_text.strip())
        empty_penalty = empty_translations / len(translated_segments) * 0.5
        
        # 综合评分
        avg_length_score = sum(length_scores) / len(length_scores) if length_scores else 0.5
        final_score = max(0.0, avg_length_score - empty_penalty)
        
        return min(1.0, final_score)