// static/js/modules/ai_teach.js
// Module chỉnh sửa tóm tắt & huấn luyện AI (Few-shot learning)

// ==============================================================================
// TÍNH NĂNG CHỈNH SỬA TÓM TẮT & HUẤN LUYỆN AI (FEW-SHOT LEARNING)
// ==============================================================================
function openAiTeachModal(event, phone, incidentTime, ticketId) {
    if (event && event.stopPropagation) {
        event.stopPropagation();
    }
    const modal = document.getElementById('modalAiTeach');
    if (!modal) {
        console.error('Không tìm thấy element modalAiTeach!');
        return;
    }

    let t = null;
    if (typeof cachedTickets !== 'undefined' && Array.isArray(cachedTickets)) {
        t = cachedTickets.find(x => (ticketId && x.ticket_id == ticketId) || (x.phone == phone && (!incidentTime || x.incident_time == incidentTime)));
    }
    if (!t && typeof ticketsData !== 'undefined' && Array.isArray(ticketsData)) {
        t = ticketsData.find(x => (ticketId && x.ticket_id == ticketId) || (x.phone == phone && (!incidentTime || x.incident_time == incidentTime)));
    }

    const rawContent = (t && t.ticket_content) ? t.ticket_content : '';
    const packageTitle = (t && t.package_title) ? t.package_title : '';
    let summary = (t && t.ai_summary) ? t.ai_summary : '';

    if (!summary || summary === 'null' || summary.trim() === '') {
        summary = `1. Gói cước sử dụng: ${packageTitle || 'Không đề cập'}\n2. Tình trạng truy cập: Không vào được mạng (toàn bộ)\n3. Tình trạng dung lượng: Không đề cập\n4. Thiết bị sử dụng: Không đề cập\n5. Khu vực xảy ra lỗi: Không đề cập\n6. Tóm tắt thông tin khác: Không có thông tin hành động phụ.`;
    }

    const elTicketId = document.getElementById('aiTeachTicketId');
    const elPhone = document.getElementById('aiTeachPhone');
    const elIncidentTime = document.getElementById('aiTeachIncidentTime');
    const elPackageTitle = document.getElementById('aiTeachPackageTitle');
    if (elTicketId) elTicketId.value = ticketId || '';
    if (elPhone) elPhone.value = phone || '';
    if (elIncidentTime) elIncidentTime.value = incidentTime || '';
    if (elPackageTitle) elPackageTitle.value = packageTitle || '';

    const elPhoneDisplay = document.getElementById('aiTeachPhoneDisplay');
    const elPackageDisplay = document.getElementById('aiTeachPackageDisplay');
    const elRawContent = document.getElementById('aiTeachRawContent');
    if (elPhoneDisplay) elPhoneDisplay.innerText = phone || '--';
    if (elPackageDisplay) elPackageDisplay.innerText = packageTitle || '--';
    if (elRawContent) elRawContent.innerText = rawContent || '(Không có nội dung phản ánh gốc)';

    // Điền dữ liệu vào form chuẩn hóa 6 mục
    parseAiTeachSummaryToForm(summary.replace(/\[?AI\]?[:\-\s]*/gi, '').trim(), packageTitle);

    // Mặc định luôn hiện chế độ Form có Dropdown
    const formBox = document.getElementById('aiTeachFormContainer');
    const textBox = document.getElementById('aiTeachTextContainer');
    const btnToggle = document.getElementById('btnToggleAiTeachView');
    if (formBox) formBox.style.display = 'block';
    if (textBox) textBox.style.display = 'none';
    if (btnToggle) btnToggle.innerText = 'Xem dạng văn bản 6 dòng';

    updateAiTeachPreview();
    modal.style.display = 'flex';
}

