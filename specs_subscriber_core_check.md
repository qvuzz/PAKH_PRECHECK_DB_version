# TÀI LIỆU KỸ THUẬT: HỆ THỐNG TRA CỨU "KIỂM TRA DỊCH VỤ THUÊ BAO DI ĐỘNG" (CORE HSS/HLR/OCS)

- **Hệ thống**: Web Portal Tra cứu Dịch vụ Thuê bao Di động VNPT (Core HSS/HLR/OCS/EPC/IMS)
- **Địa chỉ truy cập**: `http://10.155.42.218`
- **Mục đích**: Tra cứu trạng thái dịch vụ thời gian thực của thuê bao di động phục vụ tiền kiểm sự cố mạng, cuộc gọi, tin nhắn, data, cước và roaming.

---

## 1. PHÂN HỆ TRA CỨU SMS (TAB SMS) — CÁC TRƯỜNG DỮ LIỆU ĐẶC BIỆT DÙNG ĐƯỢC CHO TIỀN KIỂM PHIẾU

Trang cung cấp các cờ dịch vụ SMS chuyên sâu trên cả 2 miền mạng: **2G/3G (CS Core)** và **VoLTE (IMS Core)**.

### 1.1. Dịch vụ SMO trên miền 2G/3G (Short Message Originated — Gửi tin nhắn đi)
* **`OBO & TS22`**:
  * Ý nghĩa: Cờ khóa chặn chiều gửi tin nhắn đi từ phía nhà mạng (Operator Barring of Outgoing SMS / Teleservice 22).
  * Giá trị chuẩn bình thường: `2 & 1` ➔ Hiển thị: **"không bị chặn gửi SMS đi"**.
  * Ứng dụng: Khi khách hàng báo **không gửi được tin nhắn đi** (báo chấm than), kiểm tra trường này nếu khác `2 & 1` là do thuê bao bị khóa chặn chiều gửi tin từ Core.
* **`BAOC` (Barring of All Outgoing Calls/SMS)**:
  * Ý nghĩa: Cờ khách hàng tự kích hoạt khóa chiều gửi tin trên thiết bị đầu cuối.
  * Giá trị chuẩn: Rỗng hoặc `0` ➔ Hiển thị: **"không tự chặn SMS đi"**.

### 1.2. Dịch vụ SMT trên miền 2G/3G (Short Message Terminated — Nhận tin nhắn đến)
* **`OBI & TS21`**:
  * Ý nghĩa: Cờ khóa chặn chiều nhận tin nhắn đến từ phía nhà mạng (Operator Barring of Incoming SMS / Teleservice 21).
  * Giá trị chuẩn bình thường: `null & 1` ➔ Hiển thị: **"không bị chặn gửi/nhận SMS đến"**.
  * Ứng dụng: Khi khách hàng báo **không nhận được OTP** hoặc **không nhận được bất kỳ tin nhắn nào đến**, kiểm tra trường này nếu bị khóa ➔ Khẳng định lỗi do cờ OBI trên Core.
* **`BAIC` (Barring of All Incoming Calls/SMS)**:
  * Ý nghĩa: Cờ khách hàng tự kích hoạt chặn nhận tin trên thiết bị.
  * Giá trị chuẩn: `0` ➔ Hiển thị: **"không tự chặn SMS đến"**.
* **`SMSHR`**:
  * Ý nghĩa: Cờ chuyển tiếp / định tuyến tin nhắn (Short Message Home Routing / Mplus).
  * Giá trị chuẩn: `2-7-1` ➔ Hiển thị: **"không dùng dịch vụ Mplus"**.
  * Ứng dụng: Nhận biết thuê bao có đăng ký các dịch vụ định tuyến tin nhắn đặc thù (Mplus) gây ảnh hưởng tới luồng nhận OTP hay không.

