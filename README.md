# YouTube 视频下载器

一个功能强大的YouTube视频下载器，具有智能格式选择、代理支持和格式验证等高级特性。

## 核心特性

- **智能格式选择**
  - 自动选择最佳视频和音频质量
  - 支持多种视频格式
  - 智能分析可用格式

- **下载管理**
  - 实时进度显示
  - 下载速度监控
  - 支持断点续传
  - 自动重试机制

- **代理支持**
  - 自动检测系统代理
  - 支持手动配置代理
  - 灵活的代理切换

- **格式验证**
  - 下载完成后的格式验证
  - 视频参数检查
  - 音频质量验证

- **错误处理**
  - 健壮的异常处理
  - 友好的错误提示
  - 自动恢复机制

## 技术实现

### 核心组件
- **yt-dlp**: YouTube视频解析和下载
- **FFmpeg**: 媒体处理和格式转换
- **Python 3.6+**: 核心编程语言

### 主要功能模块
1. **格式处理**
   - 获取可用格式列表
   - 智能选择最佳格式
   - 格式参数验证

2. **下载管理**
   - 进度跟踪系统
   - 断点续传支持
   - 自动重试机制

3. **代理配置**
   - Windows注册表读取
   - 环境变量检测
   - 手动代理设置

4. **格式验证**
   - FFprobe媒体分析
   - 参数对比验证
   - 质量保证

## 系统要求

- Python 3.6 或更高版本
- FFmpeg（用于媒体处理）
- yt-dlp（核心下载组件）
- Windows/Linux/MacOS 支持

## 快速开始

### Windows用户
1. 安装Python 3.6+
2. 运行 `install.bat` 安装依赖
3. 双击 `双击运行下载.bat` 启动程序

### 手动安装
1. 克隆仓库
   ```bash
   git clone https://github.com/yourusername/youtube-downloader.git
   ```
2. 进入项目目录
   ```bash
   cd youtube-downloader
   ```
3. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```
4. 运行下载器
   ```bash
   python main.py
   ```

## 许可证
MIT许可证 - 欢迎使用和修改！

## 安装

### Windows用户
1. 从[python.org](https://www.python.org/downloads/)安装Python 3.6+
2. 运行 `install.bat` 安装依赖
3. 运行 `双击运行下载.bat` 启动下载器

### 手动安装

## 常见问题

### 如何更新下载器？

- 运行以下命令以获取最新版本：
  ```bash
  git pull origin main
  ```

### 下载速度慢怎么办？

- 确保网络连接稳定
- 尝试使用代理以提高下载速度

### 如何报告问题？

- 在GitHub仓库中创建一个issue，并提供详细的错误信息和日志。

## 贡献

欢迎贡献代码！请阅读`CONTRIBUTING.md`以了解如何参与项目。
