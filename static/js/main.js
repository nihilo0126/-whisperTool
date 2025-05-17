// 全局變量
let dropzone;
let uploadedFiles = [];
let currentTasks = {};
let taskCheckInterval;

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    checkExistingTasks();
    setCurrentTime();
    
    // 獲取已存在的 Dropzone 實例
    const dropzoneElement = document.querySelector('#audioDropzone');
    if (dropzoneElement) {
        dropzone = Dropzone.instances[0]; // 獲取 Flask-Dropzone 創建的實例
        if (dropzone) {
            console.log("使用已存在的 Dropzone 實例");
            configureDropzone(dropzone);
        } else {
            console.log("找不到現有的 Dropzone 實例，創建新實例");
            initializeDropzone();
        }
    }
});

// 初始化 Dropzone
function initializeDropzone() {
    Dropzone.autoDiscover = false;
    
    dropzone = new Dropzone("#audioDropzone", {
        url: "/upload",
        paramName: "file",
        maxFiles: 10,
        maxFilesize: 100, // MB
        acceptedFiles: ".wav,.mp3,.m4a,.ogg",
        addRemoveLinks: true,
        autoProcessQueue: false, // 不自動上傳
        parallelUploads: 1, // 一次處理一個文件
        dictDefaultMessage: "拖放音頻文件到這裡上傳",
        dictFallbackMessage: "您的瀏覽器不支持拖放上傳。",
        dictFallbackText: "請使用下面的備用表單上傳您的文件。",
        dictFileTooBig: "文件太大 ({{filesize}}MB)。最大文件大小: {{maxFilesize}}MB。",
        dictInvalidFileType: "您無法上傳此類型的文件。",
        dictResponseError: "服務器返回 {{statusCode}} 代碼。",
        dictCancelUpload: "取消上傳",
        dictCancelUploadConfirmation: "您確定要取消此上傳嗎？",
        dictRemoveFile: "移除文件",
        dictMaxFilesExceeded: "您無法上傳更多文件。",
        clickable: true,
        // 新增：初始化時禁用Dropzone，等模型切換完成再啟用
        init: function() {
            this.disable();
        }
    });
    
    configureDropzone(dropzone);
}

// 配置 Dropzone 事件處理
function configureDropzone(dz) {
    // 當文件被添加時
    dz.on("addedfile", function(file) {
        uploadedFiles.push(file.name);
        updateBatchButton();
    });
    
    // 當文件被移除時
    dz.on("removedfile", function(file) {
        const index = uploadedFiles.indexOf(file.name);
        if (index > -1) {
            uploadedFiles.splice(index, 1);
        }
        updateBatchButton();
    });
    
    // 發送其他參數
    dz.on("sending", async function(file, xhr, formData) {
        const modelSelect = document.getElementById("modelSelect");
        const modelName = modelSelect.value;
        const useGPU = document.getElementById("useGPU").checked;
        
        console.log("Dropzone sending, modelName:", modelName);
        // 添加時間戳以避免緩存
        formData.append("model", modelName);
        formData.append("use_gpu", useGPU);
        formData.append("timestamp", new Date().getTime());
        formData.append("force_model", "true");  // 強制使用選定的模型
        
        // 驗證當前模型
        try {
            const verifyResponse = await fetch('/update_model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    model: modelName,
                    timestamp: new Date().getTime(),
                    verify: true
                }),
            });
            
            const verifyData = await verifyResponse.json();
            if (!verifyData.success || verifyData.current_model !== modelName) {
                throw new Error(`模型驗證失敗：期望 ${modelName}，實際 ${verifyData.current_model}`);
            }
            
            console.log("模型驗證成功:", verifyData);
        } catch (error) {
            console.error("模型驗證失敗:", error);
            const modelStatus = document.getElementById('modelStatus');
            if (modelStatus) {
                modelStatus.innerHTML = `<div class=\"alert alert-danger\">模型驗證失敗: ${error.message}</div>`;
            }
            xhr.abort();
            throw error;
        }
    });
    
    // 上傳完成時
    dz.on("success", function(file, response) {
        console.log("文件上傳成功:", response);
        const taskId = response.task_id;
        if (taskId) {
            currentTasks[taskId] = {
                id: taskId,
                filename: file.name,
                status: 'queued'
            };
            startTaskStatusChecking();
            showTasksContainer();
            renderTasks();
        }
    });
    
    // 上傳失敗時
    dz.on("error", function(file, message) {
        console.error("上傳錯誤:", message);
        showToast("錯誤", `上傳失敗: ${message}`, "error");
    });
    
    // 上傳完成後清空隊列
    dz.on("queuecomplete", function() {
        console.log("所有文件上傳完成");
    });
}

