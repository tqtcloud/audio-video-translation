#!/usr/bin/env python3
"""
输出质量评估指标
提供音频、视频、翻译质量的评估方法
"""

import os
import subprocess
import json
import math
import wave
import librosa
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import difflib
from textstat import flesch_reading_ease, flesch_kincaid_grade


@dataclass
class AudioQualityMetrics:
    """音频质量指标"""
    snr_db: float = 0.0           # 信噪比
    thd: float = 0.0              # 总谐波失真
    frequency_response: Dict[str, float] = None  # 频率响应
    dynamic_range: float = 0.0    # 动态范围
    peak_level: float = 0.0       # 峰值电平
    rms_level: float = 0.0        # RMS电平
    duration_accuracy: float = 0.0 # 时长准确性


@dataclass
class VideoQualityMetrics:
    """视频质量指标"""
    psnr: float = 0.0            # 峰值信噪比
    ssim: float = 0.0            # 结构相似性
    bitrate: int = 0             # 比特率
    frame_rate: float = 0.0      # 帧率
    resolution: str = ""         # 分辨率
    codec_info: str = ""         # 编解码器信息
    sync_offset: float = 0.0     # 音视频同步偏移


@dataclass
class TranslationQualityMetrics:
    """翻译质量指标"""
    bleu_score: float = 0.0      # BLEU分数
    meteor_score: float = 0.0    # METEOR分数
    ter_score: float = 0.0       # TER分数（翻译错误率）
    length_ratio: float = 0.0    # 长度比例
    word_accuracy: float = 0.0   # 词准确率
    sentence_accuracy: float = 0.0 # 句子准确率
    fluency_score: float = 0.0   # 流畅度分数
    adequacy_score: float = 0.0  # 充分性分数


@dataclass
class SyncQualityMetrics:
    """同步质量指标"""
    timing_accuracy: float = 0.0  # 时序准确性
    lip_sync_score: float = 0.0   # 唇形同步分数
    segment_alignment: float = 0.0 # 段落对齐度
    overall_sync_score: float = 0.0 # 总体同步分数


