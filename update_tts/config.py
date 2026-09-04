# update_tts/config.py
# Cấu hình mapping và các hằng số dùng chung cho toàn bộ app "update_tts"

# ==================================================
# MAPPING: "NHẬN ĐỊNH TÌNH TRẠNG" (cột Excel) -> "Nguyên nhân sự cố" (dropdown TTS)
# Đảo ngược từ nguyennhansuco.json (dạng: nguyên_nhân -> [danh sách status khớp])
# ==================================================
STATUS_TO_NGUYEN_NHAN = {
    "LƯU LƯỢNG YẾU": "Thông tin đầu vào chưa chính xác, trùng lặp",
    "LƯU LƯỢNG YẾU - TẬP TRUNG 1 CELL": "Thông tin đầu vào chưa chính xác, trùng lặp",
    "THUÊ BAO BỊ BÓP BĂNG THÔNG": "Thông tin đầu vào chưa chính xác, trùng lặp",
    "KHÔNG BẮT ĐƯỢC SÓNG 4G": "Thông tin đầu vào chưa chính xác, trùng lặp",
    "BẮT SÓNG 4G KÉM": "Thông tin đầu vào chưa chính xác, trùng lặp",
    "LỖI GÓI CƯỚC / THIẾT BỊ TREO": "Lỗi do gói cước",
    "HOẠT ĐỘNG BÌNH THƯỜNG": "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường",
    "THEO DÕI THÊM": "Khách hàng theo dõi thêm",
    "LỖI THIẾT BỊ / ĐANG DÙNG VPN": "Do thiết bị đầu cuối",
    "LỖI THIẾT BỊ / ĐI NHIỀU NƠI BỊ LỖI": "Do thiết bị đầu cuối",
    "CHƯA KHAI BÁO PROFILE 4G": "Lỗi Profile thuê bao",
    "SÓNG 4G CHẬP CHỜN / YẾU": "Thông tin đầu vào chưa chính xác, trùng lặp",
    "CHƯA ĐĂNG KÝ GÓI": "Lỗi do gói cước",
    "CHỈ CÓ GÓI PAYGO": "Lỗi do gói cước",
    "LỖI GÓI VD2 - THIẾU PAYGO": "Lỗi do gói cước",
    "GÓI CƯỚC ĐÃ HẾT HẠN": "Lỗi do gói cước",
    "GÓI CÒN HẠN - KHÔNG DÙNG ĐƯỢC": "Lỗi do gói cước",
    "KHÔNG CÓ LƯU LƯỢNG ĐÁNG KỂ": "Thông tin đầu vào chưa chính xác, trùng lặp",
    "HSS CHƯA CÓ 5G": "Lỗi do VNPT-VinaPhone khai báo dịch vụ cho khách hàng",
    "BỊ KHÓA GPRS": "Lỗi do VNPT-VinaPhone khai báo dịch vụ cho khách hàng",
    "THIẾU SÓNG 5G / THIẾT BỊ": "Do thiết bị đầu cuối",
    "ĐANG SỬ DỤNG VPN / 1.1.1.1": "Do thiết bị đầu cuối",
    "SÓNG 4G KÉM / CHỈ CÓ 3G": "Khách hàng theo dõi thêm",
}

# Danh sách đầy đủ các lựa chọn có trong dropdown "Nguyên nhân sự cố" trên TTS
# (dùng để đối chiếu/kiểm tra chính tả khi chọn gợi ý typeahead)
ALL_NGUYEN_NHAN_OPTIONS = [
    "Thông tin đầu vào chưa chính xác, trùng lặp",
    "Lỗi do gói cước",
    "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường",
    "Khách hàng theo dõi thêm",
    "Do thiết bị đầu cuối",
    "Lỗi Profile thuê bao",
]

# ==================================================
# CẤU HÌNH CHROME DEBUG / TTS
# ==================================================
DEBUG_PORT_URL = "http://127.0.0.1:9222"
TTS_DOMAIN_HINT = "tts.vnpt.vn"
MAX_WAIT_SECONDS = 15

# Cấu trúc cột trong file Excel do report_bot.export_diagnostics_to_excel() xuất ra (12 Cột)
# (index 0-based, khớp với thứ tự headers trong report_bot.py)
EXCEL_COL_STATUS = 0        # Cột A (0): NHẬN ĐỊNH TÌNH TRẠNG
EXCEL_COL_PHONE = 1         # Cột B (1): SỐ ĐIỆN THOẠI (LINK BTOOLS)
EXCEL_COL_PACKAGE_TITLE = 2 # Cột C (2): DỊCH VỤ BÁO LỖI
EXCEL_COL_RECEIVED_TIME = 3 # Cột D (3): NGÀY TIẾP NHẬN
EXCEL_COL_INCIDENT_TIME = 3 # Alias dự phòng
EXCEL_COL_REAL_PACKAGE = 4  # Cột E (4): GÓI CƯỚC THỰC TẾ (SAPC & BTOOLS)
EXCEL_COL_RAT = 5           # Cột F (5): HẠ TẦNG KẾT NỐI
EXCEL_COL_CEM = 6           # Cột G (6): DỮ LIỆU CEM (TOP 3 CELL)
EXCEL_COL_APP_USAGE = 7     # Cột H (7): ỨNG DỤNG SỬ DỤNG (APP USAGE)
EXCEL_COL_AI_SUMMARY = 8    # Cột I (8): NỘI DUNG PHẢN ÁNH (TÓM TẮT AI)
EXCEL_COL_COMMENT = 9       # Cột J (9): NỘI DUNG PHÂN TÍCH KỸ THUẬT
EXCEL_COL_ACTION_PLAN = 10  # Cột K (10): HƯỚNG XỬ LÝ KHUYÊN DÙNG
EXCEL_COL_TICKET_STATUS = 11# Cột L (11): TRẠNG THÁI PHIẾU (ĐÃ ĐÓNG / CHƯA ĐÓNG)
EXCEL_HEADER_ROW = 3
EXCEL_DATA_START_ROW = 4