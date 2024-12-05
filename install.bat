@echo off
chcp 65001 > nul
title Installing Dependencies

python --version > nul 2>&1
if errorlevel 1 (
    echo Python未安装！请先安装Python...
    pause
    exit /b
)

echo 正在安装必要的依赖...
pip install -r requirements.txt

echo 安装完成！
pause 