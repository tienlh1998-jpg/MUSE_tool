import asyncio
import os
import shutil
import sys
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.account_manager import account_manager
from core.config import (
    AppConfig,
    DOWNLOADS_DIR,
    IMAGES_DIR,
    load_config,
    migrate_legacy_downloads,
    save_config,
)
from core.muse_engine import VIDEO_SIZES
from core.mv_director import extract_shots_from_script, generate_mv_plan
from core.project_manager import project_manager
from core.task_manager import task_manager
from core.video_stitcher import VideoStitcher

video_stitcher = VideoStitcher(DOWNLOADS_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_legacy_downloads()
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    cfg = load_config()
    await task_manager.start_workers(cfg)
    yield
    await task_manager.stop_workers()


app = FastAPI(title="MUSE Multi-Account AI Studio", version="3.1.0", lifespan=lifespan)

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
app.mount("/downloads", StaticFiles(directory=DOWNLOADS_DIR), name="downloads")


# ==================== HEALTH & CONFIG ====================

@app.get("/api/health")
def healthcheck():
    return {
        "status": "ok",
        "version": "3.1.0",
        "downloads_dir": DOWNLOADS_DIR,
        "images_dir": IMAGES_DIR,
        "ffmpeg": video_stitcher.ffmpeg_exe,
        "accounts": len(account_manager.accounts),
        "projects": len(project_manager.projects),
        "tasks": len(task_manager.tasks),
    }


@app.get("/api/config")
def get_config():
    return load_config().model_dump()


@app.post("/api/config")
def update_config(cfg: AppConfig):
    # Merge only the fields the UI actually sent so a partial payload cannot
    # silently reset unrelated settings (image fallback, download dir, ...).
    current = load_config().model_dump()
    incoming = cfg.model_dump()
    for field in cfg.model_fields_set:
        current[field] = incoming[field]
    merged = AppConfig(**current)
    save_config(merged)
    return {"success": True, "config": merged.model_dump()}


class TestAIRequest(BaseModel):
    provider: str
    base_url: str
    api_key: str
    model: str
    network_proxy: Optional[str] = None


@app.post("/api/test-ai")
async def test_ai_connection(req: TestAIRequest):
    """Test an AI API connection (Gemini native or OpenAI-compatible)."""
    try:
        timeout = httpx.Timeout(20.0, connect=10.0)

        if req.provider == "gemini" and (
            "generativelanguage.googleapis.com" in (req.base_url or "") or not req.base_url
        ):
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{req.model or 'gemini-1.5-flash'}:generateContent?key={req.api_key}"
            )
            payload = {
                "contents": [{"role": "user", "parts": [{"text": "Hello, respond with 'OK'."}]}]
            }
            async with httpx.AsyncClient(timeout=timeout, proxy=req.network_proxy) as client:
                res = await client.post(url, json=payload)
            if res.status_code == 200:
                return {"success": True, "message": "Kết nối Gemini API thành công!"}
            return {"success": False, "error": f"HTTP {res.status_code}: {res.text[:300]}"}

        base = (req.base_url or "https://api.openai.com/v1").rstrip("/")
        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {req.api_key}",
        }
        payload = {
            "model": req.model or "gpt-4o",
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 5,
        }
        async with httpx.AsyncClient(timeout=timeout, proxy=req.network_proxy) as client:
            res = await client.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            return {
                "success": True,
                "message": f"Kết nối thành công tới {req.provider} qua Proxy/API!",
            }
        return {"success": False, "error": f"HTTP {res.status_code}: {res.text[:300]}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ==================== ACCOUNT POOL ====================

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
    return account_manager.add_bulk(text)


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str):
    return {"success": account_manager.delete(account_id)}


@app.post("/api/accounts/{account_id}/toggle")
def toggle_account(account_id: str):
    acc = account_manager.toggle_status(account_id)
    return {"success": acc is not None, "account": acc.model_dump() if acc else None}


