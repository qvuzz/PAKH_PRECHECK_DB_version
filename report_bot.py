# report_bot.py
import os
import re
import json
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from ai_interpreter import analyze_ticket_with_ai
# Gọi bộ não kịch bản từ file độc lập vừa tách
from scenarios_engine import match_diagnostic_scenarios

# 📂 Thư mục chứa file HSS Profile riêng theo từng số (định dạng: hss_profile/{phone_84}.json)
# ⚠️ Đổi lại đúng tên thư mục thật nếu khác - đây là giá trị mặc định đang giả định.
HSS_PROFILE_DIR = "output"


def get_has_4g_profile(phone_84):
    """
    Đọc file HSS Profile riêng của 1 số (theo phone_84), xác định có khai báo 4G hay không.
    - "HSS Profile" khác rỗng/null trong subscriber_info -> True (đã khai báo 4G)
    - "HSS Profile" rỗng/null -> False (chưa khai báo, chỉ bắt được sóng 3G)
    - Không tìm thấy file / lỗi đọc file -> None (không đủ dữ liệu để xác định)
    """
    file_path = os.path.join(HSS_PROFILE_DIR, f"{phone_84}.json")
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        hss_value = data.get("subscriber_info", {}).get("HSS Profile")
        return bool(hss_value)
    except Exception as e:
        print(f"⚠️ Lỗi đọc file HSS Profile ({file_path}): {e}")
        return None

def get_formatted_sapc_packages(phone_84, fallback_btools=""):
    """
    Đọc toàn bộ hồ sơ thuê bao (Radio, HSS Profile, IPv4), gói cước từ SAPC
    và kết hợp với gói thực tế từ BTools.
    Hiển thị đầy đủ cả hồ sơ Core và gói cước trong bảng.
    """
    file_path = os.path.join(HSS_PROFILE_DIR, f"{phone_84}.json")
    sapc_lines = []
    profile_parts = []
    
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 1. Trích xuất thông tin Hồ sơ thuê bao từ msisdn_info: Radio, HSS Profile, IPv4, NAM
            sub_info = data.get("subscriber_info", {})
            if isinstance(sub_info, dict) and sub_info:
                radio = str(sub_info.get("Radio") or "").strip()
                hss_prof = str(sub_info.get("HSS Profile") or "").strip()
                ipv4 = str(sub_info.get("IPv4") or "").strip()
                nam_val = str(sub_info.get("NAM") if sub_info.get("NAM") is not None else "").strip()

                sub_tags = []
                if radio and radio.lower() != "none":
                    sub_tags.append(f"Radio: {radio}")
                if hss_prof:
                    sub_tags.append(f"HSS: {hss_prof}")
                if ipv4:
                    sub_tags.append(f"IP: {ipv4}")
                if nam_val == "1":
                    sub_tags.append("NAM: 1 (Khóa GPRS)")
                elif nam_val == "0":
                    sub_tags.append("NAM: 0 (Mở GPRS)")
                elif nam_val != "":
                    sub_tags.append(f"NAM: {nam_val}")
                
                if sub_tags:
                    profile_parts.append("Hồ sơ: " + " | ".join(sub_tags))

            packages = data.get("packages", [])
            if isinstance(packages, list) and packages:
                for pkg in packages:
                    name = pkg.get("package_name") or pkg.get("group_name") or "Gói không tên"
                    reg = str(pkg.get("register_date") or "").replace("T", " ").strip()
                    exp = str(pkg.get("expire_date") or "").replace("T", " ").strip()
                    
                    info = []
                    if reg: info.append(f"ĐK: {reg}")
                    if exp: info.append(f"HSD: {exp}")
                    
                    if info:
                        detail_str = f" ({' | '.join(info)})"
                    else:
                        if "home" in name.lower():
                            detail_str = " (Gói tích hợp Home - Không có thông tin ngày ĐK/HSD)"
                        elif "paygo" in name.lower() or name.lower() == "m0":
                            detail_str = " (Gói mặc định Pay As You Go)"
                        else:
                            detail_str = " (Không có thông tin ngày ĐK/HSD)"
                    sapc_lines.append(f"• {name}{detail_str}")
        except Exception as e:
            print(f"⚠️ Lỗi đọc file SAPC packages ({file_path}): {e}")

    # Xây dựng chuỗi hiển thị kết hợp cả hồ sơ và gói cước
    result_parts = []
    if profile_parts:
        result_parts.extend(profile_parts)

    if sapc_lines:
        result_parts.append("SAPC:\n" + "\n".join(sapc_lines))
    else:
        result_parts.append("SAPC: Không có gói")

    btools_val = str(fallback_btools).strip() if fallback_btools else "Không phát sinh gói TM"
    result_parts.append(f"BTools: {btools_val}")

    return "\n\n".join(result_parts)


def get_sapc_package_validity(phone_84):
    """
    Phân loại chi tiết các gói cước của thuê bao từ SAPC:
    Trả về: (active_packages, expired_packages)
    Mỗi phần tử là dict chứa name, reg_str, exp_str, reg_dt, exp_dt, is_no_date, is_paygo, is_home.
    """
    file_path = os.path.join(HSS_PROFILE_DIR, f"{phone_84}.json")
    if not os.path.exists(file_path):
        return [], []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        packages = data.get("packages", [])
        if not packages or not isinstance(packages, list):
            return [], []

        now = datetime.now()
        active_packages = []
        expired_packages = []

        date_formats = [
            "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"
        ]

        for pkg in packages:
            pkg_name = pkg.get("package_name") or pkg.get("group_name") or "Gói cước"
            reg_str = str(pkg.get("register_date") or "").strip()
            exp_str = str(pkg.get("expire_date") or "").strip()

            is_home = "home" in pkg_name.lower()
            is_paygo = "paygo" in pkg_name.lower() or pkg_name.lower() == "m0"

            # Trường hợp đặc biệt: Gói HOME, PAYGO hoặc gói không có ngày tháng
            if not exp_str or is_paygo:
                if is_home:
                    desc = "Gói tích hợp Home (Không có thông tin ngày)"
                elif is_paygo:
                    desc = "Gói mặc định Pay As You Go"
                else:
                    desc = "Không có thông tin ngày ĐK/HSD"
                active_packages.append({
                    "name": pkg_name,
                    "reg_str": "Chưa có thông tin",
                    "exp_str": desc,
                    "reg_dt": None,
                    "exp_dt": None,
                    "is_no_date": True,
                    "is_paygo": is_paygo,
                    "is_home": is_home
                })
                continue

            reg_dt = None
            if reg_str:
                clean_reg = reg_str.replace("T", " ")
                for fmt in date_formats:
                    try:
                        reg_dt = datetime.strptime(clean_reg, fmt)
                        break
                    except ValueError:
                        pass

            exp_dt = None
            clean_exp = exp_str.replace("T", " ")
            for fmt in date_formats:
                try:
                    exp_dt = datetime.strptime(clean_exp, fmt)
                    break
                except ValueError:
                    pass

            reg_display = reg_dt.strftime("%d/%m/%Y %H:%M") if reg_dt else (reg_str or "N/A")
            exp_display = exp_dt.strftime("%d/%m/%Y %H:%M") if exp_dt else (exp_str or "Vô thời hạn")

            pkg_info = {
                "name": pkg_name,
                "reg_str": reg_display,
                "exp_str": exp_display,
                "reg_dt": reg_dt,
                "exp_dt": exp_dt,
                "is_no_date": False,
                "is_paygo": False,
                "is_home": is_home
            }

            if exp_dt and exp_dt < now:
                expired_packages.append(pkg_info)
            else:
                active_packages.append(pkg_info)

        return active_packages, expired_packages
    except Exception as e:
        print(f"⚠️ Lỗi kiểm tra gói SAPC ({file_path}): {e}")
        return [], []


