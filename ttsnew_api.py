# ttsnew_api.py
# Module tích hợp REST API cho hệ thống TTS Mới (tts.vnptnet.vn / gw-oneoss.vnpt.vn)

import os
import json
import time
import requests
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOKEN_CACHE_FILE = BASE_DIR / "ttsnew_token_cache.json"

API_BASE_URL = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket"

# Danh sách từ khóa phân loại dịch vụ Data / Mobile Internet
DATA_SERVICE_KEYWORDS = [
    "mobile internet",
    "data",
    "4g",
    "3g",
    "5g",
    "truy cập internet",
    "chất lượng mạng ảnh hưởng đến truy cập",
]


def _is_jwt_valid(tok_str: str) -> bool:
    """Kiểm tra sơ bộ token JWT có đúng cấu trúc và chưa hết hạn exp không."""
    try:
        import base64
        raw = tok_str.replace("Bearer ", "").strip()
        parts = raw.split(".")
        if len(parts) >= 2:
            p = parts[1]
            p += "=" * ((4 - len(p) % 4) % 4)
            data = json.loads(base64.b64decode(p).decode("utf-8"))
            exp = data.get("exp")
            if exp:
                return exp > (time.time() + 30)
            return True
    except Exception:
        pass
    return bool(tok_str and len(tok_str) > 30)


def save_cached_token(token: str):
    """Lưu token vào file cache để tái sử dụng."""
    try:
        data = {"token": token, "updated_at": time.time()}
        with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get_cached_token() -> str:
    """Đọc token từ file cache hoặc lan_sessions.json nếu còn hiệu lực."""
    # 1. Thử đọc từ TOKEN_CACHE_FILE
    if TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                tok = (data.get("token") or "").strip()
                if tok and _is_jwt_valid(tok):
                    return tok
        except Exception:
            pass

    # 2. Fallback: Đọc token còn hạn mới nhất từ lan_sessions.json
    lan_file = BASE_DIR / "lan_sessions.json"
    if lan_file.exists():
        try:
            with open(lan_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)
            # Sắp xếp các session theo ttsnew_timestamp giảm dần
            sorted_sessions = sorted(
                sessions.values(),
                key=lambda s: s.get("ttsnew_timestamp", 0),
                reverse=True
            )
            for s in sorted_sessions:
                tok = (s.get("ttsnew_token") or "").strip()
                if tok and _is_jwt_valid(tok):
                    save_cached_token(tok)
                    return tok
        except Exception:
            pass

    return ""


def _extract_token_via_cdp_ws(domain_keyword: str = "tts.vnptnet.vn", storage_key: str = "TOKEN", port: int = 9222) -> str:
    """Trích xuất token trực tiếp từ Chrome qua CDP WebSocket không chuyển tab, không nhảy cửa sổ."""
    try:
        import urllib.request, json, asyncio, websockets
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as r:
            tabs = json.loads(r.read().decode("utf-8"))
        ws_url = None
        for t in tabs:
            if domain_keyword in t.get("url", "").lower():
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            return ""

        async def _query():
            async with websockets.connect(ws_url) as ws:
                msg = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": f"localStorage.getItem('{storage_key}')"}
                }
                await ws.send(json.dumps(msg))
                resp = await ws.recv()
                data = json.loads(resp)
                return data.get("result", {}).get("result", {}).get("value") or ""

        return asyncio.run(_query())
    except Exception:
        return ""


def extract_token_from_browser(driver=None, force_refresh: bool = False) -> str:
    """
    Trích xuất token trực tiếp từ bất kỳ trình duyệt nào (Chrome, Edge, Firefox) 100% ngầm.
    Tuyệt đối không chuyển tab hay nhảy cửa sổ làm gián đoạn người dùng.
    """
    token = ""

    # 1. Ưu tiên đọc từ cache nếu đã có token và không yêu cầu làm mới
    if not force_refresh:
        token = get_cached_token()
        if token:
            if not token.startswith("Bearer "):
                token = "Bearer " + token
            return token

    # 2. Quét tự động đa trình duyệt qua auth_extractor (Chrome/Edge port 9222, Firefox SQLite, etc.)
    try:
        from auth_extractor import get_universal_ttsnew_token
        token = get_universal_ttsnew_token(driver=driver)
    except Exception:
        pass

    # 3. Fallback qua Playwright CDP tới port 9222 nếu có
    if not token:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
                for page in browser.contexts[0].pages:
                    if "tts.vnptnet.vn" in page.url.lower():
                        token = page.evaluate("() => localStorage.getItem('TOKEN')")
                        if token:
                            break
        except Exception:
            pass

    if token:
        if not token.startswith("Bearer "):
            token = "Bearer " + token
        save_cached_token(token)

    return token


def make_api_request(url: str, token: str, timeout: int = 15) -> dict:
    """Gửi request HTTP GET tới API gw-oneoss."""
    if not token.startswith("Bearer "):
        token = "Bearer " + token

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": token,
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # Token hết hạn -> xóa file cache để buộc trích xuất token mới ở lần tiếp theo
            if TOKEN_CACHE_FILE.exists():
                try:
                    os.remove(TOKEN_CACHE_FILE)
                except Exception:
                    pass
        raise


def fetch_active_tickets(token: str, limit: int = 1000, offset: int = 0) -> list:
    """
    Lấy danh sách phiếu đang xử lý từ TTS Mới (ticketFlowStatusId=2: Đang xử lý).
    """
    url = f"{API_BASE_URL}/get-list?limit={limit}&offset={offset}&ticketFlowStatusId=2"
    resp = make_api_request(url, token)
    if resp.get("isError"):
        raise RuntimeError(f"Lỗi API get-list: {resp.get('message')}")
    return resp.get("data", [])


try:
    from update_tts.config import STATUS_TO_NGUYEN_NHAN
