// static/js/flow_audit.js
// Module Client-Side: Kiểm Tra, Đối Soát & Rà Soát Luồng Phiếu OneOSS / CCOS

let currentFlowAuditTab = 'single'; // 'single', 'batch', 'scan'
let auditSavedResults = [];
let currentFilterGrade = 'ALL';
let currentFilterCategory = 'ALL'; // 'ALL', 'FLOW_ERROR', 'OVERDUE_SLA', 'HEALTHY'

function selectFlowAuditModule(updateUrl = true) {
    if (updateUrl && window.location.pathname !== '/kiem-tra-luong') {
        history.pushState({ tab: 'kiem-tra-luong' }, '', '/kiem-tra-luong');
    }

    // 1. Highlight menu item
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById('nav-flow-audit');
    if (activeBtn) activeBtn.classList.add('active');

    // 2. Ẩn các khu vực view khác
    const mainTabs = document.getElementById('mainTabsHeader');
    if (mainTabs) mainTabs.style.display = 'none';

    const analyticsBox = document.getElementById('closedAnalyticsContainer');
    if (analyticsBox) analyticsBox.style.display = 'none';

    const tableDataView = document.getElementById('tableDataView');
    if (tableDataView) tableDataView.style.display = 'none';

    // 3. Hiện container module kiểm tra luồng
    const container = document.getElementById('flowAuditContainer');
    if (container) {
        container.style.display = 'block';
    }

    // Nạp kết quả đã lưu trước đó nếu đang ở tab rà soát
    if (currentFlowAuditTab === 'scan') {
        loadSavedAuditResults();
    }
}

function switchFlowAuditTab(tabName) {
    currentFlowAuditTab = tabName;
    document.querySelectorAll('.fa-subtab-btn').forEach(btn => btn.classList.remove('active'));
    const btn = document.getElementById(`tabBtnFa-${tabName}`);
    if (btn) btn.classList.add('active');

    document.getElementById('faSectionSingle').style.display = (tabName === 'single') ? 'block' : 'none';
    document.getElementById('faSectionBatch').style.display = (tabName === 'batch') ? 'block' : 'none';
    document.getElementById('faSectionScan').style.display = (tabName === 'scan') ? 'block' : 'none';

    if (tabName === 'scan') {
        loadSavedAuditResults();
    }
}

// =============================================================================
// 1. TRA CỨU PHIẾU ĐƠN LẺ
// =============================================================================
async function submitSingleFlowAudit(customQuery = '') {
    const queryInput = document.getElementById('faSingleInput');
    const query = (customQuery || (queryInput ? queryInput.value : '')).trim();

    if (!query) {
        alert('Vui lòng nhập Mã phiếu (ví dụ: HT/2026/09/04/22942 hoặc 22942) hoặc Số điện thoại!');
        return;
    }

    if (queryInput && customQuery) {
        queryInput.value = customQuery;
    }

    const btnSubmit = document.getElementById('btnFaSingleSubmit');
    const resultBox = document.getElementById('faSingleResultBox');
    const loadingBox = document.getElementById('faSingleLoading');

    if (btnSubmit) {
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = 'Đang kiểm tra...';
    }
    if (resultBox) resultBox.style.display = 'none';
    if (loadingBox) loadingBox.style.display = 'block';

    try {
        const resp = await fetch(`/api/flow-audit/check-single?query=${encodeURIComponent(query)}`);
        const res = await resp.json();

        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.message || 'Lỗi tra cứu phiếu từ hệ thống OneOSS');
        }

        renderSingleFlowAuditResult(res);
        if (resultBox) resultBox.style.display = 'block';
    } catch (err) {
        alert('Không thể kiểm tra phiếu: ' + err.message);
    } finally {
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = 'Kiểm tra ngay';
        }
        if (loadingBox) loadingBox.style.display = 'none';
    }
}

