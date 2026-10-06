# routers/flow_audit.py
# Module Chuyên Biệt: Rà Soát, Kiểm Tra & Đối Soát Luồng Phiếu OneOSS / CCOS

import os
import sys
import re
import time
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests
from fastapi import APIRouter, HTTPException, Query, Body, BackgroundTasks
from pydantic import BaseModel

import ttsnew_api
from db_manager import get_db_connection

router = APIRouter(prefix="/api/flow-audit", tags=["Flow Audit"])

BASE_DIR = Path(__file__).resolve().parent.parent
ICT = timezone(timedelta(hours=7))


# ==============================================================================
# KHỞI TẠO BẢNG LƯU VẾT ĐỐI SOÁT LUỒNG PHIẾU
# ==============================================================================
def init_flow_audit_db():
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flow_audit_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER UNIQUE,
                ticket_code TEXT,
                phone TEXT,
                flow_id INTEGER,
                request_date TEXT,
                incident_date TEXT,
                oneoss_status INTEGER,
                oneoss_status_name TEXT,
                cl_ticket_status_id INTEGER,
                last_step_name TEXT,
                last_step_user TEXT,
                last_step_time TEXT,
                end_node_time TEXT,
                end_node_closing_date TEXT,
                reopen_count INTEGER DEFAULT 0,
                ccos_id TEXT,
                sla_hours REAL DEFAULT 0,
                error_grade TEXT,
                error_title TEXT,
                error_details TEXT,
                raw_flows_json TEXT,
                raw_ticket_json TEXT,
                audited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ticket_id ON flow_audit_results(ticket_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ticket_code ON flow_audit_results(ticket_code)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_error_grade ON flow_audit_results(error_grade)")
    conn.close()


init_flow_audit_db()


# ==============================================================================
# HÀM BÓC TÁCH & PHÂN TÍCH LUỒNG 1 PHIẾU TỪ ONEOSS
# ==============================================================================
def audit_single_ticket_data(ticket_input: str, token: str = None, flow_id: int = None) -> dict:
    """
    Tra cứu và chẩn đoán chi tiết luồng xử lý của 1 phiếu qua OneOSS API và tickets.db.
    ticket_input có thể là:
      - Mã phiếu: HT/2026/09/04/22942
      - Ticket ID: 22942
      - Số điện thoại: 0838741928 hoặc 84838741928
      - Mã khiếu nại CCOS: 13382914
    """
    input_str = str(ticket_input or "").strip()
    if not input_str:
        return {"success": False, "message": "Chưa nhập thông tin định danh phiếu (Mã phiếu / Ticket ID / SĐT)."}

    if not token:
        token = ttsnew_api.get_cached_token()
        if not token:
            token = ttsnew_api.extract_token_from_browser()
    if not token:
        return {"success": False, "message": "Chưa có phiên làm việc TTS Mới hợp lệ. Vui lòng đăng nhập TTS Mới trên trình duyệt."}

    if not token.startswith("Bearer "):
        token = "Bearer " + token

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": token,
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # 1. Định vị ticket_id & flow_id từ DB hoặc input
    ticket_id = None
    db_row = None

    # Kiểm tra nếu input_str có dạng HT/YYYY/MM/DD/12345
    m_code = re.search(r"/(\d+)$", input_str)
    if m_code:
        ticket_id = int(m_code.group(1))
    elif input_str.isdigit() and len(input_str) <= 7:
        ticket_id = int(input_str)

    # Tra cứu trong database local (tickets và flow_audit_results)
    conn = get_db_connection()
    try:
        if ticket_id:
            db_row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ? ORDER BY updated_at DESC LIMIT 1", (ticket_id,)).fetchone()
        if not db_row:
            db_row = conn.execute("SELECT * FROM tickets WHERE ticket_code LIKE ? ORDER BY updated_at DESC LIMIT 1", (f"%{input_str}%",)).fetchone()
        if not db_row:
            clean_p = "".join(filter(str.isdigit, input_str))
            if clean_p:
                if clean_p.startswith("0") and len(clean_p) == 10:
                    clean_p = "84" + clean_p[1:]
                db_row = conn.execute("SELECT * FROM tickets WHERE phone = ? ORDER BY updated_at DESC LIMIT 1", (clean_p,)).fetchone()
        if not db_row and input_str.isdigit():
            db_row = conn.execute("SELECT * FROM tickets WHERE flow_id = ? ORDER BY updated_at DESC LIMIT 1", (int(input_str),)).fetchone()

        if db_row:
            if not ticket_id and db_row["ticket_id"]:
                ticket_id = int(db_row["ticket_id"])
            if not flow_id and db_row["flow_id"]:
                flow_id = int(db_row["flow_id"])

        # Tra cứu thêm trong tts_new_stages nếu chưa có flow_id
        if ticket_id or db_row:
            p_val = db_row["phone"] if db_row else input_str
            stage_row = conn.execute("SELECT * FROM tts_new_stages WHERE phone = ? OR ticket_code LIKE ? LIMIT 1", (p_val, f"%{input_str}%")).fetchone()
            if stage_row and not flow_id:
                flow_id = stage_row["round2_flow_id"] or stage_row["round1_flow_id"]

        # Tra cứu từ bảng flow_audit_results nếu đã từng audit
        if not flow_id and ticket_id:
            fa_row = conn.execute("SELECT flow_id FROM flow_audit_results WHERE ticket_id = ? AND flow_id IS NOT NULL", (ticket_id,)).fetchone()
            if fa_row and fa_row["flow_id"]:
                flow_id = int(fa_row["flow_id"])
    finally:
        conn.close()

    # 2. Lấy dữ liệu master ticket từ OneOSS Gateway
    ticket_data = {}
    if ticket_id:
        try:
            url_edit = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/get-editable-ticket/{ticket_id}"
            r_edit = requests.get(url_edit, headers=headers, timeout=12)
            if r_edit.status_code == 200:
                res_j = r_edit.json()
                if not res_j.get("isError") and res_j.get("data"):
                    ticket_data = res_j["data"]
        except Exception as ex_edit:
            print(f"[Flow Audit] Lỗi get-editable-ticket/{ticket_id}: {ex_edit}")

    # Nếu chưa có flow_id, thử tìm trong active tickets của OneOSS
    if not flow_id and ticket_id:
        try:
            active_list = ttsnew_api.fetch_active_tickets(token, limit=1000)
            for it in active_list:
                if str(it.get("ticketId")) == str(ticket_id) or str(ticket_id) in str(it.get("ticketCode", "")):
                    flow_id = it.get("id")
                    break
        except Exception:
            pass

    # 2b. Nếu vẫn chưa có flow_id, tự động truy tìm ticketFlowId từ OneOSS tra-cuu-tien-trinh-xu-ly-phieu theo ngày
    if not flow_id and ticket_id and ticket_data:
        req_d = str(ticket_data.get("requestDate") or ticket_data.get("incidentDate") or "").strip()
        dmy = ""
        if req_d:
            if "/" in req_d[:10]:
                dmy = req_d[:10]
            elif "-" in req_d[:10]:
                parts = req_d[:10].split("-")
                if len(parts) == 3:
                    dmy = f"{parts[2]}/{parts[1]}/{parts[0]}"
        if dmy:
            try:
                search_url = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/tra-cuu-tien-trinh-xu-ly-phieu"
                payload = {
                    "limit": 500,
                    "offset": 0,
                    "loaiPhieu": 2,
                    "tuNgay": dmy,
                    "denNgay": dmy
                }
                r_s = requests.post(search_url, json=payload, headers=headers, timeout=12)
                if r_s.status_code == 200:
                    data_items = r_s.json().get("data", [])
                    t_code_str = str(ticket_data.get("ticketCode") or ticket_id)
                    phone_str = str(ticket_data.get("customerPhone") or "")
                    for it in data_items:
                        it_maphieu = str(it.get("maPhieu") or "")
                        it_phone = str(it.get("soThueBao") or it.get("soDienTHoai") or "")
                        if (str(ticket_id) in it_maphieu) or (t_code_str and t_code_str in it_maphieu) or (phone_str and phone_str in it_phone):
                            cand_flow = it.get("ticketFlowId") or it.get("id")
                            if cand_flow:
                                flow_id = int(cand_flow)
                                break
            except Exception as ex_search:
                print(f"[Flow Audit] Lỗi tra cứu ticketFlowId tự động: {ex_search}")

    # 3. Lấy lịch sử các bước (get-history-request-process)
    history_data = {}
    steps = []
    ticket_flows = []
    if flow_id:
        try:
            url_hist = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/get-history-request-process?ticketFlowId={flow_id}"
            r_h = requests.get(url_hist, headers=headers, timeout=15)
            if r_h.status_code == 200:
                j_h = r_h.json()
                if not j_h.get("isError") and j_h.get("data"):
                    history_data = j_h["data"]
                    steps = history_data.get("steps") or []
                    ticket_flows = history_data.get("ticketFlows") or []
        except Exception as ex_hist:
            print(f"[Flow Audit] Lỗi get-history-request-process flow {flow_id}: {ex_hist}")

    # Nếu ticket_data chưa có nhưng history_data có, bổ sung từ history_data
    if not ticket_data and history_data:
        ticket_data = {
            "ticketId": history_data.get("ticketId") or ticket_id,
            "ticketCode": history_data.get("code"),
            "title": history_data.get("subject"),
            "content": history_data.get("content"),
            "requestDate": history_data.get("incidentDate"),
            "customerPhone": history_data.get("customerPhone"),
            "customerName": history_data.get("customerName"),
            "address": history_data.get("address"),
            "provinceName": history_data.get("provinceName"),
            "wardName": history_data.get("wardName"),
            "khieuNaiId": history_data.get("khieuNaiId") or history_data.get("problemId"),
            "dataSource": history_data.get("dataSource")
        }

    ticket_code_val = ticket_data.get("ticketCode") or (db_row["ticket_code"] if db_row else input_str)
    t_id_val = ticket_data.get("ticketId") or ticket_id or (db_row["ticket_id"] if db_row else None)

    # 4. CHẨN ĐOÁN LỖI LUỒNG BẰNG THUẬT TOÁN ĐỐI SOÁT
    diagnostic = analyze_ticket_flow(
        ticket_data=ticket_data,
        history_data=history_data,
        ticket_flows=ticket_flows,
        db_row=dict(db_row) if db_row else None
    )

    # 5. Lưu kết quả vào DB flow_audit_results
    if t_id_val:
        save_audit_result_to_db(
            ticket_id=t_id_val,
            ticket_code=ticket_code_val,
            phone=ticket_data.get("customerPhone") or (db_row["phone"] if db_row else ""),
            flow_id=flow_id,
            ticket_data=ticket_data,
            history_data=history_data,
            ticket_flows=ticket_flows,
            diagnostic=diagnostic
        )

    return {
        "success": True,
        "ticket_id": t_id_val,
        "ticket_code": ticket_code_val,
        "phone": ticket_data.get("customerPhone") or (db_row["phone"] if db_row else ""),
        "customer_name": ticket_data.get("customerName") or "--",
        "flow_id": flow_id,
        "master_ticket": ticket_data,
        "history": history_data,
        "ticket_flows": ticket_flows,
        "steps_count": len(ticket_flows),
        "db_info": dict(db_row) if db_row else None,
        "diagnostic": diagnostic
    }


def detect_tts_process_and_service(ticket_data: dict, history_data: dict, ticket_flows: list, db_row: dict = None) -> dict:
    """
    Tự động học và nhận diện quy trình nghiệp vụ ẩn trên OneOSS TTS:
    - Mobile Internet (Data)
    - Dịch vụ Tin nhắn (SMS)
    - Dịch vụ Thoại (Voice)
    - Dịch vụ Roaming (Chuyển vùng quốc tế)
    - Kỹ thuật Vô tuyến / Trạm phát sóng / Đo kiểm hiện trường (RF/BTS/CLM)
    - Cố định Băng rộng (MegaWAN / FiberVNN / MyTV)
    - Phân quyền tổ SOC (SOC1, SOC2, SOC3)
    """
    raw_proc = (
        ticket_data.get("processDefinitionName") or
        (history_data.get("processDefinitionName") if history_data else "") or
        ticket_data.get("flowName") or
        (history_data.get("flowName") if history_data else "") or
        ""
    )
    all_node_names = " ".join([str(f.get("processNodeName") or "") for f in ticket_flows])
    subject = str(ticket_data.get("title") or (history_data.get("subject") if history_data else "") or "")
    content = str(ticket_data.get("content") or (history_data.get("content") if history_data else "") or (db_row.get("ticket_content") if db_row else "") or "")
    combined_text = f"{raw_proc} {all_node_names} {subject} {content}".lower()

    # Nhận diện dịch vụ chính & quy trình
    service_type = "Data Di động"
    process_name = raw_proc or "Quy trình Chất lượng mạng & Dịch vụ di động"
    handling_unit = "SOC Kỹ thuật"

    # 1. Nhận diện SMS
    if "sms" in combined_text or "tin nhắn" in combined_text:
        service_type = "Dịch vụ SMS"
        if not raw_proc or "chất lượng mạng" in raw_proc.lower():
            process_name = "Quy trình Xử lý PAKH dịch vụ SMS"

    # 2. Nhận diện Thoại
    elif "thoại" in combined_text or "voice" in combined_text or "cuộc gọi" in combined_text:
        service_type = "Dịch vụ Thoại"
        if not raw_proc or "chất lượng mạng" in raw_proc.lower():
            process_name = "Quy trình Xử lý PAKH dịch vụ Thoại"

    # 3. Nhận diện Roaming
    elif "roaming" in combined_text or "cvqt" in combined_text or "chuyển vùng" in combined_text:
        service_type = "Roaming Quốc tế"
        process_name = "Quy trình PAKH Dịch vụ Roaming Outbound"

    # 4. Nhận diện Đo kiểm Hiện trường / Tối ưu trạm BTS / RF (Node 3.x, 5.x)
    elif any(k in all_node_names for k in ["3.10", "3.11", "3.12", "3.13", "5.1", "5.2", "Đo kiểm", "co DD"]):
        service_type = "Đo kiểm Vô tuyến (RF/BTS)"
        process_name = "Quy trình Phối hợp Đo kiểm Hiện trường & Kỹ thuật Mạng lưới"

    # 5. Nhận diện Cố định Băng rộng / Mega / Fiber
    elif any(k in combined_text for k in ["fibervnn", "mytv", "megawan", "băng rộng cố định", "cố định"]):
        service_type = "Cố định Băng rộng"
        process_name = "Quy trình Xử lý Băng rộng Cố định & Truyền hình"

    # Nhận diện tổ SOC
    if "soc1" in combined_text:
        handling_unit = "SOC1"
    elif "soc2" in combined_text:
        handling_unit = "SOC2"
    elif "soc3" in combined_text:
        handling_unit = "SOC3"
    elif "hiện trường" in combined_text or "đo kiểm" in combined_text:
        handling_unit = "Đội Đo kiểm / Đài trạm"

    return {
        "service_type": service_type,
        "process_name": process_name,
        "handling_unit": handling_unit,
        "is_field_measurement": service_type == "Đo kiểm Vô tuyến (RF/BTS)"
    }



def parse_flow_date(dt_val):
    """Phân tích chuỗi ngày giờ từ API OneOSS thành datetime an toàn."""
    if not dt_val:
        return None
    s = str(dt_val).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s[:26], fmt)
        except Exception:
            pass
    return None


