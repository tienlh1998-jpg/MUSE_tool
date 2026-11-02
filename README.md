# 🎬 MUSE AI MV Studio

> **Ứng dụng cá nhân kết hợp giữa Đạo diễn kịch bản MV bằng AI (AI MV Director V2) và Xưởng Render Video Muse AI Đa Tài Khoản (Account Pool & Auto-Rotation).**

---

## ✨ Tính Năng Nổi Bật

1. **🎬 AI MV Director V2 (Đạo Diễn MV Tự Động):**
   - Phân tích lời bài hát (Lyrics), BPM, Vocal, Style, Mood.
   - Đề xuất 1 trong 5 định dạng tối ưu: *Infinite Loop Visualizer, Narrative Storyboard MV, Cinematic Moodscape, Acoustic Studio, Animated Typography*.
   - Khóa tạo hình chi tiết (Visual Bible): Character Lock, Style Lock, Wardrobe Lock, Location Lock.
   - Lập kịch bản phân cảnh 5s - 10s và tự động sinh toàn bộ prompt tiếng Anh chuẩn điện ảnh cho từng shot.
   - Tính toán timeline phân lớp dựng video trên CapCut (Main Track & Overlay Track gối đầu Cross Dissolve).

2. **⚡ 1-Click Chuyển Giao Sang Render:**
   - Tự động bóc tách các shot từ kịch bản phân cảnh đẩy thẳng vào hàng đợi render của Studio.

3. **👥 Quản Lý Kho Tài Khoản Muse AI (Account Pool):**
   - Hỗ trợ dán hàng loạt tài khoản Muse theo định dạng `email|cookie` (Header String từ Cookie-Editor).
   - Tự động xoay tua (Round Robin / Least Used) giữa các tài khoản.
   - Tự động chuyển sang tài khoản dự phòng khi một tài khoản hết hạn mức hoặc lỗi phiên (**Auto-Failover**).
   - Kiểm tra tình trạng phiên (Health check) trực tiếp trên giao diện.

4. **⚙️ Kết Nối AI & Proxy Đa Dạng:**
   - Hỗ trợ **Google Gemini (Miễn phí API)**, **OpenAI**, **DeepSeek**, **Claude**.
   - Hỗ trợ kết nối qua **bất kỳ Reverse Proxy / OneAPI / NewAPI** nào (Tùy chọn Base URL, API Key, Model Name).
   - Hỗ trợ Network Proxy (HTTP/SOCKS5).

5. **🎞️ Tự Động Tải & Thư Viện CapCut:**
   - Tự động lưu toàn bộ video clip render về thư mục `downloads/`.
   - Xem video trực tiếp trên giao diện, hỗ trợ xuất file ZIP trọn gói.

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
