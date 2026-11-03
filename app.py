import os
import shutil
import subprocess
import zipfile
import httpx
import uuid
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from core.config import load_config, save_config, AppConfig, DOWNLOADS_DIR
from core.account_manager import account_manager
from core.mv_director import generate_mv_plan, extract_shots_from_script
from core.task_manager import task_manager
from core.project_manager import ProjectManager
from core.video_stitcher import VideoStitcher

project_manager = ProjectManager()
video_stitcher = VideoStitcher(DOWNLOADS_DIR)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background workers
    cfg = load_config()
    await task_manager.start_workers(cfg)
    yield
    # Shutdown logic
    task_manager._running = False

app = FastAPI(title="MUSE Multi-Account AI Studio", version="3.0.0", lifespan=lifespan)

# Mount downloads directory
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")

# ==================== CONFIG & AI ENDPOINTS ====================

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
    raw_text: Optional[str] = None
    accounts: Optional[List[str]] = None

@app.post("/api/accounts/bulk")
def add_accounts_bulk(req: BulkAccountRequest):
    text = req.raw_text or "\n".join(req.accounts or [])
    res = account_manager.add_bulk(text)
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

@app.post("/api/accounts/check-all")
async def check_all_accounts():
    cfg = load_config()
    res = await account_manager.check_all(proxy=cfg.ai_network_proxy)
    return res

# ==================== PROJECT MANAGEMENT ENDPOINTS ====================

@app.get("/api/projects")
def list_projects():
    return project_manager.list_projects()

class CreateProjectRequest(BaseModel):
    name: str
    lyrics: Optional[str] = ""
    aspect: Optional[str] = "16:9"
    audio_filename: Optional[str] = None
    audio_path: Optional[str] = None

@app.post("/api/projects")
def create_project(req: CreateProjectRequest):
    proj = project_manager.create_project(
        name=req.name,
        lyrics=req.lyrics or "",
        aspect=req.aspect or "16:9",
        audio_filename=req.audio_filename,
        audio_path=req.audio_path
    )
    return proj

@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    proj = project_manager.get_project(project_id)
    if not proj:
        raise HTTPException(404, "Không tìm thấy dự án")
    return proj

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    success = project_manager.delete_project(project_id)
    return {"success": success}

class AddImageRequest(BaseModel):
    prompt: str
    url: str
    aspect: Optional[str] = "16:9"
    ref_image: Optional[str] = None

@app.post("/api/projects/{project_id}/images")
def add_project_image(project_id: str, req: AddImageRequest):
    img = project_manager.add_image(project_id, req.model_dump())
    return img

class AddShotRequest(BaseModel):
    prompt: str
    source_image_url: Optional[str] = None
    mode: Optional[str] = "image-to-video"
    duration: Optional[int] = 7

@app.post("/api/projects/{project_id}/shots")
def add_project_shot(project_id: str, req: AddShotRequest):
    shot = project_manager.add_shot(project_id, req.model_dump())
    return shot

@app.delete("/api/projects/{project_id}/shots/{shot_id}")
def delete_project_shot(project_id: str, shot_id: str):
    success = project_manager.delete_shot(project_id, shot_id)
    return {"success": success}

@app.post("/api/projects/{project_id}/stitch")
def stitch_project_video(project_id: str):
    """
    1-Click Auto-Stitch: joins all rendered video clips of this project using FFmpeg,
    muxes with the project audio track (if available), and outputs Full_MV_{project_id}.mp4.
    """
    proj = project_manager.get_project(project_id)
    if not proj:
        raise HTTPException(404, "Không tìm thấy dự án")

    shots = proj.get("shots", [])
    # Find all completed video files
    video_paths = []
    for s in shots:
        local_p = s.get("local_path")
        if local_p and os.path.exists(local_p):
            video_paths.append(local_p)
        elif s.get("video_url"):
            # Try to resolve filename from /downloads/
            fname = s["video_url"].split("/downloads/")[-1]
            cand = os.path.join(DOWNLOADS_DIR, fname)
            if os.path.exists(cand):
                video_paths.append(cand)

    if not video_paths:
        raise HTTPException(400, "Dự án chưa có video clip nào hoàn thành để ghép!")

    safe_name = "".join(c for c in proj.get("name", "Project") if c.isalnum() or c in (" ", "_", "-")).strip()
    out_filename = f"Full_MV_{safe_name}_{int(time.time())}.mp4"
    audio_path = proj.get("audio_path")

    try:
        res = video_stitcher.stitch_videos(
            video_paths=video_paths,
            audio_path=audio_path,
            output_filename=out_filename
        )
        project_manager.set_final_video(project_id, res["url"])
        return res
    except Exception as e:
        raise HTTPException(500, f"Lỗi khi ghép video: {str(e)}")

# ==================== UPLOAD MEDIA (IMAGES & AUDIO) ====================

@app.post("/api/upload-media")
async def upload_media_file(file: UploadFile = File(...)):
    """Uploads an image or mp3 audio file directly into data/downloads."""
    ext = os.path.splitext(file.filename)[-1].lower()
    clean_name = f"upload_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
    dest_path = os.path.join(DOWNLOADS_DIR, clean_name)
    
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "success": True,
        "filename": clean_name,
        "original_name": file.filename,
        "local_path": dest_path,
        "url": f"/downloads/{clean_name}"
    }

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
    shots = extract_shots_from_script(req.raw_script)
    return {"shots": shots, "count": len(shots)}

# ==================== TASKS & BATCH ENDPOINTS ====================

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

# ==================== DOWNLOADS & EXPLORER ====================

@app.get("/api/downloads/zip")
def download_all_zip():
    """Package all completed files into a single ZIP archive."""
    zip_path = os.path.join(DOWNLOADS_DIR, "all_renders.zip")
    files = [os.path.join(DOWNLOADS_DIR, f) for f in os.listdir(DOWNLOADS_DIR) if f.endswith(('.mp4', '.png', '.webm', '.jpg')) and f != "all_renders.zip"]
    if not files:
        raise HTTPException(404, "Chưa có file nào hoàn thành để tải ZIP.")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, os.path.basename(f))

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
