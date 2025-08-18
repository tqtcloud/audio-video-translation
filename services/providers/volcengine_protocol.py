#!/usr/bin/env python3
"""
火山云WebSocket二进制协议实现
基于官方示例的标准化协议模块
"""

import io
import json
import struct
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Dict, Any, Union

logger = logging.getLogger(__name__)


class MsgType(IntEnum):
    """消息类型枚举"""
    Invalid = 0
    FullClientRequest = 0b1
    AudioOnlyClient = 0b10
    FullServerResponse = 0b1001
    AudioOnlyServer = 0b1011
    FrontEndResultServer = 0b1100
    Error = 0b1111
    ServerACK = 0b1011  # Alias for AudioOnlyServer


class MsgTypeFlagBits(IntEnum):
    """消息标志位"""
    NoSeq = 0
    PositiveSeq = 0b1
    LastNoSeq = 0b10
    NegativeSeq = 0b11
    WithEvent = 0b100


class VersionBits(IntEnum):
    """版本位"""
    Version1 = 1


class HeaderSizeBits(IntEnum):
    """头部大小位"""
    HeaderSize4 = 1


class SerializationBits(IntEnum):
    """序列化方法位"""
    JSON = 0b1


class CompressionBits(IntEnum):
    """压缩方法位"""
    None_ = 0


class EventType(IntEnum):
    """事件类型枚举"""
    None_ = 0
    
    # 连接事件
    StartConnection = 1
    FinishConnection = 2
    ConnectionStarted = 50
    ConnectionFailed = 51
    ConnectionFinished = 52
    
    # 会话事件
    StartSession = 100
    CancelSession = 101
    FinishSession = 102
    SessionStarted = 150
    SessionCanceled = 151
    SessionFinished = 152
    SessionFailed = 153
    
    # TTS事件
    TTSSentenceStart = 350
    TTSSentenceEnd = 351
    TTSResponse = 352
    TTSEnded = 359
    
    # ASR事件
    ASRInfo = 450
    ASRResponse = 451
    ASREnded = 459


