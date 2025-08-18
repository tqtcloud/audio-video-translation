"""
火山云TOS对象存储服务
基于官方Python SDK实现文件上传功能
"""
import os
import uuid
import tempfile
import base64
from typing import Optional, BinaryIO
from pathlib import Path

try:
    import tos
    from tos.exceptions import TosClientError, TosServerError
except ImportError:
    raise ImportError("请安装火山云TOS SDK: pip install tos")


def decode_base64_if_needed(value: str) -> str:
    """如果是base64编码，则解码"""
    if not value:
        return value
    try:
        # 尝试base64解码
        decoded = base64.b64decode(value + '==')  # 添加padding
        decoded_str = decoded.decode('utf-8')
        if len(decoded_str) > 10:  # 合理的密钥长度
            return decoded_str
    except:
        pass
    return value


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
        
        # 预处理参数
        processed_endpoint = self._process_endpoint(endpoint)
        processed_ak, processed_sk = self._process_credentials(access_key, secret_key)
        
        try:
            # 创建TOS客户端 - 使用多种初始化方式
            self.client = self._create_tos_client(processed_ak, processed_sk, processed_endpoint, region)
            
            # 验证连接
            self._validate_connection()
            
        except Exception as e:
            print(f"❌ TOS客户端初始化失败: {e}")
            # 尝试备用初始化方式
            self.client = self._create_tos_client_fallback(processed_ak, processed_sk, processed_endpoint, region)
    
    def _process_endpoint(self, endpoint: str) -> str:
        """预处理endpoint格式"""
        # 移除协议前缀
        if endpoint.startswith(('http://', 'https://')):
            endpoint = endpoint.replace('https://', '').replace('http://', '')
            print(f"📝 已移除endpoint协议前缀: {endpoint}")
        
        return endpoint
    
    def _process_credentials(self, access_key: str, secret_key: str) -> tuple:
        """预处理访问密钥"""
        import base64
        
        processed_ak = access_key
        processed_sk = secret_key
        
        # 处理ACCESS_KEY - 火山云的AK通常以AKLT开头，长度约47字符
        if access_key.startswith('AKLT') and len(access_key) >= 40:
            processed_ak = access_key  # 直接使用原始值
            print("✅ ACCESS_KEY格式正确，直接使用原始值")
        else:
            # 尝试多种解码方式
            for decode_method in [base64.b64decode, base64.urlsafe_b64decode]:
                try:
                    decoded_ak = decode_method(access_key).decode('utf-8')
                    if decoded_ak.startswith('AKLT'):
                        processed_ak = decoded_ak
                        print("📝 已解码ACCESS_KEY")
                        break
                except Exception:
                    continue
        
        # 处理SECRET_KEY - 尝试URL安全Base64解码
        try:
            # 为URL安全Base64添加填充
            sk_padded = secret_key + '=' * (4 - len(secret_key) % 4)
            decoded_sk = base64.urlsafe_b64decode(sk_padded).decode('utf-8')
            if len(decoded_sk) >= 20:  # 合理的密钥长度
                processed_sk = decoded_sk
                print("📝 已使用URL安全Base64解码SECRET_KEY")
        except Exception:
            # 尝试标准Base64解码
            try:
                sk_padded = secret_key + '=' * (4 - len(secret_key) % 4)
                decoded_sk = base64.b64decode(sk_padded).decode('utf-8')
                if len(decoded_sk) >= 20:
                    processed_sk = decoded_sk
                    print("📝 已使用标准Base64解码SECRET_KEY")
            except Exception:
                print("📝 SECRET_KEY无需解码，使用原始值")
        
        return processed_ak, processed_sk
    
    def _is_base64(self, s: str) -> bool:
        """检查字符串是否是Base64编码"""
        try:
            if len(s) % 4 != 0:
                return False
            import base64
            decoded = base64.b64decode(s, validate=True)
            reencoded = base64.b64encode(decoded).decode('ascii')
            return s == reencoded
        except Exception:
            return False
    
    def _create_tos_client(self, ak: str, sk: str, endpoint: str, region: str):
        """创建TOS客户端"""
        print(f"🔧 正在创建TOS客户端...")
        print(f"   Endpoint: {endpoint}")
        print(f"   Region: {region}")
        print(f"   AK: {ak[:10]}...{ak[-4:] if len(ak) > 14 else '*' * len(ak)}")
        
        # 尝试多种客户端配置方式
        client_configs = [
            # 方式1: 标准参数顺序
            lambda: tos.TosClientV2(ak, sk, endpoint, region),
            # 方式2: 命名参数
            lambda: tos.TosClientV2(ak=ak, sk=sk, endpoint=endpoint, region=region),
            # 方式3: 不同的参数名称
            lambda: tos.TosClientV2(access_key_id=ak, access_key_secret=sk, endpoint=endpoint, region=region),
            # 方式4: 添加协议前缀
            lambda: tos.TosClientV2(ak=ak, sk=sk, endpoint=f"https://{endpoint}", region=region),
            # 方式5: 按文档标准顺序
            lambda: tos.TosClientV2(ak=ak, sk=sk, region=region, endpoint=endpoint)
        ]
        
        last_error = None
        for i, config_func in enumerate(client_configs, 1):
            try:
                print(f"   尝试配置方式 {i}...")
                client = config_func()
                print(f"   ✅ 配置方式 {i} 成功！")
                return client
            except Exception as e:
                last_error = e
                print(f"   ❌ 配置方式 {i} 失败: {e}")
                continue
        
        # 如果所有方式都失败，抛出最后一个错误
        raise Exception(f"所有TOS客户端配置方式都失败，最后错误: {last_error}")
    
    def _create_tos_client_fallback(self, ak: str, sk: str, endpoint: str, region: str):
        """备用TOS客户端创建方法"""
        print("🔄 尝试备用TOS客户端创建方法...")
        
        # 尝试不同的参数组合
        try:
            return tos.TosClientV2(
                access_key_id=ak,
                access_key_secret=sk,
                region=region,
                endpoint=endpoint
            )
        except Exception:
            pass
        
        # 尝试包含https前缀的endpoint
        try:
            https_endpoint = f"https://{endpoint}" if not endpoint.startswith('https://') else endpoint
            return tos.TosClientV2(
                ak=ak,
                sk=sk,
                region=region,
                endpoint=https_endpoint
            )
        except Exception:
            pass
        
        # 最后一次尝试
        return tos.TosClientV2(ak, sk, endpoint, region)
    
    def _validate_connection(self):
        """验证TOS连接"""
        try:
            # 尝试访问存储桶
            self.client.head_bucket(self.bucket_name)
            print(f"✅ TOS连接验证成功，存储桶: {self.bucket_name}")
        except TosServerError as e:
            if e.code == 'SignatureDoesNotMatch':
                raise Exception(f"TOS签名验证失败: {e.message}. 请检查ACCESS_KEY和SECRET_KEY是否正确")
            elif e.code == 'InvalidAccessKeyId':
                raise Exception(f"TOS访问密钥无效: {e.message}. 请检查ACCESS_KEY是否正确")
            elif e.code == 'NoSuchBucket':
                print(f"⚠️  存储桶不存在: {self.bucket_name}，但TOS连接正常")
            else:
                print(f"⚠️  TOS服务器响应: {e.code} - {e.message}")
        except TosClientError as e:
            raise Exception(f"TOS客户端错误: {e.message}")
        except Exception as e:
            print(f"⚠️  TOS连接验证异常: {e}")
            # 不抛出异常，允许后续操作尝试
    
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