def calc_business_hours_excluding_weekend(start_dt: datetime, end_dt: datetime) -> float:
    """
    Tính tổng số giờ giữa start_dt và end_dt, loại trừ hoàn toàn các ngày Thứ Bảy và Chủ Nhật.
    (Không tính T7, CN - 48 giờ làm việc tương đương 2 ngày làm việc theo yêu cầu nghiệp vụ).
    """
    if not start_dt or not end_dt or end_dt <= start_dt:
        return 0.0

    cur_d = start_dt.date()
    end_d = end_dt.date()
    total_seconds = 0.0

    if cur_d == end_d:
        if cur_d.weekday() < 5:  # Thứ 2 đến Thứ 6 (0, 1, 2, 3, 4)
            total_seconds = (end_dt - start_dt).total_seconds()
    else:
        # 1. Ngày đầu tiên
        if cur_d.weekday() < 5:
            end_of_start_day = datetime(cur_d.year, cur_d.month, cur_d.day) + timedelta(days=1)
            total_seconds += (end_of_start_day - start_dt).total_seconds()

        # 2. Các ngày trung gian nguyên vẹn
        cur_d += timedelta(days=1)
        while cur_d < end_d:
            if cur_d.weekday() < 5:
                total_seconds += 86400.0  # 24 giờ làm việc
            cur_d += timedelta(days=1)

        # 3. Ngày kết thúc
        if end_d.weekday() < 5:
            start_of_end_day = datetime(end_d.year, end_d.month, end_d.day)
            total_seconds += (end_dt - start_of_end_day).total_seconds()

    return round(total_seconds / 3600.0, 1)


