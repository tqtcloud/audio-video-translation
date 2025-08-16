# 🚀 快速启动指南

本指南将帮助您在5分钟内启动音频视频翻译系统。

## 📋 前置条件检查

### 1. Python环境
```bash
# 检查Python版本 (需要3.8+)
python3 --version

# 如果没有Python，请安装：
# macOS: brew install python
# Ubuntu: sudo apt install python3 python3-pip
# Windows: 从 python.org 下载安装
```

### 2. FFmpeg安装
```bash
# 检查FFmpeg是否已安装
ffmpeg -version

# 如果没有，请安装：
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows
# 下载：https://ffmpeg.org/download.html
# 或使用 Chocolatey: choco install ffmpeg
```

## ⚡ 快速安装

### 步骤1: 克隆项目
```bash
# 如果是从GitHub克隆
git clone <repository-url>
cd audio-video-translation

# 或者直接进入项目目录
cd audio-video-translation
```

### 步骤2: 安装依赖
```bash
# 安装Python依赖
pip3 install -r requirements.txt

# 如果遇到权限问题，使用用户安装：
pip3 install --user -r requirements.txt
```

### 步骤3: 配置API密钥
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件，添加您的OpenAI API密钥
nano .env
# 或使用其他编辑器: vim .env, code .env
```

在`.env`文件中，设置：
```bash
OPENAI_API_KEY=your_actual_api_key_here
```

> 💡 **获取API密钥**: 访问 [OpenAI Platform](https://platform.openai.com/api-keys) 创建API密钥

### 步骤4: 初始化系统
```bash
# 初始化系统
python3 main.py init

# 验证安装
python3 main.py metrics
```

## 🎯 第一次使用

### 测试系统功能
```bash
# 运行基础测试
python3 run_basic_test.py

# 如果看到 "✅ 所有基础测试通过！" 说明系统正常
```

### 处理您的第一个文件
```bash
# 准备一个测试文件 (或使用生成的测试文件)
# 支持格式: MP4, AVI, MOV, MKV, MP3, WAV, AAC, FLAC

# 基础翻译 (翻译到中文)
python3 main.py process your_video.mp4

# 指定目标语言
python3 main.py process your_video.mp4 --language es  # 西班牙语

# 等待处理完成
python3 main.py process your_video.mp4 --wait
```

### 监控处理进度
```bash
# 查看所有作业
python3 main.py list

# 查看特定作业状态
python3 main.py status JOB_ID

# 等待作业完成
python3 main.py wait JOB_ID
```

## 🔧 常用配置

### 调整语音模型
```bash
# 可选模型: alloy, echo, fable, onyx, nova, shimmer
python3 main.py config set voice_model nova
```

### 设置输出目录
```bash
python3 main.py config set output_directory /path/to/your/output
```

### 语言设置
```bash
# 支持的语言: en, zh, es, fr, de
python3 main.py config set target_language zh
```

## 📱 使用示例

### 示例1: 翻译YouTube视频
```bash
# 下载视频 (需要 yt-dlp)
yt-dlp -f mp4 "https://youtube.com/watch?v=VIDEO_ID"

# 翻译视频
python3 main.py process "VIDEO_TITLE.mp4" --language zh-CN --wait
```

### 示例2: 批量处理
```bash
# 批量处理目录中的所有MP4文件
for file in ./input/*.mp4; do
    echo "处理: $file"
    python3 main.py process "$file" --language zh-CN
done

# 等待所有作业完成
python3 main.py list
```

### 示例3: 高质量处理
```bash
# 使用最佳质量设置
python3 main.py config set voice_model nova
python3 main.py config set preserve_background_audio true
python3 main.py process input.mp4 --language zh-CN --wait
```

## 🔍 故障排除

### 常见问题及解决方案

#### 1. API密钥错误
```bash
# 现象: "OpenAI API密钥未设置"
# 解决: 检查.env文件
cat .env | grep OPENAI_API_KEY

# 重新设置密钥
echo "OPENAI_API_KEY=your_key_here" > .env
```

#### 2. FFmpeg未找到
```bash
# 现象: "ffmpeg: command not found"
# 解决: 安装FFmpeg
brew install ffmpeg  # macOS
sudo apt install ffmpeg  # Linux
```

#### 3. 依赖安装失败
```bash
# 现象: pip install失败
# 解决: 更新pip并重试
pip3 install --upgrade pip
pip3 install -r requirements.txt
```

#### 4. 权限问题
```bash
# 现象: Permission denied
# 解决: 使用用户安装或调整权限
pip3 install --user -r requirements.txt
# 或
sudo chown -R $USER:$USER ./output ./temp ./uploads
```

### 获取帮助
```bash
# 查看命令帮助
python3 main.py --help
python3 main.py process --help

# 查看系统状态
python3 main.py metrics

# 运行诊断
python3 run_basic_test.py
```

## 📚 下一步

现在您已经成功启动了系统！接下来可以：

1. **阅读完整文档**: 查看 `README.md` 了解所有功能
2. **查看测试报告**: 阅读 `TEST_REPORT.md` 了解系统质量
3. **自定义配置**: 根据需求调整 `.env` 和配置参数
4. **批量处理**: 编写脚本处理大量文件
5. **质量优化**: 调整参数获得最佳输出质量

## 🎉 成功指标

如果您看到以下输出，说明系统已成功启动：

```bash
✅ 系统初始化完成!
✅ 所有基础测试通过！
🎉 文件处理完成！
```

享受使用音频视频翻译系统！ 🚀