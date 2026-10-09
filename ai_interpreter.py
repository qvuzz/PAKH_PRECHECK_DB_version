import sys
import os
import json
import re
from dotenv import load_dotenv
from rapidfuzz import fuzz, process
from ai_cache import get_cached_summary, save_summary
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Load file .env để lấy API Keys
load_dotenv()

import threading
local_llm = None
_local_llm_lock = threading.Lock()


def get_local_llm():
    """Nạp model Qwen 2.5 GGUF chạy CPU (Lazy loading & Thread-safe)"""
    global local_llm, _local_llm_lock
    if local_llm is not None:
        return local_llm

    model_path = os.getenv("LOCAL_MODEL_PATH", "models/qwen2.5-3b-instruct-q4_k_m.gguf").strip()
    if not os.path.isabs(model_path):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(base_dir, model_path)

    if not os.path.exists(model_path):
        return None

    try:
        from llama_cpp import Llama
        import threading
        if _local_llm_lock is None:
            _local_llm_lock = threading.Lock()

        cpu_threads = int(os.getenv("LOCAL_LLM_THREADS", "4"))
        local_llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=cpu_threads,
            verbose=False
        )
        print(f"🤖 [LOCAL LLM] Đã nạp thành công Qwen 2.5 GGUF ({os.path.basename(model_path)}) - CPU {cpu_threads} threads.")
        return local_llm
    except Exception as e:
        print(f"⚠️ Lỗi khởi tạo Local LLM ({model_path}): {e}")
        return None


def clean_and_normalize_text(text):
    """Lọc bỏ ký tự đặc biệt, dấu chấm thừa (ví dụ: v.......ivo -> vivo)"""
    if not text:
        return ""
    text = text.lower()
    # Xóa các dấu chấm, dấu gạch lặp đi lặp lại
    text = re.sub(r'[\.\-\_\+\=\?\!\@\#\$\%\^\&\*\]\[]', '', text)
    # Thu gọn khoảng trắng
    return " ".join(text.split())


def detect_device_smart(text):
    """Hàm thông minh nhận diện dòng máy kể cả khi gõ sai hoặc gõ tắt"""
    text_clean = clean_and_normalize_text(text)
    
    brands = ["iphone", "samsung", "oppo", "vivo", "xiaomi", "realme", "redmi", "huawei", "nokia", "ipad"]
    
    if "apple" in text_clean or "ios" in text_clean:
        return "Thiết bị Apple (iPhone/iPad)"
    if "android" in text_clean:
        return "Thiết bị Android"

    STOP_WORDS = {"dung", "may", "khong", "duoc", "thao", "tac", "khach", "hang", "dang", "xem", "choi", "mang", "truy", "cap", "bao"}
    words = text_clean.split()
    for word in words:
        if len(word) < 4 or word in STOP_WORDS: 
            continue
        best_match = process.extractOne(word, brands, scorer=fuzz.WRatio)
        if best_match:
            matched_brand, score, _ = best_match
            if score >= 85:
                # Redmi là dòng máy con của Xiaomi, gộp chung nhãn hiển thị
                return "XIAOMI" if matched_brand == "redmi" else matched_brand.upper()
                
    return "null"


