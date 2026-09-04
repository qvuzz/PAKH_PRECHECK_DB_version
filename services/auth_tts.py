# services/auth_tts.py
# Module xác thực tài khoản TTS VNPT trực tiếp từ Dashboard, hỗ trợ 2FA / OTP

import time
import json
import uuid
import base64
import threading
from playwright.sync_api import sync_playwright

# Lưu trữ các phiên đang chờ người dùng nhập OTP: session_id -> dict
ACTIVE_OTP_SESSIONS = {}
_PLAYWRIGHT = None
_BROWSER = None
_LOCK = threading.Lock()


def _get_shared_browser():
    global _PLAYWRIGHT, _BROWSER
    with _LOCK:
        if _BROWSER is None or not _BROWSER.is_connected():
            if _PLAYWRIGHT is None:
                _PLAYWRIGHT = sync_playwright().start()
            _BROWSER = _PLAYWRIGHT.chromium.launch(headless=True)
        return _BROWSER


def _cleanup_expired_sessions():
    now = time.time()
    expired = [sid for sid, s in ACTIVE_OTP_SESSIONS.items() if now - s.get("created_at", 0) > 180]
    for sid in expired:
        s = ACTIVE_OTP_SESSIONS.pop(sid, None)
        if s and "context" in s:
            try:
                s["context"].close()
            except Exception:
                pass


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


def authenticate_tts_step1(username: str, password: str, timeout: int = 15) -> dict:
    """
    Bước 1: Gửi thông tin tài khoản & mật khẩu lên hệ thống CAS TTS.
    Trả về:
      - Nếu thành công ngay: {"success": True, "token": "...", "user": {...}}
      - Nếu cần OTP: {"success": False, "otp_required": True, "session_id": "...", "message": "..."}
      - Nếu lỗi: {"success": False, "error": "..."}
    """
    username = (username or "").strip()
    password = (password or "").strip()

    if not username or not password:
        return {"success": False, "error": "Vui lòng nhập đầy đủ tài khoản và mật khẩu TTS."}

    _cleanup_expired_sessions()
    session_id = str(uuid.uuid4())

    try:
        browser = _get_shared_browser()
        context = browser.new_context()
        page = context.new_page()

        # 1. Mở trang đăng nhập TTS
        try:
            page.goto("https://tts.vnpt.vn/", timeout=18000)
        except Exception as ex:
            context.close()
            return {"success": False, "error": f"Không thể kết nối máy chủ TTS VNPT: {ex}"}

        # 2. Đợi form đăng nhập
        try:
            page.wait_for_selector("#username", timeout=8000)
        except Exception:
            tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
            if tok:
                u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                context.close()
                return {"success": True, "token": tok, "user": _decode_user_str(u_str)}
            context.close()
            return {"success": False, "error": "Không tìm thấy form đăng nhập TTS."}

        # 3. Điền tài khoản và mật khẩu
        page.fill("#username", username)
        page.fill("#password", password)
        page.click("button[type='submit']")

        # 4. Chờ xem kết quả: Lỗi mật khẩu, Cần OTP, hay Đăng nhập thành công ngay
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(0.5)

            # A. Kiểm tra thông báo lỗi từ CAS
            try:
                curr_url = page.url.lower()
                if "cas/login" in curr_url or "login" in curr_url:
                    alerts = page.query_selector_all(".alert, .errors, #status, div[role='alert']")
                    for a in alerts:
                        if a.is_visible():
                            txt = a.inner_text().strip()
                            if "không thành công" in txt.lower() or "kiểm tra tên đăng nhập" in txt.lower():
                                context.close()
                                return {"success": False, "error": "Sai tên đăng nhập hoặc mật khẩu TTS!"}
                            if "khóa" in txt.lower() or "lock" in txt.lower():
                                context.close()
                                return {"success": False, "error": f"Tài khoản bị khóa: {txt}"}
            except Exception:
                pass

            # B. Kiểm tra nếu đã có token ngay (không bị yêu cầu OTP)
            try:
                tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
                if tok:
                    u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                    context.close()
                    return {
                        "success": True,
                        "token": tok,
                        "user": _decode_user_str(u_str) or {"TaiKhoan": username, "HoTen": username}
                    }
            except Exception:
                pass

            # C. Kiểm tra nếu hệ thống chuyển sang màn hình yêu cầu OTP / 2FA
            try:
                curr_url = page.url.lower()
                content = page.content().lower()
                has_otp_in_url = any(k in curr_url for k in ["otp", "twofactor", "smartca", "verify"])
                has_otp_in_text = any(k in content for k in ["mã otp", "mã xác thực", "xác thực otp", "smartca", "nhập mã"])
                has_otp_input = bool(page.query_selector("input#otp, input[name='otp'], input#token, input[name='token'], input[placeholder*='OTP'], input[placeholder*='otp']"))

                if has_otp_in_url or has_otp_in_text or has_otp_input:
                    # Lưu phiên để chờ người dùng nhập OTP
                    ACTIVE_OTP_SESSIONS[session_id] = {
                        "context": context,
                        "page": page,
                        "username": username,
                        "created_at": time.time()
                    }
                    return {
                        "success": False,
                        "otp_required": True,
                        "session_id": session_id,
                        "message": "Mã OTP đã được gửi về điện thoại của bạn (hoặc yêu cầu xác thực SmartCA)."
                    }
            except Exception:
                pass

        # Hết thời gian chờ mà chưa có token cũng chưa phát hiện OTP
        # Nếu vẫn còn ở trang khác login, có thể là OTP dạng redirect
        ACTIVE_OTP_SESSIONS[session_id] = {
            "context": context,
            "page": page,
            "username": username,
            "created_at": time.time()
        }
        return {
            "success": False,
            "otp_required": True,
            "session_id": session_id,
            "message": "Vui lòng nhập mã OTP để hoàn tất đăng nhập."
        }

    except Exception as ex:
        return {"success": False, "error": f"Lỗi hệ thống đăng nhập: {str(ex)}"}


