# services/tts_new_voice.py
# Nghiệp vụ: Hệ thống TTS Mới - Thoại / SMS / Gói (Tiền kiểm On-Demand)

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

def _is_valid_technical_status(st):
    if not st:
        return False
    s_u = str(st).strip().upper()
    if "LỖI KẾT NỐI" in s_u or "CHƯA ĐĂNG NHẬP" in s_u or "LỖI MÁY CHỦ" in s_u or "CHƯA PHÂN LOẠI" in s_u or "CHỜ TIỀN KIỂM" in s_u:
        return False
    return True


def execute_ttsnew_voice_cycle(service_type: str = "voice_sms", force_recheck: bool = False, target_region: str = None, user_token: str = None):
    type_labels = {
        "call": "Cuộc gọi",
        "spam_call": "Chặn gọi ngoại mạng",
        "sms": "Tin nhắn",
        "roaming": "Chuyển vùng quốc tế",
        "sim": "Sim / MultiSIM",
        "other": "Gói cước / PA Khác",
        "voice_sms": "Thoại / SMS / Gói"
    }
    lbl = type_labels.get(service_type, "Thoại / SMS")
    t_reg = str(target_region).strip().upper() if target_region and str(target_region).strip().upper() in ("MB", "MN", "MT") else None

    if t_reg:
        state.set_region_status(t_reg, "PROCESSING", f"Đang quét phiếu {lbl} {t_reg}...")
    else:
        state.status = "PROCESSING"
        state.status_message = f"Đang quét phiếu {lbl} TTS Mới..."
    state.current_step = f"Đang lấy danh sách phiếu {lbl} TTS Mới{f' [{t_reg}]' if t_reg else ''}"
    state.log("STEP", f"⚡ Bắt đầu quét danh sách phiếu {lbl} từ TTS Mới{f' [{t_reg}]' if t_reg else ''}...", region=t_reg)

    try:
        from ttsnew_api import get_ttsnew_tickets_for_precheck
        from db_manager import save_or_update_ticket, sync_active_tickets_state

        from auth_extractor import get_chrome_debug_driver
        driver = get_chrome_debug_driver()

        voice_tickets, total_scanned = get_ttsnew_tickets_for_precheck(
            driver=driver, service_type=service_type, token=user_token, target_region=t_reg
        )
        if not voice_tickets:
            voice_tickets = []

        # TỰ ĐỘNG GỘP CÁC PHIẾU CHƯA ĐÓNG TỪ DATABASE NẾU force_recheck HOẶC CÓ PHIẾU LỖI
        try:
            from db_manager import get_all_tickets
            db_unclosed = get_all_tickets(tab_filter="chua_dong", source="tts_new", service_type=service_type, region=t_reg)
            existing_codes = {str(t.get("ticket_code", "")).strip() for t in voice_tickets if t.get("ticket_code")}
            existing_phones = {str(t.get("phone", "")).strip() for t in voice_tickets if t.get("phone")}

            for t_db in (db_unclosed or []):
                p_clean = str(t_db.get("phone") or "").strip()
                c_clean = str(t_db.get("ticket_code") or "").strip()
                st_raw = str(t_db.get("status") or "")
                is_err_status = (not _is_valid_technical_status(st_raw)) or ("LỖI" in st_raw.upper()) or ("CHỜ TIỀN KIỂM" in st_raw.upper())

                if force_recheck or is_err_status:
                    if (c_clean and c_clean not in existing_codes) or (p_clean and p_clean not in existing_phones):
                        voice_tickets.append({
                            "phone": p_clean,
                            "ticket_code": c_clean,
                            "ticket_id": t_db.get("ticket_id"),
                            "flow_id": t_db.get("flow_id"),
                            "title": t_db.get("package_title") or "",
                            "content": t_db.get("ticket_content") or "",
                            "incident_time": t_db.get("incident_time") or "",
                            "created_time": t_db.get("created_time") or "",
                            "reopen_count": t_db.get("reopen_count") or 0,
                            "last_reopened_date": t_db.get("last_reopened_date") or "",
                            "processing_content": t_db.get("processing_content") or "",
                            "region": t_db.get("region") or t_reg or "MN",
                            "loaded_by": t_db.get("loaded_by") or ""
                        })
                        if c_clean:
                            existing_codes.add(c_clean)
                        if p_clean:
                            existing_phones.add(p_clean)
        except Exception as ex_vdb:
            state.log("WARN", f"Lỗi nạp bổ sung phiếu từ DB khi tiền kiểm lại {lbl}: {ex_vdb}")

        if not voice_tickets:
            state.log("WARN", f"ℹ️ Đã quét {total_scanned} phiếu trên TTS Mới nhưng không có phiếu {lbl} nào đang xử lý / cần tiền kiểm lại{f' tại {t_reg}' if t_reg else ''}.", region=t_reg)
            return 0

        state.log("SUCCESS", f"Thu được {len(voice_tickets)} phiếu {lbl} cần xử lý{f' [{t_reg}]' if t_reg else ''} (Quét TTS Mới: {total_scanned}). Đang nạp vào bảng...", region=t_reg)

        # Bước 1: Nạp nhanh toàn bộ phiếu vào Database trước với status CHỜ TIỀN KIỂM
        active_codes = set()
        for t in voice_tickets:
            phone_84 = normalize_phone_vn(t.get("phone", ""))
            code = str(t.get("ticket_code", "")).strip()
            if code:
                active_codes.add(code)
            inc_time = str(t.get("incident_time") or t.get("created_time") or "").strip()
            t_content = t.get("content", "")
            t_title = t.get("title", "Thoại / SMS")
            ai_sum_init = t_content
            try:
                from services.sms_analyzer import is_sms_ticket, generate_sms_ticket_summary
                if service_type == "sms" or is_sms_ticket(t_title, t_content):
                    ai_sum_init = generate_sms_ticket_summary(t_content, inc_time)
            except Exception:
                pass

            rec = {
                "phone": phone_84,
                "incident_time": inc_time,
                "package_title": t_title,
                "ticket_content": t_content,
                "status": "CHỜ TIỀN KIỂM",
                "real_packages": "--",
                "rat_types": "--",
                "cem_data": "--",
                "app_usage": "--",
                "ai_summary": ai_sum_init,
                "comment": "",
                "action_plan": "",
                "ticket_status": "Chưa đóng",
                "force_update_status": True,
                "source": "tts_new",
                "created_time": t.get("created_time", ""),
                "ticket_code": code,
                "ticket_id": t.get("ticket_id"),
                "flow_id": t.get("flow_id", ""),
                "reopen_count": int(t.get("reopen_count") or 0),
                "last_reopened_date": str(t.get("last_reopened_date") or "").strip(),
                "processing_content": t.get("processing_content", ""),
                "region": t.get("region"),
                "ward": t.get("ward", ""),
                "loaded_by": t.get("loaded_by", "")
            }
            save_or_update_ticket(rec)

        is_admin_sync = True
        if user_token:
            from services.session_manager import decode_jwt
            from region_detector import is_superadmin
            is_admin_sync = is_superadmin(decode_jwt(user_token))

        if active_codes and is_admin_sync:
            scanned_regs = {t.get("region") for t in voice_tickets if t.get("region")}
            if scanned_regs:
                for s_reg in scanned_regs:
                    sync_active_tickets_state(active_codes, source="tts_new", key_type="ticket_code", service_type=service_type, region=s_reg)
            else:
                sync_active_tickets_state(active_codes, source="tts_new", key_type="ticket_code", service_type=service_type)

        # Đối với Cuộc gọi (call): Hoàn tất ngay sau khi nạp danh sách phiếu (tiền kiểm On-Demand từng số).
        # Đối với Tin nhắn (sms): Chạy tiếp xuống Bước 2 để tự động bóc tách thực thể và tra cứu CDR SMSC.
        if service_type in ("call", "spam_call"):
            state.log("SUCCESS", f"✅ Đã nạp xong {len(voice_tickets)} phiếu {lbl} lên bảng (Chế độ Tiền kiểm On-Demand từng số).", region=t_reg)
            return len(voice_tickets)

        state.log("INFO", f"✅ Đã nạp xong {len(voice_tickets)} phiếu lên bảng. Đang tiến hành tra cứu Core...")

        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)
        from sapc_client import SAPCClient
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from converter import convert_sapc_response
        from report_bot import get_formatted_sapc_packages, analyze_subscriber_status

        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception:
            sapc_client = None

        from services.voice_precheck import precheck_single_voice_ticket

        # Bước 2: Tra cứu Core & Profile song song để xử lý nhanh toàn bộ danh sách phiếu
        import concurrent.futures

        def _process_single_voice_ticket(item_tuple):
            idx, t = item_tuple
            if state.stop_requested:
                return False
            phone_84 = normalize_phone_vn(t.get("phone", ""))
            code = t.get("ticket_code", "")
            inc_time = str(t.get("incident_time") or t.get("created_time") or "").strip()

            state.current_step = f"Tiền kiểm {lbl} {idx}/{len(voice_tickets)}: {phone_84}"
            try:
                step_name_raw = str(t.get("step_name") or "")
                raw_code_step = f"{step_name_raw} {code}".lower()
                is_step_23 = ("2.3" in raw_code_step) and ("2.4" not in raw_code_step) and ("2.6" not in raw_code_step)
                is_step_26 = ("2.6" in raw_code_step) or (t.get("ticket_status") == "Chờ đóng lần 2")

                default_comment = ""
                default_action_plan = ""

                existing_db_row = None
                try:
                    conn_chk = get_db_connection()
                    t_id = t.get("ticket_id")
                    clean_c = (code or "").split("\n")[0].strip()
                    if t_id:
                        existing_db_row = conn_chk.execute("""
                            SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary, ccos_attachments
                            FROM tickets 
                            WHERE ticket_id = ? AND source = 'tts_new'
                            ORDER BY updated_at DESC LIMIT 1
                        """, (t_id,)).fetchone()
                    if not existing_db_row and clean_c:
                        existing_db_row = conn_chk.execute("""
                            SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary, ccos_attachments
                            FROM tickets 
                            WHERE (ticket_code = ? OR ticket_code LIKE ?) AND source = 'tts_new'
                            ORDER BY updated_at DESC LIMIT 1
                        """, (clean_c, f"{clean_c}%")).fetchone()
                    conn_chk.close()
                except Exception:
                    pass

                def _is_valid_technical_status(st):
                    if not st:
                        return False
                    s_u = str(st).strip().upper()
                    if "LỖI KẾT NỐI" in s_u or "CHƯA ĐĂNG NHẬP" in s_u or "LỖI MÁY CHỦ" in s_u or "CHƯA PHÂN LOẠI" in s_u or "CHỜ TIỀN KIỂM" in s_u:
                        return False
                    return True

                is_sms_target = (service_type == "sms" or any(k in str(t.get("title", "")).lower() for k in ["sms", "tin nhắn", "lỗi gửi tin", "otp"]))
                has_stale_data_pkg = existing_db_row and ("SAPC:" in str(existing_db_row["real_packages"] or "") or "MI_" in str(existing_db_row["real_packages"] or "") or existing_db_row["comment"] == "Chuyển 2.4")

                can_reuse_db = (
                    not force_recheck
                    and existing_db_row 
                    and _is_valid_technical_status(existing_db_row["status"])
                    and not (is_sms_target and has_stale_data_pkg)
                )

                ccos_json_str = ""
                if existing_db_row and "ccos_attachments" in existing_db_row.keys() and existing_db_row["ccos_attachments"]:
                    ccos_json_str = existing_db_row["ccos_attachments"]

                if can_reuse_db:
                    old_sum = existing_db_row["ai_summary"] or ""
                    # Nếu là sự cố Tin nhắn (SMS) mà tóm tắt trong DB lại là định dạng data cũ hoặc rỗng, buộc phải bóc tách lại chuẩn SMS
                    if is_sms_target and ("gói cước sử dụng:" in old_sum.lower() or not old_sum.startswith("1.")):
                        try:
                            from ai_sms_interpreter import generate_sms_ticket_summary
                            old_sum = generate_sms_ticket_summary(t.get("title", "Tin nhắn (SMS)"), t.get("content", ""))
                        except Exception:
                            pass
                    final_comment = existing_db_row["comment"] if existing_db_row["comment"] else default_comment
                    final_plan = existing_db_row["action_plan"] if existing_db_row["action_plan"] else default_action_plan
                    eval_res = {
                        "status": existing_db_row["status"],
                        "color": existing_db_row["color"] or "green",
                        "comment": final_comment,
                        "action_plan": final_plan,
                        "real_packages": existing_db_row["real_packages"] or "--",
                        "rat_types": existing_db_row["rat_types"] or "2G/3G/4G Thoại",
                        "cem_data": existing_db_row["cem_data"] or "--",
                        "ai_summary": old_sum or t.get("content", "")
                    }
                else:
                    eval_res = precheck_single_voice_ticket(
                        phone_84=phone_84, 
                        ticket=t, 
                        sapc_client=sapc_client
                    )
                    final_comment = eval_res.get("comment") or default_comment
                    final_plan = eval_res.get("action_plan") or default_action_plan

                # Tra cứu file đính kèm trên CCOS nếu chưa có hoặc yêu cầu recheck
                if force_recheck or not ccos_json_str or ccos_json_str == "null":
                    try:
                        from ccos_client import get_ccos_attachments
                        ccos_info = get_ccos_attachments(phone_84, driver=driver)
                        if ccos_info:
                            ccos_json_str = json.dumps(ccos_info, ensure_ascii=False)
                            if ccos_info.get("has_file"):
                                f_names = ", ".join([f["name"] for f in ccos_info.get("files", [])])
                                state.log("INFO", f"   📎 [CCOS] Thuê bao {phone_84} có file đính kèm: {f_names}")
                    except Exception as e_ccos:
                        ccos_json_str = json.dumps({"has_file": False, "files": [], "message": f"Lỗi CCOS: {e_ccos}"}, ensure_ascii=False)

                ticket_content = t.get("content", "")
                reopen_count = int(t.get("reopen_count") or 0)
                last_reopened_date = str(t.get("last_reopened_date") or "").strip()

                sms_cdr_str = ""
                if eval_res.get("sms_cdr_summary"):
                    try:
                        sms_cdr_str = json.dumps(eval_res["sms_cdr_summary"], ensure_ascii=False) if isinstance(eval_res["sms_cdr_summary"], dict) else str(eval_res["sms_cdr_summary"])
                    except Exception:
                        sms_cdr_str = ""
                sms_prob = eval_res.get("sms_problem") or eval_res.get("entities", {}).get("problem_title") or ""
                sms_inc_time = eval_res.get("sms_incident_time") or eval_res.get("entities", {}).get("time_range_desc") or ""

                rec_update = {
                    "phone": phone_84,
                    "incident_time": inc_time,
                    "package_title": t.get("title", "Cuộc gọi"),
                    "ticket_content": ticket_content,
                    "status": eval_res.get("status", "MẠNG LƯỚI ĐẢM BẢO"),
                    "color": eval_res.get("color", "green"),
                    "comment": final_comment,
                    "action_plan": final_plan,
                    "real_packages": eval_res.get("real_packages", "--"),
                    "rat_types": eval_res.get("rat_types", "2G/3G/4G Thoại"),
                    "cem_data": eval_res.get("cem_data", "--"),
                    "app_usage": eval_res.get("app_usage", "--"),
                    "ai_summary": eval_res.get("ai_summary", ticket_content),
                    "ticket_status": "Chưa đóng",
                    "force_update_status": True,
                    "source": "tts_new",
                    "ticket_code": code,
                    "ticket_id": t.get("ticket_id"),
                    "flow_id": t.get("flow_id", ""),
                    "reopen_count": reopen_count,
                    "last_reopened_date": last_reopened_date,
                    "ccos_attachments": ccos_json_str,
                    "sms_problem": sms_prob,
                    "sms_incident_time": sms_inc_time,
                    "sms_cdr_summary": sms_cdr_str,
                    "incident_cause": eval_res.get("suggested_cause_code") or eval_res.get("incident_cause") or "",
                    "processing_content": eval_res.get("suggested_conclusion") or eval_res.get("processing_content") or ""
                }
                save_or_update_ticket(rec_update)
                if not can_reuse_db:
                    state.log("SUCCESS", f"[{idx}/{len(voice_tickets)}] Đã tiền kiểm mới {lbl}: {phone_84} -> {eval_res.get('status')}")
                return True
            except Exception as e:
                state.log("ERROR", f"Lỗi tiền kiểm {phone_84}: {e}")
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            items = list(enumerate(voice_tickets, 1))
            futures = [executor.submit(_process_single_voice_ticket, it) for it in items]
            for future in concurrent.futures.as_completed(futures):
                if state.stop_requested:
                    state.log("WARN", "Nhận được yêu cầu dừng.")
                    break

        state.log("SUCCESS", f"🎉 Hoàn tất chu kỳ tiền kiểm {lbl} TTS Mới{f' [{t_reg}]' if t_reg else ''} cho {len(voice_tickets)} phiếu.", region=t_reg)
        return len(voice_tickets)

    except Exception as e:
        err_str = str(e)
        if "401" in err_str or "Unauthorized" in err_str:
            state.log("WARN", f"⚠️ Token TTS Mới đã hết hạn (401){f' [{t_reg}]' if t_reg else ''}. Tạm dừng quét {lbl}, vui lòng bấm 'TTS (mới)' để đăng nhập lại.", region=t_reg)
        else:
            state.log("ERROR", f"Lỗi quét phiếu {lbl} TTS Mới{f' [{t_reg}]' if t_reg else ''}: {e}", region=t_reg)
        return 0
    finally:
        if t_reg:
            state.set_region_status(t_reg, "IDLE", f"Sẵn sàng ({t_reg})")
        else:
            state.status = "IDLE"
            state.status_message = "Đã dừng. Sẵn sàng nhận lệnh."
        state.current_step = f"Sẵn sàng{f' [{t_reg}]' if t_reg else ''}"


