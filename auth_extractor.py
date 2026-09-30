# auth_extractor.py
# Module trích xuất Token & Cookie đa trình duyệt (Chrome, Firefox, Edge, Brave, Cốc Cốc, v.v.)
# Hoạt động 100% ngầm, không phụ thuộc riêng vào Chrome cổng 9222.

import os
import glob
import json
import sqlite3
import shutil
import tempfile
import urllib.request
import asyncio

def get_firefox_profile_dirs():
    """Lấy danh sách tất cả các thư mục Profile của Firefox trên máy."""
    app_data = os.getenv("APPDATA")
    if not app_data:
        return []
    pattern = os.path.join(app_data, "Mozilla", "Firefox", "Profiles", "*")
    profiles = glob.glob(pattern)
    # Sắp xếp ưu tiên profile được sửa đổi gần nhất
    return sorted(profiles, key=lambda p: os.path.getmtime(p), reverse=True)


def extract_firefox_local_storage(domain_keyword: str, key_name: str) -> str:
    """
    Trích xuất giá trị LocalStorage từ Firefox SQLite database.
    Hỗ trợ giải nén Snappy raw (chuẩn nén của Firefox LocalStorage) để lấy token chính xác 100%.
    """
    for prof in get_firefox_profile_dirs():
        storage_dir = os.path.join(prof, "storage", "default")
        if not os.path.exists(storage_dir):
            continue

        for folder in os.listdir(storage_dir):
            if domain_keyword.lower() in folder.lower():
                data_sqlite = os.path.join(storage_dir, folder, "ls", "data.sqlite")
                if os.path.exists(data_sqlite):
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        tmp_name = tmp.name
                    try:
                        shutil.copy2(data_sqlite, tmp_name)
                        conn = sqlite3.connect(tmp_name)
                        row = conn.execute("SELECT value FROM data WHERE key = ?", (key_name,)).fetchone()
                        conn.close()
                        if row and row[0]:
                            raw = row[0]
                            if isinstance(raw, bytes):
                                # Thử giải nén Snappy raw (chuẩn nén của Firefox LocalStorage)
                                try:
                                    import cramjam
                                    decomp = bytes(cramjam.snappy.decompress_raw(raw))
                                    return decomp.decode("utf-8", errors="ignore").strip()
                                except Exception:
                                    pass

                                # Fallback nếu không bị nén
                                try:
                                    return raw.decode("utf-8", errors="ignore").strip()
                                except Exception:
                                    pass
                            elif isinstance(raw, str):
                                return raw.strip()
                    except Exception:
                        pass
                    finally:
                        if os.path.exists(tmp_name):
                            try:
                                os.remove(tmp_name)
                            except Exception:
                                pass
    return ""


def extract_firefox_cookies(domain_keyword: str) -> dict:
    """
    Trích xuất toàn bộ cookies của một domain từ cookies.sqlite của Firefox.
    Trả về dict {cookie_name: cookie_value}.
    """
    results = {}
    for prof in get_firefox_profile_dirs():
        cookie_db = os.path.join(prof, "cookies.sqlite")
        if not os.path.exists(cookie_db):
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = os.path.join(tmpdir, "cookies.sqlite")
            try:
                shutil.copy2(cookie_db, tmp_db)
                wal_db = cookie_db + "-wal"
                if os.path.exists(wal_db):
                    try:
                        shutil.copy2(wal_db, tmp_db + "-wal")
                    except Exception:
                        pass
                shm_db = cookie_db + "-shm"
                if os.path.exists(shm_db):
                    try:
                        shutil.copy2(shm_db, tmp_db + "-shm")
                    except Exception:
                        pass

                conn = sqlite3.connect(tmp_db)
                query = "SELECT name, value FROM moz_cookies WHERE host LIKE ?"
                rows = conn.execute(query, (f"%{domain_keyword}%",)).fetchall()
                conn.close()
                for name, val in rows:
                    if name not in results:
                        results[name] = val
            except Exception:
                pass
    return results


def is_debug_port_open(port: int = 9222) -> bool:
    """Kiểm tra cực nhanh (0.05s) xem port debug có đang mở hay không trước khi gửi request."""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.05)
        is_open = (sock.connect_ex(('127.0.0.1', port)) == 0)
        sock.close()
        return is_open
    except Exception:
        return False


def _run_async_safely(coro, timeout: float = 2.0):
    """Chạy coroutine async an toàn, tương thích 100% với FastAPI event loop và có timeout bắt buộc."""
    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result(timeout=timeout)
    except Exception:
        return None


