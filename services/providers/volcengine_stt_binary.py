#!/usr/bin/env python3
"""
火山云语音识别服务 - 二进制协议实现
基于官方binary protocol示例
"""

import os
import json
import uuid
import asyncio
import logging
from typing import Optional
from pathlib import Path
import struct
import io
from enum import IntEnum
from dataclasses import dataclass

import websockets

from services.providers import SpeechToTextProvider, TranscriptionResult
from utils.provider_errors import ProviderError

logger = logging.getLogger(__name__)


# ============= Binary Protocol Classes =============
class MsgType(IntEnum):
    """Message type enumeration"""
    Invalid = 0
    FullClientRequest = 0b1
    AudioOnlyClient = 0b10
    FullServerResponse = 0b1001
    AudioOnlyServer = 0b1011
    FrontEndResultServer = 0b1100
    Error = 0b1111
    ServerACK = 0b1011  # Alias for AudioOnlyServer

class MsgTypeFlagBits(IntEnum):
    """Message type flag bits"""
    NoSeq = 0
    PositiveSeq = 0b1
    LastNoSeq = 0b10
    NegativeSeq = 0b11
    WithEvent = 0b100

class VersionBits(IntEnum):
    """Version bits"""
    Version1 = 1

class HeaderSizeBits(IntEnum):
    """Header size bits"""
    HeaderSize4 = 1

class SerializationBits(IntEnum):
    """Serialization method bits"""
    JSON = 0b1

class CompressionBits(IntEnum):
    """Compression method bits"""
    None_ = 0

class EventType(IntEnum):
    """Event type enumeration"""
    None_ = 0
    ASRResponse = 451
    ASREnded = 459

@dataclass
class Message:
    """Binary protocol message"""
    version: VersionBits = VersionBits.Version1
    header_size: HeaderSizeBits = HeaderSizeBits.HeaderSize4
    type: MsgType = MsgType.Invalid
    flag: MsgTypeFlagBits = MsgTypeFlagBits.NoSeq
    serialization: SerializationBits = SerializationBits.JSON
    compression: CompressionBits = CompressionBits.None_
    
    event: EventType = EventType.None_
    session_id: str = ""
    connect_id: str = ""
    sequence: int = 0
    error_code: int = 0
    payload: bytes = b""
    
    def marshal(self) -> bytes:
        """Serialize message to bytes"""
        buffer = io.BytesIO()
        
        # Write header
        header = [
            (self.version << 4) | self.header_size,
            (self.type << 4) | self.flag,
            (self.serialization << 4) | self.compression,
        ]
        
        header_size = 4 * self.header_size
        if padding := header_size - len(header):
            header.extend([0] * padding)
        
        buffer.write(bytes(header))
        
        # Write sequence if needed
        if self.flag in [MsgTypeFlagBits.PositiveSeq, MsgTypeFlagBits.NegativeSeq]:
            buffer.write(struct.pack(">i", self.sequence))
        
        # Write payload
        size = len(self.payload)
        buffer.write(struct.pack(">I", size))
        buffer.write(self.payload)
        
        return buffer.getvalue()
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        """Create message from bytes"""
        if len(data) < 3:
            raise ValueError(f"Data too short: {len(data)}")
        
        msg = cls()
        buffer = io.BytesIO(data)
        
        # Read header
        version_and_header = buffer.read(1)[0]
        msg.version = VersionBits(version_and_header >> 4)
        msg.header_size = HeaderSizeBits(version_and_header & 0b00001111)
        
        type_and_flag = buffer.read(1)[0]
        msg.type = MsgType(type_and_flag >> 4)
        msg.flag = MsgTypeFlagBits(type_and_flag & 0b00001111)
        
        ser_comp = buffer.read(1)[0]
        msg.serialization = SerializationBits(ser_comp >> 4)
        msg.compression = CompressionBits(ser_comp & 0b00001111)
        
        # Skip header padding
        header_size = 4 * msg.header_size
        if padding := header_size - 3:
            buffer.read(padding)
        
        # Read sequence if present
        if msg.flag in [MsgTypeFlagBits.PositiveSeq, MsgTypeFlagBits.NegativeSeq]:
            seq_bytes = buffer.read(4)
            if seq_bytes:
                msg.sequence = struct.unpack(">i", seq_bytes)[0]
        
        # Read error code if error message
        if msg.type == MsgType.Error:
            error_bytes = buffer.read(4)
            if error_bytes:
                msg.error_code = struct.unpack(">I", error_bytes)[0]
        
        # Read payload
        size_bytes = buffer.read(4)
        if size_bytes:
            size = struct.unpack(">I", size_bytes)[0]
            if size > 0:
                msg.payload = buffer.read(size)
        
        return msg


