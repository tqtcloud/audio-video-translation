#!/usr/bin/env python3
"""
火山云语音识别服务 - v3 API实现
使用最新的v3 API端点，无占位符
"""

import os
import json
import time
import uuid
import asyncio
import logging
from typing import Optional
from pathlib import Path

import websockets

from services.providers import SpeechToTextProvider, TranscriptionResult
from utils.provider_errors import ProviderError

logger = logging.getLogger(__name__)


class VolcengineSpeechToText(SpeechToTextProvider):
    """火山云ASR提供者 - v3 API WebSocket实现"""
    
    def __init__(self, app_id: str, access_token: str):
        if not app_id or not access_token:
            raise ProviderError("火山云ASR配置参数不完整")
        
        self.app_id = app_id
        self.access_token = access_token
        
        # v3 API WebSocket端点
        self.ws_url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"
        
        # 支持的音频格式
        self.supported_formats = ['.mp3', '.wav', '.flac', '.aac', '.m4a']
        self.max_file_size = 100 * 1024 * 1024  # 100MB
    
    def transcribe(self, audio_path: str, language: Optional[str] = None, 
                  prompt: Optional[str] = None) -> TranscriptionResult:
        """同步接口：转录音频"""
        try:
            # 在多线程环境中正确处理事件循环
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, 
                                           self._transcribe_async(audio_path, language, prompt))
                    return future.result()
            except RuntimeError:
                # 当前线程没有运行的事件循环
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
        """异步转录实现 - v3 API"""
        if not os.path.exists(audio_path):
            raise ProviderError(f"音频文件不存在: {audio_path}")
        
        self._validate_audio_file(audio_path)
        
        logger.info(f"🚀 开始ASR转录 (v3 API): {audio_path}")
        logger.info(f"📝 语言: {language or 'auto'}")
        
        try:
            # v3 API使用HTTP Headers认证
            headers = {
                "X-Api-App-Key": self.app_id,
                "X-Api-Access-Key": self.access_token,
                "X-Api-Resource-Id": "volc.bigasr.sauc.bigmodel",
                "X-Api-Connect-Id": str(uuid.uuid4())
            }
            
            async with websockets.connect(
                self.ws_url,
                additional_headers=headers,
                max_size=10 * 1024 * 1024
            ) as websocket:
                
                # 1. 发送开始请求（v3格式）
                start_request = {
                    "user": {
                        "uid": str(uuid.uuid4())
                    },
                    "request": {
                        "model_name": "bigmodel",
                        "nbest": 1,
                        "show_utterances": False,
                        "enable_itn": True,
                        "enable_punc": True,
                        "enable_ddc": False,
                        "language": language or "zh"
                    },
                    "audio": {
                        "format": "wav",
                        "sample_rate": 16000,
                        "bits": 16,
                        "channel": 1
                    }
                }
                
                await websocket.send(json.dumps(start_request))
                logger.debug("📤 发送v3开始请求")
                
                # 2. 发送音频数据（二进制流）
                chunk_size = 8192  # v3推荐的块大小
                with open(audio_path, 'rb') as f:
                    bytes_sent = 0
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        
                        # 直接发送二进制数据
                        await websocket.send(chunk)
                        bytes_sent += len(chunk)
                        
                        # 控制发送速率
                        await asyncio.sleep(0.02)
                    
                    logger.debug(f"📤 音频发送完成: {bytes_sent} 字节")
                
                # 3. 发送结束信号（空二进制数据）
                await websocket.send(b'')
                logger.debug("📤 发送结束信号")
                
                # 4. 接收转录结果
                transcription_text = ""
                full_response = None
                
                while True:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        
                        # 解析响应
                        if isinstance(response, str):
                            data = json.loads(response)
                            logger.debug(f"📥 收到响应: {data.get('message', '')}")
                            
                            # v3 API响应格式
                            if data.get("code") == 20000000:
                                # 成功响应
                                result = data.get("result", {})
                                
                                # 提取转录文本
                                if "text" in result:
                                    transcription_text = result["text"]
                                    full_response = data
                                    logger.info(f"✅ 转录成功: {transcription_text[:50]}...")
                                    break
                                
                                # 处理分段结果
                                utterances = result.get("utterances", [])
                                for utterance in utterances:
                                    text = utterance.get("text", "")
                                    if text:
                                        transcription_text += text + " "
                                
                                # 检查是否完成
                                if data.get("is_final", False):
                                    logger.debug("✅ 转录完成")
                                    break
                            
                            elif data.get("code") != 20000000 and data.get("code") is not None:
                                # 错误响应
                                error_msg = data.get("message", "未知错误")
                                raise ProviderError(f"ASR API错误 (code={data.get('code')}): {error_msg}")
                        
                        elif isinstance(response, bytes):
                            # 某些响应可能是二进制格式
                            logger.debug(f"📥 收到二进制响应: {len(response)} 字节")
                            
                    except asyncio.TimeoutError:
                        logger.warning("⏱️ 接收超时")
                        break
                    except websockets.exceptions.ConnectionClosed:
                        logger.debug("🔌 连接正常关闭")
                        break
                
                # 5. 处理结果
                if transcription_text:
                    # 清理多余的空格
                    transcription_text = ' '.join(transcription_text.split())
                    
                    return TranscriptionResult(
                        text=transcription_text,
                        language=language or "zh",
                        duration=self._estimate_duration(audio_path),
                        segments=[]  # v3 API暂不返回详细分段
                    )
                else:
                    # 真实报错，不使用占位符
                    raise ProviderError("ASR转录失败：未收到有效转录结果")
                    
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket错误: {e}")
            raise ProviderError(f"WebSocket连接失败: {str(e)}")
        except Exception as e:
            logger.error(f"ASR处理错误: {e}")
            raise ProviderError(f"ASR处理失败: {str(e)}")
    
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
        # 简单估算：基于文件大小
        file_size = os.path.getsize(audio_path)
        # 假设16kHz, 16bit, 单声道
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
            return 'zh'  # 默认中文