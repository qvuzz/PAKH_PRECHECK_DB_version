# update_tts/test_clicks.py
# Test riêng LUỒNG BẤM NÚT (không đụng tới Excel), dừng lại sau mỗi bước để bạn tự
# quan sát trên trình duyệt xem đã đúng chưa, rồi mới bấm Enter để qua bước kế tiếp.
#
# Cách dùng: python -m update_tts.test_clicks <so_dien_thoai>
# Ví dụ:     python -m update_tts.test_clicks 0987654321

import sys
from playwright.sync_api import sync_playwright

from . import config
from . import browser_utils
from . import ticket_actions


def pause(msg):
    input(f"\n👉 {msg}\n   (Kiểm tra trên trình duyệt, sau đó nhấn Enter để tiếp tục...)")


def main():
    if len(sys.argv) < 2:
        print("❌ Vui lòng truyền số điện thoại cần test.")
        print("   Cách dùng: python -m update_tts.test_clicks 0987654321")
        sys.exit(1)

    phone = sys.argv[1].strip()
    nguyen_nhan_text = "Khách hàng theo dõi thêm"  # giá trị mẫu cố định để test, không lấy từ Excel
    comment_text = "[TEST] Đây là nội dung test luồng bấm nút, không phải dữ liệu thật."
    action_plan_text = "[TEST] Hướng xử lý mẫu."

    with sync_playwright() as p:
        try:
            browser = browser_utils.connect_to_chrome(p)
            print("✅ Đã kết nối vào Chrome debug thành công!")
        except Exception as ex:
            print(f"❌ Không kết nối được Chrome Debugging Port 9222: {ex}")
            sys.exit(1)

        context = browser_utils.get_context(browser)
        page = browser_utils.find_tts_page(context)

        if page is None:
            print("❌ Không tìm thấy tab TTS đang mở. Vui lòng mở sẵn tab TTS trước khi chạy script này.")
            sys.exit(1)

        print(f"📄 Đang dùng tab TTS: {page.url}")

        # ----------------------------------------------
        # BƯỚC 1: Tìm dòng ticket theo SĐT + bấm nút dropdown-toggle
        # ----------------------------------------------
        pause(f"Chuẩn bị TÌM DÒNG và BẤM NÚT DROPDOWN cho SĐT {phone}.")
        dropdown_container = ticket_actions.find_dropdown_container_by_phone(page, phone)
        if dropdown_container is None:
            print(f"❌ KHÔNG tìm thấy dòng ticket cho SĐT {phone}. Dừng test tại đây.")
            print("   👉 Kiểm tra: SĐT có đang hiển thị trên trang hiện tại không (có thể do phân trang)?")
            browser.close()
            sys.exit(1)
        dropdown_container.locator("button.btn-caretdown").click()
        print("✅ Đã bấm nút dropdown. Kiểm tra xem menu có bung ra đúng vị trí dòng này không.")

        # ----------------------------------------------
        # BƯỚC 2: Bấm "Xác nhận đóng" (giới hạn trong đúng dòng, tránh khớp nhầm menu ẩn của dòng khác)
        # ----------------------------------------------
        pause("Chuẩn bị bấm 'Xác nhận đóng' trong menu vừa bung ra.")
        try:
            page.locator("a:visible", has_text="Xác nhận đóng").click(timeout=3000)
            print("✅ Đã bấm 'Xác nhận đóng'.")
        except Exception as ex:
            print(f"❌ Lỗi khi bấm 'Xác nhận đóng': {ex}")
            browser.close()
            sys.exit(1)

        # ----------------------------------------------
        # BƯỚC 3: Chờ modal xuất hiện (scope theo div.modal.in - modal đang thực sự mở)
        # ----------------------------------------------
        pause("Chuẩn bị chờ MODAL 'Xác nhận đóng phiếu' xuất hiện.")
        modal = ticket_actions.get_open_modal(page)
        if modal is None:
            print("❌ KHÔNG thấy modal xuất hiện. Dừng test tại đây.")
            browser.close()
            sys.exit(1)
        print("✅ Modal đã xuất hiện.")

        # ----------------------------------------------
        # BƯỚC 4: Điền "Nguyên nhân sự cố" (phần dễ sai selector nhất)
        # ----------------------------------------------
        pause(f"Chuẩn bị điền ô 'Nguyên nhân sự cố' với giá trị mẫu: '{nguyen_nhan_text}'.")
        ok = ticket_actions.fill_nguyen_nhan(modal, nguyen_nhan_text, phone)
        if ok:
            print("✅ Đã chọn được gợi ý trong ô 'Nguyên nhân sự cố'. Kiểm tra xem giá trị hiển thị có đúng không.")
        else:
            print("❌ KHÔNG chọn được gợi ý. Đây là chỗ cần sửa lại selector trong ticket_actions.fill_nguyen_nhan().")
            print("   👉 Gửi lại outerHTML của danh sách gợi ý (bấm F12 -> Inspect vào đúng lúc gợi ý đang hiện).")

        # ----------------------------------------------
        # BƯỚC 5: Điền "NỘI DUNG"
        # ----------------------------------------------
        pause("Chuẩn bị điền ô 'NỘI DUNG'.")
        ticket_actions.fill_noi_dung(modal, comment_text, action_plan_text)
        print("✅ Đã điền ô NỘI DUNG. Kiểm tra xem text có hiện đúng trong textarea không.")

        # ----------------------------------------------
        # BƯỚC 6: Bấm "HỦY" (KHÔNG bấm XÁC NHẬN thật trong lúc test)
        # ----------------------------------------------
        pause("Chuẩn bị bấm 'HỦY' để đóng modal lại (KHÔNG ghi dữ liệu test này lên hệ thống thật).")
        ticket_actions.submit_modal(modal, phone, dry_run=True)

        print("\n🎉 Test luồng bấm nút hoàn tất. Xem log phía trên để biết bước nào cần sửa lại (nếu có).")
        browser.close()


if __name__ == "__main__":
    main()