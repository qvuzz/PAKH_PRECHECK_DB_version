let isRunning = false;
let currentAutoClose = true;

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function updateModeUI(autoClose) {
    currentAutoClose = !!autoClose;
    const chk = document.getElementById('chkAutoClose');
    if (chk) chk.checked = currentAutoClose;
    const chkApi = document.getElementById('chkAutoCloseApi');
    if (chkApi) chkApi.checked = currentAutoClose;
    const chkNew = document.getElementById('chkAutoCloseNew');
    if (chkNew) chkNew.checked = currentAutoClose;
    const chkUnified = document.getElementById('chkAutoCloseUnified');
    if (chkUnified) chkUnified.checked = currentAutoClose;

    const modeLabelBadge = document.getElementById('modeLabelBadge');
    const headerModeTag = document.getElementById('headerModeTag');

    if (currentAutoClose) {
        if (modeLabelBadge) {
            modeLabelBadge.className = 'badge-mode auto';
            modeLabelBadge.innerText = 'Bật: Tự động đóng (TTS Cũ & Mới)';
        }
        if (headerModeTag) {
            headerModeTag.style.color = '#15803d';
            headerModeTag.innerText = 'Chế độ: Tự động đóng (TTS Cũ & Mới)';
        }
    } else {
        if (modeLabelBadge) {
            modeLabelBadge.className = 'badge-mode manual';
            modeLabelBadge.innerText = 'Tắt: Đóng thủ công 100%';
        }
        if (headerModeTag) {
            headerModeTag.style.color = '#b45309';
            headerModeTag.innerText = 'Chế độ: Đóng thủ công 100%';
        }
    }
}

async function toggleAutoCloseUnified(isChecked) {
    try {
        updateModeUI(isChecked);
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                auto_close: isChecked,
                auto_close_mode: isChecked ? 'all' : 'none'
            })
        });
        loadTickets();
    } catch (e) {
        console.error("Lỗi cập nhật cấu hình tự động đóng:", e);
    }
}

async function toggleAutoCloseMode(isChecked) {
    return toggleAutoCloseUnified(isChecked);
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();

        isRunning = data.is_running;
        const currentEngine = data.engine || 'api';
        const isOldRunning = isRunning && (currentEngine === 'api' || currentEngine === 'selenium');
        const isNewRunning = isRunning && (currentEngine === 'tts_new');

        const btnStart = document.getElementById('btnStart');
        const btnStop = document.getElementById('btnStop');
        if (btnStart) btnStart.style.display = isOldRunning ? 'none' : 'flex';
        if (btnStop) btnStop.style.display = isOldRunning ? 'flex' : 'none';

        const btnStartApi = document.getElementById('btnStartApi');
        const btnStopApi = document.getElementById('btnStopApi');
        if (btnStartApi) btnStartApi.style.display = isOldRunning ? 'none' : 'flex';
        if (btnStopApi) btnStopApi.style.display = isOldRunning ? 'flex' : 'none';

        const btnStartNew = document.getElementById('btnStartNew');
        const btnStopNew = document.getElementById('btnStopNew');
        if (btnStartNew) btnStartNew.style.display = isNewRunning ? 'none' : 'flex';
        if (btnStopNew) btnStopNew.style.display = isNewRunning ? 'flex' : 'none';

        // Điều khiển Cụm điều khiển thống nhất (Unified)
        const btnStartUnified = document.getElementById('btnStartUnified');
        const btnStopUnified = document.getElementById('btnStopUnified');
        if (btnStartUnified) btnStartUnified.style.display = isRunning ? 'none' : 'inline-flex';
        if (btnStopUnified) btnStopUnified.style.display = isRunning ? 'inline-flex' : 'none';

        const dot = document.getElementById('statusDot');
        dot.className = 'status-dot';
        if (data.status === 'PROCESSING') dot.classList.add('processing');
        else if (data.status === 'WAITING') dot.classList.add('waiting');
        else if (isRunning) dot.classList.add('active');
        let msg = data.status_message || 'Sẵn sàng';
        if (msg.includes('Đã dừng')) {
            msg = 'Tiến trình: Đã dừng';
        }
        let displayStatus = data.status;
        if (data.status === 'PROCESSING') {
            displayStatus = 'ĐANG QUÉT TIỀN KIỂM';
        } else if (data.status === 'WAITING') {
            displayStatus = 'CHỜ CHU KỲ KẾ';
        } else if (data.status === 'IDLE') {
            displayStatus = 'SẴN SÀNG';
        }

        const statStatusEl = document.getElementById('statStatus');
        if (statStatusEl) statStatusEl.innerText = displayStatus;
        if (document.getElementById('statCycles')) document.getElementById('statCycles').innerText = data.total_cycles || 0;
        if (document.getElementById('currentStepText')) document.getElementById('currentStepText').innerText = data.current_step || '--';

        const pillStatus = document.getElementById('pillStatus');
        if (pillStatus) {
            pillStatus.className = 'stat-pill ' + (data.status === 'PROCESSING' ? 'processing' : (data.status === 'WAITING' ? 'waiting' : 'idle'));
        }

        // Cập nhật chỉ báo trạng thái quét riêng biệt theo từng module ở Sidebar
        const isOldDataScanning = (data.status === 'PROCESSING') && (currentEngine === 'api' || currentEngine === 'selenium');
        const isNewDataScanning = (data.status === 'PROCESSING') && (currentEngine === 'tts_new');
        
        const navOldSub = document.querySelector('#nav-tts_old_api-data .nav-item-sub');
        if (navOldSub) {
            navOldSub.innerHTML = isOldDataScanning 
                ? '<span style="color:#0284c7; font-weight:700;">⚡ Đang quét...</span>' 
                : 'Quét tự động';
        }
        const navNewSub = document.querySelector('#nav-tts_new-data .nav-item-sub');
        if (navNewSub) {
            navNewSub.innerHTML = isNewDataScanning 
                ? '<span style="color:#0284c7; font-weight:700;">⚡ Đang quét...</span>' 
                : 'Quét toàn bộ';
        }

        if (data.system_counts) {
            const sc = data.system_counts;
            const bOldData = document.getElementById('badgeOldData');
            const bOldVoice = document.getElementById('badgeOldVoice');
            const bOldApiData = document.getElementById('badgeOldApiData');
            const bOldApiVoice = document.getElementById('badgeOldApiVoice');
            const bNewData = document.getElementById('badgeNewData');
            const bNewVoice = document.getElementById('badgeNewVoice');
            const bTotalClosed = document.getElementById('badgeTotalClosed');
            const bTotalAll = document.getElementById('badgeTotalAll');

            if (bOldData) bOldData.innerText = sc.tts_old_data || 0;
            if (bOldVoice) bOldVoice.innerText = sc.tts_old_voice || 0;
            if (bOldApiData) bOldApiData.innerText = sc.tts_old_api_data || 0;
            if (bOldApiVoice) bOldApiVoice.innerText = sc.tts_old_api_voice || 0;
            if (bNewData) bNewData.innerText = sc.tts_new_data || 0;
            if (bNewVoice) bNewVoice.innerText = sc.tts_new_voice || 0;
            if (bTotalClosed) bTotalClosed.innerText = sc.total_closed || 0;
            if (bTotalAll) bTotalAll.innerText = sc.total_all || 0;

            const statTotal = document.getElementById('statTotalTickets');
            const statClosed = document.getElementById('statClosedTickets');
            if (statTotal) statTotal.innerText = (sc.today_total !== undefined ? sc.today_total : (sc.total_all || 0)).toLocaleString();
            if (statClosed) statClosed.innerText = (sc.today_closed !== undefined ? sc.today_closed : (sc.total_closed || 0)).toLocaleString();
        }

        const cb1 = document.getElementById('countdownBadge');
        const cb2 = document.getElementById('countdownBadgeApi');
        const cb3 = document.getElementById('countdownBadgeNew');
        const cbUnified = document.getElementById('countdownBadgeUnified');

        if (data.countdown_seconds > 0) {
            const m = Math.floor(data.countdown_seconds / 60);
            const s = data.countdown_seconds % 60;
            const cdText = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
            if (cb1) cb1.innerText = isOldRunning ? cdText : '--:--';
            if (cb2) cb2.innerText = isOldRunning ? cdText : '--:--';
            if (cb3) cb3.innerText = isNewRunning ? cdText : '--:--';
            if (cbUnified) cbUnified.innerText = isRunning ? cdText : '--:--';
        } else {
            if (cb1) cb1.innerText = '--:--';
            if (cb2) cb2.innerText = '--:--';
            if (cb3) cb3.innerText = '--:--';
            if (cbUnified) cbUnified.innerText = '--:--';
        }

        const isAutoCloseActive = (data.auto_close_mode !== 'none' && data.auto_close !== false);
        if (isAutoCloseActive !== currentAutoClose) {
            updateModeUI(isAutoCloseActive);
        }

        if (data.interval_minutes) {
            const inpInt = document.getElementById('inpIntervalUnified');
            if (inpInt && document.activeElement !== inpInt) {
                inpInt.value = data.interval_minutes;
            }
        }

        if (Array.isArray(data.scan_scopes) && typeof isScopeDropdownOpen !== 'undefined' && !isScopeDropdownOpen) {
            if (typeof syncScopeCheckboxes === 'function') {
                syncScopeCheckboxes(data.scan_scopes);
            }
        }

        // Render Logs
        const logs = data.logs || [];
        const term = document.getElementById('logTerminal');
        if (term) {
            const atBottom = term.scrollHeight - term.clientHeight <= term.scrollTop + 40;
            term.innerHTML = logs.map(l => `
                        <div class="log-line">
                            <span class="log-time">[${l.time}]</span>
                            <span class="log-level ${l.level}">[${l.level}]</span>
                            <span class="log-msg">${escapeHtml(l.message)}</span>
                        </div>
                    `).join('');
            if (atBottom) term.scrollTop = term.scrollHeight;
        }

        // Chỉ đếm lỗi nghiêm trọng thực tế (ERROR, CRITICAL, Exception)
        const errorLogs = logs.filter(l =>
            l.level === 'ERROR' || l.level === 'CRITICAL' ||
            (l.message && (l.message.includes('Exception') || l.message.includes('CRITICAL') || l.message.includes('Traceback')))
        );
        window.currentLiveErrCount = errorLogs.length;

        // Nếu có lỗi MỚI xuất hiện sau khi người dùng đã xem/xóa -> mới kích hoạt nhấp nháy lại
        if (window.currentLiveErrCount > (window.lastSeenErrorCount || 0)) {
            window.liveLogDismissed = false;
        }

        const hasError = !window.liveLogDismissed && (window.currentLiveErrCount > 0);
        const pillLog = document.getElementById('pillLiveLog');
        const logTxt = document.getElementById('liveLogStatusText');
        const errBadge = document.getElementById('liveLogErrorBadge');

        if (pillLog) {
            if (hasError) {
                pillLog.classList.add('has-error');
                if (logTxt) logTxt.innerText = 'CÓ LỖI!';
                if (errBadge) errBadge.style.display = 'inline-block';
            } else {
                pillLog.classList.remove('has-error');
                if (logTxt) logTxt.innerText = 'Bình thường';
                if (errBadge) errBadge.style.display = 'none';
            }
        }

    } catch (e) {
        console.error("Lỗi fetch status:", e);
    }
}

let lastTicketsSignature = "";
let currentTableTab = 'chua_dong';
let currentSystem = 'tts_old_api';
let currentService = 'data';

// PHÂN TRANG DANH SÁCH PHIẾU
let currentTicketPage = 1;
let currentTicketPageSize = 10;
let cachedTickets = [];

function changeTicketPage(page) {
    currentTicketPage = page;
    renderTicketsTable(true);
    const tbl = document.getElementById('tableTitleText');
    if (tbl) tbl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function changeTicketPageSize(size) {
    currentTicketPageSize = size;
    currentTicketPage = 1;
    renderTicketsTable(true);
}

function renderPaginationNav(currentPage, totalPages) {
    const nav = document.getElementById('paginationNav');
    if (!nav) return;
    if (totalPages <= 1) {
        nav.innerHTML = '';
        return;
    }

    let html = '';
    html += `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="changeTicketPage(1)" title="Trang đầu">&laquo;</button>`;
    html += `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="changeTicketPage(${currentPage - 1})" title="Trang trước">&lsaquo;</button>`;

    let pages = [];
    if (totalPages <= 7) {
        for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
        pages.push(1);
        let start = Math.max(2, currentPage - 1);
        let end = Math.min(totalPages - 1, currentPage + 1);

        if (currentPage <= 3) {
            end = 4;
        } else if (currentPage >= totalPages - 2) {
            start = totalPages - 3;
        }

        if (start > 2) pages.push('...');
        for (let i = start; i <= end; i++) pages.push(i);
        if (end < totalPages - 1) pages.push('...');
        pages.push(totalPages);
    }

    pages.forEach(p => {
        if (p === '...') {
            html += `<span class="page-ellipsis">&hellip;</span>`;
        } else {
            const activeClass = (p === currentPage) ? 'active' : '';
            html += `<button class="page-btn ${activeClass}" onclick="changeTicketPage(${p})">${p}</button>`;
        }
    });

    html += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="changeTicketPage(${currentPage + 1})" title="Trang sau">&rsaquo;</button>`;
    html += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="changeTicketPage(${totalPages})" title="Trang cuối">&raquo;</button>`;

    nav.innerHTML = html;
}

let currentClosedPeriod = 'all';
let currentClosedSource = 'all';
let currentClosedService = 'all';
let isHistoryStatsView = false;

function selectClosedSource(src) {
    currentClosedSource = src;
    document.querySelectorAll('#caSourcePills .ca-filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-src') === src);
    });
    if (isHistoryStatsView) {
        currentSystem = src;
    }
    loadClosedAnalytics();
}

function selectClosedService(srv) {
    currentClosedService = srv;
    const sel = document.getElementById('caServiceSelect');
    if (sel && sel.value !== srv) {
        sel.value = srv;
    }
    if (isHistoryStatsView) {
        currentService = srv;
    }
    loadClosedAnalytics();
}

function selectClosedPeriod(period) {
    currentClosedPeriod = period;
    document.querySelectorAll('#caPeriodPills .ca-filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-period') === period);
    });
    loadClosedAnalytics();
}

