# services/tts_new_data.py
# Nghiệp vụ: Hệ thống TTS Mới - Mobile Internet

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from services.state import state, normalize_phone_vn
from db_manager import (
    save_or_update_ticket, 
    sync_active_tickets_state, 
    get_db_connection
)
import ttsnew_api

def execute_tts_new_data_cycle():
    """
    Quy trình tiền kiểm tra phiếu sự cố từ hệ thống TTS Mới:
    1. Lấy danh sách phiếu đang xử lý.
    2. Lọc riêng các phiếu Mobile Internet (Data).
    3. Lấy số điện thoại thuê bao song song.
    4. Tra cứu Core: SAPC, CEM, BTools.
    5. Chạy Scenarios Engine & AI Summarizer để đưa ra nhận định, ý kiến và hướng xử lý.
    6. Lưu vào Database SQLite với source='tts_new' và xuất Excel báo cáo.
    """
    if state.status == "PROCESSING":
        state.log("WARN", "Hệ thống đang bận thực hiện chu kỳ khác.")
        return

    state.status = "PROCESSING"
    state.status_message = "Đang chạy tiền kiểm TTS Mới..."
    state.current_step = "Kết nối TTS Mới"

    try:
        from crawler_btools import extract_btools_single_phone
        from data_processor import standardize_btools_data
        from report_bot import (
            analyze_subscriber_status, 
            get_formatted_sapc_packages, 
            export_diagnostics_to_excel,
            extract_incident_time
        )
        from cem_client import CEMClient, save_cem_data_to_file

        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)
        from sapc_client import SAPCClient
        from converter import convert_sapc_response
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from ai_interpreter import analyze_ticket_with_ai

        from ttsnew_api import get_ttsnew_tickets_for_precheck, api_transfer_ttsnew_ticket, extract_token_from_browser
        state.log("STEP", "Đang kết nối hệ thống TTS Mới...")

        from auth_extractor import get_chrome_debug_driver
        driver = get_chrome_debug_driver()

        token = extract_token_from_browser(driver=driver)
        enriched_tickets, total_scanned = get_ttsnew_tickets_for_precheck(driver=driver)
        if not enriched_tickets:
            state.log("WARN", f"Đã quét {total_scanned} phiếu trên TTS Mới nhưng không tìm thấy phiếu Mobile Internet nào đang xử lý.")
            from db_manager import sync_active_tickets_state
            sync_active_tickets_state([], source="tts_new", key_type="ticket_code", service_type="data")
            return

        total_tickets = len(enriched_tickets)
        state.log("SUCCESS", f"Thu được {total_tickets} thuê bao Mobile Internet từ TTS Mới (Tổng {total_scanned} phiếu). Bắt đầu tra cứu Core...")

        # Đồng bộ danh sách phiếu hiện hữu với thực tế trên TTS Mới
        active_codes = {str(t.get("ticket_code", "")).strip() for t in enriched_tickets if t.get("ticket_code")}
        if active_codes:
            from db_manager import sync_active_tickets_state
            sync_active_tickets_state(active_codes, source="tts_new", key_type="ticket_code", service_type="data")

        now = datetime.now()
        start_d = (now - timedelta(days=4)).strftime("%d%m%Y")
        end_d = now.strftime("%d%m%Y")

        # Khởi tạo SAPC & CEM
        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception as ex_s:
            state.log("WARN", f"Chưa khởi tạo được SAPCClient: {ex_s}")
            sapc_client = None

        try:
            cem_client = CEMClient(driver=driver)
        except Exception as ex_c:
            state.log("WARN", f"Chưa khởi tạo được CEMClient: {ex_c}")
            cem_client = None

        excel_summary_list = []

        for idx, ticket in enumerate(enriched_tickets, 1):
            if state.stop_requested:
                state.log("WARN", "Nhận được yêu cầu dừng trong khi đang xử lý các thuê bao TTS Mới.")
                break

            phone_84 = normalize_phone_vn(ticket["phone"])
            title = str(ticket.get("title", "")).strip()
            content = str(ticket.get("content", "")).strip()
            ticket_code = str(ticket.get("ticket_code", "")).strip()
            incident_time_str = str(ticket.get("incident_time", "")).strip()
            created_time_str = str(ticket.get("created_time", "")).strip()

            state.current_step = f"Tra cứu thuê bao {idx}/{total_tickets}: {phone_84}"
            state.log("INFO", f"[{idx}/{total_tickets}] Đang tra cứu thuê bao: {phone_84} ({ticket_code} - {title})")

            # Tra cứu BTools (chạy ngầm tự động)
            raw_btools_data = extract_btools_single_phone(driver, phone_84, start_d, end_d)
            clean_data = standardize_btools_data(raw_btools_data)

            # Lưu file JSON vào number/ (hoặc fallback dùng lại dữ liệu BTools chu kỳ trước nếu lần này lỗi)
            output_dir = str(BASE_DIR / "number")
            os.makedirs(output_dir, exist_ok=True)
            json_filename = os.path.join(output_dir, f"{phone_84}.json")
            if clean_data is None and os.path.exists(json_filename):
                try:
                    with open(json_filename, "r", encoding="utf-8") as jf:
                        cached = json.load(jf)
                        cached_data = cached.get("btools_technical_data") or cached.get("data")
                        if cached_data:
                            clean_data = cached_data
                            state.log("INFO", f"   ↳ 🔄 Tạm dùng dữ liệu BTools đã lưu từ chu kỳ trước cho {phone_84}")
                except Exception:
                    pass

            if clean_data is not None:
                with open(json_filename, "w", encoding="utf-8") as jf:
                    json.dump({
                        "phone": phone_84,
                        "package_title": title,
                        "ticket_content": content,
                        "title": title,
                        "content": content,
                        "ticket_code": ticket_code,
                        "btools_technical_data": clean_data,
                        "data": clean_data
                    }, jf, ensure_ascii=False, indent=2)

            # Tra SAPC + HSS Profile
            if sapc_client is not None:
                try:
                    raw_sapc_data = sapc_client.query(phone_84)
                    sapc_result = convert_sapc_response(raw_sapc_data)
                except Exception as e:
                    sapc_result = {"msisdn": phone_84, "packages": []}

                info_result = tra_cell_tu_so_dien_thoai(phone_84, session=sapc_client.session)
                hss_output_dir = str(BASE_DIR / "output")
                os.makedirs(hss_output_dir, exist_ok=True)
                with open(os.path.join(hss_output_dir, f"{phone_84}.json"), "w", encoding="utf-8") as hf:
                    json.dump({
                        **sapc_result,
                        "subscriber_info": info_result,
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, hf, ensure_ascii=False, indent=4)

                # Kiểm tra hành vi bổ sung Case 2: Nếu gói ĐK trước 5 ngày và BTools 5 ngày không có data
                try:
                    from report_bot import get_sapc_package_validity
                    from crawler_btools import fetch_supplementary_btools_if_needed
                    active_pkgs, _ = get_sapc_package_validity(phone_84)
                    commercial_pkgs = [p for p in active_pkgs if not p.get("is_paygo") and not p.get("is_home") and not p.get("is_no_date")]
                    earliest_reg_dt = min([p["reg_dt"] for p in commercial_pkgs if p.get("reg_dt")], default=None)
                    start_scan_date = (datetime.now() - timedelta(days=4)).date()
                    if earliest_reg_dt and earliest_reg_dt.date() < start_scan_date:
                        clean_data = fetch_supplementary_btools_if_needed(driver, phone_84, clean_data, earliest_reg_dt, start_scan_date)
                except Exception as ex_case2:
                    state.log("WARN", f"Lỗi tra cứu bổ sung Case 2: {ex_case2}")

            # Tra cứu CEM & App Usage
            cem_records = []
            app_events = []
            cem_data_str = "Không có dữ liệu CEM"
            app_usage_str = "Không có dữ liệu App Usage"

            try:
                if cem_client is None:
                    cem_client = CEMClient(driver=driver)
                cem_records = cem_client.get_subscriber_history_5days(phone_84, days=5)
                app_events = cem_client.get_subscriber_app_events(phone_84, days=5)
                cem_data_str = CEMClient.extract_top_cells_summary(cem_records, app_events=app_events)
                app_usage_str = CEMClient.extract_top_apps_summary(app_events)

                save_cem_data_to_file(phone_84, cem_records, app_events, base_dir=BASE_DIR)
            except Exception as ex_cem:
                cem_data_str = f"Lỗi CEM: {ex_cem}"

            # Tóm tắt thông tin bằng AI / NLP Offline
            ai_summary = analyze_ticket_with_ai(json_filename)

            # Kiểm tra THÔNG TIN MỞ LẠI TTS / Số lần mở lại
            reopen_count = int(ticket.get("reopen_count") or 0)
            last_reopened_date = str(ticket.get("last_reopened_date") or "").strip()
            if reopen_count > 0:
                reopen_warn = f"⚠️ [CẢNH BÁO: Phiếu mở lại {reopen_count} lần"
                if last_reopened_date:
                    reopen_warn += f" (Lần cuối: {last_reopened_date})"
                reopen_warn += " - KHÔNG TỰ ĐỘNG ĐÓNG, yêu cầu KTV kiểm tra kỹ!]\n"
                ai_summary = reopen_warn + (ai_summary if ai_summary and ai_summary != "null" else "")
                state.log("WARN", f"⚠️ Phiếu {ticket_code} ({phone_84}) có THÔNG TIN MỞ LẠI TTS: Số lần mở lại = {reopen_count} -> KHÔNG TỰ ĐỘNG ĐÓNG!")

            # Kiểm tra xem phiếu đã có nhận định / nội dung xử lý trong DB chưa (đặc biệt khi ở bước 2.6)
            existing_db_row = None
            try:
                conn_chk = get_db_connection()
                existing_db_row = conn_chk.execute("""
                    SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary
                    FROM tickets 
                    WHERE (ticket_id = ? OR ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
                    ORDER BY updated_at DESC LIMIT 1
                """, (ticket.get("ticket_id"), f"{ticket_code}%", phone_84)).fetchone()
                conn_chk.close()
            except Exception:
                pass

            step_name_raw = str(ticket.get("step_name") or "")
            is_step_26 = "2.6" in step_name_raw

            # Kiểm tra xem nhận định cũ trong DB có hợp lệ không (KHÔNG được tái sử dụng lỗi kết nối / chưa đăng nhập)
            def _is_valid_technical_status(st):
                if not st:
                    return False
                s_u = str(st).strip().upper()
                if "LỖI KẾT NỐI" in s_u or "CHƯA ĐĂNG NHẬP" in s_u or "LỖI MÁY CHỦ" in s_u or "CHƯA PHÂN LOẠI" in s_u:
                    return False
                return True

            can_reuse_db = (
                is_step_26 
                and existing_db_row 
                and existing_db_row["comment"] 
                and _is_valid_technical_status(existing_db_row["status"])
            )

            if can_reuse_db:
                state.log("INFO", f"   ↳ 📋 Phiếu tại bước 2.6 kế thừa nhận định kỹ thuật chuẩn từ vòng 1: [{existing_db_row['status']}]")
                status = existing_db_row["status"]
                comment = existing_db_row["comment"]
                action_plan = existing_db_row["action_plan"] or ""
                color = existing_db_row["color"] or "#4CAF50"
                real_pkgs_str = existing_db_row["real_packages"] or ""
                final_packages_str = real_pkgs_str
                rat_types_string = existing_db_row["rat_types"] or ""
                cem_data_str = existing_db_row["cem_data"] or ""
                app_usage_str = existing_db_row["app_usage"] or ""
                ai_summary = existing_db_row["ai_summary"] or ""
                reopen_count = int(ticket.get("reopen_count") or 0)
                last_reopened_date = str(ticket.get("last_reopened_date") or "").strip()
            else:
                # Phân tích kịch bản mới dựa trên Core / BTools / CEM vừa cào
                status, comment, action_plan, color = analyze_subscriber_status(
                    clean_data, title, content, phone_84=phone_84, cem_records=cem_records, app_events=app_events, incident_time_str=incident_time_str, driver=driver
                )
                state.log("INFO", f"   ↳ Nhận định: [{status}]")

                # Hạ tầng
                rats = list(set(str(r.get("RAT_TYPE_NAME", "")) for r in (clean_data or []) if r.get("RAT_TYPE_NAME")))
                rat_types_string = ", ".join(rats) if rats else "Không có dữ liệu"

                # Gói cước BTools / SAPC
                cfg_p = BASE_DIR / "diagnostic_config.json"
                ex_codes = set()
                if cfg_p.exists():
                    with open(cfg_p, "r", encoding="utf-8") as cf:
                        ex_codes = set(json.load(cf).get("EXCLUDED_SYSTEM_CODES", []))
                real_pkgs = set()
                for r in (clean_data or []):
                    sc = str(r.get("SERVICE_ID_CODE", "")).strip()
                    sn = str(r.get("SERVICE_NAME", "")).strip()
                    if sc.lower() and sc.lower() not in ex_codes:
                        if sn and "gói cước lạ" not in sn.lower() and sn.lower() not in ex_codes:
                            real_pkgs.add(sn)
                        else:
                            real_pkgs.add(sc)
                real_pkgs_str = ", ".join(list(real_pkgs)) if real_pkgs else "Không phát sinh gói TM"
                final_packages_str = get_formatted_sapc_packages(phone_84, fallback_btools=real_pkgs_str)

            rec = {
                "phone": phone_84,
                "ticket_code": ticket_code,
                "ticket_id": ticket.get("ticket_id"),
                "flow_id": ticket.get("flow_id"),
                "package_title": title,
                "incident_time": incident_time_str,
                "ticket_content": content,
                "created_time": created_time_str,
                "real_packages": final_packages_str,
                "rat_types": rat_types_string,
                "cem_data": cem_data_str,
                "app_usage": app_usage_str,
                "status": status,
                "comment": comment,
                "action_plan": action_plan,
                "color": color,
                "ticket_status": "Chưa đóng",
                "force_update_status": True,
                "source": "tts_new",
                "ai_summary": ai_summary if ai_summary else "null",
                "reopen_count": reopen_count,
                "last_reopened_date": last_reopened_date
            }
            excel_summary_list.append(rec)
            save_or_update_ticket(rec)

            # Tự động đóng phiếu 2 vòng nếu được phép theo chế độ auto_close_mode
            if state.should_auto_close("tts_new") and ticket.get("flow_id") and ticket.get("ticket_id"):
                from db_manager import check_ticket_can_close
                can_close, reason = check_ticket_can_close(rec)
                if not can_close:
                    state.log("INFO", f"   ↳ ⏸️ Giữ nguyên phiếu {phone_84}: Chưa đủ điều kiện đóng ({reason})")
                else:
                    state.log("STEP", f"🤖 [Tự Động Đóng] Đang xử lý phiếu TTS Mới cho {phone_84}...")
                    try:
                        close_res = api_transfer_ttsnew_ticket(
                            token=token,
                            ticket_flow_id=ticket.get("flow_id"),
                            ticket_id=ticket.get("ticket_id"),
                            phone=phone_84,
                            ticket_code=ticket_code,
                            status=status,
                            closing_content=comment,
                            assign_content=action_plan
                        )
                        if close_res.get("success"):
                            state.log("SUCCESS", f"   ↳ {close_res.get('message')}")
                            if close_res.get("round") == 0 or "2.4" in close_res.get("step_name", ""):
                                rec["ticket_status"] = "Đã chuyển 2.4"
                                save_or_update_ticket(rec)
                                # TỰ ĐỘNG CHUYỂN TIẾP SANG 2.6 HOẶC 5.1 THEO CHUỖI LIVE
                                try:
                                    time.sleep(1.5)
                                    raw_act = fetch_active_tickets(token, limit=100)
                                    next_f_id = None
                                    for r_it in raw_act:
                                        if (ticket.get("ticket_id") and str(r_it.get("ticketId")) == str(ticket.get("ticket_id"))) or \
                                           (phone_84 and phone_84 in str(r_it.get("contactPhone", ""))):
                                            next_f_id = r_it.get("id")
                                            break
                                    if next_f_id:
                                        state.log("STEP", f"🤖 [Tự Đóng Live] Phiếu {phone_84} tiếp tục chuyển từ 2.4 sang 2.6/5.1...")
                                        c_res2 = api_transfer_ttsnew_ticket(
                                            token=token,
                                            ticket_flow_id=next_f_id,
                                            ticket_id=ticket.get("ticket_id"),
                                            phone=phone_84,
                                            ticket_code=ticket_code,
                                            status=status,
                                            closing_content=comment,
                                            assign_content=action_plan
                                        )
                                        if c_res2.get("success"):
                                            state.log("SUCCESS", f"   ↳ {c_res2.get('message')}")
                                            if "2.6" in c_res2.get("step_name", ""):
                                                rec["ticket_status"] = "Chờ đóng lần 2"
                                                save_or_update_ticket(rec)
                                                # TIẾP TỤC ĐÓNG DỨT ĐIỂM NẾU SANG 2.6
                                                time.sleep(1.5)
                                                raw_act3 = fetch_active_tickets(token, limit=100)
                                                f3_id = None
                                                for r_it3 in raw_act3:
                                                    if (ticket.get("ticket_id") and str(r_it3.get("ticketId")) == str(ticket.get("ticket_id"))) or \
                                                       (phone_84 and phone_84 in str(r_it3.get("contactPhone", ""))):
                                                        f3_id = r_it3.get("id")
                                                        break
                                                if f3_id:
                                                    state.log("STEP", f"🤖 [Tự Đóng Live] Phiếu {phone_84} đóng dứt điểm tại bước 2.6...")
                                                    c_res3 = api_transfer_ttsnew_ticket(
                                                        token=token,
                                                        ticket_flow_id=f3_id,
                                                        ticket_id=ticket.get("ticket_id"),
                                                        phone=phone_84,
                                                        ticket_code=ticket_code,
                                                        status=status,
                                                        closing_content=comment,
                                                        assign_content=action_plan
                                                    )
                                                    if c_res3.get("success"):
                                                        state.log("SUCCESS", f"   ↳ {c_res3.get('message')}")
                                                        rec["ticket_status"] = "Đã đóng"
                                                        save_or_update_ticket(rec)
                                            else:
                                                rec["ticket_status"] = "Chuyển VTT"
                                                save_or_update_ticket(rec)
                                except Exception as ex_chain:
                                    state.log("WARN", f"Lỗi auto-chain cho {phone_84}: {ex_chain}")
                            elif close_res.get("round") == 1:
                                rec["ticket_status"] = "Chờ đóng lần 2" if "2.6" in close_res.get("step_name", "") else "Chuyển VTT"
                                save_or_update_ticket(rec)
                                # TIẾP TỤC ĐÓNG DỨT ĐIỂM NẾU SANG 2.6
                                if "2.6" in close_res.get("step_name", ""):
                                    try:
                                        time.sleep(1.5)
                                        raw_act3 = fetch_active_tickets(token, limit=100)
                                        f3_id = None
                                        for r_it3 in raw_act3:
                                            if (ticket.get("ticket_id") and str(r_it3.get("ticketId")) == str(ticket.get("ticket_id"))) or \
                                               (phone_84 and phone_84 in str(r_it3.get("contactPhone", ""))):
                                                f3_id = r_it3.get("id")
                                                break
                                        if f3_id:
                                            state.log("STEP", f"🤖 [Tự Đóng Live] Phiếu {phone_84} đóng dứt điểm tại bước 2.6...")
                                            c_res3 = api_transfer_ttsnew_ticket(
                                                token=token,
                                                ticket_flow_id=f3_id,
                                                ticket_id=ticket.get("ticket_id"),
                                                phone=phone_84,
                                                ticket_code=ticket_code,
                                                status=status,
                                                closing_content=comment,
                                                assign_content=action_plan
                                            )
                                            if c_res3.get("success"):
                                                state.log("SUCCESS", f"   ↳ {c_res3.get('message')}")
                                                rec["ticket_status"] = "Đã đóng"
                                                save_or_update_ticket(rec)
                                    except Exception:
                                        pass
                            else:
                                rec["ticket_status"] = "Đã đóng"
                                save_or_update_ticket(rec)
                        else:
                            state.log("WARN", f"   ↳ ⚠️ [Phiếu lỗi] Không thể tự động chuyển bước phiếu {phone_84}: {close_res.get('message')}")
                            rec["ticket_status"] = "Phiếu lỗi"
                            save_or_update_ticket(rec)
                    except Exception as ex_auto:
                        state.log("WARN", f"   ↳ ⚠️ [Phiếu lỗi] Lỗi khi tự động đóng phiếu {phone_84}: {ex_auto}")
                        rec["ticket_status"] = "Phiếu lỗi"
                        save_or_update_ticket(rec)

        # Xuất file Excel báo cáo riêng cho TTS Mới
        if excel_summary_list:
            result_dir = BASE_DIR / "result"
            os.makedirs(result_dir, exist_ok=True)
            excel_name = result_dir / f"BaoCao_TienKiem_TTS_NEW_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"
            saved_excel_file = export_diagnostics_to_excel(excel_summary_list, excel_name, start_d, end_d)
            state.log("SUCCESS", f"Báo cáo Excel TTS Mới đã lưu: {saved_excel_file}")

        mode_str = "Tự động đóng 2 vòng" if state.should_auto_close("tts_new") else "Chỉ hiển thị, đóng thủ công"
        state.log("SUCCESS", f"✅ Hoàn tất chu kỳ tiền kiểm {len(excel_summary_list)} phiếu TTS Mới (Chế độ: {mode_str}).")

    except Exception as e:
        state.log("ERROR", f"Lỗi trong chu kỳ tiền kiểm TTS Mới: {e}")
    finally:
        state.current_step = "Hoàn tất tiền kiểm TTS Mới"
        if not state.is_running:
            state.status = "IDLE"
            state.status_message = "Đã dừng. Sẵn sàng nhận lệnh."




# Alias tương thích
execute_ttsnew_cycle = execute_tts_new_data_cycle
