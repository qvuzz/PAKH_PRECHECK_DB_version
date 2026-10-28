# services/smsc_cdr_client.py
# Module tích hợp tra cứu SMSC CDR từ dự án CDRSearch (Elastic trực tiếp & cầu nối SFTP VHKT)

import os
import json
import time
import tempfile
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Cấu hình Elastic SMSC (Hỗ trợ truy vấn cả 2 Site HCM & HN, gồm M2P, P2A, P2P và Trace, bao gồm cả cụm HN và HNI)
HN_INDEX_PATTERNS = "smsc-cdr-hn-search-m2p-*,smsc-cdr-hn-search-p2a-*,smsc-cdr-hn-search-p2p-*,smsc-cdr-hn-trace-m2p-*,smsc-cdr-hn-trace-p2a-*,smsc-cdr-hn-trace-p2p-*,smsc-cdr-hni-search-m2p-*,smsc-cdr-hni-search-p2a-*,smsc-cdr-hni-search-p2p-*,smsc-cdr-hni-trace-m2p-*,smsc-cdr-hni-trace-p2a-*,smsc-cdr-hni-trace-p2p-*"
HCM_INDEX_PATTERNS = "smsc-cdr-hcm-search-m2p-*,smsc-cdr-hcm-search-p2a-*,smsc-cdr-hcm-search-p2p-*,smsc-cdr-hcm-trace-m2p-*,smsc-cdr-hcm-trace-p2a-*,smsc-cdr-hcm-trace-p2p-*"
INDEX_PATTERNS = f"{HCM_INDEX_PATTERNS},{HN_INDEX_PATTERNS}"
ALL_INDEX_PATTERNS = INDEX_PATTERNS

ELASTIC_HOSTS = ["10.204.57.26"]
DIRECT_TIMEOUT_SECS = 5.0
ELASTIC_URL = f"http://{ELASTIC_HOSTS[0]}/{ALL_INDEX_PATTERNS}/_search"
AUTH_HEADER = "Basic ZWxhc3RpYzpWSUFTWHRiek1MTFJhdklnTjAxQw=="

def get_elastic_url_for_site(site_opt: str = "all") -> str:
    s = str(site_opt or "all").strip().lower()
    if s in ("hn", "hni", "hanoi", "ha_noi"):
        p = HN_INDEX_PATTERNS
    elif s in ("hcm", "hcmc", "sg", "sai_gon"):
        p = HCM_INDEX_PATTERNS
    else:
        p = ALL_INDEX_PATTERNS
    return f"http://{ELASTIC_HOSTS[0]}/{p}/_search"

