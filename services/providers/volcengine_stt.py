import json
import time
import uuid
import base64
import websocket
from typing import Optional
from threading import Thread, Event
from queue import Queue
from services.providers import SpeechToTextProvider, TranscriptionResult
from models.adapters import VolcengineSTTAdapter
from utils.provider_errors import ProviderError, map_volcengine_error
from config import Config


class VolcengineSpeechToText(SpeechToTextProvider):
    """火山云语音识别提供者"""
    
    def __init__(self, app_id: str, access_token: str, cluster: str = "volcengine_streaming_common"):
        if not app_id or not access_token:
            raise ProviderError("火山云ASR配置参数不完整")
        
        self.app_id = app_id
        self.access_token = access_token
        self.cluster = cluster
        self.base_url = "wss://openspeech.bytedance.com/api/v2/asr"
        
        # 支持的音频格式
        self.supported_formats = ['.mp3', '.wav', '.flac', '.aac', '.m4a']
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        
        # WebSocket连接配置
        self.connect_timeout = 10
        self.response_timeout = 30
    
    def transcribe(self, audio_path: str, language: Optional[str] = None, 
                  prompt: Optional[str] = None) -> TranscriptionResult:
        """转录音频文件"""
        return self._transcribe_internal(audio_path, language, prompt, with_timestamps=False)
    
    def transcribe_with_timestamps(self, audio_path: str, language: Optional[str] = None,
                                 prompt: Optional[str] = None) -> TranscriptionResult:
        """转录音频文件并获取时间戳信息"""
        return self._transcribe_internal(audio_path, language, prompt, with_timestamps=True)
    
    def detect_language(self, audio_path: str) -> str:
        """检测音频语言"""
        try:
            result = self.transcribe(audio_path)
            return result.language or 'zh'  # 默认中文
        except Exception:
            return 'zh'  # 检测失败时默认中文
    
    def _transcribe_internal(self, audio_path: str, language: Optional[str], 
                           prompt: Optional[str], with_timestamps: bool) -> TranscriptionResult:
        """内部转录实现"""
        import os
        
        if not os.path.exists(audio_path):
            raise ProviderError(f"音频文件不存在: {audio_path}")
        
        self._validate_audio_file(audio_path)
        
        try:
            # 准备WebSocket连接
            ws_url = self._build_websocket_url()
            
            # 创建WebSocket连接并处理转录
            result_queue = Queue()
            error_queue = Queue()
            
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if data.get("message") == "success":
                        result_queue.put(data)
                    elif "error" in data:
                        error_queue.put(data)
                except Exception as e:
                    error_queue.put({"error": str(e)})
            
            def on_error(ws, error):
                error_queue.put({"error": str(error)})
            
            def on_close(ws, close_status_code, close_msg):
                result_queue.put({"closed": True})
            
            # 建立WebSocket连接
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # 在新线程中运行WebSocket
            ws_thread = Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            # 等待连接建立
            time.sleep(1)
            
            # 发送音频数据
            self._send_audio_data(ws, audio_path, language, with_timestamps)
            
            # 等待结果
            start_time = time.time()
            while time.time() - start_time < self.response_timeout:
                if not result_queue.empty():
                    result = result_queue.get()
                    if "closed" in result:
                        break
                    # 使用适配器转换结果
                    return VolcengineSTTAdapter.adapt_response(result)
                
                if not error_queue.empty():
                    error = error_queue.get()
                    error_msg = error.get("error", "未知错误")
                    raise ProviderError(f"火山云ASR错误: {error_msg}")
                
                time.sleep(0.1)
            
            ws.close()
            raise ProviderError("火山云ASR请求超时")
            
        except Exception as e:
            if isinstance(e, ProviderError):
                raise e
            raise ProviderError(f"火山云ASR调用失败: {str(e)}")
    
    def _build_websocket_url(self) -> str:
        """构建WebSocket URL"""
        return f"{self.base_url}?appid={self.app_id}&token={self.access_token}&cluster={self.cluster}"
    
    def _send_audio_data(self, ws, audio_path: str, language: Optional[str], with_timestamps: bool):
        """发送音频数据到WebSocket"""
        # 发送开始信号
        start_request = {
            "signal": "start",
            "nbest": 1,
            "language": language or "zh",
            "format": "mp3",
            "sample_rate": 16000,
            "show_utterances": with_timestamps
        }
        ws.send(json.dumps(start_request))
        
        # 读取并发送音频文件
        chunk_size = 3200  # 每次发送的字节数
        
        with open(audio_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                # 编码音频数据
                audio_data = base64.b64encode(chunk).decode('utf-8')
                
                audio_request = {
                    "signal": "audio",
                    "data": audio_data
                }
                ws.send(json.dumps(audio_request))
                
                # 控制发送速度
                time.sleep(0.04)  # 25fps
        
        # 发送结束信号
        end_request = {"signal": "end"}
        ws.send(json.dumps(end_request))
    
    def _validate_audio_file(self, audio_path: str):
        """验证音频文件"""
        import os
        
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