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

class AnalyzeRequest(BaseModel):
    audience: str = "通用视角"

from config import FRONTEND_DIR, OUTPUT_DIR, UPLOAD_DIR
from core.content_extractor import extract_content
from core.policy_analyzer import analyze_policy
from reports.html_report import generate_html_report
from task_store import task_store

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
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
        
        # 1. 提取所有内容并合并
        all_content = []
        
        # 处理文件
        for file_info in task.get("files", []):
            task_store.update(task_id, current_stage="提取文件内容", message=f"正在读取 {file_info['filename']}")
            text = await extract_content(file_path=file_info["path"])
            if text:
                all_content.append(text)
                
        # 处理 URL
        for url in task.get("urls", []):
            task_store.update(task_id, current_stage="提取网页内容", message=f"正在抓取 {url}")
            text = await extract_content(url=url)
            if text:
                all_content.append(text)
                
        merged_content = "\n\n---\n\n".join(all_content)
        
        if not merged_content.strip():
            raise ValueError("未能提取到任何有效的文本内容")
            
        # 2. 执行分析
        def progress_callback(stage, progress, message):
            task_store.update(task_id, current_stage=stage, progress=progress, message=message)
            
        audience = task.get("audience", "通用视角")
        result = await analyze_policy(merged_content, progress_callback, audience=audience)
        
        # 3. 生成 HTML 报告
        task_store.update(task_id, current_stage="生成报告", progress=90, message="正在生成可视化报告...")
        
        report_filename = f"report_{task_id}.html"
        report_path = OUTPUT_DIR / task_id / report_filename
        generate_html_report(result, report_path)
        
        # 保存 JSON 结果
        json_path = OUTPUT_DIR / task_id / f"result_{task_id}.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        # 4. 更新完成状态
        task_store.update(
            task_id, 
            status="completed", 
            progress=100, 
            current_stage="完成", 
            message="分析全部完成",
            result={
                "report_url": f"/outputs/{task_id}/{report_filename}",
                "json_url": f"/outputs/{task_id}/result_{task_id}.json",
                "title": result.get("title", "")
            }
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
    task_store.update(task_id, audience=audience)
        
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
