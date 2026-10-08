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


def _submit_otp_form(page, otp_input, otp_code: str = "", dialog_holder: list = None) -> bool:
    """
    Điền mã OTP và submit form xác thực CAS.
    Khắc phục triệt để lỗi JavaScript của CAS VNPT:
    - VNPT CAS có nút: <button onclick="javascript:return submitForm(this)">
    - Bắt sự kiện dialog để lấy ngay thông báo lỗi nếu CAS gọi alert()
    """
    if dialog_holder is not None:
        def _on_dialog(d):
            msg = d.message
            print(f"[OTP Dialog] Nhận dialog alert từ CAS: {msg}")
            dialog_holder.append(msg)
            try:
                d.accept()
            except Exception:
                pass
        try:
            page.on("dialog", _on_dialog)
        except Exception:
            pass

    # 1. Điền input và kích hoạt submit qua JS (vá lỗi e.preventDefault của CAS và submit form trực tiếp)
    submitted = False
    try:
        js_res = page.evaluate("""(code) => {
            // A. Điền mã OTP vào ô input
            const inps = Array.from(document.querySelectorAll("input#passOTP, input[name='validate_pass_otp'], input#otp, input[name='otp'], input[placeholder*='OTP'], input[placeholder*='otp'], input[type='text'], input[type='number']"));
            let mainInp = inps.find(i => (i.id === 'passOTP' || i.name === 'validate_pass_otp')) || inps[0];
            if (mainInp) {
                mainInp.value = code;
                mainInp.setAttribute('value', code);
                mainInp.dispatchEvent(new Event('input', { bubbles: true }));
                mainInp.dispatchEvent(new Event('change', { bubbles: true }));
            }
            const elPass = document.getElementById('passOTP');
            if (elPass) {
                elPass.value = code;
                elPass.setAttribute('value', code);
            }

            // B. Vá lỗi hàm submitForm của CAS (khi nút bấm gọi submitForm(this), this là Button element khiến e.preventDefault() bị crash)
            window.submitForm = function(el) {
                try { if (el && typeof el.preventDefault === 'function') el.preventDefault(); } catch(err) {}
                try { if (document.loginForm) { document.loginForm.submit(); return true; } } catch(err) {}
                try { const f = document.querySelector('form'); if (f) { f.submit(); return true; } } catch(err) {}
                return false;
            };

            // C. Kích hoạt submit form ngay lập tức qua JS DOM
            let done = false;
            try {
                if (document.loginForm && typeof document.loginForm.submit === 'function') {
                    document.loginForm.submit();
                    done = true;
                }
            } catch(e) {}
            if (!done) {
                try {
                    const f = document.getElementById('loginForm') || document.querySelector('form');
                    if (f && typeof f.submit === 'function') {
                        f.submit();
                        done = true;
                    }
                } catch(e) {}
            }
            return done;
        }""", otp_code)
        if js_res:
            print("[OTP Step 2] Đã kích hoạt form.submit() trực tiếp qua JS thành công! Bỏ qua các bước click phụ để tránh xung đột navigation.", flush=True)
            return True
    except Exception as ex:
        print(f"[OTP Step 2] Lỗi JS điền/submit OTP: {ex}", flush=True)

    # 2. CHỈ FALLBACK KHI JS SUBMIT THẤT BẠI:
    try:
        btn = page.locator("button:has-text('OK'), input[value='OK'], input[type='submit'], button[type='submit']").first
        if btn.is_visible(timeout=1000):
            print("[OTP Step 2] Fallback: Đang bấm nút Submit...", flush=True)
            btn.click(timeout=1500, no_wait_after=True)
            return True
    except Exception:
        pass

    if otp_input:
        try:
            print("[OTP Step 2] Fallback: Nhấn Enter trên ô nhập OTP...", flush=True)
            otp_input.press("Enter", timeout=1500, no_wait_after=True)
            return True
        except Exception:
            pass

    return True


