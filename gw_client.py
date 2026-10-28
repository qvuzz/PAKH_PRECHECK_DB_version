# gw_client.py
# Module tra cứu dữ liệu thuê bao từ hệ thống VNPT-GW (http://10.165.15.29:8080)
# Hỗ trợ quét các tab dịch vụ: SMS, Voice, OCS, Data và bóc tách cấu trúc bảng

import os
import re
import json
import time
from datetime import datetime
from pathlib import Path
import urllib3
import requests

# Hỗ trợ đa dạng parser (ưu tiên lxml có sẵn, fallback BeautifulSoup)
try:
    from lxml import html as lxml_html
except ImportError:
    lxml_html = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Tắt cảnh báo SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = Path(__file__).resolve().parent
GW_CACHE_FILE = BASE_DIR / "gw_auth_cache.json"

GW_HOST = os.environ.get("GW_HOST", "10.165.15.29:8080")
GW_SEARCH_URL = os.environ.get("GW_SEARCH_URL", f"http://{GW_HOST}/VNPT-GW/client/search")
GW_BASE_URL = os.environ.get("GW_BASE_URL", f"http://{GW_HOST}/VNPT-GW")


def load_gw_cache() -> dict:
    """Đọc thông tin phiên GW (JSESSIONID, ViewState) từ cache."""
    if GW_CACHE_FILE.exists():
        try:
            with open(GW_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def clear_gw_cache():
    """Xóa file cache phiên làm việc GW."""
    if GW_CACHE_FILE.exists():
        try:
            GW_CACHE_FILE.unlink()
        except Exception:
            pass


def extract_clean_jsession(raw: str) -> str:
    """Bóc tách chính xác JSESSIONID từ mọi định dạng chuỗi cookie hoặc hex ID."""
    s = str(raw or "").strip()
    if not s:
        return ""
    # 1. Tìm theo regex JSESSIONID=...
    m = re.search(r'JSESSIONID=([^;\s]+)', s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # 2. Nếu chuỗi có chứa dấu ; (header cookie nhiều trường)
    if ";" in s:
        for part in s.split(";"):
            if "jsessionid" in part.lower():
                return part.split("=")[-1].strip()
    # 3. Chuỗi token thuần (chỉ chứa ký tự an toàn alphanumeric và gạch)
    clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '', s)
    return clean


def save_gw_cache(jsessionid: str, view_state: str = "", verify: bool = False) -> tuple:
    """
    Lưu phiên làm việc của GW vào file cache gw_auth_cache.json.
    Trả về: (success: bool, message: str)
    """
    clean_jsession = extract_clean_jsession(jsessionid)

    if not clean_jsession:
        return False, "JSESSIONID không được để trống"

    is_valid = True
    msg = "Đã lưu phiên GW thành công"
    if verify:
        is_valid, msg = verify_gw_session(clean_jsession, view_state)

    data = {
        "jsessionid": clean_jsession,
        "view_state": str(view_state or "").strip(),
        "is_valid": is_valid,
        "updated_at": time.time(),
        "updated_at_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": msg
    }

    try:
        with open(GW_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return is_valid, msg
    except Exception as e:
        return False, f"Lỗi khi lưu cache GW: {e}"


def verify_gw_session(jsessionid: str, view_state: str = "") -> tuple:
    """
    Kiểm tra xem phiên làm việc GW có hợp lệ và truy cập được hay không.
    Trả về: (is_valid: bool, reason_message: str)
    """
    clean_jsession = extract_clean_jsession(jsessionid)
    if not clean_jsession:
        return False, "Chưa có JSESSIONID của GW"

    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": f"JSESSIONID={clean_jsession}"
        })
        session.cookies.set("JSESSIONID", clean_jsession, domain="10.165.15.29", path="/VNPT-GW")
        resp = session.get(GW_SEARCH_URL, timeout=4, verify=False, allow_redirects=False)

        if resp.status_code == 302:
            loc = str(resp.headers.get("Location") or "").lower()
            if "cas/login" in loc or "id.vnpt.com.vn" in loc:
                return False, "Phiên GW đã hết hạn (Bị chuyển về trang đăng nhập CAS)"
            return False, f"Phiên GW bị chuyển hướng đến: {loc[:80]}"
        elif resp.status_code == 200:
            text = resp.text
            final_url = str(resp.url).lower()
            if "cas/login" in final_url or "id.vnpt.com.vn" in final_url:
                return False, "Phiên GW đã hết hạn (Bị chuyển về trang đăng nhập CAS)"
            if any(k in text for k in ["form_main:subs", "pnl_search", "form_main:type", "VNPT-GW", "javax.faces.ViewState"]):
                return True, "Kết nối GW thành công (Phiên hợp lệ)"
            return True, "Kết nối GW thành công"
        elif resp.status_code in (401, 403):
            return False, "Phiên GW hết hạn hoặc không có quyền truy cập (401/403)"
        else:
            return False, f"Máy chủ GW phản hồi mã lỗi HTTP {resp.status_code}"
    except Exception as e:
        return False, f"Không thể kết nối tới máy chủ GW ({GW_HOST}): {e}"


