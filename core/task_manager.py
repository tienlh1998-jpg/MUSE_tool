"""Background render queue with persistence and auto-recovery.

Tasks survive restarts: on startup every ``pending`` task and every task that
was interrupted mid-run is pushed back onto the queue.  Image generation tasks
do not require a Muse account, so they run even on a fresh install with an
empty account pool.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from core.account_manager import account_manager
from core.config import DATA_DIR, load_config
from core.muse_engine import MuseEngine, MuseAuthError
from core.project_manager import project_manager

TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")


class RenderTask(BaseModel):
    id: str
    project_id: Optional[str] = None
    shot_id: Optional[str] = None
    prompt: str
    negative_prompt: str = ""
    mode: str = "text-to-video"  # "text-to-video", "image-to-video", "text-to-image"
    aspect: str = "16:9"
    duration: int = 7
    ref_image: Optional[str] = None
    source_image_path: Optional[str] = None
    status: str = "pending"  # "pending", "running", "completed", "failed"
    progress: int = 0
    status_message: str = "Đang chờ trong hàng đợi..."
    account_id: Optional[str] = None
    account_email: Optional[str] = None
    result_url: Optional[str] = None
    local_file: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class TaskManager:
    def __init__(self, tasks_file: Optional[str] = None):
        self.tasks_file = tasks_file or TASKS_FILE
        self.tasks: List[RenderTask] = []
        self._queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._pending_ids: List[str] = []
        self._running = False
        self._workers: List[asyncio.Task] = []
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def load(self):
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.tasks = [RenderTask(**item) for item in data]
            except Exception as exc:
                print(f"[TaskManager] Error loading tasks: {exc}")
                self.tasks = []
        else:
            self.tasks = []

    def save(self):
        os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
        tmp_path = self.tasks_file + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump([t.model_dump() for t in self.tasks], f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self.tasks_file)

    # ------------------------------------------------------------------
    # Queue API
    # ------------------------------------------------------------------
    def _get_queue(self) -> asyncio.Queue:
        # The queue must be created on the worker event loop.  When it is
        # first needed from a thread-pool thread we remember the ids and let
        # ``start_workers`` drain them.
        if self._queue is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = None
            self._queue = asyncio.Queue()
        return self._queue

    def _enqueue(self, task_id: str):
        """Thread-safe enqueue from sync endpoints and worker threads."""
        if self._queue is None:
            self._pending_ids.append(task_id)
            return
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, task_id)
            return
        try:
            self._queue.put_nowait(task_id)
        except RuntimeError:
            self._pending_ids.append(task_id)

    def add_tasks_bulk(self, task_items: List[Dict[str, Any]]) -> List[RenderTask]:
        now = datetime.now().isoformat()
        new_tasks = []
        for item in task_items:
            prompt = (item.get("prompt") or "").strip()
            if not prompt:
                continue
            task = RenderTask(
                id=uuid.uuid4().hex[:10],
                project_id=item.get("project_id"),
                shot_id=item.get("shot_id"),
                prompt=prompt,
                negative_prompt=item.get("negative_prompt", "") or "",
                mode=item.get("mode", "text-to-video"),
                aspect=item.get("aspect", "16:9"),
                duration=int(item.get("duration", 7) or 7),
                ref_image=item.get("ref_image"),
                source_image_path=item.get("source_image_path"),
                created_at=now,
            )
            self.tasks.append(task)
            new_tasks.append(task)
            self._enqueue(task.id)

        self.save()
        return new_tasks

    def get_task(self, task_id: str) -> Optional[RenderTask]:
        return next((t for t in self.tasks if t.id == task_id), None)

    def clear_all(self):
        self.tasks = []
        self.save()

    def recover_pending_tasks(self) -> int:
        """Re-queue pending and interrupted tasks after a restart."""
        recovered = 0
        for task in self.tasks:
            if task.status in ("pending", "running"):
                task.status = "pending"
                task.progress = 0
                task.error = None
                task.status_message = "Đang khôi phục vào hàng đợi..."
                self._pending_ids.append(task.id)
                recovered += 1
        if recovered:
            self.save()
        return recovered

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------
    async def start_workers(self, cfg=None):
        if self._running:
            return
        cfg = cfg or load_config()
        self._running = True
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()

        recovered = self.recover_pending_tasks()
        # Drain tasks queued before the loop existed (sync endpoint calls).
        for task_id in self._pending_ids:
            self._queue.put_nowait(task_id)
        self._pending_ids.clear()
        if recovered:
            print(f"[TaskManager] Da khoi phuc {recovered} task vao hang doi.")

        concurrency = max(1, min(int(cfg.concurrency or 1), 10))
        for _ in range(concurrency):
            worker = asyncio.create_task(self._worker_loop(cfg))
            self._workers.append(worker)

    async def stop_workers(self):
        self._running = False
        for worker in self._workers:
            worker.cancel()
        self._workers = []

    async def _worker_loop(self, cfg):
        engine = MuseEngine(cfg)
        queue = self._queue
        while self._running:
            task_id = await queue.get()
            task = self.get_task(task_id)
            if not task or task.status == "completed":
                queue.task_done()
                continue

            try:
                await self._process_task(task, engine, cfg)
            except Exception as exc:  # defensive: never kill the worker loop
                print(f"[TaskManager] Worker error: {exc}")
                task.status = "failed"
                task.error = str(exc)
                task.status_message = f"Lỗi: {str(exc)[:120]}"
                self.save()
            finally:
                queue.task_done()
            await asyncio.sleep(0.2)

    async def _process_task(self, task: RenderTask, engine: MuseEngine, cfg):
        mode_lower = (task.mode or "").strip().lower()
        is_text_image = mode_lower == "text-to-image"

        # Allocate active Muse account from pool
        account = account_manager.get_next_account(mode=cfg.rotation_mode)
        if account:
            account_manager.ensure_account_state(account)

        task.status = "running"
        task.progress = 5
        task.error = None
        if account:
            task.account_id = account.id
            task.account_email = account.email
            task.status_message = f"Đang gửi tới tài khoản Muse: {account.email}..."
        else:
            task.status_message = "Đang khởi tạo engine tạo ảnh..." if is_text_image else "Đang render bằng engine cục bộ..."
        self.save()

        def progress_cb(pct, msg):
            task.progress = max(0, min(int(pct), 99))
            task.status_message = msg
            self.save()

        try:
            result = await engine.generate_media(
                cookie=account.cookie if account else "",
                state_dir=account.state_dir if account else None,
                prompt=task.prompt,
                negative_prompt=task.negative_prompt,
                mode=task.mode,
                aspect=task.aspect,
                duration=task.duration,
                ref_image_base64=task.ref_image,
                source_image_path=task.source_image_path,
                on_progress=progress_cb,
            )
        except Exception as exc:
            err_str = str(exc)
            if account and not (is_text_image and ("OpenAI" in err_str or "Free engine" in err_str)):
                account_manager.record_usage(account.id, success=False, error=err_str)

            auth_failure = isinstance(exc, MuseAuthError) or "401" in err_str
            if account and cfg.auto_failover:
                alt = account_manager.get_next_account(mode=cfg.rotation_mode)
                if alt and alt.id != account.id:
                    task.status = "pending"
                    task.progress = 0
                    task.account_id = None
                    task.account_email = None
                    task.status_message = (
                        f"Tài khoản lỗi ({err_str[:40]}). Đang chuyển sang {alt.email}..."
                    )
                    self.save()
                    self._enqueue(task.id)
                    return
                if auth_failure:
                    task.status_message = "Tất cả tài khoản Muse đều hết hạn — thử lại sau."
            task.status = "failed"
            task.error = err_str
            task.status_message = f"Lỗi: {err_str[:120]}"
            self._mark_shot_failed(task)
            self.save()
            return

        task.status = "completed"
        task.progress = 100
        task.result_url = result.get("url")
        task.local_file = result.get("local_path")
        task.completed_at = datetime.now().isoformat()
        task.status_message = "Hoàn thành!"
        if account:
            account_manager.record_usage(account.id, success=True)

        self._sync_result_to_project(task, result)
        self.save()

    # ------------------------------------------------------------------
    # Project sync
    # ------------------------------------------------------------------
    def _sync_result_to_project(self, task: RenderTask, result: Dict[str, Any]):
        if not task.project_id:
            return
        try:
            if task.shot_id:
                project_manager.update_shot(task.project_id, task.shot_id, {
                    "status": "ready",
                    "video_url": result.get("url"),
                    "local_path": result.get("local_path"),
                    "camera_motion": result.get("camera_motion"),
                    "rendered_at": datetime.now().isoformat(),
                })
            elif "image" in (task.mode or ""):
                project_manager.add_image(task.project_id, {
                    "prompt": task.prompt,
                    "url": result.get("url"),
                    "local_path": result.get("local_path"),
                    "aspect": result.get("aspect", task.aspect),
                    "width": result.get("width"),
                    "height": result.get("height"),
                    "provider": result.get("provider"),
                    "watermark_stripped": result.get("watermark_stripped", False),
                })
        except Exception as exc:
            print(f"[TaskManager] Error syncing project task: {exc}")

    def _mark_shot_failed(self, task: RenderTask):
        if task.project_id and task.shot_id:
            try:
                project_manager.update_shot(task.project_id, task.shot_id, {"status": "failed"})
            except Exception:
                pass


task_manager = TaskManager()
