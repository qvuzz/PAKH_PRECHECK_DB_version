# db_manager.py
import sqlite3
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tickets.db"

_db_initialized = False

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  # Tăng tốc độ và chống khóa file
    conn.execute("PRAGMA busy_timeout=60000;")
    return conn

def init_db():
    global _db_initialized
    if _db_initialized:
        return
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                phone TEXT,
                incident_time TEXT,
                package_title TEXT,
                real_packages TEXT,
                rat_types TEXT,
                cem_data TEXT,
                app_usage TEXT,
                ticket_content TEXT,
                status TEXT,
                comment TEXT,
                action_plan TEXT,
                color TEXT,
                ticket_status TEXT DEFAULT 'Chưa đóng',
                created_time TEXT,
                ai_summary TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (phone, incident_time)
            );
        """)
        # Migration cho database cũ nếu chưa có cột ai_summary, source, ticket_code
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN ai_summary TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN source TEXT DEFAULT 'tts_old';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN ticket_code TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN ticket_id INTEGER;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN flow_id INTEGER;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN closed_by TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN reopen_count INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN last_reopened_date TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN phan_hoi_he_thong INTEGER DEFAULT 1;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN id_he_thong INTEGER DEFAULT 0;")
        except Exception:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tts_new_stages (
                phone TEXT PRIMARY KEY,
                ticket_code TEXT,
                round INTEGER DEFAULT 1,
                round1_flow_id INTEGER,
                round1_done_at TIMESTAMP,
                round2_flow_id INTEGER,
                round2_done_at TIMESTAMP,
                status TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.close()
    _db_initialized = True

def record_ttsnew_stage(phone: str, ticket_code: str = "", round_num: int = 1, flow_id: int = None, status: str = ""):
    """Lưu vết tiến trình đóng phiếu 2 vòng trên TTS Mới."""
    from datetime import datetime
    init_db()
    conn = get_db_connection()
    with conn:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        existing = conn.execute("SELECT * FROM tts_new_stages WHERE phone = ?", (phone,)).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO tts_new_stages (phone, ticket_code, round, round1_flow_id, round1_done_at, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (phone, ticket_code, round_num, flow_id if round_num == 1 else None, now_str if round_num == 1 else None, status, now_str))
        else:
            if round_num == 1:
                conn.execute("""
                    UPDATE tts_new_stages 
                    SET ticket_code = COALESCE(?, ticket_code), round = 1, round1_flow_id = ?, round1_done_at = ?, status = ?, updated_at = ?
                    WHERE phone = ?
                """, (ticket_code, flow_id, now_str, status, now_str, phone))
            else:
                conn.execute("""
                    UPDATE tts_new_stages 
                    SET ticket_code = COALESCE(?, ticket_code), round = 2, round2_flow_id = ?, round2_done_at = ?, status = ?, updated_at = ?
                    WHERE phone = ?
                """, (ticket_code, flow_id, now_str, status, now_str, phone))
    conn.close()

def get_ttsnew_stage(phone: str) -> dict:
    """Lấy thông tin stage đóng phiếu của thuê bao trên TTS Mới."""
    init_db()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM tts_new_stages WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def check_ticket_can_close(t):
    """
    Kiểm tra xem 1 phiếu có đủ điều kiện để đóng tự động / thủ công hay không.
    Trả về tuple: (can_close: bool, reason: str)
    """
    ticket_st = str(t.get("ticket_status") or "")
    if ticket_st in ("Đã đóng", "Da dong"):
        return True, "Đã đóng"

    # THÔNG TIN MỞ LẠI TTS: Nếu số lần mở lại khác 0 (> 0) thì TUYỆT ĐỐI không tự động đóng
    reopen_count = int(t.get("reopen_count") or 0)
    if reopen_count > 0:
        return False, f"⚠️ Phiếu đã mở lại {reopen_count} lần (THÔNG TIN MỞ LẠI TTS) - KHÔNG ĐÓNG TỰ ĐỘNG, yêu cầu KTV kiểm tra kỹ!"

    # BẢO VỆ AN TOÀN TUYỆT ĐỐI: Chỉ tự động đóng cho phiếu thuộc dịch vụ Mobile Internet / Data
    pkg_title_raw = str(t.get("package_title") or t.get("title") or "").strip()
    if pkg_title_raw and not is_mobile_internet_ticket(pkg_title_raw):
        return False, f"Phiếu thuộc dịch vụ [{pkg_title_raw}] (ngoài Data/Mobile Internet) - KHÔNG ĐÓNG TỰ ĐỘNG, KTV xử lý thủ công!"

    status = str(t.get("status", "")).strip()
    if not status or status.upper() in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", "--", "NONE", "NULL"):
        return False, "Chưa có kết quả tiền kiểm tra kỹ thuật"

    # PHẢN ÁNH LỖI ỨNG DỤNG CỤ THỂ (ZALO, TIKTOK...): Bắt buộc KTV review, tuyệt đối không đóng tự động
    st_raw = status.lower()
    sum_raw = str(t.get("ai_summary", "") or t.get("ticket_content", "")).lower()
    if "lỗi ứng dụng" in st_raw or "lỗi ứng dụng cụ thể" in sum_raw:
        return False, "Khách hàng phản ánh lỗi ứng dụng cụ thể (Zalo, TikTok...) - Dành cho KTV kiểm tra xử lý, không đóng tự động!"

    try:
        from update_tts import excel_reader

        norm_status = excel_reader.normalize_text(status)

        ai_sum = t.get("ai_summary") or t.get("ticket_content") or ""
        rec = {
            "status": status,
            "phone": t.get("phone", ""),
            "comment": t.get("comment", ""),
            "action_plan": t.get("action_plan", ""),
            "ai_summary": ai_sum,
            "access_status": excel_reader.get_access_status(ai_sum),
            "error_area": excel_reader.get_error_area(ai_sum),
        }

        matched_nguyen_nhan, _ = excel_reader.get_nguyen_nhan_and_action(rec)
        if not matched_nguyen_nhan:
            return False, f"Chưa có mapping nguyên nhân đóng trên TTS cho [{status}]"

        can_close = excel_reader.is_level_1_auto_close_candidate(rec)
        if can_close:
            return True, "Đủ điều kiện tự động đóng"
        else:
            return False, f"Trạng thái [{status}] chưa đủ điều kiện tự đóng (dành cho KTV kiểm tra xử lý)"
    except Exception as e:
        return False, f"Lỗi kiểm tra điều kiện: {e}"

def save_or_update_ticket(t):
    """
    Lưu hoặc cập nhật phiếu vào database theo cặp (phone, incident_time).
    Mỗi lần phản ánh ở các mốc thời gian khác nhau sẽ là một bản ghi riêng biệt.
    """
    phone = str(t.get("phone", "")).strip()
    incident_time = str(t.get("incident_time", "")).strip() or "Không xác định"
    if not phone:
        return

    init_db()
    import time
    for attempt in range(5):
        conn = None
        try:
            conn = get_db_connection()
            with conn:
                source = t.get("source", "tts_old") or "tts_old"
                ticket_code = t.get("ticket_code", "")
        
                # 1. Chống trùng lặp theo ticket_code (dành riêng cho TTS Mới)
                if ticket_code:
                    existing_code = conn.execute(
                        "SELECT * FROM tickets WHERE ticket_code = ?", 
                        (ticket_code,)
                    ).fetchone()
                    if existing_code and existing_code["incident_time"] != incident_time:
                        # Kế thừa kết quả tiền kiểm cũ trước khi xóa bản ghi lệch thời gian
                        has_old_eval = existing_code["status"] and existing_code["status"] not in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", None, "")
                        if has_old_eval:
                            if not t.get("status") or t.get("status") in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", ""):
                                t["status"] = existing_code["status"]
                                t["color"] = existing_code["color"] or "green"
                                if not t.get("comment"):
                                    t["comment"] = existing_code["comment"] or ""
                                if not t.get("action_plan"):
                                    t["action_plan"] = existing_code["action_plan"] or ""
                                if not t.get("real_packages") or t.get("real_packages") == "--":
                                    t["real_packages"] = existing_code["real_packages"] or "--"
                                if not t.get("rat_types") or t.get("rat_types") == "--":
                                    t["rat_types"] = existing_code["rat_types"] or "--"
                                if not t.get("cem_data") or t.get("cem_data") == "--":
                                    t["cem_data"] = existing_code["cem_data"] or "--"
                                if not t.get("app_usage") or t.get("app_usage") == "--":
                                    t["app_usage"] = existing_code["app_usage"] or "--"
                        conn.execute(
                            "DELETE FROM tickets WHERE ticket_code = ?",
                            (ticket_code,)
                        )
        
                # 2. Chống trùng lặp theo số thuê bao đang ở trạng thái 'Chưa đóng' cùng nguồn
                # Nếu đã có bản ghi chưa đóng nhưng lệch định dạng incident_time -> kế thừa toàn bộ kết quả tiền kiểm rồi xóa bản ghi cũ
                existing_active = conn.execute(
                    """SELECT * FROM tickets 
                       WHERE phone = ? AND (source = ? OR (source IS NULL AND ? = 'tts_old')) 
                         AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')""",
                    (phone, source, source)
                ).fetchone()
        
                if existing_active and existing_active["incident_time"] != incident_time:
                    has_old_eval = existing_active["status"] and existing_active["status"] not in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", None, "")
                    if has_old_eval:
                        if not t.get("status") or t.get("status") in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", ""):
                            t["status"] = existing_active["status"]
                            t["color"] = existing_active["color"] or "green"
                            if not t.get("comment"):
                                t["comment"] = existing_active["comment"] or ""
                            if not t.get("action_plan"):
                                t["action_plan"] = existing_active["action_plan"] or ""
                            if not t.get("real_packages") or t.get("real_packages") == "--":
                                t["real_packages"] = existing_active["real_packages"] or "--"
                            if not t.get("rat_types") or t.get("rat_types") == "--":
                                t["rat_types"] = existing_active["rat_types"] or "--"
                            if not t.get("cem_data") or t.get("cem_data") == "--":
                                t["cem_data"] = existing_active["cem_data"] or "--"
                            if not t.get("app_usage") or t.get("app_usage") == "--":
                                t["app_usage"] = existing_active["app_usage"] or "--"
                    if not t.get("ai_summary") and existing_active["ai_summary"]:
                        t["ai_summary"] = existing_active["ai_summary"]

                    conn.execute(
                        "DELETE FROM tickets WHERE phone = ? AND incident_time = ?",
                        (phone, existing_active["incident_time"])
                    )
        
                existing = conn.execute(
                    "SELECT * FROM tickets WHERE phone = ? AND incident_time = ?", 
                    (phone, incident_time)
                ).fetchone()
                
                comment = t.get("comment", "")
                action_plan = t.get("action_plan", "")
                ticket_status = t.get("ticket_status", "Chưa đóng")
                ai_summary = t.get("ai_summary", "")
        
                if existing:
                    # Đối với tts_new (quét trực tiếp từ live API), nếu phiếu đang xuất hiện thì luôn khôi phục 'Chưa đóng'
                    # Chỉ giữ 'Đã đóng' khi là nguồn tts_old và không có force_update_status
                    if source != "tts_new" and not t.get("force_update_status") and existing["ticket_status"] in ("Đã đóng", "Da dong") and ticket_status == "Chưa đóng":
                        ticket_status = "Đã đóng"
                    if not ai_summary and "ai_summary" in existing.keys():
                        ai_summary = existing["ai_summary"] or ""

                    # BẢO VỆ DỮ LIỆU TIỀN KIỂM ĐÃ CÓ TRONG DATABASE:
                    # Nếu bản ghi cũ đã có kết quả phân tích kỹ thuật hợp lệ, và bản ghi mới là dữ liệu thô / CHỜ TIỀN KIỂM
                    # thì kế thừa và hiển thị theo kết quả Database cũ, không bị ghi đè thành rỗng.
                    has_valid_old = (
                        existing["status"] 
                        and existing["status"] not in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", None, "")
                    )
                    is_incoming_unprocessed = (
                        not comment 
                        or t.get("status") in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", None, "")
                    )
                    if has_valid_old and is_incoming_unprocessed:
                        t["status"] = existing["status"]
                        t["color"] = existing["color"] or "green"
                        comment = existing["comment"]
                        action_plan = existing["action_plan"] or action_plan
                        if existing["real_packages"] and existing["real_packages"] != "--":
                            t["real_packages"] = existing["real_packages"]
                        if existing["rat_types"] and existing["rat_types"] != "--":
                            t["rat_types"] = existing["rat_types"]
                        if existing["cem_data"] and existing["cem_data"] != "--":
                            t["cem_data"] = existing["cem_data"]
                        if existing["app_usage"] and existing["app_usage"] != "--":
                            t["app_usage"] = existing["app_usage"]
        
                reopen_count = int(t.get("reopen_count") or 0)
                last_reopened_date = str(t.get("last_reopened_date") or "").strip()
                if existing and reopen_count == 0 and "reopen_count" in existing.keys():
                    existing_rc = int(existing["reopen_count"] or 0)
                    if existing_rc > 0:
                        reopen_count = existing_rc
                        last_reopened_date = str(existing["last_reopened_date"] or "")
        
                conn.execute("""
                    INSERT INTO tickets (
                        phone, incident_time, package_title, real_packages, rat_types,
                        cem_data, app_usage, ticket_content, status, comment,
                        action_plan, color, ticket_status, created_time, ai_summary,
                        source, ticket_code, ticket_id, flow_id, reopen_count, last_reopened_date,
                        phan_hoi_he_thong, id_he_thong, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(phone, incident_time) DO UPDATE SET
                        package_title = excluded.package_title,
                        real_packages = excluded.real_packages,
                        rat_types = excluded.rat_types,
                        cem_data = excluded.cem_data,
                        app_usage = excluded.app_usage,
                        ticket_content = excluded.ticket_content,
                        status = excluded.status,
                        comment = excluded.comment,
                        action_plan = excluded.action_plan,
                        color = excluded.color,
                        ticket_status = excluded.ticket_status,
                        created_time = excluded.created_time,
                        ai_summary = excluded.ai_summary,
                        source = excluded.source,
                        ticket_code = excluded.ticket_code,
                        ticket_id = COALESCE(excluded.ticket_id, tickets.ticket_id),
                        flow_id = COALESCE(excluded.flow_id, tickets.flow_id),
                        reopen_count = excluded.reopen_count,
                        last_reopened_date = excluded.last_reopened_date,
                        phan_hoi_he_thong = COALESCE(excluded.phan_hoi_he_thong, tickets.phan_hoi_he_thong),
                        id_he_thong = COALESCE(excluded.id_he_thong, tickets.id_he_thong),
                        updated_at = CURRENT_TIMESTAMP;
                """, (
                    phone,
                    incident_time,
                    t.get("package_title", ""),
                    t.get("real_packages", ""),
                    t.get("rat_types", ""),
                    t.get("cem_data", ""),
                    t.get("app_usage", ""),
                    t.get("ticket_content", ""),
                    t.get("status", "CHƯA PHÂN LOẠI"),
                    comment,
                    action_plan,
                    t.get("color", "FFFFFF"),
                    ticket_status,
                    t.get("created_time", ""),
                    ai_summary,
                    source,
                    ticket_code,
                    t.get("ticket_id") or None,
                    t.get("flow_id") or None,
                    reopen_count,
                    last_reopened_date,
                    t.get("phan_hoi_he_thong", 1),
                    t.get("id_he_thong", 0),
                ))
            conn.close()
            conn = None
            break
        except sqlite3.OperationalError as e:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            if "locked" in str(e).lower() and attempt < 4:
                time.sleep(0.2 * (attempt + 1))
                continue
            raise
        except Exception:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            raise

