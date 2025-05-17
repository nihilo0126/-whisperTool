import os
import sys
import time
import json
import logging
import threading
import tempfile
from pathlib import Path
import shutil
from datetime import datetime
from flask import Flask, request, render_template, jsonify, flash, redirect, url_for, send_file, session
from flask_dropzone import Dropzone
from werkzeug.utils import secure_filename
import whisper
import torch
import subprocess

# 導入現有的功能
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from whisper_transcribe import check_gpu, select_model_size, format_timestamp

# 設置日誌
logging.basicConfig(
    level=logging.DEBUG,  # 改為 DEBUG 級別以獲取更多信息
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('web_app.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)  # 同時輸出到控制台
    ]
)

# 初始化 Flask 應用
app = Flask(__name__)
app.config.update(
    DROPZONE_UPLOAD_MULTIPLE=True,
    DROPZONE_PARALLEL_UPLOADS=3,
    DROPZONE_UPLOAD_ON_CLICK=True,
    DROPZONE_ALLOWED_FILE_CUSTOM=True,
    DROPZONE_ALLOWED_FILE_TYPE='.wav, .mp3, .m4a, .ogg',
    DROPZONE_MAX_FILE_SIZE=100,  # MB
    DROPZONE_MAX_FILES=10,
    SECRET_KEY=os.urandom(24),
    UPLOAD_FOLDER=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'),
    OUTPUT_FOLDER=os.path.join(os.path.dirname(os.path.abspath(__file__)), '轉錄結果'),
    MAX_CONTENT_LENGTH=100 * 1024 * 1024  # 100 MB
)

# 初始化 Dropzone
dropzone = Dropzone(app)

# 確保上傳和輸出目錄存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# 全局變量
tasks = {}  # 保存任務狀態的字典
loaded_model = None  # 全局模型變量
model_lock = threading.Lock()  # 模型載入鎖
gpu_info = None  # GPU 信息

# 獲取模型資料夾路徑
MODELS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
os.makedirs(MODELS_FOLDER, exist_ok=True)

# 在應用啟動時檢查 GPU - 使用 before_request 代替 before_first_request
@app.before_request
def check_resources():
    global gpu_info
    if gpu_info is None:
        gpu_info = check_gpu()

# 上下文處理器：添加當前年份到模板
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

def load_local_model(model_name, device="cuda"):
    """從本地加載模型"""
    model_path = os.path.join(MODELS_FOLDER, f"{model_name}.pt")
    if os.path.exists(model_path):
        logging.info(f"從本地加載模型: {model_path}")
        try:
            model = whisper.load_model(model_name, device=device)
            model.load_state_dict(torch.load(model_path))
            logging.info(f"本地模型 {model_name} 載入成功")
            return model
        except Exception as e:
            logging.error(f"載入本地模型失敗: {str(e)}")
            return None
    return None

def load_whisper_model(model_name, device="cuda"):
    """加載模型，優先使用本地模型"""
    # 嘗試從本地加載
    model = load_local_model(model_name, device)
    if model is not None:
        return model
    
    # 如果本地加載失敗，從網絡下載
    logging.info(f"本地未找到模型 {model_name}，從網絡下載...")
    model = whisper.load_model(model_name, device=device)
    
    # 保存到本地
    try:
        model_path = os.path.join(MODELS_FOLDER, f"{model_name}.pt")
        torch.save(model.state_dict(), model_path)
        logging.info(f"模型已保存到本地: {model_path}")
    except Exception as e:
        logging.warning(f"保存模型到本地時發生錯誤: {str(e)}")
    
    return model

