# services/auth_tts.py
# Module xác thực tài khoản TTS VNPT trực tiếp từ Dashboard, hỗ trợ 2FA / OTP
# SỬ DỤNG DEDICATED WORKER THREAD để đảm bảo Playwright luôn chạy trên cùng 1 thread
# loại bỏ triệt để lỗi greenlet: "cannot switch to a different thread"

import sys
import time
import json
import uuid
import base64
import queue
import threading

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from playwright.sync_api import sync_playwright

_JOB_QUEUE = queue.Queue()
_WORKER_THREAD = None
_WORKER_LOCK = threading.Lock()


def _ensure_worker_started():
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD is None or not _WORKER_THREAD.is_alive():
            _WORKER_THREAD = threading.Thread(target=_auth_worker_loop, daemon=True, name="PlaywrightAuthWorker")
            _WORKER_THREAD.start()


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


def _find_otp_input(page):
    """
    Tìm ô nhập mã OTP trên giao diện CAS với nhiều chiến lược dự phòng.
    Ưu tiên cao nhất cho input chuẩn của CAS VNPT: #passOTP hoặc validate_pass_otp.
    """
    candidates = [
        "input#passOTP", "input[name='validate_pass_otp']",
        "input#otp", "input[name='otp']",
        "input#token", "input[name='token']",
        "input#code", "input[name='code']",
        "input#passcode", "input[name='passcode']",
        "input[name='otpToken']", "input[name='smsCode']",
        "input[name='credential']", "input[name='twoFactorCode']",
        "input[placeholder*='OTP' i]", "input[placeholder*='otp' i]",
        "input[placeholder*='mã' i]", "input[placeholder*='Mã' i]",
    ]
    for sel in candidates:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el
        except Exception:
            pass

    # Tìm tất cả input có thể nhập liệu không phải username hay password
    try:
        all_inputs = page.query_selector_all("input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='checkbox']):not([type='radio'])")
        for inp in all_inputs:
            try:
                inp_id = (inp.get_attribute("id") or "").lower()
                inp_name = (inp.get_attribute("name") or "").lower()
                inp_type = (inp.get_attribute("type") or "").lower()
                if "username" in inp_id or "username" in inp_name:
                    continue
                if "password" in inp_id or "password" in inp_name or inp_type == "password":
                    continue
                if inp.is_visible():
                    return inp
            except Exception:
                pass
    except Exception:
        pass

    return None


def _submit_otp_form(page, otp_input, otp_code: str = "") -> bool:
    """
    Điền mã OTP và submit form xác thực CAS.
    Khắc phục triệt để lỗi JavaScript của CAS VNPT:
    - VNPT CAS có nút: <button onclick="javascript:return submitForm(this)">
    - Trong submitForm(e): e.preventDefault() bị lỗi Uncaught TypeError vì e là HTMLButtonElement (không phải event)
    - Giải pháp: Gán prototype preventDefault cho HTMLButtonElement và gọi form.submit() trực tiếp qua page.evaluate!
    """
    # 1. Tự động chấp nhận mọi dialog alert() để không chặn luồng Playwright
    try:
        page.on("dialog", lambda dialog: dialog.accept())
    except Exception:
        pass

    # 2. Điền input và kích hoạt submit bằng JavaScript với độ tương thích tuyệt đối
    submitted_via_js = False
    try:
        submitted_via_js = page.evaluate("""(code) => {
            // Khắc phục bug e.preventDefault() trên trang CAS VNPT
            if (typeof HTMLButtonElement !== 'undefined' && !HTMLButtonElement.prototype.preventDefault) {
                HTMLButtonElement.prototype.preventDefault = function() {};
            }
            if (typeof HTMLElement !== 'undefined' && !HTMLElement.prototype.preventDefault) {
                HTMLElement.prototype.preventDefault = function() {};
            }

            // Tìm ô nhập OTP
            const inp = document.getElementById('passOTP') || 
                        document.querySelector("input[name='validate_pass_otp']") ||
                        document.querySelector("input#otp, input[name='otp'], input#token, input[name='token']") ||
                        document.querySelector("input[placeholder*='OTP' i], input[placeholder*='otp' i]");
            if (inp) {
                inp.value = code;
                inp.dispatchEvent(new Event('input', { bubbles: true }));
                inp.dispatchEvent(new Event('change', { bubbles: true }));
            }

            // Tìm form
            const form = document.getElementById('loginForm') || 
                         document.loginForm || 
                         (inp ? inp.closest('form') : null) || 
                         document.forms[0];
            if (form) {
                console.log('[AuthWorker] Đang gọi form.submit() trực tiếp');
                form.submit();
                return true;
            }
            return false;
        }""", otp_code)
    except Exception as ex:
        print(f"[OTP Step 2] Lỗi JS submit: {ex}")

    if submitted_via_js:
        return True

    # 3. Dự phòng: Bấm nút nếu JS submit không tìm thấy form
    btn_candidates = [
        "button:has-text('ĐĂNG NHẬP')",
        "button:has-text('Đăng nhập')",
        "button[type='submit']",
        "input[type='submit']",
        "input[value*='ĐĂNG NHẬP']",
        "input[value*='Đăng nhập']",
        "input[value*='LOGIN']",
        "button:has-text('Xác nhận')",
        "button:has-text('Tiếp tục')",
        "#submit",
        ".btn-submit",
    ]
    for b_sel in btn_candidates:
        try:
            b = page.query_selector(b_sel)
            if b and b.is_visible():
                b.click()
                return True
        except Exception:
            pass

    # Thử Enter trên input
    if otp_input:
        try:
            otp_input.press("Enter")
            return True
        except Exception:
            pass

    return False


