import re
import json
import httpx
from typing import Dict, Any, List, Optional
from core.config import AppConfig

CANVAS_DIRECTOR_SYSTEM_PROMPT = """# AI MV DIRECTOR V5 - MASTERCLASS CINEMATIC & MOTION ENGINE
(Tối ưu hóa chuyên sâu cho Muse AI, Google Veo 2, Kling 1.5, Sora, Google Flow & Storyboard Workflow Canvas)

Bạn là Giám Đốc Sáng Tạo và Đạo Diễn Music Video (MV) điện ảnh hàng đầu thế giới. Bạn biến phong cách âm nhạc Suno (Style Prompt) và Lời bài hát (Lyrics) thành một Kế Hoạch Sản Xuất Music Video Điện Ảnh Đỉnh Cao (Narrative Storyboard Masterclass).

## 3 QUY TẮC CỐT LÕI CỦA ĐẠO DIỄN:

### 1. QUY TẮC ĐỒNG NHẤT NHÂN VẬT THÉP (CHARACTER CONSISTENCY LOCK):
- Khi xác định CHARACTER_LOCK và character_prompt (CHARACTER_PRIMARY_ID), bạn phải chỉ định CHI TIẾT ĐẶC TẢ TẠO HÌNH CỐ ĐỊNH: giới tính, độ tuổi, vóc dáng, cấu trúc xương mặt, đặc điểm hóa trang/nhận dạng độc nhất (ví dụ: gã hề 40 tuổi người Việt hốc hác, mặt phết vôi trắng loang lổ, viền mắt mực đen hất ngược kiểu Hát Bội, nụ cười son chu sa vẽ lệch dài tới mang tai) và TRANG PHỤC CỐ ĐỊNH (áo the nâu sồng rách vá, khăn đầu vải thô).
- **QUY TẮC BẮT BUỘC:** MỌI PHÂN CẢNH (SHOT) CÓ SỰ XUẤT HIỆN CỦA NHÂN VẬT CHÍNH ĐỀU PHẢI SAO CHÉP ĐẦY ĐỦ ĐOẠN ĐẶC TẢ TẠO HÌNH NÀY vào prompt của shot đó.
- TUYỆT ĐỐI CẤM chỉ viết chung chung "a person", "a woman", "the clown" mà không lặp lại chi tiết tạo hình, vì AI tạo ảnh sẽ tạo ra người lạ khác hoàn toàn!
- TUYỆT ĐỐI CẤM các chi tiết hiện đại lạc quẻ (micro hiện đại, kính râm, đèn neon, bối cảnh phòng thu) nếu tác phẩm là dân gian/cổ điển/thế kỷ trước.

### 2. QUY TẮC CHUYỂN ĐỘNG VIDEO 100% ĐỘNG (ANTI-KEN-BURNS & CẤM ZOOM ẢNH TĨNH):
- TUYỆT ĐỐI CẤM miêu tả ảnh tĩnh rồi chỉ thêm các từ khóa "slow zoom in/out", "static establishing shot", "ken burns pan". Video AI sẽ chỉ phóng to thu nhỏ ảnh tĩnh gây nhàm chán!
- Mọi prompt video BẮT BUỘC phải là **CHUYỂN ĐỘNG HÀNH ĐỘNG THỰC TẾ (Live-Action Dynamic Cinematography)**:
  + **Hành động cụ thể của nhân vật:** gã hề giật phắt dải khăn, vung tay múa may giễu cợt giật cục theo nhịp trống tuồng, bước lảo đảo vấp ngã, há to miệng gào thét không ra tiếng, ngực phập phồng thở dốc, hai bàn tay gầy vục mạnh vào thau đồng làm nước bắn tung tóe.
  + **Hiệu ứng môi trường động:** tàn lửa đuốc bay mù mịt, khói đen cuộn tròn bay qua mặt, tà áo the rách bay phần phật trong gió đêm.
  + **Máy quay động:** Cinematic dynamic dolly tracking, low-angle whip pan, orbiting camera, smooth steadycam follow.
  + **Từ khóa chuyển động bắt buộc:** "fluid natural human motion, alive, dynamic physical action, expressive gestures, NOT a static image, dynamic steadycam tracking".
- Negative prompt của MỌI shot bắt buộc có: "static image, still photo, photo zoom, slideshow, ken burns effect, frozen frame, motionless subject".

### 3. QUY TẮC KHỚP THỜI LƯỢNG AUDIO TIMELINE (100% COVERAGE):
- Nếu được cung cấp thời lượng bài nhạc thực tế (ví dụ: 180s, 225s), bạn BẮT BUỘC phải chia bài hát thành đủ số phân cảnh (mỗi cảnh từ 6 đến 9 giây) sao cho TỔNG duration của tất cả các shot PHỦ KÍN 100% THỜI LƯỢNG BÀI HÁT TỪ 0:00 ĐẾN KẾT THÚC.

## QUY TẮC ĐỊNH DẠNG ĐẦU RA BẮT BUỘC:
Bạn BẮT BUỘC phải xuất kết quả dưới dạng DUY NHẤT MỘT KHỐI JSON hợp lệ nằm trong ```json ... ``` theo đúng cấu trúc sau:

```json
{
  "song_title": "Tên bài hát",
  "music_genre": "Style nhạc đầy đủ",
  "visual_motif": "Tên và ý nghĩa motif thị giác trung tâm",
  "visual_bible": {
    "style_lock": "Điện ảnh 35mm, chiaroscuro contrast, tone màu...",
    "character_lock": "Nam/Nữ, tuổi, vóc người, khuôn mặt, biểu cảm...",
    "wardrobe_lock": "Bộ trang phục cố định bất biến...",
    "location_lock": "Bối cảnh chính cố định...",
    "inviolables": [
      "Chi tiết bất biến 1",
      "Chi tiết bất biến 2",
      "Chi tiết bất biến 3"
    ]
  },
  "reference_pack": {
    "character_primary": "Cinematic close-up portrait, a 40-year-old gaunt Vietnamese traditional folk theatre clown actor (Gã Kép Hề), hollow sunken cheeks, face covered in crude chalk-white lime paint with rough flaking texture, stylized sharp black ink eye contours inspired by Hat Boi opera, a grotesque smeared cinnabar red lipstick smile painted unnaturally wide across cheeks, wearing a tattered dark brown raw cotton ao tu than, dimly lit by flickering warm torchlight and ambient cold moonlight, extreme chiaroscuro contrast, 35mm film grain, 16:9 photorealistic masterpiece",
    "character_secondary": "Cinematic portrait of a 55-year-old wealthy Northern Vietnamese feudal landlord / Phu Ong (Lão Phú Ông), arrogant double chin, portly plump belly, wearing opulent dark emerald green embroidered silk robe with golden threads, holding an antique carved ivory fan, contemptuous smirk, warm lantern light, 16:9 photorealistic",
    "location_main": "Master architectural establishing shot of an ancient 19th-century Northern Vietnamese communal village courtyard (Sân Đình Làng Cổ) at midnight, curved mossy tile roof, ancient lim wood pillars, damp ground fog, burning bamboo torches casting dancing shadows, 16:9",
    "prop_primary": "Close-up macro shot of symbolic folk theatre props: a rough-carved wooden theatrical clown mask covered in flaking chalk-white lime paint, a tattered bamboo hand fan, beside a tarnished antique bronze water basin on damp stone courtyard floor, torchlight reflection, 16:9"
  },
  "shots": [
    {
      "shot_number": 1,
      "section": "Intro",
      "title": "Khúc Dạo Đầu Ma Quái",
      "lyric_line": "Đoạn lời bài hát ứng với cảnh này",
      "camera_motion": "Dynamic low-angle camera tracking",
      "start_frame": "Sân đình hoang vu mờ sương, đuốc cháy rừng rực",
      "end_frame": "Gã hề bước lảo đảo vào giữa sân, quạt nan vung vẩy",
      "duration": 8,
      "aspect": "16:9",
      "prompt": "Live-action dynamic cinematic shot: a 40-year-old gaunt Vietnamese traditional folk theatre clown actor, hollow sunken cheeks, crude flaking chalk-white painted lime face, stylized sharp black Hat Boi opera eyeliner, grotesque smeared cinnabar red lipstick smile, wearing tattered dark brown raw cotton ao tu than, stumbling erratically into an ancient 19th-century village courtyard at midnight. Dynamic steadycam tracking, bamboo torches violently flickering, glowing embers flying past his face, fluid natural human motion, expressive theatrical gestures, damp ground fog swirling, extreme chiaroscuro lighting, 35mm film grain, 8k photorealistic, 16:9, NOT a static image",
      "subject": "clown",
      "refs": ["character_primary", "location_main"],
      "negative_prompt": "static photo, still image, photo zoom, slideshow, ken burns effect, frozen frame, motionless subject, modern microphone, vintage microphone, sunglasses, modern clothing, 3D CGI plastic skin, anime, deformed fingers, extra limbs, western features, low quality"
    }
  ]
}
```
Tuyệt đối không viết thêm bất kỳ văn bản giải thích nào ngoài khối JSON trên.
"""


