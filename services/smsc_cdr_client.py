# services/smsc_cdr_client.py
# Module tích hợp tra cứu SMSC CDR từ dự án CDRSearch (Elastic trực tiếp & cầu nối SFTP VHKT)

import os
import json
import time
import tempfile
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Cấu hình Elastic SMSC (Hỗ trợ truy vấn cả 2 Site HCM & HNI, gồm M2P, P2A, P2P và Trace)
INDEX_PATTERNS = "smsc-cdr-hcm-search-m2p-*,smsc-cdr-hcm-search-p2a-*,smsc-cdr-hcm-search-p2p-*,smsc-cdr-hcm-trace-m2p-*,smsc-cdr-hcm-trace-p2a-*,smsc-cdr-hcm-trace-p2p-*,smsc-cdr-hni-search-m2p-*,smsc-cdr-hni-search-p2a-*,smsc-cdr-hni-search-p2p-*,smsc-cdr-hni-trace-m2p-*,smsc-cdr-hni-trace-p2a-*,smsc-cdr-hni-trace-p2p-*"
ELASTIC_URL = f"http://10.204.57.26/{INDEX_PATTERNS}/_search"
AUTH_HEADER = "Basic ZWxhc3RpYzpWSUFTWHRiek1MTFJhdklnTjAxQw=="

TERMINATION_CAUSE_MAP = {
    "0": "Normal / Successful",
    "0000": "Normal / Successful",
    "100c": "Message Delivery Successful",
    "100C": "Message Delivery Successful",
    "4108": "Message Delivery Successful",
    "1001": "Unidentified Subscriber",
    "1004": "Call Barred / Facility Not Supported",
    "1009": "System Failure",
    "100b": "Subscriber Busy For MT SMS",
    "100B": "Subscriber Busy For MT SMS",
    "100d": "SM Delivery Failure",
    "100D": "SM Delivery Failure",
    "100e": "Message Waiting List Full",
    "100E": "Message Waiting List Full",
    "101f": "Absent Subscriber / Not Reachable",
    "101F": "Absent Subscriber / Not Reachable",
    "1020": "Memory Capacity Exceeded",
    "1021": "Equipment Protocol Error",
    "1032": "Roaming Restriction / Barred",
    "1033": "Illegal Subscriber",
    "1034": "Bearer Service Not Provisioned",
    "1035": "Teleservice Not Provisioned",
    "1036": "Illegal Equipment"
}

def _resolve_termination_info(src: dict, term_cause: str) -> str:
    raw_info = src.get("terminationcauseinfo") or src.get("messagestate") or src.get("networkerr")
    if raw_info and str(raw_info).strip():
        return str(raw_info).strip()
    key = str(term_cause or "").strip()
    if key in TERMINATION_CAUSE_MAP:
        return TERMINATION_CAUSE_MAP[key]
    if key.upper() in TERMINATION_CAUSE_MAP:
        return TERMINATION_CAUSE_MAP[key.upper()]
    if key and key != "--":
        return f"Cause: {key}"
    return "--"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Authorization": AUTH_HEADER,
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "http://10.204.57.26",
    "Referer": "http://10.204.57.26/admin/cdr-search",
    "Connection": "keep-alive"
}

# Cấu hình SFTP VHKT
WINSCP_PATH = r"C:\Program Files (x86)\WinSCP\WinSCP.com"
if not os.path.exists(WINSCP_PATH):
    WINSCP_PATH = r"C:\Program Files\WinSCP\WinSCP.com"

SFTP_HOST = "10.165.15.84"
SFTP_USER = "ktm_soc2"
SFTP_PASS = "slkwD![l(s"
REMOTE_INPUT_DIR = "/home/sftp/ktm/soc2/quangvu/input"
REMOTE_OUTPUT_DIR = "/home/sftp/ktm/soc2/quangvu/output"
POLL_TIMEOUT_SECS = 45

# Cache kết quả ngắn hạn (5 phút) tránh gọi lặp lại
CDR_MEMORY_CACHE = {}


