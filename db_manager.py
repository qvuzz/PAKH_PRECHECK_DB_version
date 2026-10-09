# db_manager.py
import sqlite3
import os
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tickets.db"

import threading
_DB_WRITE_LOCK = threading.RLock()

_db_initialized = False

def extract_ward_address(text: str) -> str:
    """
    Trích xuất địa bàn (Phường/Xã, Quận/Huyện, Tỉnh/TP) từ nội dung phản ánh khách hàng.
    """
    if not text:
        return ""
    
    # 1. ƯU TIÊN 1: Bắt theo từ khóa Địa chỉ rõ ràng (Địa chỉ mới, Địa chỉ sự cố, Địa chỉ, Đ/c, Nơi phản ánh)
    m = re.search(r'(?:địa chỉ(?: mới| sự cố)?|đ/c|nơi phản ánh)[:\s]+([^\n\r]+)', text, re.I)
    raw = m.group(1).strip() if m else ""
    
    # 2. ƯU TIÊN 2: Tìm cụm hành chính cấp xã/phường/ấp/thôn kèm quận/huyện/tỉnh/tp
    if not raw:
        m2 = re.search(r'((?:ấp|thôn|tổ|khóm|xã|phường|thị trấn|quận|huyện|thành phố|tp\.?|tỉnh)\s+[^,\n\r]+(?:,\s*[^,\n\r]+){1,3})', text, re.I)
        if m2:
            raw = m2.group(1).strip()

    # 3. ƯU TIÊN 3: Bắt theo từ khóa khu vực/tại nếu theo sau có thông tin địa danh hành chính
    if not raw:
        m3 = re.search(r'(?:khu vực|tại)[:\s]+((?:ấp|thôn|tổ|khóm|xã|phường|thị trấn|quận|huyện|thành phố|tp\.?|tỉnh)\s+[^\n\r]+)', text, re.I)
        if m3:
            raw = m3.group(1).strip()
            
    if not raw:
        return ""
        
    # Loại bỏ các từ rác hoặc câu nối sau địa chỉ
    stop_words = [
        'kh nhờ', 'kh yêu cầu', 'kh báo', 'kh phan anh', 'kh phản ánh', 'kính chuyển', 
        'kinh chuyen', 'chuyển tc', 'chuyen tc', 'các số vina', 'thuê bao khác', 
        'kh không đồng ý', 'ktv đã', 'kh đã', 'liên hệ', 'lh:', 'sđt:', 'sdt:', 
        'ẩn danh', 'gọi lại', 'thời điểm', 'khi dùng', 'không vào được', 'mạng chậm'
    ]
    cleaned = raw
    for sw in stop_words:
        idx = cleaned.lower().find(sw)
        if idx != -1:
            cleaned = cleaned[:idx]
            
    # Cắt dấu câu rác ở cuối
    cleaned = cleaned.strip(' .,;-\t\r\n"\'')
    if '.' in cleaned:
        cleaned = cleaned.split('.')[0].strip()
    return cleaned

def _recover_corrupted_db(reason: str = ""):
    """
    Tự động xử lý khi file SQLite bị malformed hoặc lỗi cấu trúc:
    - Backup file hỏng sang .bak để bảo toàn dữ liệu cho KTV
    - Xóa các file phụ wal / shm / journal xung đột
    - Khởi tạo lại database mới sạch sẽ
    """
    global _db_initialized
    _db_initialized = False
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[DB REPAIR] Phát hiện database bị lỗi hỏng ({reason}). Bắt đầu tự động khắc phục...")
    
    # 1. Nếu Docker volume mount nhầm file DB thành thư mục
    if DB_PATH.exists() and DB_PATH.is_dir():
        dir_bak = BASE_DIR / f"tickets_dir_corrupt_{timestamp}.bak"
        try:
            DB_PATH.rename(dir_bak)
            print(f"[DB REPAIR] Đã đổi tên thư mục xung đột tickets.db -> {dir_bak.name}")
        except Exception as e:
            print(f"[DB REPAIR ERROR] Không thể đổi tên thư mục tickets.db: {e}")

    # 2. Nếu file tickets.db tồn tại (Lưu ý: Không dùng rename/unlink vì Docker bind-mount sẽ báo Device or resource busy)
    if DB_PATH.exists() and DB_PATH.is_file():
        bak_file = BASE_DIR / f"tickets.db.malformed_{timestamp}.bak"
        try:
            import shutil
            shutil.copy2(DB_PATH, bak_file)
            print(f"[DB REPAIR] Đã sao lưu database lỗi sang: {bak_file.name}")
        except Exception as e:
            print(f"[DB REPAIR WARN] Sao lưu copy2 thất bại: {e}")

        try:
            # Ghi đè file rỗng (truncate 0) để giữ nguyên inode mountpoint của Docker container
            with open(DB_PATH, "wb") as f:
                f.truncate(0)
            print("[DB REPAIR] Đã làm sạch file tickets.db (truncate 0) thành công!")
        except Exception as e:
            print(f"[DB REPAIR ERROR] Truncate file thất bại: {e}")

    # 3. Dọn dẹp triệt để các file journal, wal, shm cũ
    for ext in ["-wal", "-shm", "-journal"]:
        side_file = BASE_DIR / f"tickets.db{ext}"
        try:
            if side_file.exists():
                side_file.unlink(missing_ok=True)
        except Exception:
            pass


def get_db_connection(retry_count: int = 1):
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")  # Tăng tốc độ và chống khóa file
        conn.execute("PRAGMA busy_timeout=60000;")
        return conn
    except sqlite3.DatabaseError as e:
        err_msg = str(e).lower()
        if "malformed" in err_msg or "file is not a database" in err_msg or "corrupt" in err_msg:
            print(f"[DB ERROR] SQLite database bị lỗi ({e}). Đang tự động khôi phục...")
            if retry_count > 0:
                with _DB_WRITE_LOCK:
                    _recover_corrupted_db(reason=str(e))
                return get_db_connection(retry_count=retry_count - 1)
        raise