def analyze_ticket_flow(ticket_data: dict, history_data: dict, ticket_flows: list, db_row: dict = None) -> dict:
    """
    Phân tích toàn diện luồng quy trình để phát hiện các mẫu lỗi kỹ thuật luồng trên OneOSS.
    Tuân thủ quy chuẩn:
    - HEALTHY: Phiếu đã đóng hoàn tất thành công trên OneOSS không có lỗi tắc nghẽn luồng.
    - CRITICAL: Lỗi hệ thống khiến phiếu bị kẹt cứng hoặc treo quá hạn oan trên CCOS.
    - WARNING: Lỗi luân chuyển hoặc lệch trạng thái cần rà soát.
    - INFO: Thông tin quy trình, dịch vụ, số giờ SLA và số lần Reopen.
    """
    issues = []
    grade = "HEALTHY"
    title = "Luồng quy trình hoàn tất hợp lệ"

    # 1. Tự động nhận diện quy trình và dịch vụ thực tế trên TTS
    proc_info = detect_tts_process_and_service(ticket_data, history_data, ticket_flows, db_row)
    service_type = proc_info["service_type"]
    process_name = proc_info["process_name"]
    handling_unit = proc_info["handling_unit"]

    ticket_data = ticket_data or {}
    history_data = history_data or {}

    req_date_str = ticket_data.get("requestDate") or history_data.get("createdDate") or ""
    reopen_count = history_data.get("reopenCount") or ticket_data.get("reopenCount") or 0
    cl_status_id = ticket_data.get("clTicketStatusId")
    status_name = ticket_data.get("statusName") or ""
    ccos_id = ticket_data.get("khieuNaiId") or ticket_data.get("problemId") or history_data.get("khieuNaiId")

    # 2. Tính toán thời gian SLA theo từng bước và toàn trình (loại trừ T7, CN)
    start_dt = parse_flow_date(req_date_str)

    last_flow = ticket_flows[-1] if ticket_flows else {}
    last_flow_name = str(last_flow.get("processNodeName") or "")
    last_flow_user = str(last_flow.get("receivedUserName") or "")
    last_flow_created = last_flow.get("createdDate")
    last_flow_closing = last_flow.get("closingDate")

    end_dt = datetime.now()
    if last_flow_closing:
        end_dt = parse_flow_date(last_flow_closing) or end_dt
    elif last_flow_created and last_flow_name == "Kết thúc":
        end_dt = parse_flow_date(last_flow_created) or end_dt

    # Mốc thời gian của BƯỚC HIỆN TẠI (loại trừ Thứ 7, Chủ Nhật)
    step_start_dt = parse_flow_date(last_flow_created) or start_dt
    step_end_dt = end_dt
    step_sla_hours = calc_business_hours_excluding_weekend(step_start_dt, step_end_dt) if step_start_dt else 0.0

    # Tổng thời gian toàn trình (loại trừ Thứ 7, Chủ Nhật)
    total_sla_hours = calc_business_hours_excluding_weekend(start_dt, end_dt) if start_dt else step_sla_hours

    # 3. Nhận diện trạng thái đã đóng hoàn tất trên OneOSS
    status_name_lower = str(status_name or "").strip().lower()
    is_closed_oneoss = (
        status_name_lower in ("đã đóng", "da dong", "hoàn thành", "hoan thanh", "đã xử lý", "da xu ly", "closed", "completed") or
        cl_status_id in (3, 100, 4, 5) or
        ticket_data.get("status") in (3, 100) or
        (last_flow_closing and last_flow_name in ("Kết thúc", "2.6 Đóng phiếu Trên TTS"))
    )

    # 3b. Nhận diện trạng thái đã đóng trên CCOS (Tổng đài / Phía khách hàng)
    is_closed_ccos = (
        bool(ticket_data.get("customerCompletionDate")) or
        (db_row and db_row.get("ticket_status") in ("Đã đóng", "Da dong", "Hoàn thành")) or
        (db_row and bool(db_row.get("closed_at"))) or
        (is_closed_oneoss) or
        any("đóng phiếu" in str(f.get("processNodeName") or "").lower() and f.get("closingDate") for f in ticket_flows)
    )

    # =========================================================================
    # LỖI 1: TREO Ở NODE "KẾT THÚC" TRÊN ONEOSS (Rất phổ biến trên TTS Mới)
    # Phiếu đã chuyển sang bước Kết thúc nhưng closingDate = null VÀ clTicketStatusId = 2
    # NẾU TRÊN CCOS ĐÃ ĐÓNG: Chỉ cảnh báo WARNING (vì CCOS đã dừng tính SLA).
    # NẾU TRÊN CCOS CHƯA ĐÓNG: Báo lỗi nghiêm trọng CRITICAL (vì trôi giờ oan).
    # =========================================================================
    has_end_node = any(str(f.get("processNodeName") or "") == "Kết thúc" for f in ticket_flows)
    if has_end_node:
        end_flow = next((f for f in reversed(ticket_flows) if str(f.get("processNodeName") or "") == "Kết thúc"), None)
        if end_flow and not end_flow.get("closingDate") and not is_closed_oneoss:
            if is_closed_ccos:
                issues.append({
                    "code": "HANG_END_NODE",
                    "severity": "WARNING",
                    "name": "Treo node Kết thúc trên OneOSS (Trên CCOS đã đóng hoàn tất)",
                    "description": f"Phiếu đã được ghi nhận đóng hoàn tất trên CCOS (hoặc KTV đã hoàn tất bước đóng kỹ thuật), nhưng luồng OneOSS còn giữ node 'Kết thúc' (Flow ID: {end_flow.get('id')}) chưa cập nhật closingDate hoặc chưa đổi clTicketStatusId sang hoàn thành. CCOS đã dừng tính SLA nên không ảnh hưởng đến tiến độ khách hàng.",
                    "recommendation": "Báo Admin OneOSS đồng bộ trigger hoàn tất luồng hoặc bỏ qua vì CCOS đã đóng thành công."
                })
                if grade == "HEALTHY":
                    grade = "WARNING"
                    title = "Lệch node Kết thúc OneOSS (CCOS đã đóng)"
            else:
                issues.append({
                    "code": "HANG_END_NODE",
                    "severity": "CRITICAL",
                    "name": "Treo node Kết thúc & Không đồng bộ CCOS",
                    "description": f"Phiếu đã hoàn tất bước đóng và chuyển sang node 'Kết thúc' (Flow ID: {end_flow.get('id')}), nhưng OneOSS chưa cập nhật closingDate và chưa đổi trạng thái phiếu sang Hoàn thành (clTicketStatusId hiện vẫn là {cl_status_id}). Kết quả xử lý không được tự động bắn về CCOS (Mã CCOS: {ccos_id or '--'}), khiến CCOS tiếp tục tính trôi thời gian và báo quá hạn.",
                    "recommendation": "Cần cập nhật đóng thủ công trên CCOS theo mốc thời gian hoàn tất tại bước đóng kỹ thuật, đồng thời báo Admin OneOSS cập nhật trigger hoàn tất luồng."
                })
                grade = "CRITICAL"
                title = "Lỗi OneOSS treo node Kết thúc & Không đồng bộ CCOS"

    # =========================================================================
    # LỖI 2: KẸT CỨNG HOẶC VĂNG NGƯỢC LUỒNG VỀ BƯỚC "2.1 PHÂN LOẠI"
    # Chỉ áp dụng khi phiếu ĐANG TỒN CHƯA ĐÓNG
    # =========================================================================
    if "2.1" in last_flow_name and not is_closed_oneoss:
        # Kiểm tra xem trước đó đã từng có bước đóng phiếu (2.6 hoặc closingDate) chưa
        has_closed_earlier = any(
            ("đóng phiếu" in str(f.get("processNodeName") or "").lower() or "2.6" in str(f.get("processNodeName") or ""))
            and f.get("closingDate")
            for f in ticket_flows[:-1]
        )
        if has_closed_earlier:
            issues.append({
                "code": "LOOP_BACK_STEP_2_1",
                "severity": "CRITICAL",
                "name": "Văng ngược luồng về 2.1 sau khi KTV đã đóng phiếu",
                "description": f"KTV đã thực hiện bấm đóng hoàn tất tại bước đóng kỹ thuật, nhưng cấu hình BPMN OneOSS bị lỗi rẽ nhánh khiến phiếu bị văng ngược về bước '2.1 Phân loại' và kẹt lại tại đây.",
                "recommendation": "Báo Quản trị BPMN OneOSS điều chỉnh luồng hoặc cập nhật hoàn tất vì KTV đã xử lý đóng hoàn tất."
            })
            grade = "CRITICAL"
            title = "Lỗi BPMN OneOSS văng ngược về 2.1 sau khi đóng"
        else:
            issues.append({
                "code": "STUCK_STEP_2_1",
                "severity": "CRITICAL",
                "name": "Kẹt cứng tại bước 2.1 Phân loại (Dead-lock BPMN)",
                "description": f"Phiếu đang dừng ở bước '2.1 Phân loại' của quy trình '{process_name}'. Cấu hình BPMN OneOSS tại bước này thiếu transition rẽ nhánh sang bước nội bộ SOC, khiến KTV không thể thao tác đóng hoặc xử lý tại SOC.",
                "recommendation": "Báo Admin OneOSS bổ sung nhánh rẽ BPMN từ 2.1 sang bước xử lý kỹ thuật tiếp theo, hoặc điều chuyển thủ công sang bước xử lý tiếp theo."
            })
            grade = "CRITICAL"
            title = "Kẹt cứng tại bước 2.1 Phân loại (Dead-lock BPMN)"

    # =========================================================================
    # BƯỚC 2.6: PHIẾU ĐANG CHỜ KTV ĐÓNG (Không phải lỗi hệ thống / không phải lỗi treo)
    # Phiếu đang dừng ở bước 2.6 Đóng phiếu Trên TTS do KTV đang giữ xử lý và chưa bấm đóng.
    # - Nếu thời gian SLA > 48h: Quá hạn SLA CCOS (KTV chưa kịp đóng).
    # - Nếu thời gian SLA <= 48h: Tiến trình bình thường trong hạn.
    # =========================================================================
    is_at_closing_step = ("2.6" in last_flow_name or "đóng phiếu" in last_flow_name.lower())
    if is_at_closing_step and not is_closed_oneoss and not last_flow_closing:
        is_overdue = step_sla_hours > 48.0
        issues.append({
            "code": "WAITING_KTV_CLOSE",
            "severity": "WARNING" if is_overdue else "INFO",
            "name": f"Phiếu đang chờ KTV đóng tại bước {last_flow_name}",
            "description": f"Phiếu đang dừng ở bước '{last_flow_name}' ({last_flow_user or 'KTV phụ trách'}) được {step_sla_hours} giờ làm việc (đã trừ Thứ 7, Chủ Nhật). KTV đang giữ phiếu xử lý kỹ thuật và chưa thực hiện bấm nút đóng hoàn tất trên hệ thống.",
            "recommendation": f"KTV kiểm tra nội dung kỹ thuật và thực hiện bấm 'Đóng phiếu' trên TTS Mới."
        })
        if is_overdue and grade == "HEALTHY":
            grade = "WARNING"
            title = f"Phiếu chờ KTV đóng quá hạn bước ({step_sla_hours}h làm việc - trừ T7/CN)"
        elif grade == "HEALTHY":
            title = f"Đang chờ KTV đóng ({last_flow_name})"

    # =========================================================================
    # LỖI 4: LỆCH TRẠNG THÁI LOCAL DB VỚI ONEOSS
    # Không áp dụng cho các phiếu đang ở bước đo kiểm hiện trường (5.1, 5.2, 3.11)
    # vì đây là tiến trình kỹ thuật mạng lưới thực tế đang diễn ra.
    # =========================================================================
    is_field_step = any(k in last_flow_name for k in ["3.10", "3.11", "3.12", "3.13", "5.1", "5.2", "Đo kiểm", "chất lượng"])
    db_closed = db_row and db_row.get("ticket_status") in ("Đã đóng", "Da dong")
    if db_closed and not is_closed_oneoss and not has_end_node and not is_field_step:
        issues.append({
            "code": "STATUS_DESYNC",
            "severity": "WARNING",
            "name": "Lệch trạng thái giữa Cơ sở dữ liệu và OneOSS Gateway",
            "description": f"Trong database hệ thống ghi nhận trạng thái '{db_row.get('ticket_status')}' nhưng trên OneOSS Gateway trạng thái vẫn là '{status_name}' (clTicketStatusId: {cl_status_id}).",
            "recommendation": "Kiểm tra lại kết quả API đóng phiếu trên OneOSS để đồng bộ trạng thái."
        })
        if grade == "HEALTHY":
            grade = "WARNING"
            title = "Lệch trạng thái giữa CSDL và OneOSS"

    # =========================================================================
    # LỖI 5: KẸT DỞ DANG Ở BƯỚC TRUNG GIAN QUÁ HẠN (Phiếu CHƯA ĐÓNG)
    # Tiêu chí: Dừng tại bước hiện tại > 48 giờ làm việc (không tính T7, CN).
    # Không áp dụng cho các bước kỹ thuật đo kiểm hiện trường / xử lý chất lượng vô tuyến.
    # =========================================================================
    if not is_closed_oneoss and grade == "HEALTHY":
        is_field_step = any(k in last_flow_name for k in ["3.10", "3.11", "3.12", "3.13", "5.1", "5.2", "Đo kiểm", "chất lượng"])
        if is_field_step or proc_info.get("is_field_measurement"):
            issues.append({
                "code": "FIELD_MEASUREMENT_IN_PROGRESS",
                "severity": "INFO",
                "name": f"Đang đo kiểm / xử lý chất lượng kỹ thuật ({last_flow_name})",
                "description": f"Phiếu đang trong tiến trình đo kiểm hiện trường hoặc xử lý kỹ thuật vô tuyến tại bước '{last_flow_name}'.",
                "recommendation": "Tiến trình kỹ thuật mạng lưới bình thường."
            })
            title = f"Đang đo kiểm / xử lý kỹ thuật ({last_flow_name})"
        elif step_sla_hours > 48.0 and last_flow_name:
            issues.append({
                "code": "OVERDUE_SLA",
                "severity": "WARNING",
                "name": f"Quá hạn tại bước '{last_flow_name}' ({step_sla_hours} giờ làm việc)",
                "description": f"Phiếu chưa hoàn tất, đang dừng ở bước '{last_flow_name}' ({last_flow_user or 'Chưa tiếp nhận'}) đã trôi qua {step_sla_hours} giờ làm việc (đã trừ Thứ 7, Chủ Nhật, vượt ngưỡng cam kết 48 giờ / 2 ngày làm việc cho mỗi bước).",
                "recommendation": f"Đôn đốc nhân sự {last_flow_user or 'tổ xử lý'} hoàn tất xử lý tại bước {last_flow_name}."
            })
            grade = "WARNING"
            title = f"Quá hạn bước {last_flow_name} ({step_sla_hours}h làm việc - trừ T7/CN)"
        elif not last_flow_name and not is_closed_oneoss:
            issues.append({
                "code": "NO_FLOW_DATA",
                "severity": "INFO",
                "name": "Chưa có dữ liệu luồng xử lý trên OneOSS",
                "description": "Phiếu chưa có lịch sử các bước luân chuyển BPMN (chưa kích hoạt tiến trình tiếp nhận hoặc thuộc quyền quản lý của đơn vị khác). Không đủ dữ liệu chứng cứ để chẩn đoán lỗi luồng.",
                "recommendation": "Kiểm tra trực tiếp phiếu trên giao diện OneOSS hoặc yêu cầu đơn vị kích hoạt phân công tiếp nhận."
            })
            title = "Chưa có dữ liệu luồng OneOSS"

    # =========================================================================
    # MỤC THÔNG TIN VẬN HÀNH (SEVERITY: INFO)
    # Tuyệt đối KHÔNG làm đổi grade của phiếu nếu phiếu đã hoàn tất thành công!
    # =========================================================================
    # Thông tin quy trình & dịch vụ
    issues.append({
        "code": "PROCESS_PROFILE",
        "severity": "INFO",
        "name": f"Quy trình: {process_name} | Dịch vụ: {service_type}",
        "description": f"Phiếu vận hành trên quy trình '{process_name}', phân loại dịch vụ '{service_type}', đơn vị thực hiện: {handling_unit}.",
        "recommendation": "Thông tin cấu hình luồng nghiệp vụ OneOSS."
    })

    # Thông tin thời gian SLA của phiếu đã hoàn tất
    if is_closed_oneoss and total_sla_hours > 0:
        issues.append({
            "code": "SLA_INFO",
            "severity": "INFO",
            "name": f"Thời gian xử lý: {total_sla_hours} giờ làm việc (trừ T7/CN)",
            "description": f"Tổng thời gian làm việc từ lúc CCOS tiếp nhận ban đầu ({req_date_str or '--'}) đến khi đóng hoàn tất là {total_sla_hours} giờ làm việc (đã trừ Thứ 7, Chủ Nhật). Bước cuối hoàn thành trong {step_sla_hours} giờ làm việc.",
            "recommendation": "Số liệu thời gian xử lý phục vụ báo cáo chất lượng dịch vụ."
        })

    # Thông tin số lần Reopen
    if reopen_count > 0:
        issues.append({
            "code": "CCOS_REOPENED",
            "severity": "INFO" if is_closed_oneoss else "WARNING",
            "name": f"Phiếu từng bị CCOS Reopen {reopen_count} lần",
            "description": f"Phiếu có lịch sử bị điện thoại viên CCOS Reopen trả lại {reopen_count} lần do khách hàng liên hệ lại.",
            "recommendation": "Kiểm tra kỹ nội dung khách phản ánh và biên bản đo kiểm hiện trường."
        })
        if not is_closed_oneoss and grade == "HEALTHY":
            grade = "WARNING"
            title = f"Phiếu bị CCOS Reopen {reopen_count} lần"

    # Nếu phiếu đã đóng hoàn tất và không dính lỗi critical/warning nào
    if is_closed_oneoss and grade == "HEALTHY":
        title = f"Luồng quy trình hoàn tất ({process_name})"

    # =========================================================================
    # NGUYÊN TẮC: NẾU TRÊN CCOS ĐÃ ĐÓNG THÌ CHỈ CẢNH BÁO (WARNING), KHÔNG PHẢI CRITICAL
    # =========================================================================
    if is_closed_ccos and grade == "CRITICAL":
        grade = "WARNING"
        if "Lỗi" in title:
            title = title.replace("Lỗi", "Cảnh báo luồng").replace("lỗi", "cảnh báo") + " (CCOS đã đóng)"
        else:
            title = f"Cảnh báo luồng OneOSS (CCOS đã đóng hoàn tất)"
        for iss in issues:
            if iss.get("severity") == "CRITICAL":
                iss["severity"] = "WARNING"
                if "CCOS đã đóng" not in iss.get("name", ""):
                    iss["name"] += " (CCOS đã đóng)"

    # =========================================================================
    # PHÂN LOẠI CHUYÊN BIỆT: LỖI LUỒNG HỆ THỐNG vs QUÁ HẠN SLA BƯỚC (> 48h TRỪ T7/CN)
    # =========================================================================
    FLOW_ERROR_CODES = {
        "HANG_END_NODE",
        "LOOP_BACK_STEP_2_1",
        "STUCK_STEP_2_1",
        "NULL_FORM_CLOSE"
    }
    has_flow_issue = any(i.get("code") in FLOW_ERROR_CODES for i in issues)

    is_flow_error = has_flow_issue or (grade == "CRITICAL")
    is_field_step = any(k in last_flow_name for k in ["3.10", "3.11", "3.12", "3.13", "5.1", "5.2", "Đo kiểm", "chất lượng"])
    is_sla_overdue = (step_sla_hours > 48.0) and bool(last_flow_name) and not is_closed_oneoss and not is_field_step

    if is_flow_error:
        audit_category = "FLOW_ERROR"
    elif is_sla_overdue:
        audit_category = "OVERDUE_SLA"
    else:
        audit_category = "HEALTHY"

    return {
        "grade": grade,
        "title": title,
        "process_name": process_name,
        "service_type": service_type,
        "handling_unit": handling_unit,
        "total_sla_hours": total_sla_hours,
        "step_sla_hours": step_sla_hours,
        "sla_hours": step_sla_hours,
        "reopen_count": reopen_count,
        "cl_ticket_status_id": cl_status_id,
        "status_name": status_name,
        "last_step_name": last_flow_name,
        "last_step_user": last_flow_user,
        "last_step_time": last_flow_created,
        "ccos_id": ccos_id,
        "issues_count": len(issues),
        "issues": issues,
        "audit_category": audit_category,
        "is_flow_error": is_flow_error,
        "is_sla_overdue": is_sla_overdue
    }