def save_tickets_bulk(ticket_list):
    for t in ticket_list:
        save_or_update_ticket(t)

DATA_PKG_SQL = "(package_title LIKE '%Mobile Internet%' AND package_title NOT LIKE '%Gói cước Mobile Internet%' AND package_title NOT LIKE '%Mobile Internet (M0/Gói Data)%' AND package_title NOT LIKE '%CVQT - DV Mobile Internet (Data)%')"

CALL_PKG_SQL = """(
    package_title LIKE '%Gọi đi trong nước%' 
    OR package_title LIKE '%Nhận cuộc gọi đến trong nước%' 
    OR package_title LIKE '%Nhận cuộc gọi dến trong nước%'
    OR package_title LIKE '%Cuộc gọi đi và đến%'
    OR package_title LIKE '%Bị khóa Spam cuộc gọi%'
    OR package_title LIKE '%Giữ cuộc gọi%'
    OR package_title LIKE '%Gọi Quốc tế%'
    OR package_title LIKE '%VoWifi%'
)"""

SMS_PKG_SQL = """(
    package_title LIKE '%nhận tin nhắn%' 
    OR package_title LIKE '%khóa spam tin nhắn%' 
    OR package_title LIKE '%Tin nhắn (SMS)%' 
    OR package_title LIKE '%Tin nhắn (sms)%' 
    OR package_title LIKE '%gửi tin nhắn đi và đến%' 
    OR package_title LIKE '%gửi tin nhắn đi%' 
    OR package_title LIKE '%Tin nhắn rác%'
    OR (package_title LIKE '%Tin nhắn%' AND package_title NOT LIKE '%CVQT%')
)"""

