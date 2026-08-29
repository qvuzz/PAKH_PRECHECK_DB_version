import sys
import time
from playwright.sync_api import sync_playwright

TARGET_URL = "https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new"
CDP_URL = "http://127.0.0.1:9222"
LOAD_TIMEOUT = 90000  # 90 giây

DATA_SELECTOR = "label.text-success"
FIRST_PAGE_JS = r"""
(function() {
    var ul = document.querySelector('ul.pagination.pull-right');
    if (!ul) return false;
    var links = Array.from(ul.querySelectorAll('a'));
    var target = links.find(function(a){
        var t = (a.textContent || '').trim();
        var m = t.match(/^(\d+)/);
        return m && parseInt(m[1], 10) === 1;
    });
    if (target) { target.click(); return true; }
    return false;
})();
"""


def _close_unwanted_tabs(context):
    """
    Đóng TẤT CẢ tab rác và tab IP 10.* (BTools) trong một Playwright context.
    Sử dụng page.close() trực tiếp — phương pháp DUY NHẤT hoạt động khi Chrome
    không được khởi động với --remote-allow-origins=* (WebSocket CDP bị 403).
    """
    BLANK_URLS = {"about:blank", "chrome://newtab/", "chrome://new-tab-page/", ""}
    # Tab TTS và Dashboard KHÔNG được phép đóng dù URL tạm thời thay đổi
    PROTECTED_HOSTS = ("tts.vnpt.vn", "localhost", "127.0.0.1")
    closed_count = 0

    for page in list(context.pages):
        url = page.url

        # Bỏ qua tab được bảo vệ
        if any(host in url for host in PROTECTED_HOSTS):
            continue

        is_blank = url in BLANK_URLS or url.startswith("chrome://")
        is_ip_10 = url.startswith("http://10.") or url.startswith("https://10.")

        if is_blank or is_ip_10:
            try:
                page.close()
                print(f"Closed tab: {url[:80]}")
                closed_count += 1
            except Exception as ex:
                print(f"Cannot close tab {url[:60]}: {ex}")

    return closed_count


def close_blank_tabs():
    """Đóng tab IP 10.* và tab rác — gọi từ n8n hoặc main.py."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0] if browser.contexts else None
            if context is None:
                print("No browser context found.")
                return
            n = _close_unwanted_tabs(context)
            print(f"Done: closed {n} tab(s).")
    except Exception as e:
        print(f"Error: {e}")


def refresh_tab():
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0] if browser.contexts else None
            if context is None:
                print("ERROR: No browser context found.")
                sys.exit(1)

            # 1. Đóng sạch các tab rác trước khi refresh
            n = _close_unwanted_tabs(context)
            if n:
                print(f"[Pre-refresh] Closed {n} unwanted tab(s).")

            # 2. Tìm tab TTS
            target_page = None
            for page in context.pages:
                if "tts.vnpt.vn" in page.url:
                    target_page = page
                    break
            if not target_page and context.pages:
                target_page = context.pages[0]

            if not target_page:
                print("ERROR: Khong tim thay tab Chrome tts.vnpt.vn")
                sys.exit(1)

            print("1. Bat dau lenh reload...")
            try:
                with target_page.expect_response(lambda r: r.status == 200, timeout=15000):
                    target_page.reload(wait_until="domcontentloaded", timeout=LOAD_TIMEOUT)
            except Exception:
                target_page.reload(wait_until="domcontentloaded", timeout=LOAD_TIMEOUT)

            print("2. Dang cho DOM cu giai phong...")
            target_page.wait_for_timeout(3000)

            if target_page.url != TARGET_URL:
                print("Trang bi vang URL, dang tro lai dung trang...")
                target_page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT)
                target_page.wait_for_timeout(3000)

            print(f"3. Dang cho the du lieu '{DATA_SELECTOR}' moi render...")
            target_page.wait_for_selector(DATA_SELECTOR, state="visible", timeout=LOAD_TIMEOUT)

            print("4. Dang ep ve trang dau tien qua nut pagination...")
            try:
                clicked = target_page.evaluate(FIRST_PAGE_JS)
                if clicked:
                    target_page.wait_for_timeout(1500)
                    print("   -> Da nhan nut page 1 sau refresh.")
                else:
                    print("   -> Khong tim thay nut page 1, giu nguyen state.")
            except Exception as e:
                print(f"   -> Khong the bam page 1: {e}")

            print("5. Cho 5s cho Angular render du lieu hoan tat...")
            target_page.wait_for_timeout(5000)

            print("SUCCESS: Trang da lam moi va render du lieu hoan toan!")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    refresh_tab()