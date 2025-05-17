@echo off
chcp 65001
echo 正在設置語音轉錄程式環境...
echo ==================================================

:: 檢查 Python 是否已安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo 錯誤：未找到 Python，請先安裝 Python
    pause
    exit /b 1
)

:: 創建虛擬環境
echo 正在創建虛擬環境...
python -m venv venv

:: 啟動虛擬環境
call venv\Scripts\activate

:: 更新 pip
echo 正在更新 pip...
python -m pip install --upgrade pip

:: 安裝必要的套件
echo 正在安裝必要的套件...
pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
pip install openai-whisper numpy psutil tqdm ffmpeg-python soundfile

:: 檢查安裝結果
if errorlevel 1 (
    echo 安裝套件時發生錯誤！
    pause
    exit /b 1
)

echo.
echo 環境設置完成！
echo 您現在可以執行 run_transcribe.bat 來啟動程式
echo ==================================================
pause 