"""Cinematic media engine.

The engine renders real MP4 files locally with FFmpeg:

* ``image-to-video`` animates a source image with a camera move inferred from
  the prompt (dolly/zoom/pan) and encodes 1080p H.264/yuv420p at 30 FPS.
* ``text-to-video`` first generates a genuine keyframe through
  :class:`core.image_engine.ImageEngine`, then animates it.  There is no
  solid-colour placeholder path anymore.
* ``text-to-image`` delegates to the image engine and returns a real PNG.

A Muse AI session ping is performed when a real session cookie is available so
expired accounts fail over quickly; unreachable sessions fall back to local
rendering instead of blocking the queue.
"""

import asyncio
import base64
import io
import json
import os
import re
import subprocess
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
import imageio_ffmpeg
from PIL import Image, ImageOps

from core.config import AppConfig
from core.image_engine import ImageEngine, ImageGenerationError, normalise_aspect

# Global mutex lock to strictly serialize Muse AI calls per account
_MUSE_ACCOUNT_LOCK: Optional[asyncio.Lock] = None
_PROJECT_MUSE_SESSIONS: Dict[str, str] = {}
_SESSION_SEEN_IMAGE_IDS: Dict[str, set] = {}


def _get_muse_account_lock() -> asyncio.Lock:
    global _MUSE_ACCOUNT_LOCK
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    if _MUSE_ACCOUNT_LOCK is None or getattr(_MUSE_ACCOUNT_LOCK, "_loop", None) != current_loop:
        _MUSE_ACCOUNT_LOCK = asyncio.Lock()
    return _MUSE_ACCOUNT_LOCK


def get_or_create_muse_session(project_id: Optional[str] = None) -> str:
    key = (project_id or "").strip() or "muse_studio_main"
    if key not in _PROJECT_MUSE_SESSIONS:
        _PROJECT_MUSE_SESSIONS[key] = str(uuid.uuid4())
    return _PROJECT_MUSE_SESSIONS[key]


def reset_muse_session(project_id: Optional[str] = None) -> str:
    key = (project_id or "").strip() or "muse_studio_main"
    _PROJECT_MUSE_SESSIONS[key] = str(uuid.uuid4())
    return _PROJECT_MUSE_SESSIONS[key]


class MuseAuthError(Exception):
    """The provided Muse session cookie is expired/invalid (HTTP 401)."""


# Output resolution for each aspect ratio (even dimensions required by H.264).
VIDEO_SIZES: Dict[str, Tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
}

_ZOOM_IN_WORDS = (
    "dolly", "zoom in", "push in", "push-in", "tiến lại", "cận cảnh",
    "phóng to", "zoom-in", "approach", "closer",
)
_ZOOM_OUT_WORDS = (
    "pull back", "pull-back", "zoom out", "zoom-out", "toàn cảnh",
    "lùi lại", "kéo ra", "reveal", "wider",
)
_PAN_WORDS = (
    "pan", "lướt", "mist", "walk", "đi bộ", "lia máy", "trượt",
    "tracking", "drift", "glide", "sweep",
)
_PAN_LEFT_WORDS = ("pan left", "lướt trái", "sang trái", "left to right", "trái sang phải")


def _looks_like_muse_cookie(cookie: str) -> bool:
    """Real Muse session cookies are long JWT-style values.

    Short placeholder cookies (used by tests or fresh installs) skip the
    network ping so local rendering is never blocked by an unreachable site.
    """
    value = (cookie or "").strip()
    return len(value) >= 60 and ("hatch" in value or "sess" in value or value.count(".") >= 2)


def detect_camera_motion(prompt: str) -> str:
    """Map prompt keywords to a cinematic camera move.

    Returns one of ``zoom_in``, ``zoom_out``, ``pan_left``, ``pan_right``,
    ``pan_up``, ``pan_down``.
    """
    text = (prompt or "").lower()

    if any(word in text for word in _ZOOM_OUT_WORDS):
        return "zoom_out"
    if any(word in text for word in _ZOOM_IN_WORDS):
        return "zoom_in"
    if any(word in text for word in _PAN_WORDS):
        # A left-to-right pan is the most natural "walk/tracking" move.
        if any(word in text for word in _PAN_LEFT_WORDS):
            return "pan_left"
        return "pan_right"
    if any(word in text for word in ("tilt up", "ngước lên", "hướng lên")):
        return "pan_up"
    if any(word in text for word in ("tilt down", "cúi xuống", "hướng xuống")):
        return "pan_down"
    return "zoom_in"


