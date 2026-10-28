# routers/cdr.py
# Router cung cấp API tra cứu lịch sử SMSC CDR (tích hợp từ cdrsearch)

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from services.smsc_cdr_client import (
    fetch_smsc_cdr,
    WINSCP_PATH,
    CDR_QUEUE_DIR,
    CDR_LOCAL_INPUT_DIR,
    CDR_LOCAL_OUTPUT_DIR
)
import os

router = APIRouter(prefix="/api/cdr", tags=["Tra cứu SMSC CDR"])


@router.get("/status")
def get_cdr_integration_status():
    try:
        import paramiko
        has_paramiko = True
    except ImportError:
        has_paramiko = False

    has_winscp = os.path.exists(WINSCP_PATH)
    is_docker = os.getenv("IS_DOCKER") == "1"
    has_local_queue = os.path.exists(CDR_LOCAL_INPUT_DIR)

    return {
        "success": True,
        "is_docker": is_docker,
        "local_queue_available": has_local_queue,
        "local_queue_input": CDR_LOCAL_INPUT_DIR,
        "local_queue_output": CDR_LOCAL_OUTPUT_DIR,
        "paramiko_available": has_paramiko,
        "winscp_available": has_winscp,
        "winscp_path": WINSCP_PATH,
        "elastic_target": "10.204.57.26 (SMSC Core)",
        "sftp_target": "10.165.15.84 (VHKT Bridge)",
        "active_method": "sftp_vhkt (10.165.15.84)"
    }


@router.get("/test")
def test_both_cdr_channels(phone: str = Query("84917969796", description="Số thuê bao mẫu để test")):
    """
    Chẩn đoán song song các đường tra cứu SMS CDR:
    - Kênh 1 (SFTP VHKT): Cầu nối chính qua 10.165.15.84:22 (/home/sftp/ktm/soc2/quangvu/input -> output)
    - Kênh 2 (Direct Elastic): Dự phòng khi máy thông thẳng tới 10.204.57.26:80
    """
    import time
    import socket

    # 1. Kiểm tra Kênh Local Queue
    queue_res = {
        "target": f"Local File Queue ({CDR_LOCAL_INPUT_DIR})",
        "input_dir_exists": os.path.exists(CDR_LOCAL_INPUT_DIR),
        "output_dir_exists": os.path.exists(CDR_LOCAL_OUTPUT_DIR),
        "status": "ready" if (os.path.exists(CDR_LOCAL_INPUT_DIR) and os.path.exists(CDR_LOCAL_OUTPUT_DIR)) else "not_configured",
        "message": "Thư mục hàng đợi sẵn sàng" if (os.path.exists(CDR_LOCAL_INPUT_DIR) and os.path.exists(CDR_LOCAL_OUTPUT_DIR)) else "Chưa tạo thư mục hàng đợi"
    }

    # 2. Kiểm tra Kênh Direct 10.204.57.26
    direct_res = {"target": "10.204.57.26:80", "socket_connected": False, "status": "failed", "latency_ms": None, "message": ""}
    t0 = time.time()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.5)
        conn = s.connect_ex(("10.204.57.26", 80))
        s.close()
        if conn == 0:
            direct_res["socket_connected"] = True
            import requests
            from services.smsc_cdr_client import HEADERS, INDEX_PATTERNS
            url = f"http://10.204.57.26/{INDEX_PATTERNS}/_search"
            c_headers = dict(HEADERS)
            c_headers["Origin"] = "http://10.204.57.26"
            c_headers["Referer"] = "http://10.204.57.26/admin/cdr-search"
            payload = {"query": {"match_all": {}}}
            resp = requests.post(url, headers=c_headers, params={"size": 1}, json=payload, timeout=6.0)
            elapsed = round((time.time() - t0) * 1000, 1)
            direct_res["latency_ms"] = elapsed
            if resp.status_code == 200:
                direct_res["status"] = "ok"
                direct_res["message"] = f"Kết nối và query Elastic SMSC thành công trong {elapsed}ms"
            else:
                direct_res["status"] = f"http_{resp.status_code}"
                direct_res["message"] = f"Elastic SMSC trả về mã HTTP {resp.status_code}"
        else:
            direct_res["message"] = f"Không thể mở cổng 80 (connect_ex error code: {conn})"
    except Exception as ex_d:
        direct_res["message"] = str(ex_d)

    # 3. Kiểm tra Kênh SFTP 10.165.15.84
    sftp_res = {"target": "10.165.15.84:22", "socket_connected": False, "status": "failed", "latency_ms": None, "message": ""}
    t1 = time.time()
    try:
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.settimeout(2.5)
        conn2 = s2.connect_ex(("10.165.15.84", 22))
        s2.close()
        if conn2 == 0:
            sftp_res["socket_connected"] = True
            try:
                import paramiko
                from services.smsc_cdr_client import SFTP_USER, SFTP_PASS
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect("10.165.15.84", 22, SFTP_USER, SFTP_PASS, timeout=4.0)
                ssh.close()
                elapsed2 = round((time.time() - t1) * 1000, 1)
                sftp_res["latency_ms"] = elapsed2
                sftp_res["status"] = "ok"
                sftp_res["message"] = f"Đăng nhập SFTP VHKT thành công trong {elapsed2}ms"
            except Exception as ex_p:
                sftp_res["status"] = "ssh_failed"
                sftp_res["message"] = f"Socket mở nhưng SSH lỗi: {ex_p}"
        else:
            sftp_res["message"] = f"Không thể mở cổng 22 (connect_ex error code: {conn2})"
    except Exception as ex_s:
        sftp_res["message"] = str(ex_s)

    if sftp_res["status"] == "ok":
        active_route = "SFTP VHKT (10.165.15.84)"
    elif direct_res["status"] == "ok":
        active_route = "Direct (10.204.57.26)"
    else:
        active_route = "Không có đường nào thông"

    return {
        "success": sftp_res["status"] == "ok" or direct_res["status"] == "ok",
        "active_route": active_route,
        "local_queue": queue_res,
        "direct_channel": direct_res,
        "sftp_channel": sftp_res,
        "advice": f"Môi trường hiện tại sẽ chạy bằng {active_route}"
    }


