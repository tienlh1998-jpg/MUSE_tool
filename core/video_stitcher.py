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
import uuid
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
        srt_path: Optional[str] = None,
        srt_content: Optional[str] = None,
        output_filename: Optional[str] = None,
        target_size: Optional[Tuple[int, int]] = None,
        burn_subtitles: bool = True,
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

        # Resolve Audio
        resolved_audio = self._resolve(audio_path) if audio_path else None

        # Resolve or prepare Subtitles (.srt)
        resolved_srt = None
        temp_srt_path = None
        if srt_content and srt_content.strip():
            temp_srt_name = f"sub_{int(time.time())}_{uuid.uuid4().hex[:6]}.srt" if 'uuid' in globals() else f"sub_{int(time.time())}.srt"
            temp_srt_path = os.path.join(self.downloads_dir, temp_srt_name)
            with open(temp_srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content.strip() + "\n")
            resolved_srt = temp_srt_path
        elif srt_path:
            resolved_srt = self._resolve(srt_path)

        has_subtitles = bool(resolved_srt and os.path.exists(resolved_srt) and burn_subtitles)
        has_audio = bool(resolved_audio and os.path.exists(resolved_audio))

        # Determine intermediate joining path
        joined_path = output_path
        temp_joined = None
        if has_audio or has_subtitles:
            temp_joined = os.path.join(
                self.downloads_dir, f".join_{os.getpid()}_{abs(hash(tuple(valid_videos))) % 100000}.mp4"
            )
            joined_path = temp_joined

        try:
            # 1. Concat all normalised video clips
            self._concat_normalised(valid_videos, joined_path, width, height, fps)
            duration = self._probe_duration(joined_path)

            # 2. Mux Audio and/or Burn Subtitles if provided
            if has_audio or has_subtitles:
                self._mux_audio_and_subtitles(
                    video_path=joined_path,
                    audio_path=resolved_audio if has_audio else None,
                    srt_path=resolved_srt if has_subtitles else None,
                    output_path=output_path,
                    height=height,
                )
                duration = self._probe_duration(output_path)
        finally:
            if temp_joined and os.path.exists(temp_joined):
                try:
                    os.remove(temp_joined)
                except Exception:
                    pass
            if temp_srt_path and os.path.exists(temp_srt_path):
                try:
                    os.remove(temp_srt_path)
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
            "has_audio": has_audio,
            "has_subtitles": has_subtitles,
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
        self._mux_audio_and_subtitles(
            video_path=video_path,
            audio_path=audio_path,
            srt_path=None,
            output_path=output_path,
        )

    def _mux_audio_and_subtitles(
        self,
        video_path: str,
        output_path: str,
        audio_path: Optional[str] = None,
        srt_path: Optional[str] = None,
        height: int = 1080,
    ) -> None:
        video_path = os.path.abspath(video_path)
        output_path = os.path.abspath(output_path)
        if audio_path:
            audio_path = os.path.abspath(audio_path)
        if srt_path:
            srt_path = os.path.abspath(srt_path)

        video_duration = self._probe_duration(video_path)
        audio_duration = self._probe_duration(audio_path) if audio_path else 0.0

        # Subtitle filter if srt_path provided
        sub_filter = None
        cwd = None
        if srt_path and os.path.exists(srt_path):
            font_size = max(18, int(height * 0.024))
            sub_dir = os.path.dirname(os.path.abspath(srt_path))
            sub_name = os.path.basename(srt_path)
            cwd = sub_dir
            # Style: Font size scaled to height, crisp white with black outline and subtle shadow, centered at bottom
            style_str = f"FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=35"
            sub_filter = f"subtitles={sub_name}:force_style='{style_str}'"

        cmd = [self.ffmpeg_exe, "-y"]

        has_audio = bool(audio_path and os.path.exists(audio_path))
        if has_audio and audio_duration > video_duration + 0.15:
            # Loop video to cover the whole song
            cmd.extend(["-stream_loop", "-1", "-i", video_path, "-i", audio_path])
        elif has_audio:
            cmd.extend(["-i", video_path, "-i", audio_path])
        else:
            cmd.extend(["-i", video_path])

        if sub_filter:
            cmd.extend(["-vf", sub_filter])

        if has_audio:
            cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
            cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"])
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            if audio_duration < video_duration - 0.15:
                cmd.extend(["-af", "apad"])
            cmd.append("-shortest")
        else:
            cmd.extend(["-map", "0:v:0"])
            if sub_filter:
                cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"])
            else:
                cmd.extend(["-c:v", "copy"])
            cmd.append("-an")

        cmd.extend(["-movflags", "+faststart", output_path])
        self._run(cmd, timeout=900, cwd=cwd)

    def _run(self, cmd: List[str], timeout: int = 600, cwd: Optional[str] = None):
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout, cwd=cwd
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