function renderSingleFlowAuditResult(data) {
    const master = data.master_ticket || {};
    const diag = data.diagnostic || {};
    const flows = data.ticket_flows || [];
    const issues = diag.issues || [];

    // 1. Thẻ chẩn đoán kết luận & cảnh báo
    const alertBox = document.getElementById('faSingleAlertBox');
    let gradeBadgeClass = 'fa-badge-healthy';
    let alertBoxClass = 'fa-alert-healthy';

    if (diag.grade === 'CRITICAL') {
        gradeBadgeClass = 'fa-badge-critical';
        alertBoxClass = 'fa-alert-critical';
    } else if (diag.grade === 'WARNING') {
        gradeBadgeClass = 'fa-badge-warning';
        alertBoxClass = 'fa-alert-warning';
    }

    let issuesHtml = '';
    if (issues.length > 0) {
        issuesHtml = issues.map((iss, idx) => `
            <div style="margin-top:8px; padding-top:8px; border-top:1px dashed rgba(0,0,0,0.1);">
                <div style="font-weight:700; color:#0f172a;">${idx + 1}. [${escapeHtml(iss.severity)}] ${escapeHtml(iss.name)}</div>
                <div style="margin-top:3px; color:#334155;">${escapeHtml(iss.description)}</div>
                <div style="margin-top:3px; color:#005baa; font-weight:600;">Kiến nghị: ${escapeHtml(iss.recommendation)}</div>
            </div>
        `).join('');
    } else {
        issuesHtml = '<div style="margin-top:4px; color:#166534;">Luồng xử lý bình thường, không phát hiện điểm nghẽn hay lỗi đồng bộ OneOSS/CCOS.</div>';
    }

    alertBox.innerHTML = `
        <div class="fa-alert-box ${alertBoxClass}">
            <div class="fa-alert-title">
                <span class="fa-badge ${gradeBadgeClass}">${escapeHtml(diag.grade)}</span>
                <span style="font-size:13.5px;">${escapeHtml(diag.title || 'Kết quả chẩn đoán luồng')}</span>
            </div>
            ${issuesHtml}
        </div>
    `;

    // 2. Thẻ thông tin Master Phiếu
    const infoBox = document.getElementById('faSingleInfoBox');
    infoBox.innerHTML = `
        <div class="fa-info-list">
            <div class="fa-info-item">
                <span class="fa-info-key">Mã Phiếu OneOSS:</span>
                <span class="fa-info-val" style="color:#005baa; font-weight:700;">${escapeHtml(master.ticketCode || data.ticket_code || '--')}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Ticket ID:</span>
                <span class="fa-info-val">${escapeHtml(String(master.ticketId || data.ticket_id || '--'))}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Số Điện Thoại:</span>
                <span class="fa-info-val" style="color:#0284c7; font-family:'JetBrains Mono', monospace; font-weight:700;">${escapeHtml(data.phone || master.customerPhone || '--')}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Tên Khách Hàng:</span>
                <span class="fa-info-val">${escapeHtml(master.customerName || data.customer_name || '--')}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Tiêu Đề / Gói Cước:</span>
                <span class="fa-info-val">${escapeHtml(master.title || '--')}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Mã Khiếu Nại CCOS:</span>
                <span class="fa-info-val" style="color:#d97706; font-weight:700;">${escapeHtml(String(master.khieuNaiId || diag.ccos_id || '--'))}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Nguồn Tiếp Nhận:</span>
                <span class="fa-info-val">${escapeHtml(master.dataSource || 'CCOS')}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Thời Điểm CCOS Gửi:</span>
                <span class="fa-info-val">${escapeHtml(master.requestDate || '--')}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Thời Điểm Sự Cố:</span>
                <span class="fa-info-val">${escapeHtml(master.incidentDate || '--')}</span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Trạng Thái OneOSS:</span>
                <span class="fa-info-val">
                    <span class="fa-badge ${master.clTicketStatusId === 3 ? 'fa-badge-healthy' : 'fa-badge-warning'}">
                        ${escapeHtml(diag.status_name || master.statusName || (master.status === 1 ? 'Đang xử lý' : 'Đã đóng'))} (ID: ${escapeHtml(String(master.clTicketStatusId || '--'))})
                    </span>
                </span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Tổng Thời Gian SLA:</span>
                <span class="fa-info-val" style="font-weight:700; color:${diag.total_sla_hours > 48 ? '#dc2626' : '#16a34a'};">
                    ${diag.total_sla_hours} giờ ${diag.total_sla_hours > 48 ? '(Quá hạn cam kết)' : '(Trong hạn)'}
                </span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Số Lần Reopen:</span>
                <span class="fa-info-val" style="color:${diag.reopen_count > 0 ? '#d97706' : '#64748b'}; font-weight:700;">
                    ${diag.reopen_count} lần
                </span>
            </div>
            <div class="fa-info-item">
                <span class="fa-info-key">Địa Bàn Hành Chính:</span>
                <span class="fa-info-val">${escapeHtml(master.wardName || '')} ${escapeHtml(master.provinceName ? '— ' + master.provinceName : master.address || '--')}</span>
            </div>
        </div>
    `;

    // 3. Timeline các bước xử lý
    const timelineBox = document.getElementById('faSingleTimelineBox');
    if (!flows || flows.length === 0) {
        timelineBox.innerHTML = '<div style="color:#64748b; font-style:italic;">Không tìm thấy lịch sử luồng xử lý chi tiết từ OneOSS Gateway.</div>';
        return;
    }

    const timelineItemsHtml = flows.map((f, idx) => {
        const stepName = strVal(f.processNodeName || 'Bước không tên');
        const user = strVal(f.receivedUserName || 'Hệ thống tự động');
        const created = strVal(f.createdDate || '').replace('T', ' ').substring(0, 19);
        const closing = strVal(f.closingDate || '').replace('T', ' ').substring(0, 19);
        const content = strVal(f.closingContent || '');

        let dotClass = '';
        if (stepName === 'Kết thúc') {
            dotClass = f.closingDate ? 'end' : 'hang';
        } else if (stepName.includes('2.6')) {
            dotClass = 'end';
        } else if (stepName.includes('2.1')) {
            dotClass = 'reopen';
        }

        return `
            <div class="fa-timeline-item">
                <div class="fa-timeline-dot ${dotClass}"></div>
                <div class="fa-timeline-content">
                    <div class="fa-timeline-head">
                        <span class="fa-timeline-step">#${idx + 1}. ${escapeHtml(stepName)}</span>
                        <span class="fa-timeline-time">${escapeHtml(created)} ${closing ? `➔ ${escapeHtml(closing)}` : ''}</span>
                    </div>
                    <div class="fa-timeline-user">Người thụ lý: ${escapeHtml(user)} ${f.unit ? `(${escapeHtml(f.unit)})` : ''}</div>
                    ${content ? `<div class="fa-timeline-desc">${escapeHtml(content)}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');

    timelineBox.innerHTML = `
        <div style="font-size:12px; color:#64748b; margin-bottom:10px;">
            Tổng cộng: <b>${flows.length}</b> lượt luân chuyển luồng quy trình trên OneOSS Gateway.
        </div>
        <div class="fa-timeline">${timelineItemsHtml}</div>
    `;
}

// =============================================================================
// 2. NHẬP DANH SÁCH PHIẾU (BATCH CHECK)
// =============================================================================
async function submitBatchFlowAudit() {
    const inputArea = document.getElementById('faBatchTextarea');
    const rawText = (inputArea ? inputArea.value : '').trim();

    if (!rawText) {
        alert('Vui lòng nhập hoặc dán danh sách mã phiếu (mỗi mã 1 dòng)!');
        return;
    }

    const lines = rawText.split('\n').map(l => l.trim()).filter(l => l);
    if (lines.length === 0) {
        alert('Danh sách mã phiếu không hợp lệ.');
        return;
    }

    const btnSubmit = document.getElementById('btnFaBatchSubmit');
    const loadingBox = document.getElementById('faBatchLoading');
    const resultBox = document.getElementById('faBatchResultBox');

    if (btnSubmit) {
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = `Đang kiểm tra (${lines.length} phiếu)...`;
    }
    if (loadingBox) loadingBox.style.display = 'block';
    if (resultBox) resultBox.style.display = 'none';

    try {
        const resp = await fetch('/api/flow-audit/check-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket_list: lines })
        });
        const res = await resp.json();

        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.message || 'Lỗi kiểm tra danh sách phiếu');
        }

        renderBatchTableResults('faBatchTbody', res.items || []);
        updateBatchKpiStats(res);
        if (resultBox) resultBox.style.display = 'block';
    } catch (err) {
        alert('Không thể thực hiện kiểm tra hàng loạt: ' + err.message);
    } finally {
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = 'Bắt đầu kiểm tra danh sách';
        }
        if (loadingBox) loadingBox.style.display = 'none';
    }
}

function handleBatchFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const textarea = document.getElementById('faBatchTextarea');
        if (textarea) {
            textarea.value = content;
        }
    };
    reader.readAsText(file);
}

// =============================================================================
// 3. RÀ SOÁT TẤT CẢ PHIẾU ĐÃ ĐÓNG (SCAN CLOSED TICKETS)
// =============================================================================
function setScanQuickDate(type) {
    const fromInput = document.getElementById('faScanFromDate');
    const toInput = document.getElementById('faScanToDate');
    if (!fromInput || !toInput) return;

    const now = new Date();
    const formatDate = (d) => {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    };

    if (type === 'today') {
        fromInput.value = formatDate(now);
        toInput.value = formatDate(now);
    } else if (type === '3days') {
        const past = new Date(now.getTime() - 3 * 24 * 3600 * 1000);
        fromInput.value = formatDate(past);
        toInput.value = formatDate(now);
    } else if (type === '7days') {
        const past = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
        fromInput.value = formatDate(past);
        toInput.value = formatDate(now);
    } else if (type === 'this_month') {
        const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
        fromInput.value = formatDate(firstDay);
        toInput.value = formatDate(now);
    } else if (type === 'all') {
        fromInput.value = '';
        toInput.value = '';
    }

    loadSavedAuditResults();
}

