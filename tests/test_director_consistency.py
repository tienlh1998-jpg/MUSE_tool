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
