import os
import subprocess
import tempfile
import imageio_ffmpeg
from typing import List, Optional, Dict, Any

class VideoStitcher:
    def __init__(self, downloads_dir: str):
        self.downloads_dir = downloads_dir
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def stitch_videos(
        self,
        video_paths: List[str],
        audio_path: Optional[str] = None,
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Concatenates a list of video files in order, multiplexes with optional audio track,
        and saves the resulting full video in downloads_dir.
        """
        if not video_paths:
            raise ValueError("Không có video nào trong danh sách để ghép!")

        # Verify all video paths exist
        valid_videos = []
        for vp in video_paths:
            if os.path.exists(vp):
                valid_videos.append(vp)
            else:
                # Check inside downloads_dir
                local_vp = os.path.join(self.downloads_dir, os.path.basename(vp))
                if os.path.exists(local_vp):
                    valid_videos.append(local_vp)

        if not valid_videos:
            raise ValueError("Không tìm thấy các file video hợp lệ trên ổ cứng!")

        os.makedirs(self.downloads_dir, exist_ok=True)
        if not output_filename:
            output_filename = f"Full_MV_stitched_{len(valid_videos)}shots.mp4"
        
        output_path = os.path.join(self.downloads_dir, output_filename)

        # Create temporary concat list file for FFmpeg
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            list_file_path = f.name
            for vp in valid_videos:
                # Escape backslashes for FFmpeg concat format
                safe_path = vp.replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        try:
            # Build FFmpeg command
            cmd = [self.ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", list_file_path]

            if audio_path and os.path.exists(audio_path):
                # We have an audio track to mux
                cmd.extend(["-i", audio_path, "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k", "-shortest", output_path])
            else:
                # Re-encode to ensure uniform timestamps
                cmd.extend(["-c:v", "libx264", "-c:a", "aac", output_path])

            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
            if result.returncode != 0:
                # Fallback: simple copy stream if re-encode fails
                cmd_fallback = [self.ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy", output_path]
                fb_result = subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                if fb_result.returncode != 0:
                    raise Exception(f"Lỗi khi ghép video bằng FFmpeg: {result.stderr[:300]}")

            return {
                "success": True,
                "output_filename": output_filename,
                "output_path": output_path,
                "url": f"/downloads/{output_filename}",
                "shot_count": len(valid_videos)
            }
        finally:
            if os.path.exists(list_file_path):
                try:
                    os.remove(list_file_path)
                except Exception:
                    pass
