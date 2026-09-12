# routers/tickets.py
# Quản lý danh sách phiếu, phân tích thống kê, xuất Excel và các tác vụ đóng phiếu

import os
import sys
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse

from db_manager import (
    get_all_tickets, 
    get_system_counts, 
    get_closed_tickets_analytics, 
    get_db_connection, 
    update_ticket_field, 
    delete_all_tickets,
    is_mobile_internet_ticket
)
from services.state import state
from services.session_manager import ACTIVE_LAN_SESSIONS, resolve_ttsnew_token
from tts_old_api import extract_token_from_browser, fetch_nguyen_nhan_list_api, close_tts_old_ticket_api

BASE_DIR = Path(__file__).resolve().parent.parent
router = APIRouter(prefix="/api", tags=["Quản lý Phiếu Sự Cố (Tickets)"])


@router.get("/tickets")
def get_tickets_api(
    search: str = None, 
    status: str = None, 
    tab: str = None, 
    source: str = "tts_old", 
    service_type: str = "data"
):
    src_f = None if source == "all" else source
    srv_f = None if service_type == "all" else service_type

    tickets = get_all_tickets(
        search=search, 
        status_filter=status, 
        tab_filter=tab, 
        source=src_f, 
        service_type=srv_f
    )
    sys_counts = get_system_counts()
    all_raw = get_all_tickets(source=src_f, service_type=srv_f)
    closed_cnt = sum(1 for t in all_raw if t.get("ticket_status") == "Đã đóng")
    active_cnt = len(all_raw) - closed_cnt

    return {
        "tickets": tickets,
        "total_count": len(all_raw),
        "closed_count": closed_cnt,
        "active_count": active_cnt,
        "system_counts": sys_counts
    }


@router.get("/tickets/closed_stats")
def get_closed_stats_api(
    period: str = "all", 
    source: str = "all", 
    service_type: str = "all"
):
    src_f = None if source == "all" else source
    srv_f = None if service_type == "all" else service_type
    stats = get_closed_tickets_analytics(time_filter=period, source_filter=src_f, service_filter=srv_f)
    return stats


@router.get("/export_excel")
def export_excel_api(source: str = "tts_old"):
    from report_bot import export_diagnostics_to_excel
    src_f = None if source == "all" else source
    tickets = get_all_tickets(source=src_f)
    if not tickets:
        return Response(content="Database trống, chưa có phiếu để xuất Excel.", status_code=400)

    out_dir = BASE_DIR / "result"
    os.makedirs(out_dir, exist_ok=True)
    prefix = "BaoCao_TTS_NEW" if source == "tts_new" else "BaoCao_TTS_OLD"
    out_file = out_dir / f"{prefix}_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    saved_path = export_diagnostics_to_excel(tickets, out_file)

    if os.path.exists(saved_path):
        return FileResponse(
            saved_path, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(saved_path)
        )
    return Response(content="Lỗi xuất file Excel", status_code=500)


@router.post("/tickets/update")
async def update_ticket_api(request: Request):
    body = await request.json()
    phone = body.get("phone")
    incident_time = body.get("incident_time")
    field = body.get("field")
    value = body.get("value")
    if phone and field:
        ok = update_ticket_field(phone, field, value, incident_time=incident_time)
        return {"success": ok}
    return Response(content="Missing phone or field", status_code=400)