# 轉錄文件函數
def transcribe_file(file_path, output_dir, model_name="small", task_id=None, use_gpu=True):
    """轉錄單個音頻文件的後台任務"""
    global loaded_model, tasks
    
    try:
        # 確保任務存在
        if task_id not in tasks:
            logging.error(f"找不到任務 {task_id}")
            return False
            
        # 更新任務狀態
        tasks[task_id]['status'] = 'processing'
        tasks[task_id]['progress'] = 10
        tasks[task_id]['message'] = f'準備使用 {model_name} 模型轉錄...'
        
        logging.info(f"開始轉錄文件: {os.path.basename(file_path)}, 使用模型: {model_name}")
        
        # 獲取檔案的絕對路徑
        audio_path = os.path.abspath(file_path)
        
        # 檢查檔案是否存在
        if not os.path.exists(audio_path):
            logging.error(f"找不到檔案: {audio_path}")
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['message'] = f'找不到檔案: {os.path.basename(audio_path)}'
            return False
        
        # 設置設備
        device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        logging.info(f"使用設備: {device} 處理文件 {os.path.basename(audio_path)}")
        
        tasks[task_id]['progress'] = 20
        tasks[task_id]['message'] = f'載入 {model_name} 模型中...'
        
        # 載入模型（使用模型鎖來確保線程安全）
        with model_lock:
            current_model = loaded_model['name'] if loaded_model else 'None'
            logging.info(f"當前已載入的模型: {current_model}")
            
            if loaded_model is None or loaded_model['name'] != model_name:
                logging.info(f"需要切換模型從 {current_model} 到 {model_name}")
                
                # 保存當前模型名稱
                target_model = model_name
                
                # 清理 GPU 記憶體
                if use_gpu and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logging.info("已清理 GPU 記憶體")
                
                # 載入新模型
                logging.info(f"開始載入 {target_model} 模型...")
                model = load_whisper_model(target_model, device=device)
                loaded_model = {'model': model, 'name': target_model}
                logging.info(f"模型 {target_model} 載入成功")
            else:
                model = loaded_model['model']
                logging.info(f"使用已載入的 {model_name} 模型")
        
        # 再次確認使用的模型是否正確
        if loaded_model['name'] != model_name:
            error_msg = f"模型載入錯誤！請求的模型是 {model_name}，但實際載入的是 {loaded_model['name']}"
            logging.error(error_msg)
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['message'] = error_msg
            return False
            
        tasks[task_id]['progress'] = 40
        tasks[task_id]['message'] = f'使用 {model_name} 模型開始轉錄...'
        
        # 設置轉錄選項
        transcribe_options = {
            "language": "zh",
            "task": "transcribe",
            "fp16": use_gpu and torch.cuda.is_available()
        }
        
        # 使用 autocast 進行混合精度計算
        with torch.amp.autocast('cuda') if use_gpu and torch.cuda.is_available() else torch.no_grad():
            logging.info(f"使用 {model_name} 模型開始轉錄檔案: {audio_path}")
            result = model.transcribe(audio_path, **transcribe_options)
        
        tasks[task_id]['progress'] = 80
        tasks[task_id]['message'] = '轉錄完成，保存結果...'
        
        # 生成輸出文件名
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        txt_output_file = os.path.join(output_dir, f"{base_name}.txt")
        srt_output_file = os.path.join(output_dir, f"{base_name}.srt")
        
        # 保存純文本結果
        full_text = ""
        with open(txt_output_file, "w", encoding="utf-8") as f:
            # 在文件開頭添加使用的模型信息
            f.write(f"# 使用模型: {model_name}\n\n")
            for segment in result["segments"]:
                text = segment["text"].strip()
                full_text += text + "\n"
                f.write(text + "\n")
        
        # 保存 SRT 格式
        with open(srt_output_file, "w", encoding="utf-8") as f:
            # 在文件開頭添加使用的模型信息
            f.write(f"1\n00:00:00,000 --> 00:00:01,000\n使用模型: {model_name}\n\n")
            offset = 2
            for i, segment in enumerate(result["segments"], offset):
                start_time = format_timestamp(segment["start"]).replace(".", ",")
                end_time = format_timestamp(segment["end"]).replace(".", ",")
                text = segment["text"].strip()
                
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n\n")
        
        logging.info(f"使用 {model_name} 模型轉錄完成：{txt_output_file} 和 {srt_output_file}")
        
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['progress'] = 100
        tasks[task_id]['message'] = f'使用 {model_name} 模型轉錄完成！'
        tasks[task_id]['output_files'] = {
            'txt': os.path.basename(txt_output_file),
            'srt': os.path.basename(srt_output_file)
        }
        
        return True
        
    except Exception as e:
        logging.error(f"轉錄音頻時發生錯誤: {str(e)}", exc_info=True)
        
        if task_id in tasks:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['message'] = f'轉錄過程中發生錯誤: {str(e)}'
        
        return False

