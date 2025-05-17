# Whisper 訪談記錄辨識工具

這是一個基於 OpenAI Whisper 的語音轉文字工具，專門用於處理訪談記錄的轉錄工作。該工具提供了友好的網頁界面，支持多種音頻格式，並可以選擇不同的 Whisper 模型來平衡準確度和速度。


## 系統需求

- Python 3.8 或更高版本
- CUDA 支持的 GPU（可選，但推薦）
- FFmpeg

## 快速開始

1. 下載專案：
   - 點擊頁面上方的綠色 "Code" 按鈕
   - 選擇 "Download ZIP"
   - 解壓縮下載的檔案



## 使用方法

### 第一次啟動前的準備

1.開啟 `setup_env.bat ` 
2.開啟 `setup.bat` 
3.等待所有安裝和下載完成

### 日常使用步驟

1. 開啟 ` start_web.bat ` 

## 模型說明

- tiny: 最小模型，速度最快，準確度較低
- base: 基礎模型，平衡速度和準確度
- small: 小型模型，適合一般使用
- medium: 中型模型，準確度較高
- large-v3: 大型模型，最高準確度，需要較多 GPU 記憶體



## 注意事項

- 首次運行時會自動下載選擇的模型
- 使用 NVDIA GPU 可以顯著提升轉錄速度
- 建議使用 SSD 存儲模型文件
- 使用 GPU 時請確保有足夠的顯存，如果使用CPU且記憶體不足可能可以靠增加虛擬記憶體解決
- 大型模型需要較多系統資源
- 建議定期清理任務歷史

## 更新日誌

### v1.0.0
- 初始版本發布
- 支持基本的音頻轉錄功能
- 添加網頁界面
- 支持 GPU 加速

## 授權

MIT License

使用的開源資源

- [OpenAI Whisper](https://github.com/openai/whisper)
- [Flask](https://flask.palletsprojects.com/)
- [Dropzone.js](https://www.dropzonejs.com/)

免責聲明
請遵守所有的開源法規與使用者原則，本頁面之所有本人提供的資源目的皆出以學習與交流之目的
