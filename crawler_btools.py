import sys
import time
import urllib.request
import re
import os
import json
from datetime import datetime, timedelta

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# Global cache cho session cookie BTools
_BTOOLS_COOKIE_CACHE = None


def _normalize_phone(phone_84):
    clean_p = "".join(filter(str.isdigit, str(phone_84 or "").strip()))
    if clean_p.startswith("84") and len(clean_p) == 11:
        return clean_p
    elif clean_p.startswith("0") and len(clean_p) == 10:
        return "84" + clean_p[1:]
    elif len(clean_p) == 9:
        return "84" + clean_p
    elif clean_p.startswith("0"):
        return "84" + clean_p[1:]
    elif not clean_p.startswith("84"):
        return "84" + clean_p
    return clean_p


def _normalize_date_btools(d_str):
    """
    Chuẩn hóa ngày về định dạng ddmmyyyy theo đúng yêu cầu của Oracle BTools.
    Hỗ trợ đầu vào: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, hoặc ddmmyyyy.
    """
    clean = str(d_str or "").strip()
    if not clean:
        return ""
    if len(clean) == 8 and clean.isdigit():
        return clean
    if " " in clean:
        clean = clean.split()[0]
    if "-" in clean:
        parts = clean.split("-")
        if len(parts) == 3:
            if len(parts[0]) == 4:  # 2026-08-28
                return f"{parts[2].zfill(2)}{parts[1].zfill(2)}{parts[0]}"
            elif len(parts[2]) == 4:  # 28-08-2026
                return f"{parts[0].zfill(2)}{parts[1].zfill(2)}{parts[2]}"
    if "/" in clean:
        parts = clean.split("/")
        if len(parts) == 3:
            if len(parts[2]) == 4:  # 28/08/2026
                return f"{parts[0].zfill(2)}{parts[1].zfill(2)}{parts[2]}"
            elif len(parts[0]) == 4:  # 2026/08/28
                return f"{parts[2].zfill(2)}{parts[1].zfill(2)}{parts[0]}"
    return clean


def _get_btools_cookie_via_cdp_ws(port=9222):
    """Trích xuất cookie của BTools trực tiếp qua CDP WebSocket không chuyển tab."""
    try:
        import urllib.request, json, asyncio, websockets
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as r:
            tabs = json.loads(r.read().decode("utf-8"))
        ws_url = None
        for t in tabs:
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                ws_url = t.get("webSocketDebuggerUrl")
                break
        if not ws_url:
            return ""

        async def _query():
            async with websockets.connect(ws_url) as ws:
                msg = {"id": 1, "method": "Network.getAllCookies", "params": {}}
                await ws.send(json.dumps(msg))
                resp = await ws.recv()
                data = json.loads(resp)
                cookies = data.get("result", {}).get("cookies", [])
                btools_cookies = [f"{c['name']}={c['value']}" for c in cookies if "10.159.21.241" in c.get("domain", "")]
                return "; ".join(btools_cookies)

        return asyncio.run(_query())
    except Exception:
        return ""


def get_btools_cookie(driver=None, force_refresh=False):
    """
    Lấy chuỗi cookie xác thực của BTools từ bất kỳ trình duyệt nào (Chrome, Edge, Firefox).
    Tuyệt đối KHÔNG gọi driver.switch_to.window() để không làm gián đoạn người dùng.
    """
    global _BTOOLS_COOKIE_CACHE
    if _BTOOLS_COOKIE_CACHE and not force_refresh:
        return _BTOOLS_COOKIE_CACHE


    # 1. Trích xuất đa trình duyệt (Chrome, Edge, Firefox, browser_cookie3)
    try:
        from auth_extractor import get_universal_btools_cookie
        cookie_val = get_universal_btools_cookie(driver=driver)
        if cookie_val:
            _BTOOLS_COOKIE_CACHE = cookie_val
            return _BTOOLS_COOKIE_CACHE
    except Exception:
        pass

    cookie_val = None

    # 2. Fallback qua CDP Network.getAllCookies từ Selenium driver (nếu có)
    if driver:
        try:
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            btools_cookies = [f"{c['name']}={c['value']}" for c in cookies if "10.159.21.241" in c.get("domain", "")]
            if btools_cookies:
                cookie_val = "; ".join(btools_cookies)
        except Exception:
            pass

    # 3. Fallback qua CDP WebSocket tới port 9222
    if not cookie_val:
        try:
            cookie_val = _get_btools_cookie_via_cdp_ws()
        except Exception:
            pass

    if cookie_val:
        _BTOOLS_COOKIE_CACHE = cookie_val
    return _BTOOLS_COOKIE_CACHE