// 設置事件監聽器
function setupEventListeners() {
    // 選擇模型下拉選單
    const modelSelect = document.getElementById('modelSelect');
    if (modelSelect) {
        console.log("找到模型選擇元素:", modelSelect);
        console.log("當前選擇的模型:", modelSelect.value);
        
        modelSelect.addEventListener('change', async function() {
            const selectedModel = this.value;
            const modelStatus = document.getElementById('modelStatus');
            if (dropzone) dropzone.disable(); // 切換時禁用Dropzone
            modelStatus.innerHTML = `<div class=\"alert alert-info\">正在切換到模型: ${selectedModel}，請等待...</div>`;
            try {
                const response = await fetch('/update_model', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ 
                        model: selectedModel,
                        timestamp: new Date().getTime(),
                        force: true,
                        manual: true
                    }),
                });
                const data = await response.json();
                if (data.success) {
                    modelStatus.innerHTML = `<div class=\"alert alert-success\">模型已成功切換到: ${selectedModel}</div>`;
                    if (dropzone) dropzone.enable(); // 切換完成再啟用Dropzone
                } else {
                    throw new Error(data.message || "模型更新失敗");
                }
            } catch (error) {
                modelStatus.innerHTML = `<div class=\"alert alert-danger\">更新模型失敗: ${error.message}</div>`;
            }
        });
    } else {
        console.error("找不到模型選擇元素!");
        alert("錯誤: 找不到模型選擇元素!");
    }
    
    // 批量處理按鈕
    const batchButton = document.getElementById('startBatchBtn');
    batchButton.addEventListener('click', function() {
        // 移除功能，按鈕不再觸發任何處理
        console.log("按鈕被點擊，但功能已被移除");
    });
    
    // 定期更新任務狀態
    if (!taskCheckInterval) {
        taskCheckInterval = setInterval(updateTasksStatus, 2000);
    }

    // 更新模型按鈕
    const updateModelBtn = document.getElementById('updateModelBtn');
    if (updateModelBtn) {
        console.log("找到更新模型按鈕:", updateModelBtn);
        
        updateModelBtn.addEventListener('click', function() {
            const selectedModel = document.getElementById('modelSelect').value;
            console.log("點擊更新模型按鈕");
            console.log("選擇的模型:", selectedModel);
            
            // 顯示狀態
            const modelStatus = document.getElementById('modelStatus');
            if (modelStatus) {
                modelStatus.innerHTML = `<div class="alert alert-info">正在切換到模型: ${selectedModel}...</div>`;
            }
            
            // 發送請求到後端以更新模型
            fetch('/update_model', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    model: selectedModel,
                    timestamp: new Date().getTime(),
                    manual: true,
                    force: true // 強制更新
                }),
            })
            .then(response => {
                console.log("收到響應:", response);
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("響應數據:", data);
                if (modelStatus) {
                    if (data.success) {
                        console.log("模型更新成功:", data.message);
                        modelStatus.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
                    } else {
                        console.error("模型更新失敗:", data.message);
                        modelStatus.innerHTML = `<div class="alert alert-danger">${data.message}</div>`;
                    }
                }
            })
            .catch(error => {
                console.error("更新模型時發生錯誤:", error);
                if (modelStatus) {
                    modelStatus.innerHTML = `<div class="alert alert-danger">更新模型時發生錯誤: ${error.message}</div>`;
                }
            });
        });
    } else {
        console.error("找不到更新模型按鈕!");
    }
}

// 更新批量處理按鈕狀態
function updateBatchButton() {
    const batchButton = document.getElementById('startBatchBtn');
    if (uploadedFiles.length > 0) {
        batchButton.disabled = false;
    } else {
        batchButton.disabled = true;
    }
}

// 處理批量上傳
function processBatch() {
    if (uploadedFiles.length === 0) {
        showToast("警告", "請先上傳文件", "warning");
        return;
    }
    
    const modelName = document.getElementById("modelSelect").value;
    const useGPU = document.getElementById("useGPU").checked;
    
    // 開始處理上傳隊列
    dropzone.processQueue();
}

