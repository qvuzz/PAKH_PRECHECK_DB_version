# services/auth_tts.py
# Module xác thực tài khoản TTS VNPT trực tiếp từ Dashboard bằng Playwright headless

import time
import json
import base64
from playwright.sync_api import sync_playwright


def _decode_user_str(user_str: str) -> dict:
    if not user_str:
        return {}
    try:
        data = json.loads(user_str)
    except Exception:
        try:
            decoded = base64.b64decode(user_str).decode("utf-8", errors="ignore")
            data = json.loads(decoded)
        except Exception:
            return {}
    if isinstance(data, dict):
        if "userInfo" in data and isinstance(data["userInfo"], dict):
            return data["userInfo"]
        return data
    return {}


def authenticate_tts(username: str, password: str, timeout: int = 25) -> dict:
    """
    Đăng nhập vào VNPT TTS bằng Playwright headless.
    Trả về dict:
      - success: bool
      - token: str (nếu thành công)
      - user: dict (nếu thành công)
      - error: str (nếu thất bại)
    """
    username = (username or "").strip()
    password = (password or "").strip()

    if not username or not password:
        return {"success": False, "error": "Vui lòng nhập đầy đủ tài khoản và mật khẩu TTS."}

    start_time = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 1. Điều hướng tới cổng đăng nhập TTS
            try:
                page.goto("https://tts.vnpt.vn/", timeout=18000)
            except Exception as ex:
                browser.close()
                return {"success": False, "error": f"Không thể kết nối máy chủ TTS VNPT: {ex}"}

            # 2. Đợi form đăng nhập xuất hiện
            try:
                page.wait_for_selector("#username", timeout=8000)
            except Exception:
                # Nếu đã vào thẳng
                tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
                if tok:
                    u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                    browser.close()
                    return {"success": True, "token": tok, "user": _decode_user_str(u_str)}
                browser.close()
                return {"success": False, "error": "Không tìm thấy form đăng nhập TTS."}

            # 3. Điền thông tin đăng nhập và submit
            page.fill("#username", username)
            page.fill("#password", password)
            page.click("button[type='submit']")

            # 4. Chờ phản hồi: hoặc lỗi hoặc lấy được token
            token = ""
            user_info = {}
            poll_interval = 0.5

            while (time.time() - start_time) < timeout:
                time.sleep(poll_interval)

                # Kiểm tra xem có thông báo lỗi từ CAS không
                try:
                    curr_url = page.url.lower()
                    if "cas/login" in curr_url or "login" in curr_url:
                        alerts = page.query_selector_all(".alert, .errors, #status, div[role='alert']")
                        for a in alerts:
                            if a.is_visible():
                                txt = a.inner_text().strip()
                                if "không thành công" in txt.lower() or "kiểm tra tên đăng nhập" in txt.lower():
                                    browser.close()
                                    return {"success": False, "error": "Sai tên đăng nhập hoặc mật khẩu TTS!"}
                                if "khóa" in txt.lower() or "lock" in txt.lower():
                                    browser.close()
                                    return {"success": False, "error": f"Tài khoản bị khóa: {txt}"}
                except Exception:
                    pass

                # Kiểm tra token trong localStorage
                try:
                    tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
                    if tok:
                        token = tok
                        u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                        user_info = _decode_user_str(u_str)
                        break
                except Exception:
                    pass

            browser.close()

            if token:
                return {
                    "success": True,
                    "token": token,
                    "user": user_info or {"TaiKhoan": username, "HoTen": username}
                }
            else:
                return {
                    "success": False,
                    "error": "Quá thời gian chờ phản hồi từ hệ thống TTS. Vui lòng thử lại."
                }

    except Exception as ex:
        return {"success": False, "error": f"Lỗi hệ thống đăng nhập: {str(ex)}"}
