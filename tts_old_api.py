# tts_old_api.py
# Module tích hợp REST API cho hệ thống TTS Cũ (tts.vnpt.vn/WS/api)

import os
import json
import time
import requests
from datetime import datetime, timedelta
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
    """Đọc token và user_info từ file cache nếu còn hiệu lực."""
    if TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("token", ""), data.get("user_info", {})
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


def extract_token_from_browser(driver=None) -> tuple:
    """
    Trích xuất token scnntttoken và userInfo trực tiếp từ Chrome tab tts.vnpt.vn.
    Trả về: (token, user_info)
    """
    token = ""
    user_info = {}

    # 1. Thử lấy qua Selenium driver nếu đang kết nối
    if driver:
        try:
            current_handle = driver.current_window_handle
            for handle in driver.window_handles:
                try:
                    driver.switch_to.window(handle)
                    if "tts.vnpt.vn" in driver.current_url.lower():
                        token = driver.execute_script("return localStorage.getItem('scnntttoken');")
                        user_str = driver.execute_script("return localStorage.getItem('userInfo');")
                        if user_str:
                            user_info = _decode_user_str(user_str)
                        if token:
                            break
                except Exception:
                    pass
            try:
                driver.switch_to.window(current_handle)
            except Exception:
                pass
        except Exception:
            pass

    # 2. Nếu chưa có, kết nối nhanh qua Playwright CDP tới port 9222
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

    # 3. Fallback về cache nếu không lấy được từ browser
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
                if ten and id_val:
                    mapping[ten.lower()] = id_val
                    mapping[ten] = id_val
    except Exception as e:
        print(f"⚠️ Lỗi fetch danh mục nguyên nhân TTS Cũ: {e}")
    return mapping


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
        # NgayKetThuc: Thời gian xảy ra sự cố (Ví dụ: 28/08/2026 18:19:41)
        # NgayYeuCauHH: Thời gian tiếp nhận yêu cầu (Ví dụ: 03/09/2026 14:03:29)
        inc_time = str(t.get("NgayKetThuc") or "").strip()
        created_time = str(t.get("NgayYeuCauHH") or t.get("NgayYeuCau") or "").strip()
        if not inc_time:
            inc_time = created_time

        # Xác định loại dịch vụ (data vs voice_sms)
        title_lower = title.lower()
        if "gói cước" in title_lower or "goi cuoc" in title_lower:
            is_data = False
        else:
            is_data = any(k in title_lower for k in DATA_SERVICE_KEYWORDS)
        service_type = "data" if is_data else "voice_sms"

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
            "ticket_id": t.get("Id"),
            "id_yeu_cau": t.get("IdYeuCau"),
            "ma_ccos": t.get("MaCCOS"),
            "phan_hoi_he_thong": t.get("PhanHoiHeThong") or 1,
            "id_he_thong": t.get("IdHeThong") or 0,
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
    ticket_id = ticket.get("ticket_id")
    id_yeu_cau = ticket.get("id_yeu_cau")

    if not ticket_id or not id_yeu_cau:
        return False, f"Phiếu {phone} thiếu ticket_id hoặc id_yeu_cau để gọi API đóng."

    if dry_run:
        return True, f"[DRY-RUN] Giả lập đóng phiếu API thành công cho {phone} (Id={ticket_id}, NguyenNhan={id_nguyen_nhan})."

    headers = get_request_headers(token)

    # Bước 1: POST luu_CapNhatTrangThaiPhieu
    url_step1 = f"{API_BASE_URL}/XLXuLy/luu_CapNhatTrangThaiPhieu"
    payload_step1 = {
        "Id": ticket_id,
        "IdNhanVien": user_id or 0,
        "IdYeuCau": id_yeu_cau,
        "IdNguyenNhan": id_nguyen_nhan,
        "NoiDung": noi_dung,
        "Op": 0,
        "MaCCOS": ticket.get("ma_ccos"),
        "PhanHoiHeThong": ticket.get("phan_hoi_he_thong") or 1,
        "IdHeThong": ticket.get("id_he_thong") or 0
    }

    try:
        res1 = requests.post(url_step1, headers=headers, json=payload_step1, timeout=15)
        if res1.status_code != 200:
            return False, f"Lỗi gọi luu_CapNhatTrangThaiPhieu (status {res1.status_code}): {res1.text[:200]}"
        data1 = res1.json()
        if not data1.get("success", False):
            return False, f"luu_CapNhatTrangThaiPhieu thất bại: {data1.get('message', 'Không rõ')}"
    except Exception as ex1:
        return False, f"Ngoại lệ khi gọi luu_CapNhatTrangThaiPhieu: {ex1}"

    # Bước 2: Phản hồi CCOS nếu có MaCCOS và PhanHoiHeThong == 1
    phan_hoi_ht = ticket.get("phan_hoi_he_thong") or 1
    ma_ccos = ticket.get("ma_ccos")
    if phan_hoi_ht == 1 and ma_ccos:
        url_step2 = f"{API_BASE_URL}/XLXuLy/phanHoi_Ccos1"
        payload_step2 = {
            "IdYeuCau": id_yeu_cau,
            "IdXuLy": ticket_id,
            "dsFile": "[]"
        }
        try:
            res2 = requests.post(url_step2, headers=headers, json=payload_step2, timeout=15)
            if res2.status_code == 200:
                data2 = res2.json()
                if data2.get("codeField") == -1:
                    return False, f"Đã cập nhật phiếu nhưng lỗi kết nối CCOS: {data2.get('messageField')}"
        except Exception as ex2:
            print(f"⚠️ Cảnh báo phản hồi CCOS cho {phone}: {ex2}")

    return True, f"✅ Đã đóng phiếu thành công qua REST API cho SĐT {phone} (Mã CCOS: {ma_ccos or '--'})."
