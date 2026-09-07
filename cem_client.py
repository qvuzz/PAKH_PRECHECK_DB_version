import os
import ssl
import time
from collections import Counter
from datetime import datetime, timedelta
import requests
from requests.adapters import HTTPAdapter
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
DEFAULT_API_KEY = "net_ktm_quangvu%seQyfEELlCD19c2CljcOLfolTBsHfwSEUSSDFNVw"
CEM_API_KEY = os.getenv("CEM_API_KEY", DEFAULT_API_KEY)

CEM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://cem.vnptmedia.vn",
    "Referer": "https://cem.vnptmedia.vn/",
}


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


class CEMClient:
    def __init__(self, api_key=None, driver=None):
        self.api_key = api_key or os.getenv("CEM_API_KEY", DEFAULT_API_KEY)
        self.session = requests.Session()
        self.session.mount("https://", LegacySSLAdapter())
        self.load_cookies_from_chrome(driver=driver)

    def load_cookies_from_chrome(self, driver=None):
        """Tự động trích xuất apikey và toàn bộ cookie của CEM từ trình duyệt (Firefox, Chrome, Edge)."""
        try:
            from auth_extractor import get_universal_cem_auth
            extracted_key, cookies_dict = get_universal_cem_auth(driver=driver)

            for name, val in cookies_dict.items():
                self.session.cookies.set(
                    name,
                    val,
                    domain="cem.vnptmedia.vn",
                    path="/"
                )

            if extracted_key:
                self.api_key = extracted_key
                print(f"🔑 [CEM] Đã tự động lấy API Key từ Cookie trình duyệt: {self.api_key[:25]}...")
                return True
        except Exception as e:
            print(f"⚠️ [CEM] Không thể trích xuất cookie tự động: {e}")

        return False

    def get_subscriber_history_5days(self, msisdn, days=5):
        """
        Tra cứu lịch sử bắt sóng Cell từ CEM API trong N ngày gần nhất.
        MSISDN chuẩn hóa bỏ số 0 và mã quốc gia 84 (ví dụ 918161817).
        """
        clean_phone = "".join(filter(str.isdigit, str(msisdn or "").strip()))
        if clean_phone.startswith("84") and len(clean_phone) >= 11:
            clean_phone = clean_phone[2:]
        elif clean_phone.startswith("0") and len(clean_phone) >= 10:
            clean_phone = clean_phone[1:]

        all_records = []
        today = datetime.now()

        for i in range(days):
            date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            payload = {
                "apikey": self.api_key,
                "start_date": date_str,
                "msisdn": clean_phone
            }
            try:
                res = self.session.post(
                    CEM_URL,
                    headers=CEM_HEADERS,
                    json=payload,
                    timeout=15,
                    verify=False
                )
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("data") or data.get("result") or data
                    if isinstance(items, list):
                        for row in items:
                            if isinstance(row, dict):
                                row["_query_date"] = date_str
                                all_records.append(row)
            except Exception as e:
                print(f"⚠️ [CEM] Lỗi tra ngày {date_str} cho {clean_phone}: {e}")
            time.sleep(0.15)

        return all_records

    @staticmethod
    def extract_top_cells_summary(records):
        """
        Trích xuất tên Cell và tính Top 3 Cell bắt sóng nhiều nhất kèm phần trăm (%) và ngày có data.
        """
        if not records or not isinstance(records, list):
            return "Không có dữ liệu CEM (5 ngày)"

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
                or (f"ECI:{r.get('eci')}" if r.get("eci") else None)
            )
            if cell_name:
                cell_identifiers.append(str(cell_name).strip())
                q_date = r.get("_query_date") or r.get("start_date") or r.get("date") or r.get("time")
                if q_date:
                    active_dates.add(str(q_date)[:10])

        if not cell_identifiers:
            return "Không có thông tin Cell"

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

        return "\n".join(lines)

    def get_subscriber_app_events(self, msisdn, days=5, date_str=None, rat="4G - LTE"):
        """
        Lấy thống kê App Usage từ getTopSubEvents trong N ngày gần nhất (mặc định 5 ngày).
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

        all_app_records = []
        today = datetime.now()

        # Nếu truyền cụ thể 1 ngày
        if date_str:
            target_dates = [date_str]
        else:
            target_dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]

        for d_str in target_dates:
            payload = {
                "apikey": self.api_key,
                "phone": clean_phone,
                "date": d_str,
                "rat": rat,
                "period": "1 hour",
                "n_top_elements": 24,
                "kpi_type": "application"
            }
            try:
                url = "https://api-cem.vnptmedia.vn/api2/getTopSubEvents"
                res = self.session.post(url, headers=CEM_HEADERS, json=payload, timeout=15, verify=False)
                if res.status_code == 200:
                    data = res.json()
                    data_items = data.get("data") or []
                    if isinstance(data_items, list):
                        for hour_item in data_items:
                            if isinstance(hour_item, dict):
                                hour_item["_query_date"] = d_str
                                all_app_records.append(hour_item)
            except Exception as e:
                print(f"⚠️ [CEM] Lỗi lấy getTopSubEvents ngày {d_str} cho {clean_phone}: {e}")
            time.sleep(0.1)

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
            if vol >= 1024:
                vol_str = f"{vol/1024:.1f} MB"
            else:
                vol_str = f"{vol:.1f} KB"
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

    cell_summary = CEMClient.extract_top_cells_summary(cell_records)
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
