import re
import time
from typing import List, Optional
import openai
from models.core import TimedSegment
from services.providers import TranslationProvider, TranslationResult
from utils.provider_errors import ProviderError, map_openai_error


class OpenAITranslation(TranslationProvider):
    """OpenAI GPT翻译提供者"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        if not self.api_key:
            raise ProviderError("OpenAI API密钥未设置")
        
        openai.api_key = self.api_key
        
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
            raise map_openai_error(type(e).__name__.lower(), str(e))
    
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
            translated_text = self._call_translation_api(
                text, source_language, target_language
            )
            
            return translated_text
            
        except Exception as e:
            if isinstance(e, ProviderError):
                raise e
            raise map_openai_error(type(e).__name__.lower(), str(e))
    
    def _detect_language(self, segments: List[TimedSegment]) -> str:
        """检测片段语言"""
        # 合并前几个片段的文本进行语言检测
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
            return 'en'  # 默认为英语
        
        # 返回得分最高的语言
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
            
            # 如果添加当前片段会超过限制，开始新批次
            if current_length + segment_length > self.max_tokens_per_request and current_batch:
                batches.append(current_batch)
                current_batch = [segment]
                current_length = segment_length
            else:
                current_batch.append(segment)
                current_length += segment_length
        
        # 添加最后一批
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _translate_batch(self, segments: List[TimedSegment],
                        source_language: str, target_language: str) -> List[TimedSegment]:
        """翻译批次片段"""
        # 构建翻译提示
        source_lang_name = self.language_map[source_language]
        target_lang_name = self.language_map[target_language]
        
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
        
        # 调用API进行翻译
        translated_text = self._call_translation_api_with_retry(prompt)
        
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
    
    def _call_translation_api(self, text: str, source_language: str,
                            target_language: str) -> str:
        """调用翻译API"""
        source_lang_name = self.language_map[source_language]
        target_lang_name = self.language_map[target_language]
        
        prompt = f"请将以下{source_lang_name}文本翻译成{target_lang_name}，保持原意准确，语言自然流畅：\n\n{text}"
        
        return self._call_translation_api_with_retry(prompt)
    
    def _call_translation_api_with_retry(self, prompt: str) -> str:
        """带重试的API调用"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个专业的翻译助手，专门提供准确、自然的翻译服务。"
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    temperature=self.temperature,
                    max_tokens=4000
                )
                
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                
        raise map_openai_error(type(last_error).__name__.lower(), str(last_error))
    
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