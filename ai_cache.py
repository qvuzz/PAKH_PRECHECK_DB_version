import os
import json
import hashlib
import time

CACHE_FILE = "ai_cache.json"

# 6 giờ
CACHE_TTL = 6 * 60 * 60


def load_cache():
    """
    Đọc cache từ file JSON
    """
    if not os.path.exists(CACHE_FILE):
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    """
    Ghi cache xuống file JSON
    """
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            cache,
            f,
            ensure_ascii=False,
            indent=2
        )


def build_content_hash(content):
    """
    Tạo hash từ nội dung phản ánh
    """
    normalized = str(content or "").strip().lower()

    return hashlib.md5(
        normalized.encode("utf-8")
    ).hexdigest()


def get_cached_summary(phone, package_title="", content=""):
    """
    Kiểm tra cache còn hiệu lực hay không.
    Hỗ trợ linh hoạt 2 hoặc 3 tham số:
    - get_cached_summary(phone, content)
    - get_cached_summary(phone, package_title, content)

    Return:
        summary nếu cache hợp lệ
        None nếu không tìm thấy hoặc hết hạn
    """
    if not content and package_title:
        ticket_content = package_title
    else:
        ticket_content = content

    cache = load_cache()

    phone_key = str(phone).strip() if phone else ""
    current_hash = build_content_hash(ticket_content)

    # Tìm theo phone_key trước, nếu không có thử tìm theo content_hash (để tương thích dữ liệu cũ)
    item = cache.get(phone_key)
    if not item and current_hash in cache:
        item = cache.get(current_hash)

    if not item:
        return None

    if item.get("content_hash") and item.get("content_hash") != current_hash:
        return None

    timestamp = item.get("timestamp", 0)

    if time.time() - timestamp > CACHE_TTL:
        return None

    return item.get("summary")


def save_summary(phone, package_title="", content="", summary=""):
    """
    Lưu summary vào cache với thông tin đầy đủ:
    phone, package_title, ticket_content, content_hash, summary, timestamp.
    Hỗ trợ linh hoạt 3 hoặc 4 tham số:
    - save_summary(phone, content, summary)
    - save_summary(phone, package_title, content, summary)
    """
    if not summary and content:
        actual_package_title = ""
        actual_content = package_title
        actual_summary = content
    else:
        actual_package_title = package_title
        actual_content = content
        actual_summary = summary

    cache = load_cache()
    phone_key = str(phone).strip() if phone else build_content_hash(actual_content)

    cache[phone_key] = {
        "phone": str(phone).strip() if phone else "",
        "package_title": actual_package_title,
        "ticket_content": actual_content,
        "content_hash": build_content_hash(actual_content),
        "summary": actual_summary,
        "timestamp": time.time()
    }

    save_cache(cache)


def clean_expired_cache():
    """
    Xóa cache hết hạn
    Có thể gọi lúc khởi động chương trình
    """
    cache = load_cache()
    now = time.time()
    new_cache = {}

    for key, item in cache.items():
        timestamp = item.get("timestamp", 0)
        if now - timestamp <= CACHE_TTL:
            new_cache[key] = item

    save_cache(new_cache)


def clear_cache():
    """
    Xóa toàn bộ nội dung cache (reset về {})
    """
    save_cache({})
    print("[AI CACHE] Da tu dong don sach file ai_cache.json")