@echo off
chcp 65001
echo 正在打包程式為執行檔...
echo ==================================================

:: 檢查 Python 是否已安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo 錯誤：未找到 Python，請先安裝 Python
    pause
    exit /b 1
)

:: 啟動虛擬環境
call venv\Scripts\activate

:: 使用 PyInstaller 打包
echo 正在打包程式...
pyinstaller --noconfirm --onefile --console ^
    --add-data "訪談記錄;訪談記錄" ^
    --add-data "轉錄結果;轉錄結果" ^
    --icon "NONE" ^
    --name "語音轉錄程式" ^
    whisper_transcribe.py

:: 檢查打包結果
if errorlevel 1 (
    echo 打包過程中發生錯誤！
    pause
    exit /b 1
)

echo.
echo 打包完成！
echo 執行檔位置：dist\語音轉錄程式.exe
echo ==================================================
pause 