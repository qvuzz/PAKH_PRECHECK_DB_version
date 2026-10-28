# sapccheck/ims_client.py
# Module tra cứu hồ sơ thuê bao IMS / VoLTE Profile từ hệ thống Core (http://10.155.42.218/api/getIMS)
# Hỗ trợ bóc tách trạng thái đăng ký IMS (REGISTERED), chặn cước (Barring Ind), S-CSCF, SIP/TEL URI

import os
import sys
import json
import re
import argparse
from pathlib import Path
import urllib3
import requests

if hasattr(sys.stdout, "reconfigure") and sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure") and sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
COOKIE_FILES = [
    BASE_DIR / "sapc_cookies.json",
    BASE_DIR / "cookies.json"
]

IMS_HOST = os.environ.get("IMS_HOST", "10.155.42.218")
IMS_API_URL = os.environ.get("IMS_API_URL", f"http://{IMS_HOST}/api/getIMS")
IMS_REFERER = f"http://{IMS_HOST}/imsFull"
CDP_URL = os.environ.get("CDP_URL", "http://127.0.0.1:9222")


def normalize_phone(phone: str) -> str:
    """Chuẩn hóa số điện thoại về định dạng 84xxxxxxxxx."""
    s = re.sub(r"[^\d]", "", str(phone or "")).strip()
    if s.startswith("0"):
        s = "84" + s[1:]
    elif s.startswith("84"):
        pass
    elif len(s) == 9:
        s = "84" + s
    return s


