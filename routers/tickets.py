# routers/tickets.py
# Quản lý danh sách phiếu, phân tích thống kê, xuất Excel và các tác vụ đóng phiếu

import os
import sys
import json
import time
import threading
from datetime import datetime, timedelta, timezone
ICT = timezone(timedelta(hours=7))
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse

from db_manager import (
    get_all_tickets, 
    get_system_counts, 
    get_ticket_counts,
    get_closed_tickets_analytics, 
    get_db_connection, 
    update_ticket_field, 
    delete_all_tickets,
    is_mobile_internet_ticket
)
from services.state import state
from services.session_manager import ACTIVE_LAN_SESSIONS, resolve_ttsnew_token

BASE_DIR = Path(__file__).resolve().parent.parent
router = APIRouter(prefix="/api", tags=["Quản lý Phiếu Sự Cố (Tickets)"])


@router.get("/tickets")
def get_tickets_api(
    request: Request,
    search: str = None, 
    status: str = None, 
    tab: str = None, 
    source: str = "tts_new", 
    service_type: str = "data",
    region: str = None
):
    src_f = None if source == "all" else source
    srv_f = None if service_type == "all" else service_type

    # Chỉ phân hệ Data (Mobile Internet) mới áp dụng bộ lọc nhận định kỹ thuật
    status_f = status if (srv_f == "data" and status != "all") else None

    # 🎯 Nhận diện quyền truy cập và Phân vùng 3 Miền
    client_ip = request.client.host if request and request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")
    client_tok = request.headers.get("Authorization") or request.cookies.get("TOKEN") or ""

    effective_region = "ALL"
    user_role = "admin"
    current_user_name = "Quản trị viên"

    _, uinfo = resolve_ttsnew_token(client_ip, is_local=is_local, client_tok=client_tok)
    if not uinfo and client_ip in ACTIVE_LAN_SESSIONS:
        sess = ACTIVE_LAN_SESSIONS.get(client_ip) or {}
        uinfo = sess.get("ttsnew_user") or sess.get("user") or {}

    from region_detector import is_superadmin, detect_user_region, is_user_permitted

    user_reg = detect_user_region(uinfo) if uinfo else None
    is_region_locked = False

    if is_local or is_superadmin(uinfo):
        user_role = "admin"
        effective_region = (region or "ALL").upper()
        current_user_name = (uinfo.get("displayName") or uinfo.get("userName") or uinfo.get("HoTen") or "Quản trị viên") if uinfo else "Quản trị viên"
        is_region_locked = False
    elif uinfo:
        # Kiểm soát phân quyền nghiêm ngặt: User phải có trong whitelist user_regions.json
        permitted, matched_u = is_user_permitted(uinfo)
        if not permitted:
            return {
                "tickets": [],
                "total_count": 0,
                "closed_count": 0,
                "active_count": 0,
                "system_counts": {},
                "region": "ALL",
                "user_role": "unauthorized",
                "user_name": uinfo.get("displayName") or uinfo.get("userName") or "Chưa cấp quyền",
                "message": "Tài khoản của bạn chưa được cấp quyền truy cập WebApp. Vui lòng liên hệ Quản trị viên để khai báo thông tin và phân vùng TT SOC."
            }

        user_role = "ktv"
        # User khu vực nào thì chỉ thấy phiếu ở KV đó thôi:
        if user_reg and user_reg in ("MB", "MT", "MN"):
            effective_region = user_reg
            is_region_locked = True
        elif region:
            effective_region = region.upper()
            is_region_locked = False
        else:
            effective_region = "ALL"
            is_region_locked = False
        current_user_name = uinfo.get("displayName") or uinfo.get("userName") or "KTV"
    else:
        user_role = "guest"
        effective_region = (region or "ALL").upper()
        is_region_locked = False
        current_user_name = ""

    tickets = get_all_tickets(
        search=search, 
        status_filter=status_f, 
        tab_filter=tab, 
        source=src_f, 
        service_type=srv_f,
        region=effective_region
    )

    # Tự động bù tóm tắt 6 mục cho các phiếu Mobile Internet nếu chưa có hoặc đang là 'null'
    try:
        from db_manager import is_mobile_internet_ticket
        from ai_interpreter import generate_ticket_summary
        need_db_update = []
        for t in tickets:
            pkg = t.get("package_title") or ""
            tc = t.get("ticket_content") or ""
            ai_s = str(t.get("ai_summary") or "").strip()
            if is_mobile_internet_ticket(pkg) and tc:
                if not ai_s or ai_s == "null" or ai_s == "None" or not ai_s.startswith("1.") or ai_s == tc.strip():
                    new_sum = generate_ticket_summary(pkg, tc, phone=t.get("phone", ""))
                    if new_sum and new_sum.strip().startswith("1."):
                        t["ai_summary"] = new_sum
                        need_db_update.append((new_sum, t.get("ticket_code"), t.get("phone")))

        if need_db_update:
            conn_u = get_db_connection()
            with conn_u:
                for sum_val, t_code, ph in need_db_update:
                    if t_code:
                        clean_c = str(t_code).split("\n")[0].strip()
                        conn_u.execute("UPDATE tickets SET ai_summary = ? WHERE ticket_code = ? OR ticket_code LIKE ?", (sum_val, clean_c, f"{clean_c}%"))
                    elif ph:
                        conn_u.execute("UPDATE tickets SET ai_summary = ? WHERE phone = ?", (sum_val, ph))
            conn_u.close()
    except Exception:
        pass

    sys_counts = get_system_counts(region=effective_region)
    total_cnt, closed_cnt, active_cnt = get_ticket_counts(
        source=src_f, 
        service_type=srv_f, 
        search=search,
        region=effective_region
    )

    return {
        "tickets": tickets,
        "total_count": total_cnt,
        "closed_count": closed_cnt,
        "active_count": active_cnt,
        "system_counts": sys_counts,
        "region": effective_region,
        "user_region": user_reg,
        "is_region_locked": is_region_locked,
        "user_role": user_role,
        "user_name": current_user_name
    }


@router.get("/tickets/closed_stats")
def get_closed_stats_api(
    request: Request,
    period: str = "all", 
    source: str = "all", 
    service_type: str = "all",
    region: Optional[str] = None
):
    src_f = None if source == "all" else source
    srv_f = None if service_type == "all" else service_type

    # 🎯 Nhận diện quyền truy cập và Phân vùng 3 Miền cho Thống kê phiếu đã đóng
    client_ip = request.client.host if request and request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")
    client_tok = request.headers.get("Authorization") or request.cookies.get("TOKEN") or ""

    effective_region = "ALL"
    is_region_locked = False
    _, uinfo = resolve_ttsnew_token(client_ip, is_local=is_local, client_tok=client_tok)
    if not uinfo and client_ip in ACTIVE_LAN_SESSIONS:
        sess = ACTIVE_LAN_SESSIONS.get(client_ip) or {}
        uinfo = sess.get("ttsnew_user") or sess.get("user") or {}

    from region_detector import is_superadmin, detect_user_region, is_user_permitted

    user_reg = detect_user_region(uinfo) if uinfo else None

    if is_local or is_superadmin(uinfo):
        effective_region = (region or "ALL").upper()
        is_region_locked = False
    elif uinfo:
        permitted, _ = is_user_permitted(uinfo)
        if not permitted:
            return {
                "total": 0, "auto_cnt": 0, "auto_percent": 0, "manual_cnt": 0, "manual_percent": 0,
                "synced_cnt": 0, "synced_percent": 0, "tool_closed_cnt": 0,
                "today_cnt": 0, "today_manual_cnt": 0, "today_synced_cnt": 0, "today_total_cnt": 0,
                "tts_new_cnt": 0, "tts_old_cnt": 0, "data_cnt": 0, "call_cnt": 0, "sms_cnt": 0, "other_cnt": 0, "voice_cnt": 0,
                "by_diagnosis": [], "daily_trend": [], "top_packages": [], "staff_list": [],
                "effective_region": "ALL",
                "user_role": "unauthorized",
                "message": "Chưa được cấp quyền truy cập"
            }
        # KTV chỉ thấy phiếu ở khu vực của họ
        if user_reg and user_reg in ("MB", "MT", "MN"):
            effective_region = user_reg
            is_region_locked = True
        else:
            effective_region = (region or "ALL").upper()
            is_region_locked = False
    else:
        effective_region = (region or "ALL").upper()
        is_region_locked = False

    stats = get_closed_tickets_analytics(
        time_filter=period, 
        source_filter=src_f, 
        service_filter=srv_f,
        region=effective_region
    )
    stats["effective_region"] = effective_region
    stats["user_region"] = user_reg
    stats["is_region_locked"] = is_region_locked
    return stats


@router.get("/export_excel")
def export_excel_api(source: str = "tts_new"):
    from report_bot import export_diagnostics_to_excel
    src_f = None if source == "all" else source
    tickets = get_all_tickets(source=src_f)
    if not tickets:
        return Response(content="Database trống, chưa có phiếu để xuất Excel.", status_code=400)

    out_dir = BASE_DIR / "result"
    os.makedirs(out_dir, exist_ok=True)
    prefix = "BaoCao_TTS_NEW"
    out_file = out_dir / f"{prefix}_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    saved_path = export_diagnostics_to_excel(tickets, out_file)

    if os.path.exists(saved_path):
        return FileResponse(
            saved_path, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(saved_path)
        )
    return Response(content="Lỗi xuất file Excel", status_code=500)


_CELL_INFO_CACHE = {}
_CELL_LOCATION_CACHE = {}


