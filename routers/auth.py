# routers/auth.py
# Quản lý xác thực tài khoản KTV, phân quyền LAN/Local và OTP

import time
from fastapi import APIRouter, Request, HTTPException
from services.state import state
from services.session_manager import (
    ACTIVE_LAN_SESSIONS, 
    _save_lan_sessions, 
    resolve_ttsnew_token
)
from tts_old_api import save_cached_auth
from ttsnew_api import save_cached_token

router = APIRouter(prefix="/api", tags=["Xác thực & Phiên KTV"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@router.get("/current_user")
def get_current_user_info(request: Request):
    client_ip = _get_client_ip(request)
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")

    token = ""
    user_info = {}
    lan_ttsnew_tok = ""
    lan_ttsnew_usr = {}
    if client_ip in ACTIVE_LAN_SESSIONS:
        if time.time() - ACTIVE_LAN_SESSIONS[client_ip].get("timestamp", 0) < 86400:
            token = ACTIVE_LAN_SESSIONS[client_ip].get("token", "")
            user_info = ACTIVE_LAN_SESSIONS[client_ip].get("user", {})
        cand_tok = ACTIVE_LAN_SESSIONS[client_ip].get("ttsnew_token", "")
        from ttsnew_api import _is_jwt_valid
        if cand_tok and _is_jwt_valid(cand_tok):
            lan_ttsnew_tok = cand_tok
            lan_ttsnew_usr = ACTIVE_LAN_SESSIONS[client_ip].get("ttsnew_user", {})

    # Lấy token đang hoạt động từ máy chủ (TTS Cũ & TTS Mới)
    srv_token, srv_user = "", {}
    try:
        from tts_old_api import extract_token_from_browser as extract_old_token
        srv_token, srv_user = extract_old_token()
    except Exception:
        pass

    srv_ttsnew_token = ""
    try:
        from ttsnew_api import get_cached_token
        srv_ttsnew_token = get_cached_token()
        if not srv_ttsnew_token:
            from auth_extractor import get_universal_ttsnew_token
            srv_ttsnew_token = get_universal_ttsnew_token()
    except Exception:
        pass

    if is_local:
        if not token:
            token = srv_token
            user_info = srv_user
        client_server_token = srv_token
        client_server_ttsnew = srv_ttsnew_token
    else:
        client_server_token = ""
        client_server_ttsnew = ""

    from region_detector import is_superadmin
    auth_hdr = request.headers.get("Authorization") or ""
    client_jwt_user = {}
    if auth_hdr:
        from services.session_manager import decode_jwt
        client_jwt_user = decode_jwt(auth_hdr)

    active_user = client_jwt_user or user_info or lan_ttsnew_usr or (srv_user if is_local else {})
    is_admin = is_local or is_superadmin(active_user)

    return {
        "is_local": is_local,
        "is_admin": is_admin,
        "client_ip": client_ip,
        "has_server_token": bool(client_server_token),
        "server_user": srv_user if is_local else {},
        "server_token": client_server_token,
        "server_ttsnew_token": client_server_ttsnew,
        "token": token,
        "user": user_info or client_jwt_user,
        "ttsnew_token": client_server_ttsnew if is_local else lan_ttsnew_tok,
        "ttsnew_user": srv_user if is_local else (lan_ttsnew_usr or client_jwt_user)
    }


@router.post("/login")
async def login_tts_step1(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    system = str(body.get("system") or "tts_new").strip()
    print(f"[AUTH API] 📥 [BƯỚC 1] Nhận yêu cầu Đăng nhập: system={system}, user={username}", flush=True)

    from services.auth_tts import authenticate_tts_step1
    result = authenticate_tts_step1(username, password, system=system)

    if result.get("success"):
        client_ip = _get_client_ip(request)
        is_local = (client_ip in ("127.0.0.1", "localhost", "::1"))
        token = result.get("token", "")
        ttsnew_token = result.get("ttsnew_token", "")
        user_info = result.get("user", {})

        # KIỂM SOÁT PHÂN QUYỀN TRUY CẬP NGHIÊM NGẶT (WHITELIST)
        if system in ("tts_new", "tts_old", "tts"):
            from region_detector import is_user_permitted
            permitted, matched_u = is_user_permitted(user_info or {"username": username})
            if not permitted:
                u_disp = (user_info.get("displayName") or user_info.get("name") or user_info.get("HoTen") or username)
                print(f"[AUTH API] 🚫 Từ chối truy cập cho [{u_disp}]: Tài khoản chưa có trong danh sách phân vùng!", flush=True)
                return {
                    "success": False,
                    "message": f"Tài khoản [{u_disp}] chưa được cấp quyền truy cập WebApp. Vui lòng liên hệ Quản trị viên hệ thống để khai báo thông tin và phân vùng TT SOC."
                }
            if matched_u and isinstance(user_info, dict):
                user_info["soc"] = matched_u.get("soc", "")
                user_info["region"] = matched_u.get("region", "")

        if client_ip not in ACTIVE_LAN_SESSIONS:
            ACTIVE_LAN_SESSIONS[client_ip] = {}

        if system == "tts_new":
            tok_to_save = ttsnew_token or token
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = tok_to_save
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
            if tok_to_save:
                from region_detector import detect_user_region
                u_reg = detect_user_region(user_info)
                save_cached_token(tok_to_save, region=u_reg if u_reg in ("MN", "MT", "MB") else "MN", user_info=user_info)
        elif system == "btools":
            from btools_manager import save_btools_cookie
            save_btools_cookie(token, verify=False)
            ACTIVE_LAN_SESSIONS[client_ip]["btools_cookie"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["btools_timestamp"] = time.time()
        elif system == "cem":
            ACTIVE_LAN_SESSIONS[client_ip]["cem_apikey"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["cem_timestamp"] = time.time()
        elif system == "sapc":
            ACTIVE_LAN_SESSIONS[client_ip]["sapc_cookie"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["sapc_timestamp"] = time.time()
        elif system == "ccos":
            ACTIVE_LAN_SESSIONS[client_ip]["ccos_cookie"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["ccos_timestamp"] = time.time()
        else:
            ACTIVE_LAN_SESSIONS[client_ip]["token"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["timestamp"] = time.time()
            if is_local:
                if ttsnew_token:
                    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = ttsnew_token
                    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
                    from region_detector import detect_user_region
                    u_reg = detect_user_region(user_info)
                    save_cached_token(ttsnew_token, region=u_reg if u_reg in ("MN", "MT", "MB") else "MN", user_info=user_info)
                if token:
                    save_cached_auth(token, user_info)
        _save_lan_sessions()

        user_display = user_info.get("HoTen") or user_info.get("TaiKhoan") or user_info.get("displayName") or username
        sys_tag = "BTOOLS" if system == "btools" else ("CEM" if system == "cem" else ("SAPC" if system == "sapc" else ("CCOS" if system == "ccos" else ("TTS MỚI" if system == "tts_new" else "TTS CŨ"))))
        print(f"[AUTH API] ✅ [BƯỚC 1] Đăng nhập {sys_tag} THÀNH CÔNG cho {user_display}! (Không cần OTP)", flush=True)
        try:
            state.log("SUCCESS", f"🔑 [XÁC THỰC {sys_tag}] {user_display} (IP: {client_ip}) đã đăng nhập thành công!")
        except Exception:
            pass
        return {
            "success": True,
            "token": token or ttsnew_token,
            "ttsnew_token": ttsnew_token or token,
            "system": system,
            "user": user_info
        }
    elif result.get("otp_required"):
        sid = result.get("session_id", "")
        phone = result.get("phone", "")
        print(f"[AUTH API] 📲 [BƯỚC 1] Hệ thống [{system}] yêu cầu OTP! session_id={sid[:8] if sid else 'None'}, phone={phone}", flush=True)
        return {
            "success": False,
            "otp_required": True,
            "session_id": sid,
            "username": result.get("username", username),
            "phone": phone,
            "system": system,
            "message": result.get("message", "Vui lòng nhập mã OTP để tiếp tục.")
        }
    else:
        err = result.get("error", "Đăng nhập thất bại. Vui lòng kiểm tra lại tài khoản hoặc mật khẩu.")
        print(f"[AUTH API] ❌ [BƯỚC 1] Đăng nhập [{system}] thất bại: {err}", flush=True)
        return {
            "success": False,
            "error": err
        }


@router.post("/login/otp")
async def login_tts_step2_otp(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "").strip()
    otp_code = body.get("otp", "").strip()
    print(f"[AUTH API] 📥 [BƯỚC 2] Nhận yêu cầu Xác thực OTP từ Client: session_id={session_id[:8] if session_id else 'Trống/None'}, otp={otp_code}", flush=True)

    from services.auth_tts import authenticate_tts_step2_otp
    result = authenticate_tts_step2_otp(session_id, otp_code)

    if result.get("success"):
        client_ip = _get_client_ip(request)
        is_local = (client_ip in ("127.0.0.1", "localhost", "::1"))
        token = result.get("token", "")
        ttsnew_token = result.get("ttsnew_token", "")
        user_info = result.get("user", {})
        system = result.get("system", "tts_new")

        # KIỂM SOÁT PHÂN QUYỀN TRUY CẬP NGHIÊM NGẶT (WHITELIST)
        if system in ("tts_new", "tts_old", "tts"):
            from region_detector import is_user_permitted
            permitted, matched_u = is_user_permitted(user_info)
            if not permitted:
                u_disp = (user_info.get("displayName") or user_info.get("name") or user_info.get("HoTen") or "KTV")
                print(f"[AUTH API] 🚫 Từ chối truy cập OTP cho [{u_disp}]: Tài khoản chưa có trong danh sách phân vùng!", flush=True)
                return {
                    "success": False,
                    "message": f"Tài khoản [{u_disp}] chưa được cấp quyền truy cập WebApp. Vui lòng liên hệ Quản trị viên hệ thống để khai báo thông tin và phân vùng TT SOC."
                }
            if matched_u and isinstance(user_info, dict):
                user_info["soc"] = matched_u.get("soc", "")
                user_info["region"] = matched_u.get("region", "")

        if client_ip not in ACTIVE_LAN_SESSIONS:
            ACTIVE_LAN_SESSIONS[client_ip] = {}
        if system == "tts_new":
            tok_to_save = ttsnew_token or token
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = tok_to_save
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
            if tok_to_save:
                from region_detector import detect_user_region
                u_reg = detect_user_region(user_info)
                save_cached_token(tok_to_save, region=u_reg if u_reg in ("MN", "MT", "MB") else "MN", user_info=user_info)
        elif system == "btools":
            from btools_manager import save_btools_cookie
            save_btools_cookie(token, verify=False)
            ACTIVE_LAN_SESSIONS[client_ip]["btools_cookie"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["btools_timestamp"] = time.time()
        elif system == "cem":
            ACTIVE_LAN_SESSIONS[client_ip]["cem_apikey"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["cem_timestamp"] = time.time()
        elif system == "ccos":
            ACTIVE_LAN_SESSIONS[client_ip]["ccos_cookie"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["ccos_timestamp"] = time.time()
        else:
            ACTIVE_LAN_SESSIONS[client_ip]["token"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["timestamp"] = time.time()
            if is_local:
                if ttsnew_token:
                    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = ttsnew_token
                    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
                    save_cached_token(ttsnew_token)
                if token:
                    save_cached_auth(token, user_info)
        _save_lan_sessions()

        user_display = user_info.get("HoTen") or user_info.get("TaiKhoan") or user_info.get("displayName") or "KTV"
        sys_label = "BTools" if system == "btools" else ("CEM" if system == "cem" else ("TTS Mới" if system == "tts_new" else "TTS Cũ"))
        print(f"[AUTH API] 🔑 [BƯỚC 2] Xác thực OTP [{sys_label}] THÀNH CÔNG cho {user_display}! Đã lưu phiên.", flush=True)
        try:
            state.log("SUCCESS", f"🔑 [XÁC THỰC OTP {sys_label}] {user_display} (IP: {client_ip}) đã qua bước OTP thành công!")
        except Exception:
            pass
        return {
            "success": True,
            "token": token,
            "ttsnew_token": ttsnew_token or (token if system == "tts_new" else ""),
            "system": system,
            "user": user_info
        }
    else:
        client_ip = request.client.host if request.client else "127.0.0.1"
        err_msg = result.get("error", "Xác thực OTP thất bại. Vui lòng thử lại.")
        print(f"[AUTH API] ❌ [BƯỚC 2] Xác thực OTP THẤT BÀI: {err_msg}", flush=True)
        try:
            state.log("ERROR", f"❌ [XÁC THỰC OTP THẤT BÀI] IP {client_ip}: {err_msg}")
        except Exception:
            pass
        return {
            "success": False,
            "error": err_msg
        }


@router.post("/session/register")
@router.post("/tts_old/token")
async def register_browser_session(request: Request):
    body = await request.json()
    token = body.get("token", "").strip()
    user_info = body.get("user") or {}
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")
    if token:
        from tts_old_api import is_tts_old_token_valid, fetch_tts_old_user_info
        if not is_tts_old_token_valid(token):
            return {"success": False, "message": "Token TTS Cũ đã hết hạn hoặc không hợp lệ trên máy chủ"}

        if not user_info or not user_info.get("Id") or user_info.get("Id") == 0:
            fresh_u = fetch_tts_old_user_info(token)
            if fresh_u and fresh_u.get("Id"):
                user_info = fresh_u

        if client_ip not in ACTIVE_LAN_SESSIONS:
            ACTIVE_LAN_SESSIONS[client_ip] = {}
        ACTIVE_LAN_SESSIONS[client_ip]["token"] = token
        ACTIVE_LAN_SESSIONS[client_ip]["user"] = user_info
        ACTIVE_LAN_SESSIONS[client_ip]["timestamp"] = time.time()
        _save_lan_sessions()

        if is_local:
            save_cached_auth(token, user_info)

        try:
            u_display = user_info.get("HoTen") or user_info.get("TaiKhoan") or "KTV"
            state.log("SUCCESS", f"🔑 [AUTH] Đã kết nối phiên TTS Cũ cho [{u_display}] (IP: {client_ip})")
        except Exception:
            pass
        return {"success": True, "message": f"Đã kết nối phiên cho IP {client_ip}"}
    return {"success": False, "message": "Thiếu mã token"}


@router.post("/ttsnew/token")
async def save_ttsnew_token_api(request: Request):
    body = await request.json()
    tok_input = str(body.get("token") or "").strip()
    user_info = body.get("user") or {}
    if not tok_input:
        return {"success": False, "message": "Token không được để trống"}
    if not tok_input.startswith("Bearer ") and "." in tok_input:
        tok_input = f"Bearer {tok_input}"

    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = (client_ip in ("127.0.0.1", "localhost", "::1"))
    if client_ip not in ACTIVE_LAN_SESSIONS:
        ACTIVE_LAN_SESSIONS[client_ip] = {}
    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = tok_input
    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_user"] = user_info
    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
    _save_lan_sessions()

    if is_local:
        from region_detector import detect_user_region
        u_reg = detect_user_region(user_info)
        save_cached_token(tok_input, region=u_reg if u_reg in ("MN", "MT", "MB") else "MN", user_info=user_info)

    u_name = user_info.get("displayName") or user_info.get("username") or "KTV"
    try:
        state.log("SUCCESS", f"🔑 [AUTH] Đã kết nối token TTS Mới cho [{u_name}] (IP: {client_ip})")
    except Exception:
        pass
    return {"success": True, "message": "Xác thực và lưu token TTS Mới thành công!"}


def _check_is_admin(request: Request, body_token: str = "") -> bool:
    """Kiểm tra quyền Quản trị viên hệ thống (Superadmin hoặc Localhost)."""
    client_ip = _get_client_ip(request)
    if client_ip in ("127.0.0.1", "localhost", "::1"):
        return True
    auth_hdr = request.headers.get("Authorization") or body_token or ""
    from services.session_manager import decode_jwt
    from region_detector import is_superadmin
    uinfo = decode_jwt(auth_hdr) if auth_hdr else {}
    if not uinfo and client_ip in ACTIVE_LAN_SESSIONS:
        sess = ACTIVE_LAN_SESSIONS.get(client_ip) or {}
        uinfo = sess.get("ttsnew_user") or sess.get("user") or {}
    return is_superadmin(uinfo)


@router.get("/admin/users")
async def get_admin_users_api(request: Request):
    from region_detector import get_user_regions_config
    cfg = get_user_regions_config()
    is_admin = _check_is_admin(request)
    return {
        "success": True,
        "is_admin": is_admin,
        "users": cfg.get("users", []),
        "soc_mapping": cfg.get("soc_mapping", {"SOC1": "MB", "SOC2": "MN", "SOC3": "MT"})
    }


@router.post("/admin/users")
async def save_admin_user_api(request: Request):
    body = await request.json()
    tok = body.get("token") or ""
    if not _check_is_admin(request, body_token=tok):
        raise HTTPException(
            status_code=403, 
            detail="Tài khoản hiện tại không có quyền Quản trị viên (Admin). Vui lòng đăng nhập tài khoản Admin hoặc thao tác trên máy chủ để khai báo nhân viên mới."
        )
    from region_detector import save_user_to_config
    ok, msg = save_user_to_config(body)
    return {"success": ok, "message": msg}


@router.delete("/admin/users/{identifier}")
async def delete_admin_user_api(identifier: str, request: Request):
    if not _check_is_admin(request):
        raise HTTPException(
            status_code=403, 
            detail="Tài khoản hiện tại không có quyền Quản trị viên (Admin) để xóa nhân viên."
        )
    from region_detector import delete_user_from_config
    ok, msg = delete_user_from_config(identifier)
    return {"success": ok, "message": msg}

