# services/sms_analyzer.py
# Module phân tích nội dung phản ánh tin nhắn (SMS): Bóc tách Thực thể & Kịch bản Automation

import re
from datetime import datetime, timedelta


# Danh mục các Ứng dụng / Ngân hàng / Đầu số OTP phổ biến
KNOWN_APPS_AND_BANKS = [
    ("1414", ["1414", "tttb"]),
    ("My VNPT", ["my vnpt", "myvnpt"]),
    ("VNeID", ["vneid", "vne-id", "định danh điện tử", "dinh danh"]),
    ("Vietcombank", ["vietcombank", "vcb", "digibank"]),
    ("MB Bank", ["mb bank", "mbbank", "ngân hàng quân đội", r"\bmb\b"]),
    ("Agribank", ["agribank"]),
    ("BIDV", ["bidv", "smartbanking"]),
    ("VietinBank", ["vietinbank", "vietin bank", "i-pay"]),
    ("TPBank", ["tpbank", "tp bank"]),
    ("Techcombank", ["techcombank", "tcb"]),
    ("ACB", [r"\bacb\b", "á châu"]),
    ("SHB", [r"\bshb\b"]),
    ("HD Bank", ["hdbank", "hd bank"]),
    ("Nam A Bank", ["nam a", "namabank"]),
    ("VPBank", ["vpbank", "vp bank", "neo"]),
    ("Sacombank", ["sacombank"]),
    ("Momo", ["momo", "ví momo"]),
    ("Zalo", ["zalo", "zalo pay", "zalopay"]),
    ("Facebook", ["facebook", r"\bfb\b", "meta"]),
    ("Shopee", ["shopee", "shopeepay"]),
    ("Lazada", ["lazada"]),
    ("TikTok", ["tiktok", "tik tok"]),
    ("Telegram", ["telegram"]),
    ("Xanh SM", ["xanh sm", "xanhsm"]),
    ("VETC / EPASS", ["vetc", "epass", "etc"]),
]

# Danh mục các Dòng máy / Hệ điều hành phổ biến
KNOWN_DEVICES = [
    ("iPhone (iOS)", ["iphone", "ip1", "ip2", "ip3", "ip4", "ip5", "ip6", "ip7", "ip8", "ip9", "ipx", "ip x", "apple", "ios", "ipad"]),
    ("Samsung", ["samsung", "galaxy", "ss "]),
    ("Oppo", ["oppo", "reno"]),
    ("Vivo", ["vivo"]),
    ("Xiaomi / Redmi", ["xiaomi", "redmi", "mi "]),
    ("Realme", ["realme"]),
    ("Huawei", ["huawei"]),
    ("Nokia", ["nokia"]),
]


def parse_sms_entities(ticket_content: str, incident_time_fallback: str = "", package_title: str = "") -> dict:
    """
    Bóc tách toàn diện các thực thể (Entities) phục vụ hiển thị tóm tắt và Automation.
    Được module hóa độc lập tại ai_sms_interpreter.py.
    """
    from ai_sms_interpreter import interpret_sms_ticket
    return interpret_sms_ticket(ticket_content, package_title=package_title, incident_time_fallback=incident_time_fallback)

