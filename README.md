# VNPT TTS Precheck — Hệ Thống Tiền Kiểm & Tự Động Hóa Xử Lý Phản Ánh Khách Hàng

Hệ thống phần mềm chuyên dụng hỗ trợ Khối Kỹ thuật Viễn thông VNPT / VinaPhone tự động hóa quy trình tiền kiểm tra hạ tầng mạng, đối soát thuê bao Core, phân tích nguyên nhân sự cố và đóng phiếu phản ánh khách hàng (PAKH) trên hệ thống OneOSS TTS Mới (`tts.vnptnet.vn`) và TTS Cũ (`tts.vnpt.vn`).

---

## 1. Tổng Quan Hệ Thống

Mỗi ngày, hệ thống tiếp nhận khối lượng lớn các phản ánh từ khách hàng liên quan đến chất lượng dịch vụ di động:
* **Dịch vụ Mobile Internet (Data)**: Mất mạng, truy cập chậm, chập chờn, không load được ứng dụng (Facebook, Youtube, TikTok...), lỗi gói cước, hạ băng thông, đặc thù địa hình...
* **Dịch vụ Cuộc gọi (Voice)**: Không gọi đi/đến được, rớt cuộc gọi, nghẽn mạng, chất lượng thoại kém...
* **Dịch vụ Tin nhắn (SMS)**: Không gửi/nhận được SMS, chậm trễ tin nhắn OTP, dịch vụ GTGT...
* **Gói cước & Phản ánh khác**: Tra cứu chính sách gói cước, khiếu nại cước, lỗi roaming, chuyển mạng giữ số (MNP)...

**VNPT TTS Precheck** thay thế hoàn toàn thao tác tra cứu thủ công rời rạc trên nhiều hệ thống bằng quy trình tự động hóa tập trung:
1. **Thu thập phiếu sự cố**: Tự động đồng bộ danh sách phiếu từ OneOSS TTS Mới (qua REST API) và TTS Cũ (34 TTP), phân tách rõ ràng theo từng phân hệ dịch vụ.
2. **Tiền kiểm tra hạ tầng Core đa luồng**:
   * **BTools (`10.159.21.241`)**: Khai thác lịch sử phiên 4G/5G, lưu lượng tải, nguyên nhân ngắt phiên (Cause Code: 300, 2042, 2043, 2045...), tốc độ bóp băng thông thực tế (kbps) và phân loại RAT (2G/3G/4G/5G).
   * **SAPC Core (`10.155.42.218`)**: Tra cứu gói cước đang kích hoạt, ngày đăng ký, hạn sử dụng, trạng thái gói data thực tế.
   * **Cell Location & HSS Profile (`10.155.42.218`)**: Tra cứu trạm phát sóng (Cell ID, eNodeB, ECGI), trạng thái hồ sơ HSS, cờ khóa cước NAM (0 = mở, 1 = khóa cước), địa chỉ IP gán cho thuê bao.
   * **Hạ tầng sóng trạm CEM (`api-cem.vnptmedia.vn`)**: Phân tích chất lượng phát sóng 5 ngày gần nhất tại vị trí phản ánh, lịch sử sự cố trạm vô tuyến và thống kê Top ứng dụng tiêu thụ dữ liệu.
   * **CCOS (`gqknccos.vnpt.vn`)**: Trích xuất chi tiết nội dung khiếu nại và file đính kèm biên bản kiểm tra hiện trường.
3. **Phân tích chẩn đoán kỹ thuật**: Ứng dụng động cơ chẩn đoán theo kịch bản kỹ thuật (`scenarios_engine.py`) kết hợp mô hình AI (`ai_interpreter.py`) để đưa ra nhận định nguyên nhân sự cố và giải pháp xử lý. Hỗ trợ nhận diện các kịch bản chuyên sâu: bóp băng thông, lưu lượng yếu, phục hồi sau sự cố, và kịch bản đặc thù địa hình biển đảo.
4. **Phân định an toàn & Tự động đóng phiếu OneOSS**:
   * **Mobile Internet (Data)**: Hỗ trợ quy trình đóng tự động dứt điểm (2.3 -> 2.4 -> 2.6 -> Hoàn thành), tự động điền Lĩnh vực "Chất lượng mạng", chuẩn hóa địa bàn theo địa giới hành chính hiện hành (bao gồm các mô hình sáp nhập tỉnh/thành & đặc khu) và phân loại nguyên nhân theo danh mục chuẩn VNPT.
   * **Cuộc gọi & Tin nhắn (Voice / SMS)**: Tuân thủ nguyên tắc an toàn viễn thông, hỗ trợ chuyển bước nhanh 2.3 -> 2.4 để KTV kiểm tra thủ công, nghiêm cấm tự động điền form/comment và đóng tự động ngoài kiểm soát.

