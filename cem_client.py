import os
import ssl
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Memory Cache cho kết quả CEM để tránh spam request liên tục (TTL 15 phút)
_cem_memory_cache = {}
_cem_cache_lock = threading.Lock()
_CEM_CACHE_TTL = 900

# Khắc phục lỗi [SSL: DH_KEY_TOO_SMALL] trên server VNPT Media
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        except Exception:
            pass
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)


CEM_URL = os.getenv("CEM_API_URL", "https://api-cem.vnptmedia.vn/api2/getSubHistoryInfo")
DEFAULT_API_KEY = "net_ktm_quangvu%6kvjpF82DYQPjgqJHyhGow6iGA5IPaxQO9klaxm6"
CEM_API_KEY = os.getenv("CEM_API_KEY", DEFAULT_API_KEY)

CEM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://cem.vnptmedia.vn",
    "Referer": "https://cem.vnptmedia.vn/",
}


def safe_log(msg: str):
    """In log ra màn hình an toàn trên mọi hệ điều hành (tránh UnicodeEncodeError trên Windows cp1252)."""
    try:
        print(msg)
    except Exception:
        try:
            clean_msg = msg.encode("ascii", errors="replace").decode("ascii")
            print(clean_msg)
        except Exception:
            pass


def format_active_dates_compact(date_list):
    """
    Format danh sách các ngày có dữ liệu thành chuỗi ngắn gọn, ví dụ:
    ['2026-09-01', '2026-09-02', '2026-09-03'] -> '1-2-3/9'
    ['2026-08-25', '2026-08-26', '2026-08-28'] -> '25-26-28/8'
    ['2026-08-31', '2026-09-01', '2026-09-02'] -> '31/8, 1-2/9'
    """
    if not date_list:
        return ""
    
    from datetime import datetime
    from collections import defaultdict

    parsed_dates = []
    for d in date_list:
        if not d:
            continue
        if isinstance(d, str):
            clean_d = d.strip()
            try:
                if "-" in clean_d:
                    parsed_dates.append(datetime.strptime(clean_d[:10], "%Y-%m-%d"))
                elif "/" in clean_d:
                    parsed_dates.append(datetime.strptime(clean_d[:10], "%d/%m/%Y"))
            except Exception:
                pass
        elif isinstance(d, datetime):
            parsed_dates.append(d)

    if not parsed_dates:
        return ""

    unique_dates = sorted(list(set(parsed_dates)))
    month_groups = defaultdict(list)
    for dt in unique_dates:
        month_groups[(dt.year, dt.month)].append(dt.day)

    parts = []
    for (year, month), days in sorted(month_groups.items(), key=lambda x: (x[0][0], x[0][1])):
        day_str = "-".join(str(day) for day in sorted(days))
        parts.append(f"{day_str}/{month}")

    return ", ".join(parts)


