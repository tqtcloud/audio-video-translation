"""
火山云TOS对象存储服务
基于官方Python SDK实现文件上传功能
"""
import os
import uuid
import tempfile
from typing import Optional, BinaryIO
from pathlib import Path

try:
    import tos
    from tos.exceptions import TosClientError, TosServerError
except ImportError:
    raise ImportError("请安装火山云TOS SDK: pip install tos")


class VolcengineTOS:
    """火山云TOS对象存储服务"""
    
    def __init__(self, access_key: str, secret_key: str, endpoint: str, region: str, bucket_name: str):
        """
        初始化TOS客户端
        
        Args:
            access_key: 访问密钥ID
            secret_key: 访问密钥Secret
            endpoint: TOS服务端点，如 tos-cn-beijing.volces.com
            region: 区域，如 cn-beijing
            bucket_name: 存储桶名称
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint = endpoint
        self.region = region
        self.bucket_name = bucket_name
        
        # 创建TOS客户端
        self.client = tos.TosClientV2(
            ak=access_key,
            sk=secret_key,
            region=region,
            endpoint=endpoint
        )
    
    def upload_file(self, file_path: str, object_key: Optional[str] = None) -> str:
        """
        上传本地文件到TOS
        
        Args:
            file_path: 本地文件路径
            object_key: 对象存储中的键名，如果不指定则自动生成
            
        Returns:
            str: 上传后的文件URL
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        if object_key is None:
            # 生成唯一的对象键名
            file_ext = Path(file_path).suffix
            object_key = f"audio/{uuid.uuid4().hex}{file_ext}"
        
        try:
            # 上传文件
            result = self.client.put_object_from_file(
                bucket=self.bucket_name,
                key=object_key,
                file_path=file_path
            )
            
            print(f"✅ 文件上传成功: {object_key}")
            print(f"📊 请求ID: {result.request_id}")
            
            # 构建文件访问URL
            file_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"
            return file_url
            
        except TosClientError as e:
            error_msg = f"TOS客户端错误: {e.message}, 原因: {e.cause}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except TosServerError as e:
            error_msg = f"TOS服务器错误: {e.code} - {e.message}"
            print(f"❌ {error_msg}")
            print(f"🔍 请求ID: {e.request_id}")
            print(f"📡 请求URL: {e.request_url}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"未知错误: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def upload_bytes(self, file_bytes: bytes, object_key: Optional[str] = None, 
                     file_extension: str = ".mp3") -> str:
        """
        上传字节数据到TOS
        
        Args:
            file_bytes: 文件字节数据
            object_key: 对象存储中的键名，如果不指定则自动生成
            file_extension: 文件扩展名
            
        Returns:
            str: 上传后的文件URL
        """
        if object_key is None:
            # 生成唯一的对象键名
            object_key = f"audio/{uuid.uuid4().hex}{file_extension}"
        
        try:
            # 上传字节数据
            result = self.client.put_object(
                bucket=self.bucket_name,
                key=object_key,
                content=file_bytes
            )
            
            print(f"✅ 字节数据上传成功: {object_key}")
            print(f"📊 请求ID: {result.request_id}")
            
            # 构建文件访问URL
            file_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"
            return file_url
            
        except TosClientError as e:
            error_msg = f"TOS客户端错误: {e.message}, 原因: {e.cause}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except TosServerError as e:
            error_msg = f"TOS服务器错误: {e.code} - {e.message}"
            print(f"❌ {error_msg}")
            print(f"🔍 请求ID: {e.request_id}")
            print(f"📡 请求URL: {e.request_url}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"未知错误: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def upload_stream(self, file_stream: BinaryIO, object_key: Optional[str] = None,
                      file_extension: str = ".mp3") -> str:
        """
        上传文件流到TOS
        
        Args:
            file_stream: 文件流对象
            object_key: 对象存储中的键名，如果不指定则自动生成
            file_extension: 文件扩展名
            
        Returns:
            str: 上传后的文件URL
        """
        if object_key is None:
            # 生成唯一的对象键名
            object_key = f"audio/{uuid.uuid4().hex}{file_extension}"
        
        try:
            # 上传文件流
            result = self.client.put_object(
                bucket=self.bucket_name,
                key=object_key,
                content=file_stream
            )
            
            print(f"✅ 文件流上传成功: {object_key}")
            print(f"📊 请求ID: {result.request_id}")
            
            # 构建文件访问URL
            file_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"
            return file_url
            
        except TosClientError as e:
            error_msg = f"TOS客户端错误: {e.message}, 原因: {e.cause}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except TosServerError as e:
            error_msg = f"TOS服务器错误: {e.code} - {e.message}"
            print(f"❌ {error_msg}")
            print(f"🔍 请求ID: {e.request_id}")
            print(f"📡 请求URL: {e.request_url}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"未知错误: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def delete_object(self, object_key: str) -> bool:
        """
        删除TOS中的对象
        
        Args:
            object_key: 要删除的对象键名
            
        Returns:
            bool: 是否删除成功
        """
        try:
            self.client.delete_object(self.bucket_name, object_key)
            print(f"✅ 对象删除成功: {object_key}")
            return True
        except Exception as e:
            print(f"❌ 删除对象失败: {e}")
            return False
    
    def close(self):
        """关闭TOS客户端"""
        try:
            if self.client:
                self.client.close()
                print("🔐 TOS客户端已关闭")
        except Exception as e:
            print(f"⚠️ 关闭TOS客户端时出错: {e}")
    
    @classmethod
    def from_env(cls) -> "VolcengineTOS":
        """
        从环境变量创建TOS客户端实例
        
        需要以下环境变量:
        - VOLCENGINE_ACCESS_KEY: 访问密钥ID
        - VOLCENGINE_SECRET_KEY: 访问密钥Secret  
        - TOS_ENDPOINT: TOS服务端点
        - TOS_REGION: TOS区域
        - TOS_BUCKET: 存储桶名称
        """
        access_key = os.getenv('VOLCENGINE_ACCESS_KEY')
        secret_key = os.getenv('VOLCENGINE_SECRET_KEY')
        endpoint = os.getenv('TOS_ENDPOINT')
        region = os.getenv('TOS_REGION')
        bucket = os.getenv('TOS_BUCKET')
        
        if not all([access_key, secret_key, endpoint, region, bucket]):
            raise ValueError(
                "缺少必要的环境变量: "
                "VOLCENGINE_ACCESS_KEY, VOLCENGINE_SECRET_KEY, "
                "TOS_ENDPOINT, TOS_REGION, TOS_BUCKET"
            )
        
        return cls(
            access_key=access_key,
            secret_key=secret_key,
            endpoint=endpoint,
            region=region,
            bucket_name=bucket
        )


def create_temp_file_and_upload(file_bytes: bytes, file_extension: str = ".mp3") -> str:
    """
    创建临时文件并上传到TOS
    
    Args:
        file_bytes: 文件字节数据
        file_extension: 文件扩展名
        
    Returns:
        str: 上传后的文件URL
    """
    tos_client = VolcengineTOS.from_env()
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
        temp_file.write(file_bytes)
        temp_file_path = temp_file.name
    
    try:
        # 上传临时文件
        file_url = tos_client.upload_file(temp_file_path)
        return file_url
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_file_path)
        except Exception as e:
            print(f"⚠️ 清理临时文件失败: {e}")
        
        # 关闭TOS客户端
        tos_client.close()