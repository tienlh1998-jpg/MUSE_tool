import os
import json
import uuid
import asyncio
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from core.config import AppConfig, load_config
from core.account_manager import account_manager
from core.muse_engine import MuseEngine

TASKS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tasks.json")

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
    def __init__(self):
        self.tasks: List[RenderTask] = []
        self._queue = asyncio.Queue()
        self._running = False
        self._workers = []
        self.load()

    def load(self):
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.tasks = [RenderTask(**item) for item in data]
            except Exception as e:
                print(f"[TaskManager] Error loading tasks: {e}")
                self.tasks = []
        else:
            self.tasks = []

    def save(self):
        os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump([t.model_dump() for t in self.tasks], f, indent=2, ensure_ascii=False)

    def add_tasks_bulk(self, task_items: List[Dict[str, Any]]) -> List[RenderTask]:
        now = datetime.now().isoformat()
        new_tasks = []
        for item in task_items:
            task = RenderTask(
                id=uuid.uuid4().hex[:10],
                project_id=item.get("project_id"),
                shot_id=item.get("shot_id"),
                prompt=item.get("prompt", "").strip(),
                negative_prompt=item.get("negative_prompt", "").strip(),
                mode=item.get("mode", "text-to-video"),
                aspect=item.get("aspect", "16:9"),
                duration=item.get("duration", 7),
                ref_image=item.get("ref_image"),
                source_image_path=item.get("source_image_path"),
                created_at=now
            )
            self.tasks.append(task)
            new_tasks.append(task)
            self._queue.put_nowait(task.id)

        self.save()
        return new_tasks

    def get_task(self, task_id: str) -> Optional[RenderTask]:
        return next((t for a in self.tasks if (t := a).id == task_id), None)

    def clear_all(self):
        self.tasks = []
        self.save()

    async def start_workers(self, cfg: AppConfig):
        if self._running:
            return
        self._running = True
        concurrency = max(1, min(cfg.concurrency, 10))
        for _ in range(concurrency):
            w = asyncio.create_task(self._worker_loop(cfg))
            self._workers.append(w)

    async def _worker_loop(self, cfg: AppConfig):
        engine = MuseEngine(cfg)
        while self._running:
            task_id = await self._queue.get()
            task = self.get_task(task_id)
            if not task or task.status == "completed":
                self._queue.task_done()
                continue

            account = account_manager.get_next_account(mode=cfg.rotation_mode)
            if not account:
                task.status = "failed"
                task.error = "Không có tài khoản Muse nào khả dụng (hết lượt hoặc chưa thêm cookie)"
                task.status_message = "Thất bại: Không có tài khoản"
                self.save()
                self._queue.task_done()
                await asyncio.sleep(2)
                continue

            task.status = "running"
            task.progress = 10
            task.account_id = account.id
            task.account_email = account.email
            task.status_message = f"Đang gửi tới tài khoản: {account.email}..."
            self.save()

            def progress_cb(pct, msg):
                task.progress = pct
                task.status_message = msg
                self.save()

            try:
                result = await engine.generate_media(
                    cookie=account.cookie,
                    prompt=task.prompt,
                    negative_prompt=task.negative_prompt,
                    mode=task.mode,
                    aspect=task.aspect,
                    duration=task.duration,
                    ref_image_base64=task.ref_image,
                    source_image_path=task.source_image_path,
                    on_progress=progress_cb
                )

                task.status = "completed"
                task.progress = 100
                task.result_url = result.get("url")
                task.local_file = result.get("local_path")
                task.completed_at = datetime.now().isoformat()
                task.status_message = "Hoàn thành!"
                account_manager.record_usage(account.id, success=True)

                # Sync back to project shot or image if project_id is given
                if task.project_id:
                    try:
                        from core.project_manager import ProjectManager
                        pm = ProjectManager()
                        if task.shot_id:
                            pm.update_shot(task.project_id, task.shot_id, {
                                "status": "completed",
                                "video_url": task.result_url,
                                "local_path": task.local_file
                            })
                        elif "image" in task.mode:
                            pm.add_image(task.project_id, {
                                "prompt": task.prompt,
                                "url": task.result_url,
                                "local_path": task.local_file,
                                "aspect": task.aspect
                            })
                    except Exception as pe:
                        print(f"Error syncing project task: {pe}")

            except Exception as e:
                err_str = str(e)
                account_manager.record_usage(account.id, success=False, error=err_str)
                
                if cfg.auto_failover:
                    alt_account = account_manager.get_next_account(mode=cfg.rotation_mode)
                    if alt_account and alt_account.id != account.id:
                        task.status_message = f"Tài khoản lỗi ({err_str[:40]}). Đang tự động đổi sang {alt_account.email}..."
                        self.save()
                        self._queue.put_nowait(task.id)
                        self._queue.task_done()
                        continue

                task.status = "failed"
                task.error = err_str
                task.status_message = f"Lỗi: {err_str[:100]}"
                if task.project_id and task.shot_id:
                    try:
                        from core.project_manager import ProjectManager
                        pm = ProjectManager()
                        pm.update_shot(task.project_id, task.shot_id, {"status": "failed"})
                    except Exception:
                        pass

            self.save()
            self._queue.task_done()
            await asyncio.sleep(1)

task_manager = TaskManager()
