import os
import sys
import time
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Fix Unicode tiếng Việt trên console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ensure_tts_logged_in(max_wait_seconds=180):
    """
    Đảm bảo Chrome đã mở và tài khoản đã đăng nhập vào VNPT TTS.
    Tự động điền USER/PASS và chờ xác thực OTP nếu cần.
    """
    base_dir = Path(__file__).resolve().parent
    env_file = base_dir / ".env"
    load_dotenv(env_file)

    bat_file = base_dir / "open_chrome.bat"
    if bat_file.exists():
        print("🚀 [LOGIN] Kiểm tra và khởi động Chrome Debugging...")
        subprocess.Popen(str(bat_file), shell=True)
        time.sleep(3)

    user = os.getenv("TTS_USER", "").strip()
    password = os.getenv("TTS_PASS", "").strip()

    if not user or not password:
        print("ℹ️ [LOGIN] Chưa điền TTS_USER/PASS trong .env. Hãy đăng nhập thủ công trên trình duyệt nếu cần.")

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            print("✅ [LOGIN] Đã kết nối Chrome Debugging (Port 9222)!")
        except Exception as ex:
            print(f"❌ [LOGIN] Không kết nối được Chrome Debugging Port 9222: {ex}")
            return False

        context = browser.contexts[0] if browser.contexts else browser.new_context()

        # Tìm tab TTS nếu đã mở sẵn
        page = None
        for pge in context.pages:
            if "tts.vnpt.vn" in pge.url:
                page = pge
                print("♻️ [LOGIN] Tái sử dụng tab TTS đang mở.")
                break

        if page is None:
            print("🌐 [LOGIN] Đang mở trang chủ TTS...")
            page = context.new_page()
            try:
                page.goto("https://tts.vnpt.vn/", wait_until="networkidle", timeout=20000)
            except Exception:
                pass

        current_url = page.url
        print(f"📍 [LOGIN] URL hiện tại: {current_url}")

        # Tự động điền form đăng nhập nếu phát hiện form
        try:
            page.wait_for_selector("#username", timeout=5000)
            print("🔑 [LOGIN] Phát hiện form đăng nhập, đang điền tài khoản...")
            page.fill("#username", user)
            page.fill("#password", password)
            page.press("#password", "Enter")
            print("📤 [LOGIN] Đã gửi thông tin đăng nhập!")
        except Exception:
            print("ℹ️ [LOGIN] Không phát hiện form login (có thể đã đăng nhập sẵn).")

        # Chờ vượt qua màn hình login / OTP nếu có
        print(f"📲 [LOGIN] Đang kiểm tra trạng thái đăng nhập (tối đa {max_wait_seconds}s)...")
        check_interval = 2
        elapsed = 0

        while elapsed < max_wait_seconds:
            curr = page.url.lower()
            if "login" not in curr and "otp" not in curr:
                print("✅ [LOGIN] Đã đăng nhập / qua bước OTP thành công!")
                break
            time.sleep(check_interval)
            elapsed += check_interval
        else:
            print(f"⚠️ [LOGIN] Hết thời gian chờ {max_wait_seconds}s.")

        # Điều hướng thẳng vào trang xử lý sự cố nếu đã login
        curr = page.url.lower()
        if "login" not in curr and "otp" not in curr:
            print("➡️ [LOGIN] Chuyển hướng sang trang Xử lý sự cố...")
            try:
                page.evaluate("window.location.href = 'https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new'")
                time.sleep(3)
            except Exception:
                try:
                    page.goto("https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new", timeout=15000)
                except Exception:
                    pass
            success = True
        else:
            print("⚠️ [LOGIN] Chưa hoàn tất đăng nhập/OTP.")
            success = False

        browser.close()
        return success


if __name__ == "__main__":
    ensure_tts_logged_in()
