# routers/customer_position.py
# FastAPI Native Router cho Module Tra Cứu Vị Trí Thuê Bao & Bản Đồ Cell BTS
# Tương thích 100% với CustomerPosition, hoạt động trực tiếp không cần Flask

import os
import sys
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

BASE_DIR = Path(__file__).resolve().parent.parent
CP_DIR = BASE_DIR / "CustomerPosition"
if str(CP_DIR) not in sys.path:
    sys.path.insert(0, str(CP_DIR))

# Import các service lõi từ CustomerPosition
from CustomerPosition import config
from CustomerPosition.excel_service import excel_service
from CustomerPosition.geocode_service import get_address_details
from CustomerPosition.enodebid import (
    tra_cell_tu_so_dien_thoai,
    test_subscriber_cookie,
    login_subscriber_check,
    get_active_auth_cookies
)
from CustomerPosition.npmran_kpi import get_cell_traffic_kpi, test_npmran_token, get_auth_token
from CustomerPosition.fms_service import query_fms_alarms, test_fms_cookie, get_fms_session

router = APIRouter(prefix="/vitri", tags=["CustomerPosition"])
root_router = APIRouter(tags=["CustomerPosition_RootAPI"])

def register_api(path: str, methods: list = ["GET"]):
    """Decorator đăng ký route vào cả /vitri/... và /... để tương thích 100% frontend"""
    def decorator(func):
        router.add_api_route(path, func, methods=methods)
        root_router.add_api_route(path, func, methods=methods)
        return func
    return decorator


def get_cp_html() -> str:
    """Đọc file giao diện index.html của CustomerPosition."""
    html_path = CP_DIR / "templates" / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Không tìm thấy file giao diện CustomerPosition/templates/index.html</h3>"