def get_active_gw_session() -> tuple:
    """
    Lấy phiên GW đang hoạt động theo thứ tự:
    1. Cache file gw_auth_cache.json
    2. Trích xuất tự động qua Chrome CDP cổng 9222 (nếu đang mở tab GW)
    3. Trích xuất từ Firefox cookies.sqlite
    Trả về: (jsessionid, view_state)
    """
    # 1. Đọc từ cache
    cached = load_gw_cache()
    c_jsession = cached.get("jsessionid", "")
    c_vs = cached.get("view_state", "")
    if c_jsession:
        return c_jsession, c_vs

    # 2. Quét qua Chrome CDP 9222
    try:
        from auth_extractor import extract_cdp_cookies
        cdp_cookies = extract_cdp_cookies("10.165.15.29")
        if cdp_cookies and "JSESSIONID" in cdp_cookies:
            js = cdp_cookies["JSESSIONID"]
            save_gw_cache(js, verify=False)
            return js, ""
    except Exception:
        pass

    # 3. Quét Firefox cookies
    try:
        from auth_extractor import extract_firefox_cookies
        ff_cookies = extract_firefox_cookies("10.165.15.29")
        if ff_cookies and "JSESSIONID" in ff_cookies:
            js = ff_cookies["JSESSIONID"]
            save_gw_cache(js, verify=False)
            return js, ""
    except Exception:
        pass

    return "", ""