VNPT_PROVINCE_MAP = {
    'AGG': 'An Giang', 'BDG': 'Bình Dương', 'BDH': 'Bình Định', 'BGG': 'Bắc Giang', 'BKN': 'Bắc Kạn',
    'BLU': 'Bạc Liêu', 'BNH': 'Bắc Ninh', 'BPC': 'Bình Phước', 'BTE': 'Bến Tre', 'BTN': 'Bình Thuận',
    'CBG': 'Cao Bằng', 'CMU': 'Cà Mau', 'CTO': 'Cần Thơ', 'CTH': 'Cần Thơ', 'DBN': 'Điện Biên',
    'DLK': 'Đắk Lắk', 'DNG': 'Đà Nẵng', 'DNI': 'Đồng Nai', 'DNO': 'Đắk Nông', 'DTP': 'Đồng Tháp',
    'GLI': 'Gia Lai', 'HBH': 'Hòa Bình', 'HCM': 'TP. Hồ Chí Minh', 'HDG': 'Hải Dương', 'HGG': 'Hà Giang',
    'HNI': 'Hà Nội', 'HNO': 'Hà Nội', 'HNM': 'Hà Nam', 'HPG': 'Hải Phòng', 'HTH': 'Hà Tĩnh',
    'HUE': 'Thừa Thiên Huế', 'HUG': 'Hậu Giang', 'HYN': 'Hưng Yên', 'KGG': 'Kiên Giang', 'KHA': 'Khánh Hòa',
    'KTM': 'Kon Tum', 'LAN': 'Long An', 'LCI': 'Lào Cai', 'LCU': 'Lai Châu', 'LDG': 'Lâm Đồng',
    'LSN': 'Lạng Sơn', 'NAN': 'Nghệ An', 'NBH': 'Ninh Bình', 'NDH': 'Nam Định', 'NTN': 'Ninh Thuận',
    'PTO': 'Phú Thọ', 'PYN': 'Phú Yên', 'QBH': 'Quảng Bình', 'QNH': 'Quảng Ninh', 'QNI': 'Quảng Ngãi',
    'QNM': 'Quảng Nam', 'QTI': 'Quảng Trị', 'SLA': 'Sơn La', 'STG': 'Sóc Trăng', 'TBH': 'Thái Bình',
    'TGG': 'Tiền Giang', 'THA': 'Thanh Hóa', 'TNH': 'Tây Ninh', 'TNN': 'Thái Nguyên', 'TQG': 'Tuyên Quang',
    'TVH': 'Trà Vinh', 'VLG': 'Vĩnh Long', 'VPC': 'Vĩnh Phúc', 'YBI': 'Yên Bái'
}


def normalize_vn_commune_and_province(ward, district, province, address):
    """
    Chuẩn hóa cấp hành chính Việt Nam:
    CHỈ LẤY DUY NHẤT: Phường/Xã và Tỉnh/TP (loại bỏ hoàn toàn cấp Thôn/Ấp/Xóm và mã trạm viễn thông như PLO, DLI...).
    """
    import re
    COMMUNE_PREFIXES = ('xã ', 'phường ', 'thị trấn ', 'tt. ', 'p. ', 'x. ', 'tt ', 'p ')
    HAMLET_PREFIXES = ('thôn ', 'ấp ', 'bản ', 'xóm ', 'tổ ', 'khu phố ', 'tổ dân phố ', 'kdc ', 'kdt ')

    w = (ward or '').strip()
    d = (district or '').strip()
    p = (province or '').strip()
    addr = (address or '').strip()

    # 1. Trích xuất Tỉnh/TP chuẩn: ưu tiên từ chuỗi address đầy đủ (VD: '... Tỉnh Cà Mau, Việt Nam')
    if addr:
        m_prov = re.search(r'(?:,\s*)(Tỉnh\s+[^,]+|Thành phố\s+[^,]+)', addr, re.I)
        if m_prov:
            p = m_prov.group(1).strip()

    # 🎯 Chuẩn hóa về 34 Tỉnh/Thành phố mới của Việt Nam
    from region_detector import normalize_to_new_province
    new_prov, _ = normalize_to_new_province(p)
    if not new_prov and addr:
        new_prov, _ = normalize_to_new_province(addr)
    if new_prov:
        p = new_prov
    elif p.upper() in VNPT_PROVINCE_MAP:
        mapped, _ = normalize_to_new_province(VNPT_PROVINCE_MAP[p.upper()])
        p = mapped or VNPT_PROVINCE_MAP[p.upper()]

    # 2. Trích xuất Phường/Xã chuẩn:
    # 2.1 Nếu district thực chất là Phường/Xã (VD: district = 'Xã Phong Hiệp', 'Xã Hòa Bắc')
    if any(d.lower().startswith(prefix) for prefix in COMMUNE_PREFIXES):
        w = d
    # 2.2 Hoặc nếu ward hiện tại không phải Phường/Xã (là Thôn/Ấp hoặc địa danh nhỏ như 'Chủ Chí')
    elif not any(w.lower().startswith(prefix) for prefix in COMMUNE_PREFIXES) and addr:
        m_commune = re.search(r'(?:,\s*|\b)(Xã\s+[^,]+|Phường\s+[^,]+|Thị trấn\s+[^,]+)', addr, re.I)
        if m_commune:
            w = m_commune.group(1).strip()
        else:
            if any(w.lower().startswith(prefix) for prefix in HAMLET_PREFIXES):
                w = ''

    # 3. YÊU CẦU: ONLY PHƯỜNG/XÃ VÀ TỈNH/TP (Không lấy Quận/Huyện, không lấy Thôn/Ấp, không lấy mã trạm như PLO)
    loc_parts = []
    if w:
        loc_parts.append(w)
    if p:
        loc_parts.append(p)

    return w, p, ', '.join(loc_parts)


_DETECTED_1708_BASE_URL = None
_LAST_1708_CHECK_TIME = 0


def get_1708_base_url() -> str:
    global _DETECTED_1708_BASE_URL, _LAST_1708_CHECK_TIME
    now = time.time()
    if _DETECTED_1708_BASE_URL and (now - _LAST_1708_CHECK_TIME < 300):
        return _DETECTED_1708_BASE_URL

    env_url = (os.getenv("PORT_1708_URL") or os.getenv("GEOCODE_URL") or "").rstrip("/")
    candidates = []
    if env_url:
        candidates.append(env_url)

    # Ưu tiên các kênh giao tiếp trong Docker bridge và máy Host
    candidates.extend([
        "http://vnpt_customer_position_app:1708",
        "http://vnpt-customer-position:1708",
        "http://host.docker.internal:1708",
        "http://172.17.0.1:1708",
        "http://10.155.59.158:1708",
        "http://127.0.0.1:1708",
    ])

    import requests
    seen = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            r = requests.get(f"{cand}/", timeout=1.2)
            if r.status_code in (200, 302, 307):
                _DETECTED_1708_BASE_URL = cand
                _LAST_1708_CHECK_TIME = now
                print(f"🎯 [1708 Service] Đã kết nối CustomerPosition tại: {cand}")
                return cand
        except Exception:
            continue

    fallback = env_url or "http://vnpt_customer_position_app:1708"
    _DETECTED_1708_BASE_URL = fallback
    _LAST_1708_CHECK_TIME = now
    return fallback


@router.get("/cell_info/{phone}")
def get_cell_info_api(phone: str):
    """
    Tra cứu Cell Name, Phường/Xã, Tỉnh/TP từ service CustomerPosition (Link 1).
    URL: http://127.0.0.1:1708/api/msisdn/84... hoặc host.docker.internal:1708
    Kèm fallback trực tiếp từ Core SAPC nếu CustomerPosition chưa có session.
    """
    phone_clean = str(phone or "").strip()
    if not phone_clean:
        return {"success": False, "cell_name": None, "radio": None, "ward": None, "province": None, "location_str": ""}
    
    # Chuẩn hóa về format 84...
    if phone_clean.startswith("0"):
        phone_84 = "84" + phone_clean[1:]
    elif not phone_clean.startswith("84") and len(phone_clean) == 9:
        phone_84 = "84" + phone_clean
    else:
        phone_84 = phone_clean

    now_t = time.time()
    cached = _CELL_INFO_CACHE.get(phone_84)
    if cached and (now_t - cached.get("time", 0) < 600):
        # Chỉ trả về ngay từ cache nếu đã có Cell Name hoặc Phường/Xã chuẩn
        cached_data = cached.get("data", {})
        if cached_data.get("cell_name") or cached_data.get("ward"):
            return cached_data

    import requests
    base_1708 = get_1708_base_url()
    target_urls = [
        f"{base_1708}/api/msisdn/{phone_84}",
    ]
    if phone_84.startswith("84"):
        target_urls.append(f"{base_1708}/api/msisdn/0{phone_84[2:]}")

    cell_name = None
    radio = "4G"
    site_name = None
    ward = None
    province = None
    district = None
    address = None

    for url in target_urls:
        try:
            resp = requests.get(url, headers={"Accept": "application/json"}, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, dict):
                    loc_dict = data.get("location") or {}
                    sum_dict = data.get("summary") or {}
                    cell_name = (data.get("cell") or data.get("cell_name") or sum_dict.get("current_cell") or loc_dict.get("cell_name") or "").strip() or None
                    ward = (data.get("ward") or data.get("phuong_xa") or sum_dict.get("ward") or loc_dict.get("ward") or "").strip() or None
                    province = (data.get("province") or data.get("tinh_tp") or sum_dict.get("province") or loc_dict.get("province") or "").strip() or None
                    district = (data.get("district") or data.get("quan_huyen") or sum_dict.get("district") or loc_dict.get("district") or "").strip() or None
                    address = (data.get("address") or data.get("dia_chi") or loc_dict.get("address") or "").strip() or None
                    site_name = (data.get("site") or sum_dict.get("current_site") or loc_dict.get("site_name") or "").strip() or None

                    if cell_name:
                        c_upper = cell_name.upper()
                        if c_upper.startswith("5G"):
                            radio = "5G"
                        elif c_upper.startswith("3G"):
                            radio = "3G"
                        elif c_upper.startswith("2G"):
                            radio = "2G"
                        else:
                            radio = "4G"
                        break
        except Exception:
            continue

    # Fallback endpoint cũ nếu chưa có dữ liệu
    if not cell_name and not ward:
        try:
            old_url = f"{base_1708}/msisdn/{phone_84}"
            resp = requests.get(old_url, headers={"Accept": "application/json"}, timeout=3.5)
            if resp.status_code == 200:
                d = resp.json()
                summary = d.get("summary") or {}
                location = d.get("location") or {}
                subscriber = d.get("subscriber") or {}
                cell_name = summary.get("current_cell") or location.get("cell_name") or (d.get("cell") or "")
                radio = subscriber.get("Radio") or "4G"
                site_name = summary.get("current_site") or location.get("site_name")
        except Exception:
            pass

    # 🎯 Fallback nội bộ: Tra cứu trực tiếp từ Core SAPC (10.155.42.218) nếu port 1708 chưa có cell
    if not cell_name:
        try:
            try:
                from sapccheck.msisdn_info import tra_cell_tu_so_dien_thoai
            except Exception:
                import sys
                from pathlib import Path
                root_d = Path(__file__).resolve().parent.parent
                sapc_d = root_d / "sapccheck"
                if str(root_d) not in sys.path:
                    sys.path.insert(0, str(root_d))
                if str(sapc_d) not in sys.path:
                    sys.path.insert(0, str(sapc_d))
                try:
                    from sapccheck.msisdn_info import tra_cell_tu_so_dien_thoai
                except Exception:
                    from msisdn_info import tra_cell_tu_so_dien_thoai
            sapc_res = tra_cell_tu_so_dien_thoai(phone_84)
            if sapc_res and isinstance(sapc_res, dict) and not sapc_res.get("error"):
                c_sapc = sapc_res.get("CellName") or sapc_res.get("cell_name")
                if c_sapc:
                    cell_name = str(c_sapc).strip()
                r_sapc = sapc_res.get("Radio") or sapc_res.get("radio")
                if r_sapc:
                    radio = str(r_sapc).strip()
        except Exception as sapc_ex:
            print(f"⚠️ [CellInfo Fallback SAPC] Lỗi tra cứu: {sapc_ex}")

    coord_lat = None
    coord_lng = None
    map_url = None

    # 🎯 Nếu có cell_name, ưu tiên lấy Phường/Xã và Tỉnh/TP chuẩn từ Google Maps (reverse-geocode port 1708) qua get_cell_location_api
    if cell_name:
        try:
            loc_res = get_cell_location_api(cell_name, phone=phone_84)
            if loc_res and (loc_res.get("ward") or loc_res.get("province") or loc_res.get("location_str")):
                if loc_res.get("ward"):
                    ward = loc_res.get("ward")
                if loc_res.get("province"):
                    province = loc_res.get("province")
                if loc_res.get("district"):
                    district = loc_res.get("district")
                if loc_res.get("address"):
                    address = loc_res.get("address")
                if loc_res.get("site"):
                    site_name = loc_res.get("site")
                coord_lat = loc_res.get("latitude")
                coord_lng = loc_res.get("longitude")
                map_url = loc_res.get("map_url")
        except Exception as e:
            print(f"⚠️ [CellInfo] Lỗi gọi get_cell_location_api cho cell {cell_name}: {e}")

    norm_w, norm_p, loc_str = normalize_vn_commune_and_province(ward, district, province, address)

    result = {
        "success": bool(cell_name or norm_w or norm_p),
        "cell_name": cell_name,
        "radio": radio,
        "site_name": site_name,
        "ward": norm_w,
        "province": norm_p,
        "district": "",
        "address": address,
        "location_str": loc_str,
        "latitude": coord_lat,
        "longitude": coord_lng,
        "map_url": map_url,
        "cell_url": f"http://127.0.0.1:1708/cellid/{cell_name}" if cell_name else None
    }
    _CELL_INFO_CACHE[phone_84] = {"time": now_t, "data": result}
    return result


