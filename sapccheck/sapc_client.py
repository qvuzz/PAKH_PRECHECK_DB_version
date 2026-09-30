import os
import sys
import json
import requests
from pathlib import Path

if hasattr(sys.stdout, "reconfigure") and sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure") and sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from .config import BASE_URL
except (ImportError, ValueError):
    try:
        from config import BASE_URL
    except ImportError:
        BASE_URL = "http://10.155.42.218/api/sapc"


CDP_URL = "http://127.0.0.1:9222"
COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")


class SAPCClient:

    def __init__(self, cdp_url=CDP_URL, driver=None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*"
        })
        if driver is not None:
            self.load_cookies_from_selenium(driver)
        else:
            self._load_cookies(cdp_url)

    def load_cookies_from_selenium(self, driver):
        """Load toan bo cookie cua tat ca cac domain qua CDP Network.getAllCookies."""
        try:
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            for c in cookies:
                self.session.cookies.set(
                    c['name'],
                    c['value'],
                    domain=c.get('domain'),
                    path=c.get('path', '/')
                )
            print(f"[OK] Loaded {len(cookies)} global cookies from Chrome CDP.")
            return True
        except Exception as e:
            try:
                cookies = driver.get_cookies()
                for c in cookies:
                    self.session.cookies.set(
                        c['name'],
                        c['value'],
                        domain=c.get('domain'),
                        path=c.get('path', '/')
                    )
                return True
            except Exception as ex:
                print(f"[WARN] Error loading cookies from Selenium: {ex}")
                return False

    def _load_cookies(self, cdp_url):
        urls_to_try = [cdp_url]
        if "localhost" in cdp_url:
            urls_to_try.append(cdp_url.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in cdp_url:
            urls_to_try.append(cdp_url.replace("127.0.0.1", "localhost"))

        # 1. Ưu tiên cao nhất: Đọc từ sapc_cookies.json hoặc cookies.json (được Extension Chrome hoặc Web đồng bộ)
        sapc_files = [
            os.path.join(os.path.dirname(__file__), "sapc_cookies.json"),
            COOKIE_FILE
        ]
        for cf in sapc_files:
            if os.path.exists(cf):
                try:
                    with open(cf, "r", encoding="utf-8") as f:
                        cookie_data = json.load(f)
                        if isinstance(cookie_data, dict):
                            self.session.cookies.update(cookie_data)
                        elif isinstance(cookie_data, list):
                            for c in cookie_data:
                                self.session.cookies.set(
                                    c['name'],
                                    c['value'],
                                    domain=c.get('domain', '10.155.42.218'),
                                    path=c.get('path', '/')
                                )
                    if self._is_cookie_valid():
                        print(f"[OK] Loaded and verified SAPC cookie from file: {os.path.basename(cf)}")
                        return
                except Exception as e:
                    print(f"[WARN] Error reading cookie file {cf}: {e}")

        # 2. Thử lấy cookie qua Chrome CDP nếu cổng 9222 đang mở
        for u in urls_to_try:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.connect_over_cdp(u)
                    context = browser.contexts[0]
                    cookies = context.cookies()
                    for c in cookies:
                        self.session.cookies.set(
                            c['name'],
                            c['value'],
                            domain=c.get('domain'),
                            path=c.get('path', '/')
                        )
                    sapc_cookies = [c for c in cookies if '10.155' in c.get('domain', '')]
                    if sapc_cookies:
                        try:
                            with open(COOKIE_FILE, 'w', encoding='utf-8') as cf_out:
                                json.dump(sapc_cookies, cf_out, indent=2, ensure_ascii=False)
                        except Exception:
                            pass
                    browser.close()
                    if self._is_cookie_valid():
                        print(f"[OK] Loaded SAPC cookie via Chrome CDP ({u})")
                        return
            except Exception:
                pass

        # 3. Thử quét browser_cookie3
        try:
            import browser_cookie3
            for loader in (browser_cookie3.chrome, browser_cookie3.edge):
                try:
                    cj = loader(domain_name="10.155.42.218")
                    count = 0
                    for c in cj:
                        self.session.cookies.set(c.name, c.value, domain="10.155.42.218", path="/")
                        count += 1
                    if count > 0 and self._is_cookie_valid():
                        print(f"[OK] Loaded {count} SAPC cookies via browser_cookie3 ({loader.__name__})")
                        return
                except Exception:
                    continue
        except Exception:
            pass

        # 4. Fallback cuối cùng: Firefox cookies.sqlite (chỉ dùng nếu còn hạn thực tế)
        try:
            import sys
            from pathlib import Path
            root_dir = str(Path(__file__).resolve().parent.parent)
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)
            from auth_extractor import extract_firefox_cookies
            ff_cookies = extract_firefox_cookies("10.155.42")
            if ff_cookies:
                for name, val in ff_cookies.items():
                    self.session.cookies.set(name, val, domain="10.155.42.218", path="/")
                if self._is_cookie_valid():
                    print(f"[OK] Loaded and verified SAPC cookies from Firefox.")
                    return
                else:
                    # Cookie Firefox đã hết hạn, xóa khỏi session để tránh gửi rác
                    self.session.cookies.clear()
        except Exception:
            pass

    def _is_cookie_valid(self) -> bool:
        """Kiểm tra nhanh xem cookie hiện tại có thực sự gọi được API SAPC hay không."""
        try:
            has_auth = any("ApplicationCookie" in getattr(c, 'name', '') or "Session" in getattr(c, 'name', '') for c in self.session.cookies)
            if not has_auth and len(self.session.cookies) == 0:
                return False
            url = f"{BASE_URL}/84916352813"
            r = self.session.get(url, timeout=3)
            return r.status_code == 200 and "json" in r.headers.get("Content-Type", "").lower()
        except Exception:
            return False


        print("[ERROR] Cannot load Chrome cookies via CDP, cookies.json, or browser_cookie3!")
        print("FIX INSTRUCTIONS:")
        print("   1. Run open_chrome.bat to open Chrome with Remote Debugging (port 9222) and log in to http://10.155.42.218.")
        print("   2. Or create file sapccheck/cookies.json with exported login cookies.")

    def query(self, msisdn):
        url = f"{BASE_URL}/{msisdn}"
        print(f"\nCalling API: {url}")
        response = self.session.get(url, timeout=30)

        print("STATUS:", response.status_code)
        print("CONTENT-TYPE:", response.headers.get("Content-Type"))

        if "json" not in response.headers.get("Content-Type", "").lower():
            out_path = Path(__file__).resolve().parent.parent / "output" / "debug_response.html"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            raise Exception(
                "Chưa đăng nhập hệ thống Core/SAPC (http://10.155.42.218) hoặc phiên đăng nhập đã hết hạn. "
                "Vui lòng mở trình duyệt và đăng nhập vào http://10.155.42.218."
            )

        response.raise_for_status()
        return response.json()