@router.get("/sms")
def get_sms_cdr(
    phone: str = Query(..., description="Số thuê bao cần tra cứu (vd: 84917969796)"),
    direction: str = Query("both", description="Chiều tin nhắn: 'both', 'mo' (gửi đi), 'mt' (nhận vào)"),
    hours: int = Query(48, description="Số giờ cần tra cứu lùi lại từ hiện tại (mặc định 48h)"),
    gte_time: str = Query(None, description="Mốc thời gian bắt đầu YYMMDDhhmmss"),
    lte_time: str = Query(None, description="Mốc thời gian kết thúc YYMMDDhhmmss"),
    from_date: str = Query(None, description="Từ ngày cụ thể (YYYY-MM-DD hoặc YYYY-MM-DD HH:mm:ss)"),
    to_date: str = Query(None, description="Đến ngày cụ thể (YYYY-MM-DD hoặc YYYY-MM-DD HH:mm:ss)"),
    limit: int = Query(100, description="Số lượng bản ghi tối đa (tối đa 10000)"),
    ticket_code: str = Query(None, description="Mã phiếu OneOSS để lưu vào database"),
    incident_time: str = Query(None, description="Thời điểm phản ánh để lưu vào database"),
    force_refresh: bool = Query(False, description="Ép cào mới từ mạng SMSC thay vì đọc từ Database")
):
    if not phone or not phone.strip():
        return {
            "success": False,
            "total_hits": 0,
            "records": [],
            "message": "Vui lòng cung cấp số điện thoại cần tra cứu"
        }

    clean_p = "".join(filter(str.isdigit, str(phone).strip()))
    if len(clean_p) == 9:
        clean_p = "84" + clean_p
    elif clean_p.startswith("0") and len(clean_p) == 10:
        clean_p = "84" + clean_p[1:]

    from_time = from_date or gte_time
    to_time = to_date or lte_time

    # OFFLINE-FIRST: Nếu không yêu cầu ép cào mới (force_refresh=False), luôn đọc từ SQLite và trả về ngay tức thì (~2ms)
    if not force_refresh:
        try:
            from db_manager import get_sms_cdr_records
            db_records = get_sms_cdr_records(clean_p, ticket_code=ticket_code, limit=limit)
            if not db_records and ticket_code:
                # Thử lại chỉ với số điện thoại nếu mã phiếu không khớp
                db_records = get_sms_cdr_records(clean_p, limit=limit)

            filtered_recs = db_records or []
            notice_msg = (
                f"Tìm thấy {len(filtered_recs)} bản ghi SMSC CDR lưu trong Database (Tốc độ tức thì)"
                if filtered_recs
                else "Không có bản ghi SMSC CDR nào được lưu trong Database (0 bản ghi). Bấm 'Quét mới từ SMSC' nếu cần tra cứu trực tiếp từ mạng."
            )
            if filtered_recs and (from_time or to_time):
                f_clean = str(from_time or "").split()[0].replace("-", "")
                t_clean = str(to_time or "").split()[0].replace("-", "")
                res_filtered = []
                for r in filtered_recs:
                    d_time = str(r.get("delivery_time") or r.get("time") or "").replace("-", "").replace(":", "").replace(" ", "")
                    r_day = d_time[:8] if len(d_time) >= 8 else ""
                    if f_clean and r_day and r_day < f_clean:
                        continue
                    if t_clean and r_day and r_day > t_clean:
                        continue
                    res_filtered.append(r)
                if not res_filtered and db_records:
                    # Trường hợp GDV gõ nhầm tháng trong phiếu khiến dải ngày from_time/to_time lệch với ngày phát sinh thực tế
                    sample_date = str(db_records[0].get("delivery_time") or db_records[0].get("time") or "")[:10]
                    filtered_recs = db_records
                    notice_msg = f"Lưu ý: Dải ngày lọc theo phiếu ({from_time or '--'} → {to_time or '--'}) không có bản ghi, nhưng tìm thấy {len(db_records)} bản ghi SMSC CDR thực tế phát sinh quanh ngày {sample_date} (GDV gõ nhầm tháng)."
                else:
                    filtered_recs = res_filtered
                    notice_msg = f"Tìm thấy {len(filtered_recs)} bản ghi SMSC CDR lưu trong Database (Tốc độ tức thì)" if filtered_recs else "Không có bản ghi SMSC CDR nào được lưu trong Database (0 bản ghi). Bấm 'Quét mới từ SMSC' nếu cần tra cứu trực tiếp từ mạng."

            return {
                "success": True,
                "phone": clean_p,
                "total_hits": len(filtered_recs),
                "method": "database",
                "source": "database_local",
                "from_time": from_time or "--",
                "to_time": to_time or "--",
                "records": filtered_recs,
                "message": notice_msg
            }
        except Exception as ex_db_read:
            print(f"⚠️ [CDR OFFLINE READ] Lỗi đọc SQLite: {ex_db_read}")
            return {
                "success": True,
                "phone": clean_p,
                "total_hits": 0,
                "method": "database",
                "source": "database_local",
                "from_time": from_time or "--",
                "to_time": to_time or "--",
                "records": [],
                "message": f"Lỗi đọc SQLite: {ex_db_read}"
            }

    res = fetch_smsc_cdr(
        phone=clean_p,
        direction=direction,
        from_time_str=from_time,
        to_time_str=to_time,
        hours=hours,
        limit=limit
    )

    # Tự động tính toán tóm tắt KPI và lưu vào database tickets nếu thành công
    if res.get("success") and isinstance(res.get("records"), list):
        try:
            import json
            from db_manager import save_sms_cdr_summary

            clean_p = phone.strip().replace("+", "")
            recs = res.get("records") or []
            
            # QUY TẮC B: Gom nhóm theo CALL REFERENCE cho các bản ghi kết quả (loại bỏ 199C / Attempts = 000 / Status 12)
            from services.sms_analyzer import is_sms_cdr_success

            mo_groups = {}
            mt_groups = {}
            cause_map = {}

            for r in recs:
                term_cause = str(r.get("termination_cause") or r.get("result_code") or "").strip().upper()
                attempts_str = str(r.get("attempts") or r.get("number_of_attempts") or "").strip()
                st_code_str = str(r.get("status_code") or r.get("status") or "").strip()
                is_inter = (term_cause == "199C" or attempts_str in ("0", "000") or st_code_str == "12" or r.get("status_type") == "intermediate" or r.get("is_intermediate") is True)
                if is_inter:
                    continue  # Bỏ qua dòng trung gian phân mảnh tin dài khi đếm số lượng tin thực tế

                is_mo = (r.get("direction") and "MO" in str(r.get("direction")).upper()) or (str(r.get("calling_number")) == clean_p)
                target_groups = mo_groups if is_mo else mt_groups

                call_ref = str(r.get("call_reference") or "").strip()
                if not call_ref or call_ref in ("--", "None", "null"):
                    sub_t = str(r.get("submission_time") or r.get("delivery_time") or "").strip()
                    call_ref = f"{r.get('calling_number')}_{r.get('called_number')}_{sub_t}"

                if call_ref not in target_groups:
                    target_groups[call_ref] = []
                target_groups[call_ref].append(r)

            # Tính MO
            mo_count = len(mo_groups)
            mo_ok = 0
            for c_ref, rows in mo_groups.items():
                if any(is_sms_cdr_success(row) for row in rows):
                    mo_ok += 1
                else:
                    last_row = rows[-1]
                    cause = last_row.get("termination_cause_info") or last_row.get("termination_cause") or last_row.get("status_desc") or "Lỗi không xác định"
                    cause_map[cause] = cause_map.get(cause, 0) + 1

            # Tính MT
            mt_count = len(mt_groups)
            mt_ok = 0
            for c_ref, rows in mt_groups.items():
                if any(is_sms_cdr_success(row) for row in rows):
                    mt_ok += 1
                else:
                    last_row = rows[-1]
                    cause = last_row.get("termination_cause_info") or last_row.get("termination_cause") or last_row.get("status_desc") or "Lỗi không xác định"
                    cause_map[cause] = cause_map.get(cause, 0) + 1

            mo_rate = round((mo_ok / mo_count) * 100) if mo_count > 0 else 0
            mt_rate = round((mt_ok / mt_count) * 100) if mt_count > 0 else 0
            sorted_errs = sorted(cause_map.items(), key=lambda x: x[1], reverse=True)[:3]
            top_errors = [{"cause": k, "count": v} for k, v in sorted_errs]

            time_desc = f"{from_time} → {to_time}" if (from_time and to_time) else f"{hours}h qua"

            summary_dict = {
                "phone": clean_p,
                "totalHits": res.get("total_hits") or len(recs),
                "moCount": mo_count,
                "moOk": mo_ok,
                "moFail": mo_count - mo_ok,
                "moRate": mo_rate,
                "mtCount": mt_count,
                "mtOk": mt_ok,
                "mtFail": mt_count - mt_ok,
                "mtRate": mt_rate,
                "fromDate": from_time or "",
                "toDate": to_time or "",
                "timeRangeDesc": time_desc,
                "topErrors": top_errors,
                "recordsCount": len(recs)
            }
            save_sms_cdr_summary(
                phone=clean_p,
                summary_json_str=json.dumps(summary_dict, ensure_ascii=False),
                incident_time=incident_time or "",
                ticket_code=ticket_code or ""
            )
            # Tự động lưu chi tiết danh sách bản ghi vào bảng sms_cdr_records phục vụ tra cứu & train AI
            from db_manager import save_sms_cdr_records
            save_sms_cdr_records(
                phone=clean_p,
                ticket_code=ticket_code or "",
                records=recs
            )
            res["summary"] = summary_dict
        except Exception as ex_db:
            print(f"⚠️ [CDR DB SAVE] Không thể lưu tóm tắt CDR vào database: {ex_db}")
    else:
        # Graceful Fallback: Nếu quét mạng SMSC thất bại (Watcher timeout / lỗi mạng), kiểm tra và giữ lại dữ liệu từ Database
        try:
            from db_manager import get_sms_cdr_records
            fallback_db_records = get_sms_cdr_records(clean_p, ticket_code=ticket_code, from_date=from_time, to_date=to_time, limit=limit)
            if not fallback_db_records and ticket_code:
                fallback_db_records = get_sms_cdr_records(clean_p, from_date=from_time, to_date=to_time, limit=limit)
            if fallback_db_records:
                net_err = res.get("message") or "Không thể kết nối tổng đài SMSC"
                return {
                    "success": True,
                    "phone": clean_p,
                    "total_hits": len(fallback_db_records),
                    "method": "database_fallback",
                    "source": "database_local",
                    "from_time": from_time or "--",
                    "to_time": to_time or "--",
                    "records": fallback_db_records,
                    "warning": f"Quét mạng SMSC thất bại ({net_err}). Hệ thống tự động giữ lại và hiển thị {len(fallback_db_records)} bản ghi từ Database đã lưu trước đó.",
                    "message": f"Quét mạng SMSC thất bại ({net_err}). Hệ thống tự động giữ lại và hiển thị {len(fallback_db_records)} bản ghi từ Database đã lưu trước đó."
                }
        except Exception as ex_fallback:
            print(f"⚠️ [CDR FALLBACK] Lỗi fallback Database: {ex_fallback}")

    return res