@router.get("/cell_location/{cell_id:path}")
def get_cell_location_api(
    cell_id: str,
    lat: Optional[str] = None,
    long: Optional[str] = None,
    lng: Optional[str] = None,
    phone: Optional[str] = None
):
    """
    Tra cứu Phường/Xã, Tỉnh/TP từ Cell ID service CustomerPosition (Link 2).
    - URL chính: http://127.0.0.1:1708/api/cell/{cell_id}
    - Fallback khi thiếu data: Sử dụng tọa độ (lat/long) từ CEM gọi
      http://127.0.0.1:1708/api/reverse-geocode?lat=...&long=...
    """
    clean_cell = str(cell_id or "").strip()
    if not clean_cell:
        return {"success": False, "cell": None, "ward": None, "province": None, "location_str": ""}

    now_t = time.time()
    cached = _CELL_LOCATION_CACHE.get(clean_cell)
    if cached and (now_t - cached.get("time", 0) < 3600):
        # Chỉ trả về ngay từ cache nếu đã có Phường/Xã chuẩn (bắt đầu bằng Xã, Phường, Thị trấn)
        c_ward = (cached.get("data", {}).get("ward") or "").lower()
        COMMUNE_PREFIXES = ('xã ', 'phường ', 'thị trấn ', 'tt. ', 'p. ', 'x. ', 'tt ', 'p ')
        if any(c_ward.startswith(pfx) for pfx in COMMUNE_PREFIXES):
            return cached["data"]

    import requests
    import re
    ward = None
    province = None
    district = None
    address = None
    site = None
    cell_name = clean_cell
    coord_lat = lat
    coord_lng = long or lng

    base_1708 = get_1708_base_url()

    def _fetch_from_1708(query_target):
        nonlocal ward, province, district, address, site, cell_name
        try:
            resp = requests.get(f"{base_1708}/api/cell/{query_target}", headers={"Accept": "application/json"}, timeout=4.0)
            if resp.status_code == 200:
                data = resp.json()
                if data and isinstance(data, dict) and data.get("success") is not False:
                    w = (data.get("ward") or data.get("phuong_xa") or (data.get("summary") or {}).get("ward") or "").strip() or None
                    p = (data.get("province") or data.get("tinh_tp") or (data.get("summary") or {}).get("province") or "").strip() or None
                    if w or p:
                        ward = w
                        province = p
                        district = (data.get("district") or data.get("quan_huyen") or (data.get("summary") or {}).get("district") or "").strip() or None
                        address = (data.get("address") or data.get("dia_chi") or "").strip() or None
                        site = (data.get("site") or (data.get("summary") or {}).get("site") or "").strip() or None
                        cell_name = (data.get("cell") or clean_cell).strip()
                        return True
        except Exception:
            pass
        return False

    # 1. Tra cứu theo tên Cell ID gốc
    found = _fetch_from_1708(clean_cell)

    # 2. Nếu không tìm thấy, tự động fallback bóc tách Site + Tỉnh (VD: 4G-TDM074M12-BDG -> TDM074_BDG -> TDM074)
    if not found:
        prov_m = re.search(r'[-_]([A-Z]{3})$', clean_cell, re.I)
        prov = prov_m.group(1).upper() if prov_m else ''
        site_m = re.search(r'(?:[2-5]G[-_]|UL[-_]|DL[-_])?([A-Z]{2,4}\d{2,4})', clean_cell, re.I)
        site_code = site_m.group(1).upper() if site_m else ''

        if site_code and prov:
            found = _fetch_from_1708(f"{site_code}_{prov}")
            if not found:
                found = _fetch_from_1708(f"{site_code}-{prov}")
        if not found and site_code:
            found = _fetch_from_1708(site_code)

    # 3. 🎯 Fallback Reverse-Geocode qua tọa độ lat/long từ CEM nếu 1708 thiếu data Phường/Xã/Địa chỉ
    if not ward or not address:
        if not coord_lat or not coord_lng:
            try:
                from cem_client import get_cell_coordinates
                c_lat, c_lng = get_cell_coordinates(clean_cell, phone=phone)
                if c_lat and c_lng:
                    coord_lat, coord_lng = c_lat, c_lng
            except Exception:
                pass

        if coord_lat and coord_lng:
            try:
                geo_resp = requests.get(
                    f"{base_1708}/api/reverse-geocode",
                    params={"lat": coord_lat, "long": coord_lng, "lng": coord_lng},
                    timeout=4.0
                )
                if geo_resp.status_code == 200:
                    geo_data = geo_resp.json()
                    if geo_data and geo_data.get("success") is not False:
                        g_ward = (geo_data.get("ward") or "").strip()
                        g_prov = (geo_data.get("province") or "").strip()
                        g_dist = (geo_data.get("district") or "").strip()
                        g_addr = (geo_data.get("address") or "").strip()

                        if g_ward and not ward:
                            ward = g_ward
                        if g_prov and (not province or len(province) <= 3):
                            province = g_prov
                        if g_dist and not district:
                            district = g_dist
                        if g_addr and not address:
                            address = g_addr
            except Exception:
                pass

    norm_w, norm_p, loc_str = normalize_vn_commune_and_province(ward, district, province, address)

    result = {
        "success": bool(norm_w or norm_p or address),
        "cell": cell_name,
        "ward": norm_w,
        "province": norm_p,
        "district": "",
        "address": address,
        "site": site,
        "latitude": coord_lat,
        "longitude": coord_lng,
        "location_str": loc_str,
        "cell_url": f"http://127.0.0.1:1708/cellid/{cell_name}" if cell_name else None,
        "map_url": f"https://www.google.com/maps?q={coord_lat},{coord_lng}" if (coord_lat and coord_lng) else None
    }
    _CELL_LOCATION_CACHE[clean_cell] = {"time": now_t, "data": result}
    return result


@router.post("/tickets/update")
async def update_ticket_api(request: Request):
    body = await request.json()
    phone = body.get("phone")
    incident_time = body.get("incident_time")
    field = body.get("field")
    value = body.get("value")
    if phone and field:
        ok = update_ticket_field(phone, field, value, incident_time=incident_time)
        return {"success": ok}
    return Response(content="Missing phone or field", status_code=400)


