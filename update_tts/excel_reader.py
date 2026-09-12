# update_tts/excel_reader.py
# Đọc file Excel kết quả (do report_bot.export_diagnostics_to_excel() xuất ra)

import openpyxl
import re
from . import config


LEVEL_1_STATUS = "hoạt động bình thường"
LEVEL_1_ACCESS_STATUSES = {
    "không được",
    "không được hoàn toàn",
}

# Các trạng thái đã được scenarios_engine và phân tích số liệu kỹ thuật xác nhận
# (KC_01/KC_02/KC_03/KC_07, CEM dominant cell, Gói cước SAPC) -> Tự động cập nhật + đóng phiếu.
AUTO_CLOSE_STATUSES_NO_ACCESS_CHECK = {
    "không bắt được sóng 4g",           # KC_01_NO_4G
    "chưa khai báo profile 4g",         # KC_07_NO_4G_PROFILE
    "profile lạ",                       # HSS Profile từ 3 chữ số trở lên
    "bắt sóng 4g kém",                  # KC_02_WEAK_4G
    "thuê bao bị bóp băng thông",       # KC_03_THROTTLED
    "lỗi gói cước / thiết bị treo",     # KC_04
    "lỗi thiết bị / đi nhiều nơi bị lỗi",# Khách báo đi nhiều nơi và CEM phân tán -> Do thiết bị
    "lỗi thiết bị / đang dùng vpn",     # Phát hiện dùng VPN / 1.1.1.1 / Cloudflare
    "đang sử dụng vpn / 1.1.1.1",       # 6: Phát hiện app VPN / 1.1.1.1
    "chưa đăng ký gói",                 # KC chưa có gói
    "chỉ có gói paygo",                 # Thuê bao chỉ có gói PAYGO
    "lỗi gói vd2 - thiếu paygo",        # Dùng VD2 nhưng không có gói PAYGO
    "lưu lượng yếu - tập trung 1 cell", # CEM Cell > 50%
    "gói cước đã hết hạn",              # SAPC toàn bộ gói hết hạn
    "gói còn hạn - không dùng được",    # Case 1 & Case 2A: Từ khi đăng ký gói không phát sinh data
    "lỗi thiết bị / sim treo data",     # Case 2B: Trước có data, 5 ngày gần đây mất data dù bắt 4G
    "sóng 4g kém / chỉ có 3g",          # 1: KH phản ánh sóng 4G kém / chỉ 3G
    "bị khóa gprs",                     # 3: NAM = 1
    "hss chưa có 5g",                   # 4: Profile HSS chưa mở 5G
    "sóng 4g chập chờn / yếu",          # 7: SÓNG 4G CHẬP CHỜN / YẾU (KC_05)
    "off thiết bị nhiều ngày",           # Sub State = MS PURGED
    "tắt thiết bị nhiều ngày",          # Sub State = MS PURGED
    "theo dõi thêm",                    # Row 2: THEO DÕI THÊM
    "không có dữ liệu",                 # Row 4: KHÔNG CÓ DỮ LIỆU
    "không có lưu lượng đáng kể",        # Row 8: KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ
    "lỗi do gói cước",                  # Báo lỗi do gói cước đóng luôn (Case 1 sai service id / data < 1MB)
    "lỗi gói cước - sai service id",    # Case 1: AI ghi nhận gói nhưng BTools không thấy Service ID
    "lỗi gói home / nghẽn băng thông",  # Case 2: Gói HOME không có mã data và không có phiên > 1MB
    "nghi ngờ lỗi gói cước",            # Đóng tự động chuyển KTV/Tính cước
}

LEVEL_LUU_LUONG_YEU_STATUS = "lưu lượng yếu"
# Tiền tố nhận diện "lỗi khoanh vùng tại 1 khu vực cụ thể" - giá trị thật luôn kèm chi tiết
# trong ngoặc (vd "Tại 1 khu vực (Phường X...)"), nên so khớp theo PREFIX, không so tuyệt đối.
ERROR_AREA_LOCALIZED_PREFIX = "tại 1 khu vực"


def normalize_text(value):
    return " ".join(str(value or "").casefold().split())


def get_access_status(ai_summary):
    """
    Lấy giá trị ở dòng:
    '2. Tình trạng truy cập: ...'
    trong cột TÓM TẮT AI.
    """
    match = re.search(
        r"(?im)^\s*2\.\s*tình trạng truy cập\s*:\s*(.+?)\s*$",
        str(ai_summary or ""),
    )
    return match.group(1).strip() if match else ""


def get_error_area(ai_summary):
    """
    Lấy giá trị ở dòng:
    '5. Khu vực xảy ra lỗi: ...'
    trong cột TÓM TẮT AI.
    """
    match = re.search(
        r"(?im)^\s*5\.\s*khu vực xảy ra lỗi\s*:\s*(.+?)\s*$",
        str(ai_summary or ""),
    )
    return match.group(1).strip() if match else ""


