# update_tts/ticket_actions.py
# Luồng thao tác cho từng ticket: bấm dropdown -> "Xác nhận đóng" -> điền form -> Xác nhận/Hủy
#
# ⚠️ LƯU Ý QUAN TRỌNG VỀ CẤU TRÚC TRANG TTS:
# Trang này load sẵn RẤT NHIỀU bản sao ẩn của cùng 1 cấu trúc (dropdown menu, modal...) cho
# từng dòng ticket, chỉ đang ẩn bằng CSS (không phải bị xóa khỏi DOM). Vì vậy KHÔNG được tìm
# phần tử theo selector "trần" trên toàn trang (dễ khớp nhầm 10-30 bản ẩn), mà luôn phải:
#   - Với dropdown: dùng ":visible" (chỉ đúng 1 dropdown đang mở tại 1 thời điểm)
#   - Với modal: scope vào đúng "div.modal.in" (class Bootstrap gắn cho modal đang hiển thị)

from . import config
from . import pagination

MODAL_OPEN_SELECTOR = "div.modal.in"

# Nhãn đánh dấu phiếu đã bị mở lại (label.bg-red, ví dụ: "Phiếu mở lại").
# Các phiếu có nhãn này KHÔNG được tự động đóng - cần kỹ thuật kiểm tra thủ công.
REOPENED_LABEL_TEXT = "Phiếu mở lại"


def normalize_phone_for_search(phone):
    """
    Excel lưu số theo chuẩn phone_84 (84xxxxxxxxx), nhưng bảng TTS hiển thị KHÔNG có tiền tố 84.
    Bỏ tiền tố "84" để lấy phần số lõi, dùng để so khớp dạng "chứa chuỗi con" - vẫn tìm đúng
    dù TTS hiển thị có/không có số 0 ở đầu.
    """
    p = "".join(filter(str.isdigit, str(phone or "").strip()))
    if p.startswith("84") and len(p) >= 11:
        return p[2:]
    if p.startswith("0") and len(p) >= 10:
        return p[1:]
    return p


def find_row_by_phone(page, phone):
    """
    Tìm đúng <tr> chứa số điện thoại này trong #myTable (chỉ trang đang hiển thị hiện tại).
    Trả về locator của <tr>, hoặc None nếu không tìm thấy trên trang này.
    """
    search_phone = normalize_phone_for_search(phone)
    row_locator = page.locator("#myTable tbody tr", has_text=search_phone)
    count = row_locator.count()
    if count == 0:
        return None
    if count > 1:
        print(f"⚠️ Tìm thấy {count} dòng khớp SĐT {phone}, dùng dòng đầu tiên. Cần kiểm tra lại nếu bị trùng.")
    return row_locator.first


def is_reopened_ticket(row):
    """
    True nếu dòng ticket có gắn nhãn 'Phiếu mở lại' (label.bg-red).
    <label class="label bg-red"><i class="fa fa-flag-o"></i> Phiếu mở lại</label>
    """
    return row.locator("label.bg-red", has_text=REOPENED_LABEL_TEXT).count() > 0


def is_reopened_ticket_by_phone(page, phone):
    """
    Quét qua các trang để tìm đúng dòng ticket của SĐT này, kiểm tra có bị đánh dấu
    'Phiếu mở lại' hay không.
    Nếu không tìm thấy dòng nào ở bất kỳ trang nào, trả về False (để luồng mở modal phía sau
    tự báo lỗi "không tìm thấy ticket", tránh in trùng 2 thông báo cho cùng 1 nguyên nhân).
    """
    row, _ = pagination.find_container_across_pages(page, find_row_by_phone, phone)
    if row is None:
        return False
    return is_reopened_ticket(row)


def find_dropdown_container_by_phone(page, phone):
    """
    Tìm đúng <tr> chứa số điện thoại này trong #myTable, trả về khối div.dropdown của dòng đó.
    ⚠️ CHƯA xử lý việc SĐT nằm ở trang khác (phân trang) - chỉ tìm trong trang đang hiển thị.
    """
    row = find_row_by_phone(page, phone)
    if row is None:
        return None
    return row.locator("div.dropdown")