except Exception:
    STATUS_TO_NGUYEN_NHAN = {
        "LƯU LƯỢNG YẾU": "Thông tin đầu vào chưa chính xác, trùng lặp",
        "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL": "Thông tin đầu vào chưa chính xác, trùng lặp",
        "THUÊ BAO BỊ BÓP BĂNG THÔNG": "Thông tin đầu vào chưa chính xác, trùng lặp",
        "KHÔNG BẮT ĐƯỢC SÓNG 4G": "Thông tin đầu vào chưa chính xác, trùng lặp",
        "BẮT SÓNG 4G KÉM": "Thông tin đầu vào chưa chính xác, trùng lặp",
        "LỖI GÓI CƯỚC / THIẾT BỊ TREO": "Lỗi do gói cước",
        "HOẠT ĐỘNG BÌNH THƯỜNG": "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường",
        "THEO DÕI THÊM": "Khách hàng theo dõi thêm",
        "LỖI THIẾT BỊ / ĐANG DÙNG VPN": "Do thiết bị đầu cuối",
        "LỖI THIẾT BỊ / ĐI NHIỀU NƠI BỊ LỖI": "Do thiết bị đầu cuối",
        "CHƯA KHAI BÁO PROFILE 4G": "Lỗi profile thuê bao",
        "PROFILE LẠ": "Lỗi profile thuê bao",
        "SÓNG 4G CHẬP CHỜN / YẾU": "Thông tin đầu vào chưa chính xác, trùng lặp",
        "CHƯA ĐĂNG KÝ GÓI": "Lỗi do gói cước",
        "CHỈ CÓ GÓI PAYGO": "Lỗi do gói cước",
        "LỖI GÓI VD2 - THIẾU PAYGO": "Lỗi do gói cước",
        "GÓI CƯỚC ĐÃ HẾT HẠN": "Lỗi do gói cước",
        "GÓI CÒN HẠN - KHÔNG DÙNG ĐƯỢC": "Lỗi do gói cước",
        "KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ": "Do thiết bị đầu cuối",
        "KHÔNG CÓ DỮ LIỆU": "Do thiết bị đầu cuối",
        "HSS CHƯA CÓ 5G": "Lỗi do VNPT-VinaPhone khai báo dịch vụ cho khách hàng",
        "BỊ KHÓA GPRS": "Lỗi do VNPT-VinaPhone khai báo dịch vụ cho khách hàng",
        "THIẾU SÓNG 5G / THIẾT BỊ": "Do thiết bị đầu cuối",
        "ĐANG SỬ DỤNG VPN / 1.1.1.1": "Do thiết bị đầu cuối",
        "OFF THIẾT BỊ NHIỀU NGÀY": "Do thiết bị đầu cuối",
        "TẮT THIẾT BỊ NHIỀU NGÀY": "Do thiết bị đầu cuối",
        "LỖI THIẾT BỊ / SIM TREO DATA": "Do thiết bị đầu cuối",
        "LỖI DO GÓI CƯỚC": "Lỗi do gói cước",
        "LỖI GÓI CƯỚC - SAI SERVICE ID": "Lỗi do gói cước",
        "LỖI GÓI HOME / NGHẼN BĂNG THÔNG": "Lỗi do gói cước",
        "NGHI NGỜ LỖI GÓI CƯỚC": "Lỗi do gói cước",
    }

# Mapping từ tên nguyên nhân chuẩn hóa sang ID của ClIncidentCause trên TTS Mới (clTicketTypeId=2)
NGUYEN_NHAN_TO_INCIDENT_CAUSE_ID = {
    "thông tin đầu vào chưa chính xác, trùng lặp": 2012,
    "lỗi do gói cước": 2039,
    "mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường": 2011,
    "khách hàng theo dõi thêm": 2113,
    "do thiết bị đầu cuối": 2111,
    "lỗi profile thuê bao": 2040,
    "lỗi do vnpt-vinaphone khai báo dịch vụ cho khách hàng": 2143,
}

def get_ttsnew_incident_cause(status_or_reason: str) -> tuple:
    """
    Trả về (incident_cause_id, incident_cause_name) từ status nhận định trong tickets.db
    theo đúng bảng mapping tương tự như TTS Cũ.
    """
    if not status_or_reason:
        return 2011, "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        
    s_clean = str(status_or_reason).strip()
    s_upper = s_clean.upper()
    
    # 1. Tra cứu qua mapping STATUS_TO_NGUYEN_NHAN (tương tự TTS cũ)
    mapped_name = STATUS_TO_NGUYEN_NHAN.get(s_upper)
    if not mapped_name:
        for k, v in STATUS_TO_NGUYEN_NHAN.items():
            if k in s_upper or s_upper in k:
                mapped_name = v
                break
                
    if not mapped_name:
        mapped_name = s_clean
        
    # 2. Map mapped_name -> ClIncidentCause ID trên TTS Mới
    cause_id = NGUYEN_NHAN_TO_INCIDENT_CAUSE_ID.get(mapped_name.lower())
    if not cause_id:
        for k, v in NGUYEN_NHAN_TO_INCIDENT_CAUSE_ID.items():
            if k in mapped_name.lower() or mapped_name.lower() in k:
                cause_id = v
                break
                
    if not cause_id:
        cause_id = 2011
        mapped_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        
    return cause_id, mapped_name


EXCLUDED_DATA_TITLES = [
    "mobile internet (m0/gói data)",
    "gói cước mobile internet",
    "cvqt - dv mobile internet (data)"
]

def is_mobile_internet_data_ticket(it: dict) -> bool:
    title = str(it.get("title") or "").strip().lower()
    if "mobile internet" not in title:
        return False
    for ex in EXCLUDED_DATA_TITLES:
        if ex in title:
            return False
    return True


def filter_data_tickets(raw_tickets: list) -> list:
    """
    Scan tất cả các phiếu có 'Tiêu đề' là Mobile Internet, trừ:
    - Mobile Internet (M0/Gói Data)
    - Gói cước Mobile Internet
    - CVQT - DV Mobile Internet (Data)
    Bỏ tất cả các điều kiện lọc còn lại như Tên Quy trình và Tên Bước.
    """
    return [it for it in raw_tickets if is_mobile_internet_data_ticket(it)]


def is_call_ticket(it: dict) -> bool:
    title = str(it.get("title") or "").strip().lower()
    return any(k in title for k in [
        "gọi đi trong nước", "nhận cuộc gọi đến trong nước", "nhận cuộc gọi dến trong nước",
        "cuộc gọi đi và đến", "bị khóa spam cuộc gọi", "giữ cuộc gọi", "gọi quốc tế", "vowifi"
    ])


def filter_call_tickets(raw_tickets: list) -> list:
    """Lọc danh sách phiếu thuộc module Cuộc gọi."""
    return [it for it in raw_tickets if is_call_ticket(it)]


