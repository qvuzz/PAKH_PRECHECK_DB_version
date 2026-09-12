# tts_old_api.py
# Module tích hợp REST API cho hệ thống TTS Cũ (tts.vnpt.vn/WS/api)

import os
import json
import time
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOKEN_CACHE_FILE = BASE_DIR / "tts_old_token_cache.json"

API_BASE_URL = "https://tts.vnpt.vn/WS/api"

DATA_SERVICE_KEYWORDS = [
    "mobile internet",
]


def save_cached_auth(token: str, user_info: dict = None):
    """Lưu token và user_info vào file cache để tái sử dụng."""
    try:
        data = {
            "token": token,
            "user_info": user_info or {},
            "updated_at": time.time()
        }
        with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_cached_auth() -> tuple:
    """Đọc token và user_info từ file cache hoặc lan_sessions.json nếu còn hiệu lực."""
    # 1. Đọc từ file cache chính
    if TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                tok = (data.get("token") or "").strip()
                if tok:
                    return tok, data.get("user_info", {})
        except Exception:
            pass

    # 2. Fallback: Đọc từ lan_sessions.json
    lan_file = BASE_DIR / "lan_sessions.json"
    if lan_file.exists():
        try:
            with open(lan_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)
            sorted_sessions = sorted(
                sessions.values(),
                key=lambda s: s.get("timestamp", 0),
                reverse=True
            )
            for s in sorted_sessions:
                tok = (s.get("token") or "").strip()
                if tok:
                    usr = s.get("user", {})
                    save_cached_auth(tok, usr)
                    return tok, usr
        except Exception:
            pass

    return "", {}


def _decode_user_str(user_str: str) -> dict:
    if not user_str:
        return {}
    try:
        data = json.loads(user_str)
    except Exception:
        try:
            import base64
            decoded = base64.b64decode(user_str).decode("utf-8", errors="ignore")
            data = json.loads(decoded)
        except Exception:
            return {}
    if isinstance(data, dict):
        if "userInfo" in data and isinstance(data["userInfo"], dict):
            return data["userInfo"]
        return data
    return {}


def _extract_tts_old_via_cdp_ws(port: int = 9222):
    """Trích xuất token & user_info từ tab tts.vnpt.vn qua CDP WebSocket hoàn toàn ngầm."""
    try:
        import urllib.request, json, asyncio, websockets
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as r:
            tabs = json.loads(r.read().decode("utf-8"))
        ws_url = None
        for t in tabs:
            if "tts.vnpt.vn" in t.get("url", "").lower():
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            return "", {}

        async def _query():
            async with websockets.connect(ws_url) as ws:
                msg1 = {"id": 1, "method": "Runtime.evaluate", "params": {"expression": "localStorage.getItem('scnntttoken')"}}
                await ws.send(json.dumps(msg1))
                res1 = json.loads(await ws.recv())
                token = res1.get("result", {}).get("result", {}).get("value") or ""

                msg2 = {"id": 2, "method": "Runtime.evaluate", "params": {"expression": "localStorage.getItem('userInfo')"}}
                await ws.send(json.dumps(msg2))
                res2 = json.loads(await ws.recv())
                user_str = res2.get("result", {}).get("result", {}).get("value") or ""
                user_info = _decode_user_str(user_str) if user_str else {}
                return token, user_info

        return asyncio.run(_query())
    except Exception:
        return "", {}


