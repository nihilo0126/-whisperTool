import whisper
import torch
import os
from pathlib import Path
import logging
import traceback
from contextlib import nullcontext
import sys
from datetime import datetime
import psutil
import platform

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 設置 ffmpeg 路徑
FFMPEG_PATH = r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG_PATH):
    logging.error(f"找不到 ffmpeg: {FFMPEG_PATH}")
    print(f"錯誤：找不到 ffmpeg: {FFMPEG_PATH}")
    print("請確保 ffmpeg 已正確安裝在指定路徑")
    sys.exit(1)

os.environ["PATH"] = os.path.dirname(FFMPEG_PATH) + os.pathsep + os.environ["PATH"]
print(f"設置 ffmpeg 路徑: {FFMPEG_PATH}")
logging.info(f"設置 ffmpeg 路徑: {FFMPEG_PATH}")

def get_system_memory():
    """獲取系統記憶體信息"""
    memory = psutil.virtual_memory()
    return {
        'total': memory.total / (1024**3),  # GB
        'available': memory.available / (1024**3),  # GB
        'used': memory.used / (1024**3)  # GB
    }

def check_gpu():
    """檢查 GPU 狀態並返回設備信息"""
    print("\n檢查系統資源狀態...")
    print("="*50)
    
    # 檢查 PyTorch 和 CUDA
    print(f"PyTorch 版本: {torch.__version__}")
    cuda_available = torch.cuda.is_available()
    print(f"CUDA 是否可用: {cuda_available}")
    
    if cuda_available:
        print(f"CUDA 版本: {torch.version.cuda}")
        device_count = torch.cuda.device_count()
        print(f"找到 {device_count} 個 GPU 設備")
        
        # 獲取 GPU 信息
        gpu_info = []
        for i in range(device_count):
            gpu = torch.cuda.get_device_properties(i)
            total_memory = gpu.total_memory / (1024**3)  # GB
            allocated_memory = torch.cuda.memory_allocated(i) / (1024**3)  # GB
            reserved_memory = torch.cuda.memory_reserved(i) / (1024**3)  # GB
            free_memory = total_memory - allocated_memory
            
            gpu_info.append({
                'name': gpu.name,
                'total_memory': total_memory,
                'allocated_memory': allocated_memory,
                'reserved_memory': reserved_memory,
                'free_memory': free_memory
            })
            
            print(f"\nGPU {i}: {gpu.name}")
            print(f"總記憶體: {total_memory:.2f} GB")
            print(f"已分配記憶體: {allocated_memory:.2f} GB")
            print(f"實際使用記憶體: {reserved_memory:.2f} GB")
            print(f"可用記憶體: {free_memory:.2f} GB")
    else:
        print("未找到可用的 GPU，將使用 CPU 模式")
        gpu_info = None
    
    # 獲取系統記憶體信息
    system_memory = get_system_memory()
    print(f"\n系統記憶體:")
    print(f"總記憶體: {system_memory['total']:.2f} GB")
    print(f"已使用: {system_memory['used']:.2f} GB")
    print(f"可用: {system_memory['available']:.2f} GB")
    
    return {
        'cuda_available': cuda_available,
        'gpu_info': gpu_info,
        'system_memory': system_memory
    }

def select_model_size(system_info):
    """根據系統資源選擇合適的模型大小"""
    if system_info['cuda_available'] and system_info['gpu_info']:
        # 使用 GPU 時，根據 GPU 記憶體選擇模型
        gpu_memory = system_info['gpu_info'][0]['free_memory']
        if gpu_memory >= 10:
            return "large-v3"
        elif gpu_memory >= 6:
            return "medium"
        elif gpu_memory >= 4:
            return "small"
        else:
            return "base"
    else:
        # 使用 CPU 時，根據系統記憶體選擇模型
        system_memory = system_info['system_memory']['available']
        if system_memory >= 16:
            return "large-v3"
        elif system_memory >= 8:
            return "medium"
        elif system_memory >= 4:
            return "small"
        else:
            return "base"