async function loadClosedAnalytics() {
    try {
        const res = await fetch(`/api/tickets/closed_stats?period=${encodeURIComponent(currentClosedPeriod)}&source=${encodeURIComponent(currentClosedSource)}&service_type=${encodeURIComponent(currentClosedService)}`);
        const data = await res.json();

        // 1. Cập nhật các thẻ KPI
        const elTotal = document.getElementById('caValTotal');
        const elAuto = document.getElementById('caValAuto');
        const elAutoPct = document.getElementById('caValAutoPercent');
        const elBarAuto = document.getElementById('caBarAuto');
        const elManual = document.getElementById('caValManual');
        const elManualPct = document.getElementById('caValManualPercent');
        const elSubManual = document.getElementById('caSubManual');
        const elToday = document.getElementById('caValToday');
        const elTtsNew = document.getElementById('caValTtsNew');
        const elTtsOld = document.getElementById('caValTtsOld');
        const elData = document.getElementById('caValData');
        const elVoice = document.getElementById('caValVoice');
        const elBadge = document.getElementById('caSourceBadge');

        if (elTotal) elTotal.innerText = (data.total || 0).toLocaleString();
        if (elAuto) elAuto.innerText = (data.auto_cnt || 0).toLocaleString();
        if (elAutoPct) elAutoPct.innerText = `${data.auto_percent || 0}%`;
        if (elBarAuto) elBarAuto.style.width = `${Math.min(100, data.auto_percent || 0)}%`;

        if (elManual) elManual.innerText = (data.manual_cnt || 0).toLocaleString();
        if (elManualPct) elManualPct.innerText = `${data.manual_percent || 0}%`;
        if (elSubManual) {
            if (data.staff_list && data.staff_list.length > 0) {
                const names = data.staff_list.map(s => `${s.name} (${s.count})`).join(', ');
                elSubManual.innerHTML = `KTV: <span style="font-weight:600; color:#b45309;">${escapeHtml(names)}</span>`;
            } else {
                elSubManual.innerText = "Phiếu cần can thiệp nghiệp vụ / mở lại";
            }
        }

        if (elToday) elToday.innerText = (data.today_cnt || 0).toLocaleString();
        if (elTtsNew) elTtsNew.innerText = (data.tts_new_cnt || 0).toLocaleString();
        if (elTtsOld) elTtsOld.innerText = (data.tts_old_cnt || 0).toLocaleString();
        if (elData) elData.innerText = (data.data_cnt || 0).toLocaleString();
        if (elVoice) elVoice.innerText = (data.voice_cnt || 0).toLocaleString();

        if (elBadge) {
            if (currentClosedSource === 'tts_new') elBadge.innerText = 'TTS Mới';
            else if (currentClosedSource === 'tts_old') elBadge.innerText = 'TTS Cũ';
            else elBadge.innerText = 'Tất cả nguồn';
        }

        // 2. Phân bổ theo nhận định tiền kiểm
        const diagList = document.getElementById('caDiagnosisList');
        const diagCount = document.getElementById('caDiagCount');
        if (diagCount) diagCount.innerText = `${(data.by_diagnosis || []).length} nhận định`;

        if (diagList) {
            if (!data.by_diagnosis || data.by_diagnosis.length === 0) {
                diagList.innerHTML = '<div style="text-align:center; padding:20px; color:#94a3b8; font-size:12px;">Chưa có dữ liệu nhận định trong mốc này.</div>';
            } else {
                diagList.innerHTML = data.by_diagnosis.map(item => {
                    let fillColor = 'linear-gradient(90deg, #64748b, #475569)';
                    const up = item.label.toUpperCase();
                    if (up.includes('BÌNH THƯỜNG')) fillColor = 'linear-gradient(90deg, #34d399, #059669)';
                    else if (up.includes('CHỜ TIỀN KIỂM')) fillColor = 'linear-gradient(90deg, #fbbf24, #d97706)';
                    else if (up.includes('BTOOLS') || up.includes('KHÓA') || up.includes('LỖI')) fillColor = 'linear-gradient(90deg, #f87171, #dc2626)';
                    else if (up.includes('LƯU LƯỢNG')) fillColor = 'linear-gradient(90deg, #a78bfa, #7c3aed)';
                    else if (up.includes('4G') || up.includes('SÓNG')) fillColor = 'linear-gradient(90deg, #38bdf8, #0284c7)';

                    return `
                                <div class="ca-diag-item">
                                    <div class="ca-diag-row">
                                        <span class="ca-diag-name" title="${escapeHtml(item.label)}">${escapeHtml(item.label)}</span>
                                        <span class="ca-diag-stat">${item.count} <small>(${item.percentage}%)</small></span>
                                    </div>
                                    <div class="ca-diag-track">
                                        <div class="ca-diag-fill" style="width: ${Math.min(100, item.percentage)}%; background: ${fillColor};"></div>
                                    </div>
                                </div>
                            `;
                }).join('');
            }
        }

        // 3. Biểu đồ xu hướng đóng theo ngày
        const trendBars = document.getElementById('caTrendBars');
        if (trendBars) {
            if (!data.daily_trend || data.daily_trend.length === 0) {
                trendBars.innerHTML = '<div style="margin:auto; font-size:12px; color:#94a3b8;">Chưa có dữ liệu xu hướng ngày.</div>';
            } else {
                const maxCnt = Math.max(...data.daily_trend.map(d => d.count), 1);
                trendBars.innerHTML = data.daily_trend.map(d => {
                    const pct = Math.max(12, Math.round((d.count / maxCnt) * 80));
                    return `
                                <div class="ca-trend-col" title="Ngày ${escapeHtml(d.date)}: ${d.count} phiếu">
                                    <span class="ca-trend-val">${d.count}</span>
                                    <div class="ca-trend-bar" style="height: ${pct}%;"></div>
                                    <span class="ca-trend-lbl">${escapeHtml(d.label)}</span>
                                </div>
                            `;
                }).join('');
            }
        }

        // 4. Top gói cước/dịch vụ
        const topPkg = document.getElementById('caTopPackages');
        if (topPkg) {
            if (!data.top_packages || data.top_packages.length === 0) {
                topPkg.innerHTML = '<span style="font-size:11.5px; color:#94a3b8;">Không có dữ liệu</span>';
            } else {
                topPkg.innerHTML = data.top_packages.map(p => `
                            <span class="ca-pkg-pill" title="${escapeHtml(p.name)}">
                                <span>${escapeHtml(p.name)}</span>
                                <b>${p.count}</b>
                            </span>
                        `).join('');
            }
        }

    } catch (err) {
        console.error("Lỗi nạp dashboard thống kê phiếu đã đóng:", err);
    }
}

function selectHistoryStats() {
    isHistoryStatsView = true;
    currentSystem = currentClosedSource;
    currentService = currentClosedService;
    currentTableTab = 'da_dong';

    // Highlight nav item
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById('nav-all-stats');
    if (activeBtn) activeBtn.classList.add('active');

    // Ẩn tabs header trên bảng
    const mainTabs = document.getElementById('mainTabsHeader');
    if (mainTabs) mainTabs.style.display = 'none';

    // Hiện dashboard thống kê
    const container = document.getElementById('closedAnalyticsContainer');
    if (container) container.style.display = 'block';

    // Ẩn hoàn toàn bảng danh sách phiếu
    const tableDataView = document.getElementById('tableDataView');
    if (tableDataView) tableDataView.style.display = 'none';

    const sel = document.getElementById('caServiceSelect');
    if (sel) sel.value = currentClosedService;

    loadClosedAnalytics();
}

function selectModule(sys, srv) {
    isHistoryStatsView = false;
    currentSystem = sys;
    currentService = srv;

    const mainTabs = document.getElementById('mainTabsHeader');
    if (mainTabs) mainTabs.style.display = 'flex';
    const analyticsBox = document.getElementById('closedAnalyticsContainer');
    if (analyticsBox) analyticsBox.style.display = 'none';
    const tableDataView = document.getElementById('tableDataView');
    if (tableDataView) tableDataView.style.display = 'block';

    // Highlight nav item
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(`nav-${sys}-${srv}`);
    if (activeBtn) activeBtn.classList.add('active');

    // Cột Mã Phiếu & Quy Trình luôn hiển thị cố định 12 cột để Cột 10 và 11 luôn chuẩn vị trí
    const thTicketCode = document.getElementById('thTicketCode');
    if (thTicketCode) {
        thTicketCode.style.display = 'table-cell';
    }

    // Cập nhật tiêu đề cột: Tóm tắt nội dung chỉ dùng cho Mobile Internet, các trường hợp khác là Nội dung phản ánh
    const thAiSummary = document.getElementById('thAiSummary');
    if (thAiSummary) {
        thAiSummary.innerText = (srv === 'data') ? 'Tóm Tắt Nội Dung PAKH' : 'Nội Dung Phản Ánh';
    }

    // Ẩn bộ lọc nguồn & loại PAKH vì đây là menu chuyên biệt của TTS
    const srcSel = document.getElementById('filterSourceSelect');
    if (srcSel) srcSel.style.display = 'none';
    const catSel = document.getElementById('filterCategorySelect');
    if (catSel) catSel.style.display = 'none';

    switchTableTab(currentTableTab);
}

function selectHistoryModule(tab = 'all') {
    isHistoryStatsView = false;
    currentSystem = 'all';
    currentService = 'all';

    const mainTabs = document.getElementById('mainTabsHeader');
    if (mainTabs) mainTabs.style.display = 'flex';
    const analyticsBox = document.getElementById('closedAnalyticsContainer');
    if (analyticsBox) analyticsBox.style.display = 'none';
    const tableDataView = document.getElementById('tableDataView');
    if (tableDataView) tableDataView.style.display = 'block';

    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById('nav-all-history');
    if (activeBtn) activeBtn.classList.add('active');

    // Đồng bộ hiển thị cột Mã Phiếu & Quy Trình cho tab Lịch Sử & Cơ Sở Dữ Liệu
    const thTicketCode = document.getElementById('thTicketCode');
    if (thTicketCode) {
        thTicketCode.style.display = 'table-cell';
    }

    const thAiSummary = document.getElementById('thAiSummary');
    if (thAiSummary) {
        thAiSummary.innerText = 'Nội Dung / Tóm Tắt';
    }

    const srcSel = document.getElementById('filterSourceSelect');
    if (srcSel) {
        srcSel.style.display = 'inline-block';
        srcSel.value = 'all';
    }
    const catSel = document.getElementById('filterCategorySelect');
    if (catSel) {
        catSel.style.display = 'inline-block';
        catSel.value = 'all';
    }

    switchTableTab(tab);
}

function onSourceFilterChange(val) {
    currentSystem = val;
    loadTickets(true, true);
}

function onCategoryFilterChange(val) {
    currentService = val;
    loadTickets(true, true);
}

function switchSystem(sys) {
    selectModule(sys, 'data');
}

async function startTtsNewScan() {
    const btn = document.getElementById('btnRunNowNew') || document.getElementById('btnTtsNewScan');
    if (btn) btn.disabled = true;
    const originalHtml = btn ? btn.innerHTML : '';
    if (btn) btn.innerHTML = '<span class="status-dot processing" style="display:inline-block; margin-right:6px;"></span> Đang quét & tiền kiểm...';
    try {
        const res = await fetch('/api/ttsnew/run-now', { method: 'POST' });
        const data = await res.json();
        if (!data.success) {
            alert(data.message || "Không thể khởi động quét TTS Mới.");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
            return;
        }

        let checkAttempts = 0;
        const interval = setInterval(async () => {
            checkAttempts++;
            const stRes = await fetch('/api/status');
            const stData = await stRes.json();
            await fetchStatus();
            await loadTickets(true);
            if (stData.status !== 'PROCESSING' || checkAttempts > 45) {
                clearInterval(interval);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
                await loadTickets(true);
                await fetchStatus();
            }
        }, 2000);

    } catch (e) {
        alert("Lỗi kết nối khi quét TTS Mới: " + e);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
}

async function startOldVoiceScan() {
    return startTtsOldApiVoiceScan();
}

async function startNewVoiceScan() {
    const btn = document.getElementById('btnScanNewVoice');
    const originalHtml = btn ? btn.innerHTML : 'Quét Phiếu Thoại/SMS';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="status-dot processing" style="display:inline-block; margin-right:6px;"></span> Đang kết nối...';
    }
    try {
        const res = await fetch('/api/ttsnew/scan_voice', { method: 'POST' });
        const data = await res.json();
        if (!data.success) {
            alert(data.message || "Không thể quét phiếu Thoại/SMS TTS Mới.");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
            return;
        }

        let checkAttempts = 0;
        const interval = setInterval(async () => {
            checkAttempts++;
            const stRes = await fetch('/api/status');
            const stData = await stRes.json();
            if (stData.status !== 'PROCESSING' || checkAttempts > 35) {
                clearInterval(interval);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
                await loadTickets(true);
                await fetchStatus();

                const vCount = (stData.system_counts && stData.system_counts.tts_new_voice) || 0;
                if (vCount === 0) {
                    alert("Đã quét xong: Bảng sự cố TTS Mới hiện tại không có phiếu Thoại / SMS nào.");
                } else {
                    alert(`Đã nạp & tiền kiểm tra thành công ${vCount} phiếu Thoại / SMS từ TTS Mới!`);
                }
            }
        }, 2000);

    } catch (e) {
        alert("Lỗi kết nối khi quét phiếu Thoại/SMS: " + e);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
}

function switchTableTab(tab) {
    currentTableTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

    let srvName = 'Mobile Internet';
    if (currentService === 'voice_sms') srvName = 'Thoại / SMS';
    else if (currentService === 'all') srvName = '';

    let title = '';
    if (currentSystem === 'all' || !srvName) {
        if (tab === 'chua_dong') title = 'Phiếu Cần Xử Lý (Chưa Đóng)';
        else if (tab === 'da_dong') title = 'Lịch Sử Phiếu Đã Đóng (Chỉ Xem)';
        else title = 'Toàn Bộ Cơ Sở Dữ Liệu (Tổng hợp tất cả trạng thái)';
    } else {
        if (tab === 'chua_dong') title = `Phiếu ${srvName}`;
        else if (tab === 'da_dong') title = `Phiếu ${srvName} Đã Đóng`;
        else title = `Tất Cả Phiếu ${srvName}`;
    }

    if (tab === 'chua_dong') {
        if (document.getElementById('tabActive')) document.getElementById('tabActive').classList.add('active');
    } else if (tab === 'da_dong') {
        if (document.getElementById('tabClosed')) document.getElementById('tabClosed').classList.add('active');
    } else if (tab === 'all') {
        if (document.getElementById('tabAll')) document.getElementById('tabAll').classList.add('active');
    }

    // Đồng bộ highlight menu sidebar DỮ LIỆU & LỊCH SỬ nếu đang ở chế độ xem tổng hợp
    if (currentSystem === 'all') {
        document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
        const navTarget = document.getElementById('nav-all-history');
        if (navTarget) navTarget.classList.add('active');
    }

    // Chỉ hiển thị dashboard thống kê khi đang ở phân hệ Thống Kê Phiếu Đã Đóng
    if (!isHistoryStatsView) {
        const analyticsBox = document.getElementById('closedAnalyticsContainer');
        if (analyticsBox) analyticsBox.style.display = 'none';
        const tableDataView = document.getElementById('tableDataView');
        if (tableDataView) tableDataView.style.display = 'block';
    }

    const titleElem = document.getElementById('tableTitleText');
    if (titleElem) titleElem.textContent = title;

    loadTickets(true, true);
}

async function precheckSingleTicket(phone, incidentTime, btnElem) {
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = 'Đang kiểm...';
        btnElem.style.opacity = '0.75';
    }
    try {
        const res = await fetch('/api/tickets/precheck_one', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, incident_time: incidentTime })
        });
        const data = await res.json();
        if (data.success) {
            lastTicketsSignature = "";
            await loadTickets(true);
            await fetchStatus();
        } else {
            alert(data.error || "Không thể thực hiện tiền kiểm.");
            if (btnElem) {
                btnElem.disabled = false;
                btnElem.innerHTML = 'Tiền kiểm Core';
                btnElem.style.opacity = '1';
            }
        }
    } catch (e) {
        alert("Lỗi khi gửi yêu cầu tiền kiểm: " + e);
        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = 'Tiền kiểm Core';
            btnElem.style.opacity = '1';
        }
    }
}

