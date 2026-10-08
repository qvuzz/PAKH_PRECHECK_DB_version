# btools_manager.py
# Quản lý và đồng bộ Cookie / Phiên đăng nhập BTools
import os
import json
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BTOOLS_COOKIE_FILE = BASE_DIR / "btools_cookie.json"

BTOOLS_HOST = os.environ.get("BTOOLS_HOST", "10.159.21.241:9267")
BTOOLS_BASE_URL = os.environ.get("BTOOLS_URL", f"http://{BTOOLS_HOST}/B_tools_v2")

def verify_btools_cookie(cookie_str: str) -> tuple:
    """
    Kiểm tra xem cookie BTools có hợp lệ và truy cập được hay không.
    Trả về: (is_valid: bool, reason_message: str)
    """
    if not cookie_str:
        return False, "Chưa có cookie BTools"
    
    clean_cookie = cookie_str.strip()
    if "JSESSIONID" not in clean_cookie:
        clean_cookie = f"JSESSIONID={clean_cookie}"

    test_url = f"{BTOOLS_BASE_URL}/data_view.jsp"
    try:
        req = urllib.request.Request(
            test_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": clean_cookie,
                "Host": "10.159.21.241:9267"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        if any(k in html for k in ["CAS – Central Authentication Service", "/cas/login", "id=\"login\"", "Tên đăng nhập"]):
            return False, "Cookie BTools đã hết hạn (bị chuyển hướng về cổng xác thực CAS)"
        if "SQLException" in html or "Internal Server Error" in html or "HTTP Status 500" in html:
            return False, "Máy chủ BTools báo lỗi cơ sở dữ liệu (500)"
        if any(k in html for k in ["customers", "data_view.jsp", "RAT_TYPE", "MSISDN", "DATA_VOLUME", "name=\"name\"", "Tìm Kiếm"]):
            return True, "Kết nối BTools thành công!"

        return False, "Trang phản hồi không đúng cấu trúc BTools"
    except Exception as e:
        return False, f"Lỗi kết nối tới máy chủ BTools (10.159.21.241): {e}"


def save_btools_cookie(cookie_str: str, verify: bool = False) -> tuple:
    """
    Lưu cookie BTools vào file cấu hình btools_cookie.json.
    Nếu verify=True: kiểm tra kết nối tới BTools server trước khi lưu.
    Nếu verify=False: lưu tức thì để tránh nghẽn luồng đồng bộ API.
    """
    clean_cookie = cookie_str.strip()
    if not clean_cookie:
        return False, "Cookie trống"
    if "JSESSIONID" not in clean_cookie:
        clean_cookie = f"JSESSIONID={clean_cookie}"

    is_valid = True
    msg = "Đã lưu Cookie BTools thành công"
    if verify:
        is_valid, msg = verify_btools_cookie(clean_cookie)

    data = {
        "cookie": clean_cookie,
        "is_valid": is_valid,
        "message": msg,
        "updated_at": json.dumps(str(Path(__file__).stat().st_mtime))
    }
    try:
        with open(BTOOLS_COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return False, f"Lỗi ghi file btools_cookie.json: {e}"

    return is_valid, msg


def load_saved_btools_cookie() -> str:
    """Đọc cookie đã lưu từ btools_cookie.json."""
    if not os.path.exists(BTOOLS_COOKIE_FILE):
        return ""
    try:
        with open(BTOOLS_COOKIE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("cookie", "").strip()
    except Exception:
        return ""


def get_cdp_browser_btools_cookie(port: int = 9222) -> str:
    """
    Lấy cookie của 10.159.21.241 trực tiếp từ Chrome Debug qua Browser WebSocket Target.
    Truy vấn toàn bộ cookie trình duyệt mà không cần chuyển tab.
    """
    try:
        from auth_extractor import is_debug_port_open, _run_async_safely
        if not is_debug_port_open(port):
            return ""

        import urllib.request, websockets, asyncio
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as r:
            ver = json.loads(r.read().decode("utf-8"))
        ws_url = ver.get("webSocketDebuggerUrl")
        if not ws_url:
            return ""

        async def _query():
            async with websockets.connect(ws_url, open_timeout=1.0, close_timeout=1.0) as ws:
                await ws.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
                raw_resp = await asyncio.wait_for(ws.recv(), timeout=1.5)
                res = json.loads(raw_resp)
                cookies = res.get("result", {}).get("cookies", [])
                btools_cookies = [f"{c['name']}={c['value']}" for c in cookies if "10.159.21.241" in c.get("domain", "")]
                return "; ".join(btools_cookies)

        res = _run_async_safely(_query(), timeout=2.0)
        return res or ""
    except Exception:
        return ""


def get_active_btools_cookie(driver=None, force_refresh=False) -> str:
    """
    Hàm tổng hợp để lấy Cookie BTools hoạt động tốt nhất:
    1. Kiểm tra cookie đã lưu từ btools_cookie.json.
    2. Nếu chưa có hoặc force_refresh: thử lấy từ Chrome Debug (Browser Target).
    3. Thử lấy từ Selenium driver nếu đang mở tab BTools.
    4. Thử lấy từ Firefox cookies.sqlite.
    5. Kiểm tra và tự động lưu lại nếu hợp lệ.
    """
    # 1. Đọc cookie đã lưu
    if not force_refresh:
        saved = load_saved_btools_cookie()
        if saved:
            is_valid, _ = verify_btools_cookie(saved)
            if is_valid:
                return saved

    # 2. Lấy từ Chrome Debug Browser Target (port 9222)
    cdp_cookie = get_cdp_browser_btools_cookie()
    if cdp_cookie:
        is_valid, _ = verify_btools_cookie(cdp_cookie)
        if is_valid:
            save_btools_cookie(cdp_cookie)
            return cdp_cookie

    # 3. Lấy từ driver window_handles
    if driver:
        try:
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            b_list = [f"{c['name']}={c['value']}" for c in cookies if "10.159.21.241" in c.get("domain", "")]
            if b_list:
                cand = "; ".join(b_list)
                is_valid, _ = verify_btools_cookie(cand)
                if is_valid:
                    save_btools_cookie(cand)
                    return cand
        except Exception:
            pass

    # 4. Fallback cookie đã lưu kể cả khi verify tạm thời fail (nếu không còn nguồn nào khác)
    saved = load_saved_btools_cookie()
    if saved:
        return saved

    return ""
