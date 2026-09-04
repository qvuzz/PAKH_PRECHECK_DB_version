# 🛡️ VNPT TTS Precheck — Hệ Thống Tiền Kiểm Phản Ánh Khách Hàng

> **Nền tảng tự động hóa tiền kiểm tra, phân tích hạ tầng Core và đóng phiếu sự cố mạng di động VNPT / VinaPhone.**  
> Hỗ trợ song song cả **Hệ thống TTS Cũ** (`tts.vnpt.vn`) và **Hệ thống TTS Mới** (`tts.vnptnet.vn`), tích hợp phân tích AI, tra cứu hạ tầng Core (HSS/HLR/Cell ID/SAPC), BTools và Dashboard điều hành tập trung.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![VNPT](https://img.shields.io/badge/VNPT-Brand%20Blue-005baa)](https://vnpt.vn)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📋 Mục Lục

1. [Tổng quan hệ thống](#-tổng-quan-hệ-thống)
2. [Các tính năng nổi bật](#-các-tính-năng-nổi-bật)
3. [Kiến trúc phân tầng (Modular Architecture)](#-kiến-trúc-phân-tầng-modular-architecture)
4. [Cấu trúc mã nguồn](#-cấu-trúc-mã-nguồn)
5. [Quy trình tiền kiểm & Đóng phiếu](#-quy-trình-tiền-kiểm--đóng-phiếu)
6. [Cài đặt & Khởi chạy](#-cài-đặt--khởi-chạy)
7. [Chế độ đóng phiếu (Tự động vs Thủ công)](#-chế-độ-đóng-phiếu-tự-động-vs-thủ-công)
8. [Bảo mật & Phân quyền](#-bảo-mật--phân-quyền)

---

## 🌐 Tổng Quan Hệ Thống

**VNPT TTS Precheck** giải quyết bài toán xử lý hàng nghìn phiếu phản ánh sự cố mạng di động (Mobile Internet, Cuộc gọi, Tin nhắn SMS, Gói cước...) mỗi ngày bằng cách:
* **Tự động trích xuất danh sách phiếu sự cố**: Cào giao diện qua Selenium (TTS Cũ) và gọi REST API ngầm siêu tốc (TTS Mới).
* **Tiền kiểm tra tức thì hạ tầng Core**:
  * Tra cứu thông tin hồ sơ thuê bao HSS/HLR (Radio 2G/3G/4G/5G, IP, trạng thái NAM/Khóa GPRS).
  * Tra cứu trạm phát sóng (Cell ID / ECGI) phục vụ tại thời điểm xảy ra sự cố.
  * Phân tích chính sách gói cước thực tế từ hệ thống SAPC.
  * Trích xuất lịch sử phiên truy cập dữ liệu kỹ thuật từ BTools.
* **Tóm tắt thông minh**:
  * **Phiếu Mobile Internet**: Ứng dụng mô hình AI tóm tắt ngắn gọn 6 trường thông tin phản ánh cốt lõi.
  * **Phiếu Thoại / SMS / Gói cước**: Giữ nguyên vẹn toàn bộ nội dung phản ánh gốc để nhân viên kỹ thuật nắm bắt chính xác hiện tượng.
* **Tự động đóng phiếu chuẩn xác**: Áp dụng bộ 6 kịch bản chuẩn đoán và phân loại lỗi để tự động đóng phiếu đúng nguyên nhân, hoặc hỗ trợ mở tab chi tiết để đóng thủ công an toàn.

---

## ✨ Các Tính Năng Nổi Bật

| Nhóm chức năng | Chi tiết |
|---|---|
| 🏢 **Hệ Thống TTS Cũ** | Tự động đọc bảng phiếu, tiền kiểm tra hạ tầng Core & BTools, tự động click đóng phiếu qua Chrome CDP. |
| ⚡ **Hệ Thống TTS Mới** | Tích hợp sâu REST API (`/ticket-mobile/search`, `/ticket-mobile/finish-ticket`), tự động trích xuất token đăng nhập từ trình duyệt, tiền kiểm hàng trăm phiếu chỉ trong vài giây. |
| 📶 **Mobile Internet** | Đối soát dung lượng, chặn bóp băng thông, treo gói, lỗi sóng 4G/3G, tóm tắt AI chuyên sâu. |
| 📞 **Thoại / SMS / Gói** | Quét riêng biệt danh mục sự cố ngoài Data (Gọi đi/đến, SMS, Spam, Khóa cước...), tra cứu HLR/HSS và Cell ID. |
| 🎛️ **Dashboard Hiện Đại** | Giao diện chuẩn màu xanh VNPT (`#005baa`), phẳng, chuyên nghiệp, hiển thị Live Log thời gian thực, bộ lọc trạng thái và thống kê tự động. |
| 🎯 **Đóng Thủ Công 1-Click** | Nút chuyển thẳng sang tab chi tiết phiếu (`chi-tiet-phieu-pakh`) trên TTS Mới, sẵn sàng để người dùng nghiệm thu và đóng phiếu. |
| 📊 **Xuất Báo Cáo Excel** | Xuất bảng tổng hợp 12 cột chuẩn quy chuẩn VNPT kèm tô màu phân loại nhận định. |

---

## 🏗️ Kiến Trúc Phân Tầng (Modular Architecture)

Mã nguồn được tái cấu trúc thành các module độc lập, tách biệt rõ ràng giữa điều phối máy chủ, dịch vụ nghiệp vụ và giao diện người dùng:

```
PAKH_PRECHECK/
├── dashboard.py                     # HTTP Server Router & Điều phối trung tâm (~500 dòng)
├── templates/
│   └── dashboard.html               # Giao diện Web HTML, CSS phẳng chuyên nghiệp & Client JS
├── services/
│   ├── __init__.py                  # Package marker
│   ├── state.py                     # Singleton AutomationState quản lý tiến trình & logs
│   ├── tts_old_data.py              # Logic tiền kiểm & chu kỳ quét Mobile Internet (TTS Cũ)
│   ├── tts_old_voice.py             # Logic tiền kiểm & chu kỳ quét Thoại / SMS / Gói (TTS Cũ)
│   ├── tts_new_data.py              # Logic gọi REST API & tiền kiểm Mobile Internet (TTS Mới)
│   ├── tts_new_voice.py             # Logic gọi REST API & tiền kiểm Thoại / SMS / Gói (TTS Mới)
│   └── automation_worker.py         # Worker luồng ngầm chạy chu kỳ quét tự động định kỳ
├── ttsnew_api.py                    # Module giao tiếp REST API TTS Mới & trích xuất Bearer Token
├── update_tts/                      # Bộ điều khiển đóng phiếu trên TTS Cũ
├── sapccheck/                       # Module tra cứu SAPC và thông tin thuê bao
└── open_dashboard.bat               # File khởi chạy 1-click cho người dùng Windows
```

---

## 📁 Cấu Trúc Mã Nguồn Chi Tiết

* **`dashboard.py`**: Khởi chạy `ThreadingHTTPServer` cổng `1234`, tiếp nhận các yêu cầu API điều khiển (`/api/start`, `/api/stop`, `/api/run-now`, `/api/tickets`, `/api/ttsnew/open_detail`...).
* **`templates/dashboard.html`**: Nạp giao diện người dùng động. Có thể chỉnh sửa giao diện mà không cần khởi động lại tiến trình Python.
* **`services/tts_old_data.py` & `services/tts_old_voice.py`**: Tương tác với Chrome đang mở (cổng 9222), đọc DOM của `tts.vnpt.vn`, bóc tách dữ liệu và lưu vào cơ sở dữ liệu SQLite `tickets.db`.
* **`services/tts_new_data.py` & `services/tts_new_voice.py`**: Gọi trực tiếp REST API `https://tts.vnptnet.vn` với Bearer Token được đọc tự động từ trình duyệt, phân loại danh sách phiếu Mobile Internet và ngoài Mobile Internet.
* **`ai_interpreter.py`**: Tóm tắt phản ánh khách hàng bằng AI (Qwen/Groq hoặc Gemini) kèm cơ chế offline fallback (Fuzzy/NLP).
* **`report_bot.py`**: Engine phân loại trạng thái theo 6 kịch bản chuẩn đoán và xuất báo cáo Excel định dạng chuẩn.

---

## 🚀 Cài Đặt & Khởi Chạy

### 1. Yêu cầu tiên quyết
- **Hệ điều hành**: Windows 10/11.
- **Python**: Phiên bản 3.10 trở lên.
- **Google Chrome**: Cài đặt sẵn trên máy.

### 2. Cài đặt các thư viện cần thiết
```bash
pip install -r requirements.txt
```
*(Nếu chưa có file `requirements.txt`: `pip install selenium requests openpyxl rapidfuzz google-generativeai python-dotenv`)*

### 3. Khởi chạy 1-Click (Khuyến nghị)
Nhấp đúp chuột vào file:
```bash
open_dashboard.bat
```
Script sẽ tự động:
1. Mở Google Chrome ở chế độ Remote Debugging (cổng 9222).
2. Khởi động Web Server Python tại `http://localhost:1234`.
3. Tự động mở giao diện Dashboard trên trình duyệt của bạn.

---

## ⚙️ Chế Độ Đóng Phiếu (Tự Động vs Thủ Công)

Hệ thống cung cấp công tắc chuyển đổi linh hoạt:

1. **Chế độ Tự Động Đóng (`Auto Close = ON`)**:
   - Khi chạy chu kỳ quét (định kỳ hoặc bấm nút Quét), hệ thống tự động kiểm tra điều kiện đóng mức 1 (Level 1 Auto-Close Candidate).
   - Nếu đủ điều kiện (Mạng lưới bình thường, cấu hình đúng), hệ thống sẽ gửi lệnh đóng phiếu lên TTS.
   - Các phiếu chưa đủ điều kiện sẽ được gán nhãn `Chưa đóng được` kèm lý do chi tiết.

2. **Chế độ Đóng Thủ Công (`Auto Close = OFF`)**:
   - Hệ thống chỉ thực hiện cào dữ liệu, đối soát Core/SAPC/BTools và phân loại nhận định.
   - Nhân viên chủ động bấm nút:
     - **Đóng Phiếu** (trên TTS Cũ): Gửi lệnh đóng riêng cho từng phiếu đã chọn.
     - **Đóng thủ công** (trên TTS Mới): Chuyển tab Chrome tới trang chi tiết phiếu (`chi-tiet-phieu-pakh`) để người dùng xem lại thông tin và xác nhận hoàn tất.

---

## 🔒 Bảo Mật & Phân Quyền Sử Dụng

> [!IMPORTANT]
> - Khi khởi chạy trên máy tính cá nhân, hệ thống sử dụng phiên đăng nhập (Cookie / Token) trên trình duyệt Chrome của chính máy tính đó.
> - **Nếu chia sẻ cho đồng nghiệp**: Khuyến nghị gửi toàn bộ thư mục cho đồng nghiệp để họ chạy file `open_dashboard.bat` trên máy của họ. Việc này đảm bảo các thao tác xử lý phiếu luôn ghi nhận đúng tài khoản và danh tính của người thực hiện.
> - Tuyệt đối không commit file `.env`, file cấu hình chứa mật khẩu hoặc database khách hàng lên kho chứa mã nguồn công khai.

---

## 📄 Bản Quyền & Phát Triển
* Được xây dựng và tối ưu bởi đội ngũ kỹ thuật VNPT.
* Giấy phép sử dụng: **MIT License**.