---

## 2. Kiến Trúc Phân Tầng Hệ Thống (System Architecture)

```
[ Trình duyệt KTV / Trình duyệt Chrome ]
       │
       ├── Giao diện SPA Dashboard (Port 1234)
       │     ├── Realtime WebSocket Feed & Live Logs
       │     ├── Bảng điều phối danh mục (Data, Cuộc gọi, SMS, Gói cước)
       │     ├── Sắp xếp 2 chiều theo thời gian sự cố & Chấm đỏ thông báo phiếu mới
       │     └── Drawer kiểm tra chi tiết & Modal cấu hình Auto-Close
       │
       └── Tiện ích mở rộng "VNPT Token Utilities"
             └── Tự động trích xuất & đồng bộ Session/Cookie/Bearer Token một chạm
                   ├── OneOSS TTS Mới (Bearer JWT)
                   ├── OneOSS TTS Cũ (scnntttoken, XSRF)
                   ├── SAPC Core (Cookie .AspNet.ApplicationCookie)
                   ├── BTools (JSESSIONID)
                   ├── CEM (Bearer API Key)
                   └── CCOS (SessionDB, SESSIONID)
       │
[ FastAPI Gateway Server (Port 1234) ]
       │
       ├── Routers:
       │     ├── routers/web.py          : Phục vụ SPA & Static Assets
       │     ├── routers/auth.py         : Quản lý phiên làm việc & xác thực KTV
       │     ├── routers/tickets.py      : Điều phối phiếu, API bảng, Precheck On-Demand
       │     ├── routers/automation.py   : Cấu hình quy tắc đóng tự động & điều khiển Worker
       │     ├── routers/integrations.py : Cổng tiếp nhận token & đồng bộ trạng thái ngoại vi
       │     └── routers/cdr.py          : Tra cứu nhật ký bản tin SMSC/CDR
       │
       ├── Services & Business Logic:
       │     ├── services/automation_worker.py : Luồng lập lịch quét định kỳ ngầm
       │     ├── services/tts_new_data.py      : Engine tiền kiểm Data TTS Mới (8 Workers)
       │     ├── services/tts_new_voice.py     : Engine tiền kiểm Thoại/SMS TTS Mới (8 Workers)
       │     ├── services/tts_old_api_data.py  : Engine tiền kiểm Data TTS Cũ
       │     ├── services/tts_old_api_voice.py : Engine tiền kiểm Thoại TTS Cũ
       │     ├── services/voice_precheck.py    : Tiền kiểm hồ sơ cuộc gọi & tin nhắn (NAM, HSS)
       │     ├── services/smsc_cdr_client.py   : Khai thác chi tiết bản tin SMSC & cuộc gọi CDR
       │     └── services/state.py             : Quản lý trạng thái luồng & bộ nhớ tạm
       │
       ├── Core Diagnostic Engines:
       │     ├── scenarios_engine.py     : Thuật toán nhận diện kịch bản lỗi BTools/SAPC
       │     ├── diagnostic_scenarios.json: Cấu hình ma trận kịch bản chẩn đoán
       │     ├── serviceid.json          : Từ điển gói cước & bảng mã bóp băng thông
       │     ├── ai_interpreter.py       : Bóc tách thực thể & tóm tắt phản ánh bằng AI
       │     └── report_bot.py           : Tổng hợp chứng cứ kỹ thuật & sinh mẫu kết luận
       │
       ├── Connectors & Clients:
       │     ├── ttsnew_api.py           : REST API Client OneOSS TTS Mới
       │     ├── tts_old_api.py          : REST API Client OneOSS TTS Cũ
       │     ├── btools_manager.py       : Kết nối Chrome CDP & HTTP Crawler BTools
       │     ├── sapccheck/              : Kết nối API SAPC Core & Tra cứu Cell HSS
       │     ├── cem_client.py           : Kết nối API đo kiểm vô tuyến CEM
       │     └── ccos_client.py          : Kết nối hệ thống khiếu nại CCOS
       │
       └── Persistence Layer:
             └── db_manager.py -> tickets.db (SQLite: Lưu vết phiếu, cấu hình, lịch sử tiền kiểm)
```