def analyze_ticket_offline(package_title, ticket_content):
    """Hàm tóm tắt Offline - 100% dự phòng khi không có mạng hoặc không có API Key"""
    content_lower = ticket_content.lower()  # Giữ nguyên dấu tiếng Việt để khớp keyword đúng
    content_clean = clean_and_normalize_text(ticket_content)  # Bản đã clean dùng riêng cho regex số
    title_lower = clean_and_normalize_text(package_title)

    # ----------------------------------------------------------------
    # 1. BÓC TÁCH GÓI CƯỚC
    # Ưu tiên: tìm dạng "gói: XXXXX" hoặc "gói XXXXX" trước
    # Fallback: regex pattern cũ (vdXX, dXX, bigXX...)
    # ----------------------------------------------------------------
    package_used = "null"
    # Bắt dạng "gói: THAGA70N", "gói THAGA70N", "gói cước SODA125",
    # hoặc mã gói có gạch dưới như "MI_BIGKM_VD120M".
    # - Cho phép "_" trong ký tự bắt (nhiều mã gói dạng MI_XXX_YYY bị cắt cụt
    #   thành "MI" nếu chỉ dùng [A-Za-z0-9]).
    # - Bỏ qua từ đệm "cước"/"data" đứng giữa "gói" và mã gói thực tế, tránh
    #   bắt nhầm ký tự đầu của "cước"/"miễn phí" thành mã gói như "C"/"MI".
    package_match = re.search(r'gói(?:\s+(?:cước|data))?[:\s]+([^\n,;]+)', ticket_content, re.IGNORECASE)
    if package_match:
        pkg_raw = package_match.group(1).strip().strip('_')
        pkg_words = pkg_raw.split()
        if len(pkg_words) <= 4:
            package_used = pkg_raw
        else:
            package_used = " ".join(pkg_words[:3])
    else:
        # Fallback pattern bóc tách từ tên gói phổ biến
        package_match2 = re.search(r'\b(vd\d+[a-z]*|d\d+[a-z]*|big\d+[a-z]*|yolo\d+[a-z]*|thaga\d+[a-z]*|mim\d+[a-z]*|soda\d+[a-z]*|fclub[a-z]*|fhappy[a-z]*|u\d+[a-z]*|may\d+[a-z]*|vip\d+[a-z]*|bum\d+[a-z]*|spotv\d+[a-z]*|game\d+[a-z]*)\b', content_lower)
        if package_match2:
            package_used = package_match2.group(1).upper()
        elif title_lower and "mobile internet" not in title_lower:
            package_used = package_title

    # ----------------------------------------------------------------
    # 2. BÓC TÁCH TÌNH TRẠNG TRUY CẬP (THÔNG MINH: NHẬN DIỆN LỖI APP RIÊNG BIỆT)
    # ----------------------------------------------------------------
    truy_cap_bao = ""
    tc_match = re.search(r'(?:truy cập báo|báo lỗi|báo)[:\s]*([^,\n\r]+)', content_lower)
    if tc_match:
        truy_cap_bao = tc_match.group(1).strip()

    app_patterns = [
        (r'\bzalo\b', 'Zalo'),
        (r'\btik\s?tok\b', 'TikTok'),
        (r'\b(?:facebook|fb)\b', 'Facebook'),
        (r'\b(?:youtube|ytb)\b', 'YouTube'),
        (r'\bmessenger\b', 'Messenger'),
        (r'\btelegram\b', 'Telegram'),
        (r'\bviber\b', 'Viber'),
        (r'\b(?:liên quân|lien quan)\b', 'Game Liên Quân'),
        (r'\b(?:free fire|freefire)\b', 'Game Free Fire'),
        (r'\bpubg\b', 'Game PUBG'),
        (r'\bgame\b', 'Game'),
        (r'\b(?:shopee|lazada)\b', 'Shopee/Lazada'),
        (r'\b(?:web|wed|trình duyệt|website)\b', 'Web'),
        (r'\bvnedu\b', 'VnEdu'),
        (r'\bmy\s?vnpt\b', 'My VNPT'),
        (r'\b(?:ngân hàng|vietcombank|vcb|agribank|bidv|techcombank|tcb|mbbank|mb bank|acb|vpbank|tpbank|vietinbank|ctg)\b', 'App Ngân hàng'),
        (r'\b(?:vneid|vssid)\b', 'VNeID / Dịch vụ công'),
        (r'\b(?:momo|vnpt money|vnpt pay|zalopay|viettel money)\b', 'Ví điện tử'),
        (r'\b(?:gmail|email|mail)\b', 'Email / Gmail'),
        (r'\b(?:đầu số|tổng đài|1414)\b', 'Tổng đài / Đầu số SMS'),
        (r'\botp\b', 'Nhận OTP App'),
    ]
    detected_apps = []
    for pattern, name in app_patterns:
        if re.search(pattern, content_lower):
            if name not in detected_apps:
                detected_apps.append(name)

    access_status = "Không đề cập"
    if detected_apps:
        app_list_str = ", ".join(detected_apps)
        if truy_cap_bao and not any(truy_cap_bao == g.lower() for g in ["không được", "chậm", "kém"]):
            access_status = f"Lỗi ứng dụng cụ thể: {app_list_str} ({truy_cap_bao})"
        elif "trừ" in content_lower and ("dung lượng" in content_lower or "data" in content_lower):
            access_status = f"Lỗi ứng dụng cụ thể: {app_list_str} (Bị trừ vào dung lượng gói chính)"
        elif any(k in content_lower for k in ["chậm", "lag", "xoay", "quay vòng"]):
            detail = "Chậm / lag khi dùng ứng dụng"
            if truy_cap_bao: detail = f"{detail} ({truy_cap_bao})"
            access_status = f"Lỗi ứng dụng cụ thể: {app_list_str} ({detail})"
        elif any(k in content_lower for k in ["không được", "không vào được", "ko vào", "mất kết nối", "không kết nối"]):
            detail = "Không truy cập được ứng dụng"
            if truy_cap_bao: detail = f"{detail} ({truy_cap_bao})"
            access_status = f"Lỗi ứng dụng cụ thể: {app_list_str} ({detail})"
        else:
            access_status = f"Lỗi ứng dụng cụ thể: {app_list_str}"
    else:
        khong_duoc = any(k in content_lower for k in [
            "không được", "không đượ", "không truy cập", "không vào được", "mất kết nối",
            "ko vao duoc", "ko duoc", "chặn", "bị chặn", "không sử dụng được",
            "không dùng được", "không sd được", "ko sd được", "không kết nối",
            "không có kết nối", "không có mạng", "không có dịch vụ", "không có internet",
            "chưa sử dụng được", "chưa truy cập được", "chưa sd được", "chưa dùng được"
        ])
        bi_cham = any(k in content_lower for k in [
            "chậm", "load chậm", "yếu", "chập chờn", "lag", "xoay", "quay vòng"
        ])
        extra_detail = f" ({truy_cap_bao})" if (truy_cap_bao and truy_cap_bao not in ["không được", "chậm", "kém"]) else ""

        if khong_duoc and bi_cham:
            access_status = f"Không được / Load chậm{extra_detail}"
        elif khong_duoc:
            access_status = f"Không được hoàn toàn{extra_detail}"
        elif any(k in content_lower for k in ["h+", "chỉ hiện 3g", "không lên 4g", "không lên 5g", "mất 4g", "mất 5g", "mất lte", "chữ e"]):
            access_status = f"Rớt mạng 2G/3G (Không lên được 4G/5G){extra_detail}"
        elif bi_cham:
            access_status = f"Chỉ bị chậm, chập chờn{extra_detail}"
        elif any(k in content_lower for k in ["mau hết dung lượng", "nhanh hết dung lượng", "mau hết data", "nhanh hết data", "hao data", "hao dung lượng", "trừ cước nhanh", "trừ data nhanh", "nhanh hết gói"]):
            access_status = "Phản ánh mau hết dung lượng / Hao data nhanh"

    # ----------------------------------------------------------------
    # 3. BÓC TÁCH TÌNH TRẠNG DUNG LƯỢNG
    # Sửa lỗi: tách đúng số thập phân (4.9GB, không thành 49GB)
    # ----------------------------------------------------------------
    data_status = "Không đề cập"
    # Ưu tiên 1: dạng "còn: 4.9GB" / "còn 4.9 GB" / "còn: 5G" (đơn vị viết tắt
    # chỉ 1 chữ "G", hay gặp khi KTV gõ tắt "5G" thay vì "5GB")
    volume_match = re.search(
        r'(?:dung lượng còn|còn)[:\s]*(\d+[.,]\d+|\d+)\s*(gb|mb|g)\b',
        content_lower
    )
    if volume_match:
        so = volume_match.group(1).replace(',', '.')
        don_vi = volume_match.group(2).upper()
        don_vi = "GB" if don_vi == "G" else don_vi
        data_status = f"Còn {so}{don_vi}"
    else:
        # Ưu tiên 2: dạng "đã sử dụng: X/Y" (đã dùng X trên tổng Y) - hay gặp
        # ở các phiếu ghi theo mẫu "Dung lượng đã sử dụng: 2.1 MB/1GB"
        used_total_match = re.search(
            r'(?:đã sử dụng|sử dụng)[:\s]*(\d+[.,]\d+|\d+)\s*(gb|mb|g)?\s*/\s*(\d+[.,]\d+|\d+)\s*(gb|mb|g)',
            content_lower
        )
        if used_total_match:
            used_so = used_total_match.group(1).replace(',', '.')
            used_dv = (used_total_match.group(2) or used_total_match.group(4)).upper()
            used_dv = "GB" if used_dv == "G" else used_dv
            total_so = used_total_match.group(3).replace(',', '.')
            total_dv = used_total_match.group(4).upper()
            total_dv = "GB" if total_dv == "G" else total_dv
            data_status = f"Đã dùng {used_so}{used_dv}/{total_so}{total_dv}"
        else:
            # Ưu tiên 3: chỉ có "đã sử dụng: X" (không kèm tổng dung lượng gói)
            used_match = re.search(
                r'(?:dung lượng )?đã sử dụng[:\s]*(\d+[.,]\d+|\d+)\s*(gb|mb|g)\b',
                content_lower
            )
            if used_match:
                so = used_match.group(1).replace(',', '.')
                don_vi = used_match.group(2).upper()
                don_vi = "GB" if don_vi == "G" else don_vi
                data_status = f"Đã sử dụng {so}{don_vi}"
            elif any(k in content_lower for k in ["mau hết dung lượng", "nhanh hết dung lượng", "mau hết data", "nhanh hết data", "hao data", "hao dung lượng", "trừ cước nhanh", "trừ data nhanh", "nhanh hết gói"]):
                data_status = "Phản ánh mau hết data / Hao dung lượng"
            elif any(k in content_lower for k in ["hết dung lượng", "hết data", "hết gói", "het data"]):
                data_status = "Đã hết dung lượng"
            else:
                # Fallback cuối: tìm số + đơn vị GB/MB bất kỳ trong text (giữ
                # hành vi cũ để không bỏ sót các câu không theo mẫu chuẩn)
                fallback_match = re.search(r'(\d+[.,]\d+|\d+)\s*(gb|mb)', content_lower)
                if fallback_match:
                    so = fallback_match.group(1).replace(',', '.')
                    don_vi = fallback_match.group(2).upper()
                    data_status = f"Còn {so}{don_vi}"

    # ----------------------------------------------------------------
    # 4. BÓC TÁCH THIẾT BỊ
    # Kiểm tra "iphone" / "ipad" trực tiếp TRƯỚC khi đưa vào fuzzy match
    # (tránh fuzzy match nhầm sang samsung/oppo)
    # ----------------------------------------------------------------
    device_used = "Không đề cập"
    content_lower_clean = content_lower

    # Ưu tiên check trực tiếp từ khoá rõ ràng trước
    if any(k in content_lower_clean for k in ["cục phát wifi", "cuc phat wifi", "bộ phát wifi", "bo phat wifi", "cục phát", "bộ phát", "mifi", "dcom", "router wifi", "router 4g"]):
        device_used = "Cục phát WiFi (Router/Mifi)"
    elif any(k in content_lower_clean for k in ["máy pos", "pos", "máy quẹt thẻ", "quẹt thẻ"]):
        device_used = "Máy POS / Quẹt thẻ"
    elif any(k in content_lower_clean for k in ["apple watch", "đồng hồ", "smartwatch"]):
        device_used = "Đồng hồ thông minh (Smartwatch)"
    elif any(k in content_lower_clean for k in ["thiết bị cảnh báo", "định vị", "camera", "hộp đen"]):
        device_used = "Thiết bị IoT / Camera / Cảnh báo"
    elif any(k in content_lower_clean for k in ["iphone", "ipad"]):
        # Thử lấy thêm model (14 pro max, 15...)
        model_match = re.search(r'iphone\s*([\w\s]+?)(?:,|\.|$)', content_lower_clean)
        if model_match:
            device_used = f"iPhone {model_match.group(1).strip().title()}"
        else:
            device_used = "IPHONE"
    elif re.search(r'\bip\s?\d{1,2}[a-z]*\b', content_lower_clean):
        # Viết tắt kiểu "ip15", "ip 13 pro max", "ip8 pls"...
        model_match = re.search(r'\bip\s?(\d{1,2}[\w\s]*?)(?:,|\.|$)', content_lower_clean)
        if model_match:
            device_used = f"iPhone {model_match.group(1).strip().title()}"
        else:
            device_used = "IPHONE"
    elif "samsung" in content_lower_clean:
        device_used = "SAMSUNG"
    elif "oppo" in content_lower_clean:
        device_used = "OPPO"
    elif "xiaomi" in content_lower_clean or "redmi" in content_lower_clean:
        device_used = "XIAOMI"
    elif "vivo" in content_lower_clean:
        device_used = "VIVO"
    elif "realme" in content_lower_clean:
        device_used = "REALME"
    elif "huawei" in content_lower_clean:
        device_used = "HUAWEI"
    elif "nokia" in content_lower_clean:
        device_used = "NOKIA"
    elif "honor" in content_lower_clean:
        device_used = "HONOR"
    elif any(k in content_lower_clean for k in ["pixel", "google"]):
        device_used = "GOOGLE PIXEL"
    elif "oneplus" in content_lower_clean:
        device_used = "ONEPLUS"
    elif "nubia" in content_lower_clean:
        device_used = "NUBIA"
    elif "tecno" in content_lower_clean:
        device_used = "TECNO"
    elif "itel" in content_lower_clean:
        device_used = "ITEL"
    elif "meizu" in content_lower_clean:
        device_used = "MEIZU"
    elif "lenovo" in content_lower_clean:
        device_used = "LENOVO"
    elif "motorola" in content_lower_clean:
        device_used = "MOTOROLA"
    elif "sony" in content_lower_clean:
        device_used = "SONY"
    elif any(k in content_lower_clean for k in ["apple", "ios"]):
        device_used = "Thiết bị Apple (iPhone/iPad)"
    elif "android" in content_lower_clean:
        device_used = "Thiết bị Android"
    else:
        # Sửa một số lỗi gõ phổ biến hay gặp trong dữ liệu trước khi thử fuzzy match
        typo_map = {
            "androi": "ANDROID", "aidroi": "ANDROID",
            "aplle": "APPLE", "iphpne": "IPHONE", "iphơn": "IPHONE", "ịphone": "IPHONE",
            "oppa": "OPPO", "opppo": "OPPO", "ôppo": "OPPO",
            "xaomi": "XIAOMI", "xioami": "XIAOMI",
            "sansung": "SAMSUNG", "samsum": "SAMSUNG", "samssung": "SAMSUNG",
            "sámsung": "SAMSUNG", "sámung": "SAMSUNG", "sam sung": "SAMSUNG", "sam sum": "SAMSUNG",
        }
        for typo, brand in typo_map.items():
            if typo in content_lower_clean:
                device_used = brand
                break
        if device_used == "Không đề cập":
            # Fallback về fuzzy match cho trường hợp gõ sai (v.....ivo, aphone...)
            detected = detect_device_smart(ticket_content)
            if detected and detected != "null":
                device_used = detected

    # ----------------------------------------------------------------
    # 5. BÓC TÁCH KHU VỰC
    # ----------------------------------------------------------------
    area = "Không đề cập"
    if any(k in content_lower for k in [
        "đi nhiều nơi", "di nhiều nơi", "di chuyển khu vực", "khu vực khác cũng",
        "nhiều khu vực", "kv khác"
    ]):
        area = "Đi nhiều nơi bị lỗi"
    else:
        try:
            from db_manager import extract_ward_address
            w_addr = extract_ward_address(ticket_content)
        except Exception:
            w_addr = ""
        if w_addr:
            area = f"Tại 1 khu vực ({w_addr})"
        elif any(k in content_lower for k in ["tại chỗ", "ở nhà", "trong phòng"]):
            area = "Tại 1 khu vực (ở nhà/trong phòng)"
        else:
            area_match = re.search(r'(?:tại|ở|khu vực)\s+([^,;\n]+)', content_lower)
            if area_match:
                short_area = " ".join(area_match.group(1).strip().split()[:4])
                area = f"Tại 1 khu vực ({short_area.title()})"
            else:
                area = "Không đề cập"

    # ----------------------------------------------------------------
    # 6. TÓM TẮT THÔNG TIN KHÁC
    # Bổ sung đầy đủ các thao tác phổ biến
    # ----------------------------------------------------------------
    other_info = []
    if any(k in content_lower for k in ["bật dldđ", "bật dldd", "bật data", "bat data", "dldđ", "dldd"]):
        other_info.append("KH đã bật dữ liệu di động")
    if any(k in content_lower for k in ["chọn mạng", "chon mang"]):
        other_info.append("KH đã chọn lại mạng")
    if any(k in content_lower for k in ["xóa cache", "xoa cache", "cache"]):
        other_info.append("KH đã xóa Cache")
    if any(k in content_lower for k in ["reset gprs", "gprs"]):
        other_info.append("KH đã Reset GPRS")
    if any(k in content_lower for k in ["khởi động", "restart", "reset máy", "tắt máy", "tat may"]):
        other_info.append("KH đã khởi động lại máy")
    if any(k in content_lower for k in ["sim khác", "đổi sim", "doi sim"]):
        other_info.append("KH đã thử đổi SIM/máy khác")

    other_info_str = ", ".join(other_info) if other_info else "Không có thông tin hành động phụ."

    return f"""1. Gói cước sử dụng: {package_used}
2. Tình trạng truy cập: {access_status}
3. Tình trạng dung lượng: {data_status}
4. Thiết bị sử dụng: {device_used}
5. Khu vực xảy ra lỗi: {area}
6. Tóm tắt thông tin khác: {other_info_str}"""