TERMINATION_CAUSE_MAP = {
    "0": "Normal / Successful",
    "0000": "Normal / Successful",
    "100c": "Message Delivery Successful",
    "100C": "Message Delivery Successful",
    "130c": "SRI-for-SM / Routing Failure (Unknown Subscriber / Check MAP Error)",
    "130C": "SRI-for-SM / Routing Failure (Unknown Subscriber / Check MAP Error)",
    "135c": "Message Waiting / Delivery Protocol Failure (Intermediate)",
    "135C": "Message Waiting / Delivery Protocol Failure (Intermediate)",
    "136c": "Delivery Failure / Anti-Spam Policy Rejection (Spam Retry Loop)",
    "136C": "Delivery Failure / Anti-Spam Policy Rejection (Spam Retry Loop)",
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

SFTP_HOST = os.getenv("SFTP_HOST", "10.165.15.84")
SFTP_PORT = int(os.getenv("SFTP_PORT", "22"))
SFTP_USER = os.getenv("SFTP_USER", "ktm_soc2")
SFTP_PASS = os.getenv("SFTP_PASS", "slkwD![l(s")
REMOTE_INPUT_DIR = os.getenv("REMOTE_INPUT_DIR", "/home/sftp/ktm/soc2/quangvu/input")
REMOTE_OUTPUT_DIR = os.getenv("REMOTE_OUTPUT_DIR", "/home/sftp/ktm/soc2/quangvu/output")
POLL_TIMEOUT_SECS = 120

def _get_poll_timeout_for_size(size: int = 100) -> int:
    """Tính toán thời gian timeout linh hoạt dựa trên dung lượng số bản ghi truy vấn."""
    if size >= 5000:
        return 60   # 60s cho ca lớn (5.000 - 10.000 bản ghi qua 18 index Elastic và Watcher)
    elif size >= 1000:
        return 45   # 45s cho ca trung bình
    return 30       # 30s cho truy vấn thông thường

# Cấu hình Hàng đợi Local (cho Docker .158 trao đổi trực tiếp với Watcher trên máy .82)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CDR_QUEUE_DIR = os.getenv("CDR_QUEUE_DIR", os.path.join(BASE_DIR, "cdr_queue"))
CDR_LOCAL_INPUT_DIR = os.path.join(CDR_QUEUE_DIR, "input")
CDR_LOCAL_OUTPUT_DIR = os.path.join(CDR_QUEUE_DIR, "output")
try:
    os.makedirs(CDR_LOCAL_INPUT_DIR, exist_ok=True)
    os.makedirs(CDR_LOCAL_OUTPUT_DIR, exist_ok=True)
except Exception:
    pass

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

    open_line = f'open sftp://{SFTP_USER}:{SFTP_PASS}@{SFTP_HOST}:{SFTP_PORT}/ -hostkey=*'
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


def _merge_mo_mt_hits(raw_mo: dict, raw_mt: dict, limit: int) -> dict:
    """Gộp các bản ghi hai chiều MO và MT từ kết quả query, sắp xếp giảm dần theo thời gian"""
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

    return {
        "hits": {
            "total": {"value": max(val_mo + val_mt, len(merged_hits))},
            "hits": merged_hits[:limit]
        }
    }


def _query_via_local_queue(phone: str, direction_str: str, gte_time: str, lte_time: str, size: int, target_url: str = None) -> dict:
    """
    Gửi yêu cầu qua Hàng đợi Local File (cho Docker .158 trao đổi trực tiếp với Watcher trên máy .82).
    - Input: ghi file .req vào CDR_LOCAL_INPUT_DIR (/app/cdr_queue/input)
    - Output: chờ Watcher trên máy .82 nhả file .json vào CDR_LOCAL_OUTPUT_DIR (/app/cdr_queue/output)
    """
    os.makedirs(CDR_LOCAL_INPUT_DIR, exist_ok=True)
    os.makedirs(CDR_LOCAL_OUTPUT_DIR, exist_ok=True)

    dir_tag = "MO" if "MO" in str(direction_str).upper() else ("MT" if "MT" in str(direction_str).upper() else "ALL")
    req_id = f"{phone}_{dir_tag}_{datetime.now().strftime('%y%m%d%H%M%S%f')[:16]}"
    req_fname = f"{req_id}.req"
    json_fname = f"{req_id}.json"

    params = {
        "phone": phone,
        "direction": direction_str,
        "gte_time": gte_time,
        "lte_time": lte_time,
        "size": size,
        "elastic_url": target_url or ELASTIC_URL
    }
    req_json_str = json.dumps(params, ensure_ascii=False)

    local_req = os.path.join(CDR_LOCAL_INPUT_DIR, req_fname)
    local_json = os.path.join(CDR_LOCAL_OUTPUT_DIR, json_fname)

    # 1. Ghi file .req vào input/
    with open(local_req, "w", encoding="utf-8") as f:
        f.write(req_json_str)

    # 2. Polling chờ file .json kết quả từ output/ do Watcher máy .82 ghi về
    current_poll_timeout = _get_poll_timeout_for_size(size)
    for _ in range(current_poll_timeout):
        time.sleep(1)
        if os.path.exists(local_json) and os.path.getsize(local_json) > 0:
            try:
                with open(local_json, "r", encoding="utf-8") as rf:
                    data = json.load(rf)
                # Dọn dẹp file kết quả và file request sau khi đọc thành công
                try:
                    os.remove(local_json)
                except Exception:
                    pass
                try:
                    if os.path.exists(local_req):
                        os.remove(local_req)
                except Exception:
                    pass
                return data
            except json.JSONDecodeError:
                continue

    # Nếu timeout, dọn file .req tránh đầy thư mục
    try:
        if os.path.exists(local_req):
            os.remove(local_req)
    except Exception:
        pass

    raise TimeoutError(f"Hết thời gian {current_poll_timeout}s chờ Watcher trên máy .82 xử lý kết quả CDR ({size} bản ghi).")


def _query_via_sftp(phone: str, direction_str: str, gte_time: str, lte_time: str, size: int, target_url: str = None) -> dict:
    """Gửi yêu cầu qua SFTP 10.165 (/home/sftp/ktm/soc2/quangvu/input -> output) và chờ VHKT Watcher xử lý trả kết quả"""
    dir_tag = "MO" if "MO" in str(direction_str).upper() else ("MT" if "MT" in str(direction_str).upper() else "ALL")
    req_id = f"{phone}_{dir_tag}_{datetime.now().strftime('%y%m%d%H%M%S%f')[:16]}"
    req_fname = f"{req_id}.req"
    json_fname = f"{req_id}.json"

    params = {
        "phone": phone,
        "direction": direction_str,
        "gte_time": gte_time,
        "lte_time": lte_time,
        "size": size,
        "elastic_url": target_url or ELASTIC_URL
    }
    req_json_str = json.dumps(params, ensure_ascii=False)

    # 1. ƯU TIÊN SỐ 1: Dùng thư viện Python thuần Paramiko (hoạt động 100% trên cả Windows, Linux và Docker)
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=SFTP_HOST,
            port=SFTP_PORT,
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
            current_poll_timeout = _get_poll_timeout_for_size(size)
            for _ in range(current_poll_timeout):
                time.sleep(1)
                try:
                    st = sftp.stat(remote_json)
                    if st and st.st_size > 0:
                        with sftp.open(remote_json, "r") as rf:
                            raw_data = rf.read()
                            data_str = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else raw_data
                            result = json.loads(data_str)
                        # Dọn dẹp file kết quả và file request trên SFTP sau khi đã lấy
                        try:
                            sftp.remove(remote_json)
                        except Exception:
                            pass
                        try:
                            sftp.remove(remote_req)
                        except Exception:
                            pass
                        return result
                except (IOError, FileNotFoundError, json.JSONDecodeError):
                    continue

            # Dọn file .req nếu hết thời gian chờ tránh tồn đọng trong input/
            try:
                sftp.remove(remote_req)
            except Exception:
                pass
            raise TimeoutError(f"Hết thời gian {current_poll_timeout}s chờ VHKT (10.165.15.84) xử lý trả kết quả CDR ({size} bản ghi).")
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


def _query_direct_elastic(phone: str, direction_str: str, gte_time: str, lte_time: str, size: int, target_url: str = None) -> dict:
    """Truy vấn trực tiếp Elastic nếu có route mạng nội bộ (hỗ trợ thử tuần tự các IP máy chủ Elastic SMSC)"""
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

    last_error = None
    query_url = target_url or ELASTIC_URL
    custom_headers = dict(HEADERS)
    custom_headers["Origin"] = "http://10.204.57.26"
    custom_headers["Referer"] = "http://10.204.57.26/admin/cdr-search"
    try:
        resp = requests.post(
            query_url,
            params=params,
            headers=custom_headers,
            json=payload,
            timeout=DIRECT_TIMEOUT_SECS
        )
        if resp.status_code == 200:
            return resp.json()
        last_error = f"HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as ex:
        last_error = f"Error: {ex}"

    raise RuntimeError(f"Máy chủ Elastic SMSC không phản hồi: {last_error}")


def fetch_smsc_cdr(
    phone: str,
    direction: str = "both",
    from_time_str: str = None,
    to_time_str: str = None,
    hours: int = 48,
    limit: int = 100,
    site: str = "all",
    **kwargs
) -> dict:
    """
    Tra cứu SMSC CDR cho số thuê bao:
    - direction: 'both', 'mo' (gửi đi), 'mt' (nhận vào)
    - site: 'all' (Cả hai Site), 'hn' (Hà Nội), 'hcm' (Hồ Chí Minh)
    - from_time_str, to_time_str: định dạng YYMMDDhhmmss (hoặc để None để tự động tính theo `hours`)
    - Trả về dict chuẩn hóa: { success, phone, total_hits, method, records, message }
    """
    # Hỗ trợ linh hoạt các tên tham số thay thế
    if not from_time_str and "from_time" in kwargs:
        from_time_str = kwargs["from_time"]
    if not to_time_str and "to_time" in kwargs:
        to_time_str = kwargs["to_time"]

    if str(direction or "").lower() in ("all", "both", "cả hai chiều"):
        direction = "both"

    limit = min(max(int(limit or 100), 1), 10000)
    target_elastic_url = get_elastic_url_for_site(site)

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

    cache_key = f"{clean_p}_{direction}_{from_time_str}_{to_time_str}_{limit}_{site}"
    cached = CDR_MEMORY_CACHE.get(cache_key)
    if cached and (time.time() - cached["cached_at"] < 180):
        return cached["data"]

    method_used = "sftp_vhkt"
    raw_result = None
    err_sftp = None
    err_direct = None
    err_queue = None

    # 1. KÊNH ƯU TIÊN SỐ 1: Cầu nối SFTP VHKT 10.165.15.84 (/home/sftp/ktm/soc2/quangvu/input -> output)
    # Hoạt động đồng nhất trên cả Container Docker (.158) lẫn máy Local thông qua thư viện Paramiko
    try:
        method_used = "sftp_vhkt"
        if direction.lower() in ("both", "cả hai chiều", "all"):
            raw_mo = None
            raw_mt = None
            err_mo = None
            err_mt = None
            try:
                raw_mo = _query_via_sftp(clean_p, "MO (Gửi đi)", from_time_str, to_time_str, limit, target_url=target_elastic_url)
            except Exception as e_mo:
                err_mo = str(e_mo)
            try:
                raw_mt = _query_via_sftp(clean_p, "MT (Nhận vào)", from_time_str, to_time_str, limit, target_url=target_elastic_url)
            except Exception as e_mt:
                err_mt = str(e_mt)

            if not raw_mo and not raw_mt:
                raise RuntimeError(f"SFTP 10.165.15.84 không phản hồi kết quả: MO ({err_mo or 'không có dữ liệu'}) | MT ({err_mt or 'không có dữ liệu'})")

            raw_result = _merge_mo_mt_hits(raw_mo or {}, raw_mt or {}, limit)
        else:
            sftp_dir = "MT (Nhận vào)" if direction.lower() == "mt" else "MO (Gửi đi)"
            raw_result = _query_via_sftp(clean_p, sftp_dir, from_time_str, to_time_str, limit, target_url=target_elastic_url)
    except Exception as ex_sftp:
        err_sftp = str(ex_sftp)
        raw_result = None

    # 2. KÊNH DỰ PHÒNG 2: Direct Elastic (nếu máy có kết nối thẳng mạng tới 10.204.57.26)
    if not raw_result:
        try:
            method_used = "direct"
            raw_result = _query_direct_elastic(clean_p, dir_label, from_time_str, to_time_str, limit, target_url=target_elastic_url)
        except Exception as ex_dir:
            err_direct = str(ex_dir)

    if not raw_result:
        return {
            "success": False,
            "phone": clean_p,
            "total_hits": 0,
            "method": "failed",
            "records": [],
            "message": f"Không thể lấy SMSC CDR (SFTP 10.165: {err_sftp or '--'} | Direct: {err_direct or '--'})"
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
        origin = str(h.get("_site_origin") or "").upper()
        if "HNI" in origin or "HN" in origin:
            site = "HNI"
        elif "HCM" in origin:
            site = "HCM"
        elif "hn" in idx or "hni" in idx or "hn" in tags or "hni" in tags:
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

        attempts_raw = src.get("numberofattempts") or src.get("attempts") or src.get("retry_count") or 1
        attempts_str = str(attempts_raw).strip()

        # 3. Đánh giá trạng thái thành công / lỗi chuẩn xác (Chuẩn 3GPP TS 23.040 & VNPT SMSC)
        # QUY TẮC A: Bản ghi có CAUSE == "199C" hoặc attempts == "000" hoặc Status 12 là log tiếp nhận trung gian / ghép mảnh tin dài, TUYỆT ĐỐI KHÔNG PHẢI LỖI VÀ CHƯA PHẢI THÀNH CÔNG!
        is_intermediate = (term_cause.upper() == "199C" or attempts_str in ("0", "000") or status_code == "12")

        fail_causes = {
            "130C", "135C", "136C", "101F", "1020", "1001", "1004", "1009", "100B", 
            "100D", "100E", "1021", "1032", "1033", "1034", "1035", "1036", "175C", "103C"
        }
        tc_up = term_cause.upper()
        sc_up = status_code.upper()
        is_success_cause = (tc_up in ("100C", "133C", "4108") or sc_up in ("100C", "133C", "4108")) and not is_intermediate
        is_fail_cause = tc_up in fail_causes or status_code in ("1", "3", "4", "5", "7", "8")

        is_delivered = is_success_cause or (status_code == "2" and not is_fail_cause and not is_intermediate and tc_up in ("0", "0000", "", "--"))

        if is_intermediate:
            status_desc = f"Tiếp nhận phân mảnh tin dài (Intermediate - Status: {status_code or '--'}, Cause: {term_cause or '199C'})"
            status_type = "intermediate"
            is_delivered = False
        elif is_delivered:
            status_desc = f"Thành công (Đã phát đến thuê bao/đối tác - Status: {status_code}, Cause: {term_cause or '100C'})"
            status_type = "success"
        elif status_code == "8":
            status_desc = f"Bị từ chối / Chặn cước OCS (Status: 8, Cause: {term_cause or '--'})"
            status_type = "failed"
        elif status_code == "0":
            status_desc = f"Đang trong hàng đợi SMSC (Status: 0, Cause: {term_cause or '--'})"
            status_type = "pending"
        elif status_code in ("1", "3", "4", "5", "7", "12"):
            status_desc = f"Thất bại (Status: {status_code}, Cause: {term_cause or '--'})"
            status_type = "failed"
        else:
            status_desc = f"Thất bại (Status: {status_code or '--'}, Cause: {term_cause or '--'})"
            status_type = "failed"

        # Bóc tách linh hoạt các biến thể key từ SMSC Elastic/Logstash
        orig_msc = str(
            src.get("originatingmscaddress") or src.get("originating_msc") or 
            src.get("orig_msc") or src.get("originating_msc_address") or 
            src.get("msc_in") or "--"
        ).strip()
        dest_msc = str(
            src.get("destinationmscaddress") or src.get("destination_msc") or 
            src.get("dest_msc") or src.get("destination_msc_address") or 
            src.get("msc_out") or "--"
        ).strip()
        call_ref = str(
            src.get("callreference") or src.get("call_reference") or 
            src.get("callref") or src.get("callRef") or 
            src.get("reference") or src.get("call_id") or 
            src.get("callid") or src.get("session_id") or 
            src.get("seq") or "--"
        ).strip()

        records.append({
            "site": site,
            "calling_number": calling,
            "called_number": called,
            "delivery_time": dt_fmt,
            "originating_msc": orig_msc or "--",
            "destination_msc": dest_msc or "--",
            "submission_time": sub_fmt,
            "call_reference": call_ref or "--",
            "message_length": str(src.get("messagelength") or "--"),
            "attempts": src.get("numberofattempts") or 1,
            "mapped_network_err": mapped_net_err,
            "status_code": status_code,
            "status_desc": status_desc,
            "status_type": status_type,
            "is_success": is_delivered,
            "is_intermediate": is_intermediate,
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
        "source": "local_queue" if method_used == "local_queue" else ("elastic_direct" if method_used == "direct" else "vhkt_bridge"),
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


# Alias tương thích ngược
get_smsc_cdr = fetch_smsc_cdr

