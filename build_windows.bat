@echo off
REM ============================================================
REM  WeiboArchive - Windows 一键打包脚本 (PyInstaller + PyWebView)
REM  用法：在 Windows 上于项目根目录双击运行本脚本
REM  产物：dist/WeiboArchive.exe + dist/WeiboArchive-portable.zip
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/4] 构建前端 (frontend/dist) ...
if not exist "frontend\dist\index.html" (
    pushd frontend
    call npm install || goto :err
    call npm run build || goto :err
    popd
) else (
    echo     已存在 frontend/dist，跳过构建。
)

echo [2/4] 准备 Python 环境 ...
if not exist ".venv-win" (
    python -m venv .venv-win || goto :err
)
call .venv-win\Scripts\activate.bat
python -m pip install -U pip setuptools wheel || goto :err
pip install -r requirements.txt || goto :err
pip install pyinstaller || goto :err

echo [3/4] 运行 PyInstaller 打包 ...
pyinstaller --clean --noconfirm webo_archive.spec || goto :err

echo [4/4] 生成免安装绿色版 zip ...
if exist "dist\WeiboArchive.exe" (
    powershell -NoProfile -Command "Compress-Archive -Path 'dist\WeiboArchive.exe' -DestinationPath 'dist\WeiboArchive-portable.zip' -Force"
)

echo.
echo ============================================================
echo  打包完成！产物位于 dist\ 目录：
echo    - WeiboArchive.exe         （安装/直接运行）
echo    - WeiboArchive-portable.zip（免安装绿色版）
echo ============================================================
goto :eof

:err
echo.
echo [错误] 打包失败，请检查上方日志。
exit /b 1