def extract_cdp_cookies(domain_keyword: str, port: int = 9222) -> dict:
    """Trích xuất cookies qua Chrome/Edge CDP nếu cổng debug đang mở (an toàn, không treo)."""
    if not is_debug_port_open(port):
        return {}

    results = {}
    try:
        import websockets
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as r:
            ver = json.loads(r.read().decode("utf-8"))
        ws_url = ver.get("webSocketDebuggerUrl")
        if not ws_url:
            return results

        async def _query():
            async with websockets.connect(ws_url, open_timeout=1.0, close_timeout=1.0) as ws:
                msg = {"id": 1, "method": "Storage.getCookies", "params": {}}
                await ws.send(json.dumps(msg))
                resp = await asyncio.wait_for(ws.recv(), timeout=1.5)
                data = json.loads(resp)
                cookies = data.get("result", {}).get("cookies", [])
                for c in cookies:
                    if domain_keyword.lower() in c.get("domain", "").lower():
                        results[c["name"]] = c["value"]
            return results

        _run_async_safely(_query(), timeout=2.0)
    except Exception:
        pass
    return results


def extract_cdp_local_storage(domain_keyword: str, key_name: str, port: int = 9222) -> str:
    """Trích xuất localStorage qua Chrome/Edge CDP port 9222 nếu đang mở."""
    if not is_debug_port_open(port):
        return ""

    try:
        import websockets
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1.0) as r:
            tabs = json.loads(r.read().decode("utf-8"))
        ws_url = None
        for t in tabs:
            if domain_keyword.lower() in t.get("url", "").lower():
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            return ""

        async def _query():
            async with websockets.connect(ws_url, open_timeout=1.0, close_timeout=1.0) as ws:
                msg = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": f"localStorage.getItem('{key_name}')"}
                }
                await ws.send(json.dumps(msg))
                resp = await asyncio.wait_for(ws.recv(), timeout=1.5)
                data = json.loads(resp)
                return data.get("result", {}).get("result", {}).get("value") or ""

        res = _run_async_safely(_query(), timeout=2.0)
        return res or ""
    except Exception:
        return ""


def get_universal_btools_cookie(driver=None) -> str:
    """
    Lấy cookie BTools tự động từ bất kỳ trình duyệt nào (Chrome, Edge, Firefox, hoặc cache).
    """
    # 1. Thử lấy từ Chrome/Edge driver nếu đang có
    if driver:
        try:
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            b_list = [f"{c['name']}={c['value']}" for c in cookies if "10.159.21.241" in c.get("domain", "")]
            if b_list:
                return "; ".join(b_list)
        except Exception:
            pass

    # 2. Thử lấy từ Chrome/Edge CDP cổng 9222
    cdp_cookies = extract_cdp_cookies("10.159.21.241")
    if cdp_cookies:
        return "; ".join([f"{k}={v}" for k, v in cdp_cookies.items()])

    # 3. Thử lấy từ Firefox cookies.sqlite
    ff_cookies = extract_firefox_cookies("10.159.21.241")
    if ff_cookies:
        return "; ".join([f"{k}={v}" for k, v in ff_cookies.items()])

    # 4. Thử lấy qua browser_cookie3 (quét tất cả các trình duyệt cài đặt trên máy)
    try:
        import browser_cookie3
        for loader in (browser_cookie3.firefox,):
            try:
                cj = loader(domain_name="10.159.21.241")
                parts = [f"{c.name}={c.value}" for c in cj]
                if parts:
                    return "; ".join(parts)
            except Exception:
                continue
    except Exception:
        pass

    return ""


def get_universal_ttsnew_token(driver=None) -> str:
    """
    Lấy Bearer Token TTS Mới từ bất kỳ trình duyệt nào (Chrome, Edge, Firefox, hoặc cache).
    """
    # 1. Thử lấy từ Chrome/Edge CDP 9222
    tok = extract_cdp_local_storage("tts.vnptnet.vn", "TOKEN")
    if tok:
        if not tok.startswith("Bearer "):
            tok = "Bearer " + tok
        return tok

    # 2. Thử lấy từ Firefox localStorage
    tok_ff = extract_firefox_local_storage("tts.vnptnet.vn", "TOKEN")
    if tok_ff:
        if not tok_ff.startswith("Bearer "):
            tok_ff = "Bearer " + tok_ff
        return tok_ff

    # 3. Thử lấy từ driver nếu đang mở đúng tab
    if driver:
        try:
            if "tts.vnptnet.vn" in driver.current_url.lower():
                tok_drv = driver.execute_script("return localStorage.getItem('TOKEN');")
                if tok_drv:
                    if not tok_drv.startswith("Bearer "):
                        tok_drv = "Bearer " + tok_drv
                    return tok_drv
        except Exception:
            pass

    return ""