def extract_token_from_browser(driver=None) -> tuple:
    """
    Trích xuất token và thông tin user từ trình duyệt Chrome (tab tts.vnpt.vn) 100% ngầm.
    Tuyệt đối không dùng driver.switch_to.window() để không làm gián đoạn người dùng.
    """
    token = ""
    user_info = {}

    # 1. Thử lấy ngầm siêu tốc qua CDP WebSocket (0 tab switch)
    token, user_info = _extract_tts_old_via_cdp_ws()

    # 2. Nếu chưa có, kết nối qua Playwright CDP tới port 9222 (không chuyển tab)
    if not token:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                pages = browser.contexts[0].pages
                for page in pages:
                    if "tts.vnpt.vn" in page.url.lower():
                        token = page.evaluate("() => localStorage.getItem('scnntttoken')")
                        user_str = page.evaluate("() => localStorage.getItem('userInfo')")
                        if user_str:
                            user_info = _decode_user_str(user_str)
                        if token:
                            break
                browser.close()
        except Exception:
            pass

    # 2.5 Nếu chưa có, trích xuất từ Firefox (nếu người dùng đăng nhập trên Firefox)
    if not token:
        try:
            from auth_extractor import extract_firefox_local_storage
            tok_ff = extract_firefox_local_storage("tts.vnpt.vn", "scnntttoken")
            user_str_ff = extract_firefox_local_storage("tts.vnpt.vn", "userInfo")
            if tok_ff:
                token = tok_ff
                if user_str_ff:
                    user_info = _decode_user_str(user_str_ff)
        except Exception:
            pass

    # 3. Fallback qua Selenium driver NẾU tab hiện tại đã là tts.vnpt.vn (không switch window)
    if not token and driver:
        try:
            if "tts.vnpt.vn" in driver.current_url.lower():
                token = driver.execute_script("return localStorage.getItem('scnntttoken');")
                user_str = driver.execute_script("return localStorage.getItem('userInfo');")
                if user_str:
                    user_info = _decode_user_str(user_str)
        except Exception:
            pass

    # 4. Fallback về cache nếu không lấy được từ browser
    if not token:
        token, cached_user = get_cached_auth()
        if not user_info:
            user_info = cached_user

    if token:
        save_cached_auth(token, user_info)

    return token, user_info


def get_request_headers(token: str) -> dict:
    """Tạo headers chuẩn cho các lệnh gọi REST API TTS Cũ."""
    auth_header = token if token.startswith("Bearer ") else ("Bearer " + token)
    return {
        "Authorization": auth_header,
        "Content-Type": "application/json;charset=utf-8",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }


def fetch_nguyen_nhan_list_api(token: str) -> dict:
    """
    Lấy danh mục nguyên nhân đóng sự cố từ TTS Cũ.
    Trả về dict ánh xạ {tên_nguyên_nhân: Id}.
    """
    url = f"{API_BASE_URL}/DM_NguyenNhanSuCo/PaginationDMNguyenNhanSuCo?offset=0&pagesize=1000&keyword="
    headers = get_request_headers(token)
    mapping = {}
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                ten = str(item.get("Ten") or "").strip()
                id_val = item.get("Id")
                if ten and id_val is not None:
                    id_int = int(id_val)
                    mapping[ten.lower()] = id_int
                    mapping[ten] = id_int
    except Exception as e:
        print(f"⚠️ Lỗi fetch danh mục nguyên nhân TTS Cũ: {e}")
    return mapping


def fetch_lich_su_step1_map(id_yeu_cau_list: list, token: str) -> dict:
    """
    Truy vấn ngầm lịch sử xử lý (/XLXuLy/DanhSach_XuLyLichSu) song song đa luồng cho danh sách IdYeuCau.
    Trả về dict: {id_yeu_cau: (ngay_su_co, ngay_tiep_nhan)}.
    Giống hệt cách crawler_tts.py mở modal xl-xu-ly-lich-su của Mobile Internet.
    """
    if not id_yeu_cau_list:
        return {}
    headers = get_request_headers(token)
    url = f"{API_BASE_URL}/XLXuLy/DanhSach_XuLyLichSu"
    result_map = {}

    def _fetch_one(id_yc):
        if not id_yc:
            return id_yc, None, None
        try:
            r = requests.post(url, headers=headers, json={"IdYeuCau": int(id_yc)}, timeout=6)
            if r.status_code == 200:
                his = r.json()
                step1 = next((item for item in his if str(item.get("BuocXuLy")) in ("1.1", "1")), his[0] if his else {})
                return id_yc, step1.get("NgaySuCo"), step1.get("NgayTiepNhan")
        except Exception:
            pass
        return id_yc, None, None

    with ThreadPoolExecutor(max_workers=8) as ex:
        for id_yc, ngay_su_co, ngay_tiep_nhan in ex.map(_fetch_one, id_yeu_cau_list):
            if id_yc:
                result_map[id_yc] = (ngay_su_co, ngay_tiep_nhan)
    return result_map