@router.post("/tickets/clear")
async def clear_tickets_api(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    source = body.get("source") if body else None
    delete_all_tickets(source=source)
    state.total_scanned = 0
    state.closed_count = 0
    sys_text = "TTS Mới" if source == "tts_new" else ("TTS Cũ" if source == "tts_old" else "toàn bộ")
    state.log("WARN", f"🗑️ ĐÃ XÓA DỮ LIỆU BẢNG TẠM {sys_text.upper()}.")
    return {"success": True}


@router.post("/tts_old_api/close_one")
@router.post("/tickets/close_one")
async def close_one_tts_old_ticket(request: Request):
    body = await request.json()
    phone = body.get("phone")
    incident_time = body.get("incident_time")
    comment_input = body.get("comment")
    action_plan_input = body.get("action_plan")
    if not phone:
        return Response(content="Missing phone", status_code=400)

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM tickets WHERE phone = ? AND incident_time = ?", (phone, incident_time)).fetchone()
    conn.close()

    if not row:
        return {"success": False, "message": f"Không tìm thấy phiếu của SĐT {phone} trong cơ sở dữ liệu."}

    ticket_dict = dict(row)
    if not is_mobile_internet_ticket(ticket_dict.get("package_title")):
        return {
            "success": False,
            "message": "Tuyệt đối không đóng phiếu loại PAKH khác (Thoại/SMS/Gói cước/CVQT) bằng API! Vui lòng bấm 'Đóng thủ công' để xử lý trên giao diện web TTS."
        }

    if not ticket_dict.get("id_yeu_cau") and ticket_dict.get("flow_id"):
        ticket_dict["id_yeu_cau"] = ticket_dict["flow_id"]
    if not ticket_dict.get("ma_ccos") and ticket_dict.get("ticket_code"):
        ticket_dict["ma_ccos"] = ticket_dict["ticket_code"]

    if comment_input is not None:
        update_ticket_field(phone, "comment", comment_input, incident_time=incident_time)
        ticket_dict["comment"] = comment_input
    if action_plan_input is not None:
        update_ticket_field(phone, "action_plan", action_plan_input, incident_time=incident_time)
        ticket_dict["action_plan"] = action_plan_input

    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")

    client_token = (body.get("token") or "").strip()
    client_user_id = body.get("user_id")
    client_user_name = (body.get("user_name") or "").strip()

    token = client_token
    user_id = client_user_id
    user_name = client_user_name

    if not token:
        if client_ip in ACTIVE_LAN_SESSIONS and ACTIVE_LAN_SESSIONS[client_ip].get("token"):
            token = ACTIVE_LAN_SESSIONS[client_ip]["token"]
            u_inf = ACTIVE_LAN_SESSIONS[client_ip].get("user") or {}
            user_id = user_id or u_inf.get("Id") or u_inf.get("id") or 0
            user_name = user_name or u_inf.get("HoTen") or u_inf.get("TaiKhoan") or "Kỹ thuật viên"
        elif is_local:
            token, user_info = extract_token_from_browser()
            if user_info:
                user_id = user_id or user_info.get("Id") or user_info.get("id") or 0
                user_name = user_name or user_info.get("HoTen") or user_info.get("TaiKhoan") or "Quản trị viên"
        else:
            return {"success": False, "message": "Bạn chưa kết nối tài khoản TTS Cũ của mình trên trình duyệt này. Vui lòng bấm vào nút TTS CŨ trên thanh công cụ để đăng nhập trước khi đóng phiếu!"}

    if token and not user_id and client_ip in ACTIVE_LAN_SESSIONS:
        u_inf = ACTIVE_LAN_SESSIONS[client_ip].get("user") or {}
        user_id = user_id or u_inf.get("Id") or u_inf.get("id") or 0
        user_name = user_name or u_inf.get("HoTen") or u_inf.get("TaiKhoan") or "Kỹ thuật viên"

    if not token:
        return {"success": False, "message": "Không tìm thấy token scnntttoken của TTS Cũ. Vui lòng kết nối tài khoản TTS trước."}

    user_name = user_name or "Kỹ thuật viên"
    user_id = user_id or 0
    nguyen_nhan_map = fetch_nguyen_nhan_list_api(token)

    import update_tts.config as tts_config
    import update_tts.excel_reader as excel_reader
    matched_nn, action_override = excel_reader.get_nguyen_nhan_and_action(ticket_dict)

    id_nn = None
    if matched_nn:
        id_nn = nguyen_nhan_map.get(matched_nn.lower()) or nguyen_nhan_map.get(matched_nn)
    if not id_nn:
        id_nn = 1016

    action_text = ticket_dict.get('action_plan', '') or action_override or ''
    full_content = f"{ticket_dict.get('comment', '')}\n{action_text}".strip()
    if not full_content:
        full_content = "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường"

    state.log("STEP", f"Đang gửi request đóng phiếu TTS Cũ cho SĐT {phone} bởi [{user_name}]...")
    ok, msg = close_tts_old_ticket_api(
        ticket=ticket_dict,
        id_nguyen_nhan=id_nn,
        noi_dung=full_content,
        token=token,
        user_id=user_id,
        dry_run=False
    )
    if not ok and ("401" in str(msg) or "Authorization has been denied" in str(msg)):
        fresh_token, fresh_user = extract_token_from_browser()
        if fresh_token and fresh_token != token:
            state.log("INFO", "🔄 Token TTS Cũ đã hết hạn, tự động trích xuất token mới từ trình duyệt và thử lại...")
            token = fresh_token
            if fresh_user:
                user_id = fresh_user.get("Id") or user_id
                user_name = fresh_user.get("HoTen") or fresh_user.get("TaiKhoan") or user_name
            nguyen_nhan_map = fetch_nguyen_nhan_list_api(token)
            if matched_nn:
                id_nn = nguyen_nhan_map.get(matched_nn.lower()) or nguyen_nhan_map.get(matched_nn) or 1016
            ok, msg = close_tts_old_ticket_api(
                ticket=ticket_dict,
                id_nguyen_nhan=id_nn,
                noi_dung=full_content,
                token=token,
                user_id=user_id,
                dry_run=False
            )

    if ok:
        update_ticket_field(phone, "ticket_status", "Đã đóng", incident_time=incident_time)
        update_ticket_field(phone, "closed_by", user_name, incident_time=incident_time)
        state.closed_count += 1
        state.log("SUCCESS", f"✅ [{user_name}] {msg}")
    else:
        state.log("WARN", msg)

    return {
        "success": ok, 
        "message": msg, 
        "closed_by": user_name,
        "token": token,
        "user_id": user_id
    }


@router.post("/ttsnew/open_detail")
async def open_detail_ttsnew_api(request: Request):
    body = await request.json()
    ticket_code = str(body.get("ticket_code") or "").strip()
    phone = str(body.get("phone") or "").strip()

    conn = get_db_connection()
    row = None
    if ticket_code:
        row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id, comment, action_plan FROM tickets WHERE ticket_code = ? OR ticket_code LIKE ?", (ticket_code, f"{ticket_code}%")).fetchone()
    if not row and phone:
        row = conn.execute("SELECT ticket_code, phone, ticket_id, flow_id, comment, action_plan FROM tickets WHERE phone = ? AND source = 'tts_new'", (phone,)).fetchone()
    conn.close()

    ticket_id = row["ticket_id"] if (row and row["ticket_id"]) else None
    flow_id = row["flow_id"] if (row and row["flow_id"]) else None
    code = row["ticket_code"] if (row and row["ticket_code"]) else ticket_code
    clean_code = code.split("\n")[0].strip() if code else ""
    comment_val = str(row["comment"] or "").strip() if (row and "comment" in row.keys()) else ""
    action_plan_val = str(row["action_plan"] or "").strip() if (row and "action_plan" in row.keys()) else ""

    if not ticket_id and clean_code and "/" in clean_code:
        try:
            ticket_id = int(clean_code.split("/")[-1])
        except Exception:
            pass

    if not flow_id:
        try:
            from ttsnew_api import extract_token_from_browser, fetch_active_tickets
            tok = extract_token_from_browser()
            if tok:
                active_t = fetch_active_tickets(tok, limit=1000)
                for at in active_t:
                    tc = at.get("ticketCode")
                    if tc == code or tc == clean_code or (ticket_id and at.get("ticketId") == ticket_id):
                        flow_id = at.get("id")
                        ticket_id = at.get("ticketId")
                        conn_u = get_db_connection()
                        with conn_u:
                            conn_u.execute("UPDATE tickets SET flow_id = ?, ticket_id = ? WHERE ticket_code = ?", (flow_id, ticket_id, code))
                        conn_u.close()
                        break
        except Exception as ex_f:
            state.log("WARN", f"Không tìm thấy flow_id cho {code}: {ex_f}")

    if not flow_id or not ticket_id:
        return {"success": False, "message": f"Không tìm thấy mã luồng (flow_id/ticket_id) của phiếu {code or phone}."}

    state.log("STEP", f"🌐 Đang mở cửa sổ Cập nhật xử lý phiếu {clean_code or code} trên TTS Mới...")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            target_page = None
            for pg in context.pages:
                if "tts.vnptnet.vn" in pg.url:
                    target_page = pg
                    break
            if not target_page:
                target_page = context.new_page()
                target_page.goto("https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu/chi-tiet-phieu-pakh")
                target_page.wait_for_timeout(1000)

            target_page.bring_to_front()
            target_page.evaluate(f"""() => {{
                window.history.pushState({{ ticketFlowId: {flow_id}, ticketId: {ticket_id}, ticketTypeId: 2 }}, '', '/tts/ticket/quan-ly-phieu/chi-tiet-phieu-pakh');
                window.location.reload();
            }}""")

            try:
                btn_cap_nhat = target_page.wait_for_selector('button.p-button-primary:has-text("Cập nhật xử lý")', timeout=10000)
                if btn_cap_nhat:
                    btn_cap_nhat.click()
                    target_page.wait_for_timeout(1200)

                    dialog = target_page.query_selector('.p-dialog:has-text("Cập nhật xử lý")')
                    if dialog:
                        b0_true = dialog.query_selector('p-radiobutton:has-text("True") .p-radiobutton-box')
                        if b0_true:
                            b0_true.click()

                        combined_text = f"{comment_val}\n{action_plan_val}".strip() if (comment_val and action_plan_val) else (comment_val or action_plan_val or "")
                        if combined_text:
                            txt_closing = dialog.query_selector('textarea[name="closingContent"], textarea[formcontrolname="closingContent"]')
                            if txt_closing:
                                txt_closing.fill(combined_text)

                            txt_assign = dialog.query_selector('textarea[name="assignContent"], textarea[formcontrolname="assignContent"]')
                            if txt_assign:
                                txt_assign.fill(combined_text)
            except Exception as ex_modal:
                state.log("WARN", f"Chưa tự động bật được nút Cập nhật xử lý: {ex_modal}")

        state.log("SUCCESS", f"✅ Đã mở cửa sổ Cập nhật xử lý phiếu {clean_code or code} trên TTS Mới!")
        return {
            "success": True, 
            "message": f"Đã mở cửa sổ Cập nhật xử lý phiếu {clean_code or code} trên TTS Mới", 
            "ticket_code": code,
            "ticket_id": ticket_id,
            "flow_id": flow_id
        }
    except Exception as ex_open:
        state.log("WARN", f"⚠️ Lỗi mở tab TTS Mới: {ex_open}")
        return {"success": False, "message": f"Lỗi mở tab TTS Mới: {str(ex_open)}"}


@router.post("/ttsnew/close_one")
async def close_one_ttsnew_ticket(request: Request):
    body = await request.json()
    phone = str(body.get("phone") or "").strip()
    ticket_code = str(body.get("ticket_code") or "").strip()
    comment_custom = str(body.get("comment") or "").strip()
    action_plan_custom = str(body.get("action_plan") or "").strip()

    conn = get_db_connection()
    row = None
    if ticket_code:
        row = conn.execute("SELECT * FROM tickets WHERE ticket_code = ? OR ticket_code LIKE ?", (ticket_code, f"{ticket_code}%")).fetchone()
    if not row and phone:
        row = conn.execute("SELECT * FROM tickets WHERE phone = ? AND source = 'tts_new'", (phone,)).fetchone()
    conn.close()

    ticket_id = row["ticket_id"] if (row and row["ticket_id"]) else None
    flow_id = row["flow_id"] if (row and row["flow_id"]) else None
    code = row["ticket_code"] if (row and row["ticket_code"]) else ticket_code
    clean_code = code.split("\n")[0].strip() if code else ""
    status_val = str(row["status"] or "") if row else ""
    comment_val = comment_custom or (str(row["comment"] or "").strip() if (row and "comment" in row.keys()) else "")
    action_plan_val = action_plan_custom or (str(row["action_plan"] or "").strip() if (row and "action_plan" in row.keys()) else "")

    if row:
        if not is_mobile_internet_ticket(row["package_title"]):
            return {
                "success": False,
                "message": "Tuyệt đối không đóng phiếu loại PAKH khác (Thoại/SMS/Gói cước/CVQT) bằng API! Vui lòng bấm 'Đóng thủ công' để xử lý trên giao diện web TTS."
            }

    reopen_cnt = int(row["reopen_count"] or 0) if (row and "reopen_count" in row.keys()) else 0
    force_close = body.get("force", False)
    if reopen_cnt > 0 and not force_close:
        return {
            "success": False, 
            "is_reopened": True,
            "reopen_count": reopen_cnt,
            "message": f"⚠️ Phiếu này đã mở lại {reopen_cnt} lần (THÔNG TIN MỞ LẠI TTS). Hệ thống chặn tự động đóng. KTV cần xác nhận trước khi đóng thủ công."
        }

    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")
    client_tok = (body.get("token") or "").strip()

    from ttsnew_api import fetch_active_tickets, api_transfer_ttsnew_ticket
    tok, ktv_user = resolve_ttsnew_token(client_ip, is_local, client_tok)
    if not tok:
        return {
            "success": False, 
            "message": "Không tìm thấy phiên xác thực TTS Mới của bạn. Vui lòng bấm vào biểu tượng TTS MỚI trên thanh công cụ để kết nối tài khoản KTV của bạn trước khi đóng phiếu!"
        }

    ktv_name = ktv_user.get("displayName") or ktv_user.get("userName") or "Kỹ thuật viên"
    state.log("STEP", f"Đang gửi yêu cầu xử lý phiếu {clean_code or phone} trên TTS Mới bởi [{ktv_name}] (IP: {client_ip})...")

    try:
        raw_active = fetch_active_tickets(tok, limit=1000)
        for r_it in raw_active:
            if (ticket_id and str(r_it.get("ticketId")) == str(ticket_id)) or \
               (clean_code and str(r_it.get("ticketCode")) == str(clean_code)) or \
               (phone and phone in str(r_it)):
                flow_id = r_it.get("id")
                ticket_id = r_it.get("ticketId")
                break
    except Exception:
        pass

    if not flow_id or not ticket_id:
        return {"success": False, "message": f"Không tìm thấy luồng xử lý (flow_id/ticket_id) của phiếu {clean_code or phone} trên TTS Mới."}

    res_close = api_transfer_ttsnew_ticket(
        token=tok,
        ticket_flow_id=flow_id,
        ticket_id=ticket_id,
        phone=phone or (row["phone"] if row else ""),
        ticket_code=clean_code,
        status=status_val,
        closing_content=comment_val,
        assign_content=action_plan_val
    )
    if not res_close.get("success"):
        err_msg = res_close.get("message", "Lỗi chuyển bước")
        state.log("WARN", f"⚠️ [Phiếu lỗi] Phiếu {clean_code} ({phone}) không đóng được: {err_msg}")
        try:
            conn = get_db_connection()
            target_phone = phone or (row["phone"] if row else "")
            conn.execute("""
                UPDATE tickets 
                SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                WHERE (ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
            """, (f"{clean_code}%", target_phone))
            conn.commit()
            conn.close()
        except Exception:
            pass
    return res_close


@router.post("/ttsnew/close_all")
async def close_all_ttsnew_tickets(request: Request):
    from ttsnew_api import fetch_active_tickets, filter_data_tickets, api_transfer_ttsnew_ticket
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_local = client_ip in ("127.0.0.1", "localhost", "::1")
    body = await request.json()
    client_tok = (body.get("token") or "").strip()
    tok, ktv_user = resolve_ttsnew_token(client_ip, is_local, client_tok)
    if not tok:
        return {
            "success": False, 
            "message": "Không tìm thấy phiên xác thực TTS Mới. Vui lòng kết nối tài khoản KTV của bạn trước khi thực hiện đóng tự động."
        }

    ktv_name = ktv_user.get("displayName") or ktv_user.get("userName") or "KTV"
    def _run_close_all():
        state.log("STEP", f"🚀 Bắt đầu tự động chuyển bước/đóng tất cả phiếu TTS Mới bởi [{ktv_name}]...")
        try:
            raw = fetch_active_tickets(tok, limit=1000)
            data_tickets = filter_data_tickets(raw)
            conn = get_db_connection()
            total_success = 0
            for it in data_tickets:
                flow_id = it.get("id")
                ticket_id = it.get("ticketId")
                ticket_code = it.get("ticketCode")
                row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ? OR ticket_code = ? OR ticket_code LIKE ?", 
                                   (ticket_id, ticket_code, f"{ticket_code}%")).fetchone()
                if row and row["status"]:
                    rc = int(row["reopen_count"] or 0) if "reopen_count" in row.keys() else 0
                    if rc > 0:
                        state.log("WARN", f"   ↳ ⛔ Bỏ qua {ticket_code} ({row['phone']}): Đã mở lại {rc} lần (THÔNG TIN MỞ LẠI TTS) - KHÔNG ĐÓNG TỰ ĐỘNG!")
                        continue

                    from db_manager import check_ticket_can_close
                    can_close, reason = check_ticket_can_close(dict(row))
                    if not can_close:
                        state.log("INFO", f"   ↳ ⏸️ Giữ nguyên {ticket_code} ({row['phone']}): Chưa đủ điều kiện đóng ({reason})")
                        continue

                    res = api_transfer_ttsnew_ticket(
                        token=tok,
                        ticket_flow_id=flow_id,
                        ticket_id=ticket_id,
                        phone=row["phone"],
                        ticket_code=ticket_code,
                        status=row["status"],
                        closing_content=row["comment"] or "",
                        assign_content=row["action_plan"] or ""
                    )
                    if res.get("success"):
                        total_success += 1
                        state.log("SUCCESS", f"   ↳ [{total_success}] {res.get('message')}")
                    else:
                        state.log("WARN", f"   ↳ ⚠️ [Phiếu lỗi] {ticket_code}: {res.get('message')}")
                        try:
                            conn.execute("""
                                UPDATE tickets 
                                SET ticket_status = 'Phiếu lỗi', updated_at = CURRENT_TIMESTAMP 
                                WHERE (ticket_code LIKE ? OR phone = ?) AND source = 'tts_new'
                            """, (f"{ticket_code}%", row["phone"]))
                            conn.commit()
                        except Exception:
                            pass
            conn.close()
            state.log("SUCCESS", f"🎉 Hoàn thành xử lý {total_success}/{len(data_tickets)} phiếu TTS Mới!")
        except Exception as ex_all:
            state.log("ERROR", f"Lỗi khi đóng hàng loạt phiếu TTS Mới: {ex_all}")

    threading.Thread(target=_run_close_all, daemon=True).start()
    return {"success": True, "message": "Đang tiến hành tự động chuyển bước/đóng hàng loạt phiếu TTS Mới..."}


