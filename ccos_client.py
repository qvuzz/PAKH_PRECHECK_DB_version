# ccos_client.py
# Module tra cứu phản ánh khiếu nại và trích xuất file đính kèm từ CCOS (http://gqknccos.vnpt.vn)
# Hỗ trợ tự động nhận diện phiên mới từ trình duyệt và tự động reset khi cookie hết hạn

import os
import re
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CCOS_CACHE_FILE = BASE_DIR / "ccos_cookie_cache.json"
CCOS_BASE_URL = "http://gqknccos.vnpt.vn"


def save_ccos_cache(cookies: dict):
    """Lưu cookies CCOS vào cache để tái sử dụng."""
    if not cookies:
        return
    try:
        data = {
            "cookies": cookies,
            "updated_at": time.time()
        }
        with open(CCOS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_ccos_cache() -> dict:
    """Đọc cookies CCOS từ cache."""
    if CCOS_CACHE_FILE.exists():
        try:
            with open(CCOS_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("cookies", {})
        except Exception:
            pass
    return {}


def invalidate_ccos_cache():
    """Xóa hoặc hủy cache CCOS khi phiên làm việc hết hạn."""
    try:
        if CCOS_CACHE_FILE.exists():
            os.remove(CCOS_CACHE_FILE)
    except Exception:
        pass


def get_ccos_cookies(driver=None, force_refresh: bool = False) -> dict:
    """
    Lấy cookies CCOS từ:
    1. Driver / Chrome CDP port 9222 (nếu đang mở)
    2. Firefox cookies.sqlite (nếu có)
    3. Cache file ccos_cookie_cache.json
    Nếu force_refresh=True, bỏ qua cache và ép quét trực tiếp từ trình duyệt.
    """
    cookies = {}

    # 1. Thử lấy trực tiếp từ Chrome CDP 9222 hoặc Chrome debug driver (ưu tiên cao nhất)
    try:
        from auth_extractor import extract_cdp_cookies, is_debug_port_open
        if driver:
            raw_c = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            for c in raw_c:
                if "gqknccos" in c.get("domain", ""):
                    cookies[c["name"]] = c["value"]
        elif is_debug_port_open(9222):
            cdp_c = extract_cdp_cookies("gqknccos.vnpt.vn", port=9222)
            if cdp_c:
                cookies.update(cdp_c)
    except Exception:
        pass

    # 2. Thử lấy từ Firefox
    if not cookies:
        try:
            from auth_extractor import extract_firefox_cookies
            ff_c = extract_firefox_cookies("gqknccos.vnpt.vn")
            if ff_c:
                cookies.update(ff_c)
        except Exception:
            pass

    # 3. Nếu tìm thấy cookies mới từ trình duyệt -> lưu ngay vào cache và trả về
    if cookies and ("SessionDB" in cookies or "SESSIONID" in cookies):
        save_ccos_cache(cookies)
        return cookies

    # 4. Nếu không lấy được từ trình duyệt và không ép refresh -> dùng cache đã lưu
    if not force_refresh:
        cached = load_ccos_cache()
        if cached:
            return cached

    return cookies


def build_cookie_header(cookies_dict: dict) -> str:
    """Tạo chuỗi header Cookie từ dict."""
    if not cookies_dict:
        return ""
    return "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])


def normalize_msisdn_ccos(phone: str) -> str:
    """
    Chuẩn hóa số điện thoại về format 9 số theo chuẩn tra cứu CCOS (bỏ 84 hoặc 0 ở đầu).
    Ví dụ: 0941420319 -> 941420319, 84941420319 -> 941420319.
    """
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("84") and len(digits) >= 11:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) >= 10:
        digits = digits[1:]
    return digits


def _is_session_invalid_response(raw_text: str) -> bool:
    """Kiểm tra xem phản hồi từ CCOS có báo hiệu phiên hết hạn hoặc lỗi chuyển trang hay không."""
    if not raw_text or not raw_text.strip():
        return True
    s_low = raw_text.lower()
    if "login.aspx" in s_low or "error.html" in s_low or "aspxerrorpath" in s_low:
        return True
    if "hết hạn phiên" in s_low or "session timeout" in s_low or "vui lòng đăng nhập" in s_low:
        return True
    return False


def get_ccos_attachments(phone: str, driver=None, timeout: float = 6.0, retry_count: int = 1) -> dict:
    """
    Tra cứu khiếu nại trên CCOS theo số thuê bao và bóc tách file đính kèm.
    Tự động reset và lấy cookie mới từ phiên trình duyệt nếu phiên cũ hết hạn.
    
    Trả về dict:
    {
        "has_file": bool,
        "files": [{"name": "...", "url": "..."}],
        "kn_code": "PA-0013342736",
        "kn_id": "13342736",
        "message": "Không có file đính kèm" | ""
    }
    """
    default_res = {
        "has_file": False,
        "files": [],
        "kn_code": "",
        "kn_id": "",
        "message": "Không có file đính kèm"
    }

    tb = normalize_msisdn_ccos(phone)
    if not tb:
        return default_res

    cookies = get_ccos_cookies(driver=driver)
    if not cookies:
        default_res["message"] = "Chưa có session CCOS"
        return default_res

    cookie_hdr = build_cookie_header(cookies)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": CCOS_BASE_URL,
        "Referer": f"{CCOS_BASE_URL}/Views/TTKH/ThongTinKhachHang.aspx",
        "Cookie": cookie_hdr,
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        # Bước 1: Tra cứu lịch sử khiếu nại theo số thuê bao
        url_search = f"{CCOS_BASE_URL}/Views/TTKH/Handler/ThongTinKhachHang.ashx?Type=LSKhieuNai"
        post_data = urllib.parse.urlencode({
            "SoThueBao": tb,
            "ViewAll": "0",
            "page": 1,
            "rp": 10
        }).encode("utf-8")

        req1 = urllib.request.Request(url_search, data=post_data, headers=headers)
        with urllib.request.urlopen(req1, timeout=timeout) as resp1:
            raw_text = resp1.read().decode("utf-8", errors="ignore")

        # Kiểm tra nếu phiên CCOS bị hết hạn
        if _is_session_invalid_response(raw_text):
            if retry_count > 0:
                from services.state import state
                state.log("WARN", "⚠️ Phiên CCOS có dấu hiệu hết hạn. Đang tự động làm mới cookie từ trình duyệt...")
                invalidate_ccos_cache()
                new_cookies = get_ccos_cookies(driver=driver, force_refresh=True)
                if new_cookies:
                    return get_ccos_attachments(phone, driver=driver, timeout=timeout, retry_count=retry_count - 1)
            default_res["message"] = "Phiên CCOS hết hạn"
            return default_res

        try:
            data1 = json.loads(raw_text)
        except Exception:
            return default_res

        rows = data1.get("rows", [])
        if not rows or not isinstance(rows, list):
            return default_res

        # Lấy khiếu nại đầu tiên (mới nhất)
        top_row = rows[0]
        ma_kn_raw = str(top_row.get("MaKhieuNai") or "")

        # Trích xuất kn_id và mã khiếu nại
        kn_id = ""
        m_id = re.search(r'data-id=[\'"](\d+)[\'"]', ma_kn_raw)
        if m_id:
            kn_id = m_id.group(1)
        else:
            m_fn = re.search(r"ShowPoupChiTietKN\(['\"](\d+)['\"]", ma_kn_raw)
            if m_fn:
                kn_id = m_fn.group(1)

        kn_code = ""
        m_code = re.search(r'>([^<]+)</a>', ma_kn_raw)
        if m_code:
            kn_code = m_code.group(1).strip()
        else:
            kn_code = re.sub(r'<[^>]+>', '', ma_kn_raw).strip()

        if not kn_id:
            return default_res

        # Bước 2: Gọi Handler.ashx?key=5 để lấy chi tiết khiếu nại và file đính kèm
        url_detail = f"{CCOS_BASE_URL}/Views/QLKhieuNai/Handler/Handler.ashx?key=5&id={kn_id}&view=0&archive=0"
        post_detail = urllib.parse.urlencode({"ReturnUrl": ""}).encode("utf-8")

        req2 = urllib.request.Request(url_detail, data=post_detail, headers=headers)
        with urllib.request.urlopen(req2, timeout=timeout) as resp2:
            raw_detail = resp2.read().decode("utf-8", errors="ignore")

        if _is_session_invalid_response(raw_detail):
            if retry_count > 0:
                invalidate_ccos_cache()
                new_cookies = get_ccos_cookies(driver=driver, force_refresh=True)
                if new_cookies:
                    return get_ccos_attachments(phone, driver=driver, timeout=timeout, retry_count=retry_count - 1)
            default_res["message"] = "Phiên CCOS hết hạn"
            return default_res

        data2 = json.loads(raw_detail)
        file_kh = str(data2.get("FileDinhKemKH") or "").strip()
        file_gqkn = str(data2.get("FileDinhKemGQKN") or "").strip()

        all_html = f"{file_kh}\n{file_gqkn}"
        
        # Bóc tách các link Download.aspx
        # Mẫu: <a href ='/Views/ChiTietKhieuNai/Download.aspx?id=1827032'>CamScanner 24-8-26 08.44.pdf</a>
        found_files = []
        links = re.findall(r'<a[^>]+href\s*=\s*[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', all_html, re.IGNORECASE)
        for link_url, link_name in links:
            clean_name = re.sub(r'<[^>]+>', '', link_name).strip()
            clean_url = link_url.strip()
            if not clean_url.startswith("http"):
                clean_url = urllib.parse.urljoin(CCOS_BASE_URL, clean_url)
            if clean_name and "Download.aspx" in clean_url:
                found_files.append({
                    "name": clean_name,
                    "url": clean_url
                })

        if found_files:
            return {
                "has_file": True,
                "files": found_files,
                "kn_code": kn_code,
                "kn_id": kn_id,
                "message": ""
            }
        else:
            return {
                "has_file": False,
                "files": [],
                "kn_code": kn_code,
                "kn_id": kn_id,
                "message": "Không có file đính kèm"
            }

    except Exception as e:
        default_res["message"] = f"Lỗi CCOS ({e})"
        return default_res