def check_data_used_since_registration(clean_data, reg_dt):
    """
    Kiểm tra xem sau thời điểm đăng ký gói cước reg_dt, thuê bao có từng phát sinh data (>0) không.
    """
    if not clean_data:
        return False
    reg_date = reg_dt.date() if isinstance(reg_dt, datetime) else None
    for row in clean_data:
        time_str = row.get("RECORD_OPENING_TIME", "")
        if time_str:
            try:
                date_part = time_str.split(" ")[0]
                session_date = datetime.strptime(date_part, "%d/%m/%Y").date()
                if reg_date is None or session_date >= reg_date:
                    v = float(row.get("DATA_VOLUME_DOWNLINK", 0) or 0)
                    if v > 0:
                        return True
            except Exception:
                pass
    return False


VPN_KEYWORDS = [
    "1.1.1.1", "cloudflare", "warp", "vpn", "expressvpn", "nordvpn", "openvpn",
    "wireguard", "betternet", "turbo vpn", "supervpn", "surfshark", "psiphon",
    "adguard", "v2ray", "shadowsocks", "outline", "speedify", "tunnelbear",
    "hotspot shield", "windscribe", "protonvpn", "hide.me", "cyberghost"
]

def detect_vpn_application(app_events):
    """
    Kiểm tra xem trong dữ liệu App Usage của CEM có xuất hiện ứng dụng VPN / 1.1.1.1 / Cloudflare không.
    Trả về tên app VPN phát hiện được, hoặc None.
    """
    if not app_events:
        return None
        
    app_names = set()
    if isinstance(app_events, dict):
        data_list = app_events.get("data", [])
        if isinstance(data_list, list):
            for h in data_list:
                for item in h.get("top_list", []):
                    app_name = str(item.get("up_application") or "").strip().lower()
                    if app_name:
                        app_names.add(app_name)
    elif isinstance(app_events, list):
        for item in app_events:
            if isinstance(item, dict):
                app_name = str(item.get("up_application") or item.get("app_name") or item.get("name") or "").strip().lower()
                if app_name:
                    app_names.add(app_name)
            elif isinstance(item, str):
                app_names.add(item.strip().lower())
    elif isinstance(app_events, str):
        for line in app_events.split("\n"):
            clean_l = line.strip().lower().replace("•", "").strip()
            if clean_l:
                app_names.add(clean_l)
                
    for app in app_names:
        for kw in VPN_KEYWORDS:
            if kw in app:
                return app.title()
    return None

def extract_site_name_from_cell(cell_name):
    """
    Trích xuất mã Trạm (Site/eNodeB/BTS) từ tên Cell.
    Ví dụ: '4G-VTH008M32-KGG' -> 'VTH008-KGG'
           '4G-VTH008M12-KGG' -> 'VTH008-KGG'
           '3G-HNI012A-HNI'   -> 'HNI012-HNI'
    """
    if not cell_name:
        return ""
    c_name = str(cell_name).strip()
    clean = re.sub(r"^(4G|3G|2G|5G|LTE|NR)[-_]", "", c_name, flags=re.IGNORECASE)
    
    # 1. Tìm mẫu mã trạm chuẩn VNPT: [2-5 chữ cái][2-6 chữ số] (ví dụ: VTH008, HNI012, KGG008, HCM1234)
    m = re.search(r"([A-Za-z]{2,5}\d{2,6})", clean)
    if m:
        site_code = m.group(1).upper()
        prov_m = re.search(r"[-_]([A-Za-z]{2,4})$", clean)
        if prov_m and prov_m.group(1).upper() != site_code:
            return f"{site_code}-{prov_m.group(1).upper()}"
        return site_code
        
    # 2. Dự phòng: Cắt bỏ đuôi sector như _1, _2, -1, -2, _A, _B, M12, M32...
    base = clean.split("-")[0].split("_")[0]
    return base if base else c_name

def parse_dt_safe(val):
    if not val:
        return None
    val_str = str(val).strip()
    fmts = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ]
    for f in fmts:
        try:
            return datetime.strptime(val_str, f)
        except Exception:
            pass
    return None