class GWScanner:
    """Class điều phối tra cứu và bóc tách dữ liệu từ hệ thống VNPT-GW (PrimeFaces/JSF)."""

    def __init__(self, jsessionid: str, view_state: str = None):
        self.url = GW_SEARCH_URL
        self.jsessionid = extract_clean_jsession(jsessionid)
        self.session = requests.Session()
        self.session.cookies.set("JSESSIONID", self.jsessionid, domain="10.165.15.29", path="/VNPT-GW")

        self.headers = {
            "Accept": "application/xml, text/xml, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Faces-Request": "partial/ajax",
            "Origin": f"http://{GW_HOST}",
            "Referer": self.url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": f"JSESSIONID={self.jsessionid}"
        }

        self.form_id = "form_main"
        self.subs_input = "form_main:subs"
        self.type_select = "form_main:type"
        self.search_btn_id = "form_main:j_idt40"
        self.render_targets = "form_main:pmessages form_main:pnl_detail form_main:pnl_main"
        self.service_types = []
        self.service_type_map = {}
        self.is_session_expired = False
        self.view_state = view_state
        self.init_page_metadata()

    def init_page_metadata(self):
        """Khởi tạo ViewState ban đầu, tự động nhận diện dynamic form fields và cố định tab SMS trên web."""
        try:
            resp = self.session.get(self.url, timeout=4, verify=False, allow_redirects=False)
            if resp.status_code == 302:
                loc = str(resp.headers.get("Location") or "").lower()
                if "cas/login" in loc or "id.vnpt.com.vn" in loc:
                    self.is_session_expired = True
                    return
                self.is_session_expired = True
                return
            if resp.status_code != 200:
                self.is_session_expired = True
                return

            final_url = str(resp.url).lower()
            text = resp.text

            # Chỉ coi là hết hạn NẾU URL cuối cùng chuyển sang CAS hoặc không có Form/PrimeFaces
            if "id.vnpt.com.vn" in final_url or "cas/login" in final_url:
                self.is_session_expired = True
                return
            if not any(k in text for k in ["form_main", "PrimeFaces", "VNPT-GW", "javax.faces.ViewState"]):
                self.is_session_expired = True
                return

            # 1. Bóc tách ViewState mới nhất từ phản hồi GET
            vs_match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', text) or \
                       re.search(r'value="([^"]+)"[^>]*name="javax\.faces\.ViewState"', text)
            if vs_match:
                self.view_state = vs_match.group(1)

            # 2. Nhận diện Form ID (Ưu tiên form_main)
            form_match = re.search(r'<form\s+[^>]*id="([^"]*form_main[^"]*)"', text) or \
                         re.search(r'<form\s+[^>]*id="([^"]*main[^"]*)"', text) or \
                         re.search(r'<form\s+[^>]*id="([^"]+)"', text)
            if form_match:
                self.form_id = form_match.group(1)
            else:
                self.form_id = "form_main"

            # 3. Nhận diện Input số thuê bao
            sub_match = re.search(r'<input\s+[^>]*name="([^"]*subs[^"]*)"', text, re.I) or \
                        re.search(r'<input\s+[^>]*name="(' + re.escape(self.form_id) + r':[^"]*)"[^>]*type="text"', text, re.I)
            if sub_match:
                self.subs_input = sub_match.group(1)
            else:
                self.subs_input = f"{self.form_id}:subs"

            # 4. Nhận diện Select loại dịch vụ
            type_match = re.search(r'<select\s+[^>]*name="([^"]*type[^"]*)"', text, re.I)
            if type_match:
                self.type_select = type_match.group(1)
            else:
                self.type_select = f"{self.form_id}:type"

            # 5. Nhận diện Button Tra cứu (Tìm kiếm) thực tế
            btn_match = re.search(r'<(?:button|input)\s+[^>]*id="([^"]+)"[^>]*(?:Tra cứu|Tìm kiếm|search|value="Tra cứu")', text, re.I) or \
                        re.search(r'<(?:button|input)\s+[^>]*(?:Tra cứu|Tìm kiếm|search|value="Tra cứu")[^>]*id="([^"]+)"', text, re.I) or \
                        re.search(r'<(?:button|input)\s+[^>]*id="(' + re.escape(self.form_id) + r':j_idt\d+)"', text)
            if btn_match:
                self.search_btn_id = btn_match.group(1)
            else:
                self.search_btn_id = f"{self.form_id}:j_idt40"

            # 6. Nhận diện Render Target
            pnl_match = re.search(r'id="(' + re.escape(self.form_id) + r':pnl_[^"]+)"', text)
            if pnl_match:
                self.render_targets = f"{self.form_id}:pmessages {pnl_match.group(1)} {self.form_id}:pnl_main"
            else:
                self.render_targets = f"{self.form_id}:pmessages {self.form_id}:pnl_detail {self.form_id}:pnl_main"

        except Exception as e:
            print(f"⚠️ [GW INIT ERR] {e}")

        # Khóa cứng chỉ quét DUY NHẤT tab SMS (đã có trọn bộ Profile VoLTE, SMO/SMT 2G/3G & VoLTE)
        self.service_types = ["sms"]
        self.service_type_map = {"sms": "sms", "tin nhắn": "sms"}

    def lookup_single_type(self, msisdn: str, service_type: str) -> dict:
        """Gửi partial ajax request lấy dữ liệu của 1 dịch vụ (sms, voice, data, ocs, roaming)."""
        if self.is_session_expired:
            return {
                "error": "session_expired",
                "messages": ["Phiên làm việc GW (JSESSIONID) đã hết hạn. Vui lòng đăng nhập lại CAS."],
                "tables": []
            }

        # Tìm mã option thực tế trên dropdown/radio
        st_clean = str(service_type or "").strip().lower()
        if st_clean == "volte":
            # Profile VoLTE nằm bên trong tab sms của GW
            st_clean = "sms"

        actual_type = self.service_type_map.get(st_clean)
        if not actual_type:
            # Tìm mờ trong danh sách option
            for opt_val in self.service_types:
                if st_clean in opt_val.lower() or opt_val.lower() in st_clean:
                    actual_type = opt_val
                    break
        if not actual_type:
            actual_type = st_clean

        btn_id = self.search_btn_id or f"{self.form_id}:j_idt40"
        payload = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": btn_id,
            "javax.faces.partial.execute": f"{btn_id} {self.form_id}:pnl_search",
            "javax.faces.partial.render": self.render_targets,
            btn_id: btn_id,
            self.form_id: self.form_id,
            self.subs_input: str(msisdn),
            self.type_select: str(actual_type),
            "javax.faces.ViewState": self.view_state or ""
        }

        try:
            response = self.session.post(self.url, headers=self.headers, data=payload, timeout=28, verify=False)
            if response.status_code != 200:
                return {
                    "error": f"http_{response.status_code}",
                    "messages": [f"Máy chủ GW phản hồi mã lỗi HTTP {response.status_code}"],
                    "tables": []
                }

            # Tự động phục hồi khi gặp ViewExpiredException của JSF
            if "ViewExpiredException" in response.text:
                print("⚠️ [GW] Gặp ViewExpiredException -> Tự động khởi tạo lại ViewState tươi mới và gửi lại...")
                self.init_page_metadata()
                payload["javax.faces.ViewState"] = self.view_state or ""
                payload[btn_id] = btn_id
                response = self.session.post(self.url, headers=self.headers, data=payload, timeout=28, verify=False)

            # Kiểm tra xem có bị chuyển về trang đăng nhập CAS hoặc hết hạn phiên không
            resp_lower = response.text.lower()
            if "<partial-response" not in resp_lower:
                if any(k in resp_lower for k in ["login", "cas", "đăng nhập", "j_security_check", "id.vnpt.com.vn"]):
                    self.is_session_expired = True
                    return {
                        "error": "session_expired",
                        "messages": ["Phiên làm việc GW (JSESSIONID) đã hết hạn. Vui lòng đăng nhập lại CAS."],
                        "tables": []
                    }

            # Cập nhật ViewState xoay vòng từ phản hồi XML
            new_vs = re.search(r'<update id=".*javax\.faces\.ViewState.*"><!\[CDATA\[(.*?)\]\]></update>', response.text)
            if new_vs:
                self.view_state = new_vs.group(1)
                js = self.session.cookies.get("JSESSIONID") or ""
                if js:
                    save_gw_cache(js, self.view_state, verify=False)

            # Lưu log phản hồi thô phục vụ chẩn đoán
            try:
                debug_dir = BASE_DIR / "result" / "gw"
                debug_dir.mkdir(parents=True, exist_ok=True)
                with open(debug_dir / "last_raw_response.txt", "w", encoding="utf-8") as f:
                    f.write(response.text)
            except Exception:
                pass

            return self.parse_all_tables(response.text)
        except Exception as e:
            return {
                "error": str(e),
                "messages": [f"Lỗi khi gửi truy vấn tới GW: {e}"],
                "tables": []
            }

    def _parse_tables_regex(self, full_html: str, result: dict) -> dict:
        """Bộ bóc tách bảng thuần Regex (Zero-Dependency), độc lập hoàn toàn với lxml và bs4."""
        for msg_m in re.finditer(r'class="[^"]*(?:ui-messages|ui-growl)[^"]*"[^>]*>(.*?)</div>', full_html, re.DOTALL):
            txt = re.sub(r'<[^>]+>', ' ', msg_m.group(1)).strip()
            if txt and txt not in result["messages"]:
                result["messages"].append(txt)

        table_matches = list(re.finditer(r'<table\b([^>]*)>(.*?)</table>', full_html, re.DOTALL))
        for idx, tm in enumerate(table_matches):
            attrs, tbody = tm.group(1), tm.group(2)
            pos = tm.start()
            prefix = full_html[:pos]
            title = f"Bảng_{idx+1}"

            cap_m = re.search(r'<caption\b[^>]*>(.*?)</caption>', tbody, re.DOTALL)
            if cap_m:
                c_txt = re.sub(r'<[^>]+>', '', cap_m.group(1)).strip()
                if c_txt:
                    title = c_txt
            else:
                leg_matches = list(re.finditer(r'<(?:legend|span)[^>]*class="[^"]*(?:ui-fieldset-legend|ui-panel-title)[^"]*"[^>]*>(.*?)</(?:legend|span)>', prefix, re.DOTALL))
                if leg_matches:
                    l_txt = re.sub(r'<[^>]+>', '', leg_matches[-1].group(1)).strip()
                    if l_txt:
                        title = l_txt

            rows_data = []
            for tr_m in re.finditer(r'<tr\b[^>]*>(.*?)</tr>', tbody, re.DOTALL):
                tr_content = tr_m.group(1)
                if '<table' in tr_content:
                    continue
                cols = []
                for td_m in re.finditer(r'<(?:td|th)\b[^>]*>(.*?)</(?:td|th)>', tr_content, re.DOTALL):
                    td_content = td_m.group(1)
                    val_matches = re.findall(r'<input[^>]*value="([^"]*)"', td_content)
                    txt = re.sub(r'<script.*?</script>', '', td_content, flags=re.DOTALL)
                    txt = re.sub(r'<[^>]+>', ' ', txt).strip()
                    parts = []
                    if txt:
                        parts.append(txt)
                    for v in val_matches:
                        v = v.strip()
                        if v and v not in txt:
                            parts.append(v)
                    cell_val = " ".join(parts).strip() if parts else txt
                    cell_val = re.sub(r'PrimeFaces(?:Ext)?\.cw\([^;]+\);?\s*', '', cell_val)
                    cell_val = re.sub(r'\$\(function\(\)\s*\{[^}]+\}\);\s*', '', cell_val).strip()
                    cols.append(cell_val)
                if any(cols):
                    rows_data.append(cols)

            if rows_data:
                result["tables"].append({
                    "table_name": title,
                    "rows": rows_data
                })
        return result

    def parse_all_tables(self, xml_text: str) -> dict:
        """Bóc tách toàn bộ thông báo và các bảng dữ liệu trong CDATA của XML trả về."""
        cdata_blocks = re.findall(r'<!\[CDATA\[(.*?)\]\]>', xml_text, re.DOTALL)
        full_html = "\n".join(cdata_blocks)

        result = {
            "messages": [],
            "tables": []
        }

        if not full_html.strip():
            return result

        # TẦNG 1: Ưu tiên bộ parser siêu tốc lxml (nếu có sẵn)
        if lxml_html is not None:
            try:
                doc = lxml_html.fromstring(full_html)
                for el in doc.xpath('//*[contains(@class, "ui-messages") or contains(@class, "ui-growl")]'):
                    txt = el.text_content().strip()
                    if txt:
                        result["messages"].append(txt)

                for idx, table in enumerate(doc.xpath('//table')):
                    caption = table.xpath('.//caption')
                    title = f"Bảng_{idx+1}"
                    if caption and caption[0].text_content().strip():
                        title = caption[0].text_content().strip()
                    else:
                        header = table.xpath('preceding::*[contains(@class, "ui-panel-title") or contains(@class, "ui-fieldset-legend")][1]')
                        if header and header[0].text_content().strip():
                            title = header[0].text_content().strip()

                    rows_data = []
                    for row in table.xpath('.//tr'):
                        if row.xpath('.//table'):
                            continue
                        cols = []
                        for c in row.xpath('.//td | .//th'):
                            txt = c.text_content().strip()
                            inp_vals = []
                            for inp in c.xpath('.//input | .//textarea'):
                                v = str(inp.get('value') or '').strip()
                                if v and v not in txt:
                                    inp_vals.append(v)
                            cell_val = f"{txt} {' '.join(inp_vals)}".strip() if inp_vals else txt
                            cell_val = re.sub(r'PrimeFaces(?:Ext)?\.cw\([^;]+\);?\s*', '', cell_val)
                            cell_val = re.sub(r'\$\(function\(\)\s*\{[^}]+\}\);\s*', '', cell_val).strip()
                            cols.append(cell_val)

                        if any(cols):
                            rows_data.append(cols)

                    if rows_data:
                        result["tables"].append({
                            "table_name": title,
                            "rows": rows_data
                        })
                if result["tables"]:
                    return result
            except Exception as e:
                result["messages"].append(f"Lỗi parse lxml: {e}")

        # TẦNG 2: Dự phòng BeautifulSoup (nếu lxml vắng mặt hoặc không bóc tách được bảng)
        if BeautifulSoup is not None and not result["tables"]:
            try:
                soup = BeautifulSoup(full_html, "html.parser")
                for msg in soup.find_all(class_=re.compile(r"ui-messages|ui-growl")):
                    text = msg.get_text(strip=True)
                    if text and text not in result["messages"]:
                        result["messages"].append(text)

                for idx, table in enumerate(soup.find_all("table")):
                    caption = table.find("caption")
                    title = f"Bảng_{idx+1}"
                    parent_panel = table.find_parent(class_=re.compile(r"ui-panel|ui-fieldset|panel"))
                    if caption:
                        title = caption.get_text(strip=True)
                    elif parent_panel:
                        header = parent_panel.find(class_=re.compile(r"ui-panel-title|ui-fieldset-legend|panel-heading"))
                        if header:
                            title = header.get_text(strip=True)

                    rows_data = []
                    for row in table.find_all("tr"):
                        if row.find("table"):
                            continue
                        cols = []
                        for col in row.find_all(["td", "th"]):
                            txt = col.get_text(" ", strip=True)
                            inp_vals = []
                            for inp in col.find_all(["input", "textarea"]):
                                v = str(inp.get("value") or "").strip()
                                if v and v not in txt:
                                    inp_vals.append(v)
                            cell_val = f"{txt} {' '.join(inp_vals)}".strip() if inp_vals else txt
                            cols.append(cell_val)

                        if any(cols):
                            rows_data.append(cols)

                    if rows_data:
                        result["tables"].append({
                            "table_name": title,
                            "rows": rows_data
                        })
                if result["tables"]:
                    return result
            except Exception as e:
                result["messages"].append(f"Lỗi parse bs4: {e}")

        # TẦNG 3: BỘ BÓC TÁCH REGEX NỘI TẠI (Zero-Dependency Fallback)
        # Hoạt động 100% độc lập, không cần bất kỳ thư viện ngoài nào (kể cả khi Docker không có lxml/bs4)
        if not result["tables"]:
            return self._parse_tables_regex(full_html, result)

        return result


    def lookup_all_services(self, msisdn: str, custom_types: list = None) -> dict:
        """Quét duy nhất tab SMS cho 1 thuê bao (chứa toàn bộ VoLTE Profile, SMO/SMT 2G/3G & VoLTE)."""
        types_to_run = ["sms"]
        all_results = {}

        for s_type in types_to_run:
            all_results[s_type] = self.lookup_single_type(msisdn, s_type)

        return all_results