def _legacy_parse_sms_entities(ticket_content: str, incident_time_fallback: str = "") -> dict:
    raw = str(ticket_content or "").strip()
    low = raw.lower()
    pad = lambda n: str(n).zfill(2)

    # 1. Bóc tách Mốc thời gian sự cố (Incident Time) & Dải ngày cho CDR
    fallback_year = 2026
    fallback_month = 10
    fallback_day = 1
    if incident_time_fallback:
        y_match = re.search(r'\b(20\d{2})\b', str(incident_time_fallback))
        if y_match:
            fallback_year = int(y_match.group(1))
        dm_match = re.search(r'(\d{1,2})[/\-](\d{1,2})', str(incident_time_fallback))
        if dm_match:
            fallback_day = int(dm_match.group(1))
            fallback_month = int(dm_match.group(2))

    detected_time = ""
    from_date = ""
    to_date = ""
    time_range_desc = ""

    # Quét giờ xảy ra nếu có (vd: 09:15, 9h30, lúc 14:00)
    time_str = ""
    t_match = re.search(r'\b([0-2]?[0-9])[:hH]([0-5][0-9])(?:\s*(?:phút|p))?\b', raw)
    if t_match:
        time_str = f"{pad(int(t_match.group(1)))}:{pad(int(t_match.group(2)))}"

    # 0. Quét Khoảng Ngày Cụ Thể (Date Range, vd: 13-09-2026 - 20-09-2026, từ 13/09 đến 20/09/2026, 08/10 → 11/10/2026)
    range_pat = re.compile(
        r'(?:từ\s+(?:ngày\s+)?)?([0-3]?[0-9])[/\-]([0-1]?[0-9])(?:[/\-](20\d{2}|\d{2}))?'
        r'\s*(?:đến|\-|–|—|->|→|tới)\s*'
        r'(?:ngày\s+)?([0-3]?[0-9])[/\-]([0-1]?[0-9])(?:[/\-](20\d{2}|\d{2}))?',
        re.IGNORECASE
    )
    m_range = range_pat.search(raw)
    if not m_range and incident_time_fallback:
        m_range = range_pat.search(str(incident_time_fallback))

    # 1. Full date dd/mm/yyyy (vd: 14/10/2026, 05/10/2026)
    m_full = None
    if not m_range:
        m_full = re.search(r'\b([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20\d{2}|\d{2})\b', raw)

    # 2. Month pattern (vd: cước tháng 09/2026, trong tháng 9, T09/2026, hoặc độc lập 09/2026)
    m_month = None
    if not m_range:
        m_month = re.search(r'(?<![0-9/])(?:trong\s+tháng|cước\s+tháng|tháng|t)\s*([0-1]?[0-9])(?:\s*[/\-]\s*(20\d{2}))?\b', raw, re.IGNORECASE)
        if not m_month and not m_full:
            m_month = re.search(r'(?<![0-9/])([0-1]?[0-9])[/\-](20\d{2})\b', raw)
        if not m_month and incident_time_fallback:
            m_month = re.search(r'(?<![0-9/])(?:trong\s+tháng|cước\s+tháng|tháng|t)\s*([0-1]?[0-9])(?:\s*[/\-]\s*(20\d{2}))?\b', str(incident_time_fallback), re.IGNORECASE) or \
                      re.search(r'(?<![0-9/])([0-1]?[0-9])[/\-](20\d{2})\b', str(incident_time_fallback))

    # 3. Day/Month without year (vd: ngày 28/08, 14/10, lúc 14:00 ngày 28/08)
    m_dm = None
    if not m_range and not m_full and not m_month:
        m_dm = re.search(r'(?:ngày|hôm|lúc|từ)\s*([0-3]?[0-9])[/\-]([0-1]?[0-9])\b', raw, re.IGNORECASE) or \
               re.search(r'(?<![0-9/])([0-3]?[0-9])[/\-]([0-1]?[0-9])(?![0-9/])', raw)

    if m_range:
        d1, m1, y1, d2, m2, y2 = m_range.groups()
        d1, m1, d2, m2 = int(d1), int(m1), int(d2), int(m2)
        if 1 <= d1 <= 31 and 1 <= m1 <= 12 and 1 <= d2 <= 31 and 1 <= m2 <= 12:
            y2_val = int(f"20{y2}") if (y2 and len(y2) == 2) else (int(y2) if y2 else fallback_year)
            y1_val = int(f"20{y1}") if (y1 and len(y1) == 2) else (int(y1) if y1 else y2_val)
            try:
                dt1 = datetime(y1_val, m1, d1)
                dt2 = datetime(y2_val, m2, d2)
                if dt1 <= dt2:
                    from_date = dt1.strftime("%Y-%m-%d 00:00:00")
                    to_date = dt2.strftime("%Y-%m-%d 23:59:59")
                    time_range_desc = f"{pad(d1)}/{pad(m1)} → {pad(d2)}/{pad(m2)}/{y2_val}"
                    detected_time = f"{pad(d1)}/{pad(m1)}/{y1_val} → {pad(d2)}/{pad(m2)}/{y2_val}"
            except Exception:
                from_date = f"{y1_val}-{pad(m1)}-{pad(d1)} 00:00:00"
                to_date = f"{y2_val}-{pad(m2)}-{pad(d2)} 23:59:59"
                time_range_desc = f"{pad(d1)}/{pad(m1)} → {pad(d2)}/{pad(m2)}/{y2_val}"
                detected_time = time_range_desc

    elif m_full:
        d_val = int(m_full.group(1))
        m_val = int(m_full.group(2))
        raw_y = m_full.group(3)
        y_val = int(f"20{raw_y}") if len(raw_y) == 2 else int(raw_y)
        if 1 <= d_val <= 31 and 1 <= m_val <= 12:
            base_date_str = f"{pad(d_val)}/{pad(m_val)}/{y_val}"
            detected_time = f"{time_str} ngày {base_date_str}" if time_str else base_date_str
            try:
                target_dt = datetime(y_val, m_val, d_val)
                prev_dt = target_dt - timedelta(days=1)
                next_dt = target_dt + timedelta(days=1)
                from_date = prev_dt.strftime("%Y-%m-%d 00:00:00")
                to_date = next_dt.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{prev_dt.strftime('%d/%m')} → {next_dt.strftime('%d/%m/%Y')}"
            except Exception:
                from_date = f"{y_val}-{pad(m_val)}-{pad(d_val)} 00:00:00"
                to_date = f"{y_val}-{pad(m_val)}-{pad(d_val)} 23:59:59"
                time_range_desc = base_date_str

    elif m_month:
        m_val = int(m_month.group(1))
        if 1 <= m_val <= 12:
            yr = int(m_month.group(2)) if (len(m_month.groups()) >= 2 and m_month.group(2)) else fallback_year
            if m_val in (1, 3, 5, 7, 8, 10, 12):
                last_day = 31
            elif m_val in (4, 6, 9, 11):
                last_day = 30
            else:
                last_day = 29 if (yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)) else 28

            detected_time = f"Tháng {pad(m_val)}/{yr}"
            from_date = f"{yr}-{pad(m_val)}-01 00:00:00"
            to_date = f"{yr}-{pad(m_val)}-{pad(last_day)} 23:59:59"
            time_range_desc = f"01/{pad(m_val)}/{yr} → {pad(last_day)}/{pad(m_val)}/{yr} ({detected_time})"

    elif m_dm:
        d_val = int(m_dm.group(1))
        m_val = int(m_dm.group(2))
        y_val = fallback_year
        if 1 <= d_val <= 31 and 1 <= m_val <= 12:
            base_date_str = f"{pad(d_val)}/{pad(m_val)}/{y_val}"
            detected_time = f"{time_str} ngày {base_date_str}" if time_str else base_date_str
            try:
                target_dt = datetime(y_val, m_val, d_val)
                prev_dt = target_dt - timedelta(days=1)
                next_dt = target_dt + timedelta(days=1)
                from_date = prev_dt.strftime("%Y-%m-%d 00:00:00")
                to_date = next_dt.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{prev_dt.strftime('%d/%m')} → {next_dt.strftime('%d/%m/%Y')}"
            except Exception:
                from_date = f"{y_val}-{pad(m_val)}-{pad(d_val)} 00:00:00"
                to_date = f"{y_val}-{pad(m_val)}-{pad(d_val)} 23:59:59"
                time_range_desc = base_date_str

    # ƯU TIÊN 3: Fallback theo ngày tiếp nhận trên hệ thống
    if not detected_time:
        if incident_time_fallback and incident_time_fallback != "--":
            detected_time = incident_time_fallback.split(" ")[0] if " " in incident_time_fallback else incident_time_fallback
            try:
                base_dt = datetime(fallback_year, fallback_month, fallback_day)
                past3 = base_dt - timedelta(days=3)
                from_date = past3.strftime("%Y-%m-%d 00:00:00")
                to_date = base_dt.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{past3.strftime('%d/%m')} → {base_dt.strftime('%d/%m/%Y')}"
            except Exception:
                from_date = ""
                to_date = ""
                time_range_desc = detected_time
        else:
            detected_time = "--"
            now_dt = datetime.now()
            past3 = now_dt - timedelta(days=3)
            from_date = past3.strftime("%Y-%m-%d 00:00:00")
            to_date = now_dt.strftime("%Y-%m-%d 23:59:59")
            time_range_desc = "3 ngày gần nhất"

    # 2. Bóc tách Ứng dụng / Ngân hàng OTP (App / Brandname)
    app_brand = ""
    for standard_name, keywords in KNOWN_APPS_AND_BANKS:
        matched = False
        for kw in keywords:
            if kw.startswith(r"\b"):
                if re.search(kw, low):
                    matched = True
                    break
            elif kw in low:
                matched = True
                break
        if matched:
            app_brand = standard_name
            break

    if not app_brand:
        bank_match = re.search(r'(?:từ|của|qua|app|brn)\s*[:\s]*([A-Za-z0-9_\s]{2,20}?)(?:,|\.|\s+bị|\s+không|\s+báo|\n|$)', raw, re.IGNORECASE)
        if bank_match:
            candidate = bank_match.group(1).strip()
            stop_candidates = ["sdt", "số", "tb", "kh", "máy", "ai", "nào", "gì", "đâu", "được", "người", "nhau", "minh", "mình"]
            if candidate and candidate.lower() not in stop_candidates and len(candidate) >= 2:
                # Chỉ lấy nếu giống tên riêng (có viết hoa hoặc từ viết tắt)
                if any(c.isupper() for c in candidate) or candidate.lower() in ["vietcombank", "momo", "zalo", "vneid", "facebook"]:
                    app_brand = candidate.title()

    # 3. Bóc tách Dòng máy thiết bị (Device)
    device_type = ""
    for standard_dev, keywords in KNOWN_DEVICES:
        if any(kw in low for kw in keywords):
            device_type = standard_dev
            # Cố gắng bắt model cụ thể: vd iPhone 14, Samsung A20, Vivo Y20
            model_match = re.search(rf'(?:máy|dùng|dt|điện thoại)?\s*({keywords[0]}[A-Za-z0-9_\s]{{1,12}})', raw, re.IGNORECASE)
            if model_match:
                device_type = model_match.group(1).strip()
            break

    # 4. Bóc tách Số tiền khiếu nại cước (Claimed Amount)
    claimed_amount = ""
    if any(k in low for k in ["cước", "tiền", "phát sinh", "trừ tiền", "trừ cước"]):
        amt_match = re.search(r'(\d{1,3}(?:[.,]\d{3})+)(?:\s*(?:đ|dong|đồng|k))?', raw)
        if amt_match:
            claimed_amount = f"{amt_match.group(1)} đ"

    # 5. Bóc tách Thao tác KTV / Khách hàng đã thực hiện trước đó (Prior Actions)
    prior_actions = []
    if any(k in low for k in ["cài lại tttn", "cài lại trung tâm tin nhắn", "cài tttn"]):
        prior_actions.append("Đã cài lại TTTN")
    if any(k in low for k in ["reset smt", "rs smt"]):
        prior_actions.append("Đã reset SMT")
    if any(k in low for k in ["reset máy", "rs máy", "tắt mở máy", "khởi động lại"]):
        prior_actions.append("Đã reset máy")
    if any(k in low for k in ["thay sim", "đổi sim", "thay sang máy khác"]):
        prior_actions.append("Đã thử đổi SIM")
    if any(k in low for k in ["cam kết", "bản cam kết"]):
        prior_actions.append("Đã có bản cam kết")

    # 6. Nhận diện Dấu hiệu bất thường (Anomaly)
    anomaly = ""
    denial_kws = [
        "không có soạn tin", "không soạn tin", "không nhắn tin", "không hề nhắn tin",
        "không gửi tin", "không hề gửi tin", "không sử dụng dịch vụ tin nhắn",
        "không thao tác nhắn tin", "không chủ động soạn tin", "không gửi tin nhắn đi",
        "không quen biết", "không hề quen biết", "không biết của ai", "không biết nhắn tin",
        "không cho ai mượn", "không ai mượn", "không ai giữ máy", "không có lịch sử gửi",
        "không hiện việc gửi tin", "không gửi cho ai", "không làm gì mà trừ cước", "không hề gửi",
        "không gửi tin nhắn cho ai", "không gửi bất cứ số nào"
    ]
    has_denial = any(k in low for k in denial_kws)
    is_iphone = any(k in low for k in ["iphone", "ios", "ip ", "ipx", "apple", "imesage", "imessage"])

    if any(k in low for k in ["vài giây", "liên tục", "nhanh liên tục", "tự động gửi"]):
        anomaly = "Gửi tin nhắn liên tục vài giây/tin - Dấu hiệu mã độc / Botnet tự động phát tán"
    elif re.search(r'\b(004\d{7,}|84004\d{7,})\b', raw):
        anomaly = "Phát sinh tin nhắn gửi đi quốc tế lạ (004...) - Dấu hiệu mã độc chiếm quyền SMS"
    elif has_denial:
        if is_iphone:
            anomaly = "KH khẳng định không gửi: Nghi vấn tính năng iMessage tự chuyển đổi sang SMS (Send as SMS) hoặc kích hoạt ngầm"
        else:
            anomaly = "KH khẳng định không gửi: Nghi vấn thiết bị cài app ngầm / nhiễm mã độc tự phát sinh SMS trong nền"
    elif any(k in low for k in ["spam", "tin nhắn rác", "quấy rối"]):
        anomaly = "Phản ánh bị quấy rối / tin nhắn rác"

    # 7. Phân loại Loại vấn đề (Problem Type) & Tiêu đề
    problem_type = "other"
    problem_title = "Sự cố tin nhắn SMS"
    suggested_cause_code = "2011"
    suggested_cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
    suggested_conclusion = "Hệ thống mạng VNPT hoạt động bình thường, không suy hao dịch vụ."
    suggested_action_plan = "Hướng dẫn khách hàng theo dõi thêm và kiểm tra thiết bị."

    if claimed_amount or any(k in low for k in ["phát sinh cước", "hoàn cước", "trừ cước", "trừ tiền", "cước cao"]):
        problem_type = "cost_issue"
        problem_title = f"Khiếu nại phát sinh cước SMS{f' ({claimed_amount})' if claimed_amount else ''}"
        suggested_cause_code = "2006"
        suggested_cause_name = "Cung cấp log file SMS theo yêu cầu"
        suggested_conclusion = (
            f"Hệ thống SMSC VNPT ghi nhận thuê bao có phát sinh tin nhắn gửi đi (MO) trong {detected_time}. "
            f"Theo quy định cước viễn thông, cước dịch vụ được tính khi thuê bao khởi tạo gửi tin thành công lên tổng đài, "
            f"chính xác theo số lượng bản tin/phân đoạn thực tế phát sinh từ thiết bị."
        )
        suggested_action_plan = "Cung cấp chi tiết log SMSC phát sinh tin nhắn cho KTV/GDV giải thích cước cho khách hàng."
    elif any(k in low for k in ["không gửi được", "ko gửi được", "gửi không được", "gửi ko được", "gửi tin thất bại", "chấm than", "không gửi tin"]):
        problem_type = "mo_fail"
        problem_title = f"Không gửi được tin nhắn đi{f' (tới {app_brand})' if app_brand else ''} (Báo lỗi)"
        suggested_cause_code = "2014" if "Đã cài lại TTTN" not in prior_actions else "2015"
        suggested_cause_name = "Thuê bao cài đặt sai trung tâm tin nhắn" if "Đã cài lại TTTN" not in prior_actions else "Thuê bao chưa mở dịch vụ, gói cước"
        suggested_conclusion = "Kiểm tra Core và SMSC: Thuê bao gặp trở ngại khi thiết lập bản tin MO từ thiết bị."
        suggested_action_plan = "Kiểm tra trạng thái cước tài khoản chính và cài đặt lại số Trung tâm tin nhắn (+8491020005)."
    elif any(k in low for k in ["otp", "mã xác thực", "ma xac thuc"]) or (app_brand and any(k in low for k in ["không nhận", "ko nhận", "chưa nhận", "không về", "ko về"])):
        problem_type = "otp"
        problem_title = f"Không nhận được mã OTP{f' ({app_brand})' if app_brand else ''}"
        suggested_cause_code = "2111"
        suggested_cause_name = "Do thiết bị đầu cuối"
        suggested_conclusion = f"Hệ thống SMSC VNPT đã chuyển phát tin nhắn từ {app_brand or 'đối tác'} đến thuê bao thành công. Mạng lưới đảm bảo."
        suggested_action_plan = "Hướng dẫn khách hàng kiểm tra thiết bị: tắt chế độ lọc tin nhắn rác, kiểm tra hòm thư Spam, khởi động lại máy."
    elif any(k in low for k in ["không nhận được tin", "ko nhận được tin", "không nhận được sms", "ko nhận được sms", "không có tin nhắn đến"]):
        problem_type = "mt_fail"
        problem_title = "Không nhận được tin nhắn đến"
        suggested_cause_code = "2011"
        suggested_cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        suggested_conclusion = "Trạng thái profile thuê bao trên Core HSS bình thường, dịch vụ SMS mở 2 chiều."
        suggested_action_plan = "Đề nghị khách hàng kiểm tra lại bộ nhớ tin nhắn máy và khởi động lại thiết bị."
    elif any(k in low for k in ["tin nhắn rác", "spam", "chặn"]):
        problem_type = "spam"
        problem_title = "Sự cố tin nhắn rác / Spam SMS"
        suggested_cause_code = "2007"
        suggested_cause_name = "Đóng/Mở chặn spam"
        suggested_conclusion = "Kiểm tra lịch sử phát sinh tin nhắn và rà soát danh sách chặn spam."
        suggested_action_plan = "Hướng dẫn khách hàng đăng ký dịch vụ chặn tin nhắn rác hoặc báo cáo đầu số 156."

    # 8. Tạo chuỗi tóm tắt hiển thị chuyên nghiệp chuẩn 6 đầu mục
    lines = [
        f"1. Vấn đề phản ánh: {problem_title}",
        f"2. Mốc thời gian xảy ra: {detected_time}{f' ({time_range_desc})' if time_range_desc and time_range_desc != detected_time else ''}",
        f"3. Ứng dụng / Đầu số: {app_brand or 'SMS thông thường'}",
    ]
    dev_act = []
    if device_type:
        dev_act.append(f"Máy {device_type}")
    if prior_actions:
        dev_act.append(f"Đã thử: {', '.join(prior_actions)}")
    lines.append(f"4. Thiết bị & Thao tác: {' | '.join(dev_act) if dev_act else 'Không đề cập'}")
    lines.append(f"5. Cước phí khiếu nại: {claimed_amount or 'Không đề cập'}")
    lines.append(f"6. Cảnh báo / Dấu hiệu: {anomaly or 'Bình thường'}")
    summary_formatted = "\n".join(lines)

    return {
        "problem_type": problem_type,
        "problem_title": problem_title,
        "app_brand": app_brand,
        "device_type": device_type,
        "claimed_amount": claimed_amount,
        "prior_actions": prior_actions,
        "anomaly": anomaly,
        "incident_time": detected_time,
        "from_date": from_date,
        "to_date": to_date,
        "time_range_desc": time_range_desc,
        "suggested_cause_code": suggested_cause_code,
        "suggested_cause_name": suggested_cause_name,
        "suggested_conclusion": suggested_conclusion,
        "suggested_action_plan": suggested_action_plan,
        "summary_formatted": summary_formatted,
    }