def parse_incident_date(incident_time_str):
    """
    Trích xuất an toàn datetime.date từ chuỗi thời gian sự cố / tiếp nhận
    (hỗ trợ cả có giây, không có giây (%H:%M), hoặc chỉ có ngày).
    """
    if not incident_time_str:
        return None
    clean = str(incident_time_str).strip()
    d_part = clean.split()[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(d_part, fmt).date()
        except Exception:
            pass
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(clean, fmt).date()
        except Exception:
            pass
    return None


class CEMClient:
    def __init__(self, api_key=None, driver=None):
        self.driver = driver
        self.last_auth_error = False
        self.api_key = api_key or os.getenv("CEM_API_KEY", DEFAULT_API_KEY)
        self.session = requests.Session()
        self.session.mount("https://", LegacySSLAdapter(pool_connections=20, pool_maxsize=20))
        self.load_cookies_from_chrome(driver=driver)

    def load_cookies_from_chrome(self, driver=None, force_refresh=False):
        """Tự động trích xuất apikey và toàn bộ cookie của CEM từ trình duyệt (Chrome CDP, Firefox, Edge)."""
        drv = driver or self.driver
        if not drv:
            try:
                from auth_extractor import get_chrome_debug_driver
                drv = get_chrome_debug_driver()
                if drv:
                    self.driver = drv
            except Exception:
                pass

        try:
            from auth_extractor import get_universal_cem_auth
            extracted_key, cookies_dict = get_universal_cem_auth(driver=drv, force_refresh=force_refresh)

            for name, val in cookies_dict.items():
                self.session.cookies.set(name, val, domain="cem.vnptmedia.vn", path="/")
                self.session.cookies.set(name, val, domain=".vnptmedia.vn", path="/")
                self.session.cookies.set(name, val, domain="api-cem.vnptmedia.vn", path="/")

            if extracted_key:
                import urllib.parse
                while "%25" in extracted_key:
                    extracted_key = urllib.parse.unquote(extracted_key)
                self.api_key = extracted_key
                self.last_auth_error = False
                safe_log(f"[CEM] Đã tự động cập nhật API Key từ trình duyệt: {self.api_key[:25]}...")
                return True
        except Exception as e:
            safe_log(f"[CEM] Không thể trích xuất cookie tự động: {e}")

        return False

    def _post_with_retry(self, url, payload, headers=None, timeout=15):
        """
        Gửi POST request đến CEM API, tự động phát hiện mã 401/403/405 hoặc 'Authentication Fail'
        và làm mới session/apikey từ Chrome rồi gửi lại (retry).
        """
        if headers is None:
            headers = CEM_HEADERS

        import urllib.parse
        clean_key = self.api_key or ""
        while "%25" in clean_key:
            clean_key = urllib.parse.unquote(clean_key)
        payload["apikey"] = clean_key
        try:
            res = self.session.post(url, headers=headers, json=payload, timeout=timeout, verify=False)
        except Exception as ex:
            return None, str(ex)

        # Kiểm tra nếu bị hết hạn session / Authentication Fail
        is_auth_fail = (res.status_code in (401, 403, 405))
        if not is_auth_fail and res.status_code == 200:
            try:
                data_check = res.json()
                if isinstance(data_check, dict) and "Authentication Fail" in str(data_check.get("message", "")):
                    is_auth_fail = True
            except Exception:
                pass

        if is_auth_fail:
            safe_log("[CEM] ⚠️ Phát hiện API Key hoặc Session CEM hết hạn!")
            if not self.last_auth_error:
                refreshed = self.load_cookies_from_chrome(force_refresh=True)
                if refreshed and self.api_key != payload.get("apikey"):
                    payload["apikey"] = self.api_key
                    try:
                        res = self.session.post(url, headers=headers, json=payload, timeout=timeout, verify=False)
                        safe_log(f"[CEM] ✅ Thử lại thành công sau khi làm mới key (status={res.status_code})")
                        return res, None
                    except Exception as ex_retry:
                        return None, str(ex_retry)
            self.last_auth_error = True
            safe_log("[CEM] ❌ Vui lòng mở trang CEM hoặc dùng Extension để đồng bộ API Key.")

        return res, None

    def get_subscriber_history_5days(self, msisdn, days=5, use_cache=True, incident_time_str=None):
        """
        Tra cứu lịch sử bắt sóng Cell từ CEM API trong N ngày gần nhất và ngày tiếp nhận sự cố (nếu có).
        Truy vấn song song đa luồng.
        MSISDN chuẩn hóa bỏ số 0 và mã quốc gia 84 (ví dụ 918161817).
        """
        clean_phone = "".join(filter(str.isdigit, str(msisdn or "").strip()))
        if clean_phone.startswith("84") and len(clean_phone) >= 11:
            clean_phone = clean_phone[2:]
        elif clean_phone.startswith("0") and len(clean_phone) >= 10:
            clean_phone = clean_phone[1:]

        cache_key = f"cell_{clean_phone}_{days}_{incident_time_str or ''}"
        now_ts = time.time()
        if use_cache:
            with _cem_cache_lock:
                cached_entry = _cem_memory_cache.get(cache_key)
                if cached_entry and (now_ts - cached_entry["ts"] < _CEM_CACHE_TTL):
                    return cached_entry["data"]

        today = datetime.now()
        recent_dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        incident_dates = []
        inc_dt = parse_incident_date(incident_time_str)
        if inc_dt:
            incident_dates.append(inc_dt.strftime("%Y-%m-%d"))

        target_dates = sorted(list(set(recent_dates + incident_dates)), reverse=True)

        def _fetch_day_cell(date_str):
            payload = {
                "start_date": date_str,
                "msisdn": clean_phone
            }
            res, err = self._post_with_retry(CEM_URL, payload, timeout=12)
            day_records = []
            if res and res.status_code == 200:
                try:
                    data = res.json()
                    items = data.get("data") or data.get("result") or data
                    if isinstance(items, list):
                        for row in items:
                            if isinstance(row, dict):
                                row["_query_date"] = date_str
                                day_records.append(row)
                except Exception as e:
                    safe_log(f"[CEM] Lỗi parse dữ liệu ngày {date_str} cho {clean_phone}: {e}")
            elif err:
                safe_log(f"[CEM] Lỗi kết nối ngày {date_str} cho {clean_phone}: {err}")
            return day_records

        all_records = []
        with ThreadPoolExecutor(max_workers=min(len(target_dates), 5)) as executor:
            results = list(executor.map(_fetch_day_cell, target_dates))
            for day_recs in results:
                all_records.extend(day_recs)

        if all_records:
            with _cem_cache_lock:
                _cem_memory_cache[cache_key] = {"data": all_records, "ts": now_ts}

        return all_records

    def get_subscriber_cell_history(self, msisdn, days=5):
        """Alias cho get_subscriber_history_5days hỗ trợ tương thích ngược."""
        return self.get_subscriber_history_5days(msisdn, days=days)

    @staticmethod
    def extract_top_cells_summary(records, app_events=None):
        """
        Trích xuất tên Cell và tính Top 3 Cell bắt sóng nhiều nhất kèm phần trăm (%) và ngày có data.
        """
        vpn_note = ""
        if app_events:
            try:
                from report_bot import detect_vpn_application
                vpn_name = detect_vpn_application(app_events)
                if vpn_name:
                    vpn_note = f"\n⚠️ CẢNH BÁO VPN: Phát hiện thiết bị có app {vpn_name}"
            except Exception:
                pass

        if not records or not isinstance(records, list):
            return f"Không có dữ liệu CEM (5 ngày){vpn_note}"

        # Tìm tên trường Cell trong các bản ghi JSON của CEM và gom ngày có data
        cell_identifiers = []
        active_dates = set()

        for r in records:
            if not isinstance(r, dict):
                continue
            cell_name = (
                r.get("cell_name")
                or r.get("cell_name_5g")
                or r.get("cellName")
                or r.get("cell_id")
                or r.get("cellId")
                or r.get("cgi")
                or r.get("CGI")
                or r.get("site_name")
                or r.get("siteName")
                or r.get("enodeb_id")
                or (f"ECI:{r.get('eci')}" if r.get('eci') else None)
            )
            if cell_name:
                cell_identifiers.append(str(cell_name).strip())
                q_date = r.get("_query_date") or r.get("start_date") or r.get("date") or r.get("time")
                if q_date:
                    active_dates.add(str(q_date)[:10])

        if not cell_identifiers:
            return f"Không có thông tin Cell{vpn_note}"

        total_samples = len(cell_identifiers)
        counter = Counter(cell_identifiers)
        top_3 = counter.most_common(3)

        lines = []
        compact_date_str = format_active_dates_compact(active_dates)
        if compact_date_str:
            lines.append(f"({compact_date_str}):")

        for rank, (cell, count) in enumerate(top_3, 1):
            pct = (count / total_samples) * 100
            lines.append(f"• {cell}: {pct:.1f}% ({count}/{total_samples})")

        # 🎯 Bổ sung cảnh báo VPN ngay sau phần Cell
        if vpn_note:
            lines.append(vpn_note.strip())

        return "\n".join(lines)

    @staticmethod
    def extract_two_period_summary(records, incident_time_str=None, app_events=None, days=5):
        """
        Trích xuất dữ liệu CEM chia làm 2 phần:
        - Cột 1: Ngày tiếp nhận sự cố
        - Cột 2: Ngày gần nhất lấy được data (5 ngày)
        Trả về tuple: (summary_incident, summary_recent, combined_str)
        """
        vpn_note = ""
        if app_events:
            try:
                from report_bot import detect_vpn_application
                vpn_name = detect_vpn_application(app_events)
                if vpn_name:
                    vpn_note = f"\n⚠️ CẢNH BÁO VPN: Phát hiện thiết bị có app {vpn_name}"
            except Exception:
                pass

        today = datetime.now()
        recent_dates_set = set((today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days))

        inc_date_str = None
        inc_date_vn = None
        dt = parse_incident_date(incident_time_str)
        if dt:
            inc_date_str = dt.strftime("%Y-%m-%d")
            inc_date_vn = dt.strftime("%d/%m/%Y")

        incident_recs = []
        recent_recs = []
        for r in (records or []):
            if not isinstance(r, dict):
                continue
            q_date = r.get("_query_date") or str(r.get("start_date") or r.get("date") or r.get("time") or "")[:10]
            if inc_date_str and q_date == inc_date_str:
                incident_recs.append(r)
            if q_date in recent_dates_set:
                recent_recs.append(r)

        # 1. Tóm tắt ngày tiếp nhận
        if not inc_date_str:
            summary_incident = "Chưa có thông tin ngày tiếp nhận"
        elif not incident_recs:
            summary_incident = f"Không có dữ liệu CEM ngày {inc_date_vn}"
        else:
            summary_incident = CEMClient.extract_top_cells_summary(incident_recs)

        # 2. Tóm tắt ngày gần nhất có data
        if not recent_recs:
            summary_recent = f"Không có dữ liệu CEM ({days} ngày gần đây){vpn_note}"
        else:
            summary_recent = CEMClient.extract_top_cells_summary(recent_recs, app_events=app_events)

        combined_str = f"[TIẾP NHẬN]\n{summary_incident}\n\n[GẦN NHẤT]\n{summary_recent}"
        return summary_incident, summary_recent, combined_str

    def get_subscriber_app_events(self, msisdn, days=5, date_str=None, rat="4G - LTE", use_cache=True, incident_time_str=None):
        """
        Lấy thống kê App Usage từ getTopSubEvents trong N ngày gần nhất (mặc định 5 ngày, song song) và ngày sự cố nếu có.
        """
        clean_phone = "".join(filter(str.isdigit, str(msisdn or "").strip()))
        if clean_phone.startswith("84") and len(clean_phone) == 11:
            pass
        elif clean_phone.startswith("0") and len(clean_phone) == 10:
            clean_phone = "84" + clean_phone[1:]
        elif len(clean_phone) == 9:
            clean_phone = "84" + clean_phone
        elif clean_phone.startswith("0"):
            clean_phone = "84" + clean_phone[1:]
        elif not clean_phone.startswith("84"):
            clean_phone = "84" + clean_phone

        cache_key = f"app_{clean_phone}_{days}_{date_str}_{rat}_{incident_time_str or ''}"
        now_ts = time.time()
        if use_cache:
            with _cem_cache_lock:
                cached_entry = _cem_memory_cache.get(cache_key)
                if cached_entry and (now_ts - cached_entry["ts"] < _CEM_CACHE_TTL):
                    return cached_entry["data"]

        today = datetime.now()
        # Nếu truyền cụ thể 1 ngày
        if date_str:
            target_dates = [date_str]
        else:
            recent_dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
            incident_dates = []
            inc_dt = parse_incident_date(incident_time_str)
            if inc_dt:
                incident_dates.append(inc_dt.strftime("%Y-%m-%d"))
            target_dates = sorted(list(set(recent_dates + incident_dates)), reverse=True)

        url = "https://api-cem.vnptmedia.vn/api2/getTopSubEvents"

        def _fetch_day_app(d_str):
            payload = {
                "phone": clean_phone,
                "date": d_str,
                "rat": rat,
                "period": "1 hour",
                "n_top_elements": 24,
                "kpi_type": "application"
            }
            res, err = self._post_with_retry(url, payload, timeout=12)
            day_records = []
            if res and res.status_code == 200:
                try:
                    data = res.json()
                    data_items = data.get("data") or []
                    if isinstance(data_items, list):
                        for hour_item in data_items:
                            if isinstance(hour_item, dict):
                                hour_item["_query_date"] = d_str
                                day_records.append(hour_item)
                except Exception as e:
                    safe_log(f"[CEM] Lỗi parse getTopSubEvents ngày {d_str} cho {clean_phone}: {e}")
            elif err:
                safe_log(f"[CEM] Lỗi kết nối getTopSubEvents ngày {d_str} cho {clean_phone}: {err}")
            return day_records

        all_app_records = []
        with ThreadPoolExecutor(max_workers=min(len(target_dates), 5)) as executor:
            results = list(executor.map(_fetch_day_app, target_dates))
            for day_recs in results:
                all_app_records.extend(day_recs)

        if all_app_records:
            with _cem_cache_lock:
                _cem_memory_cache[cache_key] = {"data": all_app_records, "ts": now_ts}

        return all_app_records

    @staticmethod
    def extract_top_apps_summary(app_data):
        """
        Trích xuất và tổng hợp top ứng dụng sử dụng nhiều nhất từ getTopSubEvents (5 ngày) kèm ngày có data.
        """
        if not app_data:
            return "Không có dữ liệu App Usage (5 ngày)"

        if isinstance(app_data, dict):
            data_list = app_data.get("data", [])
        elif isinstance(app_data, list):
            data_list = app_data
        else:
            return "Không có dữ liệu App Usage (5 ngày)"

        if not data_list:
            return "Không có dữ liệu App Usage (5 ngày)"

        from collections import defaultdict
        app_volumes = defaultdict(float)
        active_dates = set()

        for hour_item in data_list:
            if not isinstance(hour_item, dict):
                continue
            top_list = hour_item.get("top_list", [])
            for item in top_list:
                app_name = str(item.get("up_application") or "unknown").strip().title()
                down = float(item.get("volume_downlink", 0) or 0)
                up = float(item.get("volume_uplink", 0) or 0)
                total_vol = down + up
                if total_vol > 0:
                    app_volumes[app_name] += total_vol
                    q_d = hour_item.get("_query_date") or item.get("date") or hour_item.get("time")
                    if q_d:
                        active_dates.add(str(q_d)[:10])

        if not app_volumes:
            return "Không có dữ liệu App Usage (5 ngày)"

        sorted_apps = sorted(app_volumes.items(), key=lambda x: x[1], reverse=True)[:4]
        lines = []
        compact_date_str = format_active_dates_compact(active_dates)
        if compact_date_str:
            lines.append(f"({compact_date_str}):")

        for app, vol in sorted_apps:
            if vol >= 1024 * 1024:
                vol_str = f"{vol / (1024 * 1024):.1f} MB"
            elif vol >= 1024:
                vol_str = f"{vol / 1024:.1f} KB"
            else:
                vol_str = f"{vol:.0f} B"
            lines.append(f"• {app}: {vol_str}")

        return "\n".join(lines)


def save_cem_data_to_file(phone_84, cell_records, app_events, base_dir=None):
    """
    Lưu toàn bộ dữ liệu CEM (Cell 5 ngày + App Usage 5 ngày) vào thư mục cem/{phone_84}.json
    """
    import json
    from pathlib import Path
    
    clean_phone = "".join(filter(str.isdigit, str(phone_84 or "").strip()))
    if clean_phone.startswith("84") and len(clean_phone) == 11:
        pass
    elif clean_phone.startswith("0") and len(clean_phone) == 10:
        clean_phone = "84" + clean_phone[1:]
    elif len(clean_phone) == 9:
        clean_phone = "84" + clean_phone
    elif clean_phone.startswith("0"):
        clean_phone = "84" + clean_phone[1:]
    elif not clean_phone.startswith("84"):
        clean_phone = "84" + clean_phone

    if base_dir is None:
        target_dir = Path("cem")
    else:
        target_dir = Path(base_dir) / "cem"

    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{clean_phone}.json"

    cell_summary = CEMClient.extract_top_cells_summary(cell_records, app_events=app_events)
    app_summary = CEMClient.extract_top_apps_summary(app_events)

    data_payload = {
        "msisdn": clean_phone,
        "query_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "top_cells_summary": cell_summary,
        "top_apps_summary": app_summary,
        "cell_history_5days": cell_records if cell_records else [],
        "app_usage_5days": app_events if app_events else []
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data_payload, f, ensure_ascii=False, indent=4)
        return str(file_path)
    except Exception as e:
        print(f"⚠️ [CEM] Lỗi khi lưu file {file_path}: {e}")
        return None


# Singleton instance tiện lợi
_default_cem_client = None

def get_cem_cell_summary(msisdn, days=5, driver=None):
    global _default_cem_client
    if _default_cem_client is None:
        _default_cem_client = CEMClient(driver=driver)
    elif driver is not None:
        _default_cem_client.load_cookies_from_chrome(driver=driver)
        
    try:
        records = _default_cem_client.get_subscriber_history_5days(msisdn, days=days)
        return CEMClient.extract_top_cells_summary(records)
    except Exception as e:
        return f"Lỗi truy vấn CEM: {e}"

def get_cem_app_usage_summary(msisdn, days=5, date_str=None, driver=None):
    global _default_cem_client
    if _default_cem_client is None:
        _default_cem_client = CEMClient(driver=driver)
    elif driver is not None:
        _default_cem_client.load_cookies_from_chrome(driver=driver)
        
    try:
        app_data = _default_cem_client.get_subscriber_app_events(msisdn, days=days, date_str=date_str)
        return CEMClient.extract_top_apps_summary(app_data)
    except Exception as e:
        return f"Lỗi truy vấn App Usage: {e}"