def save_audit_result_to_db(ticket_id: int, ticket_code: str, phone: str, flow_id: int,
                            ticket_data: dict, history_data: dict, ticket_flows: list, diagnostic: dict):
    """Lưu kết quả đối soát vào bảng flow_audit_results để tra cứu lại siêu tốc."""
    conn = get_db_connection()
    try:
        now_str = datetime.now(ICT).strftime("%Y-%m-%d %H:%M:%S")
        end_flow = next((f for f in reversed(ticket_flows) if str(f.get("processNodeName") or "") == "Kết thúc"), None) if ticket_flows else None
        
        is_flow_err_val = "1" if diagnostic.get("is_flow_error") else "0"
        is_sla_overdue_val = "1" if diagnostic.get("is_sla_overdue") else "0"
        cat_val = diagnostic.get("audit_category") or ("FLOW_ERROR" if is_flow_err_val == "1" else ("OVERDUE_SLA" if is_sla_overdue_val == "1" else "HEALTHY"))

        conn.execute("""
            INSERT INTO flow_audit_results (
                ticket_id, ticket_code, phone, flow_id, request_date, incident_date,
                oneoss_status, oneoss_status_name, cl_ticket_status_id,
                last_step_name, last_step_user, last_step_time,
                end_node_time, end_node_closing_date, reopen_count, ccos_id,
                sla_hours, error_grade, error_title, error_details,
                raw_flows_json, raw_ticket_json, audited_at,
                process_name, service_type,
                audit_category, is_flow_error, is_sla_overdue
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticket_id) DO UPDATE SET
                ticket_code = excluded.ticket_code,
                phone = excluded.phone,
                flow_id = COALESCE(excluded.flow_id, flow_audit_results.flow_id),
                request_date = excluded.request_date,
                incident_date = excluded.incident_date,
                oneoss_status = excluded.oneoss_status,
                oneoss_status_name = excluded.oneoss_status_name,
                cl_ticket_status_id = excluded.cl_ticket_status_id,
                last_step_name = excluded.last_step_name,
                last_step_user = excluded.last_step_user,
                last_step_time = excluded.last_step_time,
                end_node_time = excluded.end_node_time,
                end_node_closing_date = excluded.end_node_closing_date,
                reopen_count = excluded.reopen_count,
                ccos_id = excluded.ccos_id,
                sla_hours = excluded.sla_hours,
                error_grade = excluded.error_grade,
                error_title = excluded.error_title,
                error_details = excluded.error_details,
                raw_flows_json = excluded.raw_flows_json,
                raw_ticket_json = excluded.raw_ticket_json,
                audited_at = excluded.audited_at,
                process_name = excluded.process_name,
                service_type = excluded.service_type,
                audit_category = excluded.audit_category,
                is_flow_error = excluded.is_flow_error,
                is_sla_overdue = excluded.is_sla_overdue
        """, (
            ticket_id,
            ticket_code,
            phone,
            flow_id,
            ticket_data.get("requestDate"),
            ticket_data.get("incidentDate"),
            ticket_data.get("status"),
            diagnostic.get("status_name"),
            diagnostic.get("cl_ticket_status_id"),
            diagnostic.get("last_step_name"),
            diagnostic.get("last_step_user"),
            diagnostic.get("last_step_time"),
            end_flow.get("createdDate") if end_flow else None,
            end_flow.get("closingDate") if end_flow else None,
            diagnostic.get("reopen_count", 0),
            str(diagnostic.get("ccos_id") or ""),
            diagnostic.get("step_sla_hours", diagnostic.get("total_sla_hours", 0.0)),
            diagnostic.get("grade"),
            diagnostic.get("title"),
            json.dumps(diagnostic.get("issues", []), ensure_ascii=False),
            json.dumps(ticket_flows, ensure_ascii=False),
            json.dumps(ticket_data, ensure_ascii=False),
            now_str,
            diagnostic.get("process_name", ""),
            diagnostic.get("service_type", ""),
            cat_val,
            is_flow_err_val,
            is_sla_overdue_val
        ))
        conn.commit()
    except Exception as ex_db:
        print(f"[Flow Audit] Lỗi lưu kết quả audit vào DB: {ex_db}")
    finally:
        conn.close()


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@router.get("/check-single")
def api_check_single_ticket(query: str = Query(..., description="Mã phiếu, Ticket ID, SĐT hoặc Mã CCOS")):
    """Kiểm tra chi tiết luồng xử lý của 1 phiếu duy nhất."""
    res = audit_single_ticket_data(query)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Lỗi kiểm tra phiếu"))
    return res