def generate_sms_ticket_summary(ticket_content: str, incident_time_fallback: str = "") -> str:
    """
    Tóm tắt nội dung phản ánh tin nhắn (SMS) chuẩn 6 đầu mục rõ ràng đồng bộ với Mobile Internet:
    1. Vấn đề phản ánh: ...
    2. Mốc thời gian xảy ra: ...
    3. Ứng dụng / Đầu số: ...
    4. Thiết bị & Thao tác: ...
    5. Cước phí khiếu nại: ...
    6. Cảnh báo / Dấu hiệu: ...
    """
    res = parse_sms_entities(ticket_content, incident_time_fallback)
    return res.get("summary_formatted") or ""



def parse_sms_incident_details(ticket_content: str, incident_time_fallback: str = "") -> dict:
    """Hàm tương thích ngược với code cũ, gọi sang parse_sms_entities"""
    res = parse_sms_entities(ticket_content, incident_time_fallback)
    return {
        "incident_time": res["incident_time"],
        "from_date": res["from_date"],
        "to_date": res["to_date"],
        "time_range_desc": res["time_range_desc"],
        "problem": res["problem_title"]
    }


def is_sms_ticket(title: str, content: str = "") -> bool:
    """Nhận diện xem phiếu có thuộc nhóm dịch vụ Tin nhắn (SMS) hay không."""
    raw = f"{title or ''} {content or ''}".lower()
    sms_keywords = [
        "tin nhắn", "sms", "otp", "1414", "mo fail", "mt fail", "trừ cước sms", 
        "gửi tin", "nhận tin", "bản tin", "brandname", "spamsms", "spam tin"
    ]
    return any(k in raw for k in sms_keywords)


