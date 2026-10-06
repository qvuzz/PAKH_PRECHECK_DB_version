# services/tts_old_api_data.py
# Chu kỳ quét & tiền kiểm Mobile Internet trên Hệ Thống TTS Cũ ngầm tự động
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


def _is_valid_technical_status(st):
    if not st:
        return False
    s_u = str(st).strip().upper()
    if "LỖI KẾT NỐI" in s_u or "CHƯA ĐĂNG NHẬP" in s_u or "LỖI MÁY CHỦ" in s_u or "CHƯA PHÂN LOẠI" in s_u or "CHỜ TIỀN KIỂM" in s_u:
        return False
    return True


def execute_tts_old_api_data_cycle(driver=None, force_recheck: bool = False):
    """
    Thực hiện 1 chu kỳ quét & tiền kiểm Mobile Internet trên TTS Cũ.
    Chạy ngầm tự động 100%. Tái sử dụng kết quả DB nếu đã tiền kiểm, trừ khi force_recheck=True.
    """
    if state.status == "PROCESSING":
        state.log("WARN", "Hệ thống đang bận thực hiện chu kỳ khác.")
        return 0

    state.status = "PROCESSING"
    state.stop_requested = False
    state.total_cycles += 1
    state.last_run_time = datetime.now().strftime("%H:%M:%S")
    state.status_message = "Đang quét Mobile Internet TTS Cũ..."
    state.log("STEP", f"🚀 [TTS CŨ - DATA] Bắt đầu chu kỳ #{state.total_cycles}")

    try:
        # 1. Trích xuất token từ Chrome hoặc cache
        token, user_info = extract_token_from_browser(driver)
        if not token:
            state.log("ERROR", "❌ Không tìm thấy token 'scnntttoken' của TTS Cũ. Vui lòng mở và đăng nhập tab tts.vnpt.vn trên Chrome.")
            return 0

        user_id = user_info.get("Id") or user_info.get("id") or 0

        # 2. Lấy danh mục nguyên nhân để map
        nguyen_nhan_map = fetch_nguyen_nhan_list_api(token)

        # 3. Quét danh sách phiếu
        state.current_step = "Đang tải danh sách phiếu từ TTS Cũ..."
        raw_tickets = fetch_tts_old_tickets_api(token, limit=250)

        # Lọc và đồng bộ nhanh các phiếu ngoài Data (Thoại / SMS / Gói cước / PA Khác) của TTS Cũ
        voice_tickets = [t for t in raw_tickets if t.get("service_type") != "data"]
        active_voice_phones = set()
        for vt in voice_tickets:
            p84 = vt.get("phone", "")
            if not p84:
                continue
            active_voice_phones.add(p84)
            inc_t = vt.get("incident_time") or ""
            is_reopened_v = bool(vt.get("is_reopened") or (vt.get("reopen_count", 0) > 0))
            reopen_count_v = int(vt.get("reopen_count", 0) or (1 if is_reopened_v else 0))
            reopen_cmt_v = "Phiếu mở lại, KTV kiểm tra thêm." if is_reopened_v else ""

            rec = {
                "phone": p84,
                "incident_time": inc_t,
                "package_title": vt.get("title", "Thoại / SMS"),
                "ticket_content": vt.get("content", ""),
                "status": "⚠️ PHIẾU MỞ LẠI" if is_reopened_v else "",
                "real_packages": "--",
                "rat_types": "--",
                "cem_data": "--",
                "app_usage": "--",
                "ai_summary": vt.get("content", ""),
                "comment": reopen_cmt_v,
                "action_plan": "KTV kiểm tra và xử lý thủ công" if is_reopened_v else "",
                "ticket_status": "Chưa đóng",
                "source": "tts_old_api",
                "created_time": vt.get("created_time") or inc_t,
                "ticket_id": vt.get("ticket_id"),
                "flow_id": str(vt.get("id_yeu_cau") or ""),
                "ticket_code": vt.get("ma_ccos") or vt.get("MaCCOS") or "",
                "reopen_count": reopen_count_v,
                "last_reopened_date": vt.get("last_reopened_date") or ""
            }
            save_or_update_ticket(rec)
        sync_active_tickets_state(active_voice_phones, source="tts_old_api", key_type="phone", service_type="voice_sms")
        if voice_tickets:
            state.log("INFO", f"📞 [TTS CŨ] Đã tự động đồng bộ {len(voice_tickets)} phiếu Thoại / SMS / Gói cước / PA Khác.")

        # Lọc các phiếu thuộc Mobile Internet
        data_tickets = [t for t in raw_tickets if t.get("service_type") == "data"]
        state.total_scanned = len(data_tickets)

        if not data_tickets:
            state.log("WARN", "ℹ️ Không có phiếu sự cố Mobile Internet nào đang chờ xử lý trên TTS Cũ.")
            sync_active_tickets_state([], source="tts_old_api", key_type="phone", service_type="data")
            state.status = "IDLE"
            state.status_message = "Đã đồng bộ: Không còn phiếu Mobile Internet nào chờ xử lý trên TTS Cũ."
            return 0

        state.log("SUCCESS", f"⚡ Đã tải {len(data_tickets)} phiếu Mobile Internet (trong tổng số {len(raw_tickets)} phiếu).")

        # Import các client kỹ thuật (SAPC, BTools, AI, CEM)
        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)

        from sapc_client import SAPCClient
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from converter import convert_sapc_response
        from report_bot import get_formatted_sapc_packages, analyze_subscriber_status, extract_btools_packages_summary
        from ai_interpreter import analyze_ticket_with_ai

        from crawler_btools import extract_btools_single_phone
        from data_processor import standardize_btools_data

        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception:
            sapc_client = None

        try:
            from cem_client import CEMClient, save_cem_data_to_file
            cem_client = CEMClient(driver=driver)
        except Exception as ex_c:
            state.log("WARN", f"Chưa khởi tạo được CEMClient: {ex_c}")
            cem_client = None

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
            ticket_id = t.get("ticket_id") or t.get("id_yeu_cau")
            ticket_code = t.get("ma_ccos") or t.get("MaCCOS") or t.get("ticket_code") or ""

            # 0. Kiểm tra kế thừa kết quả tiền kiểm đã có trong DB
            existing_db_row = None
            if not force_recheck:
                try:
                    conn_chk = get_db_connection()
                    if conn_chk:
                        if ticket_id or ticket_code:
                            existing_db_row = conn_chk.execute("""
                                SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary
                                FROM tickets 
                                WHERE ((ticket_id IS NOT NULL AND ticket_id = ?) OR (ticket_code IS NOT NULL AND ticket_code = ?)) 
                                  AND source = 'tts_old_api'
                                ORDER BY updated_at DESC LIMIT 1
                            """, (ticket_id, ticket_code)).fetchone()
                        elif incident_time_str:
                            existing_db_row = conn_chk.execute("""
                                SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary
                                FROM tickets 
                                WHERE phone = ? AND incident_time = ?
                                  AND source = 'tts_old_api'
                                ORDER BY updated_at DESC LIMIT 1
                            """, (phone_84, incident_time_str)).fetchone()
                        conn_chk.close()
                except Exception:
                    pass

            is_reopened = bool(t.get("is_reopened") or (t.get("reopen_count", 0) > 0))
            reopen_count = int(t.get("reopen_count", 0) or (1 if is_reopened else 0))

            can_reuse_db = (
                existing_db_row 
                and existing_db_row["comment"] 
                and _is_valid_technical_status(existing_db_row["status"])
            )

            if can_reuse_db:
                state.log("INFO", f"   ↳ 📋 [{ticket_code or phone_84}] Thuê bao {phone_84} đã có kết quả trong DB: [{existing_db_row['status']}]. Kế thừa hiển thị.")
                reopen_prefix = "Phiếu mở lại, KTV kiểm tra thêm."
                db_comment = str(existing_db_row["comment"] or "").strip()
                if is_reopened:
                    if reopen_prefix not in db_comment:
                        final_comment = f"{reopen_prefix}\n\n{db_comment}" if db_comment else reopen_prefix
                    else:
                        final_comment = db_comment
                else:
                    final_comment = db_comment

                real_pkgs_val = existing_db_row["real_packages"] or "--"
                if "BTools:" in real_pkgs_val and "(max " not in real_pkgs_val and "Không phát sinh" not in real_pkgs_val:
                    num_file = BASE_DIR / "number" / f"{phone_84}.json"
                    if num_file.exists():
                        try:
                            with open(num_file, "r", encoding="utf-8") as jf:
                                j_data = json.load(jf)
                                b_data = j_data.get("btools_technical_data") or j_data.get("data") or []
                                if b_data:
                                    s_btools = extract_btools_packages_summary(b_data)
                                    real_pkgs_val = get_formatted_sapc_packages(phone_84, fallback_btools=s_btools)
                        except Exception:
                            pass

                rec = {
                    "phone": phone_84,
                    "incident_time": inc_time,
                    "package_title": t.get("title", ""),
                    "real_packages": real_pkgs_val,
                    "rat_types": existing_db_row["rat_types"] or "--",
                    "cem_data": existing_db_row["cem_data"] or "--",
                    "app_usage": existing_db_row["app_usage"] or "--",
                    "ticket_content": t.get("content", ""),
                    "status": "⚠️ PHIẾU MỞ LẠI" if is_reopened and not str(existing_db_row["status"]).startswith("⚠️") else existing_db_row["status"],
                    "comment": final_comment,
                    "action_plan": existing_db_row["action_plan"] or ("KTV kiểm tra và xử lý thủ công" if is_reopened else ""),
                    "color": existing_db_row["color"] or "#4CAF50",
                    "ticket_status": "Chưa đóng",
                    "created_time": t.get("created_time") or inc_time,
                    "ai_summary": existing_db_row["ai_summary"] or t.get("content", ""),
                    "source": "tts_old_api",
                    "ticket_code": ticket_code,
                    "ticket_id": ticket_id,
                    "flow_id": str(t.get("id_yeu_cau") or ""),
                    "phan_hoi_he_thong": t.get("phan_hoi_he_thong", 1),
                    "id_he_thong": t.get("id_he_thong", 0),
                    "reopen_count": reopen_count,
                    "last_reopened_date": t.get("last_reopened_date") or "",
                    "closed_by": None
                }
                save_or_update_ticket(rec)
                continue

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

                # Kiểm tra hành vi bổ sung Case 2
                try:
                    from report_bot import get_sapc_package_validity
                    from crawler_btools import fetch_supplementary_btools_if_needed
                    active_pkgs, _ = get_sapc_package_validity(phone_84)
                    commercial_pkgs = [p for p in active_pkgs if not p.get("is_paygo") and not p.get("is_home") and not p.get("is_no_date") and not p.get("is_addon_app")]
                    earliest_reg_dt = min([p["reg_dt"] for p in commercial_pkgs if p.get("reg_dt")], default=None)
                    start_scan_date = (datetime.now() - timedelta(days=4)).date()
                    if earliest_reg_dt and earliest_reg_dt.date() < start_scan_date:
                        clean_btools_data = fetch_supplementary_btools_if_needed(driver, phone_84, clean_btools_data, earliest_reg_dt, start_scan_date)
                except Exception as ex_case2:
                    state.log("WARN", f"Lỗi tra cứu bổ sung Case 2: {ex_case2}")

                # Trích xuất gói cước phát sinh từ BTools kèm max session đưa vào Data Usage (BTools)
                real_pkgs_str = extract_btools_packages_summary(clean_btools_data)
                formatted_packages = get_formatted_sapc_packages(phone_84, fallback_btools=real_pkgs_str)

                # Tra cứu CEM & App Usage
                cem_records = []
                app_events = []
                cem_data_str = "Không có dữ liệu CEM"
                app_usage_str = "Không có dữ liệu App Usage"
                try:
                    if cem_client is None:
                        cem_client = CEMClient(driver=driver)
                    cem_records = cem_client.get_subscriber_history_5days(phone_84, days=5, incident_time_str=inc_time)
                    app_events = cem_client.get_subscriber_app_events(phone_84, days=5, incident_time_str=inc_time)
                    _, _, cem_data_str = CEMClient.extract_two_period_summary(
                        cem_records, incident_time_str=inc_time, app_events=app_events, days=5
                    )
                    app_usage_str = CEMClient.extract_top_apps_summary(app_events)
                    save_cem_data_to_file(phone_84, cem_records, app_events, base_dir=BASE_DIR)
                except Exception as ex_cem:
                    cem_data_str = f"Lỗi CEM: {ex_cem}"

                # 4. Phân loại theo bộ kịch bản
                status_calc, comment_calc, action_plan, _ = analyze_subscriber_status(
                    clean_btools_data, t.get("title", ""), t.get("content", ""),
                    phone_84=phone_84, cem_records=cem_records, app_events=app_events, incident_time_str=inc_time, driver=driver
                )

                cell_desc = info_result.get("Cell ID") or info_result.get("ECGI") or "--"
                rat_type_str = info_result.get("Radio") or "Sóng di động"
                if not cem_records and cell_desc and cell_desc != "--":
                    vpn_suffix = ""
                    if app_events:
                        try:
                            from report_bot import detect_vpn_application
                            vname = detect_vpn_application(app_events)
                            if vname:
                                vpn_suffix = f"\n⚠️ CẢNH BÁO VPN: Phát hiện thiết bị có app {vname}"
                        except Exception:
                            pass
                    cem_data_str = f"Không có dữ liệu CEM (5 ngày) [Cell HSS: {cell_desc}]{vpn_suffix}"

                is_reopened = bool(t.get("is_reopened") or (t.get("reopen_count", 0) > 0))
                reopen_count = int(t.get("reopen_count", 0) or (1 if is_reopened else 0))
                reopen_prefix = "Phiếu mở lại, KTV kiểm tra thêm."
                if is_reopened:
                    if reopen_prefix not in comment_calc:
                        comment_calc = f"{reopen_prefix}\n\n{comment_calc}" if comment_calc else reopen_prefix

                rec = {
                    "phone": phone_84,
                    "incident_time": inc_time,
                    "package_title": t.get("title", ""),
                    "ticket_content": t.get("content", ""),
                    "status": "⚠️ PHIẾU MỞ LẠI" if is_reopened and not status_calc.startswith("⚠️") else status_calc,
                    "real_packages": formatted_packages,
                    "rat_types": rat_type_str,
                    "cem_data": cem_data_str,
                    "app_usage": app_usage_str,
                    "ai_summary": ai_summary if ai_summary else t.get("content", ""),
                    "comment": comment_calc,
                    "action_plan": action_plan,
                    "ticket_status": "Chưa đóng",
                    "source": "tts_old_api",
                    "created_time": t.get("created_time") or inc_time,
                    "ticket_id": t.get("ticket_id"),
                    "flow_id": str(t.get("id_yeu_cau") or ""),
                    "ticket_code": t.get("ma_ccos") or t.get("MaCCOS") or "",
                    "phan_hoi_he_thong": t.get("phan_hoi_he_thong", 1),
                    "id_he_thong": t.get("id_he_thong", 0),
                    "reopen_count": reopen_count,
                    "last_reopened_date": t.get("last_reopened_date") or ""
                }

                # 5. Kiểm tra điều kiện tự động đóng
                norm_status = excel_reader.normalize_text(status_calc)
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

                matched_nguyen_nhan, action_override = excel_reader.get_nguyen_nhan_and_action(check_dict)
                if action_override:
                    action_plan = action_override
                    rec["action_plan"] = action_plan

                can_close = bool(not is_reopened and clean_btools_data is not None and matched_nguyen_nhan and excel_reader.is_level_1_auto_close_candidate(check_dict))

                if is_reopened:
                    state.log("WARN", f"⚠️ Phiếu {phone_84} là phiếu mở lại (reopen_count={reopen_count}). Giữ nguyên 'Chưa đóng' để KTV kiểm tra thủ công!")
                elif clean_btools_data is None:
                    state.log("WARN", f"⚠️ Phiếu {phone_84} lỗi tra cứu BTools (chưa đăng nhập hoặc lỗi máy chủ). Giữ trạng thái 'Chưa đóng' để KTV kiểm tra!")
                elif state.should_auto_close("tts_old") and can_close:
                    state.log("STEP", f"🤖 Thuê bao {phone_84} đủ điều kiện. Đang tự động đóng phiếu...")
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
                        state.total_closed += 1
                        state.log("SUCCESS", close_msg)
                    else:
                        state.log("WARN", f"⚠️ Không thể đóng phiếu {phone_84}: {close_msg}")
                else:
                    state.log("SUCCESS", f"Hoàn tất tiền kiểm: {phone_84} -> {status_calc}")

                save_or_update_ticket(rec)

            except Exception as ex_sub:
                state.log("ERROR", f"Lỗi tiền kiểm tra {phone_84}: {ex_sub}")

        if active_phones:
            sync_active_tickets_state(active_phones, source="tts_old_api", key_type="phone", service_type="data")

        state.log("SUCCESS", f"🎉 Hoàn tất chu kỳ tiền kiểm Mobile Internet TTS Cũ cho {len(data_tickets)} phiếu!")
        return len(data_tickets)

    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "Authorization has been denied" in err_str:
            state.log("WARN", "⚠️ Token TTS Cũ đã hết hạn trên máy chủ OneOSS (401). Đã dọn dẹp cache, vui lòng đăng nhập lại.")
            try:
                from tts_old_api import save_cached_auth
                save_cached_auth("", {})
            except Exception:
                pass
        else:
            state.log("ERROR", f"Lỗi chu kỳ quét TTS Cũ: {e}")
        return 0
    finally:
        state.current_step = "Hoàn tất chu kỳ"
        if not state.is_running:
            state.status = "IDLE"
            state.status_message = "Sẵn sàng"