# 首頁路由
@app.route('/')
def index():
    # 獲取可用模型
    models = ["tiny", "base", "small", "medium", "large-v3"]
    
    # 獲取系統資訊
    system_info = check_gpu()
    
    # 建議的模型
    suggested_model = select_model_size(system_info)
    
    # 獲取歷史記錄
    history_files = []
    output_dir = app.config['OUTPUT_FOLDER']
    if os.path.exists(output_dir):
        for file in os.listdir(output_dir):
            if file.endswith('.txt') or file.endswith('.srt'):
                file_path = os.path.join(output_dir, file)
                file_stat = os.stat(file_path)
                history_files.append({
                    'name': file,
                    'path': file_path,
                    'size': file_stat.st_size / 1024,  # KB
                    'modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
    
    # 按修改時間排序
    history_files.sort(key=lambda x: x['modified'], reverse=True)
    
    return render_template('index.html', 
                           models=models, 
                           suggested_model=suggested_model,
                           tasks=tasks,
                           history=history_files,
                           system_info=system_info,
                           torch=torch)

# 上傳文件路由
@app.route('/upload', methods=['POST'])
def upload():
    global loaded_model, tasks
    
    if 'file' not in request.files:
        return jsonify({'error': '沒有文件被上傳'}), 400
    
    file = request.files['file']
    # 使用當前已載入的模型作為預設值
    current_model = loaded_model['name'] if loaded_model else 'small'
    model_name = request.form.get('model', current_model)
    use_gpu = request.form.get('use_gpu', 'true').lower() == 'true'
    force_model = request.form.get('force_model', 'false').lower() == 'true'
    
    # 記錄收到的請求信息
    logging.info(f"收到上傳請求，選擇的模型: {model_name}，使用GPU: {use_gpu}，強制使用模型: {force_model}")
    
    # 確認當前加載的模型
    device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
    
    # 生成任務ID並創建任務
    timestamp = int(time.time())
    filename = secure_filename(file.filename)
    base_name = os.path.splitext(filename)[0]
    task_id = f"task_{timestamp}_{base_name}"
    
    logging.info(f"創建新任務 {task_id}，使用模型: {model_name}")
    
    # 創建任務記錄
    tasks[task_id] = {
        'id': task_id,
        'filename': filename,
        'status': 'queued',
        'progress': 0,
        'message': '等待處理...',
        'model': model_name,
        'use_gpu': use_gpu,
        'start_time': time.time()
    }
    
    # 保存上傳的文件
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(upload_path)
    
    # 在新線程中處理轉錄
    thread = threading.Thread(
        target=transcribe_file,
        args=(upload_path, app.config['OUTPUT_FOLDER'], model_name, task_id, use_gpu)
    )
    thread.start()
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '文件上傳成功，開始處理'
    })

# 獲取任務狀態
@app.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id):
    if task_id not in tasks:
        return jsonify({'error': '找不到任務'}), 404
    
    task = tasks[task_id]
    # 計算運行時間
    if task['status'] != 'completed' and task['status'] != 'error':
        task['run_time'] = int(time.time() - task['start_time'])
    
    return jsonify(task)

# 獲取所有任務狀態
@app.route('/tasks', methods=['GET'])
def get_all_tasks():
    return jsonify(tasks)

# 下載文件
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename),
                     as_attachment=True)

