#!/usr/bin/env python3
"""
火山云文本转语音服务 - 修复版
使用二进制WebSocket协议实现，完全兼容官方示例
"""

import os
import json
import time
import uuid
import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

import websockets

from services.providers import TextToSpeechProvider
from protocols.volcengine_protocol import (
    Message, MsgType, EventType, MsgTypeFlagBits,
    start_connection,
    finish_connection,
    start_session,
    finish_session
)
from utils.provider_errors import ProviderError

logger = logging.getLogger(__name__)


class VolcengineTextToSpeech(TextToSpeechProvider):
    """火山云TTS提供者 - 二进制WebSocket协议实现"""
    
    def __init__(self, app_id: str, access_token: str):
        if not app_id or not access_token:
            raise ProviderError("火山云TTS配置参数不完整")
        
        self.app_id = app_id
        self.access_token = access_token
        
        # WebSocket端点（二进制协议）
        self.ws_url = "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"
        
        # 支持的语音类型（经过验证的）
        self.voice_types = {
            "zh": "zh_female_cancan_mars_bigtts",
            "en": "en_female_amanda_mars",
            "ja": "ja_female_nanami_mars",
            "ko": "ko_female_yeonhee_mars"
        }
        
        # 默认配置
        self.sample_rate = 24000
        self.encoding = "wav"
        self.compression = "raw"
        self.speed_ratio = 1.0
        self.volume_ratio = 1.0
        self.pitch_ratio = 1.0
    
    def synthesize(self, text: str, language: str = "zh", 
                  output_path: Optional[str] = None, voice: Optional[str] = None) -> str:
        """同步接口：合成语音"""
        try:
            # 在多线程环境中正确处理事件循环
            try:
                # 尝试获取当前线程的事件循环
                loop = asyncio.get_running_loop()
                # 如果事件循环正在运行，使用线程池执行器
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, 
                                           self._synthesize_async(text, language, output_path, voice))
                    return future.result()
            except RuntimeError:
                # 当前线程没有运行的事件循环，创建新的事件循环
                logger.debug("创建新的事件循环用于TTS合成")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self._synthesize_async(text, language, output_path, voice)
                    )
                finally:
                    loop.close()
                    # 清理事件循环
                    asyncio.set_event_loop(None)
        except Exception as e:
            logger.error(f"TTS合成失败: {e}")
            raise ProviderError(f"TTS合成失败: {str(e)}")
    
    async def _synthesize_async(self, text: str, language: str, 
                               output_path: Optional[str], voice: Optional[str]) -> str:
        """异步合成实现"""
        if not text:
            raise ProviderError("输入文本不能为空")
        
        # 确定输出路径
        if not output_path:
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            output_path = str(output_dir / f"tts_{int(time.time())}.wav")
        
        # 选择语音类型
        if not voice:
            voice = self.voice_types.get(language, self.voice_types["zh"])
        
        logger.info(f"🚀 开始TTS合成: {text[:50]}...")
        logger.info(f"📝 语言: {language}, 语音: {voice}")
        
        try:
            # 建立WebSocket连接
            headers = {
                "Authorization": f"Bearer;{self.access_token}"
            }
            
            async with websockets.connect(self.ws_url, additional_headers=headers, max_size=10 * 1024 * 1024) as websocket:
                # 1. 发送开始连接消息
                start_msg_data = start_connection()
                await websocket.send(start_msg_data)
                logger.debug("📤 发送开始连接消息")
                
                # 等待连接确认
                response = await websocket.recv()
                msg = Message.from_bytes(response)
                if msg.event != EventType.ConnectionStarted:
                    raise ProviderError(f"连接失败: {msg}")
                logger.debug("✅ 连接建立成功")
                
                # 2. 发送开始会话消息
                session_id = str(uuid.uuid4())
                session_payload = {
                    "app": {
                        "appid": self.app_id,
                        "token": "access_token",
                        "cluster": "volcano_tts"
                    },
                    "user": {
                        "uid": "audio_translation_user"
                    },
                    "audio": {
                        "voice_type": voice,
                        "encoding": self.encoding,
                        "compression": self.compression,
                        "rate": self.sample_rate,
                        "speed_ratio": self.speed_ratio,
                        "volume_ratio": self.volume_ratio,
                        "pitch_ratio": self.pitch_ratio
                    },
                    "request": {
                        "text": text,
                        "text_type": "plain",
                        "operation": "submit"
                    }
                }
                
                session_msg_data = start_session(json.dumps(session_payload).encode(), session_id)
                await websocket.send(session_msg_data)
                logger.debug(f"📤 发送会话请求: {text[:30]}...")
                
                # 3. 接收音频数据
                audio_chunks = []
                while True:
                    response = await websocket.recv()
                    msg = Message.from_bytes(response)
                    
                    if msg.type == MsgType.AudioOnlyServer:
                        # 音频数据
                        if msg.payload:
                            audio_chunks.append(msg.payload)
                            logger.debug(f"📥 接收音频块: {len(msg.payload)} 字节")
                    
                    elif msg.event == EventType.SessionFinished:
                        # 会话结束
                        logger.debug("✅ 会话完成")
                        break
                    
                    elif msg.type == MsgType.Error:
                        # 错误消息
                        try:
                            error_info = json.loads(msg.payload.decode('utf-8'))
                        except:
                            error_info = msg.payload.decode('utf-8', 'ignore')
                        raise ProviderError(f"TTS错误: {error_info}")
                
                # 4. 发送结束会话消息
                finish_msg_data = finish_session(session_id)
                await websocket.send(finish_msg_data)
                
                # 5. 发送结束连接消息
                finish_conn_msg_data = finish_connection()
                await websocket.send(finish_conn_msg_data)
                
                # 6. 保存音频文件
                if audio_chunks:
                    audio_data = b''.join(audio_chunks)
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)
                    
                    logger.info(f"✅ TTS合成成功: {output_path}")
                    logger.info(f"📊 音频大小: {len(audio_data)} 字节")
                    return output_path
                else:
                    raise ProviderError("未接收到音频数据")
                    
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket错误: {e}")
            raise ProviderError(f"WebSocket连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"TTS处理错误: {e}")
            raise ProviderError(f"TTS处理失败: {str(e)}")
    
    def synthesize_with_timestamps(self, text: str, language: str = "zh",
                                  output_path: Optional[str] = None) -> tuple:
        """合成语音并返回时间戳信息"""
        audio_path = self.synthesize(text, language, output_path)
        # 简化实现，返回占位时间戳
        return audio_path, []
    
    def get_supported_voices(self, language: str) -> list:
        """获取支持的语音列表"""
        if language in self.voice_types:
            return [self.voice_types[language]]
        return list(self.voice_types.values())
    
    def estimate_duration(self, text: str, language: str = "zh") -> float:
        """估算语音时长"""
        # 简单估算：中文每秒3个字，英文每秒2.5个词
        if language == "zh":
            return len(text) / 3.0
        else:
            words = text.split()
            return len(words) / 2.5
    
    def set_voice_parameters(self, speed: float = 1.0, pitch: float = 1.0, 
                            volume: float = 1.0):
        """设置语音参数"""
        self.speed_ratio = max(0.5, min(2.0, speed))
        self.pitch_ratio = max(0.5, min(2.0, pitch))
        self.volume_ratio = max(0.5, min(2.0, volume))
    
    def synthesize_speech(self, segments, language: str,
                         voice_config: Optional[Dict] = None,
                         match_original_timing: bool = True):
        """实现抽象方法：合成语音"""
        from services.providers import SpeechSynthesisResult
        from models.core import TimedSegment
        import time
        
        # 合并所有片段文本
        full_text = " ".join([seg.text for seg in segments])
        
        # 合成语音
        output_path = self.synthesize(full_text, language)
        
        # 返回结果
        return SpeechSynthesisResult(
            audio_file_path=output_path,
            total_duration=self.estimate_duration(full_text, language),
            segments_count=len(segments),
            processing_time=0.0,
            quality_score=1.0
        )
    
    def synthesize_text(self, text: str, language: str,
                       voice_config: Optional[Dict] = None) -> str:
        """实现抽象方法：合成单个文本的语音"""
        return self.synthesize(text, language)