@echo off
chcp 65001 >nul
title 本地化工具箱 - 首次安装

echo ================================================
echo    本地化工具箱 - 首次安装
echo ================================================
echo.
echo 正在检查 Python 环境...
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 Python
    echo 请先去 https://www.python.org/downloads/ 下载安装 Python 3.10 或更高版本
    echo 安装时记得勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

python --version
echo.
echo 正在安装依赖（第一次会比较慢，请耐心等待）...
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败
    echo 可能的原因：
    echo   1. 网络问题 - 试试连公司 VPN 或换网络
    echo   2. 用代理：python -m pip install --proxy http://代理地址:端口 -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================
echo    安装完成！
echo ================================================
echo.
echo 现在可以双击 "启动器.py" 使用工具箱了
echo.
pause
