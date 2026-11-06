import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from core.mv_director import (
    enforce_character_consistency,
    parse_timed_lyrics,
    group_srt_into_shots,
)

def test_character_consistency_universal():
    visual_bible = {
        "character_lock": "a 25-year-old Vietnamese woman with long black silk hair and sorrowful brown eyes in vintage Ao Dai"
    }
    ref_pack = {
        "character_prompt": "Cinematic portrait of a 25-year-old Vietnamese woman with long black silk hair and sorrowful brown eyes, wearing vintage Ao Dai, 8k resolution"
    }
    shots = [
        {"shot_number": 1, "prompt": "She sits by the rainy wooden window weeping gently", "section": "Shot 1"},
        {"shot_number": 2, "prompt": "Walking through misty garden in the dark night", "section": "Shot 2"}
    ]
    processed = enforce_character_consistency(shots, visual_bible, ref_pack)
    assert len(processed) == 2
    assert "Vietnamese woman with long black silk hair" in processed[0]["prompt"]
    assert "Vietnamese woman with long black silk hair" in processed[1]["prompt"]
    assert "western caucasian features" in processed[0]["negative_prompt"]
    assert "ken burns effect" in processed[0]["negative_prompt"]

def test_srt_lrc_karaoke_matching():
    lrc_sample = """[00:08.50] Khăn rách quạt nan mặt bôi vôi trắng
[00:15.20] Lão phú ông bụng phệ lần chuỗi hạt
[00:23.00] Tiếng não bạt khua chát chúa sân đình
"""
    segments = parse_timed_lyrics(lrc_sample)
    assert len(segments) == 3
    shots = group_srt_into_shots(segments, min_dur=5.0, max_dur=10.0)
    assert len(shots) >= 2
    assert "0:08" in shots[0]["timecode"]


def test_storyboard_director_v6_schema():
    from core.mv_director import parse_full_director_plan, enforce_video_motion

    sample_json = """```json
    {
      "project_info": {
        "title": "Podcast Công Nghệ AI",
        "mode": "PODCAST",
        "mode_display": "MODE 3 — PODCAST DIRECTOR",
        "duration": 45,
        "aspect_ratio": "16:9"
      },
      "creative_treatment": {
        "concept": "Talkshow đối thoại giữa 2 chuyên gia AI",
        "theme": "Tương lai tự động hóa",
        "color_palette": "Warm amber key light, cold teal rim light"
      },
      "visual_locks": {
        "char_locks": [
          {"id": "CHAR_01", "name": "Host Nam", "description": "Vietnamese man 30yo, undercut hair, navy polo shirt"},
          {"id": "CHAR_02", "name": "Guest Nam", "description": "Vietnamese man 32yo, slim glasses, charcoal shirt"}
        ],
        "set_locks": [
          {"id": "SET_01", "name": "Studio Podcast", "description": "Acoustic wooden panels, warm lighting, microphones"}
        ],
        "style_locks": [
          {"id": "STYLE_01", "description": "35mm shallow depth of field, cinematic bokeh, 16:9 photorealistic"}
        ],
        "negative_prompt": "3D CGI, cartoon, anime, blurry, distorted"
      },
      "reference_asset_library": [
        {
          "asset_id": "REF_CHAR_01_FRONT_V1",
          "lock_group": "CHAR_LOCK",
          "name": "Host Nam",
          "prompt": "Cinematic portrait of Host Nam, Vietnamese man 30yo, 16:9",
          "aspect": "16:9"
        },
        {
          "asset_id": "REF_CHAR_02_FRONT_V1",
          "lock_group": "CHAR_LOCK",
          "name": "Guest Nam",
          "prompt": "Cinematic portrait of Guest Nam, Vietnamese man 32yo, 16:9",
          "aspect": "16:9"
        },
        {
          "asset_id": "REF_SET_01_WIDE_V1",
          "lock_group": "SET_LOCK",
          "name": "Studio Podcast",
          "prompt": "Master establishing shot of modern podcast studio, 16:9",
          "aspect": "16:9"
        }
      ],
      "shots": [
        {
          "shot_number": 1,
          "title": "Lời mở đầu Host",
          "timecode": "0:00 - 0:07",
          "duration": 7,
          "first_frame_description": "Host nhìn thẳng camera mỉm cười",
          "image_prompt": "Close-up of Host Nam, Vietnamese man 30yo, talking warmly into broadcast microphone, 16:9",
          "video_prompt": "Host Nam speaks with lively gestures, fluid natural human motion, alive, dynamic physical action",
          "required_references": ["REF_CHAR_01_FRONT_V1", "REF_SET_01_WIDE_V1"]
        }
      ]
    }
    ```"""

    parsed = parse_full_director_plan(sample_json)
    assert parsed["project_info"]["mode"] == "PODCAST"
    assert len(parsed["reference_asset_library"]) == 3
    assert len(parsed["shots"]) == 1
    assert parsed["shots"][0]["image_prompt"].startswith("Close-up")
    assert "fluid natural human motion" in parsed["shots"][0]["video_prompt"]

    # Verify enforce_video_motion
    shots = enforce_video_motion(parsed["shots"])
    assert "ken burns effect" in shots[0]["negative_prompt"]
