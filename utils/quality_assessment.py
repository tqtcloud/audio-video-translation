import os
import re
import math
import json
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from models.core import TimedSegment
from services.providers import TranscriptionResult, SpeechSynthesisResult, TranslationResult


@dataclass
class AudioQualityMetrics:
    """音频质量指标"""
    duration: float
    sample_rate: int
    bit_rate: int
    format: str
    signal_to_noise_ratio: float
    dynamic_range: float
    distortion_level: float
    quality_score: float


@dataclass
class TranslationQualityMetrics:
    """翻译质量指标"""
    fluency_score: float
    accuracy_score: float
    consistency_score: float
    completeness_score: float
    timing_preservation: float
    overall_score: float


@dataclass
class QualityReport:
    """质量评估报告"""
    timestamp: str
    test_case: str
    provider: str
    service_type: str
    metrics: Dict[str, Any]
    recommendations: List[str]
    overall_rating: str


class AudioQualityAssessment:
    """音频质量评估器"""
    
    def __init__(self):
        self.quality_thresholds = {
            "excellent": 0.9,
            "good": 0.7,
            "fair": 0.5,
            "poor": 0.0
        }
    
    def assess_transcription_quality(self, result: TranscriptionResult, 
                                   reference_text: Optional[str] = None) -> Dict[str, float]:
        """评估转录质量"""
        metrics = {
            "text_length_score": self._assess_text_length(result.text),
            "language_confidence": self._assess_language_confidence(result),
            "segment_completeness": self._assess_segment_completeness(result.segments),
            "timing_accuracy": self._assess_timing_accuracy(result.segments),
            "confidence_score": self._assess_confidence_scores(result.segments)
        }
        
        if reference_text:
            metrics["accuracy_score"] = self._assess_text_accuracy(result.text, reference_text)
        
        # 计算综合分数
        weights = {
            "text_length_score": 0.15,
            "language_confidence": 0.15,
            "segment_completeness": 0.20,
            "timing_accuracy": 0.25,
            "confidence_score": 0.25
        }
        
        if "accuracy_score" in metrics:
            weights["accuracy_score"] = 0.30
            # 调整其他权重
            for key in weights:
                if key != "accuracy_score":
                    weights[key] *= 0.7
        
        overall_score = sum(metrics[key] * weights[key] for key in weights if key in metrics)
        metrics["overall_score"] = overall_score
        
        return metrics
    
    def assess_synthesis_quality(self, result: SpeechSynthesisResult,
                               original_segments: List[TimedSegment]) -> Dict[str, float]:
        """评估语音合成质量"""
        metrics = {
            "duration_accuracy": self._assess_duration_accuracy(result, original_segments),
            "timing_adjustments": self._assess_timing_adjustments(result.timing_adjustments),
            "processing_efficiency": self._assess_processing_efficiency(result),
            "segments_completeness": self._assess_segments_completeness(result, original_segments),
            "quality_score": result.quality_score
        }
        
        # 计算综合分数
        weights = {
            "duration_accuracy": 0.25,
            "timing_adjustments": 0.20,
            "processing_efficiency": 0.15,
            "segments_completeness": 0.20,
            "quality_score": 0.20
        }
        
        overall_score = sum(metrics[key] * weights[key] for key in weights)
        metrics["overall_score"] = overall_score
        
        return metrics
    
    def analyze_audio_file(self, audio_path: str) -> AudioQualityMetrics:
        """分析音频文件质量"""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        try:
            # 模拟音频分析（实际项目中可以使用librosa或pydub）
            file_size = os.path.getsize(audio_path)
            file_ext = os.path.splitext(audio_path)[1].lower()
            
            # 基于文件大小和格式估算质量指标
            duration = max(1.0, file_size / 16000)  # 估算时长
            sample_rate = 44100 if file_ext in ['.wav', '.flac'] else 22050
            bit_rate = 128 if file_ext == '.mp3' else 256
            
            # 模拟质量分析
            snr = 25.0 + (file_size % 1000) / 100  # 信噪比
            dynamic_range = 60.0 + (file_size % 500) / 50  # 动态范围
            distortion = max(0.01, min(0.1, (file_size % 100) / 1000))  # 失真度
            
            # 计算质量分数
            quality_score = self._calculate_audio_quality_score(
                snr, dynamic_range, distortion, sample_rate, bit_rate
            )
            
            return AudioQualityMetrics(
                duration=duration,
                sample_rate=sample_rate,
                bit_rate=bit_rate,
                format=file_ext,
                signal_to_noise_ratio=snr,
                dynamic_range=dynamic_range,
                distortion_level=distortion,
                quality_score=quality_score
            )
        
        except Exception as e:
            raise RuntimeError(f"音频质量分析失败: {str(e)}")
    
    def _assess_text_length(self, text: str) -> float:
        """评估文本长度合理性"""
        length = len(text.strip())
        if length == 0:
            return 0.0
        elif length < 10:
            return 0.3
        elif length < 50:
            return 0.7
        else:
            return 1.0
    
    def _assess_language_confidence(self, result: TranscriptionResult) -> float:
        """评估语言检测置信度"""
        if result.language:
            # 基于语言代码的长度和格式判断置信度
            if len(result.language) == 2 and result.language.isalpha():
                return 0.9
            else:
                return 0.6
        return 0.0
    
    def _assess_segment_completeness(self, segments: List[TimedSegment]) -> float:
        """评估片段完整性"""
        if not segments:
            return 0.0
        
        # 检查片段是否有文本内容
        non_empty_segments = [seg for seg in segments if seg.original_text.strip()]
        completeness = len(non_empty_segments) / len(segments)
        
        # 检查时间覆盖
        if len(segments) > 1:
            total_duration = segments[-1].end_time - segments[0].start_time
            segments_duration = sum(seg.end_time - seg.start_time for seg in segments)
            coverage = min(1.0, segments_duration / total_duration)
            completeness = (completeness + coverage) / 2
        
        return completeness
    
    def _assess_timing_accuracy(self, segments: List[TimedSegment]) -> float:
        """评估时序准确性"""
        if len(segments) < 2:
            return 1.0
        
        # 检查时间顺序
        timing_errors = 0
        for i in range(1, len(segments)):
            prev_seg = segments[i-1]
            curr_seg = segments[i]
            
            # 检查时间顺序错误
            if curr_seg.start_time < prev_seg.end_time:
                timing_errors += 1
            
            # 检查不合理的时间间隔
            if curr_seg.start_time - prev_seg.end_time > 5.0:  # 超过5秒间隔
                timing_errors += 0.5
        
        accuracy = max(0.0, 1.0 - (timing_errors / len(segments)))
        return accuracy
    
    def _assess_confidence_scores(self, segments: List[TimedSegment]) -> float:
        """评估置信度分数"""
        if not segments:
            return 0.0
        
        # 计算平均置信度（注意confidence可能是负数或对数值）
        confidences = [seg.confidence for seg in segments if seg.confidence is not None]
        if not confidences:
            return 0.5  # 默认中等置信度
        
        avg_confidence = sum(confidences) / len(confidences)
        
        # 转换为0-1范围的分数
        if avg_confidence < 0:  # 可能是对数概率
            # 假设范围是-5到0
            normalized = max(0.0, min(1.0, (avg_confidence + 5) / 5))
        else:  # 已经是0-1范围
            normalized = max(0.0, min(1.0, avg_confidence))
        
        return normalized
    
    def _assess_text_accuracy(self, predicted: str, reference: str) -> float:
        """评估文本准确性（与参考文本对比）"""
        if not reference.strip():
            return 0.0 if predicted.strip() else 1.0
        
        # 简单的编辑距离计算
        predicted_words = predicted.lower().split()
        reference_words = reference.lower().split()
        
        if not reference_words:
            return 1.0 if not predicted_words else 0.0
        
        # 计算词级别的相似度
        max_len = max(len(predicted_words), len(reference_words))
        if max_len == 0:
            return 1.0
        
        # 简化的相似度计算
        common_words = set(predicted_words) & set(reference_words)
        accuracy = len(common_words) / max_len
        
        return min(1.0, accuracy)
    
    def _assess_duration_accuracy(self, result: SpeechSynthesisResult,
                                 original_segments: List[TimedSegment]) -> float:
        """评估持续时间准确性"""
        if not original_segments:
            return 0.5
        
        expected_duration = original_segments[-1].end_time - original_segments[0].start_time
        actual_duration = result.total_duration
        
        if expected_duration <= 0:
            return 0.5
        
        ratio = actual_duration / expected_duration
        # 理想比例接近1.0
        accuracy = 1.0 - min(1.0, abs(ratio - 1.0))
        
        return accuracy
    
    def _assess_timing_adjustments(self, adjustments: List[Tuple[int, float]]) -> float:
        """评估时序调整质量"""
        if not adjustments:
            return 1.0  # 没有调整是最好的
        
        # 调整次数越少越好
        adjustment_penalty = len(adjustments) * 0.1
        
        # 调整幅度越小越好
        if adjustments:
            avg_adjustment = sum(abs(adj[1] - 1.0) for adj in adjustments) / len(adjustments)
            adjustment_penalty += avg_adjustment * 0.5
        
        score = max(0.0, 1.0 - adjustment_penalty)
        return score
    
    def _assess_processing_efficiency(self, result: SpeechSynthesisResult) -> float:
        """评估处理效率"""
        if result.total_duration <= 0 or result.processing_time <= 0:
            return 0.5
        
        # 实时倍速：处理时间与音频时长的比例
        realtime_factor = result.processing_time / result.total_duration
        
        if realtime_factor <= 0.5:  # 小于0.5倍实时速度，非常高效
            return 1.0
        elif realtime_factor <= 1.0:  # 实时处理
            return 0.8
        elif realtime_factor <= 2.0:  # 2倍实时时间
            return 0.6
        else:  # 处理时间过长
            return max(0.0, 0.4 - (realtime_factor - 2.0) * 0.1)
    
    def _assess_segments_completeness(self, result: SpeechSynthesisResult,
                                    original_segments: List[TimedSegment]) -> float:
        """评估片段完整性"""
        expected_count = len(original_segments)
        actual_count = result.segments_count
        
        if expected_count == 0:
            return 1.0 if actual_count == 0 else 0.0
        
        completeness = min(1.0, actual_count / expected_count)
        return completeness
    
    def _calculate_audio_quality_score(self, snr: float, dynamic_range: float,
                                     distortion: float, sample_rate: int,
                                     bit_rate: int) -> float:
        """计算音频质量综合分数"""
        # SNR评分 (0-1)
        snr_score = min(1.0, max(0.0, (snr - 10) / 30))  # 10-40dB范围
        
        # 动态范围评分 (0-1)
        dr_score = min(1.0, max(0.0, (dynamic_range - 20) / 60))  # 20-80dB范围
        
        # 失真评分 (0-1, 失真越小越好)
        distortion_score = max(0.0, 1.0 - distortion * 10)
        
        # 采样率评分 (0-1)
        sr_score = min(1.0, sample_rate / 44100)
        
        # 比特率评分 (0-1)
        br_score = min(1.0, bit_rate / 320)
        
        # 加权平均
        weights = [0.3, 0.25, 0.25, 0.1, 0.1]
        scores = [snr_score, dr_score, distortion_score, sr_score, br_score]
        
        quality_score = sum(w * s for w, s in zip(weights, scores))
        return quality_score


