# report_bot.py
import os
import re
import json
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from ai_interpreter import analyze_ticket_with_ai
# Gọi bộ não kịch bản từ file độc lập vừa tách
from scenarios_engine import match_diagnostic_scenarios, is_throttled_service_code, get_throttled_speed_desc

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


def extract_btools_packages_summary(clean_btools_data, excluded_codes=None, days=5):
    """
    Trích xuất danh sách gói cước từ BTools kèm dung lượng phiên lớn nhất (max session) trong N ngày gần nhất (mặc định 5 ngày).
    Ví dụ: 'BIG(max 10MB), TIKTOK(max 5.2MB), MoMo(max 1.5MB), DIP_Youtube (dùng thống kê Youtube data IP) (max 0.8MB)'
    """
    if not clean_btools_data or not isinstance(clean_btools_data, list):
        return "Không phát sinh gói TM"

    start_date_filter = None
    if days:
        start_date_filter = (datetime.now() - timedelta(days=days - 1)).date()

    if excluded_codes is None:
        cfg_p = os.path.join(os.path.dirname(__file__), "diagnostic_config.json")
        excluded_codes = set()
        if os.path.exists(cfg_p):
            try:
                with open(cfg_p, "r", encoding="utf-8") as cf:
                    excluded_codes = set(json.load(cf).get("EXCLUDED_SYSTEM_CODES", []))
            except Exception:
                pass

    pkg_max_mb = {}
    for r in clean_btools_data:
        if not isinstance(r, dict):
            continue
        if start_date_filter:
            t_str = r.get("RECORD_OPENING_TIME", "")
            if t_str:
                try:
                    r_date = datetime.strptime(t_str.split()[0], "%d/%m/%Y").date()
                    if r_date < start_date_filter:
                        continue
                except Exception:
                    pass
        sc = str(r.get("SERVICE_ID_CODE", "") or r.get("SERVICE_ID", "")).strip()
        sn = str(r.get("SERVICE_NAME", "")).strip()
        sc_lower = sc.lower()
        if not sc_lower or sc_lower in excluded_codes or sc_lower in ("null", "none"):
            continue

        sn_lower = sn.lower()
        if sn and "gói cước lạ" not in sn_lower and sn_lower not in excluded_codes and sn_lower not in ("null", "none"):
            pkg_name = sn
        elif sc_lower not in ("null", "none"):
            pkg_name = sc
        else:
            continue

        try:
            dl = float(r.get("DATA_VOLUME_DOWNLINK") or 0)
            ul = float(r.get("DATA_VOLUME_UPLINK") or 0)
            session_mb = (dl + ul) / (1024 * 1024)
        except Exception:
            session_mb = 0.0

        if pkg_name not in pkg_max_mb or session_mb > pkg_max_mb[pkg_name]:
            pkg_max_mb[pkg_name] = session_mb

    if not pkg_max_mb:
        return "Không phát sinh gói TM"

    def _fmt_mb(mb):
        if mb >= 1024:
            gb = mb / 1024
            return f"{gb:.1f}GB" if round(gb, 1) != int(round(gb, 1)) else f"{int(round(gb))}GB"
        if mb >= 10:
            return f"{mb:.1f}MB" if round(mb, 1) != int(round(mb, 1)) else f"{int(round(mb))}MB"
        if mb >= 1:
            return f"{mb:.1f}MB" if round(mb, 1) != int(round(mb, 1)) else f"{int(round(mb))}MB"
        if mb > 0:
            if mb < 0.05:
                return "<0.1MB"
            return f"{mb:.1f}MB"
        return "0MB"

    sorted_pkgs = sorted(pkg_max_mb.items(), key=lambda x: (-x[1], x[0]))

    parts = []
    for name, max_mb in sorted_pkgs:
        val_str = _fmt_mb(max_mb)
        if name.endswith(")"):
            parts.append(f"{name} (max {val_str})")
        else:
            parts.append(f"{name}(max {val_str})")

    return ", ".join(parts)


def refine_btools_with_sapc(btools_str: str, sapc_packages: list) -> str:
    """
    Rút gọn các nhóm gói BTools dài ngoằng (ví dụ: BIG (VD120M, VD89, D159V...))
    thành đúng tên gói của khách hàng nếu khách hàng đang sử dụng gói đó trên SAPC.
    Chỉ khi khách hàng không có gói hoặc không khớp gói nào thì mới giữ nguyên để KTV phán đoán.
    """
    if not btools_str or not sapc_packages or not isinstance(sapc_packages, list):
        return btools_str

    # Lấy danh sách tên gói cước từ SAPC (bỏ M0, Pay As You Go)
    sapc_names = []
    for p in sapc_packages:
        n = ""
        if isinstance(p, dict):
            n = (p.get("package_name") or p.get("group_name") or "").upper().strip()
        elif isinstance(p, str):
            n = p.upper().strip()
        if n and "PAYGO" not in n and n != "M0":
            clean_n = n.split("(")[0].replace("•", "").strip()
            if clean_n:
                sapc_names.append(clean_n)

    if not sapc_names:
        return btools_str

    def _replace_group(match):
        full_match = match.group(0)
        group_name = match.group(1)
        inner_content = match.group(2)
        max_part = match.group(3) if len(match.groups()) >= 3 and match.group(3) else ""

        # Chỉ xử lý nếu trong ngoặc là danh sách phân tách bằng dấu phẩy hoặc có chấm lửng
        if "," not in inner_content and "..." not in inner_content:
            return full_match

        # Tách danh sách ứng viên trong ngoặc
        raw_candidates = re.split(r'[,;/]', inner_content)
        candidates = []
        for c in raw_candidates:
            clean_c = re.sub(r'[\.\.\.\(\)]', '', c).strip()
            if clean_c and len(clean_c) >= 2 and clean_c.upper() not in ("GÓI", "DATA", "NGÀY", "TUẦN", "THÁNG"):
                candidates.append(clean_c)

        # Sắp xếp candidate dài trước ngắn sau
        candidates.sort(key=lambda x: -len(x))

        matched_cand = None
        for cand in candidates:
            cand_upper = cand.upper()
            for s_name in sapc_names:
                if cand_upper in s_name:
                    matched_cand = cand
                    break
                s_core = re.sub(r'^(MI_|DC_|KM_|D_)', '', s_name)
                if cand_upper in s_core or s_core.startswith(cand_upper):
                    matched_cand = cand
                    break
            if matched_cand:
                break

        # Nếu không khớp candidate con, kiểm tra tên nhóm (VD: BIG khớp với BIGKM_6GBN)
        if not matched_cand and group_name:
            grp_upper = group_name.upper()
            for s_name in sapc_names:
                s_core = re.sub(r'^(MI_|DC_|KM_|D_)', '', s_name)
                if s_core.upper().startswith(grp_upper) or grp_upper in s_core.upper():
                    matched_cand = s_core
                    break
            if not matched_cand and len(sapc_names) == 1:
                s_core = re.sub(r'^(MI_|DC_|KM_|D_)', '', sapc_names[0])
                matched_cand = s_core

        if matched_cand:
            return f"{matched_cand}{max_part}"
        return full_match

    pattern = r'([A-Za-z0-9_]+)\s*\(([^)]+)\)(\s*\(max\s*[^)]+\))?'
    refined = re.sub(pattern, _replace_group, btools_str)

    return refined


