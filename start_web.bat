@echo off
chcp 65001
echo 正在啟動 Whisper 語音轉錄工具網頁界面...
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
    pip install flask flask-dropzone werkzeug
) else (
    call venv\Scripts\activate
    :: 確保所有套件都已安裝
    echo 正在檢查並安裝必要的套件...
    pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
    pip install openai-whisper numpy psutil tqdm ffmpeg-python soundfile
    pip install flask flask-dropzone werkzeug
)

:: 確保目錄存在
if not exist "uploads" mkdir uploads
if not exist "轉錄結果" mkdir 轉錄結果
if not exist "訪談記錄" mkdir 訪談記錄

:: 啟動 Web 應用
echo.
echo 正在啟動 Web 應用...
echo 請打開瀏覽器訪問: http://127.0.0.1:3000/
echo.
echo 按 Ctrl+C 可停止服務
echo ==================================================

python app.py

:: 如果發生錯誤，暫停顯示錯誤訊息
if errorlevel 1 (
    echo.
    echo 啟動 Web 應用時發生錯誤！
    pause
)

:: 關閉虛擬環境
deactivate 