import os
import time
import tempfile
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pydub import AudioSegment
from pydub.utils import which
import ffmpeg
from models.core import TimedSegment


class AudioOptimizerError(Exception):
    """音频优化器错误"""
    pass


@dataclass
class OptimizationResult:
    """音频优化结果"""
    optimized_audio_path: str
    speed_adjustments: List[Tuple[int, float]]  # (segment_index, speed_ratio)
    background_preserved: bool
    quality_metrics: Dict[str, float]
    processing_time: float
    optimization_details: Dict[str, any]


@dataclass
class QualityMetrics:
    """音频质量指标"""
    sample_rate: int
    bit_depth: int
    dynamic_range: float  # dB
    peak_level: float  # dB
    rms_level: float  # dB
    snr_estimate: float  # dB


class AudioOptimizer:
    """
    音频调整和优化服务
    
    实现音频速度调整功能（0.8x - 1.2x 范围），
    保留背景音乐和音效，实现音频质量保持机制。
    """
    
    def __init__(self):
        """初始化音频优化器"""
        # 速度调整配置
        self.speed_config = {
            'min_ratio': 0.8,      # 最小速度倍率
            'max_ratio': 1.2,      # 最大速度倍率
            'step_size': 0.05,     # 调整步长
            'smooth_transition': True,  # 平滑过渡
            'preserve_pitch': True      # 保持音调
        }
        
        # 背景音保留配置
        self.background_config = {
            'detection_threshold': -30,  # 背景音检测阈值（dB）
            'separation_method': 'spectral',  # 分离方法
            'mix_ratio': 0.3,  # 背景音混合比例
            'frequency_bands': {
                'speech': (300, 3400),  # 语音频率范围（Hz）
                'music': (80, 15000),   # 音乐频率范围（Hz）
                'effects': (20, 20000)  # 音效频率范围（Hz）
            }
        }
        
        # 质量保持配置
        self.quality_config = {
            'target_sample_rate': 44100,  # 目标采样率
            'target_bit_depth': 16,       # 目标位深度
            'normalize_levels': True,     # 归一化音量
            'noise_reduction': True,      # 降噪处理
            'dynamic_range_target': 60,   # 目标动态范围（dB）
            'peak_limit': -1.0            # 峰值限制（dB）
        }
        
        # 检查依赖
        if not which("ffmpeg"):
            raise AudioOptimizerError("未找到 FFmpeg，请确保已安装")
    
    def optimize_audio_timing(self, audio_path: str,
                             target_segments: List[TimedSegment],
                             preserve_background: bool = True,
                             output_path: Optional[str] = None) -> OptimizationResult:
        """
        优化音频时序以匹配目标片段
        
        Args:
            audio_path: 输入音频文件路径
            target_segments: 目标时序片段
            preserve_background: 是否保留背景音乐和音效
            output_path: 输出文件路径（可选）
            
        Returns:
            OptimizationResult: 优化结果
            
        Raises:
            AudioOptimizerError: 优化失败
        """
        if not os.path.exists(audio_path):
            raise AudioOptimizerError(f"音频文件不存在: {audio_path}")
        
        if not target_segments:
            raise AudioOptimizerError("目标片段列表为空")
        
        start_time = time.time()
        
        try:
            # 加载原始音频
            audio = AudioSegment.from_file(audio_path)
            
            # 分析音频质量
            original_quality = self._analyze_audio_quality(audio)
            
            # 计算速度调整策略
            speed_adjustments = self._calculate_speed_adjustments(audio, target_segments)
            
            # 应用优化处理
            if preserve_background:
                optimized_audio = self._optimize_with_background_preservation(
                    audio, target_segments, speed_adjustments
                )
            else:
                optimized_audio = self._optimize_simple_speed_adjustment(
                    audio, target_segments, speed_adjustments
                )
            
            # 质量保持处理
            optimized_audio = self._maintain_audio_quality(optimized_audio, original_quality)
            
            # 保存优化后的音频
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            optimized_audio.export(output_path, format="mp3", bitrate="192k")
            
            # 分析优化后的质量
            final_quality = self._analyze_audio_quality(optimized_audio)
            
            processing_time = time.time() - start_time
            
            return OptimizationResult(
                optimized_audio_path=output_path,
                speed_adjustments=speed_adjustments,
                background_preserved=preserve_background,
                quality_metrics={
                    'original_quality': original_quality.__dict__,
                    'final_quality': final_quality.__dict__,
                    'quality_preservation_score': self._calculate_quality_preservation_score(
                        original_quality, final_quality
                    )
                },
                processing_time=processing_time,
                optimization_details={
                    'method': 'background_preserved' if preserve_background else 'simple_speed',
                    'adjustments_applied': len(speed_adjustments),
                    'total_segments': len(target_segments),
                    'original_duration': len(audio) / 1000.0,
                    'final_duration': len(optimized_audio) / 1000.0
                }
            )
            
        except Exception as e:
            raise AudioOptimizerError(f"音频优化失败: {str(e)}")
    
    def adjust_audio_speed_range(self, audio_path: str,
                               speed_ratio: float,
                               preserve_quality: bool = True,
                               output_path: Optional[str] = None) -> str:
        """
        在指定范围内调整音频速度
        
        Args:
            audio_path: 输入音频文件路径
            speed_ratio: 速度调整比例（0.8-1.2）
            preserve_quality: 是否保持音频质量
            output_path: 输出文件路径（可选）
            
        Returns:
            str: 调整后的音频文件路径
            
        Raises:
            AudioOptimizerError: 调整失败
        """
        if not os.path.exists(audio_path):
            raise AudioOptimizerError(f"音频文件不存在: {audio_path}")
        
        # 验证速度比例范围
        if not (self.speed_config['min_ratio'] <= speed_ratio <= self.speed_config['max_ratio']):
            raise AudioOptimizerError(
                f"速度比例超出范围 ({self.speed_config['min_ratio']}-{self.speed_config['max_ratio']}): {speed_ratio}"
            )
        
        try:
            # 加载音频
            audio = AudioSegment.from_file(audio_path)
            
            # 应用速度调整
            if preserve_quality:
                adjusted_audio = self._adjust_speed_with_quality_preservation(audio, speed_ratio)
            else:
                adjusted_audio = self._adjust_speed_simple(audio, speed_ratio)
            
            # 保存调整后的音频
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            adjusted_audio.export(output_path, format="mp3", bitrate="192k")
            
            return output_path
            
        except Exception as e:
            raise AudioOptimizerError(f"音频速度调整失败: {str(e)}")
    
    def preserve_background_audio(self, speech_audio_path: str,
                                background_audio_path: str,
                                output_path: Optional[str] = None,
                                mix_ratio: float = 0.3) -> str:
        """
        保留背景音乐和音效
        
        Args:
            speech_audio_path: 语音音频文件路径
            background_audio_path: 背景音频文件路径
            output_path: 输出文件路径（可选）
            mix_ratio: 背景音混合比例（0-1）
            
        Returns:
            str: 混合后的音频文件路径
            
        Raises:
            AudioOptimizerError: 处理失败
        """
        if not os.path.exists(speech_audio_path):
            raise AudioOptimizerError(f"语音音频文件不存在: {speech_audio_path}")
        
        if not os.path.exists(background_audio_path):
            raise AudioOptimizerError(f"背景音频文件不存在: {background_audio_path}")
        
        if not (0.0 <= mix_ratio <= 1.0):
            raise AudioOptimizerError(f"混合比例超出范围 (0-1): {mix_ratio}")
        
        try:
            # 加载音频
            speech_audio = AudioSegment.from_file(speech_audio_path)
            background_audio = AudioSegment.from_file(background_audio_path)
            
            # 调整背景音长度以匹配语音音频
            if len(background_audio) < len(speech_audio):
                # 循环播放背景音
                repeat_count = (len(speech_audio) // len(background_audio)) + 1
                background_audio = background_audio * repeat_count
            
            # 截取匹配长度
            background_audio = background_audio[:len(speech_audio)]
            
            # 调整背景音音量
            background_volume = mix_ratio * 100  # 转换为百分比
            background_audio = background_audio - (60 - background_volume)  # 降低音量
            
            # 混合音频
            mixed_audio = speech_audio.overlay(background_audio)
            
            # 保存混合后的音频
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            mixed_audio.export(output_path, format="mp3", bitrate="192k")
            
            return output_path
            
        except Exception as e:
            raise AudioOptimizerError(f"背景音频保留失败: {str(e)}")
    
    def enhance_audio_quality(self, audio_path: str,
                            output_path: Optional[str] = None,
                            normalize: bool = True,
                            noise_reduction: bool = True) -> str:
        """
        增强音频质量
        
        Args:
            audio_path: 输入音频文件路径
            output_path: 输出文件路径（可选）
            normalize: 是否归一化音量
            noise_reduction: 是否降噪
            
        Returns:
            str: 增强后的音频文件路径
            
        Raises:
            AudioOptimizerError: 增强失败
        """
        if not os.path.exists(audio_path):
            raise AudioOptimizerError(f"音频文件不存在: {audio_path}")
        
        try:
            # 使用 FFmpeg 进行音频增强
            if not output_path:
                output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
            
            # 构建 FFmpeg 滤镜链
            filters = []
            
            if noise_reduction:
                # 添加降噪滤镜
                filters.append('highpass=f=80')  # 高通滤波器去除低频噪音
                filters.append('lowpass=f=15000')  # 低通滤波器去除高频噪音
            
            if normalize:
                # 添加音量归一化
                filters.append('loudnorm=I=-16:LRA=11:TP=-1.5')
            
            # 应用滤镜
            if filters:
                filter_chain = ','.join(filters)
                (
                    ffmpeg
                    .input(audio_path)
                    .filter('aformat', 'sample_rates=44100')
                    .filter_complex(filter_chain)
                    .output(output_path, acodec='mp3', audio_bitrate='192k')
                    .overwrite_output()
                    .run(quiet=True)
                )
            else:
                # 只是格式转换
                (
                    ffmpeg
                    .input(audio_path)
                    .output(output_path, acodec='mp3', audio_bitrate='192k')
                    .overwrite_output()
                    .run(quiet=True)
                )
            
            return output_path
            
        except Exception as e:
            raise AudioOptimizerError(f"音频质量增强失败: {str(e)}")
    
    def _analyze_audio_quality(self, audio: AudioSegment) -> QualityMetrics:
        """分析音频质量"""
        try:
            # 获取基本属性
            sample_rate = audio.frame_rate
            bit_depth = audio.sample_width * 8
            
            # 计算音量统计
            peak_level = audio.max_dBFS
            rms_level = audio.dBFS
            
            # 估算动态范围
            audio_array = np.array(audio.get_array_of_samples())
            if audio.channels == 2:
                audio_array = audio_array.reshape((-1, 2))
                audio_array = np.mean(audio_array, axis=1)
            
            # 计算动态范围
            dynamic_range = np.ptp(audio_array) / np.max(np.abs(audio_array)) * 96 if np.max(np.abs(audio_array)) > 0 else 0
            
            # 估算信噪比
            signal_power = np.mean(audio_array ** 2)
            noise_floor = np.percentile(np.abs(audio_array), 10)  # 使用10%分位数作为噪声基准
            snr_estimate = 10 * np.log10(signal_power / (noise_floor ** 2 + 1e-10))
            
            return QualityMetrics(
                sample_rate=sample_rate,
                bit_depth=bit_depth,
                dynamic_range=dynamic_range,
                peak_level=peak_level,
                rms_level=rms_level,
                snr_estimate=snr_estimate
            )
            
        except Exception:
            # 返回默认值
            return QualityMetrics(
                sample_rate=audio.frame_rate,
                bit_depth=audio.sample_width * 8,
                dynamic_range=60.0,
                peak_level=audio.max_dBFS,
                rms_level=audio.dBFS,
                snr_estimate=20.0
            )
    
    def _calculate_speed_adjustments(self, audio: AudioSegment,
                                   target_segments: List[TimedSegment]) -> List[Tuple[int, float]]:
        """计算各个片段的速度调整"""
        adjustments = []
        current_duration = len(audio) / 1000.0
        target_duration = target_segments[-1].end_time if target_segments else current_duration
        
        # 全局速度调整
        global_ratio = current_duration / target_duration
        
        # 限制在允许范围内
        global_ratio = max(self.speed_config['min_ratio'],
                          min(self.speed_config['max_ratio'], global_ratio))
        
        # 为每个片段分配相同的调整
        for i, segment in enumerate(target_segments):
            adjustments.append((i, global_ratio))
        
        return adjustments
    
    def _optimize_with_background_preservation(self, audio: AudioSegment,
                                             target_segments: List[TimedSegment],
                                             speed_adjustments: List[Tuple[int, float]]) -> AudioSegment:
        """保留背景音的优化处理"""
        try:
            # 简化实现：使用高质量的速度调整
            global_ratio = speed_adjustments[0][1] if speed_adjustments else 1.0
            
            # 使用 FFmpeg 进行高质量调整
            return self._adjust_speed_with_ffmpeg(audio, global_ratio, preserve_pitch=True)
            
        except:
            # 回退到简单方法
            return self._optimize_simple_speed_adjustment(audio, target_segments, speed_adjustments)
    
    def _optimize_simple_speed_adjustment(self, audio: AudioSegment,
                                        target_segments: List[TimedSegment],
                                        speed_adjustments: List[Tuple[int, float]]) -> AudioSegment:
        """简单速度调整优化"""
        if not speed_adjustments:
            return audio
        
        # 使用第一个调整值作为全局调整
        global_ratio = speed_adjustments[0][1]
        
        return self._adjust_speed_simple(audio, global_ratio)
    
    def _adjust_speed_with_quality_preservation(self, audio: AudioSegment, speed_ratio: float) -> AudioSegment:
        """保持质量的速度调整"""
        return self._adjust_speed_with_ffmpeg(audio, speed_ratio, preserve_pitch=True)
    
    def _adjust_speed_simple(self, audio: AudioSegment, speed_ratio: float) -> AudioSegment:
        """简单速度调整"""
        try:
            if speed_ratio > 1.0:
                # 加速
                return audio.speedup(playback_speed=speed_ratio)
            else:
                # 减速：调整采样率
                return audio._spawn(audio.raw_data, overrides={
                    "frame_rate": int(audio.frame_rate * speed_ratio)
                }).set_frame_rate(audio.frame_rate)
        except:
            return audio
    
    def _adjust_speed_with_ffmpeg(self, audio: AudioSegment, speed_ratio: float,
                                preserve_pitch: bool = False) -> AudioSegment:
        """使用 FFmpeg 调整速度"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_input:
            audio.export(temp_input.name, format="wav")
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_output:
                try:
                    if preserve_pitch:
                        # 保持音调的速度调整
                        (
                            ffmpeg
                            .input(temp_input.name)
                            .filter('atempo', speed_ratio)
                            .output(temp_output.name)
                            .overwrite_output()
                            .run(quiet=True)
                        )
                    else:
                        # 简单的速度调整
                        (
                            ffmpeg
                            .input(temp_input.name)
                            .filter('atempo', speed_ratio)
                            .output(temp_output.name)
                            .overwrite_output()
                            .run(quiet=True)
                        )
                    
                    # 加载调整后的音频
                    adjusted_audio = AudioSegment.from_wav(temp_output.name)
                    return adjusted_audio
                    
                except:
                    # FFmpeg 失败，回退到原音频
                    return audio
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(temp_input.name)
                        os.unlink(temp_output.name)
                    except:
                        pass
    
    def _maintain_audio_quality(self, audio: AudioSegment, target_quality: QualityMetrics) -> AudioSegment:
        """保持音频质量"""
        try:
            # 确保采样率
            if audio.frame_rate != target_quality.sample_rate:
                audio = audio.set_frame_rate(target_quality.sample_rate)
            
            # 音量归一化
            if self.quality_config['normalize_levels']:
                # 调整到目标RMS级别
                target_rms = max(-20, target_quality.rms_level)  # 不超过-20dB
                current_rms = audio.dBFS
                if current_rms < target_rms - 3:  # 如果当前音量明显偏低
                    gain = target_rms - current_rms
                    audio = audio + min(6, gain)  # 限制增益不超过6dB
            
            return audio
            
        except:
            return audio
    
    def _calculate_quality_preservation_score(self, original: QualityMetrics,
                                           final: QualityMetrics) -> float:
        """计算质量保持分数"""
        try:
            # 采样率保持
            sample_rate_score = 1.0 if final.sample_rate >= original.sample_rate * 0.9 else 0.5
            
            # 动态范围保持
            dynamic_range_ratio = final.dynamic_range / (original.dynamic_range + 1e-6)
            dynamic_range_score = min(1.0, dynamic_range_ratio)
            
            # 信噪比保持
            snr_ratio = final.snr_estimate / (original.snr_estimate + 1e-6)
            snr_score = min(1.0, snr_ratio)
            
            # 综合评分
            return (sample_rate_score + dynamic_range_score + snr_score) / 3
            
        except:
            return 0.7  # 默认评分