def analyze_sms_ticket_with_cdr(phone_84: str, ticket: dict, force_cdr: bool = True) -> dict:
    """
    Tiền kiểm và phân tích chuyên sâu cho phiếu Tin nhắn (SMS):
    1. Bóc tách thực thể (Loại sự cố, ngân hàng/app, dải ngày, số tiền cước, dòng máy).
    2. Tự động tra cứu CDR SMSC theo dải ngày thực tế và lưu vào SQLite (Phương án B).
    3. Phân tích kết quả thực tế (thành công 100C, thất bại, nguyên nhân) và sinh câu kết luận.
    4. Gợi ý mã lỗi OneOSS chuẩn hóa theo diagnostic_scenarios_sms.json.
    5. Xử lý bước 2.3: Ghi nhận "Chuyển 2.4" cho KTV.
    """
    title = str(ticket.get("title") or ticket.get("package_title") or "Tin nhắn (SMS)").strip()
    content = str(ticket.get("content") or ticket.get("ticket_content") or "").strip()
    incident_time = str(ticket.get("incident_time") or ticket.get("created_time") or "").strip()
    step_name = str(ticket.get("step_name") or "")
    code = str(ticket.get("ticket_code") or "")

    # 1. Bóc tách thực thể
    entities = parse_sms_entities(content, incident_time, package_title=title)
    try:
        from services.state import state
        state.log("INFO", f"   📩 [ai_sms_interpreter] Phân tích: {entities.get('problem_title')} | Thiết bị: {entities.get('device_type')}")
    except Exception:
        pass
    prob_type = entities.get("problem_type", "other")
    from_date = entities.get("from_date")
    to_date = entities.get("to_date")
    time_desc = entities.get("time_range_desc") or entities.get("incident_time") or "thời gian gần đây"
    app_brand = entities.get("app_brand") or ""

    # 2. Tra cứu CDR SMSC
    cdr_records = []
    cdr_error = None
    if force_cdr and (from_date or to_date):
        try:
            from services.smsc_cdr_client import fetch_smsc_cdr
            cdr_res = fetch_smsc_cdr(
                phone=phone_84, 
                direction="both", 
                from_time_str=from_date, 
                to_time_str=to_date, 
                limit=200
            )
            if cdr_res and cdr_res.get("success"):
                cdr_records = cdr_res.get("records", [])
                # Tự động lưu vào SQLite để tái sử dụng và huấn luyện AI (Phương án B)
                try:
                    from db_manager import save_sms_cdr_records
                    save_sms_cdr_records(phone_84, code, cdr_records)
                except Exception as ex_db:
                    print(f"⚠️ [SMS CDR SAVE ERROR] {ex_db}")
            else:
                cdr_error = cdr_res.get("message") if cdr_res else "Không có phản hồi từ SMSC"
        except Exception as ex_cdr:
            cdr_error = str(ex_cdr)

    # Đọc dự phòng từ database SQLite (nếu live fetch không có bản ghi hoặc offline / recheck)
    if not cdr_records:
        try:
            from db_manager import get_sms_cdr_records
            cached_db = get_sms_cdr_records(phone_84, ticket_code=code, limit=200)
            if not cached_db:
                # Tìm dự phòng theo riêng số điện thoại nếu ticket_code khác hoặc chưa gán
                cached_db = get_sms_cdr_records(phone_84, limit=200)
            if cached_db:
                cdr_records = cached_db
                cdr_error = None
        except Exception as ex_db_read:
            print(f"⚠️ [SMS CDR DB READ] {ex_db_read}")

    # 3. Thống kê dữ liệu thực tế từ CDR (Facts)
    total_mo = 0
    total_mt = 0
    mo_success = 0
    mo_fail = 0
    mt_success = 0
    mt_fail = 0
    long_sms_count = 0
    recent_otp_delivery_time = ""
    recent_otp_sender = ""
    recent_mo_time = ""
    recent_mo_destination = ""
    recent_mo_status = ""
    mo_fail_causes = {}
    mt_fail_causes = {}

    for rec in cdr_records:
        rec_dir = rec.get("direction", "")
        st_type = rec.get("status_type", "")
        st_code = str(rec.get("status_code", "")).strip()
        t_cause = str(rec.get("termination_cause", "")).strip()
        del_time = rec.get("delivery_time") or rec.get("submission_time") or ""

        # Quét độ dài tin nhắn (nếu > 70 ký tự/bytes là tin nhắn ghép 2-5 phân đoạn cước)
        try:
            m_len_val = int(str(rec.get("message_length") or "").strip())
            if m_len_val > 70:
                long_sms_count += 1
        except Exception:
            pass

        if "MO" in rec_dir:
            total_mo += 1
            is_mo_ok = (st_type == "success" or st_code in ("100C", "100c", "8", "0", "2") or t_cause in ("100C", "100c", "0", "0000", "2"))
            if is_mo_ok:
                mo_success += 1
                if not recent_mo_time:
                    recent_mo_time = del_time
                    recent_mo_destination = str(rec.get("called_number") or "").strip()
                    recent_mo_status = st_code or t_cause or "100C"
            else:
                mo_fail += 1
                cause_key = f"{t_cause} ({st_code})" if t_cause and t_cause != "--" else st_code
                mo_fail_causes[cause_key] = mo_fail_causes.get(cause_key, 0) + 1
        elif "MT" in rec_dir:
            total_mt += 1
            calling_no = str(rec.get("calling_number", "")).strip()
            # Kiểm tra nếu là bản tin OTP hoặc tin từ đầu số ngắn/brandname
            is_otp_candidate = False
            if app_brand and app_brand.lower() in calling_no.lower():
                is_otp_candidate = True
            elif len(calling_no) <= 8 and not calling_no.startswith("849") and not calling_no.startswith("848"):
                is_otp_candidate = True
            elif not calling_no.isdigit() and len(calling_no) > 0:
                is_otp_candidate = True

            is_mt_ok = (st_type == "success" or st_code in ("100C", "100c", "8", "0", "2") or t_cause in ("100C", "100c", "0", "0000", "2"))
            if is_mt_ok:
                mt_success += 1
                if (is_otp_candidate or not recent_otp_delivery_time) and not recent_otp_delivery_time:
                    recent_otp_delivery_time = del_time
                    recent_otp_sender = calling_no
            else:
                mt_fail += 1
                cause_key = f"{t_cause} ({st_code})" if t_cause and t_cause != "--" else st_code
                mt_fail_causes[cause_key] = mt_fail_causes.get(cause_key, 0) + 1

    # 4. Xác định Kịch bản Chẩn đoán & Kết luận kỹ thuật
    has_cdr = len(cdr_records) > 0
    status = "MẠNG LƯỚI ĐẢM BẢO"
    color = "green"
    scenario_id = "SMS_07_MT_RECEIVE_FAIL_GENERAL"
    cause_code = "2011"
    cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
    tech_comment = ""
    action_plan = ""

    # Kịch bản 1: Khiếu nại cước (cost_issue)
    if prob_type == "cost_issue":
        is_apple_fee = any("+44" in str(rec.get("called_number", "")) or str(rec.get("called_number", "")).startswith("0044") for rec in cdr_records) or "imessage" in content.lower() or "facetime" in content.lower()
        if is_apple_fee:
            scenario_id = "SMS_01B_APPLE_IMESSAGE_FEE"
            cause_code = "2111"
            cause_name = "Do thiết bị đầu cuối"
            status = "CƯỚC KÍCH HOẠT IMESSAGE/FACETIME APPLE"
            color = "green"
            tech_comment = (
                f"Kiểm tra hệ thống SMSC: Thuê bao sử dụng iPhone có phát sinh bản tin gửi đi (MO) quốc tế đến đầu số máy chủ kích hoạt của Apple (+44... Vương quốc Anh) trong {time_desc}. "
                f"Đây là cơ chế bảo mật tự động của hệ điều hành iOS khi kích hoạt iMessage/FaceTime hoặc thay SIM. Cước phát sinh được tính chính xác theo đơn giá cước tin nhắn quốc tế hiện hành (2.500đ/SMS). "
                f"Mạng lưới VNPT đảm bảo thông suốt dịch vụ."
            )
            action_plan = "Giải thích cho khách hàng về cơ chế gửi SMS kích hoạt iMessage/FaceTime quốc tế của Apple. Hướng dẫn tắt tính năng trong Cài đặt nếu không có nhu cầu sử dụng."
        elif has_cdr and total_mo > 0:
            scenario_id = "SMS_01_COST_DISPUTE_VALID_USAGE"
            cause_code = "2006"
            cause_name = "Cung cấp log file SMS theo yêu cầu"
            status = "CƯỚC PHÁT SINH ĐÚNG LƯU LƯỢNG"
            color = "green"
            long_msg_desc = f", trong đó có {long_sms_count} bản tin nhắn dài (tách thành 2–5 phân đoạn SMS/tin)" if long_sms_count > 0 else ""
            status_desc_note = f" (gồm {mo_success} tin phát thành công, {mo_fail} tin máy đích không nhận được)" if mo_fail > 0 else ""
            tech_comment = (
                f"Hệ thống SMSC VNPT ghi nhận thuê bao có phát sinh {total_mo} lượt gửi tin nhắn (MO) "
                f"trong {time_desc}{long_msg_desc}{status_desc_note}. "
                f"Theo quy định cước viễn thông, cước dịch vụ SMS được tính khi thuê bao khởi tạo gửi tin thành công lên tổng đài SMSC, "
                f"không phụ thuộc vào trạng thái nhận của thuê bao đích. Cước phát sinh được tính chính xác theo số lượng phân đoạn tin nhắn thực tế phát sinh từ thiết bị."
            )
            action_plan = (
                "Cung cấp chi tiết log SMSC phát sinh tin nhắn cho KTV/GDV giải thích cước cho khách hàng. "
                "Giải thích cơ chế tính cước theo phân đoạn tin nhắn (tin nhắn dài/có dấu tính từ 2 phân đoạn trở lên). "
                "Hướng dẫn khách hàng kiểm tra tính năng 'Send as SMS' trên iPhone hoặc rà soát các ứng dụng nhắn tin ngầm trên máy."
            )
        elif has_cdr and total_mo == 0:
            status = "KHÔNG CÓ DỮ LIỆU GỬI SMS TRONG KỲ"
            color = "orange"
            tech_comment = f"Kiểm tra hệ thống SMSC trong {time_desc}: Không ghi nhận bản tin gửi đi (MO) nào từ số máy {phone_84}."
            action_plan = "Chuyển bộ phận tính cước đối soát chi tiết cước phát sinh từ dịch vụ khác hoặc cước ngoài gói."
        else:
            status = "CHỜ ĐỐI SOÁT LOG CƯỚC SMSC"
            color = "orange"
            tech_comment = f"Thuê bao khiếu nại cước SMS trong {time_desc}. Đang chờ đối soát log cước SMSC."
            action_plan = "Truy vấn log SMSC theo khoảng ngày phản ánh để giải thích cước cho khách hàng."

    # Kịch bản 2 & 3 & 3B: Lỗi OTP (otp)
    elif prob_type == "otp":
        if has_cdr and recent_otp_delivery_time:
            brand_label = recent_otp_sender or app_brand or "đối tác/ngân hàng"
            # Kiểm tra xem bản tin OTP thành công có phát sinh sau thời điểm phản ánh/sự cố không
            is_delivered_after_incident = False
            try:
                deliv_dt = None
                for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%y%m%d%H%M%S"):
                    try:
                        deliv_dt = datetime.strptime(recent_otp_delivery_time.strip(), fmt)
                        break
                    except Exception:
                        pass

                inc_dt = None
                for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        inc_dt = datetime.strptime(incident_time.strip(), fmt)
                        break
                    except Exception:
                        pass

                if deliv_dt and inc_dt:
                    if deliv_dt > inc_dt + timedelta(minutes=30):
                        is_delivered_after_incident = True
                elif deliv_dt:
                    # Nếu không rõ mốc phản ánh nhưng bản tin phát sinh gần đây (trong vòng 3 ngày)
                    if (datetime.now() - deliv_dt).total_seconds() < 3 * 86400:
                        is_delivered_after_incident = True
            except Exception:
                pass

            if is_delivered_after_incident:
                scenario_id = "SMS_02B_OTP_RECEIVED_NORMAL"
                cause_code = "2011"
                cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
                status = "KH ĐÃ NHẬN ĐƯỢC OTP BÌNH THƯỜNG"
                color = "green"
                tech_comment = (
                    f"Kiểm tra hệ thống SMSC VNPT: Sau thời điểm phản ánh, thuê bao đã tiếp tục nhận được bản tin OTP từ {brand_label} "
                    f"thành công lúc {recent_otp_delivery_time} (Mã trạng thái: 100C/2 - Giao bản tin thành công). "
                    f"Hiện tại dịch vụ nhận tin nhắn xác thực/OTP hoạt động bình thường, không phát sinh lỗi trên mạng lưới."
                )
                action_plan = "Thông báo khách hàng dịch vụ nhận tin nhắn OTP đã hoạt động bình thường và thực hiện đóng phiếu theo quy định."
            else:
                scenario_id = "SMS_02_OTP_DELIVERY_SUCCESS"
                cause_code = "2111"
                cause_name = "Do thiết bị đầu cuối"
                status = "SMSC ĐÃ PHÁT OTP THÀNH CÔNG VỀ MÁY"
                color = "green"
                tech_comment = (
                    f"Kiểm tra hệ thống SMSC VNPT: Ghi nhận bản tin OTP từ {brand_label} đã được tổng đài SMSC chuyển phát thành công "
                    f"tới thuê bao lúc {recent_otp_delivery_time} (Mã trạng thái: 100C/2 - Giao bản tin thành công). Mạng lưới VNPT đảm bảo thông suốt dịch vụ. "
                    f"Phân tích nguyên nhân thiết bị: Hệ điều hành (iOS hoặc Android) đã nhận được tin nhắn ở cấp độ hệ thống, tuy nhiên ứng dụng Tin nhắn "
                    f"(Google Messages, Samsung Messages hoặc bộ lọc iOS) tự động nhận diện đầu số OTP là tin rác/quảng cáo và đẩy vào mục ẩn, "
                    f"khiến hộp thư đến (Inbox) không hiển thị."
                )
                action_plan = (
                    f"Hướng dẫn khách hàng kiểm chứng: Mở ứng dụng Tin nhắn trên điện thoại -> vào menu mở rộng (biểu tượng 3 chấm hoặc biểu tượng tài khoản) "
                    f"-> chọn mục 'Thư rác và bị chặn' (Spam & Blocked) hoặc 'Tin nhắn chưa biết & Rác' (Junk) để lấy mã OTP của {brand_label}. "
                    f"Đồng thời chọn 'Không phải thư rác' hoặc thêm vào danh bạ tin cậy để các bản tin OTP sau hiển thị thẳng vào Hộp thư chính."
                )
        elif has_cdr and mo_success > 0 and not recent_otp_delivery_time:
            # Kịch bản 3B: Xác thực 2 chiều (MO OK nhưng đối tác chưa đẩy bản tin MT OTP)
            scenario_id = "SMS_03B_2WAY_OTP_MO_OK_MT_MISSING"
            cause_code = "2011"
            cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
            status = "MO THÀNH CÔNG - ĐỐI TÁC CHƯA TRẢ OTP"
            color = "orange"
            brand_label = app_brand or "đối tác/ngân hàng"
            dest_info = recent_mo_destination or "đầu số trung gian của đối tác"
            time_mo_info = f" lúc {recent_mo_time}" if recent_mo_time else ""
            st_info = recent_mo_status or "Thành công (100C/2)"
            tech_comment = (
                f"Kiểm tra hệ thống SMSC VNPT: Ghi nhận luồng xác thực 2 chiều của thuê bao. "
                f"Chiều gửi đi (MO) thành công tới đầu số {dest_info}{time_mo_info} (Mã trạng thái: {st_info} - Đã giao bản tin thành công sang tổng đài đối tác). "
                f"Tuy nhiên, SMSC VNPT hoàn toàn không ghi nhận bản tin phản hồi/OTP (MT) nào từ phía {brand_label} đẩy về cho thuê bao trong {time_desc}. "
                f"Nguyên nhân: Đứt gãy luồng xác thực phía đối tác (Lỗi kết nối API giữa SMS Gateway trung gian với máy chủ {brand_label}, hoặc SMS Vendor đối tác gặp sự cố định tuyến mạng). "
                f"Mạng lưới VNPT hoàn thành chuyển phát MO và đảm bảo thông suốt dịch vụ."
            )
            action_plan = (
                f"Mạng VNPT đã chuyển phát tin nhắn xác thực của khách hàng sang đối tác thành công. "
                f"Đề nghị hướng dẫn khách hàng sử dụng tính năng 'Gửi lại mã' trên ứng dụng {brand_label} vào một thời điểm khác để hệ thống đối tác tạo phiên gửi mới, "
                f"hoặc liên hệ kênh hỗ trợ của {brand_label} vì sự cố nằm ngoài phạm vi mạng VNPT."
            )
        elif has_cdr and not recent_otp_delivery_time:
            scenario_id = "SMS_03_OTP_NOT_SENT_BY_PARTNER"
            cause_code = "2011"
            cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
            status = "ĐỐI TÁC CHƯA ĐẨY BẢN TIN OTP"
            color = "orange"
            brand_label = app_brand or "đối tác/ngân hàng"
            tech_comment = (
                f"Kiểm tra hệ thống SMSC VNPT trong {time_desc}: Không ghi nhận bản tin OTP nào từ phía {brand_label} "
                f"gửi vào hệ thống SMSC VNPT để định tuyến đến thuê bao. Profile thuê bao nhận tin bình thường."
            )
            action_plan = (
                f"Thông báo khách hàng thao tác yêu cầu gửi lại OTP trên ứng dụng đối tác hoặc liên hệ tổng đài của {brand_label} "
                f"để kiểm tra luồng phát tin OTP từ hệ thống của họ."
            )
        else:
            brand_label = app_brand or "đối tác/ngân hàng"
            scenario_id = "SMS_02_OTP_DELIVERY_SUCCESS"
            cause_code = "2111"
            cause_name = "Do thiết bị đầu cuối"
            status = "MẠNG LƯỚI BÌNH THƯỜNG - HƯỚNG DẪN KH"
            color = "green"
            tech_comment = (
                f"Kiểm tra hệ thống Core và SMSC VNPT trong {time_desc}: Profile thuê bao mở bình thường 2 chiều, mạng lưới đảm bảo thông suốt. "
                f"Nếu khách hàng không thấy mã OTP từ {brand_label}, đề nghị hướng dẫn kiểm tra thư mục 'Thư rác và bị chặn' trên máy hoặc thao tác gửi lại mã."
            )
            action_plan = f"Hướng dẫn khách hàng kiểm tra mục Thư rác/Spam trên ứng dụng Tin nhắn của điện thoại để lấy mã OTP của {brand_label}."

    # Kịch bản 8: Thiết bị tự động phát sinh tin nhắn ngầm (device_background_sms)
    elif prob_type == "device_background_sms":
        scenario_id = "SMS_08_DEVICE_AUTO_SEND_BACKGROUND"
        cause_code = "2111"
        cause_name = "Do thiết bị đầu cuối"
        status = "TIN NHẮN PHÁT SINH TỰ ĐỘNG TỪ THIẾT BỊ"
        color = "green"
        dev_label = entities.get("device_type") or "Oppo/Android"
        dest_val = recent_mo_destination or "đầu số dịch vụ (129/...)"
        mo_stats = f" (Hệ thống SMSC ghi nhận {total_mo} lượt gửi MO, {mo_success} lượt thành công)" if total_mo > 0 else ""
        tech_comment = (
            f"Kiểm tra hệ thống SMSC VNPT trong {time_desc}: Thuê bao có phát sinh bản tin gửi đi (MO) từ thiết bị{mo_stats} "
            f"tới đầu số {dest_val}. Phân tích nguyên nhân: Do tính năng tự động gửi tin nhắn kích hoạt/đồng bộ ngầm của hệ điều hành "
            f"trên máy {dev_label} (Tài khoản dịch vụ hãng, sao lưu dữ liệu đám mây, tính năng Tìm thiết bị) hoặc ứng dụng ngầm trên máy "
            f"tự động khởi tạo bản tin MO mà không hiển thị trong giao diện soạn tin nhắn. Mạng lưới VNPT đảm bảo thông suốt và trừ cước/định tuyến đúng phát sinh thực tế từ thiết bị."
        )
        action_plan = (
            f"Giải thích cho khách hàng về cơ chế tin nhắn kích hoạt/đồng bộ tự động của dòng máy {dev_label}. "
            f"Hướng dẫn khách hàng vào phần Cài đặt máy -> Tài khoản dịch vụ hãng (Oppo Cloud / HeyTap) -> tắt tính năng Tự động sao lưu/Tìm thiết bị qua SMS, "
            f"hoặc kiểm tra quyền gửi SMS của các ứng dụng lạ trên thiết bị để tránh phát sinh tin nhắn ngoài ý muốn."
        )

    # Kịch bản 4: Không gửi được tin nhắn MO (mo_fail)
    elif prob_type == "mo_fail":
        dest_short = re.search(r'(?:tới|đến|đầu số)\s*(\d{3,6})\b', content)
        if dest_short:
            scenario_id = "SMS_04B_PREMIUM_SMS_BLOCK"
            cause_code = "2111"
            cause_name = "Do thiết bị đầu cuối"
            status = "MÁY CHẶN GỬI TIN NHẮN ĐẦU SỐ DỊCH VỤ"
            color = "orange"
            tech_comment = (
                f"Profile thuê bao trên Core HSS mở đầy đủ 2 chiều. Thuê bao gửi tin nhắn đến các số thông thường bình thường "
                f"nhưng không gửi được tới đầu số {dest_short.group(1)}. Nguyên nhân: Thiết bị Android đã bật tính năng 'Chặn dịch vụ SMS cước cao / Premium SMS'."
            )
            action_plan = "Hướng dẫn khách hàng vào Cài đặt máy -> Ứng dụng -> Truy cập đặc biệt -> Quyền truy cập dịch vụ SMS cước cao (Premium SMS) -> chọn ứng dụng Tin nhắn và chuyển sang 'Luôn cho phép'."
        else:
            scenario_id = "SMS_04_MO_SEND_FAIL_WRONG_SMSC"
            cause_code = "2014"
            cause_name = "Thuê bao cài đặt sai trung tâm tin nhắn"
            status = "SAI SỐ TRUNG TÂM TIN NHẮN (SMSC)"
            color = "orange"
            tech_comment = (
                "Profile dịch vụ SMS trên Core HSS mở bình thường 2 chiều. Tổng đài SMSC không ghi nhận bản tin gửi đi "
                "từ thuê bao do thiết bị chưa cấu hình đúng số Trung tâm tin nhắn SMSC của VinaPhone."
            )
            action_plan = "Hướng dẫn khách hàng cài đặt lại số Trung tâm tin nhắn VinaPhone (+8491020005) trong Cài đặt tin nhắn và khởi động lại máy."

    # Kịch bản 5: Khóa SPS do tin nhắn rác hoặc mở theo Cam kết (spam)
    elif prob_type == "spam":
        if any(k in content.lower() for k in ["cam kết", "bản cam kết", "mở lại"]):
            scenario_id = "SMS_06B_SPS_COMMITMENT_RESTORE"
            cause_code = "2007"
            cause_name = "Đóng/Mở chặn spam"
            status = "TIẾP NHẬN BẢN CAM KẾT - MỞ CHIỀU SMO"
            color = "green"
            tech_comment = (
                "Thuê bao trước đó bị hệ thống SPS chặn chiều gửi tin nhắn do vi phạm quy định chống tin nhắn rác. "
                "Điểm giao dịch / KTV đã tiếp nhận Bản cam kết sử dụng dịch vụ viễn thông đúng quy định của chủ thuê bao."
            )
            action_plan = "Kiểm tra hồ sơ cam kết hợp lệ, chuyển thông tin đề nghị mở chiều tin nhắn (SMO) trên hệ thống SPS/Core theo quy trình."
        else:
            scenario_id = "SMS_06_SPS_SPAM_BLOCK"
            cause_code = "2007"
            cause_name = "Đóng/Mở chặn spam"
            status = "BỊ HỆ THỐNG SPS KHÓA DO PHÁT TÁN SPAM"
            color = "red"
            tech_comment = (
                "Thuê bao bị hệ thống giám sát SPS tự động khóa chiều nhắn tin (SMO) do phát sinh lưu lượng tin nhắn bất thường "
                "với tần suất cao theo quy định phòng chống tin nhắn rác (CV 939/2013/DQ-VNP-KD)."
            )
            action_plan = "Hướng dẫn khách hàng mang CCCD ra điểm giao dịch VinaPhone để ký Bản cam kết sử dụng dịch vụ viễn thông và mở lại chiều gửi tin."

    # Kịch bản 6 & 7: Nhận lỗi MT chung hoặc phản ánh khác
    else:
        scenario_id = "SMS_07_MT_RECEIVE_FAIL_GENERAL"
        cause_code = "2011"
        cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        status = "MẠNG LƯỚI ĐẢM BẢO - KIỂM TRA BỘ NHỚ/SIM"
        color = "green"
        tech_comment = "Trạng thái profile thuê bao trên Core HSS bình thường, dịch vụ SMS mở 2 chiều, tài khoản hoạt động bình thường. Mạng lưới VNPT đảm bảo thông suốt."
        action_plan = "Đề nghị khách hàng xóa bớt tin nhắn cũ để giải phóng bộ nhớ SIM/máy, lắp lại SIM hoặc đổi SIM vật lý nếu SIM cũ lâu năm bị suy hao."

    # 5. Lưu ý kiến phân tích kỹ thuật và nội dung phản hồi chi tiết
    comment_for_ticket = tech_comment
    action_plan_for_ticket = action_plan

    # 6. Tạo AI Summary chuẩn 6 đầu mục hiển thị chuyên nghiệp trên Drawer
    summary_blocks = [
        f"1. Vấn đề phản ánh: {entities.get('problem_title', 'Sự cố tin nhắn SMS')}",
        f"2. Mốc thời gian xảy ra: {time_desc}",
        f"3. Ứng dụng / Đầu số: {app_brand or 'SMS thông thường'}",
    ]
    dev_act = []
    if entities.get("device_type"):
        dev_act.append(f"Máy {entities['device_type']}")
    if entities.get("prior_actions"):
        dev_act.append(f"Đã thử: {', '.join(entities['prior_actions'])}")
    summary_blocks.append(f"4. Thiết bị & Thao tác: {' | '.join(dev_act) if dev_act else 'Không đề cập'}")
    summary_blocks.append(f"5. Cước phí khiếu nại: {entities.get('claimed_amount') or 'Không đề cập'}")
    summary_blocks.append(f"6. Cảnh báo / Dấu hiệu: {entities.get('anomaly') or 'Bình thường'}")
    ai_summary_full = "\n".join(summary_blocks)

    sms_cdr_summary = {
        "moCount": total_mo,
        "moOk": mo_success,
        "moFail": mo_fail,
        "moRate": round(mo_success * 100 / total_mo, 1) if total_mo > 0 else 0,
        "mtCount": total_mt,
        "mtOk": mt_success,
        "mtFail": mt_fail,
        "mtRate": round(mt_success * 100 / total_mt, 1) if total_mt > 0 else 0,
        "totalHits": len(cdr_records),
        "appBrand": app_brand,
        "fromDate": from_date,
        "toDate": to_date,
        "timeRangeDesc": time_desc,
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Tự động cập nhật sms_cdr_summary vào SQLite
    try:
        from db_manager import update_ticket_field
        import json as _json
        update_ticket_field(phone_84, "sms_cdr_summary", _json.dumps(sms_cdr_summary, ensure_ascii=False))
        update_ticket_field(phone_84, "sms_problem", entities.get("problem_title", "Sự cố tin nhắn SMS"))
        update_ticket_field(phone_84, "sms_incident_time", time_desc)
    except Exception:
        pass

    return {
        "status": status,
        "color": color,
        "action_plan": action_plan_for_ticket,
        "comment": comment_for_ticket,
        "real_packages": f"SMS {prob_type.upper()}",
        "formatted_pkg": f"SMS {prob_type.upper()}",
        "rat_types": "2G/3G/VoLTE SMS",
        "cem_data": "--",
        "app_usage": f"MO: {mo_success}/{total_mo} | MT: {mt_success}/{total_mt}" if has_cdr else "--",
        "ai_summary": ai_summary_full,
        "suggested_cause_code": cause_code,
        "suggested_cause_name": cause_name,
        "scenario_id": scenario_id,
        "is_sms": True,
        "total_mo": total_mo,
        "mo_success": mo_success,
        "mo_fail": mo_fail,
        "total_mt": total_mt,
        "mt_success": mt_success,
        "mt_fail": mt_fail,
        "cdr_count": len(cdr_records),
        "app_brand": app_brand,
        "sms_problem": entities.get("problem_title", "Sự cố tin nhắn SMS"),
        "sms_incident_time": time_desc,
        "sms_cdr_summary": sms_cdr_summary,
        "entities": entities
    }