def is_sms_ticket(it: dict) -> bool:
    title = str(it.get("title") or "").strip().lower()
    return any(k in title for k in [
        "nhận tin nhắn", "khóa spam tin nhắn", "tin nhắn (sms)", "gửi tin nhắn", "tin nhắn rác"
    ]) or ("tin nhắn" in title and "cvqt" not in title)


def filter_sms_tickets(raw_tickets: list) -> list:
    """Lọc danh sách phiếu thuộc module Tin nhắn."""
    return [it for it in raw_tickets if is_sms_ticket(it)]


def is_other_ticket(it: dict) -> bool:
    return not is_mobile_internet_data_ticket(it) and not is_call_ticket(it) and not is_sms_ticket(it)


def filter_other_tickets(raw_tickets: list) -> list:
    """Lọc danh sách phiếu thuộc module Gói cước / PA Khác."""
    return [it for it in raw_tickets if is_other_ticket(it)]


def filter_non_data_tickets(raw_tickets: list) -> list:
    """
    Lọc danh sách các phiếu NGOÀI Mobile Internet (Thoại, SMS, Gói cước, CVQT, MNP...).
    """
    return [it for it in raw_tickets if not is_mobile_internet_data_ticket(it)]


def enrich_ticket_customer(it: dict, token: str) -> dict:
    """
    Gọi API get-customer-by-ticketflowid để lấy SĐT, tên khách hàng và hạng hội viên.
    Tạm đưa chung 2 trường Tên quy trình và Tên bước vào ticket_code.
    """
    flow_id = it.get("id")
    proc_name = str(it.get("processDefinitionName") or it.get("processInstanceName") or "").strip()
    step_name = str(it.get("stepName") or it.get("processNodeName") or "").strip()
    raw_code = str(it.get("ticketCode") or "").strip()

    # Lưu 3 dòng: Mã phiếu, [Tên quy trình], Tên bước hiện tại
    if proc_name or step_name:
        combined_code = f"{raw_code}\n[{proc_name}]\n{step_name}"
    else:
        combined_code = raw_code

    url_cust = f"{API_BASE_URL}/get-customer-by-ticketflowid/{flow_id}"
    url_info = f"{API_BASE_URL}/get-ticket-info?ticketTypeId=2&ticketFlowId={flow_id}"
    reopen_count = int(it.get("reopenCount") or 0)
    last_reopened_date = str(it.get("lastReopenedDate") or "").strip()

    try:
        resp = make_api_request(url_cust, token, timeout=10)
        cust = resp.get("data") or {}
        raw_phone = str(
            cust.get("phone") 
            or cust.get("contactPhone") 
            or it.get("subscriberNumber") 
            or it.get("customerPhone") 
            or ""
        ).strip()

        # Chuẩn hóa SĐT về dạng 84xxxxxxxxx
        phone = normalize_phone_number(raw_phone)

        # Lấy THÔNG TIN MỞ LẠI TTS (reopenCount, lastReopenedDate)
        try:
            resp_info = make_api_request(url_info, token, timeout=8)
            info_data = resp_info.get("data") or {}
            if isinstance(info_data, dict):
                rc = info_data.get("reopenCount")
                if rc is not None:
                    reopen_count = int(rc or 0)
                lrd = info_data.get("lastReopenedDate")
                if lrd:
                    last_reopened_date = str(lrd).strip()
        except Exception:
            pass

        return {
            "flow_id": flow_id,
            "ticket_id": it.get("ticketId"),
            "ticket_code": combined_code,
            "raw_ticket_code": raw_code,
            "process_name": proc_name,
            "step_name": step_name,
            "phone": phone,
            "raw_phone": raw_phone,
            "customer_name": cust.get("name", ""),
            "customer_level": cust.get("clMemberLevelName", ""),
            "title": it.get("title", ""),
            "content": it.get("content", ""),
            "incident_time": it.get("incidentDate", "") or it.get("requestDate", ""),
            "created_time": it.get("requestDate", ""),
            "assigned_unit": it.get("assignedUnitName", ""),
            "source": "tts_new",
            "reopen_count": reopen_count,
            "last_reopened_date": last_reopened_date,
        }
    except Exception as e:
        raw_fb = str(it.get("subscriberNumber") or it.get("customerPhone") or "").strip()
        return {
            "flow_id": flow_id,
            "ticket_id": it.get("ticketId"),
            "ticket_code": combined_code,
            "raw_ticket_code": raw_code,
            "process_name": proc_name,
            "step_name": step_name,
            "phone": normalize_phone_number(raw_fb),
            "raw_phone": raw_fb,
            "customer_name": "",
            "customer_level": "",
            "title": it.get("title", ""),
            "content": it.get("content", ""),
            "incident_time": it.get("incidentDate", "") or it.get("requestDate", ""),
            "created_time": it.get("requestDate", ""),
            "assigned_unit": it.get("assignedUnitName", ""),
            "source": "tts_new",
            "reopen_count": reopen_count,
            "last_reopened_date": last_reopened_date,
            "error": str(e),
        }


def normalize_phone_number(phone_str: str) -> str:
    """Chuẩn hóa số điện thoại thành format 84xxxxxxxxx để tra cứu Core."""
    import re
    digits = re.sub(r"\D", "", phone_str)
    if digits.startswith("0") and len(digits) >= 10:
        return "84" + digits[1:]
    if digits.startswith("84") and len(digits) >= 11:
        return digits
    if len(digits) == 9:
        return "84" + digits
    return digits


