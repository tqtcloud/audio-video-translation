#!/usr/bin/env python3
"""
火山云TOS SDK安装脚本
帮助用户安装TOS Python SDK并测试上传功能
"""

import subprocess
import sys
import os
from pathlib import Path

def install_tos_sdk():
    """安装TOS SDK"""
    print("🔧 正在安装火山云TOS Python SDK...")
    
    try:
        # 尝试安装TOS SDK
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "tos", "--user", "--break-system-packages"
        ])
        print("✅ TOS SDK安装成功！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ TOS SDK安装失败: {e}")
        print("\n💡 替代安装方法:")
        print("1. 使用虚拟环境:")
        print("   python3 -m venv venv")
        print("   source venv/bin/activate")  
        print("   pip install tos")
        print("\n2. 或者手动下载安装:")
        print("   wget https://pypi.org/simple/tos/")
        return False

def test_tos_import():
    """测试TOS导入"""
    try:
        import tos
        print("✅ TOS SDK导入成功！")
        
        # 显示TOS客户端的初始化参数
        help_text = str(tos.TosClientV2.__doc__)
        print(f"📖 TOS客户端初始化参数: {help_text[:200]}...")
        return True
    except ImportError as e:
        print(f"❌ TOS SDK导入失败: {e}")
        return False

def create_env_template():
    """创建环境变量配置模板"""
    template = """
# 火山云TOS配置示例
# 请在.env文件中配置以下变量

VOLCENGINE_ACCESS_KEY=your_access_key_here
VOLCENGINE_SECRET_KEY=your_secret_key_here
TOS_ENDPOINT=tos-cn-beijing.volces.com
TOS_REGION=cn-beijing
TOS_BUCKET=your-bucket-name

# 获取这些信息的步骤:
# 1. 登录火山云控制台 https://console.volcengine.com/
# 2. 访问对象存储TOS控制台
# 3. 创建存储桶获得bucket名称
# 4. 在访问管理中创建访问密钥获得AK/SK
"""
    
    env_example_path = Path(__file__).parent.parent / ".env.tos.example"
    with open(env_example_path, 'w', encoding='utf-8') as f:
        f.write(template)
    
    print(f"📝 已创建TOS配置模板: {env_example_path}")
    print("💡 请参考该文件配置.env中的TOS相关环境变量")

def main():
    """主函数"""
    print("🚀 火山云TOS SDK安装和配置向导")
    print("=" * 50)
    
    # 1. 检查当前环境
    print(f"🐍 Python版本: {sys.version}")
    print(f"📁 当前目录: {os.getcwd()}")
    
    # 2. 尝试导入TOS，如果失败则安装
    if not test_tos_import():
        print("\n📦 TOS SDK未安装，开始安装...")
        if install_tos_sdk():
            # 安装成功后再次测试
            if not test_tos_import():
                print("❌ 安装后仍无法导入TOS SDK，请检查安装")
                return False
        else:
            print("❌ TOS SDK安装失败")
            return False
    
    # 3. 创建配置模板
    create_env_template()
    
    # 4. 提供使用指南
    print("\n🎯 接下来的步骤:")
    print("1. 配置.env文件中的TOS相关环境变量")
    print("2. 运行测试: python3 main.py process <audio_file> --language en --wait")
    print("3. 系统会自动上传本地文件到TOS并进行处理")
    
    print("\n✅ TOS SDK配置完成！")
    return True

if __name__ == "__main__":
    main()