async function triggerScanClosedTickets() {
    const limitSelect = document.getElementById('faScanLimitSelect');
    const limit = parseInt(limitSelect ? limitSelect.value : 500, 10);
    const fromDate = document.getElementById('faScanFromDate') ? document.getElementById('faScanFromDate').value : '';
    const toDate = document.getElementById('faScanToDate') ? document.getElementById('faScanToDate').value : '';
    const scanSource = document.getElementById('faScanSourceSelect') ? document.getElementById('faScanSourceSelect').value : 'oneoss_live';
    const ticketStatusType = document.getElementById('faTicketStatusTypeSelect') ? document.getElementById('faTicketStatusTypeSelect').value : 'closed';
    const chkSkip = document.getElementById('chkFaSkipExisting');
    const forceRefresh = chkSkip ? !chkSkip.checked : false;

    const btnScan = document.getElementById('btnFaScanClosed');
    const loadingBox = document.getElementById('faScanLoading');

    if (btnScan) {
        btnScan.disabled = true;
        btnScan.innerHTML = 'Đang rà soát đối soát...';
    }
    if (loadingBox) {
        loadingBox.style.display = 'block';
        const sourceLabel = scanSource === 'oneoss_live' ? 'máy chủ OneOSS TTS Mới' : 'CSDL hệ thống';
        loadingBox.innerHTML = `Đang kết nối ${sourceLabel} để rà soát danh sách phiếu (${fromDate || 'toàn thời gian'} đến ${toDate || 'hiện tại'})...`;
    }

    try {
        const url = `/api/flow-audit/scan-closed-tickets?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}&limit=${limit}&source=tts_new&scan_source=${encodeURIComponent(scanSource)}&ticket_status_type=${encodeURIComponent(ticketStatusType)}&force_refresh=${forceRefresh}`;
        const resp = await fetch(url, { method: 'POST' });
        const res = await resp.json();

        if (!resp.ok || !res.success) {
            throw new Error(res.detail || res.message || 'Lỗi khi rà soát phiếu');
        }

        if (res.message && res.total === 0) {
            alert(res.message);
        } else {
            let srcText = 'toàn bộ OneOSS TTS Mới (Tra cứu tiến trình)';
            if (res.scan_source === 'oneoss_personal') {
                srcText = 'hàng đợi cá nhân KTV (TTS Mới)';
            } else if (res.scan_source === 'db') {
                srcText = 'CSDL hệ thống (Nội bộ)';
            }
            const flowErr = res.flow_error_count !== undefined ? res.flow_error_count : (res.critical_count || 0);
            const slaOverdue = res.sla_overdue_count !== undefined ? res.sla_overdue_count : (res.warning_count || 0);
            const healthy = res.healthy_count || 0;
            const summaryMsg = `Đã đối soát xong ${res.total} phiếu từ ${srcText} (Quét mới: ${res.scanned_new}, Tái sử dụng: ${res.reused_existing}).\n- Lỗi luồng hệ thống: ${flowErr} phiếu\n- Quá hạn SLA CCOS: ${slaOverdue} phiếu\n- Quy trình hợp lệ: ${healthy} phiếu`;
            alert(summaryMsg);
        }

        loadSavedAuditResults();
    } catch (err) {
        alert('Lỗi rà soát phiếu: ' + err.message);
    } finally {
        if (btnScan) {
            btnScan.disabled = false;
            btnScan.innerHTML = 'Bắt đầu rà soát phiếu';
        }
        if (loadingBox) loadingBox.style.display = 'none';
    }
}