---

## 3. Bản Đồ Cấu Trúc Mã Nguồn

| Đường dẫn / Tên file | Trọng trách chính trong dự án |
| :--- | :--- |
| **`dashboard.py` / `main.py`** | Điểm khởi động máy chủ FastAPI, quản lý tiến trình Uvicorn (Port 1234), kết nối WebSocket realtime và các Background Workers. |
| **`db_manager.py`** | Quản lý cơ sở dữ liệu SQLite `tickets.db`: Lưu trữ phiếu, kết quả tiền kiểm, cấu hình Auto-Close, tối ưu hóa truy vấn cache. |
| **`scenarios_engine.py`** | Thuật toán lõi nhận diện kịch bản sự cố từ dữ liệu BTools: Bóp băng thông theo gói, rớt 2G/3G, treo phiên quản trị `300`/`2042`, lỗi SIM/HSS. |
| **`diagnostic_scenarios.json`** | Định nghĩa chi tiết các bước logic chẩn đoán tuần tự phục vụ phân loại nguyên nhân OneOSS. |
| **`serviceid.json`** | Từ điển định danh gói cước data VNPT, bảng đối chiếu mã bóp băng thông (`10002` .. `10014`) và tốc độ tương ứng (kbps). |
| **`incident_causes_ttsnew.json`** | Danh mục mã nguyên nhân sự cố đóng phiếu chuẩn hóa cho hệ thống OneOSS TTS Mới. |
| **`incident_causes_catalog.json`** | Danh mục ánh xạ nguyên nhân đóng phiếu cho hệ thống OneOSS TTS Cũ (34 TTP). |
| **`report_bot.py`** | Tổng hợp chứng cứ kỹ thuật từ BTools, SAPC, CEM; nhận diện đặc thù địa hình biển đảo, tính lưu lượng tích lũy và sinh nội dung kết luận xử lý kỹ thuật. |
| **`ai_interpreter.py`** | Bóc tách thực thể tự nhiên (NLP) và tóm tắt nội dung phản ánh khách hàng bằng AI hoặc Fuzzy Matcher offline. |
| **`ttsnew_api.py`** | Khai thác REST API của hệ thống OneOSS TTS Mới: Tìm kiếm phiếu, nhận phiếu, chuyển bước 2.3/2.4/2.6 và hoàn tất phiếu. |
| **`tts_old_api.py`** | Khai thác API hệ thống TTS Cũ (34 Tỉnh/Thành phố): Lấy danh sách phiếu và cập nhật kết quả xử lý. |
| **`btools_manager.py`** | Kết nối Chrome Remote Debugging (cổng 9222), trích xuất cookie và thực hiện cào ngầm dữ liệu phiên BTools qua HTTP. |
| **`cem_client.py`** | Giao tiếp API CEM: Đánh giá chất lượng sóng trạm vô tuyến 5 ngày gần nhất và trích xuất Top ứng dụng sử dụng. |
| **`ccos_client.py`** | Khai thác API CCOS: Tra cứu thông tin phản ánh ban đầu và tải file đính kèm biên bản khảo sát hiện trường. |
| **`sapccheck/`** | Phân hệ kết nối Core SAPC (`10.155.42.218`): Tra cứu gói cước, cờ NAM, Radio phục vụ, địa chỉ IP và HSS Profile. |
| **`routers/`** | Phân tầng Router FastAPI: Phân chia rõ ràng giữa giao diện web (`web.py`), điều khiển tự động hóa (`automation.py`), API phiếu (`tickets.py`), xác thực (`auth.py`), tích hợp token (`integrations.py`) và nhật ký cước CDR (`cdr.py`). |
| **`services/`** | Các worker nền: Điều phối chu kỳ quét đa luồng (`automation_worker.py`), xử lý tiền kiểm song song Data TTS Mới/Cũ (`tts_new_data.py`, `tts_old_api_data.py`), tiền kiểm Thoại/SMS (`tts_new_voice.py`, `tts_old_api_voice.py`, `voice_precheck.py`). |
| **`templates/dashboard.html`** | Giao diện điều hành tập trung Single Page Application (SPA), tích hợp điều khiển và hiển thị thời gian thực. |
| **`static/css/dashboard.css`** | Thiết kế phong cách VNPT hiện đại: Chuẩn nhận diện viễn thông chuyên nghiệp, tối ưu không gian hiển thị thông tin kỹ thuật. |
| **`static/js/dashboard.js`** | Xử lý logic phía client: WebSocket realtime feed, bộ lọc động, bảng dữ liệu, sắp xếp 2 chiều, drawer chi tiết và modal xử lý. |

