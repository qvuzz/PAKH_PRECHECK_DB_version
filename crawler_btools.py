import time
import urllib.request
import re

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


def get_btools_cookie(driver=None, force_refresh=False):
    """
    Lấy cookie JSESSIONID từ Chrome tab BTools và cache lại.
    Nếu chưa có, mở nhẹ page BTools qua Playwright CDP để tạo phiên.
    """
    global _BTOOLS_COOKIE_CACHE
    if _BTOOLS_COOKIE_CACHE and not force_refresh:
        return _BTOOLS_COOKIE_CACHE

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            cookies = context.cookies()
            btools_cookies = [f"{c['name']}={c['value']}" for c in cookies if "10.159.21.241" in c.get("domain", "")]
            if btools_cookies and not force_refresh:
                _BTOOLS_COOKIE_CACHE = "; ".join(btools_cookies)
            else:
                page = context.new_page()
                page.goto("http://10.159.21.241:9267/B_tools_v2/", timeout=10000)
                cookies = context.cookies()
                btools_cookies = [f"{c['name']}={c['value']}" for c in cookies if "10.159.21.241" in c.get("domain", "")]
                if btools_cookies:
                    _BTOOLS_COOKIE_CACHE = "; ".join(btools_cookies)
                page.close()
            browser.close()
    except Exception:
        pass

    if not driver:
        return _BTOOLS_COOKIE_CACHE

    orig_handle = None
    try:
        orig_handle = driver.current_window_handle
    except Exception:
        pass

    cookie_val = None
    try:
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                if "10.159.21.241" in driver.current_url:
                    cookies = driver.get_cookies()
                    cookie_parts = [f"{c['name']}={c['value']}" for c in cookies]
                    if cookie_parts:
                        cookie_val = "; ".join(cookie_parts)
                        break
            except Exception:
                continue
    finally:
        if orig_handle:
            try:
                driver.switch_to.window(orig_handle)
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
                print(f"[BTools HTTP Ngầm] Phản hồi không hợp lệ: {err_reason}")
        except Exception as ex_http:
            print(f"[BTools] Chạy ngầm HTTP gặp lỗi ({ex_http}), chuyển sang phương án dự phòng...")

    # --- PHƯƠNG ÁN 2: SILENT FETCH QUA JAVASCRIPT TRÊN TAB BTOOLS (KHÔNG RELOAD TRANG) ---
    if driver:
        try:
            btools_handle = None
            orig_h = driver.current_window_handle
            for h in driver.window_handles:
                try:
                    driver.switch_to.window(h)
                    if "10.159.21.241" in driver.current_url:
                        btools_handle = h
                        break
                except Exception:
                    continue

            if btools_handle:
                driver.switch_to.window(btools_handle)
                js_fetch = f"""
                var done = arguments[arguments.length - 1];
                fetch('{query_url}')
                    .then(r => r.text())
                    .then(html => done(html))
                    .catch(err => done(''));
                """
                html = driver.execute_async_script(js_fetch)
                driver.switch_to.window(orig_h)
                
                valid, err_reason = is_valid_btools_html(html)
                if valid:
                    data_rows = parse_btools_table_html(html)
                    if data_rows:
                        print(f"[BTools Silent Fetch] Đã cào thành công {len(data_rows)} dòng dữ liệu.")
                    else:
                        print(f"[BTools Silent Fetch] Thuê bao {target_phone} không phát sinh phiên dữ liệu.")
                    return data_rows
                else:
                    print(f"[BTools Silent Fetch] Phản hồi không hợp lệ: {err_reason}")
            else:
                driver.switch_to.window(orig_h)
        except Exception as ex_fetch:
            print(f"[BTools] Silent Fetch gặp lỗi: {ex_fetch}")

    # --- PHƯƠNG ÁN 3: DỰ PHÒNG CUỐI CÙNG (SELENIUM NAVIGATE TRỰC TIẾP) ---
    if driver:
        try:
            print(f"[BTools] Sử dụng chế độ tải trang truyền thống cho: {target_phone}")
            driver.get(query_url)
            table_loaded = False
            for _ in range(20):
                time.sleep(0.4)
                has_table = driver.execute_script("""
                    var tbl = document.querySelector('table');
                    if(!tbl) return false;
                    return tbl.innerText.toUpperCase().includes("RAT_TYPE") || tbl.innerText.toUpperCase().includes("MSISDN");
                """)
                if has_table:
                    table_loaded = True
                    break
            if table_loaded:
                html = driver.page_source
                valid, err_reason = is_valid_btools_html(html)
                if valid:
                    data_rows = parse_btools_table_html(html)
                    print(f"[BTools Legacy] Đã cào thành công {len(data_rows)} dòng dữ liệu.")
                    return data_rows
                else:
                    print(f"[BTools Legacy] Phản hồi không hợp lệ: {err_reason}")
        except Exception as ex_nav:
            print(f"[BTools Legacy] Lỗi tải trang truyền thống: {ex_nav}")

    # BTOOLS LỖI HOẶC CHƯA ĐĂNG NHẬP -> TRẢ VỀ None ĐỂ BÁO LỖI VÀ KHÔNG TỰ ĐỘNG ĐÓNG PHIẾU
    print(f"[BTools] ⚠️ CẢNH BÁO: Không thể truy cập dữ liệu BTools cho {target_phone} (Chưa đăng nhập hoặc lỗi máy chủ). Trả về None!")
    return None