def lookup_subscriber_gw(msisdn: str, custom_types: list = None, save_json: bool = True, output_dir: str = "result/gw") -> dict:
    """
    Hàm giao tiếp chính: Tra cứu toàn bộ thông tin thuê bao từ hệ thống GW.
    - Đầu vào: Số điện thoại (msisdn)
    - Đầu ra: Dictionary chứa kết quả và tự động ghi file JSON ra thư mục output_dir.
    """
    raw_phone = str(msisdn or "").strip().replace(" ", "").replace("+", "").replace("-", "")
    if not raw_phone:
        return {"success": False, "message": "Số điện thoại không hợp lệ"}

    clean_digits = "".join(filter(str.isdigit, raw_phone))
    if len(clean_digits) == 9:
        primary_phone = f"84{clean_digits}"
    elif clean_digits.startswith("84") and len(clean_digits) >= 11:
        primary_phone = clean_digits
    elif clean_digits.startswith("0") and len(clean_digits) >= 10:
        primary_phone = f"84{clean_digits[1:]}"
    else:
        primary_phone = f"84{clean_digits}" if not clean_digits.startswith("84") else clean_digits

    # Cổng GW chỉ chấp nhận chuẩn quốc tế 84xxxxxxxxx
    # Mặc định ưu tiên quét tab 'sms' (chứa toàn bộ IMSI, VoLTE Profile, SMO/SMT 2G/3G & VoLTE)
    types_to_query = custom_types or ["sms"]

    jsessionid, view_state = get_active_gw_session()
    if not jsessionid:
        return {
            "success": False,
            "connected": False,
            "message": "Chưa có phiên làm việc GW (JSESSIONID). Vui lòng đồng bộ hoặc cấu hình JSESSIONID.",
            "msisdn": primary_phone
        }

    try:
        scanner = GWScanner(jsessionid=jsessionid, view_state=view_state)
        if scanner.is_session_expired:
            return {
                "success": False,
                "connected": False,
                "message": "Phiên làm việc GW đã hết hạn hoặc chưa đăng nhập CAS. Vui lòng đăng nhập lại VNPT-GW.",
                "msisdn": primary_phone
            }

        # Tra cứu chuẩn xác với đầu số 84xxxxxxxxx
        data = scanner.lookup_all_services(primary_phone, custom_types=types_to_query)
        if scanner.is_session_expired or any(isinstance(s, dict) and s.get("error") == "session_expired" for s in data.values()):
            return {
                "success": False,
                "connected": False,
                "message": "Phiên làm việc GW đã hết hạn hoặc chưa đăng nhập CAS. Vui lòng đăng nhập lại VNPT-GW.",
                "msisdn": primary_phone,
                "data": data
            }

        total_tables = sum(len(s.get("tables", [])) for s in data.values() if isinstance(s, dict))
        successful_phone = primary_phone if total_tables > 0 else ""

        # Fallback thử nghiệm với số dạng 0... nếu dạng 84... không có bảng
        if total_tables == 0 and len(clean_digits) >= 9:
            fallback_phone = f"0{clean_digits[2:]}" if clean_digits.startswith("84") else (f"0{clean_digits}" if not clean_digits.startswith("0") else clean_digits)
            data_fb = scanner.lookup_all_services(fallback_phone, custom_types=types_to_query)
            tb_fb = sum(len(s.get("tables", [])) for s in data_fb.values() if isinstance(s, dict))
            if tb_fb > 0:
                data = data_fb
                total_tables = tb_fb
                successful_phone = fallback_phone

        if total_tables == 0:
            err_msgs = []
            for s in data.values():
                if isinstance(s, dict) and s.get("messages"):
                    err_msgs.extend(s.get("messages"))
            msg_text = "; ".join(err_msgs) if err_msgs else f"Không có dữ liệu bảng hồ sơ thuê bao từ cổng GW (10.165.15.29) cho số {primary_phone}."
            return {
                "success": False,
                "connected": True,
                "message": msg_text,
                "msisdn": primary_phone,
                "data": data
            }

        saved_path = ""
        if save_json:
            out_folder = BASE_DIR / output_dir
            out_folder.mkdir(parents=True, exist_ok=True)
            saved_file = out_folder / f"{primary_phone}_gw.json"
            payload = {
                "success": True,
                "phone": primary_phone,
                "msisdn": successful_phone,
                "queried_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data": data
            }
            with open(saved_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            saved_path = str(saved_file)

        return {
            "success": True,
            "phone": primary_phone,
            "msisdn": successful_phone,
            "queried_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "saved_file": saved_path,
            "data": data
        }
    except Exception as e:
        return {
            "success": False,
            "msisdn": primary_phone,
            "message": f"Lỗi khi tra cứu GW: {e}"
        }


def run_gw_diagnostic(msisdn: str = "0845061315", verbose: bool = False) -> dict:
    """
    Công cụ chẩn đoán chuyên sâu (Deep Diagnostic) toàn diện cho kết nối VNPT-GW (10.165.15.29:8080):
    1. Kiểm tra cấu hình Proxy môi trường.
    2. Thử nghiệm kết nối Socket TCP tới 10.165.15.29:8080.
    3. Đọc và kiểm tra tính hợp lệ của Cache JSESSIONID.
    4. Thực hiện HTTP GET Initial Handshake (bóc tách ViewState, kiểm tra CAS Redirect).
    5. Thực hiện HTTP POST Ajax tra cứu thử nghiệm thuê bao.
    6. Đưa ra kết luận và khuyến nghị kỹ thuật cụ thể.
    """
    import socket
    diag_logs = []
    def log_diag(level: str, msg: str):
        diag_logs.append(f"[{level}] {msg}")
        if verbose:
            print(f"[{level}] {msg}")

    log_diag("INFO", f"=== BẮT ĐẦU CHẨN ĐOÁN HỆ THỐNG VNPT-GW (HOST: {GW_HOST}) ===")
    diag_report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_host": GW_HOST,
        "test_msisdn": msisdn,
        "steps": {},
        "conclusion": "UNKNOWN",
        "recommendations": []
    }

    # BƯỚC 1: KIỂM TRA PROXY MÔI TRƯỜNG
    proxy_env = {
        k: os.environ.get(k) for k in [
            "http_proxy", "https_proxy", "no_proxy", 
            "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"
        ] if os.environ.get(k)
    }
    has_active_proxy = bool(proxy_env.get("http_proxy") or proxy_env.get("HTTP_PROXY") or proxy_env.get("all_proxy") or proxy_env.get("ALL_PROXY"))
    no_proxy_val = str(proxy_env.get("no_proxy") or proxy_env.get("NO_PROXY") or "")
    proxy_bypassed = ("10.165.15.29" in no_proxy_val) or ("10.165." in no_proxy_val) or ("10." in no_proxy_val)

    step1_ok = True
    if has_active_proxy and not proxy_bypassed:
        step1_ok = False
        log_diag("WARN", f"Phát hiện biến môi trường PROXY ({proxy_env}) nhưng 10.165.15.29 KHÔNG nằm trong NO_PROXY! Gói tin có thể bị chuyển hướng ra ngoài gây treo.")
        diag_report["recommendations"].append("Cần bổ sung '10.165.15.29,10.0.0.0/8' vào biến môi trường NO_PROXY trong container Docker.")
    else:
        log_diag("PASS", f"Cấu hình Proxy môi trường bình thường. (Active Proxy: {has_active_proxy})")

    diag_report["steps"]["1_network_proxy"] = {
        "passed": step1_ok,
        "proxy_env": proxy_env,
        "bypassed": proxy_bypassed
    }

    # BƯỚC 2: KIỂM TRA KẾT NỐI SOCKET TCP LỚP 4
    step2_ok = False
    tcp_latency_ms = None
    try:
        t0 = time.time()
        host_ip = GW_HOST.split(":")[0]
        host_port = int(GW_HOST.split(":")[1]) if ":" in GW_HOST else 8080
        s = socket.create_connection((host_ip, host_port), timeout=4.0)
        tcp_latency_ms = round((time.time() - t0) * 1000, 2)
        s.close()
        step2_ok = True
        log_diag("PASS", f"Mở kết nối TCP tới {host_ip}:{host_port} THÀNH CÔNG (Độ trễ: {tcp_latency_ms} ms)")
    except socket.timeout:
        log_diag("FAIL", f"Kết nối TCP tới {GW_HOST} bị TIMEOUT (quá 4s). Máy chủ không phản hồi!")
        diag_report["recommendations"].append("Kiểm tra lại dải IP/Route mạng từ container Docker tới 10.165.15.29 (ping/traceroute).")
    except Exception as ex_sock:
        log_diag("FAIL", f"Kết nối TCP tới {GW_HOST} THẤT BẠI: {ex_sock}")
        diag_report["recommendations"].append(f"Lỗi mạng lớp 4: {ex_sock}. Đảm bảo container Docker nằm cùng mạng nội bộ kết nối được GW.")

    diag_report["steps"]["2_tcp_socket"] = {
        "passed": step2_ok,
        "latency_ms": tcp_latency_ms
    }

    # BƯỚC 3: KIỂM TRA FILE CACHE VÀ JSESSIONID
    cached = load_gw_cache()
    cached_jsession = cached.get("jsessionid", "")
    cached_vs = cached.get("view_state", "")
    up_time_str = cached.get("updated_at_str", "Chưa xác định")

    step3_ok = bool(cached_jsession)
    if step3_ok:
        log_diag("PASS", f"Tìm thấy JSESSIONID trong cache: {cached_jsession[:8]}... (Cập nhật lúc: {up_time_str})")
    else:
        log_diag("WARN", "Chưa có file cache hoặc JSESSIONID trong gw_auth_cache.json bị rỗng!")
        diag_report["recommendations"].append("Cần copy JSESSIONID từ trình duyệt vào giao diện Cài đặt / Đồng bộ GW.")

    diag_report["steps"]["3_auth_cache"] = {
        "passed": step3_ok,
        "has_jsession": bool(cached_jsession),
        "updated_at": up_time_str
    }

    # BƯỚC 4: HTTP GET INITIAL HANDSHAKE
    step4_ok = False
    get_status = None
    get_final_url = ""
    view_state_found = ""
    form_id_found = ""
    cas_redirect = False

    test_session = requests.Session()
    # Tắt proxy nếu phát hiện nội bộ
    test_session.trust_env = False
    if cached_jsession:
        test_session.cookies.set("JSESSIONID", cached_jsession, domain="10.165.15.29", path="/VNPT-GW")

    try:
        t0 = time.time()
        resp_get = test_session.get(GW_SEARCH_URL, timeout=8.0, verify=False, allow_redirects=True)
        get_latency_ms = round((time.time() - t0) * 1000, 2)
        get_status = resp_get.status_code
        get_final_url = str(resp_get.url)

        if "cas/login" in get_final_url.lower() or "id.vnpt.com.vn" in get_final_url.lower():
            cas_redirect = True
            log_diag("FAIL", f"HTTP GET trả về {get_status} nhưng bị chuyển hướng sang CAS ({get_final_url}). JSESSIONID đã hết hạn!")
            diag_report["recommendations"].append("JSESSIONID của GW đã hết hạn. Hãy đăng nhập lại CAS trên trình duyệt và cập nhật JSESSIONID mới.")
        elif get_status == 200:
            vs_m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', resp_get.text) or \
                   re.search(r'value="([^"]+)"[^>]*name="javax\.faces\.ViewState"', resp_get.text)
            if vs_m:
                view_state_found = vs_m.group(1)
            f_m = re.search(r'<form\s+[^>]*id="([^"]*form_main[^"]*)"', resp_get.text) or \
                  re.search(r'<form\s+[^>]*id="([^"]+)"', resp_get.text)
            if f_m:
                form_id_found = f_m.group(1)

            step4_ok = bool(view_state_found)
            log_diag("PASS", f"HTTP GET thành công ({get_status}, {get_latency_ms} ms). Bóc tách được ViewState: {view_state_found[:12]}..., Form ID: {form_id_found}")
        else:
            log_diag("FAIL", f"HTTP GET phản hồi mã lỗi {get_status} ({get_latency_ms} ms)")
    except Exception as ex_get:
        log_diag("FAIL", f"HTTP GET ban đầu thất bại: {ex_get}")
        diag_report["recommendations"].append(f"Không thể gửi HTTP GET tới GW: {ex_get}")

    diag_report["steps"]["4_http_handshake"] = {
        "passed": step4_ok,
        "status_code": get_status,
        "final_url": get_final_url,
        "cas_redirect": cas_redirect,
        "view_state_found": bool(view_state_found),
        "form_id": form_id_found
    }

    # BƯỚC 5: HTTP POST AJAX SEARCH THỬ NGHIỆM
    step5_ok = False
    post_status = None
    post_elapsed = None
    tables_count = 0
    tables_names = []
    view_expired = False
    snippet_resp = ""

    if step4_ok and cached_jsession:
        try:
            scanner = GWScanner(jsessionid=cached_jsession, view_state=view_state_found or cached_vs)
            btn_id = scanner.search_btn_id or f"{scanner.form_id}:j_idt40"
            payload = {
                "javax.faces.partial.ajax": "true",
                "javax.faces.source": btn_id,
                "javax.faces.partial.execute": f"{btn_id} {scanner.form_id}:pnl_search",
                "javax.faces.partial.render": scanner.render_targets,
                btn_id: btn_id,
                scanner.form_id: scanner.form_id,
                scanner.subs_input: str(msisdn),
                scanner.type_select: "sms",
                "javax.faces.ViewState": view_state_found or cached_vs or ""
            }

            t0 = time.time()
            post_resp = scanner.session.post(scanner.url, headers=scanner.headers, data=payload, timeout=25.0, verify=False)
            post_elapsed = round(time.time() - t0, 2)
            post_status = post_resp.status_code

            if "ViewExpiredException" in post_resp.text:
                view_expired = True
                log_diag("WARN", f"HTTP POST gặp ViewExpiredException ({post_elapsed}s). Hệ thống đã tự động thử nghiệm khởi tạo lại ViewState.")

            parsed = scanner.parse_all_tables(post_resp.text)
            tables = parsed.get("tables", [])
            tables_count = len(tables)
            tables_names = [t.get("table_name", "") for t in tables]

            snippet_resp = post_resp.text[:400].replace("\n", " ").strip()
            if tables_count > 0:
                step5_ok = True
                log_diag("PASS", f"HTTP POST tra cứu số {msisdn} THÀNH CÔNG ({post_status}, {post_elapsed}s). Bóc tách được {tables_count} bảng: {', '.join(tables_names)}")
            else:
                log_diag("WARN", f"HTTP POST thành công ({post_status}, {post_elapsed}s) nhưng không tìm thấy bảng dữ liệu nào cho số {msisdn}. Thông điệp: {parsed.get('messages')}")
        except Exception as ex_post:
            log_diag("FAIL", f"HTTP POST tra cứu thất bại: {ex_post}")
            diag_report["recommendations"].append(f"Lỗi truy vấn POST: {ex_post}")

    diag_report["steps"]["5_ajax_search_test"] = {
        "passed": step5_ok,
        "status_code": post_status,
        "elapsed_seconds": post_elapsed,
        "tables_count": tables_count,
        "tables": tables_names,
        "view_expired": view_expired,
        "raw_snippet": snippet_resp[:300] if snippet_resp else ""
    }

    # TỔNG KẾT KẾT LUẬN
    if step5_ok:
        diag_report["conclusion"] = "HOÀN TOÀN BÌNH THƯỜNG"
        log_diag("SUCCESS", "=> KẾT LUẬN: Kết nối VNPT-GW từ môi trường hiện tại hoạt động hoàn hảo!")
    elif not step2_ok:
        diag_report["conclusion"] = "LỖI MẠNG LỚP 4 (TCP TIMEOUT / REFUSED)"
        log_diag("FAIL", "=> KẾT LUẬN: Mạng không thông tới máy chủ 10.165.15.29:8080.")
    elif cas_redirect or not step3_ok:
        diag_report["conclusion"] = "LỖI PHIÊN ĐĂNG NHẬP (JSESSIONID HẾT HẠN HOẶC THIẾU)"
        log_diag("FAIL", "=> KẾT LUẬN: Cần cập nhật lại JSESSIONID mới từ trình duyệt.")
    elif view_expired:
        diag_report["conclusion"] = "LỖI VIEWSTATE CỦA PRIMEFACES"
        log_diag("WARN", "=> KẾT LUẬN: Phiên làm việc trên cổng GW bị lệch ViewState.")
    else:
        diag_report["conclusion"] = "KHÔNG CÓ DỮ LIỆU BẢNG HOẶC TRUY VẤN LỖI"
        log_diag("WARN", "=> KẾT LUẬN: Kết nối được nhưng cổng GW không trả về bảng dữ liệu thuê bao.")

    diag_report["logs"] = diag_logs
    return diag_report


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    args = sys.argv[1:]
    is_diag = any(a in ("--diagnose", "-d", "diag") for a in args)
    test_num = "0845061315"
    for a in args:
        if not a.startswith("-") and a.isdigit():
            test_num = a
            break

    if is_diag:
        print("\n=======================================================")
        print(f"[DIAGNOSTIC] KIEM TRA CHAN DOAN CHUYEN SAU VNPT-GW: {test_num}")
        print("=======================================================\n")
        res = run_gw_diagnostic(msisdn=test_num, verbose=True)
        print("\n--- BAO CAO TONG HOP JSON ---")
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"=== TEST TRA CUU GW CHO SO: {test_num} ===")
        res = lookup_subscriber_gw(test_num)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        print("\nGoi y: Chay lenh sau de kiem tra chan doan toan dien:")
        print(f"   python gw_client.py {test_num} --diagnose\n")
