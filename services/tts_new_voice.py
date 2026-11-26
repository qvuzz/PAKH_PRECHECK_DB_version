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
        from db_manager import save_or_update_ticket, sync_active_tickets_state, get_db_connection

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

        # Sắp xếp ưu tiên: Quét những phiếu có ngày tiếp nhận cũ nhất trước (FIFO)
        def _parse_ticket_date_sort_key(t: dict):
            raw_val = t.get("created_time") or t.get("incident_time") or t.get("requestDate") or ""
            s = str(raw_val).strip()
            if not s or s in ("--", "null", "None"):
                return datetime.max
            for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(s, fmt)
                except Exception:
                    pass
            import re
            m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
            if m:
                try:
                    d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    return datetime(y, mth, d)
                except Exception:
                    pass
            return datetime.max

        voice_tickets.sort(key=_parse_ticket_date_sort_key)

        if not voice_tickets:
            is_admin_sync = True
            if user_token:
                from services.session_manager import decode_jwt
                from region_detector import is_superadmin
                is_admin_sync = is_superadmin(decode_jwt(user_token))

            if is_admin_sync or t_reg:
                sync_active_tickets_state([], source="tts_new", key_type="ticket_code", service_type=service_type, region=t_reg)

            state.log("WARN", f"ℹ️ Đã quét {total_scanned} phiếu trên TTS Mới nhưng không có phiếu {lbl} nào đang xử lý / cần tiền kiểm lại{f' tại {t_reg}' if t_reg else ''}.", region=t_reg)
            return 0

        state.log("SUCCESS", f"Thu được {len(voice_tickets)} phiếu {lbl} cần xử lý{f' [{t_reg}]' if t_reg else ''} (Quét TTS Mới: {total_scanned}). Đang nạp vào bảng...", region=t_reg)

        # ⚡ IMMEDIATE INGESTION: Lưu ngay toàn bộ phiếu vào Database ở trạng thái 'CHỜ TIỀN KIỂM'
        # Giúp WebApp hiển thị phiếu lên màn hình tức thì trong <0.5s, đồng thời cập nhật ngay hạn bước (deadline)
        try:
            from db_manager import save_tickets_bulk
            init_records = []
            for t in voice_tickets:
                p_84 = normalize_phone_vn(t.get("phone", ""))
                inc_time = str(t.get("incident_time") or t.get("created_time") or "").strip()
                if p_84 and inc_time:
                    init_records.append({
                        "phone": p_84,
                        "incident_time": inc_time,
                        "package_title": t.get("title") or ("Tin nhắn SMS" if service_type == "sms" else "Cuộc gọi Thoại"),
                        "ticket_content": t.get("content") or "",
                        "status": "CHỜ TIỀN KIỂM",
                        "real_packages": "--",
                        "rat_types": "--",
                        "cem_data": "--",
                        "app_usage": "--",
                        "ticket_status": "Chưa đóng",
                        "created_time": t.get("created_time") or "",
                        "source": "tts_new",
                        "ticket_code": t.get("ticket_code") or "",
                        "ticket_id": t.get("ticket_id"),
                        "flow_id": t.get("flow_id"),
                        "reopen_count": t.get("reopen_count") or 0,
                        "last_reopened_date": t.get("last_reopened_date") or "",
                        "region": t.get("region") or t_reg or "MN",
                        "loaded_by": t.get("loaded_by") or "",
                        "deadline_overall": t.get("deadline", "") or t.get("deadline_overall", "")
                    })
            if init_records:
                save_tickets_bulk(init_records)
        except Exception as ex_ingest:
            state.log("WARN", f"Lỗi Immediate Ingestion: {ex_ingest}")

        # Bước 1: Nạp nhanh toàn bộ phiếu vào Database trước (Bảo tồn kết quả cũ nếu đã có)
        active_codes = set()
        conn_check_step1 = get_db_connection()
        # ⚡ TỐI ƯU SIÊU TỐC & AN TOÀN ĐĨA:
        # Nạp trước map các phiếu trong 7 ngày gần đây vào RAM (1 câu query duy nhất < 2ms)
        # Hạn chế quét database, chỉ quét trong thời hạn 1 tuần trở lại
        recent_tickets_map = {}
        try:
            cur_7d = conn_check_step1.execute("""
                SELECT ticket_id, ticket_code, phone, incident_time, status, real_packages, rat_types,
                       cem_data, app_usage, ai_summary, comment, action_plan, color, ticket_status, 
                       flow_id, reopen_count, last_reopened_date, processing_content, region, ward, loaded_by,
                       ccos_attachments, deadline_overall
                FROM tickets
                WHERE (updated_at >= datetime('now', '-7 days') OR created_at >= datetime('now', '-7 days'))
                  AND source = 'tts_new'
            """)
            for r_7d in cur_7d.fetchall():
                if r_7d["ticket_id"]:
                    recent_tickets_map[f"id_{r_7d['ticket_id']}"] = r_7d
                if r_7d["ticket_code"]:
                    c_clean = str(r_7d["ticket_code"]).split("\n")[0].strip()
                    recent_tickets_map[f"code_{c_clean}"] = r_7d
                if r_7d["phone"] and r_7d["incident_time"]:
                    recent_tickets_map[f"pi_{r_7d['phone']}_{r_7d['incident_time']}"] = r_7d
        except Exception as e_map:
            print(f"⚠️ [tts_new_voice] Lỗi nạp cache 7 ngày: {e_map}")

        try:
            for t in voice_tickets:
                phone_84 = normalize_phone_vn(t.get("phone", ""))
                code = str(t.get("ticket_code", "")).strip()
                if code:
                    active_codes.add(code)
                inc_time = str(t.get("incident_time") or t.get("created_time") or "").strip()
                t_content = t.get("content", "")
                t_title = t.get("title", "Thoại / SMS")
                clean_c = (code or "").split("\n")[0].strip()
                t_id = t.get("ticket_id")

                # Kiểm tra xem phiếu đã có trong DB (trong 7 ngày gần đây) chưa
                old_row = None
                if t_id and f"id_{t_id}" in recent_tickets_map:
                    old_row = recent_tickets_map[f"id_{t_id}"]
                elif clean_c and f"code_{clean_c}" in recent_tickets_map:
                    old_row = recent_tickets_map[f"code_{clean_c}"]
                elif phone_84 and inc_time and f"pi_{phone_84}_{inc_time}" in recent_tickets_map:
                    old_row = recent_tickets_map[f"pi_{phone_84}_{inc_time}"]

                has_valid_eval = bool(
                    old_row 
                    and old_row["status"] 
                    and _is_valid_technical_status(old_row["status"])
                    and not force_recheck
                )

                if has_valid_eval:
                    t["_already_evaluated"] = True
                    # 🎯 QUY TẮC TỐI ƯU: Nếu DB đã có phiếu và đã có nhận định hợp lệ -> BỎ QUA TIỀN KIỂM NẶNG!
                    # Đồng bộ hạn bước (deadline) và mã bước nếu OneOSS có cập nhật mới:
                    new_dl = t.get("deadline", "") or t.get("deadline_overall", "")
                    old_dl = old_row["deadline_overall"] if old_row and "deadline_overall" in old_row.keys() else ""
                    old_code = old_row["ticket_code"] if old_row and "ticket_code" in old_row.keys() else ""
                    if (new_dl and new_dl != old_dl) or (code and code != old_code):
                        try:
                            conn_check_step1.execute(
                                "UPDATE tickets SET deadline_overall = COALESCE(NULLIF(?, ''), deadline_overall), ticket_code = COALESCE(NULLIF(?, ''), ticket_code), updated_at = CURRENT_TIMESTAMP WHERE (ticket_id = ? AND ticket_id IS NOT NULL) OR (phone = ? AND incident_time = ?)",
                                (new_dl, code, t_id, phone_84, inc_time)
                            )
                            conn_check_step1.commit()
                        except Exception:
                            pass
                    continue

                t["_already_evaluated"] = False
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
                    "ticket_id": t_id,
                    "flow_id": t.get("flow_id", ""),
                    "reopen_count": int(t.get("reopen_count") or 0),
                    "last_reopened_date": str(t.get("last_reopened_date") or "").strip(),
                    "processing_content": t.get("processing_content", ""),
                    "region": t.get("region"),
                    "ward": t.get("ward", ""),
                    "loaded_by": t.get("loaded_by", ""),
                    "deadline_overall": t.get("deadline", "") or t.get("deadline_overall", "") or (old_row["deadline_overall"] if old_row and "deadline_overall" in old_row.keys() and old_row["deadline_overall"] else "")
                }
                save_or_update_ticket(rec)
        finally:
            conn_check_step1.close()

        # TUYỆT ĐỐI KHÔNG dùng sync_active_tickets_state đóng hàng loạt bằng NOT IN,
        # tránh việc một KTV quét làm đóng oan toàn bộ phiếu của KTV khác trong vùng.
        # Phiếu chỉ được đóng khi KTV bấm nút Đóng hoặc Auto-Close thành công.

        # Đối với Cuộc gọi (call / spam_call): Tự động đồng bộ file đính kèm CCOS cho các phiếu chưa có
        if service_type in ("call", "spam_call"):
            ccos_tickets_to_fetch = []
            for t in voice_tickets:
                p_84 = normalize_phone_vn(t.get("phone", ""))
                c_clean = (str(t.get("ticket_code", "")).split("\n")[0]).strip()
                t_id = t.get("ticket_id")
                old_row = None
                if t_id and f"id_{t_id}" in recent_tickets_map:
                    old_row = recent_tickets_map[f"id_{t_id}"]
                elif c_clean and f"code_{c_clean}" in recent_tickets_map:
                    old_row = recent_tickets_map[f"code_{c_clean}"]
                elif p_84 and t.get("incident_time") and f"pi_{p_84}_{t.get('incident_time')}" in recent_tickets_map:
                    old_row = recent_tickets_map[f"pi_{p_84}_{t.get('incident_time')}"]

                has_ccos = bool(
                    old_row 
                    and old_row.get("ccos_attachments") 
                    and str(old_row["ccos_attachments"]).strip() not in ("", "null", "None", "{}")
                )
                if not has_ccos or force_recheck:
                    ccos_tickets_to_fetch.append((p_84, t_id, c_clean, t.get("incident_time") or t.get("created_time")))

            if ccos_tickets_to_fetch:
                state.log("INFO", f"📎 Đang đồng bộ file đính kèm CCOS cho {len(ccos_tickets_to_fetch)} phiếu {lbl}...", region=t_reg)
                from ccos_client import get_ccos_attachments
                import concurrent.futures

                def _fetch_single_ccos(item):
                    p, tid, tcode, inc = item
                    if not p or state.stop_requested:
                        return
                    try:
                        ccos_info = get_ccos_attachments(p, driver=driver)
                        if ccos_info:
                            ccos_str = json.dumps(ccos_info, ensure_ascii=False)
                            conn_ccos = get_db_connection()
                            try:
                                with conn_ccos:
                                    if tid:
                                        conn_ccos.execute(
                                            "UPDATE tickets SET ccos_attachments = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ? AND source = 'tts_new'",
                                            (ccos_str, tid)
                                        )
                                    elif p and inc:
                                        conn_ccos.execute(
                                            "UPDATE tickets SET ccos_attachments = ?, updated_at = CURRENT_TIMESTAMP WHERE phone = ? AND incident_time = ?",
                                            (ccos_str, p, inc)
                                        )
                            finally:
                                conn_ccos.close()
                            if ccos_info.get("has_file"):
                                f_names = ", ".join([f["name"] for f in ccos_info.get("files", [])])
                                state.log("INFO", f"   📎 [CCOS] Thuê bao {p} có file đính kèm: {f_names}", region=t_reg)
                    except Exception:
                        pass

                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ccos_exec:
                    list(ccos_exec.map(_fetch_single_ccos, ccos_tickets_to_fetch))

            state.log("SUCCESS", f"✅ Đã nạp xong {len(voice_tickets)} phiếu {lbl} lên bảng (Đã đồng bộ file CCOS, Chế độ Tiền kiểm On-Demand từng số).", region=t_reg)
            return len(voice_tickets)

        # 🎯 LỌC DANH SÁCH PHIẾU CẦN TIỀN KIỂM:
        # Nếu không force_recheck: CHỈ TIỀN KIỂM NHỮNG PHIẾU MỚI VỪA NHẬN (chưa có nhận định hợp lệ trong DB).
        # Tất cả các phiếu đã có nhận định được giữ nguyên 100%, không cào lại CDR/Core/CCOS.
        if not force_recheck:
            tickets_to_precheck = [t for t in voice_tickets if not t.get("_already_evaluated")]
        else:
            tickets_to_precheck = list(voice_tickets)

        if not tickets_to_precheck:
            state.log("SUCCESS", f"✅ Đã đồng bộ {len(voice_tickets)} phiếu {lbl}{f' [{t_reg}]' if t_reg else ''} (Tất cả đã có nhận định hợp lệ). Không có phiếu mới cần tiền kiểm.", region=t_reg)
            return len(voice_tickets)

        state.log("INFO", f"⚡ Phát hiện {len(tickets_to_precheck)}/{len(voice_tickets)} phiếu {lbl} mới vừa nhận cần tiền kiểm{f' [{t_reg}]' if t_reg else ''}. Đang tra cứu Core...")

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

        # Bước 2: Tra cứu Core & Profile song song để xử lý các phiếu mới vừa nhận
        import concurrent.futures

        def _process_single_voice_ticket(item_tuple):
            idx, t = item_tuple
            if state.stop_requested:
                return False
            phone_84 = normalize_phone_vn(t.get("phone", ""))
            code = t.get("ticket_code", "")
            inc_time = str(t.get("incident_time") or t.get("created_time") or "").strip()

            state.current_step = f"Tiền kiểm {lbl} {idx}/{len(tickets_to_precheck)}: {phone_84}"
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
                            SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary, ccos_attachments, processing_content
                            FROM tickets 
                            WHERE ticket_id = ? AND source = 'tts_new'
                            ORDER BY updated_at DESC LIMIT 1
                        """, (t_id,)).fetchone()
                    if not existing_db_row and clean_c:
                        existing_db_row = conn_chk.execute("""
                            SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary, ccos_attachments, processing_content
                            FROM tickets 
                            WHERE (ticket_code = ? OR ticket_code LIKE ?) AND source = 'tts_new'
                            ORDER BY updated_at DESC LIMIT 1
                        """, (clean_c, f"{clean_c}%")).fetchone()
                    if not existing_db_row and phone_84 and inc_time:
                        existing_db_row = conn_chk.execute("""
                            SELECT status, comment, action_plan, color, real_packages, rat_types, cem_data, app_usage, ai_summary, ccos_attachments, processing_content
                            FROM tickets 
                            WHERE (phone = ? OR phone LIKE ?) AND incident_time = ? AND source = 'tts_new'
                            ORDER BY updated_at DESC LIMIT 1
                        """, (phone_84, f"%{phone_84[-9:]}%", inc_time)).fetchone()
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

                can_reuse_db = (
                    not force_recheck
                    and existing_db_row 
                    and _is_valid_technical_status(existing_db_row["status"])
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
                    "processing_content": t.get("processing_content") or (existing_db_row["processing_content"] if existing_db_row and "processing_content" in existing_db_row.keys() else "") or eval_res.get("processing_content") or "",
                    "deadline_overall": t.get("deadline", "") or t.get("deadline_overall", "") or (old_row["deadline_overall"] if old_row and "deadline_overall" in old_row.keys() and old_row["deadline_overall"] else "")
                }
                save_or_update_ticket(rec_update)
                if not can_reuse_db:
                    state.log("SUCCESS", f"[{idx}/{len(tickets_to_precheck)}] Đã tiền kiểm mới {lbl}: {phone_84} -> {eval_res.get('status')}")
                return True
            except Exception as e:
                state.log("ERROR", f"Lỗi tiền kiểm {phone_84}: {e}")
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            items = list(enumerate(tickets_to_precheck, 1))
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