### 1.3. Dịch vụ SMO trên miền VoLTE (SMS over IP / IMS Core)
* **`SMSBarring`**:
  * Ý nghĩa: Cờ chặn tin nhắn SMS trên nền VoLTE / IMS.
  * Giá trị chuẩn: `0` ➔ Hiển thị: **"không bị chặn SMS đi"**.
  * Ứng dụng: Thuê bao sử dụng VoLTE gửi SMS qua kênh IMS (SMS over IP). Có trường hợp thuê bao gọi VoLTE bình thường nhưng cờ `SMSBarring` bị bật khiến không thể gửi tin nhắn đi qua mạng 4G/VoLTE.

### 1.4. Thông tin cơ bản thuê bao & Thiết bị thực tế
* **`HSS STATE`**: `REGISTERED` ➔ Thuê bao đang đăng ký thành công trên Core HSS.
* **`USER AGENT`**: Ví dụ `iOS/27.0.1 iPhone` ➔ **Nhận diện chính xác 100% dòng máy thực tế** mà khách đang lắp SIM sử dụng, đối soát ngay với dòng máy khách khai báo trên phiếu.
* **`CSCF`**: `Register VoLTE` ➔ Trạng thái đăng ký server điều khiển phiên IMS.
* **`MSC` / `MME`**: Xác định node mạng lõi thuê bao đang bám.

---

## 2. PHÂN HỆ OCS (TAB OCS) — DỮ LIỆU CƯỚC & LỊCH SỬ TIN NHẮN LỖI

Tab này cung cấp thông tin sống còn cho các khiếu nại cước SMS và sự cố gửi/nhận thất bại:

1. **Khung "Lịch sử các tin nhắn lỗi" (Vô cùng giá trị)**:
   * **Cột dữ liệu**: `STT`, `Transaction DateTime`, `Other Party Number`, `ErrCode`, `Location Number`.
   * **Ứng dụng**: Khi khách hàng báo lỗi gửi/nhận SMS hoặc thắc mắc bị trừ cước, bảng này liệt kê chính xác các mốc thời gian tin nhắn bị lỗi kèm **Mã lỗi cụ thể (`ErrCode`)**, giúp chẩn đoán nguyên nhân tận gốc mà không cần tra cứu log thô SMSC.
2. **Khung "Lịch sử các cuộc gọi lỗi"**:
   * Tương tự bảng tin nhắn lỗi, liệt kê các cuộc gọi bị rớt/thất bại kèm `ErrCode`.
3. **Trạng thái tài khoản & Thuê bao**:
   * `ActivationStatusFlag`: `1` (Đã kích hoạt).
   * `TemporaryBlockedFlag`: Đang hoạt động / Bị chặn.
   * `PostPaidState`: `Active` (Trả sau không bị khóa dịch vụ).
   * `SupervisionExpireDate`: Hạn sử dụng của thuê bao.

---

## 3. PHÂN HỆ DATA (TAB DATA)
* `PDPCP`, `NAM`: `0` (Mở dịch vụ data 2G/3G).
* `epsProfileID`: `67` (5G/VoLTE sử dụng gói qua OCS).
* `SGSN`, `MME Address`, `GGSN/PGW`.
* `PCC Rule`: Mã rule chính sách (ví dụ `3000`).
* `LOCTYPE`: `LAI` (Ăn sóng 4G).
* `APN ID`: `m3-world.mnc002.mcc452.gprs` (IPv4, IPv6) & `ims.mnc002.mcc452.gprs`.
* `LIMIT USAGE` & `ACCUMULATED DATA`: Tên gói data, dung lượng đã dùng, chu kỳ reset gói.

---

## 4. PHÂN HỆ VOICE & ROAMING
* **Tab Voice**: Dịch vụ MO/MT trên miền 2G/3G và VoLTE, chuyển tiếp cuộc gọi, chặn cuộc gọi, thông tin bổ sung.
* **Tab Roaming**: Profile Roaming HLR (`OBR`), HSS (`Roaming Allow`), VLR mạng khách, cấu hình Data Roaming.