def enforce_character_consistency(shots: List[Dict[str, Any]], visual_bible: Dict[str, Any], ref_pack: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Inject character lock traits accurately per entity (Clown vs Phu Ong vs Prop vs Landscape) without cross-contamination."""
    char_lock = visual_bible.get("character_lock", "").strip()
    primary_prompt = ref_pack.get("character_primary") or ref_pack.get("character_prompt", "").strip()
    secondary_prompt = ref_pack.get("character_secondary", "").strip()
    location_prompt = ref_pack.get("location_main") or ref_pack.get("location_prompt", "").strip()
    prop_prompt = ref_pack.get("prop_primary", "").strip()

    def clean_sig(text: str, default: str) -> str:
        if not text:
            return default
        cleaned = re.sub(r'^(?:CHARACTER_PRIMARY_ID|CHARACTER_PRIMARY|CHARACTER_SECONDARY|MASTER_LOCATION|PROP_PRIMARY)[\s\:\-]+', '', text, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'[,.\s]+(?:photorealistic|16:9|8k resolution|8k|35mm film grain|masterpiece)[\s,.]*$', '', cleaned, flags=re.IGNORECASE).strip(' ,.')
        return cleaned if len(cleaned) > 20 else default

    clown_sig = clean_sig(primary_prompt or char_lock, "a 40-year-old gaunt Vietnamese traditional folk theatre clown actor, hollow sunken cheeks, crude chalk-white painted lime face, stylized black Hat Boi opera eyeliner, smeared cinnabar red lipstick smile, tattered dark brown raw cotton ao tu than")
    phu_ong_sig = clean_sig(secondary_prompt, "a wealthy 55-year-old Northern Vietnamese feudal landlord / Phu Ong, portly plump belly, arrogant double chin, luxurious dark emerald embroidered silk robe with golden embroidery, holding carved ivory fan")
    location_sig = clean_sig(location_prompt, "ancient 19th-century Northern Vietnamese communal village courtyard (dinh lang) at midnight, curved mossy tile roof, burning bamboo torches casting dancing shadows, damp ground fog")
    prop_sig = clean_sig(prop_prompt, "theatrical folk clown wooden mask covered in flaking chalk-white paint, beside a tattered bamboo fan and an antique bronze water basin")

    for shot in shots:
        p = shot.get("prompt", "")
        p_lower = p.lower()
        title_lyric = f"{shot.get('title', '')} {shot.get('lyric_line', '')}".lower()

        # Detect specific focal subject
        is_rich_man = any(k in title_lyric or k in p_lower for k in ["phú ông", "lão phú", "rich man", "bụng phệ", "quan lại", "địa chủ"])
        is_prop_only = any(k in title_lyric or k in p_lower for k in ["mặt nạ", "quạt nan rơi", "thau đồng", "giọt nước mắt rơi", "prop mask", "water basin"]) and not any(k in title_lyric for k in ["bước", "hát", "ngồi", "cười"])
        is_landscape = any(k in p_lower for k in ["establishing shot of empty", "pure landscape", "no people", "dẫn nhập không gian", "đuốc tàn dần, bóng tối nuốt"])
        is_clown = not is_rich_man and not is_landscape and not is_prop_only

        if is_rich_man:
            shot["subject"] = "rich_man"
            shot["refs"] = ["character_secondary", "location_main"]
            if "phu ong" not in p_lower and "landlord" not in p_lower and "wealthy" not in p_lower:
                shot["prompt"] = f"{phu_ong_sig}. {p}"
        elif is_prop_only:
            shot["subject"] = "prop"
            shot["refs"] = ["prop_primary", "location_main"]
            if "mask" not in p_lower and "basin" not in p_lower:
                shot["prompt"] = f"{prop_sig}. {p}"
        elif is_landscape:
            shot["subject"] = "landscape"
            shot["refs"] = ["location_main"]
            if "courtyard" not in p_lower and "dinh lang" not in p_lower:
                shot["prompt"] = f"{location_sig}. {p}"
        else:
            shot["subject"] = "clown"
            shot["refs"] = ["character_primary", "prop_primary"]
            if "clown" not in p_lower and "chalk-white" not in p_lower:
                shot["prompt"] = f"{clown_sig}. {p}"

        # Clean modern hallucinated artifacts
        shot["prompt"] = re.sub(r'\b(vintage microphone|modern microphone|sunglasses|neon lights|modern city)\b', 'flickering ambient torches, rustic atmospheric village environment', shot["prompt"], flags=re.IGNORECASE)

        # Enforce strong anti-modern / anti-CGI / anti-static negative tags
        neg = shot.get("negative_prompt", "")
        banned_tags = (
            "modern microphone, vintage microphone, sunglasses, clean modern skin, modern casual clothes, "
            "western caucasian features, blonde hair, 3D CGI plastic skin, "
            "anime, distorted anatomy, static photo, still image, motionless, frozen frame, ken burns effect, photo zoom"
        )
        if "ken burns effect" not in neg:
            shot["negative_prompt"] = f"{neg}, {banned_tags}".strip(", ")

    return shots


def enforce_video_motion(shots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform static prompts into active live-action video cinematography."""
    motion_verbs = ["moves", "walking", "running", "gesturing", "ripping", "crying", "dancing", "spinning", "lunging", "clashing", "splashing", "billowing", "fluttering", "tracking", "dolly", "sweeping", "whipping", "stumbling", "wiping"]

    for shot in shots:
        p = shot.get("prompt", "")
        p_lower = p.lower()

        p = re.sub(r'\bslow push-in shot of\b', 'Dynamic cinematic steadycam tracking into', p, flags=re.IGNORECASE)
        p = re.sub(r'\bstatic shot of\b', 'Live-action dramatic camera movement of', p, flags=re.IGNORECASE)

        has_motion = any(v in p_lower for v in motion_verbs)
        motion_directive = "fluid natural human motion, alive, dynamic physical action, real-time cinema physics, expressive theatrical gestures, NOT a static image, no frozen frames, dynamic steadycam tracking"

        if not has_motion or "fluid natural human motion" not in p:
            p = f"{p.rstrip('.')}. {motion_directive}."
        shot["prompt"] = p

        neg = shot.get("negative_prompt", "")
        anti_still = "static photo, still image, photo zoom, slideshow, ken burns effect, frozen frame, motionless subject, camera panning over still image"
        if "ken burns effect" not in neg:
            shot["negative_prompt"] = f"{neg}, {anti_still}".strip(", ")

    return shots


def calibrate_audio_timeline(shots: List[Dict[str, Any]], audio_duration: Optional[float]) -> List[Dict[str, Any]]:
    """Calibrate shot count and durations to fully cover 100% of the audio timeline."""
    if not audio_duration or audio_duration <= 10 or not shots:
        return shots

    target_sec = int(round(audio_duration))
    current_total = sum(s.get("duration", 7) for s in shots)

    # If shots only cover a small fraction of audio, expand with dynamic multi-angle shots
    if len(shots) > 0 and current_total < target_sec * 0.75:
        avg_shot_dur = 8
        needed_shots = max(len(shots), int(round(target_sec / avg_shot_dur)))

        angle_variations = [
            ("Master Tracking Shot", "Dynamic low-angle wide camera tracking"),
            ("Intense Close-up", "Extreme close-up macro tracking on face micro-expressions"),
            ("Reverse Angle Dynamic", "Over-the-shoulder dynamic camera movement"),
            ("Dutch Angle Climax", "Tilted Dutch-angle handheld camera motion with swirling embers")
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
                copy_s["shot_number"] = len(expanded_shots) + 1
                copy_s["shot_num"] = copy_s["shot_number"]
                expanded_shots.append(copy_s)
        shots = expanded_shots

    # Calibrate durations so sum(duration) == target_sec EXACTLY
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


def detect_subject_from_text(text: str) -> str:
    """Identify key character or focal subject from text/lyrics to guide continuity and scene cuts."""
    t = text.lower()
    if any(k in t for k in ["phú ông", "lão phú", "rich man", "bụng phệ", "quan lại", "địa chủ"]):
        return "rich_man"
    if any(k in t for k in ["hề", "kép", "clown", "bôi vôi", "chu sa", "hát bội", "chèo"]):
        return "clown"
    if any(k in t for k in ["đại cảnh", "sân đình", "bối cảnh", "landscape", "courtyard", "mái đình", "hoang vu", "sương mù"]):
        return "landscape"
    if any(k in t for k in ["gian tấu", "nhạc dạo", "dẫn nhập", "hạ màn", "vĩ thanh", "solo"]):
        return "instrumental"
    return "lead_character"


def group_srt_into_shots(
    srt_items: List[Dict[str, Any]], 
    audio_duration: Optional[float] = None, 
    min_dur: float = 5.0, 
    max_dur: float = 9.5
) -> List[Dict[str, Any]]:
    """Group subtitle cues and instrumental intervals (Intro, Interludes, Outro)
    into a continuous sequence of cinematic shots covering 100% of the audio timeline without any gaps,
    building organic Narrative Bridges between preceding and succeeding scenes.
    """
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
                    'subject': 'clown' if i % 2 == 0 else 'landscape',
                    'refs': ['character_primary'] if i % 2 == 0 else ['location_main']
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

        prev_subj = prev_shot.get('subject', 'clown') if prev_shot else 'landscape'
        next_text = next_item.get('text', '') if next_item else ''
        next_subj = detect_subject_from_text(next_text) if next_item else 'clown'

        for j in range(n_inst):
            s_t = round(start_t + j * inst_dur, 2)
            e_t = round(end_t if j == n_inst - 1 else start_t + (j + 1) * inst_dur, 2)
            dur = round(e_t - s_t, 2)

            if section_type == "Intro":
                if n_inst == 1:
                    sub_label = "[Dẫn nhập - Đại cảnh sân đình mờ sương và bóng gã hề xuất hiện]"
                    sub_subject = "clown"
                    sub_refs = ["character_primary", "location_main"]
                elif j == 0:
                    sub_label = "[Dẫn nhập không gian - Đại cảnh sân đình làng cổ mờ sương đêm trăng, đuốc leo lét]"
                    sub_subject = "landscape"
                    sub_refs = ["location_main"]
                else:
                    sub_label = "[Dẫn nhập nhân vật - Bóng gã hề bước ra từ góc tối, tà áo the rách, tay cầm quạt nan]"
                    sub_subject = "clown"
                    sub_refs = ["character_primary", "prop_primary"]

            elif section_type == "Gian tấu":
                if prev_subj == "clown" and next_subj == "rich_man":
                    if j == 0:
                        sub_label = "[Gian tấu 1 - Gã hề xoay tròn múa giễu cợt theo nhịp trống, liếc mắt sang góc tối]"
                        sub_subject = "clown"
                        sub_refs = ["character_primary"]
                    elif j == 1 and n_inst >= 3:
                        sub_label = "[Gian tấu 2 - Lia máy quay qua hàng đuốc bập bùng, chuyển từ sân đình sang góc hiên gấm lụa]"
                        sub_subject = "landscape"
                        sub_refs = ["location_main"]
                    else:
                        sub_label = "[Gian tấu - Cận cảnh bàn tay đeo nhẫn ngọc gõ nhịp kiêu hãnh lên tay vịn ghế lim của Phú Ông]"
                        sub_subject = "rich_man"
                        sub_refs = ["character_secondary"]
                elif prev_subj == "rich_man" and next_subj == "clown":
                    if j == 0:
                        sub_label = "[Gian tấu - Phú ông phe phẩy quạt ngà cười khẩy trịch thượng nhấp ngụm trà sen]"
                        sub_subject = "rich_man"
                        sub_refs = ["character_secondary"]
                    else:
                        sub_label = "[Gian tấu - Máy quay lùi xa, gã hề siết chặt quạt nan rách nhìn Phú Ông căm phẫn]"
                        sub_subject = "clown"
                        sub_refs = ["character_primary", "prop_primary"]
                else:
                    if j == 0:
                        sub_label = "[Gian tấu - Vũ điệu hề cuồng loạn, tàn than đỏ bay mù mịt theo nhịp trống dồn dập]"
                        sub_subject = "clown"
                        sub_refs = ["character_primary", "prop_primary"]
                    else:
                        sub_label = "[Gian tấu - Cận cảnh giọt mồ hôi nhòe vôi trắng, ngực phập phồng thở dốc giữa tiếng cười cay đắng]"
                        sub_subject = "clown"
                        sub_refs = ["character_primary"]

            elif section_type == "Outro":
                if j == 0:
                    sub_label = "[Vĩ thanh - Gã hề quỳ gối trước thau đồng, run rẩy vục tay rửa sạch lớp vôi bôi trên mặt]"
                    sub_subject = "clown"
                    sub_refs = ["character_primary", "prop_primary"]
                elif j == 1:
                    sub_label = "[Hạ màn - Cận cảnh giọt nước mắt hòa vôi trắng rơi xao động mặt nước, chiếc quạt nan rơi bên cạnh]"
                    sub_subject = "prop"
                    sub_refs = ["prop_primary"]
                else:
                    sub_label = "[Kết thúc - Đuốc tàn dần, bóng tối nuốt trọn sân đình vắng lặng, trăng khuya chìm vào mây đen]"
                    sub_subject = "landscape"
                    sub_refs = ["location_main"]
            else:
                sub_label = f"[{section_type} - Đoạn nối kịch bản {j+1}]"
                sub_subject = "clown"
                sub_refs = ["character_primary", "location_main"]

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

    # 1. INTRO: Covers from 0.0 to first vocal line
    first_start = srt_items[0]['start']
    if first_start >= 2.5:
        intro_shots = make_narrative_interlude_shots(0.0, first_start, section_type="Intro", prev_shot=None, next_item=srt_items[0])
        shots.extend(intro_shots)

    # 2. VOCAL SHOTS WITH INTERLUDES (GIAN TẤU) IN BETWEEN
    current_shot = None

    for idx, item in enumerate(srt_items):
        item_subj = detect_subject_from_text(item['text'])
        item_refs = ["character_secondary", "location_main"] if item_subj == "rich_man" else (["prop_primary", "location_main"] if item_subj == "prop" else ["character_primary", "prop_primary"])

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
                    if item_subj != "lead_character":
                        current_shot['subject'] = item_subj
                        current_shot['refs'] = item_refs
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

    # 3. OUTRO: Covers from last vocal line to total audio duration
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

    # 4. Finalise timecodes, titles, and exact durations
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
    """Bulletproof multi-tier parser extracting rich plan (Visual Bible, Reference Pack, Shots)."""
    shots = []
    visual_motif = ""
    visual_bible = {}
    reference_pack = {}

    # -------------------------------------------------------------
    # Tier 1: Parse JSON (Directly or within ```json ... ``` blocks)
    # -------------------------------------------------------------
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
                    visual_motif = data.get("visual_motif", "")
                    visual_bible = data.get("visual_bible", {})
                    reference_pack = data.get("reference_pack", {})

                    raw_shots = data.get("shots", [])
                    if isinstance(raw_shots, list) and len(raw_shots) > 0:
                        for idx, s in enumerate(raw_shots):
                            shots.append({
                                "shot_number": s.get("shot_number", idx + 1),
                                "shot_num": s.get("shot_number", idx + 1),
                                "section": s.get("section", f"Shot {idx+1}"),
                                "title": s.get("title", f"Shot {idx+1}"),
                                "lyric_line": s.get("lyric_line", ""),
                                "camera_motion": s.get("camera_motion", "slow_pan"),
                                "start_frame": s.get("start_frame", ""),
                                "end_frame": s.get("end_frame", ""),
                                "duration": max(5, min(int(s.get("duration", 7)), 12)),
                                "aspect": s.get("aspect", "16:9"),
                                "prompt": s.get("prompt", "").strip(),
                                "negative_prompt": s.get("negative_prompt", "ugly, deformed, mutated, text, watermark, blurry, low quality")
                            })
                        if shots:
                            return {
                                "visual_motif": visual_motif,
                                "visual_bible": visual_bible,
                                "reference_pack": reference_pack,
                                "shots": shots
                            }
            except Exception:
                pass

    # -------------------------------------------------------------
    # Tier 2: Regex Header Parser (Supports SHOT, Shot, Loop, Cảnh, Phân cảnh)
    # -------------------------------------------------------------
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

            if "### 6" in body or "### 7" in body or "CapCut Edit" in body:
                body = re.split(r'###\s*[67]|CapCut\s*Edit', body, flags=re.IGNORECASE)[0]

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
                p_inline = re.search(r'(?:FLOW|VEO|MUSE|VIDEO)?\s*PROMPT[^:\n]*:\s*([^\n]+(?:\n[^\n#]+)*)', body, re.IGNORECASE)
                if p_inline:
                    prompt = p_inline.group(1).strip().strip('`*')

            desc_match = re.search(r'(?:Mô tả cảnh|Mô tả|Description)[:\s]*([^\n]+)', body, re.IGNORECASE)
            desc = desc_match.group(1).strip() if desc_match else (shot_title or f"Phân cảnh {shot_num}")

            if prompt and len(prompt) > 10:
                shots.append({
                    "shot_number": int(shot_num) if shot_num.isdigit() else len(shots) + 1,
                    "shot_num": int(shot_num) if shot_num.isdigit() else len(shots) + 1,
                    "section": f"Shot {shot_num}",
                    "title": f"Shot {shot_num}: {shot_title}" if shot_title else f"Shot {shot_num}",
                    "description": desc,
                    "duration": max(5, min(duration, 12)),
                    "aspect": "16:9",
                    "prompt": prompt,
                    "negative_prompt": negative_prompt
                })
        if shots:
            return {
                "visual_motif": visual_motif,
                "visual_bible": visual_bible,
                "reference_pack": reference_pack,
                "shots": shots
            }

    # -------------------------------------------------------------
    # Tier 3: Global Codeblock Fallback
    # -------------------------------------------------------------
    codeblocks = re.findall(r'```(?:[a-zA-Z]*\n)?(.*?)```', markdown_text, re.DOTALL)
    for i, cb in enumerate(codeblocks):
        cb_clean = cb.strip()
        if len(cb_clean) > 25 and not cb_clean.startswith(("{", "[", "def ", "import ")) and not "track" in cb_clean.lower() and not "layer" in cb_clean.lower():
            if not any(w in cb_clean.lower() for w in ["ugly", "deformed", "watermark"]):
                shots.append({
                    "shot_number": len(shots) + 1,
                    "shot_num": len(shots) + 1,
                    "section": f"Shot {len(shots)+1}",
                    "title": f"Shot {len(shots)+1}",
                    "description": f"Phân cảnh {len(shots)+1}",
                    "duration": 7,
                    "aspect": "16:9",
                    "prompt": cb_clean,
                    "negative_prompt": "ugly, deformed, mutated, bad anatomy, text, watermark, blurry, low quality"
                })
    if shots:
        return {
            "visual_motif": visual_motif,
            "visual_bible": visual_bible,
            "reference_pack": reference_pack,
            "shots": shots
        }

    # -------------------------------------------------------------
    # Tier 4: Emergency Bulletproof Fallback (Never return empty)
    # -------------------------------------------------------------
    lyrics_lines = [l.strip() for l in (fallback_lyrics or "").splitlines() if l.strip() and not l.strip().startswith(("#", "//"))]
    sections = []
    current_sec = []
    for line in lyrics_lines:
        if line.startswith("[") and line.endswith("]"):
            if current_sec:
                sections.append("\n".join(current_sec))
                current_sec = []
        current_sec.append(line)
    if current_sec:
        sections.append("\n".join(current_sec))
    if not sections and lyrics_lines:
        sections = [lyrics_lines[i] for i in range(0, min(len(lyrics_lines), 6))]

    for idx, sec in enumerate(sections[:8]):
        first_line = sec.splitlines()[0] if sec else f"Phân cảnh {idx+1}"
        shots.append({
            "shot_number": idx + 1,
            "shot_num": idx + 1,
            "section": f"Scene {idx+1}",
            "title": f"Shot {idx+1}: {first_line[:40]}",
            "lyric_line": sec[:80],
            "duration": 7,
            "aspect": "16:9",
            "prompt": f"Cinematic shot, {fallback_style or 'Vietnamese traditional theatrical atmosphere'}, dramatic cinematic lighting, slow camera motion, highly detailed, photorealistic 8k",
            "negative_prompt": "ugly, deformed, mutated, text, watermark, blurry, low quality"
        })

    return {
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
    genre_style: str = "dark avant-garde Vietnamese theatrical folk, 96 bpm",
    bpm: str = "85 BPM",
    vocal: str = "Nữ trầm ấm, da diết",
    mood: str = "Hoài niệm, buồn sâu lắng",
    extra_notes: str = "",
    audio_duration: Optional[float] = None,
    audio_url: Optional[str] = None,
    srt_content: Optional[str] = None
) -> Dict[str, Any]:
    """Call configured AI LLM (Gemini or OpenAI-compatible proxy) to generate structured MV production plan."""
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
            srt_table_info = "\n### BẢNG TIMECODE CHÍNH XÁC TỪ FILE PHỤ ĐỀ (.SRT):\n" + "\n".join(srt_table_lines) + """

QUY TẮC BẮT BUỘC KHI CÓ FILE PHỤ ĐỀ SRT:
1. Bạn BẮT BUỘC phải tạo ĐÚNG """ + str(len(srt_shots)) + """ phân cảnh tương ứng với """ + str(len(srt_shots)) + """ mục trong bảng timecode trên.
2. Tại mỗi phân cảnh, hành động điện ảnh của nhân vật và bối cảnh BẮT BUỘC phải ăn khớp CHÍNH XÁC với ý nghĩa câu hát tại đúng mốc thời gian đó!
3. Giữ nguyên thời lượng (duration) và câu hát (lyric_line) của từng phân cảnh như trong bảng SRT.
"""
    if srt_shots:
        target_shots = len(srt_shots)
        audio_info = f"- **Thời lượng bài nhạc Suno thực tế:** {int(audio_duration)} giây. BẮT BUỘC chia thành ĐÚNG {target_shots} phân cảnh tương ứng với {target_shots} mục timecode trong bảng phụ đề bên dưới!\n"
    else:
        target_shots = max(5, int(round(audio_duration / 7.5))) if audio_duration else 8
        audio_info = f"- **Thời lượng bài nhạc Suno thực tế:** {int(audio_duration)} giây (~{int(audio_duration)//60}p{int(audio_duration)%60:02d}s). BẮT BUỘC chia thành khoảng {target_shots} phân cảnh (mỗi cảnh 6-9s) sao cho TỔNG THỜI LƯỢNG các phân cảnh BẰNG ĐÚNG {int(audio_duration)}s để phủ kín 100% video cho bài hát!\n" if audio_duration else ""
    user_prompt = f"""Hãy làm Đạo Diễn MV và chia phân cảnh chi tiết cho bài hát sau:

- **Tên bài hát:** {song_title}
- **Style nhạc Suno đầy đủ (Bao gồm thể loại, nhạc cụ, giọng hát, BPM, negative tags):** {genre_style}
{audio_info}{srt_table_info}- **Ghi chú thêm từ Đạo diễn:** {extra_notes or "Không"}

**Lời bài hát (Lyrics):**
\"\"\"
{lyrics}
\"\"\"

YÊU CẦU QUAN TRỌNG:
Hãy phân tích nhịp điệu bài hát, giọng ca và phong cách từ Style Suno trên, xây dựng kế hoạch sản xuất MV Narrative Storyboard chuẩn điện ảnh theo 5 bước:
1. Xác định Motif thị giác trung tâm và Lyric Evidence Map.
2. Xây dựng Visual Bible (khóa tạo hình nhân vật, trang phục, bối cảnh) và 3 điều bất biến (INVIOLABLES).
3. Tạo Bộ ảnh mẫu neo tham chiếu (Reference Pack) gồm character_prompt (chân dung nhân vật chính) và location_prompt (đại cảnh bối cảnh chính).
4. Chia bài hát thành đúng số phân cảnh (Shots) khớp chuẩn từng giai đoạn cảm xúc và bảng timecode phụ đề.
5. Viết Prompt tiếng Anh điện ảnh chi tiết, giàu từ khóa vi chuyển động thực tế và Negative Prompt riêng biệt cho từng shot.

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

    # 2. OpenAI / DeepSeek / Claude / Custom Proxy (OpenAI format)
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

    # Execute request
    timeout = httpx.Timeout(120.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, proxy=cfg.ai_network_proxy) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise Exception(f"AI API Error (HTTP {resp.status_code}): {resp.text}")
        
        data = resp.json()
        
        # Parse output text
        if "candidates" in data:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        elif "choices" in data:
            content = data["choices"][0]["message"]["content"]
        else:
            raise Exception(f"Unknown AI response structure: {data}")
            
    # Extract rich plan with bulletproof fallback
    parsed = parse_full_director_plan(content, fallback_lyrics=lyrics, fallback_style=genre_style)
    shots = parsed.get("shots", [])
    visual_bible = parsed.get("visual_bible", {})
    ref_pack = parsed.get("reference_pack", {})

    # Apply 3-pillar enforcement: Character consistency, Live-action motion, Audio timeline matching
    shots = enforce_character_consistency(shots, visual_bible, ref_pack)
    shots = enforce_video_motion(shots)
    shots = calibrate_audio_timeline(shots, audio_duration)
    
        # Align shots perfectly with SRT / LRC segments
    if srt_shots:
        aligned_shots = []
        for idx, ref_s in enumerate(srt_shots):
            if idx < len(shots):
                s = dict(shots[idx])
            else:
                primary_char = visual_bible.get("character_lock") or ref_pack.get("character_prompt") or "Vietnamese traditional theatrical folk clown actor"
                style_lock = visual_bible.get("style_lock") or "Dark folk gothic, chiaroscuro contrast, 35mm film grain, 16:9"
                s = {
                    "shot_number": idx + 1,
                    "shot_num": idx + 1,
                    "section": f"Shot {idx+1}",
                    "title": f"Shot {idx+1}: {ref_s['lyric_line'][:35]}",
                    "camera_motion": "Dynamic cinematic steadycam tracking",
                    "aspect": "16:9",
                    "prompt": f"Live-action dynamic cinematic shot: {primary_char}. Expressive theatrical performance directly reflecting the sung lyrics: \"{ref_s['lyric_line']}\". {style_lock}, fluid natural human motion, alive, dynamic physical action, 8k photorealistic, 16:9, NOT a static image.",
                    "negative_prompt": "static photo, still image, photo zoom, slideshow, ken burns effect, frozen frame, motionless subject, modern microphone, sunglasses, modern clothing, 3D CGI plastic skin, anime, low quality"
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
        "visual_motif": parsed.get("visual_motif", ""),
        "visual_bible": parsed.get("visual_bible", {}),
        "reference_pack": parsed.get("reference_pack", {}),
        "shots_count": len(shots),
        "shots": shots
    }
