@echo off
chcp 65001 >nul
echo ========================================
echo   DAC-3D V3.0 软件在环(SIL)快速启动
echo ========================================
echo.

REM 检查Python环境
echo [提示] 正在检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python！请先安装Python 3.9+
    pause
    exit /b 1
)

echo [提示] Python环境检测成功
echo.

REM 快速检查关键依赖
echo [提示] 正在检查依赖...
python -c "import transitions" >nul 2>&1
if errorlevel 1 (
    echo [警告] 缺少关键依赖 'transitions'
    echo [建议] 请先运行: 快速安装依赖.bat
    echo.
    echo 是否现在安装？
    choice /C YN /M "按Y安装依赖，按N取消"
    if errorlevel 2 goto :skip_install
    if errorlevel 1 (
        echo.
        echo [提示] 正在安装核心依赖...
        pip install transitions loguru pyyaml pydantic PyQt5 numpy scipy opencv-python Pillow tqdm colorama python-dotenv pytest requests
        if errorlevel 1 (
            echo [错误] 依赖安装失败！
            pause
            exit /b 1
        )
        echo [提示] 依赖安装完成！
        echo.
    )
)

:skip_install

REM 启动系统
echo ========================================
echo   启动DAC-3D系统（软件在环模式）...
echo ========================================
echo.

python main_sil.py

if errorlevel 1 (
    echo.
    echo [错误] 程序运行出错！
    echo [建议] 请检查错误信息
    pause
    exit /b 1
)

pause
