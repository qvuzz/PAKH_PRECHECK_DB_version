# services_checker.py
# Kiểm tra nhanh trạng thái kích hoạt (activate/deactivate) của:
# BTools, CEM, SAPC, TTS (cũ), TTS (mới)
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

_HEALTH_CACHE = {
    "btools": False,
    "cem": False,
    "sapc": False,
    "tts_old": False,
    "tts_new": False,
    "ccos": False,
    "last_checked": 0
}

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

def check_tts_old_fast(driver=None, token: str = None) -> bool:
    try:
        from tts_old_api import get_cached_auth, extract_token_from_browser, fetch_nguyen_nhan_list_api
        tok = (token or "").strip()
        if not tok:
            tok, _ = get_cached_auth()
        if not tok:
            tok, _ = extract_token_from_browser(driver=driver)
        if not tok:
            return False
        res = fetch_nguyen_nhan_list_api(tok)
        return bool(res)
    except Exception:
        return False

def check_tts_new_fast(driver=None, token: str = None) -> bool:
    try:
        from ttsnew_api import get_cached_token, extract_token_from_browser, fetch_active_tickets
        tok = (token or "").strip()
        if not tok:
            tok = get_cached_token()
        if not tok:
            tok = extract_token_from_browser(driver=driver)
        if not tok:
            return False
        if not tok.startswith("Bearer ") and "." in tok:
            tok = f"Bearer {tok}"
        res = fetch_active_tickets(tok, limit=1)
        return True
    except Exception:
        return False

def get_services_health(force=False, driver=None, tts_old_token: str = None, tts_new_token: str = None) -> dict:
    global _HEALTH_CACHE
    now = time.time()
    has_custom_tokens = bool((tts_old_token and tts_old_token.strip()) or (tts_new_token and tts_new_token.strip()))
    
    if not force and not has_custom_tokens and (now - _HEALTH_CACHE["last_checked"] < 25):
        return {
            "btools": _HEALTH_CACHE["btools"],
            "cem": _HEALTH_CACHE["cem"],
            "sapc": _HEALTH_CACHE["sapc"],
            "tts_old": _HEALTH_CACHE["tts_old"],
            "tts_new": _HEALTH_CACHE["tts_new"],
            "ccos": _HEALTH_CACHE.get("ccos", False)
        }

    from auth_extractor import get_chrome_debug_driver
    if driver is None:
        try:
            driver = get_chrome_debug_driver()
        except Exception:
            driver = None

    btools_ok = check_btools_fast(driver=driver)
    cem_ok = check_cem_fast(driver=driver)
    sapc_ok = check_sapc_fast(driver=driver)
    tts_old_ok = check_tts_old_fast(driver=driver, token=tts_old_token)
    tts_new_ok = check_tts_new_fast(driver=driver, token=tts_new_token)
    ccos_ok = check_ccos_fast(driver=driver)

    if not has_custom_tokens:
        _HEALTH_CACHE["btools"] = btools_ok
        _HEALTH_CACHE["cem"] = cem_ok
        _HEALTH_CACHE["sapc"] = sapc_ok
        _HEALTH_CACHE["tts_old"] = tts_old_ok
        _HEALTH_CACHE["tts_new"] = tts_new_ok
        _HEALTH_CACHE["ccos"] = ccos_ok
        _HEALTH_CACHE["last_checked"] = now

    return {
        "btools": btools_ok,
        "cem": cem_ok,
        "sapc": sapc_ok,
        "tts_old": tts_old_ok,
        "tts_new": tts_new_ok,
        "ccos": ccos_ok
    }
