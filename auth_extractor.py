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


def extract_cdp_cookies(domain_keyword: str, port: int = 9222) -> dict:
    """Trích xuất cookies qua Chrome/Edge CDP nếu cổng 9222 đang mở."""
    results = {}
    try:
        import websockets
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1.5) as r:
            tabs = json.loads(r.read().decode("utf-8"))
        ws_url = None
        for t in tabs:
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            return results

        async def _query():
            async with websockets.connect(ws_url) as ws:
                msg = {"id": 1, "method": "Network.getAllCookies", "params": {}}
                await ws.send(json.dumps(msg))
                resp = await ws.recv()
                data = json.loads(resp)
                cookies = data.get("result", {}).get("cookies", [])
                for c in cookies:
                    if domain_keyword.lower() in c.get("domain", "").lower():
                        results[c["name"]] = c["value"]

        asyncio.run(_query())
    except Exception:
        pass
    return results


def extract_cdp_local_storage(domain_keyword: str, key_name: str, port: int = 9222) -> str:
    """Trích xuất localStorage qua Chrome/Edge CDP port 9222 nếu đang mở."""
    try:
        import websockets
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1.5) as r:
            tabs = json.loads(r.read().decode("utf-8"))
        ws_url = None
        for t in tabs:
            if domain_keyword.lower() in t.get("url", "").lower():
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            return ""

        async def _query():
            async with websockets.connect(ws_url) as ws:
                msg = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": f"localStorage.getItem('{key_name}')"}
                }
                await ws.send(json.dumps(msg))
                resp = await ws.recv()
                data = json.loads(resp)
                return data.get("result", {}).get("result", {}).get("value") or ""

        return asyncio.run(_query())
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
        for loader in (browser_cookie3.firefox, browser_cookie3.edge, browser_cookie3.chrome):
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


def get_universal_cem_auth(driver=None):
    """
    Trích xuất tự động apikey và cookies của CEM VNPT Media từ bất kỳ trình duyệt nào
    (Firefox session recovery.jsonlz4, Chrome CDP, Edge, hoặc browser_cookie3).
    Trả về tuple: (api_key, cookies_dict)
    """
    import urllib.parse
    api_key = None
    cookies_dict = {}

    # 1. Thử lấy từ driver nếu đang mở tab hoặc có cookies
    if driver:
        try:
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            for c in cookies:
                if "vnptmedia" in c.get("domain", "").lower():
                    cookies_dict[c["name"]] = c["value"]
                    if c["name"] == "apikey":
                        api_key = urllib.parse.unquote(c["value"])
            if api_key:
                return api_key, cookies_dict
        except Exception:
            pass

    # 2. Thử lấy từ Chrome/Edge CDP port 9222 (an toàn, socket timeout 0.3s)
    cdp_cookies = extract_cdp_cookies("vnptmedia")
    if cdp_cookies:
        cookies_dict.update(cdp_cookies)
        if "apikey" in cdp_cookies:
            api_key = urllib.parse.unquote(cdp_cookies["apikey"])
            return api_key, cookies_dict

    # 3. Quét qua browser_cookie3 (Firefox session cookies trong recovery.jsonlz4, Chrome, Edge)
    try:
        import browser_cookie3
        for loader in (browser_cookie3.firefox, browser_cookie3.edge, browser_cookie3.chrome):
            try:
                cj = loader(domain_name="vnptmedia.vn")
                for c in cj:
                    cookies_dict[c.name] = c.value
                    if c.name == "apikey":
                        api_key = urllib.parse.unquote(c.value)
                if api_key:
                    return api_key, cookies_dict
            except Exception:
                continue
    except Exception:
        pass

    return api_key, cookies_dict

