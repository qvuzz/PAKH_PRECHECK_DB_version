// static/js/modules/smsc_cdr.js
// Module tra cứu nhật ký tin nhắn SMSC (CDR)

// ==========================================
// TÍCH HỢP TRA CỨU NHẬT KÝ TIN NHẮN SMSC (CDR)
// ==========================================

function ensureSmscCdrHeaders() {
    const table = document.getElementById('cdrResultsTable');
    if (!table) return;
    table.style.minWidth = '1600px';
    const thead = table.querySelector('thead');
    if (thead) {
        thead.innerHTML = `
            <tr style="white-space:nowrap; background:#f1f5f9; color:#1e293b;">
                <th style="padding:8px 8px; width:42px; text-align:center;">STT</th>
                <th style="padding:8px 8px; width:58px; text-align:center;">Site</th>
                <th style="padding:8px 10px; min-width:120px;">Calling Number</th>
                <th style="padding:8px 10px; min-width:120px;">Called Number</th>
                <th style="padding:8px 10px; min-width:145px;">Delivery Time</th>
                <th style="padding:8px 10px; min-width:160px;">Originating MSC Address</th>
                <th style="padding:8px 10px; min-width:160px;">Destination MSC Address</th>
                <th style="padding:8px 10px; min-width:155px;">Message Submission Time</th>
                <th style="padding:8px 10px; min-width:130px;">Call Reference</th>
                <th style="padding:8px 10px; width:95px; text-align:center;">Message Length</th>
                <th style="padding:8px 10px; width:110px; text-align:center;">Number Of Attempts</th>
                <th style="padding:8px 10px; width:125px; text-align:center;">Mapped Network Error</th>
                <th style="padding:8px 10px; width:95px; text-align:center;">Message Status</th>
                <th style="padding:8px 10px; width:130px; text-align:center;">Cause For Termination</th>
                <th style="padding:8px 12px; min-width:240px;">Termination Cause Information</th>
            </tr>
        `;
    }
}

function openSmscCdrModal(phone, event) {
    if (event) event.stopPropagation();
    const modal = document.getElementById('modalSmscCdr');
    if (!modal) return;
    modal.style.display = 'flex';

    // Đảm bảo khung mở rộng tối đa theo màn hình (96vw)
    const innerBox = modal.querySelector('div') || document.getElementById('modalSmscCdrInner');
    if (innerBox) {
        innerBox.style.width = '96vw';
        innerBox.style.maxWidth = '1850px';
    }
    ensureSmscCdrHeaders();

    const input = document.getElementById('cdrPhoneInput');
    if (phone && input) {
        let cleanPhone = String(phone).trim().replace(/\D/g, '');
        if (cleanPhone.startsWith('0')) cleanPhone = '84' + cleanPhone.slice(1);
        input.value = cleanPhone;
        executeSmscCdrQuery();
    } else if (input) {
        input.focus();
    }
}

function closeSmscCdrModal() {
    const modal = document.getElementById('modalSmscCdr');
    if (modal) modal.style.display = 'none';
}

function setCdrTimePreset(val, btn) {
    const hiddenInp = document.getElementById('cdrHoursSelect');
    if (hiddenInp) hiddenInp.value = val;

    document.querySelectorAll('.cdr-time-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    toggleCdrDateInputs(val);
}

function toggleCdrDateInputs(val) {
    const box = document.getElementById('cdrCustomDateBox');
    if (!box) return;
    if (val === 'custom') {
        box.style.display = 'flex';
        const fromInp = document.getElementById('cdrFromDate');
        const toInp = document.getElementById('cdrToDate');
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const past = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const pastStr = `${past.getFullYear()}-${pad(past.getMonth() + 1)}-${pad(past.getDate())}`;
        if (fromInp && !fromInp.value) fromInp.value = pastStr;
        if (toInp && !toInp.value) toInp.value = todayStr;
    } else {
        box.style.display = 'none';
    }
}

// Lắng nghe phím ESC để đóng Modal SMSC CDR
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        const modal = document.getElementById('modalSmscCdr');
        if (modal && modal.style.display !== 'none') {
            closeSmscCdrModal();
        }
    }
});

