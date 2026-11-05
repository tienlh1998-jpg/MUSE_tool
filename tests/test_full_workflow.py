"""End-to-end workflow tests for MUSE AI MV Studio V3.

The suite runs against the real FastAPI app in an isolated temporary data
directory, so it never touches the developer's projects, cookies or renders.

Run directly:
    python test_app.py            # all 5 scenarios, verbose
    python test_app.py -k stitch  # only the stitch scenario

Or via pytest:
    pytest tests/test_full_workflow.py -v
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Isolated environment MUST be configured before importing the application.
# ---------------------------------------------------------------------------
_TEMP_ROOT = tempfile.mkdtemp(prefix="muse_e2e_")
os.environ["MUSE_DATA_DIR"] = _TEMP_ROOT
os.environ["MUSE_DOWNLOADS_DIR"] = os.path.join(_TEMP_ROOT, "downloads")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
from core.config import DOWNLOADS_DIR, IMAGES_DIR  # noqa: E402
from core.video_stitcher import VideoStitcher  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app_module.app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def state():
    """Shared state across ordered scenarios (project, image, videos)."""
    return {}


def _wait_for_task(client, task_id, timeout=300):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get(f"/api/tasks/{task_id}")
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] in ("completed", "failed"):
            return last
        time.sleep(1)
    pytest.fail(f"Task {task_id} không kết thúc sau {timeout}s: {last}")


def _ffmpeg_probe(path):
    ffmpeg = VideoStitcher(str(DOWNLOADS_DIR)).ffmpeg_exe
    result = subprocess.run(
        [ffmpeg, "-i", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )
    return result.stderr or ""


# ---------------------------------------------------------------------------
# Test 1: Healthcheck & Config
# ---------------------------------------------------------------------------
def test_01_healthcheck_and_config(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    config = client.get("/api/config")
    assert config.status_code == 200
    payload = config.json()
    assert "ai_provider" in payload
    assert "free_image_fallback" in payload
    assert payload["download_dir"] == DOWNLOADS_DIR

    accounts = client.get("/api/accounts")
    assert accounts.status_code == 200
    assert isinstance(accounts.json(), list)

    # Partial config update must not wipe unrelated settings.
    update = client.post("/api/config", json={"concurrency": 2})
    assert update.status_code == 200
    assert update.json()["config"]["concurrency"] == 2
    assert update.json()["config"]["free_image_fallback"] is True


# ---------------------------------------------------------------------------
# Test 2: Project lifecycle
# ---------------------------------------------------------------------------
def test_02_project_lifecycle(client, state):
    created = client.post("/api/projects", json={
        "name": "E2E Test MV",
        "lyrics": "Test lyrics for automated workflow",
        "aspect": "16:9",
    })
    assert created.status_code == 200
    project = created.json()
    assert project["id"]
    state["project_id"] = project["id"]

    detail = client.get(f"/api/projects/{project['id']}")
    assert detail.status_code == 200
    body = detail.json()
    for key in ("id", "name", "images", "shots", "aspect", "final_video_url"):
        assert key in body
    assert body["images"] == []
    assert body["shots"] == []

    missing = client.get("/api/projects/does_not_exist")
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# Test 3: End-to-end image generation
# ---------------------------------------------------------------------------
def test_03_image_generation(client, state):
    project_id = state["project_id"]
    response = client.post("/api/tasks", json={
        "tasks": [{
            "project_id": project_id,
            "prompt": "cinematic portrait of Vietnamese girl in rain, 8k",
            "mode": "text-to-image",
            "aspect": "16:9",
        }]
    })
    assert response.status_code == 200, response.text
    task = response.json()["tasks"][0]
    final = _wait_for_task(client, task["id"])
    assert final["status"] == "completed", final.get("error")

    image_path = Path(final["local_file"])
    assert image_path.exists(), "File ảnh không được tạo trên ổ đĩa"
    assert image_path.suffix.lower() == ".png"
    assert image_path.stat().st_size > 50 * 1024, "Ảnh phải lớn hơn 50KB"

    from PIL import Image
    with Image.open(image_path) as img:
        assert img.size == (1280, 720), f"Kích thước sai: {img.size}"
        assert img.format == "PNG"

    # The image must be auto-attached to the project.
    detail = client.get(f"/api/projects/{project_id}").json()
    assert len(detail["images"]) == 1
    saved = detail["images"][0]
    assert saved["url"] == final["result_url"]
    assert saved["local_path"] == final["local_file"]
    assert saved["aspect"] == "16:9"
    # The free provider must report that the footer/watermark band was cropped.
    if str(saved.get("provider", "")).startswith("free:"):
        assert saved["watermark_stripped"] is True
    state["image"] = saved
    state["image_path"] = str(image_path)

    # The static mount must serve the generated PNG.
    served = client.get(saved["url"])
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/png")


# ---------------------------------------------------------------------------
# Test 4: End-to-end video rendering from the generated image
# ---------------------------------------------------------------------------
def test_04_video_rendering(client, state):
    project_id = state["project_id"]
    image = state["image"]

    # Register the shot, then render it through the real endpoint.
    shot_resp = client.post(f"/api/projects/{project_id}/shots", json={
        "prompt": "slow dolly forward toward the girl in the rain, cinematic",
        "source_image_url": image["url"],
        "mode": "image-to-video",
        "duration": 5,
    })
    assert shot_resp.status_code == 200, shot_resp.text
    shot = shot_resp.json()
    state["shot"] = shot

    render = client.post(f"/api/projects/{project_id}/shots/{shot['id']}/render")
    assert render.status_code == 200, render.text
    task = render.json()["task"]
    final = _wait_for_task(client, task["id"], timeout=300)
    assert final["status"] == "completed", final.get("error")

    video_path = Path(final["local_file"])
    assert video_path.exists(), "File MP4 không được tạo"
    assert video_path.suffix.lower() == ".mp4"
    assert video_path.stat().st_size > 200 * 1024, "Video phải lớn hơn 200KB"

    probe = _ffmpeg_probe(video_path)
    assert "h264" in probe.lower(), probe[-500:]
    assert "yuv420p" in probe.lower(), probe[-500:]
    assert "1920x1080" in probe, probe[-500:]

    detail = client.get(f"/api/projects/{project_id}").json()
    updated = next(s for s in detail["shots"] if s["id"] == shot["id"])
    assert updated["status"] == "ready"
    assert updated["video_url"] == final["result_url"]
    assert updated["local_path"] == final["local_file"]

    state["video_1"] = updated


# ---------------------------------------------------------------------------
# Test 5: 1-Click auto-stitch (two clips + music)
# ---------------------------------------------------------------------------
def test_05_auto_stitch(client, state):
    project_id = state["project_id"]
    first_shot = state["video_1"]

    # Create a second shot from the same image with a different camera move.
    shot_resp = client.post(f"/api/projects/{project_id}/shots", json={
        "prompt": "pull back toàn cảnh revealing the rainy street, cinematic",
        "source_image_url": state["image"]["url"],
        "mode": "image-to-video",
        "duration": 5,
    })
    assert shot_resp.status_code == 200
    second_shot = shot_resp.json()

    render = client.post(f"/api/projects/{project_id}/shots/{second_shot['id']}/render")
    assert render.status_code == 200
    final = _wait_for_task(client, render.json()["task"]["id"], timeout=300)
    assert final["status"] == "completed", final.get("error")

    # Attach a real 6-second WAV so the muxer has a genuine audio stream.
    audio_path = os.path.join(DOWNLOADS_DIR, "test_music.wav")
    ffmpeg = VideoStitcher(str(DOWNLOADS_DIR)).ffmpeg_exe
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
         "-c:a", "pcm_s16le", audio_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True,
    )

    # Persist the audio attachment through the shared manager.
    app_module.project_manager.update_audio(project_id, "test_music.wav", audio_path)

    stitched = client.post(f"/api/projects/{project_id}/stitch")
    assert stitched.status_code == 200, stitched.text
    result = stitched.json()
    assert result["success"] is True
    assert result["shot_count"] == 2

    out_path = Path(result["output_path"])
    assert out_path.exists()
    assert out_path.name.startswith("Full_MV_")
    assert out_path.suffix == ".mp4"
    assert out_path.stat().st_size > 200 * 1024

    probe = _ffmpeg_probe(out_path)
    assert "h264" in probe.lower()
    assert "aac" in probe.lower()

    # Duration must cover both clips (2 x 5s) and the 6s music.
    assert result["duration"] >= 9.5, result["duration"]

    detail = client.get(f"/api/projects/{project_id}").json()
    assert detail["final_video_url"] == result["url"]
    served = client.get(result["url"])
    assert served.status_code == 200

    # Stitching with no rendered shots must fail cleanly.
    empty = client.post("/api/projects", json={"name": "Empty Project"})
    empty_id = empty.json()["id"]
    bad = client.post(f"/api/projects/{empty_id}/stitch")
    assert bad.status_code == 400


# ---------------------------------------------------------------------------
# Extra guards: no placeholder colour renders remain in the engine.
# ---------------------------------------------------------------------------
def test_06_no_placeholder_color_rendering():
    engine_source = (PROJECT_ROOT / "core" / "muse_engine.py").read_text(encoding="utf-8")
    assert "color=c=0x" not in engine_source
    assert "lavfi" not in engine_source

    # Every video render must be 1080p-class H.264/yuv420p.
    assert '"libx264"' in engine_source
    assert '"yuv420p"' in engine_source


def test_07_camera_motion_detection():
    from core.muse_engine import detect_camera_motion

    assert detect_camera_motion("slow dolly forward") == "zoom_in"
    assert detect_camera_motion("zoom in on her eyes") == "zoom_in"
    assert detect_camera_motion("pull back toàn cảnh") == "zoom_out"
    assert detect_camera_motion("pan left through the mist") == "pan_left"
    assert detect_camera_motion("walk through the street") == "pan_right"


def test_08_queue_recovery():
    """Pending tasks must be re-queued after a simulated restart."""
    from core.task_manager import TaskManager

    with tempfile.TemporaryDirectory() as tmp:
        tasks_file = os.path.join(tmp, "tasks.json")
        manager = TaskManager(tasks_file=tasks_file)
        manager.add_tasks_bulk([{
            "prompt": "recovery probe",
            "mode": "text-to-image",
        }])
        # Simulate an interrupted process.
        manager.tasks[0].status = "running"
        manager.save()

        restarted = TaskManager(tasks_file=tasks_file)
        recovered = restarted.recover_pending_tasks()
        assert recovered == 1
        assert restarted.tasks[0].status == "pending"


def teardown_module(module):
    """Remove the isolated temp data directory after the run."""
    shutil.rmtree(_TEMP_ROOT, ignore_errors=True)