async function loadTickets(force = false, resetPage = false) {
    if (isHistoryStatsView) {
        return;
    }
    if (resetPage) {
        currentTicketPage = 1;
    }
    try {
        const activeEl = document.activeElement;
        const isEditing = activeEl && activeEl.closest('#ticketsBody') && activeEl.tagName === 'TEXTAREA';
        if (isEditing && !force) {
            return;
        }

        const search = document.getElementById('searchInput').value;
        const statusFilter = document.getElementById('filterStatus').value;
        const res = await fetch(`/api/tickets?search=${encodeURIComponent(search)}&status=${encodeURIComponent(statusFilter)}&tab=${encodeURIComponent(currentTableTab)}&source=${encodeURIComponent(currentSystem)}&service_type=${encodeURIComponent(currentService)}`);
        const data = await res.json();
        const tickets = data.tickets || [];

        if (data.system_counts) {
            const sc = data.system_counts;
            const bOldData = document.getElementById('badgeOldData');
            const bOldVoice = document.getElementById('badgeOldVoice');
            const bOldApiData = document.getElementById('badgeOldApiData');
            const bOldApiVoice = document.getElementById('badgeOldApiVoice');
            const bNewData = document.getElementById('badgeNewData');
            const bNewVoice = document.getElementById('badgeNewVoice');
            const bTotalClosed = document.getElementById('badgeTotalClosed');
            const bTotalAll = document.getElementById('badgeTotalAll');

            if (bOldData) bOldData.innerText = sc.tts_old_data || 0;
            if (bOldVoice) bOldVoice.innerText = sc.tts_old_voice || 0;
            if (bOldApiData) bOldApiData.innerText = sc.tts_old_api_data || 0;
            if (bOldApiVoice) bOldApiVoice.innerText = sc.tts_old_api_voice || 0;
            if (bNewData) bNewData.innerText = sc.tts_new_data || 0;
            if (bNewVoice) bNewVoice.innerText = sc.tts_new_voice || 0;
            if (bTotalClosed) bTotalClosed.innerText = sc.total_closed || 0;
            if (bTotalAll) bTotalAll.innerText = sc.total_all || 0;

            const statTotal = document.getElementById('statTotalTickets');
            const statClosed = document.getElementById('statClosedTickets');
            if (statTotal) statTotal.innerText = (sc.today_total !== undefined ? sc.today_total : (sc.total_all || 0)).toLocaleString();
            if (statClosed) statClosed.innerText = (sc.today_closed !== undefined ? sc.today_closed : (sc.total_closed || 0)).toLocaleString();
        }

        if (document.getElementById('badgeActiveCount')) document.getElementById('badgeActiveCount').innerText = data.active_count || 0;
        if (document.getElementById('badgeClosedCount')) document.getElementById('badgeClosedCount').innerText = data.closed_count || 0;
        if (document.getElementById('badgeAllCount')) document.getElementById('badgeAllCount').innerText = data.total_count || 0;

        cachedTickets = tickets;
        renderTicketsTable(force);

    } catch (e) {
        console.error("Lỗi fetch tickets:", e);
    }
}

// Quản lý trạng thái mở rộng chi tiết của các dòng phiếu (giữ nguyên khi tự động làm mới)
let expandedTicketKeys = new Set();

function toggleTicketRow(ticketKey, event) {
    if (event) event.stopPropagation();
    const detailRow = document.getElementById(`row-detail-${ticketKey}`);
    const mainRow = document.getElementById(`row-main-${ticketKey}`);
    const btn = document.getElementById(`btn-toggle-${ticketKey}`);
    if (!detailRow) return;

    if (expandedTicketKeys.has(ticketKey)) {
        expandedTicketKeys.delete(ticketKey);
        detailRow.style.display = 'none';
        if (mainRow) mainRow.classList.remove('is-row-expanded');
        if (btn) {
            btn.classList.remove('is-expanded');
            btn.title = 'Bấm để xem chi tiết';
        }
    } else {
        expandedTicketKeys.add(ticketKey);
        detailRow.style.display = 'table-row';
        if (mainRow) mainRow.classList.add('is-row-expanded');
        if (btn) {
            btn.classList.add('is-expanded');
            btn.title = 'Bấm để thu nhỏ lại';
        }
        setTimeout(() => {
            detailRow.querySelectorAll('textarea').forEach(ta => {
                ta.style.height = 'auto';
                ta.style.height = Math.max(55, ta.scrollHeight + 4) + 'px';
            });
        }, 15);
    }
}

function syncCompactToDetail(ticketKey, field, val) {
    const detailTa = document.getElementById(`textarea-detail-${field}-${ticketKey}`);
    if (detailTa) {
        detailTa.value = val;
    }
}

function syncDetailToCompact(ticketKey, field, val) {
    const compactInp = document.getElementById(`input-compact-${field === 'comment' ? 'comment' : 'plan'}-${ticketKey}`);
    if (compactInp) {
        compactInp.value = val;
    }
}