# 批量處理路由
@app.route('/batch', methods=['POST'])
def batch_process():
    files = request.json.get('files', [])
    model_name = request.json.get('model', 'small')
    use_gpu = request.json.get('use_gpu', True)
    
    if not files:
        return jsonify({'error': '沒有選擇文件'}), 400
    
    # 創建批處理任務
    batch_id = f"batch_{int(time.time())}"
    tasks[batch_id] = {
        'id': batch_id,
        'status': 'processing',
        'progress': 0,
        'message': '開始批量處理',
        'subtasks': [],
        'start_time': time.time()
    }
    
    # 創建並啟動子任務
    for file in files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file))
        if os.path.exists(file_path):
            task_id = f"task_{int(time.time())}_{os.path.splitext(file)[0]}"
            tasks[task_id] = {
                'id': task_id,
                'filename': file,
                'status': 'queued',
                'progress': 0,
                'message': '排隊中...',
                'model': model_name,
                'use_gpu': use_gpu,
                'start_time': time.time(),
                'batch_id': batch_id
            }
            tasks[batch_id]['subtasks'].append(task_id)
            
            # 啟動轉錄線程
            thread = threading.Thread(
                target=transcribe_file,
                args=(file_path, app.config['OUTPUT_FOLDER'], model_name, task_id, use_gpu)
            )
            thread.daemon = True
            thread.start()
    
    return jsonify({
        'batch_id': batch_id,
        'message': f'已開始處理 {len(tasks[batch_id]["subtasks"])} 個文件'
    })

# 獲取系統信息
@app.route('/system-info', methods=['GET'])
def get_system_info():
    system_info = check_gpu()
    return jsonify(system_info)

# 處理 "訪談記錄" 資料夾中的文件
@app.route('/process-interview', methods=['POST'])
def process_interview():
    current_model = loaded_model['name'] if loaded_model else 'small'
    model_name = request.form.get('model', current_model)
    use_gpu = request.form.get('use_gpu', 'true').lower() == 'true'
    
    # 獲取訪談記錄資料夾路徑
    interview_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "訪談記錄")
    if not os.path.exists(interview_dir):
        return jsonify({'error': '找不到訪談記錄資料夾'}), 404
    
    # 獲取所有音頻文件
    audio_files = []
    for ext in ['.wav', '.mp3', '.m4a', '.ogg']:
        audio_files.extend([f for f in os.listdir(interview_dir) if f.lower().endswith(ext)])
    
    if not audio_files:
        return jsonify({'error': '找不到任何音頻文件'}), 404
    
    # 創建批處理任務
    batch_id = f"interview_batch_{int(time.time())}"
    tasks[batch_id] = {
        'id': batch_id,
        'status': 'processing',
        'progress': 0,
        'message': '開始處理訪談記錄',
        'subtasks': [],
        'start_time': time.time()
    }
    
    # 創建並啟動子任務
    for file in audio_files:
        file_path = os.path.join(interview_dir, file)
        if os.path.exists(file_path):
            task_id = f"task_{int(time.time())}_{os.path.splitext(file)[0]}"
            tasks[task_id] = {
                'id': task_id,
                'filename': file,
                'status': 'queued',
                'progress': 0,
                'message': '排隊中...',
                'model': model_name,
                'use_gpu': use_gpu,
                'start_time': time.time(),
                'batch_id': batch_id
            }
            tasks[batch_id]['subtasks'].append(task_id)
            
            # 啟動轉錄線程
            thread = threading.Thread(
                target=transcribe_file,
                args=(file_path, app.config['OUTPUT_FOLDER'], model_name, task_id, use_gpu)
            )
            thread.daemon = True
            thread.start()
    
    return jsonify({
        'batch_id': batch_id,
        'message': f'已開始處理 {len(tasks[batch_id]["subtasks"])} 個訪談文件'
    })

# 清理過期任務
@app.route('/clean-tasks', methods=['POST'])
def clean_tasks():
    global tasks
    current_time = time.time()
    
    # 保留的任務
    active_tasks = {}
    
    # 清理24小時前的任務
    for task_id, task in tasks.items():
        if current_time - task.get('start_time', 0) < 86400:  # 24小時 = 86400秒
            active_tasks[task_id] = task
    
    # 更新任務列表
    tasks = active_tasks
    
    return jsonify({'message': f'清理完成，保留 {len(tasks)} 個任務'})

# 獲取模型資料夾路徑
MODELS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
os.makedirs(MODELS_FOLDER, exist_ok=True)

