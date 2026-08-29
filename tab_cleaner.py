# tab_cleaner.py
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def close_blank_tabs(driver, keep_urls=None):
    """
    Tự động quét và đóng toàn bộ các tab trống (about:blank, newtab, tab rác không dùng đến).
    Đảm bảo luôn giữ lại ít nhất 1 tab và ưu tiên giữ lại tab TTS / Dashboard.
    """
    if keep_urls is None:
        keep_urls = ["tts.vnpt.vn", "localhost:1234", "127.0.0.1:1234"]

    try:
        handles = list(driver.window_handles)
        if len(handles) <= 1:
            return

        target_main_handle = None

        for handle in handles:
            try:
                driver.switch_to.window(handle)
                current_url = (driver.current_url or "").lower().strip()
                title = (driver.title or "").lower().strip()

                # Kiểm tra tab có phải là tab chính cần giữ không
                is_keep = any(k.lower() in current_url for k in keep_urls)

                if is_keep:
                    if not target_main_handle:
                        target_main_handle = handle
                    continue

                # Nhận diện các loại tab rác / tab trống
                is_blank = (
                    current_url in ["about:blank", "chrome://newtab/", "chrome://new-tab-page/", "data:,", ""] or
                    current_url.startswith("chrome-extension://") or
                    title in ["new tab", "tab mới", "about:blank", ""]
                )

                if is_blank:
                    # Chỉ đóng nếu số tab hiện tại còn nhiều hơn 1
                    if len(driver.window_handles) > 1:
                        driver.close()
            except Exception:
                pass

        # Chuyển tiêu điểm về lại tab chính
        remaining = driver.window_handles
        if target_main_handle and target_main_handle in remaining:
            driver.switch_to.window(target_main_handle)
        elif remaining:
            driver.switch_to.window(remaining[0])

    except Exception as e:
        print(f"⚠️ Lỗi khi dọn dẹp tab trống: {e}")

if __name__ == "__main__":
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    try:
        d = webdriver.Chrome(options=opts)
        close_blank_tabs(d)
        print("✅ Đã dọn dẹp xong các tab trống trên Chrome!")
    except Exception as ex:
        print("Chrome 9222 chưa chạy:", ex)