def _worker_step1(browser, active_sessions: dict, username: str, password: str, timeout: int = 15, system: str = "tts_old") -> dict:
    username = (username or "").strip()
    password = (password or "").strip()
    system = "tts_new" if system == "tts_new" else "tts_old"

    if not username or not password:
        return {"success": False, "error": "Vui lòng nhập đầy đủ tài khoản và mật khẩu."}

    session_id = str(uuid.uuid4())

    try:
        context = browser.new_context()
        page = context.new_page()

        # 1. Mở trang đăng nhập CAS tương ứng
        if system == "tts_new":
            start_url = "https://id.vnpt.com.vn/cas/login?service=https://oneoss.vnpt.vn/sso"
        else:
            start_url = "https://tts.vnpt.vn/"

        try:
            page.goto(start_url, timeout=20000)
        except Exception as ex:
            context.close()
            return {"success": False, "error": f"Không thể kết nối máy chủ xác thực: {ex}"}

        # 2. Đợi form đăng nhập
        try:
            page.wait_for_selector("#username", timeout=8000)
        except Exception:
            if system == "tts_new":
                tok = page.evaluate("() => localStorage.getItem('TOKEN')")
                if tok:
                    context.close()
                    return {"success": True, "token": tok, "ttsnew_token": tok, "user": {"username": username, "displayName": username}}
            else:
                tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
                if tok:
                    u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                    context.close()
                    return {"success": True, "token": tok, "user": _decode_user_str(u_str)}
            context.close()
            return {"success": False, "error": "Không tìm thấy form đăng nhập."}

        # 3. Điền tài khoản và mật khẩu
        page.fill("#username", username)
        page.fill("#password", password)
        try:
            page.click("button[type='submit'], input[type='submit'], .btn-login, button.btn-primary")
        except Exception:
            page.press("#password", "Enter")

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
                            if any(k in txt.lower() for k in ["không thành công", "kiểm tra tên đăng nhập", "không đúng", "sai"]):
                                context.close()
                                return {"success": False, "error": "Sai tên đăng nhập hoặc mật khẩu!"}
                            if "khóa" in txt.lower() or "lock" in txt.lower():
                                context.close()
                                return {"success": False, "error": f"Tài khoản bị khóa: {txt}"}
            except Exception:
                pass

            # B. Kiểm tra nếu đã có token ngay (không bị yêu cầu OTP)
            try:
                if system == "tts_new":
                    curr_url = page.url.lower()
                    if "oneoss.vnpt.vn" in curr_url or "tts.vnptnet.vn" in curr_url:
                        tok = page.evaluate("() => localStorage.getItem('TOKEN')")
                        if tok and len(tok) > 20:
                            context.close()
                            return {
                                "success": True,
                                "token": tok,
                                "ttsnew_token": tok,
                                "user": {"username": username, "displayName": username}
                            }
                else:
                    tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
                    if tok:
                        u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                        ttsnew_tok = ""
                        try:
                            p_new = context.new_page()
                            p_new.goto("https://id.vnpt.com.vn/cas/login?service=https://oneoss.vnpt.vn/sso", timeout=15000, wait_until="domcontentloaded")
                            for _ in range(12):
                                time.sleep(0.7)
                                ttsnew_tok = p_new.evaluate("() => localStorage.getItem('TOKEN')")
                                if ttsnew_tok and len(ttsnew_tok) > 20:
                                    break
                            p_new.close()
                        except Exception:
                            pass

                        context.close()
                        return {
                            "success": True,
                            "token": tok,
                            "ttsnew_token": ttsnew_tok or "",
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
                has_otp_input = bool(page.query_selector("input#passOTP, input[name='validate_pass_otp'], input#otp, input[name='otp'], input#token, input[name='token'], input[placeholder*='OTP'], input[placeholder*='otp']"))

                if has_otp_in_url or has_otp_in_text or has_otp_input:
                    import re
                    phone = ""
                    pm = re.search(r'(0\d{9,10}|\d{4}\*{3}\d{3})', content)
                    if pm:
                        phone = pm.group(0)

                    active_sessions[session_id] = {
                        "context": context,
                        "page": page,
                        "username": username,
                        "phone": phone,
                        "system": system,
                        "created_at": time.time()
                    }
                    print(f"[AuthWorker] Đã tạo phiên chờ OTP [{system}]: {session_id[:8]} cho user: {username}")
                    return {
                        "success": False,
                        "otp_required": True,
                        "session_id": session_id,
                        "username": username,
                        "phone": phone,
                        "system": system,
                        "message": f"Mã xác thực OTP của bạn hiện đã được gửi đến số điện thoại: {phone}" if phone else "Mã xác thực OTP đã được gửi đến số điện thoại của bạn."
                    }
            except Exception:
                pass

        # Hết thời gian chờ mà chưa có token cũng chưa phát hiện OTP
        active_sessions[session_id] = {
            "context": context,
            "page": page,
            "username": username,
            "system": system,
            "created_at": time.time()
        }
        return {
            "success": False,
            "otp_required": True,
            "session_id": session_id,
            "system": system,
            "message": "Vui lòng nhập mã OTP để hoàn tất đăng nhập."
        }

    except Exception as ex:
        return {"success": False, "error": f"Lỗi hệ thống đăng nhập: {str(ex)}"}


def _worker_step2(active_sessions: dict, session_id: str, otp_code: str, timeout: int = 30) -> dict:
    session = active_sessions.get(session_id)
    if not session:
        return {"success": False, "error": "Phiên đăng nhập đã hết hạn hoặc không tồn tại. Vui lòng bấm Đăng nhập lại."}

    page = session["page"]
    context = session["context"]
    username = session["username"]
    system = session.get("system", "tts_old")
    otp_code = (otp_code or "").strip()

    print(f"[OTP Step 2] Bắt đầu xác thực OTP [{system}] cho user: {username}, session: {session_id[:8]}...")
    print(f"[OTP Step 2] Trang hiện tại: {page.url}")

    try:
        # 1. Tìm ô nhập OTP và điền mã nếu có
        otp_input = _find_otp_input(page)
        if otp_code:
            if otp_input:
                try:
                    inp_name = otp_input.get_attribute("name") or otp_input.get_attribute("id") or "unnamed"
                    print(f"[OTP Step 2] Đã tìm thấy ô nhập OTP ({inp_name}), tiến hành điền: {otp_code}...")
                    otp_input.fill("")
                    otp_input.fill(otp_code)
                    time.sleep(0.2)
                except Exception as ex:
                    print(f"[OTP Step 2] Lỗi khi điền OTP qua locator: {ex}")
            else:
                print("[OTP Step 2] CẢNH BÁO: Locator không tìm thấy ô nhập OTP, sẽ thử submit trực tiếp qua JS.")

            # 2. Bấm nút submit / gọi form.submit()
            submitted = _submit_otp_form(page, otp_input, otp_code)
            print(f"[OTP Step 2] Đã kích hoạt submit: {submitted}")

        # 3. Chờ token xuất hiện trong localStorage / sessionStorage hoặc phát hiện thông báo lỗi
        start_time = time.time()
        token = ""
        user_info = {}
        last_url = page.url

        while time.time() - start_time < timeout:
            time.sleep(0.6)

            # A. Kiểm tra thông báo lỗi từ CAS
            try:
                alerts = page.query_selector_all(".alert, .errors, #status, div[role='alert'], #msg, .error, .text-danger, .has-error")
                for a in alerts:
                    if a.is_visible():
                        txt = a.inner_text().strip()
                        if any(k in txt.lower() for k in ["không đúng", "sai", "hết hạn", "invalid", "thất bại", "không hợp lệ"]):
                            print(f"[OTP Step 2] Phát hiện lỗi CAS: {txt}")
                            return {"success": False, "error": f"Lỗi xác thực: {txt}"}
            except Exception:
                pass

            # B. Theo dõi URL thay đổi
            try:
                curr_url = page.url.lower()
                if curr_url != last_url:
                    last_url = curr_url
                    print(f"[OTP Step 2] URL chuyển sang: {curr_url}")
            except Exception:
                pass

            # C. Kiểm tra token theo hệ thống tương ứng
            try:
                if system == "tts_new":
                    curr_url = page.url.lower()
                    # Sau khi CAS chấp nhận OTP, CAS redirect sang https://oneoss.vnpt.vn/sso?ticket=ST-...
                    # OneOSS Angular app tải xong sẽ lưu token vào localStorage
                    if "oneoss.vnpt.vn" in curr_url or "tts.vnptnet.vn" in curr_url:
                        tok = page.evaluate("() => localStorage.getItem('TOKEN')")
                        if tok and len(tok) > 20:
                            token = tok
                            user_info = {"username": username, "displayName": username}
                            print(f"[OTP Step 2] [TTS Mới] Thành công! Đã lấy được TOKEN: {token[:15]}...")
                            break
                else:
                    tok = page.evaluate("() => localStorage.getItem('scnntttoken') || sessionStorage.getItem('scnntttoken')")
                    if tok and len(tok) > 10:
                        token = tok
                        u_str = page.evaluate("() => localStorage.getItem('userInfo') || sessionStorage.getItem('userInfo')")
                        user_info = _decode_user_str(u_str)
                        print(f"[OTP Step 2] [TTS Cũ] Thành công! Đã lấy được scnntttoken: {token[:15]}...")
                        break
            except Exception:
                pass

        if token:
            ttsnew_tok = ""
            if system == "tts_new":
                ttsnew_tok = token
                # Đưa token sang domain tts.vnptnet.vn để đồng bộ hoàn toàn
                try:
                    p_tts = context.new_page()
                    p_tts.goto("https://tts.vnptnet.vn/", timeout=10000)
                    p_tts.evaluate("""(tok, u) => {
                        localStorage.setItem('TOKEN', tok);
                        localStorage.setItem('USER_INFO', JSON.stringify({userName: u, name: u}));
                    }""", token, username)
                    p_tts.close()
                except Exception:
                    pass
            else:
                # Đăng nhập TTS Cũ thành công -> Mượn CAS session để lấy luôn Bearer token cho TTS Mới
                try:
                    p_new = context.new_page()
                    p_new.goto("https://id.vnpt.com.vn/cas/login?service=https://oneoss.vnpt.vn/sso", timeout=15000, wait_until="domcontentloaded")
                    for _ in range(15):
                        time.sleep(0.7)
                        ttsnew_tok = p_new.evaluate("() => localStorage.getItem('TOKEN')")
                        if ttsnew_tok and len(ttsnew_tok) > 20:
                            print(f"[OTP Step 2] Đã tự động lấy luôn token TTS Mới: {ttsnew_tok[:15]}...")
                            break
                    p_new.close()
                except Exception as ex:
                    print(f"[OTP Step 2] Lưu ý khi lấy token TTS Mới: {ex}")

            try:
                context.close()
            except Exception:
                pass
            active_sessions.pop(session_id, None)
            return {
                "success": True,
                "token": token,
                "ttsnew_token": ttsnew_tok or "",
                "system": system,
                "user": user_info or {"TaiKhoan": username, "HoTen": username}
            }
        else:
            # Lưu snapshot để phân tích nguyên nhân nếu thất bại
            try:
                import os
                os.makedirs("scratch", exist_ok=True)
                page.screenshot(path="scratch/otp_failed_snapshot.png")
                with open("scratch/otp_failed_dom.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"[OTP Step 2] Thất bại - Đã lưu snapshot tại scratch/otp_failed_snapshot.png. URL: {page.url}")
            except Exception as snap_ex:
                print(f"[OTP Step 2] Không thể lưu snapshot: {snap_ex}")

            # Kiểm tra text trong body xem có thông báo lỗi cụ thể
            try:
                body_txt = page.inner_text("body").lower()
                for err_k in ["không đúng", "sai", "hết hạn", "không hợp lệ", "thất bại"]:
                    if err_k in body_txt:
                        return {"success": False, "error": "Mã OTP không chính xác hoặc đã hết hạn. Vui lòng kiểm tra lại."}
            except Exception:
                pass

            return {
                "success": False,
                "error": "Xác thực OTP không thành công hoặc hết thời gian chờ từ máy chủ CAS. Vui lòng thử lại."
            }

    except Exception as ex:
        print(f"[OTP Step 2] Ngoại lệ hệ thống: {ex}")
        return {"success": False, "error": f"Lỗi xử lý xác thực OTP: {str(ex)}"}


def _auth_worker_loop():
    """
    Dedicated worker thread nơi Playwright duy nhất được khởi tạo và chạy.
    Mọi Page, Context, Event Loop đều gắn cố định với thread này.
    """
    print("[AuthWorker] Khởi tạo luồng xử lý Playwright chuyên biệt...")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            active_sessions = {}

            print("[AuthWorker] Playwright Browser đã sẵn sàng nhận lệnh.")
            while True:
                try:
                    # Dọn dẹp session quá hạn (> 180s)
                    now = time.time()
                    expired = [sid for sid, s in active_sessions.items() if now - s.get("created_at", 0) > 180]
                    for sid in expired:
                        s = active_sessions.pop(sid, None)
                        if s and "context" in s:
                            try:
                                s["context"].close()
                            except Exception:
                                pass

                    # Nhận job từ queue
                    try:
                        job = _JOB_QUEUE.get(timeout=0.5)
                    except queue.Empty:
                        continue

                    if job is None:
                        break

                    action = job.get("action")
                    args = job.get("args", {})
                    res_q = job.get("res_q")

                    if action == "step1":
                        res = _worker_step1(browser, active_sessions, args.get("username", ""), args.get("password", ""), args.get("timeout", 15), args.get("system", "tts_old"))
                        res_q.put(res)
                    elif action == "step2":
                        res = _worker_step2(active_sessions, args.get("session_id", ""), args.get("otp_code", ""), args.get("timeout", 25))
                        res_q.put(res)
                    else:
                        res_q.put({"success": False, "error": f"Hành động không hợp lệ: {action}"})

                except Exception as ex:
                    print(f"[AuthWorker] Ngoại lệ trong vòng lặp worker: {ex}")
    except Exception as fatal_ex:
        print(f"[AuthWorker] Lỗi nghiêm trọng: {fatal_ex}")


def authenticate_tts_step1(username: str, password: str, timeout: int = 15, system: str = "tts_old") -> dict:
    """
    Bước 1: Gửi thông tin tài khoản & mật khẩu lên hệ thống CAS TTS qua Dedicated Worker Thread.
    """
    _ensure_worker_started()
    res_q = queue.Queue()
    _JOB_QUEUE.put({
        "action": "step1",
        "args": {"username": username, "password": password, "timeout": timeout, "system": system},
        "res_q": res_q
    })
    try:
        return res_q.get(timeout=timeout + 10)
    except queue.Empty:
        return {"success": False, "error": "Quá thời gian kết nối tới dịch vụ xác thực máy chủ."}


def authenticate_tts_step2_otp(session_id: str, otp_code: str, timeout: int = 25) -> dict:
    """
    Bước 2: Gửi mã OTP vào phiên CAS đang chờ qua Dedicated Worker Thread.
    """
    _ensure_worker_started()
    res_q = queue.Queue()
    _JOB_QUEUE.put({
        "action": "step2",
        "args": {"session_id": session_id, "otp_code": otp_code, "timeout": timeout},
        "res_q": res_q
    })
    try:
        return res_q.get(timeout=timeout + 10)
    except queue.Empty:
        return {"success": False, "error": "Quá thời gian xử lý mã xác thực OTP từ máy chủ CAS."}