def _extract_cem_key_and_cookies(page, context, captured_req_holder: dict = None) -> tuple:
    """
    Trích xuất triệt để API Key và Cookies của CEM VNPT Media với 5 lớp bảo đảm:
    1. Lấy từ request listener (bắt trúng header 'apikey' / 'authorization' khi React gọi API)
    2. Lấy từ cookies in-memory (tìm cookie 'apikey' hoặc cookie có value chứa 'net_ktm_')
    3. Lấy từ document.cookie
    4. Lấy từ localStorage (duyệt toàn bộ key/value, tìm regex net_ktm_)
    5. Lấy từ sessionStorage
    """
    import urllib.parse, re
    api_key = None
    cookies_dict = {}

    # 1. Bắt trực tiếp từ request listener nếu có
    if captured_req_holder and captured_req_holder.get("key"):
        api_key = captured_req_holder["key"]

    # 2. Quét cookies trong context
    try:
        all_c = context.cookies()
        for c in all_c:
            cookies_dict[c["name"]] = c["value"]
            c_name_lower = c["name"].lower()
            c_val = c.get("value", "")
            if not api_key:
                if c_name_lower in ("apikey", "api_key"):
                    api_key = c_val
                elif "net_ktm_" in c_val:
                    api_key = c_val
    except Exception:
        pass

    # 3. Quét document.cookie
    if not api_key:
        try:
            raw_c = page.evaluate("() => document.cookie")
            if raw_c:
                m = re.search(r'apikey=([^;]+)', raw_c, re.I)
                if m:
                    api_key = m.group(1).strip()
                else:
                    m2 = re.search(r'(net_ktm_[^;]+)', raw_c)
                    if m2:
                        api_key = m2.group(1).strip()
        except Exception:
            pass

    # 4. Quét toàn bộ localStorage & sessionStorage (kể cả JSON trong storage)
    if not api_key:
        try:
            api_key = page.evaluate("""() => {
                function scanStorage(storage) {
                    if (!storage) return null;
                    for (let i = 0; i < storage.length; i++) {
                        const k = storage.key(i);
                        const v = storage.getItem(k) || '';
                        if (k.toLowerCase().includes('apikey') || k.toLowerCase().includes('api_key')) {
                            if (v.length > 10) return v;
                        }
                        if (v.includes('net_ktm_')) {
                            const m = v.match(/net_ktm_[A-Za-z0-9_%-]+/);
                            if (m) return m[0];
                            return v;
                        }
                    }
                    return null;
                }
                return scanStorage(window.localStorage) || scanStorage(window.sessionStorage);
            }""")
        except Exception:
            pass

    if api_key:
        api_key = str(api_key).strip()
        while "%25" in api_key:
            api_key = urllib.parse.unquote(api_key)
        if api_key.startswith('"') and api_key.endswith('"'):
            api_key = api_key[1:-1]
        if len(api_key) > 10:
            return api_key, cookies_dict

    return None, cookies_dict