class IMSClient:
    """Client giao tiếp với API Core IMS (http://10.155.42.218/api/getIMS)."""

    def __init__(self, cdp_url: str = CDP_URL, driver=None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/155.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Referer": IMS_REFERER,
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive"
        })
        self.loaded_source = "None"

        if driver is not None:
            self._load_from_driver(driver)

        if not self._is_cookie_loaded():
            self._load_cookies(cdp_url)

    def _is_cookie_loaded(self) -> bool:
        return any("ApplicationCookie" in getattr(c, "name", "") for c in self.session.cookies)

    def _load_from_driver(self, driver):
        try:
            cookies = driver.execute_cdp_cmd("Network.getAllCookies", {}).get("cookies", [])
            for c in cookies:
                if "10.155" in str(c.get("domain", "")):
                    self.session.cookies.set(c["name"], c["value"], domain=c.get("domain", IMS_HOST), path=c.get("path", "/"))
            self.loaded_source = "Selenium CDP"
        except Exception:
            try:
                for c in driver.get_cookies():
                    self.session.cookies.set(c["name"], c["value"], domain=c.get("domain", IMS_HOST), path=c.get("path", "/"))
                self.loaded_source = "Selenium get_cookies"
            except Exception:
                pass

    def _load_cookies(self, cdp_url: str):
        # 1. Đọc từ file JSON (ưu tiên sapc_cookies.json hoặc cookies.json)
        for cf in COOKIE_FILES:
            if cf.exists():
                try:
                    with open(cf, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for c in data:
                            self.session.cookies.set(
                                c.get("name", ""),
                                c.get("value", ""),
                                domain=c.get("domain", IMS_HOST),
                                path=c.get("path", "/")
                            )
                    elif isinstance(data, dict):
                        for k, v in data.items():
                            self.session.cookies.set(k, v, domain=IMS_HOST, path="/")
                    if self._is_cookie_loaded():
                        self.loaded_source = f"File: {cf.name}"
                        return
                except Exception:
                    pass

        # 2. Thử Chrome CDP nếu mở cổng 9222
        for u in [cdp_url, cdp_url.replace("127.0.0.1", "localhost")]:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.connect_over_cdp(u)
                    context = browser.contexts[0]
                    cookies = context.cookies()
                    matched = False
                    for c in cookies:
                        if "10.155" in str(c.get("domain", "")):
                            self.session.cookies.set(c["name"], c["value"], domain=c.get("domain", IMS_HOST), path=c.get("path", "/"))
                            matched = True
                    browser.close()
                    if matched and self._is_cookie_loaded():
                        self.loaded_source = f"Chrome CDP ({u})"
                        return
            except Exception:
                pass

        # 3. Thử browser_cookie3
        try:
            import browser_cookie3
            for loader in (browser_cookie3.chrome, browser_cookie3.edge):
                try:
                    cj = loader(domain_name=IMS_HOST)
                    for c in cj:
                        self.session.cookies.set(c.name, c.value, domain=IMS_HOST, path="/")
                    if self._is_cookie_loaded():
                        self.loaded_source = f"browser_cookie3 ({loader.__name__})"
                        return
                except Exception:
                    continue
        except Exception:
            pass

    def update_cookies_manual(self, app_cookie: str, verification_token: str = ""):
        """Cập nhật cookie thủ công và lưu vào file cache."""
        cookie_list = [
            {
                "name": ".AspNet.ApplicationCookie",
                "value": app_cookie.strip(),
                "domain": IMS_HOST,
                "path": "/"
            }
        ]
        if verification_token:
            cookie_list.append({
                "name": "__RequestVerificationToken",
                "value": verification_token.strip(),
                "domain": IMS_HOST,
                "path": "/"
            })
        for c in cookie_list:
            self.session.cookies.set(c["name"], c["value"], domain=c["domain"], path=c["path"])

        for cf in COOKIE_FILES:
            try:
                with open(cf, "w", encoding="utf-8") as f:
                    json.dump(cookie_list, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        self.loaded_source = "Manual input"

    def query_raw(self, msisdn: str) -> dict:
        """Gửi HTTP GET truy vấn hồ sơ IMS thuê bao."""
        std_msisdn = normalize_phone(msisdn)
        url = f"{IMS_API_URL}/{std_msisdn}"

        try:
            resp = self.session.get(url, timeout=20.0, verify=False)
        except Exception as e:
            raise ConnectionError(f"Không thể kết nối tới máy chủ Core IMS ({url}): {e}")

        if resp.status_code in (401, 403) or "login" in resp.url.lower():
            raise PermissionError(
                f"Phiên đăng nhập Core IMS ({IMS_HOST}) đã hết hạn hoặc chưa đăng nhập. "
                "Vui lòng cập nhật .AspNet.ApplicationCookie mới."
            )

        content_type = resp.headers.get("Content-Type", "").lower()
        if "json" not in content_type and "text/plain" not in content_type:
            if "<html" in resp.text.lower():
                raise PermissionError(
                    f"Máy chủ Core IMS trả về trang đăng nhập HTML thay vì JSON. "
                    "Vui lòng đăng nhập lại vào http://10.155.42.218."
                )

        try:
            return resp.json()
        except Exception as e:
            raise ValueError(f"Dữ liệu trả về từ Core IMS không phải JSON hợp lệ: {e}. Raw: {resp.text[:200]}")

    def parse_ims_data(self, raw_data: dict, msisdn: str) -> dict:
        """Bóc tách dữ liệu Core IMS thành cấu trúc thông tin chuẩn."""
        std_msisdn = normalize_phone(msisdn)
        error_code = str(raw_data.get("error_code", ""))
        ims_sub = raw_data.get("imsSub") or {}

        if not ims_sub:
            return {
                "success": False,
                "msisdn": std_msisdn,
                "error_code": error_code,
                "message": "Không tìm thấy hồ sơ IMS thuê bao trên Core HSS/IMS.",
                "is_registered": False,
                "registration_state": "NOT_FOUND"
            }

        # 1. Thông tin cơ bản
        is_psi = str(ims_sub.get("isPsi", "false")).lower() == "true"
        charging_prof_id = str(ims_sub.get("chargingProfId") or "")
        orig_scscf = str(ims_sub.get("originatingCallsSCSCF") or "")
        dia_serv_id = str(ims_sub.get("diaServId") or "")

        # 2. Private User (IMSI, Chặn cước, SIP Failed)
        private_users = ims_sub.get("privateUser") or []
        user_imsi = ""
        user_barring = False
        roaming_allowed = True
        failed_sip_auth = 0

        if private_users and isinstance(private_users, list):
            pu0 = private_users[0]
            user_imsi = str(pu0.get("userImsi") or "")
            user_barring = str(pu0.get("userBarringInd", "false")).lower() == "true"
            roaming_allowed = str(pu0.get("roamingAllowed", "true")).lower() == "true"
            try:
                failed_sip_auth = int(pu0.get("numOfFailedSipAuthAttempts", 0))
            except Exception:
                failed_sip_auth = 0

        # 3. Configured Service Profile (danh sách dịch vụ: sccas, SMS, USSI...)
        configured_services = []
        sub_serv_profiles = ims_sub.get("subscriberServiceProfile") or []
        for ssp in sub_serv_profiles:
            for csp in (ssp.get("configuredServiceProfile") or []):
                s_id = str(csp.get("configuredServiceProfileId") or "").strip()
                if s_id and s_id not in configured_services:
                    configured_services.append(s_id)

        # 4. Public Data (Đăng ký IMS / VoLTE, SIP URI, Session Barring)
        public_data = ims_sub.get("publicData") or []
        sip_uris = []
        tel_uris = []
        is_registered = False
        reg_states = []
        session_barring_flags = []

        for pd in public_data:
            val = str(pd.get("publicIdValue") or "")
            if val.startswith("sip:"):
                sip_uris.append(val)
            elif val.startswith("tel:"):
                tel_uris.append(val)

            s_bar = str(pd.get("sessionBarringInd", "false")).lower() == "true"
            session_barring_flags.append(s_bar)

            for pus in (pd.get("privateUserIdState") or []):
                st = str(pus.get("state") or "").strip().upper()
                if st:
                    reg_states.append(st)
                    if st == "REGISTERED":
                        is_registered = True

        registration_state = "REGISTERED" if is_registered else (reg_states[0] if reg_states else "NOT_REGISTERED")

        # 5. Đánh giá tóm tắt kỹ thuật
        summary_lines = []
        if is_registered:
            summary_lines.append("Thuê bao ĐÃ ĐĂNG KÝ VoLTE/IMS thành công (State: REGISTERED).")
        else:
            summary_lines.append(f"Thuê bao CHƯA ĐĂNG KÝ VoLTE/IMS (State: {registration_state}).")

        if user_barring:
            summary_lines.append("CẢNH BÁO: Thuê bao bị gắn cờ CHẶN IMS (userBarringInd = TRUE).")
        else:
            summary_lines.append("Trạng thái chặn IMS: Bình thường (userBarringInd = FALSE).")

        if configured_services:
            summary_lines.append(f"Dịch vụ kích hoạt trên IMS: {', '.join(configured_services)}.")

        if orig_scscf:
            summary_lines.append(f"Server S-CSCF phục vụ: {orig_scscf}.")

        return {
            "success": True,
            "msisdn": std_msisdn,
            "error_code": error_code,
            "imsi": user_imsi,
            "is_registered": is_registered,
            "registration_state": registration_state,
            "user_barring": user_barring,
            "session_barring": any(session_barring_flags),
            "roaming_allowed": roaming_allowed,
            "failed_sip_auth_attempts": failed_sip_auth,
            "scscf_server": orig_scscf,
            "dia_server_id": dia_serv_id,
            "charging_profile": charging_prof_id,
            "configured_services": configured_services,
            "sip_uris": sip_uris,
            "tel_uris": tel_uris,
            "summary_text": " ".join(summary_lines),
            "raw_ims_sub": ims_sub
        }


def get_ims_profile(msisdn: str, save_to_file: bool = True) -> dict:
    """Hàm giao tiếp cấp cao: Truy vấn và trả về thông tin hồ sơ IMS của số thuê bao."""
    client = IMSClient()
    std_msisdn = normalize_phone(msisdn)
    raw_data = client.query_raw(std_msisdn)
    parsed = client.parse_ims_data(raw_data, std_msisdn)

    if save_to_file and parsed.get("success"):
        out_dir = ROOT_DIR / "result" / "ims"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{std_msisdn}_ims.json"
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(parsed, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return parsed


def main():
    parser = argparse.ArgumentParser(description="Tra cứu thông tin Core IMS / VoLTE Profile của số thuê bao VNPT")
    parser.add_argument("msisdn", nargs="?", help="Số điện thoại cần tra cứu (VD: 84845061315)")
    parser.add_argument("--raw", action="store_true", help="In ra toàn bộ JSON gốc từ API")
    parser.add_argument("--update-cookie", nargs=2, metavar=("APP_COOKIE", "VERIFICATION_TOKEN"),
                        help="Cập nhật cookie .AspNet.ApplicationCookie và __RequestVerificationToken mới")

    args = parser.parse_args()

    client = IMSClient()

    if args.update_cookie:
        app_cookie, v_token = args.update_cookie
        client.update_cookies_manual(app_cookie, v_token)
        print(f"[OK] Đã cập nhật thành công cookie Core IMS vào: {', '.join(cf.name for cf in COOKIE_FILES)}")
        if not args.msisdn:
            return

    if not args.msisdn:
        parser.print_help()
        sys.exit(1)

    std_msisdn = normalize_phone(args.msisdn)
    print(f"\n=== ĐANG TRA CỨU HỒ SƠ CORE IMS CHO SỐ: {std_msisdn} ===")
    print(f"[*] Nguồn Cookie: {client.loaded_source}")

    try:
        raw_res = client.query_raw(std_msisdn)
        if args.raw:
            print(json.dumps(raw_res, indent=2, ensure_ascii=False))
            return

        parsed = client.parse_ims_data(raw_res, std_msisdn)
        print("\n" + "="*50)
        print(f"KẾT QUẢ TRA CỨU CORE IMS: {std_msisdn}")
        print("="*50)
        print(f"[*] IMSI:                     {parsed.get('imsi')}")
        print(f"[*] Trạng thái đăng ký IMS:   {parsed.get('registration_state')} ({'ĐÃ ĐĂNG KÝ VoLTE' if parsed.get('is_registered') else 'CHƯA ĐĂNG KÝ'})")
        print(f"[*] Chặn IMS (User Barring):  {'BỊ CHẶN' if parsed.get('user_barring') else 'Bình thường'}")
        print(f"[*] Cho phép Roaming:         {'Có' if parsed.get('roaming_allowed') else 'Không'}")
        print(f"[*] Thất bại xác thực SIP:    {parsed.get('failed_sip_auth_attempts')} lần")
        print(f"[*] S-CSCF phục vụ:           {parsed.get('scscf_server')}")
        print(f"[*] Profile tính cước:        {parsed.get('charging_profile')}")
        print(f"[*] Dịch vụ kích hoạt:        {', '.join(parsed.get('configured_services', []))}")
        print(f"[*] SIP URIs:                 {', '.join(parsed.get('sip_uris', []))}")
        print(f"[*] TEL URIs:                 {', '.join(parsed.get('tel_uris', []))}")
        print("-" * 50)
        print(f"[*] Tóm tắt: {parsed.get('summary_text')}")
        print("=" * 50 + "\n")

        # Lưu file
        out_dir = ROOT_DIR / "result" / "ims"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{std_msisdn}_ims.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
        print(f"[OK] Đã lưu kết quả tra cứu vào: {out_file.relative_to(ROOT_DIR)}")

    except Exception as e:
        print(f"[ERROR] Tra cứu Core IMS thất bại: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
