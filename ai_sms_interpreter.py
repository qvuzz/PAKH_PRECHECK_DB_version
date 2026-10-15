# ai_sms_interpreter.py
# Module chuyên trách NLP & Bóc tách thực thể phản ánh Tin nhắn (SMS)
# Chuẩn hóa 6 mục nghiệp vụ viễn thông VNPT, độc lập hoàn toàn với phân hệ Data

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
    ("SeABank", ["seabank", "sea bank", "seanet"]),
    ("FE Credit", ["fe credit", "fecredit", "fe cr"]),
    ("Dai Ngan", ["dai ngan", "daingan"]),
    ("OCB", [r"\bocb\b", "omni"]),
    ("VIB", [r"\bvib\b", "myvib"]),
    ("Shinhan", ["shinhan", "shinhanbank"]),
    ("MSB", [r"\bmsb\b"]),
    ("Eximbank", ["eximbank", "exim bank"]),
    ("Tinhte", ["tinhte", "tinhte.vn"]),
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

# Các từ ngữ hành chính / văn phong viễn thông cần loại bỏ khi bóc tách thực thể
STOP_ADMIN_WORDS = [
    "kính chuyển", "chuyển hỗ trợ", "hỗ trợ", "liên hệ kh", "liên hệ", "nhờ kiểm tra",
    "kiểm tra giúp", "xử lý giúp", "ktv", "kh", "khách hàng", "thuê bao", "tb",
    "bị lỗi", "không được", "báo lỗi", "phản ánh"
]


def extract_sms_device(text: str) -> str:
    """
    Bóc tách thiết bị chuẩn xác cho SMS, tuyệt đối không nuốt sang các câu hành chính
    hay dòng sau (như 'iphone kính chuyển hỗ trợ...').
    """
    if not text:
        return "Không đề cập"
    
    # Chỉ xét từng dòng có đề cập tới thiết bị hoặc quét từ khóa
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    target_line = ""
    for line in lines:
        l_low = line.lower()
        if any(k in l_low for k in ["máy", "thiết bị", "đt", "điện thoại", "iphone", "ipad", "samsung", "oppo", "vivo", "xiaomi", "redmi", "realme", "nokia"]):
            target_line = line
            break
    
    scan_text = target_line if target_line else text
    low = scan_text.lower()

    # 1. Nhận diện iPhone và Model số cụ thể
    if any(k in low for k in ["iphone", "ipad", "ios", "apple"]):
        # Bắt model cụ thể: iPhone 11..16, Pro, Pro Max, Plus, Mini, X, XS, XR, SE...
        m_ip = re.search(
            r'\biphone\s*(1[1-6](?:\s*(?:pro\s*max|promax|pro|plus|mini))?|[6-8](?:\s*plus)?|x[rs]?(?:\s*max)?|se)\b',
            low
        )
        if m_ip:
            model_suffix = m_ip.group(1).upper().replace("PROMAX", "Pro Max").replace("PLUS", "Plus").replace("MINI", "Mini")
            return f"iPhone {model_suffix}"
        
        # Bắt viết tắt: IP11..IP16, IPX, IPXS...
        m_ip_short = re.search(
            r'\bip\s*(1[1-6](?:\s*(?:pro\s*max|promax|pro|plus|mini))?|[6-8](?:\s*plus)?|x[rs]?(?:\s*max)?|se)\b',
            low
        )
        if m_ip_short:
            model_suffix = m_ip_short.group(1).upper().replace("PROMAX", "Pro Max").replace("PLUS", "Plus")
            return f"iPhone {model_suffix}"
            
        return "iPhone"

    # 2. Samsung
    if "samsung" in low or "galaxy" in low:
        m_ss = re.search(r'\b(?:samsung|galaxy)\s*([aszem]\d{1,2}[a-z]?(?:\s*(?:ultra|plus|fe))?)\b', low)
        if m_ss:
            return f"Samsung {m_ss.group(1).upper()}"
        return "Samsung"

    # 3. Oppo
    if "oppo" in low:
        m_op = re.search(r'\boppo\s*(reno\s*\d{1,2}[a-z]?|[af]\d{1,2}[a-z]?)\b', low)
        if m_op:
            return f"Oppo {m_op.group(1).upper()}"
        return "Oppo"

    # 4. Xiaomi / Redmi
    if "xiaomi" in low or "redmi" in low:
        m_mi = re.search(r'\b(?:xiaomi|redmi)\s*(note\s*\d{1,2}[a-z]?|\d{1,2}[a-z]?)\b', low)
        if m_mi:
            return f"Xiaomi {m_mi.group(1).title()}"
        return "Xiaomi"

    # 5. Các dòng khác
    for brand in ["vivo", "realme", "huawei", "nokia", "itel", "tecno", "bphone"]:
        if brand in low:
            return brand.title()

    if "android" in low:
        return "Thiết bị Android"

    return "Không đề cập"