function renderTicketsTable(force = false) {
    const tbody = document.getElementById('ticketsBody');
    const pagContainer = document.getElementById('ticketsPaginationContainer');
    if (!tbody) return;

    // Bảng luôn giữ cố định 12 cột: Cột 10 = Ý Kiến Phân Tích, Cột 11 = Nội Dung Phản Hồi
    const thTicketCode = document.getElementById('thTicketCode');
    if (thTicketCode) {
        thTicketCode.style.display = 'table-cell';
    }
    const ticketCodeDisplay = '';

    const totalItems = cachedTickets.length;
    if (totalItems === 0) {
        let emptyMsg = 'Chưa có dữ liệu phiếu phản ánh trong phân hệ này.';
        if (currentTableTab === 'chua_dong') {
            emptyMsg = 'Hiện không có phiếu nào cần xử lý hoặc toàn bộ phiếu đã được giải quyết.';
        } else if (currentTableTab === 'da_dong') {
            emptyMsg = 'Chưa có phiếu nào trong danh sách lịch sử đã đóng của phân hệ này.';
        }
        tbody.innerHTML = `<tr><td colspan="13" style="text-align:center; padding:40px; color:var(--text-muted); font-size:13px;">${emptyMsg}</td></tr>`;
        if (pagContainer) pagContainer.style.display = 'none';
        lastTicketsSignature = "EMPTY_" + currentTableTab + "_" + currentSystem + "_" + currentService;
        return;
    }

    // Tính toán số trang & vị trí trang
    let pageSizeNum = (currentTicketPageSize === 'all') ? totalItems : (parseInt(currentTicketPageSize, 10) || 10);
    let totalPages = Math.max(1, Math.ceil(totalItems / pageSizeNum));

    if (currentTicketPage < 1) currentTicketPage = 1;
    if (currentTicketPage > totalPages) currentTicketPage = totalPages;

    let startIndex = (currentTicketPageSize === 'all') ? 0 : (currentTicketPage - 1) * pageSizeNum;
    let endIndex = Math.min(startIndex + pageSizeNum, totalItems);
    let pageTickets = (currentTicketPageSize === 'all') ? cachedTickets : cachedTickets.slice(startIndex, endIndex);

    // Cập nhật thanh phân trang
    const rangeText = document.getElementById('pageRangeText');
    const totalText = document.getElementById('pageTotalItemsText');
    if (rangeText) rangeText.innerText = `${startIndex + 1} - ${endIndex}`;
    if (totalText) totalText.innerText = totalItems.toLocaleString();
    if (pagContainer) pagContainer.style.display = 'flex';
    renderPaginationNav(currentTicketPage, totalPages);

    const newSignature = JSON.stringify(pageTickets) + '_' + currentTicketPage + '_' + currentAutoClose + '_' + currentTableTab + '_' + currentSystem + '_' + currentTicketPageSize;
    if (!force && newSignature === lastTicketsSignature) {
        return;
    }
    lastTicketsSignature = newSignature;

    tbody.innerHTML = pageTickets.map((t, idx) => {
        const globalIdx = startIndex + idx;
        const ticketKey = (t.phone + '_' + (t.incident_time || t.ticket_code || idx)).replace(/[^a-zA-Z0-9]/g, '_');
        const isExpanded = expandedTicketKeys.has(ticketKey);

        let badgeClass = 'badge-gray';
        if (t.status.includes('BÌNH THƯỜNG') || t.status.includes('VPN')) badgeClass = 'badge-green';
        else if (t.status.includes('YẾU') || t.status.includes('GÓI')) badgeClass = 'badge-yellow';

        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const endD = `${pad(now.getDate())}${pad(now.getMonth() + 1)}${now.getFullYear()}`;
        const past = new Date(now.getTime() - 4 * 24 * 60 * 60 * 1000);
        const startD = `${pad(past.getDate())}${pad(past.getMonth() + 1)}${past.getFullYear()}`;
        const btoolsUrl = `http://10.159.21.241:9267/B_tools_v2/data_view.jsp?name=${t.phone}&start_d=${startD}&end_d=${endD}&submit=T%C3%ACm+Ki%E1%BA%BFm`;

        let actionHtml = '';
        let compactActionHtml = '';
        const isTtsNew = (t.source === 'tts_new' || currentSystem === 'tts_new');
        const isTtsOldApi = (t.source === 'tts_old_api' || currentSystem === 'tts_old_api');
        let cleanTicketCode = (t.ticket_code || '').split('\n')[0].trim();
        if (cleanTicketCode.endsWith('.0') && !isNaN(Number(cleanTicketCode))) {
            cleanTicketCode = cleanTicketCode.slice(0, -2);
        }
        const reopenCount = parseInt(t.reopen_count || 0, 10);

        if (t.ticket_status === 'Đã đóng' || t.ticket_status === 'Da dong') {
            actionHtml = `
                        <div style="display:flex; flex-direction:column; align-items:center; gap:3px;">
                            <span class="badge-status badge-green" style="font-weight:700; padding:4px 8px; font-size:11px;">ĐÃ ĐÓNG</span>
                        </div>
                    `;
            compactActionHtml = `<span class="badge-status badge-green" style="font-weight:700; padding:2px 6px; font-size:10px;">ĐÃ ĐÓNG</span>`;
        } else if (isTtsNew) {
            const hasProfile = t.real_packages && t.real_packages.includes('Radio:');
            const precheckBtn = hasProfile
                ? `<span class="badge-status badge-green" style="font-size:10px; padding:3px 6px; font-weight:700;">Đã kiểm Core</span>`
                : `<button class="btn-precheck-blue" onclick="precheckSingleTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để tiền kiểm tra Core tức thì">Tiền kiểm Core</button>`;

            let stageBadge = '';
            if (reopenCount > 0) {
                stageBadge = `<span class="badge-status" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-size:9.5px; padding:2px 6px; font-weight:700;" title="THÔNG TIN MỞ LẠI TTS: Số lần mở lại là ${reopenCount}. Không tự động đóng, yêu cầu KTV kiểm tra!">KHÔNG TỰ ĐÓNG</span>`;
            } else if (t.ticket_status === 'Chờ đóng lần 2') {
                stageBadge = `<span class="badge-status" style="background:#fef3c7; color:#b45309; border:1px solid #fde68a; font-size:10px; padding:2px 6px; font-weight:700;">Chờ lần 2</span>`;
            } else if (t.ticket_status === 'Phiếu lỗi' || (t.ticket_status && t.ticket_status.includes('lỗi'))) {
                stageBadge = `<span class="badge-status" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-size:10px; padding:2px 6px; font-weight:700;" title="Hệ thống TTS Mới chưa đóng được phiếu này (TTS Mới đang hoàn thiện)">Phiếu lỗi</span>`;
            } else if (currentTableTab === 'all') {
                stageBadge = `<span class="badge-status badge-yellow" style="font-size:10px; padding:2px 6px; font-weight:700;">CHƯA ĐÓNG</span>`;
            }

            actionHtml = `
                        <div style="display:flex; flex-direction:column; align-items:center; gap:4px;">
                            ${precheckBtn}
                            ${stageBadge}
                            <div style="display:flex; gap:4px; margin-top:2px;">
                                <button class="btn-close-green" style="padding:4px 8px; font-size:10.5px; ${reopenCount > 0 ? 'background:#ea580c; border-color:#c2410c;' : ''}" onclick="closeTtsNewTicketApi('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this, ${reopenCount})" title="${reopenCount > 0 ? 'Phiếu đã mở lại ' + reopenCount + ' lần. Bấm để KTV xác nhận và đóng thủ công' : 'Tự động chuyển bước / đóng phiếu (Vòng 1 -> Vòng 2)'}">
                                    Đóng phiếu
                                </button>
                                <button class="btn-sm btn-outline" style="padding:4px 6px; font-size:10px;" onclick="openTtsNewTicketDetail('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this)" title="Mở trang chi tiết phiếu trên TTS Mới">
                                    Mở TTS
                                </button>
                            </div>
                        </div>
                    `;

            compactActionHtml = `
                        <div style="display:inline-flex; align-items:center; justify-content:center; gap:3px;">
                            <button class="btn-close-green" style="padding:2px 6px; font-size:10px; height:24px; line-height:1; ${reopenCount > 0 ? 'background:#ea580c; border-color:#c2410c;' : ''}" onclick="closeTtsNewTicketApi('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this, ${reopenCount})" title="Đóng phiếu TTS Mới">
                                Đóng
                            </button>
                            <button class="btn-sm btn-outline" style="padding:2px 5px; font-size:10px; height:24px; line-height:1; display:inline-flex; align-items:center; justify-content:center;" onclick="openTtsNewTicketDetail('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this)" title="Mở chi tiết trên TTS Mới">
                                <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
                            </button>
                        </div>
                    `;
        } else {
            const statusBadgeAll = (currentTableTab === 'all')
                ? `<span class="badge-status badge-yellow" style="font-size:10px; padding:2px 6px; font-weight:700; margin-bottom:2px;">CHƯA ĐÓNG</span>`
                : '';
            if (currentService === 'voice_sms' || (currentTableTab === 'all' && t.service_type === 'voice_sms')) {
                const hasProfile = t.real_packages && t.real_packages.includes('Radio:');
                const precheckBtn = hasProfile
                    ? `<span class="badge-status badge-green" style="font-size:10px; padding:3px 6px; font-weight:700;">Đã kiểm Core</span>`
                    : `<button class="btn-precheck-blue" onclick="precheckSingleTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để tiền kiểm tra Core tức thì">Tiền kiểm Core</button>`;
                actionHtml = `
                            <div style="display:flex; flex-direction:column; align-items:center; gap:4px;">
                                ${statusBadgeAll}
                                ${precheckBtn}
                                <button class="btn-close-green" style="padding:4px 8px; font-size:10.5px;" onclick="closeTtsOldApiTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để đóng phiếu">
                                    Đóng phiếu
                                </button>
                            </div>
                        `;
            } else {
                if (t.can_close) {
                    actionHtml = `
                                <div style="display:flex; flex-direction:column; align-items:center; gap:4px;">
                                    ${statusBadgeAll}
                                    <button class="btn-close-green" onclick="closeTtsOldApiTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để đóng phiếu ngay">
                                        <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                                        Đóng phiếu
                                    </button>
                                </div>
                            `;
                } else {
                    actionHtml = `
                                <div style="display:flex; flex-direction:column; align-items:center; gap:4px;">
                                    ${statusBadgeAll}
                                    <span class="badge-close-yellow" title="${t.cannot_close_reason || 'Chưa đủ điều kiện tự động đóng, dành cho KTV kiểm tra xử lý'}">
                                        <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>
                                        KTV xử lý
                                    </span>
                                    <button class="btn-close-green" style="padding:4px 8px; font-size:10.5px; margin-top:2px;" onclick="closeTtsOldApiTicket('${t.phone}', '${t.incident_time}', this)" title="KTV kiểm tra ý kiến phân tích & phương án rồi bấm để đóng thủ công qua API">
                                        Đóng thủ công
                                    </button>
                                </div>
                            `;
                }
            }

            compactActionHtml = `
                        <button class="btn-close-green" style="padding:2px 7px; font-size:10px; height:24px; line-height:1;" onclick="closeTtsOldApiTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để đóng phiếu TTS Cũ">
                            Đóng
                        </button>
                    `;
        }

        // Tóm tắt nội dung chỉ dùng cho Mobile Internet. Các trường hợp khác chỉ đưa nội dung phản ánh vào.
        const isDataTicket = (currentService === 'data') || (currentService === 'all' && t.package_title && (t.package_title.toLowerCase().includes('data') || t.package_title.toLowerCase().includes('internet')));

        let aiSummaryHtml = '--';
        let compactSummaryHtml = '--';
        let compactSummaryTooltip = '';
        if (isDataTicket && t.ai_summary && t.ai_summary !== 'null' && t.ai_summary.trim() !== '' && t.ai_summary !== t.ticket_content) {
            const cleanSummaryText = t.ai_summary.replace(/\[?AI\]?[:\-\s]*/gi, '').trim();
            const lines = cleanSummaryText.split('\n').map(l => l.trim().replace(/^\[?AI\]?[:\-\s]*/gi, '')).filter(l => l.length > 0);
            compactSummaryTooltip = lines.join(' | ');
            compactSummaryHtml = escapeHtml(lines.join(' • '));
            aiSummaryHtml = `
                        <div style="font-size:11.5px; line-height:1.45;">
                            <div style="display:inline-flex; align-items:center; gap:4px; margin-bottom:6px; font-size:10.5px; font-weight:700; color:#0369a1; background:#f0f9ff; border:1px solid #bae6fd; padding:2px 8px; border-radius:4px;">
                                Tóm Tắt Nội Dung
                            </div>
                            ${lines.map(line => {
                const colonIdx = line.indexOf(':');
                if (colonIdx !== -1) {
                    const label = line.substring(0, colonIdx);
                    const val = line.substring(colonIdx + 1).trim();
                    return `<div style="margin-bottom:3px;"><span style="color:#475569; font-weight:600;">${escapeHtml(label)}:</span> <span style="color:#0f172a; font-weight:500;">${escapeHtml(val)}</span></div>`;
                }
                return `<div>${escapeHtml(line)}</div>`;
            }).join('')}
                            ${t.ticket_content ? `
                                <details style="margin-top:6px; font-size:10.5px; border-top:1px dashed #cbd5e1; padding-top:4px;">
                                    <summary style="cursor:pointer; color:#0369a1; font-weight:600;">Xem phản ánh gốc</summary>
                                    <div style="margin-top:4px; max-height:85px; overflow-y:auto; color:#64748b; font-style:italic; line-height:1.35; background:#f8fafc; padding:4px 6px; border-radius:4px; border:1px solid #e2e8f0;">${escapeHtml(t.ticket_content)}</div>
                                </details>
                            ` : ''}
                        </div>
                    `;
        } else {
            const content = t.ticket_content || (t.ai_summary && t.ai_summary !== 'null' ? t.ai_summary : '');
            if (content) {
                compactSummaryTooltip = content;
                compactSummaryHtml = escapeHtml(content.replace(/\n/g, ' '));
                aiSummaryHtml = `<div style="font-size:11.5px; color:#1e293b; line-height:1.45; word-break:break-word;">${escapeHtml(content)}</div>`;
            }
        }

        // HẠ TẦNG (RAT TYPES) - CÁCH 1: HIỂN THỊ RÕ CÔNG NGHỆ 4G / 3G / 5G
        let ratTypesHtml = '--';
        let compactRatHtml = '--';
        if (t.rat_types && t.rat_types !== '--') {
            const rawUpper = t.rat_types.toUpperCase();
            const knownTechs = ['5G', '4G', '3G', '2G'];
            const detected = knownTechs.filter(tech => rawUpper.includes(tech));

            let displayTech = '';
            if (detected.length > 0) {
                displayTech = detected.join(' / ');
            } else {
                displayTech = t.rat_types.replace(/Sóng\s*/gi, '').trim();
            }

            let badgeClass = 'badge-rat-4g';
            if (displayTech.includes('3G') || displayTech.includes('2G')) {
                badgeClass = 'badge-rat-3g';
            } else if (displayTech.toLowerCase().includes('báo hiệu') || displayTech.toLowerCase().includes('bao hieu')) {
                badgeClass = 'badge-rat-signal';
            }
            compactRatHtml = `<span class="table-rat-badge ${badgeClass}" title="${escapeHtml(t.rat_types)}">${escapeHtml(displayTech)}</span>`;

            const rats = t.rat_types.split(',').map(r => r.trim()).filter(r => r);
            ratTypesHtml = rats.map(r => {
                let bClass = 'badge-rat-4g';
                if (r.includes('3G') || r.includes('2G')) {
                    bClass = 'badge-rat-3g';
                } else if (r.toLowerCase().includes('báo hiệu') || r.toLowerCase().includes('bao hieu')) {
                    bClass = 'badge-rat-signal';
                }
                return `<span class="table-rat-badge ${bClass}" style="display:block; margin-bottom:3px; text-align:center; white-space:nowrap;">${escapeHtml(r)}</span>`;
            }).join('');
        }

        let incTimeHtml = '--';
        if (t.incident_time && t.incident_time !== '--') {
            const parts = t.incident_time.split(' ');
            if (parts.length >= 2) {
                incTimeHtml = `<div style="color:#b45309; font-weight:700; font-size:11px;">${escapeHtml(parts[0])}</div><div style="color:#64748b; font-size:10.5px; font-weight:600; margin-top:2px;">${escapeHtml(parts.slice(1).join(' '))}</div>`;
            } else {
                incTimeHtml = `<span style="color:#b45309; font-weight:700; font-size:11px;">${escapeHtml(t.incident_time)}</span>`;
            }
        }

        let pkgHtml = '--';
        let compactProfileHtml = '--';
        let compactProfileTooltip = '';
        if (t.real_packages && t.real_packages !== '--') {
            const raw = t.real_packages;
            compactProfileTooltip = raw.replace(/\\n/g, ' | ').replace(/\n/g, ' | ');
            
            const lines = raw.split('\\n');
            let currentSection = '';
            let sapcLines = [];
            let btoolsLines = [];
            let radioVal = '';
            let hssVal = '';
            let ipVal = '';
            let namVal = '';
            let isNamLocked = false;

            lines.forEach(line => {
                const trimmed = line.trim();
                if (trimmed.startsWith('Hồ sơ:')) {
                    let info = trimmed.replace('Hồ sơ:', '').trim();
                    if (info.includes('SAPC:')) {
                        const sIdx = info.indexOf('SAPC:');
                        let sapcPart = info.substring(sIdx + 5).trim();
                        info = info.substring(0, sIdx).trim();
                        if (sapcPart.includes('BTools:')) {
                            const bIdx = sapcPart.indexOf('BTools:');
                            const bPart = sapcPart.substring(bIdx + 7).trim();
                            sapcPart = sapcPart.substring(0, bIdx).trim();
                            if (bPart) btoolsLines.push(bPart);
                        }
                        if (sapcPart) sapcLines.push(sapcPart);
                    }
                    const tags = info.split('|').map(tag => tag.trim());
                    tags.forEach(tTrim => {
                        if (tTrim.startsWith('Radio:')) {
                            radioVal = tTrim.replace('Radio:', '').trim();
                        } else if (tTrim.startsWith('HSS:')) {
                            hssVal = tTrim.replace('HSS:', '').trim();
                        } else if (tTrim.startsWith('IP:')) {
                            ipVal = tTrim.replace('IP:', '').trim();
                        } else if (tTrim.startsWith('NAM:') || tTrim.includes('Khóa GPRS') || tTrim.includes('Mở GPRS')) {
                            namVal = tTrim;
                            if (tTrim.includes('NAM: 1') || tTrim.includes('Khóa GPRS')) {
                                isNamLocked = true;
                            }
                        }
                    });
                } else if (trimmed.startsWith('SAPC:')) {
                    currentSection = 'sapc';
                    let rest = trimmed.replace('SAPC:', '').trim();
                    if (rest.includes('BTools:')) {
                        const bIdx = rest.indexOf('BTools:');
                        const bPart = rest.substring(bIdx + 7).trim();
                        rest = rest.substring(0, bIdx).trim();
                        if (bPart) btoolsLines.push(bPart);
                    }
                    if (rest) sapcLines.push(rest);
                } else if (trimmed.startsWith('BTools:')) {
                    currentSection = 'btools';
                    const rest = trimmed.replace('BTools:', '').trim();
                    if (rest) btoolsLines.push(rest);
                } else if (trimmed) {
                    if (currentSection === 'sapc') {
                        let rest = trimmed;
                        if (rest.includes('BTools:')) {
                            const bIdx = rest.indexOf('BTools:');
                            const bPart = rest.substring(bIdx + 7).trim();
                            rest = rest.substring(0, bIdx).trim();
                            if (bPart) btoolsLines.push(bPart);
                        }
                        if (rest) sapcLines.push(rest);
                    } else if (currentSection === 'btools') {
                        btoolsLines.push(trimmed);
                    }
                }
            });

            let sapcItems = [];
            if (sapcLines.length > 0) {
                const fullText = sapcLines.join(' \n ');
                const parts = fullText.split(/•|\n/).map(p => p.trim()).filter(p => p && !p.startsWith('SAPC:'));
                parts.forEach(part => {
                    let clean = part.replace(/^SAPC:\s*/gi, '').trim();
                    if (!clean) return;
                    if (clean.includes('BTools:')) {
                        const bIdx = clean.indexOf('BTools:');
                        const bPart = clean.substring(bIdx + 7).trim();
                        clean = clean.substring(0, bIdx).trim();
                        if (bPart) btoolsLines.push(bPart);
                    }
                    if (!clean) return;
                    const parenIdx = clean.indexOf('(');
                    if (parenIdx !== -1) {
                        sapcItems.push({
                            name: clean.substring(0, parenIdx).trim(),
                            dates: clean.substring(parenIdx).trim()
                        });
                    } else {
                        sapcItems.push({
                            name: clean,
                            dates: ''
                        });
                    }
                });
            }

            let gridHtml = '';
            if (radioVal || hssVal || ipVal || namVal || sapcItems.length > 0 || btoolsLines.length > 0) {
                gridHtml = `
                            <div class="telecom-diag-grid">
                                <div class="diag-metric-item">
                                    <span class="diag-metric-label">RADIO STATUS</span>
                                    <span class="diag-metric-val val-radio">${escapeHtml(radioVal || '--')}</span>
                                </div>
                                <div class="diag-metric-item">
                                    <span class="diag-metric-label">HSS PROFILE</span>
                                    <span class="diag-metric-val val-hss">${escapeHtml(hssVal || '--')}</span>
                                </div>
                                <div class="diag-metric-item">
                                    <span class="diag-metric-label" style="text-transform:none;">IPv4</span>
                                    <span class="diag-metric-val val-ip">${escapeHtml(ipVal || '--')}</span>
                                </div>
                                <div class="diag-metric-item">
                                    <span class="diag-metric-label">TÌNH TRẠNG GÓI CƯỚC</span>
                                    <div style="font-family:'JetBrains Mono', monospace; font-size:11px; margin-top:2px;">
                                        <div style="margin-bottom:3px;">
                                            <span class="${isNamLocked ? 'val-locked' : 'val-normal'}">${escapeHtml(namVal || 'NAM: 0 (Mở GPRS)')}</span>
                                        </div>
                                        ${sapcItems.map(item => `
                                            <div style="margin-top:4px; padding-top:3px; border-top:1px dashed #e2e8f0;">
                                                <div style="font-size:11px; margin-bottom:2px;">
                                                    <span style="color:#64748b; font-weight:700; font-size:9.5px; text-transform:uppercase;">TÊN GÓI:</span> 
                                                    <span style="color:#0f766e; font-weight:700;">${escapeHtml(item.name)}</span>
                                                </div>
                                                ${item.dates ? `<div style="font-size:9.5px; color:#475569; line-height:1.35; word-break:break-word;">${escapeHtml(item.dates)}</div>` : ''}
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                            </div>
                        `;
                    }

                    let btoolsHtml = '';
                    if (btoolsLines.length > 0) {
                        btoolsHtml = `<div style="font-size:10.5px; line-height:1.4; background:#ffffff; border:1px solid #e2e8f0; border-radius:4px; padding:6px 8px; margin-top:4px;"><strong style="color:#b45309; font-size:10px; text-transform:uppercase; display:block; margin-bottom:2px; letter-spacing:0.03em;">Data Usage (BTools):</strong> <span style="color:#334155;">${escapeHtml(btoolsLines.join(' '))}</span></div>`;
                    }

                    pkgHtml = `<div>${gridHtml}${btoolsHtml}</div>`;

            // Tạo bản hiển thị rút gọn 1 dòng cho cột Hồ Sơ
            let cParts = [];
            if (raw.includes('Radio:')) {
                const m = raw.match(/Radio:\s*([^\|\n\\]+)/);
                if (m) cParts.push(`<span style="color:#0369a1; font-weight:700; font-family:'JetBrains Mono', monospace;">Radio: ${escapeHtml(m[1].trim())}</span>`);
            }
            if (raw.includes('NAM: 1') || raw.includes('Khóa GPRS')) {
                cParts.push(`<span style="background:#fee2e2; color:#b91c1c; font-weight:700; padding:1px 5px; border-radius:3px; border:1px solid #fca5a5;">Khóa GPRS</span>`);
            } else if (raw.includes('NAM: 0')) {
                cParts.push(`<span style="color:#475569; font-weight:600; font-family:'JetBrains Mono', monospace;">NAM: 0</span>`);
            }
            if (sapcLines.length > 0) {
                let firstPkg = sapcLines[0].replace(/^SAPC:\s*/gi, '').trim();
                cParts.push(`<span style="color:#475569; font-weight:500;">Gói: ${escapeHtml(firstPkg)}</span>`);
            }
            if (cParts.length > 0) {
                compactProfileHtml = cParts.join(' | ');
            } else {
                compactProfileHtml = escapeHtml(compactProfileTooltip);
            }
        }

        let cemHtml = '--';
        if (t.cem_data && t.cem_data !== '--') {
            const lines = t.cem_data.split('\n').map(l => l.trim()).filter(l => l.length > 0);
            cemHtml = `<div style="font-size:10.5px; line-height:1.35; color:#334155;">` + 
                      lines.map(line => `<div style="margin-top:2px;">${escapeHtml(line)}</div>`).join('') + 
                      `</div>`;
        }

        let displayStatus = (t.status || '--').trim();
        const fullStatus = displayStatus;
        if (displayStatus.includes('HOẠT ĐỘNG BÌNH THƯỜNG') || displayStatus.includes('HOAT DONG BINH THUONG')) {
            displayStatus = 'BÌNH THƯỜNG';
        } else if (displayStatus.includes('GÓI CÒN HẠN')) {
            displayStatus = 'GÓI CÒN HẠN';
        } else if (displayStatus.includes('BẮT SÓNG 4G KÉM') || displayStatus.includes('KHÔNG CÓ 4G')) {
            displayStatus = 'SÓNG 4G KÉM';
        } else if (displayStatus.includes('LƯU LƯỢNG YẾU')) {
            displayStatus = 'LƯU LƯỢNG YẾU';
        } else if (displayStatus.includes('BỊ KHÓA GPRS')) {
            displayStatus = 'KHÓA GPRS';
        } else if (displayStatus.includes('HSS CHƯA CÓ 5G')) {
            displayStatus = 'HSS CHƯA CÓ 5G';
        }
        let statusHtml = '';
        if (t.status && t.status !== '--' && t.status.trim() !== '') {
            statusHtml = `<span class="badge-status ${badgeClass}" title="${escapeHtml(fullStatus)}">${escapeHtml(displayStatus)}</span>`;
        }
        if (t.ticket_status === 'Phiếu lỗi' || (t.ticket_status && t.ticket_status.includes('lỗi'))) {
            statusHtml += `<div style="margin-top:3px;"><span class="badge-status" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-size:9.5px; padding:1px 5px; font-weight:700;">Phiếu lỗi</span></div>`;
        }

        let ticketCodeHtml = '<span style="color:#94a3b8; font-size:11px;">--</span>';
        let compactTicketCodeHtml = '<span style="color:#94a3b8; font-size:11px;">--</span>';

        if (t.ticket_code) {
            const codeLines = t.ticket_code.split('\n').map(l => l.trim()).filter(l => l);
            let mainCode = codeLines[0] || '';
            if (mainCode.endsWith('.0') && !isNaN(Number(mainCode))) {
                mainCode = mainCode.slice(0, -2);
            }
            const extraLines = codeLines.slice(1);
            const extraHtml = extraLines.map(l => {
                if (l.startsWith('[') && l.endsWith(']')) {
                    return `<div style="font-size:10px; font-weight:700; color:#0369a1; background:#f0f9ff; border:1px solid #bae6fd; padding:1px 5px; border-radius:3px; margin-top:3px; display:inline-block; font-family:-apple-system, BlinkMacSystemFont, sans-serif;">${escapeHtml(l)}</div>`;
                }
                return `<div style="font-size:10.5px; font-weight:500; color:#475569; margin-top:2px; line-height:1.25; font-family:-apple-system, BlinkMacSystemFont, sans-serif;">${escapeHtml(l)}</div>`;
            }).join('');

            let reopenBadgeHtml = '';
            if (reopenCount > 0) {
                reopenBadgeHtml = `
                            <div style="margin-top:4px;">
                                <span class="badge-status" style="background:#fee2e2; color:#dc2626; border:1px solid #f87171; font-weight:800; font-size:10px; padding:2px 7px; display:inline-flex; align-items:center; gap:4px; box-shadow:0 1px 2px rgba(220,38,38,0.15);" title="THÔNG TIN MỞ LẠI TTS: Số lần mở lại là ${reopenCount}">
                                    MỞ LẠI: ${reopenCount} LẦN
                                </span>
                            </div>
                            ${t.last_reopened_date ? `<div style="font-size:9.5px; color:#ef4444; font-weight:600; margin-top:2px;">(Lần cuối: ${escapeHtml(t.last_reopened_date)})</div>` : ''}
                        `;
            }

            ticketCodeHtml = `
                        <div>
                            <span style="color:#0f172a; font-weight:700; font-size:11.5px;">
                                ${escapeHtml(mainCode)}
                            </span>
                            ${extraHtml}
                            ${reopenBadgeHtml}
                        </div>
                    `;

            compactTicketCodeHtml = `
                        <div style="display:inline-flex; align-items:center; gap:3px; max-width:100%;" class="compact-ellipsis">
                            <span style="color:#0f172a; font-weight:700; font-size:11px;">
                                ${escapeHtml(mainCode)}
                            </span>
                            ${reopenCount > 0 ? `<span class="badge-status" style="background:#fee2e2; color:#dc2626; border:1px solid #f87171; font-weight:800; font-size:9px; padding:1px 3px; border-radius:3px;" title="Mở lại ${reopenCount} lần">Lại: ${reopenCount}L</span>` : ''}
                        </div>
                    `;
        }

        let rawPakhType = (t.package_title || '').trim();
        let displayPakhType = rawPakhType;
        let pakhBadgeStyle = '';

        if (!displayPakhType || displayPakhType === '--' || displayPakhType === 'null') {
            if (t.service_type === 'data') {
                displayPakhType = 'Mobile Internet';
            } else if (t.service_type === 'voice_sms') {
                displayPakhType = 'Thoại / SMS';
            } else {
                displayPakhType = '--';
            }
        }

        const lowerType = displayPakhType.toLowerCase();
        if (lowerType.includes('internet') || lowerType.includes('data') || lowerType.includes('3g') || lowerType.includes('4g') || lowerType.includes('5g')) {
            pakhBadgeStyle = 'background:#e0f2fe; color:#0284c7; border:1px solid #bae6fd;';
        } else if (lowerType.includes('thoại') || lowerType.includes('cuộc gọi') || lowerType.includes('thoai') || lowerType.includes('call')) {
            pakhBadgeStyle = 'background:#f3e8ff; color:#7e22ce; border:1px solid #d8b4fe;';
        } else if (lowerType.includes('sms') || lowerType.includes('tin nhắn')) {
            pakhBadgeStyle = 'background:#fef3c7; color:#b45309; border:1px solid #fde68a;';
        } else if (lowerType.includes('gói') || lowerType.includes('goi') || lowerType.includes('cước')) {
            pakhBadgeStyle = 'background:#dcfce7; color:#15803d; border:1px solid #86efac;';
        } else {
            pakhBadgeStyle = 'background:#f1f5f9; color:#475569; border:1px solid #cbd5e1;';
        }

        let compactPakhTypeHtml = (displayPakhType === '--')
            ? '<span style="color:#94a3b8; font-size:11px;">--</span>'
            : `<span class="badge-status" style="${pakhBadgeStyle} font-size:9.5px; font-weight:700; padding:2px 6px; border-radius:3px; display:inline-block; max-width:100%; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${escapeHtml(rawPakhType || displayPakhType)}">${escapeHtml(displayPakhType)}</span>`;

        return `
                    <!-- 1 DÒNG GỌN CHÍNH (COMPACT ROW) -->
                    <tr id="row-main-${ticketKey}" class="ticket-main-row ${isExpanded ? 'is-row-expanded' : ''}">
                        <td style="text-align:center; vertical-align:middle; padding:2px 2px;">
                            <div style="display:flex; align-items:center; justify-content:center;">
                                <button id="btn-toggle-${ticketKey}" class="stt-expand-pill ${isExpanded ? 'is-expanded' : ''}" onclick="toggleTicketRow('${ticketKey}', event)" title="${isExpanded ? 'Bấm để thu nhỏ lại' : 'Bấm để xem chi tiết'}">
                                    <span class="stt-num">${globalIdx + 1}</span>
                                    <svg class="stt-chevron" viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                                        <polyline points="6 9 12 15 18 9"></polyline>
                                    </svg>
                                </button>
                            </div>
                        </td>
                        <td style="${ticketCodeDisplay} font-family:'JetBrains Mono', monospace; vertical-align:middle; padding:2px 4px;">
                            ${compactTicketCodeHtml}
                        </td>
                        <td style="vertical-align:middle; text-align:center; padding:2px 3px;">
                            <span class="badge-status ${badgeClass}" style="white-space:nowrap; font-size:10px; padding:2px 5px; font-weight:700;" title="${escapeHtml(fullStatus)}">${escapeHtml(displayStatus)}</span>
                        </td>
                        <td style="vertical-align:middle; padding:2px 4px; white-space:nowrap;">
                            <div class="compact-ellipsis">
                                <a href="${btoolsUrl}" target="_blank" class="table-phone-link" title="Tra cứu BTools cho số ${t.phone}">
                                    ${t.phone}
                                </a>
                            </div>
                        </td>
                        <td style="vertical-align:middle; text-align:center; padding:2px 3px;">
                            ${compactPakhTypeHtml}
                        </td>
                        <td style="text-align:center; vertical-align:middle; padding:2px 3px; white-space:nowrap;">
                            <span class="table-time-val" title="${escapeHtml(t.incident_time || '--')}">${escapeHtml(t.incident_time || '--')}</span>
                        </td>
                        <td style="vertical-align:middle; padding:2px 4px;">
                            <div class="compact-ellipsis" style="font-size:10.5px; color:#334155;" title="${escapeHtml(compactProfileTooltip)}">
                                ${compactProfileHtml}
                            </div>
                        </td>
                        <td style="text-align:center; vertical-align:middle; padding:2px 2px;">
                            ${compactRatHtml}
                        </td>
                        <td style="vertical-align:middle; padding:2px 4px;">
                            <div class="compact-ellipsis" style="font-size:10px; color:#475569;" title="${escapeHtml(t.cem_data || '--')}">
                                ${(!t.cem_data || t.cem_data === '--' || t.cem_data.includes('Không có dữ liệu'))
                ? `<span style="color:#94a3b8; font-family:'JetBrains Mono', monospace;">--</span>`
                : (t.cem_data.trim().startsWith('Cell:')
                    ? `<span style="font-family:'JetBrains Mono', monospace; font-weight:600; color:#0f172a;">${escapeHtml(t.cem_data.replace(/\n/g, ' ').trim())}</span>`
                    : escapeHtml(t.cem_data.replace(/\n/g, ' ').trim()))}
                            </div>
                        </td>
                        <td style="vertical-align:middle; padding:2px 4px;">
                            <div class="compact-ellipsis" style="font-size:11px; color:#1e293b; line-height:1.4;" title="${escapeHtml(compactSummaryTooltip)}">
                                ${compactSummaryHtml}
                            </div>
                        </td>
                        <td style="vertical-align:middle; padding:2px 3px;">
                            <input type="text" id="input-compact-comment-${ticketKey}" class="compact-input-cell" value="${escapeHtml(t.comment || '')}" placeholder="Ý kiến KTV..." oninput="syncCompactToDetail('${ticketKey}', 'comment', this.value)" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'comment', this.value)">
                        </td>
                        <td style="vertical-align:middle; padding:2px 3px;">
                            <input type="text" id="input-compact-plan-${ticketKey}" class="compact-input-cell" value="${escapeHtml(t.action_plan || '')}" placeholder="Nội dung phản hồi..." oninput="syncCompactToDetail('${ticketKey}', 'action_plan', this.value)" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'action_plan', this.value)">
                        </td>
                        <td style="text-align:center; vertical-align:middle; padding:2px 2px;">
                            ${compactActionHtml}
                        </td>
                    </tr>

                    <!-- KHUNG CHI TIẾT MỞ RỘNG (EXPANDED DETAIL ROW) -->
                    <tr id="row-detail-${ticketKey}" class="ticket-detail-row" style="display: ${isExpanded ? 'table-row' : 'none'};">
                        <td colspan="13" style="background:#f8fafc; padding:12px 16px; border-bottom:2px solid #cbd5e1;">
                            <div class="detail-expanded-grid">
                                <!-- Card 1: Tóm Tắt Nội Dung & Phản ánh gốc -->
                                <div class="detail-card">
                                    <div class="detail-card-title">
                                        <span>TÓM TẮT NỘI DUNG & PHẢN ÁNH GỐC</span>
                                        <span style="font-size:10px; color:#64748b; font-family:'JetBrains Mono', monospace;">${escapeHtml(t.package_title || '')}</span>
                                    </div>
                                    <div style="flex:1; overflow-y:auto; max-height:230px;">
                                        ${aiSummaryHtml}
                                    </div>
                                </div>

                                <!-- Card 2: Hồ Sơ Kỹ Thuật & CEM -->
                                <div class="detail-card">
                                    <div class="detail-card-title">
                                        <span>PROFILE & DỮ LIỆU CEM</span>
                                        <a href="${btoolsUrl}" target="_blank" style="font-size:10.5px; color:#005baa; font-weight:700; text-decoration:none;">Xem BTools ↗</a>
                                    </div>
                                    <div style="flex:1; overflow-y:auto; max-height:230px; font-size:11px; line-height:1.4;">
                                        <div style="margin-bottom:8px;">${pkgHtml}</div>
                                        ${t.cem_data && t.cem_data !== '--' ? `
                                            <div style="border-top:1px dashed #cbd5e1; padding-top:6px; margin-top:6px;">
                                                <strong style="color:#0f172a; font-size:11px;">Dữ liệu CEM:</strong>
                                                ${cemHtml}
                                            </div>
                                        ` : ''}
                                    </div>
                                </div>

                                <!-- Card 3: Nhập Ý Kiến Cột 10 & 11 + Thao Tác -->
                                <div class="detail-card" style="background:#ffffff; border-color:#cbd5e1;">
                                    <div class="detail-card-title">
                                        <span>Ý KIẾN KTV & NỘI DUNG PHẢN HỒI</span>
                                        <span style="font-size:10.5px; color:#15803d; font-weight:600;">Tự động lưu</span>
                                    </div>
                                    <div style="display:flex; flex-direction:column; gap:8px;">
                                        <div>
                                            <div style="font-size:11px; font-weight:700; color:#334155; margin-bottom:3px; display:flex; justify-content:space-between;">
                                                <span>Ý kiến phân tích (Cột 10):</span>
                                                <div id="save-comment-${ticketKey}" class="save-indicator">Đã lưu tự động</div>
                                            </div>
                                            <textarea id="textarea-detail-comment-${ticketKey}" class="editable-cell" oninput="syncDetailToCompact('${ticketKey}', 'comment', this.value); this.style.height='auto'; this.style.height=(this.scrollHeight+4)+'px';" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'comment', this.value)">${escapeHtml(t.comment || '')}</textarea>
                                        </div>
                                        <div>
                                            <div style="font-size:11px; font-weight:700; color:#334155; margin-bottom:3px; display:flex; justify-content:space-between;">
                                                <span>Nội dung phản hồi (Cột 11):</span>
                                                <div id="save-plan-${ticketKey}" class="save-indicator">Đã lưu tự động</div>
                                            </div>
                                            <textarea id="textarea-detail-action_plan-${ticketKey}" class="editable-cell" oninput="syncDetailToCompact('${ticketKey}', 'action_plan', this.value); this.style.height='auto'; this.style.height=(this.scrollHeight+4)+'px';" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'action_plan', this.value)">${escapeHtml(t.action_plan || '')}</textarea>
                                        </div>

                                        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px; margin-top:4px; padding-top:6px; border-top:1px solid #f1f5f9;">
                                            ${reopenCount > 0 ? `
                                                <div style="font-size:10.5px; font-weight:700; color:#b91c1c; background:#fee2e2; border:1px solid #fca5a5; padding:3px 8px; border-radius:4px;">
                                                    Phiếu mở lại ${reopenCount} lần (Yêu cầu KTV xử lý)
                                                </div>
                                            ` : '<div></div>'}
                                            <div style="display:flex; align-items:center; gap:6px; margin-left:auto;">
                                                ${actionHtml}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </td>
                    </tr>
                    `;
    }).join('');

    autoResizeAllTextareas();
}

async function autoResizeAllTextareas() {
    document.querySelectorAll('.editable-cell').forEach(el => {
        el.style.height = 'auto';
        el.style.height = (el.scrollHeight + 4) + 'px';
    });
}

async function manualRefreshDashboard() {
    const btn = document.getElementById('btnRefresh');
    if (btn) btn.classList.add('spinning');
    try {
        lastTicketsSignature = "";
        // Kích hoạt quét nhanh từ API theo phân hệ đang chọn để đồng bộ dữ liệu thực tế
        if (currentSystem === 'tts_old_api') {
            if (currentService === 'data') {
                fetch('/api/tts_old_api/run-now', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
            } else if (currentService === 'voice_sms') {
                fetch('/api/tts_old_api/scan_voice', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
            }
        } else if (currentSystem === 'tts_new') {
            if (currentService === 'data') {
                fetch('/api/ttsnew/run-now', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
            } else if (currentService === 'voice_sms') {
                fetch('/api/ttsnew/scan_voice', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
            }
        }
        await Promise.all([
            fetchStatus(),
            loadTickets(true)
        ]);
    } finally {
        setTimeout(() => {
            if (btn) btn.classList.remove('spinning');
        }, 800);
    }
}
function closeSingleTicket(phone, incidentTime, btnElem) {
    closeTtsOldApiTicket(phone, incidentTime, btnElem);
}

function manualCloseTicket(btnElem, phone, incidentTime) {
    closeTtsOldApiTicket(phone, incidentTime, btnElem);
}

async function closeTtsOldApiTicket(phone, incidentTime, btnElem) {
    if (btnElem && btnElem.disabled) return;

    const session = getTtsAuthSession();
    if (!session || !session.token) {
        alert("Bạn cần đăng nhập tài khoản TTS của mình trước khi thực hiện thao tác đóng phiếu!");
        openConnectModal();
        return;
    }

    const row = btnElem ? btnElem.closest('tr') : null;
    let commentVal = '';
    let actionPlanVal = '';
    if (row) {
        const textareas = row.querySelectorAll('textarea.editable-cell');
        if (textareas.length >= 2) {
            commentVal = textareas[0].value.trim();
            actionPlanVal = textareas[1].value.trim();
        }
    }

    const originalHtml = btnElem ? btnElem.innerHTML : '';
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = `Đang đóng...`;
        btnElem.style.opacity = '0.7';
    }

    try {
        const res = await fetch('/api/tts_old_api/close_one', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                phone,
                incident_time: incidentTime,
                comment: commentVal,
                action_plan: actionPlanVal,
                token: session.token,
                user_id: session.userId || 0,
                user_name: session.displayName || session.username || "Kỹ thuật viên"
            })
        });
        const data = await res.json();
        if (data.success) {
            lastTicketsSignature = "";
            await loadTickets(true);
            await fetchStatus();
        } else {
            // Nếu thông báo có chứa 'Lưu ý CCOS' hoặc đã đóng trên TTS
            if (data.message && data.message.includes('thành công')) {
                lastTicketsSignature = "";
                await loadTickets(true);
                await fetchStatus();
            } else {
                alert(data.message || "Thao tác đóng phiếu thất bại.");
                if (btnElem) {
                    btnElem.disabled = false;
                    btnElem.innerHTML = originalHtml;
                    btnElem.style.opacity = '1';
                }
            }
        }
    } catch (e) {
        console.warn("Lỗi kết nối khi gửi yêu cầu đóng phiếu:", e);
        // Tự động kiểm tra lại DB xem phiếu đã thực sự đóng trên máy chủ chưa
        setTimeout(async () => {
            lastTicketsSignature = "";
            await loadTickets(true);
            await fetchStatus();
        }, 1000);

        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = originalHtml;
            btnElem.style.opacity = '1';
        }
    }
}