@router.post("/tickets/save-ai-feedback")
async def save_ai_feedback_api(request: Request):
    """Tiếp nhận phản hồi tóm tắt chuẩn từ KTV và lưu mẫu huấn luyện Few-shot cho Qwen"""
    from db_manager import save_ai_feedback_sample
    from ai_cache import save_summary
    body = await request.json()
    ticket_id = body.get("ticket_id")
    phone = body.get("phone", "")
    package_title = body.get("package_title", "")
    ticket_content = body.get("ticket_content", "")
    summary_content = body.get("summary_content", "")
    verified_by = body.get("verified_by", "KTV")

    if not summary_content:
        return {"success": False, "error": "Nội dung tóm tắt không được để trống"}

    try:
        save_ai_feedback_sample(
            ticket_id=ticket_id,
            phone=phone,
            package_title=package_title,
            ticket_content=ticket_content,
            summary_content=summary_content,
            verified_by=verified_by
        )
        if phone:
            save_summary(phone, package_title, ticket_content, summary_content)
        return {
            "success": True, 
            "message": "Đã lưu mẫu chuẩn thành công! Qwen sẽ học theo mẫu này cho các phiếu sau."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/tickets/clear")
async def clear_tickets_api(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    source = body.get("source") if body else None
    delete_all_tickets(source=source)
    state.total_scanned = 0
    state.closed_count = 0
    sys_text = "TTS Mới" if source == "tts_new" else ("TTS Cũ" if source == "tts_old" else "toàn bộ")
    state.log("WARN", f"🗑️ ĐÃ XÓA DỮ LIỆU BẢNG TẠM {sys_text.upper()}.")
    return {"success": True}


@router.post("/tts_old_api/close_one")
@router.post("/tickets/close_one")
async def close_one_tts_old_ticket(request: Request):
    return {"success": False, "message": "Hệ thống TTS Cũ đã ngừng hoạt động. Vui lòng đóng phiếu qua hệ thống TTS Mới."}


@router.post("/ttsnew/open_detail")
async def open_detail_ttsnew_api(request: Request):
    body = await request.json()
    ticket_code = str(body.get("ticket_code") or "").strip()
    phone = str(body.get("phone") or "").strip()
    incident_time = str(body.get("incident_time") or "").strip()

    conn = get_db_connection()
    row = None
    if ticket_code:
        row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id, comment, action_plan, package_title FROM tickets WHERE ticket_code = ? OR ticket_code LIKE ?", (ticket_code, f"{ticket_code}%")).fetchone()
    if not row and phone and incident_time:
        row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id, comment, action_plan, package_title FROM tickets WHERE phone = ? AND incident_time = ? AND source = 'tts_new'", (phone, incident_time)).fetchone()
    if not row and phone:
        row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id, comment, action_plan, package_title FROM tickets WHERE phone = ? AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1", (phone,)).fetchone()
    conn.close()

    ticket_id = row["ticket_id"] if (row and row["ticket_id"]) else None
    flow_id = row["flow_id"] if (row and row["flow_id"]) else None
    code = row["ticket_code"] if (row and row["ticket_code"]) else ticket_code
    clean_code = code.split("\n")[0].strip() if code else ""
    comment_val = str(row["comment"] or "").strip() if (row and "comment" in row.keys()) else ""
    action_plan_val = str(row["action_plan"] or "").strip() if (row and "action_plan" in row.keys()) else ""
    pkg_title = (row["package_title"] if (row and "package_title" in row.keys()) else "") or ""
    is_data_ticket = is_mobile_internet_ticket(pkg_title)

    if not ticket_id and clean_code and "/" in clean_code:
        try:
            ticket_id = int(clean_code.split("/")[-1])
        except Exception:
            pass

    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")
    client_tok = (body.get("token") or request.headers.get("Authorization") or "").strip()
    from ttsnew_api import fetch_active_tickets
    tok, ktv_user = resolve_ttsnew_token(client_ip, is_local, client_tok)
    if not tok:
        return {
            "success": False,
            "require_login": True,
            "message": "Bạn chưa đăng nhập TTS Mới trên trình duyệt này. Vui lòng đăng nhập tài khoản của bạn trước khi xử lý phiếu."
        }

    if not flow_id and tok:
        try:
            active_t = fetch_active_tickets(tok, limit=1000)
            for at in active_t:
                tc = str(at.get("ticketCode") or "")
                t_id = at.get("ticketId")
                if tc == code or tc == clean_code or (ticket_id and t_id == ticket_id) or (clean_code and clean_code.endswith(str(t_id))):
                    flow_id = at.get("id")
                    ticket_id = at.get("ticketId")
                    conn_u = get_db_connection()
                    with conn_u:
                        if ticket_id:
                            conn_u.execute("UPDATE tickets SET flow_id = ?, ticket_id = ? WHERE ticket_id = ? AND source = 'tts_new'", (flow_id, ticket_id, ticket_id))
                        elif clean_code:
                            conn_u.execute("UPDATE tickets SET flow_id = ?, ticket_id = ? WHERE (ticket_code = ? OR ticket_code LIKE ?) AND source = 'tts_new'", (flow_id, ticket_id, clean_code, f"{clean_code}%"))
                        elif phone and incident_time:
                            conn_u.execute("UPDATE tickets SET flow_id = ?, ticket_id = ? WHERE phone = ? AND incident_time = ? AND source = 'tts_new'", (flow_id, ticket_id, phone, incident_time))
                        elif phone:
                            conn_u.execute("UPDATE tickets SET flow_id = ?, ticket_id = ? WHERE rowid = (SELECT rowid FROM tickets WHERE phone = ? AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1)", (flow_id, ticket_id, phone))
                    conn_u.close()
                    break
        except Exception as ex_f:
            state.log("WARN", f"Không tìm thấy flow_id cho {code}: {ex_f}")

    if not flow_id or not ticket_id:
        return {
            "success": False, 
            "message": f"Không tìm thấy mã luồng OneOSS của phiếu {clean_code or code}. Vui lòng mở trang Quản lý phiếu và tìm kiếm.",
            "fallback_url": "https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu",
            "clean_code": clean_code
        }

    state.log("STEP", f"🌐 Đang mở cửa sổ chi tiết phiếu {clean_code or code} trên TTS Mới...")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            target_page = None
            for pg in context.pages:
                if "tts.vnptnet.vn" in pg.url:
                    target_page = pg
                    break
            if not target_page:
                target_page = context.new_page()
                target_page.goto("https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu/chi-tiet-phieu-pakh")
                target_page.wait_for_timeout(1000)

            target_page.bring_to_front()
            target_page.evaluate(f"""() => {{
                window.history.pushState({{ ticketFlowId: {flow_id}, ticketId: {ticket_id}, ticketTypeId: 2 }}, '', '/tts/ticket/quan-ly-phieu/chi-tiet-phieu-pakh');
                window.location.reload();
            }}""")

            # Đợi nhẹ cho trang chi tiết hiển thị
            target_page.wait_for_timeout(1500)

            # TUYỆT ĐỐI KHÔNG TỰ Ý ĐIỀN THÔNG TIN VÀO CÁC PHẢN ÁNH KHÁC NGOÀI MOBILE INTERNET.
            # Chỉ tự động mở dialog và điền nội dung xử lý khi là phiếu Mobile Internet!
            if is_data_ticket:
                try:
                    btn_cap_nhat = target_page.query_selector('button.p-button-primary:has-text("Cập nhật xử lý")')
                    if btn_cap_nhat:
                        btn_cap_nhat.click()
                        target_page.wait_for_timeout(1000)

                        dialog = target_page.query_selector('.p-dialog:has-text("Cập nhật xử lý")')
                        if dialog:
                            b0_true = dialog.query_selector('p-radiobutton:has-text("True") .p-radiobutton-box')
                            if b0_true:
                                b0_true.click()

                            combined_text = f"{comment_val}\n{action_plan_val}".strip() if (comment_val and action_plan_val) else (comment_val or action_plan_val or "")
                            if combined_text:
                                txt_closing = dialog.query_selector('textarea[name="closingContent"], textarea[formcontrolname="closingContent"]')
                                if txt_closing:
                                    txt_closing.fill(combined_text)

                                txt_assign = dialog.query_selector('textarea[name="assignContent"], textarea[formcontrolname="assignContent"]')
                                if txt_assign:
                                    txt_assign.fill(combined_text)
                except Exception as ex_modal:
                    pass

        state.log("SUCCESS", f"✅ Đã mở chi tiết phiếu {clean_code or code} trên tab TTS Mới thành công!")
        return {
            "success": True, 
            "message": f"Đã mở chi tiết phiếu {clean_code or code} trên tab trình duyệt TTS Mới!", 
            "ticket_code": clean_code or code,
            "ticket_id": ticket_id,
            "flow_id": flow_id
        }
    except Exception as ex_open:
        state.log("WARN", f"⚠️ Không thể tương tác trực tiếp với Chrome 9222: {ex_open}")
        return {
            "success": False, 
            "message": f"Không thể tự động điều khiển tab Chrome: {str(ex_open)}",
            "fallback_url": "https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu",
            "clean_code": clean_code
        }


@router.get("/ttsnew/incident_causes")
async def get_ttsnew_incident_causes_api():
    cat_file = BASE_DIR / "incident_causes_catalog.json"
    if cat_file.exists():
        try:
            with open(cat_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"groups": [], "id_map": {}}


@router.post("/ttsnew/close_one")
async def close_one_ttsnew_ticket(request: Request):
    body = await request.json()
    phone = str(body.get("phone") or "").strip()
    ticket_code = str(body.get("ticket_code") or "").strip()
    comment_custom = str(body.get("comment") or "").strip()
    action_plan_custom = str(body.get("action_plan") or "").strip()
    incident_cause_custom = str(body.get("incident_cause") or "").strip()

    body_ticket_id = body.get("ticket_id")
    incident_time = str(body.get("incident_time") or "").strip()
    conn = get_db_connection()
    row = None
    if body_ticket_id:
        row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ? AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1", (body_ticket_id,)).fetchone()
    if not row and ticket_code:
        clean_c = ticket_code.split("\n")[0].strip()
        row = conn.execute("SELECT * FROM tickets WHERE (ticket_code = ? OR ticket_code LIKE ?) AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1", (clean_c, f"{clean_c}%")).fetchone()
    if not row and phone and incident_time:
        row = conn.execute("SELECT * FROM tickets WHERE phone = ? AND incident_time = ? AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1", (phone, incident_time)).fetchone()
    if not row and phone:
        row = conn.execute("SELECT * FROM tickets WHERE phone = ? AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1", (phone,)).fetchone()
    conn.close()

    ticket_id = row["ticket_id"] if (row and row["ticket_id"]) else None
    flow_id = row["flow_id"] if (row and row["flow_id"]) else None
    code = row["ticket_code"] if (row and row["ticket_code"]) else ticket_code
    clean_code = code.split("\n")[0].strip() if code else ""
    status_val = str(row["status"] or "") if row else ""
    comment_val = comment_custom or (str(row["comment"] or "").strip() if (row and "comment" in row.keys()) else "")
    action_plan_val = action_plan_custom or (str(row["action_plan"] or "").strip() if (row and "action_plan" in row.keys()) else "")
    incident_cause_val = incident_cause_custom or (str(row["incident_cause"] or "").strip() if (row and "incident_cause" in row.keys() and row["incident_cause"]) else "")
    target_step = str(body.get("target_step") or "").strip()

    if incident_cause_custom and phone:
        try:
            update_ticket_field(phone, "incident_cause", incident_cause_custom, incident_time=row["incident_time"] if row else None)
        except Exception:
            pass

    reopen_cnt = int(row["reopen_count"] or 0) if (row and "reopen_count" in row.keys()) else 0
    force_close = body.get("force", False)
    if reopen_cnt > 0 and not force_close:
        return {
            "success": False, 
            "is_reopened": True,
            "reopen_count": reopen_cnt,
            "message": f"⚠️ Phiếu này đã mở lại {reopen_cnt} lần (THÔNG TIN MỞ LẠI TTS). Hệ thống chặn tự động đóng. KTV cần xác nhận trước khi đóng thủ công."
        }

    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")
    client_tok = (body.get("token") or request.headers.get("Authorization") or "").strip()

    from ttsnew_api import fetch_active_tickets, api_transfer_ttsnew_ticket
    tok, ktv_user = resolve_ttsnew_token(client_ip, is_local, client_tok)
    if not tok:
        return {
            "success": False, 
            "message": "Không tìm thấy phiên xác thực TTS Mới của bạn. Vui lòng bấm vào biểu tượng TTS MỚI trên thanh công cụ để kết nối tài khoản KTV của bạn trước khi đóng phiếu!"
        }

    ktv_name = ktv_user.get("displayName") or ktv_user.get("userName") or "Kỹ thuật viên"
    state.log("STEP", f"Đang gửi yêu cầu xử lý phiếu {clean_code or phone} trên TTS Mới bởi [{ktv_name}] (IP: {client_ip})...")

    if not flow_id or not ticket_id:
        try:
            raw_active = fetch_active_tickets(tok, limit=1000)
            for r_it in raw_active:
                if (ticket_id and str(r_it.get("ticketId")) == str(ticket_id)) or \
                   (clean_code and str(r_it.get("ticketCode")) == str(clean_code)) or \
                   (phone and phone in str(r_it)):
                    flow_id = r_it.get("id")
                    ticket_id = r_it.get("ticketId")
                    break
        except Exception:
            pass

    if not flow_id or not ticket_id:
        return {"success": False, "message": f"Không tìm thấy luồng xử lý (flow_id/ticket_id) của phiếu {clean_code or phone} trên TTS Mới."}

    force_override_ward = bool(body.get("force_override_ward", False))

    res_close = api_transfer_ttsnew_ticket(
        token=tok,
        ticket_flow_id=flow_id,
        ticket_id=ticket_id,
        phone=phone or (row["phone"] if row else ""),
        ticket_code=clean_code,
        status=status_val,
        closing_content=comment_val,
        assign_content=action_plan_val,
        target_step=target_step,
        incident_cause=incident_cause_val,
        force_override_ward=force_override_ward
    )
    if not res_close.get("success"):
        err_msg = res_close.get("message", "Lỗi chuyển bước")
        if res_close.get("blocked_by_ward"):
            state.log("WARN", f"⛔ {err_msg}")
            return res_close
        state.log("WARN", f"⚠️ [Phiếu lỗi] Phiếu {clean_code} ({phone}) không đóng được: {err_msg}")
        try:
            conn = get_db_connection()
            target_phone = phone or (row["phone"] if row else "")
            if ticket_id:
                conn.execute("""
                    UPDATE tickets 
                    SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                    WHERE ticket_id = ? AND source = 'tts_new'
                """, (ticket_id,))
            elif clean_code:
                conn.execute("""
                    UPDATE tickets 
                    SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                    WHERE (ticket_code = ? OR ticket_code LIKE ?) AND source = 'tts_new'
                """, (clean_code, f"{clean_code}%"))
            elif target_phone:
                conn.execute("""
                    UPDATE tickets 
                    SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                    WHERE phone = ? AND source = 'tts_new'
                """, (target_phone,))
            conn.commit()
            conn.close()
        except Exception:
            pass
    return res_close


@router.post("/ttsnew/close_all")
async def close_all_ttsnew_tickets(request: Request):
    from ttsnew_api import fetch_active_tickets, filter_data_tickets, api_transfer_ttsnew_ticket
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")
    body = await request.json()
    client_tok = (body.get("token") or request.headers.get("Authorization") or "").strip()
    tok, ktv_user = resolve_ttsnew_token(client_ip, is_local, client_tok)
    if not tok:
        return {
            "success": False, 
            "require_login": True,
            "message": "Không tìm thấy phiên xác thực TTS Mới. Vui lòng kết nối tài khoản KTV của bạn trước khi thực hiện đóng tự động."
        }

    ktv_name = ktv_user.get("displayName") or ktv_user.get("userName") or "KTV"
    def _run_close_all():
        state.log("STEP", f"🚀 Bắt đầu tự động chuyển bước/đóng tất cả phiếu TTS Mới bởi [{ktv_name}]...")
        try:
            raw = fetch_active_tickets(tok, limit=1000)
            data_tickets = filter_data_tickets(raw)
            conn = get_db_connection()
            total_success = 0
            for it in data_tickets:
                flow_id = it.get("id")
                ticket_id = it.get("ticketId")
                ticket_code = it.get("ticketCode")
                row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ? OR ticket_code = ? OR ticket_code LIKE ?", 
                                   (ticket_id, ticket_code, f"{ticket_code}%")).fetchone()
                if row and row["status"]:
                    rc = int(row["reopen_count"] or 0) if "reopen_count" in row.keys() else 0
                    if rc > 0:
                        state.log("WARN", f"   ↳ ⛔ Bỏ qua {ticket_code} ({row['phone']}): Đã mở lại {rc} lần (THÔNG TIN MỞ LẠI TTS) - KHÔNG ĐÓNG TỰ ĐỘNG!")
                        continue

                    from db_manager import check_ticket_can_close
                    can_close, reason = check_ticket_can_close(dict(row))
                    if not can_close:
                        state.log("INFO", f"   ↳ ⏸️ Giữ nguyên {ticket_code} ({row['phone']}): Chưa đủ điều kiện đóng ({reason})")
                        continue

                    res = api_transfer_ttsnew_ticket(
                        token=tok,
                        ticket_flow_id=flow_id,
                        ticket_id=ticket_id,
                        phone=row["phone"],
                        ticket_code=ticket_code,
                        status=row["status"],
                        closing_content=row["comment"] or "",
                        assign_content=row["action_plan"] or "",
                        incident_cause=(str(row["incident_cause"]).strip() if ("incident_cause" in row.keys() and row["incident_cause"]) else "")
                    )
                    if res.get("success"):
                        total_success += 1
                        state.log("SUCCESS", f"   ↳ [{total_success}] {res.get('message')}")
                    elif res.get("blocked_by_ward"):
                        state.log("WARN", f"   ↳ ⛔ Bỏ qua {ticket_code} ({row['phone']}): Hướng 5.1 nhưng Phường/Xã chưa cập nhật hoặc sai khác - Giữ nguyên phiếu!")
                    else:
                        state.log("WARN", f"   ↳ ⚠️ [Phiếu lỗi] {ticket_code}: {res.get('message')}")
                        try:
                            t_id = row["ticket_id"] if ("ticket_id" in row.keys() and row["ticket_id"]) else None
                            if t_id:
                                conn.execute("""
                                    UPDATE tickets 
                                    SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                                    WHERE ticket_id = ? AND source = 'tts_new'
                                """, (t_id,))
                            elif ticket_code:
                                conn.execute("""
                                    UPDATE tickets 
                                    SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                                    WHERE (ticket_code = ? OR ticket_code LIKE ?) AND source = 'tts_new'
                                """, (ticket_code, f"{ticket_code}%"))
                            elif row["phone"]:
                                conn.execute("""
                                    UPDATE tickets 
                                    SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                                    WHERE phone = ? AND source = 'tts_new'
                                """, (row["phone"],))
                            conn.commit()
                        except Exception:
                            pass
            conn.close()
            state.log("SUCCESS", f"🎉 Hoàn thành xử lý {total_success}/{len(data_tickets)} phiếu TTS Mới!")
        except Exception as ex_all:
            state.log("ERROR", f"Lỗi khi đóng hàng loạt phiếu TTS Mới: {ex_all}")

    threading.Thread(target=_run_close_all, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành tự động chuyển bước/đóng hàng loạt phiếu TTS Mới..."}


@router.post("/tickets/precheck_one")
async def precheck_one_ticket(request: Request):
    body = await request.json()
    phone = body.get("phone")
    incident_time = body.get("incident_time")
    req_service_type = str(body.get("service_type") or "").strip().lower()
    req_region = str(body.get("region") or "").strip().upper()
    if req_region not in ("MB", "MN", "MT"):
        req_region = None

    if not phone:
        return Response(content="Missing phone", status_code=400)

    clean_digits = "".join(filter(str.isdigit, str(phone).strip()))
    phone_84 = ("84" + clean_digits[1:]) if clean_digits.startswith("0") else (("84" + clean_digits) if len(clean_digits) == 9 else clean_digits)

    state.log("STEP", f"⚡ Đang thực hiện tiền kiểm tra nhanh cho thuê bao {phone_84}...")

    try:
        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)
        from sapc_client import SAPCClient
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from converter import convert_sapc_response
        from report_bot import get_formatted_sapc_packages, analyze_subscriber_status, extract_btools_packages_summary
        from auth_extractor import get_chrome_debug_driver
        driver = get_chrome_debug_driver()

        from concurrent.futures import ThreadPoolExecutor
        from services.voice_precheck import is_voice_ticket, precheck_single_voice_ticket

        conn = get_db_connection()
        with conn:
            if incident_time:
                cur = conn.execute("SELECT package_title, ticket_content, reopen_count, ticket_code FROM tickets WHERE (phone = ? OR phone = ? OR phone LIKE ?) AND incident_time = ?", (phone, phone_84, f"%{clean_digits[-9:]}%", incident_time))
            else:
                cur = conn.execute("SELECT package_title, ticket_content, reopen_count, ticket_code FROM tickets WHERE phone = ? OR phone = ? OR phone LIKE ? ORDER BY updated_at DESC LIMIT 1", (phone, phone_84, f"%{clean_digits[-9:]}%"))
            row = cur.fetchone()
            pkg_title = (row[0] if row else "Thoại / SMS") or ""
            t_content = row[1] if row else ""
            reopen_cnt = row[2] if row and len(row) > 2 else 0
            t_code = row[3] if row and len(row) > 3 else ""

        from region_detector import detect_ticket_region
        target_reg = req_region or detect_ticket_region({
            "user_region": req_region,
            "ticket_code": t_code,
            "title": pkg_title,
            "content": t_content
        })

        if req_service_type in ("call", "sms", "spam_call", "voice", "voice_sms", "roaming", "cvqt", "sim", "sim_multisim"):
            is_voice = True
        else:
            is_voice = is_voice_ticket(pkg_title)
        is_mobile_data = not is_voice

        # Khởi tạo Client
        sapc_client = None
        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception:
            try:
                sapc_client = SAPCClient()
            except Exception:
                pass

        cem_client = None
        if is_mobile_data:
            try:
                from cem_client import CEMClient, save_cem_data_to_file
                cem_client = CEMClient(driver=driver)
            except Exception:
                pass

        # -------------------------------------------------------------
        # KHỞI CHẠY ĐỒNG THỜI CÁC DỊCH VỤ CORE (SIÊU TỐC ĐA LUỒNG)
        # -------------------------------------------------------------
        info_res = {}
        sapc_res = {"msisdn": phone, "packages": []}
        existing_clean_data = []
        cem_recs = []
        app_evs = []
        v_res = {}
        ccos_json_str = ""

        today = datetime.today()
        start_d = (today - timedelta(days=4)).strftime("%Y-%m-%d")
        end_d = today.strftime("%Y-%m-%d")

        def _fetch_sapc_cell_task():
            nonlocal info_res, sapc_res
            try:
                if sapc_client:
                    raw_sapc = sapc_client.query(phone)
                    sapc_res = convert_sapc_response(raw_sapc)
            except Exception as ex_sapc:
                state.log("WARN", f"Lỗi tra cứu gói cước SAPC cho {phone}: {ex_sapc}")
            try:
                info_res = tra_cell_tu_so_dien_thoai(phone, session=sapc_client.session if sapc_client else None)
            except Exception as ex_cell:
                state.log("WARN", f"Lỗi tra cứu Cell/HLR cho {phone}: {ex_cell}")

        def _fetch_btools_task():
            nonlocal existing_clean_data
            try:
                from crawler_btools import extract_btools_single_phone
                from data_processor import standardize_btools_data
                raw_bt = extract_btools_single_phone(driver, phone, start_d, end_d)
                if raw_bt:
                    existing_clean_data = standardize_btools_data(raw_bt)
                    num_file = BASE_DIR / "number" / f"{phone}.json"
                    with open(num_file, "w", encoding="utf-8") as nf:
                        json.dump({
                            "phone": phone,
                            "package_title": pkg_title,
                            "ticket_content": t_content,
                            "btools_technical_data": existing_clean_data,
                            "data": existing_clean_data
                        }, nf, ensure_ascii=False, indent=2)
            except Exception as ex_bt_pre:
                state.log("WARN", f"Lỗi cào BTools khi tiền kiểm {phone}: {ex_bt_pre}")

        def _fetch_cem_task():
            nonlocal cem_recs, app_evs
            if cem_client:
                try:
                    cem_recs = cem_client.get_subscriber_history_5days(phone_84, days=5, use_cache=False, incident_time_str=incident_time)
                    app_evs = cem_client.get_subscriber_app_events(phone_84, days=5, use_cache=False, incident_time_str=incident_time)
                    save_cem_data_to_file(phone_84, cem_recs, app_evs, base_dir=BASE_DIR)
                except Exception as ex_c:
                    state.log("WARN", f"Lỗi tra cứu CEM khi tiền kiểm tra {phone_84}: {ex_c}")

        def _fetch_voice_task():
            nonlocal v_res, ccos_json_str
            t_info = {
                "package_title": pkg_title,
                "ticket_content": t_content,
                "incident_time": incident_time,
                "reopen_count": reopen_cnt,
                "ticket_code": t_code
            }
            v_res = precheck_single_voice_ticket(phone_84, t_info, driver=driver)
            try:
                from ccos_client import get_ccos_attachments
                ccos_info = get_ccos_attachments(phone_84, driver=driver)
                if ccos_info:
                    ccos_json_str = json.dumps(ccos_info, ensure_ascii=False)
                    if ccos_info.get("has_file"):
                        f_names = ", ".join([f["name"] for f in ccos_info.get("files", [])])
                        state.log("INFO", f"   📎 [CCOS] Thuê bao {phone_84} có file đính kèm: {f_names}")
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=3) as exec_pre:
            f_sc = exec_pre.submit(_fetch_sapc_cell_task)
            if is_voice:
                f_vc = exec_pre.submit(_fetch_voice_task)
                f_sc.result()
                f_vc.result()
            else:
                f_bt = exec_pre.submit(_fetch_btools_task)
                f_cm = exec_pre.submit(_fetch_cem_task)
                f_sc.result()
                f_bt.result()
                f_cm.result()

        out_dir = str(BASE_DIR / "output")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{phone}.json"), "w", encoding="utf-8") as f:
            json.dump({
                **sapc_res,
                "subscriber_info": info_res,
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, f, ensure_ascii=False, indent=4)

        cell_desc = info_res.get("Cell ID") or info_res.get("ECGI") or "--"
        rat = info_res.get("Radio") or "Sóng di động"
        now_precheck_str = datetime.now(ICT).strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        with conn:
            if is_voice:
                if incident_time:
                    conn.execute("""
                        UPDATE tickets 
                        SET real_packages = ?, 
                            rat_types = ?,
                            cem_data = ?,
                            status = ?,
                            comment = ?,
                            action_plan = ?,
                            ccos_attachments = COALESCE(NULLIF(?, ''), ccos_attachments),
                            prechecked_at = ?,
                            region = CASE WHEN ? IN ('MB', 'MN', 'MT') THEN ? ELSE region END,
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE (phone = ? OR phone = ? OR phone LIKE ?) AND incident_time = ?
                    """, (
                        v_res.get("formatted_pkg", ""),
                        v_res.get("rat_types", ""),
                        v_res.get("cem_data", ""),
                        v_res.get("status", ""),
                        v_res.get("comment", ""),
                        v_res.get("action_plan", ""),
                        ccos_json_str,
                        now_precheck_str,
                        target_reg, target_reg,
                        phone, phone_84, f"%{clean_digits[-9:]}%", incident_time
                    ))
                else:
                    conn.execute("""
                        UPDATE tickets 
                        SET real_packages = ?, 
                            rat_types = ?,
                            cem_data = ?,
                            status = ?,
                            comment = ?,
                            action_plan = ?,
                            ccos_attachments = COALESCE(NULLIF(?, ''), ccos_attachments),
                            prechecked_at = ?,
                            region = CASE WHEN ? IN ('MB', 'MN', 'MT') THEN ? ELSE region END,
                            updated_at = CURRENT_TIMESTAMP 
                        WHERE rowid = (SELECT rowid FROM tickets WHERE phone = ? OR phone = ? OR phone LIKE ? ORDER BY updated_at DESC LIMIT 1)
                    """, (
                        v_res.get("formatted_pkg", ""),
                        v_res.get("rat_types", ""),
                        v_res.get("cem_data", ""),
                        v_res.get("status", ""),
                        v_res.get("comment", ""),
                        v_res.get("action_plan", ""),
                        ccos_json_str,
                        now_precheck_str,
                        target_reg, target_reg,
                        phone, phone_84, f"%{clean_digits[-9:]}%"
                    ))
                state.log("SUCCESS", f"✅ Đã tiền kiểm Thoại / SMS / Gói xong cho {phone_84}: {v_res.get('status')}", region=target_reg)
                return {"success": True, "formatted_pkg": v_res.get("formatted_pkg", ""), "info": info_res}

            # Xử lý Mobile Data
            real_pkgs_str = extract_btools_packages_summary(existing_clean_data)
            formatted_pkg = get_formatted_sapc_packages(phone, fallback_btools=real_pkgs_str)

            cem_desc = (f"Không có dữ liệu CEM (5 ngày) [Cell HSS: {cell_desc}]" if cell_desc and cell_desc != "--" else "Không có dữ liệu CEM (5 ngày)")
            app_usage_str = "--"
            if cem_recs or app_evs:
                try:
                    sum_inc, sum_rec, combined_cem = CEMClient.extract_two_period_summary(
                        cem_recs, incident_time_str=incident_time, app_events=app_evs, days=5
                    )
                    cem_desc = combined_cem
                    if app_evs:
                        app_usage_str = CEMClient.extract_top_apps_summary(app_evs)
                except Exception:
                    pass

            ai_sum_calc = ""
            if is_mobile_data:
                status_calc, comment_calc, action_calc, _ = analyze_subscriber_status(
                    existing_clean_data, pkg_title, t_content, phone_84=phone_84,
                    cem_records=cem_recs, app_events=app_evs, incident_time_str=incident_time, driver=driver
                )
                if t_content:
                    try:
                        from ai_interpreter import generate_ticket_summary
                        ai_sum_calc = generate_ticket_summary(pkg_title, t_content, phone=phone_84)
                    except Exception:
                        pass
            else:
                status_calc = ""
                comment_calc = ""
                action_calc = ""

            if incident_time:
                conn.execute("""
                    UPDATE tickets 
                    SET real_packages = ?, 
                        rat_types = ?,
                        cem_data = ?,
                        app_usage = CASE WHEN ? != '--' THEN ? ELSE app_usage END,
                        status = ?,
                        comment = ?,
                        action_plan = ?,
                        ai_summary = CASE WHEN ? != '' THEN ? ELSE ai_summary END,
                        prechecked_at = ?,
                        region = CASE WHEN ? IN ('MB', 'MN', 'MT') THEN ? ELSE region END,
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE (phone = ? OR phone = ? OR phone LIKE ?) AND incident_time = ?
                """, (formatted_pkg, rat, cem_desc, app_usage_str, app_usage_str, status_calc, comment_calc, action_calc, ai_sum_calc, ai_sum_calc, now_precheck_str, target_reg, target_reg, phone, phone_84, f"%{clean_digits[-9:]}%", incident_time))
            else:
                conn.execute("""
                    UPDATE tickets 
                    SET real_packages = ?, 
                        rat_types = ?,
                        cem_data = ?,
                        app_usage = CASE WHEN ? != '--' THEN ? ELSE app_usage END,
                        status = ?,
                        comment = ?,
                        action_plan = ?,
                        ai_summary = CASE WHEN ? != '' THEN ? ELSE ai_summary END,
                        prechecked_at = ?,
                        region = CASE WHEN ? IN ('MB', 'MN', 'MT') THEN ? ELSE region END,
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE rowid = (SELECT rowid FROM tickets WHERE phone = ? OR phone = ? OR phone LIKE ? ORDER BY updated_at DESC LIMIT 1)
                """, (formatted_pkg, rat, cem_desc, app_usage_str, app_usage_str, status_calc, comment_calc, action_calc, ai_sum_calc, ai_sum_calc, now_precheck_str, target_reg, target_reg, phone, phone_84, f"%{clean_digits[-9:]}%"))
        conn.close()

        state.log("SUCCESS", f"✅ Đã tiền kiểm Core xong cho {phone_84}: Radio={info_res.get('Radio')}, HSS={info_res.get('HSS Profile')}, IP={info_res.get('IPv4')}, NAM={info_res.get('NAM')}", region=target_reg)
        return {"success": True, "formatted_pkg": formatted_pkg, "info": info_res}
    except Exception as ex_pre:
        state.log("WARN", f"⚠️ Lỗi tiền kiểm tra cho {phone}: {ex_pre}", region=target_reg if 'target_reg' in locals() else None)
        return {"success": False, "error": str(ex_pre)}


@router.post("/tickets/move_to_2_4")
async def move_ticket_to_step_2_4(request: Request):
    """
    API tiếp nhận yêu cầu chuyển phiếu TTS Mới từ bước 2.3 sang bước 2.4.
    """
    body = await request.json()
    phone = str(body.get("phone") or "").strip()
    ticket_code = str(body.get("ticket_code") or "").strip()
    clean_code = ticket_code.split("\n")[0].strip()
    if clean_code.endswith(".0") and clean_code[:-2].isdigit():
        clean_code = clean_code[:-2]

    ticket_id = body.get("ticket_id")
    flow_id = body.get("flow_id")
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")
    client_tok = (body.get("token") or request.headers.get("Authorization") or "").strip()

    tok, ktv_user = resolve_ttsnew_token(client_ip, is_local, client_tok)
    if not tok:
        return {
            "success": False,
            "message": "Không tìm thấy phiên đăng nhập TTS Mới. Vui lòng kết nối tài khoản KTV trên thanh công cụ trước khi chuyển bước!"
        }

    from ttsnew_api import fetch_active_tickets, api_move_step_2_3_to_2_4

    ktv_name = ktv_user.get("displayName") or ktv_user.get("userName") or "Kỹ thuật viên"

    # Nếu thiếu flow_id hoặc ticket_id, tra cứu từ active tickets trên OneOSS
    if not flow_id or not ticket_id:
        try:
            raw_active = fetch_active_tickets(tok, limit=1000)
            for r_it in raw_active:
                r_code = str(r_it.get("ticketCode") or "")
                r_phone = str(r_it.get("phone") or r_it.get("contactPhone") or "")
                if (ticket_id and str(r_it.get("ticketId")) == str(ticket_id)) or \
                   (clean_code and clean_code in r_code) or \
                   (phone and phone in r_phone or phone in str(r_it)):
                    flow_id = r_it.get("id")
                    ticket_id = r_it.get("ticketId")
                    break
        except Exception:
            pass

    if not flow_id or not ticket_id:
        return {
            "success": False,
            "message": f"Không tìm thấy luồng xử lý (flow_id/ticket_id) của phiếu {clean_code or phone} trên hệ thống TTS Mới."
        }

    comment = (body.get("comment") or "").strip()
    action_plan = (body.get("action_plan") or "").strip()
    if not comment or not action_plan:
        try:
            conn = get_db_connection()
            r_db = None
            if ticket_id:
                r_db = conn.execute("""
                    SELECT comment, action_plan 
                    FROM tickets 
                    WHERE ticket_id = ? AND source = 'tts_new'
                    ORDER BY updated_at DESC LIMIT 1
                """, (ticket_id,)).fetchone()
            if not r_db and clean_code:
                r_db = conn.execute("""
                    SELECT comment, action_plan 
                    FROM tickets 
                    WHERE (ticket_code = ? OR ticket_code LIKE ?) AND source = 'tts_new'
                    ORDER BY updated_at DESC LIMIT 1
                """, (clean_code, f"{clean_code}%")).fetchone()
            if not r_db and phone:
                r_db = conn.execute("""
                    SELECT comment, action_plan 
                    FROM tickets 
                    WHERE phone = ? AND source = 'tts_new'
                    ORDER BY updated_at DESC LIMIT 1
                """, (phone,)).fetchone()

            if r_db:
                if not comment and r_db["comment"]:
                    comment = str(r_db["comment"]).strip()
                if not action_plan and r_db["action_plan"]:
                    action_plan = str(r_db["action_plan"]).strip()
            conn.close()
        except Exception:
            pass

    state.log("STEP", f"Đang gửi yêu cầu chuyển bước 2.4 cho phiếu {clean_code or phone} bởi [{ktv_name}]...")
    res = api_move_step_2_3_to_2_4(
        token=tok,
        ticket_flow_id=int(flow_id),
        ticket_id=int(ticket_id),
        phone=phone,
        ticket_code=clean_code,
        comment=comment,
        action_plan=action_plan
    )

    if res.get("success"):
        state.log("SUCCESS", res.get("message", f"✅ Đã chuyển phiếu {clean_code} sang bước 2.4"))
    else:
        state.log("WARN", f"⚠️ {res.get('message', 'Lỗi chuyển bước 2.4')}")

    return res


@router.post("/ccos/update-cookie")
async def update_ccos_cookie_api(request: Request):
    """Cập nhật Cookie CCOS từ người dùng hoặc trình duyệt."""
    body = await request.json()
    cookie_str = body.get("cookie", "")
    cookies_dict = body.get("cookies", {})
    from ccos_client import save_ccos_cache, get_ccos_cookies
    if cookie_str:
        for part in cookie_str.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies_dict[k.strip()] = v.strip()
    if cookies_dict:
        save_ccos_cache(cookies_dict)
        return {"success": True, "message": "Đã cập nhật Cookie CCOS thành công!", "cookies": list(cookies_dict.keys())}
    return {"success": False, "message": "Không tìm thấy dữ liệu cookie hợp lệ."}


@router.get("/ccos/status")
def get_ccos_status_api():
    """Kiểm tra trạng thái Cookie CCOS hiện tại."""
    from ccos_client import get_ccos_cookies
    cookies = get_ccos_cookies()
    has_session = bool(cookies and ("SessionDB" in cookies or "SESSIONID" in cookies))
    return {
        "connected": has_session,
        "cookie_keys": list(cookies.keys()) if cookies else [],
        "has_session_db": "SessionDB" in cookies if cookies else False,
        "has_session_id": "SESSIONID" in cookies if cookies else False
    }


@router.post("/ccos/check")
async def check_ccos_ticket_api(request: Request):
    """Tra cứu thủ công file đính kèm CCOS cho 1 SĐT bất kỳ."""
    body = await request.json()
    phone = body.get("phone", "")
    from ccos_client import get_ccos_attachments
    res = get_ccos_attachments(phone)
    return res


# ==============================================================================
# QUẢN LÝ ĐỊA GIỚI HÀNH CHÍNH & ĐỒNG BỘ CẬP NHẬT ĐỊA BÀN PHIẾU LÊN TTS MỚI
# ==============================================================================
_PROVINCES_CACHE = []
_WARDS_CACHE = {}


def _get_oneoss_headers(token: str = ""):
    import ttsnew_api
    tok = token or ttsnew_api.get_cached_token()
    if not tok:
        return None
    if not tok.startswith("Bearer "):
        tok = "Bearer " + tok
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Authorization": tok,
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }


@router.get("/tts_new/locations/provinces")
def get_tts_new_provinces():
    """Lấy danh sách Tỉnh/TP chuẩn sau sáp nhập từ hệ thống OneOSS TTS Mới."""
    global _PROVINCES_CACHE
    if _PROVINCES_CACHE:
        return {"success": True, "data": _PROVINCES_CACHE}

    headers = _get_oneoss_headers()
    if not headers:
        return {"success": False, "message": "Chưa có token TTS Mới hoặc phiên hết hạn.", "data": []}

    try:
        import requests
        url = "https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/ClBoundaries/get-list?limit=100&offset=0&lvls=1"
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            raw_data = res.json().get("data", [])
            provinces = []
            for item in raw_data:
                provinces.append({
                    "id": item.get("id"),
                    "code": item.get("code"),
                    "name": item.get("name")
                })
            # Sắp xếp theo tên tiếng Việt
            provinces.sort(key=lambda x: str(x.get("name") or ""))
            _PROVINCES_CACHE = provinces
            return {"success": True, "data": provinces}
        else:
            return {"success": False, "message": f"OneOSS trả về lỗi {res.status_code}", "data": []}
    except Exception as e:
        return {"success": False, "message": str(e), "data": []}


@router.get("/tts_new/locations/wards")
def get_tts_new_wards(province_id: int):
    """Lấy danh sách Phường/Xã chuẩn sau sáp nhập theo Tỉnh/TP từ OneOSS TTS Mới."""
    global _WARDS_CACHE
    if province_id in _WARDS_CACHE:
        return {"success": True, "data": _WARDS_CACHE[province_id]}

    headers = _get_oneoss_headers()
    if not headers:
        return {"success": False, "message": "Chưa có token TTS Mới.", "data": []}

    try:
        import requests
        url = f"https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/ClBoundaries/get-list?limit=1000&offset=0&lvl=2&parentId={province_id}"
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            raw_data = res.json().get("data", [])
            wards = []
            for item in raw_data:
                wards.append({
                    "id": item.get("id"),
                    "code": item.get("code"),
                    "name": item.get("name")
                })
            wards.sort(key=lambda x: str(x.get("name") or ""))
            _WARDS_CACHE[province_id] = wards
            return {"success": True, "data": wards}
        else:
            return {"success": False, "message": f"OneOSS trả về lỗi {res.status_code}", "data": []}
    except Exception as e:
        return {"success": False, "message": str(e), "data": []}


