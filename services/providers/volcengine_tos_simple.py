"""
简化的火山云TOS对象存储服务
基于官方Python SDK标准实现
"""
import os
import uuid
from typing import Optional
from pathlib import Path

try:
    import tos
    from tos.exceptions import TosClientError, TosServerError
except ImportError:
    raise ImportError("请安装火山云TOS SDK: pip install tos")


class VolcengineTOSSimple:
    """简化的火山云TOS对象存储服务"""
    
    def __init__(self, access_key: str, secret_key: str, endpoint: str, region: str, bucket_name: str):
        """
        初始化TOS客户端
        
        Args:
            access_key: 访问密钥ID (原始格式)
            secret_key: 访问密钥Secret (原始格式)
            endpoint: TOS服务端点，如 tos-cn-beijing.volces.com
            region: 区域，如 cn-beijing
            bucket_name: 存储桶名称
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint = endpoint
        self.region = region
        self.bucket_name = bucket_name
        
        print(f"🔧 创建TOS客户端:")
        print(f"   AK: {access_key[:10]}...")
        print(f"   SK: {secret_key[:10]}...")
        print(f"   Endpoint: {endpoint}")
        print(f"   Region: {region}")
        print(f"   Bucket: {bucket_name}")
        
        # 按照官方文档标准方式创建TOS客户端
        self.client = tos.TosClientV2(access_key, secret_key, endpoint, region)
    
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
        
        print(f"🌥️ 开始上传文件:")
        print(f"   本地路径: {file_path}")
        print(f"   对象键名: {object_key}")
        print(f"   目标桶: {self.bucket_name}")
        
        try:
            # 上传文件
            result = self.client.put_object_from_file(
                bucket=self.bucket_name,
                key=object_key,
                file_path=file_path
            )
            
            print(f"✅ 文件上传成功!")
            print(f"📊 请求ID: {result.request_id}")
            print(f"🔗 CRC64: {result.hash_crc64_ecma}")
            
            # 构建文件访问URL
            file_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"
            print(f"🌐 访问URL: {file_url}")
            return file_url
            
        except TosClientError as e:
            error_msg = f"TOS客户端错误: {e.message}"
            if hasattr(e, 'cause') and e.cause:
                error_msg += f", 原因: {e.cause}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
        except TosServerError as e:
            error_msg = f"TOS服务器错误: {e.code} - {e.message}"
            print(f"❌ {error_msg}")
            print(f"🔍 请求ID: {e.request_id}")
            if hasattr(e, 'request_url'):
                print(f"📡 请求URL: {e.request_url}")
            print(f"🔧 HTTP状态码: {e.status_code}")
            if hasattr(e, 'header'):
                print(f"📋 响应头: {e.header}")
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"未知错误: {e}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    def close(self):
        """关闭TOS客户端"""
        try:
            if hasattr(self.client, 'close'):
                self.client.close()
                print("🔐 TOS客户端已关闭")
        except Exception as e:
            print(f"⚠️ 关闭TOS客户端时出错: {e}")
    
    @classmethod
    def from_env(cls) -> "VolcengineTOSSimple":
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
            missing = [name for name, value in [
                ('VOLCENGINE_ACCESS_KEY', access_key),
                ('VOLCENGINE_SECRET_KEY', secret_key),
                ('TOS_ENDPOINT', endpoint),
                ('TOS_REGION', region),
                ('TOS_BUCKET', bucket)
            ] if not value]
            raise ValueError(f"缺少必要的环境变量: {', '.join(missing)}")
        
        print(f"📖 从环境变量加载TOS配置:")
        print(f"   ACCESS_KEY: {access_key[:12]}...")
        print(f"   SECRET_KEY: {secret_key[:12]}...")
        print(f"   ENDPOINT: {endpoint}")
        print(f"   REGION: {region}")
        print(f"   BUCKET: {bucket}")
        
        return cls(
            access_key=access_key,
            secret_key=secret_key,
            endpoint=endpoint,
            region=region,
            bucket_name=bucket
        )