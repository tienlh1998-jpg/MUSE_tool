import os
import subprocess
import zipfile
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from core.config import load_config, save_config, AppConfig, DOWNLOADS_DIR
from core.account_manager import account_manager
from core.mv_director import generate_mv_plan, extract_shots_from_script
from core.task_manager import task_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background workers
    cfg = load_config()
    await task_manager.start_workers(cfg)
    yield
    # Shutdown logic if any
    task_manager._running = False

app = FastAPI(title="MUSE Multi-Account AI Studio", version="2.0.0", lifespan=lifespan)

# Mount downloads directory
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

# ==================== CONFIG ENDPOINTS ====================

@app.get("/api/config")
def get_config():
    return load_config().model_dump()

@app.post("/api/config")
def update_config(cfg: AppConfig):
    save_config(cfg)
    return {"success": True, "config": cfg.model_dump()}

class TestAIRequest(BaseModel):
    provider: str
    base_url: str
    api_key: str
    model: str
    network_proxy: Optional[str] = None

@app.post("/api/test-ai")
async def test_ai_connection(req: TestAIRequest):
    """Test AI API connection (supports Gemini, OpenAI, DeepSeek, Claude, and Custom Reverse Proxies)."""
    try:
        timeout = httpx.Timeout(20.0, connect=10.0)
        
        # Test Gemini native API
        if req.provider == "gemini" and ("generativelanguage.googleapis.com" in req.base_url or not req.base_url):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{req.model or 'gemini-1.5-flash'}:generateContent?key={req.api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "Hello, respond with 'OK'."}]}]
            }
            async with httpx.AsyncClient(timeout=timeout, proxy=req.network_proxy) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return {"success": True, "message": "Kết nối Gemini API thành công!"}
                return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}

        # Test OpenAI-compatible / Custom Proxy
        base = (req.base_url or "https://api.openai.com/v1").rstrip("/")
        url = f"{base}/chat/completions" if not base.endswith("/chat/completions") else base
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {req.api_key}"
        }
        payload = {
            "model": req.model or "gpt-4o",
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 5
        }
        async with httpx.AsyncClient(timeout=timeout, proxy=req.network_proxy) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                return {"success": True, "message": f"Kết nối thành công tới {req.provider} qua Proxy/API!"}
            return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==================== ACCOUNT POOL ENDPOINTS ====================

@app.get("/api/accounts")
def get_accounts():
    account_manager._check_daily_reset()
    return [a.model_dump() for a in account_manager.accounts]

class BulkAccountRequest(BaseModel):
    raw_text: str

@app.post("/api/accounts/bulk")
def add_accounts_bulk(req: BulkAccountRequest):
    res = account_manager.add_bulk(req.raw_text)
    return res

@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str):
    success = account_manager.delete(account_id)
    return {"success": success}

@app.post("/api/accounts/{account_id}/toggle")
def toggle_account(account_id: str):
    acc = account_manager.toggle_status(account_id)
    return {"success": acc is not None, "account": acc.model_dump() if acc else None}

@app.post("/api/accounts/{account_id}/check")
async def check_account_health(account_id: str):
    cfg = load_config()
    res = await account_manager.check_health(account_id, proxy=cfg.ai_network_proxy)
    return res

# ==================== AI MV DIRECTOR ENDPOINTS ====================

class MVPlanRequest(BaseModel):
    song_title: str
    lyrics: str
    genre_style: str = "Pop Ballad"
    bpm: str = "85 BPM"
    vocal: str = "Nữ trầm ấm, da diết"
    mood: str = "Hoài niệm, buồn sâu lắng"
    extra_notes: Optional[str] = ""

@app.post("/api/director/generate")
async def generate_director_plan(req: MVPlanRequest):
    cfg = load_config()
    if not cfg.ai_api_key:
        raise HTTPException(400, "Vui lòng cấu hình API Key trong mục Cài đặt trước khi chạy tự động.")
    
    try:
        res = await generate_mv_plan(
            cfg=cfg,
            song_title=req.song_title,
            lyrics=req.lyrics,
            genre_style=req.genre_style,
            bpm=req.bpm,
            vocal=req.vocal,
            mood=req.mood,
            extra_notes=req.extra_notes or ""
        )
        return res
    except Exception as e:
        raise HTTPException(500, f"Lỗi tạo kịch bản MV: {str(e)}")

class ParseTextRequest(BaseModel):
    raw_script: str

@app.post("/api/director/parse")
def parse_raw_script(req: ParseTextRequest):
    """Extract shots directly from pasted markdown script (useful when generating outside)."""
    shots = extract_shots_from_script(req.raw_script)
    return {"shots": shots, "count": len(shots)}

# ==================== BATCH STUDIO & TASKS ENDPOINTS ====================

@app.get("/api/tasks")
def get_tasks():
    return [t.model_dump() for t in task_manager.tasks]

class CreateTasksRequest(BaseModel):
    tasks: List[Dict[str, Any]]

@app.post("/api/tasks")
def create_tasks(req: CreateTasksRequest):
    new_tasks = task_manager.add_tasks_bulk(req.tasks)
    return {"success": True, "count": len(new_tasks), "tasks": [t.model_dump() for t in new_tasks]}

@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    task_manager.tasks = [t for t in task_manager.tasks if t.id != task_id]
    task_manager.save()
    return {"success": True}

@app.post("/api/tasks/clear")
def clear_tasks():
    task_manager.clear_all()
    return {"success": True}

@app.post("/api/tasks/retry/{task_id}")
def retry_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task không tồn tại")
    task.status = "pending"
    task.progress = 0
    task.error = None
    task.status_message = "Đang đưa lại vào hàng đợi..."
    task_manager.save()
    task_manager._queue.put_nowait(task.id)
    return {"success": True, "task": task.model_dump()}

# ==================== DOWNLOADS & GALLERY ====================

@app.get("/api/downloads/zip")
def download_all_zip():
    """Package all completed files into a single ZIP archive for CapCut."""
    zip_path = os.path.join(DOWNLOADS_DIR, "all_renders.zip")
    completed_tasks = [t for t in task_manager.tasks if t.status == "completed" and t.local_file and os.path.exists(t.local_file)]
    
    if not completed_tasks:
        # Check files directly in folder
        files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('.mp4', '.png', '.webm'))]
        if not files:
            raise HTTPException(404, "Chưa có video nào hoàn thành để tải ZIP.")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in files:
                z.write(f, os.path.basename(f))
    else:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for t in completed_tasks:
                arcname = f"Shot_{t.id}_{os.path.basename(t.local_file)}"
                z.write(t.local_file, arcname)

    return FileResponse(zip_path, media_type="application/zip", filename="MUSE_MV_Clips.zip")

@app.post("/api/open-downloads")
def open_downloads_folder():
    """Open Windows Explorer folder."""
    try:
        os.startfile(DOWNLOADS_DIR)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Serve static web frontend
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