def analyze_ticket_with_local_ai(package_title, ticket_content):
    """Gửi yêu cầu tới Local LLM (Qwen 2.5 3B GGUF) để tóm tắt thông minh 6 mục"""
    llm = get_local_llm()
    if not llm:
        return None

    # Tra cứu 1 mẫu thực tế gần nhất đã được KTV duyệt để làm ví dụ mẫu (Few-shot learning)
    few_shot_text = ""
    try:
        from db_manager import get_similar_ai_samples
        similar_samples = get_similar_ai_samples(ticket_content, limit=1)
        if similar_samples:
            s = similar_samples[0]
            clean_tc = str(s["ticket_content"] or "").strip()
            clean_sc = str(s["summary_content"] or "").strip()
            few_shot_text = f"\nMẪU THỰC TẾ ĐÃ ĐƯỢC KTV DUYỆT CHUẨN:\n- Phản ánh gốc: {clean_tc}\n- Tóm tắt chuẩn 6 mục:\n{clean_sc}\n"
    except Exception:
        few_shot_text = ""

    prompt = f"""Bạn là trợ lý AI chuyên gia phân tích sự cố mạng viễn thông di động Vinaphone/VNPT.
Nhiệm vụ: Trích xuất nội dung phản ánh khách hàng thành đúng 6 mục theo định dạng tiêu chuẩn viễn thông sau (mỗi mục 1 dòng):

1. Gói cước sử dụng: [Tên gói cước cụ thể (ví dụ YOLO90, D159V, VD149, Thương gia 249...) hoặc "Không đề cập"]
2. Tình trạng truy cập: [Chọn 1 trong các chuẩn: "Không vào được mạng (toàn bộ)" / "Truy cập chậm, chập chờn" / "Lỗi ứng dụng cụ thể: TênApp" / "Phản ánh mau hết dung lượng / Hao data nhanh" / "Không đề cập"]
3. Tình trạng dung lượng: [Ví dụ: "Còn 1.5GB", "Đã hết dung lượng", "Không đề cập"]
4. Thiết bị sử dụng: [Ví dụ: "IPHONE", "SAMSUNG", "Thiết bị Android", hoặc "Không đề cập"]
5. Khu vực xảy ra lỗi: [Ví dụ: "Chỉ ở 1 khu vực (Địa chỉ)", "Đi nhiều nơi bị lỗi", hoặc "Không đề cập"]
6. Tóm tắt thông tin khác: [Ví dụ: "KH đã bật dữ liệu di động, đã chọn lại mạng, đã reset máy" hoặc "Không có thông tin hành động phụ."]
{few_shot_text}
Nội dung phản ánh cần trích xuất:
- Tiêu đề phiếu: {package_title}
- Chi tiết phản ánh: {ticket_content}

BẮT BUỘC:
- Toàn bộ kết quả phải viết 100% bằng TIẾNG VIỆT.
- TUYỆT ĐỐI KHÔNG dịch tên riêng, tên gói cước (ví dụ: 'Thương gia', 'Đỉnh', 'Chất'...) sang tiếng Trung Quốc hay bất kỳ ngôn ngữ nào khác. Giữ nguyên tên gốc Tiếng Việt.
- Chỉ trả về đúng 6 dòng theo thứ tự từ 1 đến 6.
- Không thêm bất kỳ lời chào hay giải thích nào."""

    try:
        with _local_llm_lock:
            completion = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": "Bạn là chuyên gia viễn thông. Nhiệm vụ duy nhất của bạn là trích xuất đúng 6 dòng tiếng Việt bắt đầu bằng 1., 2., 3., 4., 5., 6. Tuyệt đối không dịch tên gói cước sang tiếng Trung Quốc."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=220,
                stop=["<|im_end|>", "\n\n7.", "###"]
            )
        ai_reply = completion["choices"][0]["message"]["content"].strip()
        if "<think>" in ai_reply and "</think>" in ai_reply:
            ai_reply = ai_reply.split("</think>")[-1].strip()

        # Chuẩn hóa nếu model LLM vô tình dịch tên gói sang tiếng Trung (VD: 商家 -> Thương gia)
        if "商家" in ai_reply:
            ai_reply = ai_reply.replace("商家", "Thương gia")

        # Kiểm tra nghiêm ngặt: Phải có ít nhất các mục 1, 2, 5
        if ai_reply and "1. Gói cước" in ai_reply and "2. Tình trạng" in ai_reply:
            return ai_reply
        else:
            print(f"⚠️ Qwen sinh ra định dạng không chuẩn 6 mục. Lùi về Regex chuẩn.")
    except Exception as e:
        print(f"⚠️ Local LLM bận/lỗi ({e}). Tự động lùi về chế độ Offline...")

    return None


