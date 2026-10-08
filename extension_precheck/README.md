# VNPT Token Utilities - Chrome Extension

Bo tien ich mo rong (Chrome Extension) chuyen biet danh rieng cho mang ky thuat vien va ky su VNPT, giup tu dong thu thap, duy tri va dong bo hoa Session, Cookie va Bearer Token giua trinh duyet va cac ung dung web noi bo.

---

## 1. Cac Dich Vu VNPT Duoc Ho Tro
- **CTS (MBB QoS Tap Doan)** (`cts.vnpt.vn`): Tu dong quet Cookie `.AspNetCore.Cookies`.
- **PMS (3G & 5G Vo Tuyen)** (`pms.vnpt.vn`): Tu dong quet `sessionid` va `csrftoken`.
- **OneOSS / NPMRAN 4G** (`oneoss.vnpt.vn`): Tu dong quet Bearer JWT Token tu LocalStorage.
- **TTS Moi (OneOSS PAKH)** (`tts.vnptnet.vn`): Tu dong quet Bearer JWT Token tu LocalStorage.
- **TTS Cu (34 TTP)** (`tts.vnpt.vn`): Tu dong trich xuat `scnntttoken`.
- **CCOS (Khieu Nai KH)** (`gqknccos.vnpt.vn`): Tu dong quet `SessionDB` va `SESSIONID`.
- **BTools (Phan Tich TB)** (`10.159.21.241`): Tu dong quet `JSESSIONID`.

---

## 2. Cac Cong May Chu Noi Bo Nhan Du Lieu (Multi-Port Dispatcher)
- **Port 710 (`kpi_assistant`)**: Nhan CTS, PMS, OneOSS, TTS Moi.
- **Port 9190 (`Report Tool`)**: Nhan CCOS, TTS Cu, TTS Moi, PMS, CTS.
- **Port 1234 (`PAKH Precheck`)**: Nhan CCOS, TTS Cu, TTS Moi, BTools.

---

## 3. Huong Dan Cai Dat Vao Google Chrome
1. Mo Google Chrome, truy cap: `chrome://extensions/`
2. Bat cong tac **Developer mode** (Che do nha phat trien) o goc tren ben phai.
3. Bam vao nut **Load unpacked** (Tai tien ich da giai nen).
4. Chon thu muc:
   `C:\Users\lequa\OneDrive - VNPT\python\VNPT_Token_Utilities`
5. Ghim (Pin) tien ich **VNPT Token Utilities** len thanh cong cu Chrome.

---

## 4. Huong Dan Su Dung
- Mo cac trang web dich vu VNPT (OneOSS, PMS, CTS, CCOS...).
- Tien ich se **tu dong cào ngam 100%** va ban du lieu sang cac port 710, 9190, 1234 khi dang bat.
- Neu can bat buoc lam moi token, click vao icon tien ich va bam nut **"Dong Bo Lai Toan Bo"** hoac **"Xoa Cache & Bat Token Moi"**.