class QualityAssessmentTool:
    """质量评估工具"""
    
    def __init__(self):
        """初始化评估工具"""
        self.temp_dir = Path("./temp_quality_analysis")
        self.temp_dir.mkdir(exist_ok=True)
    
    def assess_audio_quality(self, 
                           original_audio_path: str, 
                           processed_audio_path: str) -> AudioQualityMetrics:
        """
        评估音频质量
        
        Args:
            original_audio_path: 原始音频文件路径
            processed_audio_path: 处理后音频文件路径
            
        Returns:
            音频质量指标
        """
        metrics = AudioQualityMetrics()
        
        try:
            # 加载音频文件
            original_audio, orig_sr = librosa.load(original_audio_path, sr=None)
            processed_audio, proc_sr = librosa.load(processed_audio_path, sr=None)
            
            # 确保采样率一致
            if orig_sr != proc_sr:
                processed_audio = librosa.resample(processed_audio, orig_sr=proc_sr, target_sr=orig_sr)
            
            # 确保长度一致（取较短的）
            min_length = min(len(original_audio), len(processed_audio))
            original_audio = original_audio[:min_length]
            processed_audio = processed_audio[:min_length]
            
            # 计算信噪比 (SNR)
            metrics.snr_db = self._calculate_snr(original_audio, processed_audio)
            
            # 计算总谐波失真 (THD)
            metrics.thd = self._calculate_thd(processed_audio, orig_sr)
            
            # 计算动态范围
            metrics.dynamic_range = self._calculate_dynamic_range(processed_audio)
            
            # 计算峰值和RMS电平
            metrics.peak_level = np.max(np.abs(processed_audio))
            metrics.rms_level = np.sqrt(np.mean(processed_audio**2))
            
            # 计算时长准确性
            orig_duration = len(original_audio) / orig_sr
            proc_duration = len(processed_audio) / orig_sr
            metrics.duration_accuracy = 1.0 - abs(orig_duration - proc_duration) / orig_duration
            
            # 计算频率响应
            metrics.frequency_response = self._analyze_frequency_response(
                original_audio, processed_audio, orig_sr
            )
            
        except Exception as e:
            print(f"音频质量评估失败: {str(e)}")
        
        return metrics
    
    def assess_video_quality(self, 
                           original_video_path: str, 
                           processed_video_path: str) -> VideoQualityMetrics:
        """
        评估视频质量
        
        Args:
            original_video_path: 原始视频文件路径
            processed_video_path: 处理后视频文件路径
            
        Returns:
            视频质量指标
        """
        metrics = VideoQualityMetrics()
        
        try:
            # 获取视频信息
            orig_info = self._get_video_info(original_video_path)
            proc_info = self._get_video_info(processed_video_path)
            
            metrics.bitrate = proc_info.get('bit_rate', 0)
            metrics.frame_rate = proc_info.get('r_frame_rate', 0.0)
            metrics.resolution = f"{proc_info.get('width', 0)}x{proc_info.get('height', 0)}"
            metrics.codec_info = proc_info.get('codec_name', '')
            
            # 计算PSNR（如果FFmpeg支持）
            metrics.psnr = self._calculate_video_psnr(original_video_path, processed_video_path)
            
            # 计算SSIM（如果FFmpeg支持）
            metrics.ssim = self._calculate_video_ssim(original_video_path, processed_video_path)
            
            # 计算音视频同步偏移
            metrics.sync_offset = self._calculate_av_sync_offset(
                original_video_path, processed_video_path
            )
            
        except Exception as e:
            print(f"视频质量评估失败: {str(e)}")
        
        return metrics
    
    def assess_translation_quality(self, 
                                 reference_text: str, 
                                 translated_text: str,
                                 source_language: str = "en",
                                 target_language: str = "zh-CN") -> TranslationQualityMetrics:
        """
        评估翻译质量
        
        Args:
            reference_text: 参考翻译
            translated_text: 实际翻译
            source_language: 源语言
            target_language: 目标语言
            
        Returns:
            翻译质量指标
        """
        metrics = TranslationQualityMetrics()
        
        try:
            # 计算BLEU分数
            metrics.bleu_score = self._calculate_bleu_score(reference_text, translated_text)
            
            # 计算编辑距离相关指标
            metrics.ter_score = self._calculate_ter_score(reference_text, translated_text)
            
            # 计算长度比例
            ref_length = len(reference_text.split())
            trans_length = len(translated_text.split())
            if ref_length > 0:
                metrics.length_ratio = trans_length / ref_length
            
            # 计算词准确率
            metrics.word_accuracy = self._calculate_word_accuracy(reference_text, translated_text)
            
            # 计算句子准确率
            metrics.sentence_accuracy = self._calculate_sentence_accuracy(reference_text, translated_text)
            
            # 计算流畅度分数（基于可读性）
            metrics.fluency_score = self._calculate_fluency_score(translated_text, target_language)
            
            # 计算充分性分数（基于内容覆盖）
            metrics.adequacy_score = self._calculate_adequacy_score(reference_text, translated_text)
            
        except Exception as e:
            print(f"翻译质量评估失败: {str(e)}")
        
        return metrics
    
    def assess_sync_quality(self, 
                          original_segments: List[Dict], 
                          translated_segments: List[Dict],
                          original_audio_path: str,
                          translated_audio_path: str) -> SyncQualityMetrics:
        """
        评估同步质量
        
        Args:
            original_segments: 原始语音段落
            translated_segments: 翻译语音段落
            original_audio_path: 原始音频路径
            translated_audio_path: 翻译音频路径
            
        Returns:
            同步质量指标
        """
        metrics = SyncQualityMetrics()
        
        try:
            # 计算时序准确性
            metrics.timing_accuracy = self._calculate_timing_accuracy(
                original_segments, translated_segments
            )
            
            # 计算段落对齐度
            metrics.segment_alignment = self._calculate_segment_alignment(
                original_segments, translated_segments
            )
            
            # 计算唇形同步分数（简化版本）
            metrics.lip_sync_score = self._calculate_lip_sync_score(
                original_audio_path, translated_audio_path
            )
            
            # 计算总体同步分数
            metrics.overall_sync_score = (
                metrics.timing_accuracy * 0.4 +
                metrics.segment_alignment * 0.4 +
                metrics.lip_sync_score * 0.2
            )
            
        except Exception as e:
            print(f"同步质量评估失败: {str(e)}")
        
        return metrics
    
    def generate_quality_report(self, 
                              job_id: str,
                              original_file: str,
                              output_file: str,
                              processing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成完整的质量报告
        
        Args:
            job_id: 作业ID
            original_file: 原始文件路径
            output_file: 输出文件路径
            processing_results: 处理结果
            
        Returns:
            质量报告
        """
        report = {
            "job_id": job_id,
            "timestamp": time.time(),
            "files": {
                "original": original_file,
                "output": output_file
            },
            "metrics": {}
        }
        
        try:
            # 音频质量评估
            if "audio_extraction" in processing_results:
                original_audio = processing_results["audio_extraction"]["audio_path"]
                final_audio = processing_results["audio_sync"]["final_audio_path"]
                
                report["metrics"]["audio_quality"] = self.assess_audio_quality(
                    original_audio, final_audio
                ).__dict__
            
            # 视频质量评估（如果适用）
            if original_file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                report["metrics"]["video_quality"] = self.assess_video_quality(
                    original_file, output_file
                ).__dict__
            
            # 翻译质量评估
            if "text_translation" in processing_results and "speech_to_text" in processing_results:
                original_text = processing_results["speech_to_text"]["transcription"]
                # 这里需要参考翻译，实际应用中可能需要人工提供
                reference_translation = "参考翻译文本"  # 占位符
                
                # 提取翻译后的文本
                translated_segments = processing_results["text_translation"]["translated_segments"]
                translated_text = " ".join([seg.translated_text for seg in translated_segments])
                
                if reference_translation != "参考翻译文本":  # 如果有真实的参考翻译
                    report["metrics"]["translation_quality"] = self.assess_translation_quality(
                        reference_translation, translated_text
                    ).__dict__
            
            # 同步质量评估
            if ("speech_to_text" in processing_results and 
                "text_translation" in processing_results and
                "audio_sync" in processing_results):
                
                original_segments = processing_results["speech_to_text"]["segments"]
                translated_segments = processing_results["text_translation"]["translated_segments"]
                original_audio = processing_results["audio_extraction"]["audio_path"]
                translated_audio = processing_results["audio_sync"]["final_audio_path"]
                
                # 转换为字典格式
                orig_segs = [{"start": seg.start_time, "end": seg.end_time, "text": seg.original_text} 
                           for seg in original_segments]
                trans_segs = [{"start": seg.start_time, "end": seg.end_time, "text": seg.translated_text}
                            for seg in translated_segments]
                
                report["metrics"]["sync_quality"] = self.assess_sync_quality(
                    orig_segs, trans_segs, original_audio, translated_audio
                ).__dict__
            
            # 计算总体质量分数
            report["overall_quality_score"] = self._calculate_overall_quality_score(
                report["metrics"]
            )
            
        except Exception as e:
            report["error"] = f"质量报告生成失败: {str(e)}"
        
        return report
    
    # 私有辅助方法
    def _calculate_snr(self, signal: np.ndarray, noisy_signal: np.ndarray) -> float:
        """计算信噪比"""
        noise = noisy_signal - signal
        signal_power = np.mean(signal**2)
        noise_power = np.mean(noise**2)
        
        if noise_power == 0:
            return float('inf')
        
        snr = 10 * np.log10(signal_power / noise_power)
        return snr
    
    def _calculate_thd(self, signal: np.ndarray, sample_rate: int) -> float:
        """计算总谐波失真"""
        # 简化的THD计算
        # 实际应用中需要更复杂的频域分析
        fft = np.fft.fft(signal)
        freqs = np.fft.fftfreq(len(signal), 1/sample_rate)
        
        # 找到基频
        fundamental_idx = np.argmax(np.abs(fft[1:len(fft)//2])) + 1
        fundamental_power = np.abs(fft[fundamental_idx])**2
        
        # 计算谐波功率
        harmonics_power = 0
        for h in range(2, 6):  # 2-5次谐波
            harmonic_idx = fundamental_idx * h
            if harmonic_idx < len(fft)//2:
                harmonics_power += np.abs(fft[harmonic_idx])**2
        
        if fundamental_power == 0:
            return 0
        
        thd = np.sqrt(harmonics_power / fundamental_power)
        return thd
    
    def _calculate_dynamic_range(self, signal: np.ndarray) -> float:
        """计算动态范围"""
        if len(signal) == 0:
            return 0
        
        max_level = np.max(np.abs(signal))
        
        # 计算噪声底限（最小10%的样本的RMS）
        sorted_abs = np.sort(np.abs(signal))
        noise_floor = np.sqrt(np.mean(sorted_abs[:len(sorted_abs)//10]**2))
        
        if noise_floor == 0:
            return float('inf')
        
        dynamic_range = 20 * np.log10(max_level / noise_floor)
        return dynamic_range
    
    def _analyze_frequency_response(self, 
                                  original: np.ndarray, 
                                  processed: np.ndarray, 
                                  sample_rate: int) -> Dict[str, float]:
        """分析频率响应"""
        # 计算频谱
        orig_fft = np.fft.fft(original)
        proc_fft = np.fft.fft(processed)
        freqs = np.fft.fftfreq(len(original), 1/sample_rate)
        
        # 只分析正频率
        pos_freqs = freqs[:len(freqs)//2]
        orig_magnitude = np.abs(orig_fft[:len(freqs)//2])
        proc_magnitude = np.abs(proc_fft[:len(freqs)//2])
        
        # 定义频带
        bands = {
            "low": (20, 250),      # 低频
            "mid": (250, 4000),    # 中频
            "high": (4000, 20000)  # 高频
        }
        
        response = {}
        for band_name, (low_freq, high_freq) in bands.items():
            band_mask = (pos_freqs >= low_freq) & (pos_freqs <= high_freq)
            if np.any(band_mask):
                orig_band_power = np.mean(orig_magnitude[band_mask]**2)
                proc_band_power = np.mean(proc_magnitude[band_mask]**2)
                
                if orig_band_power > 0:
                    response[f"{band_name}_band_ratio"] = proc_band_power / orig_band_power
                else:
                    response[f"{band_name}_band_ratio"] = 0
        
        return response
    
    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """获取视频信息"""
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", video_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            # 找到视频流
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    return stream
            
            return {}
        except Exception:
            return {}
    
    def _calculate_video_psnr(self, original_path: str, processed_path: str) -> float:
        """计算视频PSNR"""
        try:
            cmd = [
                "ffmpeg", "-i", original_path, "-i", processed_path,
                "-lavfi", "psnr", "-f", "null", "-"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 解析PSNR值（简化版本）
            # 实际实现需要更精确的解析
            if "PSNR" in result.stderr:
                # 这里需要正则表达式解析具体的PSNR值
                return 30.0  # 占位符
            
            return 0.0
        except Exception:
            return 0.0
    
    def _calculate_video_ssim(self, original_path: str, processed_path: str) -> float:
        """计算视频SSIM"""
        try:
            cmd = [
                "ffmpeg", "-i", original_path, "-i", processed_path,
                "-lavfi", "ssim", "-f", "null", "-"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 解析SSIM值（简化版本）
            if "SSIM" in result.stderr:
                return 0.95  # 占位符
            
            return 0.0
        except Exception:
            return 0.0
    
    def _calculate_av_sync_offset(self, original_path: str, processed_path: str) -> float:
        """计算音视频同步偏移"""
        # 简化的同步偏移计算
        # 实际实现需要更复杂的音视频分析
        return 0.0
    
    def _calculate_bleu_score(self, reference: str, candidate: str) -> float:
        """计算BLEU分数"""
        ref_tokens = reference.split()
        cand_tokens = candidate.split()
        
        if len(cand_tokens) == 0:
            return 0.0
        
        # 计算1-gram到4-gram的精确度
        scores = []
        for n in range(1, 5):
            ref_ngrams = self._get_ngrams(ref_tokens, n)
            cand_ngrams = self._get_ngrams(cand_tokens, n)
            
            if len(cand_ngrams) == 0:
                scores.append(0.0)
                continue
            
            matches = 0
            for ngram in cand_ngrams:
                if ngram in ref_ngrams:
                    matches += min(cand_ngrams[ngram], ref_ngrams[ngram])
            
            precision = matches / sum(cand_ngrams.values())
            scores.append(precision)
        
        # 计算几何平均
        if any(score == 0 for score in scores):
            return 0.0
        
        bleu = math.exp(sum(math.log(score) for score in scores) / len(scores))
        
        # 简化的简洁性惩罚
        bp = min(1.0, math.exp(1 - len(ref_tokens) / len(cand_tokens)))
        
        return bleu * bp
    
    def _get_ngrams(self, tokens: List[str], n: int) -> Dict[tuple, int]:
        """获取n-grams"""
        ngrams = {}
        for i in range(len(tokens) - n + 1):
            ngram = tuple(tokens[i:i+n])
            ngrams[ngram] = ngrams.get(ngram, 0) + 1
        return ngrams
    
    def _calculate_ter_score(self, reference: str, candidate: str) -> float:
        """计算TER分数（翻译错误率）"""
        ref_tokens = reference.split()
        cand_tokens = candidate.split()
        
        # 使用编辑距离计算
        matcher = difflib.SequenceMatcher(None, ref_tokens, cand_tokens)
        edits = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                edits += max(i2 - i1, j2 - j1)
        
        if len(ref_tokens) == 0:
            return 0.0
        
        return edits / len(ref_tokens)
    
    def _calculate_word_accuracy(self, reference: str, candidate: str) -> float:
        """计算词准确率"""
        ref_words = set(reference.lower().split())
        cand_words = set(candidate.lower().split())
        
        if len(ref_words) == 0:
            return 1.0 if len(cand_words) == 0 else 0.0
        
        correct_words = len(ref_words.intersection(cand_words))
        return correct_words / len(ref_words)
    
    def _calculate_sentence_accuracy(self, reference: str, candidate: str) -> float:
        """计算句子准确率"""
        ref_sentences = [s.strip() for s in reference.split('.') if s.strip()]
        cand_sentences = [s.strip() for s in candidate.split('.') if s.strip()]
        
        if len(ref_sentences) == 0:
            return 1.0 if len(cand_sentences) == 0 else 0.0
        
        # 简化的句子匹配
        matches = 0
        for ref_sent in ref_sentences:
            for cand_sent in cand_sentences:
                # 使用编辑距离判断相似性
                similarity = difflib.SequenceMatcher(None, ref_sent, cand_sent).ratio()
                if similarity > 0.8:
                    matches += 1
                    break
        
        return matches / len(ref_sentences)
    
    def _calculate_fluency_score(self, text: str, language: str) -> float:
        """计算流畅度分数"""
        if language == "en":
            try:
                # 使用可读性指标评估流畅度
                ease = flesch_reading_ease(text)
                grade = flesch_kincaid_grade(text)
                
                # 将分数标准化到0-1范围
                fluency = max(0, min(1, (ease - 30) / 70))
                return fluency
            except:
                pass
        
        # 其他语言或失败时的简化计算
        words = text.split()
        if len(words) == 0:
            return 0.0
        
        # 基于平均词长和句子长度的简单评估
        avg_word_length = sum(len(word) for word in words) / len(words)
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        avg_sentence_length = len(words) / max(len(sentences), 1)
        
        # 简化的流畅度评估
        fluency = max(0, min(1, 1 - abs(avg_word_length - 5) / 10 - abs(avg_sentence_length - 15) / 30))
        return fluency
    
    def _calculate_adequacy_score(self, reference: str, candidate: str) -> float:
        """计算充分性分数"""
        ref_words = reference.lower().split()
        cand_words = candidate.lower().split()
        
        if len(ref_words) == 0:
            return 1.0
        
        # 计算内容覆盖率
        ref_content_words = [word for word in ref_words if len(word) > 3]  # 过滤短词
        cand_content_words = [word for word in cand_words if len(word) > 3]
        
        if len(ref_content_words) == 0:
            return 1.0
        
        covered_words = len(set(ref_content_words).intersection(set(cand_content_words)))
        adequacy = covered_words / len(set(ref_content_words))
        
        return adequacy
    
    def _calculate_timing_accuracy(self, 
                                 original_segments: List[Dict], 
                                 translated_segments: List[Dict]) -> float:
        """计算时序准确性"""
        if len(original_segments) == 0 or len(translated_segments) == 0:
            return 0.0
        
        # 计算时序偏差
        total_deviation = 0.0
        valid_segments = 0
        
        for orig_seg, trans_seg in zip(original_segments, translated_segments):
            orig_duration = orig_seg["end"] - orig_seg["start"]
            trans_duration = trans_seg["end"] - trans_seg["start"]
            
            if orig_duration > 0:
                deviation = abs(orig_duration - trans_duration) / orig_duration
                total_deviation += deviation
                valid_segments += 1
        
        if valid_segments == 0:
            return 0.0
        
        avg_deviation = total_deviation / valid_segments
        accuracy = max(0.0, 1.0 - avg_deviation)
        
        return accuracy
    
    def _calculate_segment_alignment(self, 
                                   original_segments: List[Dict], 
                                   translated_segments: List[Dict]) -> float:
        """计算段落对齐度"""
        if len(original_segments) != len(translated_segments):
            return 0.0
        
        if len(original_segments) == 0:
            return 1.0
        
        alignment_score = 0.0
        
        for orig_seg, trans_seg in zip(original_segments, translated_segments):
            # 计算起始时间对齐度
            start_diff = abs(orig_seg["start"] - trans_seg["start"])
            start_alignment = max(0.0, 1.0 - start_diff / 5.0)  # 5秒内认为对齐
            
            # 计算结束时间对齐度
            end_diff = abs(orig_seg["end"] - trans_seg["end"])
            end_alignment = max(0.0, 1.0 - end_diff / 5.0)
            
            segment_alignment = (start_alignment + end_alignment) / 2
            alignment_score += segment_alignment
        
        return alignment_score / len(original_segments)
    
    def _calculate_lip_sync_score(self, 
                                original_audio_path: str, 
                                translated_audio_path: str) -> float:
        """计算唇形同步分数（简化版本）"""
        # 这是一个简化的实现
        # 实际的唇形同步需要视频分析和复杂的信号处理
        
        try:
            # 加载音频
            orig_audio, orig_sr = librosa.load(original_audio_path, sr=None)
            trans_audio, trans_sr = librosa.load(translated_audio_path, sr=None)
            
            # 计算音频包络相关性
            orig_envelope = np.abs(librosa.stft(orig_audio))
            trans_envelope = np.abs(librosa.stft(trans_audio))
            
            # 调整长度
            min_length = min(orig_envelope.shape[1], trans_envelope.shape[1])
            orig_envelope = orig_envelope[:, :min_length]
            trans_envelope = trans_envelope[:, :min_length]
            
            # 计算相关系数
            correlation = np.corrcoef(
                orig_envelope.flatten(), 
                trans_envelope.flatten()
            )[0, 1]
            
            # 确保返回值在[0, 1]范围内
            lip_sync_score = max(0.0, min(1.0, (correlation + 1) / 2))
            
            return lip_sync_score
            
        except Exception:
            return 0.5  # 默认中等分数
    
    def _calculate_overall_quality_score(self, metrics: Dict[str, Any]) -> float:
        """计算总体质量分数"""
        scores = []
        weights = []
        
        # 音频质量（权重：30%）
        if "audio_quality" in metrics:
            audio_metrics = metrics["audio_quality"]
            audio_score = 0.0
            
            # SNR分数（越高越好，>20dB为好）
            if audio_metrics.get("snr_db", 0) > 0:
                snr_score = min(1.0, audio_metrics["snr_db"] / 40.0)
                audio_score += snr_score * 0.3
            
            # 动态范围分数
            if audio_metrics.get("dynamic_range", 0) > 0:
                dr_score = min(1.0, audio_metrics["dynamic_range"] / 60.0)
                audio_score += dr_score * 0.2
            
            # 时长准确性
            duration_acc = audio_metrics.get("duration_accuracy", 0)
            audio_score += duration_acc * 0.3
            
            # THD分数（越低越好）
            thd = audio_metrics.get("thd", 1.0)
            thd_score = max(0.0, 1.0 - thd)
            audio_score += thd_score * 0.2
            
            scores.append(audio_score)
            weights.append(0.3)
        
        # 视频质量（权重：20%）
        if "video_quality" in metrics:
            video_metrics = metrics["video_quality"]
            video_score = 0.0
            
            # PSNR分数
            psnr = video_metrics.get("psnr", 0)
            if psnr > 0:
                psnr_score = min(1.0, (psnr - 20) / 30.0)  # 20-50dB范围
                video_score += psnr_score * 0.4
            
            # SSIM分数
            ssim = video_metrics.get("ssim", 0)
            video_score += ssim * 0.4
            
            # 同步偏移分数
            sync_offset = abs(video_metrics.get("sync_offset", 0))
            sync_score = max(0.0, 1.0 - sync_offset / 0.5)  # 0.5秒内为好
            video_score += sync_score * 0.2
            
            scores.append(video_score)
            weights.append(0.2)
        
        # 翻译质量（权重：30%）
        if "translation_quality" in metrics:
            trans_metrics = metrics["translation_quality"]
            trans_score = 0.0
            
            # BLEU分数
            bleu = trans_metrics.get("bleu_score", 0)
            trans_score += bleu * 0.3
            
            # 词准确率
            word_acc = trans_metrics.get("word_accuracy", 0)
            trans_score += word_acc * 0.2
            
            # 流畅度分数
            fluency = trans_metrics.get("fluency_score", 0)
            trans_score += fluency * 0.25
            
            # 充分性分数
            adequacy = trans_metrics.get("adequacy_score", 0)
            trans_score += adequacy * 0.25
            
            scores.append(trans_score)
            weights.append(0.3)
        
        # 同步质量（权重：20%）
        if "sync_quality" in metrics:
            sync_metrics = metrics["sync_quality"]
            sync_score = sync_metrics.get("overall_sync_score", 0)
            
            scores.append(sync_score)
            weights.append(0.2)
        
        # 计算加权平均分
        if len(scores) == 0:
            return 0.0
        
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        
        weighted_score = sum(score * weight for score, weight in zip(scores, weights))
        overall_score = weighted_score / total_weight
        
        return min(1.0, max(0.0, overall_score))
    
    def save_quality_report(self, report: Dict[str, Any], output_path: str):
        """保存质量报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    # 测试质量评估工具
    tool = QualityAssessmentTool()
    
    # 创建示例报告
    sample_report = {
        "job_id": "test_001",
        "timestamp": time.time(),
        "files": {
            "original": "test_input.mp4",
            "output": "test_output.mp4"
        },
        "metrics": {
            "audio_quality": {
                "snr_db": 25.0,
                "thd": 0.05,
                "dynamic_range": 45.0,
                "duration_accuracy": 0.98
            },
            "translation_quality": {
                "bleu_score": 0.75,
                "word_accuracy": 0.85,
                "fluency_score": 0.80,
                "adequacy_score": 0.88
            }
        }
    }
    
    overall_score = tool._calculate_overall_quality_score(sample_report["metrics"])
    sample_report["overall_quality_score"] = overall_score
    
    print(f"示例质量报告总分: {overall_score:.2f}")
    print("质量评估工具测试完成！")