def get_open_modal(page, timeout=5000):
    """Trả về locator của đúng modal đang mở (div.modal.in), hoặc None nếu không có/timeout."""
    modal = page.locator(MODAL_OPEN_SELECTOR)
    try:
        modal.wait_for(state="visible", timeout=timeout)
        return modal
    except Exception:
        return None


def force_close_any_open_modal(page, timeout=1000):
    """
    Nếu còn modal nào đang mở dở (do lần xử lý trước bị lỗi/treo giữa chừng), đóng nó lại
    bằng phím Escape trước khi tiếp tục sang SĐT mới. Tránh việc modal kẹt cản trở toàn bộ
    các thao tác tìm/click SĐT tiếp theo.
    """
    modal = page.locator(MODAL_OPEN_SELECTOR)
    try:
        modal.wait_for(state="visible", timeout=timeout)
    except Exception:
        return  # không có modal nào đang mở dở, không cần làm gì

    print("⚠️ Phát hiện modal còn đang mở dở từ lượt xử lý trước, đang tự động đóng lại...")
    try:
        page.keyboard.press("Escape")
        modal.wait_for(state="hidden", timeout=3000)
        print("✅ Đã đóng modal kẹt lại thành công.")
    except Exception:
        print("⚠️ Không tự đóng được modal cũ bằng Escape - có thể cần kiểm tra/đóng thủ công trên trình duyệt.")


def open_close_ticket_modal(page, phone, step_delay_ms=0):
    """
    Bấm dropdown -> 'Xác nhận đóng' -> chờ modal mở.
    Tự động quét qua các trang khác nếu SĐT không nằm ở trang đang hiển thị hiện tại.
    Trả về locator của modal đang mở nếu thành công, None nếu thất bại.
    step_delay_ms: nếu > 0, tạm dừng sau mỗi bước để quan sát bằng mắt.
    """
    dropdown_container, found_on_page = pagination.find_container_across_pages(
        page, find_dropdown_container_by_phone, phone
    )
    if dropdown_container is None:
        print(f"⚠️ Không tìm thấy dòng ticket cho SĐT {phone} ở bất kỳ trang nào.")
        return None
    if found_on_page != "trang hiện tại":
        print(f"📄 Đã tìm thấy SĐT {phone} ở trang {found_on_page}.")

    dropdown_container.locator("button.btn-caretdown").click()
    print(f"   ↳ [1/4] Đã bấm nút dropdown cho SĐT {phone}.")
    page.wait_for_timeout(max(300, step_delay_ms))

    try:
        # Chỉ đúng 1 menu "visible" tại 1 thời điểm (menu vừa bung ra của đúng dòng này)
        page.locator("a:visible", has_text="Xác nhận đóng").click(timeout=3000)
        print(f"   ↳ [2/4] Đã bấm 'Xác nhận đóng'.")
    except Exception as ex:
        print(f"⚠️ Không bấm được 'Xác nhận đóng' cho SĐT {phone}: {ex}")
        return None
    page.wait_for_timeout(step_delay_ms)

    modal = get_open_modal(page)
    if modal is None:
        print(f"⚠️ Modal không xuất hiện cho SĐT {phone}.")
        return None
    print(f"   ↳ [3/4] Modal đã mở.")
    page.wait_for_timeout(step_delay_ms)
    return modal


