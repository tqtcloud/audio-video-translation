#!/usr/bin/env python3
"""
火山云TOS认证问题诊断脚本
系统性检查和修复TOS认证失败问题
"""

import os
import sys
import base64
import json
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import tos
    from tos.exceptions import TosClientError, TosServerError
except ImportError:
    print("❌ TOS SDK未安装，请运行: pip install tos")
    sys.exit(1)


class TOSAuthDiagnostic:
    """TOS认证诊断工具"""
    
    def __init__(self):
        self.issues = []
        self.solutions = []
        self.test_results = {}
    
    def check_environment_variables(self):
        """检查环境变量配置"""
        print("🔍 检查环境变量配置...")
        
        required_vars = [
            'VOLCENGINE_ACCESS_KEY',
            'VOLCENGINE_SECRET_KEY', 
            'TOS_ENDPOINT',
            'TOS_REGION',
            'TOS_BUCKET'
        ]
        
        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                print(f"  ✅ {var}: {'*' * (len(value) - 4)}{value[-4:]}")
        
        if missing_vars:
            self.issues.append(f"缺少环境变量: {', '.join(missing_vars)}")
            self.solutions.append("设置所有必需的环境变量")
            return False
        
        return True
    
    def check_access_key_format(self):
        """检查访问密钥格式"""
        print("\n🔍 检查访问密钥格式...")
        
        ak = os.getenv('VOLCENGINE_ACCESS_KEY', '')
        sk = os.getenv('VOLCENGINE_SECRET_KEY', '')
        
        # 检查是否是Base64编码
        ak_issues = []
        sk_issues = []
        
        # 检查AK格式
        if ak.startswith('AKLT'):
            print("  ✅ ACCESS_KEY格式正确 (以AKLT开头)")
        else:
            if self._is_base64(ak):
                ak_issues.append("ACCESS_KEY似乎是Base64编码的，需要解码")
                try:
                    decoded_ak = base64.b64decode(ak).decode('utf-8')
                    print(f"  ⚠️  解码后的ACCESS_KEY: {decoded_ak[:10]}...")
                    if decoded_ak.startswith('AKLT'):
                        self.solutions.append(f"将ACCESS_KEY解码为: {decoded_ak}")
                except:
                    ak_issues.append("ACCESS_KEY无法解码，可能格式错误")
            else:
                ak_issues.append("ACCESS_KEY格式不正确，应以AKLT开头")
        
        # 检查SK格式
        if len(sk) >= 32:
            print("  ✅ SECRET_KEY长度合理")
        else:
            sk_issues.append("SECRET_KEY长度太短")
        
        if self._is_base64(sk):
            try:
                decoded_sk = base64.b64decode(sk).decode('utf-8')
                print(f"  ⚠️  解码后的SECRET_KEY: {decoded_sk[:8]}...")
                self.solutions.append("需要解码SECRET_KEY")
            except:
                sk_issues.append("SECRET_KEY无法解码")
        
        if ak_issues or sk_issues:
            self.issues.extend(ak_issues + sk_issues)
            return False
        
        return True
    
    def check_endpoint_format(self):
        """检查endpoint格式"""
        print("\n🔍 检查endpoint格式...")
        
        endpoint = os.getenv('TOS_ENDPOINT', '')
        region = os.getenv('TOS_REGION', '')
        
        endpoint_issues = []
        
        # 检查endpoint格式
        if endpoint.startswith(('http://', 'https://')):
            print(f"  ⚠️  endpoint包含协议前缀: {endpoint}")
            endpoint_issues.append("endpoint不应包含http://或https://前缀")
            clean_endpoint = endpoint.replace('https://', '').replace('http://', '')
            self.solutions.append(f"移除协议前缀，使用: {clean_endpoint}")
        
        if not endpoint.endswith('.volces.com'):
            endpoint_issues.append("endpoint格式不正确，应以.volces.com结尾")
        
        # 检查region匹配
        expected_endpoint = f"tos-{region}.volces.com"
        if endpoint != expected_endpoint and not endpoint.startswith('https://'):
            endpoint_issues.append(f"endpoint与region不匹配，应为: {expected_endpoint}")
            self.solutions.append(f"将endpoint设置为: {expected_endpoint}")
        
        if endpoint_issues:
            self.issues.extend(endpoint_issues)
            return False
        
        print(f"  ✅ endpoint格式正确: {endpoint}")
        return True
    
    def check_bucket_access(self):
        """检查存储桶访问权限"""
        print("\n🔍 检查存储桶访问权限...")
        
        try:
            # 使用原始配置测试
            ak = os.getenv('VOLCENGINE_ACCESS_KEY')
            sk = os.getenv('VOLCENGINE_SECRET_KEY')
            endpoint = os.getenv('TOS_ENDPOINT')
            region = os.getenv('TOS_REGION')
            bucket = os.getenv('TOS_BUCKET')
            
            # 尝试解码密钥（如果是Base64编码）
            if self._is_base64(ak):
                try:
                    ak = base64.b64decode(ak).decode('utf-8')
                    print("  📝 使用解码后的ACCESS_KEY")
                except:
                    pass
            
            if self._is_base64(sk):
                try:
                    sk = base64.b64decode(sk).decode('utf-8')
                    print("  📝 使用解码后的SECRET_KEY")
                except:
                    pass
            
            # 移除endpoint中的协议前缀
            if endpoint.startswith(('http://', 'https://')):
                endpoint = endpoint.replace('https://', '').replace('http://', '')
                print(f"  📝 使用清理后的endpoint: {endpoint}")
            
            # 创建客户端
            client = tos.TosClientV2(
                ak=ak,
                sk=sk,
                endpoint=endpoint,
                region=region
            )
            
            # 测试存储桶访问
            print(f"  🧪 测试存储桶访问: {bucket}")
            client.head_bucket(bucket)
            print("  ✅ 存储桶访问成功！")
            
            self.test_results['bucket_access'] = True
            return True
            
        except TosServerError as e:
            error_msg = f"TOS服务器错误: {e.code} - {e.message}"
            print(f"  ❌ {error_msg}")
            
            if e.code == 'SignatureDoesNotMatch':
                self.issues.append("签名验证失败 - 密钥或配置错误")
                self.solutions.append("检查ACCESS_KEY和SECRET_KEY是否正确")
                self.solutions.append("确认endpoint和region配置匹配")
            elif e.code == 'InvalidAccessKeyId':
                self.issues.append("访问密钥ID无效")
                self.solutions.append("检查ACCESS_KEY是否正确且有效")
            elif e.code == 'NoSuchBucket':
                self.issues.append(f"存储桶不存在: {bucket}")
                self.solutions.append("检查存储桶名称是否正确")
            else:
                self.issues.append(f"未知服务器错误: {e.code}")
            
            self.test_results['bucket_access'] = False
            return False
            
        except TosClientError as e:
            error_msg = f"TOS客户端错误: {e.message}"
            print(f"  ❌ {error_msg}")
            self.issues.append("客户端配置错误")
            self.solutions.append("检查网络连接和客户端配置")
            self.test_results['bucket_access'] = False
            return False
            
        except Exception as e:
            print(f"  ❌ 未知错误: {e}")
            self.issues.append(f"未知错误: {e}")
            self.test_results['bucket_access'] = False
            return False
    
    def test_file_upload(self):
        """测试文件上传功能"""
        print("\n🔍 测试文件上传功能...")
        
        if not self.test_results.get('bucket_access', False):
            print("  ⏭️  跳过上传测试（存储桶访问失败）")
            return False
        
        try:
            # 创建测试文件
            test_content = b"TOS authentication test file"
            with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as temp_file:
                temp_file.write(test_content)
                temp_file_path = temp_file.name
            
            # 使用修正后的配置
            ak = os.getenv('VOLCENGINE_ACCESS_KEY')
            sk = os.getenv('VOLCENGINE_SECRET_KEY')
            endpoint = os.getenv('TOS_ENDPOINT')
            region = os.getenv('TOS_REGION')
            bucket = os.getenv('TOS_BUCKET')
            
            # 应用修正
            if self._is_base64(ak):
                ak = base64.b64decode(ak).decode('utf-8')
            if self._is_base64(sk):
                sk = base64.b64decode(sk).decode('utf-8')
            if endpoint.startswith(('http://', 'https://')):
                endpoint = endpoint.replace('https://', '').replace('http://', '')
            
            client = tos.TosClientV2(ak=ak, sk=sk, endpoint=endpoint, region=region)
            
            # 上传测试文件
            test_key = f"test/auth_diagnostic_{os.getpid()}.txt"
            result = client.put_object_from_file(
                bucket=bucket,
                key=test_key,
                file_path=temp_file_path
            )
            
            print(f"  ✅ 文件上传成功！对象键: {test_key}")
            print(f"  📊 请求ID: {result.request_id}")
            
            # 清理测试文件
            client.delete_object(bucket, test_key)
            os.unlink(temp_file_path)
            
            self.test_results['file_upload'] = True
            return True
            
        except Exception as e:
            print(f"  ❌ 文件上传失败: {e}")
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            self.test_results['file_upload'] = False
            return False
    
    def _is_base64(self, s):
        """检查字符串是否是Base64编码"""
        try:
            if len(s) % 4 != 0:
                return False
            decoded = base64.b64decode(s, validate=True)
            reencoded = base64.b64encode(decoded).decode('ascii')
            return s == reencoded
        except:
            return False
    
    def generate_fixed_config(self):
        """生成修正后的配置"""
        print("\n🔧 生成修正后的配置...")
        
        ak = os.getenv('VOLCENGINE_ACCESS_KEY', '')
        sk = os.getenv('VOLCENGINE_SECRET_KEY', '')
        endpoint = os.getenv('TOS_ENDPOINT', '')
        region = os.getenv('TOS_REGION', '')
        bucket = os.getenv('TOS_BUCKET', '')
        
        # 应用修正
        if self._is_base64(ak):
            ak = base64.b64decode(ak).decode('utf-8')
        
        if self._is_base64(sk):
            sk = base64.b64decode(sk).decode('utf-8')
        
        if endpoint.startswith(('http://', 'https://')):
            endpoint = endpoint.replace('https://', '').replace('http://', '')
        
        fixed_config = {
            'VOLCENGINE_ACCESS_KEY': ak,
            'VOLCENGINE_SECRET_KEY': sk,
            'TOS_ENDPOINT': endpoint,
            'TOS_REGION': region,
            'TOS_BUCKET': bucket
        }
        
        # 保存修正后的配置到文件
        config_file = Path(__file__).parent.parent / '.env.tos.fixed'
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("# 修正后的TOS配置\n")
            f.write("# 请将以下内容复制到.env文件中\n\n")
            for key, value in fixed_config.items():
                if key.endswith('_KEY'):
                    # 隐藏密钥显示
                    display_value = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "*" * len(value)
                    f.write(f"{key}={value}\n")
                    print(f"  📝 {key}={display_value}")
                else:
                    f.write(f"{key}={value}\n")
                    print(f"  📝 {key}={value}")
        
        print(f"\n💾 修正后的配置已保存到: {config_file}")
        return fixed_config
    
    def run_full_diagnostic(self):
        """运行完整诊断"""
        print("🚀 开始TOS认证问题诊断...")
        print("=" * 60)
        
        # 1. 检查环境变量
        env_ok = self.check_environment_variables()
        
        # 2. 检查密钥格式
        key_format_ok = self.check_access_key_format()
        
        # 3. 检查endpoint格式
        endpoint_ok = self.check_endpoint_format()
        
        # 4. 测试存储桶访问
        bucket_ok = self.check_bucket_access()
        
        # 5. 测试文件上传
        upload_ok = self.test_file_upload()
        
        # 6. 生成修正配置
        if self.issues:
            self.generate_fixed_config()
        
        # 7. 输出诊断报告
        self.print_diagnostic_report()
        
        return all([env_ok, bucket_ok])
    
    def print_diagnostic_report(self):
        """打印诊断报告"""
        print("\n" + "=" * 60)
        print("📋 TOS认证诊断报告")
        print("=" * 60)
        
        # 测试结果摘要
        print("\n🧪 测试结果摘要:")
        results = [
            ("环境变量检查", "✅" if not any("缺少环境变量" in issue for issue in self.issues) else "❌"),
            ("密钥格式检查", "✅" if not any("ACCESS_KEY" in issue or "SECRET_KEY" in issue for issue in self.issues) else "❌"),
            ("Endpoint格式", "✅" if not any("endpoint" in issue for issue in self.issues) else "❌"),
            ("存储桶访问", "✅" if self.test_results.get('bucket_access', False) else "❌"),
            ("文件上传测试", "✅" if self.test_results.get('file_upload', False) else "❌")
        ]
        
        for test_name, status in results:
            print(f"  {status} {test_name}")
        
        # 发现的问题
        if self.issues:
            print("\n❌ 发现的问题:")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
        
        # 建议的解决方案
        if self.solutions:
            print("\n💡 建议的解决方案:")
            for i, solution in enumerate(set(self.solutions), 1):
                print(f"  {i}. {solution}")
        
        # 成功状态
        if not self.issues and self.test_results.get('bucket_access', False):
            print("\n🎉 所有测试通过！TOS认证配置正确。")
        else:
            print("\n⚠️  请根据上述建议修复问题后重新运行诊断。")
        
        print("\n📞 如需进一步帮助:")
        print("  1. 检查火山云控制台中的访问密钥状态")
        print("  2. 确认存储桶权限设置") 
        print("  3. 查看TOS服务状态页面")


def main():
    """主函数"""
    # 加载环境变量
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"📁 已加载环境变量: {env_path}")
    else:
        print("⚠️  未找到.env文件，请确保配置了环境变量")
    
    # 运行诊断
    diagnostic = TOSAuthDiagnostic()
    success = diagnostic.run_full_diagnostic()
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()