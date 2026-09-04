# crawler_tts.py
import time
from tab_cleaner import close_blank_tabs

def get_vnpt_tickets(driver, service_type=None):
    # Dọn dẹp các tab trống rác trước khi bắt đầu
    close_blank_tabs(driver)

    all_tabs = driver.window_handles
    tts_tab_handle = None

    # 1. Tìm bất kỳ tab nào thuộc domain tts.vnpt.vn
    for tab in all_tabs:
        try:
            driver.switch_to.window(tab)
            current_url = driver.current_url.lower()
            if "tts.vnpt.vn" in current_url:
                tts_tab_handle = tab
                print(f"🎯 Đã tìm thấy tab VNPT TTS: {driver.title} ({current_url})")
                if "xl-xu-ly-su-co" not in current_url and "xu-ly-su-co-new" not in current_url:
                    print("➡️ Tab TTS đang ở trang khác, chuyển ngay sang trang Xử lý sự cố...")
                    driver.get("https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new")
                break
        except Exception:
            pass

    # 2. Nếu chưa có tab TTS nào, tự động mở tab mới
    if not tts_tab_handle:
        print("🌐 Chưa có tab TTS nào, đang tự động mở tab mới tới trang Xử lý sự cố...")
        driver.switch_to.new_window('tab')
        driver.get("https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new")
        tts_tab_handle = driver.current_window_handle

    try:
        driver.set_script_timeout(180)
    except Exception:
        pass

    # 3. Tự động làm mới dữ liệu danh sách phiếu trên TTS vào đầu chu kỳ
    try:
        refreshed = driver.execute_script("""
            var btn = Array.from(document.querySelectorAll('button, input[type="button"], a')).find(function(el) {
                return (el.innerText || el.value || '').trim().toLowerCase() === 'tìm kiếm';
            });
            if (btn) {
                btn.click();
                return true;
            }
            return false;
        """)
        if refreshed:
            print("🔄 Đã bấm nút [Tìm kiếm] trên TTS để nạp mới dữ liệu phiếu cho chu kỳ...")
            time.sleep(1.5)
        else:
            print("🔄 Không thấy nút [Tìm kiếm], tải lại URL trang sự cố TTS...")
            driver.get("https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new")
            time.sleep(2.0)
    except Exception as ex_ref:
        print(f"⚠️ Lưu ý khi làm mới bảng TTS: {ex_ref}")

    # Chờ bảng #myTable xuất hiện động (tối đa 8s, xong ngay khi bảng xuất hiện)
    for _ in range(25):
        has_table = driver.execute_script("return !!(document.getElementById('myTable') || document.querySelector('table[class*=\"dataTable\"]'));")
        if has_table:
            break
        time.sleep(0.3)

    print("⚡ Đang kích hoạt click tự động bung toàn bộ chữ ẩn...")
    click_js = """
    var readMoreButtons = document.querySelectorAll('#myTable tbody tr td a, #myTable tbody tr td span');
    readMoreButtons.forEach(function(btn) {
        var text = (btn.innerText || btn.textContent || "").trim().toLowerCase();
        if (text.includes('xem thêm') || text.includes('xemthem')) btn.click();
    });
    """
    driver.execute_script(click_js)
    time.sleep(0.6)

    # 🎯 JAVASCRIPT ĐỈNH CAO: Tự động cào bảng và mở modal Lịch sử xử lý để lấy chính xác Thời điểm sự cố
    vnpt_js_script = """
    var callback = arguments[arguments.length - 1];

    async function crawlTableWithAccurateIncidentTime() {
        var targetTable = document.getElementById('myTable') || document.querySelector('table[class*="dataTable"]');
        if (!targetTable) return callback([]);

        // 1. DÒ TÌM CHÍNH XÁC VỊ TRÍ CÁC CỘT TỪ HEADER
        var title_column_idx = -1;
        var phone_column_idx = -1;
        var content_column_idx = -1;
        var created_time_column_idx = -1;
        var headers = targetTable.querySelectorAll('thead th');
        headers.forEach(function(th, idx) {
            var thText = (th.innerText || th.textContent || "").trim().toLowerCase();
            if (thText.includes('tiêu đề') || thText.includes('tieu de')) {
                title_column_idx = idx;
            }
            if (thText.includes('điện thoại') || thText.includes('dien thoai') || thText.includes('sđt') || thText.includes('sdt')) {
                phone_column_idx = idx;
            }
            if (thText.includes('nội dung') || thText.includes('noidung')) {
                content_column_idx = idx;
            }
            if (thText.includes('ngày yêu cầu') || thText.includes('ngay yeu cau') || thText.includes('thời gian') || thText.includes('ngay tao')) {
                created_time_column_idx = idx;
            }
        });

        if (title_column_idx === -1) title_column_idx = 2;
        if (phone_column_idx === -1) phone_column_idx = 3;
        if (content_column_idx === -1) content_column_idx = 4;
        if (created_time_column_idx === -1) created_time_column_idx = 5;

        var data_rows = [];
        var rows = targetTable.querySelectorAll('tbody tr');

        function closeModalSafely() {
            var closeButtons = document.querySelectorAll('.modal.in .close, .modal.in .btn-close, .modal.in button, xl-xu-ly-lich-su .close, xl-xu-ly-lich-su .btn-close, xl-xu-ly-lich-su button');
            closeButtons.forEach(function(b) {
                var t = (b.innerText || b.textContent || "").trim();
                if (t === '×' || t === 'Đóng' || t === 'Thoát' || b.classList.contains('close') || b.classList.contains('btn-close')) {
                    try { b.click(); } catch(e) {}
                }
            });
            if (window.jQuery) {
                try {
                    window.jQuery('.modal.in').modal('hide');
                    window.jQuery('.modal-backdrop').remove();
                    window.jQuery('body').removeClass('modal-open');
                } catch(e) {}
            }
            document.querySelectorAll('.modal.in').forEach(function(m) {
                m.classList.remove('in');
                m.style.display = 'none';
            });
            document.querySelectorAll('.modal-backdrop').forEach(function(el) { el.remove(); });
            document.body.classList.remove('modal-open');
        }

        closeModalSafely();
        await new Promise(r => setTimeout(r, 300));

        var rows = Array.from(targetTable.querySelectorAll('tbody > tr')).filter(function(r) {
            return r.querySelectorAll('td').length >= 4;
        });

        for (var i = 0; i < rows.length; i++) {
            var row = rows[i];
            var cells = row.querySelectorAll('td');
            if (cells.length < 3) continue;

            var phone = "";
            var title = "";
            var content = ""; 
            var grid_date = "";

            // Lấy số điện thoại từ cột phone_column_idx hoặc tìm ô có định dạng SĐT
            if (cells.length > phone_column_idx) {
                var rawPhone = (cells[phone_column_idx].innerText || cells[phone_column_idx].textContent || "").trim().replace(/\\s+/g, '');
                if (/^\\d{9,11}$/.test(rawPhone)) {
                    phone = rawPhone;
                }
            }
            if (!phone) {
                cells.forEach(function(cell, idx) {
                    var cellText = (cell.innerText || cell.textContent || "").trim().replace(/\\s+/g, '');
                    if (/^\\d{9,11}$/.test(cellText) && !phone) {
                        phone = cellText;
                    }
                });
            }

            // Lấy tiêu đề dịch vụ thực tế từ cột title_column_idx
            if (cells.length > title_column_idx) {
                title = (cells[title_column_idx].innerText || cells[title_column_idx].textContent || "").trim();
            }

            if (cells.length > content_column_idx) {
                var contentCell = cells[content_column_idx];
                content = (contentCell.textContent || contentCell.innerText || "").trim();
                content = content.replace(/\\s*👁\\s*Xem thêm/gi, "").replace(/\\s*Xem thêm/gi, "");
                content = content.replace(/\\n{2,}/g, ' ').replace(/\\s+/g, ' ').trim();
            }

            if (created_time_column_idx !== -1 && cells.length > created_time_column_idx) {
                grid_date = (cells[created_time_column_idx].innerText || cells[created_time_column_idx].textContent || "").trim();
            }

            if (!phone) continue;

            // 🎯 MỞ MODAL LỊCH SỬ XỬ LÝ ĐỂ LẤY CHÍNH XÁC NGÀY TIẾP NHẬN & THỜI ĐIỂM SỰ CỐ BƯỚC 1.1
            var incident_time = "";
            var reception_time = "";
            var historyLink = Array.from(row.querySelectorAll('a')).find(function(el){
                var t = (el.textContent || el.innerText || '').toLowerCase().replace(/\\s+/g, ' ');
                return t.includes('lịch sử xử lý') && t.includes('yêu cầu');
            });

            if (historyLink) {
                try {
                    closeModalSafely();
                    await new Promise(r => setTimeout(r, 120));
                    historyLink.scrollIntoView({block: 'center'});
                    await new Promise(r => setTimeout(r, 100));
                    historyLink.click();
                    for (var w = 0; w < 35; w++) {
                        await new Promise(r => setTimeout(r, 100));
                        var modal = document.querySelector('.modal.in xl-xu-ly-lich-su') || document.querySelector('xl-xu-ly-lich-su');
                        if (modal && modal.innerText && modal.innerText.length > 50) {
                            var text = modal.innerText;
                            var mInc = text.match(/THỜI\\s*ĐIỂM\\s*XẢY\\s*RA\\s*SỰ\\s*CỐ[:\\s]*([\\d]{1,2}[/-][\\d]{1,2}[/-][\\d]{2,4}(?:\\s+[\\d]{1,2}:[\\d]{1,2}(?::[\\d]{1,2})?)?)/i);
                            if (mInc) incident_time = mInc[1].trim();
                            var mStep1 = text.match(/Bước\\s*1(?:\\.1)?[\\s\\S]*?(\\d{1,2}\\/\\d{1,2}\\/\\d{4}\\s+\\d{1,2}:\\d{1,2})/i);
                            if (mStep1) reception_time = mStep1[1].trim();
                            break;
                        }
                    }
                    closeModalSafely();
                    await new Promise(r => setTimeout(r, 150));
                } catch(e) {
                    closeModalSafely();
                }
            }

            var final_incident_time = incident_time || reception_time || grid_date;
            var final_created_time = reception_time || incident_time || grid_date;

            data_rows.push({ 
                "title": title, 
                "phone": phone, 
                "content": content,
                "created_time": final_created_time,
                "incident_time": final_incident_time
            });
        }

        // Đảm bảo đóng sạch sẽ toàn bộ modal trước khi hoàn tất
        closeModalSafely();
        callback(data_rows);
    }

    crawlTableWithAccurateIncidentTime();
    """
    # 🎯 JS: LẤY DANH SÁCH SỐ TRANG THỰC TẾ TRÊN TẤT CẢ CÁC THANH PAGINATION ĐANG HIỂN THỊ
    get_page_numbers_js = """
    var allUls = Array.from(document.querySelectorAll('ul.pagination, .pagination, [class*="pagination"]')).filter(function(el) {
        return el.offsetParent !== null;
    });
    var maxNums = [];
    allUls.forEach(function(ul) {
        var links = Array.from(ul.querySelectorAll('a, button, li'));
        var nums = [];
        links.forEach(function(a) {
            var t = (a.textContent || '').trim();
            var m = t.match(/^(\\d+)/);
            if (m) {
                var n = parseInt(m[1], 10);
                if (!nums.includes(n)) nums.push(n);
            }
        });
        if (nums.length > maxNums.length) {
            maxNums = nums;
        }
    });
    return maxNums;
    """

    click_page_number_js = """
    var targetPage = arguments[0];
    var allUls = Array.from(document.querySelectorAll('ul.pagination, .pagination, [class*="pagination"]')).filter(function(el) {
        return el.offsetParent !== null;
    });
    for (var i = 0; i < allUls.length; i++) {
        var ul = allUls[i];
        var links = Array.from(ul.querySelectorAll('li, a, button'));
        var target = links.find(function(a) {
            var t = (a.textContent || '').trim();
            var m = t.match(/^(\\d+)/);
            return m && parseInt(m[1], 10) === targetPage;
        });
        if (target) {
            var clickEl = target.querySelector('a') || target;
            clickEl.click();
            return true;
        }
    }
    return false;
    """

    # JS lấy "dấu vân tay" của dòng đầu tiên trong bảng, dùng để phát hiện khi nào Angular đã đổ dữ liệu trang mới xong
    fingerprint_js = """
    var firstRow = document.querySelector('#myTable tbody tr');
    return firstRow ? (firstRow.innerText || "").trim() : "";
    """

    all_rows = []

    # 🔒 RESTORE PAGE 1: Luôn đưa về trang 1 trước khi bắt đầu cào
    page_numbers = driver.execute_script(get_page_numbers_js)
    if page_numbers and 1 in page_numbers:
        old_fingerprint = driver.execute_script(fingerprint_js)
        clicked_first = driver.execute_script(click_page_number_js, 1)
        if clicked_first:
            waited = 0.0
            while waited < 5.0:
                time.sleep(0.3)
                waited += 0.3
                new_fingerprint = driver.execute_script(fingerprint_js)
                if new_fingerprint != old_fingerprint:
                    break
            print(f"   ↳ Đã reset về trang 1 thành công.")

    # Dò tổng số trang thực tế đang hiển thị
    page_numbers = driver.execute_script(get_page_numbers_js)
    total_pages = max(page_numbers) if page_numbers else 1
    print(f"📄 Phát hiện tổng cộng {total_pages} trang cần quét (Các trang: {page_numbers}).")

    for page_num in range(1, total_pages + 1):
        print(f"\n📄 Đang quét dữ liệu trang {page_num}/{total_pages}...")

        if page_num > 1:
            old_fingerprint = driver.execute_script(fingerprint_js)
            clicked = driver.execute_script(click_page_number_js, page_num)
            if not clicked:
                print(f"⚠️ Không tìm thấy nút số trang {page_num}, dừng lại.")
                break

            # Chờ dữ liệu bảng thực sự đổi sau khi bấm chuyển trang
            changed = False
            waited = 0.0
            while waited < 20.0:
                time.sleep(0.3)
                waited += 0.3
                new_fingerprint = driver.execute_script(fingerprint_js)
                if new_fingerprint != old_fingerprint:
                    changed = True
                    break
            if changed:
                print(f"   ↳ Dữ liệu trang {page_num} đã tải xong sau {waited:.1f}s.")
            else:
                print(f"⚠️ Đã chờ {waited:.1f}s nhưng bảng không đổi dữ liệu sau khi bấm trang {page_num}.")

        # Bung "Xem thêm" trước khi cào (áp dụng cho từng trang)
        driver.execute_script(click_js)
        time.sleep(1.0)

        page_data = driver.execute_async_script(vnpt_js_script)
        if page_data:
            all_rows.extend(page_data)
            print(f"   ↳ Thu được {len(page_data)} dòng từ trang {page_num}.")

    # Lọc trùng ngay tại đây theo phone (phòng trường hợp trùng số giữa các trang)
    seen = set()
    dedup_rows = []
    for row in all_rows:
        if row["phone"] not in seen:
            seen.add(row["phone"])
            dedup_rows.append(row)

    if service_type == "data":
        dedup_rows = [r for r in dedup_rows if "mobile internet" in str(r.get("title", "")).lower() and "gói cước" not in str(r.get("title", "")).lower()]
    elif service_type == "voice_sms":
        dedup_rows = [r for r in dedup_rows if not ("mobile internet" in str(r.get("title", "")).lower() and "gói cước" not in str(r.get("title", "")).lower())]

    print(f"📊 Tổng cộng {len(dedup_rows)} thuê bao sau khi lọc (service_type={service_type}).")
    return dedup_rows, tts_tab_handle