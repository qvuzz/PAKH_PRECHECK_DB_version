# scenarios_engine.py

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
    if "0000010002" in service_set:
        return "KC_03_THROTTLED", "SYSTEM"

    # --- Kịch bản 4: Chỉ có dịch vụ hệ thống (Treo gói / Thiết bị treo) ---
    # Kiểm tra trên N ngày gần nhất: chỉ xuất hiện '000000300' hoặc '0000002042'
    # xuyên suốt, không có mã dịch vụ nào khác phát sinh -> chắc chắn hơn 1 ngày
    if _service_set_Nday and _service_set_Nday.issubset({"000000300", "0000002042"}):
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

    # --- Kịch bản 2: Bắt sóng 4G kém ---
    if "6" in rat_set:
        count_1_2 = rat_codes.count("1") + rat_codes.count("2")
        count_6 = rat_codes.count("6")
        if count_1_2 > count_6 and count_6 > 0:
            return "KC_02_WEAK_4G", "SIGNAL"

    # --- Kịch bản 6 CẢI TIẾN: Nghi vấn dùng VPN (Chặn khoảng 5MB - 11MB) ---
    # BTools ghi nhận giá trị Bytes (10MB = 10,485,760 Bytes), mở rộng trần lên 11.5MB (11,500,000 Bytes)
    if len(downlink_values) >= 2 and ("1" in rat_set or "6" in rat_set):
        all_in_vpn_range = all(4500000 <= v <= 11500000 for v in downlink_values if v > 0)
        if all_in_vpn_range:
            valid_v = [v for v in downlink_values if v > 0]
            if valid_v and (max(valid_v) - min(valid_v)) <= 2500000:
                return "KC_06_VPN_OR_DEVICE_ISSUE", "BEHAVIOR"

    # --- Kịch bản 5: Sóng 4G chập chờn dựa trên mật độ phiên ---
    if total_sessions >= 3:
        count_low_rat = rat_codes.count("1") + rat_codes.count("2")
        if (count_low_rat / total_sessions) >= 0.70:
            return "KC_05_LOW_DOWNLINK_BURST", "SIGNAL"

    return None, None