def _run_init_schema(conn):
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
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN incident_cause TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN ccos_attachments TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN processing_content TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN closed_at TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN prechecked_at TEXT;")
        except Exception:
            pass
        try:
            # Đồng bộ prechecked_at sang UTC+7 cho các phiếu đã có kết quả tiền kiểm
            conn.execute("UPDATE tickets SET prechecked_at = datetime(updated_at, '+7 hours') WHERE prechecked_at IS NULL AND status IS NOT NULL AND status != '' AND status != 'CHƯA PHÂN LOẠI';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE tickets ADD COLUMN region TEXT DEFAULT 'MN';")
        except Exception:
            pass
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_region ON tickets(region);")
        except Exception:
            pass
        try:
            from region_detector import detect_ticket_region
            # Cập nhật miền cho các phiếu chưa có region
            rows_reg = conn.execute("SELECT phone, incident_time, ward, ticket_content FROM tickets WHERE region IS NULL OR region = '';").fetchall()
            for r in rows_reg:
                rg = detect_ticket_region({"province": r["ward"], "ticket_content": r["ticket_content"]}, default_region="MN")
                conn.execute("UPDATE tickets SET region = ? WHERE phone = ? AND incident_time = ?", (rg, r["phone"], r["incident_time"]))
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_feedback_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER,
                phone TEXT,
                package_title TEXT,
                ticket_content TEXT,
                summary_content TEXT,
                verified_by TEXT DEFAULT 'KTV',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


def init_db():
    global _db_initialized
    if _db_initialized:
        return
    with _DB_WRITE_LOCK:
        if _db_initialized:
            return
        try:
            conn = get_db_connection()
            _run_init_schema(conn)
            conn.close()
            _db_initialized = True
        except sqlite3.DatabaseError as e:
            err_msg = str(e).lower()
            if "malformed" in err_msg or "file is not a database" in err_msg or "corrupt" in err_msg:
                print(f"[DB INIT ERROR] Phát hiện lỗi database lúc khởi động ({e}). Đang tự động backup và tạo lại DB sạch...")
                _recover_corrupted_db(reason=str(e))
                conn = get_db_connection(retry_count=0)
                _run_init_schema(conn)
                conn.close()
                _db_initialized = True
            else:
                raise


def save_ai_feedback_sample(ticket_id=None, phone="", package_title="", ticket_content="", summary_content="", verified_by="KTV"):
    """Lưu mẫu tóm tắt chuẩn KTV đã duyệt để Qwen học theo (Few-shot)"""
    init_db()
    conn = get_db_connection()
    with conn:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO ai_feedback_samples (ticket_id, phone, package_title, ticket_content, summary_content, verified_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ticket_id, phone, package_title, ticket_content, summary_content, verified_by, now_str))

        if ticket_id:
            conn.execute("UPDATE tickets SET ai_summary = ? WHERE ticket_id = ?", (summary_content, ticket_id))
        elif phone:
            conn.execute("UPDATE tickets SET ai_summary = ? WHERE phone = ?", (summary_content, phone))
    conn.close()