def format_timestamp(seconds):
    """將秒數轉換為時間戳格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

def transcribe_audio(model, audio_path, output_dir, use_gpu=True):
    """轉錄單個音頻文件"""
    try:
        print(f"\n處理檔案: {audio_path}")
        logging.info(f"處理檔案: {audio_path}")
        
        # 獲取檔案的絕對路徑
        audio_path = os.path.abspath(audio_path)
        print(f"檔案絕對路徑: {audio_path}")
        logging.info(f"檔案絕對路徑: {audio_path}")
        
        # 檢查檔案是否存在
        if not os.path.exists(audio_path):
            print(f"錯誤：找不到檔案 {audio_path}")
            logging.error(f"找不到檔案: {audio_path}")
            return False
            
        # 檢查檔案大小
        file_size = os.path.getsize(audio_path) / (1024 * 1024)  # 轉換為 MB
        print(f"檔案大小: {file_size:.2f} MB")
        logging.info(f"檔案大小: {file_size:.2f} MB")
        
        # 檢查 GPU 狀態
        check_gpu()
        
        # 設置設備
        device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        print(f"使用設備: {device}")
        logging.info(f"使用設備: {device}")
        
        # 選擇模型大小
        model_name = select_model_size(get_system_memory())
        print(f"選擇的模型: {model_name}")
        logging.info(f"選擇的模型: {model_name}")
        
        # 檢查模型文件
        model_path = os.path.expanduser(f"~/.cache/whisper/{model_name}.pt")
        if os.path.exists(model_path):
            print(f"找到模型文件: {model_path}")
            logging.info(f"找到模型文件: {model_path}")
            model_size = os.path.getsize(model_path) / (1024 * 1024 * 1024)  # 轉換為 GB
            print(f"模型文件大小: {model_size:.2f} GB")
            logging.info(f"模型文件大小: {model_size:.2f} GB")
        else:
            print(f"警告：找不到模型文件 {model_path}")
            logging.warning(f"找不到模型文件: {model_path}")
        
        print(f"正在載入 {model_name} 模型...")
        logging.info(f"正在載入 {model_name} 模型...")
        
        # 清理 GPU 記憶體
        if use_gpu and torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("已清理 GPU 記憶體")
            logging.info("已清理 GPU 記憶體")
        
        # 載入模型
        model = whisper.load_model(model_name, device=device)
        print("模型載入成功")
        logging.info("模型載入成功")
        
        # 將模型移動到 GPU
        if use_gpu and torch.cuda.is_available():
            model = model.to(device)
            print("模型已成功移動到 GPU")
            logging.info("模型已成功移動到 GPU")
        
        # 檢查模型大小
        model_size = sum(p.numel() * p.element_size() for p in model.parameters()) / (1024 * 1024 * 1024)
        print(f"模型大小: {model_size:.2f} GB")
        logging.info(f"模型大小: {model_size:.2f} GB")
        
        # 檢查 GPU 記憶體
        if use_gpu and torch.cuda.is_available():
            free_memory = torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)
            free_memory_gb = free_memory / (1024 * 1024 * 1024)
            print(f"當前可用 GPU 記憶體: {free_memory_gb:.2f} GB")
            logging.info(f"當前可用 GPU 記憶體: {free_memory_gb:.2f} GB")
        
        print(f"開始轉錄 {os.path.basename(audio_path)}...")
        logging.info(f"開始轉錄 {os.path.basename(audio_path)}...")
        
        # 設置轉錄選項
        transcribe_options = {
            "language": "zh",
            "task": "transcribe",
            "fp16": use_gpu and torch.cuda.is_available()
        }
        
        # 使用 autocast 進行混合精度計算
        with torch.cuda.amp.autocast() if use_gpu else nullcontext():
            print(f"使用路徑: {audio_path}")
            logging.info(f"使用路徑: {audio_path}")
            
            # 檢查檔案是否可讀
            if not os.access(audio_path, os.R_OK):
                print(f"錯誤：無法讀取檔案 {audio_path}")
                logging.error(f"無法讀取檔案: {audio_path}")
                return False
            
            print("檔案檢查通過，開始轉錄...")
            logging.info("檔案檢查通過，開始轉錄...")
            
            # 嘗試使用 POSIX 格式路徑
            audio_path_posix = str(Path(audio_path).as_posix())
            print(f"使用 POSIX 格式路徑: {audio_path_posix}")
            logging.info(f"使用 POSIX 格式路徑: {audio_path_posix}")
            
            print("嘗試使用 POSIX 格式路徑進行轉錄...")
            logging.info("嘗試使用 POSIX 格式路徑進行轉錄...")
            
            try:
                result = model.transcribe(audio_path_posix, **transcribe_options)
            except Exception as e:
                print(f"使用 POSIX 格式路徑失敗，嘗試使用原始路徑: {str(e)}")
                logging.warning(f"使用 POSIX 格式路徑失敗，嘗試使用原始路徑: {str(e)}")
                
                print("嘗試使用原始路徑進行轉錄...")
                logging.info("嘗試使用原始路徑進行轉錄...")
                
                audio_path_str = str(audio_path)
                result = model.transcribe(audio_path_str, **transcribe_options)
        
        # 清理 GPU 記憶體
        if use_gpu and torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("已清理 GPU 記憶體")
            logging.info("已清理 GPU 記憶體")
        
        # 生成輸出文件名
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        output_file = os.path.join(output_dir, f"{base_name}.txt")
        
        # 保存轉錄結果
        with open(output_file, "w", encoding="utf-8") as f:
            for segment in result["segments"]:
                start_time = format_timestamp(segment["start"])
                end_time = format_timestamp(segment["end"])
                text = segment["text"].strip()
                f.write(f"[{start_time} --> {end_time}] {text}\n")
        
        print(f"轉錄完成：{output_file}")
        logging.info(f"轉錄完成：{output_file}")
        return True
        
    except Exception as e:
        print(f"轉錄音頻時發生錯誤: {str(e)}")
        logging.error(f"轉錄音頻時發生錯誤: {str(e)}")
        logging.error("錯誤追蹤:", exc_info=True)
        print("錯誤追蹤:")
        traceback.print_exc()
        return False

def process_interview_files(input_dir, output_dir, model_name="base"):
    """
    處理訪談記錄資料夾中的所有音頻文件
    
    參數:
        input_dir (str/Path): 輸入資料夾路徑
        output_dir (str/Path): 輸出資料夾路徑
        model_name (str): Whisper 模型名稱
    """
    try:
        # 轉換為 Path 對象
        input_dir = Path(input_dir).resolve()
        output_dir = Path(output_dir).resolve()
        
        logging.info(f"輸入資料夾: {input_dir}")
        logging.info(f"輸出資料夾: {output_dir}")
        
        # 檢查輸入資料夾是否存在
        if not input_dir.exists():
            raise FileNotFoundError(f"找不到輸入資料夾: {input_dir}")
        
        # 創建輸出資料夾
        output_dir.mkdir(exist_ok=True)
        
        # 獲取所有 WAV 文件
        audio_files = []
        for file in input_dir.iterdir():
            if file.suffix.lower() == '.wav':
                # 檢查檔案是否可讀
                if not os.access(file, os.R_OK):
                    logging.warning(f"無法讀取檔案: {file}")
                    continue
                # 檢查檔案大小
                if file.stat().st_size == 0:
                    logging.warning(f"檔案大小為 0: {file}")
                    continue
                audio_files.append(file)
        
        if not audio_files:
            logging.warning("警告：沒有找到任何有效的 WAV 檔案")
            return
        
        # 按照檔案名稱排序
        audio_files.sort(key=lambda x: x.name)
        
        logging.info(f"找到 {len(audio_files)} 個音頻文件")
        
        # 顯示所有找到的檔案
        for audio_file in audio_files:
            size_mb = audio_file.stat().st_size / (1024*1024)
            logging.info(f"發現檔案: {audio_file.name} ({size_mb:.2f} MB)")
        
        # 處理每個音頻檔案
        success_count = 0
        for i, audio_path in enumerate(audio_files, 1):
            try:
                logging.info(f"\n開始處理第 {i}/{len(audio_files)} 個檔案: {audio_path.name}")
                
                # 再次確認檔案存在且可讀
                if not audio_path.exists():
                    logging.error(f"檔案不存在: {audio_path}")
                    continue
                
                if not os.access(audio_path, os.R_OK):
                    logging.error(f"無法讀取檔案: {audio_path}")
                    continue
                
                # 設定輸出檔案路徑
                txt_output_path = output_dir / f"{audio_path.stem}.txt"
                srt_output_path = output_dir / f"{audio_path.stem}.srt"
                
                # 檢查是否已經處理過
                if txt_output_path.exists() and srt_output_path.exists():
                    logging.info(f"檔案 {audio_path.name} 已經處理過，跳過")
                    success_count += 1
                    continue
                
                # 進行轉錄
                full_text, srt_content = transcribe_audio(None, audio_path, output_dir)
                
                if full_text and srt_content:
                    # 保存純文字版本
                    txt_output_path.write_text(full_text, encoding='utf-8')
                    logging.info(f"純文字轉錄結果已保存至: {txt_output_path}")
                    
                    # 保存 SRT 格式版本
                    srt_output_path.write_text(srt_content, encoding='utf-8')
                    logging.info(f"SRT 格式轉錄結果已保存至: {srt_output_path}")
                    
                    success_count += 1
                else:
                    logging.error(f"處理 {audio_path.name} 失敗")
                
                logging.info(f"完成處理: {audio_path.name}\n")
                
            except Exception as e:
                logging.error(f"處理檔案 {audio_path.name} 時發生錯誤: {str(e)}")
                logging.error(f"錯誤追蹤:\n{traceback.format_exc()}")
                continue
        
        # 顯示處理結果統計
        logging.info("\n" + "="*50)
        logging.info(f"轉錄完成！成功處理 {success_count}/{len(audio_files)} 個檔案")
        logging.info(f"轉錄結果已保存至: {output_dir}")
        logging.info("="*50 + "\n")
    
    except Exception as e:
        logging.error(f"處理過程中發生錯誤: {str(e)}")
        logging.error(f"錯誤追蹤:\n{traceback.format_exc()}")
        raise

def main():
    """主函數"""
    print("開始執行語音轉錄程式...")
    print("=" * 50)
    
    # 設置目錄
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(current_dir, "訪談記錄")
    output_dir = os.path.join(current_dir, "轉錄結果")
    
    print(f"當前目錄: {current_dir}")
    print(f"輸入目錄: {input_dir}")
    print(f"輸出目錄: {output_dir}")
    print("=" * 50)
    
    # 創建輸出目錄
    os.makedirs(output_dir, exist_ok=True)
    print(f"已創建輸出目錄: {output_dir}")
    
    # 檢查系統資源
    system_info = check_gpu()
    
    # 選擇模型大小
    model_size = select_model_size(system_info)
    print(f"\n選擇使用模型: {model_size}")
    
    # 獲取所有音頻文件
    audio_files = []
    for ext in ['.wav', '.mp3', '.m4a']:
        audio_files.extend(list(Path(input_dir).glob(f'*{ext}')))
    
    if not audio_files:
        print("未找到任何音頻文件")
        return
    
    print(f"\n找到 {len(audio_files)} 個音頻文件")
    
    # 處理每個音頻文件
    success_count = 0
    for i, audio_file in enumerate(audio_files, 1):
        print("\n" + "-" * 50)
        print(f"處理第 {i}/{len(audio_files)} 個檔案: {audio_file.name}")
        print("-" * 50)
        
        print("開始轉錄...")
        audio_path = os.path.join(input_dir, audio_file)
        
        try:
            if transcribe_audio(None, audio_path, output_dir):
                success_count += 1
                print(f"處理 {audio_file.name} 成功")
            else:
                print(f"處理 {audio_file.name} 失敗")
        except Exception as e:
            print(f"轉錄過程中發生錯誤: {str(e)}")
            logging.error(f"轉錄過程中發生錯誤: {str(e)}")
            logging.error("錯誤追蹤:", exc_info=True)
            print("錯誤追蹤:")
            traceback.print_exc()
        
        print(f"完成處理: {audio_file.name}")
        print("-" * 50)
    
    # 輸出總結
    print("\n" + "=" * 50)
    print(f"轉錄完成！成功處理 {success_count}/{len(audio_files)} 個檔案")
    print(f"轉錄結果已保存至: {output_dir}")
    print("=" * 50)
    print("\n程式執行完成！")

if __name__ == "__main__":
    main() 