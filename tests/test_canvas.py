"""Tests for Node Workflow Canvas integration in MUSE AI Studio."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app as app_module


@pytest.fixture(scope="module")
def client():
    with TestClient(app_module.app) as test_client:
        yield test_client


def test_canvas_route_renders_html(client):
    """Ensure GET /canvas serves the complete workflow canvas HTML."""
    res = client.get("/canvas")
    assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}"
    html = res.text

    # Title & Branding
    assert "Workflow Canvas" in html
    assert "Quay lại Studio Chính" in html

    # Essential Canvas DOM Elements
    assert '<main id="viewport">' in html
    assert '<svg id="edges">' in html
    assert '<div id="canvas">' in html
    assert 'id="timelineDock"' in html
    assert 'id="timelineTrack"' in html
    assert 'id="projectSelect"' in html
    assert 'id="loadProjectBtn"' in html
    assert 'id="scriptImportBtn"' in html
    assert 'id="runBtn"' in html

    # Script tags
    assert "canvas.js" in html


def test_flow_route_alias(client):
    """Ensure /flow acts as a valid route alias for /canvas."""
    res = client.get("/flow")
    assert res.status_code == 200
    assert "Workflow Canvas" in res.text


def test_canvas_static_assets_and_no_chrome_apis(client):
    """Ensure static files are served and canvas.js contains 0 Chrome Extension calls."""
    res_js = client.get("/static/canvas/canvas.js")
    assert res_js.status_code == 200
    js_content = res_js.text

    assert "chrome.runtime" not in js_content, "canvas.js must not contain chrome.runtime"
    assert "chrome.storage" not in js_content, "canvas.js must not contain chrome.storage"
    assert "chrome.tabs" not in js_content, "canvas.js must not contain chrome.tabs"
    assert "chrome.scripting" not in js_content, "canvas.js must not contain chrome.scripting"

    res_css = client.get("/static/canvas/styles.css")
    assert res_css.status_code == 200
    assert len(res_css.text) > 1000


def test_api_generate_image_validation_and_creation(client):
    """Test POST /api/generate-image validation and task creation."""
    # 1. Empty prompt rejected
    res_bad = client.post("/api/generate-image", json={"prompt": ""})
    assert res_bad.status_code == 400

    # 2. Valid prompt queues task
    res_ok = client.post(
        "/api/generate-image",
        json={
            "prompt": "Cyberpunk Saigon street with neon lights",
            "aspect": "16:9",
            "wait": False,
        },
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["success"] is True
    assert "task_id" in data
    assert data["task"]["mode"] == "text-to-image"

    # Clean up test task from queue
    client.post("/api/tasks/clear")


def test_api_render_shot_validation_and_creation(client):
    """Test POST /api/render-shot validation and task creation."""
    # 1. Empty prompt rejected
    res_bad = client.post("/api/render-shot", json={"prompt": ""})
    assert res_bad.status_code == 400

    # 2. Valid prompt queues task
    res_ok = client.post(
        "/api/render-shot",
        json={
            "prompt": "Camera slow pan across the futuristic city skyline",
            "aspect": "16:9",
            "duration": 5,
            "wait": False,
        },
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["success"] is True
    assert "task_id" in data
    assert "video" in data["task"]["mode"]

    # Clean up test task from queue to avoid background worker overhead
    client.post("/api/tasks/clear")


def test_api_auto_stitch_validation(client):
    """Test POST /api/auto-stitch input validation."""
    # 1. Empty video list without project rejected
    res_bad = client.post("/api/auto-stitch", json={"video_paths": []})
    assert res_bad.status_code == 400


def test_main_studio_index_contains_canvas_button(client):
    """Ensure main Studio UI (/) features the prominent button linking to /canvas."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text
    assert 'href="/canvas"' in html or 'href="/canvas/"' in html
    assert "Bàn Dựng Canvas Kéo Thả" in html


def test_api_otp_endpoints_validation(client):
    """Test OTP send and confirm endpoint validation."""
    # 1. Invalid email rejected
    res = client.post("/api/accounts/otp/send", json={"email": "not-an-email"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "hợp lệ" in data["error"]

    # 2. Confirm without prior send rejected
    res_conf = client.post(
        "/api/accounts/otp/confirm",
        json={"email": "unregistered@gmail.com", "otp_code": "123456"},
    )
    assert res_conf.status_code == 200
    conf_data = res_conf.json()
    assert conf_data["success"] is False
    assert "không tồn tại" in conf_data["error"]


def test_ai_director_endpoints_and_canvas_dom(client):
    """Ensure AI Director config/generate endpoints work and Canvas HTML includes AI Director UI."""
    # 1. Config endpoint
    res = client.get("/api/director/config")
    assert res.status_code == 200
    data = res.json()
    assert "ai_provider" in data
    assert "ai_base_url" in data
    assert "ai_model" in data
    assert "has_api_key" in data

    # 2. Generate endpoint validation
    res = client.post("/api/director/generate", json={
        "song_title": "Test Song",
        "lyrics": "Test Lyrics",
        "genre_style": "Pop",
        "ai_api_key": ""
    })
    # If no key, expect 400
    assert res.status_code in [400, 500]

    # 3. Canvas HTML has AI Director button & modal
    res_html = client.get("/canvas/")
    assert res_html.status_code == 200
    html = res_html.text
    assert 'id="aiDirectorBtn"' in html
    assert 'id="aiDirectorModal"' in html
    assert "AI Đạo Diễn Suno" in html