def fill_nguyen_nhan(modal, nguyen_nhan_text, phone, step_delay_ms=0):
    """
    Điền ô 'Nguyên nhân sự cố' (input[name='dongNguyenNhanSuCo'], ngx-bootstrap Typeahead)
    và chọn đúng gợi ý khớp text trong danh sách xổ xuống.
    Scope theo `modal` (locator của modal đang mở) để tránh khớp nhầm các bản ẩn khác.

    ⚠️ VẤN ĐỀ TYPEAHEAD:
    Gõ toàn bộ text dài (>40 ký tự) khiến ngx-bootstrap Typeahead lọc không kịp và đóng
    dropdown trước khi script click được. Giải pháp: chỉ gõ ~15 ký tự đầu để trigger
    dropdown, sau đó tìm và click item khớp full text.
    """
    nguyen_nhan_input = modal.locator("input[name='dongNguyenNhanSuCo']")
    nguyen_nhan_input.click()
    nguyen_nhan_input.fill("")

    # Chỉ gõ prefix ngắn (~15 ký tự) để trigger typeahead mà không làm dropdown tự đóng
    search_prefix = nguyen_nhan_text[:15]
    nguyen_nhan_input.type(search_prefix, delay=50)
    modal.page.wait_for_timeout(800)   # Chờ ngx-bootstrap render danh sách gợi ý

    try:
        # ngx-bootstrap TypeaheadContainerComponent render <ul class="dropdown-menu"><li><a>...</a></li></ul>
        # Handler click gắn ở từng <li>/<a>, không phải ở cả khối .dropdown-menu -> phải nhắm đúng item.
        suggestion = modal.page.locator(
            ".dropdown-menu:visible li, .typeahead-container li, typeahead-container li, [role='listbox'] li, .dropdown-menu:visible a, [role='option']",
            has_text=nguyen_nhan_text
        ).first
        suggestion.wait_for(state="visible", timeout=4000)
        suggestion.click(timeout=3000)
        print(f"   ↳ [4/6] Đã chọn nguyên nhân: '{nguyen_nhan_text}'.")
        modal.page.wait_for_timeout(step_delay_ms)
        return True
    except Exception as ex:
        print(f"⚠️ Không chọn được gợi ý '{nguyen_nhan_text}' cho SĐT {phone}: {ex}")
        print("   👉 Kiểm tra lại: text trong config.STATUS_TO_NGUYEN_NHAN có khớp CHÍNH XÁC (kể cả dấu)")
        print("      với text hiển thị trong danh sách gợi ý thật trên TTS không.")
        return False


def fill_noi_dung(modal, comment_text, action_plan_text, step_delay_ms=0):
    """
    Điền ô 'NỘI DUNG' (Angular ng-model textarea).

    ⚠️ VẤN ĐỀ THỰC TẾ:
    Playwright .fill() chỉ dispatch InputEvent — nhưng AngularJS ng-model cần
    $setViewValue() + $apply() mới cập nhật scope và gỡ ng-disabled trên nút XÁC NHẬN.
    Giải pháp: sau .fill(), gọi JS để buộc Angular digest cycle nhận giá trị mới.
    """
    full_text = f"{comment_text}\n\nHướng xử lý: {action_plan_text}"

    noi_dung_textarea = modal.locator("textarea[name='NoiDung']")
    noi_dung_textarea.click()
    noi_dung_textarea.fill(full_text)

    # Buộc AngularJS nhận giá trị mới vào ng-model → form hợp lệ → nút XÁC NHẬN enabled
    noi_dung_textarea.evaluate("""
        (el) => {
            var ng = window.angular;
            if (!ng) return;
            try {
                var ngModel = ng.element(el).controller('ngModel');
                if (ngModel) {
                    ngModel.$setViewValue(el.value);
                    ngModel.$commitViewValue();
                }
                var scope = ng.element(el).scope();
                if (scope && !scope.$$phase) scope.$apply();
            } catch (e) {}
        }
    """)

    print(f"   ↳ [5/6] Đã điền NỘI DUNG (cột 6 + cột 7).")
    modal.page.wait_for_timeout(max(600, step_delay_ms))


def submit_modal(modal, phone, dry_run=False):
    """
    dry_run=True -> bấm 'HỦY' thay vì 'XÁC NHẬN', để test luồng mà KHÔNG ghi dữ liệu thật lên TTS.
    dry_run=False -> bấm 'XÁC NHẬN' thật.

    ⚠️ Lưu ý: nút XÁC NHẬN có thể bị ng-disabled nếu Angular chưa digest xong sau khi điền
    NỘI DUNG. Hàm này chờ tối đa 3 giây cho nút enabled trước khi fallback sang force=True.
    """
    button_text = "HỦY" if dry_run else "XÁC NHẬN"
    btn = modal.get_by_text(button_text, exact=True)
    try:
        # Chờ nút xuất hiện + enabled (Angular gỡ ng-disabled sau $apply)
        btn.wait_for(state="visible", timeout=3000)
        try:
            btn.click(timeout=4000)
        except Exception:
            # Fallback: force click nếu nút vẫn còn ng-disabled (bypass actionability check)
            print(f"   ↳ Nút '{button_text}' có thể vẫn disabled, thử force click...")
            btn.click(timeout=4000, force=True)
        print(f"   ↳ [6/6] Đã bấm '{button_text}'.")
    except Exception as ex:
        print(f"⚠️ Không bấm được nút '{button_text}' cho SĐT {phone}: {ex}")
        return False

    try:
        # Chờ ĐÚNG modal này hết hiển thị (không dùng "detached" vì luôn còn nhiều bản ẩn
        # khác cùng khớp selector textarea[name='NoiDung'], khiến "detached" không bao giờ đúng)
        modal.wait_for(state="hidden", timeout=8000)
        if dry_run:
            print(f"🧪 [DRY-RUN] Đã điền thử form cho SĐT {phone}, sau đó bấm HỦY (không ghi dữ liệu thật).")
        else:
            print(f"✅ Đã cập nhật thành công SĐT {phone}")
        return True
    except Exception:
        print(f"⚠️ Modal chưa đóng sau khi bấm '{button_text}' cho SĐT {phone}, cần kiểm tra thủ công.")
        return False


