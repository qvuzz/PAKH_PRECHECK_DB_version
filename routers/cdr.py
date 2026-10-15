# routers/cdr.py
# Router cung cấp API tra cứu lịch sử SMSC CDR (tích hợp từ cdrsearch)

from fastapi import APIRouter, Query
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
        "active_method": "local_queue (Watcher .82)" if (is_docker or has_local_queue) else ("elastic_direct" if not is_docker else "sftp_vhkt")
    }


@router.get("/test")
def test_both_cdr_channels(phone: str = Query("84917969796", description="Số thuê bao mẫu để test")):
    """
    Chẩn đoán song song cả 3 đường tra cứu SMS CDR:
    - Kênh 1 (Local Queue): Dành cho Docker .158 trao đổi trực tiếp với Watcher trên máy .82
    - Kênh 2 (Direct Elastic): Phục vụ máy server thông thẳng tới 10.204.57.26:80
    - Kênh 3 (SFTP VHKT): Phục vụ máy cá nhân test code (10.155.139.167 -> 10.165.15.84:22)
    """
    import time
    import socket

    # 1. Kiểm tra Kênh Local Queue (Docker .158 <-> Watcher .82)
    queue_res = {
        "target": f"Local File Queue ({CDR_LOCAL_INPUT_DIR})",
        "input_dir_exists": os.path.exists(CDR_LOCAL_INPUT_DIR),
        "output_dir_exists": os.path.exists(CDR_LOCAL_OUTPUT_DIR),
        "status": "ready" if (os.path.exists(CDR_LOCAL_INPUT_DIR) and os.path.exists(CDR_LOCAL_OUTPUT_DIR)) else "not_configured",
        "message": "Thư mục hàng đợi sẵn sàng cho Watcher máy .82" if (os.path.exists(CDR_LOCAL_INPUT_DIR) and os.path.exists(CDR_LOCAL_OUTPUT_DIR)) else "Chưa tạo thư mục hàng đợi"
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

    is_docker = os.getenv("IS_DOCKER") == "1"
    if (is_docker or queue_res["status"] == "ready"):
        active_route = "Local Queue (Watcher .82)"
    elif direct_res["status"] == "ok":
        active_route = "Direct (10.204.57.26)"
    elif sftp_res["status"] == "ok":
        active_route = "SFTP VHKT (10.165.15.84)"
    else:
        active_route = "Không có đường nào thông"

    return {
        "success": queue_res["status"] == "ready" or direct_res["status"] == "ok" or sftp_res["status"] == "ok",
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

    # OFFLINE-FIRST: Nếu không yêu cầu ép cào mới (force_refresh=False), kiểm tra dữ liệu đã lưu trong SQLite trước
    if not force_refresh:
        try:
            from db_manager import get_sms_cdr_records
            db_records = get_sms_cdr_records(clean_p, ticket_code=ticket_code, limit=limit)
            if db_records and len(db_records) > 0:
                return {
                    "success": True,
                    "phone": clean_p,
                    "total_hits": len(db_records),
                    "method": "database",
                    "source": "database_local",
                    "from_time": from_time or "--",
                    "to_time": to_time or "--",
                    "records": db_records,
                    "message": f"Tìm thấy {len(db_records)} bản ghi SMSC CDR lưu trong Database (Tốc độ tức thì)"
                }
        except Exception as ex_db_read:
            print(f"⚠️ [CDR OFFLINE READ] Lỗi đọc SQLite: {ex_db_read}")

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
            mo_count = 0
            mo_ok = 0
            mt_count = 0
            mt_ok = 0
            cause_map = {}

            for r in recs:
                is_mo = (r.get("direction") and "MO" in str(r.get("direction")).upper()) or (str(r.get("calling_number")) == clean_p)
                is_ok = (r.get("status_type") == "success")
                if is_mo:
                    mo_count += 1
                    if is_ok:
                        mo_ok += 1
                else:
                    mt_count += 1
                    if is_ok:
                        mt_ok += 1

                if not is_ok:
                    cause = r.get("termination_cause_info") or r.get("termination_cause") or r.get("status_desc") or "Lỗi không xác định"
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

    return res