def get_nguyen_nhan_and_action(record):
    """
    Xác định đúng nguyên nhân sự cố TTS và hướng xử lý dựa trên trạng thái và kết quả phân tích.
    Trả về tuple: (nguyen_nhan_tts, action_plan_override)
    """
    status = normalize_text(record.get("status", ""))
    ai_summary = record.get("ai_summary", "") or record.get("ticket_content", "") or ""
    access_status = normalize_text(record.get("access_status") or get_access_status(ai_summary))
    error_area = normalize_text(record.get("error_area") or get_error_area(ai_summary))
    current_action = record.get("action_plan", "")

    # Row 6: HOẠT ĐỘNG BÌNH THƯỜNG
    if status == LEVEL_1_STATUS:
        if access_status in LEVEL_1_ACCESS_STATUSES:
            return "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường", current_action
        else:
            return "Khách hàng theo dõi thêm", "Có thể Khách hàng đang di chuyển vào khu vực sóng kém, hoặc nghẽn mạng tạm thời. Nhờ KH theo dõi thêm giúp."

    # Row 7: LƯU LƯỢNG YẾU
    if status == LEVEL_LUU_LUONG_YEU_STATUS:
        if access_status != "không đề cập" and error_area.startswith(ERROR_AREA_LOCALIZED_PREFIX):
            return "Thông tin đầu vào chưa chính xác, trùng lặp", current_action
        else:
            return "Khách hàng theo dõi thêm", "Có thể Khách hàng đang di chuyển vào khu vực sóng kém, hoặc nghẽn mạng tạm thời. Nhờ KH theo dõi thêm giúp."

    # Row 2: THEO DÕI THÊM
    if status == "theo dõi thêm":
        return "Khách hàng theo dõi thêm", (current_action or "Có thể Khách hàng đang di chuyển vào khu vực sóng kém, hoặc nghẽn mạng tạm thời. Nhờ KH theo dõi thêm giúp.")

    # Row 4: KHÔNG CÓ DỮ LIỆU
    if status == "không có dữ liệu":
        return "Do thiết bị đầu cuối", (current_action or "Nghi ngờ do thiết bị của khách hàng bị treo data. Nhờ khách hàng thử tắt/bật thiết bị và data, đổi sim sang máy khác và kiểm tra SPEEDTEST giúp.")

    # Row 8: KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ
    if status == "không có lưu lượng đáng kể":
        return "Do thiết bị đầu cuối", (current_action or "Nghi ngờ do thiết bị của khách hàng bị treo data. Nhờ khách hàng thử tắt/bật thiết bị và data, speedtest lại giúp.")

    # Các trạng thái khác tra cứu từ STATUS_TO_NGUYEN_NHAN
    for k, v in config.STATUS_TO_NGUYEN_NHAN.items():
        if normalize_text(k) == status:
            return v, current_action

    return "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường", current_action


def is_level_1_auto_close_candidate(record):
    """
    Kiểm tra xem phiếu có đủ điều kiện tự động đóng hay không.
    Tất cả các trường hợp đã được định nghĩa trong bảng cấu hình đóng đều trả về True.
    """
    status = normalize_text(record.get("status", ""))
    ai_sum = str(record.get("ai_summary", "")).lower()

    # Phản ánh lỗi ứng dụng cụ thể -> Dành cho KTV review, không tự động đóng
    if "lỗi ứng dụng" in status or "lỗi ứng dụng cụ thể" in ai_sum:
        return False

    if status == LEVEL_1_STATUS:
        return True

    if status == LEVEL_LUU_LUONG_YEU_STATUS:
        return True

    return status in AUTO_CLOSE_STATUSES_NO_ACCESS_CHECK


def read_excel_results(excel_path):
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active

    records = []
    for row in ws.iter_rows(min_row=config.EXCEL_DATA_START_ROW, values_only=False):
        status_cell = row[config.EXCEL_COL_STATUS]
        phone_cell = row[config.EXCEL_COL_PHONE]
        comment_cell = row[config.EXCEL_COL_COMMENT]
        action_cell = row[config.EXCEL_COL_ACTION_PLAN]
        ai_summary_cell = row[config.EXCEL_COL_AI_SUMMARY]

        if not phone_cell.value:
            continue

        ai_summary = str(ai_summary_cell.value or "").strip()
        records.append({
            "status": str(status_cell.value or "").strip(),
            "phone": str(phone_cell.value or "").strip(),
            "comment": str(comment_cell.value or "").strip(),
            "action_plan": str(action_cell.value or "").strip(),
            "ai_summary": ai_summary,
            "access_status": get_access_status(ai_summary),
            "error_area": get_error_area(ai_summary),
        })

    try:
        print(f"📊 Đã đọc {len(records)} dòng dữ liệu từ file {excel_path}")
    except Exception:
        pass
    return records


def build_noi_dung_text(record):
    return f"{record['comment']}\n\nHướng xử lý: {record['action_plan']}"