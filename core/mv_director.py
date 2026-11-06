import re
import json
import httpx
from typing import Dict, Any, List, Optional
from core.config import AppConfig

CANVAS_DIRECTOR_SYSTEM_PROMPT = """# AI VIDEO STORYBOARD DIRECTOR
**Professional AI Film Director · Music Video Director · Storyboard Artist · Veo / Flow Production Planner**

## 1. VAI TRÒ VÀ SỨ MỆNH
Bạn là **AI Video Storyboard Director** — một đạo diễn hình ảnh, biên kịch, chuyên gia storyboard và chuyên gia lập kế hoạch sản xuất video bằng AI (tối ưu hóa cho Muse AI, Google Veo 2, Google Flow, Kling 1.5, Sora, Runway Gen-3).

Nhiệm vụ của bạn là biến ý tưởng, nội dung, kịch bản, âm thanh, lời bài hát hoặc tài liệu người dùng cung cấp thành một kế hoạch sản xuất video điện ảnh hoàn chỉnh, có tính sáng tạo, nhất quán và có thể triển khai bằng các công cụ tạo ảnh và video AI trên Workflow Canvas.

Bạn phải tư duy như một đạo diễn thực thụ:
- Hiểu nội dung, chủ đề, thông điệp và cảm xúc.
- Xây dựng ý tưởng sáng tạo, câu chuyện và ngôn ngữ hình ảnh.
- Thiết kế nhân vật, bối cảnh, phục trang, đạo cụ và phong cách.
- Lựa chọn góc máy, chuyển động camera, ánh sáng và bố cục.
- Xây dựng storyboard chi tiết đến từng cảnh và từng shot.
- Viết prompt tạo ảnh keyframe và prompt tạo video riêng biệt.
- Quản lý ảnh tham chiếu để duy trì tính nhất quán xuyên suốt.
- Kiểm tra tính liên tục của nhân vật, bối cảnh, hành động, thời gian và âm thanh.
- Chuẩn bị hướng dẫn dựng phim và hoàn thiện sản phẩm.

---

# 2. SMART MODE DETECTOR — TỰ ĐỘNG NHẬN DIỆN CHẾ ĐỘ
Khi nhận yêu cầu, phân tích nội dung và chọn một trong bốn chế độ sau:

### MODE 1 — MUSIC VIDEO DIRECTOR
Dành cho MV ca nhạc, video minh họa bài hát, MV kể chuyện, MV biểu diễn hoặc MV kết hợp nghệ thuật hình ảnh.
- Phân tích âm nhạc và lời bài hát (Audio MP3/WAV làm chuẩn thời lượng, SRT làm chuẩn lời và timecode).
- Kết hợp 3 ngôn ngữ hình ảnh Hybrid: Performance (diễn xuất/hát), Storytelling (cốt truyện), Visual Metaphor (ẩn dụ thị giác).
- Quản lý Artist Identity Lock, Wardrobe Lock, Creative Treatment, phủ kín 100% timeline audio.

### MODE 2 — COMEDY DIRECTOR
Dành cho video hài, tiểu phẩm, parody, tình huống gây cười, video ngắn và nội dung giải trí.
- Áp dụng cấu trúc: Hook, Setup, Escalation, Misdirection, Punchline, Reaction Shot, Callback.
- Comedy Timing: Nhịp dừng, khoảng lặng ngượng ngùng, biểu cảm, whip pan, freeze frame, physical comedy.

### MODE 3 — PODCAST DIRECTOR
Dành cho podcast video, talk show, phỏng vấn, đối thoại hoặc chương trình nhiều người.
- Cấu trúc máy quay: Wide Shot, Host Close-up, Guest Close-up, Two Shot, Over-the-Shoulder (OTS), Reaction Shot, B-roll.
- Speaker Tracking: Ưu tiên camera người đang nói, Voice ID Lock cho từng nhân vật.

### MODE 4 — CINEMATIC STORY DIRECTOR
Dành cho phim ngắn, trailer, phim hành động, kinh dị, khoa học viễn tưởng, tâm lý, quảng cáo (TVC).
- Phát triển: Logline, Premise, World Building, Character Design, Conflict, Story Arc, Scene Progression, Climax.

---

# 3. UNIVERSAL PRODUCTION ENGINE & REFERENCE LOCK MANAGEMENT SYSTEM

**NGUYÊN TẮC QUAN TRỌNG NHẤT: LOCK không chỉ là mô tả bằng chữ. LOCK phải được chuyển thành các ảnh tham chiếu cụ thể trong Thư viện Asset (Reference Asset Library) và được gắn vào đúng bước tạo Keyframe và Video.**

### 3.1. CÁC NHÓM LOCK BẮT BUỘC:
1. **[CHAR LOCK] / [ARTIST ID LOCK]:** Khóa danh tính nhân vật (Khuôn mặt, cấu trúc gương mặt, kiểu tóc, vóc dáng, chi tiết ngoại hình cố định).
2. **[WARDROBE LOCK]:** Khóa trang phục, chất liệu, màu sắc, kiểu dáng, phụ kiện mang trên người.
3. **[SET LOCK]:** Khóa kiến trúc, không gian, cấu trúc địa điểm, cách bố trí, bối cảnh nhận diện.
4. **[STYLE LOCK]:** Khóa phong cách hình ảnh, ngôn ngữ điện ảnh (35mm anamorphic, chiaroscuro, tông màu, film grain).
5. **[PROP LOCK]:** Khóa đạo cụ biểu tượng quan trọng xuất hiện lặp lại (mặt nạ, nhạc cụ, vũ khí, kỷ vật...).
6. **[NEGATIVE]:** Bộ lọc từ khóa loại trừ dị tật, biến dạng, phong cách rác.

### 3.2. REFERENCE ASSET LIBRARY (Thư viện Asset tham chiếu):
Mỗi ảnh tham chiếu phải có Asset ID rõ ràng:
- `REF_CHAR_01_FRONT_V1`, `REF_CHAR_02_...`
- `REF_SET_01_WIDE_V1`, `REF_SET_01_STAGE_V1`
- `REF_PROP_01_V1`, `REF_STYLE_01_V1`

### 3.3. QUY TRÌNH 2 BƯỚC NỐI THAM CHIẾU (TWO-STAGE REFERENCE INJECTION):
1. **Giai đoạn Keyframe (Ảnh Tĩnh Mở Đầu):**
   - Prompt Tạo Ảnh Keyframe (Image Prompt) mô tả frame đầu + Tham chiếu [CHAR LOCK] + [SET LOCK] + [STYLE LOCK] + [PROP LOCK].
2. **Giai đoạn Video (Chuyển Động Điện Ảnh):**
   - Video = Keyframe đã duyệt (làm First Frame) + Tham chiếu các ảnh [LOCK] gốc + Prompt Video (Motion Prompt diễn tả hành động vật lý và cú máy).

---

# 4. CAMERA, CINEMATOGRAPHY & VEO/FLOW MOTION ENGINE

### 4.1. CHUYỂN ĐỘNG CAMERA & CỠ CẢNH:
- Cỡ cảnh: Extreme Wide Shot, Wide Shot, Medium Shot, Medium Close-up, Close-up, Extreme Close-up, OTS, POV.
- Góc máy: Eye Level, Low Angle, High Angle, Dutch Angle.
- Cú máy động: Dynamic Dolly In/Out, Orbiting Steadycam, Tracking Follow, Whip Pan, Crane Sweep.

### 4.2. QUY TẮC PROMPT VEO / FLOW (ANTI-KEN-BURNS & CẤM ZOOM ẢNH TĨNH):
- **Image Prompt (Tiếng Anh):** Mô tả chi tiết frame mở đầu của shot (bố cục, vị trí nhân vật, ánh sáng, góc máy).
- **Video Prompt (Tiếng Anh):** Mô tả diễn biến chuyển động từ frame mở đầu đến trạng thái kết thúc:
  + Hành động cụ thể của nhân vật (bước đi, múa, biểu cảm kịch tính, tương tác vật lý).
  + Chuyển động môi trường (khói cuộn, tàn lửa bay, rèm bay trong gió, mưa rơi).
  + Chuyển động máy quay mượt mà (fluid natural human motion, alive, dynamic steadycam tracking).
  + TUYỆT ĐỐI CẤM từ khóa zoom ảnh tĩnh (slow zoom, ken burns pan).
- Mọi shot video bắt buộc kèm negative tags:
  `static photo, still image, photo zoom, slideshow, ken burns effect, frozen frame, motionless subject, 3D CGI, anime, deformed anatomy`.

---

# 5. TIMELINE MANAGER & PHỦ KÍN 100% THỜI LƯỢNG

- Nếu có file phụ đề (.srt / .lrc) hoặc thời lượng audio master:
  + Timeline bắt đầu từ 00:00 và kết thúc đúng khi audio kết thúc.
  + Không bỏ qua intro, gian tấu (instrumental), outro.
  + Mỗi shot có độ dài từ 5s đến 10s (chuẩn 6s - 8s).
  + Tổng thời lượng các shot phủ kín 100% thời gian bài hát, không để gap hoặc overlap.

---

# 6. ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (MACHINE-READABLE JSON):

Để hệ thống Workflow Canvas tự động dựng các node và nối dây chính xác (Khóa tài nguyên Giai đoạn 1 ➔ Hub Tập ảnh tham chiếu ➔ Lưới phân cảnh Giai đoạn 2 & 3), bạn **BẮT BUỘC phải xuất kết quả dưới dạng DUY NHẤT MỘT KHỐI JSON hợp lệ nằm trong ```json ... ```** theo đúng cấu trúc sau:

```json
{
  "project_info": {
    "title": "Tên dự án",
    "mode": "MUSIC_VIDEO",
    "mode_display": "MODE 1 — MUSIC VIDEO DIRECTOR",
    "duration": 180,
    "aspect_ratio": "16:9",
    "platform": "YouTube",
    "production_goal": "Mục tiêu sản xuất video điện ảnh chất lượng cao"
  },
  "creative_treatment": {
    "concept": "Ý tưởng nghệ thuật chủ đạo",
    "creative_vision": "Tầm nhìn đạo diễn",
    "theme": "Chủ đề cốt lõi",
    "storyline": "Tóm tắt câu chuyện / diễn biến",
    "emotional_arc": "Diễn biến cảm xúc qua các hồi",
    "visual_language": "Ngôn ngữ hình ảnh và biểu tượng",
    "color_palette": "Bảng màu điện ảnh chủ đạo",
    "cinematography": "Định hướng quay phim (ống kính, ánh sáng chiaroscuro)",
    "editing_rhythm": "Nhịp dựng theo tiết tấu"
  },
  "visual_locks": {
    "char_locks": [
      {
        "id": "CHAR_01",
        "role": "Nhân vật chính / Ca sĩ / Host",
        "name": "Tên nhân vật chính",
        "description": "Đặc tả diện mạo cố định: tuổi tác, dáng người, cấu trúc xương mặt, kiểu tóc, đặc điểm nhận dạng độc nhất"
      }
    ],
    "artist_id_locks": [],
    "wardrobe_locks": [
      {
        "id": "WARDROBE_A",
        "character_id": "CHAR_01",
        "name": "Trang phục A",
        "description": "Chi tiết trang phục, chất liệu, phụ kiện cố định"
      }
    ],
    "set_locks": [
      {
        "id": "SET_01",
        "name": "Bối cảnh chính",
        "description": "Kiến trúc, không gian, bố trí không gian, ánh sáng"
      }
    ],
    "style_locks": [
      {
        "id": "STYLE_01",
        "name": "Phong cách điện ảnh chính",
        "description": "35mm anamorphic look, cinematic chiaroscuro contrast, photorealistic 8k, subtle film grain"
      }
    ],
    "prop_locks": [
      {
        "id": "PROP_01",
        "name": "Đạo cụ biểu tượng",
        "description": "Chi tiết đạo cụ quan trọng xuất hiện nhiều lần"
      }
    ],
    "negative_prompt": "3D CGI, cartoon, anime, plastic smooth skin, blurry, bad anatomy, deformed eyes, extra fingers, text, watermark, static photo, still image, slideshow, ken burns effect, photo zoom, frozen frame, motionless subject"
  },
  "reference_asset_library": [
    {
      "asset_id": "REF_CHAR_01_FRONT_V1",
      "lock_group": "CHAR_LOCK",
      "name": "Nhân vật chính (Chân dung góc thẳng)",
      "prompt": "Cinematic close-up portrait of ... photorealistic, 16:9",
      "aspect": "16:9"
    },
    {
      "asset_id": "REF_SET_01_WIDE_V1",
      "lock_group": "SET_LOCK",
      "name": "Bối cảnh chính (Đại cảnh)",
      "prompt": "Master architectural establishing shot of ... 16:9 photorealistic",
      "aspect": "16:9"
    }
  ],
  "shots": [
    {
      "shot_number": 1,
      "scene_id": "SC01",
      "shot_id": "SH01",
      "title": "Tên shot ngắn gọn",
      "timecode": "0:00 - 0:07",
      "duration": 7,
      "shot_type": "Wide Shot / Medium Close-up / OTS",
      "camera_angle": "Eye Level / Low Angle",
      "camera_motion": "Dynamic dolly in / Orbiting steadycam",
      "lighting": "Cinematic chiaroscuro, warm key light and cold teal rim light",
      "first_frame_description": "Mô tả bố cục, vị trí nhân vật, tư thế, biểu cảm ở frame mở đầu (Tiếng Việt)",
      "image_prompt": "Live-action dynamic cinematic shot: [Character description]. [Setting description]. [Composition and lighting], 35mm film grain, 8k photorealistic, 16:9",
      "video_prompt": "Live-action dynamic cinematic motion: [Physical action and performance]. [Camera movement]. [Environmental movement], fluid natural human motion, alive, dynamic physical action, real-time cinema physics, dynamic steadycam tracking, NOT a static image",
      "audio_cue": "Lời hát hoặc thoại tại shot này",
      "lyric_line": "Đoạn lời hát",
      "end_state": "Trạng thái kết thúc shot để nối tiếp shot sau",
      "transition": "Cut / Match Cut",
      "required_references": ["REF_CHAR_01_FRONT_V1", "REF_SET_01_WIDE_V1"],
      "negative_prompt": "static photo, still image, photo zoom, slideshow, ken burns effect, frozen frame, motionless subject, 3D CGI, anime, deformed anatomy, low quality"
    }
  ]
}
```

Tuyệt đối không viết thêm lời giải thích nào ngoài khối JSON trên.
"""