async function startTtsOldApiDataScan() {
    const btn = document.getElementById('btnRunNowApi') || document.getElementById('btnTtsOldApiScanData');
    if (btn) btn.disabled = true;
    const originalHtml = btn ? btn.innerHTML : '';
    if (btn) btn.innerHTML = '<span class="status-dot processing" style="display:inline-block; margin-right:6px;"></span> Đang quét & tiền kiểm...';
    try {
        const res = await fetch('/api/tts_old_api/run-now', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
        });
        const data = await res.json();
        if (!data.success) {
            alert(data.message || "Không thể khởi động quét TTS Cũ.");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
            return;
        }

        let checkAttempts = 0;
        const interval = setInterval(async () => {
            checkAttempts++;
            const stRes = await fetch('/api/status');
            const stData = await stRes.json();
            await fetchStatus();
            await loadTickets(true);
            if (stData.status !== 'PROCESSING' || checkAttempts > 45) {
                clearInterval(interval);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
                await loadTickets(true);
                await fetchStatus();
            }
        }, 2000);

    } catch (e) {
        alert("Lỗi kết nối khi quét TTS Cũ: " + e);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
}

async function startTtsOldApiVoiceScan() {
    const btn = document.getElementById('btnTtsOldApiScanVoice');
    const originalHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="status-dot processing" style="display:inline-block; margin-right:6px;"></span> Đang quét dữ liệu...';
    }
    try {
        const res = await fetch('/api/tts_old_api/scan_voice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
        });
        const data = await res.json();
        if (!data.success) {
            alert(data.message || "Không thể quét phiếu Thoại/SMS.");
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
            return;
        }

        let checkAttempts = 0;
        const interval = setInterval(async () => {
            checkAttempts++;
            const stRes = await fetch('/api/status');
            const stData = await stRes.json();
            if (stData.status !== 'PROCESSING' || checkAttempts > 35) {
                clearInterval(interval);
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
                await loadTickets(true);
                await fetchStatus();

                const vCount = (stData.system_counts && stData.system_counts.tts_old_api_voice) || 0;
                if (vCount === 0) {
                    alert("Đã quét xong: Bảng sự cố TTS Cũ hiện tại không có phiếu Thoại / SMS nào.");
                } else {
                    alert(`Đã quét & tiền kiểm tra đầy đủ cho ${vCount} phiếu Thoại / SMS!`);
                }
            }
        }, 2000);
    } catch (e) {
        alert("Lỗi khi gửi yêu cầu quét Thoại/SMS: " + e);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    }
}