@app.post("/api/accounts/{account_id}/check")
async def check_account_health(account_id: str):
    cfg = load_config()
    return await account_manager.check_health(account_id, proxy=cfg.ai_network_proxy)


@app.post("/api/accounts/check-all")
async def check_all_accounts():
    cfg = load_config()
    return await account_manager.check_all(proxy=cfg.ai_network_proxy)


class SendOTPRequest(BaseModel):
    email: str


class ConfirmOTPRequest(BaseModel):
    email: str
    otp_code: str


@app.post("/api/accounts/otp/send")
async def send_account_otp(req: SendOTPRequest):
    cfg = load_config()
    return await account_manager.request_otp(req.email, proxy=cfg.ai_network_proxy)


@app.post("/api/accounts/otp/confirm")
async def confirm_account_otp(req: ConfirmOTPRequest):
    return await account_manager.confirm_otp(req.email, req.otp_code)


# ==================== PROJECTS ====================

@app.get("/api/projects")
def list_projects():
    return project_manager.list_projects()


class CreateProjectRequest(BaseModel):
    name: str
    lyrics: Optional[str] = ""
    aspect: Optional[str] = "16:9"
    audio_filename: Optional[str] = None
    srt_content: Optional[str] = None
    audio_path: Optional[str] = None


@app.post("/api/projects")
def create_project(req: CreateProjectRequest):
    return project_manager.create_project(
        name=req.name,
        lyrics=req.lyrics or "",
        aspect=req.aspect or "16:9",
        audio_filename=req.audio_filename,
        audio_path=req.audio_path,
    )


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    proj = project_manager.get_project(project_id)
    if not proj:
        raise HTTPException(404, "Không tìm thấy dự án")
    return proj


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    return {"success": project_manager.delete_project(project_id)}


class AddImageRequest(BaseModel):
    prompt: str
    url: str
    aspect: Optional[str] = "16:9"
    ref_image: Optional[str] = None


@app.post("/api/projects/{project_id}/images")
def add_project_image(project_id: str, req: AddImageRequest):
    if not project_manager.get_project(project_id):
        raise HTTPException(404, "Không tìm thấy dự án")
    return project_manager.add_image(project_id, req.model_dump())


@app.delete("/api/projects/{project_id}/images/{image_id}")
def delete_project_image(project_id: str, image_id: str):
    if not project_manager.get_project(project_id):
        raise HTTPException(404, "Không tìm thấy dự án")
    success = project_manager.delete_image(project_id, image_id, delete_file=True)
    if not success:
        raise HTTPException(404, "Không tìm thấy ảnh")
    return {"success": True}


@app.post("/api/projects/{project_id}/images/{image_id}/regenerate")
async def regenerate_project_image(project_id: str, image_id: str):
    """Re-render an existing image with the same prompt/aspect ratio."""
    image = project_manager.get_image(project_id, image_id)
    if not image:
        raise HTTPException(404, "Không tìm thấy ảnh")
    project_manager.delete_image(project_id, image_id, delete_file=True)
    tasks = task_manager.add_tasks_bulk([{
        "project_id": project_id,
        "prompt": image.get("prompt", ""),
        "mode": "text-to-image",
        "aspect": image.get("aspect", "16:9"),
    }])
    return {"success": True, "task": tasks[0].model_dump() if tasks else None}


class AddShotRequest(BaseModel):
    prompt: str
    source_image_url: Optional[str] = None
    mode: Optional[str] = "image-to-video"
    duration: Optional[int] = 7


@app.post("/api/projects/{project_id}/shots")
def add_project_shot(project_id: str, req: AddShotRequest):
    if not project_manager.get_project(project_id):
        raise HTTPException(404, "Không tìm thấy dự án")
    return project_manager.add_shot(project_id, req.model_dump())


@app.delete("/api/projects/{project_id}/shots/{shot_id}")
def delete_project_shot(project_id: str, shot_id: str):
    return {"success": project_manager.delete_shot(project_id, shot_id)}


