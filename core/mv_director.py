import re
import httpx
from typing import Dict, Any, List, Optional
from core.config import AppConfig

MV_DIRECTOR_SYSTEM_PROMPT = """# AI MV Director V2

Hệ thống đạo diễn và lập kế hoạch sản xuất Music Video (MV) toàn diện bằng công cụ AI (Google Flow, Veo, Kling, Runway, CapCut). Biến mọi bài hát thành một kế hoạch sản xuất MV hoàn chỉnh với tính thẩm mỹ điện ảnh, kiểm soát thị giác nhất quán và tối ưu hóa thời lượng clip nguồn linh hoạt (từ 5 giây đến tối đa 10 giây).

## Core Directorial Rule: Đánh Giá & Chọn Duy Nhất 1 Định Dạng Tối Ưu

Khi nhận thông tin bài hát từ người dùng, hệ thống tự động phân tích sâu ca từ, tiết tấu (BPM), cấu trúc giọng hát và tính chất bản phối để lựa chọn và đề xuất DUY NHẤT 1 định dạng MV tối ưu nhất trong 5 định dạng sau (nêu rõ 2 câu lý do đạo diễn trước khi triển khai):

1. **Infinite Loop Visualizer (Vòng lặp vô hạn 5s - 10s):**
   - Phù hợp: Lofi Chill, Acoustic nhẹ nhàng, Upbeat Pop dạo phố, R&B thư giãn, Podcast/BGM.
   - Bản chất: 1 - 2 cảnh loop có chuyển động tuần hoàn tuần tự (Parallax trôi cảnh, nhịp chân, lá bay, khói, vệt nắng dao động). Tiết kiệm chi phí render, giữ chân người nghe nhạc thư giãn mà không lo trôi mặt.

2. **Narrative Storyboard MV (Cốt truyện phân cảnh điện ảnh):**
   - Phù hợp: Pop Ballad bi kịch/tự sự, Rap Storytelling, Nhạc kịch, Dark Avant-Garde Folk, Sử thi.
   - Bản chất: Kịch bản phân cảnh 6 - 12 shot nối tiếp mở - thân - kết, phối hợp toàn/trung/cận/cực cận để đẩy mạnh cao trào kịch tính.

3. **Cinematic Moodscape (Thước phim cảnh sắc & không gian):**
   - Phù hợp: Dân gian Nam Bộ Fusion, Quê hương đất nước, Ambient, Khúc tráng ca, Hòa tấu nhạc cụ.
   - Bản chất: Tôn vinh vẻ đẹp thiên nhiên, ánh sáng (bình minh, sông nước, đồng lúa, khói lam chiều, góc phố cổ). Nhân vật chỉ làm bóng lưng hoặc chấm nhỏ vi mô, triệt tiêu lỗi dị tật giải phẫu AI.

4. **Acoustic Studio / Live Session (Mô phỏng biểu diễn mộc):**
   - Phù hợp: Indie Acoustic, Ballad mộc, Unplugged, Jazz cà phê.
   - Bản chất: Góc máy cố định vào ca sĩ/nhạc công ảo bên cây đàn guitar/piano/micro trong không gian ấm áp, tập trung vào rung cảm biểu diễn.

5. **Animated Typography & Parallax Lyric Video:**
   - Phù hợp: Nhạc dance, EDM, Hiphop viral, Pop điện tử tiết tấu dồn dập.
   - Bản chất: Hình ảnh nghệ thuật 2.5D tách lớp chiều sâu kết hợp chữ chuyển động (kinetic typography) bắt nhịp vocal.

## Quy Định Thời Lượng Clip Nguồn (Flexible Duration 5s - 10s)

Google Flow và các model video tiên tiến (Veo 2, Kling, Muse) hỗ trợ thời lượng clip nguồn linh hoạt lên đến tối đa 10 giây. Không mặc định cố định 5 giây mà phải sắp xếp độ dài từng clip thông minh tùy theo nhịp điệu và mục đích cảnh quay:
- **Clip 5 giây - 6 giây:** Phù hợp cho nhịp bài nhanh (nhịp cắt dồn dập, Pre-Chorus, Drop, cảnh hành động hoặc các loop vi chuyển động ngắn lặp nhanh).
- **Clip 7 - 10 giây (Tối đa 10s):** Tối ưu cho các cú máy lướt chậm (Slow Pan/Drone Flyover trong Cinematic Moodscape), cảnh độc thoại nội tâm dài, các đoạn dạo gián tấu (Intro/Bridge/Outro), hoặc các Loop tuần hoàn có chu kỳ chuyển động dài giúp giảm tần suất cắt ghép trên CapCut.

## Output Workflow (Quy Trình 7 Bước Chuẩn)

Khi người dùng gửi bài, hệ thống kích hoạt và xuất trọn gói kế hoạch sản xuất:

### 1. Phân Tích Bài Hát & Bảng Chứng Cứ Lyrics (Lyric Evidence Map)
- Thông số tổng quan: Tên bài hát, Thời lượng, Thể loại, Nhịp điệu (BPM), Cảm xúc chủ đạo, Motif trung tâm.
- Tuyên bố Format đã chọn & Lý do: Chỉ rõ 1 format duy nhất được chọn và giải thích ngắn gọn tại sao format này phù hợp nhất với hồn bài hát.
- Bảng chứng cứ Lyrics: Phân tách chi tiết thị giác thành `DIRECT` (từ lời) và `DIRECTORIAL` (đạo diễn thêm vào để tăng sức gợi).

### 2. Khóa Tạo Hình Chi Tiết (Visual Bible)
- **STYLE_LOCK:** Quy định trường phái mỹ thuật, nét vẽ, bảng màu, tỉ lệ khung hình (luôn là 16:9). Cấm các lỗi thị giác như 3D CGI nhựa, chibi.
- **CHARACTER_LOCK:** Giới tính, độ tuổi, vóc dáng, thần thái, đặc điểm nhận diện.
- **WARDROBE_LOCK:** Trang phục, màu áo, phụ kiện cố định xuyên suốt.
- **LOCATION_LOCK:** Bối cảnh cụ thể (thời điểm trong ngày, thời tiết, ánh sáng, kiến trúc).
- **OBJECT/VEHICLE_LOCK:** Chi tiết đạo cụ/phương tiện.
- **Chi tiết bất biến (Inviolables):** Danh sách các yếu tố cấm AI tự ý thay đổi giữa các cảnh.

### 3. Bộ Ảnh Mẫu Cần Tạo (Reference Pack)
Viết prompt tạo ảnh mẫu hoàn chỉnh bằng Tiếng Anh (English) trong ô mã lệnh (code block):
- `CHARACTER_PRIMARY_ID`: Ảnh chân dung góc ngang mắt khóa nét mặt.
- `CHARACTER_FULL_OUTFIT`: Ảnh toàn thân khóa trang phục & phụ kiện.
- `MASTER_LOCATION_REF`: Ảnh bối cảnh không người khóa không gian.
- `KEYFRAME_REFS`: Khung hình bố cục chính cho các shot/loop.

### 4. Kế Hoạch Phân Cảnh (Loop Plan hoặc Storyboard Sheet)
- Lập bảng phân bổ: Tên cảnh/Loop, Đoạn nhạc, Bố cục góc máy, Vi chuyển động/Hành động, Thời lượng nguồn (Linh hoạt 5s - 10s tùy cảnh), Phương pháp lặp hoặc kỹ thuật chuyển cảnh.

### 5. Bộ Prompt Tạo Video Cho AI (Google Flow / Veo / Kling / Muse)
Chi tiết cho từng shot/loop (Đánh số rõ ràng SHOT 1, SHOT 2... hoặc LOOP 1, LOOP 2...):
- **Shot/Loop ID:** (Ví dụ: SHOT 01 - Intro)
- **Thời lượng nguồn:** (Chỉ định rõ số giây từ 5s đến 10s)
- **Tỷ lệ khung hình:** 16:9
- **Mô tả cảnh (Tiếng Việt):** Mô tả tóm tắt nội dung cảnh.
- **FLOW / VEO / MUSE PROMPT (Tiếng Anh):** Viết trong code block riêng biệt. Mô tả hành động, camera, ánh sáng, chuyển động điện ảnh chuẩn xác.
- **NEGATIVE PROMPT (Tiếng Anh):** Viết trong code block riêng biệt. Bộ lọc loại trừ biến dạng, trôi mặt, đổi đồ.

### 6. Kế Hoạch Dựng & Timeline Trên CapCut (CapCut Edit Plan)
- Tính toán toán học timeline chuẩn xác từng giây dựa trên thời lượng clip nguồn (5s - 10s).
- Thiết lập quy trình xếp Layer (Main Track và Overlay Track) để chuyển cảnh Cross Dissolve không bị hụt thời lượng âm thanh.
- Hướng dẫn thiết lập hiệu ứng mở màn (Intro) và kết màn (Outro/Fade to Black).

### 7. Bảng Kiểm Tra Chất Lượng (Quality Check)
- Đánh giá 7 tiêu chí: Tính đồng nhất nhân vật, Bất biến phục trang, Ánh sáng/Không gian, Độ mượt của chuyển động AI, Đồng bộ nhịp âm thanh (Beatsync), Tầng nghĩa thị giác và Chuẩn tỷ lệ 16:9.

## Language Rule
- Mọi phân tích, lập luận, kịch bản và kế hoạch dựng: Tiếng Việt chuyên nghiệp, sắc sảo.
- Toàn bộ prompt tạo ảnh và prompt tạo video: Tiếng Anh chuẩn xác, cô đọng để AI hiểu đúng 100%.
"""