async function startTtsNewScan() {
    const btn = document.getElementById('btnTtsNewScan');
    const originalHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="status-dot processing" style="display:inline-block; margin-right:6px;"></span> Đang quét dữ liệu...';
    }
    try {
        const res = await fetch('/api/ttsnew/run-now', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
        });
        const data = await res.json();
        if (data.success) {
            await fetchStatus();
            setTimeout(() => loadTickets(true), 2500);
        } else {
            alert(data.message || "Không thể khởi động quét TTS Mới.");
        }
    } catch (e) {
        alert("Lỗi kết nối khi quét TTS Mới: " + e);
    } finally {
        setTimeout(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        }, 3000);
    }
}

async function closeTtsNewTicketApi(ticketCode, phone, incidentTime, btnElem, reopenCount = 0) {
    if (btnElem && btnElem.disabled) return;

    const rCount = parseInt(reopenCount || 0, 10);
    if (rCount > 0) {
        const confirmed = confirm(`CẢNH BÁO KTV:\nPhiếu ${ticketCode} (${phone}) có THÔNG TIN MỞ LẠI TTS: Số lần mở lại là ${rCount}!\n\nTheo quy định, phiếu này KHÔNG được phép tự động đóng mà yêu cầu KTV phải kiểm tra kỹ lưỡng.\nBạn có chắc chắn đã kiểm tra đầy đủ và muốn ĐÓNG THỦ CÔNG phiếu này không?`);
        if (!confirmed) return;
    }

    const row = btnElem ? btnElem.closest('tr') : null;
    let commentVal = '';
    let actionPlanVal = '';
    if (row) {
        const textareas = row.querySelectorAll('textarea.editable-cell');
        if (textareas.length >= 2) {
            commentVal = textareas[0].value.trim();
            actionPlanVal = textareas[1].value.trim();
        }
    }

    const originalHtml = btnElem ? btnElem.innerHTML : '';
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = `Đang đóng...`;
        btnElem.style.opacity = '0.7';
    }

    try {
        const res = await fetch('/api/ttsnew/close_one', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ticket_code: ticketCode,
                phone: phone,
                incident_time: incidentTime,
                comment: commentVal,
                action_plan: actionPlanVal,
                force: (rCount > 0)
            })
        });
        const data = await res.json();
        if (data.success) {
            alert(data.message || `Đã xử lý thành công phiếu ${ticketCode}!`);
            lastTicketsSignature = "";
            await loadTickets(true);
            await fetchStatus();
        } else {
            alert(data.message || "Xử lý đóng phiếu TTS Mới thất bại.");
            if (btnElem) {
                btnElem.disabled = false;
                btnElem.innerHTML = originalHtml;
                btnElem.style.opacity = '1';
            }
        }
    } catch (e) {
        alert("Lỗi kết nối khi gửi yêu cầu đóng phiếu: " + e);
        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = originalHtml;
            btnElem.style.opacity = '1';
        }
    }
}

async function triggerTtsNewAutoCloseAll(btnElem) {
    if (btnElem && btnElem.disabled) return;
    if (!confirm("Xác nhận tự động xử lý đóng tất cả phiếu Mobile Internet đủ điều kiện trên TTS Mới?")) {
        return;
    }

    const originalHtml = btnElem ? btnElem.innerHTML : '';
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = `<span class="status-dot processing" style="display:inline-block; margin-right:6px;"></span> Đang tự động đóng...`;
    }

    try {
        const res = await fetch('/api/ttsnew/close_all', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            await fetchStatus();
            let checkAttempts = 0;
            const interval = setInterval(async () => {
                checkAttempts++;
                await fetchStatus();
                if (checkAttempts > 15) {
                    clearInterval(interval);
                    if (btnElem) {
                        btnElem.disabled = false;
                        btnElem.innerHTML = originalHtml;
                    }
                    await loadTickets(true);
                }
            }, 2000);
        } else {
            alert(data.message || "Không thể thực hiện đóng tự động TTS Mới.");
            if (btnElem) {
                btnElem.disabled = false;
                btnElem.innerHTML = originalHtml;
            }
        }
    } catch (e) {
        alert("Lỗi kết nối khi gửi yêu cầu đóng tự động TTS Mới: " + e);
        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = originalHtml;
            btnElem.style.opacity = '1';
        }
    }
}