async function loadSavedAuditResults(cat = null) {
    if (cat !== null) {
        currentFilterCategory = cat;
    } else {
        cat = currentFilterCategory || 'ALL';
    }

    const fromDate = document.getElementById('faScanFromDate') ? document.getElementById('faScanFromDate').value : '';
    const toDate = document.getElementById('faScanToDate') ? document.getElementById('faScanToDate').value : '';

    try {
        const url = `/api/flow-audit/saved-audit-results?category=${encodeURIComponent(cat)}&from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}&limit=1000`;
        const resp = await fetch(url);
        const res = await resp.json();

        if (res.success) {
            auditSavedResults = res.items || [];
            updateScanKpiCards(res);
            renderSavedAuditTable(auditSavedResults);

            const badge = document.getElementById('faFilteredCountBadge');
            if (badge) {
                const catLabels = {
                    'ALL': 'Tất cả phiếu',
                    'FLOW_ERROR': 'Lỗi luồng hệ thống',
                    'OVERDUE_SLA': 'Quá hạn SLA CCOS',
                    'HEALTHY': 'Quy trình hợp lệ'
                };
                badge.innerText = `Hiển thị: ${auditSavedResults.length} / ${res.total} phiếu (${catLabels[cat] || cat})`;
            }
        }
    } catch (err) {
        console.error('Lỗi tải kết quả đối soát đã lưu:', err);
    }
}

function updateScanKpiCards(stats) {
    const elTotal = document.getElementById('faKpiTotal');
    const elFlowError = document.getElementById('faKpiFlowError');
    const elOverdueSla = document.getElementById('faKpiOverdueSla');
    const elHealthy = document.getElementById('faKpiHealthy');

    if (elTotal) elTotal.innerText = stats.total || 0;
    if (elFlowError) elFlowError.innerText = stats.flow_error_count !== undefined ? stats.flow_error_count : (stats.critical_count || 0);
    if (elOverdueSla) elOverdueSla.innerText = stats.sla_overdue_count !== undefined ? stats.sla_overdue_count : (stats.warning_count || 0);
    if (elHealthy) elHealthy.innerText = stats.healthy_count || 0;
}