def get_similar_ai_samples(ticket_content: str, limit: int = 2):
    """Tìm 1-2 mẫu phản ánh trong quá khứ có độ tương đồng cao nhất để nạp vào Prompt Qwen"""
    if not ticket_content:
        return []
    try:
        init_db()
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT id, package_title, ticket_content, summary_content 
            FROM ai_feedback_samples 
            ORDER BY id DESC LIMIT 100
        """).fetchall()
        conn.close()
        if not rows:
            return []

        from rapidfuzz import fuzz
        scored = []
        tc_clean = ticket_content.lower().strip()
        for r in rows:
            sample_content = str(r["ticket_content"] or "").lower().strip()
            if not sample_content or not r["summary_content"]:
                continue
            score = fuzz.token_set_ratio(tc_clean, sample_content)
            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_samples = [s[1] for s in scored if s[0] >= 35][:limit]
        return best_samples
    except Exception as e:
        print(f"⚠️ Lỗi tìm mẫu AI tương tự: {e}")
        return []

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
            if norm_status == excel_reader.LEVEL_1_STATUS:
                acc_st = rec.get("access_status") or "không xác định"
                return False, f"Trạng thái [{status}] nhưng tình trạng truy cập [{acc_st}] chưa đủ điều kiện tự đóng (yêu cầu khách phản ánh 'Không được hoàn toàn')"
            return False, f"Trạng thái [{status}] chưa đủ điều kiện tự đóng (dành cho KTV kiểm tra xử lý)"
    except Exception as e:
        return False, f"Lỗi kiểm tra điều kiện: {e}"

def save_or_update_ticket(t):
    with _DB_WRITE_LOCK:
        _system_counts_cache.clear()
        return _save_or_update_ticket_internal(t)

def _save_or_update_ticket_internal(t):
    """
    Lưu hoặc cập nhật phiếu vào database theo cặp (phone, incident_time).
    Mỗi lần phản ánh ở các mốc thời gian khác nhau sẽ là một bản ghi riêng biệt.
    """
    phone = str(t.get("phone", "")).strip()
    incident_time = str(t.get("incident_time", "")).strip()
    if not incident_time:
        if t.get("ticket_id"):
            incident_time = f"ID_{t.get('ticket_id')}"
        elif t.get("ticket_code"):
            clean_c = (t.get("ticket_code") or "").split("\n")[0].strip()
            incident_time = f"CODE_{clean_c}"
        elif t.get("created_time"):
            incident_time = str(t.get("created_time")).strip()
        else:
            incident_time = "Không xác định"

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
                ticket_id = t.get("ticket_id")
        
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
                                if not t.get("ai_summary") and existing_code["ai_summary"]:
                                    t["ai_summary"] = existing_code["ai_summary"]
                        conn.execute(
                            "DELETE FROM tickets WHERE ticket_code = ?",
                            (ticket_code,)
                        )
        
                # 2. Xử lý trùng lặp theo ticket_id: CHỈ gộp khi đây thực sự là cùng 1 phiếu (cùng ticket_id)
                # NẾU 1 số phản ánh nhiều lần (khác thời gian incident_time / khác mã phiếu) thì ĐÂY LÀ CÁC PHIẾU ĐỘC LẬP
                # Tuyệt đối không xóa bản ghi cũ và không kế thừa nhầm kết quả cũ!
                if ticket_id:
                    existing_id = conn.execute(
                        "SELECT * FROM tickets WHERE ticket_id = ? AND source = ?", 
                        (ticket_id, source)
                    ).fetchone()
                    if existing_id and existing_id["incident_time"] != incident_time:
                        has_old_eval = existing_id["status"] and existing_id["status"] not in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", None, "")
                        if has_old_eval:
                            if not t.get("status") or t.get("status") in ("CHỜ TIỀN KIỂM", "CHƯA PHÂN LOẠI", ""):
                                t["status"] = existing_id["status"]
                                t["color"] = existing_id["color"] or "green"
                                if not t.get("comment"):
                                    t["comment"] = existing_id["comment"] or ""
                                if not t.get("action_plan"):
                                    t["action_plan"] = existing_id["action_plan"] or ""
                                if not t.get("real_packages") or t.get("real_packages") == "--":
                                    t["real_packages"] = existing_id["real_packages"] or "--"
                                if not t.get("rat_types") or t.get("rat_types") == "--":
                                    t["rat_types"] = existing_id["rat_types"] or "--"
                                if not t.get("cem_data") or t.get("cem_data") == "--":
                                    t["cem_data"] = existing_id["cem_data"] or "--"
                                if not t.get("app_usage") or t.get("app_usage") == "--":
                                    t["app_usage"] = existing_id["app_usage"] or "--"
                        if not t.get("ai_summary") and existing_id["ai_summary"]:
                            t["ai_summary"] = existing_id["ai_summary"]

                        conn.execute(
                            "DELETE FROM tickets WHERE ticket_id = ? AND source = ?",
                            (ticket_id, source)
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
                    # Đối với tts_new hoặc phiếu mở lại (reopen_count > 0 / is_reopened):
                    # Nếu phiếu đang xuất hiện trên TTS thì luôn khôi phục 'Chưa đóng' để đưa vào danh sách cần xử lý.
                    is_reopened_flag = bool(t.get("is_reopened") or int(t.get("reopen_count") or 0) > 0)
                    if source != "tts_new" and not t.get("force_update_status") and not is_reopened_flag and existing["ticket_status"] in ("Đã đóng", "Da dong") and ticket_status == "Chưa đóng":
                        ticket_status = "Đã đóng"
                    elif is_reopened_flag:
                        ticket_status = "Chưa đóng"
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
        
                ccos_attachments = t.get("ccos_attachments")
                if ccos_attachments is None and existing and "ccos_attachments" in existing.keys():
                    ccos_attachments = existing["ccos_attachments"]

                processing_content = t.get("processing_content")
                if processing_content is None and existing and "processing_content" in existing.keys():
                    processing_content = existing["processing_content"]

                ward = t.get("ward")
                if not ward and existing and "ward" in existing.keys() and existing["ward"]:
                    ward = existing["ward"]
                if not ward:
                    ward = extract_ward_address(t.get("ticket_content", ""))

                region = t.get("region")
                if not region and existing and "region" in existing.keys() and existing["region"]:
                    region = existing["region"]
                if not region:
                    from region_detector import detect_ticket_region
                    region = detect_ticket_region({
                        "ticket_code": t.get("ticket_code", ""),
                        "step_name": t.get("step_name", ""),
                        "process_name": t.get("process_name", ""),
                        "province": ward,
                        "ticket_content": t.get("ticket_content", "")
                    }, default_region="MN")

                conn.execute("""
                    INSERT INTO tickets (
                        phone, incident_time, package_title, real_packages, rat_types,
                        cem_data, app_usage, ticket_content, status, comment,
                        action_plan, color, ticket_status, created_time, ai_summary,
                        source, ticket_code, ticket_id, flow_id, reopen_count, last_reopened_date,
                        phan_hoi_he_thong, id_he_thong, ccos_attachments, processing_content, prechecked_at, ward, region, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? NOT IN ('', 'CHƯA PHÂN LOẠI') THEN datetime('now', '+7 hours') ELSE NULL END, ?, ?, CURRENT_TIMESTAMP)
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
                        ai_summary = CASE 
                            WHEN excluded.ai_summary IS NOT NULL AND excluded.ai_summary NOT IN ('', 'null', 'None') THEN excluded.ai_summary 
                            ELSE tickets.ai_summary 
                        END,
                        source = excluded.source,
                        ticket_code = excluded.ticket_code,
                        ticket_id = COALESCE(excluded.ticket_id, tickets.ticket_id),
                        flow_id = COALESCE(excluded.flow_id, tickets.flow_id),
                        reopen_count = excluded.reopen_count,
                        last_reopened_date = excluded.last_reopened_date,
                        phan_hoi_he_thong = COALESCE(excluded.phan_hoi_he_thong, tickets.phan_hoi_he_thong),
                        id_he_thong = COALESCE(excluded.id_he_thong, tickets.id_he_thong),
                        ccos_attachments = COALESCE(excluded.ccos_attachments, tickets.ccos_attachments),
                        processing_content = COALESCE(NULLIF(excluded.processing_content, ''), tickets.processing_content),
                        prechecked_at = CASE WHEN excluded.status NOT IN ('', 'CHƯA PHÂN LOẠI') THEN datetime('now', '+7 hours') ELSE COALESCE(tickets.prechecked_at, datetime('now', '+7 hours')) END,
                        ward = COALESCE(NULLIF(excluded.ward, ''), tickets.ward),
                        region = COALESCE(NULLIF(excluded.region, ''), tickets.region),
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
                    ccos_attachments,
                    processing_content or "",
                    t.get("status", "CHƯA PHÂN LOẠI"),
                    ward or "",
                    region or "MN",
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
            err_msg = str(e).lower()
            if "locked" in err_msg and attempt < 4:
                time.sleep(0.2 * (attempt + 1))
                continue
            if "malformed" in err_msg and attempt < 4:
                try:
                    r_conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
                    r_conn.execute("REINDEX;")
                    r_conn.close()
                except Exception:
                    pass
                time.sleep(0.3 * (attempt + 1))
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

