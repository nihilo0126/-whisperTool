# Whisper 訪談記錄辨識工具

這是一個基於 OpenAI Whisper 的語音轉文字工具，專門用於處理訪談記錄的轉錄工作。該工具提供了友好的網頁界面，支持多種音頻格式，並可以選擇不同的 Whisper 模型來平衡準確度和速度。

## 功能特點

- 🎯 支持多種音頻格式（WAV、MP3、M4A、OGG）
- 🚀 GPU 加速支持
- 📊 實時轉錄進度顯示
- 📝 支持輸出 TXT 和 SRT 格式
- 🎨 現代化的深色主題界面
- 🔄 支持多種 Whisper 模型（tiny、base、small、medium、large-v3）
- 📱 響應式設計，支持移動設備

## 系統需求

- Python 3.8 或更高版本
- CUDA 支持的 GPU（可選，但推薦）
- FFmpeg

## 安裝步驟

1. 克隆倉庫：
```bash
git clone https://github.com/你的用戶名/whisper-interview-transcriber.git
cd whisper-interview-transcriber
```

2. 安裝依賴：
```bash
pip install -r requirements.txt
```

3. 下載 Whisper 模型：
```bash
# 在 models 目錄下下載需要的模型
# 例如：tiny.pt, base.pt, small.pt, medium.pt, large-v3.pt
```

4. 啟動應用：
```bash
python app.py
```

## 使用方法

1. 訪問 http://localhost:3000
2. 選擇要使用的 Whisper 模型
3. 上傳音頻文件
4. 等待轉錄完成
5. 下載轉錄結果（TXT 或 SRT 格式）

## 配置說明

- 在 `config.ini` 中可以修改以下設置：
  - 端口號
  - 上傳文件大小限制
  - 模型路徑
  - GPU 設置

## 注意事項

- 首次運行時會自動下載選擇的模型
- 使用 GPU 可以顯著提升轉錄速度
- 建議使用 SSD 存儲模型文件

## 授權協議

MIT License

## 貢獻指南

歡迎提交 Issue 和 Pull Request！

## 更新日誌

### v1.0.0
- 初始版本發布
- 支持基本的音頻轉錄功能
- 添加網頁界面
- 支持 GPU 加速

## 模型說明

- tiny: 最小模型，速度最快，準確度較低
- base: 基礎模型，平衡速度和準確度
- small: 小型模型，適合一般使用
- medium: 中型模型，準確度較高
- large-v3: 大型模型，最高準確度，需要較多 GPU 記憶體

## 注意事項

- 使用 GPU 時請確保有足夠的顯存
- 大型模型需要較多系統資源
- 建議定期清理任務歷史

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 致謝

- [OpenAI Whisper](https://github.com/openai/whisper)
- [Flask](https://flask.palletsprojects.com/)
- [Dropzone.js](https://www.dropzonejs.com/)