def get_chrome_debug_driver():
    """
    Chỉ kết nối ChromeDriver NẾU port 9222 đang thực sự lắng nghe.
    Tuyệt đối không gọi webdriver.Chrome nếu port đóng, tránh Selenium bị treo khi dùng Firefox/Edge.
    """
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        is_open = (sock.connect_ex(('127.0.0.1', 9222)) == 0)
        sock.close()
        if not is_open:
            return None

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        options = Options()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        return webdriver.Chrome(options=options)
    except Exception:
        return None


CEM_CACHE_FILE = os.path.join(os.path.dirname(__file__), "cem_auth_cache.json")

def _save_cem_cache(api_key: str, cookies_dict: dict):
    if not api_key:
        return
    try:
        import time
        with open(CEM_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"api_key": api_key, "cookies": cookies_dict, "updated_at": time.time()}, f, ensure_ascii=False)
    except Exception:
        pass

def _load_cem_cache():
    if os.path.exists(CEM_CACHE_FILE):
        try:
            with open(CEM_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("api_key"), data.get("cookies", {})
        except Exception:
            pass
    return None, {}


def get_universal_cem_auth(driver=None, force_refresh=False):
    """
    Trích xuất tự động apikey và cookies của CEM VNPT Media từ bất kỳ trình duyệt nào:
    1. Chrome debug driver / Chrome port 9222 (ưu tiên cao nhất, tức thì trong RAM).
    2. Firefox cookies.sqlite (tự động đọc profile mới nhất).
    3. Browser_cookie3 (quét Edge, Chrome, Firefox).
    4. Cache file cem_auth_cache.json (phòng trường hợp đã đóng trình duyệt).
    Trả về tuple: (api_key, cookies_dict)
    """
    import urllib.parse
    api_key = None
    cookies_dict = {}

    # 1. Ưu tiên đọc từ cache file cem_auth_cache.json trước tiên nếu không bị ép buộc làm mới
    if not force_refresh:
        cached_key, cached_cookies = _load_cem_cache()
        if cached_key:
            return cached_key, cached_cookies

    # 2. Thử lấy từ driver nếu đang mở tab hoặc có cookies
    if driver:
        try:
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            for c in cookies:
                if "vnptmedia" in c.get("domain", "").lower():
                    cookies_dict[c["name"]] = c["value"]
                    if c["name"] == "apikey":
                        api_key = urllib.parse.unquote(c["value"])
            if api_key:
                _save_cem_cache(api_key, cookies_dict)
                return api_key, cookies_dict
        except Exception:
            pass

    # 3. Thử lấy từ Chrome/Edge CDP nếu port debug mở
    if is_debug_port_open():
        cdp_cookies = extract_cdp_cookies("vnptmedia")
        if cdp_cookies:
            cookies_dict.update(cdp_cookies)
            if "apikey" in cdp_cookies:
                api_key = urllib.parse.unquote(cdp_cookies["apikey"])
                _save_cem_cache(api_key, cookies_dict)
                return api_key, cookies_dict

    # 4. Thử lấy trực tiếp từ Firefox cookies.sqlite
    try:
        ff_cookies = extract_firefox_cookies("vnptmedia")
        if ff_cookies:
            cookies_dict.update(ff_cookies)
            if "apikey" in ff_cookies:
                api_key = urllib.parse.unquote(ff_cookies["apikey"])
                _save_cem_cache(api_key, cookies_dict)
                return api_key, cookies_dict
    except Exception:
        pass

    # 5. Quét nhẹ qua Firefox session trong browser_cookie3 (bỏ qua Chrome/Edge tránh nghẽn Admin trên Windows)
    try:
        import browser_cookie3
        for loader in (browser_cookie3.firefox,):
            try:
                cj = loader(domain_name="vnptmedia.vn")
                for c in cj:
                    cookies_dict[c.name] = c.value
                    if c.name == "apikey":
                        api_key = urllib.parse.unquote(c.value)
                if api_key:
                    _save_cem_cache(api_key, cookies_dict)
                    return api_key, cookies_dict
            except Exception:
                continue
    except Exception:
        pass

    return api_key, cookies_dict