function updateBatchKpiStats(stats) {
    const elTotal = document.getElementById('faBatchKpiTotal');
    const elCritical = document.getElementById('faBatchKpiCritical');
    const elWarning = document.getElementById('faBatchKpiWarning');
    const elHealthy = document.getElementById('faBatchKpiHealthy');

    if (elTotal) elTotal.innerText = stats.total || 0;
    if (elCritical) elCritical.innerText = stats.critical_count || 0;
    if (elWarning) elWarning.innerText = stats.warning_count || 0;
    if (elHealthy) elHealthy.innerText = stats.healthy_count || 0;
}

function filterAuditByCategory(cat) {
    currentFilterCategory = cat;

    // Cập nhật trạng thái active của các thẻ KPI
    document.querySelectorAll('.fa-kpi-card').forEach(c => c.classList.remove('active'));
    const cardMap = {
        'ALL': 'kpiCard-all',
        'FLOW_ERROR': 'kpiCard-flow_error',
        'OVERDUE_SLA': 'kpiCard-overdue_sla',
        'HEALTHY': 'kpiCard-healthy'
    };
    const targetCard = document.getElementById(cardMap[cat]);
    if (targetCard) targetCard.classList.add('active');

    // Cập nhật trạng thái active của các nút Subtab
    document.querySelectorAll('.fa-filter-tabs .fa-tab-item').forEach(b => {
        b.classList.remove('active');
        b.style.background = 'transparent';
        b.style.boxShadow = 'none';
    });
    const subtabBtn = document.getElementById(`subtab-cat-${cat}`);
    if (subtabBtn) {
        subtabBtn.classList.add('active');
        subtabBtn.style.background = '#ffffff';
        subtabBtn.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
    }

    loadSavedAuditResults(cat);
}

function filterAuditByGrade(grade) {
    // Tương thích ngược: map grade sang category
    const map = {
        'ALL': 'ALL',
        'CRITICAL': 'FLOW_ERROR',
        'WARNING': 'OVERDUE_SLA',
        'HEALTHY': 'HEALTHY'
    };
    filterAuditByCategory(map[grade] || 'ALL');
}