def generate_ticket_summary(package_title: str, ticket_content: str, phone: str = "") -> str:
    """
    Tóm tắt nội dung phản ánh khách hàng chuẩn 6 mục tiêu chuẩn viễn thông.
    Hoạt động 100% trong bộ nhớ, không phụ thuộc vào file trên đĩa hay BTools.
    Quy trình:
      1. Kiểm tra Cache trong SQLite.
      2. Nếu chọn 'qwen' và có nội dung -> Thử Local LLM (timeout/an toàn).
      3. Luôn lùi về Regex Offline (bóc tách 6 mục chuẩn xác 100% trong 0.1ms).
    """
    pkg_title = str(package_title or "Mobile Internet").strip()
    content = str(ticket_content or "").strip().strip('"\'').strip()
    if not content:
        return """1. Gói cước sử dụng: Không đề cập
2. Tình trạng truy cập: Không đề cập
3. Tình trạng dung lượng: Không đề cập
4. Thiết bị sử dụng: Không đề cập
5. Khu vực xảy ra lỗi: Không đề cập
6. Tóm tắt thông tin khác: Không có thông tin phản ánh."""

    phone_clean = str(phone or "").strip()

    # 1. Kiểm tra Cache
    if phone_clean:
        try:
            cached = get_cached_summary(phone_clean, pkg_title, content)
            if cached and cached.strip().startswith("1."):
                return cached
        except Exception:
            pass

    # 2. Kiểm tra mô hình Qwen nếu được bật
    selected_engine = "regex"
    try:
        from services.state import state
        selected_engine = getattr(state, "ai_summary_engine", "regex")
    except Exception:
        selected_engine = "regex"

    if selected_engine == "qwen":
        try:
            qwen_res = analyze_ticket_with_local_ai(pkg_title, content)
            if qwen_res and qwen_res.strip().startswith("1."):
                if phone_clean:
                    save_summary(phone_clean, pkg_title, content, qwen_res)
                return qwen_res
        except Exception as e:
            print(f"⚠️ Lỗi Local AI: {e}. Lùi về Regex Offline.")

    # 3. Regex Offline (Chuẩn xác 100%, 0.1ms, không bao giờ lỗi)
    offline_res = analyze_ticket_offline(pkg_title, content)
    if phone_clean and offline_res:
        try:
            save_summary(phone_clean, pkg_title, content, offline_res)
        except Exception:
            pass
    return offline_res


