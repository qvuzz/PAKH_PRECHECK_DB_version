# ⚡ VNPT Multi-Tool Auto-Sync Helper (v2.5)

Tiện ích Chrome mở rộng hỗ trợ kỹ sư VNPT Telecom tự động liên kết và đồng bộ token/cookie từ các cổng nghiệp vụ trực tiếp về **KPI AI Assistant (Port 710)** và **PAKH Precheck (Port 1234)** mà **KHÔNG CẦN mở port CDP 9222** hay quét ổ cứng:

1. **OneOSS / NPMRAN** (`https://npmran.vnpt.vn`, `https://oneoss.vnpt.vn`) $\rightarrow$ Đồng bộ Token 4G về KPI Assistant (Port 710)
2. **PMS 3G & 5G** (`https://pms.vnpt.vn`) $\rightarrow$ Đồng bộ Cookie sessionid & csrftoken về KPI Assistant (Port 710)
3. **TTS Mới** (`https://tts.vnptnet.vn`) $\rightarrow$ Đồng bộ sang cả Port 710 & Port 1234
4. **TTS Cũ** (`https://tts.vnpt.vn`), **BTools**, **CEM Sóng trạm**, **SAPC**, **CCOS** $\rightarrow$ Đồng bộ sang Precheck (Port 1234)

---

## 🛠️ Hướng Dẫn Cài Đặt / Nạp Vào Chrome:

1. Mở trình duyệt Chrome hoặc Microsoft Edge.
2. Truy cập: `chrome://extensions/` (hoặc `edge://extensions/`).
3. Bật công tắc **Chế độ dành cho nhà phát triển (Developer mode)** ở góc trên bên phải.
4. **Nếu đã cài tiện ích trước đó (`extension_precheck`)**:
   - Nhấp vào nút **Tải lại (Biểu tượng 🔄)** trên thẻ tiện ích.
5. **Nếu cài mới**:
   - Nhấp nút **Tải tiện ích đã giải nén (Load unpacked)** $\rightarrow$ Chọn thư mục `chrome_extension` này (hoặc `..\PAKH_PRECHECK\extension_precheck`).

---

## 🚀 Cách Sử Dụng (Hoàn toàn tự động 100%):
- Mỗi khi bạn mở tab **OneOSS** (`npmran.vnpt.vn`), **PMS** (`pms.vnpt.vn`) hoặc các cổng nghiệp vụ trên Chrome:
  Tiện ích sẽ tự động nhận diện token và gửi về `http://localhost:710`.
- Góc dưới màn hình sẽ hiển thị huy hiệu thông báo: `⚡ Đã đồng bộ Token OneOSS / Cookie PMS thành công!`.
- Trên giao diện **KPI AI Assistant**, chip trạng thái sẽ tự động chuyển sang màu xanh:
  - `4G OneOSS: Đã kết nối (tên_tài_khoản)`
  - `PMS 3G/5G: Hoạt động (...)`
