@echo off
echo ==================================================
echo Whisper 語音轉錄工具 - 環境設置腳本
echo ==================================================
echo.

:: 檢查 Python 是否已安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 未找到 Python，請先安裝 Python 3.8 或更高版本
    echo 您可以在 https://www.python.org/downloads/ 下載 Python
    pause
    exit /b 1
)

echo [1/4] 檢查 Python 版本...
python --version
echo.

echo [2/4] 安裝/更新 pip...
python -m pip install --upgrade pip
echo.

echo [3/4] 安裝依賴套件...
pip install -r requirements.txt
echo.

echo [4/4] 創建必要的資料夾...
if not exist "models" mkdir models
if not exist "uploads" mkdir uploads
if not exist "轉錄結果" mkdir "轉錄結果"
echo.

echo ==================================================
echo 環境設置完成！
echo.
echo 您現在可以：
echo 1. 運行 start_web.bat 啟動應用
echo 2. 訪問 http://127.0.0.1:3000/ 使用網頁界面
echo ==================================================
echo.

pause 