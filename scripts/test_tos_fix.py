#!/usr/bin/env python3
"""
测试修复后的TOS客户端
"""

import os
import sys
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"📁 已加载环境变量: {env_path}")

from services.providers.volcengine_tos import VolcengineTOS

def test_tos_connection():
    """测试TOS连接"""
    print("🧪 测试修复后的TOS客户端...")
    print("=" * 50)
    
    try:
        # 创建TOS客户端
        tos_client = VolcengineTOS.from_env()
        print("✅ TOS客户端创建成功！")
        
        # 创建测试文件
        test_content = "TOS connection test - 修复验证"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            test_file_path = f.name
        
        print(f"📝 创建测试文件: {test_file_path}")
        
        # 测试上传
        try:
            print("🔄 测试文件上传...")
            file_url = tos_client.upload_file(test_file_path)
            print(f"✅ 文件上传成功！")
            print(f"🔗 文件URL: {file_url}")
            
            # 测试上传字节数据
            print("\n🔄 测试字节数据上传...")
            byte_url = tos_client.upload_bytes(test_content.encode('utf-8'), file_extension='.txt')
            print(f"✅ 字节数据上传成功！")
            print(f"🔗 字节数据URL: {byte_url}")
            
            return True
            
        except Exception as upload_error:
            print(f"❌ 上传测试失败: {upload_error}")
            return False
            
        finally:
            # 清理测试文件
            try:
                os.unlink(test_file_path)
                print(f"🗑️  已清理测试文件: {test_file_path}")
            except Exception:
                pass
            
            # 关闭TOS客户端
            tos_client.close()
    
    except Exception as e:
        print(f"❌ TOS客户端测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_tos_connection()
    print("\n" + "=" * 50)
    if success:
        print("🎉 TOS修复验证成功！所有功能正常。")
    else:
        print("⚠️  TOS修复验证失败，请检查配置和网络。")
    
    sys.exit(0 if success else 1)