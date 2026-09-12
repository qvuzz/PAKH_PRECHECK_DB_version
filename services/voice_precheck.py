# services/voice_precheck.py
# Engine tiền kiểm chuyên biệt cho các phản ánh NGOÀI Mobile Internet (Cuộc gọi / Thoại / SMS / Gói cước / PA Khác)
# Quy tắc: BỎ HOÀN TOÀN BTools và CEM. Chỉ tra cứu SAPC (Gói cước/Dịch vụ/NAM) và HLR Cell Profile.
# Ở bước 2.3: Mặc định điền sẵn Ý kiến phân tích và Nội dung phản hồi là "Chuyển 2.4".

import os
import re
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def is_voice_ticket(title: str) -> bool:
    """Kiểm tra xem phiếu có phải thuộc nhóm Thoại / Cuộc gọi / Sự cố ngoài Mobile Internet hay không."""
    from db_manager import is_mobile_internet_ticket
    return not is_mobile_internet_ticket(title)


def precheck_single_voice_ticket(phone_84: str, ticket: dict, sapc_client=None, cem_client=None, driver=None) -> dict:
    """
    Tiền kiểm chuyên biệt cho phản ánh ngoài Mobile Internet (Cuộc gọi / Thoại / SMS / Gói cước):
    1. Tra cứu SAPC: Lấy trạng thái NAM (0/1), HSS Profile (VoLTE), gói thoại/dịch vụ.
    2. Lấy Cell trực tiếp từ HLR/SAPC (bỏ hoàn toàn cào BTools và CEM API để tối ưu tốc độ).
    3. Phân tích kịch bản cuộc gọi và đưa ra nhận định chuẩn.
    4. Ở bước 2.3: Tự động nhập sẵn Ý kiến phân tích & Nội dung phản hồi là "Chuyển 2.4".
    """
    code = ticket.get("ticket_code", "")
    title = ticket.get("title", "")
    ticket_content = ticket.get("content", "")
    step_name = str(ticket.get("step_name") or "")
    reopen_count = int(ticket.get("reopen_count") or 0)
    last_reopened_date = str(ticket.get("last_reopened_date") or "").strip()

    # Nhận diện nếu caller truyền driver vào vị trí tham số thứ 3
    if sapc_client is not None and hasattr(sapc_client, "session") is False and hasattr(sapc_client, "execute_cdp_cmd"):
        driver = sapc_client
        sapc_client = None

    if driver is None:
        try:
            from auth_extractor import get_chrome_debug_driver
            driver = get_chrome_debug_driver()
        except Exception:
            pass

    if sapc_client is None:
        try:
            from sapc_client import SAPCClient
            sapc_client = SAPCClient(driver=driver)
        except Exception:
            try:
                from sapc_client import SAPCClient
                sapc_client = SAPCClient()
            except Exception:
                pass

    info_result = {}
    sapc_result = {"msisdn": phone_84, "packages": []}
    formatted_packages = "--"
    nam_val = "0"
    sapc_cell = ""
    rat_type_str = "2G/3G/4G Thoại"

    # =========================================================================
    # 1. TRA CỨU SAPC (Kiểm tra trạng thái NAM, thuê bao, dịch vụ, trạm Cell HLR)
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
        except Exception:
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

    # Thông tin trạm Cell (lấy từ SAPC/HLR, không tiền kiểm CEM)
    if sapc_cell and sapc_cell != "--":
        cell_display_str = f"Cell SAPC: {sapc_cell}"
    else:
        cell_display_str = "Trạm phát sóng khu vực đảm bảo"

    # =========================================================================
    # 2. BỘ QUY TẮC TIỀN KIỂM CUỘC GỌI / NGOÀI DATA
    # =========================================================================
    status = "MẠNG LƯỚI ĐẢM BẢO"
    color = "green"

    # Kịch bản 1: Cảnh báo phiếu mở lại nhiều lần
    if reopen_count > 0:
        status = f"⚠️ PHIẾU MỞ LẠI ({reopen_count} LẦN)"
        color = "orange"
    # Kịch bản 2: Bị khóa Spam cuộc gọi
    elif "spam cuộc gọi" in title.lower() or "spam cuộc gọi" in ticket_content.lower():
        status = "BỊ KHÓA SPAM CUỘC GỌI"
        color = "red"
    # Kịch bản 3: Thuê bao bị khóa cước / khóa dịch vụ (NAM = 1)
    elif nam_val == "1":
        status = "KHÓA DỊCH VỤ (NAM: 1)"
        color = "red"
    # Kịch bản 4: HSS Profile bất thường / Profile lạ (ảnh hưởng VoLTE)
    elif is_strange_hss:
        status = "HSS PROFILE LẠ (ẢNH HƯỞNG VOLTE)"
        color = "red"
    # Kịch bản 5: Mạng lưới và trạm phát sóng đảm bảo bình thường
    else:
        status = "MẠNG LƯỚI ĐẢM BẢO"
        color = "green"

    # =========================================================================
    # 3. ĐIỀN SẴN NỘI DUNG CHO BƯỚC 2.3: "Chuyển 2.4"
    # =========================================================================
    raw_step_check = f"{step_name} {code}".lower()
    is_step_23 = ("2.3" in raw_step_check) or ("xử lý pakh" in raw_step_check)

    if is_step_23:
        comment = "Chuyển 2.4"
        action_plan = "Chuyển 2.4"
    else:
        comment = ""
        action_plan = ""

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
        "formatted_pkg": formatted_packages,
        "rat_types": rat_type_str,
        "cem_data": cell_display_str,
        "app_usage": "--",  # Bỏ qua CEM & App usage
        "ai_summary": ai_summary_val,
        "nam": nam_val,
        "cell_primary": sapc_cell or "khu vực"
    }
