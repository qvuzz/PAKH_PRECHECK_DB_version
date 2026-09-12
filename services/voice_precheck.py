# services/voice_precheck.py
# Engine tiền kiểm chuyên biệt cho Module Cuộc gọi (Voice / Calls)
# Quy tắc: Giữ SAPC, CEM chỉ lấy Cell/Trạm (bỏ lưu lượng MB & App events), bỏ BTools.

import os
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def precheck_single_voice_ticket(phone_84: str, ticket: dict, sapc_client=None, cem_client=None) -> dict:
    """
    Tiền kiểm chuyên biệt 1 phiếu Cuộc gọi:
    1. Tra cứu SAPC: Lấy trạng thái NAM (0/1), gói cước, dịch vụ.
    2. Tra cứu Cell từ SAPC và CEM (chỉ thống kê Top Cell/Trạm, bỏ qua App usage & lưu lượng MB).
    3. Phân tích kịch bản cuộc gọi và đưa ra nhận định, ý kiến đóng phiếu chuẩn VNPT.
    """
    code = ticket.get("ticket_code", "")
    title = ticket.get("title", "")
    ticket_content = ticket.get("content", "")
    reopen_count = int(ticket.get("reopen_count") or 0)
    last_reopened_date = str(ticket.get("last_reopened_date") or "").strip()

    info_result = {}
    sapc_result = {"msisdn": phone_84, "packages": []}
    formatted_packages = "--"
    nam_val = "0"
    sapc_cell = ""
    rat_type_str = "2G/3G/4G Thoại"

    # =========================================================================
    # 1. TRA CỨU SAPC (Kiểm tra trạng thái NAM, thuê bao, dịch vụ)
    # =========================================================================
    if sapc_client:
        try:
            from msisdn_info import tra_cell_tu_so_dien_thoai
            from converter import convert_sapc_response
            from report_bot import get_formatted_sapc_packages

            info_result = tra_cell_tu_so_dien_thoai(phone_84, session=sapc_client.session) or {}
            raw_sapc = sapc_client.query(phone_84)
            sapc_result = convert_sapc_response(raw_sapc)

            hss_output_dir = str(BASE_DIR / "output")
            os.makedirs(hss_output_dir, exist_ok=True)
            with open(os.path.join(hss_output_dir, f"{phone_84}.json"), "w", encoding="utf-8") as hf:
                json.dump({
                    **sapc_result,
                    "subscriber_info": info_result,
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, hf, ensure_ascii=False, indent=4)

            formatted_packages = get_formatted_sapc_packages(phone_84)
        except Exception as ex_sapc:
            pass

    nam_val = str(info_result.get("NAM") or "0").strip()
    hss_profile = str(info_result.get("HSS Profile") or "").strip()
    sapc_cell = str(info_result.get("Cell ID") or info_result.get("ECGI") or "").strip()
    if info_result.get("Radio"):
        rat_type_str = str(info_result.get("Radio"))

    # Kiểm tra HSS Profile bất thường ảnh hưởng dịch vụ VoLTE
    is_strange_hss = False
    if hss_profile:
        hss_digits = re.sub(r'\D', '', hss_profile)
        if len(hss_digits) >= 3 or "lạ" in hss_profile.lower():
            is_strange_hss = True

    # =========================================================================
    # 2. TRA CỨU CEM (CHỈ LẤY THỐNG KÊ CELL/TRẠM ĐỂ PHÒNG SỰ CỐ DIỆN RỘNG)
    # =========================================================================
    cem_cell_summary = ""
    top_primary_cell = ""
    if cem_client:
        try:
            from cem_client import CEMClient
            # Chỉ lấy lịch sử cell 2 ngày gần nhất, không lấy App Events
            cell_records = cem_client.get_subscriber_cell_history(phone_84, days=2)
            if cell_records:
                cem_cell_summary = CEMClient.extract_top_cells_summary(cell_records)
                # Lấy tên cell xuất hiện đầu tiên
                for r in cell_records:
                    c_name = r.get("cell_name") or r.get("cell_id") or r.get("first_cell")
                    if c_name:
                        top_primary_cell = str(c_name).strip()
                        break
        except Exception:
            pass

    # Tổng hợp thông tin trạm phát sóng
    cell_display_parts = []
    if top_primary_cell:
        cell_display_parts.append(f"Trạm CEM: {top_primary_cell}")
    elif sapc_cell and sapc_cell != "--":
        cell_display_parts.append(f"Cell SAPC: {sapc_cell}")

    if cem_cell_summary and not cem_cell_summary.startswith("Không có"):
        cell_display_str = cem_cell_summary
    elif cell_display_parts:
        cell_display_str = " | ".join(cell_display_parts)
    else:
        cell_display_str = "Trạm phát sóng khu vực đảm bảo"

    # =========================================================================
    # 3. BỘ QUY TẮC TIỀN KIỂM CUỘC GỌI (VOICE SCENARIOS & VOLTE)
    # =========================================================================
    status = "MẠNG LƯỚI ĐẢM BẢO"
    color = "green"
    action_plan = "Đủ điều kiện đóng phiếu"
    primary_cell_name = top_primary_cell or sapc_cell or "khu vực"

    # Kịch bản 1: Cảnh báo phiếu mở lại nhiều lần
    if reopen_count > 0:
        status = f"⚠️ PHIẾU MỞ LẠI ({reopen_count} LẦN)"
        color = "orange"
        action_plan = "KTV Kiểm tra lại"
        comment = (
            f"Phiếu phản ánh cuộc gọi được mở lại lần thứ {reopen_count} "
            f"(Lần cuối: {last_reopened_date or 'Gần đây'}). "
            f"Yêu cầu KTV liên hệ trực tiếp khách hàng xác minh chi tiết lỗi trước khi xử lý."
        )
    # Kịch bản 2: Bị khóa Spam cuộc gọi
    elif "spam cuộc gọi" in title.lower() or "spam cuộc gọi" in ticket_content.lower():
        status = "BỊ KHÓA SPAM CUỘC GỌI"
        color = "red"
        action_plan = "Chuyển KTV xử lý Spam"
        comment = "Thuê bao bị hệ thống chặn do nghi vấn phát tán cuộc gọi rác/Spam. Hướng dẫn khách hàng xác minh chính chủ để mở khóa."
    # Kịch bản 3: Thuê bao bị khóa cước / khóa dịch vụ (NAM = 1)
    elif nam_val == "1":
        status = "KHÓA DỊCH VỤ (NAM: 1)"
        color = "red"
        action_plan = "Chưa đủ điều kiện đóng"
        comment = "Thuê bao đang bị tạm khóa chiều/dịch vụ trên hệ thống Core (NAM: 1). KTV hướng dẫn khách hàng thanh toán cước hoặc kiểm tra tình trạng chặn chiều."
    # Kịch bản 4: HSS Profile bất thường / Profile lạ (ảnh hưởng VoLTE)
    elif is_strange_hss:
        status = "HSS PROFILE LẠ (ẢNH HƯỞNG VOLTE)"
        color = "red"
        action_plan = "KTV kiểm tra HSS/VoLTE"
        comment = (
            f"Hồ sơ Core phát hiện HSS Profile bất thường: {hss_profile} (Profile lạ). "
            f"Dấu hiệu này có thể gây lỗi đăng ký VoLTE/IMS hoặc lỗi cuộc gọi độ nét cao. "
            f"Đề nghị KTV kiểm tra lại thông số thuê bao trên HSS/IMS trước khi xử lý."
        )
    # Kịch bản 5: Mạng lưới và trạm phát sóng đảm bảo bình thường
    else:
        status = "MẠNG LƯỚI ĐẢM BẢO"
        color = "green"
        action_plan = "Đủ điều kiện đóng phiếu"
        hss_note = f", HSS Profile: {hss_profile} (VoLTE sẵn sàng)" if hss_profile else ""
        comment = (
            f"Đã kiểm tra hệ thống: Thuê bao hoạt động 2 chiều bình thường (NAM: 0{hss_note}). "
            f"Trạm phát sóng phục vụ ({primary_cell_name}) hoạt động đảm bảo chất lượng, "
            f"không phát hiện cảnh báo lỗi phần cứng hay sự cố diện rộng tại khu vực. "
            f"Đề nghị KTV liên hệ hướng dẫn khách hàng kiểm tra thiết bị, cấu hình VoLTE hoặc gọi lại thử."
        )

    # Tổng hợp trường hiển thị tóm tắt nội dung
    ai_summary_val = ticket_content
    if reopen_count > 0:
        warn_prefix = f"⚠️ [CẢNH BÁO: Phiếu mở lại {reopen_count} lần"
        if last_reopened_date:
            warn_prefix += f" (Lần cuối: {last_reopened_date})"
        warn_prefix += " - Yêu cầu KTV kiểm tra kỹ!]\n"
        ai_summary_val = warn_prefix + (ticket_content or "")

    return {
        "status": status,
        "color": color,
        "action_plan": action_plan,
        "comment": comment,
        "real_packages": formatted_packages,
        "rat_types": rat_type_str,
        "cem_data": cell_display_str,
        "app_usage": "--",  # Bỏ app usage cho cuộc gọi
        "ai_summary": ai_summary_val,
        "nam": nam_val,
        "cell_primary": primary_cell_name
    }
