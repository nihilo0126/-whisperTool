@echo off
chcp 65001
echo 正在啟動語音轉錄程式...
echo ==================================================

:: 檢查 Python 是否已安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo 錯誤：未找到 Python，請先安裝 Python
    pause
    exit /b 1
)

:: 檢查虛擬環境
if not exist "venv" (
    echo 正在創建虛擬環境...
    python -m venv venv
    call venv\Scripts\activate
    echo 正在安裝必要的套件...
    pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
    pip install openai-whisper numpy psutil tqdm ffmpeg-python soundfile
) else (
    call venv\Scripts\activate
    :: 確保所有套件都已安裝
    echo 正在檢查並安裝必要的套件...
    pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
    pip install openai-whisper numpy psutil tqdm ffmpeg-python soundfile
)

:: 執行程式
python whisper_transcribe.py

:: 如果發生錯誤，暫停顯示錯誤訊息
if errorlevel 1 (
    echo.
    echo 程式執行時發生錯誤！
    pause
)

:: 關閉虛擬環境
deactivate 