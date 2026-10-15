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

7. **Quy chuẩn đồng bộ 3 lớp & Xác nhận trước khi Build/Nén ZIP (BẮT BUỘC)**:
   * **Quy trình 3 Lớp**:
     1. **Lớp 1 (Code gốc)**: Sửa tại thư mục gốc workspace (`PAKH_PRECHECK/`).
     2. **Lớp 2 (Thư mục Docker)**: Đồng bộ sang thư mục triển khai docker `VNPT TTS PRECHECK/`.
     3. **Lớp 3 (Gói ZIP triển khai)**: Chạy `python update_deploy_zip.py` để đóng gói cập nhật đè vào file `VNPT_TTS_PRECHECK_DEPLOY.zip`.
   * **BẮT BUỘC HỎI Ý KIẾN TRƯỚC KHI BUILD DOCKER & NÉN FILE ZIP**:
     * **CẤM** tự ý chạy build Docker hoặc nén lại file ZIP (`update_deploy_zip.py`) sau mỗi lần sửa code nhỏ.
     * **BẮT BUỘC**: Trước khi thực hiện đồng bộ sang Docker / build lại container / nén file ZIP, AI phải hỏi ý kiến người dùng với lựa chọn rõ ràng **Yes/No**. Chỉ khi người dùng chọn **Yes (Đồng ý)** thì mới tiến hành đồng bộ và đóng gói ZIP.

8. **Quy chuẩn đặc biệt bảo vệ JavaScript Client (`static/js/dashboard.js`) - BẮT BUỘC TUÂN THỦ**:
   * File `static/js/dashboard.js` điều khiển toàn bộ Single Page App với gần 9.000 dòng code. Bất kỳ một lỗi cú pháp nhỏ (như thiếu dấu đóng ngoặc `});`, sai template string `${...}`) sẽ khiến trình duyệt crash toàn bộ runtime JS, làm đơ toàn bộ Dashboard (treo ở trạng thái "Đang tải dữ liệu phiếu...").
   * **BẮT BUỘC KIỂM TRA CÚ PHÁP BẰNG NODE.JS**: Sau mỗi lần chỉnh sửa bất kỳ dòng nào trong `static/js/dashboard.js`, **BẮT BUỘC** chạy ngay lệnh:
     `node -c "static/js/dashboard.js"`
   * **ĐIỀU KIỆN CHẶN BẮT BUỘC (STRICT GATE)**: Chỉ khi lệnh trên trả về **Exit code 0** (không có lỗi) thì mới được phép đồng bộ sang thư mục Docker và đóng gói ZIP. Tuyệt đối không bàn giao code JS chưa qua kiểm tra cú pháp `node -c`.

9. **Quy chuẩn chẩn đoán trước khi hành động (Root Cause & User Confirmation First — BẮT BUỘC)**:
   * **BẮT BUỘC**: Trước khi thực hiện bất kỳ sửa đổi code hay can thiệp hệ thống nào, AI phải:
     1. **Điều tra và làm rõ nguyên nhân gốc rễ (Root Cause Analysis)** một cách tường minh, dẫn chứng bằng logic, luồng dữ liệu hoặc mã nguồn thực tế.
     2. **Đưa ra khuyến nghị & phương án giải quyết cụ thể** (nêu rõ các file sẽ sửa và tác động).
     3. **CHỜ NGƯỜI DÙNG XÁC NHẬN / ĐỒNG Ý MỚI ĐƯỢC THỰC HIỆN SỬA CODE (ACTION).**
   * **CẤM TUYỆT ĐỐI**: Tự ý sửa code khi chưa phân tích nguyên nhân và chưa có sự đồng ý của người dùng.

10. **Quy chuẩn lập luận kỹ thuật & Cấm suy đoán vô căn cứ (Evidence-Based Engineering — BẮT BUỘC)**:
    * **Nguyên tắc tôn trọng sự thật và dữ liệu**: Mọi phân tích, lập luận kỹ thuật, chẩn đoán nguyên nhân sự cố (trên Core SAPC, BTools, SMSC, CEM, OneOSS...) **BẮT BUỘC phải dựa 100% trên tài liệu kỹ thuật chính thống, mã lỗi chuẩn hóa, mã nguồn dự án hoặc log hệ thống thực tế**.
    * **CẤM TUYỆT ĐỐI**:
      * Tự ý suy đoán chủ quan, phỏng đoán cơ chế hoạt động của hệ thống khi không có tài liệu/log kiểm chứng (ví dụ: tự suy diễn *"hệ thống phát hiện bất thường nên chủ động kích hoạt chặn"*, *"do nhà mạng nghẽn mạng"*, *"do khách bị hack sim"*... mà không có log sự kiện hoặc tài liệu đối chiếu).
      * Bịa đặt chức năng hoặc khẳng định nguyên nhân lỗi theo cảm tính của AI.
    * **Quy chuẩn phân định dữ liệu và giả thuyết**:
      * **Dữ liệu thực tế (Facts)**: Trích dẫn rõ trường dữ liệu, mã lỗi (`status_code`, `terminationcause`, `service_id`...), mốc thời gian, IP, nguồn trích xuất cụ thể từ log.
      * **Giả thuyết kỹ thuật (Hypothesis)**: Khi chưa có tài liệu xác định chắc chắn ý nghĩa mã lỗi hoặc cơ chế, AI **bắt buộc** phải nêu rõ là *"Theo dữ liệu log ghi nhận mã lỗi X... Hiện tại chưa có tài liệu/quy định chính thức khẳng định cơ chế này, cần đối soát thêm với KTV/tài liệu hệ thống"* chứ không được kết luận khẳng định như một chân lý hiển nhiên.