class BatchCheckRequest(BaseModel):
    ticket_list: list[str]


@router.post("/check-batch")
def api_check_batch_tickets(req: BatchCheckRequest):
    """
    Kiểm tra hàng loạt danh sách phiếu (nhập tay hoặc import từ file/danh sách).
    Chạy song song tối ưu tốc độ và lưu kết quả đối soát.
    """
    raw_list = req.ticket_list or []
    clean_inputs = []
    for item in raw_list:
        lines = str(item).replace(",", "\n").replace(";", "\n").split("\n")
        for line in lines:
            t_clean = line.strip()
            if t_clean and t_clean not in clean_inputs:
                clean_inputs.append(t_clean)

    if not clean_inputs:
        raise HTTPException(status_code=400, detail="Danh sách phiếu trống.")

    token = ttsnew_api.get_cached_token()
    results = []

    def _worker(q):
        try:
            return audit_single_ticket_data(q, token=token)
        except Exception as e:
            return {"success": False, "ticket_input": q, "message": str(e)}

    with ThreadPoolExecutor(max_workers=6) as executor:
        for res in executor.map(_worker, clean_inputs):
            results.append(res)

    # Thống kê tổng hợp
    total = len(results)
    critical_count = sum(1 for r in results if r.get("diagnostic", {}).get("grade") == "CRITICAL")
    warning_count = sum(1 for r in results if r.get("diagnostic", {}).get("grade") == "WARNING")
    healthy_count = sum(1 for r in results if r.get("diagnostic", {}).get("grade") == "HEALTHY")

    return {
        "success": True,
        "total": total,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "healthy_count": healthy_count,
        "items": results
    }