def analyze_subscriber_status(clean_data, package_title, ticket_content="", phone_84="", cem_records=None, app_events=None, incident_time_str=None):
    """
    CHIẾN LƯỢC PHÂN TÍCH ƯU TIÊN NGÀY GẦN NHẤT VÀ SIẾT CHẶT ĐIỀU KIỆN THEO PHẢN ÁNH:
    1. Kiểm tra kịch bản trống dữ liệu 2 ngày gần nhất trước.
    2. Trích xuất riêng các phiên kết nối của NGÀY GẦN NHẤT CÓ DỮ LIỆU.
    3. Gọi thư viện ngoài scenarios_engine để quét 6 kịch bản lỗi hệ thống và vật lý.
    4. Phân tầng logic "BÌNH THƯỜNG" / "LƯU LƯỢNG YẾU" / "CHƯA ĐĂNG KÝ GÓI" / "CHỈ CÓ GÓI PAYGO" / "CEM DOMINANT CELL" / "GÓI CƯỚC ĐÃ HẾT HẠN" / "GÓI CÒN HẠN KHÔNG DÙNG ĐƯỢC" / "VPN".
    5. ĐỐI VỚI HOẠT ĐỘNG BÌNH THƯỜNG: Bắt buộc phiên data >10MB phải phát sinh SAU THỜI ĐIỂM TIẾP NHẬN.
    """
    default_status = "CHƯA PHÂN LOẠI"
    default_comment = "Chưa xác định được nguyên nhân đặc thù. Cần kỹ thuật viên kiểm tra trực tiếp."
    default_color = "FFFFFF"

    ALERT_COMMENT = "\nLưu ý: 2 ngày gần nhất không thấy phát sinh data, nghi ngờ gói cước đã hết hạn, khách hàng off data hoặc đã tắt máy."
    ALERT_ACTION = "\nCần kiểm tra tình trạng thuê bao, thiết bị, sim và gói cước"
    comment_suffix = ""
    action_suffix = ""

    # 🎯 KỊCH BẢN ĐẶC THÙ: BTOOLS BỊ LỖI HOẶC CHƯA ĐĂNG NHẬP (KHÔNG ĐƯỢC TỰ ĐỘNG ĐÓNG PHIẾU)
    if clean_data is None:
        return (
            "LỖI KẾT NỐI BTOOLS",
            "Không thể tra cứu dữ liệu lưu lượng BTools (chưa đăng nhập BTools hoặc máy chủ 10.159.21.241 bị lỗi/hết phiên). Cần kiểm tra lại phiên BTools trên trình duyệt Chrome.",
            "Vui lòng mở tab BTools trên Chrome để đăng nhập hoặc kiểm tra kết nối mạng nội bộ, sau đó bấm '⚡ Tiền kiểm' để kiểm tra lại.",
            "F8D7DA"
        )
    sub_info = {}
    if phone_84:
        out_json_file = os.path.join(HSS_PROFILE_DIR, f"{phone_84}.json")
        if os.path.exists(out_json_file):
            try:
                with open(out_json_file, "r", encoding="utf-8") as f_sub:
                    d_sub = json.load(f_sub)
                    sub_info = d_sub.get("subscriber_info", {})
            except Exception:
                pass

    # 🎯 KỊCH BẢN MS PURGED: KH đã off thiết bị nhiều ngày nên không kiểm tra được
    sub_state = str(
        sub_info.get("Sub State") 
        or sub_info.get("subState") 
        or sub_info.get("sub_state")
        or sub_info.get("Location State") 
        or sub_info.get("State") 
        or ""
    ).strip().upper()
    if ("MS PURGED" in sub_state) or (sub_state == "PURGED") or ("PURGED" in sub_state):
        return (
            "OFF THIẾT BỊ NHIỀU NGÀY",
            "Khách hàng đã off thiết bị nhiều ngày nên không kiểm tra được.",
            "Thông báo khách hàng mở lại thiết bị để sử dụng dịch vụ. Nếu cần hỗ trợ thêm vui lòng liên hệ tổng đài.",
            "FFF2CC"
        )

    # 1. KỊCH BẢN NAM: NAM = 1 (BỊ KHÓA GPRS)
    nam_val = str(sub_info.get("NAM") if sub_info.get("NAM") is not None else "").strip()
    if nam_val == "1":
        return (
            "BỊ KHÓA GPRS",
            "Thuê bao đang bị khóa GPRS.",
            "Nhờ VNP khai báo lại GPRS cho Khách hàng.",
            "FFF2CC"
        )

    # 2. KỊCH BẢN MOBILE INTERNET 5G
    combined_report_text = f"{package_title} {ticket_content}".lower()
    # Loại bỏ các cụm dung lượng như 1.5GB, 5GB, 15GB, 5G/ngày, 2.5G data... tránh nhận diện nhầm là mạng 5G
    cleaned_5g_text = re.sub(r'\b\d+([.,]\d+)?\s*(gb|mb|giga|tb)\b', ' ', combined_report_text, flags=re.IGNORECASE)
    cleaned_5g_text = re.sub(r'\d+([.,]\d+)?(gb|mb)\b', ' ', cleaned_5g_text, flags=re.IGNORECASE)
    cleaned_5g_text = re.sub(r'\b\d+[.,]\d+\s*g\b', ' ', cleaned_5g_text, flags=re.IGNORECASE)
    cleaned_5g_text = re.sub(r'\b\d+\s*g\s*/\s*(?:ngày|tháng|ngay|thang|day|thg)\b', ' ', cleaned_5g_text, flags=re.IGNORECASE)
    is_5g_reported = ("mobile internet 5g" in package_title.lower()) or bool(re.search(r'(?<![0-9a-zA-Z.])5g(?![0-9a-zA-Z])', cleaned_5g_text, flags=re.IGNORECASE))
    if is_5g_reported:
        hss_profile = str(sub_info.get("HSS Profile") or "").strip()
        valid_5g_profiles = {"55", "56", "65", "66", "67"}
        if hss_profile and hss_profile not in valid_5g_profiles:
            return (
                "HSS CHƯA CÓ 5G",
                "HSS Profile của KH không phải là 5G.",
                "Nhờ VNP đăng ký 5G cho KH hoặc nhờ IT hỗ trợ thêm.",
                "FFF2CC"
            )
        elif hss_profile in valid_5g_profiles:
            # HSS Profile có 5G, kiểm tra xem BTools RAT TYPE có số 7 nào không
            has_rat_7 = False
            for r in (clean_data or []):
                r_type = str(r.get("RAT_TYPE") or "").strip()
                r_name = str(r.get("RAT_TYPE_NAME") or "").upper()
                if r_type == "7" or "5G" in r_name or "NR" in r_name:
                    has_rat_7 = True
                    break
            if not has_rat_7:
                return (
                    "THIẾU SÓNG 5G / THIẾT BỊ",
                    "HSS Profile có 5G nhưng btool RAT TYPE không có số 7 nào thì có thể do thiết bị của KH hoặc khu vực của KH không có sóng 5G.",
                    "Nhờ VNP hướng dẫn KH kiểm tra thiết bị có hỗ trợ/bật 5G hoặc kiểm tra vùng phủ sóng 5G tại khu vực của KH.",
                    "FFF2CC"
                )

    # 🎯 KỊCH BẢN ĐẶC THÙ 1: Kiểm tra App Usage có xuất hiện ứng dụng VPN / 1.1.1.1 / Cloudflare
    detected_vpn = detect_vpn_application(app_events)
    if detected_vpn:
        vpn_note = f"vào ngày tiếp nhận phản ánh ({incident_time_str[:10]})" if incident_time_str else "gần đây"
        return (
            "ĐANG SỬ DỤNG VPN / 1.1.1.1",
            f"Dữ liệu CEM ghi nhận {vpn_note}, thiết bị của khách hàng có phát sinh lưu lượng qua ứng dụng mạng riêng ảo ({detected_vpn}). Khi bật VPN, lưu lượng đi quốc tế bị bóp dung lượng dẫn đến tình trạng load chậm hoặc mất kết nối dịch vụ.",
            f"Hướng dẫn khách hàng tạm thời tắt/gỡ ứng dụng VPN ({detected_vpn}) trên máy, sau đó bật lại dữ liệu di động để truy cập bình thường." + action_suffix,
            "E2EFDA"
        )

    # 🎯 KỊCH BẢN ĐẶC THÙ 2: Khách hàng phản ánh dùng gói VD2 nhưng SAPC không thấy có gói PAYGO
    combined_report_text = f"{package_title} {ticket_content}".lower()
    is_vd2_reported = bool(re.search(r"\bvd2\b|\bvd2k\b|gói vd2|goi vd2", combined_report_text))
    if is_vd2_reported:
        active_pkgs, _ = get_sapc_package_validity(phone_84)
        has_paygo = any(p.get("is_paygo") or "paygo" in p.get("name", "").lower() for p in active_pkgs)
        if not has_paygo:
            return (
                "LỖI GÓI VD2 - THIẾU PAYGO",
                "Thuê bao đăng ký gói VD2 nhưng hệ thống SAPC chưa được khai báo gói nền PAYGO (M0), dẫn đến mất kết nối dữ liệu di động.",
                "Chuyển bộ phận IT/Khai thác cước kiểm tra và kích hoạt bổ sung gói nền PAYGO cho thuê bao trên hệ thống." + action_suffix,
                "FFF2CC"
            )

    # 🎯 KỊCH BẢN ĐẶC THÙ 3: KH phản ánh trong ngày, hồ sơ Radio: 3G & IP: null, đi nhiều nơi lỗi, BTools có data < 10MB
    radio_str = str(sub_info.get("Radio") or "").strip().upper()
    is_radio_3g = ("3G" in radio_str) or ("UTRAN" in radio_str)
    ipv4_str = str(sub_info.get("IPv4") or sub_info.get("IP") or "").strip().lower()
    is_ip_null = (not ipv4_str) or (ipv4_str in ("null", "none", "--", "undefined", "0.0.0.0"))

    is_incident_today = False
    if incident_time_str:
        try:
            date_part = incident_time_str.split(" ")[0].strip()
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    inc_d = datetime.strptime(date_part, fmt).date()
                    if inc_d == datetime.now().date():
                        is_incident_today = True
                    break
                except Exception:
                    pass
        except Exception:
            pass

    multi_area_patterns = [
        "đi nhiều nơi", "di nhiều nơi", "di nhieu noi", "nhiều nơi", "nhieu noi",
        "đi nhiều khu vực", "nhiều khu vực", "nhieu khu vuc",
        "khu vực khác cũng", "khu vuc khac cung", "kv khác cũng", "kv khac cung",
        "đi đâu cũng", "di dau cung", "các khu vực", "qua nhiều trạm", "nhiều địa chỉ"
    ]
    is_multi_area = any(p in combined_report_text for p in multi_area_patterns)

    total_bytes = 0
    if clean_data:
        for r in clean_data:
            try:
                dl = float(r.get("DATA_VOLUME_DOWNLINK") or 0)
                ul = float(r.get("DATA_VOLUME_UPLINK") or 0)
                total_bytes += (dl + ul)
            except (ValueError, TypeError):
                pass
    total_mb = total_bytes / (1024 * 1024)
    has_btools_under_10mb = bool(clean_data and len(clean_data) > 0 and 0 <= total_mb < 10.0)

    if is_incident_today and is_radio_3g and is_ip_null and is_multi_area and has_btools_under_10mb:
        return (
            "SÓNG 4G KÉM / CHỈ CÓ 3G",
            "Khách hàng đang ở khu vực sóng 4G kém, chỉ ở 3G nên khó truy cập.",
            "Nhờ VNP báo Khách hàng chi tiết giúp, thông cảm và theo dõi thêm giúp.",
            "FFF2CC"
        )

    if not clean_data or len(clean_data) == 0:
        active_pkgs, expired_pkgs = get_sapc_package_validity(phone_84)
        
        # 1. TẤT CẢ GÓI ĐỀU ĐÃ HẾT HẠN (không còn gói active nào)
        if not active_pkgs and expired_pkgs:
            exp_names = ", ".join([p["name"] for p in expired_pkgs])
            exp_dates = ", ".join([p["exp_str"] for p in expired_pkgs])
            exp_note = f" (trước/vào thời điểm tiếp nhận phản ánh {incident_time_str})" if incident_time_str else ""
            return (
                "GÓI CƯỚC ĐÃ HẾT HẠN",
                f"Thuê bao hoàn toàn không phát sinh dữ liệu trong các ngày qua do gói cước {exp_names} của khách hàng đã hết hạn vào ngày {exp_dates}{exp_note}.",
                f"Gói cước của Khách hàng ({exp_names}) đã hết hạn vào ngày {exp_dates}. Nhờ VNP kiểm tra lại, tư vấn khách hàng gia hạn/đăng ký gói cước mới.",
                "FFF2CC"
            )
        
        # 2. VẪN CÓ GÓI ACTIVE: Kiểm tra chi tiết loại gói (PAYGO / HOME / Gói thương mại)
        if active_pkgs:
            # 2.1. Thuê bao CHỈ CÓ GÓI PAYGO
            if all(p.get("is_paygo") for p in active_pkgs):
                return (
                    "CHỈ CÓ GÓI PAYGO",
                    "Thuê bao hiện chỉ có gói cước mặc định (PAYGO/M0), không có gói data ưu đãi và tài khoản chính không đủ để trừ cước truy cập ngoài gói.",
                    "Hướng dẫn khách hàng kiểm tra số dư tài khoản chính, đồng thời tư vấn đăng ký các gói cước Data VinaPhone ưu đãi để sử dụng.",
                    "FFF2CC"
                )

            # 2.2. Trường hợp đặc biệt: Gói tích hợp HOME không có ngày tháng
            if all(p.get("is_home") or p.get("is_no_date") for p in active_pkgs):
                pkg_names = ", ".join([p["name"] for p in active_pkgs])
                return (
                    "THEO DÕI THÊM",
                    f"Thuê bao đang sử dụng gói tích hợp {pkg_names} (chưa có thông tin chu kỳ ngày ĐK/HSD trên hệ thống). Lịch sử dữ liệu BTools 5 ngày qua không ghi nhận lưu lượng phát sinh.",
                    f"Kiểm tra lại trạng thái gói cước {pkg_names} trên hệ thống quản lý thuê bao, hướng dẫn khách hàng kiểm tra dữ liệu di động và khởi động lại thiết bị." + ALERT_ACTION,
                    "E2EFDA"
                )

            act_names = ", ".join([p["name"] for p in active_pkgs if not p.get("is_paygo")])
            act_exp_dates = ", ".join([p["exp_str"] for p in active_pkgs if not p.get("is_paygo")])
            act_reg_dates = ", ".join([p["reg_str"] for p in active_pkgs if not p.get("is_paygo") and p["reg_str"] != "N/A"]) or "trước đó"
            
            # Vì clean_data = 0 nên chắc chắn từ ngày ĐK đến nay không phát sinh data
            return (
                "GÓI CÒN HẠN - KHÔNG DÙNG ĐƯỢC",
                f"Thuê bao đăng ký gói {act_names} từ ngày {act_reg_dates} (còn hạn đến {act_exp_dates}) nhưng từ khi đăng ký đến nay hoàn toàn không phát sinh dữ liệu, nghi ngờ lỗi luồng cước/profile gói.",
                f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {act_names} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao.",
                "FFF2CC"
            )

        return (
            "KHÔNG CÓ DỮ LIỆU", 
            "Thuê bao hoàn toàn không phát sinh dữ liệu trong 5 ngày qua trên hệ thống BTools." + ALERT_COMMENT, 
            "Nghi ngờ do thiết bị của khách hàng bị treo data. Nhờ khách hàng thử tắt/bật thiết bị và data, đổi sim sang máy khác và kiểm tra SPEEDTEST giúp." + ALERT_ACTION, 
            "FFF2CC"
        )

    scenarios_file = "diagnostic_scenarios.json"
    if not os.path.exists(scenarios_file):
        return default_status, default_comment, default_plan, default_color

    with open(scenarios_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    scenarios = config.get("SCENARIOS", [])

    # 🕒 1. KIỂM TRA CHÉO 2 NGÀY GẦN NHẤT XEM CÓ DATA KHÔNG
    has_recent_data = False
    today_date = datetime.now().date()
    recent_dates = {today_date, today_date - timedelta(days=1)}
    latest_date_in_log = None
    
    for row in clean_data:
        time_str = row.get("RECORD_OPENING_TIME", "")
        if time_str:
            try:
                date_part = time_str.split(" ")[0]
                session_date = datetime.strptime(date_part, "%d/%m/%Y").date()
                if session_date in recent_dates:
                    has_recent_data = True
                if latest_date_in_log is None or session_date > latest_date_in_log:
                    latest_date_in_log = session_date
            except:
                pass

    comment_suffix = ALERT_COMMENT if not has_recent_data else ""
    action_suffix = ALERT_ACTION if not has_recent_data else ""

    # 🎯 2. TÁCH DỮ LIỆU NGÀY GẦN NHẤT CÓ LOG + 3 NGÀY GẦN NHẤT (cho KC_01, KC_04)
    recent_day_data = []
    recent_3days_data = []

    if latest_date_in_log:
        for row in clean_data:
            time_str = row.get("RECORD_OPENING_TIME", "")
            if time_str:
                try:
                    date_part = time_str.split(" ")[0]
                    session_date = datetime.strptime(date_part, "%d/%m/%Y").date()
                    if session_date == latest_date_in_log:
                        recent_day_data.append(row)
                    if latest_date_in_log - session_date <= timedelta(days=2):
                        recent_3days_data.append(row)
                except:
                    pass
    else:
        recent_day_data = clean_data
        recent_3days_data = clean_data

    # Tập hợp các mã gói và RAT của 3 ngày gần nhất
    service_set_3days = set(str(r.get("SERVICE_ID_CODE", "")).strip().lower() for r in recent_3days_data if r.get("SERVICE_ID_CODE"))
    rat_set_3days = set(str(r.get("RAT_TYPE_CODE", "")).strip() for r in recent_3days_data if r.get("RAT_TYPE_CODE"))

    rat_codes = []
    service_codes = []
    downlink_values = []

    for row in recent_day_data:
        r_c = row.get("RAT_TYPE_CODE")
        if r_c is not None: rat_codes.append(str(r_c).strip())
        s_c = row.get("SERVICE_ID_CODE")
        if s_c is not None: service_codes.append(str(s_c).strip().lower())
        try:
            v = row.get("DATA_VOLUME_DOWNLINK")
            if v is not None: downlink_values.append(float(v))
        except ValueError:
            pass

    rat_set = set(rat_codes)
    service_set = set(service_codes)

    # 🔎 Đối chiếu HSS Profile riêng theo số
    has_4g_profile = get_has_4g_profile(phone_84)

    # 🔥 3. GỌI THƯ VIỆN LOGIC KỊCH BẢN ĐÃ TÁCH BIỆT (scenarios_engine)
    matched_id, _ = match_diagnostic_scenarios(
        rat_set, service_set, rat_codes, downlink_values, len(recent_day_data), scenarios,
        service_set_3days=service_set_3days, rat_set_3days=rat_set_3days,
        has_4g_profile=has_4g_profile
    )
    
    if matched_id:
        status, comment, plan, color = get_scenario_result(scenarios, matched_id)
        return status, comment + comment_suffix, plan + action_suffix, color

    # =========================================================================
    # 🛑 GIAI ĐOẠN ĐÁNH GIÁ ĐIỀU KIỆN PHÂN LOẠI THEO PHẢN ÁNH & CEM
    # =========================================================================
    with open("diagnostic_config.json", "r", encoding="utf-8") as cf:
        config_data = json.load(cf)
    excluded_system_codes = set(config_data.get("EXCLUDED_SYSTEM_CODES", []))
    
    ticket_content_lower = ticket_content.lower() if ticket_content else ""

    # 🎯 ĐIỀU KIỆN 1: [CHƯA ĐĂNG KÝ GÓI]
    all_days_service_codes = set()
    for row in clean_data:
        sc = str(row.get("SERVICE_ID_CODE", "")).strip().lower()
        if sc:
            all_days_service_codes.add(sc)
            
    is_pure_system_codes_only = all(code in excluded_system_codes for code in all_days_service_codes)
    
    if is_pure_system_codes_only:
        return (
            "CHƯA ĐĂNG KÝ GÓI",
            "Lịch sử phân tích dữ liệu xuyên suốt các ngày qua chỉ xuất hiện các mã hệ thống mặc định, không tồn tại gói cước thương mại phát sinh data.",
            "Yêu cầu kỹ thuật viên kiểm tra trạng thái gói trên hLR/PCRF và hướng dẫn khách hàng cách thức đăng ký gói cước di động." + action_suffix,
            "FFF2CC"
        )

    TRAFFIC_MIN_WEAK = 1_000_000      # 1MB
    TRAFFIC_MAX_WEAK = 10_000_000     # 10MB
    
    max_downlink = max(downlink_values, default=0)
    has_session_over_10mb = max_downlink >= TRAFFIC_MAX_WEAK
    is_weak_traffic = TRAFFIC_MIN_WEAK <= max_downlink < TRAFFIC_MAX_WEAK

    is_reported_completely_failed = any(k in ticket_content_lower for k in ["không được", "khong duoc", "không vào được", "khong vao duoc", "mất hoàn toàn"])
    is_reported_slow = any(k in ticket_content_lower for k in ["chậm", "cham", "yếu", "yeu", "chập chờn", "chap chon"])
    is_reported_multiple_places = any(
        k in ticket_content_lower for k in [
            "nhiều nơi", "nhieu noi", "nhiều chỗ", "nhieu cho", "ở đâu cũng", "o dau cung",
            "đi đâu cũng", "di dau cung", "khắp nơi", "khap noi", "di chuyển", "di chuyen",
            "tại nhiều điểm", "tai nhieu diem", "nhiều khu vực", "nhieu khu vuc"
        ]
    )

    recent_day_str = latest_date_in_log.strftime('%d/%m/%Y') if latest_date_in_log else "gần nhất"

    # 🎯 PHÂN TÍCH TỶ LỆ CELL TỪ DỮ LIỆU CEM (ƯU TIÊN THEO NGÀY TIẾP NHẬN SỰ CỐ)
    dominant_cell = None
    dominant_pct = 0.0
    dominant_context_str = "5 ngày"
    if cem_records and isinstance(cem_records, list):
        from collections import Counter
        
        target_records = cem_records
        if incident_time_str:
            dt_inc = parse_dt_safe(incident_time_str)
            if dt_inc:
                inc_day_str = dt_inc.strftime("%Y-%m-%d")
                day_records = [
                    r for r in cem_records 
                    if (r.get("_query_date") == inc_day_str or str(r.get("date") or "")[:10] == inc_day_str)
                ]
                if len(day_records) >= 2:
                    target_records = day_records
                    dominant_context_str = f"ngày tiếp nhận ({dt_inc.strftime('%d/%m/%Y')})"

        cell_names = [
            str(r.get("cell_name") or r.get("cellName") or r.get("cell_id") or "").strip()
            for r in target_records if (r.get("cell_name") or r.get("cellName") or r.get("cell_id"))
        ]
        if cell_names:
            total_samples = len(cell_names)
            c_counter = Counter(cell_names)
            top_c, top_cnt = c_counter.most_common(1)[0]
            cell_pct = (top_cnt / total_samples) * 100

            # 📡 Gom nhóm nhận diện theo TRẠM (Site/eNodeB/BTS)
            site_names = [extract_site_name_from_cell(c) for c in cell_names]
            s_counter = Counter(site_names)
            top_s, top_s_cnt = s_counter.most_common(1)[0]
            site_pct = (top_s_cnt / total_samples) * 100

            if site_pct >= 50.0:
                dominant_pct = site_pct
                # Đếm các cell cụ thể thuộc trạm này
                sub_cells = [c for c in cell_names if extract_site_name_from_cell(c) == top_s]
                sub_counter = Counter(sub_cells)
                top_sub_cells = [f"{c} ({cnt*100/total_samples:.0f}%)" for c, cnt in sub_counter.most_common(3)]
                
                if len(sub_counter) > 1:
                    dominant_cell = f"{top_s} (gồm {len(sub_counter)} cell: {', '.join(top_sub_cells)})"
                else:
                    dominant_cell = top_c
            elif cell_pct >= 50.0:
                dominant_cell = top_c
                dominant_pct = cell_pct

    # 🎯 PHÂN TÍCH THEO MỐC THỜI GIAN TIẾP NHẬN PHẢN ÁNH (ĐỐI CHIẾU PHIÊN DATA SAU KHI TIẾP NHẬN)
    dt_incident = parse_dt_safe(incident_time_str)
    sessions_after_incident = []
    
    if dt_incident and clean_data:
        for row in clean_data:
            time_str = row.get("RECORD_OPENING_TIME", "")
            row_dt = parse_dt_safe(time_str)
            if row_dt and row_dt >= dt_incident:
                sessions_after_incident.append((row_dt, row))

    downlinks_after = [
        float(r.get("DATA_VOLUME_DOWNLINK", 0) or 0) 
        for _, r in sessions_after_incident 
        if r.get("DATA_VOLUME_DOWNLINK") is not None
    ]
    max_downlink_after = max(downlinks_after, default=0)
    has_session_over_10mb_after = max_downlink_after >= TRAFFIC_MAX_WEAK
    is_weak_traffic_after = TRAFFIC_MIN_WEAK <= max_downlink_after < TRAFFIC_MAX_WEAK

    # 🎯 KỊCH BẢN ĐÁNH GIÁ KHI CÓ MỐC THỜI GIAN TIẾP NHẬN
    if dt_incident:
        # Trường hợp 1: Có phiên >10MB SAU thời điểm tiếp nhận -> Khách hàng đã dùng được
        if has_session_over_10mb_after:
            if dominant_cell and is_reported_slow:
                return (
                    "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                    f"Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% lưu lượng). Nghi ngờ trạm phát sóng tại khu vực này đang tải cao hoặc suy hao cục bộ.",
                    "Nhờ tạo phiếu CLM chuyển Kỹ thuật địa bàn để đo kiểm chất lượng mạng và tối ưu vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )
            elif is_reported_slow:
                return (
                    "LƯU LƯỢNG YẾU",
                    f"Khách hàng phản ánh mạng chậm. Dữ liệu sau thời điểm tiếp nhận ({incident_time_str}) ghi nhận tốc độ download chưa ổn định, phiên cao nhất đạt {max_downlink_after/1024/1024:.1f}MB. Nghi ngờ chất lượng sóng tại khu vực khách hàng chưa đảm bảo.",
                    "Nhờ tạo phiếu CLM chuyển Kỹ thuật địa bàn để đo kiểm chất lượng mạng và tối ưu vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )
            else:
                return (
                    "HOẠT ĐỘNG BÌNH THƯỜNG",
                    f"Kiểm tra lịch sử kết nối sau thời điểm tiếp nhận phản ánh ({incident_time_str}), thuê bao đã phát sinh lưu lượng data bình thường (phiên lớn nhất đạt {max_downlink_after/1024/1024:.1f}MB, mạng 4G ổn định). Khách hàng đã sử dụng được dịch vụ.",
                    "Dịch vụ đã khôi phục hoạt động bình thường sau thời điểm phản ánh. Hướng dẫn khách hàng theo dõi sử dụng, nếu cần hỗ trợ thêm vui lòng liên hệ lại tổng đài." + action_suffix,
                    "E2EFDA"
                )
        
        # Trường hợp 2: Có phiên >10MB TRƯỚC thời điểm tiếp nhận, nhưng SAU mốc tiếp nhận CHƯA CÓ phiên >10MB -> Cần theo dõi thêm
        elif has_session_over_10mb:
            return (
                "THEO DÕI THÊM",
                f"Thuê bao có sử dụng data trước thời điểm phản ánh, tuy nhiên sau mốc tiếp nhận ({incident_time_str}) chưa ghi nhận phiên phát sinh lưu lượng mới. Cần theo dõi thêm.",
                "Có thể Khách hàng đang di chuyển vào khu vực sóng kém, hoặc nghẽn mạng tạm thời. Nhờ KH theo dõi thêm giúp." + action_suffix,
                "FFF2CC"
            )

        # Trường hợp 3: Sau tiếp nhận chỉ có lưu lượng yếu (1MB - 10MB)
        elif is_weak_traffic_after:
            if dominant_cell:
                return (
                    "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                    f"Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% lưu lượng). Nghi ngờ trạm phát sóng tại khu vực này đang tải cao hoặc suy hao cục bộ.",
                    "Nhờ tạo phiếu CLM chuyển Kỹ thuật địa bàn để đo kiểm chất lượng mạng và tối ưu vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )
            else:
                return (
                    "LƯU LƯỢNG YẾU",
                    f"Sau thời điểm tiếp nhận ({incident_time_str}), lưu lượng data thực tế ở mức thấp (phiên lớn nhất chỉ đạt {max_downlink_after/1024/1024:.1f}MB), kết nối chập chờn tại khu vực phản ánh.",
                    "Nhờ tạo phiếu CLM chuyển Kỹ thuật địa bàn để đo kiểm chất lượng mạng và tối ưu vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )

    # 🎯 KỊCH BẢN KHI CÓ DỮ LIỆU DATA >10MB (FALLBACK HOẶC KHÔNG CÓ MỐC TIẾP NHẬN)
    if has_session_over_10mb:
        if dominant_cell and (is_reported_slow or is_reported_multiple_places):
            return (
                "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                f"Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% lưu lượng). Nghi ngờ trạm phát sóng tại khu vực này đang tải cao hoặc suy hao cục bộ.",
                "Nhờ tạo phiếu CLM chuyển Kỹ thuật địa bàn để đo kiểm chất lượng mạng và tối ưu vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                "FFF2CC"
            )
        elif is_reported_completely_failed:
            return (
                "HOẠT ĐỘNG BÌNH THƯỜNG",
                f"Khách hàng phản ánh không truy cập được hoàn toàn, nhưng dữ liệu BTools thực tế ngày gần nhất ({recent_day_str}) vẫn ghi nhận phiên kết nối dung lượng lớn ({max_downlink/1024/1024:.1f}MB). Dịch vụ đã tự phục hồi sau thời điểm phản ánh.",
                "Dịch vụ đã khôi phục hoạt động bình thường. Hướng dẫn khách hàng tiếp tục theo dõi sử dụng." + action_suffix,
                "E2EFDA"
            )
        elif is_reported_slow or is_reported_multiple_places:
            return (
                "LƯU LƯỢNG YẾU",
                f"Khách hàng phản ánh mạng chậm / chập chờn. Dữ liệu thực tế ngày gần nhất ({recent_day_str}) ghi nhận tốc độ download chưa ổn định ({max_downlink/1024/1024:.1f}MB). Nghi ngờ chất lượng sóng tại khu vực khách hàng chưa đảm bảo.",
                "Nhờ tạo phiếu CLM chuyển Kỹ thuật địa bàn để đo kiểm chất lượng mạng và tối ưu vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                "FFF2CC"
            )
        else:
            return (
                "HOẠT ĐỘNG BÌNH THƯỜNG",
                f"Kiểm tra lịch sử kết nối ngày gần nhất ({recent_day_str}), thuê bao phát sinh lưu lượng data bình thường (phiên lớn nhất đạt {max_downlink/1024/1024:.1f}MB, mạng 4G ổn định).",
                "Dịch vụ đã hoạt động bình thường. Hướng dẫn khách hàng tiếp tục theo dõi sử dụng." + action_suffix,
                "E2EFDA"
            )

    # 🎯 KỊCH BẢN LƯU LƯỢNG YẾU (1MB - 10MB)
    if is_weak_traffic:
        if dominant_cell:
            return (
                "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                f"Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% lưu lượng). Nghi ngờ trạm phát sóng tại khu vực này đang tải cao hoặc suy hao cục bộ.",
                "Nhờ tạo phiếu CLM chuyển Kỹ thuật địa bàn để đo kiểm chất lượng mạng và tối ưu vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                "FFF2CC"
            )
        else:
            return (
                "LƯU LƯỢNG YẾU",
                f"Lưu lượng data thực tế ngày gần nhất ({recent_day_str}) ở mức thấp (phiên lớn nhất chỉ đạt từ 1MB đến dưới 10MB), kết nối chập chờn tại khu vực phản ánh.",
                "Nhờ tạo phiếu CLM chuyển Kỹ thuật địa bàn để đo kiểm chất lượng mạng và tối ưu vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                "FFF2CC"
            )

    # 🎯 KỊCH BẢN ĐI NHIỀU NƠI BỊ LỖI (CHỈ KHI THỰC SỰ KHÔNG LOAD ĐƯỢC DATA TRÊN NHIỀU TRẠM KHÁC NHAU)
    if is_reported_multiple_places and not dominant_cell:
        return (
            "LỖI THIẾT BỊ / ĐI NHIỀU NƠI BỊ LỖI",
            "Khách hàng phản ánh đi nhiều nơi đều bị lỗi, dữ liệu mạng ghi nhận thuê bao đổi trạm liên tục qua nhiều khu vực khác nhau nhưng đều không load được data (<1MB). Nguyên nhân do xung đột cài đặt mạng, lỗi SIM hoặc thiết bị đầu cuối của khách hàng.",
            "Hướng dẫn khách hàng khởi động lại máy, bật/tắt chế độ máy bay, vệ sinh lại khay SIM hoặc mang SIM qua điểm giao dịch VinaPhone gần nhất để kiểm tra đổi SIM." + action_suffix,
            "FFF2CC"
        )

    # 🎯 TRƯỜNG HỢP CÒN LẠI: KIỂM TRA LẠI GÓI CƯỚC SAPC
    active_pkgs, expired_pkgs = get_sapc_package_validity(phone_84)
    if not active_pkgs and expired_pkgs:
        exp_names = ", ".join([p["name"] for p in expired_pkgs])
        exp_dates = ", ".join([p["exp_str"] for p in expired_pkgs])
        return (
            "GÓI CƯỚC ĐÃ HẾT HẠN",
            f"Gói cước data của thuê bao ({exp_names}) đã hết hạn từ ngày {exp_dates}, tài khoản không còn dung lượng ưu đãi dẫn đến không truy cập được Internet.",
            f"Thông báo khách hàng gói cước ({exp_names}) đã hết hạn sử dụng. Tư vấn khách hàng nạp tiền gia hạn hoặc đăng ký gói cước mới phù hợp." + action_suffix,
            "FFF2CC"
        )
    elif active_pkgs:
        if all(p.get("is_paygo") for p in active_pkgs):
            return (
                "CHỈ CÓ GÓI PAYGO",
                f"Thuê bao hiện chỉ có gói cước mặc định (PAYGO/M0), không có gói data ưu đãi và tài khoản chính không đủ để trừ cước truy cập ngoài gói.",
                "Hướng dẫn khách hàng kiểm tra số dư tài khoản chính, đồng thời tư vấn đăng ký các gói cước Data VinaPhone ưu đãi để sử dụng." + action_suffix,
                "FFF2CC"
            )

        if all(p.get("is_home") or p.get("is_no_date") for p in active_pkgs):
            pkg_names = ", ".join([p["name"] for p in active_pkgs])
            return (
                "THEO DÕI THÊM",
                f"Thuê bao sử dụng gói tích hợp ({pkg_names}), hệ thống chưa ghi nhận phát sinh lưu lượng trong ngày gần nhất. Nghi ngờ thiết bị tắt data hoặc đang sử dụng Wifi.",
                f"Hướng dẫn khách hàng bật Dữ liệu di động (Data), khởi động lại thiết bị và theo dõi sử dụng." + action_suffix,
                "E2EFDA"
            )

        act_names = ", ".join([p["name"] for p in active_pkgs if not p.get("is_paygo")])
        act_exp_dates = ", ".join([p["exp_str"] for p in active_pkgs if not p.get("is_paygo")])
        act_reg_dates = ", ".join([p["reg_str"] for p in active_pkgs if not p.get("is_paygo") and p["reg_str"] != "N/A"]) or "trước đó"
        earliest_reg_dt = min([p["reg_dt"] for p in active_pkgs if p["reg_dt"] and not p.get("is_paygo")], default=None)
        
        # Kiểm tra xem từ ngày đăng ký đến nay thuê bao đã từng dùng data chưa
        has_used_since_reg = check_data_used_since_registration(clean_data, earliest_reg_dt)
        
        if not has_used_since_reg:
            # Từ ngày ĐK đến nay hoàn toàn không phát sinh data -> Lỗi do gói
            return (
                "GÓI CÒN HẠN - KHÔNG DÙNG ĐƯỢC",
                f"Thuê bao đăng ký gói {act_names} từ ngày {act_reg_dates} (còn hạn đến {act_exp_dates}) nhưng từ khi đăng ký đến nay hoàn toàn không phát sinh dữ liệu, nghi ngờ lỗi luồng cước/profile gói.",
                f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {act_names} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao." + action_suffix,
                "FFF2CC"
            )
        else:
            # Trước đó từng dùng bình thường, chỉ gần đây không thấy data -> Do sóng yếu / máy treo / tắt data
            return (
                "THEO DÕI THÊM",
                f"Thuê bao có gói cước {act_names} (HSD: {act_exp_dates}), lịch sử trước đó vẫn dùng bình thường nhưng ngày gần đây không thấy phát sinh data. Khả năng do khách hàng tắt data, chuyển sang dùng Wifi hoặc thiết bị treo tạm thời.",
                f"Hướng dẫn khách hàng kiểm tra lại dung lượng gói {act_names}, tắt/bật lại dữ liệu di động hoặc khởi động lại thiết bị để tiếp tục theo dõi." + action_suffix,
                "E2EFDA"
            )
    return (
        "KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ",
        f"Lịch sử truy cập ngày gần nhất ({recent_day_str}) gần như không phát sinh lưu lượng sử dụng thực tế (dưới 1MB).",
        "Nghi ngờ do thiết bị của khách hàng bị treo data. Nhờ khách hàng thử tắt/bật thiết bị và data, speedtest lại giúp." + action_suffix,
        "FFF2CC"
    )

def get_scenario_result(scenarios, scenario_id):
    for sc in scenarios:
        if sc["id"] == scenario_id:
            return sc["conclusion"], sc["technical_analysis"], sc["action_plan"], sc["color"]
    return "CHƯA PHÂN LOẠI", "Lỗi cấu hình", "Kiểm tra json", "FFFFFF"


def extract_incident_time(ticket_content, default_created_time=""):
    """
    Trích xuất thời điểm xảy ra sự cố từ nội dung phản ánh hoặc fallback về ngày yêu cầu.
    Ví dụ: 'THỜI ĐIỂM XẢY RA SỰ CỐ: 17/08/2026 18:58' -> '17/08/2026 18:58'
    """
    if ticket_content:
        content_str = str(ticket_content)
        m = re.search(
            r'(?:thời điểm xảy ra sự cố|thời điểm sự cố|thời gian sự cố|thời gian xảy ra sự cố|xảy ra sự cố lúc)[:\s]*([\d]{1,2}[/-][\d]{1,2}[/-][\d]{2,4}(?:\s+[\d]{1,2}:[\d]{1,2}(?::[\d]{1,2})?)?|[\d]{1,2}:[\d]{1,2}(?::[\d]{1,2})?\s+[\d]{1,2}[/-][\d]{1,2}[/-][\d]{2,4})',
            content_str,
            re.IGNORECASE
        )
        if m:
            return m.group(1).strip()

    if default_created_time:
        return str(default_created_time).strip()

    return "Không có thông tin"


def export_diagnostics_to_excel(summary_records, output_filename, start_d=None, end_d=None):
    if not start_d or not end_d:
        now = datetime.now()
        start_d = (now - timedelta(days=4)).strftime("%d%m%Y")
        end_d = now.strftime("%d%m%Y")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Nhận Định Sự Cố"
    ws.views.sheetView[0].showGridLines = True
    # 🔍 THIẾT LẬP ZOOM SCALE 100% ĐỂ VỪA VẶN TRÀN MÀN HÌNH VÀ FONT CHỮ TO RÕ NÉT
    try:
        ws.views.sheetView[0].zoomScale = 100
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpProperties.fitToPage = True
    except Exception:
        pass
    
    # Title Banner - Gộp vùng ô từ A1 đến L1 (12 cột)
    ws.merge_cells("A1:L1")
    title_cell = ws["A1"]
    title_cell.value = "BÁO CÁO PHÂN TÍCH VÀ ĐỀ XUẤT HƯỚNG XỬ LÝ SỰ CỐ THUÊ BAO"
    title_cell.font = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill(start_color="1F497D", fill_type="solid")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 42
    
    # 🎯 DANH SÁCH TIÊU ĐỀ CHUẨN (12 CỘT): Đưa "NHẬN ĐỊNH TÌNH TRẠNG" lên Cột 1 và bổ sung NGÀY TIẾP NHẬN + APP USAGE + TRẠNG THÁI PHIẾU
    headers = [
        "NHẬN ĐỊNH TÌNH TRẠNG", "SỐ ĐIỆN THOẠI (LINK BTOOLS)", "DỊCH VỤ BÁO LỖI", 
        "NGÀY TIẾP NHẬN", "GÓI CƯỚC THỰC TẾ (SAPC & BTOOLS)", "HẠ TẦNG KẾT NỐI", 
        "DỮ LIỆU CEM (TOP 3 CELL)", "ỨNG DỤNG SỬ DỤNG (APP USAGE)", 
        "NỘI DUNG PHẢN ÁNH (TÓM TẮT AI)", "NỘI DUNG PHÂN TÍCH KỸ THUẬT", 
        "NỘI DUNG PHẢN HỒI", "TRẠNG THÁI PHIẾU"
    ]
    header_fill = PatternFill(start_color="2F5597", fill_type="solid")
    thin_border = Border(left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'), top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9'))
    
    ws.row_dimensions[3].height = 38
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_idx, value=h)
        cell.font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
        
    current_row = 4
    for idx, rec in enumerate(summary_records, 1):
        ws.row_dimensions[current_row].height = 140
        
        # 🎯 CỘT 1 (A): NHẬN ĐỊNH TÌNH TRẠNG
        s_cell = ws.cell(row=current_row, column=1, value=rec["status"])
        s_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        s_cell.font = Font(name="Segoe UI", size=11, bold=True, color="333333")
        s_cell.fill = PatternFill(start_color=rec["color"], fill_type="solid")
        
        # 🎯 CỘT 2 (B): SỐ ĐIỆN THOẠI + HYPERLINK BTOOLS
        phone_num = rec["phone"]
        btools_url = f"http://10.159.21.241:9267/B_tools_v2/data_view.jsp?name={phone_num}&start_d={start_d}&end_d={end_d}&submit=T%C3%ACm+Ki%E1%BA%BFm"
        p_cell = ws.cell(row=current_row, column=2, value=phone_num)
        p_cell.hyperlink = btools_url
        p_cell.font = Font(name="Segoe UI", size=11, bold=True, color="0563C1", underline="single")
        p_cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # 🎯 CỘT 3 (C): DỊCH VỤ BÁO LỖI
        ws.cell(row=current_row, column=3, value=rec["package_title"]).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

        # 🎯 CỘT 4 (D): THỜI ĐIỂM XẢY RA SỰ CỐ
        inc_time = rec.get("incident_time") or extract_incident_time(rec.get("ticket_content", ""), rec.get("created_time", ""))
        ws.cell(row=current_row, column=4, value=inc_time).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # 🎯 CỘT 5 (E): GÓI CƯỚC THỰC TẾ (SAPC & BTOOLS)
        ws.cell(row=current_row, column=5, value=rec["real_packages"]).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

        # 🎯 CỘT 6 (F): HẠ TẦNG KẾT NỐI
        ws.cell(row=current_row, column=6, value=rec["rat_types"]).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        
        # 🎯 CỘT 7 (G): DỮ LIỆU CEM (TOP 3 CELL BẮT SÓNG TRONG 5 NGÀY)
        cem_text = rec.get("cem_data", "Không có dữ liệu CEM")
        ws.cell(row=current_row, column=7, value=cem_text).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

        # 🎯 CỘT 8 (H): ỨNG DỤNG SỬ DỤNG (APP USAGE TỪ CEM)
        app_text = rec.get("app_usage", "Không có dữ liệu App Usage")
        ws.cell(row=current_row, column=8, value=app_text).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

        # 🎯 CỘT 9 (I): Ô NỘI DUNG PHẢN ÁNH (TÓM TẮT AI)
        ai_text = rec.get("ai_summary", "null")
        ai_cell = ws.cell(row=current_row, column=9, value=ai_text)
        ai_cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        ai_cell.font = Font(name="Segoe UI", size=10.5, italic=True, color="404040") 
        
        # 🎯 CỘT 10 (J): NỘI DUNG PHÂN TÍCH KỸ THUẬT
        comment_text = rec["comment"]
        c_cell = ws.cell(row=current_row, column=10, value=comment_text)
        c_cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        if "Lưu ý: 2 ngày gần nhất không thấy phát sinh data" in comment_text:
            c_cell.font = Font(name="Segoe UI", size=11, bold=True, color="C00000")
            
        # 🎯 CỘT 11 (K): HƯỚNG XỬ LÝ KHUYÊN DÙNG
        action_text = rec["action_plan"]
        a_cell = ws.cell(row=current_row, column=11, value=action_text)
        a_cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        if "Cần kiểm tra tình trạng thuê bao và gói cước" in action_text:
            a_cell.font = Font(name="Segoe UI", size=11, bold=True, color="C00000")

        # 🎯 CỘT 12 (L): TRẠNG THÁI PHIẾU (ĐÃ ĐÓNG / CHƯA ĐÓNG) & NGƯỜI ĐÓNG
        ticket_st = str(rec.get("ticket_status") or ("Đã đóng" if rec.get("is_closed") else "Chưa đóng")).strip()
        closed_by = str(rec.get("closed_by") or "").strip()
        display_st = f"{ticket_st}\n({closed_by})" if (closed_by and "đã đóng" in ticket_st.lower()) else ticket_st
        st_cell = ws.cell(row=current_row, column=12, value=display_st)
        st_cell.alignment = Alignment(horizontal="center", vertical="center")
        if "đã đóng" in ticket_st.lower():
            st_cell.font = Font(name="Segoe UI", size=11, bold=True, color="006100")
            st_cell.fill = PatternFill(start_color="C6EFCE", fill_type="solid")
        else:
            st_cell.font = Font(name="Segoe UI", size=11, bold=True, color="9C6500")
            st_cell.fill = PatternFill(start_color="FFEB9C", fill_type="solid")
        
        # Vẽ border toàn bộ ô trên hàng (12 cột) và set font size 11
        for c in range(1, 13):
            ws.cell(row=current_row, column=c).border = thin_border
            if c not in [1, 2, 9, 10, 11, 12]: # Chừa các ô có định dạng font đặc biệt
                ws.cell(row=current_row, column=c).font = Font(name="Segoe UI", size=11)
            elif c in [10, 11] and ws.cell(row=current_row, column=c).font.color.rgb not in ["C00000", "00C00000"]:
                ws.cell(row=current_row, column=c).font = Font(name="Segoe UI", size=11)
        current_row += 1
        
    # Thiết lập độ rộng cột tối ưu vừa vặn hiển thị trọn vẹn trên màn hình (12 Cột)
    ws.column_dimensions["A"].width = 24  # Cột nhãn Trạng thái
    ws.column_dimensions["B"].width = 16  # Số điện thoại
    ws.column_dimensions["C"].width = 20  # Dịch vụ báo lỗi
    ws.column_dimensions["D"].width = 20  # Thời điểm sự cố
    ws.column_dimensions["E"].width = 36  # Gói cước thực tế SAPC & BTools
    ws.column_dimensions["F"].width = 15  # Hạ tầng kết nối
    ws.column_dimensions["G"].width = 32  # Dữ liệu CEM (Top 3 Cell)
    ws.column_dimensions["H"].width = 26  # Ứng dụng sử dụng (App Usage)
    ws.column_dimensions["I"].width = 42  # Tóm tắt AI
    ws.column_dimensions["J"].width = 48  # Phân tích kỹ thuật
    ws.column_dimensions["K"].width = 40  # Hướng xử lý
    ws.column_dimensions["L"].width = 16  # Trạng thái phiếu (Đã đóng / Chưa đóng)

    out_dir = os.path.dirname(output_filename)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    try:
        wb.save(output_filename)
        print(f"📊 [XLSX] Đã xuất báo cáo chẩn đoán cấu trúc mới: {output_filename}")
        return output_filename
    except PermissionError:
        backup_name = output_filename.replace(".xlsx", f"_{datetime.now().strftime('%H%M%S')}.xlsx")
        print(f"⚠️ File {output_filename} bị khóa! Đã lưu bản sao: {backup_name}")
        wb.save(backup_name)
        return backup_name