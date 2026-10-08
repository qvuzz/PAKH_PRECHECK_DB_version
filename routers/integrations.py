# routers/integrations.py
# Quản lý kết nối BTools, CEM, SAPC và các dịch vụ tích hợp nội bộ

from fastapi import APIRouter, Request
from btools_manager import get_active_btools_cookie, verify_btools_cookie, save_btools_cookie
from services_checker import get_services_health
from ttsnew_api import extract_token_from_browser
from auth_extractor import get_chrome_debug_driver

router = APIRouter(prefix="/api", tags=["Tích hợp Dịch vụ (BTools, CEM, SAPC)"])


@router.get("/btools/status")
def get_btools_status():
    cookie = get_active_btools_cookie()
    is_valid, msg = verify_btools_cookie(cookie) if cookie else (False, "Chưa có Cookie BTools")
    return {
        "success": True,
        "connected": is_valid,
        "message": msg,
        "has_cookie": bool(cookie)
    }


@router.post("/btools/cookie")
async def update_btools_cookie(request: Request):
    body = await request.json()
    cookie_input = str(body.get("cookie") or body.get("raw") or "").strip()
    if not cookie_input:
        return {"success": False, "message": "Cookie không được để trống"}
    is_valid, msg = save_btools_cookie(cookie_input, verify=False)
    return {
        "success": True,
        "connected": True,
        "message": "Đã lưu Cookie BTools thành công"
    }


@router.get("/cem/status")
def get_cem_status():
    from auth_extractor import _load_cem_cache
    api_key, cookies = _load_cem_cache()
    if not api_key:
        return {"success": False, "connected": False, "message": "Chưa có API Key CEM", "has_key": False}
    try:
        from cem_client import CEMClient, CEM_URL
        c = CEMClient(api_key=api_key)
        res, _ = c._post_with_retry(
            CEM_URL,
            payload={"start_date": "2026-09-01", "msisdn": "912345678"},
            timeout=4
        )
        is_valid = bool(res and res.status_code == 200)
        return {
            "success": True,
            "connected": is_valid,
            "message": "Kết nối CEM thành công" if is_valid else "API Key CEM không hợp lệ hoặc hết hạn",
            "has_key": True
        }
    except Exception as e:
        return {"success": False, "connected": False, "message": str(e), "has_key": True}


@router.post("/cem/auth")
async def update_cem_auth(request: Request):
    body = await request.json()
    api_key = str(body.get("api_key") or body.get("apikey") or "").strip()
    cookies = body.get("cookies") or {}
    raw_cookie = str(body.get("raw_cookie") or body.get("cookie") or "").strip()

    # Bóc tách cookies từ chuỗi raw_cookie nếu cookies dict chưa có
    if raw_cookie and not cookies:
        import urllib.parse
        cookies = {}
        for part in raw_cookie.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k.strip()] = v.strip()
                if not api_key and (k.strip().lower() in ("apikey", "api_key") or v.strip().startswith("net_ktm_")):
                    api_key = urllib.parse.unquote(v.strip())

    if not api_key:
        return {"success": False, "message": "API Key CEM không được để trống"}

    import urllib.parse
    while "%25" in api_key:
        api_key = urllib.parse.unquote(api_key)

    from auth_extractor import _save_cem_cache
    _save_cem_cache(api_key, cookies)
    try:
        import cem_client
        cem_client.CEM_API_KEY = api_key
    except Exception:
        pass

    return {
        "success": True,
        "connected": True,
        "message": "Đã lưu API Key và Cookies CEM thành công!"
    }