// 檢查現有任務
function checkExistingTasks() {
    fetch('/tasks')
        .then(response => response.json())
        .then(data => {
            currentTasks = data;
            if (Object.keys(currentTasks).length > 0) {
                showTasksContainer();
                renderTasks();
                startTaskStatusChecking();
            }
        })
        .catch(error => {
            console.error("獲取任務列表錯誤:", error);
        });
}

// 開始任務狀態檢查
function startTaskStatusChecking() {
    if (!taskCheckInterval) {
        taskCheckInterval = setInterval(updateTasksStatus, 2000);
    }
}

// 更新任務狀態
function updateTasksStatus() {
    if (Object.keys(currentTasks).length === 0) {
        if (taskCheckInterval) {
            clearInterval(taskCheckInterval);
            taskCheckInterval = null;
        }
        return;
    }
    
    fetch('/tasks')
        .then(response => response.json())
        .then(data => {
            currentTasks = data;
            renderTasks();
            
            // 檢查是否所有任務都已完成
            const allCompleted = Object.values(currentTasks).every(task => 
                task.status === 'completed' || task.status === 'error'
            );
            
            if (allCompleted && Object.keys(currentTasks).length > 0) {
                showToast("成功", "所有任務已完成", "success");
            }
        })
        .catch(error => {
            console.error("獲取任務列表錯誤:", error);
        });
}

// 顯示任務容器
function showTasksContainer() {
    document.getElementById('tasksContainer').style.display = 'block';
}

// 渲染任務列表
function renderTasks() {
    const tasksContent = document.getElementById('tasksContent');
    tasksContent.innerHTML = '';
    
    Object.values(currentTasks).forEach(task => {
        // 排除批量任務，只顯示單獨的任務
        if (task.id.startsWith('batch_')) {
            return;
        }
        
        // 創建任務卡片
        const taskCard = document.createElement('div');
        taskCard.className = `col-md-6 col-lg-4 task-card task-status-${task.status}`;
        
        let statusText = '';
        let statusBadgeClass = '';
        
        switch (task.status) {
            case 'completed':
                statusText = '已完成';
                statusBadgeClass = 'bg-success';
                break;
            case 'processing':
                statusText = '處理中';
                statusBadgeClass = 'bg-primary';
                break;
            case 'error':
                statusText = '錯誤';
                statusBadgeClass = 'bg-danger';
                break;
            case 'queued':
                statusText = '排隊中';
                statusBadgeClass = 'bg-warning';
                break;
            default:
                statusText = task.status;
                statusBadgeClass = 'bg-secondary';
        }
        
        // 組裝卡片內容
        let cardBody = `
            <div class="card h-100">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <span>${task.filename || '未知文件'}</span>
                    <span class="badge ${statusBadgeClass}">${statusText}</span>
                </div>
                <div class="card-body">
                    <p class="card-text">${task.message || '處理中...'}</p>
                    <div class="progress mb-3">
                        <div class="progress-bar" role="progressbar" style="width: ${task.progress || 0}%" 
                             aria-valuenow="${task.progress || 0}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <small class="text-muted">模型: ${task.model || 'small'}</small>
        `;
        
        // 添加下載按鈕（如果任務已完成）
        if (task.status === 'completed' && task.output_files) {
            cardBody += `
                        <div>
                            <a href="/download/${task.output_files.txt}" class="btn btn-sm btn-outline-primary">
                                <i class="fas fa-file-alt me-1"></i>TXT
                            </a>
                            <a href="/download/${task.output_files.srt}" class="btn btn-sm btn-outline-info">
                                <i class="fas fa-closed-captioning me-1"></i>SRT
                            </a>
                        </div>
            `;
        }
        
        cardBody += `
                    </div>
                </div>
            </div>
        `;
        
        taskCard.innerHTML = cardBody;
        tasksContent.appendChild(taskCard);
    });
    
    // 如果沒有任務，顯示一條消息
    if (tasksContent.children.length === 0) {
        tasksContent.innerHTML = '<p class="col-12 text-center text-muted my-4">沒有正在進行的任務</p>';
    }
}

// 顯示提示消息
function showToast(title, message, type = "info") {
    // 使用Bootstrap的toast功能，或者可以自行實現
    console.log(`[${type.toUpperCase()}] ${title}: ${message}`);
}

// 設置當前時間（用於頁腳的年份顯示）
function setCurrentTime() {
    window.now = {
        year: new Date().getFullYear()
    };
} 