---

## 4. Cơ Chế Xử Lý Đa Luồng & Tối Ưu Tốc Độ (High-Concurrency Engine)

Hệ thống được thiết kế tối ưu hóa tốc độ xử lý I/O Network thông qua mô hình đa luồng và cơ chế điều phối tài nguyên thông minh:

### 4.1. Đa luồng cấp danh sách (Batch-Level Concurrency)
* **Mobile Internet (Data)**: Sử dụng `ThreadPoolExecutor(max_workers=8)` để xử lý đồng thời **8 thuê bao cùng lúc**.
* **Cuộc gọi & Tin nhắn (Voice / SMS)**: Sử dụng `ThreadPoolExecutor(max_workers=8)` để xử lý song song danh sách phiếu thoại, giảm thời gian tiền kiểm toàn bộ danh sách 30 - 40 phiếu xuống dưới 10 giây.
* **Tái sử dụng kết quả DB thông minh (DB Cache Reuse)**: Đối với các thuê bao đã có kết quả tiền kiểm hợp lệ trong chu kỳ gần nhất và không có yêu cầu ép quét lại (`force_recheck=False`), hệ thống tái sử dụng ngay kết quả từ SQLite trong **0.01 giây**, chỉ tập trung tài nguyên mạng vào các phiếu mới phát sinh.

### 4.2. Đa luồng song song nội bộ từng thuê bao (Intra-Ticket Concurrency)
Khi KTV kích hoạt tiền kiểm tra 1 số thuê bao data cụ thể, hệ thống kích hoạt đồng thời 3 luồng con:
* **Luồng 1 (Core SAPC & HSS)**: Truy vấn gói cước SAPC và thông tin trạm phát sóng Cell ID / cờ NAM.
* **Luồng 2 (BTools)**: Cào lịch sử phiên truy cập dữ liệu 5 ngày qua HTTP.
* **Luồng 3 (CEM)**: Truy vấn chất lượng sóng trạm vô tuyến 5 ngày và Top ứng dụng.

Tổng thời gian tiền kiểm 1 thuê bao rút ngắn từ **5 - 8 giây xuống chỉ còn 1 - 1.5 giây** (tương đương thời gian của luồng mạng đơn lẻ dài nhất).

### 4.3. Cơ chế Bypass thông minh cho phiếu phi-Data (Non-Data Bypass Strategy)
* Đối với các phản ánh thuộc nhóm Cuộc gọi, SMS, Chuyển mạng giữ số (MNP)... hệ thống **tự động bypass hoàn toàn** việc cào BTools (phiên dữ liệu 4G/5G) và sóng trạm CEM vô tuyến.
* Quá trình tiền kiểm chỉ tập trung kiểm tra Core HSS, cờ NAM và hồ sơ CCOS. Nhờ đó, thời gian tiền kiểm giảm hơn 90% (từ 5 - 8 giây xuống dưới 1 giây/phiếu), giải phóng tối đa băng thông và giữ phiên Chrome Debugger BTools luôn thông suốt cho các phiếu Mobile Internet.