async function openTtsNewTicketDetail(ticketCode, phone, incidentTime, btnElem) {
    const originalHtml = btnElem ? btnElem.innerHTML : '';
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = `Đang mở...`;
        btnElem.style.opacity = '0.7';
    }

    try {
        const res = await fetch('/api/ttsnew/open_detail', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket_code: ticketCode, phone, incident_time: incidentTime })
        });
        const data = await res.json();
        if (data.success) {
            if (btnElem) {
                btnElem.innerHTML = `Đã mở`;
                setTimeout(() => {
                    btnElem.disabled = false;
                    btnElem.innerHTML = originalHtml;
                    btnElem.style.opacity = '1';
                }, 2000);
            }
        } else {
            window.open('https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu/chi-tiet-phieu-pakh', '_blank');
            alert(data.message || "Không thể chuyển trang tự động. Đã mở tab TTS Mới thủ công.");
            if (btnElem) {
                btnElem.disabled = false;
                btnElem.innerHTML = originalHtml;
                btnElem.style.opacity = '1';
            }
        }
    } catch (e) {
        window.open('https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu/chi-tiet-phieu-pakh', '_blank');
        alert("Lỗi khi mở chi tiết phiếu: " + e);
        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = originalHtml;
            btnElem.style.opacity = '1';
        }
    }
}

async function updateTicket(phone, incidentTime, field, value) {
    try {
        const res = await fetch('/api/tickets/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, incident_time: incidentTime, field, value })
        });
        if (res.ok) {
            const cleanInc = (incidentTime || '').replace(/[^a-zA-Z0-9]/g, '_');
            document.querySelectorAll(`[id^="save-${field === 'comment' ? 'comment' : 'plan'}-${phone}"]`).forEach(el => {
                el.style.display = 'block';
                setTimeout(() => el.style.display = 'none', 1800);
            });
        }
    } catch (e) {
        console.error("Lỗi update ticket:", e);
    }
}

async function startAutomation(engine = 'selenium') {
    let interval = 15;
    let autoClose = true;

    if (engine === 'tts_new') {
        const inp = document.getElementById('inpIntervalNew');
        interval = inp ? (parseInt(inp.value) || 15) : 15;
        const chk = document.getElementById('chkAutoCloseNew');
        autoClose = chk ? chk.checked : true;
    } else if (engine === 'api') {
        const inp = document.getElementById('inpIntervalApi');
        interval = inp ? (parseInt(inp.value) || 15) : 15;
        const chk = document.getElementById('chkAutoCloseApi');
        autoClose = chk ? chk.checked : true;
    } else {
        const inp = document.getElementById('inpInterval');
        interval = inp ? (parseInt(inp.value) || 5) : 5;
        const chk = document.getElementById('chkAutoClose');
        autoClose = chk ? chk.checked : true;
    }

    await fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ engine: engine, interval_minutes: interval, auto_close: autoClose })
    });
    fetchStatus();
}

async function stopAutomation() {
    await fetch('/api/stop', { method: 'POST' });
    fetchStatus();
}

async function runNow() {
    await fetch('/api/run-now', { method: 'POST' });
    fetchStatus();
    setTimeout(() => loadTickets(true), 3000);
}

// =====================================================================
// CỤM ĐIỀU KHIỂN THỐNG NHẤT (UNIFIED SCAN & CLOSE CONTROLS)
// =====================================================================
let isScopeDropdownOpen = false;

function toggleScopeDropdown(event) {
    if (event) event.stopPropagation();
    const panel = document.getElementById('scopeDropdownPanel');
    if (!panel) return;
    isScopeDropdownOpen = !panel.classList.contains('show');
    if (isScopeDropdownOpen) {
        panel.classList.add('show');
    } else {
        panel.classList.remove('show');
    }
}

// Tự động đóng dropdown chọn phạm vi khi click ra ngoài
document.addEventListener('click', function (e) {
    const container = document.getElementById('scopeDropdownContainer');
    const panel = document.getElementById('scopeDropdownPanel');
    if (panel && container && !container.contains(e.target)) {
        panel.classList.remove('show');
        isScopeDropdownOpen = false;
    }
});

function getSelectedScopes() {
    const scopes = [];
    if (document.getElementById('chkScopeOldData')?.checked) scopes.push('tts_old_data');
    if (document.getElementById('chkScopeOldVoice')?.checked) scopes.push('tts_old_voice');
    if (document.getElementById('chkScopeNewData')?.checked) scopes.push('tts_new_data');
    if (document.getElementById('chkScopeNewVoice')?.checked) scopes.push('tts_new_voice');
    return scopes;
}

function updateScopeSummaryLabel(scopes) {
    const lbl = document.getElementById('lblScopeSummary');
    if (!lbl) return;
    const len = scopes.length;
    if (len === 0) {
        lbl.innerText = 'Chưa chọn phạm vi';
    } else if (len === 4) {
        lbl.innerText = 'Quét: Tất cả (4)';
    } else if (len === 1) {
        const nameMap = {
            'tts_old_data': 'TTS Cũ (Data)',
            'tts_old_voice': 'TTS Cũ (Thoại)',
            'tts_new_data': 'TTS Mới (Data)',
            'tts_new_voice': 'TTS Mới (Thoại)'
        };
        lbl.innerText = `Quét: ${nameMap[scopes[0]] || scopes[0]}`;
    } else {
        lbl.innerText = `Quét: ${len} phạm vi`;
    }
}

function syncScopeCheckboxes(scopes) {
    const chkOldData = document.getElementById('chkScopeOldData');
    const chkOldVoice = document.getElementById('chkScopeOldVoice');
    const chkNewData = document.getElementById('chkScopeNewData');
    const chkNewVoice = document.getElementById('chkScopeNewVoice');
    if (chkOldData) chkOldData.checked = scopes.includes('tts_old_data');
    if (chkOldVoice) chkOldVoice.checked = scopes.includes('tts_old_voice');
    if (chkNewData) chkNewData.checked = scopes.includes('tts_new_data');
    if (chkNewVoice) chkNewVoice.checked = scopes.includes('tts_new_voice');
    updateScopeSummaryLabel(scopes);
}

async function handleScopeChange() {
    let scopes = getSelectedScopes();
    if (scopes.length === 0) {
        const chkOldData = document.getElementById('chkScopeOldData');
        if (chkOldData) chkOldData.checked = true;
        scopes = ['tts_old_data'];
    }
    updateScopeSummaryLabel(scopes);
    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scan_scopes: scopes })
        });
    } catch (e) {
        console.error("Lỗi cập nhật phạm vi quét:", e);
    }
}

async function handleAutoCloseModeChange(mode) {
    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_close_mode: mode })
        });
        const headerModeTag = document.getElementById('headerModeTag');
        if (headerModeTag) {
            if (mode === 'all') {
                headerModeTag.style.color = '#15803d';
                headerModeTag.innerText = 'Chế độ: Tự đóng (Cả TTS Cũ & Mới)';
            } else if (mode === 'tts_old') {
                headerModeTag.style.color = '#0284c7';
                headerModeTag.innerText = 'Chế độ: Chỉ tự đóng TTS Cũ';
            } else if (mode === 'tts_new') {
                headerModeTag.style.color = '#6366f1';
                headerModeTag.innerText = 'Chế độ: Chỉ tự đóng TTS Mới';
            } else {
                headerModeTag.style.color = '#b45309';
                headerModeTag.innerText = 'Chế độ: Đóng thủ công 100%';
            }
        }
    } catch (e) {
        console.error("Lỗi cập nhật chế độ đóng phiếu:", e);
    }
}

async function startUnifiedAutomation() {
    const scopes = getSelectedScopes();
    const chkAutoClose = document.getElementById('chkAutoCloseUnified');
    const autoClose = chkAutoClose ? chkAutoClose.checked : true;
    const autoCloseMode = autoClose ? 'all' : 'none';
    const inpInterval = document.getElementById('inpIntervalUnified');
    const interval = inpInterval ? (parseInt(inpInterval.value) || 15) : 15;

    await fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            scan_scopes: scopes,
            auto_close: autoClose,
            auto_close_mode: autoCloseMode,
            interval_minutes: interval
        })
    });
    fetchStatus();
}

async function runNowUnified() {
    const scopes = getSelectedScopes();
    await fetch('/api/run-now', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan_scopes: scopes })
    });
    fetchStatus();
    setTimeout(() => loadTickets(true), 3000);
}

function exportExcel() {
    window.location.href = '/api/export_excel';
}

// =====================================================================
// QUẢN LÝ PHIÊN ĐĂNG NHẬP TTS & PHÂN QUYỀN (MULTI-USER SESSION)
// =====================================================================
let currentAuthUser = null;
let isSystemAdmin = false;

function getTtsAuthSession() {
    try {
        const token = localStorage.getItem('tts_auth_token') || '';
        const userRaw = localStorage.getItem('tts_auth_user') || '';
        if (!token) return null;
        let userObj = {};
        try {
            userObj = JSON.parse(userRaw);
        } catch (e) {
            userObj = { TaiKhoan: userRaw, HoTen: userRaw };
        }
        const username = userObj.TaiKhoan || userObj.username || userObj.user_name || 'KTV';
        const displayName = userObj.HoTen || userObj.fullname || username;
        const userId = userObj.Id || userObj.id || userObj.user_id || 0;
        return {
            token: token,
            username: username,
            displayName: displayName,
            userId: userId,
            raw: userObj
        };
    } catch (e) {
        return null;
    }
}

function setTtsAuthSession(token, userInfo) {
    if (!token) return;
    localStorage.setItem('tts_auth_token', token.trim());
    if (typeof userInfo === 'object') {
        localStorage.setItem('tts_auth_user', JSON.stringify(userInfo));
    } else {
        localStorage.setItem('tts_auth_user', String(userInfo || ''));
    }
}

function clearTtsAuthSession() {
    localStorage.removeItem('tts_auth_token');
    localStorage.removeItem('tts_auth_user');
    currentAuthUser = null;
    applyUserSessionState();
    const welcomeModal = document.getElementById('welcomeTtsModal');
    if (welcomeModal) {
        welcomeModal.style.display = 'flex';
        const uInp = document.getElementById('loginTtsUsername');
        if (uInp) {
            uInp.value = '';
            uInp.focus();
        }
        const pInp = document.getElementById('loginTtsPassword');
        if (pInp) pInp.value = '';
        const msg = document.getElementById('loginTtsStatusMsg');
        if (msg) msg.style.display = 'none';
        const btn = document.getElementById('btnDirectLoginSubmit');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>ĐĂNG NHẬP</span>';
        }
    }
}

function switchConnectTab(tab) {
    const tabBm = document.getElementById('tabContentBm');
    const tabManual = document.getElementById('tabContentManual');
    const btnBm = document.getElementById('tabBtnBm');
    const btnManual = document.getElementById('tabBtnManual');

    if (tab === 'bm') {
        if (tabBm) tabBm.style.display = 'block';
        if (tabManual) tabManual.style.display = 'none';
        if (btnBm) btnBm.className = 'connect-tab-btn active';
        if (btnManual) btnManual.className = 'connect-tab-btn';
    } else {
        if (tabBm) tabBm.style.display = 'none';
        if (tabManual) tabManual.style.display = 'block';
        if (btnBm) btnBm.className = 'connect-tab-btn';
        if (btnManual) btnManual.className = 'connect-tab-btn active';
    }
}

