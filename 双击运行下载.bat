@echo off
echo 正在启动YouTube视频下载器...
echo.

:: 检查Python是否已安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未检测到Python安装。
    echo 请先安装Python后再运行此脚本。
    pause
    exit /b 1
)

:: 检查必要的Python包是否已安装
python -c "import yt_dlp" >nul 2>&1
if errorlevel 1 (
    echo 正在安装必要的Python包...
    pip install yt_dlp
)

:: 运行下载器脚本
python downloader.py

echo.
echo 下载完成！
pause