### 4.4. Tối ưu hóa truy vấn Database & Bộ nhớ đệm (DB Query Acceleration)
* Đánh chỉ mục (index) chuyên biệt trên bảng `tickets` theo mã phiếu, số thuê bao và mốc thời gian.
* Loại bỏ các truy vấn full-table scan dư thừa, trả kết quả bảng điều phối hàng trăm phiếu gần như tức thì (< 50ms).

---

## 5. Quy Trình Tiền Kiểm & Tự Động Đóng Phiếu (End-to-End Pipeline)

### 5.1. Tiền kiểm tra Mobile Internet
1. **Lấy danh sách phiếu**: Lọc theo điều kiện bước xử lý (2.3 Xử lý PAKH hoặc 2.4 Đánh giá kết quả).
2. **Khai thác BTools**: Lấy toàn bộ phiên data trong 5 ngày. Phân tích lưu lượng tải lên/xuống, loại sóng (4G/3G/2G), mã kết thúc phiên (Cause Code: 300, 2042, 2043, 2045...).
3. **Đối soát SAPC**: Kiểm tra thuê bao có gói cước data không, còn hạn sử dụng hay đã hết dung lượng tốc độ cao và bị hạ băng thông về mã bóp tương ứng (`10002` .. `10014`).
4. **Đối soát CEM**: Xác định trạm phát sóng phục vụ, tỷ lệ bắt sóng trên từng cell, cảnh báo nếu thiết bị bật VPN hoặc trạm có sự cố nghẽn. (Loại trừ Cloudflare 1.1.1.1 khỏi cảnh báo VPN lỗi).
5. **Đưa ra nhận định kỹ thuật**: Phân loại theo các kịch bản chuẩn:
   * **Bóp băng thông theo chính sách gói cước**: Nhận diện chính xác tốc độ bóp theo gói data đang hoạt động.
   * **Hoạt động bình thường sau thời điểm sự cố**: Phân tích mốc thời gian từ ngày bắt đầu phát sinh sự cố đến nay; kiểm tra lưu lượng tích lũy sau sự cố (phiên > 10MB hoặc tổng tích lũy >= 30MB) để khẳng định khách hàng đã dùng được dịch vụ bình thường.
   * **Đặc thù địa hình biển đảo**: Nhận diện các đặc khu/địa bàn hải đảo (Phú Quốc, Côn Đảo...), đánh giá khoảng cách trạm xa và suy hao môi trường biển; sinh nhận định kỹ thuật chuẩn xác và đề xuất hướng dẫn giải thích phù hợp cho điện thoại viên.
   * **Lưu lượng yếu / Tập trung 1 trạm phục vụ**: Cảnh báo trạm suy hao hoặc nghẽn cục bộ.
   * **Không phát sinh lưu lượng data trong thời gian phản ánh**.
   * **Treo phiên kết nối quản trị (Code 300 / 2042 / 2043 / 2045)**.
   * **Khóa cước chiều GPRS (Cờ NAM = 1)**.

### 5.2. Tiền kiểm tra Cuộc gọi & Tin nhắn
1. **Lấy danh sách phiếu**: Lọc các phản ánh thuộc nhóm Thoại, SMS, Chuyển mạng giữ số (MNP)...
2. **Kiểm tra trạng thái Core**: Kiểm tra cờ NAM, hồ sơ HSS, địa chỉ trạm VLR/MME phục vụ gần nhất.
3. **Tra cứu CCOS**: Trích xuất nội dung khiếu nại chi tiết, đối chiếu số thuê bao chủ gọi / bị gọi và tải file biên bản hiện trường nếu có.
4. **Quy tắc an toàn viễn thông bắt buộc**:
   * Nghiêm cấm tuyệt đối tự động điền form, comment kết luận và đóng tự động ngoài kiểm soát đối với phiếu Thoại/SMS.
   * Cung cấp nút thao tác **Chuyển 2.4** nhanh để KTV đưa phiếu sang bước đánh giá và trực tiếp thẩm định.