OTHER_PKG_SQL = f"(NOT {DATA_PKG_SQL} AND NOT {CALL_PKG_SQL} AND NOT {SMS_PKG_SQL})"
VOICE_PKG_SQL = f"(package_title IS NULL OR NOT {DATA_PKG_SQL})"

def is_mobile_internet_ticket(package_title: str) -> bool:
    pkg = (package_title or "").strip().lower()
    if not pkg:
        return False
    if "mobile internet" in pkg or "data" in pkg:
        if "(m0/gói data)" in pkg or "gói cước mobile internet" in pkg or "cvqt" in pkg:
            return False
        return True
    return False

def is_call_ticket(package_title: str) -> bool:
    pkg = (package_title or "").strip().lower()
    return any(k in pkg for k in [
        "gọi đi trong nước", "nhận cuộc gọi đến trong nước", "nhận cuộc gọi dến trong nước",
        "cuộc gọi đi và đến", "bị khóa spam cuộc gọi", "giữ cuộc gọi", "gọi quốc tế", "vowifi"
    ])

def is_sms_ticket(package_title: str) -> bool:
    pkg = (package_title or "").strip().lower()
    return any(k in pkg for k in [
        "nhận tin nhắn", "khóa spam tin nhắn", "tin nhắn (sms)", "gửi tin nhắn", "tin nhắn rác"
    ]) or ("tin nhắn" in pkg and "cvqt" not in pkg)