def get_ttsnew_tickets_for_precheck(driver=None, max_workers: int = 8, service_type: str = "data") -> tuple:
    """
    Hàm tổng hợp dành cho quy trình tiền kiểm:
    1. Lấy token hợp lệ.
    2. Kéo danh sách phiếu đang xử lý từ TTS Mới.
    3. Lọc theo nhóm dịch vụ (data: Mobile Internet, voice_sms: Thoại/SMS/Gói, all: Tất cả).
    4. Bóc tách song song SĐT khách hàng.
    5. Trả về: (danh_sách_phiếu_hợp_lệ, tổng_số_phiếu_quét)
    """
    token = extract_token_from_browser(driver)
    if not token:
        raise ValueError("Không tìm thấy Bearer Token của TTS Mới. Hãy chắc chắn bạn đã đăng nhập https://tts.vnptnet.vn trên trình duyệt (Firefox, Chrome, Edge).")

    try:
        raw_tickets = fetch_active_tickets(token, limit=1000)
    except urllib.error.HTTPError as he:
        if he.code == 401:
            token = extract_token_from_browser(driver, force_refresh=True)
            if not token:
                raise
            raw_tickets = fetch_active_tickets(token, limit=1000)
        else:
            raise
    if service_type == "data":
        target_tickets = filter_data_tickets(raw_tickets)
    elif service_type in ("call", "voice", "cuoc_goi"):
        target_tickets = filter_call_tickets(raw_tickets)
    elif service_type in ("sms", "tin_nhan"):
        target_tickets = filter_sms_tickets(raw_tickets)
    elif service_type in ("other", "khac"):
        target_tickets = filter_other_tickets(raw_tickets)
    elif service_type == "voice_sms":
        target_tickets = filter_non_data_tickets(raw_tickets)
    else:
        target_tickets = raw_tickets

    if not target_tickets:
        return [], len(raw_tickets)

    # Lấy thông tin khách hàng & SĐT song song
    enriched = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(enrich_ticket_customer, it, token) for it in target_tickets]
        for f in futures:
            try:
                res = f.result()
                if res.get("phone"):
                    enriched.append(res)
            except Exception:
                pass

    return enriched, len(raw_tickets)


def decode_jwt_user(tok_str: str) -> dict:
    """Giải mã thông tin KTV từ JWT token của TTS Mới."""
    try:
        import base64
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


