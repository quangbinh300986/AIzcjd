import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

class AnalyzeRequest(BaseModel):
    audience: str = "通用视角"

from config import FRONTEND_DIR, OUTPUT_DIR, UPLOAD_DIR
from api.services.task_runner import TaskRunner
from task_store import task_store

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app_error.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# 创建应用
app = FastAPI(title="AI 政策解读程序", version="1.0.0")

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态目录
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/")
async def root():
    """访问根目录时重定向到前端页面"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/frontend/index.html")


@app.post("/api/tasks")
async def create_task():
    """创建新任务"""
    task_id = str(uuid.uuid4())[:8]
    task_store.create(task_id)
    return {"task_id": task_id, "message": "任务创建成功"}


@app.post("/api/upload/{task_id}")
async def upload_content(
    task_id: str,
    files: List[UploadFile] = File(default=[]),
    urls: str = Form(default=""),
    text_content: str = Form(default=""),
):
    """上传需要分析的内容"""
    if not task_store.contains(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")

    task_dir = UPLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    uploaded_files = []
    
    # 1. 处理文件上传
    for file in files:
        if not file.filename:
            continue
            
        file_path = task_dir / file.filename
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        uploaded_files.append({
            "filename": file.filename,
            "type": "pdf" if file.filename.lower().endswith(".pdf") else "text",
            "path": str(file_path)
        })
        
    # 2. 处理 URL
    url_list = [u.strip() for u in urls.split("\n") if u.strip()]
    
    # 3. 处理纯文本
    if text_content.strip():
        text_path = task_dir / "pasted_text.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text_content)
        uploaded_files.append({
            "filename": "粘贴的文本.txt",
            "type": "text",
            "path": str(text_path)
        })
        
    # 更新任务存储
    task_store.append_files(task_id, uploaded_files)
    task_store.append_urls(task_id, url_list)
    
    return {"task_id": task_id, "files": uploaded_files, "urls": url_list}


async def run_analysis_pipeline(task_id: str):
    """后台运行分析流水线"""
    try:
        task = task_store.get(task_id)
        if not task:
            return
            
        task_store.update(task_id, status="running", progress=0, current_stage="准备中")
        
        # 将 audience 映射给 user_focus
        task_data = task.copy()
        if "audience" in task_data:
            task_data["user_focus"] = task_data["audience"]
            
        runner = TaskRunner(task_id, task_data, OUTPUT_DIR / task_id)
        
        def progress_callback(stage, progress, message):
            task_store.update(task_id, current_stage=stage, progress=progress, message=message)
            
        await runner.run(on_progress=progress_callback)
        
        # 兼容旧版前端字段结构
        runner_result = runner.get_result()
        if runner_result.get("success"):
            outputs = runner_result.get("outputs", {})
            result_payload = {
                "report_url": outputs.get("html", {}).get("url", ""),
                "json_url": outputs.get("analysis_json", {}).get("url", ""),
                "pdf_url": outputs.get("pdf", {}).get("url", ""),
                "title": runner_result.get("summary", {}).get("title", ""),
                "summary": runner_result.get("summary", {})
            }
        else:
            result_payload = runner_result
            
        task_store.update(
            task_id, 
            status="completed", 
            progress=100, 
            current_stage="完成", 
            message="分析全部完成",
            result=result_payload
        )
        
    except Exception as e:
        logger.exception(f"任务 {task_id} 分析失败")
        task_store.update(task_id, status="failed", current_stage="失败", message=str(e), error=str(e))


@app.post("/api/analyze/{task_id}")
async def start_analysis(task_id: str, background_tasks: BackgroundTasks, request: Optional[AnalyzeRequest] = None):
    """启动后台分析任务"""
    if not task_store.contains(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
        
    task = task_store.get(task_id)
    if task["status"] == "running":
        raise HTTPException(status_code=400, detail="任务正在运行中")
        
    audience = request.audience if request else "通用视角"
    task_store.update(task_id, audience=audience, status="running", progress=0, 
                      current_stage="准备中", message="正在启动分析...", error="", result=None)
        
    background_tasks.add_task(run_analysis_pipeline, task_id)
    return {"task_id": task_id, "message": "已启动分析流水线"}


@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    """SSE 端点，推送实时进度"""
    if not task_store.contains(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
        
    async def event_generator():
        last_progress = -1
        last_stage = ""
        
        while True:
            task = task_store.get(task_id)
            if not task:
                break
                
            if task["progress"] != last_progress or task["current_stage"] != last_stage:
                last_progress = task["progress"]
                last_stage = task["current_stage"]
                
                data = {
                    "task_id": task_id,
                    "status": task["status"],
                    "progress": task["progress"],
                    "current_stage": task["current_stage"],
                    "message": task.get("message", ""),
                }
                yield f"event: progress\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                
            if task["status"] in ("completed", "failed"):
                result_data = {
                    "status": task["status"],
                    "result": task.get("result"),
                    "error": task.get("error"),
                }
                yield f"event: {task['status']}\ndata: {json.dumps(result_data, ensure_ascii=False)}\n\n"
                break
                
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("app:app", host=HOST, port=PORT, reload=True)
# Trigger reload
# Trigger reload 2