def parse_btools_table_html(html):
    """
    Bóc tách bảng dữ liệu BTools từ mã nguồn HTML.
    Trả về danh sách dict tương thích 100% với cấu trúc dữ liệu cũ.
    """
    if not html:
        return []

    # 1. Tìm danh sách tiêu đề th
    ths = [
        re.sub(r'<[^>]+>', '', th).strip().upper() 
        for th in re.findall(r'<th[^>]*>(.*?)</th>', html, re.DOTALL | re.IGNORECASE)
    ]
    
    col_idx = {
        name: ths.index(name) if name in ths else -1
        for name in [
            'MSISDN', 
            'RAT_TYPE', 
            'DATA_VOLUME_UPLINK', 
            'DATA_VOLUME_DOWNLINK', 
            'RECORD_OPENING_TIME', 
            'SERVICE_ID'
        ]
    }
    
    # Kiểm tra xem có cột tối thiểu không
    if col_idx['MSISDN'] == -1 and col_idx['RAT_TYPE'] == -1:
        return []

    max_idx = max(col_idx.values())
    trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
    data_rows = []

    for tr in trs:
        tds = [
            re.sub(r'<[^>]+>', '', td).strip() 
            for td in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL | re.IGNORECASE)
        ]
        if len(tds) > max_idx:
            first_cell = tds[0].upper()
            if first_cell == 'MSISDN' or 'DANH SÁCH' in first_cell or 'BƯỚC' in first_cell:
                continue
            data_rows.append({
                k: tds[v] if v != -1 and v < len(tds) else '' 
                for k, v in col_idx.items()
            })

    return data_rows


def is_valid_btools_html(html):
    """
    Kiểm tra xem phản hồi HTML có phải là trang dữ liệu BTools hợp lệ và đã đăng nhập hay không.
    Trả về (is_valid: bool, error_msg: str)
    """
    if not html or not isinstance(html, str):
        return False, "Không nhận được phản hồi HTML từ BTools"
    
    # Bị chuyển hướng về trang đăng nhập CAS
    if any(k in html for k in ["CAS – Central Authentication Service", "/cas/login", "id=\"login\"", "Tên đăng nhập"]):
        if "/cas/" in html or "Central Authentication Service" in html or "cas-section" in html:
            return False, "BTools chưa được đăng nhập (bị chuyển hướng về cổng xác thực CAS)"
            
    if "SQLException" in html or "Internal Server Error" in html or "HTTP Status 500" in html:
        return False, "Máy chủ BTools báo lỗi cơ sở dữ liệu (SQLException / 500)"
        
    # Trang BTools hợp lệ: chứa bảng data_view, table customers, form tìm kiếm hoặc các cột dữ liệu
    if any(k in html for k in ["customers", "data_view.jsp", "RAT_TYPE", "MSISDN", "DATA_VOLUME", "name=\"name\"", "Tìm Kiếm"]):
        return True, ""
        
    return False, "Trang phản hồi không đúng cấu trúc BTools"


def extract_btools_single_phone(driver, phone_84, start_d, end_d):
    """
    Tra cứu dữ liệu kỹ thuật BTools của một thuê bao.
    Trả về:
      - list: Danh sách các dòng dữ liệu (có thể [] nếu thuê bao thực sự không có data trong khoảng thời gian).
      - None: Nếu BTools chưa đăng nhập, bị điều hướng về CAS, hoặc gặp lỗi kết nối/máy chủ.
    """
    target_phone = _normalize_phone(phone_84)
    s_clean = _normalize_date_btools(start_d)
    e_clean = _normalize_date_btools(end_d)
    query_url = (
        f"http://10.159.21.241:9267/B_tools_v2/data_view.jsp?"
        f"name={target_phone}&start_d={s_clean}&end_d={e_clean}&submit=T%C3%ACm+Ki%E1%BA%BFm"
    )

    print(f"[BTools] Tra cứu ngầm cho thuê bao: {target_phone} ({s_clean} -> {e_clean})")

    # --- PHƯƠNG ÁN 1: CHẠY NGẦM HOÀN TOÀN QUA HTTP REQUEST (SIÊU TỐC) ---
    cookie_str = get_btools_cookie(driver)
    if cookie_str:
        try:
            req = urllib.request.Request(
                query_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Cookie": cookie_str
                }
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                
            valid, err_reason = is_valid_btools_html(html)
            if not valid and ("CAS" in err_reason or "đăng nhập" in err_reason):
                print("[BTools] Phiên cookie hết hạn, đang lấy lại cookie mới từ Chrome...")
                cookie_str = get_btools_cookie(driver, force_refresh=True)
                if cookie_str:
                    req = urllib.request.Request(
                        query_url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Cookie": cookie_str
                        }
                    )
                    with urllib.request.urlopen(req, timeout=12) as resp2:
                        html = resp2.read().decode("utf-8", errors="ignore")
                        valid, err_reason = is_valid_btools_html(html)

            if valid:
                data_rows = parse_btools_table_html(html)
                if data_rows:
                    print(f"[BTools HTTP Ngầm] Đã cào thành công {len(data_rows)} dòng dữ liệu.")
                else:
                    print(f"[BTools HTTP Ngầm] Thuê bao {target_phone} không phát sinh phiên dữ liệu BTools.")
                return data_rows
            else:
                global _BTOOLS_COOKIE_CACHE
                _BTOOLS_COOKIE_CACHE = None
                print(f"[BTools HTTP Ngầm] Phản hồi không hợp lệ: {err_reason}")
        except Exception as ex_http:
            print(f"[BTools] Lỗi gửi request ngầm HTTP: {ex_http}")

    # BTOOLS LỖI HOẶC CHƯA ĐĂNG NHẬP -> TRẢ VỀ None ĐỂ BÁO LỖI VÀ KHÔNG TỰ ĐỘNG ĐÓNG PHIẾU (KHÔNG NHẢY TAB TRÌNH DUYỆT)
    print(f"[BTools] ⚠️ CẢNH BÁO: Không thể truy cập dữ liệu BTools cho {target_phone} (Chưa đăng nhập hoặc lỗi máy chủ). Trả về None!")
    return None


