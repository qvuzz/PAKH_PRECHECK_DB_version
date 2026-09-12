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
    "last_checked": 0
}

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
        from cem_client import CEMClient, CEM_URL, CEM_HEADERS
        c = CEMClient(driver=driver)
        if not c.api_key:
            return False
        res = c.session.post(
            CEM_URL,
            headers=CEM_HEADERS,
            json={"apikey": c.api_key, "start_date": "2026-09-01", "msisdn": "912345678"},
            timeout=3,
            verify=False
        )
        return res.status_code == 200
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
        cookies = [c for c in s.session.cookies if "10.155.42" in getattr(c, 'domain', '') or getattr(c, 'name', '') in ('JSESSIONID', 'PHPSESSID')]
        if len(cookies) > 0:
            return True
        try:
            resp = s.session.get("http://10.155.42.218", timeout=2)
            if resp.status_code in (200, 302):
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False

def check_tts_old_fast(driver=None) -> bool:
    try:
        from tts_old_api import get_cached_auth, extract_token_from_browser, fetch_nguyen_nhan_list_api
        token, _ = get_cached_auth()
        if not token:
            token, _ = extract_token_from_browser(driver=driver)
        if not token:
            return False
        res = fetch_nguyen_nhan_list_api(token)
        return bool(res)
    except Exception:
        return False

def check_tts_new_fast(driver=None) -> bool:
    try:
        from ttsnew_api import get_cached_token, extract_token_from_browser, fetch_active_tickets
        token = get_cached_token()
        if not token:
            token = extract_token_from_browser(driver=driver)
        if not token:
            return False
        res = fetch_active_tickets(token, limit=1)
        return True
    except Exception:
        return False

def get_services_health(force=False, driver=None) -> dict:
    global _HEALTH_CACHE
    now = time.time()
    if not force and (now - _HEALTH_CACHE["last_checked"] < 25):
        return {
            "btools": _HEALTH_CACHE["btools"],
            "cem": _HEALTH_CACHE["cem"],
            "sapc": _HEALTH_CACHE["sapc"],
            "tts_old": _HEALTH_CACHE["tts_old"],
            "tts_new": _HEALTH_CACHE["tts_new"]
        }

    from auth_extractor import get_chrome_debug_driver
    if driver is None:
        try:
            driver = get_chrome_debug_driver()
        except Exception:
            driver = None

    _HEALTH_CACHE["btools"] = check_btools_fast(driver=driver)
    _HEALTH_CACHE["cem"] = check_cem_fast(driver=driver)
    _HEALTH_CACHE["sapc"] = check_sapc_fast(driver=driver)
    _HEALTH_CACHE["tts_old"] = check_tts_old_fast(driver=driver)
    _HEALTH_CACHE["tts_new"] = check_tts_new_fast(driver=driver)
    _HEALTH_CACHE["last_checked"] = now

    return {
        "btools": _HEALTH_CACHE["btools"],
        "cem": _HEALTH_CACHE["cem"],
        "sapc": _HEALTH_CACHE["sapc"],
        "tts_old": _HEALTH_CACHE["tts_old"],
        "tts_new": _HEALTH_CACHE["tts_new"]
    }