class TranslationQualityAssessment:
    """翻译质量评估器"""
    
    def __init__(self):
        self.language_patterns = {
            'zh': re.compile(r'[\u4e00-\u9fff]'),
            'en': re.compile(r'[a-zA-Z]'),
            'es': re.compile(r'[a-zA-ZñáéíóúüÑÁÉÍÓÚÜ]'),
            'fr': re.compile(r'[a-zA-ZàâäçéèêëïîôùûüÿÀÂÄÇÉÈÊËÏÎÔÙÛÜŸ]'),
            'de': re.compile(r'[a-zA-ZäöüßÄÖÜ]')
        }
    
    def assess_translation_quality(self, result: TranslationResult,
                                 reference_translation: Optional[List[TimedSegment]] = None) -> TranslationQualityMetrics:
        """评估翻译质量"""
        fluency = self._assess_fluency(result.translated_segments)
        accuracy = self._assess_accuracy(result, reference_translation)
        consistency = self._assess_consistency(result.translated_segments)
        completeness = self._assess_completeness(result)
        timing_preservation = self._assess_timing_preservation(result)
        
        # 计算综合分数
        overall = (fluency * 0.25 + accuracy * 0.30 + consistency * 0.20 + 
                  completeness * 0.15 + timing_preservation * 0.10)
        
        return TranslationQualityMetrics(
            fluency_score=fluency,
            accuracy_score=accuracy,
            consistency_score=consistency,
            completeness_score=completeness,
            timing_preservation=timing_preservation,
            overall_score=overall
        )
    
    def _assess_fluency(self, translated_segments: List[TimedSegment]) -> float:
        """评估翻译流畅性"""
        if not translated_segments:
            return 0.0
        
        scores = []
        for segment in translated_segments:
            text = segment.translated_text.strip()
            if not text:
                scores.append(0.0)
                continue
            
            # 基本流畅性指标
            fluency_score = 1.0
            
            # 检查过短或过长的句子
            word_count = len(text.split())
            if word_count < 2:
                fluency_score *= 0.5
            elif word_count > 50:
                fluency_score *= 0.8
            
            # 检查重复词汇
            words = text.lower().split()
            unique_words = set(words)
            if len(words) > 0:
                repetition_ratio = len(unique_words) / len(words)
                if repetition_ratio < 0.7:
                    fluency_score *= 0.8
            
            # 检查特殊字符密度
            special_chars = re.findall(r'[^\w\s\u4e00-\u9fff]', text)
            if len(special_chars) > len(text) * 0.1:
                fluency_score *= 0.9
            
            scores.append(fluency_score)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _assess_accuracy(self, result: TranslationResult,
                        reference: Optional[List[TimedSegment]]) -> float:
        """评估翻译准确性"""
        if reference:
            return self._compare_with_reference(result.translated_segments, reference)
        
        # 没有参考翻译时，使用启发式方法
        return self._heuristic_accuracy_assessment(result)
    
    def _assess_consistency(self, translated_segments: List[TimedSegment]) -> float:
        """评估翻译一致性"""
        if len(translated_segments) <= 1:
            return 1.0
        
        # 检查术语一致性
        term_translations = {}
        consistency_errors = 0
        
        for segment in translated_segments:
            original_words = set(segment.original_text.lower().split())
            translated_words = set(segment.translated_text.lower().split())
            
            for orig_word in original_words:
                if len(orig_word) > 3:  # 只检查较长的词
                    if orig_word in term_translations:
                        # 检查是否使用了不同的翻译
                        prev_translations = term_translations[orig_word]
                        current_translations = translated_words
                        if not prev_translations & current_translations:
                            consistency_errors += 1
                    else:
                        term_translations[orig_word] = translated_words
        
        total_terms = len(term_translations)
        if total_terms == 0:
            return 1.0
        
        consistency_score = max(0.0, 1.0 - (consistency_errors / total_terms))
        return consistency_score
    
    def _assess_completeness(self, result: TranslationResult) -> float:
        """评估翻译完整性"""
        if not result.original_segments:
            return 1.0 if not result.translated_segments else 0.0
        
        # 检查片段数量匹配
        segment_ratio = len(result.translated_segments) / len(result.original_segments)
        segment_score = min(1.0, segment_ratio)
        
        # 检查文本长度比例
        total_orig_length = sum(len(seg.original_text) for seg in result.original_segments)
        total_trans_length = sum(len(seg.translated_text) for seg in result.translated_segments)
        
        if total_orig_length == 0:
            length_score = 1.0 if total_trans_length == 0 else 0.0
        else:
            length_ratio = total_trans_length / total_orig_length
            # 翻译长度在原文的50%-200%之间认为是合理的
            if 0.5 <= length_ratio <= 2.0:
                length_score = 1.0 - abs(length_ratio - 1.0) * 0.5
            else:
                length_score = 0.3
        
        completeness = (segment_score + length_score) / 2
        return completeness
    
    def _assess_timing_preservation(self, result: TranslationResult) -> float:
        """评估时序保持"""
        if not result.original_segments or not result.translated_segments:
            return 1.0
        
        preserved_count = 0
        total_count = min(len(result.original_segments), len(result.translated_segments))
        
        for i in range(total_count):
            orig_seg = result.original_segments[i]
            trans_seg = result.translated_segments[i]
            
            # 检查时间戳是否保持
            start_diff = abs(orig_seg.start_time - trans_seg.start_time)
            end_diff = abs(orig_seg.end_time - trans_seg.end_time)
            
            if start_diff < 0.1 and end_diff < 0.1:  # 100ms容差
                preserved_count += 1
        
        preservation_score = preserved_count / total_count if total_count > 0 else 1.0
        return preservation_score
    
    def _compare_with_reference(self, translated: List[TimedSegment],
                               reference: List[TimedSegment]) -> float:
        """与参考翻译对比"""
        if len(translated) != len(reference):
            return 0.5
        
        similarities = []
        for trans_seg, ref_seg in zip(translated, reference):
            similarity = self._calculate_text_similarity(
                trans_seg.translated_text, ref_seg.translated_text
            )
            similarities.append(similarity)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _heuristic_accuracy_assessment(self, result: TranslationResult) -> float:
        """启发式准确性评估"""
        if not result.original_segments or not result.translated_segments:
            return 0.0
        
        scores = []
        min_len = min(len(result.original_segments), len(result.translated_segments))
        
        for i in range(min_len):
            orig_seg = result.original_segments[i]
            trans_seg = result.translated_segments[i]
            
            # 检查语言匹配
            orig_lang = self._detect_language(orig_seg.original_text)
            trans_lang = self._detect_language(trans_seg.translated_text)
            
            # 检查长度合理性
            length_ratio = len(trans_seg.translated_text) / max(1, len(orig_seg.original_text))
            length_score = 1.0 if 0.5 <= length_ratio <= 2.0 else 0.5
            
            # 检查是否有翻译内容
            has_content = 1.0 if trans_seg.translated_text.strip() else 0.0
            
            # 语言检测分数
            lang_score = 0.8 if orig_lang != trans_lang else 0.3
            
            segment_score = (length_score + has_content + lang_score) / 3
            scores.append(segment_score)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _detect_language(self, text: str) -> str:
        """简单的语言检测"""
        text = text.strip().lower()
        if not text:
            return "unknown"
        
        scores = {}
        for lang, pattern in self.language_patterns.items():
            matches = pattern.findall(text)
            scores[lang] = len(matches) / len(text)
        
        return max(scores, key=scores.get) if scores else "unknown"
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        elif not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        jaccard_similarity = len(intersection) / len(union)
        return jaccard_similarity