def _format_smsc_timestamp(val_str: str) -> str:
    """Chuyển định dạng YYMMDDhhmmss (vd: 260910110137) -> YYYY-MM-DD HH:mm:ss"""
    if not val_str or len(val_str) < 12:
        return val_str or "--"
    try:
        yy = "20" + val_str[0:2]
        mm = val_str[2:4]
        dd = val_str[4:6]
        hh = val_str[6:8]
        mi = val_str[8:10]
        ss = val_str[10:12]
        return f"{yy}-{mm}-{dd} {hh}:{mi}:{ss}"
    except Exception:
        return val_str


def _normalize_to_smsc_timestamp(val: str, is_end: bool = False) -> str:
    """Chuyển đổi linh hoạt chuỗi ngày tháng sang YYMMDDhhmmss của Elastic SMSC."""
    if not val:
        return ""
    val = str(val).strip()
    digits = "".join(filter(str.isdigit, val))
    if len(digits) == 12:
        return digits
    elif len(digits) == 14:
        return digits[2:]
    elif len(digits) == 8:  # YYYYMMDD
        yy = digits[2:4]
        mm = digits[4:6]
        dd = digits[6:8]
        return f"{yy}{mm}{dd}{'235959' if is_end else '000000'}"
    elif len(digits) == 6:  # YYMMDD
        return f"{digits}{'235959' if is_end else '000000'}"

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(val, fmt)
            if fmt in ("%Y-%m-%d", "%d/%m/%Y") and is_end:
                dt = dt.replace(hour=23, minute=59, second=59)
            return dt.strftime("%y%m%d%H%M%S")
        except Exception:
            continue
    return digits[:12] if len(digits) >= 12 else val


def _run_winscp_commands(commands: list) -> tuple[bool, str]:
    import subprocess
    if not os.path.exists(WINSCP_PATH):
        return False, f"Không tìm thấy WinSCP tại {WINSCP_PATH}"

    open_line = f'open sftp://{SFTP_USER}:{SFTP_PASS}@{SFTP_HOST}/ -hostkey=*'
    script_lines = ["option batch abort", "option confirm off", open_line] + commands + ["exit"]
    script_content = "\n".join(script_lines)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(script_content)
        script_path = f.name

    try:
        creationflags = 0
        startupinfo = None
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        cmd = [WINSCP_PATH, f"/script={script_path}"]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags,
            startupinfo=startupinfo,
            timeout=30
        )
        out = proc.stdout.decode("utf-8", errors="replace")
        return (proc.returncode == 0), out
    except Exception as e:
        return False, str(e)
    finally:
        try:
            if os.path.exists(script_path):
                os.remove(script_path)
        except Exception:
            pass