def sync_active_tickets_state(active_keys, source="tts_old", key_type="phone", service_type=None):
    """
    Đồng bộ trạng thái danh sách phiếu hiện hữu với danh sách cào/quét thực tế trên TTS.
    Bất kỳ phiếu nào trong DB đang ở trạng thái 'Chưa đóng' của nguồn/nghiệp vụ này
    nhưng KHÔNG còn xuất hiện trên web TTS nữa -> Tự động chuyển thành 'Đã đóng'.
    """
    init_db()
    conn = get_db_connection()
    with conn:
        service_sql = ""
        if service_type == "data":
            service_sql = f" AND {DATA_PKG_SQL}"
        elif service_type in ("call", "voice", "cuoc_goi"):
            service_sql = f" AND {CALL_PKG_SQL}"
        elif service_type in ("sms", "tin_nhan"):
            service_sql = f" AND {SMS_PKG_SQL}"
        elif service_type in ("other", "khac"):
            service_sql = f" AND {OTHER_PKG_SQL}"
        elif service_type == "voice_sms":
            service_sql = f" AND {VOICE_PKG_SQL}"

        if source in ("tts_old", "tts_old_api"):
            source_condition = "(source IN ('tts_old', 'tts_old_api') OR source IS NULL)"
            source_params = []
        else:
            source_condition = "source = ?"
            source_params = [source]

        if not active_keys:
            # Nếu trên TTS đã hết sạch phiếu chờ xử lý -> toàn bộ phiếu chưa đóng trong DB thuộc nguồn này đã đóng!
            conn.execute(f"""
                UPDATE tickets 
                SET ticket_status = 'Đã đóng', updated_at = CURRENT_TIMESTAMP 
                WHERE {source_condition}
                  AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
                  {service_sql}
            """, source_params)
            return

        if key_type == "ticket_code":
            raw_active_keys = [k.split('\n')[0].strip() for k in active_keys if k]
            if not raw_active_keys:
                conn.execute(f"""
                    UPDATE tickets 
                    SET ticket_status = 'Đã đóng', updated_at = CURRENT_TIMESTAMP 
                    WHERE {source_condition}
                      AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
                      {service_sql}
                """, source_params)
            else:
                placeholders = ",".join(["?"] * len(raw_active_keys))
                conn.execute(f"""
                    UPDATE tickets 
                    SET ticket_status = 'Đã đóng', updated_at = CURRENT_TIMESTAMP 
                    WHERE {source_condition}
                      AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
                      {service_sql}
                      AND substr(ticket_code, 1, case when instr(ticket_code, char(10)) > 0 then instr(ticket_code, char(10)) - 1 else length(ticket_code) end) NOT IN ({placeholders})
                """, source_params + list(raw_active_keys))
        else:
            placeholders = ",".join(["?"] * len(active_keys))
            conn.execute(f"""
                UPDATE tickets 
                SET ticket_status = 'Đã đóng', updated_at = CURRENT_TIMESTAMP 
                WHERE {source_condition}
                  AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
                  {service_sql}
                  AND phone NOT IN ({placeholders})
            """, source_params + list(active_keys))
    conn.close()