def fetch_oneoss_tickets_live(token: str, status_type: str = "closed", limit: int = 500, from_date: str = "", to_date: str = "", source_mode: str = "all_system") -> list:
    """
    Kéo danh sách phiếu trực tiếp từ server OneOSS TTS Mới (gw-oneoss.vnpt.vn) theo thời gian thực:
    - Nếu source_mode == 'all_system' (Mặc định): Sử dụng API Tra cứu tiến trình xử lý phiếu toàn hệ thống
      (POST /Ticket/tra-cuu-tien-trinh-xu-ly-phieu) với kho dữ liệu 15.000+ phiếu của toàn bộ đơn vị/tỉnh thành.
    - Nếu source_mode == 'personal': Sử dụng API Quản lý phiếu của KTV cá nhân (GET /Ticket/get-list).
    """
    if not token:
        raise HTTPException(status_code=401, detail="Chưa có phiên đăng nhập OneOSS TTS Mới hợp lệ. Vui lòng bấm 'Đăng nhập TTS Mới' ở góc trên màn hình.")

    tok_clean = token.replace("Bearer ", "").strip()
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {tok_clean}",
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }

    collected_tickets = []
    seen_ids = set()

    # =========================================================================
    # PHƯƠNG PHÁP 1 (ƯU TIÊN): TRA CỨU TOÀN BỘ TIẾN TRÌNH HỆ THỐNG ONEOSS (15.000+ PHIẾU)
    # =========================================================================
    if source_mode != "personal":
        search_url = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/tra-cuu-tien-trinh-xu-ly-phieu"
        batch_size = 500
        offset = 0

        # Chuẩn hóa ngày DD/MM/YYYY cho OneOSS
        tu_ngay = ""
        if from_date:
            p_f = from_date.strip().split("-")
            tu_ngay = f"{p_f[2]}/{p_f[1]}/{p_f[0]}" if len(p_f) == 3 else from_date.strip()

        den_ngay = ""
        if to_date:
            p_t = to_date.strip().split("-")
            den_ngay = f"{p_t[2]}/{p_t[1]}/{p_t[0]}" if len(p_t) == 3 else to_date.strip()

        payload = {
            "limit": batch_size,
            "offset": 0,
            "loaiPhieu": 2, # PAKH
        }
        if status_type == "closed":
            payload["trangThaiPhieuId"] = 100 # Đã đóng
        elif status_type == "active":
            payload["trangThaiPhieuId"] = 2   # Đang xử lý
        # Nếu status_type == 'all': không truyền trangThaiPhieuId, lấy mọi trạng thái

        if tu_ngay:
            payload["tuNgay"] = tu_ngay
        if den_ngay:
            payload["denNgay"] = den_ngay

        while True:
            payload["offset"] = offset
            try:
                r = requests.post(search_url, json=payload, headers=headers, timeout=25)
                if r.status_code == 200:
                    j = r.json()
                    if not j.get("isError") and j.get("data"):
                        batch_items = j["data"]
                        for raw in batch_items:
                            ma_phieu = raw.get("maPhieu") or raw.get("ticketCode") or ""
                            t_id = raw.get("ticketId") or raw.get("id")
                            if not t_id and ma_phieu:
                                try:
                                    t_id = int(str(ma_phieu).strip().split("/")[-1])
                                except Exception:
                                    t_id = None

                            if not t_id:
                                continue

                            if t_id not in seen_ids:
                                seen_ids.add(t_id)
                                normalized_ticket = {
                                    "ticketId": t_id,
                                    "ticketCode": ma_phieu or f"TID-{t_id}",
                                    "customerPhone": raw.get("soThueBao") or raw.get("soDienTHoai") or "",
                                    "id": raw.get("ticketFlowId") or raw.get("id"),
                                    "ticketFlowId": raw.get("ticketFlowId") or raw.get("id"),
                                    "requestDate": raw.get("ngayYeuCau") or "",
                                    "incidentDate": raw.get("ngaySuCoPAKH") or "",
                                    "status": raw.get("trangThaiPhieu") or "",
                                    "title": raw.get("tieuDe") or "",
                                    "content": raw.get("noiDung") or "",
                                    "ccosId": raw.get("maCCOS") or "",
                                    "source": "tra_cuu_tien_trinh"
                                }
                                collected_tickets.append(normalized_ticket)

                        total_rec = j.get("totalRecord") or 0
                        if len(batch_items) < batch_size or (total_rec > 0 and len(seen_ids) >= total_rec):
                            break
                        offset += len(batch_items)
                        if limit > 0 and len(collected_tickets) >= limit:
                            break
                    else:
                        break
                elif r.status_code == 401:
                    raise HTTPException(status_code=401, detail="Phiên đăng nhập OneOSS TTS Mới đã hết hạn. Vui lòng bấm 'Đăng nhập TTS Mới' ở góc trên màn hình để làm mới phiên.")
                else:
                    print(f"[Flow Audit] API tra-cuu-tien-trinh-xu-ly-phieu status {r.status_code}: {r.text[:150]}")
                    break
            except requests.exceptions.RequestException as e:
                print(f"[Flow Audit] Lỗi gọi tra-cuu-tien-trinh-xu-ly-phieu: {e}")
                break

    # =========================================================================
    # PHƯƠNG PHÁP 2 (FALLBACK / PERSONAL): QUẢN LÝ PHIẾU GIAO CHO KTV (GET-LIST)
    # =========================================================================
    if not collected_tickets and (source_mode == "personal" or len(seen_ids) == 0):
        base_url = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket/get-list"
        status_ids = [3] if status_type == "closed" else ([2] if status_type == "active" else [3, 2])

        for sid in status_ids:
            offset = 0
            batch_size = 500
            while True:
                try:
                    url = f"{base_url}?limit={batch_size}&offset={offset}&ticketFlowStatusId={sid}"
                    r = requests.get(url, headers=headers, timeout=20)
                    if r.status_code == 200:
                        j = r.json()
                        if not j.get("isError") and j.get("data"):
                            batch_items = j["data"]
                            for item in batch_items:
                                t_id = item.get("ticketId") or item.get("id")
                                if t_id and t_id not in seen_ids:
                                    seen_ids.add(t_id)
                                    collected_tickets.append(item)

                            total_rec = j.get("totalRecord")
                            if not batch_items or len(batch_items) < batch_size or (total_rec and len(seen_ids) >= total_rec):
                                break
                            offset += len(batch_items)
                            if limit > 0 and len(collected_tickets) >= limit:
                                break
                        else:
                            break
                    elif r.status_code == 401:
                        raise HTTPException(status_code=401, detail="Phiên đăng nhập OneOSS TTS Mới đã hết hạn. Vui lòng bấm 'Đăng nhập TTS Mới' ở góc trên màn hình.")
                    else:
                        break
                except requests.exceptions.RequestException as e:
                    print(f"[Flow Audit] Lỗi gọi API OneOSS get-list status {sid} offset {offset}: {e}")
                    break

        # Lọc theo khoảng ngày nếu lấy từ get-list
        if (from_date or to_date) and collected_tickets:
            filtered = []
            for t in collected_tickets:
                date_raw = str(t.get("requestDate") or t.get("createdDate") or t.get("incidentDate") or "")
                d_norm = ""
                if date_raw:
                    if "/" in date_raw[:10]:
                        p = date_raw[:10].split("/")
                        if len(p) == 3:
                            d_norm = f"{p[2]}-{p[1]}-{p[0]}"
                    elif "-" in date_raw[:10]:
                        d_norm = date_raw[:10]

                if d_norm:
                    if from_date and d_norm < from_date:
                        continue
                    if to_date and d_norm > to_date:
                        continue
                filtered.append(t)
            collected_tickets = filtered

    if limit > 0 and len(collected_tickets) > limit:
        collected_tickets = collected_tickets[:limit]

    return collected_tickets