function openConnectModal() {
    const session = getTtsAuthSession();
    if (!session || !session.token) {
        const welcomeModal = document.getElementById('welcomeTtsModal');
        if (welcomeModal) {
            welcomeModal.style.display = 'flex';
            const uInp = document.getElementById('loginTtsUsername');
            if (uInp) uInp.focus();
            return;
        }
    }

    const modal = document.getElementById('connectTtsModal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Cập nhật Bookmarklet link với hostname động
    const bmLink = document.getElementById('bmLink');
    const dashOrigin = window.location.origin;
    const bmCode = `javascript:(function(){try{var t=localStorage.getItem('scnntttoken')||'';var u=localStorage.getItem('userInfo')||'';if(!t){alert('Không tìm thấy phiên TTS! Vui lòng mở tts.vnpt.vn và đăng nhập tài khoản trước.');return;}var target='${dashOrigin}/?sync_token='+encodeURIComponent(t)+'&sync_user='+encodeURIComponent(u);window.location.href=target;}catch(e){alert('Lỗi: '+e.message);}})();`;
    if (bmLink) {
        bmLink.href = bmCode;
    }

    // Hiển thị thông tin phiên hiện tại (nếu có)
    const curBox = document.getElementById('modalCurrentSessionBox');
    if (session) {
        if (curBox) {
            curBox.style.display = 'block';
            document.getElementById('curSessionUser').innerText = `${session.displayName} (${session.username})`;
            document.getElementById('curSessionToken').innerText = session.token.substring(0, 16) + '...';
        }
    } else {
        if (curBox) curBox.style.display = 'none';
    }
}

function closeConnectModal() {
    const modal = document.getElementById('connectTtsModal');
    if (modal) modal.style.display = 'none';
}

function copyBookmarkletCode() {
    const dashOrigin = window.location.origin;
    const bmCode = `javascript:(function(){try{var t=localStorage.getItem('scnntttoken')||'';var u=localStorage.getItem('userInfo')||'';if(!t){alert('Không tìm thấy phiên TTS! Vui lòng đăng nhập tts.vnpt.vn trước.');return;}var target='${dashOrigin}/?sync_token='+encodeURIComponent(t)+'&sync_user='+encodeURIComponent(u);window.location.href=target;}catch(e){alert('Lỗi: '+e.message);}})();`;
    navigator.clipboard.writeText(bmCode).then(() => {
        alert("Đã sao chép mã Bookmarklet vào bộ nhớ tạm! Bạn có thể dán vào thanh địa chỉ (URL) hoặc Bookmark trên trình duyệt.");
    }).catch(err => {
        prompt("Sao chép mã sau:", bmCode);
    });
}

function saveManualToken() {
    const tokenInp = document.getElementById('inpManualToken');
    const userInp = document.getElementById('inpManualUser');
    const token = tokenInp ? tokenInp.value.trim() : '';
    const user = userInp ? userInp.value.trim() : 'Kỹ thuật viên';

    if (!token) {
        alert("Vui lòng nhập mã Token scnntttoken!");
        return;
    }

    setTtsAuthSession(token, { TaiKhoan: user, HoTen: user });
    closeConnectModal();
    applyUserSessionState();
    alert(`Đã kết nối thành công tài khoản: ${user}!`);
}

async function syncServerTokenQuick() {
    try {
        const res = await fetch('/api/current_user');
        if (res.ok) {
            const data = await res.json();
            if (data.server_token) {
                setTtsAuthSession(data.server_token, data.server_user || { TaiKhoan: "admin", HoTen: "Quản trị viên máy chủ" });
                closeConnectModal();
                applyUserSessionState();
                alert("Đã đồng bộ thành công Token từ máy chủ!");
                return;
            }
        }
    } catch (e) { }
    alert("Máy chủ hiện chưa trích xuất được token từ trình duyệt.");
}

let pollTtsInterval = null;

async function checkTtsTokenFromBrowser() {
    // 1. Luôn ưu tiên hỏi server/LAN session xem có token mới nhất không
    let serverData = null;
    try {
        const res = await fetch('/api/current_user');
        if (res.ok) {
            serverData = await res.json();
            if (serverData.has_server_token && serverData.server_token) {
                setTtsAuthSession(serverData.server_token, serverData.server_user || { TaiKhoan: "KTV", HoTen: "Kỹ thuật viên" });
                return getTtsAuthSession();
            }
        }
    } catch (e) {
        console.warn("Lỗi kiểm tra token từ trình duyệt:", e);
    }

    // 2. Nếu server không có, kiểm tra session đã lưu trong localStorage của trình duyệt hiện tại
    let session = getTtsAuthSession();
    if (session && session.token) {
        // Bảo vệ: Nếu là client LAN (không phải Localhost) mà session lại chứa tài khoản admin máy chủ (quangvu)
        // thì lập tức hủy bỏ để tránh nhận nhầm tài khoản của chủ máy!
        const isLocal = serverData ? serverData.is_local : false;
        if (!isLocal && (session.username === 'quangvu' || (session.displayName && session.displayName.includes('Quang Vũ')))) {
            console.warn("Phát hiện session rò rỉ quangvu trên client LAN, tự động hủy bỏ.");
            localStorage.removeItem('tts_auth_token');
            localStorage.removeItem('tts_auth_user');
            return null;
        }
        return session;
    }

    return null;
}

function togglePasswordVisibility() {
    const pInp = document.getElementById('loginTtsPassword');
    if (!pInp) return;
    pInp.type = (pInp.type === 'password') ? 'text' : 'password';
}
let currentLoginSessionId = null;

async function handleDirectLoginSubmit(e) {
    if (e) e.preventDefault();
    const uInp = document.getElementById('loginTtsUsername');
    const pInp = document.getElementById('loginTtsPassword');
    const btn = document.getElementById('btnDirectLoginSubmit');
    const msg = document.getElementById('loginTtsStatusMsg');

    const username = uInp ? uInp.value.trim() : '';
    const password = pInp ? pInp.value.trim() : '';

    if (!username || !password) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.style.border = '1px solid #fca5a5';
            msg.innerText = 'Vui lòng nhập đầy đủ tài khoản và mật khẩu TTS!';
        }
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="status-dot processing" style="width:8px; height:8px; display:inline-block;"></span> ĐANG XỬ LÝ...';
    }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.style.border = '1px solid #bae6fd';
        msg.innerText = 'Đang kết nối xác thực với VNPT CAS...';
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();

        if (data.success && data.token) {
            // Thành công ngay (không có OTP)
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.style.border = '1px solid #86efac';
                msg.innerText = 'Đăng nhập thành công! Đang vào Dashboard...';
            }
            setTtsAuthSession(data.token, data.user);
            setTimeout(() => {
                const modal = document.getElementById('welcomeTtsModal');
                if (modal) modal.style.display = 'none';
                applyUserSessionState();
                loadTickets(true);
            }, 500);
        } else if (data.otp_required) {
            // Chuyển sang Bước 2: Nhập OTP y chang Ảnh 2
            currentLoginSessionId = data.session_id;
            document.getElementById('boxStep1Login').style.display = 'none';
            document.getElementById('boxStep2Otp').style.display = 'block';

            const userLabel = document.getElementById('otpUserLabel');
            if (userLabel) userLabel.innerText = data.username || username;
            const phoneLabel = document.getElementById('otpPhoneLabel');
            const phoneBox = document.getElementById('otpPhoneText');
            if (data.phone) {
                if (phoneLabel) phoneLabel.innerText = data.phone;
                if (phoneBox) phoneBox.style.display = 'block';
            } else {
                if (phoneBox) phoneBox.innerHTML = 'Mã xác thực OTP của bạn hiện đã được gửi đến số điện thoại đăng ký tài khoản.';
            }

            const otpInp = document.getElementById('loginTtsOtp');
            if (otpInp) {
                otpInp.value = '';
                otpInp.focus();
            }
            const otpMsg = document.getElementById('loginOtpStatusMsg');
            if (otpMsg) otpMsg.style.display = 'none';
            const otpBtn = document.getElementById('btnDirectOtpSubmit');
            if (otpBtn) {
                otpBtn.disabled = false;
                otpBtn.innerHTML = '<span>ĐĂNG NHẬP</span>';
            }
        } else {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span>ĐĂNG NHẬP</span>';
            }
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.style.border = '1px solid #fca5a5';
                msg.innerText = data.error || 'Sai tài khoản hoặc mật khẩu TTS!';
            }
        }
    } catch (err) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>ĐĂNG NHẬP</span>';
        }
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.style.border = '1px solid #fca5a5';
            msg.innerText = 'Lỗi kết nối tới máy chủ Precheck: ' + err.message;
        }
    }
}

async function handleDirectOtpSubmit(e) {
    if (e) e.preventDefault();
    if (!currentLoginSessionId) {
        alert('Phiên đăng nhập đã hết hạn. Vui lòng thử lại.');
        backToStep1Login();
        return;
    }

    const otpInp = document.getElementById('loginTtsOtp');
    const btn = document.getElementById('btnDirectOtpSubmit');
    const msg = document.getElementById('loginOtpStatusMsg');
    const otpVal = otpInp ? otpInp.value.trim() : '';

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="status-dot processing" style="width:8px; height:8px; display:inline-block;"></span> Đang xác thực mã OTP...';
    }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.style.border = '1px solid #bae6fd';
        msg.innerText = 'Đang xác thực với máy chủ CAS VNPT, vui lòng chờ...';
    }

    try {
        const res = await fetch('/api/login/otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentLoginSessionId, otp: otpVal })
        });
        const data = await res.json();

        if (data.success && data.token) {
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.style.border = '1px solid #86efac';
                msg.innerText = 'Xác thực OTP thành công! Đang vào Dashboard...';
            }
            setTtsAuthSession(data.token, data.user);
            setTimeout(() => {
                const modal = document.getElementById('welcomeTtsModal');
                if (modal) modal.style.display = 'none';
                backToStep1Login();
                applyUserSessionState();
                loadTickets(true);
            }, 500);
        } else {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span>ĐĂNG NHẬP</span>';
            }
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.style.border = '1px solid #fca5a5';
                msg.innerText = data.error || 'Mã OTP không chính xác hoặc hết hạn!';
            }
        }
    } catch (err) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>ĐĂNG NHẬP</span>';
        }
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.style.border = '1px solid #fca5a5';
            msg.innerText = 'Lỗi kết nối: ' + err.message;
        }
    }
}

function backToStep1Login() {
    document.getElementById('boxStep1Login').style.display = 'block';
    document.getElementById('boxStep2Otp').style.display = 'none';
    const btn = document.getElementById('btnDirectLoginSubmit');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span>ĐĂNG NHẬP</span>';
    }
    const msg = document.getElementById('loginTtsStatusMsg');
    if (msg) msg.style.display = 'none';
}

function closeWelcomeModalAndEnter() {
    const modal = document.getElementById('welcomeTtsModal');
    if (modal) modal.style.display = 'none';
    applyUserSessionState();
    loadTickets(true);
}

function applyUserSessionState() {
    const session = getTtsAuthSession();
    currentAuthUser = session;

    const unauthBtn = document.getElementById('unauthBtn');
    const authPill = document.getElementById('authPill');
    const authUserName = document.getElementById('authUserName');
    const authRoleTag = document.getElementById('authRoleTag');
    const welcomeModal = document.getElementById('welcomeTtsModal');

    if (!session || !session.token) {
        // CHƯA ĐĂNG NHẬP: HIỆN POPUP CHÀO MỪNG & KHÓA
        if (unauthBtn) unauthBtn.style.display = 'inline-flex';
        if (authPill) authPill.style.display = 'none';
        if (welcomeModal) welcomeModal.style.display = 'flex';
        document.body.classList.add('is-unauthenticated');
    } else {
        // ĐÃ ĐĂNG NHẬP: VÀO TRANG, HIỂN THỊ XIN CHÀO
        if (unauthBtn) unauthBtn.style.display = 'none';
        if (authPill) authPill.style.display = 'inline-flex';
        if (authUserName) authUserName.innerText = `Xin chào, ${session.displayName || session.username}`;
        if (authRoleTag) {
            authRoleTag.innerText = isSystemAdmin ? 'ADMIN' : 'KTV';
            authRoleTag.className = isSystemAdmin ? 'auth-role-tag admin' : 'auth-role-tag ktv';
        }
        if (welcomeModal) welcomeModal.style.display = 'none';
        document.body.classList.remove('is-unauthenticated');
    }

    // Áp dụng vai trò (Admin vs KTV)
    if (isSystemAdmin) {
        document.body.classList.remove('role-operator');
    } else {
        document.body.classList.add('role-operator');
    }
}

async function initUserSession() {
    // 1. Đọc tham số sync_token từ URL (nếu có chuyển tiếp từ bookmarklet hoặc login)
    const urlParams = new URLSearchParams(window.location.search);
    const syncToken = urlParams.get('sync_token');
    const syncUser = urlParams.get('sync_user');
    if (syncToken) {
        let parsedUser = {};
        try {
            parsedUser = JSON.parse(decodeURIComponent(syncUser));
        } catch (e) {
            parsedUser = { TaiKhoan: syncUser, HoTen: syncUser };
        }
        setTtsAuthSession(syncToken, parsedUser);
        // Làm sạch URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // 2. Lấy thông tin server & kiểm tra vai trò admin
    let serverData = { is_local: false, has_server_token: false };
    try {
        const res = await fetch('/api/current_user');
        if (res.ok) {
            serverData = await res.json();
        }
    } catch (e) {
        console.warn("Lỗi kiểm tra current_user:", e);
    }

    isSystemAdmin = serverData.is_local || urlParams.get('role') === 'admin';

    // Cập nhật phiên mới nhất từ Chrome nếu đang ở máy chủ Localhost
    if (serverData.is_local && serverData.has_server_token && serverData.server_token) {
        setTtsAuthSession(serverData.server_token, serverData.server_user || { TaiKhoan: "admin", HoTen: "Quản trị viên (Server)" });
    } else if (!serverData.is_local && !serverData.has_server_token) {
        // Nếu là client LAN và máy chủ chưa nhận token của IP này,
        // dọn sạch session 'quangvu' nếu trước đó client này từng vô tình lưu lại
        const existing = getTtsAuthSession();
        if (existing && (existing.username === 'quangvu' || (existing.displayName && existing.displayName.includes('Quang Vũ')))) {
            localStorage.removeItem('tts_auth_token');
            localStorage.removeItem('tts_auth_user');
        }
    }

    // Hiển thị nút dùng nhanh phiên máy chủ nếu là Localhost có sẵn token
    const serverQuickBox = document.getElementById('loginServerQuickBox');
    if (serverQuickBox) {
        serverQuickBox.style.display = (serverData.is_local && serverData.has_server_token) ? 'block' : 'none';
    }

    applyUserSessionState();
}

// KHỞI CHẠY HỆ THỐNG
initUserSession();
setInterval(fetchStatus, 1500);
setInterval(() => loadTickets(false), 8000);
fetchStatus();
loadTickets(true);

// ==============================================================================
// ĐIỀU KHIỂN DROPDOWN LIVE LOG TRÊN THANH IDLE BAR
// ==============================================================================
let isLiveLogOpen = false;

function toggleLiveLogDropdown(event, forceClose = false) {
    if (event) event.stopPropagation();
    const dd = document.getElementById('liveLogDropdown');
    if (!dd) return;
    if (forceClose) {
        isLiveLogOpen = false;
        dd.classList.remove('show');
        return;
    }
    isLiveLogOpen = !isLiveLogOpen;
    dd.classList.toggle('show', isLiveLogOpen);

    // Khi người dùng bấm mở Live Log để xem -> Đánh dấu đã xem và tắt nhấp nháy ngay
    if (isLiveLogOpen) {
        window.liveLogDismissed = true;
        window.lastSeenErrorCount = window.currentLiveErrCount || 0;
        const pillLog = document.getElementById('pillLiveLog');
        const logTxt = document.getElementById('liveLogStatusText');
        const errBadge = document.getElementById('liveLogErrorBadge');
        if (pillLog) pillLog.classList.remove('has-error');
        if (logTxt) logTxt.innerText = 'Bình thường';
        if (errBadge) errBadge.style.display = 'none';

        const term = document.getElementById('logTerminal');
        if (term) term.scrollTop = term.scrollHeight;
    }
}

async function clearLocalLogs() {
    window.liveLogDismissed = true;
    window.lastSeenErrorCount = 0;
    try {
        await fetch('/api/logs/clear', { method: 'POST' });
    } catch (e) {}
    const term = document.getElementById('logTerminal');
    if (term) term.innerHTML = '<div class="log-line" style="color:#64748b; font-style:italic;">Đã xóa toàn bộ nhật ký hệ thống...</div>';
    const pillLog = document.getElementById('pillLiveLog');
    const logTxt = document.getElementById('liveLogStatusText');
    const errBadge = document.getElementById('liveLogErrorBadge');
    if (pillLog) pillLog.classList.remove('has-error');
    if (logTxt) logTxt.innerText = 'Bình thường';
    if (errBadge) errBadge.style.display = 'none';
}

// Đóng dropdown khi click ra ngoài
document.addEventListener('click', function (e) {
    const container = document.querySelector('.live-log-container');
    if (container && !container.contains(e.target)) {
        const dd = document.getElementById('liveLogDropdown');
        if (dd && dd.classList.contains('show')) {
            dd.classList.remove('show');
            isLiveLogOpen = false;
        }
    }
});