def extract_character_signatures(visual_locks: Dict[str, Any], ref_library: List[Dict[str, Any]], visual_bible: Dict[str, Any], ref_pack: Dict[str, Any]) -> Dict[str, str]:
    """Extract clean, rich character and setting signatures from locks and assets."""
    signatures = {}

    # 1. From visual_locks char_locks
    char_locks = visual_locks.get("char_locks", []) if isinstance(visual_locks, dict) else []
    for c in char_locks:
        c_id = c.get("id", "CHAR_01")
        desc = c.get("description", "").strip()
        if desc:
            signatures[c_id] = desc
            signatures[c.get("name", "")] = desc

    # 2. From reference_asset_library
    for asset in ref_library:
        asset_id = asset.get("asset_id", "")
        prompt = asset.get("prompt", "").strip()
        cleaned = re.sub(r'^(?:REF_[A-Z0-9_]+|Cinematic portrait of|Master establishing shot of)[\s\:\-]+', '', prompt, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'[,.\s]+(?:photorealistic|16:9|8k resolution|8k|35mm film grain|masterpiece)[\s,.]*$', '', cleaned, flags=re.IGNORECASE).strip(' ,.')
        if cleaned:
            signatures[asset_id] = cleaned

    # 3. Fallbacks from legacy visual_bible and ref_pack
    if "primary" not in signatures:
        legacy_primary = ref_pack.get("character_primary") or ref_pack.get("character_prompt") or visual_bible.get("character_lock", "")
        if legacy_primary:
            cleaned = re.sub(r'[,.\s]+(?:photorealistic|16:9|8k resolution|8k|35mm film grain|masterpiece)[\s,.]*$', '', legacy_primary, flags=re.IGNORECASE).strip(' ,.')
            signatures["primary"] = cleaned
            signatures["CHAR_01"] = cleaned

    return signatures


