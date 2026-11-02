# 🎬 HƯỚNG DẪN SỬ DỤNG - MUSE AI MV STUDIO

Ứng dụng cá nhân toàn diện kết hợp giữa **Đạo diễn kịch bản MV bằng AI (AI MV Director V2)** và **Xưởng Render video Muse AI đa tài khoản (Account Pool & Auto-Rotation)**.

---

## 🚀 1. Cách Khởi Động Ứng Dụng

Chỉ cần nhấp đúp chuột vào file:
👉 **`run.bat`** (nằm ngay trong thư mục `d:\Tool\MUSE_TOOL`)

* Ứng dụng sẽ tự động kích hoạt môi trường ảo Python và mở trình duyệt web tại địa chỉ: **`http://127.0.0.1:8000`**

---

## ⚙️ 2. Cài Đặt Kết Nối AI & Proxy (Tab "Cài Đặt AI")

Ứng dụng hỗ trợ kết nối linh hoạt với mọi nhà cung cấp AI:

### A. Dùng qua Proxy / Trạm chuyển tiếp (OneAPI, NewAPI, Cloudflare Worker...):
1. Tại mục **Nhà Cung Cấp AI**, chọn: `Custom Proxy / OneAPI / NewAPI / OpenAI-Compatible`
2. **Base URL:** Nhập địa chỉ endpoint proxy của bạn (Ví dụ: `https://your-proxy-domain.com/v1`)
3. **API Key:** Nhập API Key của trạm proxy
4. **Tên Model:** Nhập model muốn chạy (Ví dụ: `gpt-4o`, `claude-3-5-sonnet`, `gemini-2.0-flash`, `deepseek-chat`...)
5. *(Tùy chọn)* **Network Proxy:** Nhập proxy mạng nếu cần (Ví dụ: `http://127.0.0.1:7890`)
6. Bấm **"Kiểm Tra Kết Nối AI"** $\rightarrow$ Khi hiện màu xanh **✓ Kết nối thành công** là bạn có thể bấm **"Lưu Cài Đặt"**.

### B. Dùng Google Gemini (MIỄN PHÍ):
* Chọn `Google Gemini`, dán API Key lấy từ [Google AI Studio](https://aistudio.google.com/), model mặc định là `gemini-1.5-flash`.

---

## 👥 3. Thêm Tài Khoản Muse AI (Tab "Kho Tài Khoản")

1. Cài đặt tiện ích **Cookie-Editor** trên trình duyệt Chrome/Edge.
2. Đăng nhập vào trang web [muse.ai](https://muse.ai) bằng tài khoản của bạn.
3. Mở tiện ích Cookie-Editor, bấm nút **Export** $\rightarrow$ Chọn **Header String**.
4. Vào Tab **"Kho Tài Khoản"** trong App, dán vào ô bên trái theo cú pháp:
   ```text
   user1@gmail.com|hatch_sess=...; other=...
   user2@gmail.com|hatch_sess=...; other=...
   user3@gmail.com|hatch_sess=...; other=...
   ```
5. Bấm **"Lưu & Kích Hoạt Tài Khoản"**. Hệ thống sẽ tự động nhận diện và đưa vào danh sách xoay tua (Pool).
6. Có thể bấm nút **"Kiểm Tra Tất Cả"** để kiểm tra tài khoản nào còn sống (`Live`), tài khoản nào hết hạn (`Expired`).

---

## 🎬 4. Quy Trình Sản Xuất MV 1-Click

### Bước 1: Lập Kế Hoạch MV Tại Tab "AI MV Director"
* Nhập: Tên bài hát, Thể loại nhạc, BPM, Giọng ca, Cảm xúc và Lời bài hát (Lyrics).
* Bấm **"Lập Kế Hoạch MV (AI)"** $\rightarrow$ Hệ thống tự động phân tích sâu và xuất bản kịch bản 7 bước:
  1. *Phân tích & Lyric Evidence Map* (Chọn 1 format tối ưu nhất trong 5 định dạng).
  2. *Khóa tạo hình Visual Bible* (Character / Style / Wardrobe / Location Lock).
  3. *Bộ ảnh mẫu Reference Pack*.
  4. *Storyboard Sheet 5s - 10s*.
  5. *Bộ Prompt video (FLOW / VEO / MUSE PROMPT)*.
  6. *Kế hoạch Timeline dựng CapCut*.
  7. *Bảng kiểm tra chất lượng*.
* *(Mẹo: Bạn cũng có thể copy prompt đem ném vào ChatGPT/Claude web ngoài rồi dán ngược lại bằng nút "Dán kịch bản ngoài")*.

### Bước 2: Chuyển Sang Render Hàng Loạt
* Sau khi AI sinh xong kịch bản, ở góc trên bên phải sẽ xuất hiện nút màu xanh:
  👉 **"Đẩy sang Batch Studio"**
* Bấm vào nút này, toàn bộ các Shot (kèm thời lượng 5s–10s, tỉ lệ 16:9, prompt chuẩn tiếng Anh) sẽ tự động được nạp vào hàng đợi render!

### Bước 3: Render & Tự Động Xoay Tài Khoản
* Chuyển sang Tab **"Batch Studio"**:
* Các tác vụ sẽ tự động được lấy ra và gán cho các tài khoản Muse trong kho:
  * Tự động chia đều cho các tài khoản (Round Robin / Least Used).
  * Nếu tài khoản A hết lượt hoặc lỗi phiên, hệ thống tự động nhảy sang tài khoản B (**Auto-Failover**).
* Bạn có thể theo dõi tiến độ từng shot render trực tiếp theo thời gian thực.

---

## 🎞️ 5. Thư Viện Video & Kéo Vào CapCut (Tab "Thư Viện & CapCut")

* Video render xong tự động được lưu vào thư mục:
  👉 **`d:\Tool\MUSE_TOOL\downloads\`**
* Bạn có thể bấm nút **"Mở Thư Mục Downloads"** để mở trực tiếp trong Windows Explorer hoặc bấm **"Tải Trọn Gói ZIP"**.
* Kéo các video vào CapCut theo hướng dẫn layer đã lập:
  * **Layer 1 (Main Track):** Shot 1, 3, 5, 7...
  * **Layer 2 (Overlay Track):** Shot 2, 4, 6...
  * **Chuyển cảnh:** Thêm hiệu ứng *Cross Dissolve (Hòa tan / Mờ dần)* gối đầu 0.5s - 1s giữa các shot.