def fetch_supplementary_btools_if_needed(driver, phone_84, clean_data, earliest_reg_dt, start_scan_date):
    """
    Hành vi bổ sung cho Case 2: Tra cứu bổ sung BTools từ lúc đăng ký gói (earliest_reg_dt)
    đến trước chu kỳ quét (start_scan_date - 1 ngày).
    Nếu clean_data đã chứa dữ liệu trước start_scan_date thì giữ nguyên không tra lại.
    Trả về: clean_data đã được hợp nhất (merged).
    """
    if not phone_84 or not earliest_reg_dt:
        return clean_data

    # 1. Kiểm tra xem clean_data đã có dữ liệu trước start_scan_date chưa
    for r in (clean_data or []):
        t_str = r.get("RECORD_OPENING_TIME", "")
        if t_str:
            try:
                d = datetime.strptime(t_str.split()[0], "%d/%m/%Y").date()
                if d < start_scan_date:
                    return clean_data
            except Exception:
                pass

    # 2. Xác định khoảng thời gian cần tra cứu bổ sung
    reg_date = earliest_reg_dt.date() if isinstance(earliest_reg_dt, datetime) else earliest_reg_dt
    if reg_date >= start_scan_date:
        return clean_data

    # Giới hạn tối đa 30 ngày trước start_scan_date
    supp_start_date = max(reg_date, start_scan_date - timedelta(days=30))
    supp_end_date = start_scan_date - timedelta(days=1)
    if supp_start_date > supp_end_date:
        return clean_data

    supp_start_str = supp_start_date.strftime("%d%m%Y")
    supp_end_str = supp_end_date.strftime("%d%m%Y")

    print(f"[BTools Supplementary] 🔍 [Case 2] Tra cứu bổ sung cho {phone_84} từ {supp_start_str} đến {supp_end_str} (Gói ĐK {reg_date.strftime('%d/%m/%Y')})")

    try:
        from data_processor import standardize_btools_data
        raw_supp = extract_btools_single_phone(driver, phone_84, supp_start_str, supp_end_str)
        supp_clean = standardize_btools_data(raw_supp)
        if supp_clean:
            # Hợp nhất và loại bỏ trùng lặp nếu có
            seen_keys = set()
            merged = []
            for r in list(clean_data or []) + list(supp_clean or []):
                key = (r.get("RECORD_OPENING_TIME"), r.get("SERVICE_ID"), r.get("DATA_VOLUME_DOWNLINK"))
                if key not in seen_keys:
                    seen_keys.add(key)
                    merged.append(r)

            # Cập nhật lại file number/{phone_84}.json nếu tồn tại
            out_dir = os.path.join(os.getcwd(), "number")
            j_path = os.path.join(out_dir, f"{phone_84}.json")
            if os.path.exists(j_path):
                try:
                    with open(j_path, "r", encoding="utf-8") as jf:
                        jd = json.load(jf)
                    jd["btools_technical_data"] = merged
                    jd["data"] = merged
                    with open(j_path, "w", encoding="utf-8") as jf:
                        json.dump(jd, jf, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            print(f"[BTools Supplementary] Đã hợp nhất {len(supp_clean)} dòng bổ sung vào clean_data (Tổng: {len(merged)} dòng).")
            return merged
    except Exception as e:
        print(f"[BTools Supplementary] ⚠️ Lỗi tra cứu bổ sung: {e}")

    return clean_data