@router.post("/scan-closed-tickets")
def api_scan_closed_tickets(
    from_date: str = Query("", description="Từ ngày tiếp nhận (YYYY-MM-DD)"),
    to_date: str = Query("", description="Đến ngày tiếp nhận (YYYY-MM-DD)"),
    limit: int = Query(0, description="Giới hạn số lượng (0 = tất cả trong khoảng ngày)"),
    source: str = Query("tts_new", description="Nguồn phiếu: tts_new, tts_old_api, all"),
    scan_source: str = Query("oneoss_live", description="Nguồn rà soát: 'oneoss_live' (Trực tiếp từ OneOSS TTS Mới - Toàn hệ thống), 'oneoss_personal' (Hàng đợi cá nhân KTV), 'db' (Từ CSDL Local)"),
    ticket_status_type: str = Query("closed", description="Loại phiếu: 'closed' (Đã đóng), 'active' (Đang xử lý), 'all' (Tất cả)"),
    force_refresh: bool = Query(False, description="Quét lại từ OneOSS ngay cả khi đã có kết quả đối soát")
):
    """
    Rà soát luồng phiếu OneOSS:
    - Nếu scan_source='oneoss_live': Kéo trực tiếp danh sách phiếu TOÀN BỘ HỆ THỐNG từ máy chủ OneOSS Gateway qua API tra-cuu-tien-trinh-xu-ly-phieu.
    - Nếu scan_source='oneoss_personal': Kéo danh sách phiếu gán cho cá nhân/hàng đợi KTV từ API get-list.
    - Nếu scan_source='db': Rà soát từ dữ liệu CSDL local tickets.db.
    """
    token = ttsnew_api.get_cached_token()
    target_items = []

    # =========================================================================
    # NHÁNH 1: RÀ SOÁT TRỰC TIẾP TỪ MÁY CHỦ ONEOSS TTS MỚI (LIVE GATEWAY)
    # =========================================================================
    if scan_source in ("oneoss_live", "oneoss_personal"):
        if not token:
            raise HTTPException(status_code=401, detail="Chưa có phiên đăng nhập OneOSS TTS Mới. Vui lòng bấm 'Đăng nhập TTS Mới' ở góc trên màn hình.")

        source_mode = "personal" if scan_source == "oneoss_personal" else "all_system"
        live_list = fetch_oneoss_tickets_live(
            token=token,
            status_type=ticket_status_type,
            limit=limit,
            from_date=from_date,
            to_date=to_date,
            source_mode=source_mode
        )
        for item in live_list:
            t_id = item.get("ticketId") or item.get("id")
            t_code = item.get("ticketCode") or item.get("code") or f"TID-{t_id}"
            target_items.append({
                "ticket_id": t_id,
                "ticket_code": t_code,
                "phone": item.get("customerPhone") or "",
                "flow_id": item.get("ticketFlowId") or item.get("id")
            })

    # =========================================================================
    # NHÁNH 2: RÀ SOÁT TỪ CƠ SỞ DỮ LIỆU LOCAL (SQLITE)
    # =========================================================================
    else:
        conn = get_db_connection()
        try:
            where_parts = ["ticket_id IS NOT NULL"]
            params = []
            
            if ticket_status_type == "closed":
                where_parts.append("ticket_status IN ('Đã đóng', 'Da dong')")
            elif ticket_status_type == "active":
                where_parts.append("ticket_status NOT IN ('Đã đóng', 'Da dong')")

            if source != "all":
                where_parts.append("source = ?")
                params.append(source)

            if from_date:
                where_parts.append("(substr(created_time, 7, 4) || '-' || substr(created_time, 4, 2) || '-' || substr(created_time, 1, 2)) >= ?")
                params.append(from_date)

            if to_date:
                where_parts.append("(substr(created_time, 7, 4) || '-' || substr(created_time, 4, 2) || '-' || substr(created_time, 1, 2)) <= ?")
                params.append(to_date)

            where_sql = " AND ".join(where_parts)
            limit_sql = f"LIMIT {limit}" if (limit and limit > 0) else ""

            sql = f"""
                SELECT ticket_id, ticket_code, phone, flow_id, incident_time, created_time, closed_at, updated_at
                FROM tickets
                WHERE {where_sql}
                ORDER BY created_time DESC, closed_at DESC
                {limit_sql}
            """
            rows = conn.execute(sql, params).fetchall()
            for r in rows:
                target_items.append(dict(r))
        finally:
            conn.close()

    if not target_items:
        msg = f"Không tìm thấy phiếu nào trên {'OneOSS TTS Mới' if scan_source == 'oneoss_live' else 'CSDL hệ thống'} trong khoảng thời gian đã chọn."
        return {
            "success": True,
            "total": 0,
            "scanned_new": 0,
            "reused_existing": 0,
            "critical_count": 0,
            "warning_count": 0,
            "healthy_count": 0,
            "items": [],
            "message": msg
        }

    # Đọc cache sẵn có từ flow_audit_results
    conn = get_db_connection()
    existing_audited = {}
    try:
        if not force_refresh:
            audited_rows = conn.execute("SELECT ticket_id, ticket_code, phone, flow_id, raw_flows_json, raw_ticket_json FROM flow_audit_results WHERE raw_flows_json IS NOT NULL").fetchall()
            for ar in audited_rows:
                existing_audited[ar["ticket_id"]] = ar
    finally:
        conn.close()

    scanned_count = 0
    reused_count = 0

    to_fetch_network = []
    to_recalc_offline = []
    for row in target_items:
        t_id = row["ticket_id"]
        if not force_refresh and t_id in existing_audited:
            reused_count += 1
            to_recalc_offline.append(existing_audited[t_id])
        else:
            to_fetch_network.append(row)

    # Tự động cập nhật lại kết quả chẩn đoán mới nhất cho các phiếu tái sử dụng (chạy offline cực nhanh)
    if to_recalc_offline:
        for ar in to_recalc_offline:
            try:
                flows = json.loads(ar["raw_flows_json"]) if ar["raw_flows_json"] else []
                tdata = json.loads(ar["raw_ticket_json"]) if ar["raw_ticket_json"] else {}
                diag = analyze_ticket_flow(ticket_data=tdata, history_data={}, ticket_flows=flows, db_row=None)
                save_audit_result_to_db(ar["ticket_id"], ar["ticket_code"], ar["phone"], ar["flow_id"], tdata, {}, flows, diag)
            except Exception:
                pass

    # Quét mạng OneOSS cho các phiếu mới chưa có kết quả đối soát
    if to_fetch_network:
        def _audit_item(row):
            t_id = row["ticket_id"]
            try:
                return audit_single_ticket_data(str(t_id), token=token, flow_id=row.get("flow_id"))
            except Exception as e:
                return {"success": False, "ticket_id": t_id, "ticket_code": row.get("ticket_code"), "message": str(e)}

        with ThreadPoolExecutor(max_workers=10) as executor:
            for _ in executor.map(_audit_item, to_fetch_network):
                scanned_count += 1

    # Nạp toàn bộ kết quả cập nhật mới nhất cho danh sách ticket_ids
    ticket_ids = [r["ticket_id"] for r in target_items]
    placeholders = ",".join("?" for _ in ticket_ids)
    conn = get_db_connection()
    try:
        final_rows = conn.execute(f"""
            SELECT ticket_id, ticket_code, phone, flow_id, request_date, incident_date,
                   oneoss_status_name, cl_ticket_status_id, last_step_name, last_step_user,
                   last_step_time, end_node_time, end_node_closing_date, reopen_count,
                   ccos_id, sla_hours, error_grade, error_title, error_details, audited_at,
                   process_name, service_type, audit_category, is_flow_error, is_sla_overdue
            FROM flow_audit_results
            WHERE ticket_id IN ({placeholders})
            ORDER BY audited_at DESC
        """, ticket_ids).fetchall()

        items = []
        for r in final_rows:
            d = dict(r)
            try:
                d["issues"] = json.loads(d.get("error_details") or "[]")
            except Exception:
                d["issues"] = []
            items.append(d)

        flow_error_count = sum(1 for r in items if str(r.get("is_flow_error")) == "1" or r.get("audit_category") == "FLOW_ERROR" or r.get("error_grade") == "CRITICAL")
        sla_overdue_count = sum(1 for r in items if (str(r.get("is_sla_overdue")) == "1" or r.get("audit_category") == "OVERDUE_SLA" or float(r.get("sla_hours") or 0) > 48.0) and str(r.get("is_flow_error")) != "1" and r.get("audit_category") != "FLOW_ERROR")
        healthy_count = sum(1 for r in items if r.get("audit_category") == "HEALTHY" or (r.get("error_grade") == "HEALTHY" and float(r.get("sla_hours") or 0) <= 48.0 and str(r.get("is_flow_error")) != "1"))
        critical_count = sum(1 for r in items if r.get("error_grade") == "CRITICAL")
        warning_count = sum(1 for r in items if r.get("error_grade") == "WARNING")

        return {
            "success": True,
            "total": len(items),
            "matched_tickets": len(target_items),
            "scan_source": scan_source,
            "scanned_new": scanned_count,
            "reused_existing": reused_count,
            "flow_error_count": flow_error_count,
            "sla_overdue_count": sla_overdue_count,
            "healthy_count": healthy_count,
            "critical_count": critical_count,
            "warning_count": warning_count,
            "items": items
        }
    finally:
        conn.close()


