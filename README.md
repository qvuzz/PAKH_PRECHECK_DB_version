# 🛡️ PAKH Precheck — Hệ thống Phân tích Sự cố Mạng VNPT

> **Tự động hóa quy trình kiểm tra, phân tích và báo cáo sự cố mạng di động Vinaphone/VNPT**
> Kết hợp Selenium crawling + Rule-based Engine + Groq AI (Qwen 3.6 27B reasoning model) + Auto Update TTS

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Groq AI](https://img.shields.io/badge/AI-Groq%20%7C%20Qwen3.6--27B-orange)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 📋 Tổng quan

**PAKH Precheck** là công cụ nội bộ tự động hóa toàn bộ pipeline xử lý phiếu sự cố mạng di động, từ việc **cào dữ liệu thực tế** từ hệ thống VNPT TTS & BTools, **phân tích kỹ thuật**, **xuất báo cáo Excel màu**, đến **tự động điền kết quả và đóng phiếu trên hệ thống TTS**.

### ✨ Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 🕷️ **Auto Crawler** | Tự động cào danh sách vé sự cố từ VNPT TTS qua Selenium |
| 📡 **BTools Integration** | Trích xuất dữ liệu kỹ thuật (RAT, Downlink, Service ID) theo thuê bao |
| 🧠 **Rule Engine** | 6 kịch bản chuẩn đoán lỗi mạng (4G yếu, bóp BW, VPN, treo gói...) |
| 🤖 **Groq AI** | Tóm tắt thông minh nội dung phản ánh KH bằng Qwen3.6-27B |
| 🔌 **Offline Fallback** | Tự động lùi về thuật toán NLP + Fuzzy Match khi không có API |
| 📊 **Excel Report** | Xuất báo cáo màu tự động, phân loại trạng thái từng thuê bao |
| 🔄 **Update TTS Auto** | Tự động đọc file Excel kết quả, khớp nguyên nhân và cập nhật/đóng phiếu TTS |
| 🌐 **SAPC Check** | Tra cứu thông tin thuê bao, gói cước và policy từ SAPC API |

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│              (Pipeline điều phối chính)                 │
└────────┬────────────┬────────────┬───────────────────────┘
         │            │            │
    ┌────▼────┐  ┌────▼────┐  ┌───▼──────────────────┐
    │crawler  │  │crawler  │  │    ai_interpreter.py  │
    │_tts.py  │  │_btools  │  │  ┌──────────────────┐ │
    │(VNPT    │  │.py      │  │  │ Groq AI (Online) │ │
    │ TTS)    │  │(BTools) │  │  │ qwen/qwen3.6-27b │ │
    └────┬────┘  └────┬────┘  │  └────────┬─────────┘ │
         │            │       │           │ Fallback   │
    ┌────▼────────────▼────┐  │  ┌────────▼─────────┐ │
    │   data_processor.py  │  │  │ Offline NLP      │ │
    │  (Chuẩn hóa JSON)    │  │  │ + Fuzzy Match    │ │
    └────────────┬─────────┘  │  └──────────────────┘ │
                 │            └──────────────────────────┘
    ┌────────────▼─────────────────────────────────────┐
    │              report_bot.py                        │
    │  scenarios_engine.py (6 kịch bản chuẩn đoán)     │
    │           → Excel Report (.xlsx)                  │
    └────────────────────┬──────────────────────────────┘
                         │
    ┌────────────────────▼──────────────────────────────┐
    │                update_tts/                        │
    │  Tự động cập nhật + đóng phiếu trên VNPT TTS      │
    └───────────────────────────────────────────────────┘
```

---

## 📁 Cấu trúc thư mục

```
pakh-precheck/
├── main.py                    # Pipeline chính, điều phối toàn bộ luồng
├── crawler_tts.py             # Crawl danh sách vé từ VNPT TTS (Selenium)
├── crawler_btools.py          # Cào dữ liệu kỹ thuật từ BTools
├── data_processor.py          # Chuẩn hóa và làm sạch dữ liệu BTools
├── ai_interpreter.py          # Tóm tắt phản ánh KH (Groq AI + Offline)
├── ai_cache.py                # Quản lý cache kết quả AI tóm tắt
├── ai_cache.json              # File lưu cache kết quả AI
├── report_bot.py              # Phân tích trạng thái + xuất Excel
├── scenarios_engine.py        # Engine 6 kịch bản chuẩn đoán lỗi mạng
├── refresh_chrome.py          # Tự động dọn dẹp và khởi động lại Chrome Debug
├── update_tts/                # Module tự động cập nhật & đóng phiếu TTS
│   ├── run.py                 # Script điều phối chính cho update_tts
│   ├── excel_reader.py        # Đọc dữ liệu báo cáo Excel & lọc phiếu đóng tự động
│   ├── ticket_actions.py      # Thao tác Selenium điền form & bấm đóng phiếu
│   ├── config.py              # Mapping trạng thái Excel -> Nguyên nhân sự cố TTS
│   └── pagination.py          # Xử lý chuyển trang danh sách phiếu TTS
├── sapccheck/                 # Module tra cứu SAPC API / Policy
│   ├── sapccheck.py           # Phân tích & hiển thị thông tin gói SAPC
│   └── sapc_client.py         # Kết nối SOAP/HTTP SAPC
├── diagnostic_scenarios.json  # Cấu hình kịch bản và mô tả hành động
├── diagnostic_config.json     # Mã gói hệ thống loại trừ
├── serviceid.json             # Ánh xạ Service ID → Tên dịch vụ
├── nguyennhansuco.json        # Danh mục nguyên nhân sự cố
├── n8n.ps1                    # Script tự động hóa với n8n workflow
├── open_chrome.bat            # Mở Chrome ở debug port 9222
├── .env.example               # Mẫu biến môi trường (copy thành .env)
├── .gitignore
└── README.md
```

---

## ⚙️ Cài đặt và Chạy

### 1. Yêu cầu hệ thống

- Python **3.10+**
- Google Chrome + ChromeDriver (phải khớp phiên bản)
- Tài khoản Groq AI (miễn phí tại [console.groq.com](https://console.groq.com))

### 2. Cài đặt dependencies

```bash
pip install selenium groq python-dotenv openpyxl rapidfuzz requests
```

### 3. Cấu hình biến môi trường

Tạo file `.env` từ mẫu:

```bash
cp .env.example .env
```

Chỉnh sửa `.env`:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=qwen/qwen3.6-27b
```

### 4. Cấu hình đường dẫn ChromeDriver

Mở `main.py` và sửa dòng:

```python
CHROMEDRIVER_PATH = r"C:\chromedriver\chromedriver.exe"
```

> 📥 Tải ChromeDriver tại: https://googlechromelabs.github.io/chrome-for-testing/

### 5. Khởi động Chrome ở Debug Mode

```bash
# Chạy file batch có sẵn
open_chrome.bat
```

Hoặc sử dụng script Python refresh Chrome:

```bash
python refresh_chrome.py
```

### 6. Chạy chương trình chính (Phân tích & Xuất Excel)

```bash
python main.py
```

### 7. Tự động Cập nhật & Đóng phiếu trên VNPT TTS

Sau khi kiểm tra file Excel kết quả, chạy lệnh sau để tự động điền form và đóng các phiếu đủ điều kiện:

```bash
python -m update_tts.run
```

---

## 🧠 Groq AI — Cơ chế tóm tắt thông minh

Hệ thống sử dụng model **`qwen/qwen3.6-27b`** (reasoning model của Alibaba Cloud chạy trên hạ tầng Groq) để trích xuất 6 trường thông tin từ nội dung phản ánh KH:

```
1. Gói cước sử dụng
2. Tình trạng truy cập
3. Tình trạng dung lượng
4. Thiết bị sử dụng
5. Khu vực xảy ra lỗi
6. Tóm tắt hành động đã thử
```

**Fallback tự động**: Nếu không có API key hoặc gặp lỗi rate-limit, hệ thống tự chuyển sang chế độ **Offline** dùng Regex + Fuzzy Matching (rapidfuzz) — không phụ thuộc internet.

---

## 📊 Các kịch bản chuẩn đoán lỗi & Tự động đóng phiếu

| Mã kịch bản | Tên | Điều kiện kỹ thuật | Cơ chế tự động đóng TTS |
|-------------|-----|--------------------|-------------------------|
| `KC_01_NO_4G` | Không bắt được sóng 4G | RAT chỉ có 0/1/2 (2G/3G) | 🟢 Đóng tự động |
| `KC_02_WEAK_4G` | Bắt sóng 4G kém | Tỷ lệ RAT 4G thấp hơn 2G/3G | 🟢 Đóng tự động |
| `KC_03_THROTTLED` | Bóp băng thông | Service ID `0000010002` xuất hiện | 🟢 Đóng tự động |
| `KC_04_PACKAGE_OR_DEVICE_HANG` | Treo gói / Thiết bị treo | Chỉ có mã hệ thống rỗng 3 ngày | 🟡 Cần kiểm tra thêm |
| `KC_05_LOW_DOWNLINK_BURST` | Sóng chập chờn, mật độ phiên cao | ≥70% phiên RAT thấp trong ≥3 phiên | 🟡 Cần kiểm tra thêm |
| `KC_06_VPN_OR_DEVICE_ISSUE` | Nghi vấn VPN / lỗi thiết bị | Downlink bị chặn 5-10MB đều nhau | 🟡 Cần kiểm tra thêm |
| `KC_07_NO_4G_PROFILE` | Chưa khai báo Profile 4G | Thiếu profile HSS 4G | 🟢 Đóng tự động |
| `NORMAL` | Hoạt động bình thường | Mạng lưới đảm bảo | 🟢 Đóng tự động (nếu khớp phản ánh) |

---

## 📈 Output

Sau khi chạy xong, file Excel được tự động lưu và mở tại:

```
result/Bao_Cao_Su_Co_Mang_YYYYMMDD.xlsx
```

Mỗi hàng là 1 thuê bao, có màu theo trạng thái:
- 🟢 **Xanh lá** — Bình thường / Tín hiệu ổn
- 🟡 **Vàng** — Cần kiểm tra thêm
- 🔴 **Đỏ** — Lỗi nghiêm trọng / Cần can thiệp ngay
- ⬜ **Trắng** — Chưa phân loại

---

## 🔒 Bảo mật

> ⚠️ **QUAN TRỌNG**: File `.env` chứa API key **đã được thêm vào `.gitignore`** và sẽ không bao giờ được commit lên GitHub.

Chỉ commit file `.env.example` (không chứa key thật) để làm mẫu cho người dùng mới.

---

## 📄 License

MIT License

---

*Được phát triển bởi [@qvuzz](https://github.com/qvuzz) · VNPT khu vực*

