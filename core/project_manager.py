"""Project persistence layer.

Projects are stored as a single JSON document under ``<data>/projects.json``.
All mutations are serialised with a re-entrant lock because FastAPI serves
requests from a thread-pool while the task workers run on the event loop.
"""

import json
import os
import shutil
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from core.config import DATA_DIR, DOWNLOADS_DIR


class ProjectManager:
    def __init__(
        self,
        data_file: Optional[str] = None,
        media_dir: Optional[str] = None,
    ):
        self.data_file = data_file or os.path.join(DATA_DIR, "projects.json")
        self.media_dir = media_dir or DOWNLOADS_DIR
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        os.makedirs(self.media_dir, exist_ok=True)
        self._lock = threading.RLock()
        self.projects: Dict[str, Dict[str, Any]] = self._load()
        if not self.projects:
            self._init_default_project()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                changed = False
                for project in data.values():
                    changed |= self._normalise_project_paths(project)
                if changed:
                    self.projects = data
                    self._save()
                return data
            except Exception as exc:
                print(f"[ProjectManager] Load error: {exc}")
        return {}

    def _normalise_project_paths(self, project: Dict[str, Any]) -> bool:
        """Repair absolute paths left over from the pre-V3.1 downloads folder."""
        changed = False

        def fix(value: Optional[str]) -> Optional[str]:
            nonlocal changed
            if not value or not isinstance(value, str):
                return value
            if not os.path.isabs(value):
                return value
            if os.path.exists(value):
                return value
            name = os.path.basename(value)
            for candidate in (
                os.path.join(self.media_dir, name),
                os.path.join(self.media_dir, "images", name),
            ):
                if os.path.exists(candidate):
                    changed = True
                    return candidate
            return value

        for image in project.get("images", []):
            fixed = fix(image.get("local_path"))
            if fixed != image.get("local_path"):
                image["local_path"] = fixed
        for shot in project.get("shots", []):
            fixed = fix(shot.get("local_path"))
            if fixed != shot.get("local_path"):
                shot["local_path"] = fixed
        for key in ("audio_path", "final_video_path"):
            fixed = fix(project.get(key))
            if fixed != project.get(key):
                project[key] = fixed
        return changed

    def _save(self):
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        tmp_path = self.data_file + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.projects, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.data_file)

    def reload(self):
        """Re-read projects.json (used after an external process wrote it)."""
        with self._lock:
            self.projects = self._load()

    def _init_default_project(self):
        default_id = "proj_default_01"
        self.projects[default_id] = {
            "id": default_id,
            "name": "Ngày Chưa Giông Bão (MV Cinematic)",
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "audio_filename": None,
            "audio_path": None,
            "lyrics": (
                "[Chorus] Mùa đông ơi rơi xích lòng bàn tay thì em sưởi ấm tim anh...\n"
                "Nỗi niềm thôi miên giọt sương tan trong ánh mắt em.\n"
                "Lời hẹn ước xưa như đóa hoa tàn mộng theo thời gian.\n"
                "[Verse 1] Có những ngày biển lặng không một gợn sóng rồi bão về.\n"
                "Là những ngày bão trước cơn giông bão ngập tràn hôn hoàng."
            ),
            "aspect": "16:9",
            "images": [],
            "shots": [],
            "final_video_url": None,
        }
        self._save()

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------
    def list_projects(self) -> List[Dict[str, Any]]:
        with self._lock:
            return sorted(
                list(self.projects.values()),
                key=lambda x: x.get("created_at", ""),
                reverse=True,
            )

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.projects.get(project_id)

    def create_project(
        self,
        name: str,
        lyrics: str = "",
        audio_filename: Optional[str] = None,
        audio_path: Optional[str] = None,
        aspect: str = "16:9",
    ) -> Dict[str, Any]:
        pid = f"proj_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        proj = {
            "id": pid,
            "name": (name or "").strip() or "Dự Án Mới",
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "audio_filename": audio_filename,
            "audio_path": audio_path,
            "lyrics": lyrics or "",
            "aspect": aspect or "16:9",
            "images": [],
            "shots": [],
            "final_video_url": None,
        }
        with self._lock:
            self.projects[pid] = proj
            self._save()
        return proj

    def delete_project(self, project_id: str) -> bool:
        with self._lock:
            if project_id not in self.projects:
                return False
            del self.projects[project_id]
            self._save()
            return True

    def set_final_video(self, project_id: str, video_url: str, local_path: Optional[str] = None):
        with self._lock:
            proj = self.projects.get(project_id)
            if proj:
                proj["final_video_url"] = video_url
                if local_path:
                    proj["final_video_path"] = local_path
                self._save()

    def update_audio(self, project_id: str, audio_filename: Optional[str], audio_path: Optional[str]):
        with self._lock:
            proj = self.projects.get(project_id)
            if proj:
                proj["audio_filename"] = audio_filename
                proj["audio_path"] = audio_path
                self._save()

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------
    def add_image(self, project_id: str, image_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            proj = self.projects.get(project_id)
            if not proj:
                raise KeyError("Project not found")
            image_data = dict(image_data)
            image_data.setdefault("id", f"img_{int(time.time())}_{uuid.uuid4().hex[:4]}")
            image_data.setdefault("created_at", time.strftime("%Y-%m-%d %H:%M"))
            proj.setdefault("images", []).append(image_data)
            self._save()
            return image_data

    def get_image(self, project_id: str, image_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            proj = self.projects.get(project_id)
            if not proj:
                return None
            return next((i for i in proj.get("images", []) if i.get("id") == image_id), None)

    def delete_image(self, project_id: str, image_id: str, delete_file: bool = False) -> bool:
        with self._lock:
            proj = self.projects.get(project_id)
            if not proj:
                return False
            images = proj.get("images", [])
            target = next((i for i in images if i.get("id") == image_id), None)
            if not target:
                return False
            proj["images"] = [i for i in images if i.get("id") != image_id]
            self._save()

        if delete_file:
            local_path = target.get("local_path")
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass
        return True

    # ------------------------------------------------------------------
    # Shots
    # ------------------------------------------------------------------
    def add_shot(self, project_id: str, shot_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            proj = self.projects.get(project_id)
            if not proj:
                raise KeyError("Project not found")
            shots = proj.setdefault("shots", [])
            shot_data = dict(shot_data)
            shot_data.setdefault("id", f"shot_{int(time.time())}_{uuid.uuid4().hex[:4]}")
            if "shot_number" not in shot_data:
                shot_data["shot_number"] = len(shots) + 1
            shot_data.setdefault("status", "pending")
            shot_data.setdefault("video_url", None)
            shots.append(shot_data)
            self._save()
            return shot_data

    def get_shot(self, project_id: str, shot_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            proj = self.projects.get(project_id)
            if not proj:
                return None
            return next((s for s in proj.get("shots", []) if s.get("id") == shot_id), None)

    def update_shot(
        self, project_id: str, shot_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            proj = self.projects.get(project_id)
            if not proj:
                return None
            for shot in proj.get("shots", []):
                if shot.get("id") == shot_id:
                    shot.update(updates)
                    self._save()
                    return shot
        return None

    def delete_shot(self, project_id: str, shot_id: str) -> bool:
        with self._lock:
            proj = self.projects.get(project_id)
            if not proj:
                return False
            shots = proj.get("shots", [])
            remaining = [s for s in shots if s.get("id") != shot_id]
            if len(remaining) == len(shots):
                return False
            proj["shots"] = remaining
            for idx, shot in enumerate(proj["shots"]):
                shot["shot_number"] = idx + 1
            self._save()
            return True

    def ordered_shot_videos(self, project_id: str) -> List[Dict[str, Any]]:
        """Return completed shots sorted by shot_number with a readable path."""
        proj = self.get_project(project_id)
        if not proj:
            return []
        shots = sorted(proj.get("shots", []), key=lambda s: s.get("shot_number", 0))
        result = []
        for shot in shots:
            if shot.get("status") not in ("completed", "ready"):
                continue
            local = shot.get("local_path")
            if not local or not os.path.exists(local):
                local = self.resolve_media_path(shot.get("video_url"))
            if local and os.path.exists(local):
                result.append({**shot, "resolved_path": local})
        return result

    def resolve_media_path(self, url_or_path: Optional[str]) -> Optional[str]:
        """Resolve a ``/downloads/...`` URL or absolute path to a local file."""
        if not url_or_path:
            return None
        value = str(url_or_path).strip()
        if os.path.isabs(value):
            return value if os.path.exists(value) else None
        if value.startswith("/downloads/"):
            rel = value[len("/downloads/"):]
            candidate = os.path.join(self.media_dir, *rel.split("/"))
        elif value.startswith("downloads/"):
            rel = value[len("downloads/"):]
            candidate = os.path.join(self.media_dir, *rel.split("/"))
        else:
            candidate = os.path.join(self.media_dir, os.path.basename(value))
        return candidate if os.path.exists(candidate) else None

    def copy_media_into_project(self, project_id: str, source_path: str) -> Optional[str]:
        """Copy an external media file into the downloads folder (utility)."""
        if not source_path or not os.path.exists(source_path):
            return None
        os.makedirs(self.media_dir, exist_ok=True)
        dest = os.path.join(self.media_dir, os.path.basename(source_path))
        if os.path.abspath(source_path) != os.path.abspath(dest):
            shutil.copy2(source_path, dest)
        return dest


# Shared singleton: the API layer and the background workers must mutate the
# same in-memory document, otherwise one instance overwrites the other's writes.
project_manager = ProjectManager()