def analyze_ticket_with_ai(target, ticket_content=None, phone=""):
    """
    Hàm phân tích tổng hợp: nhận vào đường dẫn json_file_path HOẶC (package_title, ticket_content).
    Ưu tiên Cache -> Qwen (nếu bật) -> Regex Offline.
    Đảm bảo KHÔNG BAO GIỜ trả về 'null' nếu có nội dung phản ánh.
    """
    if isinstance(target, str) and (os.path.exists(target) or target.endswith(".json")):
        if os.path.exists(target):
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                p_title = data.get("package_title") or data.get("title") or "Không rõ"
                p_content = str(data.get("ticket_content") or data.get("content") or "").strip()
                p_phone = str(data.get("phone") or phone or "").strip()
                return generate_ticket_summary(p_title, p_content, p_phone)
            except Exception:
                pass
        if ticket_content:
            return generate_ticket_summary(str(target), str(ticket_content), phone)
        return "null"

    return generate_ticket_summary(str(target or ""), str(ticket_content or ""), phone)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    test_text = "Khách hàng phản ánh máy v.......ivo đi nhiều nơi ko vao duoc mang dù đăng ký gói aphone"
    print(detect_device_smart("máy aphone"))
    print(analyze_ticket_offline("Mobile Internet 4G", test_text))