class QualityReportGenerator:
    """质量评估报告生成器"""
    
    def __init__(self):
        self.audio_assessor = AudioQualityAssessment()
        self.translation_assessor = TranslationQualityAssessment()
    
    def generate_comprehensive_report(self, test_cases: List[Dict[str, Any]],
                                    output_path: Optional[str] = None) -> QualityReport:
        """生成综合质量报告"""
        timestamp = datetime.now().isoformat()
        
        all_metrics = {}
        all_recommendations = []
        
        for test_case in test_cases:
            case_name = test_case.get("name", "unknown")
            provider = test_case.get("provider", "unknown")
            service_type = test_case.get("service_type", "unknown")
            
            if service_type == "stt" and "transcription_result" in test_case:
                metrics = self.audio_assessor.assess_transcription_quality(
                    test_case["transcription_result"],
                    test_case.get("reference_text")
                )
                all_metrics[f"{case_name}_stt"] = metrics
                all_recommendations.extend(
                    self._generate_stt_recommendations(metrics, provider)
                )
            
            elif service_type == "tts" and "synthesis_result" in test_case:
                metrics = self.audio_assessor.assess_synthesis_quality(
                    test_case["synthesis_result"],
                    test_case.get("original_segments", [])
                )
                all_metrics[f"{case_name}_tts"] = metrics
                all_recommendations.extend(
                    self._generate_tts_recommendations(metrics, provider)
                )
            
            elif service_type == "translation" and "translation_result" in test_case:
                metrics = self.translation_assessor.assess_translation_quality(
                    test_case["translation_result"],
                    test_case.get("reference_translation")
                )
                all_metrics[f"{case_name}_translation"] = metrics.__dict__
                all_recommendations.extend(
                    self._generate_translation_recommendations(metrics, provider)
                )
        
        # 计算总体评级
        overall_scores = []
        for metrics in all_metrics.values():
            if "overall_score" in metrics:
                overall_scores.append(metrics["overall_score"])
        
        avg_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
        overall_rating = self._get_rating_label(avg_score)
        
        report = QualityReport(
            timestamp=timestamp,
            test_case="comprehensive_assessment",
            provider="multiple",
            service_type="all",
            metrics=all_metrics,
            recommendations=list(set(all_recommendations)),  # 去重
            overall_rating=overall_rating
        )
        
        if output_path:
            self._save_report(report, output_path)
        
        return report
    
    def _generate_stt_recommendations(self, metrics: Dict[str, float], provider: str) -> List[str]:
        """生成STT建议"""
        recommendations = []
        
        if metrics.get("overall_score", 0) < 0.7:
            recommendations.append(f"考虑优化{provider} STT配置以提高整体质量")
        
        if metrics.get("timing_accuracy", 0) < 0.8:
            recommendations.append("改进时序标注算法以提高时间准确性")
        
        if metrics.get("confidence_score", 0) < 0.7:
            recommendations.append("检查音频质量输入，考虑降噪处理")
        
        if metrics.get("segment_completeness", 0) < 0.9:
            recommendations.append("优化音频分段算法以提高完整性")
        
        return recommendations
    
    def _generate_tts_recommendations(self, metrics: Dict[str, float], provider: str) -> List[str]:
        """生成TTS建议"""
        recommendations = []
        
        if metrics.get("overall_score", 0) < 0.7:
            recommendations.append(f"考虑调整{provider} TTS参数以提高合成质量")
        
        if metrics.get("duration_accuracy", 0) < 0.8:
            recommendations.append("优化语音合成速度控制算法")
        
        if metrics.get("processing_efficiency", 0) < 0.7:
            recommendations.append("考虑使用更高效的TTS模型或优化处理流程")
        
        if metrics.get("timing_adjustments", 0) < 0.8:
            recommendations.append("减少时序调整次数，改进原始时序预测")
        
        return recommendations
    
    def _generate_translation_recommendations(self, metrics: TranslationQualityMetrics, provider: str) -> List[str]:
        """生成翻译建议"""
        recommendations = []
        
        if metrics.overall_score < 0.7:
            recommendations.append(f"考虑调整{provider}翻译模型参数以提高整体质量")
        
        if metrics.fluency_score < 0.8:
            recommendations.append("优化翻译流畅性，考虑使用更先进的语言模型")
        
        if metrics.accuracy_score < 0.8:
            recommendations.append("提高翻译准确性，可能需要领域特定的微调")
        
        if metrics.consistency_score < 0.7:
            recommendations.append("建立术语词典以提高翻译一致性")
        
        if metrics.timing_preservation < 0.9:
            recommendations.append("优化时序保持算法")
        
        return recommendations
    
    def _get_rating_label(self, score: float) -> str:
        """获取评级标签"""
        if score >= 0.9:
            return "优秀"
        elif score >= 0.7:
            return "良好"
        elif score >= 0.5:
            return "一般"
        else:
            return "较差"
    
    def _save_report(self, report: QualityReport, output_path: str):
        """保存报告到文件"""
        report_data = {
            "timestamp": report.timestamp,
            "test_case": report.test_case,
            "provider": report.provider,
            "service_type": report.service_type,
            "overall_rating": report.overall_rating,
            "metrics": report.metrics,
            "recommendations": report.recommendations
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"质量评估报告已保存到: {output_path}")


def create_sample_quality_report():
    """创建示例质量报告"""
    generator = QualityReportGenerator()
    
    # 创建示例测试用例
    test_cases = [
        {
            "name": "test_case_1",
            "provider": "openai",
            "service_type": "stt",
            "transcription_result": TranscriptionResult(
                text="Hello world, this is a test",
                language="en",
                duration=5.0,
                segments=[
                    TimedSegment(0.0, 2.0, "Hello world", confidence=0.9),
                    TimedSegment(2.0, 5.0, "this is a test", confidence=0.85)
                ]
            ),
            "reference_text": "Hello world, this is a test"
        }
    ]
    
    report = generator.generate_comprehensive_report(test_cases)
    return report


if __name__ == "__main__":
    # 创建示例报告
    sample_report = create_sample_quality_report()
    print("示例质量评估报告:")
    print(f"整体评级: {sample_report.overall_rating}")
    print(f"建议数量: {len(sample_report.recommendations)}")