// 状态变量
let currentMode = 'text'; // text, file, url
let selectedFiles = [];
let currentTaskId = null;
let eventSource = null;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 设置拖拽上传
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-active'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-active'), false);
    });

    dropZone.addEventListener('drop', (e) => {
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });
});

// 切换输入 Tab
function switchTab(mode) {
    currentMode = mode;
    
    // 更新 Tab 样式
    const tabs = ['text', 'file', 'url'];
    tabs.forEach(t => {
        const btn = document.getElementById(`tab-${t}`);
        const content = document.getElementById(`content-${t}`);
        
        if (t === mode) {
            btn.className = "w-1/3 py-4 px-1 text-center border-b-2 font-medium text-sm border-blue-500 text-blue-600";
            content.classList.remove('hidden');
        } else {
            btn.className = "w-1/3 py-4 px-1 text-center border-b-2 font-medium text-sm border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300";
            content.classList.add('hidden');
        }
    });
}

// 处理文件选择
function handleFiles(files) {
    const fileList = document.getElementById('file-list');
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        // 简单校验
        if (!file.name.toLowerCase().endsWith('.pdf') && !file.name.toLowerCase().endsWith('.txt')) {
            alert(`不支持的文件格式: ${file.name}。仅支持 PDF 和 TXT`);
            continue;
        }
        
        if (file.size > 10 * 1024 * 1024) {
            alert(`文件过大: ${file.name}。最大支持 10MB`);
            continue;
        }
        
        selectedFiles.push(file);
        
        // 添加到界面
        const li = document.createElement('li');
        li.className = "flex items-center justify-between p-3 bg-white border rounded-md shadow-sm";
        li.innerHTML = `
            <div class="flex items-center">
                <svg class="w-5 h-5 text-gray-400 mr-2" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"></path></svg>
                <span class="text-sm font-medium text-gray-700 truncate max-w-xs">${file.name}</span>
                <span class="ml-2 text-xs text-gray-500">(${(file.size / 1024).toFixed(1)} KB)</span>
            </div>
            <button onclick="removeFile(${selectedFiles.length - 1}, this)" class="text-gray-400 hover:text-red-500">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>
        `;
        fileList.appendChild(li);
    }
}

// 移除文件
function removeFile(index, btnElement) {
    selectedFiles.splice(index, 1);
    btnElement.parentElement.remove();
}

// 开始分析
async function startAnalysis() {
    const btnStart = document.getElementById('btn-start');
    btnStart.disabled = true;
    btnStart.innerText = "正在提交...";
    
    try {
        // 1. 创建任务
        const createRes = await fetch('/api/tasks', { method: 'POST' });
        const createData = await createRes.json();
        currentTaskId = createData.task_id;
        
        // 2. 上传资料
        const formData = new FormData();
        
        if (currentMode === 'text') {
            const text = document.getElementById('text-input').value;
            if (!text.trim()) throw new Error("请输入政策文本");
            formData.append('text_content', text);
        } else if (currentMode === 'file') {
            if (selectedFiles.length === 0) throw new Error("请上传至少一个文件");
            selectedFiles.forEach(file => formData.append('files', file));
        } else if (currentMode === 'url') {
            const urls = document.getElementById('url-input').value;
            if (!urls.trim()) throw new Error("请输入有效的网页链接");
            formData.append('urls', urls);
        }
        
        await fetch(`/api/upload/${currentTaskId}`, {
            method: 'POST',
            body: formData
        });
        
        // 3. 启动分析
        const audience = document.getElementById('audience-select').value;
        await fetch(`/api/analyze/${currentTaskId}`, { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ audience: audience })
        });
        
        // 4. 切换到进度面板并连接 SSE
        document.getElementById('panel-input').classList.add('hidden');
        document.getElementById('panel-progress').classList.remove('hidden');
        
        // 更新顶部步骤
        document.getElementById('step-2').className = "flex items-center text-blue-600";
        document.getElementById('step-line-1').className = "w-16 h-1 bg-blue-600 mx-4";
        
        connectSSE(currentTaskId);
        
    } catch (err) {
        alert("提交失败: " + err.message);
        btnStart.disabled = false;
        btnStart.innerText = "开始智能分析";
    }
}

