# db_manager.py
import sqlite3
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tickets.db"

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  # Tăng tốc độ và chống khóa file
    return conn

def init_db():
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
    conn.close()

def check_ticket_can_close(t):
    """
    Kiểm tra xem 1 phiếu có đủ điều kiện để đóng tự động / thủ công hay không.
    Trả về tuple: (can_close: bool, reason: str)
    """
    if t.get("ticket_status") == "Đã đóng":
        return True, "Đã đóng"

    try:
        from update_tts import config as tts_config
        from update_tts import excel_reader

        status = str(t.get("status", "")).strip()
        norm_status = excel_reader.normalize_text(status)

        # 1. Kiểm tra mapping trạng thái sang nguyên nhân sự cố TTS
        matched_nguyen_nhan = None
        for k, v in tts_config.STATUS_TO_NGUYEN_NHAN.items():
            if excel_reader.normalize_text(k) == norm_status:
                matched_nguyen_nhan = v
                break
        
        if not matched_nguyen_nhan:
            return False, f"Chưa có mapping nguyên nhân đóng trên TTS cho [{status}]"

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

        can_close = excel_reader.is_level_1_auto_close_candidate(rec)
        can_close = excel_reader.is_level_1_auto_close_candidate(rec)
        if can_close:
            return True, "Đủ điều kiện tự động đóng"
        else:
            if norm_status == excel_reader.LEVEL_1_STATUS:
                return False, "Hoạt động bình thường nhưng khách báo không dùng được / cần đối chiếu"
            elif norm_status == excel_reader.LEVEL_LUU_LUONG_YEU_STATUS:
                return False, "Lưu lượng yếu nhưng chưa xác định khu vực cụ thể"
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
                conn.execute(
                    "DELETE FROM tickets WHERE ticket_code = ?",
                    (ticket_code,)
                )

        # 2. Chống trùng lặp theo số thuê bao đang ở trạng thái 'Chưa đóng' cùng nguồn
        # Nếu đã có bản ghi chưa đóng nhưng lệch định dạng incident_time -> xóa bản ghi cũ, thay thế bằng bản ghi mới
        existing_active = conn.execute(
            """SELECT * FROM tickets 
               WHERE phone = ? AND (source = ? OR (source IS NULL AND ? = 'tts_old')) 
                 AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')""",
            (phone, source, source)
        ).fetchone()

        if existing_active and existing_active["incident_time"] != incident_time:
            conn.execute(
                "DELETE FROM tickets WHERE phone = ? AND incident_time = ?",
                (phone, existing_active["incident_time"])
            )
            # Kế thừa dữ liệu đã nhập / phân tích nếu bản ghi mới chưa có
            if not t.get("comment") and existing_active["comment"]:
                t["comment"] = existing_active["comment"]
            if not t.get("action_plan") and existing_active["action_plan"]:
                t["action_plan"] = existing_active["action_plan"]
            if not t.get("ai_summary") and existing_active["ai_summary"]:
                t["ai_summary"] = existing_active["ai_summary"]

        existing = conn.execute(
            "SELECT * FROM tickets WHERE phone = ? AND incident_time = ?", 
            (phone, incident_time)
        ).fetchone()
        
        comment = t.get("comment", "")
        action_plan = t.get("action_plan", "")
        ticket_status = t.get("ticket_status", "Chưa đóng")
        ai_summary = t.get("ai_summary", "")

        if existing:
            if existing["ticket_status"] == "Đã đóng" and ticket_status == "Chưa đóng":
                ticket_status = "Đã đóng"
            if not ai_summary and "ai_summary" in existing.keys():
                ai_summary = existing["ai_summary"] or ""

        conn.execute("""
            INSERT INTO tickets (
                phone, incident_time, package_title, real_packages, rat_types,
                cem_data, app_usage, ticket_content, status, comment,
                action_plan, color, ticket_status, created_time, ai_summary,
                source, ticket_code, ticket_id, flow_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
            t.get("flow_id") or None
        ))
    conn.close()

def save_tickets_bulk(ticket_list):
    for t in ticket_list:
        save_or_update_ticket(t)

DATA_PKG_SQL = "(package_title LIKE '%Mobile Internet%' AND package_title NOT LIKE '%Gói cước%')"
VOICE_PKG_SQL = f"NOT {DATA_PKG_SQL}"

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

        placeholders = ",".join(["?"] * len(active_keys))
        if key_type == "ticket_code":
            conn.execute(f"""
                UPDATE tickets 
                SET ticket_status = 'Đã đóng', updated_at = CURRENT_TIMESTAMP 
                WHERE {source_condition}
                  AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
                  {service_sql}
                  AND ticket_code NOT IN ({placeholders})
            """, source_params + list(active_keys))
        else:
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

    # Lọc theo loại nghiệp vụ (data / voice_sms)
    if service_type == "data":
        query += f" AND {DATA_PKG_SQL}"
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
        query += " AND (ticket_status LIKE '%Chưa đóng%' OR ticket_status LIKE '%Chua dong%' OR ticket_status IS NULL OR ticket_status = '')"

    # 2. Lọc theo Nhận định kỹ thuật
    if status_filter and status_filter != "all":
        if status_filter == "da_dong":
            query += " AND (ticket_status LIKE '%Đã đóng%' OR ticket_status LIKE '%Da dong%')"
        elif status_filter == "chua_dong":
            query += " AND (ticket_status LIKE '%Chưa đóng%' OR ticket_status LIKE '%Chua dong%' OR ticket_status IS NULL OR ticket_status = '')"
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
    valid_fields = ["comment", "action_plan", "ticket_status", "status", "ai_summary", "closed_by"]
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

if __name__ == "__main__":
    init_db()
    print("✅ Database initialized successfully at:", DB_PATH)