def get_system_counts():
    """Lấy số lượng phiếu phân chia theo từng nghiệp vụ cho Menu Sidebar."""
    init_db()
    conn = get_db_connection()
    counts = {
        "tts_old_data": 0,
        "tts_old_voice": 0,
        "tts_new_data": 0,
        "tts_new_voice": 0,
        "tts_old_api_data": 0,
        "tts_old_api_voice": 0,
        "total_active": 0,
        "total_closed": 0,
        "total_all": 0
    }
    try:
        c1 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (source = 'tts_old' OR source IS NULL) 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {DATA_PKG_SQL}
        """).fetchone()
        counts["tts_old_data"] = c1[0] if c1 else 0

        c2 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (source = 'tts_old' OR source IS NULL) 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {VOICE_PKG_SQL}
        """).fetchone()
        counts["tts_old_voice"] = c2[0] if c2 else 0

        c3 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {DATA_PKG_SQL}
        """).fetchone()
        counts["tts_new_data"] = c3[0] if c3 else 0

        c_call = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {CALL_PKG_SQL}
        """).fetchone()
        counts["tts_new_call"] = c_call[0] if c_call else 0

        c_sms = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {SMS_PKG_SQL}
        """).fetchone()
        counts["tts_new_sms"] = c_sms[0] if c_sms else 0

        c_other = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {OTHER_PKG_SQL}
        """).fetchone()
        counts["tts_new_other"] = c_other[0] if c_other else 0

        c4 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {VOICE_PKG_SQL}
        """).fetchone()
        counts["tts_new_voice"] = c4[0] if c4 else 0

        c5 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (source = 'tts_old_api' OR source = 'tts_old' OR source IS NULL) 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {DATA_PKG_SQL}
        """).fetchone()
        counts["tts_old_api_data"] = c5[0] if c5 else 0

        c6 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (source = 'tts_old_api' OR source = 'tts_old' OR source IS NULL) 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {VOICE_PKG_SQL}
        """).fetchone()
        counts["tts_old_api_voice"] = c6[0] if c6 else 0

        ca = conn.execute("SELECT count(*) FROM tickets WHERE ticket_status != 'Đã đóng' AND ticket_status != 'Da dong'").fetchone()
        counts["total_active"] = ca[0] if ca else 0

        cc = conn.execute("SELECT count(*) FROM tickets WHERE ticket_status = 'Đã đóng' OR ticket_status = 'Da dong'").fetchone()
        counts["total_closed"] = cc[0] if cc else 0

        ct = conn.execute("SELECT count(*) FROM tickets").fetchone()
        counts["total_all"] = ct[0] if ct else 0

        # Thống kê ngày hiện tại (Hôm nay)
        today_iso = datetime.now().strftime("%Y-%m-%d")
        today_dmy = datetime.now().strftime("%d/%m/%Y")

        ctoday = conn.execute("""
            SELECT count(*) FROM tickets 
            WHERE SUBSTR(updated_at, 1, 10) = ? 
               OR updated_at LIKE ? 
               OR incident_time LIKE ?
        """, [today_iso, f"{today_iso}%", f"{today_dmy}%"]).fetchone()
        counts["today_total"] = ctoday[0] if ctoday else 0

        c_closed_today = conn.execute("""
            SELECT count(*) FROM tickets 
            WHERE (ticket_status = 'Đã đóng' OR ticket_status = 'Da dong') 
              AND (SUBSTR(updated_at, 1, 10) = ? OR updated_at LIKE ?)
        """, [today_iso, f"{today_iso}%"]).fetchone()
        counts["today_closed"] = c_closed_today[0] if c_closed_today else 0

        c_active_today = conn.execute("""
            SELECT count(*) FROM tickets 
            WHERE (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong') 
              AND (SUBSTR(updated_at, 1, 10) = ? OR updated_at LIKE ? OR incident_time LIKE ?)
        """, [today_iso, f"{today_iso}%", f"{today_dmy}%"]).fetchone()
        counts["today_active"] = c_active_today[0] if c_active_today else 0
    except Exception as e:
        print("Lỗi get_system_counts:", e)
    finally:
        conn.close()
    return counts

def get_all_tickets(search=None, status_filter=None, tab_filter=None, source=None, service_type=None):
    init_db()
    conn = get_db_connection()
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []

    # Lọc theo nguồn hệ thống (tts_old_api / tts_new)
    if source:
        if source in ("tts_old", "tts_old_api"):
            query += " AND (source = 'tts_old_api' OR source = 'tts_old' OR source IS NULL OR source = '')"
        else:
            query += " AND source = ?"
            params.append(source)

    # Lọc theo loại nghiệp vụ (data / call / sms / other / voice_sms)
    if service_type == "data":
        query += f" AND {DATA_PKG_SQL}"
    elif service_type in ("call", "voice", "cuoc_goi"):
        query += f" AND {CALL_PKG_SQL}"
    elif service_type in ("sms", "tin_nhan"):
        query += f" AND {SMS_PKG_SQL}"
    elif service_type in ("other", "khac"):
        query += f" AND {OTHER_PKG_SQL}"
    elif service_type == "voice_sms":
        query += f" AND {VOICE_PKG_SQL}"

    if search:
        query += " AND (phone LIKE ? OR ticket_content LIKE ? OR package_title LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])

    # 1. Lọc theo Tab trạng thái xử lý phiếu (Hiện hữu / Đã đóng / Tất cả)
    if tab_filter == "da_dong":
        query += " AND (ticket_status LIKE '%Đã đóng%' OR ticket_status LIKE '%Da dong%')"
    elif tab_filter == "chua_dong":
        query += " AND (ticket_status NOT LIKE '%Đã đóng%' AND ticket_status NOT LIKE '%Da dong%' OR ticket_status IS NULL OR ticket_status = '')"

    # 2. Lọc theo Nhận định kỹ thuật
    if status_filter and status_filter != "all":
        if status_filter == "da_dong":
            query += " AND (ticket_status LIKE '%Đã đóng%' OR ticket_status LIKE '%Da dong%')"
        elif status_filter == "chua_dong":
            query += " AND (ticket_status NOT LIKE '%Đã đóng%' AND ticket_status NOT LIKE '%Da dong%' OR ticket_status IS NULL OR ticket_status = '')"
        elif status_filter in ("HOẠT ĐỘNG BÌNH THƯỜNG", "BINH_THUONG"):
            query += " AND (status LIKE '%BÌNH THƯỜNG%' OR status LIKE '%BINH THUONG%')"
        elif status_filter == "SONG_4G":
            query += " AND (status LIKE '%4G%' OR status LIKE '%SÓNG%' OR status LIKE '%SONG%' OR status LIKE '%PROFILE%')"
        elif status_filter in ("LƯU LƯỢNG YẾU", "LUU_LUONG"):
            query += " AND (status LIKE '%LƯU LƯỢNG%' OR status LIKE '%LUU LUONG%')"
        elif status_filter == "GOI_CUOC":
            query += " AND (status LIKE '%GÓI%' OR status LIKE '%GOI%' OR status LIKE '%PAYGO%')"
        elif status_filter == "BOP_BANG_THONG":
            query += " AND (status LIKE '%BĂNG THÔNG%' OR status LIKE '%BANG THONG%' OR status LIKE '%BÓP%' OR status LIKE '%BOP%')"
        elif status_filter == "THIET_BI":
            query += " AND (status LIKE '%THIẾT BỊ%' OR status LIKE '%THIET BI%' OR status LIKE '%VPN%')"
        elif status_filter == "THEO_DOI":
            query += " AND (status LIKE '%THEO DÕI%' OR status LIKE '%THEO DOI%')"
        else:
            query += " AND (status = ? OR status LIKE ?)"
            params.extend([status_filter, f"%{status_filter}%"])

    if tab_filter == "all":
        # Ưu tiên các phiếu Chưa đóng lên đầu trang để người dùng thấy rõ sự khác biệt giữa Toàn bộ DB và Lịch sử đã đóng
        query += " ORDER BY (CASE WHEN ticket_status LIKE '%Đã đóng%' OR ticket_status LIKE '%Da dong%' THEN 1 ELSE 0 END) ASC, updated_at DESC"
    else:
        query += " ORDER BY updated_at DESC"
    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        item = dict(r)
        can_close, reason = check_ticket_can_close(item)
        item["can_close"] = can_close
        item["cannot_close_reason"] = reason
        results.append(item)
    conn.close()
    return results

def update_ticket_field(phone, field, value, incident_time=None):
    valid_fields = ["comment", "action_plan", "ticket_status", "status", "ai_summary", "closed_by", "reopen_count", "last_reopened_date"]
    if field not in valid_fields:
        return False

    init_db()
    conn = get_db_connection()
    clean_p = "".join(filter(str.isdigit, str(phone or "")))
    p_suffix = f"%{clean_p[-9:]}" if len(clean_p) >= 9 else str(phone)

    with conn:
        if incident_time and str(incident_time).strip() not in ["", "--", "None"]:
            cur = conn.execute(
                f"UPDATE tickets SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE (phone = ? OR phone LIKE ?) AND incident_time = ?", 
                (value, str(phone).strip(), p_suffix, str(incident_time).strip())
            )
            if cur.rowcount == 0:
                conn.execute(
                    f"UPDATE tickets SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE phone = ? OR phone LIKE ?", 
                    (value, str(phone).strip(), p_suffix)
                )
        else:
            conn.execute(
                f"UPDATE tickets SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE phone = ? OR phone LIKE ?", 
                (value, str(phone).strip(), p_suffix)
            )
    conn.close()
    return True

def delete_all_tickets(source=None):
    init_db()
    conn = get_db_connection()
    with conn:
        if source == "tts_old":
            conn.execute("DELETE FROM tickets WHERE source = 'tts_old' OR source IS NULL OR source = ''")
        elif source:
            conn.execute("DELETE FROM tickets WHERE source = ?", (source,))
        else:
            conn.execute("DELETE FROM tickets")
    conn.commit()
    conn.close()

def get_closed_tickets_analytics(time_filter="all", source_filter=None, service_filter=None):
    """
    Thống kê tổng hợp số liệu phân tích chuyên sâu cho các phiếu đã đóng:
    - time_filter: 'all', 'today', '7days', '30days'
    - source_filter: 'all', 'tts_old', 'tts_new'
    - service_filter: 'all', 'data' (Mobile Internet), 'voice_sms' (Thoại/SMS/Gói/PA Khác)
    """
    init_db()
    conn = get_db_connection()
    try:
        where = ["(ticket_status = 'Đã đóng' OR ticket_status = 'Da dong')"]
        params = []
        today_str = datetime.now().strftime("%Y-%m-%d")

        if time_filter == "today":
            where.append("(SUBSTR(updated_at, 1, 10) = ? OR updated_at LIKE ?)")
            params.extend([today_str, f"{today_str}%"])
        elif time_filter == "7days":
            where.append("DATE(SUBSTR(updated_at, 1, 10)) >= DATE(?, '-7 days')")
            params.append(today_str)
        elif time_filter == "30days":
            where.append("DATE(SUBSTR(updated_at, 1, 10)) >= DATE(?, '-30 days')")
            params.append(today_str)

        if source_filter and source_filter != 'all':
            if source_filter in ('tts_old', 'tts_old_api'):
                where.append("(source IN ('tts_old', 'tts_old_api') OR source IS NULL)")
            else:
                where.append("source = ?")
                params.append(source_filter)

        if service_filter and service_filter != 'all':
            if service_filter == 'data':
                where.append(DATA_PKG_SQL)
            elif service_filter == 'voice_sms':
                where.append(VOICE_PKG_SQL)
            elif service_filter == 'thoai':
                where.append("(package_title LIKE '%Gọi%' OR package_title LIKE '%Cuộc gọi%')")
            elif service_filter == 'sms':
                where.append("(package_title LIKE '%Tin nhắn%' OR package_title LIKE '%SMS%')")
            elif service_filter == 'goi_cuoc':
                where.append("package_title LIKE '%Gói cước%'")

        where_sql = " AND ".join(where)

        # 1. Tổng quan số lượng
        q_totals = f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN closed_by IS NOT NULL AND closed_by != '' AND closed_by NOT LIKE '%Tự động%' THEN 1 ELSE 0 END) as manual_cnt,
                SUM(CASE WHEN closed_by IS NULL OR closed_by = '' OR closed_by LIKE '%Tự động%' THEN 1 ELSE 0 END) as auto_cnt,
                SUM(CASE WHEN source = 'tts_new' THEN 1 ELSE 0 END) as tts_new_cnt,
                SUM(CASE WHEN source IN ('tts_old', 'tts_old_api') OR source IS NULL THEN 1 ELSE 0 END) as tts_old_cnt,
                SUM(CASE WHEN {DATA_PKG_SQL} THEN 1 ELSE 0 END) as data_cnt,
                SUM(CASE WHEN {VOICE_PKG_SQL} THEN 1 ELSE 0 END) as voice_cnt
            FROM tickets WHERE {where_sql}
        """
        row = conn.execute(q_totals, params).fetchone()
        total = row["total"] or 0
        manual_cnt = row["manual_cnt"] or 0
        auto_cnt = row["auto_cnt"] or 0
        tts_new_cnt = row["tts_new_cnt"] or 0
        tts_old_cnt = row["tts_old_cnt"] or 0
        data_cnt = row["data_cnt"] or 0
        voice_cnt = row["voice_cnt"] or 0

        # Hôm nay đóng bao nhiêu
        today_q = "SELECT COUNT(*) FROM tickets WHERE (ticket_status = 'Đã đóng' OR ticket_status = 'Da dong') AND SUBSTR(updated_at, 1, 10) = ?"
        today_row = conn.execute(today_q, [today_str]).fetchone()
        today_cnt = today_row[0] if today_row else 0

        # 2. Phân bổ theo nhận định
        q_diag = f"""
            SELECT 
                CASE 
                    WHEN status IS NULL OR TRIM(status) = '' THEN 'Khác / Chưa ghi nhận'
                    ELSE status 
                END as diag,
                COUNT(*) as cnt
            FROM tickets WHERE {where_sql}
            GROUP BY diag ORDER BY cnt DESC LIMIT 8
        """
        by_diagnosis = [
            {
                "label": r["diag"], 
                "count": r["cnt"], 
                "percentage": round(r["cnt"] * 100.0 / total, 1) if total else 0
            } 
            for r in conn.execute(q_diag, params).fetchall()
        ]

        # 3. Xu hướng đóng theo ngày (10 ngày gần nhất)
        q_trend = f"""
            SELECT SUBSTR(updated_at, 1, 10) as dt, COUNT(*) as cnt
            FROM tickets WHERE {where_sql} AND updated_at IS NOT NULL AND updated_at != ''
            GROUP BY dt ORDER BY dt ASC
        """
        daily_rows = conn.execute(q_trend, params).fetchall()
        daily_trend = []
        for r in daily_rows[-10:]:
            dt_raw = r["dt"]
            try:
                parts = dt_raw.split("-")
                label = f"{parts[2]}/{parts[1]}"
            except Exception:
                label = dt_raw
            daily_trend.append({"date": dt_raw, "label": label, "count": r["cnt"]})

        # 4. Top gói cước / phân loại
        q_pkg = f"""
            SELECT package_title, COUNT(*) as cnt
            FROM tickets WHERE {where_sql} AND package_title IS NOT NULL AND TRIM(package_title) != ''
            GROUP BY package_title ORDER BY cnt DESC LIMIT 5
        """
        top_packages = [{"name": r["package_title"], "count": r["cnt"]} for r in conn.execute(q_pkg, params).fetchall()]

        # 5. Danh sách KTV đóng thủ công
        q_staff = f"""
            SELECT closed_by, COUNT(*) as cnt
            FROM tickets 
            WHERE {where_sql} AND closed_by IS NOT NULL AND closed_by != '' AND closed_by NOT LIKE '%Tự động%'
            GROUP BY closed_by ORDER BY cnt DESC
        """
        staff_list = [{"name": r["closed_by"], "count": r["cnt"]} for r in conn.execute(q_staff, params).fetchall()]

        return {
            "total": total,
            "auto_cnt": auto_cnt,
            "auto_percent": round(auto_cnt * 100.0 / total, 1) if total else 0,
            "manual_cnt": manual_cnt,
            "manual_percent": round(manual_cnt * 100.0 / total, 1) if total else 0,
            "today_cnt": today_cnt,
            "tts_new_cnt": tts_new_cnt,
            "tts_old_cnt": tts_old_cnt,
            "data_cnt": data_cnt,
            "voice_cnt": voice_cnt,
            "by_diagnosis": by_diagnosis,
            "daily_trend": daily_trend,
            "top_packages": top_packages,
            "staff_list": staff_list
        }
    except Exception as ex:
        print("Lỗi get_closed_tickets_analytics:", ex)
        return {
            "total": 0, "auto_cnt": 0, "auto_percent": 0, "manual_cnt": 0, "manual_percent": 0,
            "today_cnt": 0, "tts_new_cnt": 0, "tts_old_cnt": 0, "data_cnt": 0, "voice_cnt": 0,
            "by_diagnosis": [], "daily_trend": [], "top_packages": [], "staff_list": []
        }
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("✅ Database initialized successfully at:", DB_PATH)