def extract_shots_from_script(markdown_text: str) -> List[Dict[str, Any]]:
    """Smart bulletproof parser extracting shots and prompts from script."""
    shots = []
    
    # Split text into sections based on Shot or Loop headers
    header_regex = re.compile(r'(?:^|\n)(?:###?\s*|\*\*\s*|\b)(?:SHOT|Shot|Loop|LOOP)\s*(\d+)[:\.\s-]*([^\n]*)', re.IGNORECASE)
    splits = list(header_regex.finditer(markdown_text))
    
    if splits:
        for i, match in enumerate(splits):
            shot_num = match.group(1).strip()
            shot_title = match.group(2).strip().strip('*#:')
            start_pos = match.end()
            end_pos = splits[i+1].start() if i + 1 < len(splits) else len(markdown_text)
            
            body = markdown_text[start_pos:end_pos]
            
            # Stop if we reached section 6 or CapCut plan
            if "### 6" in body or "### 7" in body or "CapCut Edit" in body:
                body = re.split(r'###\s*[67]|CapCut\s*Edit', body, flags=re.IGNORECASE)[0]

            # Extract duration (5s - 10s)
            dur_match = re.search(r'(?:Thời lượng|Duration)[:\s]*(\d+)\s*s?', body, re.IGNORECASE)
            duration = int(dur_match.group(1)) if dur_match else 7
            if duration < 5: duration = 5
            if duration > 10: duration = 10
            
            # Extract codeblocks in this shot block
            codeblocks = re.findall(r'```(?:[a-zA-Z]*\n)?(.*?)```', body, re.DOTALL)
            
            prompt = ""
            negative_prompt = "ugly, deformed, mutated, bad anatomy, text, watermark, blurry, low quality"
            
            # Look for specific prompt tags
            for cb in codeblocks:
                cb_clean = cb.strip()
                if not cb_clean:
                    continue
                # If negative prompt
                if any(w in cb_clean.lower() for w in ["ugly", "deformed", "mutated", "bad anatomy", "watermark"]):
                    negative_prompt = cb_clean
                elif not prompt:
                    prompt = cb_clean
                    
            # Fallback if no codeblock, look for "PROMPT:" line
            if not prompt:
                p_inline = re.search(r'(?:FLOW|VEO|MUSE|VIDEO)?\s*PROMPT[^:\n]*:\s*([^\n]+(?:\n[^\n#]+)*)', body, re.IGNORECASE)
                if p_inline:
                    prompt = p_inline.group(1).strip().strip('`*')

            # Extract description
            desc_match = re.search(r'(?:Mô tả cảnh|Mô tả|Description)[:\s]*([^\n]+)', body, re.IGNORECASE)
            desc = desc_match.group(1).strip() if desc_match else (shot_title or f"Phân cảnh {shot_num}")

            if prompt and len(prompt) > 10:
                shots.append({
                    "shot_number": int(shot_num) if shot_num.isdigit() else len(shots) + 1,
                    "title": f"Shot {shot_num}: {shot_title}" if shot_title else f"Shot {shot_num}",
                    "description": desc,
                    "duration": duration,
                    "aspect": "16:9",
                    "prompt": prompt,
                    "negative_prompt": negative_prompt
                })

    # Global fallback if no SHOT structure matched: extract all meaningful codeblocks
    if not shots:
        codeblocks = re.findall(r'```(?:[a-zA-Z]*\n)?(.*?)```', markdown_text, re.DOTALL)
        for i, cb in enumerate(codeblocks):
            cb_clean = cb.strip()
            # Must look like an English image/video prompt (at least 20 chars, not JSON/Python/Timeline)
            if len(cb_clean) > 25 and not cb_clean.startswith(("{", "[", "def ", "import ")) and not "track" in cb_clean.lower() and not "layer" in cb_clean.lower():
                shots.append({
                    "shot_number": i + 1,
                    "title": f"Shot {i+1}",
                    "description": f"Phân cảnh {i+1}",
                    "duration": 7,
                    "aspect": "16:9",
                    "prompt": cb_clean,
                    "negative_prompt": "ugly, deformed, mutated, bad anatomy, text, watermark, blurry"
                })

    return shots

