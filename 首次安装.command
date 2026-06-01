#!/bin/bash
# 本地化工具箱 - 首次安装 (macOS)

cd "$(dirname "$0")" || exit 1

echo "================================================"
echo "   本地化工具箱 - 首次安装"
echo "================================================"
echo

# 找一个可用的 Python 3
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[错误] 没找到 Python 3"
    echo "请先安装：brew install python   或者去 https://www.python.org/downloads/ 下载"
    echo
    read -r -p "按回车键退出..." _
    exit 1
fi

echo "使用 Python: $($PYTHON --version)"
echo
echo "正在安装依赖（第一次会比较慢，请耐心等待）..."
echo

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo
    echo "[错误] 依赖安装失败"
    echo "可能的原因："
    echo "  1. 网络问题"
    echo "  2. 试试加 --user 参数：$PYTHON -m pip install --user -r requirements.txt"
    echo
    read -r -p "按回车键退出..." _
    exit 1
fi

echo
echo "================================================"
echo "   安装完成！"
echo "================================================"
echo
echo "运行方式："
echo "  方式一：在终端里执行  $PYTHON 启动器.py"
echo "  方式二：在 VS Code 里打开本文件夹，按 F5"
echo
read -r -p "按回车键退出..." _