def extract_sms_prior_actions(text: str) -> list:
    """
    Bóc tách các thao tác kỹ thuật KTV hoặc khách hàng đã làm trước đó đối với sự cố SMS.
    """
    if not text:
        return []
    
    low = text.lower()
    actions = []

    # Trung tâm tin nhắn (TTNT / TTTN)
    if any(k in low for k in ["số ttnt", "ttnt", "tttn", "cài lại tttn", "trung tâm tin nhắn", "cài đặt lại ttnt"]):
        actions.append("Đã kiểm tra/cài số TTNT")

    # Reset chiều SMO (SMS Originating - gửi đi)
    if any(k in low for k in ["reset smo", "reset lại chiều smo", "chiều smo", "rs smo"]):
        actions.append("Đã reset chiều SMO")

    # Reset SMT (SMS Terminating - nhận đến)
    if any(k in low for k in ["reset smt", "reset lại chiều smt", "chiều smt", "rs smt"]):
        actions.append("Đã reset chiều SMT")

    # Khởi động lại máy / reset máy
    if any(k in low for k in ["reset máy", "khởi động lại", "tắt mở máy", "tat mo may", "restart"]):
        actions.append("Đã khởi động lại máy")

    # Thử đổi SIM / máy khác
    if any(k in low for k in ["thay sim", "đổi sim", "doi sim", "thử máy khác", "lắp máy khác"]):
        actions.append("Đã thử đổi SIM/máy khác")

    # Cam kết
    if any(k in low for k in ["cam kết", "bản cam kết"]):
        actions.append("Đã có bản cam kết")

    return actions


