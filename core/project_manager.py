import os
import json
import uuid
import time
from typing import List, Dict, Any, Optional

class ProjectManager:
    def __init__(self, data_file: str = "data/projects.json", media_dir: str = "data/downloads"):
        self.data_file = data_file
        self.media_dir = media_dir
        os.makedirs(os.path.dirname(data_file), exist_ok=True)
        os.makedirs(media_dir, exist_ok=True)
        self.projects: Dict[str, Dict[str, Any]] = self._load()
        if not self.projects:
            self._init_default_project()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.projects, f, ensure_ascii=False, indent=2)

    def _init_default_project(self):
        default_id = "proj_default_01"
        self.projects[default_id] = {
            "id": default_id,
            "name": "Ngày Chưa Giông Bão (MV Cinematic)",
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "audio_filename": None,
            "audio_path": None,
            "lyrics": "[Chorus] Mùa đông ơi rơi xích lòng bàn tay thì em sưởi ấm tim anh...\nNỗi niềm thôi miên giọt sương tan trong ánh mắt em.\nLời hẹn ước xưa như đóa hoa tàn mộng theo thời gian.\n[Verse 1] Có những ngày biển lặng không một gợn sóng rồi bão về.\nLà những ngày bão trước cơn giông bão ngập tràn hôn hoàng.",
            "aspect": "16:9",
            "images": [
                {
                    "id": "img_01",
                    "prompt": "cinematic portrait of Linh in black trench coat standing under cold night rain, Da Lat street, neon reflection",
                    "url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=800&auto=format&fit=crop&q=80",
                    "aspect": "16:9",
                    "created_at": time.strftime("%Y-%m-%d %H:%M")
                },
                {
                    "id": "img_02",
                    "prompt": "wide establishing shot of dark misty pine forest in Da Lat with morning fog and soft volumetric sunlight",
                    "url": "https://images.unsplash.com/photo-1511497584788-87676104235f?w=800&auto=format&fit=crop&q=80",
                    "aspect": "16:9",
                    "created_at": time.strftime("%Y-%m-%d %H:%M")
                }
            ],
            "shots": [
                {
                    "id": "shot_01",
                    "shot_number": 1,
                    "prompt": "slow forward dolly through dense misty pine forest in Da Lat at dawn, cinematic lighting",
                    "source_image_url": "https://images.unsplash.com/photo-1511497584788-87676104235f?w=800&auto=format&fit=crop&q=80",
                    "mode": "image-to-video",
                    "duration": 7,
                    "status": "ready",
                    "video_url": None
                },
                {
                    "id": "shot_02",
                    "shot_number": 2,
                    "prompt": "slow cinematic push-in on Linh looking into camera under rain, bokeh streetlights background",
                    "source_image_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=800&auto=format&fit=crop&q=80",
                    "mode": "image-to-video",
                    "duration": 7,
                    "status": "ready",
                    "video_url": None
                }
            ],
            "final_video_url": None
        }
        self._save()

    def list_projects(self) -> List[Dict[str, Any]]:
        return sorted(list(self.projects.values()), key=lambda x: x.get("created_at", ""), reverse=True)

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.projects.get(project_id)

    def create_project(
        self,
        name: str,
        lyrics: str = "",
        audio_filename: Optional[str] = None,
        audio_path: Optional[str] = None,
        aspect: str = "16:9"
    ) -> Dict[str, Any]:
        pid = f"proj_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        proj = {
            "id": pid,
            "name": name.strip() or "Dự Án Mới",
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
            "audio_filename": audio_filename,
            "audio_path": audio_path,
            "lyrics": lyrics,
            "aspect": aspect,
            "images": [],
            "shots": [],
            "final_video_url": None
        }
        self.projects[pid] = proj
        self._save()
        return proj

    def delete_project(self, project_id: str) -> bool:
        if project_id in self.projects:
            del self.projects[project_id]
            self._save()
            return True
        return False

    def add_image(self, project_id: str, image_data: Dict[str, Any]) -> Dict[str, Any]:
        proj = self.projects.get(project_id)
        if not proj:
            raise KeyError("Project not found")
        if "id" not in image_data:
            image_data["id"] = f"img_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        if "created_at" not in image_data:
            image_data["created_at"] = time.strftime("%Y-%m-%d %H:%M")
        proj.setdefault("images", []).append(image_data)
        self._save()
        return image_data

    def add_shot(self, project_id: str, shot_data: Dict[str, Any]) -> Dict[str, Any]:
        proj = self.projects.get(project_id)
        if not proj:
            raise KeyError("Project not found")
        shots = proj.setdefault("shots", [])
        if "id" not in shot_data:
            shot_data["id"] = f"shot_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        if "shot_number" not in shot_data:
            shot_data["shot_number"] = len(shots) + 1
        shots.append(shot_data)
        self._save()
        return shot_data

    def update_shot(self, project_id: str, shot_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        proj = self.projects.get(project_id)
        if not proj:
            return None
        for s in proj.get("shots", []):
            if s.get("id") == shot_id:
                s.update(updates)
                self._save()
                return s
        return None

    def delete_shot(self, project_id: str, shot_id: str) -> bool:
        proj = self.projects.get(project_id)
        if not proj:
            return False
        shots = proj.get("shots", [])
        proj["shots"] = [s for s in shots if s.get("id") != shot_id]
        # Re-index shot numbers
        for idx, s in enumerate(proj["shots"]):
            s["shot_number"] = idx + 1
        self._save()
        return True

    def set_final_video(self, project_id: str, video_url: str):
        proj = self.projects.get(project_id)
        if proj:
            proj["final_video_url"] = video_url
            self._save()