// Biến lưu trạng thái bảng tra cứu CDR
let cdrFilterFailedOnly = false;
let lastCdrRecords = [];
let lastCdrPhone = '';
let cdrCurrentPage = 1;
let cdrPageSize = 50; // 'all' hoặc số lượng dòng trên 1 trang

function isCdrRecordFailed(r) {
    if (!r) return false;
    if (r.status_type === 'failed') return true;
    const desc = String(r.status_desc || '').toLowerCase();
    if (desc.includes('thất bại') || desc.includes('lỗi') || desc.includes('failed') || desc.includes('rejected')) return true;
    const code = String(r.status_code || '').trim();
    if (code && !['8', '0', '1', '2', '3'].includes(code)) return true;
    const resCode = String(r.termination_cause || r.result_code || '').trim();
    if (resCode && !['0', '0000', '100c', '100C', '4108', '--', ''].includes(resCode)) return true;
    return false;
}

function isCdrRecordPending(r) {
    if (!r) return false;
    if (r.status_type === 'pending') return true;
    const desc = String(r.status_desc || '').toLowerCase();
    if (desc.includes('chờ') || desc.includes('thử lại') || desc.includes('expired')) return true;
    const code = String(r.status_code || '').trim();
    if (['1', '2', '3'].includes(code)) return true;
    return false;
}

function toggleOnlyFailedCdr(btn) {
    cdrFilterFailedOnly = !cdrFilterFailedOnly;
    cdrCurrentPage = 1;
    const btnElem = btn || document.getElementById('btnFilterFailedOnly');
    const failedCount = lastCdrRecords.filter(isCdrRecordFailed).length;
    if (btnElem) {
        if (cdrFilterFailedOnly) {
            btnElem.style.background = '#dc2626';
            btnElem.style.color = '#ffffff';
            btnElem.style.borderColor = '#b91c1c';
            btnElem.innerHTML = `<span>Đang lọc tin lỗi:</span> <span style="background:#ffffff; color:#dc2626; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:800;">${failedCount}</span> <span style="font-size:10px; opacity:0.85;">(Bấm để xem tất cả)</span>`;
        } else {
            btnElem.style.background = '#fee2e2';
            btnElem.style.color = '#b91c1c';
            btnElem.style.borderColor = '#fca5a5';
            btnElem.innerHTML = `<span>Chỉ xem tin lỗi:</span> <span id="badgeFailedCount" style="background:#dc2626; color:#ffffff; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:800;">${failedCount}</span>`;
        }
    }
    renderCdrTable();
}

function changeCdrPageSize(newVal) {
    cdrPageSize = (newVal === 'all') ? 'all' : (parseInt(newVal, 10) || 50);
    cdrCurrentPage = 1;
    renderCdrTable();
}

function changeCdrPage(delta) {
    cdrCurrentPage += delta;
    renderCdrTable();
}

function goToCdrPage(page) {
    const displayRecords = cdrFilterFailedOnly
        ? lastCdrRecords.filter(isCdrRecordFailed)
        : lastCdrRecords;
    const totalRecords = displayRecords.length;
    const pageSizeNum = (cdrPageSize === 'all') ? totalRecords : (parseInt(cdrPageSize, 10) || 50);
    const totalPages = Math.max(1, Math.ceil(totalRecords / (pageSizeNum || 1)));

    if (page === 'last') {
        cdrCurrentPage = totalPages;
    } else {
        cdrCurrentPage = parseInt(page, 10) || 1;
    }
    renderCdrTable();
}