### 5.3. Chuỗi đóng phiếu tự động OneOSS (Auto-Close Pipeline)
Khi bật chế độ **Đóng tự động (`Auto-Close = ON`)** cho phân hệ Mobile Internet, hệ thống thực hiện đóng dứt điểm theo quy trình:
* **Phiếu ở bước 2.3**: Tự động chuyển bước sang 2.4.
* **Phiếu ở bước 2.4**: Tự động chuyển tiếp sang bước 2.6 (hoặc hoàn tất theo cấu hình quy trình).
* **Phiếu ở bước 2.6**: Tự động hoàn tất đóng phiếu với:
  * Điền nội dung kết luận xử lý kỹ thuật chuẩn hóa.
  * Tự động chọn Lĩnh vực: **Chất lượng mạng**.
  * Tự động xác định địa bàn xử lý: Tỉnh/TP, Quận/Huyện, Phường/Xã từ thông tin trạm phát sóng hoặc dữ liệu phản ánh, tuân thủ tuyệt đối cấu trúc địa giới hành chính hiện hành (bao gồm các mô hình sáp nhập tỉnh/thành & đặc khu).
  * Chọn đúng mã nguyên nhân đóng phiếu theo danh mục quy định của VNPT.

---

## 6. Hướng Dẫn Cài Đặt & Vận Hành

### 6.1. Yêu cầu môi trường
* **Hệ điều hành**: Microsoft Windows 10 / 11 (64-bit).
* **Python**: Phiên bản 3.10 trở lên.
* **Google Chrome**: Phiên bản chính thức mới nhất.

### 6.2. Cài đặt các thư viện phụ thuộc
Mở Command Prompt hoặc PowerShell tại thư mục dự án và chạy:
```bash
pip install -r requirements.txt
```
*(Các thư viện chính bao gồm: `fastapi`, `uvicorn`, `requests`, `selenium`, `websockets`, `openpyxl`, `rapidfuzz`, `google-generativeai`, `python-dotenv`)*

### 6.3. Cài đặt tiện ích mở rộng Chrome (VNPT Token Utilities)
1. Mở Google Chrome, truy cập địa chỉ: `chrome://extensions/`.
2. Bật công tắc **Chế độ dành cho nhà phát triển (Developer mode)** ở góc trên bên phải.
3. Bấm nút **Tải tiện ích đã giải nén (Load unpacked)** và chọn thư mục tiện ích:
   * Thư mục tiện ích chung: `python/VNPT_Token_Utilities` (hoặc thư mục `extension_precheck` đi kèm dự án).
4. Tiện ích sẽ xuất hiện trên thanh công cụ trình duyệt. Bấm nút **Sync All Now** để tự động đồng bộ toàn bộ Session, Cookie và Token của các hệ thống nội bộ (TTS, BTools, SAPC, CEM, CCOS) sang Port 1234.

### 6.4. Khởi chạy hệ thống
Nhấp đúp chuột vào file batch:
```bash
open_dashboard.bat
```
Tập lệnh sẽ tự động:
1. Mở Chrome ở chế độ Remote Debugging trên cổng `9222`.
2. Khởi chạy Web Server FastAPI trên cổng `1234`.
3. Tự động mở giao diện Dashboard tại địa chỉ: `http://localhost:1234`.

*(Để dừng toàn bộ hệ thống khi kết thúc ca làm việc: Chạy file `stop_dashboard.bat`)*

---

## 7. Cấu Hình & Chế Độ Hoạt Động

### 7.1. Chế độ Đóng thủ công (An toàn / Kiểm thử)
* Mặc định khi khởi động, chế độ Auto-Close ở trạng thái **OFF**.
* KTV sử dụng Dashboard để giám sát toàn bộ quá trình tiền kiểm tự động, xem trước kết luận phân tích và hồ sơ Core của từng thuê bao.
* Khi muốn đóng phiếu nào, KTV bấm nút **Đóng phiếu** hoặc **Mở chi tiết** trên dòng tương ứng để kiểm tra và xác nhận đóng.

### 7.2. Chế độ Đóng tự động (Auto-Close Pipeline)
* KTV mở menu **Cấu hình Đóng tự động** trên thanh công cụ Dashboard.
* Bật công tắc Auto-Close cho phân hệ Mobile Internet.
* Thiết lập các điều kiện an toàn:
  * Chỉ đóng tự động các phiếu có kết quả tiền kiểm là *Mạng lưới đảm bảo*, *Bóp băng thông theo gói*, hoặc *Hoạt động bình thường*.
  * Loại trừ các thuê bao VIP hoặc các phiếu phản ánh mở lại nhiều lần (Reopened tickets) để KTV kiểm tra thủ công.