@app.post("/api/projects/{project_id}/shots/{shot_id}/render")
async def render_project_shot(project_id: str, shot_id: str):
    """Queue a single shot for rendering and flag it as rendering in the UI."""
    shot = project_manager.get_shot(project_id, shot_id)
    if not shot:
        raise HTTPException(404, "Không tìm thấy shot")
    project_manager.update_shot(project_id, shot_id, {"status": "rendering"})
    tasks = task_manager.add_tasks_bulk([{
        "project_id": project_id,
        "shot_id": shot_id,
        "prompt": shot.get("prompt", ""),
        "mode": shot.get("mode", "image-to-video"),
        "duration": shot.get("duration", 7),
        "source_image_path": shot.get("source_image_url"),
    }])
    return {"success": True, "task": tasks[0].model_dump() if tasks else None}


@app.post("/api/projects/{project_id}/stitch")
def stitch_project_video(project_id: str):
    """1-Click Auto-Stitch: concatenate rendered shots in order and mux music."""
    proj = project_manager.get_project(project_id)
    if not proj:
        raise HTTPException(404, "Không tìm thấy dự án")

    completed = project_manager.ordered_shot_videos(project_id)
    if not completed:
        raise HTTPException(400, "Dự án chưa có video clip nào hoàn thành để ghép!")

    video_paths = [s["resolved_path"] for s in completed]
    safe_name = "".join(
        c for c in proj.get("name", "Project") if c.isalnum() or c in (" ", "_", "-")
    ).strip().replace(" ", "_") or "Project"
    out_filename = f"Full_MV_{safe_name}_{int(time.time())}.mp4"

    audio_path = project_manager.resolve_media_path(proj.get("audio_path"))
    target_size = VIDEO_SIZES.get(proj.get("aspect", "16:9"), VIDEO_SIZES["16:9"])

    try:
        res = video_stitcher.stitch_videos(
            video_paths=video_paths,
            audio_path=audio_path,
            output_filename=out_filename,
            target_size=target_size,
        )
        project_manager.set_final_video(project_id, res["url"], res["output_path"])
        res["shot_numbers"] = [s.get("shot_number") for s in completed]
        return res
    except Exception as exc:
        raise HTTPException(500, f"Lỗi khi ghép video: {str(exc)}")


# ==================== CANVAS WORKFLOW DIRECT ENDPOINTS ====================

class GenerateImageAPIRequest(BaseModel):
    prompt: str
    aspect: Optional[str] = "16:9"
    negative_prompt: Optional[str] = ""
    project_id: Optional[str] = None
    ref_image: Optional[str] = None
    wait: Optional[bool] = False
    timeout: Optional[int] = 120


@app.post("/api/generate-image")
async def api_generate_image(req: GenerateImageAPIRequest):
    """Direct image generation endpoint for Canvas and API workflows."""
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "Prompt không được để trống.")

    task_payload = {
        "project_id": req.project_id or None,
        "prompt": prompt,
        "negative_prompt": req.negative_prompt or "",
        "mode": "image-to-image" if req.ref_image else "text-to-image",
        "aspect": req.aspect or "16:9",
        "source_image_path": req.ref_image,
        "ref_image": req.ref_image,
    }
    tasks = task_manager.add_tasks_bulk([task_payload])
    if not tasks:
        raise HTTPException(500, "Không tạo được task tạo ảnh.")
    task = tasks[0]

    if req.wait:
        deadline = time.time() + max(10, min(req.timeout or 120, 600))
        while time.time() < deadline:
            t = task_manager.get_task(task.id)
            if not t:
                raise HTTPException(500, "Task bị mất trong hàng đợi.")
            if t.status == "completed":
                return {
                    "success": True,
                    "url": t.result_url,
                    "local_path": t.local_file,
                    "task_id": t.id,
                    "task": t.model_dump(),
                }
            if t.status == "failed":
                raise HTTPException(500, f"Tạo ảnh thất bại: {t.error or t.status_message}")
            await asyncio.sleep(0.5)
        raise HTTPException(504, f"Quá thời gian chờ tạo ảnh ({req.timeout}s). Task vẫn tiếp tục chạy trong nền.")

    return {
        "success": True,
        "task_id": task.id,
        "task": task.model_dump(),
    }


