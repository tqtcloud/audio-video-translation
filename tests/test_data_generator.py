#!/usr/bin/env python3
"""
测试数据生成器
生成各种格式的测试音频和视频文件
"""

import os
import subprocess
import tempfile
import json
import time
import random
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class TestDataSpec:
    """测试数据规格"""
    file_type: str  # "audio" or "video"
    format: str     # 文件格式 (mp4, avi, mov, mp3, wav等)
    duration: float # 持续时间（秒）
    sample_rate: int = 44100  # 音频采样率
    channels: int = 2         # 音频声道数
    video_resolution: Optional[str] = None  # 视频分辨率 "1920x1080"
    video_fps: int = 30       # 视频帧率
    content_type: str = "speech"  # "speech", "music", "mixed", "silence"
    language: str = "en"      # 语言
    speech_text: Optional[str] = None  # 语音内容


class TestDataGenerator:
    """测试数据生成器"""
    
    def __init__(self, output_dir: str = "./test_data"):
        """初始化生成器"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 预定义的测试文本
        self.test_texts = {
            "en": [
                "Hello world, this is a test audio file for speech recognition.",
                "The quick brown fox jumps over the lazy dog.",
                "Testing audio video translation system with various content types.",
                "This audio contains multiple sentences for better testing coverage.",
                "Quality assurance is important for reliable translation services."
            ],
            "zh-CN": [
                "你好世界，这是一个用于语音识别的测试音频文件。",
                "快速的棕色狐狸跳过懒惰的狗。",
                "测试音频视频翻译系统的各种内容类型。",
                "这个音频包含多个句子以获得更好的测试覆盖率。",
                "质量保证对于可靠的翻译服务很重要。"
            ],
            "es": [
                "Hola mundo, este es un archivo de audio de prueba para reconocimiento de voz.",
                "El rápido zorro marrón salta sobre el perro perezoso.",
                "Probando el sistema de traducción de audio y video con varios tipos de contenido.",
                "Este audio contiene múltiples oraciones para una mejor cobertura de prueba.",
                "El control de calidad es importante para servicios de traducción confiables."
            ],
            "fr": [
                "Bonjour le monde, ceci est un fichier audio de test pour la reconnaissance vocale.",
                "Le renard brun rapide saute par-dessus le chien paresseux.",
                "Test du système de traduction audio-vidéo avec différents types de contenu.",
                "Cet audio contient plusieurs phrases pour une meilleure couverture de test.",
                "Le contrôle qualité est important pour des services de traduction fiables."
            ],
            "de": [
                "Hallo Welt, dies ist eine Test-Audiodatei für Spracherkennung.",
                "Der schnelle braune Fuchs springt über den faulen Hund.",
                "Testen des Audio-Video-Übersetzungssystems mit verschiedenen Inhaltstypen.",
                "Dieses Audio enthält mehrere Sätze für eine bessere Testabdeckung.",
                "Qualitätssicherung ist wichtig für zuverlässige Übersetzungsdienste."
            ]
        }
    
    def generate_test_dataset(self, specs: List[TestDataSpec]) -> Dict[str, str]:
        """
        生成测试数据集
        
        Args:
            specs: 测试数据规格列表
            
        Returns:
            生成的文件路径字典
        """
        generated_files = {}
        
        for i, spec in enumerate(specs):
            filename = f"test_{spec.file_type}_{spec.format}_{i+1:03d}.{spec.format}"
            output_path = self.output_dir / filename
            
            if spec.file_type == "audio":
                file_path = self._generate_audio_file(spec, output_path)
            elif spec.file_type == "video":
                file_path = self._generate_video_file(spec, output_path)
            else:
                raise ValueError(f"不支持的文件类型: {spec.file_type}")
            
            generated_files[filename] = str(file_path)
        
        # 保存数据集信息
        dataset_info = {
            "generated_at": time.time(),
            "total_files": len(generated_files),
            "files": generated_files,
            "specs": [asdict(spec) for spec in specs]
        }
        
        info_path = self.output_dir / "dataset_info.json"
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(dataset_info, f, indent=2, ensure_ascii=False)
        
        return generated_files
    
    def _generate_audio_file(self, spec: TestDataSpec, output_path: Path) -> str:
        """生成音频文件"""
        if spec.content_type == "speech":
            return self._generate_speech_audio(spec, output_path)
        elif spec.content_type == "music":
            return self._generate_music_audio(spec, output_path)
        elif spec.content_type == "mixed":
            return self._generate_mixed_audio(spec, output_path)
        elif spec.content_type == "silence":
            return self._generate_silence_audio(spec, output_path)
        else:
            raise ValueError(f"不支持的音频内容类型: {spec.content_type}")
    
    def _generate_speech_audio(self, spec: TestDataSpec, output_path: Path) -> str:
        """生成语音音频文件"""
        # 选择测试文本
        if spec.speech_text:
            text = spec.speech_text
        else:
            texts = self.test_texts.get(spec.language, self.test_texts["en"])
            text = random.choice(texts)
        
        # 使用 espeak 或 festival 生成语音（如果可用）
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        
        try:
            # 尝试使用 espeak 生成语音
            cmd = [
                "espeak", 
                "-v", spec.language,
                "-s", "150",  # 语速
                "-w", temp_wav.name,
                text
            ]
            
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode != 0:
                # 如果 espeak 不可用，生成正弦波作为替代
                self._generate_tone_audio(spec, temp_wav.name)
        
        except FileNotFoundError:
            # 如果 espeak 不可用，生成正弦波作为替代
            self._generate_tone_audio(spec, temp_wav.name)
        
        # 转换为目标格式
        return self._convert_audio_format(temp_wav.name, spec, output_path)
    
    def _generate_tone_audio(self, spec: TestDataSpec, output_path: str):
        """生成音调音频（作为语音的替代）"""
        # 使用 ffmpeg 生成正弦波
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={spec.duration}:sample_rate={spec.sample_rate}",
            "-ac", str(spec.channels),
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
    
    def _generate_music_audio(self, spec: TestDataSpec, output_path: Path) -> str:
        """生成音乐音频文件"""
        # 生成多音调混合的音乐
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        
        # 使用 ffmpeg 生成音乐（多个正弦波的混合）
        frequencies = [440, 554, 659, 880]  # C, C#, E, C 和声
        filter_complex = []
        for i, freq in enumerate(frequencies):
            filter_complex.append(f"sine=frequency={freq}:duration={spec.duration}:sample_rate={spec.sample_rate}[s{i}]")
        
        filter_complex.append(f"{''.join(f'[s{i}]' for i in range(len(frequencies)))}amix=inputs={len(frequencies)}:duration=longest")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", ";".join(filter_complex),
            "-ac", str(spec.channels),
            temp_wav.name
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        return self._convert_audio_format(temp_wav.name, spec, output_path)
    
    def _generate_mixed_audio(self, spec: TestDataSpec, output_path: Path) -> str:
        """生成混合音频文件（语音+背景音乐）"""
        # 先生成语音
        speech_spec = TestDataSpec(
            file_type="audio",
            format="wav",
            duration=spec.duration * 0.7,  # 语音占70%时间
            sample_rate=spec.sample_rate,
            channels=spec.channels,
            content_type="speech",
            language=spec.language
        )
        
        temp_speech = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._generate_speech_audio(speech_spec, Path(temp_speech.name))
        
        # 生成背景音乐
        music_spec = TestDataSpec(
            file_type="audio",
            format="wav",
            duration=spec.duration,
            sample_rate=spec.sample_rate,
            channels=spec.channels,
            content_type="music"
        )
        
        temp_music = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._generate_music_audio(music_spec, Path(temp_music.name))
        
        # 混合音频
        temp_mixed = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        cmd = [
            "ffmpeg", "-y",
            "-i", temp_speech.name,
            "-i", temp_music.name,
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=longest:weights=0.8 0.2",
            temp_mixed.name
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        # 清理临时文件
        os.unlink(temp_speech.name)
        os.unlink(temp_music.name)
        
        return self._convert_audio_format(temp_mixed.name, spec, output_path)
    
    def _generate_silence_audio(self, spec: TestDataSpec, output_path: Path) -> str:
        """生成静音音频文件"""
        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=duration={spec.duration}:sample_rate={spec.sample_rate}:channel_layout=stereo",
            temp_wav.name
        ]
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        return self._convert_audio_format(temp_wav.name, spec, output_path)
    
    def _convert_audio_format(self, input_path: str, spec: TestDataSpec, output_path: Path) -> str:
        """转换音频格式"""
        if spec.format == "wav":
            # WAV 格式直接复制
            cmd = ["cp", input_path, str(output_path)]
        else:
            # 其他格式使用 ffmpeg 转换
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-ar", str(spec.sample_rate),
                "-ac", str(spec.channels)
            ]
            
            # 根据格式添加特定参数
            if spec.format == "mp3":
                cmd.extend(["-codec:a", "libmp3lame", "-b:a", "192k"])
            elif spec.format == "aac":
                cmd.extend(["-codec:a", "aac", "-b:a", "128k"])
            elif spec.format == "flac":
                cmd.extend(["-codec:a", "flac"])
            
            cmd.append(str(output_path))
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        # 清理临时文件
        if os.path.exists(input_path):
            os.unlink(input_path)
        
        return str(output_path)
    
    def _generate_video_file(self, spec: TestDataSpec, output_path: Path) -> str:
        """生成视频文件"""
        # 先生成音频轨道
        audio_spec = TestDataSpec(
            file_type="audio",
            format="wav",
            duration=spec.duration,
            sample_rate=spec.sample_rate,
            channels=spec.channels,
            content_type=spec.content_type,
            language=spec.language,
            speech_text=spec.speech_text
        )
        
        temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        self._generate_audio_file(audio_spec, Path(temp_audio.name))
        
        # 生成视频轨道（彩色条纹或测试图案）
        resolution = spec.video_resolution or "1280x720"
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"testsrc=duration={spec.duration}:size={resolution}:rate={spec.video_fps}",
            "-i", temp_audio.name,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest"
        ]
        
        # 根据格式添加特定参数
        if spec.format == "mp4":
            cmd.extend(["-pix_fmt", "yuv420p"])
        elif spec.format == "avi":
            cmd.extend(["-codec:v", "libxvid"])
        elif spec.format == "mov":
            cmd.extend(["-codec:v", "libx264", "-pix_fmt", "yuv420p"])
        elif spec.format == "mkv":
            cmd.extend(["-codec:v", "libx264"])
        
        cmd.append(str(output_path))
        
        subprocess.run(cmd, capture_output=True, check=True)
        
        # 清理临时文件
        os.unlink(temp_audio.name)
        
        return str(output_path)
    
    def generate_standard_test_set(self) -> Dict[str, str]:
        """生成标准测试数据集"""
        specs = []
        
        # 音频文件测试集
        audio_formats = ["mp3", "wav", "aac", "flac"]
        languages = ["en", "zh-CN", "es", "fr", "de"]
        content_types = ["speech", "music", "mixed", "silence"]
        
        for format in audio_formats:
            for lang in languages[:2]:  # 只测试英语和中文
                for content_type in content_types[:2]:  # 只测试语音和音乐
                    spec = TestDataSpec(
                        file_type="audio",
                        format=format,
                        duration=10.0,  # 10秒测试文件
                        language=lang,
                        content_type=content_type
                    )
                    specs.append(spec)
        
        # 视频文件测试集
        video_formats = ["mp4", "avi", "mov", "mkv"]
        resolutions = ["1280x720", "1920x1080"]
        
        for format in video_formats:
            for resolution in resolutions:
                spec = TestDataSpec(
                    file_type="video",
                    format=format,
                    duration=15.0,  # 15秒测试视频
                    video_resolution=resolution,
                    content_type="speech",
                    language="en"
                )
                specs.append(spec)
        
        # 边缘情况测试文件
        edge_cases = [
            # 极短文件
            TestDataSpec(file_type="audio", format="mp3", duration=1.0, content_type="speech", language="en"),
            # 极长文件
            TestDataSpec(file_type="audio", format="wav", duration=300.0, content_type="speech", language="en"),
            # 低质量音频
            TestDataSpec(file_type="audio", format="mp3", duration=30.0, sample_rate=8000, channels=1, content_type="speech", language="en"),
            # 高质量音频
            TestDataSpec(file_type="audio", format="flac", duration=30.0, sample_rate=96000, channels=2, content_type="music"),
        ]
        
        specs.extend(edge_cases)
        
        return self.generate_test_dataset(specs)
    
    def clean_test_data(self):
        """清理测试数据"""
        if self.output_dir.exists():
            import shutil
            shutil.rmtree(self.output_dir)
            print(f"已清理测试数据目录: {self.output_dir}")


def main():
    """主函数：生成标准测试数据集"""
    generator = TestDataGenerator()
    
    print("🔧 开始生成测试数据集...")
    
    try:
        generated_files = generator.generate_standard_test_set()
        
        print(f"✅ 测试数据集生成完成！")
        print(f"📁 输出目录: {generator.output_dir}")
        print(f"📊 生成文件数量: {len(generated_files)}")
        
        # 显示生成的文件列表
        print("\n📋 生成的文件:")
        for filename, path in list(generated_files.items())[:10]:  # 只显示前10个
            print(f"  - {filename}")
        
        if len(generated_files) > 10:
            print(f"  ... 还有 {len(generated_files) - 10} 个文件")
        
        print(f"\n📄 详细信息已保存到: {generator.output_dir}/dataset_info.json")
        
    except Exception as e:
        print(f"❌ 生成测试数据集失败: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())