@router.post("/sapc/cookie")
async def update_sapc_cookie(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    cookie_str = str(body.get("cookie") or body.get("raw") or "").strip()
    raw_cookies_list = body.get("cookies")
    if not cookie_str and not raw_cookies_list:
        return {"success": False, "message": "Cookie SAPC không được để trống"}
    try:
        import json, os, requests
        base_sapc_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sapccheck")
        cookie_file_1 = os.path.join(base_sapc_dir, "sapc_cookies.json")
        cookie_file_2 = os.path.join(base_sapc_dir, "cookies.json")
        
        parts = []
        if isinstance(raw_cookies_list, list) and raw_cookies_list:
            for c in raw_cookies_list:
                parts.append({
                    "name": c.get("name"),
                    "value": c.get("value"),
                    "domain": c.get("domain", "10.155.42.218"),
                    "path": c.get("path", "/")
                })
        elif isinstance(raw_cookies_list, dict) and raw_cookies_list:
            for k, v in raw_cookies_list.items():
                parts.append({"name": str(k).strip(), "value": str(v).strip(), "domain": "10.155.42.218", "path": "/"})
        else:
            for item in cookie_str.split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    parts.append({"name": k.strip(), "value": v.strip(), "domain": "10.155.42.218", "path": "/"})
        
        with open(cookie_file_1, "w", encoding="utf-8") as f:
            json.dump(parts, f, indent=2, ensure_ascii=False)
        with open(cookie_file_2, "w", encoding="utf-8") as f:
            json.dump(parts, f, indent=2, ensure_ascii=False)

        # Thử test nhanh cookie với SAPC
        is_live = False
        try:
            s_test = requests.Session()
            for p in parts:
                s_test.cookies.set(p["name"], p["value"], domain="10.155.42.218", path="/")
            res_test = s_test.get("http://10.155.42.218/api/sapc/84916352813", timeout=3)
            if res_test.status_code == 200 and "json" in res_test.headers.get("Content-Type", "").lower():
                is_live = True
        except Exception:
            pass

        msg = "Đã lưu và xác thực kết nối SAPC thành công!" if is_live else "Đã lưu Cookie SAPC từ Chrome (đang chờ kiểm tra)"
        return {"success": True, "connected": is_live, "message": msg}
    except Exception as e:
        return {"success": False, "message": f"Lỗi lưu cookie SAPC: {e}"}


@router.get("/sapc/status")
def get_sapc_status_integration():
    import json, os
    base_sapc_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sapccheck")
    cookie_file = os.path.join(base_sapc_dir, "sapc_cookies.json")
    has_cookie = False
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and any(c.get("name") == ".AspNet.ApplicationCookie" and c.get("value") for c in data):
                    has_cookie = True
        except Exception:
            pass
    return {
        "success": True,
        "connected": has_cookie,
        "has_cookie": has_cookie,
        "message": "Kết nối SAPC thành công (Cookie Core đang hoạt động)" if has_cookie else "Chưa có Cookie SAPC hoặc phiên đã hết hạn"
    }


@router.post("/sapc/logout")
def logout_sapc_integration():
    import json, os
    base_sapc_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sapccheck")
    for fn in ("sapc_cookies.json", "cookies.json"):
        p = os.path.join(base_sapc_dir, fn)
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump([], f)
        except Exception:
            pass
    return {"success": True, "message": "Đã đăng xuất phiên SAPC"}


@router.post("/ccos/logout")
def logout_ccos_integration():
    from ccos_client import invalidate_ccos_cache
    invalidate_ccos_cache()
    return {"success": True, "message": "Đã đăng xuất phiên CCOS"}


@router.get("/ccos/status")
def get_ccos_status_integration():
    from ccos_client import get_ccos_cookies
    cookies = get_ccos_cookies()
    has_session = bool(cookies and ("SessionDB" in cookies or "SESSIONID" in cookies))
    return {
        "success": True,
        "connected": has_session,
        "has_cookie": has_session,
        "message": "Kết nối CCOS thành công (Session đang hoạt động)" if has_session else "Chưa có Cookie CCOS hoặc phiên đã hết hạn"
    }


@router.post("/ccos/cookie")
@router.post("/ccos/update-cookie")
async def update_ccos_cookie_integration(request: Request):
    body = await request.json()
    cookie_str = str(body.get("cookie") or body.get("raw") or "").strip()
    cookies_dict = body.get("cookies") or {}
    from ccos_client import save_ccos_cache
    if cookie_str:
        for part in cookie_str.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies_dict[k.strip()] = v.strip()
    if cookies_dict and ("SessionDB" in cookies_dict or "SESSIONID" in cookies_dict):
        save_ccos_cache(cookies_dict)
        return {"success": True, "connected": True, "message": "Đã đồng bộ Cookie CCOS thành công!"}
    return {"success": False, "message": "Cookie CCOS không hợp lệ (thiếu SessionDB / SESSIONID)"}


@router.post("/sync-tokens")
async def sync_all_tokens_api(request: Request):
    """
    Endpoint tiếp nhận đồng bộ toàn diện từ Chrome Extension (VNPT Token Utilities):
    - CCOS: ccos_cookie, ccos
    - BTools: btools_cookie, btools
    - CEM: cem_api_key, cem_cookie, cem_cookies, cem
    - TTS Mới: tts_new_token, tts_new
    - TTS Cũ: tts_old_token, tts_old
    - SAPC: sapc_cookie, sapc
    """
    import time
    try:
        body = await request.json()
    except Exception:
        body = {}

    results = {
        "success": True,
        "synced": []
    }

    # 1. BTools Cookie
    btools_raw = body.get("btools_cookie") or (body.get("btools") if isinstance(body.get("btools"), str) else (body.get("btools") or {}).get("cookie"))
    if btools_raw:
        clean_bt = str(btools_raw).strip()
        is_val, msg = save_btools_cookie(clean_bt, verify=False)
        # Nếu có JSESSIONID hợp lệ thì coi như đồng bộ thành công
        success_bt = is_val or ("JSESSIONID" in clean_bt.upper())
        results["synced"].append({"service": "BTools", "success": success_bt, "message": msg})

    # 2. CCOS Cookie
    ccos_raw = body.get("ccos_cookie") or (body.get("ccos") if isinstance(body.get("ccos"), str) else (body.get("ccos") or {}).get("cookie"))
    ccos_dict = body.get("ccos_cookies") or {}
    if ccos_raw:
        from ccos_client import save_ccos_cache
        if not ccos_dict:
            ccos_dict = {}
            for part in str(ccos_raw).split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    ccos_dict[k.strip()] = v.strip()
        if ccos_dict and ("SessionDB" in ccos_dict or "SESSIONID" in ccos_dict):
            save_ccos_cache(ccos_dict)
            results["synced"].append({"service": "CCOS", "success": True, "message": "Đã đồng bộ Cookie CCOS"})

    # 3. CEM Auth
    cem_key = body.get("cem_api_key") or (body.get("cem") if isinstance(body.get("cem"), str) else (body.get("cem") or {}).get("api_key"))
    cem_cookie = body.get("cem_cookie") or ""
    cem_cookies = body.get("cem_cookies") or {}
    if isinstance(cem_cookies, list):
        cem_cookies = {c.get("name"): c.get("value") for c in cem_cookies if isinstance(c, dict) and "name" in c}
    if not cem_cookies and cem_cookie:
        import urllib.parse
        for part in str(cem_cookie).split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cem_cookies[k.strip()] = v.strip()
                if not cem_key and (k.strip().lower() in ("apikey", "api_key") or v.strip().startswith("net_ktm_")):
                    cem_key = urllib.parse.unquote(v.strip())
    if cem_key:
        import urllib.parse
        clean_key = str(cem_key).strip()
        while "%25" in clean_key:
            clean_key = urllib.parse.unquote(clean_key)
        from auth_extractor import _save_cem_cache
        _save_cem_cache(clean_key, cem_cookies)
        try:
            import cem_client
            cem_client.CEM_API_KEY = clean_key
        except Exception:
            pass
        results["synced"].append({"service": "CEM", "success": True, "message": "Đã lưu API Key & Cookies CEM"})

    # 4. TTS Mới Token & 5. TTS Cũ Token
    tts_new_tok = body.get("tts_new_token") or (body.get("tts_new") if isinstance(body.get("tts_new"), str) else (body.get("tts_new") or {}).get("token"))
    if tts_new_tok:
        tok_str = str(tts_new_tok).strip()
        if not tok_str.startswith("Bearer ") and "." in tok_str:
            tok_str = f"Bearer {tok_str}"
        client_ip = request.client.host if request.client else "127.0.0.1"
        try:
            from services.session_manager import ACTIVE_LAN_SESSIONS, decode_jwt, _save_lan_sessions, is_docker_gateway_ip
            from ttsnew_api import save_cached_token, get_cached_token
            # Cập nhật cache máy chủ nếu máy chủ chưa có token hoặc là client localhost
            srv_curr_tok = get_cached_token()
            if not srv_curr_tok or client_ip in ("127.0.0.1", "localhost", "::1"):
                save_cached_token(tok_str)
            
            # Cập nhật session cho client này (trừ Docker gateway IP)
            if not is_docker_gateway_ip(client_ip):
                uinfo = decode_jwt(tok_str)
                old_tok = (ACTIVE_LAN_SESSIONS.get(client_ip) or {}).get("ttsnew_token")
                now_ts = time.time()
                last_ts = (ACTIVE_LAN_SESSIONS.get(client_ip) or {}).get("ttsnew_timestamp", 0)
                
                # Chỉ ghi đĩa nếu token thay đổi hoặc đã qua 60 giây
                if old_tok != tok_str or (now_ts - last_ts) > 60.0:
                    if client_ip not in ACTIVE_LAN_SESSIONS:
                        ACTIVE_LAN_SESSIONS[client_ip] = {}
                    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_token"] = tok_str
                    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_user"] = uinfo
                    ACTIVE_LAN_SESSIONS[client_ip]["ttsnew_timestamp"] = now_ts
                    _save_lan_sessions()
                    print(f"✅ [Extension Sync] Đã nhận Token TTS Mới từ {client_ip} ({uinfo.get('displayName', 'KTV')})")
            results["synced"].append({"service": "TTS Mới", "success": True})
        except Exception as e:
            results["synced"].append({"service": "TTS Mới", "success": False, "error": str(e)})

    # 6. SAPC Core Profile Cookie
    sapc_raw = body.get("sapc_cookie") or (body.get("sapc") if isinstance(body.get("sapc"), str) else (body.get("sapc") or {}).get("cookieHeader") or (body.get("sapc") or {}).get("cookie"))
    sapc_raw_cookies = body.get("sapc_cookies") or body.get("cookies") or ((body.get("sapc") or {}).get("rawCookies") if isinstance(body.get("sapc"), dict) else None) or ((body.get("sapc") or {}).get("cookieMap") if isinstance(body.get("sapc"), dict) else None)
    if sapc_raw or sapc_raw_cookies:
        try:
            import json, os
            base_sapc_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sapccheck")
            cookie_file_1 = os.path.join(base_sapc_dir, "sapc_cookies.json")
            cookie_file_2 = os.path.join(base_sapc_dir, "cookies.json")
            parts = []
            if isinstance(sapc_raw_cookies, list) and sapc_raw_cookies:
                for c in sapc_raw_cookies:
                    parts.append({
                        "name": c.get("name"),
                        "value": c.get("value"),
                        "domain": c.get("domain", "10.155.42.218"),
                        "path": c.get("path", "/")
                    })
            elif isinstance(sapc_raw_cookies, dict) and sapc_raw_cookies:
                for k, v in sapc_raw_cookies.items():
                    parts.append({"name": str(k).strip(), "value": str(v).strip(), "domain": "10.155.42.218", "path": "/"})
            elif sapc_raw:
                for item in str(sapc_raw).split(";"):
                    if "=" in item:
                        k, v = item.strip().split("=", 1)
                        parts.append({"name": k.strip(), "value": v.strip(), "domain": "10.155.42.218", "path": "/"})
            if parts:
                with open(cookie_file_1, "w", encoding="utf-8") as f:
                    json.dump(parts, f, indent=2, ensure_ascii=False)
                with open(cookie_file_2, "w", encoding="utf-8") as f:
                    json.dump(parts, f, indent=2, ensure_ascii=False)
                results["synced"].append({"service": "SAPC", "success": True, "message": "Đã đồng bộ Cookie SAPC"})
        except Exception as e:
            results["synced"].append({"service": "SAPC", "success": False, "error": str(e)})

    return results



@router.post("/btools/open_tab")
def open_btools_chrome_tab():
    driver = get_chrome_debug_driver()
    if not driver:
        return {"success": False, "message": "Không tìm thấy trình duyệt Chrome kết nối cổng 9222"}
    btools_found = False
    for h in driver.window_handles:
        driver.switch_to.window(h)
        if "10.159.21.241" in driver.current_url:
            btools_found = True
            break
    if not btools_found:
        driver.switch_to.new_window('tab')
        driver.get("http://10.159.21.241:9267/B_tools_v2/")
    return {"success": True, "message": "Đã mở tab BTools trên trình duyệt Chrome"}


@router.get("/services/status")
def get_all_services_status(request: Request, force: str = "0", tts_new_token: str = ""):
    force_check = force in ("1", "true", "yes")
    health = get_services_health(
        force=force_check, 
        tts_new_token=tts_new_token
    )
    return {
        "success": True,
        "services": health
    }


@router.get("/ttsnew/extract_token")
@router.post("/ttsnew/extract_token")
def extract_ttsnew_token_from_browser(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    if client_ip not in ("127.0.0.1", "localhost", "::1"):
        return {"success": False, "message": "Chỉ máy chủ Admin mới có quyền trích xuất token từ Chrome."}
    tok = extract_token_from_browser()
    if tok:
        return {"success": True, "token": tok, "message": "Đã trích xuất token TTS Mới từ Chrome máy chủ"}
    return {"success": False, "message": "Không tìm thấy phiên TTS Mới trên Chrome máy chủ (cổng 9222)"}
