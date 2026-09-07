import os
import json
import requests
try:
    from .config import BASE_URL
except (ImportError, ValueError):
    try:
        from config import BASE_URL
    except ImportError:
        BASE_URL = "http://10.155.42.218:8080"


CDP_URL = "http://localhost:9222"
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
        """Load toàn bộ cookie của tất cả các domain qua CDP Network.getAllCookies."""
        try:
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            for c in cookies:
                self.session.cookies.set(
                    c['name'],
                    c['value'],
                    domain=c.get('domain'),
                    path=c.get('path', '/')
                )
            print(f"[OK] Đã tải {len(cookies)} cookies toàn cục từ Chrome CDP.")
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
                print(f"⚠️ Lỗi load cookie từ Selenium: {ex}")
                return False

    def _load_cookies(self, cdp_url):
        # 1. Try fetching cookies via Chrome Remote Debugging Protocol (CDP port 9222)
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(cdp_url)
                context = browser.contexts[0]
                cookies = context.cookies()
                for c in cookies:
                    self.session.cookies.set(
                        c['name'],
                        c['value'],
                        domain=c.get('domain'),
                        path=c.get('path', '/')
                    )
                browser.close()
                print("[OK] Loaded Chrome cookies via CDP (port 9222)")
                return
        except Exception as e:
            print(f"[INFO] Cannot connect to Chrome CDP ({cdp_url}): {e}")

        # 1.5 Try loading from Firefox cookies.sqlite
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
                print(f"[OK] Loaded {len(ff_cookies)} SAPC cookies from Firefox.")
                return
        except Exception:
            pass

        # 2. Try loading from fallback cookies.json
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                    cookie_data = json.load(f)
                    if isinstance(cookie_data, dict):
                        self.session.cookies.update(cookie_data)
                    elif isinstance(cookie_data, list):
                        for c in cookie_data:
                            self.session.cookies.set(
                                c['name'],
                                c['value'],
                                domain=c.get('domain'),
                                path=c.get('path', '/')
                            )
                print(f"[OK] Loaded cookies from file: {COOKIE_FILE}")
                return
            except Exception as e:
                print(f"[WARN] Error reading file {COOKIE_FILE}: {e}")

        # 3. Try browser_cookie3 as last resort
        try:
            import browser_cookie3
            cookies = browser_cookie3.chrome()
            self.session.cookies.update(cookies)
            print("[OK] Loaded Chrome cookies via browser_cookie3")
            return
        except Exception as e:
            print(f"[WARN] browser_cookie3 failed: {e}")

        print("[ERROR] Cannot load Chrome cookies via CDP, cookies.json, or browser_cookie3!")
        print("FIX INSTRUCTIONS:")
        print("   1. Run open_chrome.bat to open Chrome with Remote Debugging (port 9222) and log in.")
        print("   2. Or create file SAPCCheck/cookies.json with exported login cookies.")

    def query(self, msisdn):
        url = f"{BASE_URL}/{msisdn}"
        print(f"\nCalling API: {url}")
        response = self.session.get(url, timeout=30)

        print("STATUS:", response.status_code)
        print("CONTENT-TYPE:", response.headers.get("Content-Type"))

        if "json" not in response.headers.get("Content-Type", "").lower():
            with open("debug_response.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            raise Exception(
                "Response is not JSON (Phiên đăng nhập hết hạn hoặc chưa đăng nhập). "
                "Saved to debug_response.html"
            )

        response.raise_for_status()
        return response.json()