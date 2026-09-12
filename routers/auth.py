# routers/auth.py
# Quản lý xác thực tài khoản KTV, phân quyền LAN/Local và OTP

import time
from fastapi import APIRouter, Request
from services.state import state
from services.session_manager import (
    ACTIVE_LAN_SESSIONS, 
    _save_lan_sessions, 
    resolve_ttsnew_token
)
from tts_old_api import save_cached_auth
from ttsnew_api import save_cached_token

router = APIRouter(prefix="/api", tags=["Xác thực & Phiên KTV"])


@router.get("/current_user")
def get_current_user_info(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")

    token = ""
    user_info = {}
    lan_ttsnew_tok = ""
    lan_ttsnew_usr = {}
    if client_ip in ACTIVE_LAN_SESSIONS:
        if time.time() - ACTIVE_LAN_SESSIONS[client_ip].get("timestamp", 0) < 86400:
            token = ACTIVE_LAN_SESSIONS[client_ip].get("token", "")
            user_info = ACTIVE_LAN_SESSIONS[client_ip].get("user", {})
        if time.time() - ACTIVE_LAN_SESSIONS[client_ip].get("ttsnew_timestamp", 0) < 86400:
            lan_ttsnew_tok = ACTIVE_LAN_SESSIONS[client_ip].get("ttsnew_token", "")
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

    return {
        "is_local": is_local,
        "client_ip": client_ip,
        "has_server_token": bool(client_server_token),
        "server_user": srv_user if is_local else {},
        "server_token": client_server_token,
        "server_ttsnew_token": client_server_ttsnew,
        "token": token,
        "user": user_info,
        "ttsnew_token": client_server_ttsnew if is_local else lan_ttsnew_tok,
        "ttsnew_user": srv_user if is_local else lan_ttsnew_usr
    }


@router.post("/login")
async def login_tts_step1(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    system = str(body.get("system") or "tts_old").strip()

    from services.auth_tts import authenticate_tts_step1
    result = authenticate_tts_step1(username, password, system=system)

    if result.get("success"):
        client_ip = request.client.host if request.client else "127.0.0.1"
        is_local = (client_ip in ("127.0.0.1", "localhost", "::1"))
        token = result.get("token", "")
        ttsnew_token = result.get("ttsnew_token", "")
        user_info = result.get("user", {})
        if client_ip not in ACTIVE_LAN_SESSIONS:
            ACTIVE_LAN_SESSIONS[client_ip] = {}
        if system == "tts_new":
            tok_to_save = ttsnew_token or token
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = tok_to_save
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
            if tok_to_save:
                save_cached_token(tok_to_save)
        else:
            ACTIVE_LAN_SESSIONS[client_ip]["token"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["timestamp"] = time.time()
            if ttsnew_token:
                ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = ttsnew_token
                ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
                save_cached_token(ttsnew_token)
            if token:
                save_cached_auth(token, user_info)
        _save_lan_sessions()

        user_display = user_info.get("HoTen") or user_info.get("TaiKhoan") or user_info.get("displayName") or username
        sys_label = "TTS Mới" if system == "tts_new" else "TTS Cũ"
        try:
            state.log("SUCCESS", f"🔑 [XÁC THỰC {sys_label}] {user_display} (IP: {client_ip}) đã đăng nhập thành công!")
        except Exception:
            pass
        return {
            "success": True,
            "token": token,
            "ttsnew_token": ttsnew_token or (token if system == "tts_new" else ""),
            "system": system,
            "user": user_info
        }
    elif result.get("otp_required"):
        return {
            "success": False,
            "otp_required": True,
            "session_id": result.get("session_id"),
            "username": result.get("username", username),
            "phone": result.get("phone", ""),
            "system": system,
            "message": result.get("message", "Vui lòng nhập mã OTP để tiếp tục.")
        }
    else:
        return {
            "success": False,
            "error": result.get("error", "Đăng nhập thất bại. Vui lòng kiểm tra lại tài khoản hoặc mật khẩu.")
        }


@router.post("/login/otp")
async def login_tts_step2_otp(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "").strip()
    otp_code = body.get("otp", "").strip()

    from services.auth_tts import authenticate_tts_step2_otp
    result = authenticate_tts_step2_otp(session_id, otp_code)

    if result.get("success"):
        client_ip = request.client.host if request.client else "127.0.0.1"
        is_local = (client_ip in ("127.0.0.1", "localhost", "::1"))
        token = result.get("token", "")
        ttsnew_token = result.get("ttsnew_token", "")
        user_info = result.get("user", {})
        system = result.get("system", "tts_old")
        if client_ip not in ACTIVE_LAN_SESSIONS:
            ACTIVE_LAN_SESSIONS[client_ip] = {}
        if system == "tts_new":
            tok_to_save = ttsnew_token or token
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = tok_to_save
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
            if tok_to_save:
                save_cached_token(tok_to_save)
        else:
            ACTIVE_LAN_SESSIONS[client_ip]["token"] = token
            ACTIVE_LAN_SESSIONS[client_ip]["user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["timestamp"] = time.time()
            if ttsnew_token:
                ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = ttsnew_token
                ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
                save_cached_token(ttsnew_token)
            if token:
                save_cached_auth(token, user_info)
        _save_lan_sessions()

        user_display = user_info.get("HoTen") or user_info.get("TaiKhoan") or user_info.get("displayName") or "KTV"
        sys_label = "TTS Mới" if system == "tts_new" else "TTS Cũ"
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
        try:
            state.log("ERROR", f"❌ [XÁC THỰC OTP THẤT BÀI] IP {client_ip}: {err_msg}")
        except Exception:
            pass
        return {
            "success": False,
            "error": err_msg
        }


@router.post("/session/register")
async def register_browser_session(request: Request):
    body = await request.json()
    token = body.get("token", "").strip()
    user_info = body.get("user") or {}
    client_ip = request.client.host if request.client else "127.0.0.1"
    if token:
        if client_ip not in ACTIVE_LAN_SESSIONS:
            ACTIVE_LAN_SESSIONS[client_ip] = {}
        ACTIVE_LAN_SESSIONS[client_ip]["token"] = token
        ACTIVE_LAN_SESSIONS[client_ip]["user"] = user_info
        ACTIVE_LAN_SESSIONS[client_ip]["timestamp"] = time.time()
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
    if client_ip not in ACTIVE_LAN_SESSIONS:
        ACTIVE_LAN_SESSIONS[client_ip] = {}
    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = tok_input
    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_user"] = user_info
    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
    _save_lan_sessions()

    save_cached_token(tok_input)

    u_name = user_info.get("displayName") or user_info.get("username") or "KTV"
    try:
        state.log("SUCCESS", f"🔑 [AUTH] Đã kết nối token TTS Mới cho [{u_name}] (IP: {client_ip})")
    except Exception:
        pass
    return {"success": True, "message": "Xác thực và lưu token TTS Mới thành công!"}