@router.post("/tickets/precheck_one")
async def precheck_one_ticket(request: Request):
    body = await request.json()
    phone = body.get("phone")
    incident_time = body.get("incident_time")
    if not phone:
        return Response(content="Missing phone", status_code=400)

    state.log("STEP", f"⚡ Đang thực hiện tiền kiểm tra nhanh cho thuê bao {phone}...")

    try:
        SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
        if SAPCCHECK_DIR not in sys.path:
            sys.path.insert(0, SAPCCHECK_DIR)
        from sapc_client import SAPCClient
        from msisdn_info import tra_cell_tu_so_dien_thoai
        from converter import convert_sapc_response
        from report_bot import get_formatted_sapc_packages, analyze_subscriber_status
        from auth_extractor import get_chrome_debug_driver
        driver = get_chrome_debug_driver()

        sapc_client = None
        try:
            sapc_client = SAPCClient(driver=driver)
        except Exception:
            try:
                sapc_client = SAPCClient()
            except Exception:
                pass

        info_res = {}
        try:
            info_res = tra_cell_tu_so_dien_thoai(phone, session=sapc_client.session if sapc_client else None)
        except Exception as ex_cell:
            state.log("WARN", f"Lỗi tra cứu Cell/HLR cho {phone}: {ex_cell}")

        sapc_res = {"msisdn": phone, "packages": []}
        try:
            if sapc_client:
                raw_sapc = sapc_client.query(phone)
                sapc_res = convert_sapc_response(raw_sapc)
        except Exception as ex_sapc:
            state.log("WARN", f"Lỗi tra cứu gói cước SAPC cho {phone}: {ex_sapc}")

        out_dir = str(BASE_DIR / "output")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, f"{phone}.json"), "w", encoding="utf-8") as f:
            json.dump({
                **sapc_res,
                "subscriber_info": info_res,
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, f, ensure_ascii=False, indent=4)

        cell_desc = info_res.get("Cell ID") or info_res.get("ECGI") or "--"
        rat = info_res.get("Radio") or "Sóng di động"

        conn = get_db_connection()
        with conn:
            cur = conn.execute("SELECT package_title, ticket_content FROM tickets WHERE phone = ?", (phone,))
            row = cur.fetchone()
            pkg_title = (row[0] if row else "Thoại / SMS") or ""
            t_content = row[1] if row else ""

            num_file = BASE_DIR / "number" / f"{phone}.json"
            existing_clean_data = []
            if num_file.exists():
                try:
                    with open(num_file, "r", encoding="utf-8") as nf:
                        ndata = json.load(nf)
                        existing_clean_data = ndata.get("btools_technical_data") or ndata.get("data") or []
                except Exception:
                    pass

            is_mobile_data = "thoại" not in str(pkg_title).lower() and "sms" not in str(pkg_title).lower()

            if is_mobile_data:
                try:
                    from crawler_btools import extract_btools_single_phone
                    from data_processor import standardize_btools_data
                    today = datetime.today()
                    start_d = (today - timedelta(days=4)).strftime("%Y-%m-%d")
                    end_d = today.strftime("%Y-%m-%d")
                    raw_bt = extract_btools_single_phone(driver, phone, start_d, end_d)
                    if raw_bt:
                        existing_clean_data = standardize_btools_data(raw_bt)
                        with open(num_file, "w", encoding="utf-8") as nf:
                            json.dump({
                                "phone": phone,
                                "package_title": pkg_title,
                                "ticket_content": t_content,
                                "btools_technical_data": existing_clean_data,
                                "data": existing_clean_data
                            }, nf, ensure_ascii=False, indent=2)
                except Exception as ex_bt_pre:
                    state.log("WARN", f"Lỗi cào BTools khi tiền kiểm {phone}: {ex_bt_pre}")

            cfg_p = BASE_DIR / "diagnostic_config.json"
            ex_codes = set()
            if cfg_p.exists():
                try:
                    with open(cfg_p, "r", encoding="utf-8") as cf:
                        ex_codes = set(json.load(cf).get("EXCLUDED_SYSTEM_CODES", []))
                except Exception:
                    pass
            real_pkgs = set()
            for r in (existing_clean_data or []):
                sc = str(r.get("SERVICE_ID_CODE", "") or r.get("SERVICE_ID", "")).strip()
                sn = str(r.get("SERVICE_NAME", "")).strip()
                if sc.lower() and sc.lower() not in ex_codes and sc.lower() not in ("null", "none"):
                    if sn and "gói cước lạ" not in sn.lower() and sn.lower() not in ex_codes and sn.lower() not in ("null", "none"):
                        real_pkgs.add(sn)
                    elif sc.lower() not in ("null", "none"):
                        real_pkgs.add(sc)
            real_pkgs_str = ", ".join(list(real_pkgs)) if real_pkgs else "Không phát sinh gói TM"
            formatted_pkg = get_formatted_sapc_packages(phone, fallback_btools=real_pkgs_str)

            cem_desc = (f"Không có dữ liệu CEM (5 ngày) [Cell HSS: {cell_desc}]" if cell_desc and cell_desc != "--" else "Không có dữ liệu CEM (5 ngày)")
            app_usage_str = "--"
            cem_recs = []
            app_evs = []
            if is_mobile_data:
                try:
                    from cem_client import CEMClient, save_cem_data_to_file
                    cem_client = CEMClient(driver=driver)
                    cem_recs = cem_client.get_subscriber_history_5days(phone, days=5)
                    app_evs = cem_client.get_subscriber_app_events(phone, days=5)
                    if cem_recs:
                        cem_desc = CEMClient.extract_top_cells_summary(cem_recs, app_events=app_evs)
                    else:
                        vpn_suffix = ""
                        if app_evs:
                            try:
                                from report_bot import detect_vpn_application
                                vname = detect_vpn_application(app_evs)
                                if vname:
                                    vpn_suffix = f"\n⚠️ CẢNH BÁO VPN: Phát hiện thiết bị có app {vname}"
                            except Exception:
                                pass
                        cem_desc = (f"Không có dữ liệu CEM (5 ngày) [Cell HSS: {cell_desc}]{vpn_suffix}" if cell_desc and cell_desc != "--" else f"Không có dữ liệu CEM (5 ngày){vpn_suffix}")
                    if app_evs:
                        app_usage_str = CEMClient.extract_top_apps_summary(app_evs)
                    save_cem_data_to_file(phone, cem_recs, app_evs, base_dir=BASE_DIR)
                except Exception as ex_c:
                    state.log("WARN", f"Lỗi tra cứu CEM khi tiền kiểm tra {phone}: {ex_c}")

            if is_mobile_data:
                status_calc, comment_calc, action_calc, _ = analyze_subscriber_status(
                    existing_clean_data, pkg_title, t_content, phone_84=phone,
                    cem_records=cem_recs, app_events=app_evs, incident_time_str=incident_time, driver=driver
                )
            else:
                status_calc = ""
                comment_calc = ""
                action_calc = ""

            conn.execute("""
                UPDATE tickets 
                SET real_packages = ?, 
                    rat_types = ?,
                    cem_data = ?,
                    app_usage = CASE WHEN ? != '--' THEN ? ELSE app_usage END,
                    status = ?,
                    comment = ?,
                    action_plan = ?,
                    updated_at = CURRENT_TIMESTAMP 
                    WHERE phone = ?
            """, (formatted_pkg, rat, cem_desc, app_usage_str, app_usage_str, status_calc, comment_calc, action_calc, phone))
        conn.close()

        state.log("SUCCESS", f"✅ Đã tiền kiểm Core xong cho {phone}: Radio={info_res.get('Radio')}, HSS={info_res.get('HSS Profile')}, IP={info_res.get('IPv4')}, NAM={info_res.get('NAM')}")
        return {"success": True, "formatted_pkg": formatted_pkg, "info": info_res}
    except Exception as ex_pre:
        state.log("WARN", f"⚠️ Lỗi tiền kiểm tra cho {phone}: {ex_pre}")
        return {"success": False, "error": str(ex_pre)}
