# services/session_manager.py
# Quản lý phiên xác thực KTV trên mạng LAN và Token TTS Mới / TTS Cũ

import os
import json
import time
import base64
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LAN_SESSIONS_FILE = BASE_DIR / "lan_sessions.json"
_session_lock = threading.Lock()


def _load_lan_sessions():
    if LAN_SESSIONS_FILE.exists():
        try:
            with open(LAN_SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_lan_sessions():
    with _session_lock:
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
            username = u.get("userName") or u.get("username") or data.get("sub") or data.get("preferred_username") or "KTV"
            email = u.get("email") or data.get("email") or ""
            return {
                "userName": username,
                "displayName": u.get("name") or u.get("displayName") or username,
                "email": email,
                "userId": u.get("userId") or 0,
                "don_vi": u.get("donVi") or u.get("department") or "",
                "ma_don_vi": u.get("maDonVi") or ""
            }
    except Exception:
        pass
    return {}


def is_docker_gateway_ip(ip: str) -> bool:
    if not ip:
        return False
    parts = ip.split(".")
    if len(parts) == 4 and parts[0] == "172":
        try:
            sec = int(parts[1])
            return 16 <= sec <= 31
        except Exception:
            pass
    return False


def resolve_ttsnew_token(client_ip: str, is_local: bool = False, client_tok: str = "") -> tuple:
    """
    Xác định token và thông tin KTV thực hiện trên TTS Mới — CHẾ ĐỘ NGHIÊM NGẶT:
    - CHỈ chấp nhận token JWT hợp lệ do CHÍNH trình duyệt client gửi lên (header Authorization / body token).
    - KHÔNG dùng phiên theo IP (trong Docker mọi client đều hiện IP gateway 172.x giống nhau).
    - KHÔNG fallback sang token máy chủ / Chrome máy chủ.
    client_ip, is_local giữ lại để tương thích chữ ký hàm cũ (chỉ dùng ghi log).
    Trả về: (token: str, user_info: dict) hoặc ("", {}) nếu chưa đăng nhập.
    """
    tok = (client_tok or "").strip()
    if not tok or len(tok) <= 30 or "." not in tok:
        return "", {}
    if not tok.startswith("Bearer "):
        tok = f"Bearer {tok}"
    from ttsnew_api import _is_jwt_valid
    if not _is_jwt_valid(tok):
        return "", {}
    user_info = decode_jwt(tok)
    if not user_info.get("userName"):
        return "", {}
    return tok, user_info


def get_request_token(request, body: dict = None) -> str:
    """Lấy token client gửi lên: ưu tiên body['token'], sau đó header Authorization."""
    tok = ""
    if body and isinstance(body, dict):
        tok = str(body.get("token") or "").strip()
    if not tok and request is not None:
        tok = (request.headers.get("Authorization") or "").strip()
    return tok


def get_request_user(request, body: dict = None) -> tuple:
    """Định danh người dùng của request chỉ dựa trên token của trình duyệt. Trả về (token, user_info)."""
    client_ip = request.client.host if (request is not None and request.client) else ""
    return resolve_ttsnew_token(client_ip, False, get_request_token(request, body))