def get_formatted_sapc_packages(phone_84, fallback_btools=""):
    """
    Đọc toàn bộ hồ sơ thuê bao (Radio, HSS Profile, IPv4), gói cước từ SAPC
    và kết hợp với gói thực tế từ BTools.
    Hiển thị đầy đủ cả hồ sơ Core và gói cước trong bảng.
    """
    if isinstance(fallback_btools, list):
        fallback_btools = extract_btools_packages_summary(fallback_btools)
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
                cell_name = str(sub_info.get("CellName") or sub_info.get("cell_name") or sub_info.get("current_cell") or "").strip()
                hss_prof = str(sub_info.get("HSS Profile") or "").strip()
                ipv4 = str(sub_info.get("IPv4") or "").strip()
                nam_val = str(sub_info.get("NAM") if sub_info.get("NAM") is not None else "").strip()

                sub_tags = []
                if radio and radio.lower() != "none":
                    if cell_name:
                        sub_tags.append(f"Radio: {radio}, {cell_name}")
                    else:
                        sub_tags.append(f"Radio: {radio}")
                elif cell_name:
                    sub_tags.append(f"Radio: 4G, {cell_name}")
                if hss_prof:
                    hss_digits = re.sub(r'\D', '', hss_prof)
                    is_strange = len(hss_digits) >= 3 and (ipv4.startswith("113.") or ipv4.startswith("172.") or ipv4.startswith("192.168."))
                    if is_strange:
                        sub_tags.append(f"HSS: {hss_prof} (PROFILE LẠ)")
                    else:
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

    # Dự phòng: Bóc tách gói từ nội dung phản ánh / AI Summary trong tickets.db nếu SAPC chưa có gói
    if not packages:
        try:
            import sqlite3
            db_path = os.path.join(os.path.dirname(__file__), "tickets.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path, timeout=3)
                c = conn.cursor()
                clean_9 = re.sub(r'\D', '', str(phone_84))[-9:]
                c.execute("SELECT ai_summary, ticket_content, package_title FROM tickets WHERE phone LIKE ? ORDER BY updated_at DESC LIMIT 1", (f"%{clean_9}%",))
                row = c.fetchone()
                conn.close()
                if row:
                    ai_sum, t_cont, pkg_title = str(row[0] or ""), str(row[1] or ""), str(row[2] or "")
                    detected_pkg = ""
                    # 1. Từ ai_summary: '1. Gói cước sử dụng: <tên_gói>'
                    m_ai = re.search(r'1\.\s*Gói\s*cước\s*sử\s*dụng\s*:\s*([^\n\r]+)', ai_sum, re.IGNORECASE)
                    if m_ai:
                        val = m_ai.group(1).strip()
                        if val and not any(k in val.lower() for k in ["không đề cập", "không có", "chưa kiểm tra", "chưa đăng ký", "m0", "paygo"]):
                            detected_pkg = val
                    # 2. Từ ticket_content nếu chưa có
                    if not detected_pkg:
                        m_tc = re.search(r'(?:dùng gói|gói cước|gói)\s*[:=]\s*([A-Za-z0-9_]+)', t_cont, re.IGNORECASE)
                        if m_tc:
                            val = m_tc.group(1).strip()
                            if val and not any(k in val.lower() for k in ["không", "m0", "paygo"]):
                                detected_pkg = val

                    if detected_pkg:
                        packages = [{"package_name": detected_pkg, "register_date": "", "expire_date": ""}]
                        sapc_lines.append(f"• {detected_pkg} (Ghi nhận từ PAKH)")
        except Exception:
            pass

    # Xây dựng chuỗi hiển thị kết hợp cả hồ sơ và gói cước
    result_parts = []
    if profile_parts:
        result_parts.extend(profile_parts)

    if sapc_lines:
        result_parts.append("SAPC:\n" + "\n".join(sapc_lines))
    else:
        result_parts.append("SAPC: Không có gói")

    btools_val = str(fallback_btools).strip() if fallback_btools else "Không phát sinh gói TM"
    if btools_val and btools_val != "Không phát sinh gói TM":
        btools_val = refine_btools_with_sapc(btools_val, packages)
    result_parts.append(f"BTools: {btools_val}")

    return "\n\n".join(result_parts)


def get_sapc_package_validity(phone_84, incident_time_str=None):
    """
    Phân loại chi tiết các gói cước của thuê bao từ SAPC:
    Trả về: (active_packages, expired_packages)
    Mỗi phần tử là dict chứa name, reg_str, exp_str, reg_dt, exp_dt, is_no_date, is_paygo, is_home.

    Quy chuẩn nghiệp vụ (Chuẩn Viễn Thông VNPT):
    - Nếu có incident_time_str (ngày tiếp nhận phản ánh):
      Gói cước chỉ được coi là HẾT HẠN nếu thời hạn sử dụng < ngày tiếp nhận phản ánh.
      Nếu thời hạn sử dụng >= ngày tiếp nhận phản ánh (kể cả khi < thời gian hiện tại),
      gói cước VẪN CÒN HẠN tại thời điểm phản ánh -> xếp vào active_packages.
    - Nếu không có incident_time_str:
      So sánh với ngày hiện tại (exp_dt.date() < now.date()).
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
        ref_date = now.date()
        if incident_time_str:
            try:
                for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        ref_date = datetime.strptime(str(incident_time_str).strip(), fmt).date()
                        break
                    except ValueError:
                        pass
            except Exception:
                ref_date = now.date()

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

            pkg_name_upper = pkg_name.upper()
            is_home = "home" in pkg_name.lower()
            is_paygo = "paygo" in pkg_name.lower() or pkg_name.lower() == "m0"

            addon_keywords = ("DE-FREE", "DE_FREE", "ZALO", "BAOMOI", "ZINGMP3", "KM5GZONE", "NHOM3DICHVU", "TIKTOK", "YOUTUBE", "MYTV")
            is_addon_app = any(k in pkg_name_upper for k in addon_keywords) or pkg_name_upper.startswith("ODA_") or "GAME" in pkg_name_upper

            # Trường hợp đặc biệt: Gói PAYGO hoặc gói hoàn toàn không có ngày tháng
            if is_paygo:
                active_packages.append({
                    "name": pkg_name,
                    "group_name": pkg.get("group_name") or "",
                    "reg_str": "Chưa có thông tin",
                    "exp_str": "Gói mặc định Pay As You Go",
                    "reg_dt": None,
                    "exp_dt": None,
                    "is_no_date": True,
                    "is_paygo": True,
                    "is_addon_app": False,
                    "is_home": False
                })
                continue

            if not exp_str and not reg_str:
                desc = "Gói tích hợp Home (Không có thông tin ngày)" if is_home else "Không có thông tin ngày ĐK/HSD"
                active_packages.append({
                    "name": pkg_name,
                    "group_name": pkg.get("group_name") or "",
                    "reg_str": "Chưa có thông tin",
                    "exp_str": desc,
                    "reg_dt": None,
                    "exp_dt": None,
                    "is_no_date": True,
                    "is_paygo": False,
                    "is_addon_app": is_addon_app,
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
                "group_name": pkg.get("group_name") or "",
                "reg_str": reg_display,
                "exp_str": exp_display,
                "reg_dt": reg_dt,
                "exp_dt": exp_dt,
                "is_no_date": False,
                "is_paygo": False,
                "is_addon_app": is_addon_app,
                "is_home": is_home
            }

            # Quy chuẩn: Hết hạn khi và chỉ khi exp_dt.date() < ref_date (ngày tiếp nhận phản ánh)
            if exp_dt and exp_dt.date() < ref_date:
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
    "1.1.1.1", "warp", "vpn", "expressvpn", "nordvpn", "openvpn",
    "wireguard", "betternet", "turbo vpn", "supervpn", "surfshark", "psiphon",
    "adguard vpn", "adguard", "v2ray", "shadowsocks", "outline", "speedify", "tunnelbear",
    "hotspot shield", "windscribe", "protonvpn", "hide.me", "cyberghost"
]

def detect_vpn_application(app_events, target_date=None):
    """
    Kiểm tra xem trong dữ liệu App Usage của CEM có xuất hiện ứng dụng VPN / 1.1.1.1 / Cloudflare không.
    Nếu có target_date: Chỉ lọc các bản ghi ứng dụng phát sinh trong đúng ngày đó.
    Trả về tên app VPN phát hiện được, hoặc None.
    """
    if not app_events:
        return None
        
    target_date_strs = set()
    if target_date:
        if isinstance(target_date, str):
            t_clean = target_date.strip().split(" ")[0].replace("/", "-")
            target_date_strs.add(t_clean)
            parts = t_clean.split("-")
            if len(parts) == 3:
                if len(parts[0]) == 4: # yyyy-mm-dd
                    target_date_strs.add(f"{parts[2]}-{parts[1]}-{parts[0]}")
                    target_date_strs.add(f"{parts[2]}/{parts[1]}/{parts[0]}")
                elif len(parts[2]) == 4: # dd-mm-yyyy
                    target_date_strs.add(f"{parts[2]}-{parts[1]}-{parts[0]}")
                    target_date_strs.add(f"{parts[0]}/{parts[1]}/{parts[2]}")
        elif hasattr(target_date, "strftime"):
            target_date_strs.add(target_date.strftime("%Y-%m-%d"))
            target_date_strs.add(target_date.strftime("%d/%m/%Y"))
            target_date_strs.add(target_date.strftime("%d-%m-%Y"))

    def _matches_target_date(item_dict):
        if not target_date_strs:
            return True
        item_d = str(item_dict.get("_query_date") or item_dict.get("date") or item_dict.get("day") or item_dict.get("time") or "").strip().split(" ")[0].replace("/", "-")
        if not item_d:
            return True  # Nếu bản ghi không gắn date metadata thì vẫn xem xét
        return any(td in item_d or item_d in td for td in target_date_strs)

    app_names = set()
    if isinstance(app_events, dict):
        data_list = app_events.get("data", [])
        if isinstance(data_list, list):
            for h in data_list:
                if isinstance(h, dict) and not _matches_target_date(h):
                    continue
                for item in h.get("top_list", []):
                    app_name = str(item.get("up_application") or "").strip().lower()
                    if app_name:
                        app_names.add(app_name)
    elif isinstance(app_events, list):
        for item in app_events:
            if isinstance(item, dict):
                if not _matches_target_date(item):
                    continue
                # Trường hợp 1: item là hour-bucket với top_list bên trong
                top_list = item.get("top_list")
                if isinstance(top_list, list):
                    for sub_item in top_list:
                        if isinstance(sub_item, dict):
                            app_name = str(sub_item.get("up_application") or sub_item.get("app_name") or sub_item.get("name") or "").strip().lower()
                            if app_name:
                                app_names.add(app_name)
                else:
                    # Trường hợp 2: item trực tiếp có up_application
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
                if kw in ("1.1.1.1", "cloudflare", "warp"):
                    return "Warp"
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


def extract_packages_from_text(text):
    """
    Bóc tách danh sách tất cả các gói cước từ nội dung text (AI summary, ticket_content, package_title).
    Ví dụ: 'Gói cước: HOME_KN, VD120N' -> ['HOME_KN', 'VD120N']
           'gói VD120 và gói D5' -> ['VD120', 'D5']
    """
    if not text:
        return []
    pkgs = []
    # 1. Tìm sau nhãn 'gói cước:' hoặc 'gói:'
    m = re.findall(r'(?:gói(?:\s+(?:cước|data))?[:\s]+)([A-Za-z0-9_, -]+?)(?=(?:\n|\.|\b(?:tình trạng|lỗi|khi|không|từ|ngày|lưu lượng|thuê bao)\b|$))', text, flags=re.IGNORECASE)
    for chunk in m:
        for p in re.split(r'[,;\s+và/]+', chunk):
            p_clean = p.strip().upper()
            if p_clean and len(p_clean) >= 2 and p_clean not in ['KHÔNG', 'KHONG', 'NULL', 'NONE', 'CHƯA', 'CHUA', 'CƯỚC', 'DATA', 'SỬ', 'DỤNG']:
                if p_clean not in pkgs:
                    pkgs.append(p_clean)
    # 2. Tìm theo pattern tên gói phổ biến
    m2 = re.findall(r'\b(vd\d+[a-z]*|d\d+[a-z]*|big\d*[a-z0-9_]*|yolo\d+[a-z]*|thaga\d*[a-z]*|mim\d+[a-z]*|home[a-z0-9_]*|td\d+|dt\d+|sg120|vocuc|d159[a-z]*)\b', text, flags=re.IGNORECASE)
    for p in m2:
        p_clean = p.strip().upper()
        if p_clean not in pkgs:
            pkgs.append(p_clean)
    return pkgs


def get_expected_service_codes_for_pkg(pkg_name, group_name=None):
    """
    Xác định mã Service ID dự kiến của gói cước để đối chiếu với BTools.
    Hỗ trợ một gói có thể có nhiều Service ID (ví dụ: mã chính, mã phụ, mã hạ băng thông).
    Nếu gói không có trong serviceid.json (VD120, VD89, THAGA...), tự động lấy mã từ Group Name SAPCCheck (ví dụ: Group Name: 3000).
    """
    codes = set()
    if group_name:
        g_clean = str(group_name).strip()
        digits = re.sub(r'\D', '', g_clean)
        if digits:
            codes.add(digits)
            codes.add(digits.lstrip("0") or "0")
            codes.add(digits.zfill(10))

    if not pkg_name:
        return codes

    p_clean = pkg_name.strip().upper()

    # Nhóm HOME / Gia đình / GD / OCSE
    if "HOME" in p_clean or "GD" in p_clean or "GIA DINH" in p_clean or "GIADINH" in p_clean or "OCSE" in p_clean:
        codes.update({"5000", "0000005000", "6000", "0000006000", "3605", "0000003605", "9301", "0000009301", "10002", "0000010002", "10003", "0000010003"})

    # Nhóm VD (VD120, VD120N, VD90, VD150, VD89...)
    if "VD" in p_clean:
        if p_clean in ["VD2", "VD2K"]:
            codes.update({"3001", "0000003001"})
        else:
            codes.update({"3000", "0000003000", "3601", "0000003601", "3602", "0000003602"})

    # Nhóm BIG (BIG, BIG70, BIG90, BIG120, ODA_BIG_OCS...)
    if "BIG" in p_clean:
        codes.update({"3000", "0000003000", "3601", "0000003601", "3602", "0000003602", "3603", "0000003603", "6000", "0000006000"})

    # Nhóm YOLO / D159 / D159V
    if "YOLO" in p_clean or "D159" in p_clean:
        codes.update({"3000", "0000003000"})

    # Nhóm Tiêu dùng TD (TD3, TD5, TD49...)
    if "TD" in p_clean or re.search(r'\bTD\d+\b', p_clean):
        codes.update({"3600", "0000003600", "8301", "0000008301"})

    # Nhóm gói ngày D5, D7, D15, FIM, P1-P4
    if any(re.search(rf'\b{d}\b', p_clean) or p_clean.startswith(d) for d in ["D5", "D7", "D15", "FIM", "P1", "P2", "P3", "P4"]):
        codes.update({"3632", "0000003632"})

    # Nhóm D3, 3D5, VX3
    if "D3" in p_clean or "3D5" in p_clean or "VX3" in p_clean:
        codes.update({"3622", "0000003622"})

    # Nhóm DT20, DT30, VX7
    if "DT" in p_clean or "VX7" in p_clean:
        codes.update({"3623", "0000003623"})

    # Nhóm D1PLUS - D10PLUS
    if "PLUS" in p_clean and "D" in p_clean:
        codes.update({"8604", "0000008604"})

    # Nhóm THAGA (THAGA70, THAGA70N, THAGA60, THAGA90... dùng nền BIG 3000 hoặc 3001)
    if "THAGA" in p_clean or "THẢ GA" in p_clean:
        codes.update({"3000", "0000003000", "3001", "0000003001", "2902", "2910", "2917"})
    elif any(k in p_clean for k in ["M0", "PAYGO"]):
        codes.update({"3001", "0000003001"})

    # Nhóm SG120, VOCUC
    if "SG120" in p_clean or "VOCUC" in p_clean:
        codes.update({"5800", "0000005800", "3000", "0000003000"})

    # Nhóm gói mở rộng X, X1, X2 (mua thêm data khi hết data gói chính / HOME)
    if p_clean in ["X", "X1", "X2"] or p_clean.startswith("X_") or "X(" in p_clean or "X (" in p_clean or "HOMED" in p_clean:
        codes.update({"6000", "0000006000", "4000", "0000004000", "9301", "0000009301"})

    # Nhóm MAX, THMAX
    if "MAX" in p_clean:
        codes.update({"5500", "0000005500"})

    # Tra cứu bổ sung từ serviceid.json
    try:
        cfg_p = os.path.join(os.path.dirname(__file__), "serviceid.json")
        if os.path.exists(cfg_p):
            with open(cfg_p, "r", encoding="utf-8") as f:
                svc_dict = json.load(f)
            tokens = [t for t in re.split(r'[^A-Za-z0-9]+', p_clean) if len(t) >= 2]
            for code, desc in svc_dict.items():
                desc_upper = desc.upper()
                if p_clean in desc_upper or any(t in desc_upper for t in tokens if len(t) >= 3):
                    codes.add(code)
                    codes.add(code.lstrip("0"))
    except Exception:
        pass

    return codes


def check_core_profile_failure(sub_info):
    """
    Kiểm tra các lỗi hồ sơ mạng lõi Core (NAM, HSS Profile chưa khai báo, HSS Profile lạ).
    Được gọi khi BTools xác nhận khách hàng gặp sự cố / không dùng được dữ liệu.
    Độ ưu tiên:
    1. Cờ NAM = 1 (Bị khóa GPRS)
    2. HSS Profile chưa khai báo (rỗng / None / "") -> CHƯA KHAI BÁO PROFILE 4G
    3. HSS Profile lạ: BẮT BUỘC thỏa mãn điều kiện AND:
       Profile >= 3 chữ số VÀ IPv4 bắt đầu bằng 113., 172. hoặc 192.168.
    """
    if not sub_info or not isinstance(sub_info, dict):
        return None

    # 1. Khóa GPRS (NAM = 1)
    nam_val = str(sub_info.get("NAM") if sub_info.get("NAM") is not None else "").strip()
    if nam_val == "1":
        return (
            "BỊ KHÓA GPRS",
            "Thuê bao đang bị khóa GPRS (cờ NAM = 1 trên Core).",
            "Nhờ VNP khai báo lại GPRS cho Khách hàng.",
            "FFF2CC"
        )

    # 2. HSS Profile chưa khai báo (rỗng / None / "")
    hss_profile = str(sub_info.get("HSS Profile") or "").strip()
    if not hss_profile or hss_profile.lower() in ("none", "null", ""):
        return (
            "CHƯA KHAI BÁO PROFILE 4G",
            "Kiểm tra trên hệ thống HSS Core, thuê bao chưa được mở profile dịch vụ 4G LTE, thiết bị chỉ kết nối được sóng 2G/3G hoặc không truy cập được dữ liệu.",
            "Chuyển bộ phận IT/Khai thác mạng kiểm tra, bổ sung kích hoạt profile 4G cho thuê bao trên hệ thống.",
            "FCE4D6"
        )

    # 3. HSS Profile lạ: Điều kiện AND (Profile >= 3 chữ số VÀ IPv4 bắt đầu bằng 113., 172. hoặc 192.168.)
    hss_digits = re.sub(r'\D', '', hss_profile)
    ipv4_val = str(sub_info.get("IPv4") or sub_info.get("IP") or "").strip()
    is_ip_captured = ipv4_val.startswith("113.") or ipv4_val.startswith("172.") or ipv4_val.startswith("192.168.")
    
    if len(hss_digits) >= 3 and is_ip_captured:
        return (
            "PROFILE LẠ",
            f"Phát hiện HSS Profile lạ ({hss_profile}), IP: {ipv4_val}.",
            "Chuyển IT kiểm tra khai báo lại HSS Profile cho khách hàng.",
            "FFC7CE"
        )

    return None


def is_explicit_5g_complaint(package_title: str, ticket_content: str) -> bool:
    """
    Phân biệt chính xác giữa:
    - Phản ánh THỰC SỰ về sự cố mạng 5G: 'không dùng được 5G', 'có 5G nhưng không dùng được', 'mất sóng 5G', 'không bắt được 5G'...
    - VỚI việc chỉ mô tả trạng thái hiển thị sóng trên máy hoặc dòng máy: 'máy hiển thị sóng 5G', 'máy có sóng: 5G', 'iphone 14 5G'...
      khi KH thực chất đang báo không dùng được data/mạng chung.
    """
    pkg = str(package_title or "").lower()
    content = str(ticket_content or "").lower()
    full_text = f"{pkg} {content}"

    # 1. Loại bỏ các cụm dung lượng (5GB, 1.5GB, 5G/ngày, 5G/tháng...)
    cleaned = re.sub(r'\b\d+([.,]\d+)?\s*(gb|mb|giga|tb)\b', ' ', full_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'\d+([.,]\d+)?(gb|mb)\b', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b\d+[.,]\d+\s*g\b', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b\d+\s*g\s*/\s*(?:ngày|tháng|ngay|thang|day|thg)\b', ' ', cleaned, flags=re.IGNORECASE)

    # Nếu sau khi loại bỏ dung lượng hoàn toàn không có chữ '5g' -> False
    if not re.search(r'(?<![0-9a-zA-Z.])5g(?![0-9a-zA-Z])', cleaned, flags=re.IGNORECASE):
        return False

    # 2. Các mẫu phản ánh ĐÍCH DANH sự cố 5G:
    # a) KH phản ánh không dùng được 5G / không truy cập được 5G
    p_cant_use = r'(?:không|chưa|ko|k)\s+(?:dùng|dung|sử\s*dụng|sd|truy\s*cập|vào|kết\s*nối|xài)\s+(?:được\s+)?(?:mạng\s+|dịch\s*vụ\s+)?5g\b'
    p_cant_use_alt = r'không\s+thể\s+(?:dùng|sử\s*dụng|truy\s*cập|kết\s*nối)\s+(?:mạng\s+)?5g\b'

    # b) Có 5G nhưng không dùng được / Có sóng 5G nhưng không dùng được
    p_have_but = r'có\s+(?:sóng\s+)?5g\s+(?:nhưng|mà|song)\s+(?:không|ko|chưa|k)\s+(?:dùng|dung|sử\s*dụng|sd|xài)\s+được'

    # c) Mất sóng 5G / Không có sóng 5G / Không bắt được 5G / Không lên được 5G / Về 3G
    p_signal = r'(?:mất|thiếu|yếu|chập\s*chờn|không\s*có|ko\s*có|chưa\s*có)\s+sóng\s+5g\b'
    p_nocatch = r'(?:không|ko|chưa)\s+(?:bắt|lên|nhận|thấy|tìm\s+thấy|có|hiện)\s+(?:được\s+)?(?:sóng\s+)?5g\b'
    p_only4g = r'(?:chỉ|chi)\s+(?:lên|bắt|nhận|hiện)\s+(?:được\s+)?(?:4g|3g|2g|lte|h\+?)\s+.*?(?:không|ko|chưa)\s+(?:lên|bắt|thấy)?\s*5g\b'
    p_was5g = r'bình\s*thường\s+(?:lên|có)\s+5g\s+nhưng\s+.*?(?:chỉ|về)\s+(?:3g|4g|2g)\b'

    # d) Lỗi / Chậm / Lag riêng cho dịch vụ hoặc mạng 5G
    p_err = r'(?:lỗi|sự\s*cố|hỏng)\s+(?:mạng\s+|dịch\s*vụ\s+|sóng\s+)?5g\b'
    p_slow = r'\b5g\s+(?:bị\s+)?(?:lỗi|sự\s*cố|hỏng|chậm|lag|chập\s*chờn|yếu|rớt)\b'
    p_net_bad = r'(?:mạng|dịch\s*vụ|sóng)\s+5g\s+(?:bị\s+)?(?:chậm|lag|yếu|kém|chập\s*chờn|rớt|không\s*ổn\s*định)\b'

    # e) Đăng ký gói 5G nhưng không dùng được mạng 5G
    p_pkg = r'(?:đăng\s*ký|đk|mua|gói\s+cước|gói)\s+5g\s+.*?(?:không|ko|chưa)\s+(?:dùng|sd|sử\s*dụng|vào)\s+được\s+(?:mạng\s+)?5g\b'

    patterns = [p_cant_use, p_cant_use_alt, p_have_but, p_signal, p_nocatch, p_only4g, p_was5g, p_err, p_slow, p_net_bad, p_pkg]
    return any(bool(re.search(p, cleaned, flags=re.IGNORECASE)) for p in patterns)


def detect_device_category(ticket_content="", ai_summary=""):
    """
    Phân loại thiết bị người dùng sử dụng từ nội dung phản ánh hoặc tóm tắt AI:
    - Trả về: (category, device_display_name)
      category: 'uncommon' | 'common' | 'unknown'
      device_display_name: chuỗi tên thiết bị hiển thị
    """
    raw_text = f"{ticket_content} {ai_summary}".strip()
    text_lower = raw_text.lower()

    # Bóc tách tên thiết bị cụ thể nếu có trường KH dùng Máy: ...
    m_dev = re.search(
        r'(?:KH dùng Máy|Dòng máy|Thiết bị sử dụng|Thiết bị|Loại máy|Máy sử dụng|Máy)[:\s]*([^\n,;]+)', 
        raw_text, 
        re.IGNORECASE
    )
    extracted_dev = m_dev.group(1).strip() if m_dev else ""
    
    # Lọc bỏ từ nối hoặc thông tin rác phía sau tên máy nếu có
    STOP_WORDS = [
        "không vào được", "khong vao duoc", "không được", "khong duoc", "mạng", "mang", 
        "chậm", "cham", "yếu", "yeu", "lag", "lỗi", "loi", "chập chờn", "chap chon", 
        "rớt", "rot", "truy cập báo", "truy cap bao", "máy có sóng", "sóng", "bật dldđ", 
        "đã thao tác", "chọn mạng", "xóa cache", "reset gprs"
    ]
    for sw in STOP_WORDS:
        if sw in extracted_dev.lower():
            idx = extracted_dev.lower().find(sw)
            extracted_dev = extracted_dev[:idx].strip()

    if any(trash in extracted_dev.lower() for trash in ["không rõ", "ko ro", "lúc 4g", "không có"]):
        extracted_dev = ""

    # 1. Các nhóm thiết bị KHÔNG THÔNG DỤNG (Ô tô, Wifi/Router, Huawei/LG, POS/Đồng hồ, Camera...)
    UNCOMMON_KEYWORDS = [
        # Thiết bị ô tô / xe hơi
        ("màn hình ô tô", "màn hình ô tô"),
        ("đầu máy ô tô", "đầu máy ô tô"),
        ("đầu máy màn hình", "đầu máy màn hình ô tô"),
        ("đầu máy", "đầu máy ô tô"),
        ("màn hình xe", "màn hình xe hơi"),
        ("ô tô", "thiết bị ô tô"),
        ("o to", "thiết bị ô tô"),
        ("xe hơi", "thiết bị xe hơi"),
        ("xe hoi", "thiết bị xe hơi"),
        ("android box", "Android Box ô tô"),
        ("tẩu sim", "tẩu SIM ô tô"),
        ("dvd", "đầu DVD ô tô"),
        ("camera hành trình", "camera hành trình"),
        
        # Thiết bị phát Wi-Fi / Router / Dcom / Modem
        ("phát wifi", "bộ phát Wi-Fi"),
        ("phat wifi", "bộ phát Wi-Fi"),
        ("bắt wifi", "thiết bị bắt Wi-Fi"),
        ("bat wifi", "thiết bị bắt Wi-Fi"),
        ("cục phát", "cục phát Wi-Fi"),
        ("cuc phat", "cục phát Wi-Fi"),
        ("router", "Router 4G"),
        ("modem", "Modem 4G"),
        ("dcom", "Dcom 4G"),
        ("usb 3g", "USB 3G/4G"),
        ("usb 4g", "USB 4G"),
        ("cpe", "thiết bị CPE"),

        # Các dòng máy đặc thù / kén sóng / nội địa / xách tay
        ("huawei", "máy Huawei"),
        ("honor", "máy Honor"),
        ("lg", "máy LG"),
        ("sony", "máy Sony"),
        ("zte", "máy ZTE"),
        ("meizu", "máy Meizu"),
        ("coolpad", "máy Coolpad"),
        ("blackberry", "máy BlackBerry"),
        ("htc", "máy HTC"),
        ("xách tay", "máy xách tay"),
        ("nội địa", "máy nội địa"),
        ("khóa mạng", "máy lock"),
        ("bản lock", "máy lock"),

        # Thiết bị IoT / POS / Đồng hồ / Camera
        ("máy pos", "máy POS"),
        ("đồng hồ", "đồng hồ thông minh"),
        ("dong ho", "đồng hồ thông minh"),
        ("smartwatch", "smartwatch"),
        ("định vị", "thiết bị định vị"),
        ("dinh vi", "thiết bị định vị"),
        ("camera", "camera 4G")
    ]

    for kw, label in UNCOMMON_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            display_name = extracted_dev or label
            return "uncommon", display_name

    # 2. Thiết bị THÔNG DỤNG (iPhone, Samsung, Oppo, Xiaomi, Vivo, Realme...)
    COMMON_KEYWORDS = [
        "iphone", "apple", "ipad", "samsung", "galaxy", "oppo", 
        "xiaomi", "redmi", "vivo", "realme", "poco", "oneplus", "infinix", "tecno"
    ]
    for kw in COMMON_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            display_name = extracted_dev or kw.capitalize()
            return "common", display_name

    return "unknown", extracted_dev or "thiết bị"


def extract_island_special_zone(ticket_content="", package_title="", address=""):
    """
    Nhận diện xem thuê bao có thuộc khu vực Đặc khu / Biển đảo đặc thù khó cải thiện không.
    Trả về tên địa danh biển đảo nếu khớp, ngược lại trả về None.
    """
    raw_text = f"{ticket_content} {package_title} {address}".lower()
    ISLAND_ZONES = [
        ("đặc khu phú quốc", "Đặc khu Phú Quốc"),
        ("phú quốc", "Đặc khu Phú Quốc"),
        ("phu quoc", "Đặc khu Phú Quốc"),
        ("hòn thơm", "Hòn Thơm (Phú Quốc)"),
        ("hon thom", "Hòn Thơm (Phú Quốc)"),
        ("an thới", "An Thới (Phú Quốc)"),
        ("dương tơ", "Dương Tơ (Phú Quốc)"),
        ("dương đông", "Dương Đông (Phú Quốc)"),
        ("bãi thơm", "Bãi Thơm (Phú Quốc)"),
        ("côn đảo", "Đặc khu Côn Đảo"),
        ("con dao", "Đặc khu Côn Đảo"),
        ("phú quý", "Đặc khu Phú Quý"),
        ("phu quy", "Đặc khu Phú Quý"),
        ("lý sơn", "Đảo Lý Sơn"),
        ("ly son", "Đảo Lý Sơn"),
        ("cù lao chàm", "Cù Lao Chàm"),
        ("cát bà", "Quần đảo Cát Bà"),
        ("bạch long vĩ", "Đảo Bạch Long Vĩ"),
        ("cô tô", "Đảo Cô Tô"),
        ("vân đồn", "Đặc khu Vân Đồn"),
        ("kiên hải", "Huyện đảo Kiên Hải"),
        ("nam du", "Quần đảo Nam Du"),
        ("hòn sơn", "Đảo Hòn Sơn"),
        ("hòn tre", "Đảo Hòn Tre"),
    ]
    for kw, label in ISLAND_ZONES:
        if kw in raw_text:
            return label
    return None


def evaluate_vpn_status(
    clean_data,
    cem_records,
    app_events,
    sub_info,
    downlink_sessions,
    max_dl_session,
    max_dl_incident_day,
    has_large_btools_session,
    incident_date,
    dt_incident,
    incident_time_str,
    dominant_cell,
    dominant_pct,
    ticket_content_lower,
    combined_report_text,
    action_suffix,
    ticket_content=""
):
    """
    KỊCH BẢN ĐẶC THÙ VPN / CLOUDFLARE 1.1.1.1 (ĐỘ ƯU TIÊN CUỐI CÙNG):
    Chỉ kích hoạt khi thỏa mãn TẤT CẢ các điều kiện:
    1. Không bị bóp băng thông gói cước (không có mã dịch vụ 100xx / 10002..10014).
    2. Khách hàng thực sự phản ánh lỗi mạng (chậm, yếu, không vào được, chập chờn...).
    3. Lưu lượng BTools ở mức thấp (toàn bộ các phiên < 11MB, không có phiên lớn >= 11MB).
    4. Thuê bao di chuyển qua nhiều khu vực (nhiều cell/site trên CEM >= 2, hoặc nội dung phản ánh, không bị tập trung 1 cell >= 70%).
    5. Có bằng chứng VPN: Xuất hiện app VPN/Cloudflare trên CEM, HOẶC bắt 4G dải lưu lượng 1-11MB đều nhau qua các ngày.
    """
    # 1. Điểm mù 3: Nếu phát hiện mã hạ/bóp băng thông BTools -> Bỏ qua VPN ngay!
    is_throttled_present = any(
        is_throttled_service_code(r.get("SERVICE_ID_CODE") or r.get("SERVICE_ID") or "")
        for r in (clean_data or [])
    )
    if is_throttled_present:
        return None

    # Điểm mù 4: Kiểm tra trần lưu lượng tổng - Nếu thuê bao phát sinh lưu lượng lớn (>= 300MB tổng)
    # thì không thể là lỗi treo VPN/nghẽn data, mà là khách hàng đang dùng data bình thường (OTT/streaming)
    total_all_bytes = sum(
        (float(r.get("DATA_VOLUME_DOWNLINK") or 0) + float(r.get("DATA_VOLUME_UPLINK") or 0))
        for r in (clean_data or [])
    )
    total_all_mb = total_all_bytes / (1024 * 1024)
    if total_all_mb >= 300.0:
        return None

    # 2. Điểm mù 2: Khách hàng phải phản ánh sự cố kết nối (chậm, yếu, mất mạng, không vào được...)
    is_trouble_reported = any(
        w in ticket_content_lower for w in [
            "chậm", "cham", "yếu", "yeu", "không vào được", "khong vao duoc", 
            "không được", "khong duoc", "mất mạng", "mat mang", "lag", "xoay", 
            "chập chờn", "chap chon", "rớt mạng", "rot mang", "không load", "ko load"
        ]
    )
    if not is_trouble_reported:
        return None

    # 3. Điểm mù 1 & Kiểm tra BTools Ground Truth: Lưu lượng phiên thấp, KHÔNG có phiên >= 11MB
    if has_large_btools_session or max_dl_session >= 11_000_000 or (max_dl_incident_day and max_dl_incident_day >= 11_000_000):
        return None

    # 4. Kiểm tra di chuyển nhiều nơi: Có từ 2 cell hoặc 2 trạm (site) khác nhau trên CEM, hoặc phản ánh đi nhiều nơi
    cem_cells = set(
        str(r.get("cell_name") or r.get("cellName") or r.get("cell_id") or "").strip()
        for r in (cem_records or [])
        if (r.get("cell_name") or r.get("cellName") or r.get("cell_id"))
    )
    cem_sites = set(extract_site_name_from_cell(c) for c in cem_cells if c)
    multi_area_patterns = [
        "đi nhiều nơi", "di nhiều nơi", "di nhieu noi", "nhiều nơi", "nhieu noi",
        "đi nhiều khu vực", "nhiều khu vực", "nhieu khu vuc",
        "khu vực khác cũng", "khu vuc khac cung", "kv khác cũng", "kv khac cung",
        "đi đâu cũng", "di dau cung", "các khu vực", "qua nhiều trạm", "nhiều địa chỉ",
        "nhiều chỗ", "nhieu cho", "ở đâu cũng", "o dau cung", "khắp nơi", "khap noi",
        "di chuyển", "di chuyen", "tại nhiều điểm", "tai nhieu diem"
    ]
    is_multi_area_reported = any(p in combined_report_text for p in multi_area_patterns)
    is_moving_multi_area = (len(cem_sites) >= 2 or len(cem_cells) >= 2 or is_multi_area_reported) and (not dominant_cell or dominant_pct < 70.0)

    if not is_moving_multi_area:
        return None

    # 5. Phát hiện VPN trên CEM (ưu tiên ngày phản ánh)
    detected_vpn_incident = detect_vpn_application(app_events, target_date=incident_date) if incident_date else None
    detected_vpn_any = detect_vpn_application(app_events)

    if detected_vpn_incident or detected_vpn_any:
        vpn_app_name = detected_vpn_incident or detected_vpn_any or "Cloudflare / 1.1.1.1"
        max_used_bytes = max_dl_incident_day if max_dl_incident_day > 0 else max_dl_session
        max_used_mb = max_used_bytes / 1_000_000
        incident_date_str_display = dt_incident.strftime("%d/%m/%Y") if dt_incident else (incident_time_str[:10] if incident_time_str else "ngày phản ánh")
        return (
            "ĐANG SỬ DỤNG VPN / 1.1.1.1",
            f"Khách hàng phản ánh mạng chậm/sự cố khi di chuyển qua nhiều khu vực. Kiểm tra thuê bao không bị bóp băng thông gói cước, nhưng dữ liệu CEM ({incident_date_str_display}) ghi nhận thiết bị phát sinh lưu lượng qua ứng dụng VPN ({vpn_app_name}). BTools ghi nhận toàn bộ lưu lượng bị giới hạn dưới 11MB (phiên lớn nhất chỉ đạt {max_used_mb:.1f} MB). Khi bật VPN, lưu lượng đi quốc tế bị bóp dung lượng dẫn đến tình trạng load chậm hoặc chập chờn.",
            f"Hướng dẫn khách hàng tạm thời tắt/gỡ ứng dụng VPN ({vpn_app_name}) trên máy, sau đó bật lại dữ liệu di động để truy cập bình thường." + action_suffix,
            "E2EFDA"
        )

    # 6. Nhánh chẩn đoán lưu lượng thấp nghi ngờ VPN / Thiết bị đầu cuối
    sub_radio_upper = str(sub_info.get("Radio") or "").upper()
    has_4g_signal = ("4G" in sub_radio_upper) or ("LTE" in sub_radio_upper) or any(
        "4G" in str(r.get("RAT_TYPE_NAME") or "").upper() or str(r.get("RAT_TYPE") or "") == "6"
        for r in (clean_data or [])
    )
    sessions_in_1_to_11mb = [s for s in downlink_sessions if 1_000_000 <= s < 11_000_000]
    if (
        has_4g_signal 
        and (1_000_000 <= max_dl_session < 11_000_000) 
        and len(sessions_in_1_to_11mb) >= 2
    ):
        day_max_sessions = {}
        if clean_data:
            for r in clean_data:
                r_time = r.get("RECORD_OPENING_TIME", "")
                r_dt = parse_dt_safe(r_time)
                if r_dt:
                    d_k = r_dt.date()
                    dl_v = float(r.get("DATA_VOLUME_DOWNLINK") or 0)
                    if dl_v > 0:
                        day_max_sessions[d_k] = max(day_max_sessions.get(d_k, 0), dl_v)

        all_days_under_11mb = all(v < 11_000_000 for v in day_max_sessions.values()) if day_max_sessions else True
        if all_days_under_11mb:
            max_used_mb = max_dl_session / 1_000_000

            # Chẩn đoán thêm thiết bị đầu cuối
            dev_cat, dev_name = detect_device_category(ticket_content=ticket_content, ai_summary="")

            # Kịch bản 1: Thiết bị không phải điện thoại di động thông dụng (ô tô, bộ phát Wi-Fi, Huawei, LG...)
            if dev_cat == "uncommon":
                dev_display = dev_name if dev_name else "đặc thù (ô tô / bộ phát Wi-Fi / Huawei / LG...)"
                return (
                    "LỖI THIẾT BỊ ĐẦU CUỐI",
                    f"Thuê bao bắt sóng 4G bình thường, gói cước không bị bóp băng thông nhưng lưu lượng BTools trong các ngày chỉ phát sinh trong dải thấp dưới 11MB (phiên lớn nhất chỉ đạt {max_used_mb:.1f} MB, không có phiên vượt 11MB). Khách hàng sử dụng SIM trên thiết bị {dev_display} (không phải dòng smartphone thông dụng), nguyên nhân do thiết bị đầu cuối bị treo kết nối data, giới hạn băng thông phần cứng hoặc lỗi cấu hình mạng của thiết bị.",
                    f"Hướng dẫn khách hàng khởi động lại thiết bị (tắt/bật lại nguồn thiết bị {dev_display}, tháo lắp lại SIM). Đề nghị khách hàng thử đổi SIM sang thiết bị di động thông dụng hơn (iPhone, Samsung, Oppo...) để test và so sánh đối chiếu." + action_suffix,
                    "FFF2CC"
                )
            else:
                # Kịch bản 2: Không có phiên VPN, không có thiết bị cụ thể hoặc là dòng máy thông dụng
                return (
                    "NGHI NGỜ VPN / LỖI THIẾT BỊ",
                    f"Thuê bao bắt sóng 4G bình thường, không bị bóp băng thông gói cước nhưng lưu lượng BTools trong các ngày đều phân bổ đều trong dải thấp dưới 11MB (phiên lớn nhất chỉ đạt {max_used_mb:.1f} MB, không có phiên vượt 11MB). Nguyên nhân có thể do thiết bị đang bật VPN / 1.1.1.1 / Private DNS dẫn đến bị giới hạn dung lượng từng phiên, hoặc do thiết bị đầu cuối bị treo phiên kết nối data.",
                    "Hướng dẫn khách hàng: (1) Kiểm tra và tắt các ứng dụng VPN / 1.1.1.1 hoặc cấu hình DNS riêng/Proxy trên máy; (2) Tắt/bật lại thiết bị và dữ liệu di động, sau đó speedtest lại; (3) Nếu vẫn chưa cải thiện, nhờ khách hàng thử đổi SIM sang máy khác để kiểm tra lại giúp." + action_suffix,
                    "FFF2CC"
                )

    return None


def analyze_subscriber_status(clean_data, package_title, ticket_content="", phone_84="", cem_records=None, app_events=None, incident_time_str=None, driver=None):
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

    # 🏝️ Nhận diện khu vực Đặc khu / Biển đảo đặc thù
    island_zone = extract_island_special_zone(ticket_content=ticket_content, package_title=package_title)

    def format_normal_plan(base_plan: str) -> str:
        plan = (base_plan or "").strip()
        if island_zone:
            island_msg = "Khu vực đặc khu biển đảo đồi núi phức tạp nên chất lượng mạng chưa ổn định, nhờ khách hàng thông cảm giúp."
            if island_msg not in plan:
                plan = f"{plan} {island_msg}" if plan else island_msg
        return plan + action_suffix

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

    # 🔍 BTOOLS GROUND TRUTH: Trích xuất sớm các phiên Downlink và mốc thời gian tiếp nhận
    downlink_sessions = []
    if clean_data:
        for r in clean_data:
            try:
                dl = float(r.get("DATA_VOLUME_DOWNLINK") or 0)
                if dl > 0:
                    downlink_sessions.append(dl)
            except (ValueError, TypeError):
                pass

    max_dl_session = max(downlink_sessions, default=0)
    has_large_btools_session = max_dl_session >= 10_000_000  # Có phiên >= 10MB

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
    has_session_over_10mb_after = max_downlink_after >= 10_000_000

    # 🎯 KIỂM TRA LỖI PROFILE CORE (NAM, HSS Profile rỗng, HSS Profile lạ):
    # Ưu tiên kiểm tra BTools trước: nếu thuê bao ĐANG CÓ PHIÊN DATA BÌNH THƯỜNG (>= 10MB) sau thời điểm tiếp nhận,
    # BTools xác nhận thuê bao đã sử dụng được dịch vụ, KHÔNG bị chặn bởi Profile.
    # Ngược lại, nếu BTools xác nhận KHÔNG có data bình thường sau tiếp nhận (hoặc không có mốc tiếp nhận và không có phiên >= 10MB):
    # -> Kiểm tra ngay các lỗi hồ sơ mạng lõi Core để xác định nguyên nhân (NAM=1, Profile rỗng, Profile lạ AND IP: 113/172/192.168).
    has_normal_btools_after = has_session_over_10mb_after or (not dt_incident and has_large_btools_session)
    if not has_normal_btools_after:
        core_err = check_core_profile_failure(sub_info)
        if core_err:
            return core_err

    # 2. KỊCH BẢN MOBILE INTERNET 5G
    # CHỈ kích hoạt khi KH phản ánh thực sự về 5G (không dùng được 5G, có 5G nhưng không dùng được, mất sóng 5G...)
    # KHÔNG kích hoạt nếu chỉ là mô tả trạng thái màn hình máy ("máy hiển thị sóng 5G") trong khi KH báo lỗi data chung.
    is_5g_reported = is_explicit_5g_complaint(package_title, ticket_content)
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

    # 🔍 BTOOLS GROUND TRUTH: Đánh giá phân bố lưu lượng phiên BTools & mốc thời gian phản ánh
    dt_incident = parse_dt_safe(incident_time_str)
    incident_date = dt_incident.date() if dt_incident else None

    # Lọc các phiên BTools trong đúng ngày phản ánh
    sessions_incident_day = []
    if clean_data and incident_date:
        for r in clean_data:
            r_time = r.get("RECORD_OPENING_TIME", "")
            r_dt = parse_dt_safe(r_time)
            if r_dt and r_dt.date() == incident_date:
                sessions_incident_day.append((r_dt, r))

    downlinks_incident_day = [
        float(r.get("DATA_VOLUME_DOWNLINK") or 0)
        for _, r in sessions_incident_day
        if r.get("DATA_VOLUME_DOWNLINK") is not None and float(r.get("DATA_VOLUME_DOWNLINK") or 0) > 0
    ]
    max_dl_incident_day = max(downlinks_incident_day, default=0)

    # Đánh giá phiên lớn nhất (toàn bộ lịch sử BTools và ngày phản ánh)
    max_dl_session = max(downlink_sessions, default=0)
    has_large_btools_session = (max_dl_session >= 11_000_000) or (max_dl_incident_day >= 11_000_000)

    # Kiểm tra xem có phiên nào đạt dải < 11MB không
    is_under_11mb_overall = bool(len(downlink_sessions) >= 1 and max_dl_session < 11_000_000)
    is_under_11mb_incident = bool(len(downlinks_incident_day) >= 1 and max_dl_incident_day < 11_000_000) if downlinks_incident_day else is_under_11mb_overall

    # Phát hiện ứng dụng VPN trên CEM để lưu ý KTV trong mọi kịch bản
    detected_vpn_incident = detect_vpn_application(app_events, target_date=incident_date) if incident_date else None
    detected_vpn_any = detect_vpn_application(app_events)
    active_vpn_name = detected_vpn_incident or detected_vpn_any
    vpn_advice_suffix = ""

    # 🎯 ƯU TIÊN KIỂM TRA GÓI CƯỚC KHÁCH BÁO ĐỐI CHIẾU PCRF (SAPC):
    # Khách hàng phản ánh dùng gói cụ thể (YOLO125, VD120, D159V, HOME...), ưu tiên check xem trên PCRF có gói này không.
    # Lưu ý: Các gói HOME (code 5000, 6000) trên PCRF có thể không hiển thị tên gói mà có cờ OCSE thay thế.
    combined_full_text = f"{package_title} {ticket_content}"
    if phone_84:
        try:
            from db_manager import get_db_connection
            conn = get_db_connection()
            with conn:
                row_t = conn.execute("SELECT ai_summary, ticket_content FROM tickets WHERE phone = ? OR phone LIKE ? ORDER BY updated_at DESC LIMIT 1", (phone_84, f"%{phone_84[-9:]}%")).fetchone()
                if row_t:
                    combined_full_text = f"{combined_full_text} {row_t[0] or ''} {row_t[1] or ''}"
        except Exception:
            pass

    extracted_reported_pkgs = extract_packages_from_text(combined_full_text)
    m_vol = re.search(r'(?:dung lượng còn|còn|đã sử dụng)[:\s]*([\d.,]+)\s*(gb|mb|g)\b', combined_full_text.lower())
    vol_reported = f"{m_vol.group(1)}{m_vol.group(2).upper()}" if m_vol else ""

    act_pkgs_all, exp_pkgs_all = get_sapc_package_validity(phone_84, incident_time_str=incident_time_str) if phone_84 else ([], [])
    all_sapc_pkgs = act_pkgs_all + exp_pkgs_all

    # Kiểm tra cờ OCSE hoặc gói HOME từ SAPC / HSS Profile
    has_ocse_flag = any(
        p.get("is_home") or "ocse" in p.get("name", "").lower() or "ocse" in str(p.get("group_name", "")).lower()
        for p in all_sapc_pkgs
    )
    if not has_ocse_flag and phone_84:
        try:
            hss_p = os.path.join(HSS_PROFILE_DIR, f"{phone_84}.json")
            if os.path.exists(hss_p):
                with open(hss_p, "r", encoding="utf-8") as f_h:
                    if "OCSE" in f_h.read().upper():
                        has_ocse_flag = True
        except Exception:
            pass

    if extracted_reported_pkgs and not has_normal_btools_after:
        for rep_p in extracted_reported_pkgs:
            is_home_req = "HOME" in rep_p.upper() or "GD" in rep_p.upper()

            # 1. Gói HOME thì chắc chắn phải có cờ OCSE trên PCRF (SAPC)
            if is_home_req:
                if has_ocse_flag:
                    # Gói HOME đã có cờ OCSE trên hệ thống -> hợp lệ
                    continue
                else:
                    # Gói HOME nhưng hoàn toàn KHÔNG CÓ cờ OCSE -> Lỗi thiếu cờ OCSE
                    return (
                        "GÓI HOME THIẾU CỜ OCSE",
                        f"Khách hàng phản ánh đang sử dụng gói {rep_p}, tuy nhiên tra cứu hệ thống PCRF (SAPC) không ghi nhận cờ OCSE (gói cước HOME bắt buộc phải có cờ OCSE để cấp lưu lượng data chia sẻ).",
                        f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {rep_p} và kích hoạt bổ sung cờ OCSE cho thuê bao trên hệ thống PCRF/OCS." + action_suffix,
                        "FFF2CC"
                    )

            # 2. Gói cước khác (YOLO, VD, D159...): Có cờ OCSE chưa chắc đã là gói HOME và không thay thế cho gói data chính độc lập
            def _pkg_match(t_pkg, s_pkg_name):
                t_c = re.sub(r'[^A-Za-z0-9]', '', t_pkg).upper()
                s_c = re.sub(r'[^A-Za-z0-9]', '', s_pkg_name).upper()
                if not t_c or not s_c:
                    return False
                if t_c in s_c or s_c in t_c:
                    return True
                t_b = re.sub(r'[A-Z]+$', '', t_c)
                s_b = re.sub(r'[A-Z]+$', '', s_c)
                if t_b and s_b and t_b == s_b and len(t_b) >= 3:
                    return True
                return False

            matched_in_exp = any(_pkg_match(rep_p, p["name"]) for p in exp_pkgs_all)
            matched_in_act = any(_pkg_match(rep_p, p["name"]) for p in act_pkgs_all)

            if matched_in_exp and not matched_in_act:
                exp_matched = [p for p in exp_pkgs_all if _pkg_match(rep_p, p["name"])]
                exp_names_str = ", ".join([p["name"] for p in exp_matched])
                exp_dates_str = ", ".join([p["exp_str"] for p in exp_matched])
                return (
                    "GÓI CƯỚC ĐÃ HẾT HẠN",
                    f"Gói cước data {exp_names_str} của thuê bao đã hết hạn từ ngày {exp_dates_str} (trước thời điểm phản ánh), tài khoản không còn dung lượng ưu đãi.",
                    f"Thông báo khách hàng gói cước ({exp_names_str}) đã hết hạn sử dụng vào ngày {exp_dates_str}. Tư vấn khách hàng gia hạn hoặc đăng ký gói cước mới phù hợp." + action_suffix,
                    "FFF2CC"
                )

            if not matched_in_act and not matched_in_exp:
                oda_pkgs = [p["name"] for p in act_pkgs_all if p["name"].upper().startswith("ODA_") or "GAME" in p["name"].upper()]
                main_pkgs = [p["name"] for p in act_pkgs_all if not p.get("is_paygo") and not p["name"].upper().startswith("ODA_") and "GAME" not in p["name"].upper()]
                if not main_pkgs:
                    vol_str = f" (dung lượng báo còn: {vol_reported})" if vol_reported else ""
                    oda_str = f" (SAPC chỉ có các gói tiện ích ODA: {', '.join(oda_pkgs)}, không có gói data Internet chính)" if oda_pkgs else " (SAPC không có gói data Internet chính)"
                    return (
                        "CHƯA ĐĂNG KÝ GÓI KHÁCH BÁO",
                        f"Khách hàng phản ánh đang sử dụng gói {rep_p}{vol_str}, tuy nhiên tra cứu hệ thống PCRF (SAPC) không ghi nhận gói cước này trên thuê bao{oda_str}. Do đó thuê bao không có quyền truy cập dữ liệu di động Internet.",
                        f"Kính chuyển VNP kiểm tra lại lịch sử đăng ký gói {rep_p} của khách hàng (chưa đăng ký thành công, đã hủy hoặc khách phản ánh nhầm số), tư vấn khách hàng kiểm tra lại trạng thái gói cước hoặc hướng dẫn đăng ký mới." + action_suffix,
                        "FFF2CC"
                    )

    # 🎯 KỊCH BẢN ĐẶC THÙ 2: Thuê bao sử dụng gói cước phụ thuộc mã 3001 (VD2, THẢ GA...) nhưng SAPC thiếu gói nền PAYGO
    combined_report_text = f"{package_title} {ticket_content}".lower()
    is_vd2_reported = bool(re.search(r"\bvd2\b|\bvd2k\b|gói vd2|goi vd2", combined_report_text))
    is_thaga_reported = bool(re.search(r"thả ga|tha ga|\bthaga\b", combined_report_text))

    active_pkgs_pre, _ = get_sapc_package_validity(phone_84, incident_time_str=incident_time_str)
    has_paygo = any(p.get("is_paygo") or "paygo" in p.get("name", "").lower() for p in active_pkgs_pre)

    # Nghiệp vụ chuẩn: Gói THẢ GA nếu check SAPCCHECK thấy code gói (như MI_THAGA70, mã 3000...)
    # thì đó là gói khai báo trực tiếp trên PCRF, hoạt động bình thường mà KHÔNG CẦN gói nền PAYGO!
    # Chỉ coi là lỗi thiếu PAYGO nếu khách báo gói THẢ GA nhưng trên SAPC KHÔNG có code gói PCRF nào và thiếu PAYGO.
    has_pcrf_thaga = any(("thaga" in p.get("name", "").lower() or "thả ga" in p.get("name", "").lower()) for p in active_pkgs_pre)

    dep_pkg_name = None
    if is_vd2_reported or any("vd2" in p.get("name", "").lower() for p in active_pkgs_pre):
        dep_pkg_name = "VD2"
    elif is_thaga_reported and not has_pcrf_thaga:
        dep_pkg_name = "THẢ GA"

    if dep_pkg_name and not has_paygo:
        return (
            f"LỖI GÓI {dep_pkg_name} - THIẾU PAYGO",
            f"Thuê bao đăng ký gói {dep_pkg_name} (gói cước phụ thuộc mã dịch vụ 3001) nhưng hệ thống PCRF/SAPC chưa được khai báo gói nền PAYGO (M0), dẫn đến mất kết nối dữ liệu di động.",
            f"Chuyển bộ phận IT/Khai thác cước kiểm tra và kích hoạt bổ sung gói nền PAYGO cho thuê bao trên hệ thống." + action_suffix,
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

    # Cô lập dữ liệu chuẩn 5 ngày gần nhất để không bị lẫn dữ liệu tra cứu bổ sung (> 5 ngày)
    start_scan_date = (datetime.now() - timedelta(days=4)).date()
    clean_data_5d = []
    for r in (clean_data or []):
        t_str = r.get("RECORD_OPENING_TIME", "")
        if t_str:
            try:
                d = datetime.strptime(t_str.split()[0], "%d/%m/%Y").date()
                if d >= start_scan_date:
                    clean_data_5d.append(r)
            except Exception:
                clean_data_5d.append(r)
        else:
            clean_data_5d.append(r)

    total_bytes = 0
    if clean_data_5d:
        for r in clean_data_5d:
            try:
                dl = float(r.get("DATA_VOLUME_DOWNLINK") or 0)
                ul = float(r.get("DATA_VOLUME_UPLINK") or 0)
                total_bytes += (dl + ul)
            except (ValueError, TypeError):
                pass
    total_mb = total_bytes / (1024 * 1024)
    has_btools_under_10mb = bool(clean_data_5d and len(clean_data_5d) > 0 and 0 <= total_mb < 10.0)

    if is_incident_today and is_radio_3g and is_ip_null and is_multi_area and has_btools_under_10mb:
        return (
            "SÓNG 4G KÉM / CHỈ CÓ 3G",
            "Khách hàng đang ở khu vực sóng 4G kém, chỉ ở 3G nên khó truy cập.",
            "Nhờ VNP báo Khách hàng chi tiết giúp, thông cảm và theo dõi thêm giúp.",
            "FFF2CC"
        )

    if not clean_data_5d or len(clean_data_5d) == 0:
        active_pkgs, expired_pkgs = get_sapc_package_validity(phone_84, incident_time_str=incident_time_str)
        act_commercial = [p for p in active_pkgs if not p.get("is_paygo") and not p.get("is_addon_app")]
        exp_commercial = [p for p in expired_pkgs if not p.get("is_paygo") and not p.get("is_addon_app")]
        addon_apps = [p for p in active_pkgs if p.get("is_addon_app")]
        
        # 1. TẤT CẢ GÓI ĐỀU ĐÃ HẾT HẠN TRƯỚC NGÀY TIẾP NHẬN PHẢN ÁNH
        if not act_commercial and exp_commercial:
            exp_names = ", ".join([p["name"] for p in exp_commercial])
            exp_dates = ", ".join([p["exp_str"] for p in exp_commercial])
            exp_note = f" (trước thời điểm tiếp nhận phản ánh {incident_time_str})" if incident_time_str else ""
            return (
                "GÓI CƯỚC ĐÃ HẾT HẠN",
                f"Thuê bao hoàn toàn không phát sinh dữ liệu trong các ngày qua do gói cước {exp_names} của khách hàng đã hết hạn vào ngày {exp_dates}{exp_note}.",
                f"Gói cước của Khách hàng ({exp_names}) đã hết hạn vào ngày {exp_dates}. Nhờ VNP kiểm tra lại, tư vấn khách hàng gia hạn/đăng ký gói cước mới.",
                "FFF2CC"
            )

        # 2. CHỈ CÓ GÓI TIỆN ÍCH / ADD-ON (KHÔNG CÓ GÓI DATA INTERNET TOÀN PHẦN)
        if not act_commercial and not exp_commercial and addon_apps:
            addon_names = ", ".join([p["name"] for p in addon_apps])
            return (
                "CHỈ CÓ GÓI TIỆN ÍCH - THIẾU DATA INTERNET",
                f"Hồ sơ SAPC ghi nhận thuê bao chỉ đăng ký gói tiện ích ứng dụng ({addon_names}) chạy trên nền PAYGO/M0, không có gói cước Data Internet toàn phần. Do tài khoản chính không đủ tiền duy trì cước ngoài gói nên thuê bao không thể truy cập các dịch vụ mạng ngoài phạm vi ưu đãi của gói.",
                f"Tư vấn khách hàng kiểm tra số dư tài khoản chính, đồng thời hướng dẫn đăng ký các gói cước Data VinaPhone chính thức (như VD120N, YOLO, D159V...) để truy cập mạng toàn diện." + action_suffix,
                "FFF2CC"
            )
        
        # 3. CHƯA ĐĂNG KÝ GÓI (Dựa vào SAPCCheck: chỉ có PAYGO / không có gói thương mại)
        if not act_commercial and not exp_commercial:
            return (
                "CHƯA ĐĂNG KÝ GÓI",
                "Hồ sơ SAPC ghi nhận thuê bao chưa đăng ký gói cước di động (chỉ có gói nền PAYGO/M0), không có gói data ưu đãi và tài khoản chính không đủ để trừ cước truy cập ngoài gói.",
                "Hướng dẫn khách hàng kiểm tra số dư tài khoản chính, đồng thời tư vấn đăng ký các gói cước Data VinaPhone ưu đãi để sử dụng.",
                "FFF2CC"
            )

        # 3. LỖI DO GÓI CƯỚC: Có gói cước còn hạn nhưng không phát sinh dữ liệu kể từ khi đăng ký
        if act_commercial:
            act_names = ", ".join([p["name"] for p in act_commercial])
            act_exp_dates = ", ".join([p["exp_str"] for p in act_commercial])
            act_reg_dates = ", ".join([p["reg_str"] for p in act_commercial if p.get("reg_str") != "N/A"]) or "trước đó"
            earliest_reg_dt = min([p["reg_dt"] for p in act_commercial if p.get("reg_dt")], default=None)
            start_scan_date = (datetime.now() - timedelta(days=4)).date()

            # Case 1: Gói mới đăng ký trong 5 ngày qua -> ĐÓNG PHIẾU LUÔN
            if earliest_reg_dt and earliest_reg_dt.date() >= start_scan_date:
                return (
                    "LỖI DO GÓI CƯỚC",
                    f"Thuê bao đăng ký gói {act_names} từ ngày {act_reg_dates} (còn hạn đến {act_exp_dates}) nhưng từ khi đăng ký đến nay không phát sinh dữ liệu, nghi ngờ lỗi luồng cước/profile gói.",
                    f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {act_names} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao.",
                    "FFF2CC"
                )

            # Case 2: Gói đăng ký trước chu kỳ 5 ngày -> Thực hiện hành vi bổ sung tra thêm BTools
            elif earliest_reg_dt and earliest_reg_dt.date() < start_scan_date:
                try:
                    from crawler_btools import fetch_supplementary_btools_if_needed
                    clean_data = fetch_supplementary_btools_if_needed(driver, phone_84, clean_data, earliest_reg_dt, start_scan_date)
                except Exception:
                    pass
                prior_rows = []
                for r in (clean_data or []):
                    t_str = r.get("RECORD_OPENING_TIME", "")
                    if t_str:
                        try:
                            d = datetime.strptime(t_str.split()[0], "%d/%m/%Y").date()
                            if d < start_scan_date:
                                prior_rows.append(r)
                        except Exception:
                            pass
                prior_mb = sum((float(r.get("DATA_VOLUME_DOWNLINK") or 0) + float(r.get("DATA_VOLUME_UPLINK") or 0))/(1024*1024) for r in prior_rows)

                # Nhánh 2A: Từ khi đăng ký đến nay cũng không có phát sinh data -> Giống Case 1, ĐÓNG PHIẾU LUÔN
                if prior_mb < 1.0:
                    return (
                        "LỖI DO GÓI CƯỚC",
                        f"Thuê bao đăng ký gói {act_names} từ ngày {act_reg_dates} (còn hạn đến {act_exp_dates}) nhưng từ khi đăng ký đến nay không phát sinh dữ liệu (kể cả trước 5 ngày gần đây), nghi ngờ lỗi luồng cước/profile gói.",
                        f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {act_names} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao.",
                        "FFF2CC"
                    )
                else:
                    # Trước đó có data, 5 ngày gần đây hoàn toàn không có phiên nào
                    if island_zone:
                        return (
                            "ĐẶC THÙ ĐỊA HÌNH BIỂN ĐẢO",
                            f"Thuê bao có gói cước {act_names} phản ánh sự cố kết nối/mất sóng tại khu vực đặc thù biển đảo ({island_zone}). Do đặc thù địa hình đồi núi ven biển, khoảng cách xa trạm BTS và suy hao truyền dẫn qua môi trường biển, khu vực này thường xuyên bị suy hao hoặc lõm sóng (5 ngày gần đây không phát sinh dữ liệu BTools).",
                            f"Khu vực biển đảo địa hình phức tạp, trạm phát sóng bị giới hạn vùng phủ và khó khả thi nâng cấp hạ tầng ngay. Kính nhờ ĐTV/VNP liên hệ giải thích đặc thù địa bàn {island_zone}, mong khách hàng thông cảm, theo dõi sử dụng và di chuyển về phía khu vực trung tâm/gần trạm để có kết nối tốt hơn.",
                            "FFF2CC"
                        )
                    return (
                        "KHÔNG CÓ DỮ LIỆU",
                        f"Thuê bao có gói cước {act_names} đã từng phát sinh dữ liệu trước đó ({prior_mb:.1f}MB), tuy nhiên 5 ngày gần đây hoàn toàn không phát sinh phiên kết nối nào trên BTools." + ALERT_COMMENT,
                        "Nghi ngờ do thiết bị của khách hàng bị treo data hoặc tắt máy. Nhờ khách hàng thử tắt/bật thiết bị và data, đổi sim sang máy khác và kiểm tra SPEEDTEST giúp." + ALERT_ACTION,
                        "FFF2CC"
                    )

            # Fallback nếu gói thương mại không có ngày tháng cụ thể
            return (
                "LỖI DO GÓI CƯỚC",
                f"Thuê bao đăng ký gói {act_names} từ ngày {act_reg_dates} (còn hạn đến {act_exp_dates}) nhưng từ khi đăng ký đến nay không phát sinh dữ liệu, nghi ngờ lỗi luồng cước/profile gói.",
                f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {act_names} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao.",
                "FFF2CC"
            )

        if island_zone:
            return (
                "ĐẶC THÙ ĐỊA HÌNH BIỂN ĐẢO",
                f"Thuê bao phản ánh sự cố sóng/kết nối tại khu vực đặc thù biển đảo ({island_zone}). Do đặc thù địa hình đồi núi ven biển và khoảng cách xa trạm BTS/hạn chế truyền dẫn qua biển, khu vực này thường xuyên bị suy hao hoặc lõm sóng (5 ngày qua không phát sinh dữ liệu BTools).",
                f"Khu vực biển đảo địa hình phức tạp, trạm phát sóng bị giới hạn vùng phủ và khó khả thi nâng cấp hạ tầng ngay. Kính nhờ ĐTV/VNP liên hệ giải thích đặc thù địa bàn {island_zone}, mong khách hàng thông cảm, theo dõi sử dụng và di chuyển về phía khu vực trung tâm/gần trạm để có kết nối tốt hơn.",
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

    # 🕒 1. KIỂM TRA CHÉO 2 NGÀY GẦN NHẤT XEM CÓ DATA KHÔNG (trên phạm vi 5 ngày chuẩn)
    has_recent_data = False
    today_date = datetime.now().date()
    recent_dates = {today_date, today_date - timedelta(days=1)}
    latest_date_in_log = None
    
    for row in clean_data_5d:
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
        for row in clean_data_5d:
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
        recent_day_data = clean_data_5d
        recent_3days_data = clean_data_5d

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
        if matched_id == "KC_04_PACKAGE_OR_DEVICE_HANG":
            # Chuyển về kịch bản LỖI DO GÓI CƯỚC / CHƯA ĐĂNG KÝ GÓI theo chuẩn SAPC
            matched_id = None

    if matched_id:
        status, comment, plan, color = get_scenario_result(scenarios, matched_id)
        if matched_id == "KC_03_THROTTLED":
            # Ghi nhận chính xác mã code 100xx đã bóp băng thông kèm thông số tốc độ (64/64, 128/64, 3072/3072...)
            detected_codes = [str(c).strip() for c in (service_set | (service_set_3days or set())) if is_throttled_service_code(c)]
            clean_codes = sorted(list(set(c.lstrip("0") or c for c in detected_codes)))
            detail_list = []
            for c in clean_codes:
                speed = get_throttled_speed_desc(c)
                if speed:
                    detail_list.append(f"{c} (bóp băng thông {speed})")
                else:
                    detail_list.append(f"{c}")
            code_str = "; ".join(detail_list) if detail_list else "100xx"
            comment = f"Hệ thống ghi nhận mã dịch vụ giới hạn băng thông: {code_str}, thuê bao đã sử dụng hết dung lượng tốc độ cao và đang bị hạ băng thông."
        return status, comment + comment_suffix, plan + action_suffix, color

    # =========================================================================
    # 🛑 GIAI ĐOẠN ĐÁNH GIÁ ĐIỀU KIỆN PHÂN LOẠI THEO PHẢN ÁNH & CEM
    # =========================================================================
    with open("diagnostic_config.json", "r", encoding="utf-8") as cf:
        config_data = json.load(cf)
    excluded_system_codes = set(config_data.get("EXCLUDED_SYSTEM_CODES", []))
    
    ticket_content_lower = ticket_content.lower() if ticket_content else ""

    # 🎯 ĐIỀU KIỆN GÓI CƯỚC & MÃ DỊCH VỤ BTOOLS (CHUẨN HÓA THEO QUY CHUẨN KỸ THUẬT)
    all_days_service_codes = set()
    for row in clean_data:
        sc = str(row.get("SERVICE_ID_CODE", "")).strip().lower()
        if sc:
            all_days_service_codes.add(sc)

    norm_service_codes = set(str(c).strip().lstrip("0") for c in all_days_service_codes if str(c).strip())
    SYSTEM_CODES = {"300", "302", "330", "2042"}

    act_p, exp_p = get_sapc_package_validity(phone_84, incident_time_str=incident_time_str) if phone_84 else ([], [])
    act_commercial = [p for p in act_p if not p.get("is_paygo") and not p.get("is_addon_app") and not p.get("name", "").upper().startswith("ODA_")]
    exp_commercial = [p for p in exp_p if not p.get("is_paygo") and not p.get("is_addon_app")]
    addon_apps = [p for p in act_p if p.get("is_addon_app")]

    # 🎯 KỊCH BẢN KHIẾU NẠI TRỪ TIỀN / TRỪ CƯỚC NGOÀI GÓI KHI BTOOLS CÓ MÃ 3001 (PAYGO)
    is_charge_complaint = bool(re.search(r"trừ tiền|tru tien|trừ cước|tru cuoc|mất tiền|mat tien|trừ tkc|bị trừ|bi tru|hao tiền|tính cước|tinh cuoc", combined_report_text))
    has_paygo_charge = ("3001" in norm_service_codes) or ("0000003001" in all_days_service_codes)
    if is_charge_complaint and has_paygo_charge and not act_commercial:
        exp_names = ", ".join([p["name"] for p in exp_commercial]) if exp_commercial else ""
        addon_names = ", ".join([p["name"] for p in addon_apps]) if addon_apps else ""
        if exp_names:
            reason_str = f"gói cước data chính ({exp_names}) đã hết hạn sử dụng"
        elif addon_names:
            reason_str = f"thuê bao chỉ có gói tiện ích ({addon_names}) và đã truy cập các dịch vụ Internet ngoài phạm vi miễn cước của gói"
        else:
            reason_str = "thuê bao không có gói cước data ưu đãi"
        return (
            "TRỪ CƯỚC NGOÀI GÓI PAYGO",
            f"Khách hàng khiếu nại trừ tiền do {reason_str}. BTools ghi nhận các phiên truy cập dữ liệu di động tính cước theo gói mặc định PAYGO (Service ID 3001) trừ vào tài khoản chính.",
            f"Giải thích cho khách hàng về nguyên nhân phát sinh lưu lượng ngoài gói theo cước PAYGO và tư vấn đăng ký gói cước data mới để tránh bị trừ tiền tài khoản chính." + action_suffix,
            "FFF2CC"
        )

    is_pure_system_codes_only = bool(all_days_service_codes) and (
        all(code in excluded_system_codes for code in all_days_service_codes) or
        (norm_service_codes and norm_service_codes.issubset(SYSTEM_CODES))
    )

    # 1. QUY TẮC "CHỈ CÓ GÓI TIỆN ÍCH" HOẶC "CHƯA ĐĂNG KÝ GÓI" (Dựa vào SAPCCheck: chỉ có PAYGO / không có gói thương mại)
    if is_pure_system_codes_only and not act_commercial and not exp_commercial:
        if addon_apps:
            addon_names = ", ".join([p["name"] for p in addon_apps])
            return (
                "CHỈ CÓ GÓI TIỆN ÍCH - THIẾU DATA INTERNET",
                f"Lịch sử dữ liệu chỉ xuất hiện các mã hệ thống do thuê bao chỉ đăng ký gói tiện ích ứng dụng ({addon_names}) chạy trên nền PAYGO/M0, không có gói data Internet chính và tài khoản chính không đủ tiền để duy trì truy cập ngoài gói.",
                f"Tư vấn khách hàng kiểm tra số dư tài khoản chính, đồng thời hướng dẫn đăng ký các gói cước Data VinaPhone ưu đãi để sử dụng Internet toàn diện." + action_suffix,
                "FFF2CC"
            )
        return (
            "CHƯA ĐĂNG KÝ GÓI",
            "Hồ sơ SAPC ghi nhận thuê bao chưa đăng ký gói cước di động (chỉ có gói nền PAYGO/M0), lịch sử dữ liệu không tồn tại gói cước thương mại phát sinh data.",
            "Yêu cầu kỹ thuật viên kiểm tra trạng thái gói trên HLR/PCRF và hướng dẫn khách hàng cách thức đăng ký các gói cước Data VinaPhone ưu đãi." + action_suffix,
            "FFF2CC"
        )

    # 2. QUY TẮC "GÓI CƯỚC HẾT HẠN" (Có gói nhưng thời hạn sử dụng < ngày tiếp nhận phản ánh)
    if is_pure_system_codes_only and not act_commercial and exp_commercial:
        exp_names = ", ".join([p["name"] for p in exp_commercial])
        exp_dates = ", ".join([p["exp_str"] for p in exp_commercial])
        return (
            "GÓI CƯỚC ĐÃ HẾT HẠN",
            f"Lịch sử phân tích dữ liệu chỉ xuất hiện các mã hệ thống do gói cước {exp_names} của khách hàng đã hết hạn vào ngày {exp_dates} (trước ngày tiếp nhận phản ánh).",
            f"Gói cước của Khách hàng ({exp_names}) đã hết hạn vào ngày {exp_dates}. Nhờ VNP kiểm tra lại, tư vấn khách hàng gia hạn/đăng ký gói cước mới." + action_suffix,
            "FFF2CC"
        )

    # 3. QUY TẮC "LỖI GÓI CƯỚC" (Kể từ khi đăng ký gói cước, không phát sinh các code gói hợp lệ)
    if act_commercial:
        expected_codes = set()
        for p in act_commercial:
            expected_codes.update(get_expected_service_codes_for_pkg(p.get("name", "")))
            grp = str(p.get("group_name") or "").strip()
            if grp and grp.lower() not in ["none", "null", ""]:
                expected_codes.add(grp)
                expected_codes.add(grp.lstrip("0") or "0")
                expected_codes.add(grp.zfill(10))
        norm_expected = set(c.lstrip("0") for c in expected_codes if c)

        has_valid_pkg_code = False
        if norm_expected:
            has_valid_pkg_code = bool(norm_expected.intersection(norm_service_codes))
        else:
            has_valid_pkg_code = bool(norm_service_codes - SYSTEM_CODES)

        if is_pure_system_codes_only or not has_valid_pkg_code:
            act_names = ", ".join([p["name"] for p in act_commercial])
            act_exp_dates = ", ".join([p["exp_str"] for p in act_commercial])
            act_reg_dates = ", ".join([p["reg_str"] for p in act_commercial if p.get("reg_str") != "N/A"]) or "trước đó"
            sys_str = ", ".join(sorted(list(norm_service_codes))) if norm_service_codes else "quản trị hệ thống"
            return (
                "LỖI DO GÓI CƯỚC",
                f"Thuê bao có gói cước {act_names} (đăng ký từ ngày {act_reg_dates}, còn hạn đến {act_exp_dates}), tuy nhiên kể từ khi đăng ký đến nay lịch sử BTools không phát sinh các mã dịch vụ (Service ID) hợp lệ của gói cước (chỉ ghi nhận mã {sys_str}). Nghi ngờ lỗi luồng cước hoặc profile gói chưa được kích hoạt quyền truy cập data.",
                f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {act_names} trên hệ thống PCRF/OCS để kích hoạt lại quyền truy cập cho thuê bao." + action_suffix,
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
    is_data_depletion_reported = any(
        k in ticket_content_lower for k in [
            "mau hết dung lượng", "nhanh hết dung lượng", "mau hết data", "nhanh hết data",
            "hao data", "hao dung lượng", "trừ cước nhanh", "trừ data nhanh", "nhanh hết gói",
            "bị mau hết", "mau het", "hao dung luong", "mau het dung luong", "trừ data", "trừ cước"
        ]
    )
    is_network_failure_reported = any(
        k in ticket_content_lower for k in [
            "không được", "khong duoc", "không vào được", "khong vao duoc", "mất hoàn toàn",
            "mất mạng", "không có mạng", "mất kết nối", "ko vào", "ko duoc", "chậm", "cham",
            "yếu", "yeu", "chập chờn", "chap chon", "load chậm", "không load", "xoay",
            "không truy cập", "khong truy cap", "không sử dụng được", "khong su dung duoc",
            "không dùng được", "khong dung duoc", "chưa dùng được", "chưa sử dụng được",
            "bị rớt mạng", "chỉ có sóng 3g", "chỉ hiện h+", "chỉ hiện 3g", "không có 4g",
            "mạng lag", "khó truy cập", "chặn mạng"
        ]
    )

    # 🎯 PHÁT HIỆN PHẢN ÁNH LỖI ỨNG DỤNG CỤ THỂ (ZALO, TIKTOK, FACEBOOK, YOUTUBE, GAME...)
    app_indicators = [
        "zalo", "tiktok", "tik tok", "facebook", "youtube", "ytb", "messenger", 
        "telegram", "viber", "liên quân", "lien quan", "free fire", "freefire", 
        "pubg", "game", "shopee", "lazada", "vnedu", "my vnpt"
    ]
    matched_apps = [app.title() for app in app_indicators if re.search(r'\b' + re.escape(app) + r'\b', ticket_content_lower)]
    is_app_specific_issue = bool(matched_apps) and (
        "truy cập báo:" in ticket_content_lower 
        or "ứng dụng" in ticket_content_lower 
        or "app" in ticket_content_lower
        or "lỗi ứng dụng cụ thể" in ticket_content_lower
        or any(k in ticket_content_lower for k in [
            "báo đang kết nối", "báo kết nối", "không lướt", "xoay", "quay vòng", 
            "ping cao", "trừ dung lượng", "trừ data", "không xem được", "không gọi được", 
            "không gửi được", "chậm", "lag", "không vào được", "không được"
        ])
    )
    app_names_str = ", ".join(list(dict.fromkeys(matched_apps)))

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

    def check_tail_vpn():
        return evaluate_vpn_status(
            clean_data=clean_data,
            cem_records=cem_records,
            app_events=app_events,
            sub_info=sub_info,
            downlink_sessions=downlink_sessions,
            max_dl_session=max_dl_session,
            max_dl_incident_day=max_dl_incident_day,
            has_large_btools_session=has_large_btools_session,
            incident_date=incident_date,
            dt_incident=dt_incident,
            incident_time_str=incident_time_str,
            dominant_cell=dominant_cell,
            dominant_pct=dominant_pct,
            ticket_content_lower=ticket_content_lower,
            combined_report_text=combined_report_text,
            action_suffix=action_suffix,
            ticket_content=ticket_content
        )

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

    total_bytes_after = sum(
        (float(r.get("DATA_VOLUME_DOWNLINK", 0) or 0) + float(r.get("DATA_VOLUME_UPLINK", 0) or 0))
        for _, r in sessions_after_incident
    )
    total_mb_after = total_bytes_after / (1024 * 1024)
    count_sessions_after = len(sessions_after_incident)
    # Thuê bao có phát sinh dữ liệu đáng kể sau mốc tiếp nhận: Có phiên >= 10MB HOẶC tích lũy >= 30MB (với >= 3 phiên OTT/Web/Streaming)
    has_continuous_data_after = (total_mb_after >= 30.0 and count_sessions_after >= 3)
    has_real_usage_after = has_session_over_10mb_after or has_continuous_data_after

    def check_island_trouble_scenario():
        if not island_zone:
            return None
        # Nếu sau sự cố đã phục hồi dùng data lớn (>= 300MB) thì không coi là lỗi biển đảo
        if dt_incident and has_real_usage_after and total_mb_after >= 300.0:
            return None
        # Khách có phản ánh sự cố mạng/sóng
        is_trouble = (
            is_network_failure_reported 
            or is_reported_slow 
            or is_network_slow 
            or any(w in ticket_content_lower for w in [
                "sóng", "mất sóng", "chập chờn", "không vào mạng", "quay vòng", 
                "xoay tròn", "không được", "sóng kém", "1 vạch", "2 vạch", "rớt", "đặc khu", "phú quốc"
            ])
        )
        if is_trouble and not is_app_specific_issue and not is_data_depletion_reported:
            return (
                "ĐẶC THÙ ĐỊA HÌNH BIỂN ĐẢO",
                f"Thuê bao phản ánh sự cố kết nối/chất lượng sóng tại khu vực đặc thù biển đảo ({island_zone}). Do đặc thù địa hình đồi núi ven biển, khoảng cách xa trạm BTS và suy hao truyền dẫn qua môi trường biển, vùng phủ sóng tại khu vực này chưa ổn định.",
                f"Khu vực biển đảo địa hình phức tạp, trạm phát sóng bị giới hạn vùng phủ và khó khả thi nâng cấp hạ tầng ngay. Kính nhờ ĐTV/VNP liên hệ giải thích đặc thù địa bàn {island_zone}, mong khách hàng thông cảm, theo dõi sử dụng và di chuyển về phía khu vực trung tâm/gần trạm để có chất lượng sóng tốt hơn." + action_suffix,
                "FFF2CC"
            )
        return None

    # 🎯 KỊCH BẢN ĐÁNH GIÁ KHI CÓ MỐC THỜI GIAN TIẾP NHẬN
    if dt_incident:
        # Trường hợp 1: Có lưu lượng thực tế (phiên >10MB hoặc tích lũy >=30MB) SAU thời điểm tiếp nhận -> Khách hàng đã dùng được
        if has_real_usage_after:
            if is_app_specific_issue:
                return (
                    "LỖI ỨNG DỤNG (KTV XỬ LÝ)",
                    f"Khách hàng phản ánh sự cố đối với ứng dụng cụ thể ({app_names_str}). Mặc dù sau thời điểm tiếp nhận ({incident_time_str}) BTools có ghi nhận dữ liệu ({total_mb_after:.1f}MB, phiên lớn nhất {max_downlink_after/1024/1024:.1f}MB), nhưng sự cố trên ứng dụng chưa được xác minh. Cần Kỹ thuật viên kiểm tra xử lý riêng đối với ứng dụng này, không đóng tự động.",
                    f"Chuyển Kỹ thuật viên kiểm tra lỗi ứng dụng ({app_names_str}) và liên hệ hỗ trợ trực tiếp khách hàng." + action_suffix,
                    "FFF2CC"
                )
            elif dominant_cell and is_reported_slow and total_mb_after < 300.0:
                island_res = check_island_trouble_scenario()
                if island_res:
                    return island_res
                return (
                    "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                    f"Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% lưu lượng).",
                    "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )
            elif is_reported_slow:
                # Nếu sau phản ánh khách vẫn cày dung lượng lớn (>= 300MB) -> Mạng đang đáp ứng bình thường
                if total_mb_after >= 300.0:
                    return (
                        "HOẠT ĐỘNG BÌNH THƯỜNG",
                        f"Khách hàng phản ánh mạng chậm lúc {incident_time_str}. Tuy nhiên dữ liệu BTools sau thời điểm tiếp nhận ghi nhận thuê bao tiếp tục truy cập Internet ổn định với lưu lượng lớn (đạt {total_mb_after:.1f}MB qua {count_sessions_after} phiên kết nối). Khách hàng đã sử dụng được dịch vụ.",
                        format_normal_plan("Dịch vụ đã khôi phục hoạt động bình thường sau thời điểm phản ánh. Hướng dẫn khách hàng theo dõi sử dụng, nếu cần hỗ trợ thêm vui lòng liên hệ lại tổng đài."),
                        "E2EFDA"
                    )

                island_res = check_island_trouble_scenario()
                if island_res:
                    return island_res

                vpn_res = check_tail_vpn()
                if vpn_res:
                    return vpn_res

                # KH phản ánh chậm, không bóp băng thông, có phiên cao, di chuyển nhiều nơi (không có trạm dominant hoặc phản ánh nhiều nơi)
                # -> Khả năng di chuyển vào khu vực sóng kém -> Khách hàng theo dõi thêm
                if is_reported_multiple_places or not dominant_cell or dominant_pct < 50.0:
                    return (
                        "THEO DÕI THÊM",
                        "Khách hàng di chuyển nhiều nơi khả năng di chuyển vào khu vực sóng kém/chất lượng mạng chưa đảm bảo.",
                        "Nhờ khách hàng theo dõi thêm giúp. Nếu khách hàng có vị trí cụ thể nhờ VNP tạo lại giúp phản ánh mới và chuyển trường chất lượng mạng để kỹ thuật địa bàn kiểm tra." + action_suffix,
                        "FFF2CC"
                    )

                return (
                    "LƯU LƯỢNG YẾU",
                    f"Khách hàng phản ánh mạng chậm. Dữ liệu sau thời điểm tiếp nhận ({incident_time_str}) ghi nhận tốc độ download chưa ổn định, phiên cao nhất đạt {max_downlink_after/1024/1024:.1f}MB. Nghi ngờ chất lượng sóng tại khu vực khách hàng chưa đảm bảo.",
                    "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )
            elif is_data_depletion_reported:
                return (
                    "KHIẾU NẠI DUNG LƯỢNG / CƯỚC (KTV XỬ LÝ)",
                    "",
                    "",
                    "FFFFFF"
                )
            elif is_network_failure_reported:
                if has_session_over_10mb_after:
                    detail_traffic_str = f"phiên lớn nhất đạt {max_downlink_after/1024/1024:.1f}MB"
                else:
                    detail_traffic_str = f"tổng lưu lượng đạt {total_mb_after:.1f}MB qua {count_sessions_after} phiên kết nối"
                return (
                    "HOẠT ĐỘNG BÌNH THƯỜNG",
                    f"Kiểm tra lịch sử kết nối sau thời điểm tiếp nhận phản ánh ({incident_time_str}), thuê bao đã phát sinh lưu lượng data bình thường ({detail_traffic_str}, mạng 4G/5G ổn định). Khách hàng đã sử dụng được dịch vụ.",
                    format_normal_plan("Dịch vụ đã khôi phục hoạt động bình thường sau thời điểm phản ánh. Hướng dẫn khách hàng theo dõi sử dụng, nếu cần hỗ trợ thêm vui lòng liên hệ lại tổng đài."),
                    "E2EFDA"
                )
            else:
                return (
                    "CHƯA RÕ KỊCH BẢN (KTV XỬ LÝ)",
                    "",
                    "",
                    "FFFFFF"
                )
        
        # Trường hợp 2: Có phiên >10MB TRƯỚC thời điểm tiếp nhận, nhưng SAU mốc tiếp nhận CHƯA CÓ phiên >10MB
        elif has_session_over_10mb:
            if is_app_specific_issue:
                return (
                    "LỖI ỨNG DỤNG (KTV XỬ LÝ)",
                    f"Khách hàng phản ánh sự cố đối với ứng dụng cụ thể ({app_names_str}). Cần Kỹ thuật viên kiểm tra xử lý riêng đối với ứng dụng này, không đóng tự động.",
                    f"Chuyển Kỹ thuật viên kiểm tra lỗi ứng dụng ({app_names_str}) và liên hệ hỗ trợ trực tiếp khách hàng." + action_suffix,
                    "FFF2CC"
                )
            elif dominant_cell and (is_reported_slow or is_reported_multiple_places):
                island_res = check_island_trouble_scenario()
                if island_res:
                    return island_res
                return (
                    "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                    f"Khách hàng phản ánh mạng chậm / sự cố. Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% kết nối). Mặc dù trước đó có sử dụng data, nhưng sau mốc tiếp nhận ({incident_time_str}) chưa ghi nhận phiên kết nối mới.",
                    "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )
            elif is_reported_slow:
                island_res = check_island_trouble_scenario()
                if island_res:
                    return island_res
                vpn_res = check_tail_vpn()
                if vpn_res:
                    return vpn_res
                if is_reported_multiple_places or not dominant_cell or dominant_pct < 50.0:
                    return (
                        "THEO DÕI THÊM",
                        "Khách hàng di chuyển nhiều nơi khả năng di chuyển vào khu vực sóng kém/chất lượng mạng chưa đảm bảo.",
                        "Nhờ khách hàng theo dõi thêm giúp. Nếu khách hàng có vị trí cụ thể nhờ VNP tạo lại giúp phản ánh mới và chuyển trường chất lượng mạng để kỹ thuật địa bàn kiểm tra." + action_suffix,
                        "FFF2CC"
                    )
                return (
                    "LƯU LƯỢNG YẾU",
                    f"Khách hàng phản ánh mạng chậm. Dữ liệu trước thời điểm tiếp nhận có phát sinh data nhưng sau mốc tiếp nhận ({incident_time_str}) chưa ghi nhận phiên kết nối mới. Nghi ngờ chất lượng sóng tại khu vực khách hàng chưa đảm bảo.",
                    "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )
            else:
                island_res = check_island_trouble_scenario()
                if island_res:
                    return island_res
                return (
                    "THEO DÕI THÊM",
                    f"Thuê bao có sử dụng data trước thời điểm phản ánh, tuy nhiên sau mốc tiếp nhận ({incident_time_str}) chưa ghi nhận phiên phát sinh lưu lượng mới. Cần theo dõi thêm.",
                    "Có thể Khách hàng đang di chuyển vào khu vực sóng kém, hoặc nghẽn mạng tạm thời. Nhờ KH theo dõi thêm giúp." + action_suffix,
                    "FFF2CC"
                )

        # Trường hợp 3: Sau tiếp nhận chỉ có lưu lượng yếu (1MB - 10MB)
        elif is_weak_traffic_after:
            island_res = check_island_trouble_scenario()
            if island_res:
                return island_res
            if dominant_cell:
                return (
                    "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                    f"Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% lưu lượng).",
                    "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )
            else:
                vpn_res = check_tail_vpn()
                if vpn_res:
                    return vpn_res
                return (
                    "LƯU LƯỢNG YẾU",
                    f"Sau thời điểm tiếp nhận ({incident_time_str}), lưu lượng data thực tế ở mức thấp (phiên lớn nhất chỉ đạt {max_downlink_after/1024/1024:.1f}MB), kết nối chập chờn tại khu vực phản ánh.",
                    "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                    "FFF2CC"
                )

    # 🎯 KỊCH BẢN KHI CÓ DỮ LIỆU DATA >10MB (FALLBACK HOẶC KHÔNG CÓ MỐC TIẾP NHẬN)
    if has_session_over_10mb:
        if is_app_specific_issue:
            return (
                "LỖI ỨNG DỤNG (KTV XỬ LÝ)",
                f"Khách hàng phản ánh sự cố đối với ứng dụng cụ thể ({app_names_str}). Dữ liệu BTools ngày gần nhất ({recent_day_str}) vẫn ghi nhận phiên kết nối chung ({max_downlink/1024/1024:.1f}MB). Cần Kỹ thuật viên kiểm tra xử lý riêng đối với ứng dụng này, không đóng tự động.",
                f"Chuyển Kỹ thuật viên kiểm tra lỗi ứng dụng ({app_names_str}) và liên hệ hỗ trợ trực tiếp khách hàng." + action_suffix,
                "FFF2CC"
            )
        elif is_data_depletion_reported:
            return (
                "KHIẾU NẠI DUNG LƯỢNG / CƯỚC (KTV XỬ LÝ)",
                "",
                "",
                "FFFFFF"
            )
        elif dominant_cell and (is_reported_slow or is_reported_multiple_places):
            island_res = check_island_trouble_scenario()
            if island_res:
                return island_res
            return (
                "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                f"Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% lưu lượng).",
                "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                "FFF2CC"
            )
        elif is_reported_completely_failed:
            return (
                "HOẠT ĐỘNG BÌNH THƯỜNG",
                f"Khách hàng phản ánh không truy cập được hoàn toàn, nhưng dữ liệu BTools thực tế ngày gần nhất ({recent_day_str}) vẫn ghi nhận phiên kết nối dung lượng lớn ({max_downlink/1024/1024:.1f}MB). Dịch vụ đã tự phục hồi sau thời điểm phản ánh.",
                format_normal_plan("Dịch vụ đã khôi phục hoạt động bình thường. Hướng dẫn khách hàng tiếp tục theo dõi sử dụng."),
                "E2EFDA"
            )
        elif is_reported_slow or is_reported_multiple_places:
            island_res = check_island_trouble_scenario()
            if island_res:
                return island_res
            vpn_res = check_tail_vpn()
            if vpn_res:
                return vpn_res
            if is_reported_multiple_places or not dominant_cell or dominant_pct < 50.0:
                return (
                    "THEO DÕI THÊM",
                    "Khách hàng di chuyển nhiều nơi khả năng di chuyển vào khu vực sóng kém/chất lượng mạng chưa đảm bảo.",
                    "Nhờ khách hàng theo dõi thêm giúp. Nếu khách hàng có vị trí cụ thể nhờ VNP tạo lại giúp phản ánh mới và chuyển trường chất lượng mạng để kỹ thuật địa bàn kiểm tra." + action_suffix,
                    "FFF2CC"
                )
            return (
                "LƯU LƯỢNG YẾU",
                f"Khách hàng phản ánh mạng chậm / chập chờn. Dữ liệu thực tế ngày gần nhất ({recent_day_str}) ghi nhận tốc độ download chưa ổn định ({max_downlink/1024/1024:.1f}MB). Nghi ngờ chất lượng sóng tại khu vực khách hàng chưa đảm bảo.",
                "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                "FFF2CC"
            )
        elif is_network_failure_reported:
            return (
                "HOẠT ĐỘNG BÌNH THƯỜNG",
                f"Kiểm tra lịch sử kết nối ngày gần nhất ({recent_day_str}), thuê bao phát sinh lưu lượng data bình thường (phiên lớn nhất đạt {max_downlink/1024/1024:.1f}MB, mạng 4G ổn định).",
                format_normal_plan("Dịch vụ đã hoạt động bình thường. Hướng dẫn khách hàng tiếp tục theo dõi sử dụng."),
                "E2EFDA"
            )
        else:
            return (
                "CHƯA RÕ KỊCH BẢN (KTV XỬ LÝ)",
                "",
                "",
                "FFFFFF"
            )

    # 🎯 KỊCH BẢN LƯU LƯỢNG YẾU (1MB - 10MB)
    if is_weak_traffic:
        island_res = check_island_trouble_scenario()
        if island_res:
            return island_res
        if dominant_cell:
            return (
                "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL",
                f"Dữ liệu trạm phát sóng (CEM) ({dominant_context_str}) ghi nhận thuê bao kết nối chủ yếu qua trạm {dominant_cell} (chiếm {dominant_pct:.0f}% lưu lượng).",
                "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                "FFF2CC"
            )
        else:
            vpn_res = check_tail_vpn()
            if vpn_res:
                return vpn_res
            return (
                "LƯU LƯỢNG YẾU",
                f"Lưu lượng data thực tế ngày gần nhất ({recent_day_str}) ở mức thấp (phiên lớn nhất chỉ đạt từ 1MB đến dưới 10MB), kết nối chập chờn tại khu vực phản ánh.",
                "Chuyển kỹ thuật địa bàn VTT kiểm tra chất lượng vùng phủ sóng tại khu vực khách hàng phản ánh." + action_suffix,
                "FFF2CC"
            )

    # =========================================================================
    # 🔍 PHÂN TÍCH LƯU LƯỢNG BTOOLS NHIỀU NGÀY & ĐỐI CHIẾU GÓI CƯỚC 3 NGUỒN
    # (Tóm tắt AI/Phản ánh KH vs Gói SAPC vs Service ID BTools)
    # =========================================================================
    
    # 1. Phân tích lưu lượng data BTools theo từng ngày
    start_scan_date = (datetime.now() - timedelta(days=4)).date()
    daily_traffic = {}  # date -> total_mb
    daily_max_session = {} # date -> max session mb
    all_btools_services = set()
    btools_service_codes = set()
    btools_service_volumes = {}       # code -> total MB (chỉ trong 5 ngày quét chuẩn)
    btools_service_max_session = {}   # code -> max session MB (chỉ trong 5 ngày quét chuẩn)
    max_session_mb = 0.0

    for row in (clean_data or []):
        t_str = row.get("RECORD_OPENING_TIME", "")
        if not t_str:
            continue
        try:
            d_str = t_str.split(" ")[0]
            d_obj = datetime.strptime(d_str, "%d/%m/%Y").date()
        except Exception:
            continue
        try:
            dl = float(row.get("DATA_VOLUME_DOWNLINK") or 0)
            ul = float(row.get("DATA_VOLUME_UPLINK") or 0)
            mb = (dl + ul) / (1024 * 1024)
        except Exception:
            mb = 0.0
        daily_traffic[d_obj] = daily_traffic.get(d_obj, 0.0) + mb
        if mb > daily_max_session.get(d_obj, 0.0):
            daily_max_session[d_obj] = mb
        
        # Chỉ đưa vào các chỉ số phân tích kịch bản nếu thuộc phạm vi 5 ngày chuẩn
        if d_obj >= start_scan_date:
            if mb > max_session_mb:
                max_session_mb = mb
            
            sc_name = str(row.get("SERVICE_NAME") or "").strip()
            sc_code = str(row.get("SERVICE_ID_CODE") or row.get("SERVICE_ID") or "").strip()
            if sc_name and sc_name.lower() != "none":
                all_btools_services.add(sc_name)
            elif sc_code and sc_code.lower() != "none":
                all_btools_services.add(sc_code)

            if sc_code and sc_code.lower() not in ["none", "null", ""]:
                c_clean = sc_code.lstrip("0") or "0"
                btools_service_codes.add(sc_code)
                btools_service_codes.add(c_clean)
                btools_service_volumes[sc_code] = btools_service_volumes.get(sc_code, 0.0) + mb
                btools_service_volumes[c_clean] = btools_service_volumes.get(c_clean, 0.0) + mb
                btools_service_max_session[sc_code] = max(btools_service_max_session.get(sc_code, 0.0), mb)
                btools_service_max_session[c_clean] = max(btools_service_max_session.get(c_clean, 0.0), mb)

    sorted_dates = sorted(daily_traffic.keys())
    latest_traffic_date = sorted_dates[-1] if sorted_dates else latest_date_in_log
    recent_traffic_mb = daily_traffic.get(latest_traffic_date, 0.0) if latest_traffic_date else 0.0

    # Xác định chuỗi ngày liên tiếp tính từ ngày gần nhất trở về trước không phát sinh data thực tế
    # (Một ngày coi là không có data thực tế nếu tổng < 1.0MB hoặc (tổng < 3.0MB và session lớn nhất < 0.8MB))
    no_data_dates = []
    for d in reversed(sorted_dates):
        d_mb = daily_traffic.get(d, 0.0)
        d_max = daily_max_session.get(d, 0.0)
        if d_mb < 1.0 or (d_mb < 3.0 and d_max < 0.8):
            no_data_dates.append(d)
        else:
            break
    no_data_dates.reverse()

    start_no_data_date = no_data_dates[0] if no_data_dates else None
    start_no_data_str = start_no_data_date.strftime('%d/%m/%Y') if start_no_data_date else ""
    count_no_data_days = len(no_data_dates)

    # Các ngày trước chuỗi lỗi (hoặc trước ngày gần nhất)
    split_date = start_no_data_date if start_no_data_date else latest_traffic_date
    prior_traffic_dates = [d for d in sorted_dates if (split_date and d < split_date)]
    prior_traffic_mb = sum(daily_traffic[d] for d in prior_traffic_dates)
    last_good_date = prior_traffic_dates[-1] if prior_traffic_dates else None
    last_good_str = last_good_date.strftime('%d/%m/%Y') if last_good_date else ""

    # 2. Bóc tách danh sách gói cước & dung lượng từ Tóm tắt AI / Nội dung phản ánh
    vol_ai = None
    combined_text = f"{package_title} {ticket_content}"
    if phone_84:
        try:
            from db_manager import get_db_connection
            conn = get_db_connection()
            with conn:
                if incident_time_str:
                    row = conn.execute("SELECT ai_summary, ticket_content FROM tickets WHERE (phone = ? OR phone LIKE ?) AND incident_time = ?", (phone_84, f"%{phone_84[-9:]}%", incident_time_str)).fetchone()
                else:
                    row = conn.execute("SELECT ai_summary, ticket_content FROM tickets WHERE phone = ? OR phone LIKE ? ORDER BY updated_at DESC LIMIT 1", (phone_84, f"%{phone_84[-9:]}%")).fetchone()
                if row:
                    combined_text = f"{combined_text} {row[0] or ''} {row[1] or ''}"
        except Exception:
            pass

    extracted_pkgs_ai = extract_packages_from_text(combined_text)
    pkg_ai = extracted_pkgs_ai[0] if extracted_pkgs_ai else None

    content_lower = combined_text.lower()
    m_vol = re.search(r'(?:dung lượng còn|còn|đã sử dụng)[:\s]*([\d.,]+)\s*(gb|mb|g)\b', content_lower)
    if m_vol:
        vol_ai = f"{m_vol.group(1)}{m_vol.group(2).upper()}"

    # 3. Lấy thông tin gói cước SAPC
    active_pkgs, expired_pkgs = get_sapc_package_validity(phone_84, incident_time_str=incident_time_str)

    # Dịch vụ thương mại thực sự đang hoạt động trên BTools (loại bỏ app miễn cước bypass)
    APP_SERVICES = {"momo", "zalo", "mytv", "vieon", "facebook", "tiktok", "youtube"}
    active_btools_commercial = [
        s for s in all_btools_services
        if not any(app in s.lower() for app in APP_SERVICES)
    ]

    # A: Toàn bộ gói cước đã hết hạn trên SAPC
    if not active_pkgs and expired_pkgs:
        exp_names = ", ".join([p["name"] for p in expired_pkgs])
        exp_dates = ", ".join([p["exp_str"] for p in expired_pkgs])
        return (
            "GÓI CƯỚC ĐÃ HẾT HẠN",
            f"Gói cước data của thuê bao ({exp_names}) đã hết hạn từ ngày {exp_dates}, tài khoản không còn dung lượng ưu đãi dẫn đến không truy cập được Internet.",
            f"Thông báo khách hàng gói cước ({exp_names}) đã hết hạn sử dụng. Tư vấn khách hàng nạp tiền gia hạn hoặc đăng ký gói cước mới phù hợp." + action_suffix,
            "FFF2CC"
        )

    # B: Chỉ có gói cước mặc định PAYGO hoặc gói tiện ích Add-on
    addon_pkgs = [p for p in active_pkgs if p.get("is_addon_app")]
    if active_pkgs and all(p.get("is_paygo") or p.get("is_addon_app") for p in active_pkgs) and not [p for p in active_pkgs if not p.get("is_paygo") and not p.get("is_addon_app")]:
        if addon_pkgs:
            addon_names = ", ".join([p["name"] for p in addon_pkgs])
            return (
                "CHỈ CÓ GÓI TIỆN ÍCH - THIẾU DATA INTERNET",
                f"Thuê bao hiện chỉ có gói tiện ích ({addon_names}) chạy trên nền PAYGO/M0, không có gói data Internet chính thức.",
                f"Tư vấn khách hàng đăng ký thêm các gói Data VinaPhone (VD120N, YOLO...) để truy cập mạng bình thường." + action_suffix,
                "FFF2CC"
            )
        return (
            "CHỈ CÓ GÓI PAYGO",
            f"Thuê bao hiện chỉ có gói cước mặc định (PAYGO/M0), không có gói data ưu đãi và tài khoản chính không đủ để trừ cước truy cập ngoài gói.",
            "Hướng dẫn khách hàng kiểm tra số dư tài khoản chính, đồng thời tư vấn đăng ký các gói cước Data VinaPhone ưu đãi để sử dụng." + action_suffix,
            "FFF2CC"
        )

    # C: XỬ LÝ CASE 1 & CASE 2 THEO GÓI CƯỚC THƯƠNG MẠI SAPC VÀ LƯU LƯỢNG BTOOLS
    commercial_pkgs = [p for p in active_pkgs if not p.get("is_paygo") and not p.get("is_home") and not p.get("is_no_date") and not p.get("is_addon_app")]
    earliest_reg_dt = min([p["reg_dt"] for p in commercial_pkgs if p.get("reg_dt")], default=None)
    act_names = ", ".join([p["name"] for p in commercial_pkgs])
    act_exp_dates = ", ".join([p["exp_str"] for p in commercial_pkgs])
    act_reg_dates = ", ".join([p["reg_str"] for p in commercial_pkgs if p.get("reg_str") != "N/A"]) or "trước đó"
    start_scan_date = (datetime.now() - timedelta(days=4)).date()

    # Tính tổng lưu lượng trong chu kỳ 5 ngày gần đây và trước đó
    prior_rows = []
    recent_5d_rows = []
    for r in (clean_data or []):
        t_str = r.get("RECORD_OPENING_TIME", "")
        if not t_str:
            continue
        try:
            d = datetime.strptime(t_str.split()[0], "%d/%m/%Y").date()
            if d < start_scan_date:
                prior_rows.append(r)
            else:
                recent_5d_rows.append(r)
        except Exception:
            recent_5d_rows.append(r)

    prior_mb = sum((float(r.get("DATA_VOLUME_DOWNLINK") or 0) + float(r.get("DATA_VOLUME_UPLINK") or 0))/(1024*1024) for r in prior_rows)
    recent_5d_mb = sum((float(r.get("DATA_VOLUME_DOWNLINK") or 0) + float(r.get("DATA_VOLUME_UPLINK") or 0))/(1024*1024) for r in recent_5d_rows)
    has_4g_recent = any(
        str(r.get("RAT_TYPE") or r.get("RAT_TYPE_CODE") or "") in ["6", "7"] 
        or "4G" in str(r.get("RAT_TYPE_NAME") or "").upper() 
        or "LTE" in str(r.get("RAT_TYPE_NAME") or "").upper() 
        for r in recent_5d_rows
    )
    has_real_session_5d = any(
        (float(r.get("DATA_VOLUME_DOWNLINK") or 0) + float(r.get("DATA_VOLUME_UPLINK") or 0)) / (1024 * 1024) >= 1.0
        for r in recent_5d_rows
    )
    is_no_real_traffic_5d = (recent_5d_mb < 1.0) or (not has_real_session_5d and recent_5d_mb < 5.0)

    if commercial_pkgs and (recent_5d_mb < 1.0 or is_no_real_traffic_5d):
        all_act_names = ", ".join([p["name"] for p in commercial_pkgs])
        extra_ai_note = f", khách hàng phản ánh gói [{pkg_ai}]" if (pkg_ai and pkg_ai not in act_names) else ""
        rec_codes = [c for c in sorted(list(btools_service_codes)) if len(c) <= 5 and c not in ["0", "00"]]
        rec_codes_str = f" (BTools chỉ ghi nhận mã {', '.join(rec_codes[:3])})" if rec_codes else " (BTools không ghi nhận mã cước data hợp lệ)"
        # Case 1: Gói mới đăng ký trong 5 ngày qua -> ĐÓNG PHIẾU LUÔN
        if earliest_reg_dt and earliest_reg_dt.date() >= start_scan_date:
            return (
                "GÓI CÒN HẠN - KHÔNG DÙNG ĐƯỢC",
                f"Hồ sơ SAPC ghi nhận gói [{all_act_names}]{extra_ai_note} đăng ký ngày {act_reg_dates} (còn hạn đến {act_exp_dates}) nhưng từ khi đăng ký đến nay không phát sinh dữ liệu sử dụng thực tế{rec_codes_str}, nghi ngờ lỗi luồng cước/profile gói.",
                f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {all_act_names}{f' và gói {pkg_ai}' if (pkg_ai and pkg_ai not in act_names) else ''} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao.",
                "FFF2CC"
            )

        # Case 2: Gói đăng ký trước chu kỳ 5 ngày -> Thực hiện hành vi bổ sung tra thêm BTools
        elif earliest_reg_dt and earliest_reg_dt.date() < start_scan_date:
            if not prior_rows:
                try:
                    from crawler_btools import fetch_supplementary_btools_if_needed
                    clean_data = fetch_supplementary_btools_if_needed(driver, phone_84, clean_data, earliest_reg_dt, start_scan_date)
                except Exception:
                    pass
                prior_rows = []
                for r in (clean_data or []):
                    t_str = r.get("RECORD_OPENING_TIME", "")
                    if t_str:
                        try:
                            d = datetime.strptime(t_str.split()[0], "%d/%m/%Y").date()
                            if d < start_scan_date:
                                prior_rows.append(r)
                        except Exception:
                            pass
                prior_mb = sum((float(r.get("DATA_VOLUME_DOWNLINK") or 0) + float(r.get("DATA_VOLUME_UPLINK") or 0))/(1024*1024) for r in prior_rows)

            # Mô tả khoảng thời gian không có data thực tế
            if count_no_data_days >= 2 and start_no_data_str:
                time_no_data_desc = f"từ ngày {start_no_data_str} đến nay ({count_no_data_days} ngày) không phát sinh data thực tế"
            else:
                time_no_data_desc = "gần đây không phát sinh data thực tế (dưới 1MB)"

            # Nhánh 2A: Sau khi tra bổ sung, từ lúc đăng ký đến nay cũng KHÔNG CÓ PHÁT SINH DATA (<1MB) -> Giống Case 1, ĐÓNG PHIẾU LUÔN
            if prior_mb < 1.0:
                return (
                    "GÓI CÒN HẠN - KHÔNG DÙNG ĐƯỢC",
                    f"Hồ sơ SAPC ghi nhận gói [{all_act_names}]{extra_ai_note} đăng ký ngày {act_reg_dates} (còn hạn đến {act_exp_dates}) nhưng từ khi đăng ký đến nay không phát sinh dữ liệu sử dụng thực tế{rec_codes_str}, nghi ngờ lỗi luồng cước/profile gói.",
                    f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {all_act_names}{f' và gói {pkg_ai}' if (pkg_ai and pkg_ai not in act_names) else ''} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao.",
                    "FFF2CC"
                )
            # Nhánh 2B: Có phát sinh data trước đó, chỉ gần đây không phát sinh dù bắt RAT TYPE = 6 (4G) bình thường -> ĐÓNG PHIẾU LUÔN
            elif has_4g_recent:
                return (
                    "LỖI THIẾT BỊ / SIM TREO DATA",
                    f"Thuê bao có gói cước {act_names} đã từng phát sinh dữ liệu bình thường từ khi đăng ký ({act_reg_dates}), tuy nhiên {time_no_data_desc} dù thiết bị vẫn bắt sóng 4G bình thường (RAT TYPE = 6). Có thể do thiết bị hoặc SIM của khách hàng bị treo data.",
                    "Có thể do thiết bị hoặc SIM, nhờ kiểm tra SIM và thiết bị giúp (thử khởi động lại máy, bật/tắt dữ liệu di động hoặc tháo lắp SIM sang máy khác kiểm tra).",
                    "FFF2CC"
                )
            else:
                good_note = f", ngày dùng tốt gần nhất {last_good_str}" if last_good_str else ""
                return (
                    "KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ",
                    f"Lịch sử BTools các ngày trước phát sinh data bình thường ({prior_mb:.1f}MB{good_note}), nhưng {time_no_data_desc}.",
                    "Nghi ngờ do thiết bị của khách hàng bị treo data. Nhờ khách hàng thử tắt/bật thiết bị và data, speedtest lại giúp." + action_suffix,
                    "FFF2CC"
                )

    # D: Trường hợp đi nhiều nơi bị lỗi (Chỉ kết luận do máy khi các ngày trước ĐÃ DÙNG DATA BÌNH THƯỜNG >= 1MB)
    if is_reported_multiple_places and not dominant_cell and prior_traffic_mb >= 1.0:
        vpn_res = check_tail_vpn()
        if vpn_res:
            return vpn_res
        return (
            "LỖI THIẾT BỊ / ĐI NHIỀU NƠI BỊ LỖI",
            "Khách hàng phản ánh đi nhiều nơi đều bị lỗi, dữ liệu mạng ghi nhận thuê bao đổi trạm liên tục qua nhiều khu vực khác nhau nhưng đều không load được data (<1MB). Nguyên nhân do xung đột cài đặt mạng, lỗi SIM hoặc thiết bị đầu cuối của khách hàng.",
            "Hướng dẫn khách hàng khởi động lại máy, bật/tắt chế độ máy bay, vệ sinh lại khay SIM hoặc mang SIM qua điểm giao dịch VinaPhone gần nhất để kiểm tra đổi SIM." + action_suffix,
            "FFF2CC"
        )

    # E: Gói tích hợp HOME / nhiều gói cước (Case 2: check serviceid & phiên > 1MB)
    VALID_DATA_SERVICE_CODES = {
        "3000", "0000003000", "3001", "0000003001", "3600", "0000003600",
        "3601", "0000003601", "3602", "0000003602", "3603", "0000003603",
        "3605", "0000003605", "3622", "0000003622", "3623", "0000003623",
        "3632", "0000003632", "4000", "0000004000", "5000", "0000005000",
        "5500", "0000005500", "5800", "0000005800", "6000", "0000006000",
        "8301", "0000008301", "8604", "0000008604", "9301", "0000009301"
    }
    THROTTLING_SERVICE_CODES = {"10002", "0000010002", "10003", "0000010003"}
    has_throttling_code = bool(THROTTLING_SERVICE_CODES.intersection(btools_service_codes))
    has_session_over_1mb = max_session_mb >= 1.0

    # Gom danh sách tất cả các gói cước đang có (SAPC active packages + AI summary packages)
    all_pkg_names = set(p["name"] for p in active_pkgs)
    for p_name in (extracted_pkgs_ai or []):
        all_pkg_names.add(p_name)

    # Gom toàn bộ expected service IDs của các gói mà KH sở hữu
    all_expected_codes = set()
    for p in active_pkgs:
        grp = str(p.get("group_name") or "").strip()
        if grp and grp.lower() not in ["none", "null", ""]:
            all_expected_codes.add(grp)
            all_expected_codes.add(grp.lstrip("0") or "0")
            all_expected_codes.add(grp.zfill(10))
    for p_name in all_pkg_names:
        all_expected_codes.update(get_expected_service_codes_for_pkg(p_name))

    # CẨN THẬN KHI SO SÁNH: Kiểm tra xem có gói thương mại nào đang chạy data tốt không
    # (Có Service ID trong BTools và có lưu lượng >= 1MB hoặc phiên >= 1MB)
    has_working_commercial_pkg = False
    for p_name in all_pkg_names:
        exp_c = get_expected_service_codes_for_pkg(p_name)
        comm_codes = exp_c - THROTTLING_SERVICE_CODES
        for code in comm_codes:
            if btools_service_volumes.get(code, 0.0) >= 1.0 or btools_service_max_session.get(code, 0.0) >= 1.0:
                has_working_commercial_pkg = True
                break
        if has_working_commercial_pkg:
            break

    # 1. Phát hiện mã hạ băng thông trên BTools (10002 / 10003)
    if has_throttling_code and not has_working_commercial_pkg:
        pkg_names = ", ".join(sorted(list(all_pkg_names))) if all_pkg_names else "HOME/Gia đình"
        return (
            "LỖI GÓI HOME / NGHẼN BĂNG THÔNG",
            f"Lịch sử BTools ghi nhận mã dịch vụ 10002/10003 (Hạ băng thông gói HOME/Gia đình). Thuê bao {pkg_names} đang bị bóp băng thông nên không thể truy cập Internet tốc độ cao.",
            f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {pkg_names} và khôi phục lưu lượng tốc độ cao cho thuê bao.",
            "FFF2CC"
        )

    # 2. Case 2: Thuê bao có gói tích hợp HOME (kể cả có thêm gói cước khác)
    has_home_pkg = any("HOME" in p.upper() or "GD" in p.upper() or "GIA DINH" in p.upper() for p in all_pkg_names)
    if has_home_pkg and not has_working_commercial_pkg:
        has_pkg_working = any(btools_service_volumes.get(c, 0.0) >= 1.0 or btools_service_max_session.get(c, 0.0) >= 1.0 for c in all_expected_codes)
        has_comm_working = any(btools_service_volumes.get(c, 0.0) >= 1.0 or btools_service_max_session.get(c, 0.0) >= 1.0 for c in VALID_DATA_SERVICE_CODES)

        if not has_pkg_working and not has_comm_working and not has_session_over_1mb:
            sapc_str = ", ".join([p["name"] for p in active_pkgs]) if active_pkgs else ""
            ai_str = ", ".join(extracted_pkgs_ai) if extracted_pkgs_ai else ""
            if sapc_str and ai_str and ai_str != sapc_str:
                pkg_desc = f"Hồ sơ SAPC ghi nhận gói [{sapc_str}], khách hàng phản ánh gói [{ai_str}]"
            elif sapc_str:
                pkg_desc = f"Hồ sơ thuê bao sử dụng gói [{sapc_str}]"
            else:
                pkg_desc = f"Khách hàng phản ánh gói [{ai_str}]"
            
            rec_codes = [c for c in sorted(list(btools_service_codes)) if len(c) <= 5 and c not in ["0", "00"]]
            rec_str = f"BTools chỉ ghi nhận mã {', '.join(rec_codes[:3])} nhưng không có mã Service ID data của các gói cước này" if rec_codes else "BTools không ghi nhận mã dịch vụ data của các gói cước này"

            return (
                "LỖI GÓI HOME / NGHẼN BĂNG THÔNG",
                f"{pkg_desc}, tuy nhiên {rec_str} và không có phiên kết nối nào trên 1MB (phiên lớn nhất đạt {max_session_mb:.2f}MB). Nghi ngờ bị bóp băng thông hoặc gói HOME bị lỗi chia sẻ data.",
                f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình các gói [{sapc_str or ai_str}] trên hệ thống và luồng chia sẻ data của thuê bao.",
                "FFF2CC"
            )
        elif active_pkgs and all(p.get("is_home") or p.get("is_no_date") for p in active_pkgs):
            pkg_names = ", ".join([p["name"] for p in active_pkgs])
            return (
                "THEO DÕI THÊM",
                f"Thuê bao sử dụng gói tích hợp ({pkg_names}), hệ thống ghi nhận phát sinh lưu lượng data. Nghi ngờ thiết bị tắt data hoặc đang sử dụng Wifi.",
                f"Hướng dẫn khách hàng bật Dữ liệu di động (Data), khởi động lại thiết bị và theo dõi sử dụng." + action_suffix,
                "E2EFDA"
            )

    # 3. 🎯 XỬ LÝ CASE 1: KH PHẢN ÁNH CÓ GÓI CƯỚC (AI TÓM TẮT HOẶC PHẢN ÁNH)
    # Check Service ID của gói cước, nếu BTools không thấy mã này (hoặc code chưa rõ nhưng data BTools < 1MB)
    # -> BÁO LỖI DO GÓI CƯỚC VÀ ĐÓNG LUÔN!
    if extracted_pkgs_ai and not has_working_commercial_pkg:
        for p_cand in extracted_pkgs_ai:
            expected_codes = get_expected_service_codes_for_pkg(p_cand)
            # Đối chiếu với active_pkgs từ SAPC để lấy thêm Group Name (ví dụ Group Name: 3000)
            for p in active_pkgs:
                if p_cand.upper() in p.get("name", "").upper() or p.get("name", "").upper() in p_cand.upper():
                    grp = str(p.get("group_name") or "").strip()
                    digits = re.sub(r'\D', '', grp)
                    if digits:
                        expected_codes.add(digits)
                        expected_codes.add(digits.lstrip("0") or "0")
                        expected_codes.add(digits.zfill(10))
            has_expected_code = bool(expected_codes.intersection(btools_service_codes))

            sapc_str = ", ".join([p["name"] for p in active_pkgs]) if active_pkgs else ""
            sapc_note = f" (Hồ sơ SAPC ghi nhận gói [{sapc_str}])" if (sapc_str and p_cand not in sapc_str) else ""

            rec_codes = [c for c in sorted(list(btools_service_codes)) if len(c) <= 5 and c not in ["0", "00"]]

            if expected_codes and not has_expected_code and not has_session_over_1mb:
                sample_c = ", ".join(sorted(list(expected_codes))[:3])
                rec_str = f"BTools chỉ ghi nhận mã {', '.join(rec_codes[:3])}, không thấy mã Service ID {sample_c} của gói" if rec_codes else f"BTools không ghi nhận mã Service ID {sample_c} của gói"
                return (
                    "LỖI DO GÓI CƯỚC",
                    f"Khách hàng phản ánh sử dụng gói [{p_cand}]{sapc_note}, tuy nhiên {rec_str} và không phát sinh phiên nào trên 1MB (phiên lớn nhất đạt {max_session_mb:.2f}MB). Nghi ngờ lỗi luồng cước / chưa kích hoạt profile gói.",
                    f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {p_cand}{f' và gói {sapc_str}' if sapc_note else ''} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao.",
                    "FFF2CC"
                )
            elif not expected_codes and (recent_5d_mb < 1.0 or recent_traffic_mb < 1.0 or not has_session_over_1mb):
                rec_str = f"BTools chỉ ghi nhận mã {', '.join(rec_codes[:3])} và lưu lượng không đáng kể (<1MB)" if rec_codes else "lịch sử dữ liệu BTools không phát sinh lưu lượng data đáng kể (<1MB)"
                return (
                    "LỖI DO GÓI CƯỚC",
                    f"Khách hàng phản ánh sử dụng gói [{p_cand}]{sapc_note}, tuy nhiên {rec_str}. Nghi ngờ lỗi luồng cước / gói cước chưa được kích hoạt quyền truy cập data.",
                    f"Chuyển bộ phận IT/Tính cước kiểm tra cấu hình gói {p_cand}{f' và gói {sapc_str}' if sapc_note else ''} trên hệ thống để kích hoạt lại quyền truy cập cho thuê bao.",
                    "FFF2CC"
                )

    # 🎯 KỊCH BẢN ĐẶC THÙ CUỐI CÙNG: PHÁT HIỆN VPN / CLOUDFLARE 1.1.1.1
    vpn_res = check_tail_vpn()
    if vpn_res:
        return vpn_res

    # F: ĐÁNH GIÁ LƯU LƯỢNG NGÀY GẦN ĐÂY KHÔNG CÓ DATA THỰC TẾ (CĂN CỨ MULTI-DAY BTOOLS)
    if count_no_data_days > 0 or recent_traffic_mb < 1.0:
        recent_day_str = latest_traffic_date.strftime('%d/%m/%Y') if latest_traffic_date else "gần nhất"
        
        # Nếu các ngày trước đó BTools KHÔNG CÓ DATA hoặc TỔNG DATA < 1MB -> Khó khẳng định do gói hay thiết bị -> KHÔNG ĐÓNG TỰ ĐỘNG
        if prior_traffic_mb < 1.0:
            if count_no_data_days >= 2 and start_no_data_str:
                time_range_txt = f"từ ngày {start_no_data_str} đến nay ({count_no_data_days} ngày)"
            else:
                time_range_txt = f"ngày gần nhất ({recent_day_str})"
            return (
                "KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ - CHƯA RÕ NGUYÊN NHÂN",
                f"Lịch sử BTools {time_range_txt} và các ngày trước đó đều không phát sinh lưu lượng đáng kể (<1MB). "
                f"Chưa đủ cơ sở để khẳng định nguyên nhân do thiết bị của khách hàng bị treo data hay do gói cước/dịch vụ mạng.",
                "Yêu cầu KTV liên hệ khách hàng kiểm tra thực tế thiết bị và tình trạng gói cước. Không đóng phiếu tự động.",
                "FFF2CC"
            )
        else:
            # Các ngày trước đó có data >= 1MB (đã từng dùng bình thường), chỉ các ngày gần đây không có data thực tế
            if count_no_data_days >= 2 and start_no_data_str:
                good_note = f", ngày dùng tốt gần nhất {last_good_str}" if last_good_str else ""
                return (
                    "KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ",
                    f"Lịch sử BTools trước đó phát sinh data bình thường ({prior_traffic_mb:.1f}MB{good_note}), "
                    f"tuy nhiên từ ngày {start_no_data_str} đến nay ({count_no_data_days} ngày) gần như không phát sinh lưu lượng sử dụng thực tế (chỉ có các phiên duy trì lắt nhắt dưới 1MB).",
                    "Nghi ngờ do thiết bị của khách hàng bị treo data. Nhờ khách hàng thử tắt/bật thiết bị và data, speedtest lại giúp." + action_suffix,
                    "FFF2CC"
                )
            else:
                return (
                    "KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ",
                    f"Lịch sử BTools các ngày trước phát sinh data bình thường ({prior_traffic_mb:.1f}MB), "
                    f"nhưng ngày gần nhất ({recent_day_str}) gần như không phát sinh lưu lượng sử dụng thực tế (dưới 1MB).",
                    "Nghi ngờ do thiết bị của khách hàng bị treo data. Nhờ khách hàng thử tắt/bật thiết bị và data, speedtest lại giúp." + action_suffix,
                    "FFF2CC"
                )

    recent_day_str = latest_traffic_date.strftime('%d/%m/%Y') if latest_traffic_date else "gần nhất"
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

    # Subtitle Copyright Banner
    ws.merge_cells("A2:L2")
    sub_cell = ws["A2"]
    sub_cell.value = "VNPT TTS PRECHECK • Copyright by quangvu@vnpt.vn (Sep.2026)"
    sub_cell.font = Font(name="Segoe UI", size=9.5, italic=True, color="595959")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18
    
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
        if rec["status"] == "PROFILE LẠ" or "PROFILE LẠ" in str(rec.get("status", "")) or rec.get("color") in ["FFC7CE", "F8D7DA"]:
            s_cell.font = Font(name="Segoe UI", size=11, bold=True, color="9C0006")
            s_cell.fill = PatternFill(start_color="FFC7CE", fill_type="solid")
        else:
            raw_c = str(rec.get("color") or "FFFFFF").replace("#", "").strip().upper()
            safe_c = raw_c if len(raw_c) in (6, 8) else "FFFFFF"
            s_cell.font = Font(name="Segoe UI", size=11, bold=True, color="333333")
            s_cell.fill = PatternFill(start_color=safe_c, fill_type="solid")
        
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
        p_val = rec["real_packages"]
        p_cell5 = ws.cell(row=current_row, column=5, value=p_val)
        p_cell5.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        if "PROFILE LẠ" in str(p_val):
            p_cell5.font = Font(name="Segoe UI", size=10.5, color="C00000", bold=True)

        # 🎯 CỘT 6 (F): HẠ TẦNG KẾT NỐI
        ws.cell(row=current_row, column=6, value=rec["rat_types"]).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        
        # 🎯 CỘT 7 (G): DỮ LIỆU CEM (TOP 3 CELL BẮT SÓNG TRONG 5 NGÀY)
        cem_text = rec.get("cem_data", "Không có dữ liệu CEM")
        cem_cell = ws.cell(row=current_row, column=7, value=cem_text)
        cem_cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        if "CẢNH BÁO VPN" in cem_text or "VPN:" in cem_text:
            cem_cell.font = Font(name="Segoe UI", size=10.5, color="C00000", bold=True)

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
        if "Phiếu mở lại" in str(comment_text):
            c_cell.font = Font(name="Segoe UI", size=11, bold=True, color="C00000")
        elif "Lưu ý: 2 ngày gần nhất không thấy phát sinh data" in comment_text:
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
            if c not in [1, 2, 5, 7, 9, 10, 11, 12]: # Chừa các ô có định dạng font đặc biệt
                ws.cell(row=current_row, column=c).font = Font(name="Segoe UI", size=11)
            elif c == 5 and "PROFILE LẠ" not in str(p_val):
                ws.cell(row=current_row, column=c).font = Font(name="Segoe UI", size=11)
            elif c == 7 and "CẢNH BÁO VPN" not in str(cem_text) and "VPN:" not in str(cem_text):
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