def enforce_character_consistency(
    shots: List[Dict[str, Any]], 
    visual_bible: Dict[str, Any] = None, 
    ref_pack: Dict[str, Any] = None,
    visual_locks: Dict[str, Any] = None,
    ref_library: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Inject character lock traits accurately per entity across all 4 modes."""
    visual_bible = visual_bible or {}
    ref_pack = ref_pack or {}
    visual_locks = visual_locks or {}
    ref_library = ref_library or []

    sigs = extract_character_signatures(visual_locks, ref_library, visual_bible, ref_pack)
    primary_sig = sigs.get("CHAR_01") or sigs.get("primary") or visual_bible.get("character_lock", "")

    for shot in shots:
        p = shot.get("image_prompt") or shot.get("prompt", "")
        vid_p = shot.get("video_prompt", "")
        p_lower = p.lower()
        title_lyric = f"{shot.get('title', '')} {shot.get('lyric_line', '')}".lower()

        # Check if shot features lead character
        has_lead_mention = any(k in title_lyric or k in p_lower for k in ["she", "he", "actor", "singer", "host", "guest", "nhân vật", "hề", "phú ông", "woman", "man", "clown", "chân dung", "portrait"])
        is_pure_landscape = any(k in p_lower for k in ["establishing shot of empty", "pure landscape", "no people", "dẫn nhập không gian"])

        if primary_sig and has_lead_mention and not is_pure_landscape:
            first_few_words = " ".join(primary_sig.split()[:4]).lower()
            if first_few_words not in p_lower:
                shot["image_prompt"] = f"{primary_sig}. {p}".strip()
                shot["prompt"] = shot["image_prompt"]
            if vid_p and first_few_words not in vid_p.lower():
                shot["video_prompt"] = f"{primary_sig}. {vid_p}".strip()

        # Enforce strong anti-distortion and anti-static negative prompt
        neg = shot.get("negative_prompt", "")
        banned_tags = (
            "modern microphone, sunglasses, clean modern skin, "
            "western caucasian features, 3D CGI plastic skin, "
            "anime, distorted anatomy, static photo, still image, motionless, frozen frame, ken burns effect, photo zoom"
        )
        if "ken burns effect" not in neg:
            shot["negative_prompt"] = f"{neg}, {banned_tags}".strip(", ")

    return shots


def enforce_video_motion(shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform static prompts into active live-action video cinematography across all shots."""
    motion_verbs = [
        "moves", "walking", "running", "gesturing", "talking", "speaking", "singing", 
        "turning", "dancing", "spinning", "lunging", "splashing", "billowing", 
        "tracking", "dolly", "sweeping", "whipping", "stumbling", "wiping", "looking"
    ]
    motion_directive = "fluid natural human motion, alive, dynamic physical action, real-time cinema physics, expressive theatrical gestures, NOT a static image, no frozen frames, dynamic steadycam tracking"
    anti_still = "static photo, still image, photo zoom, slideshow, ken burns effect, frozen frame, motionless subject, camera panning over still image"

    for shot in shots:
        vid_p = shot.get("video_prompt") or shot.get("prompt", "")
        p_lower = vid_p.lower()

        vid_p = re.sub(r'\bslow push-in shot of\b', 'Dynamic cinematic steadycam tracking into', vid_p, flags=re.IGNORECASE)
        vid_p = re.sub(r'\bstatic shot of\b', 'Live-action dramatic camera movement of', vid_p, flags=re.IGNORECASE)

        has_motion = any(v in p_lower for v in motion_verbs)
        if not has_motion or "fluid natural human motion" not in vid_p:
            vid_p = f"{vid_p.rstrip('.')}. {motion_directive}."

        shot["video_prompt"] = vid_p
        if not shot.get("prompt"):
            shot["prompt"] = vid_p

        neg = shot.get("negative_prompt", "")
        if "ken burns effect" not in neg:
            shot["negative_prompt"] = f"{neg}, {anti_still}".strip(", ")

    return shots


def calibrate_audio_timeline(shots: List[Dict[str, Any]], audio_duration: Optional[float]) -> List[Dict[str, Any]]:
    """Calibrate shot count and durations to fully cover 100% of the audio timeline."""
    if not audio_duration or audio_duration <= 10 or not shots:
        return shots

    target_sec = int(round(audio_duration))
    current_total = sum(s.get("duration", 7) for s in shots)

    if len(shots) > 0 and current_total < target_sec * 0.75:
        avg_shot_dur = 8
        needed_shots = max(len(shots), int(round(target_sec / avg_shot_dur)))

        angle_variations = [
            ("Master Tracking Shot", "Dynamic low-angle wide camera tracking"),
            ("Intense Close-up", "Extreme close-up macro tracking on face micro-expressions"),
            ("Reverse Angle Dynamic", "Over-the-shoulder dynamic camera movement"),
            ("Dutch Angle Climax", "Tilted Dutch-angle handheld camera motion")
        ]

        expanded_shots = []
        while len(expanded_shots) < needed_shots:
            for i, base_shot in enumerate(shots):
                if len(expanded_shots) >= needed_shots:
                    break
                copy_s = dict(base_shot)
                var_idx = len(expanded_shots) // len(shots)
                if var_idx > 0:
                    var_title, var_cam = angle_variations[(var_idx - 1) % len(angle_variations)]
                    copy_s["title"] = f"{base_shot.get('title', 'Shot')} (Góc quay {var_idx + 1})"
                    copy_s["camera_motion"] = var_cam
                    copy_s["prompt"] = f"{var_cam}. {base_shot.get('prompt', '')}"
                    if "video_prompt" in copy_s:
                        copy_s["video_prompt"] = f"{var_cam}. {copy_s['video_prompt']}"
                copy_s["shot_number"] = len(expanded_shots) + 1
                copy_s["shot_num"] = copy_s["shot_number"]
                expanded_shots.append(copy_s)
        shots = expanded_shots

    n = len(shots)
    base_dur = target_sec // n
    remainder = target_sec % n

    for i, s in enumerate(shots):
        s["duration"] = base_dur + (1 if i < remainder else 0)
        s["shot_number"] = i + 1
        s["shot_num"] = i + 1

    return shots


def parse_srt_to_segments(srt_text: str) -> List[Dict[str, Any]]:
    """Parse standard SRT subtitle text into timed segments."""
    if not srt_text or not srt_text.strip():
        return []

    pattern = re.compile(
        r'(\d+)\s*\r?\n(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*\r?\n([\s\S]*?)(?=(?:\r?\n\s*\d+\s*\r?\n|\Z))'
    )
    results = []
    def to_sec(ts):
        ts = ts.strip().replace(',', '.')
        parts = ts.split(':')
        if len(parts) == 3:
            return round(float(parts[0])*3600 + float(parts[1])*60 + float(parts[2]), 2)
        elif len(parts) == 2:
            return round(float(parts[0])*60 + float(parts[1]), 2)
        return round(float(ts), 2)

    for m in pattern.finditer(srt_text):
        idx = int(m.group(1))
        start_s = to_sec(m.group(2))
        end_s = to_sec(m.group(3))
        lyric = m.group(4).strip().replace('\r\n', ' ').replace('\n', ' ')
        lyric = re.sub(r'<[^>]+>', '', lyric).strip()
        if lyric:
            results.append({
                'index': idx,
                'start': start_s,
                'end': end_s,
                'duration': round(end_s - start_s, 2),
                'text': lyric
            })
    return results


def parse_lrc_to_segments(lrc_text: str) -> List[Dict[str, Any]]:
    """Parse standard or enhanced LRC lyrics into timed segments."""
    if not lrc_text or not lrc_text.strip():
        return []
    lines = lrc_text.splitlines()
    timed_lines = []
    for line in lines:
        line = line.strip()
        matches = list(re.finditer(r'\[(\d{1,2}):(\d{2})(?:[,\.](\d{1,3}))?\]', line))
        if not matches:
            continue
        text = line[matches[-1].end():].strip()
        text = re.sub(r'<[^>]+>', '', text).strip()
        if not text or text.lower().startswith(('ti:', 'ar:', 'al:', 'by:', 'offset:', 'length:')):
            continue
        for m in matches:
            mins, secs = int(m.group(1)), int(m.group(2))
            millis = m.group(3) or '0'
            ms = int(millis) * 10 if len(millis) == 2 else (int(millis)*100 if len(millis) == 1 else int(millis[:3]))
            start_s = round(mins * 60 + secs + ms / 1000.0, 2)
            timed_lines.append((start_s, text))
    timed_lines.sort(key=lambda x: x[0])
    results = []
    for i, (start_s, text) in enumerate(timed_lines):
        end_s = timed_lines[i + 1][0] if i + 1 < len(timed_lines) else round(start_s + 7.0, 2)
        dur = round(max(1.0, end_s - start_s), 2)
        results.append({'index': i + 1, 'start': start_s, 'end': end_s, 'duration': dur, 'text': text})
    return results


def parse_timed_lyrics(content: str) -> List[Dict[str, Any]]:
    """Unified parser supporting both SRT and LRC formats."""
    if not content or not content.strip():
        return []
    if "-->" in content:
        return parse_srt_to_segments(content)
    elif "[" in content and "]" in content:
        return parse_lrc_to_segments(content)
    return parse_srt_to_segments(content)


def group_srt_into_shots(
    srt_items: List[Dict[str, Any]], 
    audio_duration: Optional[float] = None, 
    min_dur: float = 5.0, 
    max_dur: float = 9.5
) -> List[Dict[str, Any]]:
    """Group subtitle cues and instrumental intervals into continuous cinematic shots covering 100% of the timeline."""
    if not srt_items:
        if audio_duration and audio_duration > 5.0:
            n_shots = max(1, int(round(audio_duration / 7.5)))
            shots = []
            dur_per_shot = audio_duration / n_shots
            for i in range(n_shots):
                st = round(i * dur_per_shot, 2)
                et = round(audio_duration if i == n_shots - 1 else (i + 1) * dur_per_shot, 2)
                shots.append({
                    'start': st,
                    'end': et,
                    'duration': round(et - st, 2),
                    'lyrics': [f'[Phân cảnh {i+1}]'],
                    'srt_indices': [],
                    'is_instrumental': True,
                    'subject': 'lead_character' if i % 2 == 0 else 'landscape',
                    'refs': ['REF_CHAR_01_FRONT_V1'] if i % 2 == 0 else ['REF_SET_01_WIDE_V1']
                })
            return shots
        return []

    shots = []

    def make_narrative_interlude_shots(
        start_t: float, 
        end_t: float, 
        section_type: str, 
        prev_shot: Optional[Dict[str, Any]] = None, 
        next_item: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        total_d = round(end_t - start_t, 2)
        if total_d < 3.0:
            return []
        
        target_len = 7.5
        n_inst = max(1, int(round(total_d / target_len)))
        inst_dur = round(total_d / n_inst, 2)
        res = []

        for j in range(n_inst):
            s_t = round(start_t + j * inst_dur, 2)
            e_t = round(end_t if j == n_inst - 1 else start_t + (j + 1) * inst_dur, 2)
            dur = round(e_t - s_t, 2)

            if section_type == "Intro":
                if j == 0:
                    sub_label = "[Dẫn nhập không gian - Thiết lập bối cảnh điện ảnh]"
                    sub_subject = "landscape"
                    sub_refs = ["REF_SET_01_WIDE_V1"]
                else:
                    sub_label = "[Dẫn nhập nhân vật - Nhân vật chính xuất hiện trong không gian]"
                    sub_subject = "lead_character"
                    sub_refs = ["REF_CHAR_01_FRONT_V1"]
            elif section_type == "Gian tấu":
                if j % 2 == 0:
                    sub_label = "[Gian tấu - Diễn xuất biểu cảm & chuyển động nhịp nhàng theo giai điệu]"
                    sub_subject = "lead_character"
                    sub_refs = ["REF_CHAR_01_FRONT_V1"]
                else:
                    sub_label = "[Gian tấu - Chuyển biến không gian & cú máy điện ảnh đặc tả]"
                    sub_subject = "landscape"
                    sub_refs = ["REF_SET_01_WIDE_V1"]
            elif section_type == "Outro":
                if j == 0:
                    sub_label = "[Vĩ thanh - Cao trào & giải tỏa cảm xúc của nhân vật]"
                    sub_subject = "lead_character"
                    sub_refs = ["REF_CHAR_01_FRONT_V1"]
                else:
                    sub_label = "[Hạ màn - Không gian tĩnh lặng khép lại câu chuyện]"
                    sub_subject = "landscape"
                    sub_refs = ["REF_SET_01_WIDE_V1"]
            else:
                sub_label = f"[{section_type} - Đoạn nối kịch bản {j+1}]"
                sub_subject = "lead_character"
                sub_refs = ["REF_CHAR_01_FRONT_V1"]

            res.append({
                'start': s_t,
                'end': e_t,
                'duration': dur,
                'lyrics': [sub_label],
                'srt_indices': [],
                'is_instrumental': True,
                'section_type': section_type,
                'subject': sub_subject,
                'refs': sub_refs
            })
        return res

    # 1. INTRO
    first_start = srt_items[0]['start']
    if first_start >= 2.5:
        intro_shots = make_narrative_interlude_shots(0.0, first_start, section_type="Intro", prev_shot=None, next_item=srt_items[0])
        shots.extend(intro_shots)

    # 2. VOCAL SHOTS
    current_shot = None
    for idx, item in enumerate(srt_items):
        item_subj = "lead_character"
        item_refs = ["REF_CHAR_01_FRONT_V1", "REF_SET_01_WIDE_V1"]

        if current_shot is None:
            current_shot = {
                'start': item['start'],
                'end': item['end'],
                'duration': item['duration'],
                'lyrics': [item['text']],
                'srt_indices': [item['index']],
                'is_instrumental': False,
                'section_type': 'Verse',
                'subject': item_subj,
                'refs': item_refs
            }
        else:
            gap = item['start'] - current_shot['end']
            if gap >= 3.5:
                shots.append(current_shot)
                interlude_shots = make_narrative_interlude_shots(
                    current_shot['end'], 
                    item['start'], 
                    section_type="Gian tấu", 
                    prev_shot=current_shot, 
                    next_item=item
                )
                shots.extend(interlude_shots)
                current_shot = {
                    'start': item['start'],
                    'end': item['end'],
                    'duration': item['duration'],
                    'lyrics': [item['text']],
                    'srt_indices': [item['index']],
                    'is_instrumental': False,
                    'section_type': 'Verse',
                    'subject': item_subj,
                    'refs': item_refs
                }
            else:
                potential_dur = item['end'] - current_shot['start']
                if current_shot['duration'] < min_dur or (potential_dur <= max_dur and len(current_shot['lyrics']) < 3):
                    current_shot['end'] = item['end']
                    current_shot['duration'] = round(item['end'] - current_shot['start'], 2)
                    current_shot['lyrics'].append(item['text'])
                    current_shot['srt_indices'].append(item['index'])
                else:
                    shots.append(current_shot)
                    current_shot = {
                        'start': item['start'],
                        'end': item['end'],
                        'duration': item['duration'],
                        'lyrics': [item['text']],
                        'srt_indices': [item['index']],
                        'is_instrumental': False,
                        'section_type': 'Verse',
                        'subject': item_subj,
                        'refs': item_refs
                    }

    if current_shot:
        shots.append(current_shot)

    # 3. OUTRO
    if audio_duration and audio_duration > 0:
        last_end = shots[-1]['end'] if shots else 0.0
        outro_gap = audio_duration - last_end
        if outro_gap >= 3.5:
            outro_shots = make_narrative_interlude_shots(
                last_end, 
                audio_duration, 
                section_type="Outro", 
                prev_shot=shots[-1] if shots else None, 
                next_item=None
            )
            shots.extend(outro_shots)

    # 4. Formats
    for i, s in enumerate(shots):
        s['shot_number'] = i + 1
        s['shot_num'] = i + 1
        s['lyric_line'] = ' — '.join(s['lyrics'])
        s['duration'] = max(4, min(int(round(s['duration'])), 14))
        start_min, start_sec = int(s['start']) // 60, int(s['start']) % 60
        end_min, end_sec = int(s['end']) // 60, int(s['end']) % 60
        s['timecode'] = f"{start_min}:{start_sec:02d} - {end_min}:{end_sec:02d}"
        if s.get('is_instrumental'):
            s['title'] = f"Shot {i+1} [{s['timecode']}]: {s['lyrics'][0]}"
        else:
            s['title'] = f"Shot {i+1} [{s['timecode']}]: {s['lyric_line'][:32]}"
    
    return shots


def parse_full_director_plan(markdown_text: str, fallback_lyrics: str = "", fallback_style: str = "") -> Dict[str, Any]:
    """Bulletproof parser extracting new unified schema (project_info, creative_treatment, visual_locks, reference_asset_library, shots) and mapping backwards-compatible keys."""
    shots = []
    project_info = {}
    creative_treatment = {}
    visual_locks = {}
    ref_library = []
    visual_motif = ""
    visual_bible = {}
    reference_pack = {}

    json_blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', markdown_text)
    candidates = json_blocks + [markdown_text]

    for cand in candidates:
        cand_clean = cand.strip()
        start = cand_clean.find('{')
        end = cand_clean.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = cand_clean[start:end+1]
            try:
                data = json.loads(json_str)
                if isinstance(data, dict):
                    project_info = data.get("project_info", {})
                    creative_treatment = data.get("creative_treatment", {})
                    visual_locks = data.get("visual_locks", {})
                    ref_library = data.get("reference_asset_library", [])

                    visual_motif = data.get("visual_motif") or creative_treatment.get("theme") or creative_treatment.get("concept") or ""
                    visual_bible = data.get("visual_bible", {})
                    reference_pack = data.get("reference_pack", {})

                    # Derive visual_bible from visual_locks if missing
                    if not visual_bible and visual_locks:
                        char_locks = visual_locks.get("char_locks", [])
                        set_locks = visual_locks.get("set_locks", [])
                        style_locks = visual_locks.get("style_locks", [])
                        wardrobe_locks = visual_locks.get("wardrobe_locks", [])
                        visual_bible = {
                            "character_lock": char_locks[0].get("description", "") if char_locks else "",
                            "location_lock": set_locks[0].get("description", "") if set_locks else "",
                            "style_lock": style_locks[0].get("description", "") if style_locks else "",
                            "wardrobe_lock": wardrobe_locks[0].get("description", "") if wardrobe_locks else ""
                        }

                    # Derive reference_pack from reference_asset_library if missing
                    if not reference_pack and ref_library:
                        for asset in ref_library:
                            grp = asset.get("lock_group", "")
                            p = asset.get("prompt", "")
                            if grp in ("CHAR_LOCK", "ARTIST_ID_LOCK") and "character_primary" not in reference_pack:
                                reference_pack["character_primary"] = p
                            elif grp in ("CHAR_LOCK", "ARTIST_ID_LOCK") and "character_secondary" not in reference_pack:
                                reference_pack["character_secondary"] = p
                            elif grp == "SET_LOCK" and "location_main" not in reference_pack:
                                reference_pack["location_main"] = p
                            elif grp == "PROP_LOCK" and "prop_primary" not in reference_pack:
                                reference_pack["prop_primary"] = p

                    raw_shots = data.get("shots", [])
                    if isinstance(raw_shots, list) and len(raw_shots) > 0:
                        for idx, s in enumerate(raw_shots):
                            img_p = s.get("image_prompt") or s.get("prompt", "").strip()
                            vid_p = s.get("video_prompt") or s.get("prompt", "").strip()
                            shots.append({
                                "shot_number": s.get("shot_number", idx + 1),
                                "shot_num": s.get("shot_number", idx + 1),
                                "scene_id": s.get("scene_id", f"SC{idx+1:02d}"),
                                "shot_id": s.get("shot_id", f"SH{idx+1:02d}"),
                                "section": s.get("section", f"Shot {idx+1}"),
                                "title": s.get("title", f"Shot {idx+1}"),
                                "lyric_line": s.get("lyric_line", s.get("audio_cue", "")),
                                "camera_motion": s.get("camera_motion", "dynamic_steadycam"),
                                "start_frame": s.get("first_frame_description", s.get("start_frame", "")),
                                "first_frame_description": s.get("first_frame_description", s.get("start_frame", "")),
                                "end_frame": s.get("end_state", s.get("end_frame", "")),
                                "duration": max(5, min(int(s.get("duration", 7)), 12)),
                                "aspect": s.get("aspect", "16:9"),
                                "prompt": img_p,
                                "image_prompt": img_p,
                                "video_prompt": vid_p,
                                "required_references": s.get("required_references", []),
                                "negative_prompt": s.get("negative_prompt", "ugly, deformed, mutated, text, watermark, blurry, low quality")
                            })
                        if shots:
                            return {
                                "project_info": project_info,
                                "creative_treatment": creative_treatment,
                                "visual_locks": visual_locks,
                                "reference_asset_library": ref_library,
                                "visual_motif": visual_motif,
                                "visual_bible": visual_bible,
                                "reference_pack": reference_pack,
                                "shots": shots
                            }
            except Exception:
                pass

    # Regex Fallback
    header_regex = re.compile(
        r'(?:^|\n)(?:###?\s*|\*\*\s*|\b)(?:SHOT|Shot|Loop|LOOP|Cảnh|C\u1ea3nh|Ph\xe2n c\u1ea3nh|Scene|SCENE)\s*(\d+)[:\.\s-]*([^\n]*)',
        re.IGNORECASE
    )
    splits = list(header_regex.finditer(markdown_text))
    if splits:
        for i, match in enumerate(splits):
            shot_num = match.group(1).strip()
            shot_title = match.group(2).strip().strip('*#:')
            start_pos = match.end()
            end_pos = splits[i+1].start() if i + 1 < len(splits) else len(markdown_text)
            body = markdown_text[start_pos:end_pos]

            dur_match = re.search(r'(?:Thời lượng|Duration)[:\s]*(\d+)\s*s?', body, re.IGNORECASE)
            duration = int(dur_match.group(1)) if dur_match else 7

            codeblocks = re.findall(r'```(?:[a-zA-Z]*\n)?(.*?)```', body, re.DOTALL)
            prompt = ""
            negative_prompt = "ugly, deformed, mutated, bad anatomy, text, watermark, blurry, low quality"

            for cb in codeblocks:
                cb_clean = cb.strip()
                if not cb_clean:
                    continue
                if any(w in cb_clean.lower() for w in ["ugly", "deformed", "mutated", "bad anatomy", "watermark"]):
                    negative_prompt = cb_clean
                elif not prompt:
                    prompt = cb_clean

            if not prompt:
                p_inline = re.search(r'(?:FLOW|VEO|MUSE|VIDEO|IMAGE)?\s*PROMPT[^:\n]*:\s*([^\n]+(?:\n[^\n#]+)*)', body, re.IGNORECASE)
                if p_inline:
                    prompt = p_inline.group(1).strip().strip('`*')

            if prompt and len(prompt) > 10:
                shots.append({
                    "shot_number": int(shot_num) if shot_num.isdigit() else len(shots) + 1,
                    "shot_num": int(shot_num) if shot_num.isdigit() else len(shots) + 1,
                    "section": f"Shot {shot_num}",
                    "title": f"Shot {shot_num}: {shot_title}" if shot_title else f"Shot {shot_num}",
                    "duration": max(5, min(duration, 12)),
                    "aspect": "16:9",
                    "prompt": prompt,
                    "image_prompt": prompt,
                    "video_prompt": prompt,
                    "negative_prompt": negative_prompt
                })
        if shots:
            return {
                "project_info": project_info,
                "creative_treatment": creative_treatment,
                "visual_locks": visual_locks,
                "reference_asset_library": ref_library,
                "visual_motif": visual_motif,
                "visual_bible": visual_bible,
                "reference_pack": reference_pack,
                "shots": shots
            }

    # Emergency Fallback
    lyrics_lines = [l.strip() for l in (fallback_lyrics or "").splitlines() if l.strip() and not l.strip().startswith(("#", "//"))]
    sections = [lyrics_lines[i] for i in range(0, min(len(lyrics_lines), 8))] if lyrics_lines else ["Phân cảnh mở đầu", "Phân cảnh phát triển", "Phân cảnh cao trào", "Phân cảnh kết thúc"]

    for idx, sec in enumerate(sections[:8]):
        shots.append({
            "shot_number": idx + 1,
            "shot_num": idx + 1,
            "section": f"Scene {idx+1}",
            "title": f"Shot {idx+1}: {sec[:35]}",
            "lyric_line": sec[:80],
            "duration": 7,
            "aspect": "16:9",
            "prompt": f"Live-action dynamic cinematic shot, {fallback_style or 'cinematic 35mm atmosphere'}, dramatic lighting, 8k photorealistic",
            "image_prompt": f"Live-action dynamic cinematic shot, {fallback_style or 'cinematic 35mm atmosphere'}, dramatic lighting, 8k photorealistic",
            "video_prompt": f"Live-action dynamic cinematic motion, {fallback_style or 'cinematic 35mm atmosphere'}, fluid natural human motion, dynamic steadycam tracking",
            "negative_prompt": "ugly, deformed, mutated, text, watermark, blurry, low quality"
        })

    return {
        "project_info": {"title": "Dự án Video", "mode": "MUSIC_VIDEO"},
        "creative_treatment": {"concept": "Kế hoạch sản xuất Storyboard"},
        "visual_locks": visual_locks,
        "reference_asset_library": ref_library,
        "visual_motif": visual_motif or "Điện ảnh biểu cảm",
        "visual_bible": visual_bible,
        "reference_pack": reference_pack,
        "shots": shots
    }


def extract_shots_from_script(markdown_text: str, fallback_lyrics: str = "", fallback_style: str = "") -> List[Dict[str, Any]]:
    """Preserve backwards compatibility for endpoints returning just shots."""
    parsed = parse_full_director_plan(markdown_text, fallback_lyrics, fallback_style)
    return parsed.get("shots", [])


async def generate_mv_plan(
    cfg: AppConfig,
    song_title: str,
    lyrics: str,
    genre_style: str = "Pop Ballad",
    bpm: str = "85 BPM",
    vocal: str = "Nữ trầm ấm, da diết",
    mood: str = "Hoài niệm, buồn sâu lắng",
    extra_notes: str = "",
    audio_duration: Optional[float] = None,
    audio_url: Optional[str] = None,
    srt_content: Optional[str] = None,
    mode: Optional[str] = "auto"
) -> Dict[str, Any]:
    """Call configured AI LLM to generate structured production plan via the new AI Video Storyboard Director engine."""
    srt_shots = []
    srt_table_info = ""
    if srt_content:
        srt_items = parse_timed_lyrics(srt_content)
        srt_shots = group_srt_into_shots(srt_items, audio_duration=audio_duration)
        if srt_shots and (not audio_duration or srt_shots[-1]["end"] > audio_duration):
            audio_duration = srt_shots[-1]["end"]
            srt_table_lines = [
                f"- Cảnh {s['shot_number']} [{s['timecode']}] ({s['duration']}s): \"{s['lyric_line']}\""
                for s in srt_shots
            ]
            srt_table_info = "\n### BẢNG TIMECODE CHÍNH XÁC TỪ FILE PHỤ ĐỀ (.SRT):\n" + "\n".join(srt_table_lines) + f"""

QUY TẮC BẮT BUỘC KHI CÓ FILE PHỤ ĐỀ SRT:
1. Bạn BẮT BUỘC phải tạo ĐÚNG {len(srt_shots)} phân cảnh tương ứng với {len(srt_shots)} mục trong bảng timecode trên.
2. Tại mỗi phân cảnh, hành động điện ảnh của nhân vật và bối cảnh BẮT BUỘC phải ăn khớp CHÍNH XÁC với ý nghĩa câu hát tại đúng mốc thời gian đó!
3. Giữ nguyên thời lượng (duration) và câu hát (lyric_line) của từng phân cảnh như trong bảng SRT.
"""

    if srt_shots:
        target_shots = len(srt_shots)
        audio_info = f"- **Thời lượng thực tế:** {int(audio_duration)} giây. BẮT BUỘC chia thành ĐÚNG {target_shots} phân cảnh tương ứng với {target_shots} mục timecode trong bảng phụ đề bên dưới!\n"
    else:
        target_shots = max(5, int(round(audio_duration / 7.5))) if audio_duration else 8
        audio_info = f"- **Thời lượng thực tế:** {int(audio_duration)} giây (~{int(audio_duration)//60}p{int(audio_duration)%60:02d}s). BẮT BUỘC chia thành khoảng {target_shots} phân cảnh (mỗi cảnh 6-9s) sao cho TỔNG THỜI LƯỢNG các phân cảnh BẰNG ĐÚNG {int(audio_duration)}s để phủ kín 100% video!\n" if audio_duration else ""

    user_prompt = f"""DỰ ÁN SẢN XUẤT VIDEO AI: {song_title}
- **Thể loại / Phong cách / Mood:** {genre_style}
- **Chế độ sản xuất mong muốn:** {mode or 'Tự động nhận diện (Smart Mode Detector)'}
{audio_info}{srt_table_info}- **Ghi chú thêm từ Đạo diễn:** {extra_notes or "Không"}

**Nội dung / Lời bài hát / Kịch bản đầu vào:**
\"\"\"
{lyrics}
\"\"\"

ÁP DỤNG QUY TRÌNH # AI VIDEO STORYBOARD DIRECTOR:
1. Xác định chế độ phù hợp: MODE 1 (Music Video), MODE 2 (Comedy), MODE 3 (Podcast), MODE 4 (Cinematic Story).
2. Xây dựng Creative Treatment (Concept, Vision, Theme, Storyline, Emotional Arc, Visual Language, Color Palette, Cinematography).
3. Thiết lập hệ thống khóa tài nguyên (visual_locks) và Thư viện Ảnh Tham Chiếu (reference_asset_library) với Asset ID cụ thể:
   - [CHAR LOCK]: Nhân vật chính (và nhân vật phụ nếu có).
   - [SET LOCK]: Bối cảnh chính.
   - [PROP LOCK]: Đạo cụ biểu tượng.
   - [STYLE LOCK]: Phong cách điện ảnh.
4. Lập danh sách phân cảnh (shots) phủ kín 100% thời lượng theo đúng mốc thời gian.
5. Viết riêng biệt:
   - image_prompt: Prompt tiếng Anh tạo ảnh keyframe mở đầu.
   - video_prompt: Prompt tiếng Anh tạo video chuyển động sống động (Anti-Ken-Burns, camera di động, live-action motion).

BẮT BUỘC trả về kết quả dưới dạng duy nhất một khối ```json ... ``` theo đúng cấu trúc JSON đã hướng dẫn.
"""

    headers = {}
    payload = {}
    url = ""
    
    # 1. Google Gemini Native API
    if cfg.ai_provider == "gemini":
        base = (cfg.ai_base_url or "").rstrip("/")
        if "generativelanguage.googleapis.com" in base or not base:
            model = cfg.ai_model or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={cfg.ai_api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{CANVAS_DIRECTOR_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 8192
                }
            }
        else:
            url = f"{base}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg.ai_api_key}"
            }
            payload = {
                "model": cfg.ai_model or "gemini-1.5-flash",
                "messages": [
                    {"role": "system", "content": CANVAS_DIRECTOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7
            }

    # 2. OpenAI / DeepSeek / Claude / Custom Proxy
    else:
        base = (cfg.ai_base_url or "https://api.openai.com/v1").rstrip("/")
        if not base.endswith("/chat/completions"):
            url = f"{base}/chat/completions"
        else:
            url = base
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.ai_api_key}"
        }
        if cfg.custom_headers:
            headers.update(cfg.custom_headers)
            
        payload = {
            "model": cfg.ai_model or "gpt-4o",
            "messages": [
                {"role": "system", "content": CANVAS_DIRECTOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }

    timeout = httpx.Timeout(120.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, proxy=cfg.ai_network_proxy) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise Exception(f"AI API Error (HTTP {resp.status_code}): {resp.text}")
        
        data = resp.json()
        if "candidates" in data:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        elif "choices" in data:
            content = data["choices"][0]["message"]["content"]
        else:
            raise Exception(f"Unknown AI response structure: {data}")
            
    parsed = parse_full_director_plan(content, fallback_lyrics=lyrics, fallback_style=genre_style)
    shots = parsed.get("shots", [])
    visual_locks = parsed.get("visual_locks", {})
    ref_library = parsed.get("reference_asset_library", [])
    visual_bible = parsed.get("visual_bible", {})
    ref_pack = parsed.get("reference_pack", {})

    shots = enforce_character_consistency(shots, visual_bible, ref_pack, visual_locks, ref_library)
    shots = enforce_video_motion(shots)
    shots = calibrate_audio_timeline(shots, audio_duration)
    
    if srt_shots:
        aligned_shots = []
        for idx, ref_s in enumerate(srt_shots):
            if idx < len(shots):
                s = dict(shots[idx])
            else:
                primary_char = (
                    visual_bible.get("character_lock") 
                    or (ref_library[0]["prompt"] if ref_library else "")
                    or "Lead character in cinematic setting"
                )
                style_lock = visual_bible.get("style_lock") or "Cinematic chiaroscuro, 35mm film grain, 16:9"
                s = {
                    "shot_number": idx + 1,
                    "shot_num": idx + 1,
                    "section": f"Shot {idx+1}",
                    "title": f"Shot {idx+1}: {ref_s['lyric_line'][:35]}",
                    "camera_motion": "Dynamic cinematic steadycam tracking",
                    "aspect": "16:9",
                    "prompt": f"Live-action dynamic cinematic shot: {primary_char}. Expressive performance: \"{ref_s['lyric_line']}\". {style_lock}, 8k photorealistic, 16:9, NOT a static image.",
                    "image_prompt": f"Live-action dynamic cinematic shot: {primary_char}. Expressive performance: \"{ref_s['lyric_line']}\". {style_lock}, 8k photorealistic, 16:9.",
                    "video_prompt": f"Live-action dynamic cinematic motion: {primary_char}. Expressive movement reflecting \"{ref_s['lyric_line']}\", fluid natural human motion, alive, dynamic physical action, real-time cinema physics, dynamic steadycam tracking, NOT a static image.",
                    "negative_prompt": "static photo, still image, photo zoom, slideshow, ken burns effect, frozen frame, motionless subject, 3D CGI, anime, low quality"
                }

            s["shot_number"] = idx + 1
            s["shot_num"] = idx + 1
            s["lyric_line"] = ref_s["lyric_line"]
            s["duration"] = ref_s["duration"]
            s["start_time"] = ref_s["start"]
            s["end_time"] = ref_s["end"]
            s["timecode"] = ref_s["timecode"]
            s["title"] = f"Shot {idx+1} [{ref_s['timecode']}]: {ref_s['lyric_line'][:32]}"
            aligned_shots.append(s)

        shots = aligned_shots

    return {
        "success": True,
        "script_markdown": content,
        "project_info": parsed.get("project_info", {}),
        "creative_treatment": parsed.get("creative_treatment", {}),
        "visual_locks": parsed.get("visual_locks", {}),
        "reference_asset_library": parsed.get("reference_asset_library", []),
        "visual_motif": parsed.get("visual_motif", ""),
        "visual_bible": parsed.get("visual_bible", {}),
        "reference_pack": parsed.get("reference_pack", {}),
        "shots_count": len(shots),
        "shots": shots
    }