def fetch_tts_old_tickets_api(token: str, limit: int = 200, from_date: str = None, to_date: str = None) -> list:
    """
    Quét toàn bộ phiếu sự cố từ REST API TTS Cũ (/WS/api/XLXuLy/DanhSach_XuLy).
    Không cần click phân trang trên trình duyệt.
    """
    if not from_date:
        from_date = (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d")
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")

    url = f"{API_BASE_URL}/XLXuLy/DanhSach_XuLy"
    headers = get_request_headers(token)

    payload = {
        "DSIdCoQuanYeuCau": "0,",
        "page": 1,
        "pagesize": limit,
        "TieuDe": "",
        "IdSuCo": 0,
        "TrangThaiXuLy": 0,
        "IdSanPham": 0,
        "IdCoQuanYeuCau": 0,
        "IdMucDo": 0,
        "LoaiPhieu": 0,
        "Sort": 1,
        "ColSort": 0,
        "HeThong": 0,
        "NgayBatDau": from_date,
        "NgayKetThuc": to_date
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"API DanhSach_XuLy trả về mã {resp.status_code}: {resp.text[:200]}")

    raw_list = resp.json()
    standard_tickets = []

    # Thu thập IdYeuCau để truy vấn song song lịch sử xử lý lấy chính xác NgaySuCo và NgayTiepNhan (chuẩn như Mobile Internet)
    id_yeu_cau_list = [int(t.get("IdYeuCau")) for t in raw_list if t.get("IdYeuCau")]
    lich_su_map = fetch_lich_su_step1_map(id_yeu_cau_list, token)

    for t in raw_list:
        phone_raw = str(t.get("DienThoai") or "").strip()
        # Chuẩn hóa phone VN (nếu 9 chữ số và đầu 8/9/3/7/5 thì thêm 84)
        clean_p = "".join(filter(str.isdigit, phone_raw))
        if len(clean_p) == 9:
            phone_84 = "84" + clean_p
        elif clean_p.startswith("0") and len(clean_p) == 10:
            phone_84 = "84" + clean_p[1:]
        else:
            phone_84 = clean_p

        title = str(t.get("TieuDeYeuCau") or t.get("LinhVuc") or "Sự cố mạng").strip()
        content = str(t.get("NoiDungYeuCau") or "").strip()

        raw_yc = t.get("IdYeuCau")
        clean_yc = int(raw_yc) if raw_yc is not None else None

        ngay_su_co, ngay_tiep_nhan = lich_su_map.get(clean_yc, (None, None))

        # Ngày yêu cầu trên bảng danh sách
        grid_date = str(t.get("NgayYeuCauHH") or t.get("NgayYeuCau") or "").strip()
        if "T" in grid_date and not t.get("NgayYeuCauHH"):
            try:
                dt = datetime.fromisoformat(grid_date)
                grid_date = dt.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                pass

        # Chuẩn hóa thời gian theo cơ chế của Mobile Internet (crawler_tts.py):
        # 1. Thời gian tiếp nhận: ưu tiên NgayTiepNhan từ Bước 1.1, fallback về grid_date (NgayYeuCauHH)
        reception_time = str(ngay_tiep_nhan or "").strip() or grid_date

        # 2. Thời điểm xảy ra sự cố: ưu tiên NgaySuCo từ Bước 1.1, fallback về extract_incident_time từ nội dung, fallback về reception_time
        incident_time = str(ngay_su_co or "").strip()
        if not incident_time or incident_time == "None":
            from report_bot import extract_incident_time
            incident_time = extract_incident_time(content, default_created_time=reception_time)
        if not incident_time or incident_time == "Không có thông tin":
            incident_time = reception_time

        created_time = reception_time
        inc_time = incident_time

        # Xác định loại dịch vụ (data vs voice_sms)
        title_lower = title.lower()
        if "gói cước" in title_lower or "goi cuoc" in title_lower:
            is_data = False
        else:
            is_data = any(k in title_lower for k in DATA_SERVICE_KEYWORDS)
        service_type = "data" if is_data else "voice_sms"

        # Chuẩn hóa MaCCOS về dạng chuỗi không có đuôi .0
        raw_ccos = t.get("MaCCOS")
        clean_ccos = ""
        if raw_ccos is not None:
            try:
                clean_ccos = str(int(float(raw_ccos)))
            except Exception:
                clean_ccos = str(raw_ccos).strip()

        # Chuẩn hóa PhanHoiHeThong và IdHeThong về int
        raw_ph = t.get("PhanHoiHeThong")
        try:
            clean_ph = int(float(raw_ph)) if raw_ph is not None else 1
        except Exception:
            clean_ph = 1

        raw_ht = t.get("IdHeThong")
        try:
            clean_ht = int(float(raw_ht)) if raw_ht is not None else 0
        except Exception:
            clean_ht = 0

        raw_id = t.get("Id")
        clean_id = int(raw_id) if raw_id is not None else None

        raw_yc = t.get("IdYeuCau")
        clean_yc = int(raw_yc) if raw_yc is not None else None

        ticket_item = {
            "phone": phone_84,
            "raw_phone": phone_raw,
            "title": title,
            "content": content,
            "incident_time": inc_time,
            "created_time": created_time,
            "service_type": service_type,
            "source": "tts_old_api",
            # Các trường kỹ thuật phục vụ đóng phiếu API
            "ticket_id": clean_id,
            "id_yeu_cau": clean_yc,
            "ma_ccos": clean_ccos,
            "phan_hoi_he_thong": clean_ph,
            "id_he_thong": clean_ht,
            "total_rows": t.get("TotalRows") or 0
        }
        standard_tickets.append(ticket_item)

    return standard_tickets


def close_tts_old_ticket_api(
    ticket: dict,
    id_nguyen_nhan: int,
    noi_dung: str,
    token: str,
    user_id: int = None,
    dry_run: bool = False
) -> tuple:
    """
    Thực hiện đóng phiếu sự cố qua REST API TTS Cũ (2 bước: cập nhật trạng thái & phản hồi CCOS).
    Trả về (success: bool, message: str).
    """
    phone = ticket.get("phone", "")
    ticket_id = ticket.get("ticket_id") or ticket.get("Id")
    id_yeu_cau = ticket.get("id_yeu_cau") or ticket.get("flow_id") or ticket.get("IdYeuCau")
    ma_ccos = ticket.get("ma_ccos") or ticket.get("ticket_code") or ticket.get("MaCCOS") or ""
    phan_hoi_ht = ticket.get("phan_hoi_he_thong") or ticket.get("PhanHoiHeThong") or 1
    id_he_thong = ticket.get("id_he_thong") or ticket.get("IdHeThong") or 0

    # Luôn tự động tra cứu lại từ TTS API để lấy phan_hoi_he_thong và id_he_thong chính xác
    # (DB có thể lưu giá trị mặc định nếu phiếu được import từ lần quét cũ trước khi có 2 cột này)
    need_api_sync = (not ticket_id or not id_yeu_cau or ticket.get("phan_hoi_he_thong") is None)
    if token and need_api_sync:
        try:
            active_list = fetch_tts_old_tickets_api(token)
            clean_p = phone.replace("+84", "0").replace("84", "0", 1) if phone.startswith("84") else phone
            for at in active_list:
                at_p = at.get("phone", "")
                at_r = at.get("raw_phone", "")
                if at_p == phone or at_r == phone or at_p == clean_p or at_r == clean_p or phone.endswith(at_r):
                    ticket_id = at.get("ticket_id") or ticket_id
                    id_yeu_cau = at.get("id_yeu_cau") or id_yeu_cau
                    ma_ccos = at.get("ma_ccos") or ma_ccos
                    phan_hoi_ht = at.get("phan_hoi_he_thong") if at.get("phan_hoi_he_thong") is not None else phan_hoi_ht
                    id_he_thong = at.get("id_he_thong") if at.get("id_he_thong") is not None else id_he_thong
                    ticket["ticket_id"] = ticket_id
                    ticket["id_yeu_cau"] = id_yeu_cau
                    ticket["flow_id"] = id_yeu_cau
                    ticket["ma_ccos"] = ma_ccos
                    # Cập nhật ngược lại vào DB
                    try:
                        from db_manager import update_ticket_field
                        update_ticket_field(phone, "ticket_id", ticket_id)
                        update_ticket_field(phone, "flow_id", str(id_yeu_cau))
                        if ma_ccos:
                            update_ticket_field(phone, "ticket_code", ma_ccos)
                        update_ticket_field(phone, "phan_hoi_he_thong", phan_hoi_ht)
                        update_ticket_field(phone, "id_he_thong", id_he_thong)
                    except Exception:
                        pass
                    break
        except Exception as ex_sync:
            print(f"⚠️ Lỗi tự động tra cứu ticket_id cho {phone}: {ex_sync}")

    if not token or not str(token).strip():
        return False, "❌ Không thể đóng phiếu: Thiếu token xác thực 'scnntttoken' của TTS Cũ. Vui lòng đăng nhập trên trình duyệt!"

    # Kiểm tra ticket_id & id_yeu_cau
    try:
        t_id = int(ticket_id) if ticket_id else 0
    except Exception:
        t_id = 0

    try:
        y_id = int(id_yeu_cau) if id_yeu_cau else 0
    except Exception:
        y_id = 0

    if not t_id or not y_id:
        return False, f"❌ Không thể đóng phiếu {phone}: Thiếu định danh bắt buộc (ticket_id={ticket_id}, id_yeu_cau={id_yeu_cau})."

    # Kiểm tra & lấy user_id (IdNhanVien)
    try:
        u_id = int(user_id) if user_id else 0
    except Exception:
        u_id = 0

    if not u_id:
        fresh_token, fresh_user = extract_token_from_browser()
        if fresh_user and (fresh_user.get("Id") or fresh_user.get("id")):
            u_id = int(fresh_user.get("Id") or fresh_user.get("id"))
            if fresh_token:
                token = fresh_token

    if not u_id:
        return False, f"❌ Không thể đóng phiếu {phone}: Thiếu thông tin người xử lý (IdNhanVien). Vui lòng đăng nhập tài khoản TTS Cũ trên trình duyệt Chrome/Firefox!"

    # Kiểm tra nội dung đóng phiếu
    clean_noi_dung = str(noi_dung or "").strip()
    if not clean_noi_dung:
        return False, f"❌ Không thể đóng phiếu {phone}: Nội dung đóng phiếu (comment/action_plan) đang bị trống!"

    # Kiểm tra nguyên nhân đóng phiếu
    try:
        nn_id = int(id_nguyen_nhan) if id_nguyen_nhan else 1016
    except Exception:
        nn_id = 1016

    if not nn_id:
        return False, f"❌ Không thể đóng phiếu {phone}: Thiếu mã nguyên nhân đóng sự cố (IdNguyenNhan)."

    if dry_run:
        return True, f"[DRY-RUN] Giả lập đóng phiếu API thành công cho {phone} (Id={t_id}, NguyenNhan={nn_id}, User={u_id})."

    headers = get_request_headers(token)

    # MaCCOS
    raw_ccos = ticket.get("ma_ccos") or ma_ccos or ""
    try:
        clean_ccos = str(int(float(raw_ccos))) if raw_ccos else ""
    except Exception:
        clean_ccos = str(raw_ccos).strip() if raw_ccos else ""

    # PhanHoiHeThong
    raw_ph = ticket.get("phan_hoi_he_thong") or phan_hoi_ht
    try:
        clean_ph = int(float(raw_ph)) if raw_ph is not None else 1
    except Exception:
        clean_ph = 1

    # IdHeThong
    raw_ht = ticket.get("id_he_thong") or id_he_thong
    try:
        clean_ht = int(float(raw_ht)) if raw_ht is not None else 0
    except Exception:
        clean_ht = 0

    # Bước 1: POST luu_CapNhatTrangThaiPhieu
    url_step1 = f"{API_BASE_URL}/XLXuLy/luu_CapNhatTrangThaiPhieu"
    payload_step1 = {
        "Id": t_id,
        "IdNhanVien": u_id,
        "IdYeuCau": y_id,
        "IdNguyenNhan": nn_id,
        "NoiDung": clean_noi_dung,
        "Op": 0,
        "MaCCOS": clean_ccos,
        "PhanHoiHeThong": clean_ph,
        "IdHeThong": clean_ht
    }

    try:
        res1 = requests.post(url_step1, headers=headers, json=payload_step1, timeout=15)
        if res1.status_code == 401:
            # Token hết hạn hoặc không hợp lệ -> tự động thử lấy token mới từ trình duyệt và retry
            fresh_token, fresh_user = extract_token_from_browser()
            if fresh_token and fresh_token != token:
                token = fresh_token
                headers = get_request_headers(token)
                if not u_id and fresh_user and fresh_user.get("Id"):
                    u_id = int(fresh_user["Id"])
                    payload_step1["IdNhanVien"] = u_id
                res1 = requests.post(url_step1, headers=headers, json=payload_step1, timeout=15)

        if res1.status_code != 200:
            return False, f"Lỗi gọi luu_CapNhatTrangThaiPhieu (status {res1.status_code}): {res1.text[:200]}"
        data1 = res1.json()
        if not data1.get("success", False):
            return False, f"luu_CapNhatTrangThaiPhieu thất bại: {data1.get('message', 'Không rõ')}"
    except Exception as ex1:
        return False, f"Ngoại lệ khi gọi luu_CapNhatTrangThaiPhieu: {ex1}"

    # Bước 2: Chuyển khiếu nại / phản hồi hệ thống (CCOS, PMS, FMS, CTS)
    feedback_msg = ""
    try:
        if clean_ph == 1 and clean_ccos:
            # Hệ thống CCOS: Gọi APICOSS/ChuyenKhieuNai
            url_step2 = f"{API_BASE_URL}/APICOSS/ChuyenKhieuNai"
            payload_step2 = {
                "IdYeuCau": y_id,
                "IdXuLy": t_id,
                "dsFile": "[]"
            }
            res2 = requests.post(url_step2, headers=headers, json=payload_step2, timeout=15)
            if res2.status_code == 200:
                data2 = res2.json()
                cf = data2.get("codeField")
                mf = data2.get("messageField", "")
                if cf == 1:
                    feedback_msg = f" (CCOS: {mf})"
                elif cf == -1:
                    feedback_msg = f" (CCOS phản hồi: {mf})"
            else:
                feedback_msg = f" (Lỗi CCOS HTTP {res2.status_code})"

        elif clean_ph == 2:
            # Hệ thống PMS
            url_step2 = f"{API_BASE_URL}/APIPMS/PhanHoiPMS"
            payload_step2 = {
                "TTS_ID": y_id,
                "STATUS": 1,
                "MESSAGE": noi_dung
            }
            requests.post(url_step2, headers=headers, json=payload_step2, timeout=15)

        elif clean_ph == 3:
            # Hệ thống FMS
            url_step2 = f"{API_BASE_URL}/APIFMS/PhanHoiFMS"
            payload_step2 = {
                "GLOBAL_ID": clean_ht,
                "TTS_ID": y_id,
                "STATUS": 1,
                "MESSAGE": noi_dung
            }
            requests.post(url_step2, headers=headers, json=payload_step2, timeout=15)

    except Exception as ex2:
        print(f"⚠️ Cảnh báo phản hồi hệ thống cho {phone}: {ex2}")
        feedback_msg = f" (Cảnh báo gửi hệ thống: {ex2})"

    return True, f"✅ Đã đóng phiếu thành công cho SĐT {phone} (Mã CCOS: {clean_ccos or '--'}){feedback_msg}."

