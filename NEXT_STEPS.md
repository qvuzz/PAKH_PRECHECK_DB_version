# 📋 KẾ HOẠCH CÔNG VIỆC TIẾP THEO (ROADMAP & TO-DO)
**Dự án:** Hệ thống Tiền kiểm và Tự động hóa Xử lý PAKH (TTS Cũ & TTS Mới)
**Ngày cập nhật:** 08/09/2026

---

## 📌 PHẦN I. HIỆN TRẠNG ĐÃ HOÀN TẤT & ĐANG HOẠT ĐỘNG ỔN ĐỊNH

1. **Giao diện & Trải nghiệm KTV (Client / Server):**
   - Đã chuẩn hóa thanh công cụ trên cùng (Header & Top Toolbar): hiển thị nhỏ gọn các chỉ báo trạng thái dịch vụ (BTools, CEM, SAPC, TTS Cũ, TTS Mới) kèm tooltip kết nối.
   - Giữ đầy đủ cụm điều khiển: *Chu kỳ quét*, nút *Bắt đầu / Tạm dừng* và nút *Tiền kiểm ngay*.
   - Cửa sổ đăng nhập TTS Mới / TTS Cũ thu gọn thành popup nhỏ ngay tại nút bấm, bảo mật và thân thiện với KTV mạng LAN.

2. **Cơ chế Danh tính KTV & Phân quyền LAN:**
   - Cách ly tuyệt đối giữa máy chủ (Admin `quangvu`) và các máy trạm LAN (KTV `nguyenhoa`, `10.155.139.145`, `10.155.139.167`...).
   - Token và thông tin KTV được ghi nhận và lưu tự động vào `lan_sessions.json`.
   - Mọi thao tác đóng/chuyển bước phiếu (TTS Cũ & TTS Mới) gửi đúng Bearer JWT / Cookie SSO của KTV thao tác, ghi nhận chính danh người xử lý trên OneOSS.

3. **Luồng xử lý TTS Mới (Quy trình 2 vòng chuẩn OneOSS):**
   - **Vòng 1 (Bước 2.4 - Phối hợp xử lý phản ánh):**
     - Tự động rẽ nhánh sang `5.1 Xây dựng PA xử lý` nếu nội dung có từ khóa chuyển VTT/địa bàn, tự động tra cứu và định tuyến đúng mã VNPT Tỉnh (ví dụ: TP.HCM -> `4636`).
     - Tự động rẽ nhánh sang `2.6 Đóng phiếu Trên TTS` nếu đóng phiếu kỹ thuật tại đơn vị (SOC2).
   - **Vòng 2 (Bước 2.6 - Đóng phiếu Trên TTS):**
     - Đóng dứt điểm qua API `/TicketProcessing/close-ticket` kèm nguyên nhân đóng chuẩn hóa và nội dung cột 10 + 11.
   - **Bảo vệ an toàn phiếu mở lại (Reopened tickets):**
     - Phát hiện `reopenCount > 0` -> Khóa tự động đóng, gắn cờ đỏ `KHÔNG TỰ ĐÓNG`, nút cam cảnh báo yêu cầu KTV xác nhận thủ công.

---

## 🚀 PHẦN II. CÁC HẠNG MỤC CẦN LÀM TIẾP THEO (NEXT STEPS)

### 1. Tự động hóa liên hoàn 2 vòng (Auto-chaining 2.4 -> 2.6):
- **Vấn đề hiện tại:** Khi KTV bấm đóng tại bước 2.4, phiếu chuyển sang trạng thái *"Chờ lần 2"*. KTV phải đợi đến chu kỳ quét kế tiếp (hoặc bấm Quét lại) mới thấy phiếu ở 2.6 để đóng tiếp.
- **Giải pháp đề xuất:** 
  - Sau khi chuyển bước 2.4 thành công, backend tự động khởi tạo một tác vụ ngầm kiểm tra định kỳ (poll sau mỗi 10-15s, tối đa 3 lần).
  - Ngay khi OneOSS sinh ra node `2.6`, worker tự động gọi tiếp API `close-ticket` để đóng dứt điểm luôn.
  - KTV trên máy client chỉ cần bấm **1 lần duy nhất** là phiếu hoàn tất 100%.

### 2. Bộ lọc & Báo cáo thống kê năng suất KTV:
- Thêm tab hoặc bộ lọc nhanh theo KTV xử lý trên giao diện:
  - Xem số lượng phiếu đã đóng trong ca trực của riêng mình (`closed_by`).
  - Xuất báo cáo ca trực nhanh theo KTV (Excel / Thống kê số lượng theo từng nhóm nguyên nhân).

### 3. Nâng cấp bộ phân tích chuyên sâu Thoại / SMS trên TTS Mới:
- Hiện tại phân hệ Mobile Internet (Data) đã hoàn thiện 100%.
- Tiếp tục hoàn thiện kịch bản nhận định lỗi và bảng mapping nguyên nhân cho các phiếu phản ánh dịch vụ Thoại, SMS, Chuyển mạng giữ số (MNP), Gói cước trên TTS Mới tương tự như TTS Cũ.

### 4. Tự động làm mới phiên (Auto-refresh Cookie / Token):
- Bổ sung cơ chế kiểm tra hạn dùng ngầm của cookie BTools và token SAPC / CEM.
- Tự động gửi cảnh báo hoặc tự động làm mới khi phiên đăng nhập sắp hết hạn để tránh gián đoạn các chu kỳ quét ca đêm.

### 5. Tối ưu hóa tài nguyên & Dọn dẹp codebase:
- Dọn dẹp các tệp thử nghiệm trong thư mục `scratch/` sau quá trình debug.
- Viết file `HDSD_KTV.md` (Hướng dẫn sử dụng nhanh) gồm 3 bước dành cho KTV mới vào ca trực kết nối và sử dụng hệ thống.

---

## 💡 CÁCH TIẾP TỤC TRONG PHIÊN TIẾP THEO:
> Khi bắt đầu phiên mới, bạn chỉ cần nhắn:  
> *"Tiếp tục thực hiện mục số 1 trong file NEXT_STEPS.md (Auto-chaining đóng liên hoàn 2 vòng 2.4 -> 2.6)"* hoặc bất kỳ mục nào bạn muốn ưu tiên làm trước!