@router.get("/lib")
def get_sms_lib_data():
    """
    Trả về dữ liệu từ điển đầu số, brandname, dịch vụ từ sms_lib.json
    """
    import json
    from pathlib import Path
    lib_path = Path(__file__).resolve().parent.parent / "sms_lib.json"
    if lib_path.exists():
        try:
            with open(lib_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    return {}


@router.get("/codes")
def get_sms_code_data():
    """
    Trả về dữ liệu định nghĩa mã lỗi SMSC CDR từ sms_code.json
    """
    import json
    from pathlib import Path
    code_path = Path(__file__).resolve().parent.parent / "sms_code.json"
    if code_path.exists():
        try:
            with open(code_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    return {}


@router.api_route("/export_excel", methods=["GET", "POST"])
async def export_smsc_cdr_excel(
    request: Request,
    phone: str = Query(None, description="Số thuê bao"),
    time_range: str = Query(None, description="Mô tả dải thời gian")
):
    """
    Xuất danh sách nhật ký SMSC CDR ra file Excel (.xlsx) chuẩn phong cách VNPT.
    Hỗ trợ cả POST (truyền records lọc trực tiếp) và GET (tự động đọc từ database theo số thuê bao).
    """
    import io
    from datetime import datetime
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    records = []
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
        phone = str(body.get("phone") or phone or "SMSC_CDR").strip()
        time_range = str(body.get("time_range") or time_range or "--").strip()
        records = body.get("records") or []

    phone = str(phone or "SMSC_CDR").strip()
    time_range = str(time_range or "--").strip()

    clean_p = "".join(filter(str.isdigit, phone))
    if len(clean_p) == 9:
        clean_p = "84" + clean_p
    elif clean_p.startswith("0") and len(clean_p) == 10:
        clean_p = "84" + clean_p[1:]

    # Nếu không truyền danh sách bản ghi (ví dụ gọi từ nút Export trên bảng chi tiết qua GET), tự động lấy từ SQLite
    if not records and clean_p:
        try:
            from db_manager import get_sms_cdr_records
            records = get_sms_cdr_records(clean_p, limit=10000) or []
        except Exception as e_db:
            print(f"⚠️ [EXPORT EXCEL CDR] Lỗi đọc SQLite cho {clean_p}: {e_db}")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "SMSC_CDR_LOG"
    ws.views.sheetView[0].showGridLines = True

    # 1. Tiêu đề Banner A1:O1
    ws.merge_cells("A1:O1")
    t_cell = ws["A1"]
    t_cell.value = f"NHẬT KÝ CHI TIẾT BẢN TIN SMSC CDR - THUÊ BAO {phone}"
    t_cell.font = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    t_cell.fill = PatternFill(start_color="1F497D", fill_type="solid")
    t_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    # 2. Phụ đề thông tin tra cứu A2:O2
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    ws.merge_cells("A2:O2")
    sub_cell = ws["A2"]
    sub_cell.value = f"Kỳ đối soát: {time_range} • Thời điểm xuất: {now_str} • Tổng số bản ghi: {len(records)} dòng"
    sub_cell.font = Font(name="Segoe UI", size=9.5, italic=True, color="475569")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # 3. Headers danh sách cột chuẩn 15 cột
    headers = [
        "STT", "Site", "Calling Number", "Called Number", "Chiều",
        "Dịch Vụ / Brandname", "Delivery Time", "Submission Time",
        "Call Reference", "Độ Dài", "Số Lần Phát", "Mapped Error",
        "Trạng Thái Bản Tin", "Mã Nguyên Nhân", "Diễn Giải Nguyên Nhân Kết Thúc"
    ]
    header_fill = PatternFill(start_color="2F5597", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    ws.row_dimensions[3].height = 30
    for col_idx, h in enumerate(headers, 1):
        c = ws.cell(row=3, column=col_idx, value=h)
        c.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = thin_border

    # Fills cho trạng thái
    success_fill = PatternFill(start_color="E2EFDA", fill_type="solid")
    failed_fill = PatternFill(start_color="FCE4D6", fill_type="solid")
    pending_fill = PatternFill(start_color="FFF2CC", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", fill_type="solid")

    row_idx = 4
    for idx, r in enumerate(records, 1):
        ws.row_dimensions[row_idx].height = 24
        is_even = (idx % 2 == 0)
        curr_fill = zebra_fill if is_even else None

        dir_val = str(r.get("direction") or "").upper()
        st_code = str(r.get("status_code") or "").strip()
        st_desc = str(r.get("status_desc") or "").strip()
        t_cause = str(r.get("termination_cause") or "").strip()
        t_info = str(r.get("termination_cause_info") or "").strip()
        st_type = str(r.get("status_type") or "").lower()

        is_ok = (st_type == "success" or t_cause.upper() in ("100C", "4108") or st_code in ("100C", "4108"))
        is_fail = (st_type == "failed" or st_code == "8" or t_cause.upper() in ("175C", "130C", "135C", "136C"))
        status_fill = success_fill if is_ok else (failed_fill if is_fail else pending_fill)

        row_data = [
            idx,
            str(r.get("site") or "--"),
            str(r.get("calling_number") or "--"),
            str(r.get("called_number") or "--"),
            dir_val or "--",
            str(r.get("service_name") or r.get("brandname") or r.get("service_info") or "--"),
            str(r.get("delivery_time") or "--"),
            str(r.get("submission_time") or "--"),
            str(r.get("call_reference") or "--"),
            str(r.get("message_length") or "--"),
            str(r.get("attempts") or "--"),
            str(r.get("mapped_network_err") or r.get("mapped_network_error") or "--"),
            f"{st_code} - {st_desc}" if (st_code and st_desc and st_code != st_desc) else (st_desc or st_code or "--"),
            t_cause or "--",
            t_info or "--"
        ]

        for col_idx, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = Font(name="Segoe UI", size=9.5)
            cell.border = thin_border
            if col_idx in (1, 2, 5, 10, 11, 12, 14):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx in (3, 4, 7, 8, 9):
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = Font(name="Consolas", size=9.5)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            # Tô màu nhấn cho cột trạng thái và nguyên nhân
            if col_idx in (13, 14):
                cell.fill = status_fill
                cell.font = Font(name="Segoe UI", size=9.5, bold=True)
            elif curr_fill:
                cell.fill = curr_fill

        row_idx += 1

    # Tự động căn chỉnh độ rộng cột tối ưu
    col_widths = {
        1: 6, 2: 8, 3: 16, 4: 16, 5: 8, 6: 24, 7: 20, 8: 20,
        9: 15, 10: 10, 11: 12, 12: 14, 13: 20, 14: 16, 15: 35
    }
    for col_idx, w in col_widths.items():
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = w

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    clean_p = phone.replace("+", "").replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"SMSC_CDR_{clean_p}_{ts}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