### 7.3. Tiện ích Thao tác & Giám sát trên Dashboard (KTV Usability)
* **Chấm đỏ thông báo phiếu mới (Pulsing Red Dot)**: Đặt ngay cạnh mã phiếu khi phát hiện phiếu mới đổ về từ OneOSS. KTV có thể nhấp chuột trực tiếp vào chấm đỏ để đánh dấu đã xem / xóa thông báo tức thì.
* **Sắp xếp 2 chiều linh hoạt (2-Way Sort)**: Cho phép nhấp vào tiêu đề cột "Thời gian sự cố" để đảo chiều sắp xếp (mới nhất <-> cũ nhất), hỗ trợ ưu tiên xử lý các phản ánh cấp thiết.
* **Chuyển đổi phân hệ nhanh chóng**: Bộ lọc tab riêng biệt cho Mobile Internet, Cuộc gọi, Tin nhắn, Gói cước với bộ đếm số lượng thời gian thực.
* **Drawer chi tiết toàn diện**: Khảo sát nhanh toàn bộ lịch sử 5 ngày phiên BTools, dữ liệu sóng trạm CEM, hồ sơ SAPC và nội dung kết luận kỹ thuật ngay trên cùng một màn hình.

---

## 8. Nguyên Tắc Bảo Mật, An Toàn Dữ Liệu & Quy Chuẩn Nghiệp Vụ

* **Xác thực phiên làm việc cá nhân**: Mọi yêu cầu tương tác và đóng phiếu lên OneOSS đều sử dụng chính phiên đăng nhập (JWT Token / Session Cookie) của KTV đang mở trên trình duyệt của máy trạm. Các thao tác trên hệ thống luôn gắn liền với danh tính và quyền hạn thực tế của KTV.
* **Bảo mật thông tin khách hàng**: Cơ sở dữ liệu SQLite `tickets.db`, dữ liệu cào tạm thời (`number/`, `output/`, `cem/`) và các file cache token đều được loại trừ trong `.gitignore`, tuyệt đối không commit lên kho lưu trữ mã nguồn công khai.
* **Cơ chế Dry-Run & Chống đóng nhầm**: Lệnh đóng phiếu tự động chỉ kích hoạt khi thỏa mãn đầy đủ ma trận điều kiện kỹ thuật đã được KTV phê duyệt cấu hình.
* **Quy chuẩn địa giới hành chính (Sáp nhập tỉnh/thành & Đặc khu - BẮT BUỘC)**:
  * Hệ thống và thuật toán phân tích tuân thủ tuyệt đối các quyết định sáp nhập / điều chỉnh địa giới hành chính mới của Việt Nam (bao gồm các mô hình Đặc khu, sáp nhập tỉnh/thành như Đặc khu Phú Quốc thuộc tỉnh An Giang, v.v.).
  * Tuyệt đối không coi việc ghi nhận địa danh/tỉnh thành mới là lỗi nhập liệu hay nhầm lẫn của điện thoại viên.
* **Quy chuẩn giao diện viễn thông chuyên nghiệp (Enterprise Standard)**:
  * Giao diện phục vụ khối Kỹ thuật Viễn thông VNPT, yêu cầu tính chuyên nghiệp, trang trọng, chỉn chu và tối giản chuẩn doanh nghiệp.
  * Nghiêm cấm sử dụng các emoji/icon cảm xúc vô nghĩa trong nhãn, nút bấm, ô chọn select, tiêu đề, bảng hay modal thông báo. Toàn bộ hệ thống sử dụng tiếng Việt kỹ thuật chuẩn mực và icon chức năng SVG sắc nét.

---

## 9. Bản Quyền & Hỗ Trợ Kỹ Thuật

* **Đơn vị phát triển**: Khối Kỹ thuật Viễn thông VNPT / VinaPhone.
* **Bảo trì & Tối ưu hóa**: Đội ngũ Quản trị Hệ thống & Tự động hóa Kỹ thuật.
* **Giấy phép**: Lưu hành nội bộ phục vụ sản xuất kinh doanh VNPT.
