"""FFmpeg-based video concatenation and MV finalisation.

Clips rendered by the engine are already 1080p/30fps, but user uploads or
older renders may differ.  The stitcher therefore normalises every input
(scale + pad + fps + SAR) before concatenating, which avoids the classic
"non-monotonous DTS" / "parameters do not match" concat failures.

Audio handling:
* music longer than the picture -> the picture is looped to match the song
  (a full MV never ends before the music);
* music shorter than the picture -> the audio is padded with silence so the
  final cut keeps every rendered shot.
"""

import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import imageio_ffmpeg


class VideoStitcher:
    def __init__(self, downloads_dir: str):
        self.downloads_dir = downloads_dir
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        os.makedirs(self.downloads_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def stitch_videos(
        self,
        video_paths: List[str],
        audio_path: Optional[str] = None,
        output_filename: Optional[str] = None,
        target_size: Optional[Tuple[int, int]] = None,
    ) -> Dict[str, Any]:
        if not video_paths:
            raise ValueError("Không có video nào trong danh sách để ghép!")

        valid_videos: List[str] = []
        for path in video_paths:
            resolved = self._resolve(path)
            if resolved:
                valid_videos.append(resolved)

        if not valid_videos:
            raise ValueError("Không tìm thấy các file video hợp lệ trên ổ cứng!")

        if not output_filename:
            output_filename = f"Full_MV_stitched_{int(time.time())}.mp4"
        output_path = os.path.join(self.downloads_dir, output_filename)

        width, height = target_size or self._detect_size(valid_videos[0])
        fps = 30

        joined_path = output_path
        temp_joined = None
        resolved_audio = self._resolve(audio_path) if audio_path else None
        if resolved_audio and os.path.exists(resolved_audio):
            temp_joined = os.path.join(
                self.downloads_dir, f".join_{os.getpid()}_{abs(hash(tuple(valid_videos))) % 100000}.mp4"
            )
            joined_path = temp_joined

        try:
            self._concat_normalised(valid_videos, joined_path, width, height, fps)
            duration = self._probe_duration(joined_path)

            if resolved_audio and os.path.exists(resolved_audio):
                self._mux_audio(joined_path, resolved_audio, output_path)
                duration = self._probe_duration(output_path)
        finally:
            if temp_joined and os.path.exists(temp_joined):
                try:
                    os.remove(temp_joined)
                except Exception:
                    pass

        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            raise RuntimeError("Không tạo được file MV hoàn chỉnh.")

        return {
            "success": True,
            "output_filename": output_filename,
            "output_path": output_path,
            "url": f"/downloads/{output_filename}",
            "shot_count": len(valid_videos),
            "duration": round(duration, 2),
            "width": width,
            "height": height,
            "has_audio": bool(resolved_audio and os.path.exists(resolved_audio)),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _resolve(self, path: str) -> Optional[str]:
        if not path:
            return None
        if os.path.exists(path):
            return path
        candidate = os.path.join(self.downloads_dir, os.path.basename(path))
        if os.path.exists(candidate):
            return candidate
        if path.startswith("/downloads/"):
            rel = path[len("/downloads/"):]
            candidate = os.path.join(self.downloads_dir, *rel.split("/"))
            if os.path.exists(candidate):
                return candidate
        return None

    def _detect_size(self, video_path: str) -> Tuple[int, int]:
        info = self._probe_stream(video_path)
        width = int(info.get("width") or 1920)
        height = int(info.get("height") or 1080)
        # Keep even dimensions for H.264.
        if width % 2:
            width -= 1
        if height % 2:
            height -= 1
        # Cap at 1080p-class output to keep stitching fast.
        if width > 1920:
            ratio = 1920 / width
            width, height = 1920, int(height * ratio) // 2 * 2
        return max(width, 2), max(height, 2)

    def _concat_normalised(
        self,
        videos: List[str],
        output_path: str,
        width: int,
        height: int,
        fps: int,
    ) -> None:
        cmd = [self.ffmpeg_exe, "-y"]
        for video in videos:
            cmd.extend(["-i", video])

        filters = []
        labels = []
        for idx in range(len(videos)):
            filters.append(
                f"[{idx}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},"
                f"format=yuv420p[v{idx}]"
            )
            labels.append(f"[v{idx}]")
        filters.append(f"{''.join(labels)}concat=n={len(videos)}:v=1:a=0[outv]")

        cmd.extend([
            "-filter_complex", ";".join(filters),
            "-map", "[outv]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",
            output_path,
        ])
        self._run(cmd, timeout=900)

    def _mux_audio(self, video_path: str, audio_path: str, output_path: str) -> None:
        video_duration = self._probe_duration(video_path)
        audio_duration = self._probe_duration(audio_path)

        if audio_duration > video_duration + 0.15:
            # Loop the picture so the MV covers the whole song.
            cmd = [
                self.ffmpeg_exe, "-y",
                "-stream_loop", "-1", "-i", video_path,
                "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                "-movflags", "+faststart",
                output_path,
            ]
        else:
            # Audio is shorter: pad it so no rendered shot is cut off.
            cmd = [
                self.ffmpeg_exe, "-y",
                "-i", video_path,
                "-i", audio_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-af", "apad",
                "-shortest",
                "-movflags", "+faststart",
                output_path,
            ]
        self._run(cmd, timeout=900)

    def _run(self, cmd: List[str], timeout: int = 600):
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout
        )
        if result.returncode != 0:
            raise RuntimeError("FFmpeg lỗi: " + (result.stderr or "")[-800:])

    def _probe_duration(self, media_path: str) -> float:
        if not os.path.exists(media_path):
            return 0.0
        cmd = [self.ffmpeg_exe, "-i", media_path]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr or "")
        if not match:
            return 0.0
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    def _probe_stream(self, media_path: str) -> Dict[str, Any]:
        cmd = [self.ffmpeg_exe, "-i", media_path]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60
        )
        text = result.stderr or ""
        match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", text)
        if not match:
            return {}
        return {"width": int(match.group(1)), "height": int(match.group(2))}
