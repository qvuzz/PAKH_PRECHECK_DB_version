# services/session_manager.py
# Quản lý phiên xác thực KTV trên mạng LAN và Token TTS Mới / TTS Cũ

import os
import json
import time
import base64
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LAN_SESSIONS_FILE = BASE_DIR / "lan_sessions.json"


def _load_lan_sessions():
    if LAN_SESSIONS_FILE.exists():
        try:
            with open(LAN_SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_lan_sessions():
    try:
        with open(LAN_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(ACTIVE_LAN_SESSIONS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


ACTIVE_LAN_SESSIONS = _load_lan_sessions()


def decode_jwt(tok_str: str) -> dict:
    try:
        raw = tok_str.replace("Bearer ", "").strip()
        parts = raw.split(".")
        if len(parts) >= 2:
            p = parts[1]
            p += "=" * ((4 - len(p) % 4) % 4)
            data = json.loads(base64.b64decode(p).decode("utf-8"))
            u = data.get("userInfo") or {}
            return {
                "userName": u.get("userName") or data.get("sub") or "KTV",
                "displayName": u.get("name") or u.get("userName") or data.get("sub") or "KTV",
                "userId": u.get("userId") or 0
            }
    except Exception:
        pass
    return {}


def resolve_ttsnew_token(client_ip: str, is_local: bool, client_tok: str = "") -> tuple:
    """
    Xác định token và thông tin KTV thực hiện trên TTS Mới:
    1. Ưu tiên token client gửi lên (nếu là JWT Bearer hợp lệ).
    2. Nếu không có, lấy từ ACTIVE_LAN_SESSIONS[client_ip].
    3. Nếu là máy chủ Localhost (Admin): cho phép lấy từ Chrome máy chủ.
    4. Nếu là máy client LAN: TUYỆT ĐỐI KHÔNG dùng token máy chủ.
    Trả về: (token: str, user_info: dict)
    """
    # 1. Kiểm tra token gửi từ client
    tok = (client_tok or "").strip()
    if tok and len(tok) > 30 and "." in tok:
        if not tok.startswith("Bearer "):
            tok = f"Bearer {tok}"
        user_info = decode_jwt(tok)
        if user_info.get("userName"):
            if client_ip not in ACTIVE_LAN_SESSIONS:
                ACTIVE_LAN_SESSIONS[client_ip] = {}
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = tok
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_user"] = user_info
            ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = time.time()
            _save_lan_sessions()
            return tok, user_info

    # 2. Kiểm tra phiên LAN session của IP này
    if client_ip in ACTIVE_LAN_SESSIONS:
        lan_tok = (ACTIVE_LAN_SESSIONS[client_ip].get("ttsnew_token") or "").strip()
        if lan_tok and len(lan_tok) > 30 and "." in lan_tok:
            if not lan_tok.startswith("Bearer "):
                lan_tok = f"Bearer {lan_tok}"
            user_info = ACTIVE_LAN_SESSIONS[client_ip].get("ttsnew_user") or decode_jwt(lan_tok)
            return lan_tok, user_info

    # 3. Nếu là máy chủ local (Admin), cho phép fallback lấy từ Chrome máy chủ
    if is_local:
        try:
            from ttsnew_api import extract_token_from_browser
            srv_tok = extract_token_from_browser()
            if srv_tok:
                if not srv_tok.startswith("Bearer "):
                    srv_tok = f"Bearer {srv_tok}"
                user_info = decode_jwt(srv_tok)
                return srv_tok, user_info
        except Exception:
            pass

    return "", {}