def authenticate_tts_step2_otp(session_id: str, otp_code: str, timeout: int = 20) -> dict:
    """
    Bước 2: Gửi mã OTP vào phiên đang chờ để hoàn tất đăng nhập.
    """
    session = ACTIVE_OTP_SESSIONS.get(session_id)
    if not session:
        return {"success": False, "error": "Phiên đăng nhập đã hết hạn hoặc không tồn tại. Vui lòng bấm Đăng nhập lại."}

    page = session["page"]
    context = session["context"]
    username = session["username"]
    otp_code = (otp_code or "").strip()

    try:
        # 1. Tìm ô nhập OTP (nếu người dùng có nhập mã)
        if otp_code:
            otp_input = (
                page.query_selector("input#otp") or
                page.query_selector("input[name='otp']") or
                page.query_selector("input#token") or
                page.query_selector("input[name='token']") or
                page.query_selector("input[placeholder*='OTP']") or
                page.query_selector("input[placeholder*='otp']") or
                page.query_selector("input[type='password']:visible") or
                page.query_selector("input[type='text']:visible")
            )

            if otp_input:
                otp_input.fill(otp_code)
                time.sleep(0.3)
                
                # Bấm submit hoặc Enter
                submit_btn = (
                    page.query_selector("button[type='submit']") or
                    page.query_selector("input[type='submit']") or
                    page.query_selector("#submit") or
                    page.query_selector("button:has-text('Xác nhận')") or
                    page.query_selector("button:has-text('Đăng nhập')") or
                    page.query_selector("button:has-text('Tiếp tục')")
                )
                if submit_btn and submit_btn.is_visible():
                    submit_btn.click()
                else:
                    otp_input.press("Enter")

        # 2. Chờ token xuất hiện trong localStorage
        start_time = time.time()
        token = ""
        user_info = {}

        while time.time() - start_time < timeout:
            time.sleep(0.5)

            # Kiểm tra lỗi OTP
            try:
                alerts = page.query_selector_all(".alert, .errors, #status, div[role='alert']")
                for a in alerts:
                    if a.is_visible():
                        txt = a.inner_text().strip()
                        if any(k in txt.lower() for k in ["không đúng", "sai", "hết hạn", "invalid", "thất bại"]):
                            return {"success": False, "error": f"Lỗi xác thực: {txt}"}
            except Exception:
                pass

            # Kiểm tra token
            try:
                tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
                if tok:
                    token = tok
                    u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                    user_info = _decode_user_str(u_str)
                    break
            except Exception:
                pass

        if token:
            try:
                context.close()
            except Exception:
                pass
            ACTIVE_OTP_SESSIONS.pop(session_id, None)
            return {
                "success": True,
                "token": token,
                "user": user_info or {"TaiKhoan": username, "HoTen": username}
            }
        else:
            return {
                "success": False,
                "error": "Mã OTP không chính xác hoặc đã hết hạn. Vui lòng thử lại."
            }

    except Exception as ex:
        return {"success": False, "error": f"Lỗi xử lý xác thực OTP: {str(ex)}"}