@dataclass
class Message:
    """
    火山云WebSocket二进制消息格式
    
    消息结构:
    - 12字节固定头部
    - 可选的扩展头部
    - 变长的载荷数据
    """
    
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
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        """从字节数据创建消息对象"""
        if len(data) < 3:
            raise ValueError(f"数据太短: 至少需要3字节，实际{len(data)}字节")
        
        # 解析消息类型和标志
        type_and_flag = data[1]
        msg_type = MsgType(type_and_flag >> 4)
        flag = MsgTypeFlagBits(type_and_flag & 0b00001111)
        
        msg = cls(type=msg_type, flag=flag)
        msg.unmarshal(data)
        return msg
    
    def marshal(self) -> bytes:
        """序列化消息为字节数据"""
        buffer = io.BytesIO()
        
        # 写入头部
        header = [
            (self.version << 4) | self.header_size,
            (self.type << 4) | self.flag,
            (self.serialization << 4) | self.compression,
        ]
        
        # 补齐头部到指定大小
        header_size = 4 * self.header_size
        if padding := header_size - len(header):
            header.extend([0] * padding)
        
        buffer.write(bytes(header))
        
        # 写入扩展字段
        if self.flag == MsgTypeFlagBits.WithEvent:
            self._write_event(buffer)
            if self.event not in [EventType.StartConnection, EventType.FinishConnection,
                                 EventType.ConnectionStarted, EventType.ConnectionFailed]:
                self._write_session_id(buffer)
        
        # 写入序列号（如果需要）
        if self.flag in [MsgTypeFlagBits.PositiveSeq, MsgTypeFlagBits.NegativeSeq]:
            self._write_sequence(buffer)
        
        # 写入错误码（错误消息）
        if self.type == MsgType.Error:
            self._write_error_code(buffer)
        
        # 写入载荷
        self._write_payload(buffer)
        
        return buffer.getvalue()
    
    def unmarshal(self, data: bytes) -> None:
        """从字节数据反序列化消息"""
        buffer = io.BytesIO(data)
        
        # 读取版本和头部大小
        version_and_header = buffer.read(1)[0]
        self.version = VersionBits(version_and_header >> 4)
        self.header_size = HeaderSizeBits(version_and_header & 0b00001111)
        
        # 跳过第二字节（已在from_bytes中处理）
        buffer.read(1)
        
        # 读取序列化和压缩方法
        ser_comp = buffer.read(1)[0]
        self.serialization = SerializationBits(ser_comp >> 4)
        self.compression = CompressionBits(ser_comp & 0b00001111)
        
        # 跳过头部填充
        header_size = 4 * self.header_size
        if padding_size := header_size - 3:
            buffer.read(padding_size)
        
        # 读取扩展字段
        if self.flag == MsgTypeFlagBits.WithEvent:
            self._read_event(buffer)
            if self.event not in [EventType.StartConnection, EventType.FinishConnection,
                                 EventType.ConnectionStarted, EventType.ConnectionFailed,
                                 EventType.ConnectionFinished]:
                self._read_session_id(buffer)
                if self.event in [EventType.ConnectionStarted, EventType.ConnectionFailed,
                                EventType.ConnectionFinished]:
                    self._read_connect_id(buffer)
        
        # 读取序列号
        if self.flag in [MsgTypeFlagBits.PositiveSeq, MsgTypeFlagBits.NegativeSeq]:
            self._read_sequence(buffer)
        
        # 读取错误码
        if self.type == MsgType.Error:
            self._read_error_code(buffer)
        
        # 读取载荷
        self._read_payload(buffer)
    
    def _write_event(self, buffer: io.BytesIO) -> None:
        """写入事件类型"""
        buffer.write(struct.pack(">i", self.event))
    
    def _write_session_id(self, buffer: io.BytesIO) -> None:
        """写入会话ID"""
        session_bytes = self.session_id.encode("utf-8")
        buffer.write(struct.pack(">I", len(session_bytes)))
        if session_bytes:
            buffer.write(session_bytes)
    
    def _write_sequence(self, buffer: io.BytesIO) -> None:
        """写入序列号"""
        buffer.write(struct.pack(">i", self.sequence))
    
    def _write_error_code(self, buffer: io.BytesIO) -> None:
        """写入错误码"""
        buffer.write(struct.pack(">I", self.error_code))
    
    def _write_payload(self, buffer: io.BytesIO) -> None:
        """写入载荷"""
        buffer.write(struct.pack(">I", len(self.payload)))
        buffer.write(self.payload)
    
    def _read_event(self, buffer: io.BytesIO) -> None:
        """读取事件类型"""
        event_bytes = buffer.read(4)
        if event_bytes:
            self.event = EventType(struct.unpack(">i", event_bytes)[0])
    
    def _read_session_id(self, buffer: io.BytesIO) -> None:
        """读取会话ID"""
        size_bytes = buffer.read(4)
        if size_bytes:
            size = struct.unpack(">I", size_bytes)[0]
            if size > 0:
                self.session_id = buffer.read(size).decode("utf-8")
    
    def _read_connect_id(self, buffer: io.BytesIO) -> None:
        """读取连接ID"""
        size_bytes = buffer.read(4)
        if size_bytes:
            size = struct.unpack(">I", size_bytes)[0]
            if size > 0:
                self.connect_id = buffer.read(size).decode("utf-8")
    
    def _read_sequence(self, buffer: io.BytesIO) -> None:
        """读取序列号"""
        seq_bytes = buffer.read(4)
        if seq_bytes:
            self.sequence = struct.unpack(">i", seq_bytes)[0]
    
    def _read_error_code(self, buffer: io.BytesIO) -> None:
        """读取错误码"""
        error_bytes = buffer.read(4)
        if error_bytes:
            self.error_code = struct.unpack(">I", error_bytes)[0]
    
    def _read_payload(self, buffer: io.BytesIO) -> None:
        """读取载荷"""
        size_bytes = buffer.read(4)
        if size_bytes:
            size = struct.unpack(">I", size_bytes)[0]
            if size > 0:
                self.payload = buffer.read(size)
    
    def get_payload_json(self) -> Optional[Dict[str, Any]]:
        """获取JSON格式的载荷"""
        if self.payload and self.serialization == SerializationBits.JSON:
            try:
                return json.loads(self.payload.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return None
        return None
    
    def set_payload_json(self, data: Dict[str, Any]) -> None:
        """设置JSON格式的载荷"""
        self.payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.serialization = SerializationBits.JSON
    
    def __str__(self) -> str:
        """字符串表示"""
        if self.type in [MsgType.AudioOnlyServer, MsgType.AudioOnlyClient]:
            return f"Message(type={self.type.name}, event={self.event.name}, payload_size={len(self.payload)})"
        elif self.type == MsgType.Error:
            payload_str = self.payload.decode("utf-8", "ignore") if self.payload else ""
            return f"Message(type=Error, code={self.error_code}, payload={payload_str})"
        else:
            payload_str = ""
            if self.payload:
                json_data = self.get_payload_json()
                if json_data:
                    payload_str = json.dumps(json_data, ensure_ascii=False)[:100]
                else:
                    payload_str = f"<binary:{len(self.payload)}bytes>"
            return f"Message(type={self.type.name}, event={self.event.name}, payload={payload_str})"


# 辅助函数
def create_start_connection_message() -> Message:
    """创建开始连接消息"""
    msg = Message(
        type=MsgType.FullClientRequest,
        flag=MsgTypeFlagBits.WithEvent,
        event=EventType.StartConnection
    )
    msg.payload = b"{}"
    return msg


def create_finish_connection_message() -> Message:
    """创建结束连接消息"""
    msg = Message(
        type=MsgType.FullClientRequest,
        flag=MsgTypeFlagBits.WithEvent,
        event=EventType.FinishConnection
    )
    msg.payload = b"{}"
    return msg


def create_start_session_message(session_id: str, payload: Dict[str, Any]) -> Message:
    """创建开始会话消息"""
    msg = Message(
        type=MsgType.FullClientRequest,
        flag=MsgTypeFlagBits.WithEvent,
        event=EventType.StartSession,
        session_id=session_id
    )
    msg.set_payload_json(payload)
    return msg


def create_finish_session_message(session_id: str) -> Message:
    """创建结束会话消息"""
    msg = Message(
        type=MsgType.FullClientRequest,
        flag=MsgTypeFlagBits.WithEvent,
        event=EventType.FinishSession,
        session_id=session_id
    )
    msg.payload = b"{}"
    return msg


def create_audio_message(audio_data: bytes, is_last: bool = False) -> Message:
    """创建音频数据消息"""
    msg = Message(
        type=MsgType.AudioOnlyClient,
        flag=MsgTypeFlagBits.LastNoSeq if is_last else MsgTypeFlagBits.NoSeq,
        payload=audio_data
    )
    return msg