def sanitize_muse_video_prompt(prompt: str) -> str:
    """Extract and compact video motion prompt into clean English cinema directives for Muse AI WebSocket."""
    p = re.sub(r'^(?:Lời nhắc|Shot|Phân cảnh|Mô tả|Kịch bản|Cảnh)[^:\n]*:\s*', '', prompt.strip(), flags=re.IGNORECASE)
    sentences = re.split(r'[.\n]+', p)
    english_sentences = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        ascii_chars = sum(1 for c in s_clean if ord(c) < 128)
        ratio = ascii_chars / len(s_clean) if len(s_clean) > 0 else 0
        if ratio > 0.8:
            english_sentences.append(s_clean)
            
    if english_sentences:
        core = '. '.join(english_sentences)
    else:
        core = p
        
    core = re.sub(r'\b(8k resolution|photorealistic masterpiece|hyper-realistic)\b', '', core, flags=re.IGNORECASE)
    core = re.sub(r'\s+', ' ', core).strip(' ,.')
    if len(core) > 320:
        cut_idx = core.rfind(' ', 0, 315)
        core = (core[:cut_idx] if cut_idx > 100 else core[:315]) + '.'
    return core


class MuseEngine:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.image_engine = ImageEngine(cfg)
        self.downloads_dir = cfg.download_dir
        os.makedirs(self.downloads_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def generate_media(
        self,
        cookie: str,
        prompt: str,
        negative_prompt: str = "",
        mode: str = "text-to-video",
        aspect: str = "16:9",
        duration: int = 7,
        ref_image_base64: Optional[str] = None,
        source_image_path: Optional[str] = None,
        ref_images: Optional[List[str]] = None,
        state_dir: Optional[str] = None,
        project_id: Optional[str] = None,
        on_progress=None,
    ) -> Dict[str, Any]:
        aspect = normalise_aspect(aspect)
        duration = max(1, min(int(duration or 7), 30))
        mode = (mode or "text-to-video").lower()

        def report(pct: int, msg: str):
            if on_progress:
                on_progress(pct, msg)

        has_session = bool((state_dir and os.path.exists(state_dir)) or (cookie and _looks_like_muse_cookie(cookie)))

        if has_session:
            report(8, "Đang kiểm tra phiên Muse AI...")
            if cookie and _looks_like_muse_cookie(cookie):
                await self._check_muse_session(cookie)
        else:
            report(8, "Không có phiên Muse — dùng engine render cục bộ...")

        if mode in ("text-to-image", "image-to-image"):
            # Gather all reference image candidates (Character Lock, Set Lock, Master References)
            candidate_refs = []
            if ref_images:
                candidate_refs.extend(ref_images)
            for single_ref in (ref_image_base64, source_image_path):
                if single_ref and single_ref not in candidate_refs:
                    candidate_refs.append(single_ref)

            resolved_ref_paths = []
            for r in candidate_refs:
                p = await self._resolve_image_to_local_path(r)
                if p and os.path.exists(p) and p not in resolved_ref_paths:
                    resolved_ref_paths.append(p)

            # Priority 1: Muse AI direct image generation via WebSocket
            if has_session:
                report(25, "Đang tạo ảnh chất lượng cao từ tài khoản Muse AI qua WebSocket...")
                muse_img = await self._try_generate_image_with_muse(
                    cookie=cookie,
                    state_dir=state_dir,
                    prompt=prompt,
                    aspect=aspect,
                    ref_images=resolved_ref_paths if resolved_ref_paths else None,
                    project_id=project_id,
                    report=report,
                )
                if muse_img:
                    report(100, "Đã tạo ảnh từ Muse AI hoàn tất!")
                    return muse_img

            report(30, "Đang tạo ảnh qua image engine dự phòng...")
            ref_data = ref_image_base64 or source_image_path
            try:
                result = await self.image_engine.generate_image(
                    prompt=prompt,
                    aspect=aspect,
                    negative_prompt=negative_prompt,
                    ref_image_base64=ref_data,
                    on_progress=lambda p, m: report(30 + int(p * 0.65), m),
                )
                report(100, "Đã tạo ảnh hoàn tất!")
                return result
            except Exception as fb_exc:
                if has_session:
                    detail = getattr(self, "_last_muse_error", None)
                    detail_suffix = f" [Muse: {detail}]" if detail else ""
                    raise RuntimeError(
                        f"Máy chủ Muse AI chưa trả kết quả ảnh sau thời gian chờ (180s){detail_suffix} và kênh dự phòng không khả dụng ({fb_exc}). "
                        f"Vui lòng bấm 'Tạo lại' để Muse AI tiếp tục kết xuất!"
                    ) from fb_exc
                raise

        # ---------------- Video modes ----------------
        # 1. Resolve source image path if directly specified or uploaded
        source_path = None
        candidate = (source_image_path or "").strip()
        if candidate:
            source_path = await self._resolve_image_to_local_path(candidate)
        if not source_path and ref_image_base64:
            source_path = await self._resolve_image_to_local_path(ref_image_base64)

        # 2. Render directly with Muse AI (one single request, native text-to-video or image-to-video)
        muse_video_path = None
        if has_session:
            report(45, "Đang kết nối WebSocket tạo video từ máy chủ Muse AI...")
            muse_video_path = await self._try_render_with_muse(
                cookie=cookie,
                state_dir=state_dir,
                prompt=prompt,
                source_image=source_path,
                ref_images=ref_images or ([ref_image_base64] if ref_image_base64 and ref_image_base64 != source_path else None),
                project_id=project_id,
                report=report,
            )

        if muse_video_path and os.path.exists(muse_video_path) and os.path.getsize(muse_video_path) > 1024:
            filename = os.path.basename(muse_video_path)
            local_path = muse_video_path
            motion = "muse_ai_native"
            report(100, "Đã nhận video từ Muse AI hoàn tất!")
        else:
            if getattr(self.cfg, "strict_ai_video", False) and has_session:
                raise RuntimeError("Máy chủ Muse AI không thể render video cho shot này (quá tải hoặc timeout). Vui lòng bấm 'Tạo lại' để Muse AI sinh video chuyển động thật!")
            motion = detect_camera_motion(prompt)
            report(55, f"Đang render chuyển động camera ({motion})...")

            # Local FFmpeg requires a physical keyframe to pan/zoom
            if not source_path or not os.path.exists(source_path):
                source_path = await self._resolve_source_image(
                    source_image_path=source_image_path,
                    ref_image_base64=ref_image_base64,
                    prompt=prompt,
                    aspect=aspect,
                    cookie=cookie,
                    state_dir=state_dir,
                    report=report,
                )

            filename = f"video_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"
            local_path = os.path.join(self.downloads_dir, filename)
            await asyncio.to_thread(
                self._render_camera_move,
                source_path,
                local_path,
                aspect,
                duration,
                motion,
            )

        if not os.path.exists(local_path) or os.path.getsize(local_path) < 1024:
            raise RuntimeError("FFmpeg không tạo được file video hợp lệ.")

        report(100, "Đã render video hoàn tất!")
        return {
            "status": "completed",
            "filename": filename,
            "local_path": local_path,
            "url": f"/downloads/{filename}",
            "aspect": aspect,
            "duration": duration,
            "width": VIDEO_SIZES[aspect][0],
            "height": VIDEO_SIZES[aspect][1],
            "fps": 30,
            "codec": "h264/yuv420p",
            "camera_motion": motion,
            "source_image": source_path,
        }

    # ------------------------------------------------------------------
    # Source image resolution
    # ------------------------------------------------------------------
    async def _resolve_source_image(
        self,
        source_image_path: Optional[str],
        ref_image_base64: Optional[str],
        prompt: str,
        aspect: str,
        cookie: str = "",
        state_dir: Optional[str] = None,
        report=None,
    ) -> str:
        """Return a local image path for image-to-video rendering."""
        candidate = (source_image_path or "").strip()

        if candidate:
            local = self._to_local_path(candidate)
            if local and os.path.exists(local):
                return local
            if candidate.startswith(("http://", "https://")):
                if report:
                    report(30, "Đang tải ảnh nguồn...")
                downloaded = await self._download_image(candidate)
                if downloaded:
                    return downloaded

        if ref_image_base64:
            if report:
                report(32, "Đang giải mã ảnh tham chiếu...")
            decoded = self._decode_base64_image(ref_image_base64)
            if decoded:
                return decoded

        # Text-to-video: generate a real keyframe first.
        has_session = bool((state_dir and os.path.exists(state_dir)) or (cookie and _looks_like_muse_cookie(cookie)))
        if has_session:
            if report:
                report(28, "Đang tạo keyframe điện ảnh chất lượng cao từ Muse AI...")
            muse_img = await self._try_generate_image_with_muse(
                cookie=cookie,
                state_dir=state_dir,
                prompt=prompt,
                aspect=aspect,
                report=report,
            )
            if muse_img and os.path.exists(muse_img.get("local_path", "")):
                return muse_img["local_path"]

        if report:
            report(28, "Chưa có ảnh nguồn — đang tạo keyframe bằng AI...")
        try:
            result = await self.image_engine.generate_image(
                prompt=prompt,
                aspect=aspect,
                on_progress=lambda p, m: report(28 + int(p * 0.25), m) if report else None,
            )
        except ImageGenerationError as exc:
            raise RuntimeError(
                "Không thể tạo khung hình nguồn cho video: " + str(exc)
            ) from exc
        return result["local_path"]

    def _to_local_path(self, value: str) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        if os.path.isabs(value) and os.path.exists(value):
            return value
        if value.startswith("/downloads/"):
            rel = value[len("/downloads/"):]
            p = os.path.join(self.downloads_dir, *rel.split("/"))
            if os.path.exists(p):
                return p
        if value.startswith("downloads/"):
            rel = value[len("downloads/"):]
            p = os.path.join(self.downloads_dir, *rel.split("/"))
            if os.path.exists(p):
                return p
        maybe = os.path.join(self.downloads_dir, os.path.basename(value))
        if os.path.exists(maybe):
            return maybe
        maybe_img = os.path.join(self.downloads_dir, "images", os.path.basename(value))
        if os.path.exists(maybe_img):
            return maybe_img
        return None

    async def _resolve_image_to_local_path(self, value: Optional[str]) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        if not value:
            return None
        local = self._to_local_path(value)
        if local and os.path.exists(local):
            return local
        if value.startswith(("http://", "https://")):
            return await self._download_image(value)
        if value.startswith("data:") or len(value) > 256:
            return self._decode_base64_image(value)
        return None

    @staticmethod
    def _image_ref_aliases(raw_path: Optional[str], url: Optional[str]) -> set:
        """All stable aliases for a Muse image ref (raw_path, clean url, filename)."""
        aliases = set()
        if raw_path and isinstance(raw_path, str) and raw_path.strip():
            rp = raw_path.strip()
            aliases.add(rp)
            aliases.add(rp.rsplit("/", 1)[-1])
        if url and isinstance(url, str) and url.strip():
            clean_u = url.strip().split("?", 1)[0].split("#", 1)[0]
            if clean_u:
                aliases.add(clean_u)
                aliases.add(clean_u.rsplit("/", 1)[-1])
        return aliases

    @staticmethod
    def _image_ref_identity(raw_path: Optional[str], url: Optional[str]) -> Optional[str]:
        """Stable identity for a Muse image ref across polls (ignores rotating query signatures)."""
        if raw_path and isinstance(raw_path, str) and raw_path.strip():
            return raw_path.strip()
        if url and isinstance(url, str) and url.strip():
            return url.strip().split("?", 1)[0].split("#", 1)[0]
        return None

    @staticmethod
    def _extract_image_refs(events_or_history: Any) -> list:
        """Extract unique (raw_path, url) pairs from Muse events or full history payloads.

        Skips user-authored messages so uploaded reference images are never
        mistaken for Muse-generated outputs.
        """
        found: List[Tuple[Optional[str], Optional[str]]] = []
        seen_keys: set = set()

        def _add(raw_path: Optional[str], url: Optional[str]) -> None:
            rp = raw_path.strip() if isinstance(raw_path, str) and raw_path.strip() else None
            u = url.strip() if isinstance(url, str) and url.strip() else None
            if not rp and not u:
                return
            ident = MuseEngine._image_ref_identity(rp, u)
            if not ident or ident in seen_keys:
                return
            seen_keys.add(ident)
            found.append((rp, u))

        def _is_user_node(node: dict) -> bool:
            role = str(node.get("role") or node.get("sender") or node.get("author") or "").strip().lower()
            if role == "user":
                return True
            ev_name = str(node.get("event_name") or "").strip().lower()
            if ev_name in ("user_message", "user.message", "chat.user_message"):
                return True
            return False

        def _looks_image_path(val: Any) -> bool:
            if not isinstance(val, str):
                return False
            clean = val.lower().split("?", 1)[0].split("#", 1)[0]
            return clean.endswith((".png", ".jpg", ".jpeg", ".webp"))

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                if _is_user_node(node):
                    return
                name = node.get("event_name", "")
                p = node.get("payload", {}) if isinstance(node.get("payload"), dict) else {}

                # 1. Explicit delta.presentation blocks
                if name == "delta.presentation":
                    data_block = p.get("data", {}) if isinstance(p.get("data"), dict) else {}
                    images = data_block.get("images", []) if isinstance(data_block.get("images"), list) else []
                    for img in images:
                        if isinstance(img, dict):
                            raw_path = img.get("path") or img.get("media_path")
                            variants = img.get("variants") if isinstance(img.get("variants"), dict) else {}
                            url = variants.get("original") or img.get("url") or img.get("src")
                            _add(raw_path, url)
                    if p.get("image_path"):
                        ipath = str(p.get("image_path"))
                        raw_p = ipath if ipath.startswith("sandbox://") else f"sandbox://{ipath.lstrip('/')}"
                        _add(raw_p, None)

                # 2. General image item / media object
                kind = str(node.get("kind") or node.get("type") or "").strip().lower()
                mime = str(
                    node.get("mime_type")
                    or node.get("mimeType")
                    or node.get("mime")
                    or node.get("content_type")
                    or ""
                ).strip().lower()
                raw_path = node.get("path") or node.get("media_path") or node.get("image_path")
                variants = node.get("variants") if isinstance(node.get("variants"), dict) else {}
                url = variants.get("original") or node.get("url") or node.get("src")
                if (
                    kind == "image"
                    or mime.startswith("image/")
                    or _looks_image_path(raw_path)
                    or _looks_image_path(url)
                ):
                    if isinstance(raw_path, str) and raw_path and not raw_path.startswith(("sandbox://", "http://", "https://")) and "/" in raw_path:
                        if node.get("image_path") and not node.get("path"):
                            raw_path = f"sandbox://{raw_path.lstrip('/')}"
                    _add(raw_path, url)

                for val in node.values():
                    _walk(val)
            elif isinstance(node, list):
                # Walk in reverse so newest events/messages appear first
                for item in reversed(node):
                    _walk(item)

        _walk(events_or_history)
        return found

    @staticmethod
    def _pick_writable_session_id(sessions_payload: Any) -> Optional[str]:
        """Pick the most recently updated writable Muse session."""
        raw_sessions = (
            sessions_payload.get("result", {}).get("sessions", [])
            if isinstance(sessions_payload, dict)
            else []
        )
        writable = [
            s
            for s in raw_sessions
            if isinstance(s, dict)
            and s.get("can_send_messages") is not False
            and str(s.get("channel") or "").lower() != "whatsapp"
            and isinstance(s.get("session_id"), str)
            and s.get("session_id")
        ]
        writable.sort(key=lambda s: int(s.get("updated_at_ms") or 0), reverse=True)
        return writable[0]["session_id"] if writable else None

    @staticmethod
    def _extract_event_list(events_or_history: Any) -> list:
        if isinstance(events_or_history, list):
            return events_or_history
        if isinstance(events_or_history, dict):
            res = events_or_history.get("result")
            if isinstance(res, dict):
                for key in ("chat_events", "messages", "events"):
                    if isinstance(res.get(key), list):
                        return res[key]
            for key in ("chat_events", "messages", "events"):
                if isinstance(events_or_history.get(key), list):
                    return events_or_history[key]
        return []

    @classmethod
    def _max_seq_and_ts(cls, events_or_history: Any) -> Tuple[int, int]:
        max_seq = 0
        max_ts = 0
        for ev in cls._extract_event_list(events_or_history):
            if not isinstance(ev, dict):
                continue
            p = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            seq = p.get("chat_event_seq") or ev.get("chat_event_seq")
            if isinstance(seq, (int, float)) and int(seq) > max_seq:
                max_seq = int(seq)
            ts = ev.get("occurred_at_ms") or p.get("occurred_at_ms") or p.get("display_text_updated_at_ms")
            if isinstance(ts, (int, float)) and int(ts) > max_ts:
                max_ts = int(ts)
        return max_seq, max_ts

    @classmethod
    def _extract_new_image_refs(
        cls,
        events_or_history: Any,
        baseline_ids: set,
        min_seq: int = 0,
        min_ts: int = 0,
    ) -> list:
        """Extract only NEW non-user image refs created after min_seq / min_ts and not in baseline_ids."""
        events = cls._extract_event_list(events_or_history)
        if not events:
            raw_refs = cls._extract_image_refs(events_or_history)
            return [
                (rp, u)
                for rp, u in raw_refs
                if not (cls._image_ref_aliases(rp, u) & baseline_ids)
            ]

        fresh_events = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            p = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            seq = p.get("chat_event_seq") or ev.get("chat_event_seq")
            ts = ev.get("occurred_at_ms") or p.get("occurred_at_ms") or p.get("display_text_updated_at_ms")
            if min_seq > 0 and isinstance(seq, (int, float)):
                if int(seq) <= min_seq:
                    continue
            elif min_ts > 0 and isinstance(ts, (int, float)):
                if int(ts) <= min_ts:
                    continue
            fresh_events.append(ev)

        raw_refs = cls._extract_image_refs(fresh_events)
        return [
            (rp, u)
            for rp, u in raw_refs
            if not (cls._image_ref_aliases(rp, u) & baseline_ids)
        ]

    async def _download_image(self, url: str) -> Optional[str]:
        try:
            timeout = httpx.Timeout(60.0, connect=15.0)
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, proxy=self.cfg.ai_network_proxy
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200 or not resp.content:
                    return None
                ext = ".png" if "png" in resp.headers.get("content-type", "") else ".jpg"
                name = f"src_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
                path = os.path.join(self.downloads_dir, "images", name)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(resp.content)
                return path
        except Exception as exc:
            print(f"[MuseEngine] Không tải được ảnh nguồn: {exc}")
            return None

    def _decode_base64_image(self, value: str) -> Optional[str]:
        try:
            payload = value.split(",", 1)[-1] if value.startswith("data:") else value
            raw = base64.b64decode(payload)
            name = f"ref_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
            path = os.path.join(self.downloads_dir, "images", name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(raw)
            return path
        except Exception as exc:
            print(f"[MuseEngine] Ảnh tham chiếu base64 không hợp lệ: {exc}")
            return None

    async def _try_generate_image_with_muse(
        self,
        cookie: str,
        state_dir: Optional[str],
        prompt: str,
        aspect: str = "16:9",
        ref_images: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        report=None,
    ) -> Optional[Dict[str, Any]]:
        # Enforce strict serial execution on the Muse account
        lock = _get_muse_account_lock()
        async with lock:
            client = None
            auth = None
            try:
                from core.muse_ai.auth import MuseAuth
                from core.muse_ai.client import MuseClient
                from core.account_manager import cookie_string_to_jar
                from core.config import DATA_DIR
                from core.image_engine import ASPECT_SIZES

                effective_state = state_dir
                if not effective_state or not os.path.exists(effective_state):
                    temp_state = os.path.join(
                        DATA_DIR, "muse_states", f"img_run_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                    )
                    os.makedirs(temp_state, exist_ok=True)
                    cookie_file = os.path.join(temp_state, "cookies.json")
                    jar = cookie_string_to_jar(cookie)
                    with open(cookie_file, "w", encoding="utf-8") as f:
                        json.dump(jar, f, indent=2, ensure_ascii=False)
                    effective_state = temp_state

                auth = MuseAuth(state_dir=effective_state)
                cookie_path = os.path.join(effective_state, "cookies.json")
                if os.path.exists(cookie_path):
                    await auth.load_cookies(cookie_path)

                client = MuseClient(auth=auth, state_dir=effective_state)
                if report:
                    report(30, "Đang kết nối WebSocket Noise tới tài khoản Muse AI...")
                await client.connect()

                # Resolve reference image paths to attach to Muse AI
                valid_ref_paths = []
                if ref_images:
                    for img in ref_images:
                        lp = await self._resolve_image_to_local_path(img)
                        if lp and os.path.exists(lp) and lp not in valid_ref_paths:
                            valid_ref_paths.append(lp)

                if report:
                    if valid_ref_paths:
                        report(38, f"Đang gửi prompt kèm {len(valid_ref_paths)} ảnh tham chiếu gốc tới Muse AI...")
                    else:
                        report(38, "Đang gửi prompt tạo ảnh chất lượng cao tới Muse AI...")

                clean_prompt = prompt.strip()
                self._last_muse_error = None

                # Resolve the active writable Muse session before calling chat_stream so we
                # can snapshot all existing images, max chat_event_seq, and max timestamp.
                from core.muse_ai.media import extract_session_ids
                sessions_before: set = set()
                active_sid: Optional[str] = session_id if session_id else None
                try:
                    sl = await client.sessions_list()
                    sessions_before = set(extract_session_ids(sl))
                    if not active_sid:
                        active_sid = self._pick_writable_session_id(sl)
                except Exception as sl_err:
                    print(f"[MuseEngine] sessions_list skipped: {sl_err}")

                baseline_ids: set = set()
                for seen_set in _SESSION_SEEN_IMAGE_IDS.values():
                    baseline_ids.update(seen_set)
                max_baseline_seq = 0
                max_baseline_ts = 0

                if active_sid:
                    try:
                        baseline_history = await client.history(session_id=active_sid, limit=80)
                        for rp, u in self._extract_image_refs(baseline_history):
                            baseline_ids.update(self._image_ref_aliases(rp, u))
                        max_baseline_seq, max_baseline_ts = self._max_seq_and_ts(baseline_history)
                    except Exception as base_err:
                        print(f"[MuseEngine] Baseline history check skipped: {base_err}")

                # Add clear image generation directive if needed
                if not any(kw in clean_prompt.lower() for kw in ("create", "generate", "render", "photorealistic", "image", "ảnh", "tạo ảnh")):
                    send_prompt = f"Create a photorealistic image: {clean_prompt}"
                else:
                    send_prompt = clean_prompt

                events = await client.chat_stream(
                    prompt=send_prompt,
                    images=valid_ref_paths or None,
                    session_id=active_sid,
                    stream_timeout=45.0,
                )

                resolved_session = (
                    await client._resolve_session_id(active_sid, events, sessions_before)
                    or active_sid
                )
                effective_session = resolved_session or "default"

                def _event_matches_session(ev: Any) -> bool:
                    if not resolved_session or not isinstance(ev, dict):
                        return True
                    ctx = ev.get("chat_context") if isinstance(ev.get("chat_context"), dict) else {}
                    ev_sid = ctx.get("chat_id") or ev.get("session_id")
                    if not ev_sid:
                        return True
                    return ev_sid == resolved_session

                # Check if chat_stream already yielded NEW image presentation events for this session
                session_events = [ev for ev in (events or []) if _event_matches_session(ev)]
                extracted = self._extract_new_image_refs(
                    session_events,
                    baseline_ids=baseline_ids,
                    min_seq=max_baseline_seq,
                    min_ts=max_baseline_ts,
                )

                if not extracted:
                    if report:
                        report(50, "Đang chờ Muse AI kết xuất ảnh độ phân giải cao...")

                    timeout = 180.0  # 3 minutes for high-detail / peak queue renders
                    start_time = time.time()
                    deadline = start_time + timeout
                    while time.time() < deadline:
                        await asyncio.sleep(2.5)
                        elapsed = time.time() - start_time
                        pct = min(88, int(48 + (elapsed / 120.0) * 40))
                        if report:
                            report(pct, f"Đang chờ Muse AI kết xuất ảnh độ phân giải cao ({int(elapsed)}s)...")

                        try:
                            h = await client.history(session_id=resolved_session, limit=60)
                            extracted = self._extract_new_image_refs(
                                h,
                                baseline_ids=baseline_ids,
                                min_seq=max_baseline_seq,
                                min_ts=max_baseline_ts,
                            )
                            if extracted:
                                break
                        except Exception as poll_err:
                            print(f"[MuseEngine] Image poll error: {poll_err}")

                found_image_data = None
                selected_aliases: set = set()
                if extracted:
                    for raw_path, img_url in extracted:
                        if raw_path:
                            if report:
                                report(90, "Đang tải ảnh gốc từ Muse AI qua WebSocket...")
                            try:
                                found_image_data = await client._fs().raw(raw_path)
                            except Exception as fs_err:
                                print(f"[MuseEngine] _fs().raw failed for {raw_path}: {fs_err}")
                                found_image_data = None
                        if not found_image_data and img_url:
                            if report:
                                report(90, "Đang tải ảnh từ đường dẫn Muse CDN...")
                            try:
                                timeout_dl = httpx.Timeout(60.0, connect=15.0)
                                async with httpx.AsyncClient(timeout=timeout_dl, follow_redirects=True, proxy=self.cfg.ai_network_proxy) as hc:
                                    dl_resp = await hc.get(img_url)
                                    if dl_resp.status_code == 200 and dl_resp.content:
                                        found_image_data = dl_resp.content
                            except Exception as dl_err:
                                print(f"[MuseEngine] CDN download failed: {dl_err}")
                        if found_image_data:
                            selected_aliases = self._image_ref_aliases(raw_path, img_url)
                            break

                if selected_aliases:
                    _SESSION_SEEN_IMAGE_IDS.setdefault(effective_session, set()).update(selected_aliases)

                if not found_image_data:
                    print(f"[MuseEngine] Không tìm thấy ảnh trả về từ Muse AI trong 180s.")
                    return None

                if report:
                    report(95, "Đang chuẩn hóa tỷ lệ khung hình...")

                target_size = ASPECT_SIZES.get(aspect, (1280, 720))
                img_obj = Image.open(io.BytesIO(found_image_data))
                if img_obj.mode in ("RGBA", "P"):
                    img_obj = img_obj.convert("RGB")

                img_resized = ImageOps.fit(img_obj, target_size, method=Image.Resampling.LANCZOS)
                filename = f"muse_img_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
                images_dir = os.path.join(self.downloads_dir, "images")
                os.makedirs(images_dir, exist_ok=True)
                local_path = os.path.join(images_dir, filename)
                img_resized.save(local_path, format="PNG", quality=95)

                # Rest briefly to let Muse server finalize before releasing lock
                await asyncio.sleep(2.5)

                return {
                    "status": "completed",
                    "filename": filename,
                    "local_path": local_path,
                    "url": f"/downloads/images/{filename}",
                    "aspect": aspect,
                    "width": target_size[0],
                    "height": target_size[1],
                    "prompt": prompt,
                    "engine": "muse_ai",
                }
            except Exception as exc:
                self._last_muse_error = str(exc)
                print(f"[MuseEngine] Tạo ảnh Muse AI thất bại ({exc}); chuyển sang fallback.")
                return None
            finally:
                if client:
                    try:
                        await client.close()
                    except Exception:
                        pass

    def _resolve_local_media_path(self, path_or_url: str) -> Optional[str]:
        if not path_or_url:
            return None
        if os.path.exists(path_or_url):
            return path_or_url
        if path_or_url.startswith("/downloads/"):
            rel = path_or_url[len("/downloads/"):].lstrip("/\\")
            candidate = os.path.join(self.downloads_dir, rel)
            if os.path.exists(candidate):
                return candidate
        return None

    async def _try_render_with_muse(
        self,
        cookie: str,
        state_dir: Optional[str] = None,
        prompt: str = "",
        source_image: Optional[str] = None,
        ref_images: Optional[List[str]] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        report=None,
    ) -> Optional[str]:
        # Enforce strict serial execution on the Muse account
        lock = _get_muse_account_lock()
        async with lock:
            client = None
            auth = None
            try:
                from core.muse_ai.auth import MuseAuth
                from core.muse_ai.client import MuseClient
                from core.account_manager import cookie_string_to_jar
                from core.config import DATA_DIR

                effective_state = state_dir
                if not effective_state or not os.path.exists(effective_state):
                    temp_state = os.path.join(
                        DATA_DIR, "muse_states", f"run_{int(time.time())}_{uuid.uuid4().hex[:4]}"
                    )
                    os.makedirs(temp_state, exist_ok=True)
                    cookie_file = os.path.join(temp_state, "cookies.json")
                    jar = cookie_string_to_jar(cookie)
                    with open(cookie_file, "w", encoding="utf-8") as f:
                        json.dump(jar, f, indent=2, ensure_ascii=False)
                    effective_state = temp_state

                auth = MuseAuth(state_dir=effective_state)
                cookie_file = os.path.join(effective_state, "cookies.json")
                if os.path.exists(cookie_file):
                    await auth.load_cookies(cookie_file)

                client = MuseClient(auth=auth, state_dir=effective_state)
                if report:
                    report(48, "Đang kết nối WebSocket tạo video từ máy chủ Muse AI...")
                await client.connect()

                if report:
                    report(55, "Đang gửi prompt và ảnh sang Muse AI...")

                images = [source_image] if source_image and os.path.exists(source_image) else []
                if ref_images:
                    for rf in ref_images:
                        if not rf:
                            continue
                        local_rf = self._resolve_local_media_path(rf)
                        if local_rf and os.path.exists(local_rf) and local_rf not in images:
                            images.append(local_rf)
                cleaned_core = sanitize_muse_video_prompt(prompt)
                video_prompt = cleaned_core.strip()
                if images and not any(w in video_prompt.lower() for w in ("animate", "animation", "video")):
                    video_prompt = f"Animate this image into video: {video_prompt}"

                effective_session = session_id or get_or_create_muse_session(project_id)

                res = await asyncio.wait_for(
                    client.generate_video(
                        prompt=video_prompt,
                        images=images,
                        output_dir=self.downloads_dir,
                        session_id=effective_session,
                        timeout=200.0,
                        min_videos=1,
                        download=True,
                    ),
                    timeout=220.0,
                )

                # Rest briefly to let Muse server finalize before releasing lock
                await asyncio.sleep(2.5)

                if res.downloaded and len(res.downloaded) > 0:
                    downloaded_file = str(res.downloaded[0])
                    if os.path.exists(downloaded_file) and os.path.getsize(downloaded_file) > 1024:
                        return downloaded_file
            except Exception as exc:
                print(f"[MuseEngine] MuseClient render không khả dụng ({exc}); chuyển sang fallback cục bộ.")
            finally:
                if client:
                    try:
                        await client.close()
                    except Exception:
                        pass
            return None

    # ------------------------------------------------------------------
    # Muse session
    # ------------------------------------------------------------------
    async def _check_muse_session(self, cookie: str) -> None:
        headers = {
            "Cookie": cookie.strip(),
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        }
        timeout = httpx.Timeout(12.0, connect=6.0)
        try:
            async with httpx.AsyncClient(
                timeout=timeout, proxy=self.cfg.ai_network_proxy
            ) as client:
                resp = await client.get("https://muse.ai/api/session", headers=headers)
        except Exception as exc:
            print(f"[MuseEngine] Không ping được Muse session ({exc}); render cục bộ.")
            return

        if resp.status_code == 401:
            raise MuseAuthError("Phiên Muse hết hạn (401 Unauthorized).")
        if resp.status_code >= 500:
            print(f"[MuseEngine] Muse session HTTP {resp.status_code}; render cục bộ.")

    # ------------------------------------------------------------------
    # FFmpeg camera motion
    # ------------------------------------------------------------------
    def _render_camera_move(
        self,
        source_path: str,
        output_path: str,
        aspect: str,
        duration: int,
        motion: str,
    ) -> None:
        width, height = VIDEO_SIZES[aspect]
        fps = 30
        frames = max(1, duration * fps)

        # Oversample 2x so zoompan always has pixels to move into.
        work_w, work_h = width * 2, height * 2

        if motion == "zoom_in":
            zoom_expr = f"min(1.0+0.25*on/{frames},1.25)"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "zoom_out":
            zoom_expr = f"max(1.25-0.25*on/{frames},1.0)"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "pan_left":
            zoom_expr = "1.15"
            x_expr = f"(iw-iw/zoom)*(1-on/{frames})"
            y_expr = "ih/2-(ih/zoom/2)"
        elif motion == "pan_up":
            zoom_expr = "1.15"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = f"(ih-ih/zoom)*(1-on/{frames})"
        elif motion == "pan_down":
            zoom_expr = "1.15"
            x_expr = "iw/2-(iw/zoom/2)"
            y_expr = f"(ih-ih/zoom)*on/{frames}"
        else:  # pan_right (default pan)
            zoom_expr = "1.15"
            x_expr = f"(iw-iw/zoom)*on/{frames}"
            y_expr = "ih/2-(ih/zoom/2)"

        fade_out_start = max(0.0, duration - 0.5)
        vf = (
            f"scale={work_w}:{work_h}:force_original_aspect_ratio=increase,"
            f"crop={work_w}:{work_h},"
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}'"
            f":d=1:s={width}x{height}:fps={fps},"
            f"setsar=1,"
            f"fade=t=in:st=0:d=0.35,"
            f"fade=t=out:st={fade_out_start:.2f}:d=0.5,"
            f"noise=alls=2:allf=t,"
            f"format=yuv420p"
        )

        cmd = [
            self.ffmpeg_exe, "-y",
            "-loop", "1", "-framerate", str(fps), "-i", source_path,
            "-vf", vf,
            "-t", str(duration),
            "-frames:v", str(frames),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",
            output_path,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(
                "FFmpeg render lỗi: " + (result.stderr or "")[-600:]
            )

    async def download_file(self, url: str, dest_path: str):
        """Download remote media file to a local destination path."""
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        async with httpx.AsyncClient(
            timeout=60.0, follow_redirects=True, proxy=self.cfg.ai_network_proxy
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
            else:
                raise Exception(f"Failed to download media: HTTP {resp.status_code}")