// 连接 Server-Sent Events 获取进度
function connectSSE(taskId) {
    if (eventSource) eventSource.close();
    
    eventSource = new EventSource(`/api/progress/${taskId}`);
    
    eventSource.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        updateProgressUI(data);
    });
    
    eventSource.addEventListener('completed', (e) => {
        const data = JSON.parse(e.data);
        updateProgressUI({ progress: 100, current_stage: "完成", message: "生成报告完毕" });
        showSuccess(data.result);
        eventSource.close();
    });
    
    eventSource.addEventListener('failed', (e) => {
        const data = JSON.parse(e.data);
        showError(data.error);
        eventSource.close();
    });
    
    eventSource.onerror = (err) => {
        console.error("SSE Error:", err);
        // 简单重连逻辑由浏览器自动处理，这里不强制 close
    };
}

// 更新进度 UI
function updateProgressUI(data) {
    const pct = data.progress || 0;
    
    document.getElementById('progress-bar').style.width = `${pct}%`;
    document.getElementById('progress-pct').innerText = `${pct}%`;
    document.getElementById('stage-badge').innerText = data.current_stage || "处理中";
    document.getElementById('progress-msg').innerText = data.message || "请稍候...";
    
    // 更新阶段状态追踪器
    updateTrackerUI(pct);
}

// 更新下方 5 个阶段的小图标
function updateTrackerUI(pct) {
    const stages = [
        { id: 1, maxPct: 15 }, // 材料理解
        { id: 2, maxPct: 40 }, // 深度分析
        { id: 3, maxPct: 60 }, // 风险情景
        { id: 4, maxPct: 80 }, // 商业影响
        { id: 5, maxPct: 95 }  // 生成报告
    ];
    
    for (const stage of stages) {
        const el = document.getElementById(`tracker-step-${stage.id}`);
        el.className = "text-center"; // reset
        
        if (pct >= stage.maxPct) {
            el.classList.add('tracker-done');
            el.querySelector('div').innerHTML = '✓';
        } else if (pct > (stage.id === 1 ? 0 : stages[stage.id-2].maxPct)) {
            el.classList.add('tracker-active');
            // 恢复 emoji（简单处理，实际应用中可以保存原始 HTML）
            const emojis = ['📄', '🔍', '⚠️', '💼', '📊'];
            el.querySelector('div').innerHTML = emojis[stage.id - 1];
        } else {
            const emojis = ['📄', '🔍', '⚠️', '💼', '📊'];
            el.querySelector('div').innerHTML = emojis[stage.id - 1];
        }
    }
}

// 显示成功面板
function showSuccess(result) {
    document.getElementById('panel-progress').classList.add('hidden');
    document.getElementById('panel-success').classList.remove('hidden');
    
    // 更新顶部步骤
    document.getElementById('step-3').className = "flex items-center text-blue-600";
    document.getElementById('step-line-2').className = "w-16 h-1 bg-blue-600 mx-4";
    
    if (result) {
        document.getElementById('success-title').innerText = result.title || "分析报告";
        document.getElementById('btn-view-report').href = result.report_url || "#";
        document.getElementById('btn-download-json').href = result.json_url || "#";
    }
}

// 显示错误面板
function showError(errorMsg) {
    document.getElementById('panel-progress').classList.add('hidden');
    document.getElementById('panel-error').classList.remove('hidden');
    
    const msg = typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg);
    document.getElementById('error-message').innerText = msg;
}

// 重置应用状态
function resetApp() {
    if (eventSource) eventSource.close();
    currentTaskId = null;
    selectedFiles = [];
    document.getElementById('file-list').innerHTML = '';
    
    const btnStart = document.getElementById('btn-start');
    btnStart.disabled = false;
    btnStart.innerText = "开始智能分析";
    
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-pct').innerText = '0%';
    
    // 恢复顶部步骤
    document.getElementById('step-2').className = "flex items-center text-gray-400";
    document.getElementById('step-line-1').className = "w-16 h-1 bg-gray-300 mx-4";
    document.getElementById('step-3').className = "flex items-center text-gray-400";
    document.getElementById('step-line-2').className = "w-16 h-1 bg-gray-300 mx-4";
    
    document.getElementById('panel-error').classList.add('hidden');
    document.getElementById('panel-success').classList.add('hidden');
    document.getElementById('panel-progress').classList.add('hidden');
    document.getElementById('panel-input').classList.remove('hidden');
}