function parseAiTeachSummaryToForm(summaryText, packageTitle) {
    let pkg = packageTitle || 'Không đề cập';
    let access = 'Không vào được mạng (toàn bộ)';
    let appDetail = '';
    let data = 'Không đề cập';
    let device = 'Không đề cập';
    let area = 'Không đề cập';
    let areaDetail = '';
    let other = 'Không có thông tin hành động phụ.';

    const lines = (summaryText || '').split('\n');
    for (const line of lines) {
        const trimmed = line.trim();
        const m1 = trimmed.match(/^1\.\s*gói cước(?: sử dụng)?\s*:\s*(.+)$/i);
        if (m1) pkg = m1[1].trim();

        const m2 = trimmed.match(/^2\.\s*tình trạng truy cập\s*:\s*(.+)$/i);
        if (m2) {
            const rawAccess = m2[1].trim();
            const lowerAccess = rawAccess.toLowerCase();
            if (lowerAccess.includes('lỗi ứng dụng') || lowerAccess.includes('ứng dụng cụ thể')) {
                access = 'Lỗi ứng dụng cụ thể';
                const subMatch = rawAccess.match(/(?:lỗi ứng dụng(?:\s+cụ thể)?\s*:\s*)(.+)/i);
                appDetail = subMatch ? subMatch[1].trim() : rawAccess;
            } else if (lowerAccess.includes('chậm') || lowerAccess.includes('chập chờn')) {
                access = 'Truy cập chậm, chập chờn';
            } else if (lowerAccess.includes('mau hết') || lowerAccess.includes('hao data') || lowerAccess.includes('nhanh hết')) {
                access = 'Phản ánh mau hết dung lượng / Hao data nhanh';
            } else if (lowerAccess.includes('không vào') || lowerAccess.includes('không được') || lowerAccess.includes('mất kết nối')) {
                access = 'Không vào được mạng (toàn bộ)';
            } else if (lowerAccess.includes('không đề cập')) {
                access = 'Không đề cập';
            } else {
                access = 'Không vào được mạng (toàn bộ)';
            }
        }

        const m3 = trimmed.match(/^3\.\s*tình trạng dung lượng\s*:\s*(.+)$/i);
        if (m3) data = m3[1].trim();

        const m4 = trimmed.match(/^4\.\s*thiết bị(?: sử dụng)?\s*:\s*(.+)$/i);
        if (m4) device = m4[1].trim();

        const m5 = trimmed.match(/^5\.\s*khu vực(?: xảy ra lỗi)?\s*:\s*(.+)$/i);
        if (m5) {
            const rawArea = m5[1].trim();
            const lowerArea = rawArea.toLowerCase();
            if (lowerArea.includes('đi nhiều nơi') || lowerArea.includes('di chuyển') || lowerArea.includes('nhiều khu vực')) {
                area = 'Đi nhiều nơi bị lỗi';
                areaDetail = '';
            } else if (lowerArea.startsWith('chỉ ở 1 khu vực') || lowerArea.startsWith('tại 1 khu vực') || lowerArea.startsWith('ở 1 khu vực') || lowerArea.includes('1 khu vực')) {
                area = 'Chỉ ở 1 khu vực';
                const subLoc = rawArea.match(/\(([^)]+)\)/);
                areaDetail = subLoc ? subLoc[1].trim() : '';
            } else if (lowerArea.includes('không đề cập')) {
                area = 'Không đề cập';
                areaDetail = '';
            } else {
                area = 'Chỉ ở 1 khu vực';
                areaDetail = rawArea;
            }
        }

        const m6 = trimmed.match(/^6\.\s*tóm tắt thông tin khác\s*:\s*(.+)$/i);
        if (m6) other = m6[1].trim();
    }

    const elPkg = document.getElementById('aiTeachPkg');
    if (elPkg) elPkg.value = pkg;

    const elAccess = document.getElementById('aiTeachAccessStatus');
    if (elAccess) elAccess.value = access;
    const elAppDetail = document.getElementById('aiTeachAppDetail');
    if (elAppDetail) elAppDetail.value = appDetail;
    handleAiTeachAccessChange();

    const elData = document.getElementById('aiTeachDataStatus');
    if (elData) elData.value = data;

    const elDevice = document.getElementById('aiTeachDevice');
    if (elDevice) elDevice.value = device;

    const elArea = document.getElementById('aiTeachAreaStatus');
    if (elArea) elArea.value = area;
    const elAreaDetail = document.getElementById('aiTeachAreaDetail');
    if (elAreaDetail) elAreaDetail.value = areaDetail;
    handleAiTeachAreaChange();

    const elOther = document.getElementById('aiTeachOtherInfo');
    if (elOther) elOther.value = other;
}

