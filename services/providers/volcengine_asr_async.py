#!/usr/bin/env python3
"""
火山云异步ASR服务 - 基于官方文档实现
使用submit/query模式，支持音频URL提交
"""

import os
import json
import uuid
import time
import asyncio
import logging
import requests
from typing import Optional
from pathlib import Path

from services.providers import SpeechToTextProvider, TranscriptionResult
from utils.provider_errors import ProviderError

logger = logging.getLogger(__name__)


class VolcengineAsyncASR(SpeechToTextProvider):
    """火山云异步ASR提供者 - 基于官方submit/query API"""
    
    def __init__(self, app_id: str, access_token: str):
        if not app_id or not access_token:
            raise ProviderError("火山云ASR配置参数不完整")
        
        self.app_id = app_id
        self.access_token = access_token
        
        # 官方API端点
        self.submit_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
        self.query_url = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
        
        # 支持的音频格式
        self.supported_formats = ['.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg']
        self.max_file_size = 500 * 1024 * 1024  # 500MB
    
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
        """异步转录实现 - 使用submit/query模式"""
        # 对于HTTP URL，跳过本地文件检查
        if not audio_path.startswith('http'):
            if not os.path.exists(audio_path):
                raise ProviderError(f"音频文件不存在: {audio_path}")
            self._validate_audio_file(audio_path)
        
        logger.info(f"🚀 开始异步ASR转录: {audio_path}")
        logger.info(f"📝 语言: {language or 'auto'}")
        
        # 检查是否为HTTP URL
        if audio_path.startswith('http'):
            audio_url = audio_path
        else:
            # 本地文件，需要提醒用户先上传
            raise ProviderError("火山云ASR需要音频文件的HTTP URL，请先将文件上传到可访问的服务器")
        
        try:
            # 1. 提交任务
            task_id = await self._submit_task(audio_url, language)
            logger.info(f"✅ 任务提交成功, Task ID: {task_id}")
            
            # 2. 轮询查询结果
            result = await self._query_result(task_id)
            
            return result
            
        except Exception as e:
            logger.error(f"异步ASR处理错误: {e}")
            raise ProviderError(f"异步ASR处理失败: {str(e)}")
    
    async def _submit_task(self, audio_url: str, language: Optional[str]) -> str:
        """提交ASR任务"""
        task_id = str(uuid.uuid4())
        
        # 构建请求头
        headers = {
            "X-Api-App-Key": self.app_id,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": "volc.bigasr.auc",
            "X-Api-Request-Id": task_id,
            "X-Api-Sequence": "-1",
            "Content-Type": "application/json"
        }
        
        # 构建请求体
        payload = {
            "user": {
                "uid": "volcengine_asr_client"
            },
            "audio": {
                "url": audio_url,
                "format": self._detect_audio_format(audio_url),
                "rate": 16000,
                "bits": 16,
                "channel": 1
            },
            "request": {
                "model_name": "bigmodel",
                "model_version": "400",  # 使用400模型获得更好效果
                "enable_itn": True,
                "enable_punc": True,
                "enable_ddc": True,  # 启用语义顺滑
                "enable_speaker_info": False,
                "enable_channel_split": False,
                "show_utterances": True  # 获取分句信息
            }
        }
        
        logger.debug(f"📤 提交任务请求: {json.dumps(payload, ensure_ascii=False)}")
        
        # 发送请求
        response = requests.post(self.submit_url, headers=headers, json=payload, timeout=30)
        
        # 检查响应头
        status_code = response.headers.get("X-Api-Status-Code")
        message = response.headers.get("X-Api-Message", "")
        logid = response.headers.get("X-Tt-Logid", "")
        
        logger.debug(f"📥 提交响应 - Status: {status_code}, Message: {message}, LogID: {logid}")
        
        if status_code == "20000000":
            return task_id
        else:
            raise ProviderError(f"任务提交失败 - Status: {status_code}, Message: {message}, LogID: {logid}")
    
    async def _query_result(self, task_id: str, max_attempts: int = 60) -> TranscriptionResult:
        """查询ASR结果，最多重试60次（约5分钟）"""
        headers = {
            "X-Api-App-Key": self.app_id,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": "volc.bigasr.auc",
            "X-Api-Request-Id": task_id,
            "Content-Type": "application/json"
        }
        
        for attempt in range(max_attempts):
            try:
                response = requests.post(self.query_url, headers=headers, json={}, timeout=30)
                
                status_code = response.headers.get("X-Api-Status-Code")
                message = response.headers.get("X-Api-Message", "")
                logid = response.headers.get("X-Tt-Logid", "")
                
                logger.debug(f"📥 查询响应 #{attempt+1} - Status: {status_code}, Message: {message}")
                
                if status_code == "20000000":
                    # 任务完成，解析结果
                    result_data = response.json()
                    return self._parse_result(result_data)
                    
                elif status_code == "20000001":
                    # 正在处理中
                    logger.debug(f"⏳ 任务处理中，等待5秒后重试...")
                    await asyncio.sleep(5)
                    continue
                    
                elif status_code == "20000002":
                    # 任务在队列中
                    logger.debug(f"📋 任务在队列中，等待5秒后重试...")
                    await asyncio.sleep(5)
                    continue
                    
                elif status_code == "20000003":
                    # 静音音频
                    raise ProviderError(f"音频文件为静音，无法识别内容")
                    
                else:
                    # 其他错误
                    raise ProviderError(f"任务查询失败 - Status: {status_code}, Message: {message}, LogID: {logid}")
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ 查询请求失败: {e}, 重试中...")
                await asyncio.sleep(2)
                continue
        
        raise ProviderError(f"任务超时，在{max_attempts * 5}秒内未完成处理")
    
    def _parse_result(self, result_data: dict) -> TranscriptionResult:
        """解析ASR返回结果"""
        try:
            # 提取主要文本
            result = result_data.get("result", {})
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            text = result.get("text", "").strip()
            if not text:
                raise ProviderError("ASR返回结果为空")
            
            # 提取时长信息
            audio_info = result_data.get("audio_info", {})
            duration = audio_info.get("duration", 0) / 1000.0  # 转换为秒
            
            # 提取分句信息
            segments = []
            utterances = result.get("utterances", [])
            for utterance in utterances:
                if isinstance(utterance, dict):
                    segment_text = utterance.get("text", "").strip()
                    start_time = utterance.get("start_time", 0) / 1000.0
                    end_time = utterance.get("end_time", 0) / 1000.0
                    
                    if segment_text:
                        segments.append({
                            "start": start_time,
                            "end": end_time,
                            "text": segment_text
                        })
            
            logger.info(f"✅ ASR解析成功: {text[:100]}...")
            logger.info(f"📊 时长: {duration:.2f}秒, 分句: {len(segments)}个")
            
            return TranscriptionResult(
                text=text,
                language="zh",  # 火山云主要支持中文
                duration=duration,
                segments=segments
            )
            
        except Exception as e:
            logger.error(f"❌ 结果解析失败: {e}")
            logger.debug(f"原始返回数据: {json.dumps(result_data, ensure_ascii=False)}")
            raise ProviderError(f"结果解析失败: {str(e)}")
    
    def _detect_audio_format(self, audio_path: str) -> str:
        """检测音频格式"""
        if audio_path.lower().endswith('.mp3'):
            return 'mp3'
        elif audio_path.lower().endswith('.wav'):
            return 'wav'
        elif audio_path.lower().endswith('.flac'):
            return 'flac'
        elif audio_path.lower().endswith('.ogg'):
            return 'ogg'
        else:
            return 'mp3'  # 默认格式
    
    def _validate_audio_file(self, audio_path: str):
        """验证音频文件"""
        if audio_path.startswith('http'):
            return  # URL格式，跳过本地文件检查
        
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