class RenderShotAPIRequest(BaseModel):
    prompt: str
    aspect: Optional[str] = "16:9"
    negative_prompt: Optional[str] = ""
    duration: Optional[int] = 7
    project_id: Optional[str] = None
    shot_id: Optional[str] = None
    source_image_url: Optional[str] = None
    source_image_path: Optional[str] = None
    ref_image_url: Optional[str] = None
    ref_images: Optional[List[str]] = None
    mode: Optional[str] = None
    wait: Optional[bool] = False
    timeout: Optional[int] = 180


@app.post("/api/render-shot")
async def api_render_shot(req: RenderShotAPIRequest):
    """Direct video shot rendering endpoint for Canvas and API workflows."""
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "Prompt không được để trống.")

    source_img = req.source_image_path or req.source_image_url
    mode = req.mode or ("image-to-video" if source_img else "text-to-video")

    shot_id = req.shot_id
    if req.project_id:
        proj = project_manager.get_project(req.project_id)
        if proj:
            if shot_id:
                shot = project_manager.get_shot(req.project_id, shot_id)
                if shot:
                    project_manager.update_shot(
                        req.project_id,
                        shot_id,
                        {
                            "prompt": prompt,
                            "source_image_url": source_img,
                            "status": "rendering",
                            "duration": req.duration or 7,
                            "mode": mode,
                        },
                    )
            else:
                new_shot = project_manager.add_shot(
                    req.project_id,
                    {
                        "prompt": prompt,
                        "source_image_url": source_img,
                        "status": "rendering",
                        "duration": req.duration or 7,
                        "mode": mode,
                    },
                )
                shot_id = new_shot.get("id")

    ref_img = req.ref_image_url or (req.ref_images[0] if req.ref_images else None)
    task_payload = {
        "project_id": req.project_id or None,
        "shot_id": shot_id,
        "prompt": prompt,
        "negative_prompt": req.negative_prompt or "",
        "mode": mode,
        "aspect": req.aspect or "16:9",
        "duration": req.duration or 7,
        "source_image_path": source_img,
        "ref_image": ref_img,
        "ref_images": req.ref_images or ([] if not ref_img else [ref_img]),
    }
    tasks = task_manager.add_tasks_bulk([task_payload])
    if not tasks:
        raise HTTPException(500, "Không tạo được task render video.")
    task = tasks[0]

    if req.wait:
        deadline = time.time() + max(10, min(req.timeout or 180, 600))
        while time.time() < deadline:
            t = task_manager.get_task(task.id)
            if not t:
                raise HTTPException(500, "Task bị mất trong hàng đợi.")
            if t.status == "completed":
                return {
                    "success": True,
                    "url": t.result_url,
                    "local_path": t.local_file,
                    "task_id": t.id,
                    "task": t.model_dump(),
                }
            if t.status == "failed":
                raise HTTPException(500, f"Render video thất bại: {t.error or t.status_message}")
            await asyncio.sleep(0.5)
        raise HTTPException(504, f"Quá thời gian chờ render ({req.timeout}s). Task vẫn tiếp tục chạy trong nền.")

    return {
        "success": True,
        "task_id": task.id,
        "task": task.model_dump(),
    }


class AutoStitchAPIRequest(BaseModel):
    project_id: Optional[str] = None
    video_paths: Optional[List[str]] = None
    audio_path: Optional[str] = None
    aspect: Optional[str] = None
    output_filename: Optional[str] = None