@router.get("/tts_new/ticket_boundary/{ticket_id}")
def get_tts_new_ticket_boundary(ticket_id: int):
    """
    Lấy chính xác Phường/Xã và Tỉnh/TP chọn trên 2 ô dropdown của hệ thống TTS Mới.
    """
    headers = _get_oneoss_headers()
    if not headers:
        return {"success": False, "message": "Chưa có token TTS Mới."}

    try:
        import requests
        url = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/get-editable-ticket/{ticket_id}"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return {"success": False, "message": f"HTTP {res.status_code}"}
        
        d = res.json().get("data", {})
        prov_id = d.get("provinceId") or d.get("customerProvinceId")
        ward_id = d.get("wardId") or d.get("customerWardId")

        prov_name = ""
        ward_name = ""

        if prov_id:
            prov_res = get_tts_new_provinces()
            for p in prov_res.get("data", []):
                if p.get("id") == prov_id:
                    prov_name = p.get("name")
                    break

        if prov_id and ward_id:
            ward_res = get_tts_new_wards(prov_id)
            for w in ward_res.get("data", []):
                if w.get("id") == ward_id:
                    ward_name = w.get("name")
                    break

        display_text = ""
        if ward_name and prov_name:
            display_text = f"{ward_name}, {prov_name}"
        elif ward_name:
            display_text = ward_name
        elif prov_name:
            display_text = prov_name

        raw_field_id = d.get("clFieldId")
        field_id = raw_field_id if raw_field_id else 71
        field_name = "Chất lượng mạng" if field_id == 71 else (d.get("clFieldName") or "Chất lượng mạng")

        return {
            "success": True,
            "ticket_id": ticket_id,
            "province_id": prov_id,
            "province_name": prov_name,
            "ward_id": ward_id,
            "ward_name": ward_name,
            "field_id": field_id,
            "field_name": field_name,
            "display_text": display_text
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/tts_new/fields")
def get_tts_new_fields_api():
    """Lấy danh mục Lĩnh vực từ OneOSS TTS Mới."""
    headers = _get_oneoss_headers()
    if not headers:
        return {"success": True, "data": [{"id": 71, "name": "Chất lượng mạng"}]}
    try:
        import requests
        url = "https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/ClField/get-list?limit=1000&offset=0"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            raw_data = res.json().get("data", [])
            fields = []
            for item in raw_data:
                fields.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "code": item.get("code")
                })
            # Đảm bảo trường 71 Chất lượng mạng luôn ở vị trí đầu
            fields.sort(key=lambda x: 0 if x.get("id") == 71 else 1)
            return {"success": True, "data": fields}
        return {"success": True, "data": [{"id": 71, "name": "Chất lượng mạng"}]}
    except Exception as e:
        return {"success": True, "data": [{"id": 71, "name": "Chất lượng mạng"}]}