def close_ticket(page, phone, status, comment_text, action_plan_text, dry_run=False, step_delay_ms=0):
    """
    Luồng đầy đủ cho 1 ticket.
    Trả về True/False (thành công/thất bại), hoặc None nếu bị bỏ qua do chưa có mapping.
    """
    nguyen_nhan_text = config.STATUS_TO_NGUYEN_NHAN.get(status)
    if not nguyen_nhan_text:
        print(f"⏭️  BỎ QUA SĐT {phone}: trạng thái '{status}' chưa có mapping trong STATUS_TO_NGUYEN_NHAN.")
        return None

    # Dọn dẹp modal kẹt lại từ lượt xử lý trước (nếu có)
    force_close_any_open_modal(page)

    # ⚡ QUÉT 1 LẦN DUY NHẤT: tìm dòng + kiểm tra 'Phiếu mở lại' trong cùng bước
    # (Trước: is_reopened_ticket_by_phone + open_close_ticket_modal gọi riêng -> 2x scan tất cả trang)
    row, found_on_page = pagination.find_container_across_pages(page, find_row_by_phone, phone)

    if row is None:
        print(f"⚠️ Không tìm thấy dòng ticket cho SĐT {phone} ở bất kỳ trang nào.")
        return False

    if found_on_page != "trang hiện tại":
        print(f"📄 Đã tìm thấy SĐT {phone} ở trang {found_on_page}.")

    if is_reopened_ticket(row):
        print(f"🚩 BỎ QUA SĐT {phone}: phiếu đang gắn nhãn 'Phiếu mở lại' - để kỹ thuật kiểm tra thủ công, không tự động đóng.")
        return None

    try:
        # Dùng luôn locator dòng đã tìm, mở dropdown từ dòng đó (không scan lại)
        dropdown_container = row.locator("div.dropdown")
        dropdown_container.locator("button.btn-caretdown").click()
        print(f"   ↳ [1/4] Đã bấm nút dropdown cho SĐT {phone}.")
        page.wait_for_timeout(max(300, step_delay_ms))

        try:
            page.locator("a:visible", has_text="Xác nhận đóng").click(timeout=3000)
            print(f"   ↳ [2/4] Đã bấm 'Xác nhận đóng'.")
        except Exception as ex:
            print(f"⚠️ Không bấm được 'Xác nhận đóng' cho SĐT {phone}: {ex}")
            return False
        page.wait_for_timeout(step_delay_ms)

        modal = get_open_modal(page)
        if modal is None:
            print(f"⚠️ Modal không xuất hiện cho SĐT {phone}.")
            return False
        print(f"   ↳ [3/4] Modal đã mở.")
        page.wait_for_timeout(step_delay_ms)

        if not fill_nguyen_nhan(modal, nguyen_nhan_text, phone, step_delay_ms=step_delay_ms):
            force_close_any_open_modal(page)
            return False

        fill_noi_dung(modal, comment_text, action_plan_text, step_delay_ms=step_delay_ms)

        return submit_modal(modal, phone, dry_run=dry_run)

    except Exception as ex:
        print(f"❌ Lỗi không mong muốn khi xử lý SĐT {phone}: {ex}")
        force_close_any_open_modal(page)
        return False