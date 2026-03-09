@echo off
chcp 65001 >nul
echo ========================================
echo   DAC-3D V3.0 快速依赖安装脚本
echo ========================================
echo.

echo [提示] 正在检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python！请先安装Python 3.9+
    pause
    exit /b 1
)

echo [提示] Python环境检测成功
echo.

echo [提示] 正在安装软件在环(SIL)模式所需的核心依赖...
echo [提示] 这将安装精简版依赖，速度更快！
echo.

pip install transitions loguru pyyaml pydantic PyQt5 numpy scipy opencv-python Pillow tqdm colorama python-dotenv pytest requests

if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败！
    echo [建议] 请检查网络连接或尝试使用：
    echo         pip install -r requirements_sil.txt
    pause
    exit /b 1
)

echo.
echo ========================================
echo   ✅ 核心依赖安装完成！
echo ========================================
echo.
echo [提示] 现在可以运行软件在环模式了！
echo [提示] 直接双击 START.bat 或运行:
echo         python main_sil.py
echo.

pause