def sync_update_ticket_boundary_tts_new(ticket_id: int, province_id: int, ward_id: int, address: str = "", token: str = "", field_id: int = 71):
    """Gọi REST API OneOSS TTS Mới để cập nhật trực tiếp địa bàn Phường/Xã và Lĩnh vực cho phiếu."""
    headers = _get_oneoss_headers(token)
    if not headers:
        return False, "Không có token TTS Mới hợp lệ để đồng bộ."

    try:
        import requests
        # 1. Lấy thông tin editable của phiếu
        url_get = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/get-editable-ticket/{ticket_id}"
        res_get = requests.get(url_get, headers=headers, timeout=10)
        if res_get.status_code != 200:
            return False, f"Không thể lấy thông tin phiếu {ticket_id} từ TTS Mới (HTTP {res_get.status_code})"

        d = res_get.json().get("data", {})
        if not d:
            return False, f"Dữ liệu phiếu {ticket_id} trả về rỗng từ TTS Mới."

        target_field_id = field_id if field_id else (d.get("clFieldId") or 71)

        safe_addr = (address or "").strip() or "null"

        # 2. Tạo payload chuẩn cập nhật phiếu
        payload = {
            "id": ticket_id,
            "customerId": d.get("customerId"),
            "customerName": d.get("customerName") or "Khách hàng",
            "customerEmail": d.get("customerEmail"),
            "customerPhone": d.get("customerPhone"),
            "customerProvinceId": province_id or d.get("customerProvinceId"),
            "customerWardId": ward_id or d.get("customerWardId"),
            "customerAddress": safe_addr,
            "subject": d.get("title") or "PAKH",
            "incidentDate": None,
            "customerCompletionDate": None,
            "provinceId": province_id,
            "wardId": ward_id,
            "address": safe_addr,
            "clFieldId": target_field_id,  # Tự động chọn Chất lượng mạng (ID 71)
            "clGeneralFieldId": d.get("clGeneralFieldId"),
            "clSubfieldId": d.get("clSubFieldId"),
            "clMemberLevelId": d.get("clMemberLevelId"),
            "clPriorityLevelId": d.get("clPriorityLevelId"),
            "clSatisfactionId": d.get("clSatisfactionId"),
            "content": d.get("content") or "Nội dung phản ánh",
            "processDefinitionId": d.get("processDefinitionId"),
            "assignedUnitId": d.get("assignedUnitId"),
            "assignedUnitName": d.get("assignedUnitName")
        }

        # 3. Gửi PUT update-draft-ticket
        url_put = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/update-draft-ticket"
        res_put = requests.put(url_put, headers=headers, json=payload, timeout=15)
        if res_put.status_code == 200:
            res_json = res_put.json()
            if not res_json.get("isError"):
                return True, "Cập nhật thành công lên hệ thống TTS Mới"
            else:
                return False, f"TTS Mới báo lỗi: {res_json.get('message')}"
        else:
            return False, f"HTTP {res_put.status_code}: {res_put.text[:150]}"
    except Exception as e:
        return False, f"Lỗi kết nối OneOSS: {str(e)}"