function handleAiTeachAccessChange() {
    const sel = document.getElementById('aiTeachAccessStatus');
    const appBox = document.getElementById('aiTeachAppContainer');
    if (sel && appBox) {
        appBox.style.display = (sel.value === 'Lỗi ứng dụng cụ thể') ? 'block' : 'none';
    }
    updateAiTeachPreview();
}

function handleAiTeachAreaChange() {
    const sel = document.getElementById('aiTeachAreaStatus');
    const areaBox = document.getElementById('aiTeachAreaDetailContainer');
    if (sel && areaBox) {
        areaBox.style.display = (sel.value === 'Chỉ ở 1 khu vực') ? 'block' : 'none';
    }
    updateAiTeachPreview();
}

function buildAiTeachSummary() {
    const elPkg = document.getElementById('aiTeachPkg');
    const elAccess = document.getElementById('aiTeachAccessStatus');
    const elAppDetail = document.getElementById('aiTeachAppDetail');
    const elData = document.getElementById('aiTeachDataStatus');
    const elDevice = document.getElementById('aiTeachDevice');
    const elArea = document.getElementById('aiTeachAreaStatus');
    const elAreaDetail = document.getElementById('aiTeachAreaDetail');
    const elOther = document.getElementById('aiTeachOtherInfo');

    const pkg = (elPkg && elPkg.value.trim()) ? elPkg.value.trim() : 'Không đề cập';
    
    let access = 'Không vào được mạng (toàn bộ)';
    if (elAccess) {
        if (elAccess.value === 'Lỗi ứng dụng cụ thể') {
            const detail = (elAppDetail && elAppDetail.value.trim()) ? elAppDetail.value.trim() : '';
            access = detail ? `Lỗi ứng dụng cụ thể: ${detail}` : 'Lỗi ứng dụng cụ thể';
        } else {
            access = elAccess.value;
        }
    }

    const data = (elData && elData.value.trim()) ? elData.value.trim() : 'Không đề cập';
    const device = (elDevice && elDevice.value.trim()) ? elDevice.value.trim() : 'Không đề cập';

    let area = 'Không đề cập';
    if (elArea) {
        if (elArea.value === 'Chỉ ở 1 khu vực') {
            const loc = (elAreaDetail && elAreaDetail.value.trim()) ? elAreaDetail.value.trim() : '';
            area = loc ? `Chỉ ở 1 khu vực (${loc})` : 'Chỉ ở 1 khu vực';
        } else {
            area = elArea.value;
        }
    }

    const other = (elOther && elOther.value.trim()) ? elOther.value.trim() : 'Không có thông tin hành động phụ.';

    return `1. Gói cước sử dụng: ${pkg}\n2. Tình trạng truy cập: ${access}\n3. Tình trạng dung lượng: ${data}\n4. Thiết bị sử dụng: ${device}\n5. Khu vực xảy ra lỗi: ${area}\n6. Tóm tắt thông tin khác: ${other}`;
}

function updateAiTeachPreview() {
    const summary = buildAiTeachSummary();
    const previewEl = document.getElementById('aiTeachSummaryPreview');
    const textInput = document.getElementById('aiTeachSummaryInput');
    if (previewEl) previewEl.innerText = summary;
    if (textInput && document.getElementById('aiTeachTextContainer').style.display !== 'block') {
        textInput.value = summary;
    }
}