@app.route('/open_models_folder', methods=['POST'])
def open_models_folder():
    try:
        if os.name == 'nt':  # Windows
            os.startfile(MODELS_FOLDER)
        elif os.name == 'posix':  # macOS 和 Linux
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['open', MODELS_FOLDER])
            else:  # Linux
                subprocess.run(['xdg-open', MODELS_FOLDER])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add_model', methods=['POST'])
def add_model():
    if 'model_file' not in request.files:
        flash('沒有選擇文件', 'danger')
        return redirect(url_for('index'))
    
    file = request.files['model_file']
    model_name = request.form.get('model_name')
    model_type = request.form.get('model_type')
    
    if file.filename == '':
        flash('沒有選擇文件', 'danger')
        return redirect(url_for('index'))
    
    if not model_name:
        flash('請輸入模型名稱', 'danger')
        return redirect(url_for('index'))
    
    # 檢查文件擴展名
    allowed_extensions = {'.pt', '.bin'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        flash('不支援的文件格式', 'danger')
        return redirect(url_for('index'))
    
    # 安全地保存文件
    filename = secure_filename(f"{model_name}{file_ext}")
    file_path = os.path.join(MODELS_FOLDER, filename)
    
    try:
        file.save(file_path)
        flash('模型添加成功', 'success')
    except Exception as e:
        flash(f'保存文件時發生錯誤: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/update_model', methods=['POST'])
def update_model():
    logging.info("收到更新模型請求")
    try:
        data = request.get_json()
        logging.info(f"請求數據: {data}")
        
        model_name = data.get('model')
        force_update = data.get('force', False)
        manual_update = data.get('manual', False)
        verify_only = data.get('verify', False)
        logging.info(f"要更新的模型名稱: {model_name}, 強制更新: {force_update}, 手動更新: {manual_update}, 僅驗證: {verify_only}")
        
        if not model_name:
            error_msg = "未提供模型名稱"
            logging.error(error_msg)
            return jsonify({"success": False, "message": error_msg}), 400
        
        global loaded_model
        with model_lock:
            current_model = loaded_model['name'] if loaded_model else 'None'
            logging.info(f"當前已載入的模型: {current_model}")
            
            if verify_only:
                return jsonify({
                    "success": True,
                    "current_model": current_model,
                    "expected_model": model_name,
                    "matches": current_model == model_name
                })
            
            if loaded_model is None or loaded_model['name'] != model_name or force_update:
                # 清理 GPU 記憶體
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logging.info("已清理 GPU 記憶體")
                
                # 載入新模型
                logging.info(f"開始載入 {model_name} 模型...")
                try:
                    # 先清除已加載的模型
                    if loaded_model is not None:
                        logging.info(f"釋放之前載入的模型 {loaded_model['name']}")
                        del loaded_model['model']
                        loaded_model = None
                        torch.cuda.empty_cache()
                        
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                    logging.info(f"使用設備: {device}")
                    
                    # 使用新的加載函數
                    model = load_whisper_model(model_name, device=device)
                    loaded_model = {'model': model, 'name': model_name}
                    logging.info(f"模型 {model_name} 載入成功")
                    
                    # 驗證模型是否正確載入
                    if loaded_model['name'] != model_name:
                        error_msg = f"模型載入驗證失敗：請求 {model_name}，但載入了 {loaded_model['name']}"
                        logging.error(error_msg)
                        return jsonify({"success": False, "message": error_msg}), 500
                    
                    return jsonify({
                        "success": True,
                        "message": f"模型 {model_name} 已成功更新",
                        "previous_model": current_model,
                        "current_model": model_name
                    })
                except Exception as e:
                    error_msg = f"載入模型 {model_name} 時發生錯誤: {str(e)}"
                    logging.error(error_msg, exc_info=True)
                    return jsonify({"success": False, "message": error_msg}), 500
            else:
                msg = f"模型 {model_name} 已經載入，無需更新"
                logging.info(msg)
                return jsonify({
                    "success": True,
                    "message": msg,
                    "current_model": model_name
                })
    except Exception as e:
        error_msg = f"處理更新模型請求時發生錯誤: {str(e)}"
        logging.error(error_msg, exc_info=True)
        return jsonify({"success": False, "message": error_msg}), 500

# 啟動服務器
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(debug=True, host='0.0.0.0', port=port) 