def api_transfer_ttsnew_ticket(token: str, ticket_flow_id: int, ticket_id: int,
                               phone: str = "", ticket_code: str = "",
                               status: str = "", closing_content: str = "", 
                               assign_content: str = "", target_step: str = "") -> dict:
    """
    Thực hiện xử lý phiếu trên hệ thống TTS Mới qua OneOSS REST API theo đúng quy trình 2 lần xuất hiện:
    - Lần 1 (Bước 2.4):
      + Hướng Đóng 5.1: Chuyển sang bước "5.1 Xây dựng PA xử lý" (định tuyến đúng VNPT Tỉnh).
      + Hướng Đóng 2.6: Chuyển sang bước "2.6 Đóng phiếu Trên TTS" (kèm clUnitId MSC/418).
    - Lần 2 (Bước 2.6 - "2.6 Đóng phiếu Trên TTS"):
      + Đóng phiếu dứt điểm qua API close-ticket.
      + Nguyên nhân đóng phiếu: Mapped từ status trong database theo danh mục ClIncidentCause (giống TTS cũ).
      + Nội dung xử lý: Cột 10 (comment) + Cột 11 (action_plan) lấy từ database.
    """
    if not token or not str(token).strip():
        return {"success": False, "message": "❌ Thiếu token xác thực OneOSS của TTS Mới. Vui lòng đăng nhập TTS Mới trên trình duyệt!"}

    if not ticket_flow_id or not ticket_id:
        return {"success": False, "message": f"❌ Thiếu định danh bắt buộc (ticket_flow_id={ticket_flow_id}, ticket_id={ticket_id}) để xử lý phiếu TTS Mới."}

    if not token.startswith("Bearer "):
        token = "Bearer " + token

    u_info = decode_jwt_user(token)
    actor_name = u_info.get("displayName") or u_info.get("userName") or "KTV"

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Authorization": token,
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        # Nếu thiếu nội dung hoặc status, lấy trực tiếp từ database
        if not status or not closing_content or not assign_content:
            try:
                from db_manager import get_db_connection
                conn = get_db_connection()
                row = conn.execute("""
                    SELECT status, comment, action_plan 
                    FROM tickets 
                    WHERE (ticket_id = ? OR ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
                    ORDER BY updated_at DESC LIMIT 1
                """, (ticket_id, f"{ticket_code}%", phone)).fetchone()
                if row:
                    if not status and row["status"]:
                        status = str(row["status"]).strip()
                    if not closing_content and row["comment"]:
                        closing_content = str(row["comment"]).strip()
                    if not assign_content and row["action_plan"]:
                        assign_content = str(row["action_plan"]).strip()
                conn.close()
            except Exception:
                pass

        # Lấy nguyên nhân đóng phiếu (mapped từ status giống TTS cũ)
        cause_id, cause_name = get_ttsnew_incident_cause(status)

        # Nội dung xử lý (Cột 10 & Cột 11)
        c10 = str(closing_content or "").strip()
        c11 = str(assign_content or "").strip()
        combined_content = f"{c10}\n{c11}".strip() if (c10 and c11 and c10 != c11) else (c10 or c11)
        if not combined_content:
            return {"success": False, "message": f"❌ Không thể đóng/chuyển phiếu {phone or ticket_code}: Nội dung xử lý (comment/action_plan) đang bị trống!"}

        # Lấy thông tin bước hiện tại
        url_step = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/get-next-step?ticketFlowId={ticket_flow_id}"
        res_step = requests.get(url_step, headers=headers, timeout=12).json()
        if res_step.get("isError"):
            return {"success": False, "message": res_step.get("message", "Lỗi lấy bước kế tiếp")}

        step_data = res_step.get("data", {})
        curr_node = step_data.get("currentNodes", [{}])[0]
        curr_node_name = str(curr_node.get("name") or "")
        next_node_list = step_data.get("nextNodeData", [])

        # =====================================================================
        # TRƯỜNG HỢP 0: Đang ở bước 2.3 -> Tự động chuyển sang bước 2.4
        # =====================================================================
        curr_step_code = str((curr_node.get("processData") or {}).get("stepCode") or "")
        if "2.3" in curr_node_name or "2.3" in curr_step_code:
            return api_move_step_2_3_to_2_4(
                token=token,
                ticket_flow_id=ticket_flow_id,
                ticket_id=ticket_id,
                phone=phone,
                ticket_code=ticket_code
            )

        # =====================================================================
        # TRƯỜNG HỢP 1: Đang ở bước "2.6 Đóng phiếu Trên TTS" (Lần 2 xuất hiện để đóng)
        # =====================================================================
        if "2.6" in curr_node_name:
            url_close = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/close-ticket"
            form_id = curr_node.get("processData", {}).get("formId") if curr_node.get("processData") else None
            payload_close = {
                "ticketFlowId": ticket_flow_id,
                "ticketId": ticket_id,
                "processNodeInstanceId": curr_node.get("id"),
                "processDefinitionId": step_data.get("processInstanceId"),
                "formId": form_id,
                "closingContent": combined_content,
                "clIncidentCauseId": cause_id,
                "columnJson": {},
                "fileUpload": []
            }
            res_c = requests.post(url_close, headers=headers, json=payload_close, timeout=15).json()
            if res_c.get("isError"):
                return {"success": False, "message": res_c.get("message", f"Lỗi đóng phiếu 2.6: {res_c.get('error')}")}

            # Cập nhật DB trạng thái "Đã đóng" kèm tên KTV thực hiện
            try:
                from db_manager import get_db_connection
                conn = get_db_connection()
                conn.execute("""
                    UPDATE tickets 
                    SET ticket_status = 'Đã đóng', closed_by = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE (ticket_id = ? OR ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
                """, (actor_name, ticket_id, f"{ticket_code}%", phone))
                conn.commit()
                conn.close()
            except Exception:
                pass

            return {
                "success": True,
                "round": 2,
                "step_name": "2.6 Đóng phiếu Trên TTS",
                "incident_cause": cause_name,
                "action_label": "Đóng phiếu hoàn tất",
                "actor": actor_name,
                "message": f"✅ [{actor_name}] Đã đóng phiếu {ticket_code or ticket_id} thành công tại bước 2.6! (Nguyên nhân đóng: {cause_name})"
            }

        # =====================================================================
        # TRƯỜNG HỢP 2: Đang ở bước 2.4 (Lần đầu xuất hiện -> Chuyển sang 2.6 hoặc 5.1)
        # =====================================================================
        if "2.4" not in curr_node_name:
            return {
                "success": False,
                "message": f"⚠️ Phiếu đang ở bước '{curr_node_name}', không phải bước 2.4 hoặc 2.6. Hệ thống chỉ cho phép tự động đóng/chuyển bước khi phiếu ở bước 2.4 (chuyển 2.6/5.1) hoặc bước 2.6 (đóng dứt điểm). Vui lòng xử lý thủ công trên web TTS!"
            }

        if target_step == "5.1":
            is_step_5_1 = True
        elif target_step == "2.6":
            is_step_5_1 = False
        else:
            resp_content = (assign_content or "").strip().lower()
            is_step_5_1 = (
                "nhờ tạo phiếu clm chuyển vtt xử lý" in resp_content or 
                "nhờ tạo phiếu clm chuyển vtt" in resp_content or
                "chuyển vtt xử lý" in resp_content or
                "chuyển vtt" in resp_content or
                "nhờ tạo phiếu clm chuyển kỹ thuật địa bàn" in resp_content
            )

        chosen_node = None
        if is_step_5_1:
            chosen_node = next((n for n in next_node_list if "5.1" in str(n.get("name", "")) or str((n.get("processData") or {}).get("stepCode", "")).startswith("5.1")), None)
            if not chosen_node:
                chosen_node = next((n for n in next_node_list if "xây dựng pa" in str(n.get("name", "")).lower() or "phương án" in str(n.get("name", "")).lower()), None)
        else:
            chosen_node = next((n for n in next_node_list if "2.6" in str(n.get("name", "")) or str((n.get("processData") or {}).get("stepCode", "")) == "2.6"), None)
            if not chosen_node:
                chosen_node = next((n for n in next_node_list if "2.4" in str(n.get("name", "")) and "soc2" in str(n.get("name", "")).lower()), None)

        if not chosen_node:
            valid_targets = [str(n.get("name")) for n in next_node_list]
            return {
                "success": False,
                "message": f"Không tìm thấy bước đích hợp lệ (2.6 hoặc 5.1) từ bước hiện tại '{curr_node_name}'. Các bước tiếp theo khả dụng: {valid_targets}"
            }

        next_step_name = chosen_node.get("name") or "Bước tiếp theo"

        # Lấy đơn vị phụ trách
        cl_unit_id = 418
        unit_type_id = (chosen_node.get("processData") or {}).get("unitTypeId")
        is_vnpt_ttp = str(unit_type_id) == "12" or "tỉnh" in str((chosen_node.get("processData") or {}).get("unitTypeName", "")).lower()

        if is_vnpt_ttp:
            try:
                # 1. Lấy thông tin tỉnh thành của phiếu từ lịch sử hoặc DB
                province_name = ""
                url_hist = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/get-history-request-process?ticketFlowId={ticket_flow_id}"
                res_hist = requests.get(url_hist, headers=headers, timeout=8).json()
                if not res_hist.get("isError") and res_hist.get("data"):
                    province_name = res_hist["data"].get("provinceName") or ""

                # 2. Lấy danh mục 61 Viễn thông tỉnh/thành phố
                url_ttp = "https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/CfUnitTypeUnit/get-by-unit-type?id=12"
                res_ttp = requests.get(url_ttp, headers=headers, timeout=8).json()
                ttp_units = res_ttp.get("data", []) if not res_ttp.get("isError") else []

                # 3. Khớp đơn vị theo tên tỉnh
                matched_unit = None
                if province_name:
                    p_clean = province_name.lower().replace("tỉnh", "").replace("thành phố", "").replace("tp", "").strip()
                    for u_it in ttp_units:
                        u_name = u_it.get("unitName", "").lower()
                        if p_clean in u_name:
                            matched_unit = u_it
                            break

                if matched_unit:
                    cl_unit_id = matched_unit.get("clUnitId", 418)
                else:
                    url_msc = f"https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/CfUnitTypeUnit/get-by-msc?ticketId={ticket_id}"
                    res_msc = requests.get(url_msc, headers=headers, timeout=10).json()
                    if not res_msc.get("isError") and res_msc.get("data"):
                        cl_unit_id = res_msc["data"][0].get("clUnitId", 418)
            except Exception:
                pass
        else:
            try:
                url_msc = f"https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/CfUnitTypeUnit/get-by-msc?ticketId={ticket_id}"
                res_msc = requests.get(url_msc, headers=headers, timeout=10).json()
                if not res_msc.get("isError") and res_msc.get("data"):
                    cl_unit_id = res_msc["data"][0].get("clUnitId", 418)
            except Exception:
                pass

        node_unit_id = cl_unit_id
        if (chosen_node.get("processData") or {}).get("unitId"):
            try:
                node_unit_id = int(chosen_node["processData"]["unitId"])
            except Exception:
                pass

        form_id = (chosen_node.get("processData") or {}).get("formId") or (curr_node.get("processData") or {}).get("formId")
        payload = {
            "ticketFlowId": ticket_flow_id,
            "ticketId": ticket_id,
            "formId": form_id,
            "processNodeInstanceId": curr_node.get("id"),
            "processDefinitionId": step_data.get("processInstanceId"),
            "closingContent": combined_content,
            "assignContent": combined_content,
            "columnJson": {"formId": form_id} if form_id else {},
            "newTicketFlow": {
                "ticketFlowParentId": ticket_flow_id,
                "processDefinitionId": chosen_node.get("processInstanceId"),
                "processDefinitionName": chosen_node.get("processInstanceName"),
                "parentProcessNodeId": curr_node.get("id"),
                "processNodeId": chosen_node.get("id"),
                "processNodeName": chosen_node.get("name") or next_step_name,
                "clUnitId": node_unit_id if chosen_node.get("nodeType") != "endEvent" else None,
                "clTicketStatusId": None,
                "clProcessingSystemId": 5,
                "precheckCode": None
            },
            "fileUpload": []
        }

        url_submit = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/ticket-processing"
        post_res = requests.post(url_submit, headers=headers, json=payload, timeout=15).json()
        if post_res.get("isError"):
            return {"success": False, "message": post_res.get("message", f"Lỗi chuyển sang bước {next_step_name}")}

        new_status = "Chuyển VTT" if is_step_5_1 else "Chờ đóng lần 2"
        clean_code = (ticket_code or "").split("\n")[0].strip()
        new_flow_id = None
        new_actual_step = next_step_name
        try:
            time.sleep(1.2)
            raw_active = fetch_active_tickets(token, limit=100)
            for r_it in raw_active:
                if (ticket_id and str(r_it.get("ticketId")) == str(ticket_id)) or \
                   (clean_code and clean_code in str(r_it.get("ticketCode", ""))):
                    new_flow_id = r_it.get("id")
                    break
            if new_flow_id and not is_step_5_1:
                url_st = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/get-next-step?ticketFlowId={new_flow_id}"
                r_st = requests.get(url_st, headers=headers, timeout=5).json()
                c_nd = (r_st.get("data") or {}).get("currentNodes", [{}])[0]
                if c_nd.get("name"):
                    new_actual_step = c_nd["name"]
        except Exception:
            pass

        new_ticket_code_val = f"{clean_code}\n[Quy trình Chất lượng mạng & dịch vụ di động]\n{new_actual_step}" if not is_step_5_1 else ticket_code
        try:
            from db_manager import get_db_connection
            conn = get_db_connection()
            conn.execute("""
                UPDATE tickets 
                SET flow_id = COALESCE(?, flow_id),
                    ticket_code = ?,
                    ticket_status = ?, 
                    closed_by = ?, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE (ticket_id = ? OR ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
            """, (new_flow_id, new_ticket_code_val, new_status, actor_name, ticket_id, f"{clean_code}%", phone))
            conn.commit()
            conn.close()
        except Exception:
            pass

        return {
            "success": True,
            "round": 1,
            "step_name": next_step_name,
            "action_label": f"Chuyển bước '{next_step_name}'",
            "actor": actor_name,
            "message": f"✅ [{actor_name}] Đã chuyển phiếu {ticket_code or ticket_id} sang '{next_step_name}'. Phiếu sẽ xuất hiện lại ở bước 2.6 để đóng hoàn tất."
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def api_move_step_2_3_to_2_4(token: str, ticket_flow_id: int, ticket_id: int,
                            phone: str = "", ticket_code: str = "") -> dict:
    """
    Thực hiện chuyển phiếu từ bước 2.3 sang bước 2.4 trên hệ thống TTS Mới:
    - B0: Kiểm tra tính chính xác của phân loại phiếu: True
    - Nội dung xử lý (closingContent): "Chuyển 2.4"
    - Bước tiếp theo: "2.4 Đánh giá, báo cáo tình hình xử lý"
    - Đơn vị nhận (clUnitId): Trung tâm Vận hành khai thác mạng Khu vực miền Nam/Tổ Dịch vụ (SOC2) (418)
    - Nội dung chuyển giao (assignContent): "Chuyển 2.4"
    """
    if not token or not str(token).strip():
        return {"success": False, "message": "❌ Thiếu token xác thực OneOSS của TTS Mới. Vui lòng đăng nhập TTS Mới trên trình duyệt!"}

    if not ticket_flow_id or not ticket_id:
        return {"success": False, "message": f"❌ Thiếu định danh bắt buộc (ticket_flow_id={ticket_flow_id}, ticket_id={ticket_id}) để xử lý phiếu TTS Mới."}

    if not token.startswith("Bearer "):
        token = "Bearer " + token

    u_info = decode_jwt_user(token)
    actor_name = u_info.get("displayName") or u_info.get("userName") or "KTV"

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Authorization": token,
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        # 1. Lấy thông tin bước hiện tại và các bước tiếp theo khả dụng
        url_step = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/get-next-step?ticketFlowId={ticket_flow_id}"
        res_step = requests.get(url_step, headers=headers, timeout=12).json()
        if res_step.get("isError"):
            return {"success": False, "message": res_step.get("message", "Lỗi lấy bước kế tiếp từ OneOSS Gateway")}

        step_data = res_step.get("data", {})
        curr_nodes = step_data.get("currentNodes", [])
        curr_node = curr_nodes[0] if curr_nodes else {}
        curr_node_name = str(curr_node.get("name") or "")
        next_node_list = step_data.get("nextNodeData", [])

        # Kiểm tra bước hiện tại
        if "2.3" not in curr_node_name and "2.3" not in str((curr_node.get("processData") or {}).get("stepCode", "")):
            # Vẫn cho phép nếu có node 2.4 trong danh sách bước tiếp theo
            has_2_4_next = any("2.4" in str(n.get("name", "")) for n in next_node_list)
            if not has_2_4_next:
                return {
                    "success": False,
                    "message": f"⚠️ Phiếu đang ở bước '{curr_node_name}', không hỗ trợ chuyển sang 2.4. Các bước tiếp theo: {[n.get('name') for n in next_node_list]}"
                }

        # 2. Tìm node bước đích 2.4
        chosen_node = None
        for n in next_node_list:
            n_name = str(n.get("name") or "")
            n_code = str((n.get("processData") or {}).get("stepCode") or "")
            if "2.4" in n_name or "2.4" in n_code or "đánh giá" in n_name.lower():
                chosen_node = n
                break

        if not chosen_node and next_node_list:
            # Fallback lấy node đầu tiên nếu chỉ có 1 node
            if len(next_node_list) == 1:
                chosen_node = next_node_list[0]

        if not chosen_node:
            valid_targets = [str(n.get("name")) for n in next_node_list]
            return {
                "success": False,
                "message": f"Không tìm thấy bước đích 2.4 từ bước hiện tại '{curr_node_name}'. Các bước tiếp theo: {valid_targets}"
            }

        next_step_name = chosen_node.get("name") or "2.4 Đánh giá, báo cáo tình hình xử lý"

        # 3. Xác định đơn vị tiếp nhận (Trung tâm Vận hành khai thác mạng Khu vực miền Nam/Tổ Dịch vụ (SOC2) - clUnitId: 418)
        cl_unit_id = 418
        if (chosen_node.get("processData") or {}).get("unitId"):
            try:
                cl_unit_id = int(chosen_node["processData"]["unitId"])
            except Exception:
                pass
        else:
            try:
                url_msc = f"https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/CfUnitTypeUnit/get-by-msc?ticketId={ticket_id}"
                res_msc = requests.get(url_msc, headers=headers, timeout=10).json()
                if not res_msc.get("isError") and res_msc.get("data"):
                    # Tìm đơn vị có tên SOC2 hoặc miền Nam
                    soc_unit = next((u for u in res_msc["data"] if "soc2" in str(u.get("unitName", "")).lower() or "miền nam" in str(u.get("unitName", "")).lower()), None)
                    if soc_unit:
                        cl_unit_id = soc_unit.get("clUnitId", 418)
                    else:
                        cl_unit_id = res_msc["data"][0].get("clUnitId", 418)
            except Exception:
                pass

        form_id = (chosen_node.get("processData") or {}).get("formId") or (curr_node.get("processData") or {}).get("formId")
        
        column_json = {}
        if form_id:
            column_json["formId"] = form_id
            try:
                import base64, urllib.parse
                url_f = f"https://gw-oneoss.vnpt.vn/oss/tts/ap/ap-tts-api/Form/{form_id}"
                r_f = requests.get(url_f, headers=headers, timeout=8).json()
                js_info = (r_f.get("data") or {}).get("jsInfo")
                if js_info:
                    raw_s = urllib.parse.unquote(base64.b64decode(js_info).decode('utf-8', errors='ignore'))
                    schema = json.loads(raw_s)
                    for comp in schema.get("components", []):
                        k = comp.get("key")
                        label = str(comp.get("label") or "").lower()
                        if k and ("b0" in label or "phân loại" in label or comp.get("validate", {}).get("required")):
                            val = "1"
                            for v in comp.get("values", []):
                                if str(v.get("label", "")).lower() == "true":
                                    val = str(v.get("value", "1"))
                                    break
                            column_json[k] = val
            except Exception:
                pass

        if "radio_4q1pss" not in column_json:
            column_json["radio_4q1pss"] = "1"
        column_json["b0"] = "1"

        payload = {
            "ticketFlowId": ticket_flow_id,
            "ticketId": ticket_id,
            "formId": form_id,
            "processNodeInstanceId": curr_node.get("id"),
            "processDefinitionId": step_data.get("processInstanceId"),
            "closingContent": "Chuyển 2.4",
            "assignContent": "Chuyển 2.4",
            "columnJson": column_json,
            "newTicketFlow": {
                "ticketFlowParentId": ticket_flow_id,
                "processDefinitionId": chosen_node.get("processInstanceId"),
                "processDefinitionName": chosen_node.get("processInstanceName"),
                "parentProcessNodeId": curr_node.get("id"),
                "processNodeId": chosen_node.get("id"),
                "processNodeName": chosen_node.get("name") or next_step_name,
                "clUnitId": cl_unit_id if chosen_node.get("nodeType") != "endEvent" else None,
                "clTicketStatusId": None,
                "clProcessingSystemId": 5,
                "precheckCode": None
            },
            "fileUpload": []
        }

        url_submit = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/ticket-processing"
        post_res = requests.post(url_submit, headers=headers, json=payload, timeout=15).json()
        if post_res.get("isError"):
            return {"success": False, "message": post_res.get("message", f"Lỗi từ hệ thống TTS khi chuyển sang bước {next_step_name}")}

        # 4. Tra cứu ngay flow mới trên TTS Mới để cập nhật trực tiếp DB theo thời gian thực (Live)
        clean_code = (ticket_code or "").split("\n")[0].strip()
        new_flow_id = None
        new_actual_step = next_step_name
        try:
            time.sleep(1.2)
            raw_active = fetch_active_tickets(token, limit=100)
            for r_it in raw_active:
                if (ticket_id and str(r_it.get("ticketId")) == str(ticket_id)) or \
                   (clean_code and clean_code in str(r_it.get("ticketCode", ""))):
                    new_flow_id = r_it.get("id")
                    break
            if new_flow_id:
                url_st = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/get-next-step?ticketFlowId={new_flow_id}"
                r_st = requests.get(url_st, headers=headers, timeout=5).json()
                c_nd = (r_st.get("data") or {}).get("currentNodes", [{}])[0]
                if c_nd.get("name"):
                    new_actual_step = c_nd["name"]
        except Exception:
            pass

        new_ticket_code_val = f"{clean_code}\n[2.4_QT_CLM_02]\n{new_actual_step}"
        try:
            from db_manager import get_db_connection
            conn = get_db_connection()
            conn.execute("""
                UPDATE tickets 
                SET flow_id = COALESCE(?, flow_id),
                    ticket_code = ?,
                    ticket_status = 'Chưa đóng', 
                    closed_by = ?, 
                    updated_at = CURRENT_TIMESTAMP 
                WHERE (ticket_id = ? OR ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
            """, (new_flow_id, new_ticket_code_val, actor_name, ticket_id, f"{clean_code}%", phone))
            conn.commit()
            conn.close()
        except Exception:
            pass

        return {
            "success": True,
            "round": 0,
            "step_name": next_step_name,
            "action_label": f"Chuyển bước '{next_step_name}'",
            "actor": actor_name,
            "message": f"✅ [{actor_name}] Đã chuyển phiếu {ticket_code or ticket_id} ({phone}) sang bước '{next_step_name}' thành công!"
        }
    except Exception as e:
        return {"success": False, "message": f"Lỗi ngoại lệ khi chuyển bước 2.4: {str(e)}"}


def sync_tts_new_live_steps(token: str = "") -> dict:
    """
    Đồng bộ live siêu tốc (REST API OneOSS Gateway, < 1.5 giây) trạng thái bước và flow_id 
    của các phiếu TTS Mới đang mở trên dashboard mà không cần cào lại BTools/SAPC/CEM.
    """
    if not token or not str(token).strip():
        token = get_cached_token()
    if not token:
        return {"success": False, "message": "Chưa có token TTS Mới"}

    if not token.startswith("Bearer "):
        token = "Bearer " + token

    try:
        active_list = fetch_active_tickets(token, limit=100)
    except Exception as e:
        return {"success": False, "message": f"Lỗi fetch active tickets: {e}"}

    try:
        from db_manager import get_db_connection
        conn = get_db_connection()
        db_rows = conn.execute("""
            SELECT ticket_id, ticket_code, phone, flow_id, ticket_status 
            FROM tickets 
            WHERE source = 'tts_new' AND ticket_status NOT IN ('Đã đóng', 'Da dong')
        """).fetchall()

        if not db_rows:
            conn.close()
            return {"success": True, "updated": 0}

        active_map = {}
        for it in active_list:
            tid = it.get("ticketId")
            if tid:
                active_map[str(tid)] = it
            code = str(it.get("ticketCode") or "")
            if code:
                clean_c = code.split("\n")[0].strip()
                active_map[clean_c] = it

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Authorization": token,
            "Origin": "https://tts.vnptnet.vn",
            "Referer": "https://tts.vnptnet.vn/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        from db_manager import save_or_update_ticket
        from services.state import normalize_phone_vn

        updated_count = 0
        known_tids = set()
        known_codes = set()

        for row in db_rows:
            tid_str = str(row["ticket_id"] or "")
            raw_code = str(row["ticket_code"] or "")
            clean_c = raw_code.split("\n")[0].strip()
            if tid_str:
                known_tids.add(tid_str)
            if clean_c:
                known_codes.add(clean_c)

            matched_it = active_map.get(tid_str) or active_map.get(clean_c)
            if matched_it:
                latest_flow_id = matched_it.get("id")
                # Nếu flow_id khác hoặc bước hiện tại cần làm mới
                if latest_flow_id and (str(row["flow_id"]) != str(latest_flow_id) or "2.3" in raw_code or "2.4" in raw_code):
                    try:
                        url_step = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/get-next-step?ticketFlowId={latest_flow_id}"
                        r_step = requests.get(url_step, headers=headers, timeout=5).json()
                        c_nodes = (r_step.get("data") or {}).get("currentNodes", [])
                        if c_nodes:
                            c_node = c_nodes[0]
                            c_name = str(c_node.get("name") or "")
                            c_proc = str((c_node.get("processData") or {}).get("processName") or "")
                            
                            new_code_lines = [clean_c]
                            if c_proc:
                                new_code_lines.append(f"[{c_proc}]")
                            if c_name:
                                new_code_lines.append(c_name)
                            new_ticket_code = "\n".join(new_code_lines)

                            if str(row["flow_id"]) != str(latest_flow_id) or raw_code != new_ticket_code:
                                conn.execute("""
                                    UPDATE tickets 
                                    SET flow_id = ?, ticket_code = ?, updated_at = CURRENT_TIMESTAMP 
                                    WHERE ticket_id = ? AND source = 'tts_new'
                                """, (latest_flow_id, new_ticket_code, row["ticket_id"]))
                                updated_count += 1
                    except Exception:
                        pass
            else:
                # Phiếu không còn nằm trong active_list -> tự động đánh dấu đã đóng trên TTS Mới
                try:
                    conn.execute("""
                        UPDATE tickets 
                        SET ticket_status = 'Đã đóng', updated_at = CURRENT_TIMESTAMP 
                        WHERE ticket_id = ? AND source = 'tts_new'
                    """, (row["ticket_id"],))
                    updated_count += 1
                except Exception:
                    pass

        conn.commit()
        conn.close()
        conn = None

        # 2. PHÁT HIỆN & TỰ ĐỘNG NẠP PHIẾU MỚI TINH VÀO ĐÚNG PHÂN HỆ MODULE
        for it in active_list:
            it_tid = str(it.get("ticketId") or "")
            it_code = str(it.get("ticketCode") or "").split("\n")[0].strip()
            if (it_tid and it_tid not in known_tids) and (it_code and it_code not in known_codes):
                try:
                    en_ticket = enrich_ticket_customer(it, token)
                    phone_val = normalize_phone_vn(en_ticket.get("phone") or "")
                    if phone_val:
                        inc_time = str(en_ticket.get("incident_time") or en_ticket.get("created_time") or "").strip()
                        rec = {
                            "phone": phone_val,
                            "incident_time": inc_time,
                            "package_title": it.get("title", "Mobile Internet"),
                            "ticket_content": it.get("content", ""),
                            "status": "CHỜ TIỀN KIỂM",
                            "real_packages": "--",
                            "rat_types": "--",
                            "cem_data": "--",
                            "app_usage": "--",
                            "ai_summary": it.get("content", ""),
                            "comment": "",
                            "action_plan": "",
                            "ticket_status": "Chưa đóng",
                            "force_update_status": True,
                            "source": "tts_new",
                            "created_time": it.get("requestDate", ""),
                            "ticket_code": en_ticket.get("ticket_code") or it_code,
                            "ticket_id": it.get("ticketId"),
                            "flow_id": it.get("id"),
                            "reopen_count": int(it.get("reopenCount") or 0),
                            "last_reopened_date": str(it.get("lastReopenedDate") or "").strip()
                        }
                        save_or_update_ticket(rec)
                        updated_count += 1
                        known_tids.add(it_tid)
                        if it_code:
                            known_codes.add(it_code)
                except Exception:
                    pass

        return {"success": True, "updated": updated_count}
    except Exception as ex:
        if 'conn' in locals() and conn:
            try:
                conn.close()
            except Exception:
                pass
        return {"success": False, "message": str(ex)}