function renderCdrTable() {
    const tableBody = document.getElementById('cdrTableBody');
    const emptyState = document.getElementById('cdrEmptyState');
    const resultsTable = document.getElementById('cdrResultsTable');
    const paginationBox = document.getElementById('cdrPaginationBox');
    const pageInfo = document.getElementById('cdrPageInfo');
    const btnFirst = document.getElementById('btnCdrFirstPage');
    const btnPrev = document.getElementById('btnCdrPrevPage');
    const btnNext = document.getElementById('btnCdrNextPage');
    const btnLast = document.getElementById('btnCdrLastPage');

    if (!tableBody) return;

    const displayRecords = cdrFilterFailedOnly
        ? lastCdrRecords.filter(isCdrRecordFailed)
        : lastCdrRecords;

    const totalRecords = displayRecords.length;

    if (totalRecords === 0) {
        if (emptyState) {
            emptyState.style.display = 'block';
            emptyState.innerHTML = cdrFilterFailedOnly
                ? `<div style="color:#15803d; font-weight:700; padding:10px;">Không có tin nhắn lỗi nào trong ${lastCdrRecords.length} bản ghi CDR!</div>`
                : `Không có bản ghi nào.`;
        }
        if (resultsTable) resultsTable.style.display = 'none';
        if (paginationBox) paginationBox.style.display = 'none';
        return;
    }

    if (emptyState) emptyState.style.display = 'none';
    if (resultsTable) resultsTable.style.display = 'table';

    // Xử lý phân trang
    let pageRecords = displayRecords;
    let startIndex = 0;
    let totalPages = 1;

    if (cdrPageSize !== 'all') {
        const pageSizeNum = parseInt(cdrPageSize, 10) || 50;
        totalPages = Math.max(1, Math.ceil(totalRecords / pageSizeNum));
        if (cdrCurrentPage > totalPages) cdrCurrentPage = totalPages;
        if (cdrCurrentPage < 1) cdrCurrentPage = 1;

        startIndex = (cdrCurrentPage - 1) * pageSizeNum;
        pageRecords = displayRecords.slice(startIndex, startIndex + pageSizeNum);
    } else {
        cdrCurrentPage = 1;
        totalPages = 1;
    }

    if (paginationBox) {
        paginationBox.style.display = 'flex';
        if (pageInfo) {
            const endIdx = Math.min(startIndex + pageRecords.length, totalRecords);
            pageInfo.innerText = `Trang ${cdrCurrentPage} / ${totalPages} (${startIndex + 1}-${endIdx} / ${totalRecords})`;
        }
        if (btnFirst) btnFirst.disabled = (cdrCurrentPage <= 1);
        if (btnPrev) btnPrev.disabled = (cdrCurrentPage <= 1);
        if (btnNext) btnNext.disabled = (cdrCurrentPage >= totalPages);
        if (btnLast) btnLast.disabled = (cdrCurrentPage >= totalPages);
    }

    const isPhoneMatch = (numStr, target) => {
        if (!numStr || !target) return false;
        const c1 = String(numStr).replace(/\D/g, '');
        const c2 = String(target).replace(/\D/g, '');
        if (!c1 || !c2) return false;
        return (c1 === c2 || c1.endsWith(c2) || c2.endsWith(c1));
    };

    tableBody.innerHTML = pageRecords.map((r, localIdx) => {
        const globalIdx = startIndex + localIdx;
        const isFailed = isCdrRecordFailed(r);
        const isPending = !isFailed && isCdrRecordPending(r);

        let rowBg = 'transparent';
        let rowHoverBg = '#f8fafc';
        let borderLeft = '4px solid transparent';
        let sttHtml = `<span style="color:#64748b; font-size:10.5px;">${globalIdx + 1}</span>`;

        if (isFailed) {
            rowBg = '#fff1f2';
            rowHoverBg = '#ffe4e6';
            borderLeft = '4px solid #ef4444';
            sttHtml = `<span style="color:#dc2626; font-weight:800; font-size:10.5px;">${globalIdx + 1}</span>`;
        } else if (isPending) {
            rowBg = '#fffbeb';
            rowHoverBg = '#fef3c7';
            borderLeft = '4px solid #f59e0b';
            sttHtml = `<span style="color:#d97706; font-weight:800; font-size:10.5px;">${globalIdx + 1}</span>`;
        }

        const padVal = (val, len) => {
            if (val === null || val === undefined || val === '' || val === '--') return '--';
            const num = parseInt(val, 10);
            return isNaN(num) ? String(val) : String(num).padStart(len, '0');
        };

        const siteUpper = String(r.site || 'HCM').toUpperCase();
        const siteBadge = siteUpper === 'HNI'
            ? `<span style="background:#ecfdf5; color:#047857; border:1px solid #a7f3d0; font-weight:800; font-size:9.5px; padding:1px 5px; border-radius:3px;">HNI</span>`
            : `<span style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; font-weight:800; font-size:9.5px; padding:1px 5px; border-radius:3px;">HCM</span>`;

        const isTargetCalling = isPhoneMatch(r.calling_number, lastCdrPhone);
        const isTargetCalled = isPhoneMatch(r.called_number, lastCdrPhone);

        const attemptsVal = r.attempts || 1;
        const attemptsPadded = padVal(attemptsVal, 3);
        const attemptsHtml = attemptsVal > 1
            ? `<b style="color:#dc2626; font-weight:800;">${escapeHtml(attemptsPadded)}</b>`
            : `<span style="color:#334155;">${escapeHtml(attemptsPadded)}</span>`;

        const msgLen = padVal(r.message_length, 4);

        const netErr = String(r.mapped_network_err || '0').trim();
        const netErrHtml = (netErr !== '--' && netErr !== '0')
            ? `<span style="background:#fef2f2; color:#b91c1c; border:1px solid #fca5a5; padding:1px 5px; border-radius:3px; font-weight:700; font-size:10.5px;">${escapeHtml(netErr)}</span>`
            : `<span style="color:#334155;">${escapeHtml(netErr)}</span>`;

        const statusCode = r.status_code ? String(r.status_code).trim() : '2';
        const statusHtml = isFailed
            ? `<span style="background:#fee2e2; color:#b91c1c; border:1px solid #f87171; padding:1px 5px; border-radius:3px; font-weight:800; font-size:10.5px;">${escapeHtml(statusCode)}</span>`
            : `<span style="color:#334155; font-weight:600;">${escapeHtml(statusCode)}</span>`;

        const termCause = String(r.termination_cause || r.result_code || '100C').trim();
        const termCauseHtml = (isFailed && termCause !== '100C' && termCause !== '--')
            ? `<span style="color:#dc2626; font-weight:800;">${escapeHtml(termCause)}</span>`
            : `<span style="color:#334155; font-weight:500;">${escapeHtml(termCause)}</span>`;

        const termInfo = String(r.termination_cause_info || 'Message Delivery Successful').trim();
        const termInfoBox = `
            <div style="display:inline-flex; align-items:center; justify-content:space-between; background:#ffffff; border:1px solid #cbd5e1; border-radius:4px; padding:3px 10px; font-size:11px; color:#334155; width:230px; box-sizing:border-box; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03);">
                <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-right:8px;" title="${escapeHtml(termInfo)}">${escapeHtml(termInfo)}</span>
                <span style="font-size:8px; color:#64748b; flex-shrink:0;">▼</span>
            </div>
        `;

        return `
            <tr style="background:${rowBg}; border-left:${borderLeft}; border-bottom:1px solid #e2e8f0; transition:background 0.15s ease; white-space:nowrap;" onmouseover="this.style.background='${rowHoverBg}'" onmouseout="this.style.background='${rowBg}'">
                <td style="padding:6px 8px; text-align:center;">${sttHtml}</td>
                <td style="padding:6px 8px; text-align:center;">${siteBadge}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; font-weight:${isTargetCalling ? '800' : '500'}; color:${isTargetCalling ? '#0f766e' : '#334155'};">${escapeHtml(r.calling_number || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; font-weight:${isTargetCalled ? '800' : '500'}; color:${isTargetCalled ? '#0f766e' : '#334155'};">${escapeHtml(r.called_number || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#334155;">${escapeHtml(r.delivery_time || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#475569;">${escapeHtml(r.originating_msc || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#475569;">${escapeHtml(r.destination_msc || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#334155;">${escapeHtml(r.submission_time || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#475569;">${escapeHtml(r.call_reference || '--')}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px; color:#334155;">${escapeHtml(msgLen)}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${attemptsHtml}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${netErrHtml}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${statusHtml}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${termCauseHtml}</td>
                <td style="padding:4px 10px; vertical-align:middle;">${termInfoBox}</td>
            </tr>
        `;
    }).join('');
}