# Alias & Helper cycles cho từng module
execute_tts_new_voice_cycle = execute_ttsnew_voice_cycle

def execute_tts_new_call_cycle(force_recheck: bool = False, target_region: str = None, user_token: str = None):
    return execute_ttsnew_voice_cycle(service_type="call", force_recheck=force_recheck, target_region=target_region, user_token=user_token)

def execute_tts_new_spam_call_cycle(force_recheck: bool = False, target_region: str = None, user_token: str = None):
    return execute_ttsnew_voice_cycle(service_type="spam_call", force_recheck=force_recheck, target_region=target_region, user_token=user_token)

def execute_tts_new_sms_cycle(force_recheck: bool = False, target_region: str = None, user_token: str = None):
    return execute_ttsnew_voice_cycle(service_type="sms", force_recheck=force_recheck, target_region=target_region, user_token=user_token)

def execute_tts_new_roaming_cycle(force_recheck: bool = False, target_region: str = None, user_token: str = None):
    return execute_ttsnew_voice_cycle(service_type="roaming", force_recheck=force_recheck, target_region=target_region, user_token=user_token)

def execute_tts_new_sim_cycle(force_recheck: bool = False, target_region: str = None, user_token: str = None):
    return execute_ttsnew_voice_cycle(service_type="sim", force_recheck=force_recheck, target_region=target_region, user_token=user_token)

def execute_tts_new_other_cycle(force_recheck: bool = False, target_region: str = None, user_token: str = None):
    return execute_ttsnew_voice_cycle(service_type="other", force_recheck=force_recheck, target_region=target_region, user_token=user_token)