def _query_via_sftp(phone: str, direction_str: str, gte_time: str, lte_time: str, size: int) -> dict:
    """Gửi yêu cầu qua SFTP 10.165 và chờ VHKT xử lý trả kết quả"""
    req_id = f"{phone}_{datetime.now().strftime('%y%m%d%H%M%S')}"
    req_fname = f"{req_id}.req"
    json_fname = f"{req_id}.json"

    params = {
        "phone": phone,
        "direction": direction_str,
        "gte_time": gte_time,
        "lte_time": lte_time,
        "size": size,
        "elastic_url": ELASTIC_URL
    }
    req_json_str = json.dumps(params, ensure_ascii=False)

    # 1. ƯU TIÊN SỐ 1: Dùng thư viện Python thuần Paramiko (hoạt động 100% trên cả Windows, Linux và Docker)
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=SFTP_HOST,
            port=22,
            username=SFTP_USER,
            password=SFTP_PASS,
            timeout=10,
            banner_timeout=15,
            look_for_keys=False,
            allow_agent=False
        )
        sftp = ssh.open_sftp()
        try:
            # Upload .req lên input/
            remote_req = f"{REMOTE_INPUT_DIR}/{req_fname}"
            with sftp.open(remote_req, "w") as f:
                f.write(req_json_str)

            # Poll output/ chờ file .json kết quả từ máy VHKT Watcher
            remote_json = f"{REMOTE_OUTPUT_DIR}/{json_fname}"
            for _ in range(POLL_TIMEOUT_SECS):
                time.sleep(1)
                try:
                    st = sftp.stat(remote_json)
                    if st and st.st_size > 0:
                        with sftp.open(remote_json, "r") as rf:
                            raw_data = rf.read()
                            data_str = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else raw_data
                            result = json.loads(data_str)
                        # Dọn dẹp file kết quả trên SFTP sau khi đã lấy
                        try:
                            sftp.remove(remote_json)
                        except Exception:
                            pass
                        return result
                except (IOError, FileNotFoundError):
                    continue

            raise TimeoutError(f"Hết thời gian {POLL_TIMEOUT_SECS}s chờ VHKT xử lý trả kết quả CDR.")
        finally:
            try:
                sftp.close()
            except Exception:
                pass
            try:
                ssh.close()
            except Exception:
                pass
    except Exception as ex_paramiko:
        # Nếu đã là TimeoutError từ VHKT thì re-raise luôn
        if isinstance(ex_paramiko, TimeoutError):
            raise ex_paramiko

        # 2. DỰ PHÒNG: Fallback sang WinSCP nếu có cài trên Windows
        if not os.path.exists(WINSCP_PATH):
            raise RuntimeError(f"Lỗi kết nối SFTP Paramiko: {ex_paramiko}")

        temp_dir = os.path.join(tempfile.gettempdir(), "cdr_precheck")
        os.makedirs(temp_dir, exist_ok=True)
        local_req = os.path.join(temp_dir, req_fname)
        local_json = os.path.join(temp_dir, json_fname)

        with open(local_req, "w", encoding="utf-8") as f:
            f.write(req_json_str)

        remote_req = f"{REMOTE_INPUT_DIR}/{req_fname}"
        up_cmd = [f'put "{local_req}" "{remote_req}"']
        ok_up, out_up = _run_winscp_commands(up_cmd)
        if not ok_up:
            raise RuntimeError(f"Lỗi upload .req qua WinSCP: {out_up[:200]}")

        remote_json = f"{REMOTE_OUTPUT_DIR}/{json_fname}"
        for _ in range(POLL_TIMEOUT_SECS):
            time.sleep(1)
            dl_cmd = [f'get "{remote_json}" "{local_json}"']
            ok_dl, _ = _run_winscp_commands(dl_cmd)
            if ok_dl and os.path.exists(local_json) and os.path.getsize(local_json) > 0:
                with open(local_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                try:
                    os.remove(local_req)
                    os.remove(local_json)
                except Exception:
                    pass
                return data

        raise TimeoutError(f"Hết thời gian {POLL_TIMEOUT_SECS}s chờ VHKT xử lý trả kết quả CDR.")


def _query_direct_elastic(phone: str, direction_str: str, gte_time: str, lte_time: str, size: int) -> dict:
    """Truy vấn trực tiếp Elastic nếu có route mạng nội bộ (timeout nhanh 3.5s)"""
    if direction_str == "MO (Gửi đi)":
        must_clauses = [
            {"range": {"deliverytime": {"gte": gte_time, "lte": lte_time}}},
            {"query_string": {"fields": ["callingnumber"], "query": phone}},
            {"query_string": {"fields": ["callednumber"], "query": "*"}}
        ]
    elif direction_str == "MT (Nhận vào)":
        must_clauses = [
            {"range": {"deliverytime": {"gte": gte_time, "lte": lte_time}}},
            {"query_string": {"fields": ["callednumber"], "query": phone}},
            {"query_string": {"fields": ["callingnumber"], "query": "*"}}
        ]
    else:
        must_clauses = [
            {"range": {"deliverytime": {"gte": gte_time, "lte": lte_time}}},
            {"bool": {"should": [
                {"query_string": {"fields": ["callingnumber"], "query": phone}},
                {"query_string": {"fields": ["callednumber"], "query": phone}}
            ]}}
        ]

    size = min(max(int(size or 100), 1), 10000)
    params = {
        "ignore_unavailable": "true",
        "from": 0,
        "size": size,
        "sort": "@timestamp:desc"
    }

    payload = {
        "query": {
            "bool": {
                "must": must_clauses
            }
        }
    }

    resp = requests.post(
        ELASTIC_URL,
        params=params,
        headers=HEADERS,
        json=payload,
        timeout=3.5
    )
    resp.raise_for_status()
    return resp.json()


def fetch_smsc_cdr(
    phone: str,
    direction: str = "both",
    from_time_str: str = None,
    to_time_str: str = None,
    hours: int = 48,
    limit: int = 100
) -> dict:
    """
    Tra cứu SMSC CDR cho số thuê bao:
    - direction: 'both', 'mo' (gửi đi), 'mt' (nhận vào)
    - from_time_str, to_time_str: định dạng YYMMDDhhmmss (hoặc để None để tự động tính theo `hours`)
    - Trả về dict chuẩn hóa: { success, phone, total_hits, method, records, message }
    """
    limit = min(max(int(limit or 100), 1), 10000)
    # Chuẩn hóa phone: 84xxxxxxxxx
    clean_p = "".join(filter(str.isdigit, str(phone or "").strip()))
    if len(clean_p) == 9:
        clean_p = "84" + clean_p
    elif clean_p.startswith("0") and len(clean_p) == 10:
        clean_p = "84" + clean_p[1:]

    now = datetime.now()
    if to_time_str:
        to_time_str = _normalize_to_smsc_timestamp(to_time_str, is_end=True)
    else:
        to_time_str = now.strftime("%y%m%d%H%M%S")

    if from_time_str:
        from_time_str = _normalize_to_smsc_timestamp(from_time_str, is_end=False)
    else:
        from_time_str = (now - timedelta(hours=hours)).strftime("%y%m%d%H%M%S")

    dir_map = {
        "mo": "MO (Gửi đi)",
        "mt": "MT (Nhận vào)",
        "both": "Cả hai chiều"
    }
    dir_label = dir_map.get(direction.lower(), "Cả hai chiều")

    cache_key = f"{clean_p}_{direction}_{from_time_str}_{to_time_str}_{limit}"
    cached = CDR_MEMORY_CACHE.get(cache_key)
    if cached and (time.time() - cached["cached_at"] < 180):
        return cached["data"]

    method_used = "direct"
    raw_result = None
    err_direct = None

    # Thử gọi Elastic trực tiếp trước
    try:
        raw_result = _query_direct_elastic(clean_p, dir_label, from_time_str, to_time_str, limit)
    except Exception as ex_dir:
        err_direct = str(ex_dir)
        # Nếu trực tiếp timeout/lỗi, chuyển sang SFTP qua VHKT
        try:
            method_used = "sftp_vhkt"
            if direction.lower() in ("both", "cả hai chiều", "all"):
                # SFTP VHKT hiện tại xử lý theo chiều đơn lẻ, thực hiện truy vấn cả MO và MT rồi gộp lại
                raw_mo = None
                raw_mt = None
                try:
                    raw_mo = _query_via_sftp(clean_p, "MO (Gửi đi)", from_time_str, to_time_str, limit)
                except Exception as e_mo:
                    pass
                try:
                    raw_mt = _query_via_sftp(clean_p, "MT (Nhận vào)", from_time_str, to_time_str, limit)
                except Exception as e_mt:
                    pass

                if not raw_mo and not raw_mt:
                    raise RuntimeError("Cả 2 chiều MO và MT qua SFTP VHKT đều không phản hồi kết quả.")

                hits_mo = raw_mo.get("hits", {}).get("hits", []) if isinstance(raw_mo, dict) else []
                hits_mt = raw_mt.get("hits", {}).get("hits", []) if isinstance(raw_mt, dict) else []

                seen_ids = set()
                merged_hits = []
                for h in hits_mo + hits_mt:
                    hid = h.get("_id")
                    if hid:
                        if hid not in seen_ids:
                            seen_ids.add(hid)
                            merged_hits.append(h)
                    else:
                        merged_hits.append(h)

                def _get_sort_key(hit):
                    s = hit.get("_source", {})
                    return str(s.get("deliverytime") or s.get("@timestamp") or "")

                merged_hits.sort(key=_get_sort_key, reverse=True)

                val_mo = raw_mo.get("hits", {}).get("total", {}).get("value", len(hits_mo)) if isinstance(raw_mo, dict) else 0
                val_mt = raw_mt.get("hits", {}).get("total", {}).get("value", len(hits_mt)) if isinstance(raw_mt, dict) else 0

                raw_result = {
                    "hits": {
                        "total": {"value": max(val_mo + val_mt, len(merged_hits))},
                        "hits": merged_hits[:limit]
                    }
                }
            else:
                sftp_dir = "MT (Nhận vào)" if direction.lower() == "mt" else "MO (Gửi đi)"
                raw_result = _query_via_sftp(clean_p, sftp_dir, from_time_str, to_time_str, limit)
        except Exception as ex_sftp:
            return {
                "success": False,
                "phone": clean_p,
                "total_hits": 0,
                "method": "failed",
                "records": [],
                "message": f"Không thể kết nối SMSC (Direct: {err_direct} | SFTP VHKT: {ex_sftp})"
            }

    # Bóc tách và chuẩn hóa bản ghi
    hits = raw_result.get("hits", {}).get("hits", [])
    total_val = raw_result.get("hits", {}).get("total", {}).get("value", len(hits))

    records = []
    for h in hits:
        src = h.get("_source", {})
        idx = str(h.get("_index", "")).lower()
        tags = [str(t).lower() for t in src.get("tags", [])] if isinstance(src.get("tags"), list) else []

        # 1. Xác định Site (HCM / HNI)
        if "hni" in idx or "hni" in tags:
            site = "HNI"
        elif "hcm" in idx or "hcm" in tags:
            site = "HCM"
        else:
            site = "HCM"

        calling = str(src.get("callingnumber") or "").strip()
        called = str(src.get("callednumber") or "").strip()
        dt_raw = src.get("deliverytime") or ""
        dt_fmt = _format_smsc_timestamp(dt_raw)
        sub_raw = src.get("submissiontime") or ""
        sub_fmt = _format_smsc_timestamp(sub_raw)

        # 2. Xác định chiều
        is_mo = (calling == clean_p or clean_p.endswith(calling) or (len(calling) >= 9 and calling.endswith(clean_p[-9:])))
        record_dir = "MO (Gửi đi)" if is_mo else "MT (Nhận đến)"

        status_code = str(src.get("status", "")).strip()
        term_cause = str(src.get("terminationcause") or src.get("resultcode") or "").strip()
        mapped_net_err = str(src.get("mappednetworkerr") or src.get("localerr") or "--").strip()
        term_info = _resolve_termination_info(src, term_cause)

        # 3. Đánh giá trạng thái thành công / lỗi chuẩn xác
        is_term_ok = (term_cause in ("0", "0000", "100C", "100c", "4108", "") or term_cause == "--")
        if status_code in ("8", "0") or (status_code == "2" and is_term_ok) or term_cause in ("100C", "100c", "4108"):
            status_desc = "Thành công (Đã phát đến thuê bao)"
            status_type = "success"
        elif status_code in ("1", "3") or (status_code == "2" and not is_term_ok):
            status_desc = f"Chờ gửi / Đang thử lại (Status: {status_code})"
            status_type = "pending"
        else:
            status_desc = f"Thất bại (Status: {status_code}, Cause: {term_cause})"
            status_type = "failed"

        records.append({
            "site": site,
            "calling_number": calling,
            "called_number": called,
            "delivery_time": dt_fmt,
            "originating_msc": str(src.get("originatingmscaddress") or "--"),
            "destination_msc": str(src.get("destinationmscaddress") or "--"),
            "submission_time": sub_fmt,
            "call_reference": str(src.get("callreference") or "--"),
            "message_length": str(src.get("messagelength") or "--"),
            "attempts": src.get("numberofattempts") or 1,
            "mapped_network_err": mapped_net_err,
            "status_code": status_code,
            "status_desc": status_desc,
            "status_type": status_type,
            "termination_cause": term_cause or "--",
            "termination_cause_info": term_info,
            "direction": record_dir,
            "raw": src
        })

    result_data = {
        "success": True,
        "phone": clean_p,
        "total_hits": total_val,
        "method": method_used,
        "source": "elastic_direct" if method_used == "direct" else "vhkt_bridge",
        "from_time": _format_smsc_timestamp(from_time_str),
        "to_time": _format_smsc_timestamp(to_time_str),
        "records": records,
        "message": f"Tìm thấy {len(records)} bản ghi SMSC CDR ({method_used})"
    }

    CDR_MEMORY_CACHE[cache_key] = {
        "cached_at": time.time(),
        "data": result_data
    }

    return result_data
