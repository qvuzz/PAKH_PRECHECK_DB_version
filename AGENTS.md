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

6. **Quy chuẩn địa giới hành chính mới (Phường/Xã & 34 Tỉnh/TP mới — BẮT BUỘC TUÂN THỦ)**:
   * **Chuẩn định dạng bắt buộc (DUY NHẤT 2 CẤP)**:
     * Định dạng chuẩn duy nhất: `[Phường/Xã/Thị trấn], [Tỉnh/Thành phố]` (hoặc `Đặc khu`).
     * **TUYỆT ĐỐI KHÔNG** lấy cấp thôn, ấp, bản, khóm, xóm, tổ dân phố (như *Thôn 3*, *Chủ Chí*, *Ấp 1*, *Tổ 5*...).
     * **TUYỆT ĐỐI KHÔNG** dùng mã trạm rút gọn hay viết tắt viễn thông (như *PLO*, *DLI*, *BLU*, *TDM*...) làm tên địa bàn.
   * **Bảng Chuẩn 34 Tỉnh / Thành phố mới & Phân chia 3 Miền (BẮT BUỘC TUÂN THỦ TUYỆT ĐỐI)**:

| STT | Tỉnh / Thành phố mới | Các tỉnh sáp nhập vào | Khu vực (Miền) |
| :---: | :--- | :--- | :---: |
| 1 | **TP. Hà Nội** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 2 | **TP. Hải Phòng** | TP. Hải Phòng + Hải Dương | **Miền Bắc (`MB`)** |
| 3 | **Tỉnh Cao Bằng** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 4 | **Tỉnh Lạng Sơn** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 5 | **Tỉnh Lai Châu** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 6 | **Tỉnh Điện Biên** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 7 | **Tỉnh Sơn La** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 8 | **Tỉnh Quảng Ninh** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 9 | **Tỉnh Tuyên Quang** | Hà Giang + Tuyên Quang | **Miền Bắc (`MB`)** |
| 10 | **Tỉnh Lào Cai** | Yên Bái + Lào Cai | **Miền Bắc (`MB`)** |
| 11 | **Tỉnh Thái Nguyên** | Bắc Kạn + Thái Nguyên | **Miền Bắc (`MB`)** |
| 12 | **Tỉnh Phú Thọ** | Vĩnh Phúc + Hòa Bình + Phú Thọ | **Miền Bắc (`MB`)** |
| 13 | **Tỉnh Bắc Ninh** | Bắc Giang + Bắc Ninh | **Miền Bắc (`MB`)** |
| 14 | **Tỉnh Hưng Yên** | Thái Bình + Hưng Yên | **Miền Bắc (`MB`)** |
| 15 | **Tỉnh Ninh Bình** | Hà Nam + Nam Định + Ninh Bình | **Miền Bắc (`MB`)** |
| 16 | **Tỉnh Thanh Hóa** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 17 | **Tỉnh Nghệ An** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 18 | **Tỉnh Hà Tĩnh** | Giữ nguyên | **Miền Bắc (`MB`)** |
| 19 | **Tỉnh Lâm Đồng** | Đắk Nông + Bình Thuận + Lâm Đồng | **Miền Nam (`MN`)** |
| 20 | **TP. Hồ Chí Minh** | TP.HCM + Bình Dương + Bà Rịa – Vũng Tàu | **Miền Nam (`MN`)** |
| 21 | **TP. Cần Thơ** | TP. Cần Thơ + Sóc Trăng + Hậu Giang | **Miền Nam (`MN`)** |
| 22 | **Tỉnh Đồng Nai** | Bình Phước + Đồng Nai | **Miền Nam (`MN`)** |
| 23 | **Tỉnh Tây Ninh** | Long An + Tây Ninh | **Miền Nam (`MN`)** |
| 24 | **Tỉnh Vĩnh Long** | Bến Tre + Trà Vinh + Vĩnh Long | **Miền Nam (`MN`)** |
| 25 | **Tỉnh Đồng Tháp** | Tiền Giang + Đồng Tháp | **Miền Nam (`MN`)** |
| 26 | **Tỉnh Cà Mau** | Bạc Liêu + Cà Mau | **Miền Nam (`MN`)** |
| 27 | **Tỉnh An Giang** | Kiên Giang + An Giang *(gồm Đặc khu Phú Quốc)* | **Miền Nam (`MN`)** |
| 28 | **TP. Huế** | Giữ nguyên *(nâng cấp từ Thừa Thiên Huế)* | **Miền Trung (`MT`)** |
| 29 | **TP. Đà Nẵng** | TP. Đà Nẵng + Quảng Nam | **Miền Trung (`MT`)** |
| 30 | **Tỉnh Quảng Trị** | Quảng Bình + Quảng Trị | **Miền Trung (`MT`)** |
| 31 | **Tỉnh Quảng Ngãi** | Kon Tum + Quảng Ngãi | **Miền Trung (`MT`)** |
| 32 | **Tỉnh Gia Lai** | Bình Định + Gia Lai | **Miền Trung (`MT`)** |
| 33 | **Tỉnh Khánh Hòa** | Ninh Thuận + Khánh Hòa | **Miền Trung (`MT`)** |
| 34 | **Tỉnh Đắk Lắk** | Phú Yên + Đắk Lắk | **Miền Trung (`MT`)** |

   * **Tổng kết phân bổ 3 Miền**:
     * **Miền Bắc (`MB`)**: **18 đơn vị** (2 TP: Hà Nội, Hải Phòng + 16 Tỉnh: Cao Bằng, Lạng Sơn, Lai Châu, Điện Biên, Sơn La, Quảng Ninh, Tuyên Quang, Lào Cai, Thái Nguyên, Phú Thọ, Bắc Ninh, Hưng Yên, Ninh Bình, Thanh Hóa, Nghệ An, Hà Tĩnh).
     * **Miền Nam (`MN`)**: **9 đơn vị** (2 TP: TP. Hồ Chí Minh, TP. Cần Thơ + 7 Tỉnh: Lâm Đồng, Đồng Nai, Tây Ninh, Vĩnh Long, Đồng Tháp, Cà Mau, An Giang).
     * **Miền Trung (`MT`)**: **7 đơn vị** (2 TP: Huế, Đà Nẵng + 5 Tỉnh: Quảng Trị, Quảng Ngãi, Gia Lai, Khánh Hòa, Đắk Lắk).
   * **Nguồn chân lý xác thực địa bàn (Port 1708 Google Maps Geocoding)**:
     * Luôn lấy kết quả địa bàn tham chiếu chuẩn từ API Google Maps của service nội bộ:
       `http://127.0.0.1:1708/api/reverse-geocode?lat=...&long=...` kết hợp tọa độ GPS (lat/long) từ CEM.
     * Hàm chuẩn hóa lõi: [`normalize_vn_commune_and_province()`](routers/tickets.py) tự động trích xuất đúng `Phường/Xã` và `Tỉnh/TP`.

