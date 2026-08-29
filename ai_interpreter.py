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

# Khởi tạo Groq Client nếu có GROQ_API_KEY
groq_client = None
groq_api_key = os.getenv("GROQ_API_KEY", "").strip()

if groq_api_key and groq_api_key != "YOUR_GROQ_API_KEY_HERE":
    try:
        from groq import Groq  # pyright: ignore[reportMissingImports]
        groq_client = Groq(api_key=groq_api_key)
        print("🤖 [GROQ AI] Đã khởi tạo thành công Groq AI (Hạn ngạch 14,400 lượt/ngày).")
    except Exception as e:
        print(f"⚠️ Lỗi khởi tạo Groq SDK: {e}")


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

    words = text_clean.split()
    for word in words:
        if len(word) < 3: 
            continue
        best_match = process.extractOne(word, brands, scorer=fuzz.WRatio)
        if best_match:
            matched_brand, score, _ = best_match
            if score >= 75:
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
    package_match = re.search(r'gói(?:\s+(?:cước|data))?[:\s]+([A-Za-z0-9_]+)', content_lower)
    if package_match:
        package_used = package_match.group(1).strip('_').upper()
    else:
        # Fallback pattern cũ
        package_match2 = re.search(r'\b(vd\d+[a-z]*|d\d+[a-z]*|big\d+[a-z]*|yolo\d+[a-z]*|thaga\d+[a-z]*|mim\d+[a-z]*)\b', content_lower)
        if package_match2:
            package_used = package_match2.group(1).upper()
        elif title_lower and "mobile internet" not in title_lower:
            package_used = package_title

    # ----------------------------------------------------------------
    # 2. BÓC TÁCH TÌNH TRẠNG TRUY CẬP
    # Ưu tiên "không được" hoàn toàn trước, chỉ fallback về "chậm" nếu không có "không được"
    # ----------------------------------------------------------------
    access_status = "Không đề cập"
    khong_duoc = any(k in content_lower for k in [
        "không được", "không đượ", "không truy cập", "không vào được", "mất kết nối",
        "ko vao duoc", "ko duoc", "chặn", "bị chặn", "không sử dụng được",
        "không dùng được", "không sd được", "ko sd được", "không kết nối",
        "không có kết nối", "không có mạng", "không có dịch vụ", "không có internet",
        "chưa sử dụng được", "chưa truy cập được", "chưa sd được", "chưa dùng được"
    ])
    bi_cham = any(k in content_lower for k in [
        "chậm", "load chậm", "yếu", "chập chờn", "lag"
    ])

    if khong_duoc and bi_cham:
        access_status = "Không được / Load chậm"
    elif khong_duoc:
        access_status = "Không được hoàn toàn"
    elif bi_cham:
        access_status = "Chỉ bị chậm, chập chờn"

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
    device_used = "null"
    content_lower_clean = content_lower

    # Ưu tiên check trực tiếp từ khoá rõ ràng trước
    if any(k in content_lower_clean for k in ["iphone", "ipad"]):
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
        device_used = "null"
        for typo, brand in typo_map.items():
            if typo in content_lower_clean:
                device_used = brand
                break
        if device_used == "null":
            # Fallback về fuzzy match cho trường hợp gõ sai (v.....ivo, aphone...)
            device_used = detect_device_smart(ticket_content)

    # ----------------------------------------------------------------
    # 5. BÓC TÁCH KHU VỰC (giữ nguyên logic cũ - đang ổn)
    # Thêm: nhận diện "di chuyển khu vực khác cũng vậy"
    # ----------------------------------------------------------------
    area = "Chưa xác định"
    if any(k in content_lower for k in [
        "đi nhiều nơi", "di nhiều nơi", "di chuyển khu vực", "khu vực khác cũng",
        "nhiều khu vực", "kv khác"
    ]):
        area = "Đi nhiều nơi bị lỗi"
    else:
        location_match = re.search(
            r'((?:phường|xã|đường|thị trấn|quận|huyện|thành phố)\s+[^,;\n]+)',
            content_lower
        )
        if location_match:
            clean_loc = location_match.group(1).strip()
            for rác in ["khác", "thử", "số", "vina", "kh ", "không biết"]:
                if f" {rác}" in clean_loc:
                    clean_loc = clean_loc.split(f" {rác}")[0].strip()
            area = f"Tại 1 khu vực ({clean_loc.title()})"
        else:
            # Tìm dạng "Địa chỉ: Trà Cổ, Trảng Bom, Đồng Nai"
            addr_match = re.search(r'địa chỉ[^:]*:\s*([^\n]+)', content_lower)
            if addr_match:
                area = f"Tại 1 khu vực ({addr_match.group(1).strip().title()})"
            elif any(k in content_lower for k in ["tại chỗ", "ở nhà", "trong phòng"]):
                area = "Tại 1 khu vực (chưa đi KV khác thử)"
            else:
                area_match = re.search(r'(?:tại|ở|khu vực)\s+([^,;\n]+)', content_lower)
                if area_match:
                    short_area = " ".join(area_match.group(1).strip().split()[:4])
                    area = f"Tại 1 khu vực ({short_area.title()})"
                else:
                    area = "Tại 1 khu vực (chưa đi KV khác thử)"

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