def interpret_sms_ticket(ticket_content: str, package_title: str = "", incident_time_fallback: str = "", created_time: str = "") -> dict:
    """
    Phân tích toàn diện nội dung phản ánh Tin nhắn (SMS):
    - Chuẩn hóa loại sự cố (mo_fail, otp, cost_issue, mt_fail, spam, other)
    - Tách đúng ngân hàng, đầu số, thiết bị, thao tác KTV
    - Đưa ra cảnh báo anomaly chính xác (không gán nhầm cảnh báo chối cước cho phiếu hỏng gửi đi)
    - Sinh summary 6 mục chuyên nghiệp chuẩn viễn thông
    - Dải ngày tra cứu CDR: từ ngày sự cố (-1 ngày) đến ngày tiếp nhận + 3 ngày
    """
    raw = str(ticket_content or "").strip()
    low = raw.lower()
    title_low = str(package_title or "").lower()

    # 1. Bóc tách Mốc thời gian
    now = datetime.now()
    detected_time = "--"
    from_date = ""
    to_date = ""
    time_range_desc = "3 ngày gần nhất"
    pad = lambda n: str(n).zfill(2)

    fallback_year = now.year
    if incident_time_fallback:
        y_match = re.search(r'\b(20\d{2})\b', str(incident_time_fallback))
        if y_match:
            fallback_year = int(y_match.group(1))

    # Parse ngày tiếp nhận phiếu (created_time) nếu có
    receipt_dt = None
    if created_time:
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                receipt_dt = datetime.strptime(str(created_time).strip(), fmt)
                break
            except Exception:
                pass

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
    m_range = range_pat.search(raw) or (range_pat.search(str(incident_time_fallback)) if incident_time_fallback else None)

    # 1. Full date dd/mm/yyyy (vd: 14/10/2026, 05/10/2026)
    m_full = None
    if not m_range:
        m_full = re.search(r'\b([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20\d{2}|\d{2})\b', raw)

    # 2. Month pattern (vd: cước tháng 09/2026, trong tháng 9, T09/2026, T9/2026, kỳ cước 09/2026, hoặc độc lập 09/2026)
    m_month = None
    if not m_range and not m_full:
        m_month = re.search(r'(?<![0-9/])(?:trong\s+tháng|cước\s+tháng|kỳ\s+cước|kỳ|tháng|t)\s*([0-1]?[0-9])(?:\s*[/\-]\s*(20\d{2}))?\b', raw, re.IGNORECASE)
        if not m_month:
            m_month = re.search(r'(?<![0-9/])([0-1]?[0-9])[/\-](20\d{2})\b', raw)

    # 3. Day/Month without year (vd: ngày 28/08, 14/10, lúc 14:00 ngày 28/08)
    m_dm = None
    if not m_range and not m_full and not m_month:
        m_dm = re.search(r'(?:ngày|hôm|lúc|từ)\s*([0-3]?[0-9])[/\-]([0-1]?[0-9])\b', raw, re.IGNORECASE) or \
               re.search(r'(?<![0-9/])([0-3]?[0-9])[/\-]([0-1]?[0-9])(?![0-9/])', raw)

    # 4. Fallback sang incident_time_fallback nếu nội dung hoàn toàn không có ngày tháng
    if not m_range and not m_full and not m_month and not m_dm and incident_time_fallback:
        fb_str = str(incident_time_fallback).strip()
        m_full = re.search(r'\b([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20\d{2}|\d{2})\b', fb_str)
        if not m_full:
            m_dm = re.search(r'(?<![0-9/])([0-3]?[0-9])[/\-]([0-1]?[0-9])(?![0-9/])', fb_str)

    if m_range:
        d1, m1, y1, d2, m2, y2 = m_range.groups()
        y1_val = int(f"20{y1}") if y1 and len(y1) == 2 else (int(y1) if y1 else fallback_year)
        y2_val = int(f"20{y2}") if y2 and len(y2) == 2 else (int(y2) if y2 else y1_val)
        d1_val, m1_val = int(d1), int(m1)
        d2_val, m2_val = int(d2), int(m2)
        if 1 <= d1_val <= 31 and 1 <= d2_val <= 31 and 1 <= m1_val <= 12 and 1 <= m2_val <= 12:
            from_date = f"{y1_val}-{pad(m1_val)}-{pad(d1_val)} 00:00:00"
            to_date = f"{y2_val}-{pad(m2_val)}-{pad(d2_val)} 23:59:59"
            time_range_desc = f"{pad(d1_val)}/{pad(m1_val)} → {pad(d2_val)}/{pad(m2_val)}/{y2_val}"
            detected_time = time_range_desc

    elif m_full:
        d_val = int(m_full.group(1))
        m_val = int(m_full.group(2))
        raw_y = m_full.group(3)
        y_val = int(f"20{raw_y}") if len(raw_y) == 2 else int(raw_y)
        if 1 <= d_val <= 31 and 1 <= m_val <= 12:
            base_date_str = f"{pad(d_val)}/{pad(m_val)}/{y_val}"
            detected_time = f"{time_str} ngày {base_date_str}".strip() if time_str else base_date_str
            try:
                target_dt = datetime(y_val, m_val, d_val)
                prev_dt = target_dt - timedelta(days=1)
                from_date = prev_dt.strftime("%Y-%m-%d 00:00:00")
                # Quy chuẩn: từ ngày sự cố đến ngày tiếp nhận + 3 ngày
                base_receipt = receipt_dt if receipt_dt else target_dt
                if receipt_dt and target_dt and (receipt_dt - target_dt).days > 5:
                    end_dt = target_dt + timedelta(days=5)
                else:
                    end_dt = base_receipt + timedelta(days=3)
                if end_dt > now:
                    end_dt = now
                to_date = end_dt.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{prev_dt.strftime('%d/%m/%Y')} → {end_dt.strftime('%d/%m/%Y')}"
            except Exception:
                from_date = f"{y_val}-{pad(m_val)}-{pad(d_val)} 00:00:00"
                to_date = now.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{base_date_str} → Hiện tại"

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
            time_range_desc = f"01/{pad(m_val)}/{yr} → {pad(last_day)}/{pad(m_val)}/{yr}"

    elif m_dm:
        d_val = int(m_dm.group(1))
        m_val = int(m_dm.group(2))
        y_val = fallback_year
        if 1 <= d_val <= 31 and 1 <= m_val <= 12:
            base_date_str = f"{pad(d_val)}/{pad(m_val)}/{y_val}"
            detected_time = f"{time_str} ngày {base_date_str}".strip() if time_str else base_date_str
            try:
                target_dt = datetime(y_val, m_val, d_val)
                prev_dt = target_dt - timedelta(days=1)
                from_date = prev_dt.strftime("%Y-%m-%d 00:00:00")
                # Quy chuẩn: từ ngày sự cố đến ngày tiếp nhận + 3 ngày
                base_receipt = receipt_dt if receipt_dt else target_dt
                if receipt_dt and target_dt and (receipt_dt - target_dt).days > 5:
                    end_dt = target_dt + timedelta(days=5)
                else:
                    end_dt = base_receipt + timedelta(days=3)
                if end_dt > now:
                    end_dt = now
                to_date = end_dt.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{prev_dt.strftime('%d/%m/%Y')} → {end_dt.strftime('%d/%m/%Y')}"
            except Exception:
                from_date = f"{y_val}-{pad(m_val)}-{pad(d_val)} 00:00:00"
                to_date = now.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{base_date_str} → Hiện tại"

    if not from_date:
        base_target = None
        if incident_time_fallback:
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    base_target = datetime.strptime(str(incident_time_fallback).strip(), fmt)
                    break
                except Exception:
                    pass
        if base_target:
            prev_dt = base_target - timedelta(days=1)
            base_receipt = receipt_dt if receipt_dt else base_target
            if receipt_dt and (receipt_dt - base_target).days > 5:
                end_dt = base_target + timedelta(days=5)
            else:
                end_dt = base_receipt + timedelta(days=3)
            if end_dt > now:
                end_dt = now
            from_date = prev_dt.strftime("%Y-%m-%d 00:00:00")
            to_date = end_dt.strftime("%Y-%m-%d 23:59:59")
            time_range_desc = f"{prev_dt.strftime('%d/%m/%Y')} → {end_dt.strftime('%d/%m/%Y')}"
        else:
            p3 = now - timedelta(days=3)
            from_date = p3.strftime("%Y-%m-%d 00:00:00")
            to_date = now.strftime("%Y-%m-%d 23:59:59")
            time_range_desc = "3 ngày gần nhất"

    # 2. Bóc tách Ứng dụng / Ngân hàng / Đầu số
    app_brand = ""
    # Thử bóc tách từ nhãn Brandname chuẩn OneOSS "- BRN: <Tên>" hoặc "BRN: <Tên>"
    brn_match = re.search(r'(?:^|[\n\-\–\—\s])BRN:\s*([^,\n\-\–]+)', raw, re.IGNORECASE)
    if brn_match:
        app_brand = brn_match.group(1).strip()

    if not app_brand:
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

    # 3. Bóc tách Thiết bị & Thao tác KTV
    device_type = extract_sms_device(raw)
    prior_actions = extract_sms_prior_actions(raw)

    # 4. Bóc tách Cước phí khiếu nại (nếu có)
    claimed_amount = ""
    is_cost_related = any(k in low for k in ["cước", "tiền", "phát sinh", "trừ tiền", "trừ cước", "hoàn tiền", "khiếu nại cước", "khiếu nại", "khieu nai"])
    if is_cost_related:
        amt_match = re.search(r'(\d{1,3}(?:[.,]\d{3})+)(?:\s*(?:đ|dong|đồng|k))?', raw)
        if amt_match:
            claimed_amount = f"{amt_match.group(1)} đ"

    # 5. Phân loại Loại vấn đề (Problem Type)
    # Nhận diện Thiết bị tự gửi tin nhắn ngầm (Activation SMS / Cloud sync / Ứng dụng ngầm / Đầu số ngắn)
    auto_send_kws = [
        "không thao tác gửi", "ko thao tác gửi", "không gửi nhưng", "ko gửi nhưng",
        "khẳng định không nhắn", "khẳng định ko nhắn", "không nhắn tin nhưng", "ko nhắn tin nhưng",
        "tự gửi tin", "tự động gửi", "tự phát sinh", "tb vừa gửi tin nhắn", "tb vừ gửi tin nhắn",
        "máy tự gửi", "tự gửi sms", "tự động nhắn", "không chủ động gửi", "không gửi tin nhắn nhưng",
        "không nhắn tin", "không có nhắn tin"
    ]
    is_device_auto_send = any(k in low for k in auto_send_kws) and any(k in low for k in ["phát sinh", "trừ tiền", "trừ cước", "vừa gửi", "tự gửi", "129"])

    # Nhận diện Khiếu nại cước SMS
    cost_kws = [
        "khiếu nại cước", "khiếu nại cước phí", "khiếu nại về cước", "khiếu nại phát sinh",
        "khiếu nại trừ", "phát sinh cước", "hoàn cước", "trừ cước", "trừ tiền sms", "cước cao",
        "phát sinh nhiều tin nhắn", "phát sinh tin nhắn"
    ]
    is_cost_issue = (claimed_amount != "" or any(k in low for k in cost_kws) or bool(re.search(r'phát sinh\s*\d+\s*tin\s*nhắn', low))) and not is_device_auto_send

    # Nhận diện Lỗi gửi tin nhắn đi (MO Fail)
    mo_fail_kws = [
        "không nhắn tin đi được", "không nhắn được", "ko nhắn được", "không nhắn tin được",
        "không gửi được", "ko gửi được", "gửi không được", "gửi ko được", "gửi tin thất bại",
        "gửi tin nhắn đi không được", "không gửi tin đi được", "chấm than", "lỗi gửi tin nhắn đi",
        "lỗi gửi tin", "không gửi tin đi", "gửi tin nhắn không được", "không gửi được tin nhắn",
        "gửi sms không được", "không gửi được sms"
    ]
    is_mo_fail = (any(k in low for k in mo_fail_kws) or "lỗi gửi tin nhắn" in title_low or "lỗi gửi tin" in title_low) and not is_device_auto_send and not is_cost_issue

    # Nhận diện Lỗi nhận OTP / Brandname
    is_otp = any(k in low for k in ["otp", "mã xác thực", "ma xac thuc", "mã kích hoạt", "xác thực"]) or \
             (bool(app_brand) and any(k in low for k in ["không nhận", "ko nhận", "chưa nhận", "không về", "ko về", "không thấy", "lỗi nhận", "không gửi mã"])) or \
             bool(re.search(r'[-–]\s*BRN:', raw, re.IGNORECASE))

    # Nhận diện Lỗi nhận tin nhắn đến (MT Fail)
    mt_fail_kws = [
        "không nhận được tin", "ko nhận được tin", "không nhận được sms", "ko nhận được sms", 
        "không có tin nhắn đến", "nhận tin nhắn tất cả các số không được", "nhận tất cả các số không được",
        "tất cả các số không gửi tin", "không nhận tin nhắn từ", "lỗi nhận tin nhắn đến",
        "nhận tin nhắn không được", "nhận sms không được"
    ]
    is_mt_fail = any(k in low for k in mt_fail_kws) or "lỗi nhận tin nhắn" in title_low or bool(re.search(r'nhận\s*(?:được\s*)?tin(?:\s*nhắn)?.*(?:không|ko)\s*được', low))

    # Nhận diện Spam / Tin nhắn rác / Cam kết mở chặn
    is_spam = any(k in low for k in ["tin nhắn rác", "spam", "chặn spam", "quấy rối", "bản cam kết", "cam kết", "mở lại tin nhắn", "sps", "khóa smo"])

    # Quyết định problem_type
    if is_device_auto_send:
        dest_match = re.search(r'(?:đầu số|tới|đến)\s*([0-9]{3,8})\b', raw)
        dest_no = dest_match.group(1) if dest_match else (app_brand or "đầu số dịch vụ")
        problem_type = "device_background_sms"
        problem_title = f"Thiết bị tự phát sinh tin nhắn ngầm{f' (tới {dest_no})' if dest_no else ''}"
        suggested_cause_code = "2111"
        suggested_cause_name = "Do thiết bị đầu cuối"
        suggested_conclusion = (
            f"Kiểm tra hệ thống SMSC VNPT: Ghi nhận thuê bao có phát sinh các bản tin gửi đi (MO) thành công từ thiết bị tới đầu số {dest_no}. "
            f"Phân tích nguyên nhân: Do tính năng tự động gửi tin nhắn kích hoạt/đồng bộ ngầm của hệ điều hành máy {device_type or 'Oppo/Android'} "
            f"(Tài khoản dịch vụ hãng, sao lưu dữ liệu đám mây, tính năng Tìm thiết bị) hoặc ứng dụng ngầm trên máy tự khởi tạo bản tin MO. Mạng lưới VNPT đảm bảo thông suốt."
        )
        suggested_action_plan = (
            f"Giải thích cơ chế gửi tin nhắn kích hoạt/đồng bộ tự động của dòng máy {device_type or 'thiết bị'}. "
            f"Hướng dẫn khách hàng vào Cài đặt máy -> Tài khoản dịch vụ -> tắt tính năng Tự động sao lưu/Tìm thiết bị qua SMS, hoặc kiểm tra quyền gửi SMS của các ứng dụng lạ trên máy."
        )

    elif is_cost_issue:
        problem_type = "cost_issue"
        problem_title = f"Khiếu nại phát sinh cước SMS{f' ({claimed_amount})' if claimed_amount else ''}"
        suggested_cause_code = "2006"
        suggested_cause_name = "Cung cấp log file SMS theo yêu cầu"
        time_desc_phrase = f"trong {detected_time}" if (detected_time and detected_time != "--") else f"trong {time_range_desc}"
        suggested_conclusion = (
            f"Hệ thống SMSC VNPT ghi nhận thuê bao có phát sinh tin nhắn gửi đi (MO) {time_desc_phrase}. "
            f"Theo quy định cước viễn thông, cước dịch vụ được tính khi thuê bao khởi tạo gửi tin thành công lên tổng đài, "
            f"chính xác theo số lượng bản tin/phân đoạn thực tế phát sinh từ thiết bị."
        )
        suggested_action_plan = "Cung cấp chi tiết log SMSC phát sinh tin nhắn cho KTV/GDV giải thích cước cho khách hàng."

    elif is_mo_fail:
        problem_type = "mo_fail"
        problem_title = f"Không gửi được tin nhắn đi{f' (tới {app_brand})' if app_brand else ''} (Báo lỗi)"
        suggested_cause_code = "2014" if "Đã kiểm tra/cài số TTNT" not in prior_actions else "2015"
        suggested_cause_name = "Thuê bao cài đặt sai trung tâm tin nhắn" if "Đã kiểm tra/cài số TTNT" not in prior_actions else "Thuê bao chưa mở dịch vụ, gói cước"
        suggested_conclusion = "Kiểm tra Core và SMSC: Thuê bao gặp trở ngại khi thiết lập bản tin MO từ thiết bị."
        suggested_action_plan = "Kiểm tra trạng thái cước tài khoản chính, mở chiều SMO và cài đặt lại số Trung tâm tin nhắn (+8491020005)."

    elif is_otp:
        problem_type = "otp"
        problem_title = f"Không nhận được mã OTP{f' ({app_brand})' if app_brand else ''}"
        suggested_cause_code = "2111"
        suggested_cause_name = "Do thiết bị đầu cuối"
        suggested_conclusion = f"Hệ thống SMSC VNPT đã chuyển phát tin nhắn từ {app_brand or 'đối tác'} đến thuê bao thành công. Mạng lưới đảm bảo."
        suggested_action_plan = "Hướng dẫn khách hàng kiểm tra thiết bị: tắt chế độ lọc tin nhắn rác, kiểm tra hòm thư Spam, khởi động lại máy."

    elif is_mt_fail:
        problem_type = "mt_fail"
        problem_title = "Không nhận được tin nhắn đến"
        suggested_cause_code = "2011"
        suggested_cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        suggested_conclusion = "Trạng thái profile thuê bao trên Core HSS bình thường, dịch vụ SMS mở 2 chiều."
        suggested_action_plan = "Đề nghị khách hàng kiểm tra lại bộ nhớ tin nhắn máy và khởi động lại thiết bị."

    elif is_spam:
        problem_type = "spam"
        problem_title = "Sự cố tin nhắn rác / Khóa SPS / Bản cam kết"
        suggested_cause_code = "2007"
        suggested_cause_name = "Đóng/Mở chặn spam"
        suggested_conclusion = "Kiểm tra lịch sử phát sinh tin nhắn và rà soát danh sách chặn spam hoặc bản cam kết mở chiều."
        suggested_action_plan = "Kiểm tra tình trạng khóa SMO trên SPS/Core và hướng dẫn thủ tục mở lại theo Bản cam kết."

    else:
        problem_type = "other"
        problem_title = "Sự cố tin nhắn SMS"
        suggested_cause_code = "2011"
        suggested_cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        suggested_conclusion = "Hệ thống mạng VNPT hoạt động bình thường, không suy hao dịch vụ."
        suggested_action_plan = "Hướng dẫn khách hàng theo dõi thêm và kiểm tra thiết bị."

    # 6. Nhận diện Dấu hiệu bất thường (Anomaly)
    # NGUYÊN TẮC: Cảnh báo "KH chối không gửi / nghi vấn iMessage / mã độc" CHỈ kích hoạt khi có khiếu nại cước (cost_issue)
    anomaly = "Không có dấu hiệu bất thường"
    if problem_type == "cost_issue":
        denial_kws = [
            "không có soạn tin", "không soạn tin", "không hề nhắn tin",
            "không sử dụng dịch vụ tin nhắn", "không thao tác nhắn tin",
            "không chủ động soạn tin", "không quen biết", "không hề quen biết",
            "không biết của ai", "không cho ai mượn", "không ai mượn", "không ai giữ máy",
            "không có lịch sử gửi", "không hiện việc gửi tin", "không gửi cho ai",
            "không làm gì mà trừ cước", "không hề gửi", "không gửi tin nhắn cho ai"
        ]
        has_denial = any(k in low for k in denial_kws)
        is_iphone = "iphone" in device_type.lower()

        if any(k in low for k in ["vài giây", "liên tục", "nhanh liên tục", "tự động gửi"]):
            anomaly = "Gửi tin nhắn liên tục vài giây/tin - Dấu hiệu mã độc / Botnet tự động phát tán"
        elif re.search(r'\b(004\d{7,}|84004\d{7,})\b', raw):
            anomaly = "Phát sinh tin nhắn gửi đi quốc tế lạ (004...) - Dấu hiệu mã độc chiếm quyền SMS"
        elif has_denial:
            if is_iphone:
                anomaly = "KH khẳng định không gửi: Nghi vấn tính năng iMessage tự chuyển đổi sang SMS (Send as SMS) hoặc kích hoạt ngầm"
            else:
                anomaly = "KH khẳng định không gửi: Nghi vấn thiết bị cài app ngầm / nhiễm mã độc tự phát sinh SMS trong nền"

    elif re.search(r'\b(004\d{7,}|84004\d{7,})\b', raw):
        anomaly = "Phát sinh tin nhắn gửi đi quốc tế lạ (004...) - Dấu hiệu mã độc chiếm quyền SMS"

    # 7. Xây dựng Chuỗi tóm tắt chuẩn 6 mục Nghiệp vụ Viễn thông SMS
    act_str = f" (Đã làm: {', '.join(prior_actions)})" if prior_actions else ""
    summary_formatted = f"""1. Vấn đề phản ánh: {problem_title}
2. Mốc thời gian xảy ra: {detected_time} ({time_range_desc})
3. Ứng dụng / Đầu số: {app_brand or 'SMS thông thường'}
4. Thiết bị & Thao tác: Máy {device_type}{act_str}
5. Cước phí khiếu nại: {claimed_amount or 'Không đề cập'}
6. Cảnh báo / Dấu hiệu: {anomaly}"""

    return {
        "problem_type": problem_type,
        "problem_title": problem_title,
        "app_brand": app_brand,
        "device_type": device_type,
        "prior_actions": prior_actions,
        "claimed_amount": claimed_amount,
        "anomaly": anomaly,
        "incident_time": detected_time,
        "from_date": from_date,
        "to_date": to_date,
        "time_range_desc": time_range_desc,
        "suggested_cause_code": suggested_cause_code,
        "suggested_cause_name": suggested_cause_name,
        "suggested_conclusion": suggested_conclusion,
        "suggested_action_plan": suggested_action_plan,
        "summary_formatted": summary_formatted
    }


def generate_sms_ticket_summary(arg1: str, arg2: str = "", phone: str = "") -> str:
    """
    Hàm entry point tạo tóm tắt chuẩn 6 mục SMS cho cơ sở dữ liệu và hiển thị UI.
    Hỗ trợ linh hoạt cả 2 kiểu gọi:
      - generate_sms_ticket_summary(package_title, ticket_content, phone="")
      - generate_sms_ticket_summary(ticket_content, incident_time_fallback="")
    """
    if len(str(arg1 or "")) > 50 and len(str(arg2 or "")) <= 30 and not any(k in str(arg1).lower() for k in ["tin nhắn", "sms", "cuộc gọi", "thoại"]):
        t_content = str(arg1 or "").strip()
        p_title = "Tin nhắn (SMS)"
        inc_fallback = str(arg2 or "").strip()
    else:
        p_title = str(arg1 or "Tin nhắn (SMS)").strip()
        t_content = str(arg2 or arg1 or "").strip()
        inc_fallback = ""

    res = interpret_sms_ticket(t_content, package_title=p_title, incident_time_fallback=inc_fallback)
    return res.get("summary_formatted") or ""
