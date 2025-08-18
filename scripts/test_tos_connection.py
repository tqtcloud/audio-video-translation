#!/usr/bin/env python3
"""
火山云TOS连接测试和问题诊断脚本
"""

import os
import sys
import base64
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

try:
    import tos
    from tos.exceptions import TosClientError, TosServerError
except ImportError:
    print("❌ 请先安装TOS SDK: pip install tos")
    sys.exit(1)


def decode_base64_if_needed(value):
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


def test_tos_connection():
    """测试TOS连接"""
    
    # 获取配置
    access_key = os.getenv('VOLCENGINE_ACCESS_KEY')
    secret_key = os.getenv('VOLCENGINE_SECRET_KEY')
    endpoint = os.getenv('TOS_ENDPOINT')
    region = os.getenv('TOS_REGION')
    bucket = os.getenv('TOS_BUCKET')
    
    print("🔍 检查TOS配置...")
    print(f"Access Key: {access_key[:10]}..." if access_key else "❌ 缺少VOLCENGINE_ACCESS_KEY")
    print(f"Secret Key: {secret_key[:10]}..." if secret_key else "❌ 缺少VOLCENGINE_SECRET_KEY")
    print(f"Endpoint: {endpoint}")
    print(f"Region: {region}")
    print(f"Bucket: {bucket}")
    
    if not all([access_key, secret_key, endpoint, region, bucket]):
        print("❌ TOS配置不完整")
        return False
    
    # 尝试base64解码密钥
    print("\n🔧 尝试解码密钥...")
    decoded_access_key = decode_base64_if_needed(access_key)
    decoded_secret_key = decode_base64_if_needed(secret_key)
    
    if decoded_access_key != access_key:
        print(f"✓ Access Key解码成功: {decoded_access_key[:10]}...")
    if decoded_secret_key != secret_key:
        print(f"✓ Secret Key解码成功: {decoded_secret_key[:10]}...")
    
    # 测试不同的客户端初始化方式
    test_cases = [
        ("原始密钥", access_key, secret_key),
        ("解码密钥", decoded_access_key, decoded_secret_key),
    ]
    
    for name, ak, sk in test_cases:
        print(f"\n🧪 测试 {name}...")
        
        try:
            # 方法1: 标准初始化
            client = tos.TosClientV2(ak, sk, endpoint, region)
            
            # 测试列举存储桶
            print("🔍 测试列举存储桶...")
            buckets = client.list_buckets()
            print(f"✅ 成功！找到 {len(buckets.buckets)} 个存储桶")
            
            # 测试访问指定存储桶
            print(f"🔍 测试访问存储桶: {bucket}...")
            objects = client.list_objects(bucket, max_keys=1)
            print(f"✅ 存储桶访问成功")
            
            client.close()
            return True
            
        except TosServerError as e:
            print(f"❌ TOS服务器错误: {e.code} - {e.message}")
            if e.code == 'SignatureDoesNotMatch':
                print("💡 签名不匹配，尝试其他密钥格式...")
                continue
            elif e.code == 'NoSuchBucket':
                print(f"💡 存储桶不存在: {bucket}")
                return False
            elif e.code == 'AccessDenied':
                print("💡 权限不足，请检查密钥权限")
                return False
        except TosClientError as e:
            print(f"❌ TOS客户端错误: {e.message}")
        except Exception as e:
            print(f"❌ 其他错误: {e}")
    
    return False


def test_minimal_upload():
    """测试最小上传功能"""
    print("\n📤 测试文件上传...")
    
    # 获取配置
    access_key = decode_base64_if_needed(os.getenv('VOLCENGINE_ACCESS_KEY'))
    secret_key = decode_base64_if_needed(os.getenv('VOLCENGINE_SECRET_KEY'))
    endpoint = os.getenv('TOS_ENDPOINT')
    region = os.getenv('TOS_REGION')
    bucket = os.getenv('TOS_BUCKET')
    
    try:
        client = tos.TosClientV2(access_key, secret_key, endpoint, region)
        
        # 创建测试内容
        test_content = "Hello TOS Test!"
        test_key = "test/hello.txt"
        
        # 上传测试
        result = client.put_object(bucket, test_key, content=test_content)
        print(f"✅ 上传成功! 请求ID: {result.request_id}")
        
        # 下载验证
        download_result = client.get_object(bucket, test_key)
        downloaded_content = download_result.read().decode('utf-8')
        
        if downloaded_content == test_content:
            print("✅ 下载验证成功!")
        else:
            print("❌ 下载内容不匹配")
        
        # 清理测试文件
        client.delete_object(bucket, test_key)
        print("✅ 测试文件已清理")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ 上传测试失败: {e}")
        return False


if __name__ == "__main__":
    print("🧪 火山云TOS连接诊断工具")
    print("=" * 50)
    
    if test_tos_connection():
        print("\n🎉 TOS连接测试成功!")
        
        if test_minimal_upload():
            print("\n✅ 所有测试通过，TOS配置正常!")
        else:
            print("\n⚠️ 连接正常但上传测试失败")
    else:
        print("\n❌ TOS连接测试失败")
        print("\n💡 建议:")
        print("1. 检查火山云控制台中的访问密钥状态")
        print("2. 确认密钥权限包含TOS操作")
        print("3. 验证存储桶名称和区域配置")
        print("4. 联系火山云技术支持")