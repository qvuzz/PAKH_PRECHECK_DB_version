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
    is_valid, msg = save_btools_cookie(cookie_input)
    return {
        "success": is_valid,
        "connected": is_valid,
        "message": msg
    }


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
def get_all_services_status(force: str = "0"):
    force_check = force in ("1", "true", "yes")
    health = get_services_health(force=force_check)
    return {
        "success": True,
        "services": health
    }


@router.get("/ttsnew/extract_token")
@router.post("/ttsnew/extract_token")
def extract_ttsnew_token_from_browser():
    tok = extract_token_from_browser()
    if tok:
        return {"success": True, "token": tok, "message": "Đã trích xuất token TTS Mới từ Chrome máy chủ"}
    return {"success": False, "message": "Không tìm thấy phiên TTS Mới trên Chrome máy chủ (cổng 9222)"}