11. **Quy chuẩn module hóa độc lập (Modular Separation over Monolith — BẮT BUỘC)**:
    * Khi phát triển các module, tính năng hoặc nghiệp vụ phân tích mới (ví dụ: bóc tách SMS, phân tích Thoại/Spam Call, kịch bản nghiệp vụ mới...), **ƯU TIÊN TUYỆT ĐỐI tạo file code riêng biệt** (ví dụ: `ai_sms_interpreter.py`, `spam_call_analyzer.py`) thay vì tiếp tục dồn nhét vào các module lớn hiện có (như `ai_interpreter.py`, `report_bot.py`).
    * Việc này nhằm đảm bảo:
      1. **Tránh phình to file (God Object)**: Giúp kiểm soát lỗi cục bộ và tiết kiệm token khi đọc/sửa code.
      2. **Độc lập nghiệp vụ**: Tránh xung đột logic giữa các phân hệ (ví dụ: logic bóc tách Data không thể áp đặt nhầm sang SMS hay Thoại).
      3. **Dễ bảo trì & nâng cấp**: Dễ dàng chỉnh sửa, test riêng từng nghiệp vụ mà không làm ảnh hưởng luồng core đang chạy ổn định.

---

## 🗺️ 2. BẢN ĐỒ CHỈ MỤC CÁC FILE LÕI (CORE REPOSITORY MAP)

Dự án đã được phân tầng rõ ràng, mọi nghiệp vụ chỉ nằm trong các file hạt nhân sau:

| Nghiệp vụ / Tính năng | File hạt nhân | Vai trò chính |
| :--- | :--- | :--- |
| **Mã dịch vụ & Tốc độ bóp** | [`serviceid.json`](serviceid.json) | Từ điển mã gói cước, bảng mã bóp băng thông (`10002` .. `10014`), mapping tên gói data. |
| **Logic kịch bản tiền kiểm** | [`scenarios_engine.py`](scenarios_engine.py) | Thuật toán phân loại BTools: Bóp băng thông, rớt 2G/3G, treo phiên quản trị `300`/`2042`. |
| **Cấu hình kịch bản chẩn đoán** | [`diagnostic_scenarios.json`](diagnostic_scenarios.json) | Định nghĩa các bước logic chẩn đoán tuần tự. |
| **Mẫu câu kết luận & Đóng phiếu** | [`report_bot.py`](report_bot.py) | Tổng hợp chứng cứ (BTools + SAPC + CEM), sinh kết luận kỹ thuật, chọn mã lỗi đóng phiếu OneOSS. |
| **Xử lý ý định phản ánh Data** | [`ai_interpreter.py`](ai_interpreter.py) | Regex & NLP bóc tách nội dung khách báo Data (gói cước, dung lượng, chậm, mất mạng, lỗi app). |
| **Xử lý ý định phản ánh SMS** | [`ai_sms_interpreter.py`](ai_sms_interpreter.py) | Regex & NLP chuyên biệt cho tin nhắn SMS (OTP, MO/MT fail, cước SMS, TTNT, SMO). |
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
   * **Bắt buộc**: Chạy `node -c "static/js/dashboard.js"` kiểm tra cú pháp trước khi đồng bộ.
   * Kiểm tra định tuyến SPA tại [`routers/web.py`](routers/web.py) và API lọc tại [`routers/tickets.py`](routers/tickets.py).
3. **Cập nhật quy tắc đóng phiếu tự động**:
   * Kiểm tra [`routers/tickets.py`](routers/tickets.py) tại các hàm `save_autoclose_config` và điều kiện trigger.
4. **Đồng bộ 3 lớp (Bắt buộc cuối mỗi tác vụ)**:
   * Copy file vừa sửa sang thư mục `VNPT TTS PRECHECK/`.
   * Chạy `python update_deploy_zip.py` để cập nhật `VNPT_TTS_PRECHECK_DEPLOY.zip`.