@router.get("/saved-audit-results")
def api_get_saved_audit_results(
    category: str = Query("ALL", description="Lọc theo nhóm: ALL, FLOW_ERROR, OVERDUE_SLA, HEALTHY"),
    grade: str = Query("ALL", description="Lọc theo cấp độ cũ: ALL, CRITICAL, WARNING, HEALTHY"),
    from_date: str = Query("", description="Từ ngày tiếp nhận YYYY-MM-DD"),
    to_date: str = Query("", description="Đến ngày tiếp nhận YYYY-MM-DD"),
    limit: int = Query(1000, ge=1, le=10000)
):
    """Lấy danh sách các kết quả đối soát đã lưu trong database theo nhóm chuyên biệt (Lỗi Luồng Hệ Thống vs Quá Hạn SLA CCOS) và thời gian."""
    conn = get_db_connection()
    try:
        where_parts = []
        params = []

        if category == "FLOW_ERROR":
            where_parts.append("(is_flow_error = '1' OR audit_category = 'FLOW_ERROR' OR error_grade = 'CRITICAL')")
        elif category == "OVERDUE_SLA":
            where_parts.append("((is_sla_overdue = '1' OR audit_category = 'OVERDUE_SLA' OR sla_hours > 48.0) AND (is_flow_error != '1' OR is_flow_error IS NULL) AND error_grade != 'CRITICAL')")
        elif category == "HEALTHY":
            where_parts.append("(audit_category = 'HEALTHY' OR (error_grade = 'HEALTHY' AND (sla_hours <= 48.0 OR sla_hours IS NULL) AND (is_flow_error != '1' OR is_flow_error IS NULL)))")

        if grade != "ALL" and category == "ALL":
            where_parts.append("error_grade = ?")
            params.append(grade)

        if from_date:
            where_parts.append("""
                (CASE 
                    WHEN request_date LIKE '__/__/____%' THEN (substr(request_date, 7, 4) || '-' || substr(request_date, 4, 2) || '-' || substr(request_date, 1, 2))
                    ELSE substr(request_date, 1, 10)
                END) >= ?
            """)
            params.append(from_date)

        if to_date:
            where_parts.append("""
                (CASE 
                    WHEN request_date LIKE '__/__/____%' THEN (substr(request_date, 7, 4) || '-' || substr(request_date, 4, 2) || '-' || substr(request_date, 1, 2))
                    ELSE substr(request_date, 1, 10)
                END) <= ?
            """)
            params.append(to_date)

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        rows = conn.execute(f"""
            SELECT ticket_id, ticket_code, phone, flow_id, request_date, incident_date,
                   oneoss_status_name, cl_ticket_status_id, last_step_name, last_step_user,
                   last_step_time, end_node_time, end_node_closing_date, reopen_count,
                   ccos_id, sla_hours, error_grade, error_title, error_details, audited_at,
                   process_name, service_type, audit_category, is_flow_error, is_sla_overdue
            FROM flow_audit_results
            {where_clause}
            ORDER BY audited_at DESC
            LIMIT ?
        """, (*params, limit)).fetchall()

        # Thống kê tổng theo bộ lọc ngày hiện tại
        stats_where_parts = []
        stats_params = []
        if from_date:
            stats_where_parts.append("""
                (CASE 
                    WHEN request_date LIKE '__/__/____%' THEN (substr(request_date, 7, 4) || '-' || substr(request_date, 4, 2) || '-' || substr(request_date, 1, 2))
                    ELSE substr(request_date, 1, 10)
                END) >= ?
            """)
            stats_params.append(from_date)
        if to_date:
            stats_where_parts.append("""
                (CASE 
                    WHEN request_date LIKE '__/__/____%' THEN (substr(request_date, 7, 4) || '-' || substr(request_date, 4, 2) || '-' || substr(request_date, 1, 2))
                    ELSE substr(request_date, 1, 10)
                END) <= ?
            """)
            stats_params.append(to_date)

        stats_where = f"WHERE {' AND '.join(stats_where_parts)}" if stats_where_parts else ""

        stats_rows = conn.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN is_flow_error = '1' OR audit_category = 'FLOW_ERROR' OR error_grade = 'CRITICAL' THEN 1 ELSE 0 END) as flow_error_count,
                SUM(CASE WHEN (is_sla_overdue = '1' OR audit_category = 'OVERDUE_SLA' OR sla_hours > 48.0) AND (is_flow_error != '1' OR is_flow_error IS NULL) AND error_grade != 'CRITICAL' AND (audit_category != 'FLOW_ERROR' OR audit_category IS NULL) THEN 1 ELSE 0 END) as sla_overdue_count,
                SUM(CASE WHEN (audit_category = 'HEALTHY' OR error_grade = 'HEALTHY') AND (sla_hours <= 48.0 OR sla_hours IS NULL) AND (is_flow_error != '1' OR is_flow_error IS NULL) AND (audit_category != 'FLOW_ERROR' OR audit_category IS NULL) THEN 1 ELSE 0 END) as healthy_count,
                SUM(CASE WHEN error_grade = 'CRITICAL' THEN 1 ELSE 0 END) as critical_count,
                SUM(CASE WHEN error_grade = 'WARNING' THEN 1 ELSE 0 END) as warning_count
            FROM flow_audit_results
            {stats_where}
        """, stats_params).fetchone()

        items = []
        for r in rows:
            d = dict(r)
            try:
                d["issues"] = json.loads(d.get("error_details") or "[]")
            except Exception:
                d["issues"] = []
            items.append(d)

        return {
            "success": True,
            "total": stats_rows["total"] or 0,
            "flow_error_count": stats_rows["flow_error_count"] or 0,
            "sla_overdue_count": stats_rows["sla_overdue_count"] or 0,
            "healthy_count": stats_rows["healthy_count"] or 0,
            "critical_count": stats_rows["critical_count"] or 0,
            "warning_count": stats_rows["warning_count"] or 0,
            "items": items
        }
    finally:
        conn.close()