7. **Quy chuẩn đồng bộ 3 lớp bắt buộc (Code gốc ➔ Thư mục Docker ➔ File nén ZIP)**:
   * **BẮT BUỘC**: Mỗi khi tạo mới hoặc sửa đổi bất kỳ file code, cấu hình, template, static hay tài liệu triển khai nào:
     1. **Lớp 1 (Code gốc)**: Sửa tại thư mục gốc workspace (`PAKH_PRECHECK/`).
     2. **Lớp 2 (Thư mục Docker)**: Đồng bộ ngay lập tức sang thư mục triển khai docker `VNPT TTS PRECHECK/` (giữ nguyên cấu trúc thư mục).
     3. **Lớp 3 (Gói ZIP triển khai)**: Chạy `python update_deploy_zip.py` để đóng gói cập nhật đè vào file `VNPT_TTS_PRECHECK_DEPLOY.zip`.
   * **Mục tiêu**: Đảm bảo code chạy trên máy trạm dev, thư mục docker server và file nén bàn giao cho KTV luôn đồng bộ 100%, không bị lệch phiên bản.

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
4. **Đồng bộ 3 lớp (Bắt buộc cuối mỗi tác vụ)**:
   * Copy file vừa sửa sang thư mục `VNPT TTS PRECHECK/`.
   * Chạy `python update_deploy_zip.py` để cập nhật `VNPT_TTS_PRECHECK_DEPLOY.zip`.