def analyze_ticket_with_groq_ai(package_title, ticket_content):
    """Gửi yêu cầu tới Groq AI (model Llama 3.3 70B) để tóm tắt thông minh 6 mục"""
    if not groq_client:
        return None

    prompt = f"""Bạn là trợ lý AI phân tích sự cố mạng viễn thông Vinaphone/VNPT.
Nhiệm vụ: Phân tích nội dung phản ánh khách hàng và trích xuất đúng 6 mục theo định dạng chính xác sau (mỗi mục 1 dòng):

1. Gói cước sử dụng: [Tên gói cước hoặc "Không đề cập"]
2. Tình trạng truy cập: [Ví dụ: "Không được hoàn toàn", "Truy cập chậm, chập chờn", "Không đề cập", "Không được", "Rất chậm"]
3. Tình trạng dung lượng: [Ví dụ: "Đã hết dung lượng", "Còn XX GB", "Không đề cập"]
4. Thiết bị sử dụng: [Tên dòng máy/hệ điều hành hoặc "null"]
5. Khu vực xảy ra lỗi: [Ví dụ: "Tại 1 khu vực (Phường X...)", "Đi nhiều nơi bị lỗi", "Tại 1 khu vực (chưa đi KV khác thử)"]
6. Tóm tắt thông tin khác: [Thông tin hành động KH đã thử như đổi SIM, bật data, reset máy... hoặc "Không có thông tin hành động phụ."]

Nội dung phản ánh từ phiếu:
- Tiêu đề gói cước: {package_title}
- Chi tiết phản ánh: {ticket_content}

LƯU Ý: Chỉ trả về đúng 6 dòng theo định dạng trên, không thêm bất kỳ lời chào hay giải thích nào."""

    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    try:
        completion = groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Bạn là trợ lý AI chuyên môn viễn thông, trả lời ngắn gọn, chuẩn xác theo đúng cấu trúc 6 dòng được yêu cầu."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=3000  # Qwen cần ~2000 token cho <think>, còn 500 cho 6 dòng output; tổng ~3000 TPM
        )
        ai_reply = completion.choices[0].message.content.strip()
        if "<think>" in ai_reply and "</think>" in ai_reply:
            ai_reply = ai_reply.split("</think>")[-1].strip()
            
        if ai_reply and "1. Gói cước" in ai_reply:
            return ai_reply
    except Exception as e:
        print(f"⚠️ Groq AI API bận/lỗi ({e}). Tự động lùi về chế độ Offline...")
        
    return None


def analyze_ticket_with_ai(json_file_path):
    """Hàm phân tích tổng hợp: Ưu tiên Groq AI -> Lùi về Offline nếu không có Key/Lỗi"""
    if not os.path.exists(json_file_path):
        return "null"

    try:
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return "null"

    package_title = data.get("package_title", "Không rõ")
    ticket_content = data.get("ticket_content", "").strip()
    phone = data.get("phone", "").strip()

    # =========================
    # CACHE CHECK
    # =========================

    cached_summary = get_cached_summary(
        phone,
        package_title,
        ticket_content
    )

    if cached_summary:
        print(f"CACHE HIT | {phone}")
        return cached_summary

    print(f"CACHE MISS | {phone}")

    # =========================
    # GROQ AI
    # =========================

    if groq_client and ticket_content:

        groq_result = analyze_ticket_with_groq_ai(
            package_title,
            ticket_content
        )

        if groq_result:

            save_summary(
                phone,
                package_title,
                ticket_content,
                groq_result
            )

            return groq_result

    # =========================
    # OFFLINE FALLBACK
    # =========================

    offline_result = analyze_ticket_offline(
        package_title,
        ticket_content
    )

    save_summary(
        phone,
        package_title,
        ticket_content,
        offline_result
    )

    return offline_result


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    test_text = "Khách hàng phản ánh máy v.......ivo đi nhiều nơi ko vao duoc mang dù đăng ký gói aphone"
    print(detect_device_smart("máy aphone"))
    print(analyze_ticket_offline("Mobile Internet 4G", test_text))