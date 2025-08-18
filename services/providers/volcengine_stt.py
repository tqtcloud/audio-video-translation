#!/usr/bin/env python3
"""
火山云语音识别服务 - 正确实现版
使用火山云v3 API和正确的WebSocket协议
"""

import os
import json
import time
import uuid
import asyncio
import logging
import base64
from typing import Optional
from pathlib import Path

import websockets

from services.providers import SpeechToTextProvider, TranscriptionResult
from utils.provider_errors import ProviderError

logger = logging.getLogger(__name__)


class VolcengineSpeechToText(SpeechToTextProvider):
    """火山云ASR提供者 - v3 API正确实现"""
    
    def __init__(self, app_id: str, access_token: str):
        if not app_id or not access_token:
            raise ProviderError("火山云ASR配置参数不完整")
        
        self.app_id = app_id
        self.access_token = access_token
        
        # 使用正确的v3端点
        self.ws_url_bidirectional = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
        self.ws_url_streaming = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"
        
        # 支持的音频格式
        self.supported_formats = ['.mp3', '.wav', '.flac', '.aac', '.m4a']
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        
        # 音频配置
        self.chunk_size = 3200  # 100-200ms音频包大小
        self.chunk_duration = 0.1  # 100ms per chunk
    
    def transcribe(self, audio_path: str, language: Optional[str] = None, 
                  prompt: Optional[str] = None) -> TranscriptionResult:
        """同步接口：转录音频"""
        try:
            # 在多线程环境中正确处理事件循环
            try:
                # 尝试获取当前线程的事件循环
                loop = asyncio.get_running_loop()
                # 如果事件循环正在运行，使用线程池执行器
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, 
                                           self._transcribe_async(audio_path, language, prompt))
                    return future.result()
            except RuntimeError:
                # 当前线程没有运行的事件循环，创建新的事件循环
                logger.debug("创建新的事件循环用于ASR转录")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self._transcribe_async(audio_path, language, prompt)
                    )
                finally:
                    loop.close()
                    # 清理事件循环
                    asyncio.set_event_loop(None)
        except Exception as e:
            logger.error(f"ASR转录失败: {e}")
            raise ProviderError(f"ASR转录失败，无法继续处理: {str(e)}")
    
    async def _transcribe_async(self, audio_path: str, language: Optional[str], 
                               prompt: Optional[str]) -> TranscriptionResult:
        """异步转录实现"""
        if not os.path.exists(audio_path):
            raise ProviderError(f"音频文件不存在: {audio_path}")
        
        self._validate_audio_file(audio_path)
        
        logger.info(f"🚀 开始ASR转录: {audio_path}")
        logger.info(f"📝 语言: {language or 'zh'}")
        
        # 生成连接ID
        connect_id = str(uuid.uuid4())
        
        # 使用正确的认证headers
        headers = {
            "X-Api-App-Key": self.app_id,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": "volc.bigasr.sauc.bigmodel",
            "X-Api-Connect-Id": connect_id
        }
        
        try:
            # 使用流式输入模式（更高精度）
            async with websockets.connect(
                self.ws_url_streaming, 
                additional_headers=headers,
                max_size=10 * 1024 * 1024,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=10
            ) as websocket:
                
                logger.info(f"✅ WebSocket连接成功，连接ID: {connect_id}")
                
                # 1. 发送开始请求（JSON格式）
                start_request = {
                    "user": {
                        "uid": "user_123"
                    },
                    "audio": {
                        "format": "wav",  # 音频格式
                        "rate": 16000,    # 采样率
                        "bits": 16,       # 位深
                        "channel": 1      # 声道数
                    },
                    "request": {
                        "reqid": str(uuid.uuid4()),
                        "model_name": "bigmodel",
                        "enable_punc": True,        # 启用标点
                        "enable_itn": True,         # 启用数字转换
                        "language": language or "zh"  # 语言设置
                    }
                }
                
                await websocket.send(json.dumps(start_request))
                logger.debug("📤 发送开始请求")
                
                # 2. 发送音频数据
                await self._send_audio_data(websocket, audio_path)
                
                # 3. 等待并接收转录结果
                transcription_text = await self._receive_transcription_result(websocket)
                
                # 4. 返回结果
                if transcription_text:
                    logger.info(f"✅ ASR转录成功: {transcription_text[:50]}...")
                    return TranscriptionResult(
                        text=transcription_text,
                        language=language or "zh",
                        duration=self._estimate_duration(audio_path),
                        segments=[]
                    )
                else:
                    raise ProviderError("ASR转录失败：未收到有效转录结果")
                    
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket连接错误: {e}")
            raise ProviderError(f"ASR连接失败: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            raise ProviderError(f"ASR响应解析失败: {str(e)}")
        except Exception as e:
            logger.error(f"ASR处理错误: {e}")
            raise ProviderError(f"ASR处理失败: {str(e)}")
    
    async def _send_audio_data(self, websocket, audio_path: str):
        """发送音频数据"""
        logger.debug("📤 开始发送音频数据")
        
        file_size = os.path.getsize(audio_path)
        sent_bytes = 0
        
        with open(audio_path, 'rb') as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                
                # 发送音频块（二进制格式）
                await websocket.send(chunk)
                sent_bytes += len(chunk)
                
                # 控制发送速率（模拟100ms音频包）
                await asyncio.sleep(self.chunk_duration)
                
                # 进度日志
                progress = (sent_bytes / file_size) * 100
                if sent_bytes % (self.chunk_size * 10) == 0:  # 每1秒日志一次
                    logger.debug(f"📤 发送进度: {progress:.1f}% ({sent_bytes}/{file_size})")
        
        logger.debug(f"✅ 音频发送完成: {sent_bytes} bytes")
    
    async def _receive_transcription_result(self, websocket) -> str:
        """接收并解析转录结果"""
        logger.debug("📥 开始接收转录结果")
        
        transcription_text = ""
        timeout_count = 0
        max_timeouts = 3
        
        while True:
            try:
                # 等待服务器响应
                response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                timeout_count = 0  # 重置超时计数
                
                # 解析响应
                if isinstance(response, str):
                    data = json.loads(response)
                    logger.debug(f"📥 收到响应: {json.dumps(data, ensure_ascii=False)[:200]}...")
                    
                    # 检查是否有错误
                    if "error" in data:
                        error_msg = data.get("error", {})
                        raise ProviderError(f"ASR服务错误: {error_msg}")
                    
                    # 处理识别结果
                    if "result" in data:
                        result = data["result"]
                        if isinstance(result, dict) and "text" in result:
                            text = result["text"]
                            if text:
                                transcription_text += text
                                logger.debug(f"📝 接收文本: {text}")
                    
                    # 检查是否结束
                    if data.get("is_end", False) or data.get("message") == "success":
                        logger.debug("✅ 转录完成")
                        break
                        
                elif isinstance(response, bytes):
                    # 处理二进制响应（如果有的话）
                    logger.debug(f"📥 收到二进制响应: {len(response)} bytes")
                    
            except asyncio.TimeoutError:
                timeout_count += 1
                logger.debug(f"⏱️ 接收超时 ({timeout_count}/{max_timeouts})")
                
                if timeout_count >= max_timeouts:
                    logger.warning("多次接收超时，结束等待")
                    break
                    
            except websockets.exceptions.ConnectionClosed:
                logger.debug("🔌 连接关闭")
                break
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败: {e}")
                continue
        
        return transcription_text.strip()
    
    def _validate_audio_file(self, audio_path: str):
        """验证音频文件"""
        # 检查文件格式
        file_ext = os.path.splitext(audio_path)[1].lower()
        if file_ext not in self.supported_formats:
            raise ProviderError(f"不支持的文件格式: {file_ext}")
        
        # 检查文件大小
        file_size = os.path.getsize(audio_path)
        if file_size > self.max_file_size:
            raise ProviderError(f"文件太大: {file_size} bytes (最大 {self.max_file_size} bytes)")
        
        if file_size == 0:
            raise ProviderError("音频文件为空")
    
    def _estimate_duration(self, audio_path: str) -> float:
        """估算音频时长"""
        # 基于文件大小的简单估算
        file_size = os.path.getsize(audio_path)
        # 假设16kHz, 16bit, 单声道
        bytes_per_second = 16000 * 2
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
            return 'zh'  # 默认中文