# ============= ASR Provider Implementation =============
class VolcengineSpeechToText(SpeechToTextProvider):
    """火山云ASR提供者 - 二进制协议实现"""
    
    def __init__(self, app_id: str, access_token: str):
        if not app_id or not access_token:
            raise ProviderError("火山云ASR配置参数不完整")
        
        self.app_id = app_id
        self.access_token = access_token
        
        # ASR WebSocket endpoint with binary protocol
        self.ws_url = "wss://openspeech.bytedance.com/api/v1/asr/ws_binary"
        
        # 支持的音频格式
        self.supported_formats = ['.mp3', '.wav', '.flac', '.aac', '.m4a']
        self.max_file_size = 100 * 1024 * 1024  # 100MB
    
    def transcribe(self, audio_path: str, language: Optional[str] = None, 
                  prompt: Optional[str] = None) -> TranscriptionResult:
        """同步接口：转录音频"""
        try:
            # Handle event loop in multi-threaded environment
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, 
                                           self._transcribe_async(audio_path, language, prompt))
                    return future.result()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self._transcribe_async(audio_path, language, prompt)
                    )
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)
        except Exception as e:
            logger.error(f"ASR转录失败: {e}")
            raise ProviderError(f"ASR转录失败: {str(e)}")
    
    async def _transcribe_async(self, audio_path: str, language: Optional[str], 
                               prompt: Optional[str]) -> TranscriptionResult:
        """异步转录实现 - 二进制协议"""
        if not os.path.exists(audio_path):
            raise ProviderError(f"音频文件不存在: {audio_path}")
        
        self._validate_audio_file(audio_path)
        
        logger.info(f"🚀 开始ASR转录 (二进制协议): {audio_path}")
        logger.info(f"📝 语言: {language or 'auto'}")
        
        try:
            # Use Authorization header for binary protocol
            headers = {
                "Authorization": f"Bearer;{self.access_token}",
            }
            
            async with websockets.connect(
                self.ws_url,
                additional_headers=headers,
                max_size=10 * 1024 * 1024
            ) as websocket:
                
                # 1. Send FullClientRequest with configuration
                config_payload = {
                    "app": {
                        "appid": self.app_id,
                        "token": self.access_token,
                        "cluster": "volcano_asr"
                    },
                    "user": {
                        "uid": str(uuid.uuid4())
                    },
                    "request": {
                        "reqid": str(uuid.uuid4()),
                        "sequence": 1,
                        "language": language or "zh-CN",
                        "format": "mp3",  # Will be auto-detected
                        "bits": 16,
                        "rate": 16000,
                        "channel": 1,
                        "show_utterances": True,
                        "nbest": 1,
                        "result_type": "single",
                        "enable_itn": True,
                        "enable_punc": True,
                        "enable_ddc": False
                    },
                    "audio": {
                        "format": "mp3",
                        "bits": 16,
                        "channel": 1,
                        "rate": 16000
                    }
                }
                
                # Send configuration
                config_msg = Message(
                    type=MsgType.FullClientRequest,
                    flag=MsgTypeFlagBits.NoSeq,
                    payload=json.dumps(config_payload).encode('utf-8')
                )
                await websocket.send(config_msg.marshal())
                logger.debug("📤 发送配置请求")
                
                # 2. Send audio data in chunks
                chunk_size = 3200
                sequence = 1
                
                with open(audio_path, 'rb') as f:
                    bytes_sent = 0
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        
                        # Send audio chunk with sequence
                        audio_msg = Message(
                            type=MsgType.AudioOnlyClient,
                            flag=MsgTypeFlagBits.PositiveSeq if chunk else MsgTypeFlagBits.NegativeSeq,
                            sequence=sequence if chunk else -sequence,
                            payload=chunk
                        )
                        await websocket.send(audio_msg.marshal())
                        
                        bytes_sent += len(chunk)
                        sequence += 1
                        
                        # Control send rate
                        await asyncio.sleep(0.02)
                    
                    logger.debug(f"📤 音频发送完成: {bytes_sent} 字节")
                
                # 3. Send end signal (empty audio with negative sequence)
                end_msg = Message(
                    type=MsgType.AudioOnlyClient,
                    flag=MsgTypeFlagBits.NegativeSeq,
                    sequence=-sequence,
                    payload=b''
                )
                await websocket.send(end_msg.marshal())
                logger.debug("📤 发送结束信号")
                
                # 4. Receive transcription results
                transcription_text = ""
                full_response = None
                
                while True:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        
                        # Parse binary message
                        if isinstance(response, bytes):
                            msg = Message.from_bytes(response)
                            
                            if msg.type == MsgType.FullServerResponse:
                                # Parse JSON payload
                                if msg.payload:
                                    data = json.loads(msg.payload.decode('utf-8'))
                                    logger.debug(f"📥 收到响应: {data.get('message', '')}")
                                    
                                    # Extract transcription text
                                    result = data.get("result", {})
                                    if isinstance(result, list):
                                        for item in result:
                                            if isinstance(item, dict):
                                                text = item.get("text", "")
                                                if text:
                                                    transcription_text += text + " "
                                    elif isinstance(result, dict):
                                        text = result.get("text", "")
                                        if text:
                                            transcription_text = text
                                    
                                    # Check if finished
                                    if data.get("is_end", False):
                                        logger.debug("✅ 转录完成")
                                        break
                            
                            elif msg.type == MsgType.FrontEndResultServer:
                                # Frontend result (intermediate)
                                if msg.payload:
                                    data = json.loads(msg.payload.decode('utf-8'))
                                    text = data.get("text", "")
                                    if text:
                                        logger.debug(f"📥 中间结果: {text}")
                            
                            elif msg.type == MsgType.Error:
                                # Error message
                                error_msg = msg.payload.decode('utf-8') if msg.payload else "Unknown error"
                                raise ProviderError(f"ASR错误: {error_msg}")
                            
                            elif msg.type == MsgType.AudioOnlyServer:
                                # Server ACK - continue
                                continue
                                
                    except asyncio.TimeoutError:
                        logger.warning("⏱️ 接收超时")
                        break
                    except websockets.exceptions.ConnectionClosed:
                        logger.debug("🔌 连接正常关闭")
                        break
                
                # 5. Process result
                if transcription_text:
                    # Clean up extra spaces
                    transcription_text = ' '.join(transcription_text.split())
                    
                    return TranscriptionResult(
                        text=transcription_text,
                        language=language or "zh",
                        duration=self._estimate_duration(audio_path),
                        segments=[]
                    )
                else:
                    # Real error, no placeholder
                    raise ProviderError("ASR转录失败：未收到有效转录结果")
                    
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket错误: {e}")
            raise ProviderError(f"WebSocket连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"ASR处理错误: {e}")
            raise ProviderError(f"ASR处理失败: {str(e)}")
    
    def _validate_audio_file(self, audio_path: str):
        """验证音频文件"""
        # Check file format
        file_ext = os.path.splitext(audio_path)[1].lower()
        if file_ext not in self.supported_formats:
            raise ProviderError(f"不支持的文件格式: {file_ext}")
        
        # Check file size
        file_size = os.path.getsize(audio_path)
        if file_size > self.max_file_size:
            raise ProviderError(f"文件太大: {file_size} bytes (最大 {self.max_file_size} bytes)")
        
        if file_size == 0:
            raise ProviderError("音频文件为空")
    
    def _estimate_duration(self, audio_path: str) -> float:
        """估算音频时长"""
        # Simple estimation based on file size
        file_size = os.path.getsize(audio_path)
        # Assume 16kHz, 16bit, mono
        bytes_per_second = 16000 * 2  # 32000 bytes/s
        return file_size / bytes_per_second
    
    def transcribe_with_timestamps(self, audio_path: str, language: Optional[str] = None,
                                 prompt: Optional[str] = None) -> TranscriptionResult:
        """转录音频文件并获取时间戳信息"""
        return self.transcribe(audio_path, language, prompt)
    
    def detect_language(self, audio_path: str) -> str:
        """检测音频语言"""
        try:
            result = self.transcribe(audio_path)
            return result.language or 'zh'
        except:
            return 'zh'  # Default Chinese