import os
import sys
import torch
import whisper
from tqdm import tqdm

def download_models():
    # 確保模型目錄存在
    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    # 要下載的模型列表
    model_names = ["tiny", "base", "small", "medium", "large-v3"]
    
    print("開始下載 Whisper 模型...")
    print(f"模型將被保存在: {models_dir}")
    print("=" * 50)
    
    for model_name in model_names:
        print(f"\n下載模型: {model_name}")
        try:
            # 下載並載入模型
            model = whisper.load_model(model_name)
            
            # 獲取模型文件路徑
            model_path = os.path.join(models_dir, f"{model_name}.pt")
            
            # 保存模型
            torch.save(model.state_dict(), model_path)
            print(f"模型 {model_name} 已保存到: {model_path}")
            
            # 清理 GPU 記憶體
            del model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
        except Exception as e:
            print(f"下載模型 {model_name} 時發生錯誤: {str(e)}")
            continue
    
    print("\n" + "=" * 50)
    print("所有模型下載完成！")
    print(f"模型文件位置: {models_dir}")

if __name__ == "__main__":
    download_models() 