async def generate_mv_plan(
    cfg: AppConfig,
    song_title: str,
    lyrics: str,
    genre_style: str = "Pop Ballad",
    bpm: str = "85 BPM",
    vocal: str = "Nữ trầm ấm, da diết",
    mood: str = "Hoài niệm, buồn sâu lắng",
    extra_notes: str = ""
) -> Dict[str, Any]:
    """Call configured AI LLM (Gemini or OpenAI-compatible proxy) to generate 7-step MV production plan."""
    user_prompt = f"""Hãy làm đạo diễn và lập kế hoạch sản xuất MV hoàn chỉnh cho bài hát sau theo quy trình 7 bước chuẩn:

- **Tên bài hát:** {song_title}
- **Thể loại/Phong cách âm nhạc:** {genre_style}
- **Tiết tấu (BPM):** {bpm}
- **Đặc trưng giọng ca:** {vocal}
- **Cảm xúc chủ đạo:** {mood}
- **Ghi chú thêm của tác giả:** {extra_notes or "Không"}

**Lời bài hát (Lyrics):**
\"\"\"
{lyrics}
\"\"\"

Hãy kích hoạt toàn bộ năng lực của AI MV Director V2, phân tích sâu, lựa chọn DUY NHẤT 1 định dạng tối ưu và xuất đầy đủ 7 bước kịch bản theo đúng hướng dẫn.
"""

    headers = {}
    payload = {}
    url = ""
    
    # 1. Google Gemini Native API
    if cfg.ai_provider == "gemini":
        base = cfg.ai_base_url.rstrip("/")
        if "generativelanguage.googleapis.com" in base or not base:
            model = cfg.ai_model or "gemini-1.5-flash"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={cfg.ai_api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{MV_DIRECTOR_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 8192
                }
            }
        else:
            # Gemini via custom proxy OpenAI-compatible
            url = f"{base}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cfg.ai_api_key}"
            }
            payload = {
                "model": cfg.ai_model or "gemini-1.5-flash",
                "messages": [
                    {"role": "system", "content": MV_DIRECTOR_SYSTEM_PROMPT},
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
                {"role": "system", "content": MV_DIRECTOR_SYSTEM_PROMPT},
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
            # Gemini format
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        elif "choices" in data:
            # OpenAI format
            content = data["choices"][0]["message"]["content"]
        else:
            raise Exception(f"Unknown AI response structure: {data}")
            
    # Extract shots
    shots = extract_shots_from_script(content)
    
    return {
        "success": True,
        "script_markdown": content,
        "shots_count": len(shots),
        "shots": shots
    }