@router.post("/tickets/update_ward")
async def update_ticket_ward_api(request: Request):
    """
    Cập nhật địa bàn Phường/Xã cho phiếu:
    - Lưu vào DB SQLite cục bộ (cột ward và ai_summary).
    - Đồng thời gọi API đồng bộ trực tiếp lên hệ thống TTS Mới nếu có province_id và ward_id!
    """
    body = await request.json()
    phone = body.get("phone", "")
    incident_time = body.get("incident_time", "")
    ticket_key = body.get("ticket_key", "")
    ward_address = body.get("ward", "").strip()
    ticket_id = body.get("ticket_id")
    province_id = body.get("province_id")
    ward_id = body.get("ward_id")
    address_detail = body.get("address", "").strip()

    if not phone and not ticket_id and not ticket_key:
        return {"success": False, "message": "Thiếu thông tin xác định phiếu."}

    # 1. Cập nhật local SQLite
    from db_manager import get_db_connection
    success_local = False
    p_name = body.get("province_name", "").strip()
    w_name = body.get("ward_name", "").strip()
    try:
        conn = get_db_connection()
        if ticket_id:
            conn.execute("""
                UPDATE tickets 
                SET ward = ?, province_id = ?, ward_id = ?, province_name = ?, ward_name = ? 
                WHERE ticket_id = ?
            """, (ward_address, province_id, ward_id, p_name, w_name, ticket_id))
        elif phone:
            conn.execute("""
                UPDATE tickets 
                SET ward = ?, province_id = ?, ward_id = ?, province_name = ?, ward_name = ? 
                WHERE phone = ? AND (incident_time = ? OR ? = '')
            """, (ward_address, province_id, ward_id, p_name, w_name, phone, incident_time or '', incident_time or ''))
        elif ticket_key:
            conn.execute("""
                UPDATE tickets 
                SET ward = ?, province_id = ?, ward_id = ?, province_name = ?, ward_name = ? 
                WHERE ticket_code = ?
            """, (ward_address, province_id, ward_id, p_name, w_name, ticket_key))
        conn.commit()
        success_local = True
    except Exception as e:
        print(f"Lỗi update tickets ward local: {e}")

    # 2. Đồng bộ lên TTS Mới nếu có ticket_id hoặc tra cứu ticket_id từ DB
    sync_msg = ""
    tts_synced = False
    target_tid = ticket_id
    if not target_tid and phone:
        try:
            conn = get_db_connection()
            row = conn.execute("SELECT ticket_id, source FROM tickets WHERE phone = ? ORDER BY updated_at DESC LIMIT 1", (phone,)).fetchone()
            if row and row["source"] == "tts_new" and row["ticket_id"]:
                target_tid = row["ticket_id"]
        except Exception:
            pass

    if target_tid and province_id and ward_id:
        client_ip = request.client.host if request.client else "127.0.0.1"
        is_local = client_ip in ("127.0.0.1", "localhost", "::1")
        client_tok = (body.get("token") or request.headers.get("Authorization") or "").strip()
        from services.session_manager import resolve_ttsnew_token
        tok, _ = resolve_ttsnew_token(client_ip, is_local, client_tok)
        if not tok:
            tts_synced = False
            sync_msg = "Chưa đăng nhập TTS Mới trên trình duyệt này, chỉ lưu cục bộ"
        else:
            target_f_id = int(body.get("field_id") or 71)
            ok, msg = sync_update_ticket_boundary_tts_new(int(target_tid), int(province_id), int(ward_id), address_detail or ward_address, token=tok, field_id=target_f_id)
            tts_synced = ok
            sync_msg = msg

    return {
        "success": success_local,
        "tts_synced": tts_synced,
        "sync_message": sync_msg,
        "message": "Đã lưu địa bàn thành công!" + (f" (Đồng bộ TTS Mới: {sync_msg})" if sync_msg else "")
    }


