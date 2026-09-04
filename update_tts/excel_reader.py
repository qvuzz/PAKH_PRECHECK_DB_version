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
    "gói còn hạn - không dùng được",    # SAPC còn gói nhưng mất data hoàn toàn
    "sóng 4g kém / chỉ có 3g",          # 1: KH phản ánh sóng 4G kém / chỉ 3G
    "bị khóa gprs",                     # 3: NAM = 1
    "hss chưa có 5g",                   # 4: Profile HSS chưa mở 5G
    "sóng 4g chập chờn / yếu",          # 7: SÓNG 4G CHẬP CHỜN / YẾU (KC_05)
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


def is_level_1_auto_close_candidate(record):
    """
    Cho phép tự động cập nhật + đóng phiếu với:
    - HOẠT ĐỘNG BÌNH THƯỜNG: cần thêm điều kiện access_status (đối chiếu phản ánh khách hàng)
    - KHÔNG BẮT ĐƯỢC SÓNG 4G / CHƯA KHAI BÁO PROFILE 4G / BẮT SÓNG 4G KÉM /
      THUÊ BAO BỊ BÓP BĂNG THÔNG: đã được xác nhận qua số liệu kỹ thuật, không cần thêm điều kiện.
    - LƯU LƯỢNG YẾU: chỉ tự đóng nếu (a) access_status (mục 2) KHÁC "Không đề cập", VÀ
      (b) lỗi khoanh vùng được TẠI 1 KHU VỰC cụ thể (mục 5 tóm tắt AI).
    """
    status = normalize_text(record["status"])

    if status == LEVEL_1_STATUS:
        access_status = normalize_text(record["access_status"])
        return access_status in LEVEL_1_ACCESS_STATUSES

    if status == LEVEL_LUU_LUONG_YEU_STATUS:
        access_status = normalize_text(record.get("access_status"))
        if access_status == "không đề cập":
            return False
        error_area = normalize_text(record.get("error_area"))
        return error_area.startswith(ERROR_AREA_LOCALIZED_PREFIX)

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