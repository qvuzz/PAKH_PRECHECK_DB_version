# AGENTS.md — Quy Chuẩn Tối Ưu Hóa Dành Cho AI (Token Saver & Precision Rules)

Tài liệu này là chỉ dẫn bắt buộc cho mọi trợ lý AI (Antigravity, Cursor, Claude Code, GitHub Copilot) khi làm việc trên dự án **PAKH_PRECHECK**.

---

## ⚡ 1. NGUYÊN TẮC TIẾT KIỆM TOKEN & TỐI ƯU TỐC ĐỘ (BẮT BUỘC)

1. **Tuyệt đối KHÔNG tạo script tạm (Zero Scratch Scripts)**:
   * **CẤM** tạo các file script Python tạm để dò tìm dữ liệu, in test hàm hay regex trong thư mục `scratch/` (như `find_*.py`, `test_*.py`).
   * Việc tạo file tạm + chạy lệnh + đọc output gây lãng phí hàng nghìn token và làm chậm phản hồi.

2. **Định vị chính xác bằng Grep (Fast Precision Search)**:
   * Khi cần tìm biến, hàm, mã dịch vụ hay logic: Dùng ngay công cụ tìm kiếm chỉ mục nhanh (`grep_search` hoặc `ripgrep`).
   * Chỉ đọc (`view_file`) đúng phạm vi các dòng cần sửa, không đọc tràn lan cả file hàng nghìn dòng.

3. **Sửa trực diện bằng Diff (Precision Chunk Editing)**:
   * Khi chỉnh sửa code, chỉ thay thế đúng đoạn dòng cần đổi (`replace_file_content`).
   * **CẤM** viết lại hoặc overwrite toàn bộ file lớn (như `report_bot.py` hay `dashboard.html`).

4. **An toàn dữ liệu & Dry-run**:
   * Tuyệt đối không tự ý kích hoạt lệnh đóng phiếu thật lên hệ thống OneOSS VNPT nếu chưa có xác nhận từ người dùng.

5. **Quy chuẩn giao diện WebApp (Professional UI Standard - BẮT BUỘC)**:
   * **CẤM TUYỆT ĐỐI THÊM EMOJI / ICON VÔ NGHĨA VÀO WEBAPP** (như 🤖, ⚡, 🚀, 🎉, 🔥, ⭐... vào nhãn, nút bấm, ô chọn select, tiêu đề, bảng hay modal thông báo).
   * Giao diện phục vụ khối Kỹ thuật Viễn thông VNPT, yêu cầu tính chuyên nghiệp, trang trọng, chỉn chu và tối giản chuẩn doanh nghiệp. Chỉ dùng chữ tiếng Việt rõ nghĩa hoặc icon SVG chức năng chuyên dụng.

---

## 🗺️ 2. BẢN ĐỒ CHỈ MỤC CÁC FILE LÕI (CORE REPOSITORY MAP)

Dự án đã được phân tầng rõ ràng, mọi nghiệp vụ chỉ nằm trong các file hạt nhân sau:

| Nghiệp vụ / Tính năng | File hạt nhân | Vai trò chính |
| :--- | :--- | :--- |
| **Mã dịch vụ & Tốc độ bóp** | [`serviceid.json`](serviceid.json) | Từ điển mã gói cước, bảng mã bóp băng thông (`10002` .. `10014`), mapping tên gói data. |
| **Logic kịch bản tiền kiểm** | [`scenarios_engine.py`](scenarios_engine.py) | Thuật toán phân loại BTools: Bóp băng thông, rớt 2G/3G, treo phiên quản trị `300`/`2042`. |
| **Cấu hình kịch bản chẩn đoán** | [`diagnostic_scenarios.json`](diagnostic_scenarios.json) | Định nghĩa các bước logic chẩn đoán tuần tự. |
| **Mẫu câu kết luận & Đóng phiếu** | [`report_bot.py`](report_bot.py) | Tổng hợp chứng cứ (BTools + SAPC + CEM), sinh kết luận kỹ thuật, chọn mã lỗi đóng phiếu OneOSS. |
| **Xử lý ý định phản ánh** | [`ai_interpreter.py`](ai_interpreter.py) | Regex & NLP bóc tách nội dung khách báo (chậm, mất mạng, lỗi app, thoại). |
| **API Phiếu & Điều phối Web** | [`routers/tickets.py`](routers/tickets.py) | Danh sách phiếu, phân loại tab Data/Cuộc gọi/SMS, kích hoạt quét và tiền kiểm, lưu cấu hình Auto-Close. |
| **Đăng nhập & Phiên KTV** | [`routers/auth.py`](routers/auth.py) | Đăng nhập TTS cũ, TTS mới, xử lý OTP và session token. |
| **FastAPI Server & WebSocket** | [`main.py`](main.py) | Server cổng 1234, kết nối WebSocket realtime, cron background auto-scan. |
| **Giao diện Dashboard** | [`templates/dashboard.html`](templates/dashboard.html) | Giao diện SPA, bảng phiếu, drawer chi tiết, modal đăng nhập. |
| **Phong cách giao diện** | [`static/css/dashboard.css`](static/css/dashboard.css) | Toàn bộ CSS phong cách VNPT hiện đại. |
| **JavaScript phía Client** | [`static/js/dashboard.js`](static/js/dashboard.js) | Gọi API, xử lý DOM, kết nối WebSocket cập nhật bảng phiếu realtime. |
| **Kết nối OneOSS TTS** | [`ttsnew_api.py`](ttsnew_api.py), [`tts_old_api.py`](tts_old_api.py) | Crawl danh sách phiếu và cập nhật kết quả xử lý lên OneOSS. |
| **Kết nối BTools Chrome CDP** | [`btools_manager.py`](btools_manager.py) | Quản lý phiên Chrome port 9222 cào lịch sử phiên 4G/5G. |
| **Hồ sơ Core SAPC** | [`sapccheck/`](sapccheck/) | Kiểm tra trạng thái gói cước, cờ NAM khóa cước, HSS Profile. |
| **Sóng trạm CEM** | [`cem_client.py`](cem_client.py) | Kiểm tra chất lượng phát sóng và sự cố trạm. |
| **Cơ sở dữ liệu SQLite** | [`db_manager.py`](db_manager.py) ➔ `tickets.db` | Lưu vết phiếu, cấu hình đóng phiếu tự động, lịch sử tiền kiểm. |

---

## 🎯 3. CHECKLIST KHI CÓ YÊU CẦU SỬA ĐỔI MỚI

1. **Thêm/sửa mã bóp băng thông**:
   * Sửa [`serviceid.json`](serviceid.json) (thêm mã + tốc độ kbps).
   * Sửa [`scenarios_engine.py`](scenarios_engine.py) (kiểm tra hàm nhận diện bóp).
   * Sửa [`report_bot.py`](report_bot.py) (câu diễn giải gửi KTV).
2. **Sửa giao diện Dashboard / Thêm tab dịch vụ**:
   * Sửa [`templates/dashboard.html`](templates/dashboard.html).
   * Sửa CSS [`static/css/dashboard.css`](static/css/dashboard.css) và JS [`static/js/dashboard.js`](static/js/dashboard.js).
   * Kiểm tra định tuyến SPA tại [`routers/web.py`](routers/web.py) và API lọc tại [`routers/tickets.py`](routers/tickets.py).
3. **Cập nhật quy tắc đóng phiếu tự động**:
   * Kiểm tra [`routers/tickets.py`](routers/tickets.py) tại các hàm `save_autoclose_config` và điều kiện trigger.