def _worker_step1(browser, active_sessions: dict, username: str, password: str, timeout: int = 15, system: str = "tts_new") -> dict:
    username = (username or "").strip()
    password = (password or "").strip()
    system = str(system or "tts_new").strip().lower()
    print(f"[AuthWorker] 🚀 [BƯỚC 1] Bắt đầu xử lý đăng nhập Playwright: system={system}, user={username}...", flush=True)

    if not username or not password:
        return {"success": False, "error": "Vui lòng nhập đầy đủ tài khoản và mật khẩu."}

    session_id = str(uuid.uuid4())
    print(f"[AuthWorker] 🆔 [BƯỚC 1] Đã khởi tạo session_id={session_id[:8]}...", flush=True)

    try:
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        captured_network_key = {"key": ""}
        def _on_net_req(req):
            try:
                hdr_k = req.headers.get("apikey") or req.headers.get("api-key") or req.headers.get("authorization") or ""
                if hdr_k:
                    if hdr_k.startswith("Bearer "):
                        hdr_k = hdr_k[7:].strip()
                    if "net_ktm_" in hdr_k or len(hdr_k) > 20:
                        captured_network_key["key"] = hdr_k
                if "apikey=" in req.url:
                    import re
                    m = re.search(r'apikey=([^&]+)', req.url)
                    if m:
                        captured_network_key["key"] = m.group(1).strip()
            except Exception:
                pass
        try:
            page.on("request", _on_net_req)
        except Exception:
            pass

        # Mở trang đăng nhập CAS tương ứng
        if system == "tts_new":
            start_url = "https://id.vnpt.com.vn/cas/login?service=https://oneoss.vnpt.vn/sso"
        elif system == "btools":
            start_url = "https://id.vnpt.com.vn/cas/login?service=http%3A%2F%2F10.159.21.241%3A9267%2FB_tools_v2%2F&customLogin=custom&customLoginPage=http://10.159.21.241:9267/B_tools_v2/caslogin.jsp"
        elif system == "cem":
            start_url = "https://id.vnpt.com.vn/cas/login?service=https://cem.vnptmedia.vn"
        elif system == "sapc":
            start_url = "http://10.155.42.218/Account/Login"
        elif system == "ccos":
            start_url = "https://id.vnpt.com.vn/cas/login?service=http%3a%2f%2floginccos.vnpt.vn%2fLogin.aspx%3fIsOtherApp%3d1%26Key%3d10019%26Url%3dhttp%3a%2f%2fgqknccos.vnpt.vn"
        else:
            start_url = "https://tts.vnpt.vn/"

        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=25000)
        except Exception:
            try:
                page.goto(start_url, wait_until="commit", timeout=20000)
            except Exception as ex:
                context.close()
                return {"success": False, "error": f"Không thể kết nối máy chủ xác thực ({start_url}): {ex}"}

        # Nếu là CEM và đang ở trang React có nút "Login with VNPT email", bấm để chuyển sang CAS
        if system == "cem":
            try:
                btn = page.locator("button:has-text('Login with VNPT email')")
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

        # 2. Đợi form đăng nhập
        user_input_sel = None
        for sel in ["#username", "#UserName", "input[name='username']", "input[name='UserName']", "input#name", "input[name='j_username']", "input[name='txtUser']", "input[type='text']"]:
            try:
                el = page.wait_for_selector(sel, timeout=3000)
                if el and el.is_visible():
                    user_input_sel = sel
                    break
            except Exception:
                pass

        if not user_input_sel:
            if system == "tts_new":
                tok = page.evaluate("() => localStorage.getItem('TOKEN')")
                if tok:
                    context.close()
                    return {"success": True, "token": tok, "ttsnew_token": tok, "user": {"username": username, "displayName": username}}
            elif system == "btools":
                cookies = context.cookies(["http://10.159.21.241:9267/B_tools_v2/", "http://10.159.21.241:9267/"])
                jsession = next((c["value"] for c in cookies if c["name"] == "JSESSIONID"), "")
                if jsession:
                    from btools_manager import save_btools_cookie
                    save_btools_cookie(jsession, verify=False)
                    context.close()
                    return {"success": True, "token": jsession, "system": "btools", "user": {"username": username}}
            elif system == "cem":
                tok = None
                try:
                    for c in context.cookies():
                        if c["name"].lower() in ("apikey", "api_key") and c.get("value"):
                            tok = c["value"]
                            break
                except Exception:
                    pass
                if not tok:
                    try:
                        tok = page.evaluate("() => localStorage.getItem('apikey') || localStorage.getItem('token') || localStorage.getItem('API_KEY')")
                    except Exception:
                        pass
                if tok:
                    context.close()
                    return {"success": True, "token": tok, "system": "cem", "user": {"username": username}}
            elif system == "sapc":
                cookies = context.cookies(["http://10.155.42.218/"])
                app_cookie = next((c["value"] for c in cookies if c["name"] == ".AspNet.ApplicationCookie"), "")
                if app_cookie:
                    context.close()
                    return {"success": True, "token": app_cookie, "system": "sapc", "user": {"username": username}}
            elif system == "ccos":
                cookies = context.cookies(["http://gqknccos.vnpt.vn/", "http://loginccos.vnpt.vn/"])
                c_dict = {c["name"]: c["value"] for c in cookies if c["name"] in ("SessionDB", "SESSIONID")}
                if c_dict and ("SessionDB" in c_dict or "SESSIONID" in c_dict):
                    context.close()
                    return {"success": True, "token": c_dict.get("SessionDB") or c_dict.get("SESSIONID"), "system": "ccos", "user": {"username": username}}
            else:
                tok = page.evaluate("() => localStorage.getItem('scnntttoken')")
                if tok:
                    u_str = page.evaluate("() => localStorage.getItem('userInfo')")
                    context.close()
                    return {"success": True, "token": tok, "user": _decode_user_str(u_str)}
            context.close()
            return {"success": False, "error": "Không tìm thấy form đăng nhập trên máy chủ."}

        # 3. Điền tài khoản và mật khẩu
        page.fill(user_input_sel, username)
        pass_input_sel = "input[type='password']"
        try:
            page.fill(pass_input_sel, password)
        except Exception:
            page.fill("#password", password)

        try:
            page.click("button[type='submit'], input[type='submit'], .btn-login, button.btn-primary, #submit, button:has-text('Đăng nhập')")
        except Exception:
            page.press(pass_input_sel, "Enter")

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
                            try:
                                from ttsnew_api import save_cached_token
                                save_cached_token(tok)
                            except Exception:
                                pass

                            context.close()
                            return {
                                "success": True,
                                "token": tok,
                                "ttsnew_token": tok,
                                "user": {"username": username, "displayName": username}
                            }
                elif system == "sapc":
                    cookies = context.cookies(["http://10.155.42.218/"])
                    app_cookie = next((c["value"] for c in cookies if c["name"] == ".AspNet.ApplicationCookie"), "")
                    if app_cookie:
                        import json
                        from pathlib import Path
                        base_sapc_dir = Path(__file__).resolve().parent.parent / "sapccheck"
                        c_list = [{
                            "name": c["name"],
                            "value": c["value"],
                            "domain": c.get("domain", "10.155.42.218"),
                            "path": c.get("path", "/")
                        } for c in cookies if "10.155.42.218" in c.get("domain", "")]
                        try:
                            with open(base_sapc_dir / "sapc_cookies.json", "w", encoding="utf-8") as f:
                                json.dump(c_list, f, indent=2, ensure_ascii=False)
                            with open(base_sapc_dir / "cookies.json", "w", encoding="utf-8") as f:
                                json.dump(c_list, f, indent=2, ensure_ascii=False)
                        except Exception as e_sapc:
                            print(f"[SAPC Cookie Save Error]: {e_sapc}")
                        context.close()
                        return {
                            "success": True,
                            "token": app_cookie,
                            "system": "sapc",
                            "user": {"username": username, "displayName": username}
                        }
                    err_el = page.query_selector(".validation-summary-errors, .field-validation-error, .text-danger")
                    if err_el and err_el.is_visible():
                        err_txt = err_el.inner_text().strip()
                        if err_txt:
                            context.close()
                            return {"success": False, "error": f"Lỗi đăng nhập SAPC: {err_txt}"}
                elif system == "cem":
                    cem_k, c_dict = _extract_cem_key_and_cookies(page, context, captured_network_key)
                    if cem_k:
                        from pathlib import Path
                        import json
                        cem_cache_file = Path(__file__).resolve().parent.parent / "cem_auth_cache.json"
                        with open(cem_cache_file, "w", encoding="utf-8") as f:
                            json.dump({"api_key": cem_k, "apikey": cem_k, "cookies": c_dict, "updated_at": time.time(), "timestamp": time.time()}, f, ensure_ascii=False, indent=2)
                        context.close()
                        return {
                            "success": True,
                            "token": cem_k,
                            "system": "cem",
                            "user": {"username": username, "displayName": username}
                        }
                elif system == "btools":
                    all_cookies = context.cookies()
                    jsession = next((c["value"] for c in all_cookies if c["name"] == "JSESSIONID" and ("10.159.21.241" in c.get("domain", "") or "/b_tools_v2" in c.get("path", "").lower())), "")
                    if jsession:
                        from btools_manager import save_btools_cookie
                        save_btools_cookie(jsession, verify=False)
                        context.close()
                        return {
                            "success": True,
                            "token": jsession,
                            "system": "btools",
                            "user": {"username": username, "displayName": username}
                        }
                elif system == "ccos":
                    curr_url = page.url.lower()
                    if "gqknccos.vnpt.vn" in curr_url or "loginccos.vnpt.vn" in curr_url:
                        cookies = context.cookies(["http://gqknccos.vnpt.vn/", "http://loginccos.vnpt.vn/"])
                        c_dict = {c["name"]: c["value"] for c in cookies if c["name"] in ("SessionDB", "SESSIONID")}
                        if c_dict and ("SessionDB" in c_dict or "SESSIONID" in c_dict):
                            from ccos_client import save_ccos_cache
                            save_ccos_cache(c_dict)
                            context.close()
                            return {
                                "success": True,
                                "token": c_dict.get("SessionDB") or c_dict.get("SESSIONID"),
                                "system": "ccos",
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
                    print(f"[AuthWorker] 📲 [BƯỚC 1] Đã tạo phiên chờ OTP [{system}]: session_id={session_id[:8]} cho user: {username}, SĐT: {phone or 'N/A'}", flush=True)
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
        print(f"[AuthWorker] ⚠️ [BƯỚC 1] Hết thời gian chờ ban đầu ({timeout}s), mở phiên chờ OTP [{system}]: session_id={session_id[:8]}", flush=True)
        return {
            "success": False,
            "otp_required": True,
            "session_id": session_id,
            "system": system,
            "message": "Vui lòng nhập mã OTP để hoàn tất đăng nhập."
        }

    except Exception as ex:
        print(f"[AuthWorker] ❌ [BƯỚC 1] Lỗi ngoại lệ trong quá trình đăng nhập [{system}]: {ex}", flush=True)
        return {"success": False, "error": f"Lỗi hệ thống đăng nhập: {str(ex)}"}


def _worker_step2(active_sessions: dict, session_id: str, otp_code: str, timeout: int = 40) -> dict:
    otp_code = (otp_code or "").strip()
    sid_short = session_id[:8] if session_id else "Trống/None"
    print(f"[OTP Step 2] 📥 Worker nhận Step 2 OTP: session_id={sid_short}, otp={otp_code}, số phiên active hiện có={len(active_sessions)}", flush=True)

    session = active_sessions.get(session_id)
    if not session:
        print(f"[OTP Step 2] ❌ LỖI: Không tìm thấy session_id='{session_id}' trong active_sessions!", flush=True)
        print(f"[OTP Step 2] ⚠️ Danh sách session_id còn hiệu lực: {list(active_sessions.keys())}", flush=True)
        print("[OTP Step 2] 💡 Nguyên nhân: Container Docker vừa khởi động lại hoặc phiên OTP đã quá hạn 3 phút. User cần quay lại Bước 1 bấm ĐĂNG NHẬP lại để nhận OTP mới.", flush=True)
        return {"success": False, "error": "Phiên đăng nhập đã hết hạn hoặc máy chủ vừa khởi động lại. Vui lòng quay lại Bước 1 bấm Đăng nhập lại để nhận OTP mới."}

    page = session["page"]
    context = session["context"]
    username = session["username"]
    system = session.get("system", "tts_new")

    print(f"[OTP Step 2] 🚀 Bắt đầu xác thực OTP [{system}] cho user: {username}, session: {sid_short}...", flush=True)
    print(f"[OTP Step 2] 🌐 Trang hiện tại: {page.url}", flush=True)

    cas_dialog_errors = []
    captured_network_key = {"key": ""}
    def _on_net_req_step2(req):
        try:
            hdr_k = req.headers.get("apikey") or req.headers.get("api-key") or req.headers.get("authorization") or ""
            if hdr_k:
                if hdr_k.startswith("Bearer "):
                    hdr_k = hdr_k[7:].strip()
                if "net_ktm_" in hdr_k or len(hdr_k) > 20:
                    captured_network_key["key"] = hdr_k
            if "apikey=" in req.url:
                import re
                m = re.search(r'apikey=([^&]+)', req.url)
                if m:
                    captured_network_key["key"] = m.group(1).strip()
        except Exception:
            pass
    try:
        page.on("request", _on_net_req_step2)
    except Exception:
        pass

    try:
        # 1. Tìm ô nhập OTP và điền mã
        otp_input = _find_otp_input(page)
        if otp_code:
            if otp_input:
                try:
                    inp_name = otp_input.get_attribute("name") or otp_input.get_attribute("id") or "unnamed"
                    print(f"[OTP Step 2] Đã tìm thấy ô nhập OTP ({inp_name}), tiến hành điền: {otp_code}...", flush=True)
                    otp_input.fill("")
                    otp_input.fill(otp_code)
                    time.sleep(0.2)
                except Exception as ex:
                    print(f"[OTP Step 2] Lỗi khi điền OTP qua locator: {ex}", flush=True)
            else:
                print("[OTP Step 2] CẢNH BÁO: Locator không tìm thấy ô nhập OTP, sẽ thử submit trực tiếp qua JS.", flush=True)

            # 2. Bấm nút submit / gọi form.submit() kèm lắng nghe alert dialog
            submitted = _submit_otp_form(page, otp_input, otp_code, dialog_holder=cas_dialog_errors)
            print(f"[OTP Step 2] Đã kích hoạt submit OTP: {submitted}", flush=True)

        # 3. Chờ token xuất hiện trong localStorage / sessionStorage hoặc phát hiện thông báo lỗi
        # 3. Chờ token xuất hiện trong cookie / storage hoặc phát hiện thông báo lỗi
        start_time = time.time()
        token = ""
        user_info = {}
        last_url = ""
        last_log_time = 0

        while time.time() - start_time < timeout:
            time.sleep(0.5)

            # A. ƯU TIÊN SỐ 1: KIỂM TRA COOKIE TRỰC TIẾP TỪ CONTEXT (Không bao giờ bị block bởi navigation)
            try:
                all_cookies = context.cookies()
                if system == "btools":
                    jsession = ""
                    for c in all_cookies:
                        if c.get("name") == "JSESSIONID" and c.get("value"):
                            dom = c.get("domain", "").lower()
                            if "10.159.21.241" in dom or "b_tools" in c.get("path", "").lower() or ("vnpt.com.vn" not in dom and "vnpt.vn" not in dom):
                                jsession = c["value"]
                                break
                    if not jsession:
                        for c in all_cookies:
                            if c.get("name") == "JSESSIONID" and len(c.get("value", "")) > 10:
                                jsession = c["value"]
                                break
                    if jsession:
                        from btools_manager import save_btools_cookie
                        save_btools_cookie(jsession, verify=False)
                        token = jsession
                        user_info = {"username": username, "displayName": username}
                        print(f"[OTP Step 2] [BTools] ✅ THÀNH CÔNG! Đã lấy được JSESSIONID: {token[:15]}...", flush=True)
                        break
                elif system == "cem":
                    cem_k, c_dict = _extract_cem_key_and_cookies(page, context, captured_network_key)
                    if cem_k:
                        from pathlib import Path
                        import json
                        cem_cache_file = Path(__file__).resolve().parent.parent / "cem_auth_cache.json"
                        with open(cem_cache_file, "w", encoding="utf-8") as f:
                            json.dump({"api_key": cem_k, "apikey": cem_k, "cookies": c_dict, "updated_at": time.time(), "timestamp": time.time()}, f, ensure_ascii=False, indent=2)
                        token = cem_k
                        user_info = {"username": username, "displayName": username}
                        print(f"[OTP Step 2] [CEM] ✅ THÀNH CÔNG! Đã lấy API Key: {token[:15]}...", flush=True)
                        break
            except Exception:
                pass

            # B. In log tiến độ mỗi 2s để KTV theo dõi
            now_loop = time.time()
            if now_loop - last_log_time >= 2.0:
                last_log_time = now_loop
                elapsed_s = round(now_loop - start_time, 1)
                try:
                    c_url = page.url
                except Exception:
                    c_url = "navigating..."
                print(f"[OTP Step 2] [{system}] Đang chờ phản hồi ({elapsed_s}s/{timeout}s)... URL: {c_url}", flush=True)

            # C. Kiểm tra ngay nếu CAS bật alert dialog
            if cas_dialog_errors:
                last_dialog = cas_dialog_errors[-1]
                print(f"[OTP Step 2] Phát hiện dialog lỗi từ CAS: {last_dialog}", flush=True)
                return {"success": False, "error": f"CAS phản hồi: {last_dialog}"}

            # D. Kiểm tra biến error trong script của trang CAS
            try:
                cas_script_err = page.evaluate("""() => {
                    if (typeof window.error !== 'undefined' && window.error) return window.error;
                    for (const s of document.scripts) {
                        const txt = s.textContent || '';
                        const m = txt.match(/var\\s+error\\s*=\\s*['\"]([^'\"]+)['\"]/);
                        if (m) return m[1];
                    }
                    return null;
                }""")
                if cas_script_err:
                    err_map = {
                        "smsExpired": "Mã xác thực OTP đã hết hạn trên máy chủ CAS. Vui lòng bấm Đăng nhập lại để nhận mã mới.",
                        "passOtpError": "Mã xác thực OTP không chính xác. Vui lòng kiểm tra lại tin nhắn điện thoại.",
                        "passOtpEmptyError": "Chưa nhập mã xác thực OTP.",
                        "countSmsError": "Bạn đã nhập sai mã OTP quá 3 lần trên hệ thống CAS!",
                        "mobileError": "Tài khoản chưa đăng ký số điện thoại nhận OTP với quản trị.",
                        "connectServerSmsError": "Lỗi kết nối tới máy chủ gửi tin nhắn SMS của VNPT."
                    }
                    err_msg = err_map.get(cas_script_err, f"Lỗi xác thực CAS: {cas_script_err}")
                    print(f"[OTP Step 2] Nhận diện mã lỗi CAS từ script: {cas_script_err} -> {err_msg}", flush=True)
                    return {"success": False, "error": err_msg}
            except Exception:
                pass

            # E. Kiểm tra các phần tử HTML báo lỗi
            try:
                alerts = page.query_selector_all(".alert, .errors, #status, div[role='alert'], #msg, .error, .text-danger, .has-error")
                for a in alerts:
                    if a.is_visible():
                        txt = a.inner_text().strip()
                        if any(k in txt.lower() for k in ["không đúng", "sai", "hết hạn", "invalid", "thất bại", "không hợp lệ"]):
                            print(f"[OTP Step 2] Phát hiện lỗi CAS (HTML): {txt}", flush=True)
                            return {"success": False, "error": f"Lỗi xác thực: {txt}"}
            except Exception:
                pass

            # F. Kiểm tra token trong storage theo hệ thống
            try:
                if system == "tts_new":
                    curr_url = page.url.lower()
                    if "oneoss.vnpt.vn" in curr_url or "tts.vnptnet.vn" in curr_url:
                        tok = page.evaluate("() => localStorage.getItem('TOKEN')")
                        if tok and len(tok) > 20:
                            token = tok
                            user_info = {"username": username, "displayName": username}
                            print(f"[OTP Step 2] [TTS Mới] Thành công! Đã lấy được TOKEN: {token[:15]}...")
                            break
                elif system == "ccos":
                    cookies = context.cookies()
                    c_dict = {c["name"]: c["value"] for c in cookies if c["name"] in ("SessionDB", "SESSIONID")}
                    if c_dict and ("SessionDB" in c_dict or "SESSIONID" in c_dict):
                        from ccos_client import save_ccos_cache
                        save_ccos_cache(c_dict)
                        token = c_dict.get("SessionDB") or c_dict.get("SESSIONID")
                        user_info = {"username": username, "displayName": username}
                        print(f"[OTP Step 2] [CCOS] Thành công! Đã lấy Cookie: {token[:15]}...")
                        break
                elif system != "btools":
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
                try:
                    from ttsnew_api import save_cached_token
                    save_cached_token(ttsnew_tok)
                except Exception:
                    pass

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
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--ignore-certificate-errors",
                    "--allow-running-insecure-content",
                    "--disable-web-security",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote"
                ]
            )
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
                        res = _worker_step1(browser, active_sessions, args.get("username", ""), args.get("password", ""), args.get("timeout", 15), args.get("system", "tts_new"))
                        res_q.put(res)
                    elif action == "step2":
                        res = _worker_step2(active_sessions, args.get("session_id", ""), args.get("otp_code", ""), args.get("timeout", 40))
                        res_q.put(res)
                    else:
                        res_q.put({"success": False, "error": f"Hành động không hợp lệ: {action}"})

                except Exception as ex:
                    print(f"[AuthWorker] Ngoại lệ trong vòng lặp worker: {ex}")
    except Exception as fatal_ex:
        print(f"[AuthWorker] Lỗi nghiêm trọng: {fatal_ex}")


def authenticate_tts_step1(username: str, password: str, timeout: int = 15, system: str = "tts_new") -> dict:
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


def authenticate_tts_step2_otp(session_id: str, otp_code: str, timeout: int = 40) -> dict:
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
        return res_q.get(timeout=timeout + 15)
    except queue.Empty:
        return {"success": False, "error": "Quá thời gian xử lý mã xác thực OTP từ máy chủ CAS."}
