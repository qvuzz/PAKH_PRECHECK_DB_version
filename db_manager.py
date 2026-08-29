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
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (phone, incident_time)
            );
        """)
    conn.close()

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
        existing = conn.execute(
            "SELECT * FROM tickets WHERE phone = ? AND incident_time = ?", 
            (phone, incident_time)
        ).fetchone()
        
        comment = t.get("comment", "")
        action_plan = t.get("action_plan", "")
        ticket_status = t.get("ticket_status", "Chưa đóng")

        if existing:
            if existing["ticket_status"] == "Đã đóng" and ticket_status == "Chưa đóng":
                ticket_status = "Đã đóng"

        conn.execute("""
            INSERT INTO tickets (
                phone, incident_time, package_title, real_packages, rat_types,
                cem_data, app_usage, ticket_content, status, comment,
                action_plan, color, ticket_status, created_time, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
            t.get("created_time", "")
        ))
    conn.close()

def save_tickets_bulk(ticket_list):
    for t in ticket_list:
        save_or_update_ticket(t)

def get_all_tickets(search=None, status_filter=None):
    init_db()
    conn = get_db_connection()
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []

    if search:
        query += " AND (phone LIKE ? OR ticket_content LIKE ? OR package_title LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])

    if status_filter:
        if status_filter == "da_dong":
            query += " AND ticket_status = 'Đã đóng'"
        elif status_filter == "chua_dong":
            query += " AND ticket_status = 'Chưa đóng'"
        elif status_filter != "all":
            query += " AND status = ?"
            params.append(status_filter)

    query += " ORDER BY updated_at DESC"
    rows = conn.execute(query, params).fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results

def update_ticket_field(phone, field, value, incident_time=None):
    valid_fields = ["comment", "action_plan", "ticket_status", "status"]
    if field not in valid_fields:
        return False

    init_db()
    conn = get_db_connection()
    with conn:
        if incident_time:
            conn.execute(
                f"UPDATE tickets SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE phone = ? AND incident_time = ?", 
                (value, phone, incident_time)
            )
        else:
            conn.execute(
                f"UPDATE tickets SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE phone = ?", 
                (value, phone)
            )
    conn.close()
    return True

def delete_all_tickets():
    init_db()
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM tickets")
    conn.close()

if __name__ == "__main__":
    init_db()
    print("✅ Database initialized successfully at:", DB_PATH)