SPAM_CALL_PKG_SQL = """(
    (package_title LIKE '%Spam%' OR package_title LIKE '%Gọi đi%' OR package_title LIKE '%Nhận cuộc gọi%' OR package_title LIKE '%Cuộc gọi%' OR package_title LIKE '%tin nhắn%')
    AND (
        ticket_content LIKE '%viettel%' OR ticket_content LIKE '%vettel%' 
        OR ticket_content LIKE '%mobi%' OR ticket_content LIKE '%vms%'
        OR ticket_content LIKE '%ngoại mạng%' OR ticket_content LIKE '%ngoai mang%'
        OR ticket_content LIKE '%liên mạng%' OR ticket_content LIKE '%lien mang%'
        OR ticket_content LIKE '%spam%' OR ticket_content LIKE '%cam kết%' OR ticket_content LIKE '%cam ket%'
        OR package_title LIKE '%Spam%'
    )
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

def sync_active_tickets_state(active_keys, source="tts_old", key_type="phone", service_type=None, region=None):
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
        elif service_type in ("spam_call", "outbound_block", "chan_goi_ngoai_mang"):
            service_sql = f" AND {SPAM_CALL_PKG_SQL}"
        elif service_type == "voice_sms":
            service_sql = f" AND {VOICE_PKG_SQL}"

        if source in ("tts_old", "tts_old_api"):
            source_condition = "(source IN ('tts_old', 'tts_old_api') OR source IS NULL)"
            source_params = []
        else:
            source_condition = "source = ?"
            source_params = [source]

        if region and region != "ALL":
            source_condition += " AND region = ?"
            source_params.append(region)

        if not active_keys:
            # Nếu trên TTS đã hết sạch phiếu chờ xử lý -> toàn bộ phiếu chưa đóng trong DB thuộc nguồn này đã đóng!
            conn.execute(f"""
                UPDATE tickets 
                SET ticket_status = 'Đã đóng', closed_at = COALESCE(closed_at, datetime('now', '+7 hours')), updated_at = CURRENT_TIMESTAMP 
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
                    SET ticket_status = 'Đã đóng', closed_at = COALESCE(closed_at, datetime('now', '+7 hours')), updated_at = CURRENT_TIMESTAMP 
                    WHERE {source_condition}
                      AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
                      {service_sql}
                """, source_params)
            else:
                placeholders = ",".join(["?"] * len(raw_active_keys))
                conn.execute(f"""
                    UPDATE tickets 
                    SET ticket_status = 'Đã đóng', closed_at = COALESCE(closed_at, datetime('now', '+7 hours')), updated_at = CURRENT_TIMESTAMP 
                    WHERE {source_condition}
                      AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
                      {service_sql}
                      AND substr(ticket_code, 1, case when instr(ticket_code, char(10)) > 0 then instr(ticket_code, char(10)) - 1 else length(ticket_code) end) NOT IN ({placeholders})
                """, source_params + list(raw_active_keys))
        else:
            placeholders = ",".join(["?"] * len(active_keys))
            conn.execute(f"""
                UPDATE tickets 
                SET ticket_status = 'Đã đóng', closed_at = COALESCE(closed_at, datetime('now', '+7 hours')), updated_at = CURRENT_TIMESTAMP 
                WHERE {source_condition}
                  AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
                  {service_sql}
                  AND phone NOT IN ({placeholders})
            """, source_params + list(active_keys))
    conn.close()

_system_counts_cache = {}
_system_counts_cache_time = {}

def get_system_counts(region=None):
    """Lấy số lượng phiếu phân chia theo từng nghiệp vụ cho Menu Sidebar (hỗ trợ lọc theo vùng miền)."""
    import time
    now_ts = time.time()
    reg_key = str(region or "ALL").strip().upper()
    if reg_key in _system_counts_cache and (now_ts - _system_counts_cache_time.get(reg_key, 0) < 3.0):
        return dict(_system_counts_cache[reg_key])

    init_db()
    conn = get_db_connection()
    counts = {
        "tts_old_data": 0,
        "tts_old_voice": 0,
        "tts_new_data": 0,
        "tts_new_call": 0,
        "tts_new_sms": 0,
        "tts_new_other": 0,
        "tts_new_spam_call": 0,
        "tts_new_voice": 0,
        "tts_old_api_data": 0,
        "tts_old_api_voice": 0,
        "total_active": 0,
        "total_closed": 0,
        "total_all": 0
    }
    try:
        reg_cond = ""
        reg_params = []
        if region and str(region).strip().upper() != "ALL":
            reg_cond = " AND region = ?"
            reg_params = [str(region).strip().upper()]

        c1 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (source = 'tts_old' OR source IS NULL) 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {DATA_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_old_data"] = c1[0] if c1 else 0

        c2 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (source = 'tts_old' OR source IS NULL) 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {VOICE_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_old_voice"] = c2[0] if c2 else 0

        c3 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {DATA_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_new_data"] = c3[0] if c3 else 0

        c_call = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {CALL_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_new_call"] = c_call[0] if c_call else 0

        c_sms = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {SMS_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_new_sms"] = c_sms[0] if c_sms else 0

        c_other = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {OTHER_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_new_other"] = c_other[0] if c_other else 0

        c_spam_call = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {SPAM_CALL_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_new_spam_call"] = c_spam_call[0] if c_spam_call else 0

        c4 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE source = 'tts_new' 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {VOICE_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_new_voice"] = c4[0] if c4 else 0

        c5 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (source = 'tts_old_api' OR source = 'tts_old' OR source IS NULL) 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {DATA_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_old_api_data"] = c5[0] if c5 else 0

        c6 = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (source = 'tts_old_api' OR source = 'tts_old' OR source IS NULL) 
              AND (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              AND {VOICE_PKG_SQL}
              {reg_cond}
        """, reg_params).fetchone()
        counts["tts_old_api_voice"] = c6[0] if c6 else 0

        ca = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong')
              {reg_cond}
        """, reg_params).fetchone()
        counts["total_active"] = ca[0] if ca else 0

        cc = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (ticket_status = 'Đã đóng' OR ticket_status = 'Da dong')
              {reg_cond}
        """, reg_params).fetchone()
        counts["total_closed"] = cc[0] if cc else 0

        ct = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE 1=1
              {reg_cond}
        """, reg_params).fetchone()
        counts["total_all"] = ct[0] if ct else 0

        # Thống kê ngày hiện tại (Hôm nay)
        today_iso = datetime.now().strftime("%Y-%m-%d")
        today_dmy = datetime.now().strftime("%d/%m/%Y")

        ctoday = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (SUBSTR(updated_at, 1, 10) = ? 
               OR updated_at LIKE ? 
               OR incident_time LIKE ?)
               {reg_cond}
        """, [today_iso, f"{today_iso}%", f"{today_dmy}%"] + reg_params).fetchone()
        counts["today_total"] = ctoday[0] if ctoday else 0

        c_closed_today = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (ticket_status = 'Đã đóng' OR ticket_status = 'Da dong') 
              AND (SUBSTR(updated_at, 1, 10) = ? OR updated_at LIKE ?)
              {reg_cond}
        """, [today_iso, f"{today_iso}%"] + reg_params).fetchone()
        counts["today_closed"] = c_closed_today[0] if c_closed_today else 0

        c_active_today = conn.execute(f"""
            SELECT count(*) FROM tickets 
            WHERE (ticket_status != 'Đã đóng' AND ticket_status != 'Da dong') 
              AND (SUBSTR(updated_at, 1, 10) = ? OR updated_at LIKE ? OR incident_time LIKE ?)
              {reg_cond}
        """, [today_iso, f"{today_iso}%", f"{today_dmy}%"] + reg_params).fetchone()
        counts["today_active"] = c_active_today[0] if c_active_today else 0
    except Exception as e:
        print("Lỗi get_system_counts:", e)
    finally:
        conn.close()
    _system_counts_cache[reg_key] = counts
    _system_counts_cache_time[reg_key] = now_ts
    return counts

def get_ticket_counts(source=None, service_type=None, search=None, region=None):
    """
    Truy vấn đếm tổng số phiếu, đã đóng, chưa đóng siêu tốc qua SQL (1-2ms),
    thay thế việc duyệt toàn bộ mảng Python get_all_tickets.
    """
    init_db()
    conn = get_db_connection()
    try:
        query = """
            SELECT 
                COUNT(*),
                SUM(CASE WHEN ticket_status LIKE '%Đã đóng%' OR ticket_status LIKE '%Da dong%' THEN 1 ELSE 0 END)
            FROM tickets WHERE 1=1
        """
        params = []
        if source:
            if source in ("tts_old", "tts_old_api"):
                query += " AND (source = 'tts_old_api' OR source = 'tts_old' OR source IS NULL OR source = '')"
            else:
                query += " AND source = ?"
                params.append(source)
        if service_type == "data":
            query += f" AND {DATA_PKG_SQL}"
        elif service_type in ("call", "voice", "cuoc_goi"):
            query += f" AND {CALL_PKG_SQL}"
        elif service_type in ("sms", "tin_nhan"):
            query += f" AND {SMS_PKG_SQL}"
        elif service_type in ("other", "khac"):
            query += f" AND {OTHER_PKG_SQL}"
        elif service_type in ("spam_call", "outbound_block", "chan_goi_ngoai_mang"):
            query += f" AND {SPAM_CALL_PKG_SQL}"
        elif service_type == "voice_sms":
            query += f" AND {VOICE_PKG_SQL}"

        # 🎯 Phân vùng miền (MB / MN / MT)
        if region and region != "ALL":
            query += " AND region = ?"
            params.append(region)

        if search:
            query += " AND (phone LIKE ? OR ticket_content LIKE ? OR package_title LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])

        row = conn.execute(query, params).fetchone()
        total = row[0] or 0
        closed = row[1] or 0
        active = total - closed
        return total, closed, active
    except Exception as e:
        print("Lỗi get_ticket_counts:", e)
        return 0, 0, 0
    finally:
        conn.close()

def get_all_tickets(search=None, status_filter=None, tab_filter=None, source=None, service_type=None, region=None):
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

    # 🎯 Phân vùng miền (MB / MN / MT)
    if region and region != "ALL":
        query += " AND region = ?"
        params.append(region)

    # Lọc theo loại nghiệp vụ (data / call / sms / other / spam_call / voice_sms)
    if service_type == "data":
        query += f" AND {DATA_PKG_SQL}"
    elif service_type in ("call", "voice", "cuoc_goi"):
        query += f" AND {CALL_PKG_SQL}"
    elif service_type in ("sms", "tin_nhan"):
        query += f" AND {SMS_PKG_SQL}"
    elif service_type in ("other", "khac"):
        query += f" AND {OTHER_PKG_SQL}"
    elif service_type in ("spam_call", "outbound_block", "chan_goi_ngoai_mang"):
        query += f" AND {SPAM_CALL_PKG_SQL}"
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
        if not search:
            query += " LIMIT 400"
    elif tab_filter == "da_dong":
        query += " ORDER BY updated_at DESC"
        if not search:
            query += " LIMIT 400"
    else:
        query += " ORDER BY updated_at DESC"

    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        item = dict(r)
        # Loại bỏ trường processing_content (chứa html log khổng lồ) để giảm payload từ 4MB xuống 200KB
        item.pop("processing_content", None)

        is_closed = (item.get("ticket_status") in ("Đã đóng", "Da dong") or "Đã đóng" in str(item.get("ticket_status") or ""))

        can_close, reason = check_ticket_can_close(item)
        item["can_close"] = can_close
        item["cannot_close_reason"] = reason
        if not item.get("closed_at") and is_closed:
            raw_up = str(item.get("updated_at") or "").strip()
            if raw_up:
                try:
                    from datetime import datetime, timedelta
                    dt = datetime.strptime(raw_up.split('.')[0], "%Y-%m-%d %H:%M:%S")
                    item["closed_at"] = (dt + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    item["closed_at"] = raw_up
            else:
                item["closed_at"] = raw_up
        if not item.get("prechecked_at") and item.get("status") not in (None, "", "CHƯA PHÂN LOẠI"):
            raw_up = str(item.get("updated_at") or "").strip()
            if raw_up:
                try:
                    from datetime import datetime, timedelta
                    dt = datetime.strptime(raw_up.split('.')[0], "%Y-%m-%d %H:%M:%S")
                    item["prechecked_at"] = (dt + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    item["prechecked_at"] = raw_up
            else:
                item["prechecked_at"] = raw_up

        # Gắn kết quả phân tích Chặn gọi ngoại mạng / Cam kết (CHỈ PHÂN TÍCH CHO PHIẾU CHƯA ĐÓNG ĐỂ TỐI ƯU TỐC ĐỘ)
        if not is_closed:
            try:
                from spam_call_analyzer import analyze_spam_call_ticket
                tc_lower = str(item.get("ticket_content") or "").lower()
                pt_lower = str(item.get("package_title") or "").lower()
                if (service_type in ("spam_call", "outbound_block", "chan_goi_ngoai_mang") or 
                    "spam" in pt_lower or "spam" in tc_lower or 
                    "viettel" in tc_lower or "mobi" in tc_lower or 
                    "cam kết" in tc_lower or "cam ket" in tc_lower or "ngoại mạng" in tc_lower):
                    s_res = analyze_spam_call_ticket(item.get("package_title", ""), item.get("ticket_content", ""), item.get("ccos_attachments"), phone=str(item.get("phone") or ""))
                    item["is_outbound_block"] = s_res["is_outbound_block"]
                    item["carrier_display"] = s_res["carrier_display"]
                    item["carriers"] = s_res["carriers"]
                    item["has_commitment"] = s_res["has_commitment"]
                    item["commitment_display"] = s_res["commitment_display"]
                    item["commitment_source"] = s_res["commitment_source"]
                    item["commitment_files"] = s_res["commitment_files"]
                    item["spam_summary"] = s_res["summary"]
            except Exception:
                pass

        results.append(item)
    conn.close()
    return results

def update_ticket_field(phone, field, value, incident_time=None):
    valid_fields = ["comment", "action_plan", "ticket_status", "status", "ai_summary", "closed_by", "reopen_count", "last_reopened_date", "incident_cause", "closed_at", "prechecked_at", "ward"]
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

        # Nếu cập nhật ward, đồng bộ luôn mục 5 trong ai_summary (nếu có)
        if field == "ward" and value:
            try:
                row_sum = conn.execute(
                    "SELECT ai_summary FROM tickets WHERE (phone = ? OR phone LIKE ?) ORDER BY updated_at DESC LIMIT 1",
                    (str(phone).strip(), p_suffix)
                ).fetchone()
                if row_sum and row_sum["ai_summary"] and "5. Khu vực xảy ra lỗi:" in row_sum["ai_summary"]:
                    old_sum = row_sum["ai_summary"]
                    new_sum = re.sub(r'5\.\s*Khu vực xảy ra lỗi:[^\n]*', f'5. Khu vực xảy ra lỗi: Tại 1 khu vực ({value})', old_sum)
                    if new_sum != old_sum:
                        conn.execute(
                            "UPDATE tickets SET ai_summary = ? WHERE (phone = ? OR phone LIKE ?)",
                            (new_sum, str(phone).strip(), p_suffix)
                        )
            except Exception:
                pass
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

def normalize_staff_name(name: str) -> str:
    if not name:
        return "Chưa rõ"
    n = str(name).strip()
    nl = n.lower()
    if "quangvu" in nl or "quang vũ" in nl or "lê quang vũ" in nl:
        return "Lê Quang Vũ"
    if "nguyenhoa" in nl or "nguyễn thị hoa" in nl or "nguyen thi hoa" in nl:
        return "Nguyễn Thị Hoa"
    if "lan phuong" in nl or "lan phương" in nl:
        return "Hoàng Thị Lan Phương"
    return n

def get_closed_tickets_analytics(time_filter="all", source_filter=None, service_filter=None):
    """
    Thống kê tổng hợp số liệu phân tích chuyên sâu cho các phiếu đã đóng:
    - time_filter: 'all', 'today', '7days', '30days'
    - source_filter: 'all', 'tts_old', 'tts_new'
    - service_filter: 'all', 'data' (Mobile Internet), 'voice_sms' (Thoại/SMS/Gói/PA Khác), 'call', 'sms', 'other'
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
            elif service_filter in ('call', 'thoai'):
                where.append(CALL_PKG_SQL)
            elif service_filter == 'sms':
                where.append(SMS_PKG_SQL)
            elif service_filter in ('other', 'goi_cuoc'):
                where.append(OTHER_PKG_SQL)
            elif service_filter == 'voice_sms':
                where.append(VOICE_PKG_SQL)

        where_sql = " AND ".join(where)

        # 1. Tổng quan số lượng tách bạch chuẩn xác
        q_totals = f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN closed_by IS NOT NULL AND closed_by != '' 
                         AND closed_by NOT LIKE '%Tự động%' AND closed_by NOT LIKE '%Hệ thống%' AND closed_by NOT LIKE '%Bot%' 
                    THEN 1 ELSE 0 END) as manual_cnt,
                SUM(CASE WHEN closed_by LIKE '%Tự động%' OR closed_by LIKE '%Hệ thống%' OR closed_by LIKE '%Bot%' 
                    THEN 1 ELSE 0 END) as auto_cnt,
                SUM(CASE WHEN closed_by IS NULL OR closed_by = '' 
                    THEN 1 ELSE 0 END) as synced_cnt,
                SUM(CASE WHEN source = 'tts_new' THEN 1 ELSE 0 END) as tts_new_cnt,
                SUM(CASE WHEN source IN ('tts_old', 'tts_old_api') OR source IS NULL THEN 1 ELSE 0 END) as tts_old_cnt,
                SUM(CASE WHEN {DATA_PKG_SQL} THEN 1 ELSE 0 END) as data_cnt,
                SUM(CASE WHEN {CALL_PKG_SQL} THEN 1 ELSE 0 END) as call_cnt,
                SUM(CASE WHEN {SMS_PKG_SQL} THEN 1 ELSE 0 END) as sms_cnt,
                SUM(CASE WHEN {OTHER_PKG_SQL} THEN 1 ELSE 0 END) as other_cnt,
                SUM(CASE WHEN {VOICE_PKG_SQL} THEN 1 ELSE 0 END) as voice_cnt
            FROM tickets WHERE {where_sql}
        """
        row = conn.execute(q_totals, params).fetchone()
        total = row["total"] or 0
        manual_cnt = row["manual_cnt"] or 0
        auto_cnt = row["auto_cnt"] or 0
        synced_cnt = row["synced_cnt"] or 0
        tts_new_cnt = row["tts_new_cnt"] or 0
        tts_old_cnt = row["tts_old_cnt"] or 0
        data_cnt = row["data_cnt"] or 0
        call_cnt = row["call_cnt"] or 0
        sms_cnt = row["sms_cnt"] or 0
        other_cnt = row["other_cnt"] or 0
        voice_cnt = row["voice_cnt"] or 0

        tool_closed = manual_cnt + auto_cnt
        manual_pct = round(manual_cnt * 100.0 / tool_closed, 1) if tool_closed else 0
        auto_pct = round(auto_cnt * 100.0 / tool_closed, 1) if tool_closed else 0
        synced_pct = round(synced_cnt * 100.0 / total, 1) if total else 0

        # Hôm nay đóng bao nhiêu (Tách phiếu KTV/Tool thực đóng vs phiếu đồng bộ)
        today_manual_q = f"""
            SELECT COUNT(*) FROM tickets 
            WHERE (ticket_status = 'Đã đóng' OR ticket_status = 'Da dong') 
              AND closed_by IS NOT NULL AND closed_by != ''
              AND SUBSTR(updated_at, 1, 10) = ?
        """
        today_m_row = conn.execute(today_manual_q, [today_str]).fetchone()
        today_manual_cnt = today_m_row[0] if today_m_row else 0

        today_total_q = f"""
            SELECT COUNT(*) FROM tickets 
            WHERE (ticket_status = 'Đã đóng' OR ticket_status = 'Da dong') 
              AND SUBSTR(updated_at, 1, 10) = ?
        """
        today_t_row = conn.execute(today_total_q, [today_str]).fetchone()
        today_total_cnt = today_t_row[0] if today_t_row else 0
        today_synced_cnt = max(0, today_total_cnt - today_manual_cnt)

        # 2. Phân bổ theo nhận định
        q_diag = f"""
            SELECT 
                CASE 
                    WHEN status IS NULL OR TRIM(status) = '' THEN 'Phiếu lịch sử OneOSS (Chưa tiền kiểm)'
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

        # 5. Danh sách KTV đóng thủ công (Đã gộp chuẩn hóa theo họ tên)
        q_staff = f"""
            SELECT closed_by, COUNT(*) as cnt
            FROM tickets 
            WHERE {where_sql} AND closed_by IS NOT NULL AND closed_by != '' 
              AND closed_by NOT LIKE '%Tự động%' AND closed_by NOT LIKE '%Hệ thống%' AND closed_by NOT LIKE '%Bot%'
            GROUP BY closed_by ORDER BY cnt DESC
        """
        staff_dict = {}
        for r in conn.execute(q_staff, params).fetchall():
            c_name = normalize_staff_name(r["closed_by"])
            staff_dict[c_name] = staff_dict.get(c_name, 0) + int(r["cnt"] or 0)

        staff_list = [
            {"name": name, "count": count} 
            for name, count in sorted(staff_dict.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "total": total,
            "manual_cnt": manual_cnt,
            "manual_percent": manual_pct,
            "auto_cnt": auto_cnt,
            "auto_percent": auto_pct,
            "synced_cnt": synced_cnt,
            "synced_percent": synced_pct,
            "tool_closed_cnt": tool_closed,
            "today_cnt": today_manual_cnt,
            "today_manual_cnt": today_manual_cnt,
            "today_synced_cnt": today_synced_cnt,
            "today_total_cnt": today_total_cnt,
            "tts_new_cnt": tts_new_cnt,
            "tts_old_cnt": tts_old_cnt,
            "data_cnt": data_cnt,
            "call_cnt": call_cnt,
            "sms_cnt": sms_cnt,
            "other_cnt": other_cnt,
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
            "synced_cnt": 0, "synced_percent": 0, "tool_closed_cnt": 0,
            "today_cnt": 0, "today_manual_cnt": 0, "today_synced_cnt": 0, "today_total_cnt": 0,
            "tts_new_cnt": 0, "tts_old_cnt": 0, "data_cnt": 0, "call_cnt": 0, "sms_cnt": 0, "other_cnt": 0, "voice_cnt": 0,
            "by_diagnosis": [], "daily_trend": [], "top_packages": [], "staff_list": []
        }
    finally:
        conn.close()

def normalize_loc_string(s: str) -> str:
    if not s:
        return ""
    import unicodedata
    s = str(s).lower()
    s = unicodedata.normalize('NFD', s)
    s = re.sub(r'[\u0300-\u036f]', '', s)
    s = s.replace('đ', 'd').replace('Đ', 'd')
    s = re.sub(r'\b(phuong|xa|thi tran|quan|huyen|thi xa|thanh pho|tinh|tp\.|tp|p\.|x\.)\b', '', s)
    s = re.sub(r'[^a-z0-9]', ' ', s)
    return ' '.join(s.split())


def is_loc_matched(tts_ward, tts_prov, act_ward, act_prov) -> bool:
    nw_t = normalize_loc_string(tts_ward)
    nw_a = normalize_loc_string(act_ward)
    if not nw_t or not nw_a:
        return False
    ward_matched = (nw_t == nw_a) or (nw_t in nw_a) or (nw_a in nw_t)
    if not ward_matched:
        st = set(nw_t.split())
        sa = set(nw_a.split())
        ward_matched = len(st) > 0 and len(st.intersection(sa)) / len(st) >= 0.6
    if not ward_matched:
        return False

    np_t = normalize_loc_string(tts_prov)
    np_a = normalize_loc_string(act_prov)
    if np_t and np_a:
        hcm = ('ho chi minh', 'hcm', 'sai gon')
        if any(x in np_t for x in hcm) and any(x in np_a for x in hcm):
            return True
        hn = ('ha noi', 'hni')
        if any(x in np_t for x in hn) and any(x in np_a for x in hn):
            return True
        return (np_t == np_a) or (np_t in np_a) or (np_a in np_t)
    return True


def validate_ttsnew_ward_for_51(ticket_id=None, phone=None, ticket_code=None, ticket_dict=None) -> tuple[bool, str]:
    """
    Kiểm tra điều kiện địa bàn Phường/Xã trước khi chuyển bước 5.1 (Xây dựng PA xử lý) trên TTS Mới.
    Yêu cầu:
    1. Đã cập nhật Tỉnh/TP trên TTS Mới
    2. Đã cập nhật Phường/Xã trên TTS Mới
    3. Không bị sai khác so với dữ liệu trạm CEM (ngày phản ánh) hoặc Radio Status (port 1708)
    
    Trả về: (is_valid: bool, reason: str)
    """
    row = None
    if ticket_dict and isinstance(ticket_dict, dict):
        row = ticket_dict
    else:
        conn = get_db_connection()
        if ticket_id:
            row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ? AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1", (ticket_id,)).fetchone()
        if not row and ticket_code:
            clean_c = ticket_code.split("\n")[0].strip()
            row = conn.execute("SELECT * FROM tickets WHERE (ticket_code = ? OR ticket_code LIKE ?) AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1", (clean_c, f"{clean_c}%")).fetchone()
        if not row and phone:
            row = conn.execute("SELECT * FROM tickets WHERE phone = ? AND source = 'tts_new' ORDER BY updated_at DESC LIMIT 1", (phone,)).fetchone()
        if row:
            row = dict(row)
        conn.close()

    prov_id = row.get("province_id") if row else None
    prov_name = (row.get("province_name") or row.get("province") or "").strip() if row else ""
    ward_id = row.get("ward_id") if row else None
    ward_name = (row.get("ward_name") or "").strip() if row else ""

    t_id = ticket_id or (row.get("ticket_id") if row else None)
    if t_id and (not prov_name or not ward_name):
        try:
            from routers.tickets import get_tts_new_ticket_boundary
            b_res = get_tts_new_ticket_boundary(int(t_id))
            if b_res and b_res.get("success"):
                prov_id = b_res.get("province_id") or prov_id
                prov_name = b_res.get("province_name") or prov_name
                ward_id = b_res.get("ward_id") or ward_id
                ward_name = b_res.get("ward_name") or ward_name
        except Exception:
            pass

    if not prov_id and not prov_name:
        return False, "chưa cập nhật Tỉnh/TP trên TTS Mới (đang bỏ trống Tỉnh/TP)"
    if not ward_id and not ward_name:
        return False, "chưa cập nhật Phường/Xã trên TTS Mới (đang bỏ trống Phường/Xã)"

    cem_text = (row.get("cem_data") or "") if row else ""
    cell_patterns = re.findall(r'(?:[2-5]G[-_]|UL[-_]|DL[-_])[A-Za-z0-9]+[-_][A-Za-z0-9]+', cem_text)

    expected_locations = []
    try:
        from routers.tickets import get_1708_base_url
        base_1708 = get_1708_base_url()
    except Exception:
        base_1708 = (os.getenv("PORT_1708_URL") or "http://vnpt_customer_position_app:1708").rstrip("/")
    for c in set(cell_patterns):
        try:
            r = requests.get(f"{base_1708}/api/cell/{c}", timeout=1.5)
            if r.status_code == 200:
                d = r.json()
                w = d.get("ward") or (d.get("summary") or {}).get("ward")
                p = d.get("province") or (d.get("summary") or {}).get("province")
                if w:
                    expected_locations.append((w.strip(), (p or "").strip()))
        except Exception:
            pass

    target_phone = phone or (row.get("phone") if row else "")
    if not expected_locations and target_phone:
        try:
            p84 = target_phone if target_phone.startswith("84") else ("84" + target_phone.lstrip("0"))
            r = requests.get(f"{base_1708}/api/msisdn/{p84}", timeout=1.5)
            if r.status_code == 200:
                d = r.json()
                w = d.get("ward") or (d.get("summary") or {}).get("ward")
                p = d.get("province") or (d.get("summary") or {}).get("province")
                if w:
                    expected_locations.append((w.strip(), (p or "").strip()))
        except Exception:
            pass

    if expected_locations:
        matched = False
        for act_w, act_p in expected_locations:
            if is_loc_matched(ward_name, prov_name, act_w, act_p):
                matched = True
                break
        if not matched:
            act_str = " | ".join([f"{w}, {p}" if p else w for w, p in set(expected_locations)])
            return False, f"địa bàn trên TTS Mới ({ward_name}, {prov_name}) sai khác so với check CEM & Profile Status (Trạm thực tế: {act_str})"

    return True, "Hợp lệ"


if __name__ == "__main__":
    init_db()
    print("✅ Database initialized successfully at:", DB_PATH)