function toggleAiTeachViewMode() {
    const formBox = document.getElementById('aiTeachFormContainer');
    const textBox = document.getElementById('aiTeachTextContainer');
    const btn = document.getElementById('btnToggleAiTeachView');
    if (!formBox || !textBox) return;

    if (formBox.style.display === 'none') {
        // Chuyển sang Form
        formBox.style.display = 'block';
        textBox.style.display = 'none';
        if (btn) btn.innerText = 'Xem dạng văn bản 6 dòng';
        const txt = document.getElementById('aiTeachSummaryInput').value;
        parseAiTeachSummaryToForm(txt, document.getElementById('aiTeachPackageTitle').value);
        updateAiTeachPreview();
    } else {
        // Chuyển sang Textarea
        formBox.style.display = 'none';
        textBox.style.display = 'block';
        if (btn) btn.innerText = 'Chuyển sang form chọn nhanh';
        const summary = buildAiTeachSummary();
        document.getElementById('aiTeachSummaryInput').value = summary;
        updateAiTeachPreview();
    }
}

function parseAiTeachTextToForm() {
    const txt = document.getElementById('aiTeachSummaryInput').value;
    const previewEl = document.getElementById('aiTeachSummaryPreview');
    if (previewEl) previewEl.innerText = txt;
}

function closeAiTeachModal() {
    const modal = document.getElementById('modalAiTeach');
    if (modal) modal.style.display = 'none';
}

async function submitAiTeachFeedback() {
    const ticketId = document.getElementById('aiTeachTicketId').value;
    const phone = document.getElementById('aiTeachPhone').value;
    const incidentTime = document.getElementById('aiTeachIncidentTime') ? document.getElementById('aiTeachIncidentTime').value : '';
    const packageTitle = document.getElementById('aiTeachPackageTitle').value;
    const rawContent = document.getElementById('aiTeachRawContent').innerText;
    
    // Nếu đang ở Text mode thì lấy từ textarea, nếu đang ở Form mode thì lấy từ buildAiTeachSummary
    const textBox = document.getElementById('aiTeachTextContainer');
    let summaryInput = '';
    if (textBox && textBox.style.display === 'block') {
        summaryInput = document.getElementById('aiTeachSummaryInput').value.trim();
    } else {
        summaryInput = buildAiTeachSummary().trim();
    }

    const btn = document.getElementById('btnSubmitAiTeach');

    if (!summaryInput) {
        alert('Vui lòng thiết lập nội dung tóm tắt 6 mục chuẩn!');
        return;
    }

    try {
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = 'Đang lưu dữ liệu...';
        }

        const res = await fetch('/api/tickets/save-ai-feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ticket_id: ticketId ? parseInt(ticketId) : null,
                phone: phone,
                package_title: packageTitle,
                ticket_content: rawContent,
                summary_content: summaryInput,
                verified_by: 'KTV'
            })
        });

        const data = await res.json();
        if (data.success) {
            closeAiTeachModal();
            // Cập nhật ngay trong cache dữ liệu bảng phía client
            if (typeof cachedTickets !== 'undefined' && Array.isArray(cachedTickets)) {
                const item = cachedTickets.find(x => (ticketId && x.ticket_id == ticketId) || (x.phone == phone && (!incidentTime || x.incident_time == incidentTime)));
                if (item) {
                    item.ai_summary = summaryInput;
                }
            }
            if (typeof renderTicketsTable === 'function') {
                renderTicketsTable(true);
            }
            alert(data.message || 'Đã lưu mẫu chuẩn thành công! Qwen 2.5 sẽ học theo mẫu này.');
        } else {
            alert('Lỗi khi lưu: ' + (data.error || 'Không xác định'));
        }
    } catch (err) {
        alert('Lỗi kết nối máy chủ: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = 'Lưu Mẫu Chuẩn & Dạy AI';
        }
    }
}
