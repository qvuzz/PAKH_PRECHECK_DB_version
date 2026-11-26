# services_checker.py
# Kiểm tra nhanh trạng thái kích hoạt (activate/deactivate) của:
# BTools, CEM, SAPC, TTS (cũ), TTS (mới)
import time
import threading
import concurrent.futures
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

_HEALTH_CACHE = {
    "btools": False,
    "cem": False,
    "sapc": False,
    "tts_new": False,
    "ccos": False,
    "gw": False,
    "last_checked": 0
}
_HEALTH_LOCK = threading.Lock()

def check_gw_fast(driver=None) -> bool:
    try:
        from gw_client import load_gw_cache, verify_gw_session
        cached = load_gw_cache()
        js = cached.get("jsessionid", "")
        vs = cached.get("view_state", "")
        if js:
            is_valid, _ = verify_gw_session(js, vs)
            return bool(is_valid)
    except Exception:
        pass
    return False

def check_ccos_fast(driver=None) -> bool:
    try:
        from ccos_client import get_ccos_cookies
        cookies = get_ccos_cookies(driver=driver)
        return bool(cookies and ("SessionDB" in cookies or "SESSIONID" in cookies))
    except Exception:
        return False


def check_btools_fast(driver=None) -> bool:
    try:
        from btools_manager import get_active_btools_cookie, verify_btools_cookie
        cookie = get_active_btools_cookie(driver=driver)
        if not cookie:
            return False
        is_valid, _ = verify_btools_cookie(cookie)
        return bool(is_valid)
    except Exception:
        return False

def check_cem_fast(driver=None) -> bool:
    try:
        from cem_client import CEMClient, CEM_URL
        c = CEMClient(driver=driver)
        if not c.api_key:
            return False
        import urllib.parse
        while "%25" in c.api_key:
            c.api_key = urllib.parse.unquote(c.api_key)
        res, _ = c._post_with_retry(
            CEM_URL,
            payload={"start_date": "2026-09-01", "msisdn": "912345678"},
            timeout=4
        )
        return bool(res and res.status_code == 200)
    except Exception:
        return False

def check_sapc_fast(driver=None) -> bool:
    try:
        import sys
        sapc_dir = str(BASE_DIR / "sapccheck")
        if sapc_dir not in sys.path:
            sys.path.insert(0, sapc_dir)
        from sapc_client import SAPCClient
        s = SAPCClient(driver=driver)
        return s._is_cookie_valid()
    except Exception:
        return False

def check_tts_new_fast(driver=None, token: str = None) -> bool:
    try:
        from ttsnew_api import get_cached_token, extract_token_from_browser, fetch_active_tickets, _is_jwt_valid
        tok = (token or "").strip()
        if not tok:
            tok = get_cached_token()
        if not tok:
            tok = extract_token_from_browser(driver=driver)
        if not tok:
            return False
        if not tok.startswith("Bearer ") and "." in tok:
            tok = f"Bearer {tok}"
        
        # 1. Kiểm tra cấu trúc JWT và hạn sử dụng exp trước
        if not _is_jwt_valid(tok):
            return False
            
        # 2. Token còn hạn exp hợp lệ -> kiểm tra thêm API OneOSS nhưng tránh để lỗi mạng làm đánh rớt trạng thái
        try:
            fetch_active_tickets(tok, limit=1)
        except Exception as api_err:
            err_str = str(api_err).lower()
            if "401" in err_str or "unauthorized" in err_str or "token hết hạn" in err_str:
                return False
        return True
    except Exception:
        return False

def get_services_health(force=False, driver=None, tts_new_token: str = None, **kwargs) -> dict:
    global _HEALTH_CACHE
    now = time.time()
    custom_tok = (tts_new_token or "").strip()

    def _eval_custom_tts_new(tok_str: str) -> bool:
        try:
            from ttsnew_api import _is_jwt_valid
            t = tok_str if (tok_str.startswith("Bearer ") or "." not in tok_str) else f"Bearer {tok_str}"
            return bool(_is_jwt_valid(t))
        except Exception:
            return False

    # Trả cache ngay (< 1ms) nếu chưa quá 30s (dù client có truyền tts_new_token)
    if not force and (now - _HEALTH_CACHE["last_checked"] < 30):
        tts_new_val = _eval_custom_tts_new(custom_tok) if custom_tok else _HEALTH_CACHE["tts_new"]
        return {
            "btools": _HEALTH_CACHE["btools"],
            "cem": _HEALTH_CACHE["cem"],
            "sapc": _HEALTH_CACHE["sapc"],
            "tts_new": tts_new_val,
            "ccos": _HEALTH_CACHE.get("ccos", False),
            "gw": _HEALTH_CACHE.get("gw", False)
        }

    with _HEALTH_LOCK:
        # Double-check sau khi nhận lock (tránh nhiều request cùng làm mới song song)
        now2 = time.time()
        if not force and (now2 - _HEALTH_CACHE["last_checked"] < 30):
            tts_new_val = _eval_custom_tts_new(custom_tok) if custom_tok else _HEALTH_CACHE["tts_new"]
            return {
                "btools": _HEALTH_CACHE["btools"],
                "cem": _HEALTH_CACHE["cem"],
                "sapc": _HEALTH_CACHE["sapc"],
                "tts_new": tts_new_val,
                "ccos": _HEALTH_CACHE.get("ccos", False),
                "gw": _HEALTH_CACHE.get("gw", False)
            }

        # Chạy song song toàn bộ các hàm check thay vì tuần tự nối đuôi nhau
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            f_btools = pool.submit(check_btools_fast, driver)
            f_cem = pool.submit(check_cem_fast, driver)
            f_sapc = pool.submit(check_sapc_fast, driver)
            f_tts_new = pool.submit(_eval_custom_tts_new, custom_tok) if custom_tok else pool.submit(check_tts_new_fast, driver, None)
            f_ccos = pool.submit(check_ccos_fast, driver)
            f_gw = pool.submit(check_gw_fast, driver)

            btools_ok = f_btools.result()
            cem_ok = f_cem.result()
            sapc_ok = f_sapc.result()
            tts_new_ok = f_tts_new.result()
            ccos_ok = f_ccos.result()
            gw_ok = f_gw.result()

        _HEALTH_CACHE["btools"] = btools_ok
        _HEALTH_CACHE["cem"] = cem_ok
        _HEALTH_CACHE["sapc"] = sapc_ok
        if not custom_tok:
            _HEALTH_CACHE["tts_new"] = tts_new_ok
        _HEALTH_CACHE["ccos"] = ccos_ok
        _HEALTH_CACHE["gw"] = gw_ok
        _HEALTH_CACHE["last_checked"] = time.time()

    return {
        "btools": btools_ok,
        "cem": cem_ok,
        "sapc": sapc_ok,
        "tts_new": tts_new_ok,
        "ccos": ccos_ok,
        "gw": gw_ok
    }
