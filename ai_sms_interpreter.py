# ai_sms_interpreter.py
# Module chuyên trách NLP & Bóc tách thực thể phản ánh Tin nhắn (SMS)
# Chuẩn hóa 6 mục nghiệp vụ viễn thông VNPT, độc lập hoàn toàn với phân hệ Data

import re
from datetime import datetime, timedelta

# Danh mục các Ứng dụng / Ngân hàng / Đầu số OTP phổ biến
KNOWN_APPS_AND_BANKS = [
    ("1414", ["1414", "tttb"]),
    ("1543", ["1543", "gói cước đại lý", "soạn y", "xác nhận 1543"]),
    ("1539", ["1539", "ứng tiền nhanh", "ung tien 1539"]),
    ("8500", ["8500", "otp zalo 8500", "zalo 8500"]),
    ("7539", ["7539", "otp zalo 7539", "zalo 7539"]),
    ("9115", ["9115", "ứng tiền", "ung tien"]),
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
    ("PayPal", ["paypal", "pay pal", "pay-pal"]),
    ("Google", ["google", r"\bgg\b", "gmail"]),
    ("Apple", ["apple", "icloud", "id apple"]),
    ("Microsoft", ["microsoft", r"\bms\b", "live", "outlook"]),
    ("Grab", ["grab"]),
    ("Be", [r"\bbe\b", "be delivery", "be ride"]),
    ("Gojek", ["gojek"]),
    ("Ahamove", ["ahamove", "aha"]),
    ("GHTK", ["ghtk", "giao hàng tiết kiệm"]),
    ("GHN", ["ghn", "giao hàng nhanh"]),
    ("J&T Express", ["j&t", "jt express"]),
    ("Viettel Post", ["viettel post", "viettelpost"]),
    ("WhatsApp", ["whatsapp"]),
    ("Viber", ["viber"]),
    ("Zalo", ["zalo", "zalo pay", "zalopay"]),
    ("Momo", ["momo", "ví momo"]),
    ("VNPay", ["vnpay", "vn pay"]),
    ("VNPT Money", ["vnpt money", "vnpt pay", "vnptmoney", "vnptpay"]),
    ("Viettel Money", ["viettel money", "viettelpay", "viettel pay"]),
    ("Shopee", ["shopee", "shopeepay"]),
    ("Lazada", ["lazada"]),
    ("Tiki", ["tiki"]),
    ("Sendo", ["sendo"]),
    ("TikTok", ["tiktok", "tik tok", "tiktok shop"]),
    ("Facebook", ["facebook", r"\bfb\b", "meta"]),
    ("Telegram", ["telegram"]),
    ("Discord", ["discord"]),
    ("Netflix", ["netflix"]),
    ("Spotify", ["spotify"]),
    ("Steam", ["steam"]),
    ("Garena", ["garena"]),
    ("Riot Games", ["riot", "riot games", "vng"]),
    ("Binance", ["binance"]),
    ("Bybit", ["bybit"]),
    ("OpenAI / ChatGPT", ["openai", "chatgpt", "chat gpt"]),
    ("Xanh SM", ["xanh sm", "xanhsm"]),
    ("VETC / EPASS", ["vetc", "epass", "etc"]),
    # Các công ty tài chính & Vay tiêu dùng
    ("Home Credit", ["home credit", "homecredit"]),
    ("Mcredit", ["mcredit", "m credit"]),
    ("Shinhan Finance", ["shinhan finance", "shinhanfinance"]),
    ("Mirae Asset", ["mirae asset", "mafc"]),
    ("Easy Credit", ["easy credit", "easycredit"]),
    ("Lotte Finance", ["lotte finance", "lottefinance"]),
    # Ngân hàng số & Quốc tế
    ("Cake", ["cake", "cake by vpbank"]),
    ("TNEX", ["tnex"]),
    ("Timo", ["timo"]),
    ("KBank", ["kbank", "kasikorn"]),
    ("HSBC", ["hsbc"]),
    ("Standard Chartered", ["standard chartered", "scb bank"]),
    ("UOB", [r"\buob\b"]),
    ("Public Bank", ["public bank", "publicbank"]),
    ("Woori Bank", ["woori", "woori bank"]),
    # Công ty Chứng khoán
    ("VPS", [r"\bvps\b"]),
    ("SSI", [r"\bssi\b"]),
    ("VNDIRECT", ["vndirect", "vnd"]),
    ("TCBS", ["tcbs", "techcom securities"]),
    ("MBS", [r"\bmbs\b"]),
    ("HSC", [r"\bhsc\b"]),
    ("VCBS", ["vcbs"]),
    ("FPTS", ["fpts"]),
    # Dịch vụ công & Bảo hiểm
    ("VssID", ["vssid", "bảo hiểm xã hội", "bhxh"]),
    ("Dịch vụ công", ["dvcqg", "dịch vụ công", "dvc"]),
    ("Bảo Việt", ["bảo việt", "baoviet"]),
    ("Manulife", ["manulife"]),
    ("Prudential", ["prudential"]),
    ("Dai-ichi", ["dai-ichi", "daiichi"]),
    ("AIA", [r"\baia\b"]),
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

    return actions


def extract_target_fault_party(raw: str, low: str, app_brand: str = "", phone: str = "") -> str:
    """
    Bóc tách đối tượng phát sinh lỗi (Số gọi/nhận lỗi):
    - "Tất cả các số": Nếu khách báo lỗi xảy ra với tất cả các số, toàn bộ, mọi số, hoặc báo lỗi chung chung không chỉ đích danh.
    - Số điện thoại cụ thể: Nếu khách báo lỗi với một số di động/cố định cụ thể (vd: 0912xxxxxx, 0837xxxxxx).
    - Brandname / Đầu số: Nếu báo lỗi liên quan tới Brandname / Ngân hàng / Đầu số dịch vụ (Vietcombank, 1414, 9115, VNeID...).
    - "Không đề cập": Nếu là khiếu nại cước không chỉ rõ số phát sinh.
    """
    if not raw:
        return "Tất cả các số"

    clean_phone = re.sub(r'[^0-9]', '', str(phone or ''))
    clean_p9 = clean_phone[-9:] if len(clean_phone) >= 9 else ""

    # 1. Quét từ khóa "Tất cả các số" / "Mọi số" / "Toàn bộ"
    all_numbers_patterns = [
        r'tất\s*cả\s*(?:các|mọi)?\s*(?:số|thuê\s*bao|cuộc\s*gọi|tin\s*nhắn|sms|người)',
        r'toàn\s*bộ\s*(?:các|mọi)?\s*(?:số|thuê\s*bao|cuộc\s*gọi|tin\s*nhắn|sms)',
        r'mọi\s*(?:số|thuê\s*bao|người)',
        r'bất\s*kỳ\s*(?:số|thuê\s*bao|ai)',
        r'không\s*(?:nhận|gửi|gọi|liên\s*lạc)\s*(?:được\s*)?(?:cho\s*)?ai',
        r'ai\s*(?:gọi|nhắn|gửi)\s*(?:đến|tới)?\s*(?:cũng|đều)\s*(?:không|ko|báo|bị)',
        r'(?:không|ko)\s*nhận\s*(?:được\s*)?(?:tin\s*nhắn|sms|cuộc\s*gọi)\s*(?:nào|từ\s*ai)',
        r'tất\s*cả\s*đều\s*(?:bị|không|ko|lỗi)',
        r'gửi\s*(?:đi\s*)?tất\s*cả',
        r'nhận\s*(?:tất\s*cả|mọi)',
    ]
    for pat in all_numbers_patterns:
        if re.search(pat, low):
            return "Tất cả các số"

    # 2. Quét số điện thoại đối phương cụ thể trong nội dung (vd: 0912345678, 84912345678)
    phone_candidates = re.findall(r'(?:\+?84|0)([35789]\d{8})\b', raw)
    if not phone_candidates:
        phone_candidates = re.findall(r'\b(0[1-9]\d{8,9})\b', raw)

    valid_party_phone = ""
    for cand in phone_candidates:
        clean_cand = re.sub(r'[^0-9]', '', cand)
        # Bỏ qua chính số thuê bao đang phản ánh
        if clean_p9 and clean_cand[-9:] == clean_p9:
            continue
        # Bỏ qua số trung tâm tin nhắn VNPT (+8491020005)
        if "91020005" in clean_cand:
            continue
        # Bỏ qua hotline CSKH 18001091, 9191
        if "18001091" in clean_cand or clean_cand in ("9191", "18001091", "1900"):
            continue
        valid_party_phone = cand if cand.startswith("0") else f"0{cand}"
        break

    if valid_party_phone:
        return valid_party_phone

    # 3. Quét Brandname / Tên đối tác / Đầu số ngắn
    if app_brand and app_brand != "SMS thông thường":
        return app_brand

    # Quét đầu số ngắn cụ thể (vd: 1414, 9115, 129, 6089, 888, 900, 156...)
    short_match = re.search(r'(?:đầu\s*số|tới|đến|gửi|nhắn|số)\s*([0-9]{3,6})\b', raw, re.IGNORECASE)
    if short_match:
        s_code = short_match.group(1).strip()
        if s_code not in ("1800", "1900", "1091"):
            return s_code

    # 4. Khiếu nại phát sinh cước thông thường không nêu đích danh số
    if any(k in low for k in ["khiếu nại cước", "phát sinh cước", "trừ cước", "trừ tiền"]) and not any(k in low for k in ["không gửi được", "không nhận được", "lỗi gửi", "lỗi nhận"]):
        return "Không đề cập"

    # Mặc định các lỗi gửi/nhận chung không chỉ đích danh -> Tất cả các số
    return "Tất cả các số"


def interpret_sms_ticket(ticket_content: str, package_title: str = "", incident_time_fallback: str = "", created_time: str = "", phone: str = "") -> dict:
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
        c_str = str(created_time).strip().split(".")[0]
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                receipt_dt = datetime.strptime(c_str, fmt)
                break
            except Exception:
                pass

    # Nếu chưa có receipt_dt, thử quét trong nội dung văn bản (vd: Tiếp nhận lúc: 05/10/2026, Ngày tạo: 05-10-2026)
    if not receipt_dt:
        m_rec_txt = re.search(r'(?:tiếp nhận|ngày tạo|thời gian tạo|tạo lúc|nhận lúc)\s*(?:vào|lúc)?\s*:?\s*([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20\d{2})(?:\s+([0-2]?[0-9])[:hH]([0-5][0-9]))?', raw, re.IGNORECASE)
        if m_rec_txt:
            d_r, m_r, y_r = int(m_rec_txt.group(1)), int(m_rec_txt.group(2)), int(m_rec_txt.group(3))
            h_r = int(m_rec_txt.group(4)) if m_rec_txt.group(4) else 0
            mi_r = int(m_rec_txt.group(5)) if m_rec_txt.group(5) else 0
            try:
                receipt_dt = datetime(y_r, m_r, d_r, h_r, mi_r)
            except Exception:
                pass

    # Quét giờ xảy ra nếu có (vd: 09:15, 9h30, lúc 14:00, lúc 10h, 10h00)
    time_str = ""
    is_time_from_receipt = False
    t_match = re.search(r'\b([0-2]?[0-9])[:hH]([0-5][0-9])(?:\s*(?:phút|p))?\b', raw)
    if t_match:
        time_str = f"{pad(int(t_match.group(1)))}:{pad(int(t_match.group(2)))}"
    else:
        t_h_only = re.search(r'(?:lúc|vào|khoảng|tầm)?\s*\b([0-2]?[0-9])\s*(?:h|giờ|gio)\b', raw, re.IGNORECASE)
        if t_h_only:
            time_str = f"{pad(int(t_h_only.group(1)))}:00"

    # Nếu nội dung văn bản không có giờ, bổ sung quét giờ từ ngày tiếp nhận (created_time) hoặc incident_time_fallback
    if not time_str:
        if receipt_dt and (receipt_dt.hour or receipt_dt.minute):
            time_str = receipt_dt.strftime("%H:%M")
            is_time_from_receipt = True
        elif incident_time_fallback:
            t_fb = re.search(r'\b([0-2]?[0-9])[:hH]([0-5][0-9])(?:\s*(?:phút|p))?\b', str(incident_time_fallback))
            if t_fb:
                time_str = f"{pad(int(t_fb.group(1)))}:{pad(int(t_fb.group(2)))}"
                is_time_from_receipt = True
            else:
                t_fb_h = re.search(r'(?:lúc|vào|khoảng|tầm)?\s*\b([0-2]?[0-9])\s*(?:h|giờ|gio)\b', str(incident_time_fallback), re.IGNORECASE)
                if t_fb_h:
                    time_str = f"{pad(int(t_fb_h.group(1)))}:00"
                    is_time_from_receipt = True

    # 0. Quét Ngày tiếng Anh (vd: Sep 19, 2026 ... đến Sep 20, 2026 hoặc 19 Sep 2026)
    en_month_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    en_dates = re.findall(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+([0-3]?[0-9])(?:st|nd|rd|th)?,?\s+(20\d{2})\b', raw, re.IGNORECASE)
    if not en_dates:
        en_dates = [(m[1], m[0], m[2]) for m in re.findall(r'\b([0-3]?[0-9])\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*,?\s+(20\d{2})\b', raw, re.IGNORECASE)]

    # 0A. Quét Khoảng Ngày Cụ Thể (Date Range, vd: 13-09-2026 - 20-09-2026, từ 13/09 đến 20/09/2026, 08/10 → 11/10/2026)
    range_pat = re.compile(
        r'(?:từ\s+(?:ngày\s+)?)?([0-3]?[0-9])[/\-]([0-1]?[0-9])(?:[/\-](20\d{2}|\d{2}))?'
        r'\s*(?:đến|\-|–|—|->|→|tới)\s*'
        r'(?:ngày\s+)?([0-3]?[0-9])[/\-]([0-1]?[0-9])(?:[/\-](20\d{2}|\d{2}))?',
        re.IGNORECASE
    )
    m_range = range_pat.search(raw) or (range_pat.search(str(incident_time_fallback)) if incident_time_fallback else None)

    # 0B. Quét tất cả các mốc ngày đầy đủ dd/mm/yyyy trong văn bản (vd ECMS: 00:17:01 01-09-2026- 12:39:30 13-09-2026)
    all_full_dates = re.findall(r'\b([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20\d{2})\b', raw)

    # 1. Full date dd/mm/yyyy (vd: 14/10/2026, 05/10/2026)
    m_full = None
    if not m_range and not en_dates and len(all_full_dates) < 2:
        m_full = re.search(r'\b([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20\d{2}|\d{2})\b', raw)

    # 2. Month pattern (vd: cước tháng 09/2026, trong tháng 9, T09/2026, T9/2026, kỳ cước 09/2026, hoặc độc lập 09/2026)
    m_month = None
    if not m_range and not m_full and not en_dates and len(all_full_dates) < 2:
        m_month = re.search(r'(?<![0-9/])(?:trong\s+tháng|cước\s+tháng|kỳ\s+cước|kỳ|tháng|t)\s*([0-1]?[0-9])(?:\s*[/\-]\s*(20\d{2}))?\b', raw, re.IGNORECASE)
        if not m_month:
            m_month = re.search(r'(?<![0-9/])([0-1]?[0-9])[/\-](20\d{2})\b', raw)

    # 3. Day/Month without year (vd: ngày 28/08, 14/10, lúc 14:00 ngày 28/08)
    m_dm = None
    if not m_range and not m_full and not m_month and not en_dates and len(all_full_dates) < 2:
        m_dm = re.search(r'(?:ngày|hôm|lúc|từ)\s*([0-3]?[0-9])[/\-]([0-1]?[0-9])\b', raw, re.IGNORECASE) or \
               re.search(r'(?<![0-9/])([0-3]?[0-9])[/\-]([0-1]?[0-9])(?![0-9/])', raw)

    # 4. Fallback sang incident_time_fallback nếu nội dung hoàn toàn không có ngày tháng và không có ngày tiếp nhận (receipt_dt)
    if not m_range and not m_full and not m_month and not m_dm and not en_dates and len(all_full_dates) < 2:
        if not receipt_dt and incident_time_fallback:
            fb_str = str(incident_time_fallback).strip()
            m_full = re.search(r'\b([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20\d{2}|\d{2})\b', fb_str)
            if not m_full:
                m_dm = re.search(r'(?<![0-9/])([0-3]?[0-9])[/\-]([0-1]?[0-9])(?![0-9/])', fb_str)

    if en_dates and len(en_dates) >= 2:
        m_str1, d1_str, y1_str = en_dates[0]
        m_str2, d2_str, y2_str = en_dates[-1]
        m1_val = en_month_map.get(m_str1.lower()[:3], 9)
        m2_val = en_month_map.get(m_str2.lower()[:3], 9)
        d1_val, y1_val = int(d1_str), int(y1_str)
        d2_val, y2_val = int(d2_str), int(y2_str)
        from_date = f"{y1_val}-{pad(m1_val)}-{pad(d1_val)} 00:00:00"
        to_date = f"{y2_val}-{pad(m2_val)}-{pad(d2_val)} 23:59:59"
        time_range_desc = f"{pad(d1_val)}/{pad(m1_val)} → {pad(d2_val)}/{pad(m2_val)}/{y2_val}"
        detected_time = time_range_desc

    elif m_range:
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

    elif len(all_full_dates) >= 2 and any(k in raw.lower() for k in ["đến", "den", "tới", "→", "->", "kỳ cước"]):
        d1_val, m1_val, y1_val = int(all_full_dates[0][0]), int(all_full_dates[0][1]), int(all_full_dates[0][2])
        d2_val, m2_val, y2_val = int(all_full_dates[-1][0]), int(all_full_dates[-1][1]), int(all_full_dates[-1][2])
        if (d1_val != d2_val or m1_val != m2_val or y1_val != y2_val):
            from_date = f"{y1_val}-{pad(m1_val)}-{pad(d1_val)} 00:00:00"
            to_date = f"{y2_val}-{pad(m2_val)}-{pad(d2_val)} 23:59:59"
            time_range_desc = f"{pad(d1_val)}/{pad(m1_val)}/{y1_val} → {pad(d2_val)}/{pad(m2_val)}/{y2_val}"
            detected_time = time_range_desc

    elif m_full:
        d_val = int(m_full.group(1))
        m_val = int(m_full.group(2))
        raw_y = m_full.group(3)
        y_val = int(f"20{raw_y}") if len(raw_y) == 2 else int(raw_y)
        if 1 <= d_val <= 31 and 1 <= m_val <= 12:
            base_date_str = f"{pad(d_val)}/{pad(m_val)}/{y_val}"
            receipt_tag = " (Tiếp nhận)" if is_time_from_receipt else ""
            detected_time = f"{time_str} ngày {base_date_str}{receipt_tag}".strip() if time_str else f"{base_date_str}{receipt_tag}"
            try:
                target_dt = datetime(y_val, m_val, d_val)
                base_start = target_dt
                from_date = base_start.strftime("%Y-%m-%d 00:00:00")
                base_receipt = receipt_dt if receipt_dt else target_dt
                end_dt = base_receipt + timedelta(days=3)
                to_date = end_dt.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{base_start.strftime('%d/%m/%Y')} → {end_dt.strftime('%d/%m/%Y')}"
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
                base_start = target_dt
                from_date = base_start.strftime("%Y-%m-%d 00:00:00")
                base_receipt = receipt_dt if receipt_dt else target_dt
                end_dt = base_receipt + timedelta(days=3)
                to_date = end_dt.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{base_start.strftime('%d/%m/%Y')} → {end_dt.strftime('%d/%m/%Y')}"
            except Exception:
                from_date = f"{y_val}-{pad(m_val)}-{pad(d_val)} 00:00:00"
                to_date = now.strftime("%Y-%m-%d 23:59:59")
                time_range_desc = f"{base_date_str} → Hiện tại"

    if not from_date:
        base_target = None
        # 🎯 ƯU TIÊN SỐ 1: NẾU KHÔNG CÓ NGÀY SỰ CỐ RIÊNG -> LẤY CHÍNH XÁC NGÀY TIẾP NHẬN PHIẾU (receipt_dt)
        if receipt_dt:
            base_target = receipt_dt
            if detected_time == "--":
                if time_str:
                    detected_time = f"{time_str} ngày {receipt_dt.strftime('%d/%m/%Y')} (Tiếp nhận)"
                elif receipt_dt.hour or receipt_dt.minute:
                    detected_time = f"{receipt_dt.strftime('%H:%M')} ngày {receipt_dt.strftime('%d/%m/%Y')} (Tiếp nhận)"
                else:
                    detected_time = f"{receipt_dt.strftime('%d/%m/%Y')} (Tiếp nhận)"
        elif incident_time_fallback:
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                try:
                    base_target = datetime.strptime(str(incident_time_fallback).strip().split(".")[0], fmt)
                    break
                except Exception:
                    pass
            if detected_time == "--" and base_target:
                if time_str:
                    detected_time = f"{time_str} ngày {base_target.strftime('%d/%m/%Y')}"
                else:
                    detected_time = f"{base_target.strftime('%d/%m/%Y')}"

        if base_target:
            base_start = base_target
            from_date = base_start.strftime("%Y-%m-%d 00:00:00")
            base_receipt = receipt_dt if receipt_dt else base_target
            end_dt = base_receipt + timedelta(days=3)
            to_date = end_dt.strftime("%Y-%m-%d 23:59:59")
            time_range_desc = f"{base_start.strftime('%d/%m/%Y')} → {end_dt.strftime('%d/%m/%Y')}"
            if detected_time == "--":
                detected_time = time_range_desc
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

    if not app_brand:
        # Bắt linh hoạt theo mẫu "OTP từ <Tên>", "OTP của <Tên>", "mã xác thực từ <Tên>", "app <Tên>"
        gen_match = re.search(r'(?:otp\s+(?:từ|của|qua)|mã\s+(?:xác thực\s+)?(?:từ|của)|nhận\s+tin\s+từ|sms\s+từ|app|ứng dụng|brn)[:\s]+([A-Za-z0-9_\-\.\s]{2,25}?)(?:,|\.|\s+vẫn|\s+bị|\s+không|\s+ko|\s+được|\s+báo|\n|$)', raw, re.IGNORECASE)
        if gen_match:
            candidate = gen_match.group(1).strip()
            stop_candidates = [
                "sdt", "số", "tb", "kh", "máy", "ai", "nào", "gì", "đâu", "được", "người", "nhau",
                "minh", "mình", "hệ thống", "tổng đài", "tin nhắn", "phản ánh",
                "1414", "5656", "156", "9123", "123", "1333", "18001091", "9191", "191", "888", "900", "tttb", "dnc", "vinaphone"
            ]
            if candidate and candidate.lower() not in stop_candidates and len(candidate) >= 2:
                if any(c.isupper() for c in candidate) or len(candidate) <= 10:
                    app_brand = candidate.strip()

    # 2B. Bóc tách Đối tượng phát sinh lỗi (Số gọi/nhận lỗi)
    target_fault_party = extract_target_fault_party(raw, low, app_brand=app_brand, phone=phone)

    # 3. Bóc tách Thiết bị & Thao tác KTV
    device_type = extract_sms_device(raw)
    prior_actions = extract_sms_prior_actions(raw)

    # 4. Bóc tách Cước phí khiếu nại (nếu có)
    claimed_amount = ""
    is_cost_related = any(k in low for k in ["cước", "tiền", "phát sinh", "trừ tiền", "trừ cước", "hoàn tiền", "khiếu nại cước", "khiếu nại", "khieu nai", "giảm trừ"])
    if is_cost_related:
        amt_match = re.search(r'(\d{1,3}(?:[.,]\d{3})+)(?:\s*(?:đ|dong|đồng|k))?', raw)
        if amt_match:
            claimed_amount = f"{amt_match.group(1)} đ"

    # 5. Phân loại Loại vấn đề (Problem Type)
    # Nhận diện Khiếu nại cước SMS (Ưu tiên nếu có số tiền hoặc từ khóa khiếu nại cước trực tiếp)
    cost_kws = [
        "khiếu nại cước", "khiếu nại cước phí", "khiếu nại về cước", "khiếu nại phát sinh",
        "khiếu nại trừ", "phát sinh cước", "hoàn cước", "trừ cước", "trừ tiền sms", "cước cao",
        "phát sinh nhiều tin nhắn", "phát sinh tin nhắn", "giảm trừ cước", "giảm cước", "hoàn tiền",
        "kiểm tra cước", "cước tháng", "cước sms", "chi tiết cước", "đóng cước sms", "đóng cước"
    ]
    is_cost_issue = (
        claimed_amount != "" or 
        any(k in low for k in cost_kws) or 
        any(k in title_low for k in ["cước", "khiếu nại cước", "phát sinh cước", "trừ tiền"]) or
        bool(re.search(r'khiếu\s*nại.*?cước', low)) or
        bool(re.search(r'phát sinh\s*\d+\s*tin\s*nhắn', low))
    )

    # Nhận diện Thiết bị tự gửi tin nhắn ngầm (Activation SMS / Cloud sync / Ứng dụng ngầm / Đầu số ngắn)
    auto_send_kws = [
        "không thao tác gửi", "ko thao tác gửi", "không gửi nhưng", "ko gửi nhưng",
        "khẳng định không nhắn", "khẳng định ko nhắn", "không nhắn tin nhưng", "ko nhắn tin nhưng",
        "tự gửi tin", "tự động gửi", "tự phát sinh", "tb vừa gửi tin nhắn", "tb vừ gửi tin nhắn",
        "máy tự gửi", "tự gửi sms", "tự động nhắn", "không chủ động gửi", "không gửi tin nhắn nhưng",
        "không nhắn tin", "không có nhắn tin"
    ]
    is_device_auto_send = any(k in low for k in auto_send_kws) and any(k in low for k in ["phát sinh", "trừ tiền", "trừ cước", "vừa gửi", "tự gửi", "129"]) and not is_cost_issue

    # Nhận diện Lỗi gửi tin nhắn đi (MO Fail)
    mo_fail_kws = [
        "không nhắn tin đi được", "không nhắn được", "ko nhắn được", "không nhắn tin được",
        "không gửi được", "ko gửi được", "gửi không được", "gửi ko được", "gửi tin thất bại",
        "gửi tin nhắn đi không được", "không gửi tin đi được", "chấm than", "lỗi gửi tin nhắn đi",
        "lỗi gửi tin", "không gửi tin đi", "gửi tin nhắn không được", "không gửi được tin nhắn",
        "gửi sms không được", "không gửi được sms"
    ]
    is_mo_fail = (
        any(k in low for k in mo_fail_kws) or 
        any(k in title_low for k in ["lỗi gửi tin nhắn", "lỗi gửi tin", "gửi tin nhắn đi", "gửi tin đi", "gửi sms"]) or
        bool(re.search(r'gửi\s*(?:được\s*)?tin(?:\s*nhắn)?.*?(?:không|ko)\s*được', low)) or
        bool(re.search(r'không\s*(?:thể\s*)?(?:gửi|nhắn)\s*(?:được\s*)?tin(?:\s*nhắn)?', low))
    ) and not is_device_auto_send and not is_cost_issue

    # Nhận diện Lỗi nhận OTP / Brandname
    is_otp = (
        any(k in low for k in ["otp", "mã xác thực", "ma xac thuc", "mã kích hoạt", "xác thực"]) or 
        any(k in title_low for k in ["otp", "mã xác thực", "brandname"]) or
        (bool(app_brand) and any(k in low for k in ["không nhận", "ko nhận", "chưa nhận", "không về", "ko về", "không thấy", "lỗi nhận", "không gửi mã", "chậm", "trễ", "hết hạn"])) or 
        bool(re.search(r'[-–]\s*BRN:', raw, re.IGNORECASE))
    )

    # Nhận diện OTP chậm / trễ / hết hạn
    is_delayed = any(k in low for k in ["chậm", "trễ", "hết hạn", "muộn", "cham", "tre", "het han", "muon", "về chậm", "nhận chậm"])
    is_otp_delayed = (is_otp or bool(app_brand)) and is_delayed

    # Nhận diện Lỗi nhận tin nhắn đến (MT Fail)
    mt_fail_kws = [
        "không nhận được tin", "ko nhận được tin", "không nhận được sms", "ko nhận được sms", 
        "không có tin nhắn đến", "nhận tin nhắn tất cả các số không được", "nhận tất cả các số không được",
        "tất cả các số không gửi tin", "không nhận tin nhắn từ", "lỗi nhận tin nhắn đến",
        "nhận tin nhắn không được", "nhận sms không được"
    ]
    is_mt_fail = (
        any(k in low for k in mt_fail_kws) or 
        any(k in title_low for k in ["lỗi nhận tin nhắn", "lỗi nhận tin", "nhận tin nhắn đến", "nhận tin đến", "nhận sms"]) or 
        bool(re.search(r'nhận\s*(?:được\s*)?tin(?:\s*nhắn)?.*?(?:không|ko)\s*được', low)) or
        bool(re.search(r'không\s*(?:thể\s*)?nhận\s*(?:được\s*)?tin(?:\s*nhắn)?', low))
    ) and not is_cost_issue

    # Nhận diện Spam / Tin nhắn rác
    spam_kws = [
        "tin nhắn rác", "tin rac", "spam", "chặn spam", "quấy rối", "sps", 
        "khóa smo", "khoa smo", "chan smo", "chặn smo", "khóa spam", "chặn tin rác",
        "cam kết", "bản cam kết"
    ]
    is_spam = any(k in low for k in spam_kws) or any(k in title_low for k in ["spam", "tin nhắn rác", "khóa spam", "chặn spam", "smo"])

    dnc_kws = [
        "dnc", "không nhận quảng cáo", "từ chối nhận tin", "từ chối tin quảng cáo",
        "chặn tin rác dnc", "quảng cáo 5656", "danh sách dnc", "từ chối qc", "soạn tc"
    ]
    is_dnc = any(k in low for k in dnc_kws)

    # Quyết định problem_type
    if is_cost_issue:
        problem_type = "cost_issue"
        problem_title = f"Khiếu nại phát sinh cước SMS{f' ({claimed_amount})' if claimed_amount else ''}"
        suggested_cause_code = "2006"
        suggested_cause_name = "Cung cấp log file SMS theo yêu cầu"
        time_desc_phrase = f"trong {detected_time}" if (detected_time and detected_time != "--") else f"trong {time_range_desc}"
        suggested_conclusion = (
            f"Hệ thống tổng đài ghi nhận thuê bao có phát sinh cước tin nhắn (MO) {time_desc_phrase}. "
            f"Cước dịch vụ được tính theo lưu lượng bản tin thực tế phát sinh từ máy của khách hàng."
        )
        suggested_action_plan = (
            "Cung cấp chi tiết lịch sử gửi tin nhắn (thời gian, số nhận, số lượng tin) cho khách hàng đối chiếu. "
            "Trường hợp bản tin phát sinh bất thường do thiết bị tự gửi ngầm hoặc ứng dụng lạ, hướng dẫn khách hàng kiểm tra ứng dụng hoặc khôi phục cài đặt gốc."
        )

    elif is_device_auto_send:
        dest_match = re.search(r'(?:đầu số|tới|đến)\s*([0-9]{3,8})\b', raw)
        dest_no = dest_match.group(1) if dest_match else (app_brand or "đầu số dịch vụ")
        problem_type = "device_background_sms"
        problem_title = f"Thiết bị tự phát sinh tin nhắn ngầm{f' (tới {dest_no})' if dest_no else ''}"
        suggested_cause_code = "2111"
        suggested_cause_name = "Do thiết bị đầu cuối"
        suggested_conclusion = (
            f"Kiểm tra hệ thống SMSC VinaPhone: Ghi nhận thuê bao có phát sinh các bản tin gửi đi (MO) thành công từ thiết bị tới đầu số {dest_no}. "
            f"Phân tích nguyên nhân: Do tính năng tự động gửi tin nhắn kích hoạt/đồng bộ ngầm của hệ điều hành máy {device_type or 'Oppo/Android'} "
            f"(Tài khoản dịch vụ hãng, sao lưu dữ liệu đám mây, tính năng Tìm thiết bị) hoặc ứng dụng ngầm trên máy tự khởi tạo bản tin MO."
        )
        suggested_action_plan = (
            f"Giải thích cơ chế gửi tin nhắn kích hoạt/đồng bộ tự động của dòng máy {device_type or 'thiết bị'}. "
            f"Hướng dẫn khách hàng vào Cài đặt máy -> Tài khoản dịch vụ -> tắt tính năng Tự động sao lưu/Tìm thiết bị qua SMS, hoặc kiểm tra quyền gửi SMS của các ứng dụng lạ trên máy."
        )

    elif is_mo_fail:
        problem_type = "mo_fail"
        problem_title = f"Không gửi được tin nhắn đi{f' (tới {app_brand})' if app_brand else ''} (Báo lỗi)"
        suggested_cause_code = "2014" if "Đã kiểm tra/cài số TTNT" not in prior_actions else "2015"
        suggested_cause_name = "Thuê bao cài đặt sai trung tâm tin nhắn" if "Đã kiểm tra/cài số TTNT" not in prior_actions else "Thuê bao chưa mở dịch vụ, gói cước"
        suggested_conclusion = "Kiểm tra Core và SMSC: Thuê bao gặp trở ngại khi thiết lập bản tin MO từ thiết bị."
        suggested_action_plan = "Kiểm tra trạng thái cước tài khoản chính, mở chiều SMO và cài đặt lại số Trung tâm tin nhắn (+8491020005)."

    elif is_otp_delayed:
        problem_type = "otp_delayed"
        problem_title = f"Nhận OTP chậm{f' ({app_brand})' if app_brand else ''}"
        suggested_cause_code = "2011"
        suggested_cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        suggested_conclusion = (
            f"Profile thuê bao trên Core HSS mở đầy đủ 2 chiều dịch vụ, thuê bao hoạt động bình thường. "
            f"Khách hàng nhận tin nhắn OTP từ {app_brand or 'đối tác'} bị chậm (khi nhận được mã đã hết hạn) do hệ thống máy chủ / tổng đài tin nhắn của đối tác bị quá tải, nghẽn mạng cục bộ tại thời điểm phát tin nên chuyển tiếp sang mạng VinaPhone muộn. "
            f"Hệ thống SMSC VinaPhone luôn chuyển phát bản tin MT đến thiết bị ngay khi tiếp nhận từ đối tác."
        )
        suggested_action_plan = (
            f"Giải thích cho khách hàng về nguyên nhân chậm trễ do luồng phát tin từ phía máy chủ tổng đài của đối tác {app_brand or ''}, "
            f"Nhờ khách hàng theo dõi thêm và thao tác yêu cầu gửi lại mã OTP vào thời điểm khác."
        )

    elif is_otp:
        problem_type = "otp"
        problem_title = f"Không nhận được mã OTP{f' ({app_brand})' if app_brand else ''}"
        suggested_cause_code = "2111"
        suggested_cause_name = "Do thiết bị đầu cuối"
        suggested_conclusion = f"Hệ thống SMSC VinaPhone đã chuyển phát tin nhắn từ {app_brand or 'đối tác'} đến thuê bao thành công."
        suggested_action_plan = "Hướng dẫn khách hàng kiểm tra thiết bị: tắt chế độ lọc tin nhắn rác, kiểm tra hòm thư Spam, khởi động lại máy."

    elif is_dnc:
        problem_type = "mt_fail"
        problem_title = "Từ chối nhận tin nhắn quảng cáo / DNC"
        suggested_cause_code = "2011"
        suggested_cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        suggested_conclusion = "Bản tin quảng cáo bị từ chối chuyển phát do thuê bao đăng ký Danh sách Không quảng cáo (DNC/5656)."
        suggested_action_plan = "Giải thích chính sách DNC bảo vệ người dùng và hướng dẫn hủy từ chối nếu muốn nhận lại tin nhắn quảng cáo."

    elif is_mt_fail:
        problem_type = "mt_fail"
        problem_title = "Không nhận được tin nhắn đến"
        suggested_cause_code = "2011"
        suggested_cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        suggested_conclusion = "Trạng thái profile thuê bao trên Core HSS bình thường, dịch vụ SMS mở 2 chiều."
        suggested_action_plan = "Đề nghị khách hàng kiểm tra lại bộ nhớ tin nhắn máy và khởi động lại thiết bị."

    elif is_spam:
        problem_type = "spam"
        problem_title = "Bị khóa chặn spam tin nhắn (SMO)"
        suggested_cause_code = "2007"
        suggested_cause_name = "Đóng/Mở chặn spam"
        suggested_conclusion = "Hệ thống ghi nhận thuê bao đang bị khóa chặn chiều gửi tin nhắn (SMO) do nghi ngờ phát tán tin nhắn rác/spam."
        suggested_action_plan = "KTV kiểm tra trạng thái khóa chặn trên hệ thống SPS/Core và xử lý theo quy định."

    else:
        problem_type = "other"
        problem_title = "Sự cố tin nhắn SMS"
        suggested_cause_code = "2011"
        suggested_cause_name = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"
        suggested_conclusion = "Hệ thống mạng VinaPhone hoạt động bình thường, không suy hao dịch vụ."
        suggested_action_plan = "Hướng dẫn khách hàng theo dõi thêm và kiểm tra thiết bị."

    # 6. Nhận diện Dấu hiệu bất thường (Anomaly)
    anomaly = "Không có dấu hiệu bất thường"
    denial_kws = [
        "không có soạn tin", "không hề soạn tin", "chưa từng soạn tin",
        "không hề nhắn tin", "không hề nhắn", "chưa từng nhắn tin", "chưa từng nhắn",
        "không hề gửi tin", "không hề gửi", "chưa từng gửi tin", "chưa từng gửi",
        "không sử dụng dịch vụ tin nhắn", "không thao tác nhắn tin", "không thao tác gửi",
        "không chủ động soạn tin", "không chủ động gửi", "không quen biết", "không hề quen biết",
        "không biết của ai", "không biết nhắn tin", "không cho ai mượn", "không ai mượn", "không ai giữ máy",
        "không có lịch sử gửi", "không hiện việc gửi tin", "không gửi cho ai", "không gửi tin nhắn cho ai",
        "không làm gì mà trừ cước", "không gửi bất cứ số nào", "kh khẳng định không nhắn", "khẳng định không nhắn",
        "kh khẳng định không nhắn tin", "kh khẳng định ko nhắn tin", "kh khẳng định ko nhắn", "khẳng định ko nhắn",
        "kh khẳng định không gửi", "khẳng định không gửi", "khẳng định không gửi tin",
        "không gửi tin nhắn nào", "không gửi tin nào", "không gửi tin nhắn", "không nhắn tin nào"
    ]
    # Chỉ xem xét phủ nhận cước khi KHÔNG PHẢI lỗi gửi tin đi (MO Fail)
    is_send_failure = (
        problem_type == "mo_fail" or 
        any(k in low for k in ["không gửi được", "gửi không được", "ko gửi được", "gửi ko được", "không nhắn được", "báo không gửi được", "báo lỗi", "lỗi hệ thống"])
    )
    has_denial = False if is_send_failure else (
        any(k in low for k in denial_kws) or
        bool(re.search(r'(?:kh|khách\s*hàng)?\s*khẳng\s*định.*?(?:không|ko)\s*(?:gửi|nhắn|soạn)', low)) or
        bool(re.search(r'(?:không|ko)\s*(?:hề\s*)?(?:gửi|nhắn)\s*(?:tin\s*)?(?:nhắn\s*)?(?:nào|đi)', low)) or
        bool(re.search(r'không\s*(?:hề\s*)?(?:quen\s*biết|biết\s*của\s*ai)', low))
    )

    anomaly = "Không có dấu hiệu bất thường"
    if problem_type in ("mt_fail", "otp", "otp_delayed"):
        if is_dnc:
            anomaly = "Thuê bao đăng ký danh sách Không quảng cáo (DNC/5656)"
        else:
            anomaly = "Không có dấu hiệu bất thường"
    else:
        has_tried_smsc_already = (
            problem_type == "mo_fail" and
            ("kiểm tra" in low or "cài" in low or "đúng" in low or "chuẩn" in low or "reset" in low) and
            ("ttnt" in low or "tttn" in low or "smsc" in low or "trung tâm" in low or "smo" in low) and
            ("không được" in low or "vẫn không" in low or "vẫn ko" in low or "ko được" in low or "không gửi được" in low or "báo lỗi" in low or "thất bại" in low)
        )

        if any(k in low for k in ["vài giây", "liên tục", "nhanh liên tục", "tự động gửi"]):
            anomaly = "Gửi tin nhắn liên tục vài giây/tin - Dấu hiệu mã độc / Botnet tự động phát tán"
        elif re.search(r'\b(004\d{7,}|84004\d{7,})\b', raw):
            anomaly = "Phát sinh tin nhắn gửi đi quốc tế lạ (004...) - Dấu hiệu mã độc chiếm quyền SMS"
        elif has_denial:
            anomaly = "Không có dấu hiệu bất thường"
        elif has_tried_smsc_already:
            anomaly = "Đã kiểm tra TTNT đúng / reset SMO nhưng vẫn không gửi được: Nghi vấn lỗi cài đặt thiết bị (Chat RCS / iMessage) hoặc lỗi SIM"
        elif any(k in low for k in ["spam", "tin nhắn rác", "quấy rối"]):
            anomaly = "Phản ánh bị quấy rối / tin nhắn rác"
        elif "chỉ gửi được nội mạng" in low or ("nội mạng gửi được" in low and "ngoại mạng" in low):
            anomaly = "Chỉ gửi được nội mạng, không gửi được ngoại mạng: Nghi vấn chặn chiều ngoại mạng"

    # 7. Xây dựng Chuỗi tóm tắt chuẩn 7 mục Nghiệp vụ Viễn thông SMS
    act_str = f" (Đã làm: {', '.join(prior_actions)})" if prior_actions else ""
    summary_formatted = f"""1. Vấn đề phản ánh: {problem_title}
2. Mốc thời gian xảy ra: {detected_time} ({time_range_desc})
3. Số gọi/nhận lỗi: {target_fault_party}
4. Ứng dụng / Đầu số: {app_brand or 'SMS thông thường'}
5. Thiết bị & Thao tác: Máy {device_type}{act_str}
6. Cước phí khiếu nại: {claimed_amount or 'Không đề cập'}
7. Cảnh báo / Dấu hiệu: {anomaly}"""

    return {
        "problem_type": problem_type,
        "problem_title": problem_title,
        "target_fault_party": target_fault_party,
        "app_brand": app_brand,
        "device_type": device_type,
        "prior_actions": prior_actions,
        "claimed_amount": claimed_amount,
        "anomaly": anomaly,
        "has_commitment": False,
        "is_dnc": is_dnc,
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


def generate_sms_ticket_summary(arg1: str, arg2: str = "", phone: str = "", package_title: str = "", incident_time_fallback: str = "", created_time: str = "") -> str:
    """
    Hàm entry point tạo tóm tắt chuẩn 7 mục SMS cho cơ sở dữ liệu và hiển thị UI.
    Hỗ trợ linh hoạt các kiểu gọi:
      - generate_sms_ticket_summary(package_title, ticket_content, phone="")
      - generate_sms_ticket_summary(ticket_content, incident_time_fallback="", package_title=pkg)
    """
    p_title = package_title
    inc_fallback = incident_time_fallback
    c_time = created_time
    p_phone = phone

    if not p_title:
        if len(str(arg1 or "")) > 50 and len(str(arg2 or "")) <= 30 and not any(k in str(arg1).lower() for k in ["tin nhắn", "sms", "cuộc gọi", "thoại"]):
            t_content = str(arg1 or "").strip()
            p_title = "Tin nhắn (SMS)"
            if not inc_fallback:
                inc_fallback = str(arg2 or "").strip()
        else:
            p_title = str(arg1 or "Tin nhắn (SMS)").strip()
            t_content = str(arg2 or arg1 or "").strip()
    else:
        t_content = str(arg1 or "").strip()
        if not inc_fallback and arg2:
            inc_fallback = str(arg2).strip()

    res = interpret_sms_ticket(t_content, package_title=p_title, incident_time_fallback=inc_fallback, created_time=c_time, phone=p_phone)
    return res.get("summary_formatted") or ""


def parse_custom_sms_time(time_input: str, receipt_dt: datetime = None, fallback_year: int = None) -> dict:
    """
    Bóc tách mốc thời gian do KTV hoặc AI chỉ định thành khoảng ngày CDR chuẩn xác.
    Hỗ trợ:
      - Khoảng ngày: 11/10/2026 → 15/10/2026, 11/10 - 15/10/2026, từ 11/10 đến 15/10
      - Ngày cụ thể: 15/10/2026, 15/10/2026 14:30, lúc 14:30 ngày 15/10/2026
      - Tháng: Tháng 10/2026, T10/2026, cước tháng 9/2026
      - Mốc tương đối: 24h qua, hôm nay, hôm qua, 3 ngày gần nhất, 7 ngày qua
    """
    now = datetime.now()
    pad = lambda n: str(n).zfill(2)
    fb_year = fallback_year or now.year

    if not time_input or str(time_input).strip() in ("--", "Không rõ", "Không đề cập"):
        p3 = now - timedelta(days=3)
        return {
            "from_date": p3.strftime("%Y-%m-%d 00:00:00"),
            "to_date": now.strftime("%Y-%m-%d 23:59:59"),
            "time_range_desc": "3 ngày gần nhất",
            "detected_time": "--",
            "time_str": ""
        }

    raw = str(time_input).strip()
    # Loại bỏ tiền tố "2. Mốc thời gian xảy ra:" nếu có
    raw = re.sub(r'^(?:2\.\s*)?mốc thời gian(?:\s+xảy ra)?\s*:\s*', '', raw, flags=re.IGNORECASE).strip()
    # Chuẩn hóa các dấu phân cách dải ngày
    raw_norm = raw.replace('–', '-').replace('—', '-').replace('->', '→').replace('=>', '→')

    # 1. Quét giờ (vd: 14:30, 9h15)
    time_str = ""
    t_match = re.search(r'\b([0-2]?[0-9])[:hH]([0-5][0-9])(?:\s*(?:phút|p))?\b', raw_norm)
    if t_match:
        time_str = f"{pad(int(t_match.group(1)))}:{pad(int(t_match.group(2)))}"

    low = raw_norm.lower()

    # 2. Quét từ khóa tương đối
    if any(k in low for k in ["hôm nay", "24h qua", "1 ngày qua", "trong ngày"]):
        prev = now - timedelta(days=1)
        return {
            "from_date": prev.strftime("%Y-%m-%d 00:00:00"),
            "to_date": now.strftime("%Y-%m-%d 23:59:59"),
            "time_range_desc": f"{prev.strftime('%d/%m/%Y')} → {now.strftime('%d/%m/%Y')} (24h qua)",
            "detected_time": raw,
            "time_str": time_str
        }
    if any(k in low for k in ["hôm qua"]):
        yest = now - timedelta(days=1)
        prev2 = now - timedelta(days=2)
        return {
            "from_date": prev2.strftime("%Y-%m-%d 00:00:00"),
            "to_date": now.strftime("%Y-%m-%d 23:59:59"),
            "time_range_desc": f"{yest.strftime('%d/%m/%Y')} (Hôm qua)",
            "detected_time": raw,
            "time_str": time_str
        }
    if any(k in low for k in ["3 ngày", "3 ngày gần nhất", "3 ngày qua"]):
        p3 = now - timedelta(days=3)
        return {
            "from_date": p3.strftime("%Y-%m-%d 00:00:00"),
            "to_date": now.strftime("%Y-%m-%d 23:59:59"),
            "time_range_desc": f"{p3.strftime('%d/%m/%Y')} → {now.strftime('%d/%m/%Y')} (3 ngày gần nhất)",
            "detected_time": raw,
            "time_str": time_str
        }
    if any(k in low for k in ["1 tuần", "7 ngày", "7 ngày qua", "tuần này"]):
        p7 = now - timedelta(days=7)
        return {
            "from_date": p7.strftime("%Y-%m-%d 00:00:00"),
            "to_date": now.strftime("%Y-%m-%d 23:59:59"),
            "time_range_desc": f"{p7.strftime('%d/%m/%Y')} → {now.strftime('%d/%m/%Y')} (7 ngày qua)",
            "detected_time": raw,
            "time_str": time_str
        }

    # 3. Quét dải ngày (vd: 11/10/2026 → 15/10/2026 hoặc 11/10 - 15/10/2026, 11/10/2026 to 15/10/2026)
    range_pat = re.compile(
        r'(?:từ\s+(?:ngày\s+)?)?([0-3]?[0-9])[/\-]([0-1]?[0-9])(?:[/\-](20\d{2}|\d{2}))?(?:\s+[0-2]?[0-9]:[0-5][0-9](?::[0-5][0-9])?)?'
        r'\s*(?:đến|den|to|,|\-|–|—|->|→|tới)\s*'
        r'(?:ngày\s+)?([0-3]?[0-9])[/\-]([0-1]?[0-9])(?:[/\-](20\d{2}|\d{2}))?',
        re.IGNORECASE
    )
    m_range = range_pat.search(raw)
    if m_range:
        d1, m1, y1, d2, m2, y2 = m_range.groups()
        y2_val = int(f"20{y2}") if y2 and len(y2) == 2 else (int(y2) if y2 else fb_year)
        y1_val = int(f"20{y1}") if y1 and len(y1) == 2 else (int(y1) if y1 else y2_val)
        d1_val, m1_val = int(d1), int(m1)
        d2_val, m2_val = int(d2), int(m2)
        if 1 <= d1_val <= 31 and 1 <= d2_val <= 31 and 1 <= m1_val <= 12 and 1 <= m2_val <= 12:
            from_d = f"{y1_val}-{pad(m1_val)}-{pad(d1_val)} 00:00:00"
            to_d = f"{y2_val}-{pad(m2_val)}-{pad(d2_val)} 23:59:59"
            desc = f"{pad(d1_val)}/{pad(m1_val)}/{y1_val} → {pad(d2_val)}/{pad(m2_val)}/{y2_val}"
            return {
                "from_date": from_d,
                "to_date": to_d,
                "time_range_desc": desc,
                "detected_time": desc,
                "time_str": time_str
            }

    # 4. Quét ngày đầy đủ (dd/mm/yyyy)
    m_full = re.search(r'\b([0-3]?[0-9])[/\-]([0-1]?[0-9])[/\-](20\d{2}|\d{2})\b', raw)
    if m_full:
        d_val = int(m_full.group(1))
        m_val = int(m_full.group(2))
        raw_y = m_full.group(3)
        y_val = int(f"20{raw_y}") if len(raw_y) == 2 else int(raw_y)
        if 1 <= d_val <= 31 and 1 <= m_val <= 12:
            target_dt = datetime(y_val, m_val, d_val)
            base_start = target_dt
            from_d = base_start.strftime("%Y-%m-%d 00:00:00")
            base_receipt = receipt_dt if receipt_dt else target_dt
            end_dt = base_receipt + timedelta(days=3)
            to_d = end_dt.strftime("%Y-%m-%d 23:59:59")
            desc = f"{base_start.strftime('%d/%m/%Y')} → {end_dt.strftime('%d/%m/%Y')}"
            return {
                "from_date": from_d,
                "to_date": to_d,
                "time_range_desc": desc,
                "detected_time": desc,
                "time_str": time_str
            }

    # 5. Quét tháng (vd: tháng 10/2026, cước tháng 9)
    m_month = re.search(r'(?<![0-9/])(?:trong\s+tháng|cước\s+tháng|kỳ\s+cước|kỳ|tháng|t)\s*([0-1]?[0-9])(?:\s*[/\-]\s*(20\d{2}))?\b', raw, re.IGNORECASE) or \
              re.search(r'(?<![0-9/])([0-1]?[0-9])[/\-](20\d{2})\b', raw)
    if m_month:
        m_val = int(m_month.group(1))
        if 1 <= m_val <= 12:
            y_val = int(m_month.group(2)) if (len(m_month.groups()) >= 2 and m_month.group(2)) else fb_year
            import calendar
            _, last_day = calendar.monthrange(y_val, m_val)
            from_d = f"{y_val}-{pad(m_val)}-01 00:00:00"
            to_d = f"{y_val}-{pad(m_val)}-{pad(last_day)} 23:59:59"
            desc = f"01/{pad(m_val)}/{y_val} → {pad(last_day)}/{pad(m_val)}/{y_val}"
            return {
                "from_date": from_d,
                "to_date": to_d,
                "time_range_desc": desc,
                "detected_time": f"Tháng {pad(m_val)}/{y_val}",
                "time_str": time_str
            }

    # 6. Quét dd/mm (không năm)
    m_dm = re.search(r'(?:ngày|hôm|lúc|từ)\s*([0-3]?[0-9])[/\-]([0-1]?[0-9])\b', raw, re.IGNORECASE) or \
           re.search(r'(?<![0-9/])([0-3]?[0-9])[/\-]([0-1]?[0-9])(?![0-9/])', raw)
    if m_dm:
        d_val = int(m_dm.group(1))
        m_val = int(m_dm.group(2))
        if 1 <= d_val <= 31 and 1 <= m_val <= 12:
            y_val = fb_year
            base_date_str = f"{pad(d_val)}/{pad(m_val)}/{y_val}"
            det_time = f"{time_str} ngày {base_date_str}".strip() if time_str else base_date_str
            target_dt = datetime(y_val, m_val, d_val)
            base_start = target_dt
            from_d = base_start.strftime("%Y-%m-%d 00:00:00")
            base_receipt = receipt_dt if receipt_dt else target_dt
            end_dt = base_receipt + timedelta(days=3)
            to_d = end_dt.strftime("%Y-%m-%d 23:59:59")
            desc = f"{base_start.strftime('%d/%m/%Y')} → {end_dt.strftime('%d/%m/%Y')}"
            return {
                "from_date": from_d,
                "to_date": to_d,
                "time_range_desc": desc,
                "detected_time": desc,
                "time_str": time_str
            }

    # 7. Fallback cuối cùng
    p3 = now - timedelta(days=3)
    return {
        "from_date": p3.strftime("%Y-%m-%d 00:00:00"),
        "to_date": now.strftime("%Y-%m-%d 23:59:59"),
        "time_range_desc": f"{p3.strftime('%d/%m/%Y')} → {now.strftime('%d/%m/%Y')} (3 ngày gần nhất)",
        "detected_time": raw,
        "time_str": time_str
    }


def update_ai_summary_incident_time(summary_text: str, new_time_str: str) -> str:
    """Cập nhật đè dòng '2. Mốc thời gian xảy ra' trong nội dung tóm tắt chuẩn 7 mục."""
    clean_time = str(new_time_str or "").strip()
    clean_time = re.sub(r'^(?:2\.\s*)?mốc thời gian(?:\s+xảy ra)?\s*:\s*', '', clean_time, flags=re.IGNORECASE).strip()
    if not clean_time:
        clean_time = "-- (3 ngày gần nhất)"

    if not summary_text or str(summary_text).strip() in ("--", "null", "None"):
        return (
            f"1. Vấn đề phản ánh: Sự cố tin nhắn SMS\n"
            f"2. Mốc thời gian xảy ra: {clean_time}\n"
            f"3. Số gọi/nhận lỗi: Tất cả các số\n"
            f"4. Ứng dụng / Đầu số: SMS thông thường\n"
            f"5. Thiết bị & Thao tác: Máy Không đề cập\n"
            f"6. Cước phí khiếu nại: Không đề cập\n"
            f"7. Cảnh báo / Dấu hiệu: Không có dấu hiệu bất thường"
        )

    lines = str(summary_text).split("\n")
    replaced = False
    new_lines = []
    for line in lines:
        if re.match(r"^(?:2\.\s*)?mốc thời gian(?:\s+xảy ra)?\s*:", line.strip(), re.IGNORECASE):
            new_lines.append(f"2. Mốc thời gian xảy ra: {clean_time}")
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        if len(new_lines) > 1:
            new_lines.insert(1, f"2. Mốc thời gian xảy ra: {clean_time}")
        else:
            new_lines.append(f"2. Mốc thời gian xảy ra: {clean_time}")

    return "\n".join(new_lines)