@app.post("/api/auto-stitch")
def api_auto_stitch(req: AutoStitchAPIRequest):
    """Direct video stitching endpoint for Canvas Timeline and Auto-Stitch."""
    video_paths: List[str] = req.video_paths or []
    audio_path = req.audio_path
    aspect = req.aspect or "16:9"
    proj_name = "Canvas_MV"

    if req.project_id:
        proj = project_manager.get_project(req.project_id)
        if proj:
            aspect = req.aspect or proj.get("aspect", "16:9")
            proj_name = "".join(
                c for c in proj.get("name", "Project") if c.isalnum() or c in (" ", "_", "-")
            ).strip().replace(" ", "_") or "Project"
            if not audio_path:
                audio_path = project_manager.resolve_media_path(proj.get("audio_path"))
            if not video_paths:
                completed = project_manager.ordered_shot_videos(req.project_id)
                video_paths = [s["resolved_path"] for s in completed]

    if not video_paths:
        raise HTTPException(400, "Không có file video nào được chỉ định để ghép!")

    if audio_path:
        audio_path = project_manager.resolve_media_path(audio_path)

    out_filename = req.output_filename or f"Full_MV_{proj_name}_{int(time.time())}.mp4"
    target_size = VIDEO_SIZES.get(aspect, VIDEO_SIZES["16:9"])

    try:
        res = video_stitcher.stitch_videos(
            video_paths=video_paths,
            audio_path=audio_path,
            output_filename=out_filename,
            target_size=target_size,
        )
        if req.project_id:
            project_manager.set_final_video(req.project_id, res["url"], res["output_path"])
        return res
    except Exception as exc:
        raise HTTPException(500, f"Lỗi khi ghép video: {str(exc)}")


# ==================== UPLOAD MEDIA ====================

ALLOWED_UPLOAD_EXT = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".mp4", ".webm",
}


@app.post("/api/upload-media")
async def upload_media_file(file: UploadFile = File(...)):
    """Upload an image, audio or video file into the media folder."""
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in ALLOWED_UPLOAD_EXT:
        raise HTTPException(400, f"Định dạng file không hỗ trợ: {ext or 'không rõ'}")

    clean_name = f"upload_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
    dest_path = os.path.join(DOWNLOADS_DIR, clean_name)

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if os.path.getsize(dest_path) == 0:
        os.remove(dest_path)
        raise HTTPException(400, "File tải lên rỗng.")

    return {
        "success": True,
        "filename": clean_name,
        "original_name": file.filename,
        "local_path": dest_path,
        "url": f"/downloads/{clean_name}",
    }


# ==================== AI MV DIRECTOR ====================

class MVPlanRequest(BaseModel):
    song_title: str
    lyrics: str
    genre_style: str = "Pop Ballad"
    bpm: str = "85 BPM"
    vocal: str = "Nữ trầm ấm, da diết"
    mood: str = "Hoài niệm, buồn sâu lắng"
    extra_notes: Optional[str] = ""
    audio_url: Optional[str] = None
    audio_duration: Optional[float] = None
    audio_filename: Optional[str] = None
    srt_content: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_base_url: Optional[str] = None
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None
    network_proxy: Optional[str] = None


@app.get("/api/director/config")
def get_director_config():
    """Get current AI configuration for Canvas AI Director."""
    cfg = load_config()
    key = cfg.ai_api_key or ""
    masked = (key[:4] + "..." + key[-4:]) if len(key) > 8 else ("***" if key else "")
    return {
        "ai_provider": cfg.ai_provider or "custom_proxy",
        "ai_base_url": cfg.ai_base_url or "https://api.openai.com/v1",
        "ai_model": cfg.ai_model or "gpt-4o",
        "has_api_key": bool(key),
        "api_key_masked": masked,
        "network_proxy": cfg.ai_network_proxy or ""
    }


