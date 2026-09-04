# services/tts_old_api_data.py
# Chu kỳ quét & tiền kiểm Mobile Internet trên Hệ Thống TTS Cũ qua REST API siêu tốc

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from services.state import state, normalize_phone_vn
from db_manager import save_or_update_ticket, sync_active_tickets_state, get_db_connection
from tts_old_api import extract_token_from_browser, fetch_tts_old_tickets_api, fetch_nguyen_nhan_list_api, close_tts_old_ticket_api
import update_tts.config as tts_config
import update_tts.excel_reader as excel_reader


def execute_tts_old_api_data_cycle(driver=None):
    """
    Thực hiện 1 chu kỳ quét & tiền kiểm Mobile Internet trên TTS Cũ qua REST API.
    Không dùng Selenium click phân trang. Tốc độ cao, chạy ngầm 100%.
    """
    if state.status == "PROCESSING":
        state.log("WARN", "Hệ thống đang bận thực hiện chu kỳ khác.")
        return 0

    state.status = "PROCESSING"
    state.stop_requested = False
    state.total_cycles += 1
    state.last_run_time = datetime.now().strftime("%H:%M:%S")
    state.status_message = "Đang quét Mobile Internet qua REST API TTS Cũ..."
    state.log("STEP", f"🚀 [TTS CŨ REST API - DATA] Bắt đầu chu kỳ #{state.total_cycles}")

    try:
        # 1. Trích xuất token từ Chrome hoặc cache
        token, user_info = extract_token_from_browser(driver)
        if not token:
            state.log("ERROR", "❌ Không tìm thấy token 'scnntttoken' của TTS Cũ. Vui lòng mở và đăng nhập tab tts.vnpt.vn trên Chrome.")
            return 0

        user_id = user_info.get("Id") or user_info.get("id") or 0

        # 2. Lấy danh mục nguyên nhân để map
        nguyen_nhan_map = fetch_nguyen_nhan_list_api(token)

        # 3. Quét danh sách phiếu qua REST API
        state.current_step = "Đang tải danh sách phiếu từ REST API TTS Cũ..."
        raw_tickets = fetch_tts_old_tickets_api(token, limit=250)

        # Lọc các phiếu thuộc Mobile Internet
        data_tickets = [t for t in raw_tickets if t.get("service_type") == "data"]
        state.total_scanned = len(data_tickets)

        if not data_tickets:
            state.log("WARN", "ℹ️ Không có phiếu sự cố Mobile Internet nào đang chờ xử lý trên TTS Cũ.")
            sync_active_tickets_state([], source="tts_old_api", key_type="phone", service_type="data")
            state.status = "IDLE"
            state.status_message = "Đã đồng bộ: Không còn phiếu Mobile Internet nào chờ xử lý trên TTS Cũ."
            return 0

        state.log("SUCCESS", f"⚡ REST API trả về {len(data_tickets)} phiếu Mobile Internet (trong tổng số {len(raw_tickets)} phiếu).")

        # Import các client kỹ thuật (SAPC, BTools, AI, CEM)
        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)

        from sapc_client import SAPCClient
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from converter import convert_sapc_response
        from report_bot import get_formatted_sapc_packages, analyze_subscriber_status
        from ai_interpreter import analyze_ticket_with_ai

        from crawler_btools import extract_btools_single_phone
        from data_processor import standardize_btools_data

        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception:
            sapc_client = None

        today = datetime.today()
        start_d = (today - timedelta(days=4)).strftime("%Y-%m-%d")
        end_d = today.strftime("%Y-%m-%d")

        active_phones = set()

        for idx, t in enumerate(data_tickets, 1):
            if state.stop_requested:
                state.log("WARN", "Nhận được yêu cầu dừng.")
                break

            phone_84 = t.get("phone", "")
            if not phone_84:
                continue

            active_phones.add(phone_84)
            inc_time = t.get("incident_time") or ""

            state.current_step = f"Tiền kiểm tra thuê bao {idx}/{len(data_tickets)}: {phone_84}"
            state.log("STEP", f"[{idx}/{len(data_tickets)}] Tiền kiểm tra cho SĐT: {phone_84} ({t.get('title')})...")

            try:
                # 1. Tra cứu Core / SAPC
                info_result = {}
                sapc_result = {"msisdn": phone_84, "packages": []}
                if sapc_client:
                    try:
                        info_result = tra_cell_tu_so_dien_thoai(phone_84, session=sapc_client.session)
                        raw_sapc = sapc_client.query(phone_84)
                        sapc_result = convert_sapc_response(raw_sapc)
                    except Exception as ex_core:
                        state.log("WARN", f"Lỗi tra Core cho {phone_84}: {ex_core}")

                hss_output_dir = str(BASE_DIR / "output")
                os.makedirs(hss_output_dir, exist_ok=True)
                with open(os.path.join(hss_output_dir, f"{phone_84}.json"), "w", encoding="utf-8") as hf:
                    json.dump({
                        **sapc_result,
                        "subscriber_info": info_result,
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, hf, ensure_ascii=False, indent=4)

                formatted_packages = get_formatted_sapc_packages(phone_84)

                # 2. Tra cứu BTools
                clean_btools_data = None
                try:
                    raw_btools = extract_btools_single_phone(driver, phone_84, start_d, end_d)
                    if raw_btools is None:
                        state.log("WARN", f"⚠️ Không thể tra cứu BTools cho {phone_84}: Chưa đăng nhập BTools hoặc lỗi máy chủ. TẠM DỪNG TỰ ĐỘNG ĐÓNG!")
                    else:
                        clean_btools_data = standardize_btools_data(raw_btools)
                except Exception as ex_bt:
                    state.log("WARN", f"⚠️ Lỗi cào BTools cho {phone_84}: {ex_bt}")

                # 3. Tóm tắt AI
                num_output_dir = str(BASE_DIR / "number")
                os.makedirs(num_output_dir, exist_ok=True)
                json_filename = os.path.join(num_output_dir, f"{phone_84}.json")
                with open(json_filename, "w", encoding="utf-8") as jf:
                    json.dump({
                        "phone": phone_84,
                        "package_title": t.get("title", ""),
                        "ticket_content": t.get("content", ""),
                        "btools_technical_data": clean_btools_data if clean_btools_data is not None else []
                    }, jf, ensure_ascii=False, indent=4)

                ai_summary = analyze_ticket_with_ai(json_filename)

                # 4. Phân loại theo bộ kịch bản
                status_calc, comment_calc, action_plan, _ = analyze_subscriber_status(
                    clean_btools_data, t.get("title", ""), t.get("content", ""),
                    phone_84=phone_84, incident_time_str=inc_time
                )

                cell_desc = info_result.get("Cell ID") or info_result.get("ECGI") or "--"
                rat_type_str = info_result.get("Radio") or "Sóng di động"

                rec = {
                    "phone": phone_84,
                    "incident_time": inc_time,
                    "package_title": t.get("title", ""),
                    "ticket_content": t.get("content", ""),
                    "status": status_calc,
                    "real_packages": formatted_packages,
                    "rat_types": rat_type_str,
                    "cem_data": f"Cell: {cell_desc}",
                    "app_usage": "--",
                    "ai_summary": ai_summary if ai_summary else t.get("content", ""),
                    "comment": comment_calc,
                    "action_plan": action_plan,
                    "ticket_status": "Chưa đóng",
                    "source": "tts_old_api",
                    "created_time": t.get("created_time") or inc_time,
                    "ticket_id": t.get("ticket_id"),
                    "flow_id": str(t.get("id_yeu_cau") or ""),
                    "ticket_code": t.get("ma_ccos") or t.get("MaCCOS") or ""
                }

                # 5. Kiểm tra điều kiện tự động đóng
                norm_status = excel_reader.normalize_text(status_calc)
                matched_nguyen_nhan = None
                for k, v in tts_config.STATUS_TO_NGUYEN_NHAN.items():
                    if excel_reader.normalize_text(k) == norm_status:
                        matched_nguyen_nhan = v
                        break

                ai_sum_text = ai_summary or t.get("content", "")
                check_dict = {
                    "status": status_calc,
                    "phone": phone_84,
                    "comment": comment_calc,
                    "action_plan": action_plan,
                    "ai_summary": ai_sum_text,
                    "access_status": excel_reader.get_access_status(ai_sum_text),
                    "error_area": excel_reader.get_error_area(ai_sum_text)
                }

                can_close = bool(clean_btools_data is not None and matched_nguyen_nhan and excel_reader.is_level_1_auto_close_candidate(check_dict))

                if clean_btools_data is None:
                    state.log("WARN", f"⚠️ Phiếu {phone_84} lỗi tra cứu BTools (chưa đăng nhập hoặc lỗi máy chủ). Giữ trạng thái 'Chưa đóng' để KTV kiểm tra!")
                elif state.auto_close and can_close:
                    state.log("STEP", f"🤖 Thuê bao {phone_84} đủ điều kiện. Đang đóng tự động qua REST API...")
                    # Tìm Id nguyên nhân tương ứng
                    id_nn = None
                    if matched_nguyen_nhan:
                        id_nn = nguyen_nhan_map.get(matched_nguyen_nhan.lower()) or nguyen_nhan_map.get(matched_nguyen_nhan)

                    if not id_nn:
                        # Fallback về nguyên nhân mạng lưới đảm bảo (Id: 1016)
                        id_nn = 1016

                    full_content = f"{comment_calc}\n{action_plan}".strip()
                    close_ok, close_msg = close_tts_old_ticket_api(
                        ticket=t,
                        id_nguyen_nhan=id_nn,
                        noi_dung=full_content,
                        token=token,
                        user_id=user_id,
                        dry_run=False
                    )
                    if close_ok:
                        rec["ticket_status"] = "Đã đóng"
                        state.closed_count += 1
                        state.log("SUCCESS", close_msg)
                    else:
                        state.log("WARN", f"⚠️ Không thể đóng phiếu API {phone_84}: {close_msg}")
                else:
                    state.log("SUCCESS", f"Hoàn tất tiền kiểm: {phone_84} -> {status_calc}")

                save_or_update_ticket(rec)

            except Exception as ex_sub:
                state.log("ERROR", f"Lỗi tiền kiểm tra {phone_84}: {ex_sub}")

        if active_phones:
            sync_active_tickets_state(active_phones, source="tts_old_api", key_type="phone", service_type="data")

        state.log("SUCCESS", f"🎉 Hoàn tất chu kỳ tiền kiểm REST API Mobile Internet TTS Cũ cho {len(data_tickets)} phiếu!")
        return len(data_tickets)

    except Exception as e:
        state.log("ERROR", f"Lỗi chu kỳ quét REST API TTS Cũ: {e}")
        return 0
    finally:
        state.current_step = "Hoàn tất chu kỳ"
        if not state.is_running:
            state.status = "IDLE"
            state.status_message = "Sẵn sàng"
