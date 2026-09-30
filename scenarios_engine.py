THROTTLED_SERVICE_CODES = {
    "10002": "64/64",
    "10003": "128/64",
    "10005": "512/256",
    "10010": "1024/1024",
    "10011": "2048/2048",
    "10012": "3072/3072",
    "10013": "2048/1024",
    "10014": "128/128",
}

def is_throttled_service_code(code):
    """
    Kiểm tra mã dịch vụ hạ/bóp băng thông BTools:
    Bao gồm các mã chính thức từ VNPT:
    - 10002: bóp băng thông 64/64
    - 10003: bóp băng thông 128/64
    - 10005: bóp băng thông 512/256
    - 10010: bóp băng thông 1024/1024
    - 10011: bóp băng thông 2048/2048
    - 10012: bóp băng thông 3072/3072
    - 10013: bóp băng thông 2048/1024
    - 10014: bóp băng thông 128/128
    Hoặc các mã code thuộc dải 100xx (độ dài 5 số bắt đầu bằng 100).
    """
    if not code:
        return False
    s = str(code).strip().lstrip("0")
    if s in THROTTLED_SERVICE_CODES:
        return True
    return len(s) == 5 and s.startswith("100") and s.isdigit()


def get_throttled_speed_desc(code):
    """Lấy chi tiết thông số tốc độ bóp băng thông (ví dụ: 3072/3072)."""
    if not code:
        return ""
    s = str(code).strip().lstrip("0")
    return THROTTLED_SERVICE_CODES.get(s, "")


def match_diagnostic_scenarios(rat_set, service_set, rat_codes, downlink_values, total_sessions, scenarios, service_set_3days=None, rat_set_3days=None, has_4g_profile=None):
    """
    Module chuyên trách đối chiếu kịch bản lỗi theo thứ tự ưu tiên tuyệt đối.
    Trả về: (scenario_id_khớp_lệnh, alert_type) hoặc (None, None)

    service_set_3days: tập SERVICE_ID_CODE của N ngày gần nhất (dùng riêng cho KC_04).
                       Nếu không truyền, fallback về service_set (1 ngày) như cũ.
    rat_set_3days: tập RAT_TYPE_CODE của N ngày gần nhất (dùng riêng cho KC_01).
                   Nếu không truyền, fallback về rat_set (1 ngày) như cũ.
    has_4g_profile: True = đã khai báo 4G (HSS Profile khác rỗng), False = chưa khai báo
                    (chỉ bắt được 3G), None = không có dữ liệu HSS Profile để xác định.
                    Dùng để tách KC_01 (không bắt 4G) thành 2 nhánh nguyên nhân khác nhau.
    """
    # Fallback nếu không có dữ liệu nhiều ngày
    _service_set_Nday = service_set_3days if service_set_3days is not None else service_set
    _rat_set_Nday = rat_set_3days if rat_set_3days is not None else rat_set

    # =========================================================================
    # 🔥 GIAI ĐOẠN 1: KIỂM TRA LỖI HỆ THỐNG CỐ ĐỊNH TRÊN NGÀY GẦN NHẤT
    # =========================================================================

    # --- Kịch bản 3: Thuê bao bị bóp băng thông ---
    # BTools các code 100xx (ví dụ: 10003, 10002, 0000010003, 0000010002...)
    if any(is_throttled_service_code(c) for c in service_set) or (_service_set_Nday and any(is_throttled_service_code(c) for c in _service_set_Nday)):
        return "KC_03_THROTTLED", "SYSTEM"

    # --- Kịch bản 4: Chỉ có dịch vụ hệ thống (Treo gói / Thiết bị treo) ---
    # Kiểm tra trên N ngày gần nhất: chỉ xuất hiện các mã dịch vụ quản lý hệ thống (300, 302, 330, 2042)
    # xuyên suốt, không có mã dịch vụ data thương mại nào khác phát sinh
    SYSTEM_SERVICE_CODES = {"300", "302", "330", "2042"}
    norm_service_set_Nday = set(str(c).strip().lstrip("0") for c in _service_set_Nday) if _service_set_Nday else set()
    if norm_service_set_Nday and norm_service_set_Nday.issubset(SYSTEM_SERVICE_CODES):
        return "KC_04_PACKAGE_OR_DEVICE_HANG", "SYSTEM"

    # --- Kịch bản 1 / 7: Không bắt được sóng 4G ---
    # Xét trên N ngày gần nhất: phải KHÔNG bắt được 4G XUYÊN SUỐT cả N ngày mới đủ
    # tin cậy kết luận lỗi hạ tầng thật, tránh kết luận sai do 1 ngày sóng yếu tạm thời.
    if _rat_set_Nday and not ("6" in _rat_set_Nday or "7" in _rat_set_Nday) and _rat_set_Nday.issubset({"0", "1", "2"}):
        if has_4g_profile is False:
            # Đối chiếu HSS Profile: CHƯA khai báo 4G -> không phải lỗi thiết bị, mà do
            # chưa đủ điều kiện kỹ thuật (IT chưa cấu hình), tách riêng kịch bản.
            return "KC_07_NO_4G_PROFILE", "SYSTEM"
        # has_4g_profile là True hoặc None (chưa có dữ liệu HSS Profile để xác định)
        # -> giữ nguyên kết luận KC_01 như trước (an toàn, không đoán khi thiếu dữ liệu)
        return "KC_01_NO_4G", "SYSTEM"

    # =========================================================================
    # 🔍 GIAI ĐOẠN 2: KIỂM TRA LỖI SUY HAO / MẠNG CHẬP CHỜN TRÊN NGÀY GẦN NHẤT
    # =========================================================================

    # --- Kịch bản 2 & 5 (Đã gộp): Bắt sóng 4G kém / chập chờn (Tần suất rớt về 2G/3G chiếm đa số) ---
    count_1_2 = rat_codes.count("1") + rat_codes.count("2")
    count_6 = rat_codes.count("6")
    is_weak_4g = False
    if "6" in rat_set and count_1_2 > count_6 and count_6 > 0:
        is_weak_4g = True
    elif total_sessions >= 3 and (count_1_2 / total_sessions) >= 0.70:
        is_weak_4g = True

    if is_weak_4g:
        return "KC_02_WEAK_4G", "SIGNAL"

    # --- Kịch bản 6 CẢI TIẾN: Nghi vấn dùng VPN (Chặn khoảng 5MB - 11MB) ---
    # BTools ghi nhận giá trị Bytes (10MB = 10,485,760 Bytes), mở rộng trần lên 11.5MB (11,500,000 Bytes)
    if len(downlink_values) >= 2 and ("1" in rat_set or "6" in rat_set):
        all_in_vpn_range = all(4500000 <= v <= 11500000 for v in downlink_values if v > 0)
        if all_in_vpn_range:
            valid_v = [v for v in downlink_values if v > 0]
            if valid_v and (max(valid_v) - min(valid_v)) <= 2500000:
                return "KC_06_VPN_OR_DEVICE_ISSUE", "BEHAVIOR"

    return None, None