@app.post("/api/director/generate")
async def generate_director_plan(req: MVPlanRequest):
    cfg = load_config()

    # Allow overriding AI settings directly from request
    if req.ai_provider:
        cfg.ai_provider = req.ai_provider
    if req.ai_base_url:
        cfg.ai_base_url = req.ai_base_url
    if req.ai_api_key:
        cfg.ai_api_key = req.ai_api_key
    if req.ai_model:
        cfg.ai_model = req.ai_model
    if req.network_proxy:
        cfg.ai_network_proxy = req.network_proxy

    if not cfg.ai_api_key:
        raise HTTPException(400, "Vui lòng nhập API Key hoặc cấu hình trong mục Cài đặt trước.")
    try:
        return await generate_mv_plan(
            cfg=cfg,
            song_title=req.song_title,
            lyrics=req.lyrics,
            genre_style=req.genre_style,
            bpm=req.bpm,
            vocal=req.vocal,
            mood=req.mood,
            extra_notes=req.extra_notes or "",
            audio_duration=req.audio_duration,
            audio_url=req.audio_url,
            srt_content=req.srt_content,
        )
    except Exception as exc:
        raise HTTPException(500, f"Lỗi tạo kịch bản MV: {str(exc)}")


class ParseTextRequest(BaseModel):
    raw_script: str


@app.post("/api/director/parse")
def parse_raw_script(req: ParseTextRequest):
    shots = extract_shots_from_script(req.raw_script)
    return {"shots": shots, "count": len(shots)}


# ==================== TASKS ====================

@app.get("/api/tasks")
def get_tasks(project_id: Optional[str] = None, status: Optional[str] = None):
    tasks = task_manager.tasks
    if project_id:
        tasks = [t for t in tasks if t.project_id == project_id]
    if status:
        tasks = [t for t in tasks if t.status == status]
    return [t.model_dump() for t in tasks]


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task không tồn tại")
    return task.model_dump()


class CreateTasksRequest(BaseModel):
    tasks: List[Dict[str, Any]]


@app.post("/api/tasks")
async def create_tasks(req: CreateTasksRequest):
    new_tasks = task_manager.add_tasks_bulk(req.tasks)
    if not new_tasks:
        raise HTTPException(400, "Không có task hợp lệ (prompt rỗng).")
    return {
        "success": True,
        "count": len(new_tasks),
        "tasks": [t.model_dump() for t in new_tasks],
    }


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
async def retry_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task không tồn tại")
    task.status = "pending"
    task.progress = 0
    task.error = None
    task.status_message = "Đang đưa lại vào hàng đợi..."
    task_manager.save()
    task_manager._enqueue(task.id)
    return {"success": True, "task": task.model_dump()}


# ==================== DOWNLOADS ====================

@app.get("/api/downloads/zip")
def download_all_zip():
    """Package every generated asset (including images/) into one ZIP."""
    zip_path = os.path.join(DOWNLOADS_DIR, "all_renders.zip")
    files = []
    for root, _dirs, names in os.walk(DOWNLOADS_DIR):
        for name in names:
            if name == "all_renders.zip":
                continue
            if os.path.splitext(name)[1].lower() in (".mp4", ".png", ".jpg", ".jpeg", ".webm"):
                files.append(os.path.join(root, name))
    if not files:
        raise HTTPException(404, "Chưa có file nào hoàn thành để tải ZIP.")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            arcname = os.path.relpath(path, DOWNLOADS_DIR).replace("\\", "/")
            archive.write(path, arcname)

    return FileResponse(zip_path, media_type="application/zip", filename="MUSE_MV_Clips.zip")


@app.post("/api/open-downloads")
def open_downloads_folder():
    try:
        os.startfile(DOWNLOADS_DIR)  # type: ignore[attr-defined]
        return {"success": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ==================== CANVAS WORKFLOW ROUTE ====================

@app.get("/canvas")
@app.get("/flow")
@app.get("/canvas.html")
def serve_canvas():
    """Serve the Node Workflow Canvas frontend by redirecting to trailing slash for proper relative asset resolution."""
    return RedirectResponse(url="/canvas/", status_code=302)


# Serve static web frontend (must stay last).
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
CANVAS_DIR = os.path.join(STATIC_DIR, "canvas")
if os.path.exists(CANVAS_DIR):
    app.mount("/canvas", StaticFiles(directory=CANVAS_DIR, html=True), name="canvas_static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static_dir")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
