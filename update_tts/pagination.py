# update_tts/pagination.py
# Xử lý phân trang bảng #myTable bằng Playwright.
# Port lại đúng logic đã dùng trong crawler_tts.py (Selenium) - click theo SỐ TRANG cụ thể
# (không dùng nút «/» vì từng phát hiện nút "»" thực chất nhảy tới trang CUỐI, không phải trang kế).

GET_PAGE_NUMBERS_JS = """
() => {
    const uls = Array.from(document.querySelectorAll('ul.pagination, .pagination, [class*="pagination"]')).filter(el => el.offsetParent !== null);
    if (!uls.length) return [];
    let maxNums = [];
    uls.forEach(ul => {
        const links = Array.from(ul.querySelectorAll('a, button, li'));
        const nums = [];
        links.forEach(a => {
            const t = (a.textContent || '').trim();
            const m = t.match(/^(\\d+)/);
            if (m) nums.push(parseInt(m[1], 10));
        });
        if (nums.length > maxNums.length) maxNums = nums;
    });
    return maxNums;
}
"""

CLICK_PAGE_NUMBER_JS = """
(targetPage) => {
    const uls = Array.from(document.querySelectorAll('ul.pagination, .pagination, [class*="pagination"]')).filter(el => el.offsetParent !== null);
    for (let ul of uls) {
        const links = Array.from(ul.querySelectorAll('li, a, button'));
        const target = links.find(a => {
            const t = (a.textContent || '').trim();
            const m = t.match(/^(\\d+)/);
            return m && parseInt(m[1], 10) === targetPage;
        });
        if (target) {
            const clickEl = target.querySelector('a') || target;
            clickEl.click();
            return true;
        }
    }
    return false;
}
"""

FINGERPRINT_JS = """
() => {
    const firstRow = document.querySelector('#myTable tbody tr');
    return firstRow ? (firstRow.innerText || '').trim() : '';
}
"""


def get_total_pages(page):
    page_numbers = page.evaluate(GET_PAGE_NUMBERS_JS)
    return max(page_numbers) if page_numbers else 1


def get_current_fingerprint(page):
    return page.evaluate(FINGERPRINT_JS)


def go_to_page(page, target_page, max_wait_seconds=7.0):
    """
    Bấm vào đúng số trang, chờ bảng đổi dữ liệu (dựa theo fingerprint dòng đầu tiên).
    Trả về True nếu chuyển trang thành công (hoặc đã sẵn ở đúng trang không cần đổi).
    """
    old_fingerprint = get_current_fingerprint(page)
    clicked = page.evaluate(CLICK_PAGE_NUMBER_JS, target_page)
    if not clicked:
        print(f"⚠️ Không tìm thấy nút số trang {target_page}.")
        return False

    waited = 0.0
    while waited < max_wait_seconds:
        page.wait_for_timeout(300)
        waited += 0.3
        new_fingerprint = get_current_fingerprint(page)
        if new_fingerprint != old_fingerprint:
            return True

    print(f"⚠️ Đã chờ {waited:.1f}s nhưng bảng không đổi dữ liệu sau khi bấm trang {target_page}.")
    return False


def find_container_across_pages(page, search_fn, phone, start_page=1, max_pages=None):
    """
    Quét lần lượt các trang cho tới khi search_fn(page, phone) tìm thấy kết quả,
    hoặc đã quét hết tất cả các trang mà không tìm thấy.

    ⏱ THỜI GIAN: worst-case = total_pages × max_wait_seconds (go_to_page).
    Với bảng lớn (20+ trang), nếu SĐT không tồn tại trên TTS nữa (đã bị đóng bởi người khác),
    hàm sẽ quét hết toàn bộ trang mới biết. Giữ timeout go_to_page thấp (12s) để giảm thiểu.

    Trả về (container, found_on_page) hoặc (None, None) nếu không tìm thấy.
    """
    total_pages = max_pages or get_total_pages(page)

    # Thử ngay trang đang hiển thị trước (không tốn công click nếu may mắn đã đúng trang)
    result = search_fn(page, phone)
    if result is not None:
        return result, "trang hiện tại"

    for page_num in range(1, total_pages + 1):
        ok = go_to_page(page, page_num)
        if not ok:
            continue  # có thể do đã đang ở đúng trang đó, cứ thử tìm luôn

        result = search_fn(page, phone)
        if result is not None:
            return result, page_num

    return None, None