function renderSavedAuditTable(items) {
    const tbody = document.getElementById('faSavedTbody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:30px; color:#64748b;">Không có phiếu nào phù hợp với bộ lọc hiện tại.</td></tr>';
        return;
    }

    tbody.innerHTML = items.map((it, idx) => {
        const issues = it.issues || [];
        const isFlowErr = String(it.is_flow_error) === '1' || it.audit_category === 'FLOW_ERROR' || it.error_grade === 'CRITICAL';
        const isSlaOverdue = (String(it.is_sla_overdue) === '1' || it.audit_category === 'OVERDUE_SLA' || parseFloat(it.sla_hours || 0) > 48.0) && !isFlowErr;

        let categoryBadge = '';
        if (isFlowErr) {
            categoryBadge = '<span class="fa-badge" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-weight:700;">LỖI LUỒNG</span>';
        } else if (isSlaOverdue) {
            categoryBadge = '<span class="fa-badge" style="background:#fef3c7; color:#b45309; border:1px solid #fcd34d; font-weight:700;">QUÁ HẠN SLA</span>';
        } else {
            categoryBadge = '<span class="fa-badge" style="background:#dcfce7; color:#15803d; border:1px solid #86efac; font-weight:700;">HỢP LỆ</span>';
        }

        // Tạo tóm tắt chi tiết
        let detailParts = [];
        if (it.sla_hours) {
            const h = parseFloat(it.sla_hours);
            if (h > 0) {
                detailParts.push(`Thời gian bước: ${h.toFixed(1)}h làm việc (trừ T7/CN)`);
            }
        }
        if (it.reopen_count && parseInt(it.reopen_count, 10) > 0) {
            detailParts.push(`Reopen ${it.reopen_count} lần`);
        }

        const issuesNames = issues.filter(iss => iss.code !== 'SLA_INFO' && iss.code !== 'FLOW_INFO').map(iss => iss.name);
        if (issuesNames.length > 0) {
            detailParts.unshift(issuesNames.join('; '));
        } else if (it.error_title && it.error_grade !== 'HEALTHY') {
            detailParts.unshift(it.error_title);
        } else if (detailParts.length === 0) {
            detailParts.push('Luồng xử lý hoàn tất đúng hạn');
        }

        const detailSummary = detailParts.join(' — ');
        const srvType = it.service_type || 'Data Di động';
        const procName = it.process_name || 'Quy trình Chất lượng mạng';

        return `
            <tr style="cursor:pointer;" onclick="viewSingleAuditFromRow('${escapeHtml(String(it.ticket_id || it.ticket_code))}')" title="Bấm để xem chi tiết Timeline và luồng OneOSS">
                <td style="text-align:center; color:#64748b;">${idx + 1}</td>
                <td style="font-weight:700; color:#005baa;">${escapeHtml(it.ticket_code || String(it.ticket_id))}</td>
                <td style="font-family:'JetBrains Mono', monospace; font-weight:600; color:#0f172a;">${escapeHtml(it.phone || '--')}</td>
                <td>
                    <div style="font-weight:600; font-size:11.5px; color:#0f172a;">${escapeHtml(srvType)}</div>
                    <div style="font-size:10.5px; color:#64748b; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(procName)}">${escapeHtml(procName)}</div>
                </td>
                <td style="font-size:11px; color:#64748b;">${escapeHtml(it.request_date || '--')}</td>
                <td style="font-size:11px; color:#0f172a;">${escapeHtml(it.last_step_name || '--')}</td>
                <td style="text-align:center;">${categoryBadge}</td>
                <td style="font-size:11.5px; color:#334155; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(detailSummary)}">
                    ${escapeHtml(detailSummary)}
                </td>
                <td style="text-align:center;">
                    <button type="button" class="fa-btn fa-btn-secondary" style="height:26px; padding:0 8px; font-size:11px;" onclick="event.stopPropagation(); viewSingleAuditFromRow('${escapeHtml(String(it.ticket_id || it.ticket_code))}')">
                        Xem Luồng
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderBatchTableResults(tbodyId, items) {
    const tbody = document.getElementById(tbodyId);
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:#64748b;">Không có kết quả.</td></tr>';
        return;
    }

    tbody.innerHTML = items.map((it, idx) => {
        const diag = it.diagnostic || {};
        const master = it.master_ticket || {};
        const isFlowErr = diag.grade === 'CRITICAL' || diag.is_flow_error;
        const isSlaOverdue = diag.is_sla_overdue;

        let badge = '<span class="fa-badge fa-badge-healthy">HỢP LỆ</span>';
        if (isFlowErr) {
            badge = '<span class="fa-badge fa-badge-critical">LỖI LUỒNG</span>';
        } else if (isSlaOverdue || diag.grade === 'WARNING') {
            badge = '<span class="fa-badge fa-badge-warning">QUÁ HẠN SLA</span>';
        }

        const issuesSummary = (diag.issues || []).map(iss => iss.name).join('; ') || diag.title || '--';

        return `
            <tr style="cursor:pointer;" onclick="viewSingleAuditFromRow('${escapeHtml(String(it.ticket_id || it.ticket_code))}')">
                <td style="text-align:center; color:#64748b;">${idx + 1}</td>
                <td style="font-weight:700; color:#005baa;">${escapeHtml(it.ticket_code || String(it.ticket_id))}</td>
                <td style="font-family:'JetBrains Mono', monospace; font-weight:600;">${escapeHtml(it.phone || master.customerPhone || '--')}</td>
                <td style="font-size:11px; color:#64748b;">${escapeHtml(master.requestDate || '--')}</td>
                <td style="text-align:center;">${badge}</td>
                <td style="font-size:11.5px; color:#334155;">${escapeHtml(issuesSummary)}</td>
                <td style="text-align:center;">
                    <button type="button" class="fa-btn fa-btn-secondary" style="height:26px; padding:0 8px; font-size:11px;" onclick="event.stopPropagation(); viewSingleAuditFromRow('${escapeHtml(String(it.ticket_id || it.ticket_code))}')">
                        Xem Luồng
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function viewSingleAuditFromRow(query) {
    switchFlowAuditTab('single');
    submitSingleFlowAudit(query);
}

// Tiện ích xuất dữ liệu kết quả đối soát theo nhóm phân loại
function exportFlowAuditToCsv() {
    if (!auditSavedResults || auditSavedResults.length === 0) {
        alert('Chưa có dữ liệu để xuất file.');
        return;
    }

    let csvContent = "\uFEFFSTT,Mã Phiếu,Ticket ID,Số Điện Thoại,Dịch Vụ,Quy Trình TTS,Mã CCOS,Thời Điểm Tiếp Nhận,Bước Cuối Cùng,Trạng Thái OneOSS,Nhóm Phân Loại,Mức Độ Đánh Giá,SLA (Giờ),Số Lần Reopen,Chi Tiết Đánh Giá Luồng\n";
    auditSavedResults.forEach((it, idx) => {
        const issuesText = (it.issues || []).map(i => `[${i.severity}] ${i.name}`).join(' | ');
        const isFlowErr = String(it.is_flow_error) === '1' || it.audit_category === 'FLOW_ERROR' || it.error_grade === 'CRITICAL';
        const isSlaOverdue = (String(it.is_sla_overdue) === '1' || it.audit_category === 'OVERDUE_SLA' || parseFloat(it.sla_hours || 0) > 48.0) && !isFlowErr;
        
        let catText = 'Hợp Lệ';
        if (isFlowErr) {
            catText = 'Lỗi Luồng Hệ Thống';
        } else if (isSlaOverdue) {
            catText = 'Quá Hạn SLA CCOS';
        }

        const row = [
            idx + 1,
            `"${(it.ticket_code || '').replace(/"/g, '""')}"`,
            it.ticket_id || '',
            `"${it.phone || ''}"`,
            `"${(it.service_type || 'Data Di động').replace(/"/g, '""')}"`,
            `"${(it.process_name || 'Quy trình Chất lượng mạng').replace(/"/g, '""')}"`,
            it.ccos_id || '',
            `"${it.request_date || ''}"`,
            `"${(it.last_step_name || '').replace(/"/g, '""')}"`,
            `"${(it.oneoss_status_name || '').replace(/"/g, '""')}"`,
            `"${catText}"`,
            it.error_grade || '',
            it.sla_hours || '0',
            it.reopen_count || '0',
            `"${(issuesText || it.error_title || '').replace(/"/g, '""')}"`
        ];
        csvContent += row.join(",") + "\n";
    });

    const dateStr = new Date().toISOString().slice(0, 10);
    let fileName = `Bao_Cao_Ra_Soat_OneOSS_Toan_Bo_${dateStr}.csv`;
    if (currentFilterCategory === 'FLOW_ERROR') {
        fileName = `DS_Phieu_Loi_Luong_He_Thong_OneOSS_${dateStr}.csv`;
    } else if (currentFilterCategory === 'OVERDUE_SLA') {
        fileName = `DS_Phieu_Qua_Han_SLA_CCOS_${dateStr}.csv`;
    } else if (currentFilterCategory === 'HEALTHY') {
        fileName = `DS_Phieu_Quy_Trinh_Hop_Le_${dateStr}.csv`;
    }

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function strVal(v) {
    return v !== null && v !== undefined ? String(v) : '';
}