# ==============================================================================
# GIAO DIỆN WEB BẢN ĐỒ VỊ TRÍ
# ==============================================================================
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def serve_customer_position_page(request: Request):
    """Trang chủ bản đồ tra cứu vị trí thuê bao & Cell BTS."""
    return HTMLResponse(
        content=get_cp_html(),
        status_code=200,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


# ==============================================================================
# LOGIC TRA CỨU LÕI (PYTHON NATIVE)
# ==============================================================================
def do_lookup_msisdn(msisdn: str, fetch_traffic: bool = False, fetch_fms: bool = False) -> dict:
    msisdn = str(msisdn).strip()
    if not msisdn:
        return {'success': False, 'error': 'Vui lòng nhập số điện thoại (MSISDN).'}

    subscriber_info = tra_cell_tu_so_dien_thoai(msisdn)
    if not subscriber_info or 'error' in subscriber_info:
        return {
            'success': False,
            'error': subscriber_info.get('error', 'Lỗi khi tra cứu thông tin mạng.') if subscriber_info else 'Không nhận được dữ liệu từ hệ thống.',
            'is_cookie_error': subscriber_info.get('is_cookie_error', False) if subscriber_info else False,
            'subscriber': subscriber_info
        }

    lac = subscriber_info.get('LAC', '')
    ci = subscriber_info.get('CI', '') or subscriber_info.get('CellID', '') or subscriber_info.get('Cell ID', '')
    enodeb_id = subscriber_info.get('eNodeB ID', '')

    mapping_result = excel_service.lookup_all(lac, ci, enodeb_id)

    if mapping_result.get('has_coordinates') and mapping_result.get('latitude') and mapping_result.get('longitude'):
        addr_info = get_address_details(
            mapping_result['latitude'],
            mapping_result['longitude'],
            default_address=mapping_result.get('address', ''),
            province_code=mapping_result.get('province', ''),
            district_code=mapping_result.get('district', '')
        )
        if addr_info.get('address'):
            mapping_result['address'] = addr_info['address']
        mapping_result['ward'] = addr_info.get('ward', '')
        mapping_result['district'] = addr_info.get('district') or mapping_result.get('district', '')
        mapping_result['province'] = addr_info.get('province') or mapping_result.get('province', '')
        mapping_result['province_code'] = addr_info.get('province_code') or mapping_result.get('province', '')
        mapping_result['district_code'] = addr_info.get('district_code') or mapping_result.get('district', '')

        nearby_data = excel_service.find_nearby_sites(
            mapping_result['latitude'],
            mapping_result['longitude'],
            target_site_name=mapping_result.get('site_name'),
            target_cell_name=mapping_result.get('cell_name'),
            limit=30
        )
        mapping_result['nearby_sites'] = nearby_data['nearby_sites']
        mapping_result['same_site_cells'] = nearby_data['same_site_cells']

    kpi_result = None
    fms_alarm_result = None
    cell_name = mapping_result.get('cell_name')

    if cell_name:
        if fetch_traffic:
            try:
                kpi_result = get_cell_traffic_kpi(cell_name, days=1, force_refresh=True)
            except Exception as e:
                kpi_result = {'success': False, 'error': f'Không thể lấy KPI: {str(e)}'}

        if fetch_fms:
            try:
                fms_alarm_result = query_fms_alarms(cell_name, prefix_len=10)
            except Exception as e:
                fms_alarm_result = {'has_alarm': False, 'error': f'Không thể kết nối FMS: {str(e)}'}

    return {
        'success': True,
        'msisdn': msisdn,
        'subscriber': subscriber_info,
        'location': mapping_result,
        'kpi': kpi_result,
        'fms_alarm': fms_alarm_result,
        'google_maps_key': getattr(config, 'GOOGLE_MAPS_API_KEY', '')
    }


def do_lookup_by_name(query: str, fetch_traffic: bool = False, fetch_fms: bool = False) -> dict:
    query = str(query).strip()
    if not query:
        return {'success': False, 'error': 'Vui lòng nhập Tên Cell hoặc Tên Site.'}

    lookup_res = excel_service.lookup_by_name(query)
    if not lookup_res.get('matched'):
        return {'success': False, 'error': lookup_res.get('error', f"Không tìm thấy dữ liệu cho '{query}'.")}

    cell_name = lookup_res.get('cell_name')
    site_name = lookup_res.get('site_name')

    subscriber_info = {
        'Radio': '4G' if '4G' in (cell_name or '').upper() else ('3G' if '3G' in (cell_name or '').upper() else 'Cell/Site'),
        'eNodeB ID': lookup_res.get('enodeb_id', '--'),
        'LAC': lookup_res.get('lac', '--'),
        'CI': lookup_res.get('ci', '--'),
        'ECGI': f"452-04-{lookup_res.get('enodeb_id', '')}-{lookup_res.get('ci', '')}" if lookup_res.get('enodeb_id') else '--',
        'State': f"MATCHED ({lookup_res.get('match_type', 'CELL')})",
        'Last Update': 'Tra cứu tức thời từ CSDL'
    }

    resolved_address = lookup_res.get('address', '')
    ward_val = ''
    dist_val = lookup_res.get('district', '')
    prov_val = lookup_res.get('province', '')
    prov_code = lookup_res.get('extracted_province') or lookup_res.get('province', '')
    dist_code = lookup_res.get('district', '')
    site_core = lookup_res.get('extracted_site', '')

    if lookup_res.get('has_coordinates') and lookup_res.get('latitude') and lookup_res.get('longitude'):
        addr_info = get_address_details(
            lookup_res['latitude'],
            lookup_res['longitude'],
            default_address=resolved_address,
            province_code=prov_code,
            district_code=dist_code
        )
        if addr_info.get('address'):
            resolved_address = addr_info['address']
        ward_val = addr_info.get('ward', '')
        dist_val = addr_info.get('district') or dist_val
        prov_val = addr_info.get('province') or prov_val
        prov_code = addr_info.get('province_code') or prov_code
        dist_code = addr_info.get('district_code') or dist_code

    location_result = {
        'cell_name': cell_name,
        'site_name': site_name,
        'mapping_matched': True,
        'has_coordinates': lookup_res.get('has_coordinates', False),
        'latitude': lookup_res.get('latitude'),
        'longitude': lookup_res.get('longitude'),
        'azimuth': lookup_res.get('azimuth', ''),
        'address': resolved_address,
        'ward': ward_val,
        'district': dist_val,
        'province': prov_val,
        'province_code': prov_code,
        'district_code': dist_code,
        'extracted_site': site_core,
        'extracted_province': prov_code,
        'vendor': lookup_res.get('vendor', ''),
        'match_type': lookup_res.get('match_type', 'CELL'),
        'site_cells': lookup_res.get('site_cells', []),
        'total_site_cells': lookup_res.get('total_site_cells', len(lookup_res.get('site_cells', [])))
    }

    if location_result.get('has_coordinates') and location_result.get('latitude') and location_result.get('longitude'):
        nearby_data = excel_service.find_nearby_sites(
            location_result['latitude'],
            location_result['longitude'],
            target_site_name=site_name,
            target_cell_name=cell_name,
            limit=30
        )
        location_result['nearby_sites'] = nearby_data['nearby_sites']
        location_result['same_site_cells'] = lookup_res.get('site_cells') or nearby_data['same_site_cells']

    kpi_result = None
    fms_alarm_result = None
    if cell_name:
        if fetch_traffic:
            try:
                kpi_result = get_cell_traffic_kpi(cell_name, days=1, force_refresh=True)
            except Exception as e:
                kpi_result = {'success': False, 'error': f'Không thể lấy KPI: {str(e)}'}

        if fetch_fms:
            try:
                fms_alarm_result = query_fms_alarms(cell_name, prefix_len=10)
            except Exception as e:
                fms_alarm_result = {'has_alarm': False, 'error': f'Không thể kết nối FMS: {str(e)}'}

    return {
        'success': True,
        'query': query,
        'subscriber': subscriber_info,
        'location': location_result,
        'kpi': kpi_result,
        'fms_alarm': fms_alarm_result,
        'google_maps_key': getattr(config, 'GOOGLE_MAPS_API_KEY', '')
    }


# ==============================================================================
# API ENDPOINTS CHO CLIENT APP.JS (HỖ TRỢ CẢ /vitri/api/... VÀ /api/...)
# ==============================================================================
@register_api("/api/lookup", methods=["POST"])
async def api_lookup(request: Request):
    data = await request.json()
    msisdn = data.get('msisdn', '')
    fetch_traffic = bool(data.get('fetch_traffic', False))
    fetch_fms = bool(data.get('fetch_fms', False))
    return do_lookup_msisdn(msisdn, fetch_traffic=fetch_traffic, fetch_fms=fetch_fms)


@register_api("/api/lookup-by-name", methods=["POST"])
async def api_lookup_by_name(request: Request):
    data = await request.json()
    query = data.get('query', '')
    fetch_traffic = bool(data.get('fetch_traffic', False))
    fetch_fms = bool(data.get('fetch_fms', False))
    return do_lookup_by_name(query, fetch_traffic=fetch_traffic, fetch_fms=fetch_fms)


@router.get("/api/msisdn/{msisdn:path}")
@router.get("/msisdn/{msisdn:path}")
@root_router.get("/api/msisdn/{msisdn:path}")
async def route_msisdn_api(msisdn: str, request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and not request.query_params.get("format"):
        return HTMLResponse(content=get_cp_html())
    return do_lookup_msisdn(msisdn)


@router.get("/api/cell/{cell_name:path}")
@router.get("/api/cellid/{cell_name:path}")
@router.get("/cell/{cell_name:path}")
@router.get("/cellid/{cell_name:path}")
@root_router.get("/api/cell/{cell_name:path}")
@root_router.get("/api/cellid/{cell_name:path}")
async def route_cell_api(cell_name: str, request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and not request.query_params.get("format"):
        return HTMLResponse(content=get_cp_html())
    return do_lookup_by_name(cell_name)


@register_api("/api/reverse-geocode", methods=["GET", "POST"])
async def api_reverse_geocode(request: Request):
    lat = None
    lng = None
    if request.method == "POST":
        try:
            body = await request.json()
            lat = body.get("latitude") or body.get("lat")
            lng = body.get("longitude") or body.get("lng") or body.get("long")
        except Exception:
            pass
    if not lat or not lng:
        lat = request.query_params.get("lat") or request.query_params.get("latitude")
        lng = request.query_params.get("long") or request.query_params.get("lng") or request.query_params.get("longitude")

    if not lat or not lng:
        return JSONResponse({"success": False, "error": "Thiếu tọa độ lat/long"}, status_code=400)

    res = get_address_details(lat, lng)
    return res


@register_api("/api/excel-status", methods=["GET"])
async def api_excel_status():
    return excel_service.get_status()


@register_api("/api/admin-check", methods=["GET", "POST"])
async def api_admin_check():
    return {"is_admin": True, "success": True}


@register_api("/api/config", methods=["GET", "POST"])
async def api_config():
    return {
        "google_maps_api_key": getattr(config, 'GOOGLE_MAPS_API_KEY', ''),
        "success": True
    }


@register_api("/api/cell-kpi", methods=["POST"])
async def api_cell_kpi(request: Request):
    data = await request.json()
    cell = data.get("cell_name", "")
    days = data.get("days", 1)
    return get_cell_traffic_kpi(cell, days=days, force_refresh=True)


@register_api("/api/fms-alarm", methods=["POST"])
async def api_fms_alarm(request: Request):
    data = await request.json()
    cell = data.get("cell_name", "")
    return query_fms_alarms(cell)


@register_api("/api/nearby-sites", methods=["GET", "POST"])
async def api_nearby_sites(request: Request):
    lat = None
    lng = None
    if request.method == "POST":
        try:
            b = await request.json()
            lat = b.get('lat') or b.get('latitude')
            lng = b.get('lng') or b.get('longitude')
        except Exception:
            pass
    if not lat or not lng:
        lat = request.query_params.get('lat')
        lng = request.query_params.get('lng') or request.query_params.get('long')
    if not lat or not lng:
        return {"success": False, "error": "Thiếu tọa độ"}
    try:
        return excel_service.find_nearby_sites(float(lat), float(lng))
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_api("/api/cookie-config", methods=["GET", "POST"])
async def api_cookie_config(request: Request):
    if request.method == "POST":
        try:
            data = await request.json()
            cookie_val = data.get("cookie", "")
            if cookie_val:
                config.save_subscriber_cookie(cookie_val)
                return {"success": True, "message": "Đã lưu cookie thành công"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    # GET
    cookies, source = get_active_auth_cookies()
    return {
        "success": True,
        "has_cookie": bool(cookies),
        "source": source,
        "cookie_preview": ".AspNet.ApplicationCookie=" + (cookies.get(".AspNet.ApplicationCookie", "")[:25] + "...") if cookies.get(".AspNet.ApplicationCookie") else ""
    }


@register_api("/api/cookie-test", methods=["POST"])
async def api_cookie_test(request: Request):
    try:
        data = await request.json()
        cookie_val = data.get("cookie", "")
        return test_subscriber_cookie(cookie_val)
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_api("/api/subscriber-login", methods=["POST"])
async def api_subscriber_login(request: Request):
    try:
        data = await request.json()
        user = data.get("username", "")
        pwd = data.get("password", "")
        ok, res = login_subscriber_check(user, pwd)
        return {"success": ok, "message" if ok else "error": res}
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_api("/api/fms-cookie", methods=["GET", "POST"])
async def api_fms_cookie_endpoint(request: Request):
    if request.method == "POST":
        try:
            data = await request.json()
            c_val = data.get("cookie", "")
            if c_val:
                config.save_fms_cookie(c_val)
                return {"success": True, "message": "Đã lưu FMS cookie"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    c = config.get_fms_cookie()
    return {"success": True, "has_cookie": bool(c)}


@register_api("/api/fms-test", methods=["POST"])
async def api_fms_test_endpoint(request: Request):
    try:
        data = await request.json()
        return test_fms_cookie(data.get("cookie"))
    except Exception as e:
        return {"success": False, "error": str(e)}


@register_api("/api/npmran-token", methods=["GET", "POST"])
async def api_npmran_token_endpoint(request: Request):
    if request.method == "POST":
        try:
            data = await request.json()
            tok = data.get("token", "")
            if tok:
                config.save_npmran_token(tok)
                return {"success": True, "message": "Đã lưu NPMRAN token"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    t = get_auth_token()
    return {"success": True, "has_token": bool(t)}


@register_api("/api/npmran-test", methods=["POST"])
async def api_npmran_test_endpoint(request: Request):
    try:
        data = await request.json()
        return test_npmran_token(data.get("token"))
    except Exception as e:
        return {"success": False, "error": str(e)}

