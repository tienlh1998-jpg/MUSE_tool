# 🎬 MUSE AI MV Studio V3.1

> **Ứng dụng cá nhân kết hợp giữa Đạo diễn kịch bản MV bằng AI (AI MV Director V2) và Xưởng Render Video Muse AI Đa Tài Khoản (Account Pool & Auto-Rotation).**

---

## ✨ Tính Năng Nổi Bật

1. **🎨 Engine Tạo Ảnh Thật (Real Image Engine):**
   - **Đa nguồn tự động:** Google Imagen 3 (khi có API Key Gemini) → OpenAI-compatible `/v1/images/generations` (DALL-E 3, Flux, Midjourney gateway) → engine miễn phí zero-config (Flux qua Pollinations).
   - Tự động chuẩn hoá kích thước bằng Pillow: `16:9` (1280×720), `9:16` (720×1280), `1:1` (1024×1024), `4:3` (1024×768).
   - **Làm sạch watermark:** với nguồn miễn phí, dải chân trang được crop tự động (kèm phát hiện dải màu đồng nhất) nên không dính logo bên thứ ba.
   - Ảnh PNG lưu tại `data/downloads/images/` và tự gắn vào thư viện dự án.

2. **🎬 Engine Render Video Điện Ảnh (Real Video Engine):**
   - **Image → Video:** render MP4 1080p H.264/yuv420p, 30 FPS bằng FFmpeg.
   - **Camera motion thực tế** đọc từ prompt: *dolly/zoom in/tiến lại* → zoom-in 1.0→1.25; *pull back/zoom out/toàn cảnh* → zoom-out 1.25→1.0; *pan/lướt/mist/walk* → pan ngang; hỗ trợ cả tilt lên/xuống.
   - **Text → Video:** tự sinh keyframe thật bằng image engine rồi áp camera motion — không còn clip màu đen.
   - Ping `https://muse.ai/api/session` khi có cookie thật; 401 kích hoạt failover sang tài khoản kế tiếp.

3. **🧵 1-Click Auto-Stitch:**
   - Nối các shot đã render theo đúng `shot_number`, chuẩn hoá scale/pad/fps trước khi concat.
   - Có nhạc nền: nhạc dài hơn hình → loop hình vừa khít bài hát; nhạc ngắn hơn → pad silence giữ đủ shot.
   - Xuất `Full_MV_{Tên_Dự_Án}_{timestamp}.mp4` và phát ngay trên giao diện.

4. **🔄 Hàng Đợi Bền Vững & Đồng Bộ Realtime:**
   - Queue auto-recovery: task `pending`/`running` bị gián đoạn được đưa lại hàng đợi khi khởi động.
   - UI polling thời gian thực: card tiến trình khi tạo ảnh, spinner khi render shot, tự nạp gallery/preview khi xong.
   - Nút **Render Lại** cho từng ảnh và từng shot.

5. **🎬 AI MV Director V2 (Đạo Diễn MV Tự Động):**
   - Phân tích lời bài hát (Lyrics), BPM, Vocal, Style, Mood.
   - Đề xuất 1 trong 5 định dạng tối ưu: *Infinite Loop Visualizer, Narrative Storyboard MV, Cinematic Moodscape, Acoustic Studio, Animated Typography*.
   - Khóa tạo hình chi tiết (Visual Bible): Character Lock, Style Lock, Wardrobe Lock, Location Lock.
   - Lập kịch bản phân cảnh 5s - 10s và tự động sinh toàn bộ prompt tiếng Anh chuẩn điện ảnh cho từng shot.
   - Tính toán timeline phân lớp dựng video trên CapCut (Main Track & Overlay Track gối đầu Cross Dissolve).

6. **👥 Quản Lý Kho Tài Khoản Muse AI (Account Pool):**
   - Hỗ trợ dán hàng loạt tài khoản Muse theo định dạng `email|cookie` (Header String từ Cookie-Editor).
   - Tự động xoay tua (Round Robin / Least Used) giữa các tài khoản.
   - Tự động chuyển sang tài khoản dự phòng khi một tài khoản hết hạn mức hoặc lỗi phiên (**Auto-Failover**).
   - Kiểm tra tình trạng phiên (Health check) trực tiếp trên giao diện.

7. **⚙️ Kết Nối AI & Proxy Đa Dạng:**
   - Hỗ trợ **Google Gemini / Imagen 3**, **OpenAI**, **DeepSeek**, **Claude**.
   - Hỗ trợ kết nối qua **bất kỳ Reverse Proxy / OneAPI / NewAPI** nào (Tùy chọn Base URL, API Key, Model Name, Image Model).
   - Hỗ trợ Network Proxy (HTTP/SOCKS5).

---

## 🚀 Khởi Động Nhanh

1. Nhấp đúp chuột vào file:
   ```cmd
   run.bat
   ```
2. Trình duyệt sẽ tự động mở tại địa chỉ: **`http://127.0.0.1:8000`**

---

## 🛠️ Cài Đặt Thủ Công (Tùy Chọn)

```bash
# 1. Khởi tạo môi trường ảo Python
python -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS
.venv\Scripts\activate     # Trên Windows

# 2. Cài đặt các thư viện cần thiết
pip install -r requirements.txt

# 3. Chạy ứng dụng
python app.py
```

---

## 🧪 Kiểm Thử Tự Động

```bash
python test_app.py
```

Bộ test chạy trong thư mục dữ liệu tạm (`MUSE_DATA_DIR`) nên không ảnh hưởng dự án/cookie thật. Các kịch bản:

| # | Kịch bản | Nội dung |
|---|----------|----------|
| 1 | Healthcheck & Config | `/api/health`, `/api/config`, `/api/accounts`, merge cấu hình từng phần |
| 2 | Project Lifecycle | Tạo dự án, lấy chi tiết, kiểm tra JSON schema, 404 |
| 3 | Image Generation | Tạo ảnh "cinematic portrait of Vietnamese girl in rain, 8k" 16:9 → PNG > 50KB, 1280×720, tự gắn dự án |
| 4 | Video Rendering | Render từ ảnh, 5s → MP4 > 200KB, H.264/yuv420p, 1920×1080, shot chuyển `ready` |
| 5 | Auto-Stitch | Ghép 2 clip + nhạc WAV → `Full_MV_*.mp4`, đủ thời lượng, có audio AAC |
| 6 | No Placeholder | Quét source đảm bảo không còn `lavfi color=c=` |
| 7 | Camera Motion | Kiểm tra mapping keyword → zoom/pan |
| 8 | Queue Recovery | Task bị gián đoạn được đưa lại hàng đợi sau restart |

---

## 📁 Cấu Trúc Dữ Liệu

```
data/
├── config.json          # Cấu hình AI provider, proxy, concurrency
├── accounts.json        # Cookie Muse (không commit)
├── projects.json        # Dự án, ảnh, shots, final video
├── tasks.json           # Hàng đợi render bền vững
└── downloads/
    ├── images/          # Ảnh AI sinh ra (PNG)
    └── Full_MV_*.mp4    # Video hoàn chỉnh sau khi ghép
```

> **Lưu ý:** thư mục `downloads/` ở gốc project là vị trí cũ (trước V3.1). Khi khởi động, app tự động migrate file sang `data/downloads/` và sửa lại đường dẫn tuyệt đối trong `projects.json`.