async function executeSmscCdrQuery() {
    const phoneInput = document.getElementById('cdrPhoneInput');
    const dirSelect = document.getElementById('cdrDirectionSelect');
    const hoursSelect = document.getElementById('cdrHoursSelect');
    const limitSelect = document.getElementById('cdrLimitSelect');

    const spinner = document.getElementById('cdrLoadingSpinner');
    const emptyState = document.getElementById('cdrEmptyState');
    const resultsTable = document.getElementById('cdrResultsTable');
    const tableBody = document.getElementById('cdrTableBody');
    const kpiSection = document.getElementById('cdrKpiSection');
    const summaryText = document.getElementById('cdrQuerySummaryText');
    const sourceDot = document.getElementById('cdrSourceDot');
    const sourceText = document.getElementById('cdrSourceText');
    const btnSubmit = document.getElementById('btnExecuteCdrQuery');

    const rawPhone = phoneInput ? phoneInput.value.trim() : '';
    let cleanPhone = rawPhone.replace(/\D/g, '');
    if (!cleanPhone) {
        alert('Vui lòng nhập số thuê bao cần tra cứu CDR!');
        if (phoneInput) phoneInput.focus();
        return;
    }
    if (cleanPhone.startsWith('0')) cleanPhone = '84' + cleanPhone.slice(1);
    if (phoneInput) phoneInput.value = cleanPhone;

    const direction = dirSelect ? dirSelect.value : 'both';
    let limit = 1000;
    if (limitSelect) {
        if (limitSelect.value === 'all') {
            limit = 10000;
        } else {
            limit = parseInt(limitSelect.value, 10) || 1000;
        }
    }

    let isCustom = (hoursSelect && hoursSelect.value === 'custom');
    let fromDateVal = '';
    let toDateVal = '';
    let hours = 24;
    let timeRangeDesc = '';

    if (isCustom) {
        const fromInp = document.getElementById('cdrFromDate');
        const toInp = document.getElementById('cdrToDate');
        fromDateVal = fromInp ? fromInp.value.trim() : '';
        toDateVal = toInp ? toInp.value.trim() : '';
        if (!fromDateVal || !toDateVal) {
            alert('Vui lòng chọn đầy đủ Từ ngày và Đến ngày!');
            return;
        }
        if (fromDateVal > toDateVal) {
            alert('Từ ngày không thể lớn hơn Đến ngày!');
            return;
        }
        timeRangeDesc = `từ ${fromDateVal} đến ${toDateVal}`;
    } else {
        hours = hoursSelect ? parseInt(hoursSelect.value, 10) || 24 : 24;
        if (hours === 168) timeRangeDesc = '1 tuần qua';
        else if (hours === 720) timeRangeDesc = '1 tháng qua';
        else timeRangeDesc = `${hours}h qua`;
    }

    // UI Loading state
    if (spinner) spinner.style.display = 'block';
    if (emptyState) emptyState.style.display = 'none';
    if (resultsTable) resultsTable.style.display = 'none';
    if (btnSubmit) {
        btnSubmit.disabled = true;
        btnSubmit.style.opacity = '0.65';
    }
    if (sourceText) sourceText.innerText = 'Đang truy vấn...';
    if (sourceDot) sourceDot.style.background = '#f59e0b';

    try {
        let queryUrl = `/api/cdr/sms?phone=${encodeURIComponent(cleanPhone)}&direction=${encodeURIComponent(direction)}&limit=${limit}`;
        if (isCustom) {
            queryUrl += `&from_date=${encodeURIComponent(fromDateVal)}&to_date=${encodeURIComponent(toDateVal)}`;
        } else {
            queryUrl += `&hours=${hours}`;
        }
        const res = await fetch(queryUrl);
        const data = await res.json();

        if (spinner) spinner.style.display = 'none';
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.style.opacity = '1';
        }

        if (!data.success) {
            if (emptyState) {
                emptyState.style.display = 'block';
                const errMsg = data.message || data.error || 'Lỗi không xác định từ hệ thống SMSC CDR';
                emptyState.innerHTML = `<div style="color:#dc2626; font-weight:700; line-height:1.5;">Tra cứu thất bại: ${escapeHtml(errMsg)}</div>`;
            }
            if (sourceText) sourceText.innerText = 'Lỗi kết nối';
            if (sourceDot) sourceDot.style.background = '#ef4444';
            return;
        }

        // Cập nhật nguồn dữ liệu (Elastic hay VHKT Bridge)
        const sourceLabel = data.source === 'elastic_direct' ? 'Elasticsearch trực tiếp' : (data.source === 'vhkt_bridge' ? 'Cầu VHKT SFTP' : data.source);
        if (sourceText) sourceText.innerText = `Nguồn: ${sourceLabel}`;
        if (sourceDot) sourceDot.style.background = '#10b981';

        const records = data.records || [];
        lastCdrRecords = records;
        lastCdrPhone = cleanPhone;
        cdrFilterFailedOnly = false;
        cdrCurrentPage = 1;

        // Reset nút lọc tin lỗi
        const btnFilter = document.getElementById('btnFilterFailedOnly');
        if (btnFilter) {
            btnFilter.style.background = '#fee2e2';
            btnFilter.style.color = '#b91c1c';
            btnFilter.style.borderColor = '#fca5a5';
            btnFilter.innerHTML = `<span>Chỉ xem tin lỗi:</span> <span id="badgeFailedCount" style="background:#dc2626; color:#ffffff; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:800;">0</span>`;
        }

        const total = records.length;
        const moCount = records.filter(r => String(r.direction || '').toUpperCase().includes('MO')).length;
        const mtCount = records.filter(r => String(r.direction || '').toUpperCase().includes('MT')).length;
        const failedCount = records.filter(isCdrRecordFailed).length;
        const successCount = records.filter(r => !isCdrRecordFailed(r) && !isCdrRecordPending(r)).length;
        const successRate = total > 0 ? Math.round((successCount / total) * 100) : 0;

        const kpiTotal = document.getElementById('kpiTotalCdr');
        const kpiMo = document.getElementById('kpiMoCdr');
        const kpiMt = document.getElementById('kpiMtCdr');
        const kpiSuccess = document.getElementById('kpiSuccessCdr');
        const kpiFailed = document.getElementById('kpiFailedCdr');
        const badgeFailed = document.getElementById('badgeFailedCount');
        const boxFilter = document.getElementById('boxFilterFailed');
        const kpiSection = document.getElementById('cdrKpiSection');
        const summaryText = document.getElementById('cdrQuerySummaryText');

        if (kpiTotal) kpiTotal.innerText = total.toLocaleString();
        if (kpiMo) kpiMo.innerText = moCount.toLocaleString();
        if (kpiMt) kpiMt.innerText = mtCount.toLocaleString();
        if (kpiSuccess) kpiSuccess.innerText = `${successRate}% (${successCount}/${total})`;
        if (kpiFailed) kpiFailed.innerText = failedCount.toLocaleString();
        if (badgeFailed) badgeFailed.innerText = failedCount;
        if (boxFilter) boxFilter.style.display = failedCount > 0 ? 'inline-flex' : 'none';
        if (kpiSection) kpiSection.style.display = 'flex';

        if (summaryText) {
            const failedNotice = failedCount > 0 ? `, <span style="color:#dc2626; font-weight:700;">(Phát hiện ${failedCount} tin nhắn lỗi)</span>` : '';
            summaryText.innerHTML = `Tìm thấy <b>${total}</b> bản ghi CDR cho thuê bao <b>${escapeHtml(cleanPhone)}</b> (${escapeHtml(timeRangeDesc)}, Hệ thống: ${escapeHtml(sourceLabel)})${failedNotice}.`;
        }

        if (total === 0) {
            if (emptyState) {
                emptyState.style.display = 'block';
                emptyState.innerHTML = `Không có bản ghi tin nhắn SMSC nào phát sinh cho thuê bao <b>${escapeHtml(cleanPhone)}</b> trong khoảng ${escapeHtml(timeRangeDesc)}.`;
            }
            if (resultsTable) resultsTable.style.display = 'none';
            return;
        }

        renderCdrTable();

    } catch (err) {
        if (spinner) spinner.style.display = 'none';
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.style.opacity = '1';
        }
        if (emptyState) {
            emptyState.style.display = 'block';
            emptyState.innerHTML = `<div style="color:#dc2626; font-weight:700;">⚠️ Lỗi kết nối API: ${escapeHtml(err.message)}</div>`;
        }
        if (sourceText) sourceText.innerText = 'Lỗi truy vấn';
        if (sourceDot) sourceDot.style.background = '#ef4444';
    }
}
