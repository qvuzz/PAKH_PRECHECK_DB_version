// [MODULE: auth_session.js] -> Tự động gắn token Authorization đã chuyển sang static/js/modules/auth_session.js

let isRunning = false;
let currentAutoClose = false;
let currentSystem = 'tts_new';
let currentService = 'data';

// ==================== QUẢN LÝ CHẾ ĐỘ BAN NGÀY / BAN ĐÊM (THEME SYSTEM) ====================
function getAppTheme() {
    return document.documentElement.getAttribute('data-theme') || localStorage.getItem('pakh_theme') || 'light';
}

function updateThemeUI(theme) {
    const btn = document.getElementById('btnThemeToggle');
    const iconSpan = document.getElementById('themeToggleIcon');
    if (!btn) return;

    if (theme === 'dark') {
        if (iconSpan) {
            iconSpan.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;
        }
        btn.title = 'Chuyển sang Giao diện Ban ngày (Light mode)';
    } else {
        if (iconSpan) {
            iconSpan.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;
        }
        btn.title = 'Chuyển sang Giao diện Ban đêm (Dark mode)';
    }
}

function toggleAppTheme() {
    const current = getAppTheme();
    const target = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', target);
    try {
        localStorage.setItem('pakh_theme', target);
    } catch (e) {}
    updateThemeUI(target);
}

// Khởi chạy cập nhật trạng thái UI theme & sidebar collapse ngay khi DOM sẵn sàng
document.addEventListener('DOMContentLoaded', function() {
    const saved = getAppTheme();
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeUI(saved);
    initSidebarCollapseState();
});

// Điều khiển thu nhỏ / mở rộng menu danh mục bên trái
function toggleSidebarCollapse() {
    const sidebar = document.getElementById('sidebarNav') || document.querySelector('.sidebar-nav');
    const layout = document.querySelector('.main-layout');
    if (!sidebar) return;
    const isCollapsed = sidebar.classList.toggle('collapsed');
    if (layout) layout.classList.toggle('sidebar-collapsed', isCollapsed);
    try {
        localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false');
    } catch (e) {}
    updateSidebarToggleIcon(isCollapsed);
}

function initSidebarCollapseState() {
    try {
        const saved = localStorage.getItem('sidebar_collapsed');
        if (saved === 'true') {
            const sidebar = document.getElementById('sidebarNav') || document.querySelector('.sidebar-nav');
            const layout = document.querySelector('.main-layout');
            if (sidebar) sidebar.classList.add('collapsed');
            if (layout) layout.classList.add('sidebar-collapsed');
            updateSidebarToggleIcon(true);
        } else {
            updateSidebarToggleIcon(false);
        }
    } catch (e) {}
}

function updateSidebarToggleIcon(isCollapsed) {
    const btn = document.getElementById('btnSidebarToggle');
    if (!btn) return;
    const iconCollapse = btn.querySelector('.icon-collapse');
    const iconExpand = btn.querySelector('.icon-expand');
    if (iconCollapse && iconExpand) {
        iconCollapse.style.display = isCollapsed ? 'none' : 'block';
        iconExpand.style.display = isCollapsed ? 'block' : 'none';
    }
    btn.setAttribute('title', isCollapsed ? 'Mở rộng menu bên trái' : 'Thu nhỏ menu bên trái');
}


// Xác định quyền Admin đồng bộ ngay lập tức dựa trên Hostname, cờ Admin hoặc Session quangvu đã lưu
function checkIsLocalHost() {
    const host = window.location.hostname || '';
    return host === 'localhost' || host === '127.0.0.1' || host === '::1' || host.startsWith('127.');
}
function checkIsUserAdmin() {
    if (checkIsLocalHost()) return true;
    if (localStorage.getItem('pakh_is_admin') === 'true') return true;
    const sp = new URLSearchParams(window.location.search);
    if (sp.get('role') === 'admin' || sp.get('admin') === '1') return true;
    try {
        const uNew = JSON.parse(localStorage.getItem('ttsnew_auth_user') || '{}');
        const uOld = JSON.parse(localStorage.getItem('tts_auth_user') || '{}');
        const checkStr = `${uNew.username || ''} ${uNew.displayName || ''} ${uNew.email || ''} ${uOld.TaiKhoan || ''} ${uOld.HoTen || ''}`.toLowerCase();
        if (checkStr.includes('quangvu') || checkStr.includes('lê quang vũ')) {
            try { localStorage.setItem('pakh_is_admin', 'true'); } catch(e) {}
            return true;
        }
    } catch(e) {}
    return false;
}
let isSystemAdmin = checkIsUserAdmin();
let currentAiEngine = 'regex';
let isUserManagementView = false;

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Cập nhật số lượng và hiệu ứng chớp đỏ khi có phiếu mới ở từng module Loại PAKH
function updateNavBadge(elem, count) {
    if (!elem) return;
    const num = parseInt(count) || 0;
    elem.innerText = num;
    const navItem = elem.closest('.nav-item');
    if (num > 0) {
        elem.classList.add('has-new');
        if (navItem) navItem.classList.add('has-new-tickets');
    } else {
        elem.classList.remove('has-new');
        if (navItem) navItem.classList.remove('has-new-tickets');
    }
}

let autoCloseState = {
    tts_old: false,
    tts_new: false,
    mode: 'none'
};

function getCurrentSystemKey() {
    return (currentSystem === 'tts_old' || currentSystem === 'tts_old_api') ? 'tts_old' : 'tts_new';
}

function updateModeUI() {
    const sysKey = getCurrentSystemKey();
    const isSysNew = (sysKey === 'tts_new');
    const isSysActive = isSysNew ? autoCloseState.tts_new : autoCloseState.tts_old;
    currentAutoClose = isSysActive;

    const chkUnified = document.getElementById('chkAutoCloseUnified');
    const ctrlUnified = document.getElementById('ctrlAutoCloseUnified');
    const lblUnified = document.getElementById('autoCloseUnifiedLabel');

    if (chkUnified) {
        if (!isSystemAdmin) {
            chkUnified.checked = false;
            chkUnified.disabled = true;
        } else {
            chkUnified.disabled = false;
            chkUnified.checked = isSysActive;
        }
    }

    if (lblUnified) {
        lblUnified.innerText = 'Tự đóng TTS Mới';
    }

    if (ctrlUnified) {
        if (isSysActive) {
            ctrlUnified.style.background = '#fef2f2';
            ctrlUnified.style.borderColor = 'rgba(220,38,38,0.5)';
            ctrlUnified.style.color = '#dc2626';
            ctrlUnified.title = `Chế độ: ĐANG BẬT tự động đóng cho TTS Mới (Bấm để tắt)`;
        } else {
            ctrlUnified.style.background = '#f8fafc';
            ctrlUnified.style.borderColor = '#cbd5e1';
            ctrlUnified.style.color = '#64748b';
            ctrlUnified.title = `Chế độ: ĐANG TẮT tự động đóng cho TTS Mới (Bấm để bật)`;
        }
    }

    const modeLabelBadge = document.getElementById('modeLabelBadge');
    const headerModeTag = document.getElementById('headerModeTag');

    if (modeLabelBadge) {
        if (autoCloseState.mode === 'all') {
            modeLabelBadge.className = 'badge-mode auto';
            modeLabelBadge.innerText = 'Bật: Cả TTS Cũ & Mới';
        } else if (autoCloseState.mode === 'tts_old') {
            modeLabelBadge.className = 'badge-mode auto';
            modeLabelBadge.innerText = 'Bật: Chỉ TTS Cũ';
        } else if (autoCloseState.mode === 'tts_new') {
            modeLabelBadge.className = 'badge-mode auto';
            modeLabelBadge.innerText = 'Bật: Chỉ TTS Mới';
        } else {
            modeLabelBadge.className = 'badge-mode manual';
            modeLabelBadge.innerText = 'Tắt: Đóng thủ công 100%';
        }
    }
    if (headerModeTag) {
        if (autoCloseState.mode === 'all') {
            headerModeTag.style.color = '#dc2626';
            headerModeTag.innerText = 'Chế độ: Tự đóng cả TTS Cũ & Mới (Đang bật)';
        } else if (autoCloseState.mode === 'tts_old') {
            headerModeTag.style.color = '#0284c7';
            headerModeTag.innerText = 'Chế độ: Chỉ tự đóng TTS Cũ (Đang bật)';
        } else if (autoCloseState.mode === 'tts_new') {
            headerModeTag.style.color = '#6366f1';
            headerModeTag.innerText = 'Chế độ: Chỉ tự đóng TTS Mới (Đang bật)';
        } else {
            headerModeTag.style.color = '#b45309';
            headerModeTag.innerText = 'Chế độ: Đóng thủ công 100%';
        }
    }
}

function handleAutoCloseClick(e) {
    if (e) e.stopPropagation();

    // 1. Nếu không phải Admin (Client LAN kết nối tới) -> Mở modal thông báo bị khóa
    if (!isSystemAdmin) {
        showAutoCloseClientBlocked();
        return;
    }

    const sysKey = getCurrentSystemKey();
    const isSysNew = (sysKey === 'tts_new');
    const isSysActive = isSysNew ? autoCloseState.tts_new : autoCloseState.tts_old;

    // 2. Nếu đang BẬT -> Click là TẮT ngay lập tức cho riêng hệ thống này
    if (isSysActive) {
        if (isSysNew) autoCloseState.tts_new = false;
        else autoCloseState.tts_old = false;
        updateModeUI();
        saveAutoCloseConfig(sysKey, false);
        return;
    }

    // 3. Nếu đang TẮT -> Bật Modal xác nhận 2 bước cho hệ thống này
    openAutoCloseConfirmModal();
}

function openAutoCloseConfirmModal() {
    const modal = document.getElementById('modalAutoCloseConfirm');
    const step1 = document.getElementById('autoCloseStep1');
    const step2 = document.getElementById('autoCloseStep2');
    const blocked = document.getElementById('autoCloseClientBlocked');
    if (!modal) return;

    const sysKey = getCurrentSystemKey();
    const sysName = 'HỆ THỐNG TTS MỚI';

    const targetSub1 = document.getElementById('autoCloseModalTargetSub1');
    const targetSub2 = document.getElementById('autoCloseModalTargetSub2');
    const targetSysTag1 = document.getElementById('autoCloseTargetSysName1');
    const targetSysTag2 = document.getElementById('autoCloseTargetSysName2');

    if (targetSub1) targetSub1.innerText = `Kích hoạt Tự Động Đóng Phiếu cho ${sysName}`;
    if (targetSub2) targetSub2.innerText = `Trách nhiệm vận hành KTV — ${sysName}`;
    if (targetSysTag1) targetSysTag1.innerText = sysName;
    if (targetSysTag2) targetSysTag2.innerText = sysName;

    if (step1) step1.style.display = 'block';
    if (step2) step2.style.display = 'none';
    if (blocked) blocked.style.display = 'none';
    modal.style.display = 'flex';
}

function proceedToAutoCloseStep2() {
    const step1 = document.getElementById('autoCloseStep1');
    const step2 = document.getElementById('autoCloseStep2');
    if (step1) step1.style.display = 'none';
    if (step2) step2.style.display = 'block';
}

function showAutoCloseClientBlocked() {
    const modal = document.getElementById('modalAutoCloseConfirm');
    const step1 = document.getElementById('autoCloseStep1');
    const step2 = document.getElementById('autoCloseStep2');
    const blocked = document.getElementById('autoCloseClientBlocked');
    if (!modal) return;
    if (step1) step1.style.display = 'none';
    if (step2) step2.style.display = 'none';
    if (blocked) blocked.style.display = 'block';
    modal.style.display = 'flex';
}

function cancelAutoCloseModal() {
    const modal = document.getElementById('modalAutoCloseConfirm');
    if (modal) modal.style.display = 'none';
    updateModeUI();
}

async function confirmAndActivateAutoClose() {
    cancelAutoCloseModal();
    const sysKey = getCurrentSystemKey();
    if (sysKey === 'tts_new') autoCloseState.tts_new = true;
    else autoCloseState.tts_old = true;
    updateModeUI();
    await saveAutoCloseConfig(sysKey, true);
}

async function saveAutoCloseConfig(targetSystem, isActive) {
    try {
        const sys = targetSystem || getCurrentSystemKey();
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                system: sys,
                auto_close: !!isActive
            })
        });
        loadTickets();
    } catch (e) {
        console.error("Lỗi cập nhật cấu hình tự động đóng:", e);
    }
}

async function toggleAutoCloseUnified(isChecked) {
    handleAutoCloseClick();
}

async function toggleAutoCloseMode(isChecked) {
    return handleAutoCloseClick();
}

async function handleAiSummaryModelChange(modelValue) {
    const curTok = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';
    const curUser = (typeof getTtsNewAuthUser === 'function') ? getTtsNewAuthUser() : null;
    const isQv = curUser && ((curUser.username || '').toLowerCase().includes('quangvu') || (curUser.displayName || '').toLowerCase().includes('quang vũ'));

    if (!isSystemAdmin && !isQv) {
        alert('Bạn không có quyền Admin để thay đổi mô hình Tóm tắt nội dung!\n(Chỉ tài khoản Admin mới được phép cấu hình)');
        const selAi = document.getElementById('selectAiSummaryModel');
        if (selAi) selAi.value = currentAiEngine || 'regex';
        return;
    }

    try {
        const headers = { 'Content-Type': 'application/json' };
        if (curTok) headers['Authorization'] = curTok;

        const res = await fetch('/api/config', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                ai_summary_engine: modelValue
            })
        });
        const data = await res.json();
        if (data.success) {
            currentAiEngine = data.ai_summary_engine || modelValue;
            const modelName = currentAiEngine === 'regex' ? 'Regex (Quy tắc mẫu)' : 'Qwen 2.5 (Offline AI)';
            alert(`Đã chuyển mô hình Tóm tắt sang: ${modelName}\nCác lượt quét và tiền kiểm tiếp theo sẽ áp dụng mô hình này.`);
        } else {
            alert('Lỗi cập nhật mô hình: ' + (data.error || 'Không xác định'));
        }
    } catch (e) {
        alert('Lỗi kết nối máy chủ: ' + e.message);
    }
}

let isFetchingStatus = false;

async function fetchStatus() {
    if (isFetchingStatus) return;
    isFetchingStatus = true;
    try {
        const regParam = encodeURIComponent(currentRegion || 'ALL');
        const res = await fetch(`/api/status?region=${regParam}`);
        const data = await res.json();

        // Đồng bộ lựa chọn mô hình Tóm tắt nội dung
        if (data.ai_summary_engine) {
            currentAiEngine = data.ai_summary_engine;
            const selAi = document.getElementById('selectAiSummaryModel');
            if (selAi && selAi.value !== currentAiEngine) {
                selAi.value = currentAiEngine;
            }
            if (selAi) {
                const curUser = (typeof getTtsNewAuthUser === 'function') ? getTtsNewAuthUser() : null;
                const isQv = curUser && ((curUser.username || '').toLowerCase().includes('quangvu') || (curUser.displayName || '').toLowerCase().includes('quang vũ'));
                const canChangeAi = isSystemAdmin || isQv;

                if (!canChangeAi) {
                    selAi.disabled = true;
                    selAi.title = "Chỉ tài khoản Quản trị viên mới có quyền đổi mô hình AI";
                    selAi.style.opacity = "0.7";
                    selAi.style.cursor = "not-allowed";
                } else {
                    selAi.disabled = false;
                    selAi.title = "Chọn mô hình Tóm tắt nội dung PAKH (Qwen 2.5 hoặc Regex)";
                    selAi.style.opacity = "1";
                    selAi.style.cursor = "pointer";
                }
            }
        }

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

        window.currentServerStatus = data.status;
        const isUnifiedRunning = isRunning || (data.status === 'PROCESSING') || (data.status === 'WAITING');

        // Điều khiển Nút Refresh Icon: xoay khi hệ thống đang quét ngầm (PROCESSING)
        const btnRefresh = document.getElementById('btnRefreshScan');
        if (btnRefresh) {
            if (data.status === 'PROCESSING') {
                btnRefresh.classList.add('spinning');
                btnRefresh.title = 'Hệ thống đang tiền kiểm chuyên sâu...';
            } else {
                btnRefresh.classList.remove('spinning');
                btnRefresh.title = 'Làm mới & kích hoạt quét tiền kiểm ngay';
            }
        }

        const dot = document.getElementById('statusDot');
        if (dot) {
            dot.className = 'status-dot';
            if (data.status === 'PROCESSING') dot.classList.add('processing');
            else if (data.status === 'WAITING') dot.classList.add('waiting');
            else if (isRunning) dot.classList.add('active');
        }
        let msg = data.status_message || 'Sẵn sàng';
        const statusText = document.getElementById('statusText');
        if (statusText) {
            statusText.innerText = msg;
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

        if (data.system_counts) {
            const sc = data.system_counts;
            const bOldData = document.getElementById('badgeOldData');
            const bOldVoice = document.getElementById('badgeOldVoice');
            const bOldApiData = document.getElementById('badgeOldApiData');
            const bOldApiVoice = document.getElementById('badgeOldApiVoice');
            const bNewData = document.getElementById('badgeNewData');
            const bNewCall = document.getElementById('badgeNewCall');
            const bNewSpamCall = document.getElementById('badgeNewSpamCall');
            const bNewSms = document.getElementById('badgeNewSms');
            const bNewRoaming = document.getElementById('badgeNewRoaming');
            const bNewSim = document.getElementById('badgeNewSim');
            const bNewOther = document.getElementById('badgeNewOther');
            const bNewVoice = document.getElementById('badgeNewVoice');
            const bTotalClosed = document.getElementById('badgeTotalClosed');
            const bTotalAll = document.getElementById('badgeTotalAll');

            updateNavBadge(bOldData, sc.tts_old_data);
            updateNavBadge(bOldVoice, sc.tts_old_voice);
            updateNavBadge(bOldApiData, sc.tts_old_api_data);
            updateNavBadge(bOldApiVoice, sc.tts_old_api_voice);
            updateNavBadge(bNewData, sc.tts_new_data);
            updateNavBadge(bNewCall, sc.tts_new_call);
            updateNavBadge(bNewSpamCall, sc.tts_new_spam_call);
            updateNavBadge(bNewSms, sc.tts_new_sms);
            updateNavBadge(bNewRoaming, sc.tts_new_roaming);
            updateNavBadge(bNewSim, sc.tts_new_sim);
            updateNavBadge(bNewOther, sc.tts_new_other);
            updateNavBadge(bNewVoice, sc.tts_new_voice);
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

        if (data.auto_close_tts_old !== undefined && data.auto_close_tts_new !== undefined) {
            autoCloseState.tts_old = !!data.auto_close_tts_old;
            autoCloseState.tts_new = !!data.auto_close_tts_new;
            autoCloseState.mode = data.auto_close_mode || 'none';
        } else if (data.auto_close_mode) {
            const m = data.auto_close_mode;
            autoCloseState.mode = m;
            autoCloseState.tts_old = (m === 'all' || m === 'tts_old');
            autoCloseState.tts_new = (m === 'all' || m === 'tts_new');
        }
        updateModeUI();

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
        const logDot = document.getElementById('liveLogDot');
        const errBadge = document.getElementById('liveLogErrorBadge');

        if (pillLog) {
            if (hasError) {
                pillLog.classList.add('has-error');
                if (logDot) {
                    logDot.className = 'svc-status-dot inactive';
                    logDot.style.backgroundColor = '#ef4444';
                }
                if (errBadge) errBadge.style.display = 'inline-block';
            } else {
                pillLog.classList.remove('has-error');
                if (logDot) {
                    logDot.className = 'svc-status-dot active';
                    logDot.style.backgroundColor = '#16a34a';
                }
                if (errBadge) errBadge.style.display = 'none';
            }
        }

    } catch (e) {
        console.error("Lỗi fetch status:", e);
    } finally {
        isFetchingStatus = false;
    }
}

let lastTicketsSignature = "";
let currentTableTab = 'chua_dong';
let currentRegion = 'ALL';
let isRegionLocked = false;
let urlRouteRegion = null;

function detectRegionFromUrl() {
    const p = (window.location.pathname || '').toLowerCase();
    const sp = new URLSearchParams(window.location.search);
    const qReg = (sp.get('region') || '').toUpperCase();
    if (p.includes('/mien-bac') || p.includes('/mb') || qReg === 'MB') return 'MB';
    if (p.includes('/mien-trung') || p.includes('/mt') || qReg === 'MT') return 'MT';
    if (p.includes('/mien-nam') || p.includes('/mn') || qReg === 'MN') return 'MN';
    return null;
}

// Khởi tạo vùng từ URL (nếu có trong link thì khởi tạo theo link đó, Superadmin không bị khóa)
urlRouteRegion = detectRegionFromUrl();
if (urlRouteRegion) {
    currentRegion = urlRouteRegion;
    if (isSystemAdmin) {
        isRegionLocked = false;
        urlRouteRegion = null;
    } else {
        isRegionLocked = true;
    }
} else {
    currentRegion = localStorage.getItem('pakh_region') || 'ALL';
    isRegionLocked = false;
}

function applyRegionUI(locked = false) {
    const regSelect = document.getElementById('regionSelect');
    if (!regSelect) return;
    if (locked && !isSystemAdmin) {
        regSelect.disabled = true;
        regSelect.style.cursor = 'not-allowed';
        regSelect.style.background = '#f1f5f9';
        regSelect.style.color = '#334155';
        regSelect.style.borderColor = '#94a3b8';
        regSelect.title = 'Khu vực đã được cố định theo liên kết hoặc tài khoản KTV';
        const targetVal = currentRegion || 'ALL';
        if (regSelect.value !== targetVal) {
            regSelect.value = targetVal;
        }
    } else {
        regSelect.disabled = false;
        regSelect.style.cursor = 'pointer';
        regSelect.style.background = '#ffffff';
        regSelect.style.color = '#0f172a';
        regSelect.style.borderColor = '#94a3b8';
        regSelect.title = 'Chọn khu vực xem phiếu (Toàn quốc hoặc từng Miền)';
        if (regSelect.value !== currentRegion) {
            regSelect.value = currentRegion;
        }
    }
}

function onRegionChange(val) {
    if (isRegionLocked && !isSystemAdmin) return;
    currentRegion = val || 'ALL';
    urlRouteRegion = currentRegion;
    localStorage.setItem('pakh_region', currentRegion);

    // Cập nhật URL động tương ứng với miền được chọn
    let regSlug = '';
    if (currentRegion === 'MB') regSlug = '/mien-bac';
    else if (currentRegion === 'MT') regSlug = '/mien-trung';
    else if (currentRegion === 'MN') regSlug = '/mien-nam';

    let srvSlug = '/data';
    if (currentService === 'call') srvSlug = '/cuoc-goi';
    else if (currentService === 'spam_call') srvSlug = '/chan-goi-ngoai-mang';
    else if (currentService === 'sms') srvSlug = '/tin-nhan';
    else if (currentService === 'roaming') srvSlug = '/chuyen-vung-quoc-te';
    else if (currentService === 'sim') srvSlug = '/sim-multisim';
    else if (currentService === 'other') srvSlug = '/khac';

    let newPath = regSlug ? `/ttsmoi${regSlug}${srvSlug}` : `/ttsmoi${srvSlug}`;
    if (window.location.pathname.startsWith('/ttsmoi') || window.location.pathname.startsWith('/mien-') || window.location.pathname.startsWith('/mb') || window.location.pathname.startsWith('/mn') || window.location.pathname.startsWith('/mt')) {
        if (window.location.pathname !== newPath) {
            history.pushState({ sys: 'tts_new', srv: currentService, region: currentRegion }, '', newPath);
        }
    }

    lastTicketsSignature = "";
    if (isHistoryStatsView) {
        loadClosedAnalytics();
    } else {
        loadTickets(true, true);
    }
    fetchStatus();
}
window.onRegionChange = onRegionChange;
window.applyRegionUI = applyRegionUI;

// SẮP XẾP DANH SÁCH PHIẾU THEO NGÀY TIẾP NHẬN
let sortIncidentTimeOrder = 'none'; // 'none', 'desc' (mới nhất trước), 'asc' (cũ nhất trước)

function parseIncidentDate(dateStr) {
    if (!dateStr || dateStr === '--' || dateStr === 'null') return 0;
    const str = String(dateStr).trim();
    // 1. DD/MM/YYYY HH:mm[:ss] hoặc DD/MM/YYYY
    const dmyMatch = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?/);
    if (dmyMatch) {
        const day = parseInt(dmyMatch[1], 10);
        const month = parseInt(dmyMatch[2], 10) - 1;
        const year = parseInt(dmyMatch[3], 10);
        const hour = parseInt(dmyMatch[4] || 0, 10);
        const minute = parseInt(dmyMatch[5] || 0, 10);
        const second = parseInt(dmyMatch[6] || 0, 10);
        return new Date(year, month, day, hour, minute, second).getTime() || 0;
    }
    // 2. YYYY-MM-DD[T/ ]HH:mm[:ss]
    const isoMatch = str.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T\s]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?/);
    if (isoMatch) {
        const year = parseInt(isoMatch[1], 10);
        const month = parseInt(isoMatch[2], 10) - 1;
        const day = parseInt(isoMatch[3], 10);
        const hour = parseInt(isoMatch[4] || 0, 10);
        const minute = parseInt(isoMatch[5] || 0, 10);
        const second = parseInt(isoMatch[6] || 0, 10);
        return new Date(year, month, day, hour, minute, second).getTime() || 0;
    }
    const ts = Date.parse(str);
    return isNaN(ts) ? 0 : ts;
}

function toggleIncidentTimeSort() {
    if (sortIncidentTimeOrder === 'none') {
        sortIncidentTimeOrder = 'desc';
    } else if (sortIncidentTimeOrder === 'desc') {
        sortIncidentTimeOrder = 'asc';
    } else {
        sortIncidentTimeOrder = 'none';
    }
    updateSortIncidentTimeUI();
    renderTicketsTable(true);
}
window.toggleIncidentTimeSort = toggleIncidentTimeSort;

function updateSortIncidentTimeUI() {
    const iconContainer = document.getElementById('sortIncidentTimeIcon');
    const th = document.getElementById('thIncidentTime');
    if (!iconContainer) return;

    if (sortIncidentTimeOrder === 'desc') {
        iconContainer.className = 'sort-icon active';
        iconContainer.innerHTML = `
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <polyline points="19 12 12 19 5 12"></polyline>
            </svg>
        `;
        if (th) th.title = "Đang xếp: Mới nhất trước (Bấm để đổi sang cũ nhất trước)";
    } else if (sortIncidentTimeOrder === 'asc') {
        iconContainer.className = 'sort-icon active';
        iconContainer.innerHTML = `
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="19" x2="12" y2="5"></line>
                <polyline points="5 12 12 5 19 12"></polyline>
            </svg>
        `;
        if (th) th.title = "Đang xếp: Cũ nhất trước (Bấm để quay về mặc định)";
    } else {
        iconContainer.className = 'sort-icon';
        iconContainer.innerHTML = `
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M7 15l5 5 5-5"/>
                <path d="M7 9l5-5 5 5"/>
            </svg>
        `;
        if (th) th.title = "Thứ tự mặc định (Bấm để sắp xếp theo ngày tiếp nhận)";
    }
}
window.updateSortIncidentTimeUI = updateSortIncidentTimeUI;

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
        const clientAuthTok = (typeof getTtsNewAuthToken === 'function' ? getTtsNewAuthToken() : '') || 
                              (typeof getTtsAuthSession === 'function' && getTtsAuthSession() ? getTtsAuthSession().token : '');
        const reqHeaders = clientAuthTok ? { 'Authorization': clientAuthTok } : {};
        const regParam = encodeURIComponent(currentRegion || 'ALL');
        const res = await fetch(`/api/tickets/closed_stats?period=${encodeURIComponent(currentClosedPeriod)}&source=${encodeURIComponent(currentClosedSource)}&service_type=${encodeURIComponent(currentClosedService)}&region=${regParam}`, {
            headers: reqHeaders
        });
        const data = await res.json();

        // 🎯 Khóa cố định phân vùng cho KTV nếu server yêu cầu
        if (data.is_region_locked && !isSystemAdmin) {
            isRegionLocked = true;
            if (data.effective_region) {
                currentRegion = data.effective_region;
            }
            applyRegionUI(true);
        }

        // 🎯 Cập nhật huy hiệu phân vùng trên Dashboard Thống kê
        const regBadge = document.getElementById('caRegionBadge');
        if (regBadge) {
            const effReg = (data.effective_region || currentRegion || 'ALL').toUpperCase();
            if (effReg === 'MB') {
                regBadge.innerText = 'Khu vực: Miền Bắc (SOC1)';
                regBadge.className = 'ca-badge-pill ca-badge-blue';
            } else if (effReg === 'MN') {
                regBadge.innerText = 'Khu vực: Miền Nam (SOC2)';
                regBadge.className = 'ca-badge-pill ca-badge-green';
            } else if (effReg === 'MT') {
                regBadge.innerText = 'Khu vực: Miền Trung (SOC3)';
                regBadge.className = 'ca-badge-pill ca-badge-amber';
            } else {
                regBadge.innerText = 'Toàn quốc (3 Miền)';
                regBadge.className = 'ca-badge-pill ca-badge-purple';
            }
        }

        // 1. Cập nhật các thẻ KPI chuẩn hóa
        const elTotal = document.getElementById('caValTotal');
        const elAuto = document.getElementById('caValAuto');
        const elAutoPct = document.getElementById('caValAutoPercent');
        const elManual = document.getElementById('caValManual');
        const elManualPct = document.getElementById('caValManualPercent');
        const elBarManual = document.getElementById('caBarManual');
        const elSynced = document.getElementById('caValSynced');
        const elSubManual = document.getElementById('caSubManual');
        const elToday = document.getElementById('caValToday');
        const elTtsNew = document.getElementById('caValTtsNew');
        const elTtsOld = document.getElementById('caValTtsOld');
        const elData = document.getElementById('caValData');
        const elCall = document.getElementById('caValCall');
        const elSms = document.getElementById('caValSms');
        const elOther = document.getElementById('caValOther');
        const elBadge = document.getElementById('caSourceBadge');

        if (elTotal) elTotal.innerText = (data.total || 0).toLocaleString();
        if (elManual) elManual.innerText = (data.manual_cnt || 0).toLocaleString();
        if (elManualPct) elManualPct.innerText = `${data.manual_percent || 0}%`;
        if (elBarManual) elBarManual.style.width = `${Math.min(100, data.manual_percent || 0)}%`;

        if (elAuto) elAuto.innerText = (data.auto_cnt || 0).toLocaleString();
        if (elAutoPct) elAutoPct.innerText = `${data.auto_percent || 0}%`;
        if (elSynced) elSynced.innerText = (data.synced_cnt || 0).toLocaleString();

        if (elSubManual) {
            if (data.staff_list && data.staff_list.length > 0) {
                const names = data.staff_list.map(s => `${s.name} (${s.count})`).join(', ');
                elSubManual.innerHTML = `KTV: <span style="font-weight:600; color:#15803d;">${escapeHtml(names)}</span>`;
            } else {
                elSubManual.innerText = "Chưa có lượt đóng qua giao diện";
            }
        }

        if (elToday) elToday.innerText = (data.today_cnt || 0).toLocaleString();
        if (elTtsNew) elTtsNew.innerText = (data.tts_new_cnt || 0).toLocaleString();
        if (elTtsOld) elTtsOld.innerText = (data.tts_old_cnt || 0).toLocaleString();
        if (elData) elData.innerText = (data.data_cnt || 0).toLocaleString();
        if (elCall) elCall.innerText = (data.call_cnt || 0).toLocaleString();
        if (elSms) elSms.innerText = (data.sms_cnt || 0).toLocaleString();
        if (elOther) elOther.innerText = (data.other_cnt || 0).toLocaleString();

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

function selectHistoryStats(updateUrl = true) {
    isHistoryStatsView = true;
    currentSystem = currentClosedSource;
    currentService = currentClosedService;
    currentTableTab = 'da_dong';

    if (updateUrl && window.location.pathname !== '/thong-ke') {
        history.pushState({ tab: 'thong-ke' }, '', '/thong-ke');
    }

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
    isUserManagementView = false;
    const tableDataView = document.getElementById('tableDataView');
    if (tableDataView) tableDataView.style.display = 'none';
    const faContainer = document.getElementById('flowAuditContainer');
    if (faContainer) faContainer.style.display = 'none';
    const userMgmtContainer = document.getElementById('userManagementContainer');
    if (userMgmtContainer) userMgmtContainer.style.display = 'none';

    const sel = document.getElementById('caServiceSelect');
    if (sel) sel.value = currentClosedService;

    loadClosedAnalytics();
}

function adjustTableColumnsLayout(srv, tab) {
    const service = srv || currentService || 'data';
    const currentTab = tab || currentTableTab || 'chua_dong';
    const thStatus = document.getElementById('thStatus');
    const thCategory = document.getElementById('thCategory');
    const thProfile = document.getElementById('thProfile');
    const thInfrastructure = document.getElementById('thInfrastructure');
    const thCemData = document.getElementById('thCemData');
    const thAiSummary = document.getElementById('thAiSummary');
    const thComment = document.getElementById('thComment');
    const thActionPlan = document.getElementById('thActionPlan');

    if (service === 'spam_call') {
        // Module Chặn gọi ngoại mạng:
        // Khóa cứng STT: 36px (col 1)
        // Mã Phiếu: 11% (col 2)
        // Nhà Mạng: 7.5% (col 3)
        // Số Thuê Bao: 7% (col 4)
        // Cam Kết & File: 10% (col 5)
        // Tiếp Nhận: 6% (col 6)
        // Ẩn: thProfile, thInfrastructure, thCemData
        // Mở rộng Nội dung (thAiSummary: 26%) và 2 cột 10, 11 (thComment: 12%, thActionPlan: 12%)
        // Thao Tác: 6%
        // Tổng: 11 + 7.5 + 7 + 10 + 6 + 26 + 12 + 12 + 6 = 97.5% (+ STT 2.5% = 100%)
        if (thStatus) { thStatus.style.display = ''; thStatus.innerText = 'Nhà Mạng'; thStatus.style.width = '7.5%'; thStatus.style.minWidth = '80px'; }
        if (thCategory) { thCategory.innerText = 'Cam Kết & File'; thCategory.style.width = '10%'; thCategory.style.minWidth = '110px'; }
        if (thProfile) thProfile.style.display = 'none';
        if (thInfrastructure) thInfrastructure.style.display = 'none';
        if (thCemData) thCemData.style.display = 'none';
        if (thAiSummary) { thAiSummary.style.width = '26%'; thAiSummary.style.minWidth = '260px'; }
        if (thComment) { thComment.style.width = '12%'; thComment.style.minWidth = '120px'; }
        if (thActionPlan) { thActionPlan.style.width = '12%'; thActionPlan.style.minWidth = '120px'; }
    } else if (service === 'call' || service === 'sms' || service === 'roaming' || service === 'sim') {
        // Module Cuộc gọi, Tin nhắn, Chuyển vùng quốc tế, Sim/MultiSIM:
        // Ẩn: thStatus (0%), thCemData (0%)
        if (thStatus) thStatus.style.display = 'none';
        if (thCategory) {
            if (service === 'call') thCategory.innerText = 'Loại Cuộc Gọi';
            else if (service === 'sms') thCategory.innerText = 'Loại Tin Nhắn';
            else if (service === 'roaming') thCategory.innerText = 'Loại CVQT';
            else if (service === 'sim') thCategory.innerText = 'Loại SIM';
            thCategory.style.width = '7%';
            thCategory.style.minWidth = '92px';
        }
        if (thProfile) {
            if (service === 'call') thProfile.innerText = 'Hồ Sơ (HSS/VoLTE)';
            else if (service === 'roaming') thProfile.innerText = 'Hồ Sơ (SAPC/HLR)';
            else thProfile.innerText = 'Trạng Thái (SAPC)';
            thProfile.style.display = '';
            thProfile.style.width = '8%';
            thProfile.style.minWidth = '95px';
        }
        if (thInfrastructure) {
            thInfrastructure.innerText = (service === 'sms') ? 'Hạ Tầng' : 'Sóng';
            thInfrastructure.style.display = '';
            thInfrastructure.style.width = '4.5%';
            thInfrastructure.style.minWidth = '52px';
        }
        if (thCemData) thCemData.style.display = 'none';
        if (thAiSummary) { thAiSummary.style.width = '26%'; thAiSummary.style.minWidth = '260px'; }
        if (thComment) { thComment.style.width = '11%'; thComment.style.minWidth = '115px'; }
        if (thActionPlan) { thActionPlan.style.width = '11%'; thActionPlan.style.minWidth = '115px'; }
    } else if (service === 'other') {
        // Module Gói Cước & PA Khác:
        if (thStatus) thStatus.style.display = 'none';
        if (thCategory) { thCategory.innerText = 'Loại PAKH'; thCategory.style.width = '6.5%'; thCategory.style.minWidth = '90px'; }
        if (thProfile) { thProfile.innerText = 'Gói Cước Core'; thProfile.style.display = ''; thProfile.style.width = '7.5%'; thProfile.style.minWidth = '95px'; }
        if (thInfrastructure) { thInfrastructure.innerText = 'Hạ Tầng'; thInfrastructure.style.display = ''; thInfrastructure.style.width = '4%'; thInfrastructure.style.minWidth = '50px'; }
        if (thCemData) { thCemData.style.display = ''; thCemData.innerText = 'Dữ Liệu CEM'; thCemData.style.width = '6.5%'; thCemData.style.minWidth = '85px'; }
        if (thAiSummary) { thAiSummary.style.width = '25%'; thAiSummary.style.minWidth = '250px'; }
        if (thComment) { thComment.style.width = '9%'; thComment.style.minWidth = '95px'; }
        if (thActionPlan) { thActionPlan.style.width = '9%'; thActionPlan.style.minWidth = '95px'; }
    } else {
        // Module Data (Mobile Internet) hoặc Toàn bộ CSDL:
        const hideStatusInData = (currentTab === 'da_dong');
        if (thStatus) {
            thStatus.style.display = hideStatusInData ? 'none' : '';
            thStatus.innerText = 'Nhận Định';
            thStatus.style.width = '6.5%';
            thStatus.style.minWidth = '85px';
        }
        if (thCategory) { thCategory.innerText = 'Loại PAKH'; thCategory.style.width = '6.5%'; thCategory.style.minWidth = '90px'; }
        if (thProfile) { thProfile.innerText = 'Hồ Sơ Core'; thProfile.style.display = ''; thProfile.style.width = '7.5%'; thProfile.style.minWidth = '95px'; }
        if (thInfrastructure) { thInfrastructure.innerText = 'Hạ Tầng'; thInfrastructure.style.display = ''; thInfrastructure.style.width = '4%'; thInfrastructure.style.minWidth = '50px'; }
        if (thCemData) { thCemData.style.display = ''; thCemData.innerText = 'Dữ Liệu CEM'; thCemData.style.width = '6.5%'; thCemData.style.minWidth = '85px'; }
        if (hideStatusInData) {
            if (thAiSummary) { thAiSummary.style.width = '26%'; thAiSummary.style.minWidth = '250px'; }
            if (thComment) { thComment.style.width = '8.25%'; thComment.style.minWidth = '90px'; }
            if (thActionPlan) { thActionPlan.style.width = '8.25%'; thActionPlan.style.minWidth = '90px'; }
        } else {
            if (thAiSummary) { thAiSummary.style.width = '23%'; thAiSummary.style.minWidth = '230px'; }
            if (thComment) { thComment.style.width = '6.75%'; thComment.style.minWidth = '85px'; }
            if (thActionPlan) { thActionPlan.style.width = '6.75%'; thActionPlan.style.minWidth = '85px'; }
        }
    }
}

function selectModule(sys, srv, updateUrl = true) {
    if (sys === 'tts_old_api' || sys === 'tts_old') {
        sys = 'tts_new';
        srv = 'data';
    }
    isHistoryStatsView = false;
    currentSystem = 'tts_new';
    currentService = srv;

    if (updateUrl) {
        let regSlug = '';
        if (currentRegion === 'MB') regSlug = '/mien-bac';
        else if (currentRegion === 'MT') regSlug = '/mien-trung';
        else if (currentRegion === 'MN') regSlug = '/mien-nam';

        let srvSlug = '/data';
        if (srv === 'data') srvSlug = '/data';
        else if (srv === 'call') srvSlug = '/cuoc-goi';
        else if (srv === 'spam_call') srvSlug = '/chan-goi-ngoai-mang';
        else if (srv === 'sms') srvSlug = '/tin-nhan';
        else if (srv === 'roaming') srvSlug = '/chuyen-vung-quoc-te';
        else if (srv === 'sim') srvSlug = '/sim-multisim';
        else if (srv === 'other') srvSlug = '/khac';
        else srvSlug = '/cuoc-goi';

        let routePath = regSlug ? `/ttsmoi${regSlug}${srvSlug}` : `/ttsmoi${srvSlug}`;
        if (window.location.pathname !== routePath) {
            history.pushState({ sys: 'tts_new', srv, region: currentRegion }, '', routePath);
        }
    }

    const mainTabs = document.getElementById('mainTabsHeader');
    if (mainTabs) mainTabs.style.display = 'flex';
    isUserManagementView = false;
    const analyticsBox = document.getElementById('closedAnalyticsContainer');
    if (analyticsBox) analyticsBox.style.display = 'none';
    const tableDataView = document.getElementById('tableDataView');
    if (tableDataView) tableDataView.style.display = 'block';
    const faContainer = document.getElementById('flowAuditContainer');
    if (faContainer) faContainer.style.display = 'none';
    const userMgmtContainer = document.getElementById('userManagementContainer');
    if (userMgmtContainer) userMgmtContainer.style.display = 'none';

    // Highlight nav item
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById(`nav-${sys}-${srv}`);
    if (activeBtn) activeBtn.classList.add('active');

    // Cột Mã Phiếu & Quy Trình luôn hiển thị cố định 12 cột để Cột 10 và 11 luôn chuẩn vị trí
    const thTicketCode = document.getElementById('thTicketCode');
    if (thTicketCode) {
        thTicketCode.style.display = 'table-cell';
    }

    // Cập nhật tiêu đề bảng theo module
    const thAiSummary = document.getElementById('thAiSummary');
    const tableTitle = document.getElementById('tableTitleText');

    if (srv === 'call') {
        if (thAiSummary) thAiSummary.innerText = 'Nội Dung Phản Ánh';
        if (tableTitle) tableTitle.innerHTML = `<span>Phiếu Cuộc Gọi — ${sys === 'tts_new' ? 'TTS Mới' : 'TTS Cũ'}</span>`;
    } else if (srv === 'spam_call') {
        if (thAiSummary) thAiSummary.innerText = 'Tóm Tắt Sự Cố & Phản Ánh';
        if (tableTitle) tableTitle.innerHTML = `<span>Phiếu Chặn Gọi Ngoại Mạng — ${sys === 'tts_new' ? 'TTS Mới' : 'TTS Cũ'}</span>`;
    } else if (srv === 'sms') {
        if (thAiSummary) thAiSummary.innerText = 'Nội Dung Tin Nhắn';
        if (tableTitle) tableTitle.innerHTML = `<span>Phiếu Tin Nhắn — ${sys === 'tts_new' ? 'TTS Mới' : 'TTS Cũ'}</span>`;
    } else if (srv === 'roaming') {
        if (thAiSummary) thAiSummary.innerText = 'Nội Dung Phản Ánh';
        if (tableTitle) tableTitle.innerHTML = `<span>Phiếu Chuyển Vùng Quốc Tế — ${sys === 'tts_new' ? 'TTS Mới' : 'TTS Cũ'}</span>`;
    } else if (srv === 'sim') {
        if (thAiSummary) thAiSummary.innerText = 'Nội Dung Phản Ánh';
        if (tableTitle) tableTitle.innerHTML = `<span>Phiếu Sim / MultiSIM — ${sys === 'tts_new' ? 'TTS Mới' : 'TTS Cũ'}</span>`;
    } else if (srv === 'other') {
        if (thAiSummary) thAiSummary.innerText = 'Nội Dung Phản Ánh';
        if (tableTitle) tableTitle.innerHTML = `<span>Phiếu Gói Cước & PA Khác — ${sys === 'tts_new' ? 'TTS Mới' : 'TTS Cũ'}</span>`;
    } else {
        if (thAiSummary) thAiSummary.innerText = 'Tóm Tắt Nội Dung PAKH';
        if (tableTitle) tableTitle.innerHTML = `<span>Phiếu Mobile Internet — ${sys === 'tts_new' ? 'TTS Mới' : 'TTS Cũ'}</span>`;
    }

    // Áp dụng layout độ rộng chuẩn cho tất cả các cột, triệt tiêu việc phình to cột STT
    adjustTableColumnsLayout(srv, currentTableTab);

    // Ẩn/hiện bộ lọc nhận định & nút Tự đóng
    const isDataSrv = (srv === 'data');
    const filterStatus = document.getElementById('filterStatus');
    if (filterStatus) filterStatus.style.display = isDataSrv ? '' : 'none';
    const ctrlAutoClose = document.getElementById('ctrlAutoCloseUnified');
    if (ctrlAutoClose) ctrlAutoClose.style.display = isDataSrv ? 'flex' : 'none';
    const btnCdr = document.getElementById('btnOpenSmscCdrSearch');
    if (btnCdr) btnCdr.style.display = (srv === 'sms') ? 'inline-flex' : 'none';

    // Ẩn bộ lọc nguồn & loại PAKH vì đây là menu chuyên biệt của TTS
    const srcSel = document.getElementById('filterSourceSelect');
    if (srcSel) srcSel.style.display = 'none';
    const catSel = document.getElementById('filterCategorySelect');
    if (catSel) catSel.style.display = 'none';

    updateModeUI();
    switchTableTab(currentTableTab);
}

function selectHistoryModule(tab = 'all', updateUrl = true) {
    isHistoryStatsView = false;
    currentSystem = 'all';
    currentService = 'all';

    const btnCdr = document.getElementById('btnOpenSmscCdrSearch');
    if (btnCdr) btnCdr.style.display = 'none';

    if (updateUrl && window.location.pathname !== '/lich-su') {
        history.pushState({ tab: 'lich-su' }, '', '/lich-su');
    }

    const mainTabs = document.getElementById('mainTabsHeader');
    if (mainTabs) mainTabs.style.display = 'flex';
    isUserManagementView = false;
    const analyticsBox = document.getElementById('closedAnalyticsContainer');
    if (analyticsBox) analyticsBox.style.display = 'none';
    const tableDataView = document.getElementById('tableDataView');
    if (tableDataView) tableDataView.style.display = 'block';
    const faContainer = document.getElementById('flowAuditContainer');
    if (faContainer) faContainer.style.display = 'none';
    const userMgmtContainer = document.getElementById('userManagementContainer');
    if (userMgmtContainer) userMgmtContainer.style.display = 'none';

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

    adjustTableColumnsLayout('all', tab);

    const filterStatus = document.getElementById('filterStatus');
    if (filterStatus) filterStatus.style.display = 'none';
    const ctrlAutoClose = document.getElementById('ctrlAutoCloseUnified');
    if (ctrlAutoClose) ctrlAutoClose.style.display = 'none';

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

// SPA ROUTER: Điều hướng trang theo URL trên thanh địa chỉ trình duyệt
function handleSpaRoute(pathname) {
    const rawP = (pathname || window.location.pathname).toLowerCase().replace(/\/$/, '') || '/';
    
    // Tách và khóa cứng vùng miền nếu có trong URL path
    let detectedReg = null;
    let p = rawP;
    
    if (p.includes('/mien-nam')) { detectedReg = 'MN'; p = p.replace(/\/mien-nam/, ''); }
    else if (p.includes('/mien-bac')) { detectedReg = 'MB'; p = p.replace(/\/mien-bac/, ''); }
    else if (p.includes('/mien-trung')) { detectedReg = 'MT'; p = p.replace(/\/mien-trung/, ''); }
    else if (p.includes('/mn')) { detectedReg = 'MN'; p = p.replace(/\/mn/, ''); }
    else if (p.includes('/mb')) { detectedReg = 'MB'; p = p.replace(/\/mb/, ''); }
    else if (p.includes('/mt')) { detectedReg = 'MT'; p = p.replace(/\/mt/, ''); }

    if (detectedReg) {
        currentRegion = detectedReg;
        if (isSystemAdmin || checkIsUserAdmin()) {
            isSystemAdmin = true;
            isRegionLocked = false;
            urlRouteRegion = null;
            applyRegionUI(false);
        } else {
            isRegionLocked = true;
            urlRouteRegion = detectedReg;
            applyRegionUI(true);
        }
    }

    if (!p || p === '' || p === '/') p = '/ttsmoi/data';

    if (p === '/ttsmoi/data' || p === '/ttsmoi/mobileinternet' || p === '/data') {
        selectModule('tts_new', 'data', false);
    } else if (p === '/ttsmoi/cuoc-goi' || p === '/ttsmoi/call' || p === '/ttsmoi/calls' || p === '/cuoc-goi' || p === '/call') {
        selectModule('tts_new', 'call', false);
    } else if (p === '/ttsmoi/chan-goi-ngoai-mang' || p === '/ttsmoi/spam-call' || p === '/ttsmoi/spam_call' || p === '/ttsmoi/outbound-block' || p === '/chan-goi-ngoai-mang' || p === '/spam-call') {
        selectModule('tts_new', 'spam_call', false);
    } else if (p === '/ttsmoi/tin-nhan' || p === '/ttsmoi/sms' || p === '/tin-nhan' || p === '/sms') {
        selectModule('tts_new', 'sms', false);
    } else if (p === '/ttsmoi/chuyen-vung-quoc-te' || p === '/ttsmoi/roaming' || p === '/ttsmoi/cvqt' || p === '/chuyen-vung-quoc-te' || p === '/roaming' || p === '/cvqt') {
        selectModule('tts_new', 'roaming', false);
    } else if (p === '/ttsmoi/sim-multisim' || p === '/ttsmoi/sim' || p === '/sim-multisim' || p === '/sim') {
        selectModule('tts_new', 'sim', false);
    } else if (p === '/ttsmoi/khac' || p === '/ttsmoi/other' || p === '/khac' || p === '/other') {
        selectModule('tts_new', 'other', false);
    } else if (p === '/ttsmoi/voice' || p === '/ttsmoi/voice_sms') {
        selectModule('tts_new', 'call', false);
    } else if (p.startsWith('/ttscu')) {
        selectModule('tts_new', 'data', false);
    } else if (p === '/thong-ke' || p === '/analytics') {
        selectHistoryStats(false);
    } else if (p === '/lich-su' || p === '/history') {
        selectHistoryModule('all', false);
    } else if (p === '/kiem-tra-luong' || p === '/flow-audit' || p === '/doi-soat-luong') {
        if (typeof selectFlowAuditModule === 'function') {
            selectFlowAuditModule(false);
        }
    } else if (p === '/quan-tri-ktv' || p === '/admin-users' || p === '/phan-vung-ktv') {
        if (typeof selectUserManagementModule === 'function') {
            selectUserManagementModule(false);
        }
    } else {
        // Mặc định: TTS Mới - Mobile Internet
        selectModule('tts_new', 'data', false);
    }
}

// Bắt sự kiện người dùng bấm nút Back / Forward của trình duyệt
window.addEventListener('popstate', function (event) {
    handleSpaRoute(window.location.pathname);
});

function onSourceFilterChange(val) {
    currentSystem = val;
    loadTickets(true, true);
}

function onCategoryFilterChange(val) {
    currentService = val;
    const isData = (val === 'data');
    const thStatus = document.getElementById('thStatus');
    if (thStatus) thStatus.style.display = isData ? '' : 'none';
    const filterStatus = document.getElementById('filterStatus');
    if (filterStatus) filterStatus.style.display = isData ? '' : 'none';
    const ctrlAutoClose = document.getElementById('ctrlAutoCloseUnified');
    if (ctrlAutoClose) ctrlAutoClose.style.display = isData ? 'flex' : 'none';
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
            const stRes = await fetch('/api/status?region=' + encodeURIComponent(currentRegion || 'ALL'));
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

async function startNewVoiceScan(srvType = null) {
    const srv = srvType || currentService;
    let endpoint = '/api/ttsnew/scan_voice';
    let label = 'Thoại / SMS';
    if (srv === 'call') {
        endpoint = '/api/ttsnew/scan_call';
        label = 'Cuộc gọi';
    } else if (srv === 'sms') {
        endpoint = '/api/ttsnew/scan_sms';
        label = 'Tin nhắn';
    } else if (srv === 'other') {
        endpoint = '/api/ttsnew/scan_other';
        label = 'Gói cước / PA Khác';
    }
    const btn = document.getElementById('btnScanNewVoice');
    const originalHtml = btn ? btn.innerHTML : `Quét Phiếu ${label}`;
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="status-dot processing" style="display:inline-block; margin-right:6px;"></span> Đang kết nối...';
    }
    try {
        const res = await fetch(endpoint, { method: 'POST' });
        const data = await res.json();
        if (!data.success) {
            alert(data.message || `Không thể quét phiếu ${label} TTS Mới.`);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
            return;
        }

        let checkAttempts = 0;
        const interval = setInterval(async () => {
            checkAttempts++;
            const stRes = await fetch('/api/status?region=' + encodeURIComponent(currentRegion || 'ALL'));
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

let activeTicketsAbortController = null;

function renderTicketsSkeleton(tbody, totalCols = 12) {
    if (!tbody) return;
    const rows = [1, 2, 3, 4, 5, 6].map(i => `
        <tr class="table-skeleton-row">
            <td class="col-stt-cell" style="width:36px; min-width:36px; max-width:36px; text-align:center; padding:4px 0;"><div class="skeleton-bar" style="width:20px; margin:auto;"></div></td>
            <td><div class="skeleton-bar" style="width:110px;"></div><div class="skeleton-bar" style="width:70px; margin-top:4px;"></div></td>
            ${totalCols === 12 ? '<td><div class="skeleton-bar" style="width:75px; margin:auto;"></div></td>' : ''}
            <td><div class="skeleton-bar" style="width:90px; margin:auto;"></div></td>
            <td><div class="skeleton-bar" style="width:65px; margin:auto;"></div></td>
            <td><div class="skeleton-bar" style="width:70px; margin:auto;"></div></td>
            <td><div class="skeleton-bar" style="width:115px;"></div></td>
            <td><div class="skeleton-bar" style="width:55px; margin:auto;"></div></td>
            <td><div class="skeleton-bar" style="width:85px;"></div></td>
            <td><div class="skeleton-bar" style="width:140px;"></div></td>
            <td><div class="skeleton-bar" style="width:105px;"></div></td>
            <td><div class="skeleton-bar" style="width:65px; margin:auto;"></div></td>
        </tr>
    `).join('');
    tbody.innerHTML = rows;
}

function switchTableTab(tab) {
    currentTableTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

    let srvName = 'Mobile Internet';
    if (currentService === 'call') srvName = 'Cuộc Gọi';
    else if (currentService === 'spam_call') srvName = 'Chặn Gọi Ngoại Mạng';
    else if (currentService === 'sms') srvName = 'Tin Nhắn';
    else if (currentService === 'roaming') srvName = 'Chuyển Vùng Quốc Tế';
    else if (currentService === 'sim') srvName = 'Sim / MultiSIM';
    else if (currentService === 'other') srvName = 'Gói Cước & PA Khác';
    else if (currentService === 'voice_sms') srvName = 'Thoại / SMS';
    else if (currentService === 'all') srvName = '';

    let title = '';
    if (currentSystem === 'all' || !srvName) {
        if (tab === 'chua_dong') title = 'Phiếu Cần Xử Lý (Chưa Đóng)';
        else if (tab === 'da_dong') title = 'Lịch Sử Phiếu Đã Đóng (Chỉ Xem)';
        else title = 'Toàn Bộ Cơ Sở Dữ Liệu (Tổng hợp tất cả trạng thái)';
    } else {
        const sysLabel = (currentSystem === 'tts_new') ? 'TTS Mới' : 'TTS Cũ';
        if (tab === 'chua_dong') title = `Phiếu ${srvName} — ${sysLabel}`;
        else if (tab === 'da_dong') title = `Phiếu ${srvName} Đã Đóng — ${sysLabel}`;
        else title = `Tất Cả Phiếu ${srvName} — ${sysLabel}`;
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
    if (!isHistoryStatsView && !isUserManagementView) {
        const analyticsBox = document.getElementById('closedAnalyticsContainer');
        if (analyticsBox) analyticsBox.style.display = 'none';
        const tableDataView = document.getElementById('tableDataView');
        if (tableDataView) tableDataView.style.display = 'block';
    }

    const titleElem = document.getElementById('tableTitleText');
    if (titleElem) {
        titleElem.innerHTML = `<span>${escapeHtml(title)}</span>`;
    }

    // Đồng bộ ngay tiêu đề cột Tóm tắt / Thời điểm đóng
    const thAiSummary = document.getElementById('thAiSummary');
    if (thAiSummary) {
        if (tab === 'da_dong') {
            thAiSummary.innerText = 'Thời Điểm Đóng';
            thAiSummary.style.textAlign = 'center';
            thAiSummary.title = 'Thời gian KTV bấm đóng 2.6 / 5.1 hoặc hệ thống tự động đóng';
        } else {
            if (currentService === 'spam_call') {
                thAiSummary.innerText = 'Tóm Tắt Sự Cố & Phản Ánh';
            } else if (currentService === 'sms') {
                thAiSummary.innerText = 'Nội Dung Tin Nhắn';
            } else if (currentService === 'call' || currentService === 'roaming' || currentService === 'sim' || currentService === 'other') {
                thAiSummary.innerText = 'Nội Dung Phản Ánh';
            } else {
                thAiSummary.innerText = 'Tóm Tắt Nội Dung PAKH';
            }
            thAiSummary.style.textAlign = '';
            thAiSummary.title = '';
        }
    }

    // Khóa cứng cột STT và điều chỉnh các cột theo tab & module
    adjustTableColumnsLayout(currentService, tab);

    // Khi chuyển tab, reset dropdown filterStatus về 'all' để không bị ẩn dữ liệu ngoài ý muốn
    const filterStatus = document.getElementById('filterStatus');
    if (filterStatus && filterStatus.value !== 'all') {
        filterStatus.value = 'all';
    }

    // Hiển thị hiệu ứng Skeleton mượt mà nếu chưa có sẵn cache (tránh chớp trắng khi chuyển tab nhanh)
    const tbody = document.getElementById('ticketsBody');
    const isDataService = (currentService === 'data');
    const isSpamCallService = (currentService === 'spam_call');
    const isCallService = (currentService === 'call');
    const isSmsService = (currentService === 'sms');
    const isRoamingService = (currentService === 'roaming');
    const isSimService = (currentService === 'sim');
    const hideCemSkeleton = isCallService || isSmsService || isSpamCallService || isRoamingService || isSimService;
    const totalCols = isSpamCallService ? 10 : (hideCemSkeleton ? 11 : (isDataService ? 13 : 12));

    const searchInputVal = document.getElementById('searchInput') ? document.getElementById('searchInput').value : '';
    const curStatusFilterVal = (currentService === 'data' && filterStatus) ? filterStatus.value : 'all';
    const expectedCacheKey = `${tab}_${currentSystem}_${currentService}_${currentRegion || 'ALL'}_${curStatusFilterVal}_${searchInputVal}`;
    const hasFreshModuleCache = window.ticketsModuleCache && window.ticketsModuleCache[expectedCacheKey] && (Date.now() - window.ticketsModuleCache[expectedCacheKey].timestamp < 30000);

    if (!hasFreshModuleCache && tbody) {
        renderTicketsSkeleton(tbody, totalCols);
    }

    lastTicketsSignature = "";
    loadTickets(false, true);
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
            body: JSON.stringify({ phone, incident_time: incidentTime, service_type: currentService, region: currentRegion })
        });
        const data = await res.json();
        if (data.success) {
            clearTicketsModuleCache();
            lastTicketsSignature = "";
            await loadTickets(true);
            await fetchStatus();
        } else {
            alert(data.error || "Không thể thực hiện tiền kiểm.");
            if (btnElem) {
                btnElem.disabled = false;
                btnElem.innerHTML = 'Tiền kiểm lại';
                btnElem.style.opacity = '1';
            }
        }
    } catch (e) {
        alert("Lỗi khi gửi yêu cầu tiền kiểm: " + e);
        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = 'Tiền kiểm lại';
            btnElem.style.opacity = '1';
        }
    }
}

// ==============================================================================
// BỘ NHỚ ĐỆM CLIENT (SWR CACHE - INSTANT MODULE SWITCHING)
// ==============================================================================
window.ticketsModuleCache = window.ticketsModuleCache || {};

function clearTicketsModuleCache() {
    window.ticketsModuleCache = {};
}

function applyTicketsData(data, force = false) {
    if (!data) return;

    // 🎯 Đồng bộ Widget Phân vùng 3 Miền & Vai trò Admin trên Header
    const authRoleTag = document.getElementById('authRoleTag');
    const authUserName = document.getElementById('authUserName');
    const authPill = document.getElementById('authPill');
    const unauthBtn = document.getElementById('unauthBtn');

    if (data.user_role === 'admin') {
        isSystemAdmin = true;
        if (authRoleTag) {
            authRoleTag.innerText = 'ADMIN';
            authRoleTag.className = 'auth-role-tag admin';
        }
    } else {
        if (authRoleTag) {
            authRoleTag.innerText = 'KTV';
            authRoleTag.className = 'auth-role-tag ktv';
        }
    }

    const regWrap = document.getElementById('regionSelectWrapper');
    if (regWrap) regWrap.style.display = 'flex';
    const regSelect = document.getElementById('regionSelect');
    const isAdmin = (data.user_role === 'admin') || isSystemAdmin || checkIsUserAdmin();
    const navAdminSec = document.getElementById('navAdminSection');
    if (navAdminSec) {
        navAdminSec.style.display = 'block';
    }

    if (regSelect) {
        if (isAdmin) {
            isSystemAdmin = true;
            isRegionLocked = false;
            urlRouteRegion = null;
            try { localStorage.setItem('pakh_is_admin', 'true'); } catch(e) {}
            applyRegionUI(false);
            const activeVal = currentRegion || data.region || 'ALL';
            if (regSelect.value !== activeVal) {
                regSelect.value = activeVal;
            }
        } else if (data.is_region_locked || (data.user_region && data.user_role === 'ktv')) {
            isRegionLocked = true;
            currentRegion = data.user_region || data.region || currentRegion;
            applyRegionUI(true);
            if (regSelect.value !== currentRegion) {
                regSelect.value = currentRegion;
            }
        } else if (urlRouteRegion && (!currentRegion || currentRegion === 'ALL')) {
            isRegionLocked = true;
            currentRegion = urlRouteRegion;
            applyRegionUI(true);
        } else {
            isRegionLocked = false;
            applyRegionUI(false);
            const activeVal = currentRegion || data.region || 'ALL';
            if (regSelect.value !== activeVal) {
                regSelect.value = activeVal;
            }
        }
    }

    // Cập nhật tên hiển thị từ server nếu có
    if (data.user_role === 'guest' || !data.user_name) {
        if (!getTtsNewAuthToken()) {
            window.currentApiUserName = '';
            if (authPill) authPill.style.display = 'none';
            if (unauthBtn) unauthBtn.style.display = 'inline-flex';
        }
    } else if (data.user_name && data.user_name !== 'KTV' && data.user_name !== 'Quản trị viên') {
        window.currentApiUserName = data.user_name;
        if (authUserName) {
            authUserName.innerText = `Xin chào, ${data.user_name}`;
        }
        if (authPill) authPill.style.display = 'inline-flex';
        if (unauthBtn) unauthBtn.style.display = 'none';
    }

    const tickets = data.tickets || [];

    if (data.system_counts) {
        const sc = data.system_counts;
        const bOldData = document.getElementById('badgeOldData');
        const bOldVoice = document.getElementById('badgeOldVoice');
        const bOldApiData = document.getElementById('badgeOldApiData');
        const bOldApiVoice = document.getElementById('badgeOldApiVoice');
        const bNewData = document.getElementById('badgeNewData');
        const bNewCall = document.getElementById('badgeNewCall');
        const bNewSpamCall = document.getElementById('badgeNewSpamCall');
        const bNewSms = document.getElementById('badgeNewSms');
        const bNewRoaming = document.getElementById('badgeNewRoaming');
        const bNewSim = document.getElementById('badgeNewSim');
        const bNewOther = document.getElementById('badgeNewOther');
        const bNewVoice = document.getElementById('badgeNewVoice');
        const bTotalClosed = document.getElementById('badgeTotalClosed');
        const bTotalAll = document.getElementById('badgeTotalAll');

        updateNavBadge(bOldData, sc.tts_old_data);
        updateNavBadge(bOldVoice, sc.tts_old_voice);
        updateNavBadge(bOldApiData, sc.tts_old_api_data);
        updateNavBadge(bOldApiVoice, sc.tts_old_api_voice);
        updateNavBadge(bNewData, sc.tts_new_data);
        updateNavBadge(bNewCall, sc.tts_new_call);
        updateNavBadge(bNewSpamCall, sc.tts_new_spam_call);
        updateNavBadge(bNewSms, sc.tts_new_sms);
        updateNavBadge(bNewRoaming, sc.tts_new_roaming);
        updateNavBadge(bNewSim, sc.tts_new_sim);
        updateNavBadge(bNewOther, sc.tts_new_other);
        updateNavBadge(bNewVoice, sc.tts_new_voice);
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
}

async function loadTickets(force = false, resetPage = false) {
    if (isHistoryStatsView || isUserManagementView) {
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

        const requestedTab = currentTableTab;
        const requestedSystem = currentSystem;
        const requestedService = currentService;

        const search = document.getElementById('searchInput') ? document.getElementById('searchInput').value : '';
        const filterStatusElem = document.getElementById('filterStatus');
        const statusFilter = (currentService === 'data' && filterStatusElem) ? filterStatusElem.value : 'all';

        // ⚡ INSTANT CACHE: Kiểm tra bộ nhớ RAM trước (0ms phản hồi)
        const cacheKey = `${requestedTab}_${requestedSystem}_${requestedService}_${currentRegion || 'ALL'}_${statusFilter}_${search}`;
        const cachedItem = window.ticketsModuleCache ? window.ticketsModuleCache[cacheKey] : null;
        const now = Date.now();

        if (cachedItem && (now - cachedItem.timestamp < 30000)) {
            // Hiển thị ngay lập tức không cần đợi mạng!
            applyTicketsData(cachedItem.data, force);
            // Nếu dữ liệu còn tươi (< 6 giây) và không bị ép buộc làm mới thì dừng luôn
            if (now - cachedItem.timestamp < 6000 && !force) {
                return;
            }
        }

        // Hủy bỏ request trước đó nếu đang chạy dở để tránh Race Condition khi bấm nhanh
        if (activeTicketsAbortController) {
            try { activeTicketsAbortController.abort(); } catch (e) {}
        }
        activeTicketsAbortController = new AbortController();
        const signal = activeTicketsAbortController.signal;

        const clientAuthTok = getTtsNewAuthToken() || (getTtsAuthSession() ? getTtsAuthSession().token : '');
        const reqHeaders = clientAuthTok ? { 'Authorization': clientAuthTok } : {};

        const res = await fetch(`/api/tickets?search=${encodeURIComponent(search)}&status=${encodeURIComponent(statusFilter)}&tab=${encodeURIComponent(requestedTab)}&source=${encodeURIComponent(requestedSystem)}&service_type=${encodeURIComponent(requestedService)}&region=${encodeURIComponent(currentRegion || 'ALL')}`, { 
            signal,
            headers: reqHeaders
        });
        const data = await res.json();

        // Kiểm tra tính hợp lệ: Nếu người dùng đã chuyển sang tab hoặc module khác trong lúc fetch thì bỏ qua kết quả cũ
        if (requestedTab !== currentTableTab || requestedSystem !== currentSystem || requestedService !== currentService) {
            return;
        }

        // Lưu vào bộ nhớ đệm client
        if (!window.ticketsModuleCache) window.ticketsModuleCache = {};
        window.ticketsModuleCache[cacheKey] = {
            data: data,
            timestamp: Date.now()
        };

        applyTicketsData(data, force);

    } catch (e) {
        if (e.name === 'AbortError') {
            return; // Request bị hủy có chủ đích do người dùng chuyển tab nhanh
        }
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
        dismissNewBeacon(ticketKey);
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

function dismissNewBeacon(ticketKey, event, clickedElem = null) {
    if (event) {
        try {
            event.stopPropagation();
            event.preventDefault();
        } catch(e) {}
    }
    try {
        let readTickets = JSON.parse(localStorage.getItem('acknowledged_tickets') || '{}');
        readTickets[ticketKey] = true;
        const keys = Object.keys(readTickets);
        if (keys.length > 2000) {
            delete readTickets[keys[0]];
        }
        localStorage.setItem('acknowledged_tickets', JSON.stringify(readTickets));
    } catch(e) {}
    
    if (clickedElem) {
        clickedElem.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        clickedElem.style.opacity = '0';
        clickedElem.style.transform = 'scale(0)';
        setTimeout(() => {
            if (clickedElem && clickedElem.parentNode) clickedElem.remove();
        }, 200);
    }

    const els = document.querySelectorAll(`[id="beacon-${ticketKey}"], .beacon-${ticketKey}`);
    els.forEach(el => {
        el.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        el.style.opacity = '0';
        el.style.transform = 'scale(0)';
        setTimeout(() => {
            if (el && el.parentNode) el.remove();
        }, 200);
    });
}
window.dismissNewBeacon = dismissNewBeacon;

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
// [MODULE: geo_cell.js] -> Quản lý định vị Cell BTS & Đối soát địa bàn đã chuyển sang static/js/modules/geo_cell.js

// =========================================================================
// DANH MỤC NGUYÊN NHÂN SỰ CỐ CHUẨN ONEOSS TTS (Áp dụng bước 2.6 & Đóng phiếu)
// =========================================================================
const TTS_INCIDENT_CAUSES = [
    "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường",
    "Thông tin đầu vào chưa chính xác, trùng lặp",
    "Lỗi do gói cước",
    "Lỗi profile thuê bao",
    "Do thiết bị đầu cuối",
    "Khách hàng theo dõi thêm",
    "Lỗi do VNPT-VinaPhone khai báo dịch vụ cho khách hàng"
];

function getPredictedIncidentCause(status) {
    if (!status) return "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường";
    const s = String(status).toUpperCase().trim();
    if (s.includes("BÌNH THƯỜNG") || s.includes("BINH THUONG") || s.includes("ĐẢM BẢO") || s.includes("ĐỦ ĐIỀU KIỆN ĐÓNG")) {
        return "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường";
    }
    if (s.includes("BÓP BĂNG THÔNG") || s.includes("LƯU LƯỢNG YẾU") || s.includes("BẮT SÓNG 4G KÉM") || s.includes("KHÔNG BẮT ĐƯỢC SÓNG 4G") || s.includes("CHẬP CHỜN")) {
        return "Thông tin đầu vào chưa chính xác, trùng lặp";
    }
    if (s.includes("GÓI") || s.includes("PAYGO") || s.includes("HẾT HẠN") || s.includes("VD2")) {
        return "Lỗi do gói cước";
    }
    if (s.includes("PROFILE LẠ") || s.includes("CHƯA KHAI BÁO PROFILE")) {
        return "Lỗi profile thuê bao";
    }
    if (s.includes("THIẾT BỊ") || s.includes("VPN") || s.includes("1.1.1.1") || s.includes("OFF THIẾT BỊ") || s.includes("TẮT THIẾT BỊ") || s.includes("KHÔNG CÓ LƯU LƯỢNG")) {
        return "Do thiết bị đầu cuối";
    }
    if (s.includes("THEO DÕI")) {
        return "Khách hàng theo dõi thêm";
    }
    if (s.includes("HSS CHƯA CÓ 5G") || s.includes("KHÓA GPRS") || s.includes("KHAI BÁO")) {
        return "Lỗi do VNPT-VinaPhone khai báo dịch vụ cho khách hàng";
    }
    return "Mạng lưới đảm bảo, khách hàng sử dụng dịch vụ bình thường";
}

// Chuẩn hóa chuỗi tiếng Việt bỏ dấu để tìm kiếm không dấu
function removeVietnameseTones(str) {
    if (!str) return '';
    str = String(str);
    str = str.replace(/à|á|ạ|ả|ã|â|ầ|ấ|ậ|ẩ|ẫ|ă|ằ|ắ|ặ|ẳ|ẵ/g, "a");
    str = str.replace(/è|é|ẹ|ẻ|ẽ|ê|ề|ế|ệ|ể|ễ/g, "e");
    str = str.replace(/ì|í|ị|ỉ|ĩ/g, "i");
    str = str.replace(/ò|ó|ọ|ỏ|õ|ô|ồ|ố|ộ|ổ|ỗ|ơ|ờ|ớ|ợ|ở|ỡ/g, "o");
    str = str.replace(/ù|ú|ụ|ủ|ũ|ư|ừ|ứ|ự|ử|ữ/g, "u");
    str = str.replace(/ỳ|ý|ỵ|ỷ|ỹ/g, "y");
    str = str.replace(/đ/g, "d");
    str = str.replace(/À|Á|Ạ|Ả|Ã|Â|Ầ|Ấ|Ậ|Ẩ|Ẫ|Ă|Ằ|Ắ|Ặ|Ẳ|Ẵ/g, "A");
    str = str.replace(/È|É|Ẹ|Ẻ|Ẽ|Ê|Ề|Ế|Ệ|Ể|Ễ/g, "E");
    str = str.replace(/Ì|Í|Ị|Ỉ|Ĩ/g, "I");
    str = str.replace(/Ò|Ó|Ọ|Ỏ|Õ|Ô|Ồ|Ố|Ộ|Ổ|Ỗ|Ơ|Ờ|Ớ|Ợ|Ở|Ỡ/g, "O");
    str = str.replace(/Ù|Ú|Ụ|Ủ|Ũ|Ư|Ừ|Ứ|Ự|Ử|Ữ/g, "U");
    str = str.replace(/Ỳ|Ý|Ỵ|Ỷ|Ỹ/g, "Y");
    str = str.replace(/Đ/g, "D");
    return str.toLowerCase().trim();
}

function getIncidentCauseGroups() {
    if (window.TTS_INCIDENT_CAUSE_GROUPS && window.TTS_INCIDENT_CAUSE_GROUPS.length > 0) {
        return window.TTS_INCIDENT_CAUSE_GROUPS;
    }
    return [
        { group: "Nguyên nhân phổ biến", items: TTS_INCIDENT_CAUSES.map((c, i) => ({ id: i, name: c })) }
    ];
}

function handleCauseChange(ticketKey, phone, incidentTime, val) {
    updateTicket(phone, incidentTime, 'incident_cause', val);
    const item = cachedTickets.find(t => {
        const key = (t.phone + '_' + (t.incident_time || t.ticket_code || '')).replace(/[^a-zA-Z0-9]/g, '_');
        return key === ticketKey || t.phone === phone;
    });
    if (item) {
        item.incident_cause = val;
    }
    const indicator = document.getElementById(`save-cause-${ticketKey}`);
    if (indicator) {
        indicator.classList.add('visible');
        setTimeout(() => indicator.classList.remove('visible'), 1500);
    }
}

function handleCauseInputChange(ticketKey, phone, incidentTime, val) {
    const hidden = document.getElementById(`select-detail-cause-${ticketKey}`);
    if (hidden) hidden.value = val;
    handleCauseChange(ticketKey, phone, incidentTime, val);
}

function selectCauseItem(ticketKey, phone, incidentTime, causeName) {
    const input = document.getElementById(`input-detail-cause-${ticketKey}`);
    if (input) {
        input.value = causeName;
        input.title = causeName;
    }
    const hidden = document.getElementById(`select-detail-cause-${ticketKey}`);
    if (hidden) hidden.value = causeName;
    handleCauseChange(ticketKey, phone, incidentTime, causeName);
    hideCauseDropdown(ticketKey);
}

function showCauseDropdown(ticketKey, forceAll = true) {
    document.querySelectorAll('.cause-dropdown-menu').forEach(m => {
        if (m.id !== `dropdown-cause-menu-${ticketKey}`) m.style.display = 'none';
    });
    const menu = document.getElementById(`dropdown-cause-menu-${ticketKey}`);
    if (!menu) return;
    const input = document.getElementById(`input-detail-cause-${ticketKey}`);
    
    // Mặc định luôn bung toàn bộ (ALL) 73 nguyên nhân (10 nhóm) để KTV duyệt và chọn chi tiết
    const query = forceAll ? '' : (input ? input.value : '');
    renderCauseDropdownMenu(ticketKey, query);
    menu.style.display = 'block';

    if (input) {
        // Tự động bôi đen chữ để KTV có thể gõ ngay ký tự bất kỳ để tìm kiếm nếu muốn
        setTimeout(() => {
            try { input.select(); } catch (e) {}
        }, 50);
    }

    // Tự động cuộn đến vị trí mục đang được chọn để KTV thấy vị trí trong danh mục
    setTimeout(() => {
        const sel = menu.querySelector('.cause-dropdown-item.is-selected');
        if (sel) {
            sel.scrollIntoView({ block: 'nearest' });
        }
    }, 60);
}

function hideCauseDropdown(ticketKey) {
    const menu = document.getElementById(`dropdown-cause-menu-${ticketKey}`);
    if (menu) menu.style.display = 'none';
}

function toggleCauseDropdown(ticketKey, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    const menu = document.getElementById(`dropdown-cause-menu-${ticketKey}`);
    if (!menu) return;
    if (menu.style.display === 'block') {
        menu.style.display = 'none';
    } else {
        showCauseDropdown(ticketKey, true);
        const input = document.getElementById(`input-detail-cause-${ticketKey}`);
        if (input) input.focus();
    }
}

function filterCauseDropdown(ticketKey, query) {
    const menu = document.getElementById(`dropdown-cause-menu-${ticketKey}`);
    if (menu && menu.style.display !== 'block') {
        menu.style.display = 'block';
    }
    renderCauseDropdownMenu(ticketKey, query);
}

function showAllCauses(ticketKey) {
    renderCauseDropdownMenu(ticketKey, '');
    const menu = document.getElementById(`dropdown-cause-menu-${ticketKey}`);
    if (menu) menu.style.display = 'block';
    const input = document.getElementById(`input-detail-cause-${ticketKey}`);
    if (input) {
        try { input.select(); } catch (e) {}
    }
}

function renderCauseDropdownMenu(ticketKey, query) {
    const menu = document.getElementById(`dropdown-cause-menu-${ticketKey}`);
    if (!menu) return;

    const currentVal = (document.getElementById(`input-detail-cause-${ticketKey}`)?.value || '').trim();
    const groups = getIncidentCauseGroups();
    const cleanQ = removeVietnameseTones(query || '');
    const tokens = cleanQ.split(/\s+/).filter(t => t.length > 0);
    const safePhone = menu.getAttribute('data-phone') || '';
    const safeTime = menu.getAttribute('data-time') || '';

    const totalAllCount = groups.reduce((acc, g) => acc + (g.items ? g.items.length : 0), 0);
    const isFiltered = tokens.length > 0;

    let itemsHtml = '';
    let matchCount = 0;

    groups.forEach(g => {
        if (!g.items || g.items.length === 0) return;
        const gNameClean = removeVietnameseTones(g.group || '');

        const matchedItems = g.items.filter(it => {
            if (!isFiltered) return true;
            const itClean = removeVietnameseTones(it.name || '');
            return tokens.every(tok => itClean.includes(tok) || gNameClean.includes(tok));
        });

        if (matchedItems.length === 0) return;
        matchCount += matchedItems.length;

        itemsHtml += `<div class="cause-group-header" style="position:sticky; top:28px; z-index:5;">${escapeHtml(g.group)} (${matchedItems.length})</div>`;
        matchedItems.forEach(it => {
            const isSelected = (currentVal && it.name.trim().toLowerCase() === currentVal.toLowerCase());
            const safeName = escapeHtml(it.name);
            const escapedForAttr = it.name.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
            
            itemsHtml += `<div class="cause-dropdown-item ${isSelected ? 'is-selected' : ''}" 
                               title="${safeName}"
                               style="white-space:normal; word-break:break-word; line-height:1.4; padding:7px 12px;"
                               onmousedown="selectCauseItem('${ticketKey}', '${safePhone}', '${safeTime}', '${escapedForAttr}')">
                            <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:8px;">
                                <span style="flex:1;">${safeName}</span>
                                <div style="display:flex; align-items:center; gap:4px; flex-shrink:0;">
                                    ${it.id ? `<span style="font-size:9.5px; color:#94a3b8; font-family:'JetBrains Mono', monospace;">#${it.id}</span>` : ''}
                                    ${isSelected ? '<span style="color:#0284c7; font-size:11px; font-weight:700;">✓</span>' : ''}
                                </div>
                            </div>
                        </div>`;
        });
    });

    if (matchCount === 0) {
        itemsHtml = `<div style="padding:14px; text-align:center; color:#94a3b8; font-size:11px; font-style:italic;">
                    Không tìm thấy nguyên nhân phù hợp với từ khóa "${escapeHtml(query)}"
                    <div style="margin-top:8px;">
                        <button type="button" onmousedown="showAllCauses('${ticketKey}')" style="background:#0284c7; color:#fff; border:none; padding:4px 12px; border-radius:4px; font-size:11px; font-weight:600; cursor:pointer;">Xem toàn bộ ${totalAllCount} nguyên nhân</button>
                    </div>
                </div>`;
    }

    const headerHtml = `
        <div style="padding:5px 10px; background:#f1f5f9; border-bottom:1px solid #cbd5e1; display:flex; align-items:center; justify-content:space-between; font-size:10px; font-weight:700; color:#475569; position:sticky; top:0; z-index:10;">
            <span>${isFiltered ? `Tìm thấy <b>${matchCount}</b> / ${totalAllCount} nguyên nhân` : `Toàn bộ danh mục OneOSS: <b>${totalAllCount} nguyên nhân</b> (${groups.length} nhóm)`}</span>
            <div style="display:flex; align-items:center; gap:8px;">
                ${isFiltered ? `<span style="cursor:pointer; color:#0284c7; text-decoration:underline;" onmousedown="showAllCauses('${ticketKey}')">Xem tất cả</span>` : '<span style="font-weight:400; color:#94a3b8; font-size:9.5px;">(Gõ để tìm kiếm)</span>'}
            </div>
        </div>
    `;

    menu.innerHTML = headerHtml + itemsHtml;
}

// Lắng nghe sự kiện click bên ngoài để tự động đóng dropdown combobox
document.addEventListener('click', function(e) {
    if (!e.target.closest('.cause-combobox-wrapper')) {
        document.querySelectorAll('.cause-dropdown-menu').forEach(m => m.style.display = 'none');
    }
});

function formatPrecheckTimeDisplay(precheckedAtStr) {
    if (!precheckedAtStr || precheckedAtStr === '--' || precheckedAtStr === 'null') {
        return '<span style="color:#94a3b8; font-style:italic;">--</span>';
    }
    try {
        const cleaned = String(precheckedAtStr).replace('T', ' ').trim();
        const parts = cleaned.split(' ');
        if (parts.length >= 2) {
            const dParts = parts[0].split('-');
            const timePart = parts[1].split('.')[0];
            const datePart = (dParts.length === 3) ? `${dParts[2]}/${dParts[1]}` : parts[0];
            return `<span title="Thời gian tiền kiểm gần nhất: ${escapeHtml(cleaned)} (UTC+7)">${escapeHtml(timePart)} ${escapeHtml(datePart)}</span>`;
        }
        return `<span>${escapeHtml(cleaned)}</span>`;
    } catch (e) {
        return `<span>${escapeHtml(String(precheckedAtStr))}</span>`;
    }
}

function renderPrecheckBtnHtml(phone, incidentTime, precheckedAtStr) {
    const timeDisplay = formatPrecheckTimeDisplay(precheckedAtStr);
    return `
        <div style="display:inline-flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; vertical-align:middle;">
            <button class="btn-sm btn-outline" style="padding:4px 8px; font-size:11px; color:#0284c7; border-color:#93c5fd; background:#f0f9ff; line-height:1.2;" onclick="precheckSingleTicket('${escapeHtml(phone)}', '${escapeHtml(incidentTime || '')}', this)" title="Tiền kiểm tra lại Core tức thì">Tiền kiểm lại</button>
            <div style="font-size:9.5px; color:#64748b; font-family:'JetBrains Mono', monospace; font-weight:600; text-align:center; line-height:1; white-space:nowrap;">${timeDisplay}</div>
        </div>
    `;
}

function formatClosedTimeDisplay(closedAtStr, closedBy, ticketStatus) {
    if (!closedAtStr || closedAtStr === '--') {
        return '<div style="text-align:center;"><span style="color:#94a3b8; font-style:italic;">--</span></div>';
    }
    let timePart = '';
    let datePart = '';
    try {
        const cleaned = String(closedAtStr).replace('T', ' ').trim();
        const parts = cleaned.split(' ');
        if (parts.length >= 2) {
            const dParts = parts[0].split('-');
            if (dParts.length === 3) {
                datePart = `${dParts[2]}/${dParts[1]}/${dParts[0]}`;
            } else {
                datePart = parts[0];
            }
            timePart = parts[1].split('.')[0];
        } else {
            timePart = cleaned;
        }
    } catch (e) {
        timePart = String(closedAtStr);
    }

    let actorHtml = '';
    if (closedBy && closedBy !== 'null' && String(closedBy).trim()) {
        actorHtml = `<span style="font-size:9.5px; font-weight:600; color:#0369a1; background:#f0f9ff; border:1px solid #bae6fd; padding:1px 5px; border-radius:3px; max-width:130px; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="KTV thực hiện: ${escapeHtml(closedBy)}">${escapeHtml(closedBy)}</span>`;
    } else {
        actorHtml = `<span style="font-size:9.5px; font-weight:600; color:#15803d; background:#dcfce7; border:1px solid #86efac; padding:1px 5px; border-radius:3px;">Đã đóng</span>`;
    }

    let stepBadge = '';
    const stLower = String(ticketStatus || '').toLowerCase();
    if (stLower.includes('5.1')) {
        stepBadge = `<span style="font-size:9px; font-weight:700; color:#b45309; background:#fef3c7; border:1px solid #fde68a; padding:1px 4px; border-radius:2px;" title="Đóng hướng 5.1 Xây dựng PA xử lý">Đóng 5.1</span>`;
    } else if (stLower.includes('2.6')) {
        stepBadge = `<span style="font-size:9px; font-weight:700; color:#15803d; background:#dcfce7; border:1px solid #86efac; padding:1px 4px; border-radius:2px;" title="Đóng dứt điểm bước 2.6">Đóng 2.6</span>`;
    }

    return `
        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px; text-align:center; padding:1px 0;">
            <div style="display:inline-flex; align-items:center; gap:4px;">
                <span style="font-family:'JetBrains Mono', monospace; font-weight:700; font-size:11.5px; color:#0f172a;">${escapeHtml(timePart)}</span>
                ${datePart ? `<span style="font-size:10px; color:#64748b; font-weight:500;">${escapeHtml(datePart)}</span>` : ''}
            </div>
            <div style="display:inline-flex; align-items:center; justify-content:center; gap:3px; flex-wrap:wrap;">
                ${actorHtml}
                ${stepBadge}
            </div>
        </div>
    `;
}

function renderTicketsTable(force = false) {
    const tbody = document.getElementById('ticketsBody');
    const pagContainer = document.getElementById('ticketsPaginationContainer');
    if (!tbody) return;

    // Cột Nhận Định / Nhà Mạng và số lượng cột theo từng phân hệ
    const isDataService = (currentService === 'data');
    const isSpamCallService = (currentService === 'spam_call');
    const isCallService = (currentService === 'call');
    const isSmsService = (currentService === 'sms');
    const isRoamingService = (currentService === 'roaming');
    const isSimService = (currentService === 'sim');
    const hideCemColumn = isCallService || isSmsService || isSpamCallService || isRoamingService || isSimService;
    const totalCols = isSpamCallService ? 10 : (hideCemColumn ? 11 : (isDataService ? 13 : 12));

    adjustTableColumnsLayout(currentService, currentTableTab);

    const filterStatus = document.getElementById('filterStatus');
    if (filterStatus) {
        filterStatus.style.display = isDataService ? '' : 'none';
    }

    const thTicketCode = document.getElementById('thTicketCode');
    if (thTicketCode) {
        thTicketCode.style.display = 'table-cell';
    }

    const thAiSummary = document.getElementById('thAiSummary');
    if (thAiSummary) {
        if (currentTableTab === 'da_dong') {
            thAiSummary.innerText = 'Thời Điểm Đóng';
            thAiSummary.style.textAlign = 'center';
            thAiSummary.title = 'Thời gian KTV bấm đóng 2.6 / 5.1 hoặc hệ thống tự động đóng';
        } else {
            if (isSpamCallService) {
                thAiSummary.innerText = 'Tóm Tắt Sự Cố & Phản Ánh';
            } else if (currentService === 'sms') {
                thAiSummary.innerText = 'Nội Dung Tin Nhắn';
            } else if (currentService === 'call' || currentService === 'roaming' || currentService === 'sim' || currentService === 'other') {
                thAiSummary.innerText = 'Nội Dung Phản Ánh';
            } else {
                thAiSummary.innerText = 'Tóm Tắt Nội Dung PAKH';
            }
            thAiSummary.style.textAlign = '';
            thAiSummary.title = '';
        }
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
        tbody.innerHTML = `<tr><td colspan="${totalCols}" style="text-align:center; padding:40px; color:var(--text-muted); font-size:13px;">${emptyMsg}</td></tr>`;
        if (pagContainer) pagContainer.style.display = 'none';
        lastTicketsSignature = "EMPTY_" + currentTableTab + "_" + currentSystem + "_" + currentService;
        return;
    }

    // Sắp xếp danh sách phiếu nếu sortIncidentTimeOrder khác 'none'
    let displayTickets = cachedTickets;
    if (sortIncidentTimeOrder === 'desc') {
        displayTickets = [...cachedTickets].sort((a, b) => {
            const timeA = parseIncidentDate(a.incident_time);
            const timeB = parseIncidentDate(b.incident_time);
            return timeB - timeA;
        });
    } else if (sortIncidentTimeOrder === 'asc') {
        displayTickets = [...cachedTickets].sort((a, b) => {
            const timeA = parseIncidentDate(a.incident_time);
            const timeB = parseIncidentDate(b.incident_time);
            return timeA - timeB;
        });
    }

    // Cập nhật biểu tượng mũi tên sắp xếp trên header
    updateSortIncidentTimeUI();

    // Tính toán số trang & vị trí trang
    let pageSizeNum = (currentTicketPageSize === 'all') ? totalItems : (parseInt(currentTicketPageSize, 10) || 10);
    let totalPages = Math.max(1, Math.ceil(totalItems / pageSizeNum));

    if (currentTicketPage < 1) currentTicketPage = 1;
    if (currentTicketPage > totalPages) currentTicketPage = totalPages;

    let startIndex = (currentTicketPageSize === 'all') ? 0 : (currentTicketPage - 1) * pageSizeNum;
    let endIndex = Math.min(startIndex + pageSizeNum, totalItems);
    let pageTickets = (currentTicketPageSize === 'all') ? displayTickets : displayTickets.slice(startIndex, endIndex);

    // Cập nhật thanh phân trang
    const rangeText = document.getElementById('pageRangeText');
    const totalText = document.getElementById('pageTotalItemsText');
    if (rangeText) rangeText.innerText = `${startIndex + 1} - ${endIndex}`;
    if (totalText) totalText.innerText = totalItems.toLocaleString();
    if (pagContainer) pagContainer.style.display = 'flex';
    renderPaginationNav(currentTicketPage, totalPages);

    const newSignature = JSON.stringify(pageTickets) + '_' + currentTicketPage + '_' + currentAutoClose + '_' + currentTableTab + '_' + currentSystem + '_' + currentService + '_' + currentTicketPageSize + '_' + sortIncidentTimeOrder;
    if (!force && newSignature === lastTicketsSignature) {
        return;
    }
    lastTicketsSignature = newSignature;

    tbody.innerHTML = pageTickets.map((t, idx) => {
        const globalIdx = startIndex + idx;
        const ticketKey = (t.phone + '_' + (t.incident_time || t.ticket_code || idx)).replace(/[^a-zA-Z0-9]/g, '_');
        const isExpanded = expandedTicketKeys.has(ticketKey);

        let badgeClass = 'badge-gray';
        const stStr = String(t.status || '');
        if (stStr.includes('BÌNH THƯỜNG') || stStr.includes('VPN') || stStr.includes('MẠNG LƯỚI ĐẢM BẢO') || stStr.includes('ĐỦ ĐIỀU KIỆN ĐÓNG')) badgeClass = 'badge-green';
        else if (stStr.includes('PROFILE LẠ') || stStr.includes('LẠ') || stStr.includes('KHÓA DỊCH VỤ') || stStr.includes('SPAM') || stStr.includes('KHÓA GPRS')) badgeClass = 'badge-red';
        else if (stStr.includes('YẾU') || stStr.includes('GÓI') || stStr.includes('LỖI ỨNG DỤNG') || stStr.includes('ỨNG DỤNG') || stStr.includes('MỞ LẠI') || stStr.includes('SỰ CỐ') || stStr.includes('KTV KIỂM TRA')) badgeClass = 'badge-yellow';

        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const endD = `${pad(now.getDate())}${pad(now.getMonth() + 1)}${now.getFullYear()}`;
        const past = new Date(now.getTime() - 4 * 24 * 60 * 60 * 1000);
        const startD = `${pad(past.getDate())}${pad(past.getMonth() + 1)}${past.getFullYear()}`;
        const btoolsUrl = `http://10.159.21.241:9267/B_tools_v2/data_view.jsp?name=${t.phone}&start_d=${startD}&end_d=${endD}&submit=T%C3%ACm+Ki%E1%BA%BFm`;

        let actionHtml = '';
        let compactActionHtml = '';
        const isTtsNew = (t.source === 'tts_new' || currentSystem === 'tts_new' || (t.source !== 'tts_old' && t.source !== 'tts_old_api'));
        const isTtsOldApi = (t.source === 'tts_old_api' || currentSystem === 'tts_old_api');
        let cleanTicketCode = (t.ticket_code || '').split('\n')[0].trim();
        if (cleanTicketCode.endsWith('.0') && !isNaN(Number(cleanTicketCode))) {
            cleanTicketCode = cleanTicketCode.slice(0, -2);
        }
        const reopenCount = parseInt(t.reopen_count || 0, 10);

        const pkgTitleLower = (t.package_title || '').toLowerCase();
        const isDataTicket = (currentService === 'data') || (
            (currentService === 'all' || currentService === '') &&
            (pkgTitleLower.includes('mobile internet') || pkgTitleLower.includes('data')) &&
            !pkgTitleLower.includes('(m0/gói data)') &&
            !pkgTitleLower.includes('gói cước mobile internet') &&
            !pkgTitleLower.includes('cvqt') &&
            !pkgTitleLower.includes('roaming')
        );
        const isOtherPakh = !isDataTicket || (currentService === 'voice_sms');
        const isSmsTicket = (currentService === 'sms') ||
            (t.service_type === 'sms') ||
            pkgTitleLower.includes('tin nhắn') ||
            pkgTitleLower.includes('sms');

        let stepName = t.step_name || '';
        if (!stepName && t.ticket_code && t.ticket_code.includes('\n')) {
            const lines = t.ticket_code.split('\n').map(l => l.trim()).filter(Boolean);
            for (let i = 1; i < lines.length; i++) {
                if (lines[i].includes('2.') || lines[i].includes('5.') || lines[i].toLowerCase().includes('bước')) {
                    stepName = lines[i];
                    break;
                }
            }
        }

        // Phân biệt chính xác bước hiện tại: 2.3, 2.4 hay 2.6 cho TẤT CẢ các module
        const rawStepCheck = ((stepName || '') + ' ' + (t.ticket_code || '') + ' ' + (t.step_name || '')).toLowerCase();
        const isStep23 = rawStepCheck.includes('2.3');
        const isStep26 = rawStepCheck.includes('2.6') || (t.ticket_status === 'Chờ đóng lần 2');
        const isStep24 = !isStep23 && !isStep26;

        if (t.ticket_status === 'Đã đóng' || t.ticket_status === 'Da dong' || (t.ticket_status && t.ticket_status.includes('Đã đóng'))) {
            let closeLabel = 'ĐÃ ĐÓNG';
            let closeBadgeStyle = 'font-weight:700; padding:4px 8px; font-size:11px;';
            let compactBadgeStyle = 'font-weight:700; padding:2px 6px; font-size:10px;';
            let closeBadgeClass = 'badge-status badge-green';

            const stStr = String(t.ticket_status || '');
            if (stStr.includes('5.1')) {
                closeLabel = 'ĐÃ ĐÓNG 5.1';
                closeBadgeClass = 'badge-status';
                closeBadgeStyle += ' background:#e0e7ff; color:#3730a3; border:1px solid #c7d2fe;';
                compactBadgeStyle += ' background:#e0e7ff; color:#3730a3; border:1px solid #c7d2fe;';
            } else if (stStr.includes('2.6')) {
                closeLabel = 'ĐÃ ĐÓNG 2.6';
                closeBadgeClass = 'badge-status badge-green';
            }

            actionHtml = `
                        <div style="display:flex; flex-direction:column; align-items:center; gap:3px;">
                            <span class="${closeBadgeClass}" style="${closeBadgeStyle}">${closeLabel}</span>
                        </div>
                    `;
            compactActionHtml = `<span class="${closeBadgeClass}" style="${compactBadgeStyle}">${closeLabel}</span>`;
        } else if (isTtsNew) {
            let stageBadge = '';
            if (reopenCount > 0) {
                stageBadge = `<span class="badge-status" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-size:9.5px; padding:2px 6px; font-weight:700;" title="THÔNG TIN MỞ LẠI TTS: Số lần mở lại là ${reopenCount}. Không tự động đóng, yêu cầu KTV kiểm tra!">KHÔNG TỰ ĐÓNG</span>`;
            } else if (t.ticket_status === 'Chờ đóng lần 2') {
                stageBadge = `<span class="badge-status" style="background:#fef3c7; color:#b45309; border:1px solid #fde68a; font-size:10px; padding:2px 6px; font-weight:700;">Chờ lần 2</span>`;
            } else if (t.ticket_status === 'Đã chuyển 2.4') {
                stageBadge = `<span class="badge-status" style="background:#e0e7ff; color:#4338ca; border:1px solid #c7d2fe; font-size:10px; padding:2px 6px; font-weight:700;">Đã sang 2.4</span>`;
            } else if (t.ticket_status === 'Phiếu lỗi' || (t.ticket_status && t.ticket_status.includes('lỗi'))) {
                stageBadge = `<span class="badge-status" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-size:10px; padding:2px 6px; font-weight:700;" title="Hệ thống TTS Mới chưa đóng được phiếu này (TTS Mới đang hoàn thiện)">Phiếu lỗi</span>`;
            } else if (currentTableTab === 'all') {
                stageBadge = `<span class="badge-status badge-yellow" style="font-size:10px; padding:2px 6px; font-weight:700;">CHƯA ĐÓNG</span>`;
            }

            if (isStep23) {
                // Bước 2.3 -> Cột Thao tác là "Chuyển 2.4"
                compactActionHtml = `
                    <button class="btn-move-2-4" style="padding:2px 8px; font-size:10px; height:24px; line-height:1;" onclick="handleMoveToStep24('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.ticket_id || ''}', '${t.flow_id || ''}', this)" title="Chuyển phiếu từ bước 2.3 sang bước 2.4 (SOC2)">
                        Chuyển 2.4
                    </button>
                `;

                actionHtml = `
                    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                        ${renderPrecheckBtnHtml(t.phone, t.incident_time, t.prechecked_at || t.updated_at)}
                        <button class="btn-sm btn-outline" style="padding:4px 8px; font-size:11px; display:inline-flex; align-items:center; gap:3px;" onclick="openTtsNewTicketDetail('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this)" title="Mở trang chi tiết phiếu trên TTS Mới">
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
                            Mở TTS
                        </button>
                        <button class="btn-move-2-4" style="padding:5px 12px; font-size:11.5px;" onclick="handleMoveToStep24('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.ticket_id || ''}', '${t.flow_id || ''}', this)" title="Chuyển phiếu từ bước 2.3 sang bước 2.4 (SOC2)">
                            Chuyển 2.4
                        </button>
                    </div>
                `;
            } else if (isStep26) {
                // Bước 2.6 -> Cột Thao tác là "Đóng 2.6"
                compactActionHtml = `
                    <button class="btn-close-green" style="padding:2px 8px; font-size:10px; height:24px; line-height:1; ${reopenCount > 0 ? 'background:#ea580c; border-color:#c2410c;' : ''}" onclick="closeTtsNewTicketApi('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this, ${reopenCount}, '2.6')" title="Đóng dứt điểm phiếu tại bước 2.6">
                        Đóng 2.6
                    </button>
                `;

                actionHtml = `
                    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                        ${renderPrecheckBtnHtml(t.phone, t.incident_time, t.prechecked_at || t.updated_at)}
                        <button class="btn-sm btn-outline" style="padding:4px 8px; font-size:11px; display:inline-flex; align-items:center; gap:3px;" onclick="openTtsNewTicketDetail('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this)" title="Mở trang chi tiết phiếu trên TTS Mới">
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
                            Mở TTS
                        </button>
                        <button class="btn-close-green" style="padding:5px 12px; font-size:11.5px; ${reopenCount > 0 ? 'background:#ea580c; border-color:#c2410c;' : ''}" onclick="closeTtsNewTicketApi('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this, ${reopenCount}, '2.6')" title="Đóng dứt điểm phiếu tại bước 2.6">
                            Đóng 2.6
                        </button>
                    </div>
                `;
            } else {
                // Bước 2.4 -> Cột Thao tác là "Chuyển 2.6"
                const extraClose51Btn = isDataTicket ? `
                    <button class="btn-close-blue" style="padding:5px 10px; font-size:11px; ${reopenCount > 0 ? 'background:#ea580c; border-color:#c2410c;' : ''}" onclick="closeTtsNewTicketApi('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this, ${reopenCount}, '5.1')" title="Chuyển phương án xử lý 5.1 sang VNPT Tỉnh / VTT địa bàn">
                        Đóng 5.1
                    </button>
                ` : '';

                compactActionHtml = `
                    <button class="btn-move-2-6" style="padding:2px 8px; font-size:10px; height:24px; line-height:1; ${reopenCount > 0 ? 'background:#ea580c; border-color:#c2410c;' : ''}" onclick="closeTtsNewTicketApi('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this, ${reopenCount}, '2.6')" title="Chuyển phiếu sang bước 2.6">
                        Chuyển 2.6
                    </button>
                `;

                actionHtml = `
                    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                        ${renderPrecheckBtnHtml(t.phone, t.incident_time, t.prechecked_at || t.updated_at)}
                        <button class="btn-sm btn-outline" style="padding:4px 8px; font-size:11px; display:inline-flex; align-items:center; gap:3px;" onclick="openTtsNewTicketDetail('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this)" title="Mở trang chi tiết phiếu trên TTS Mới">
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
                            Mở TTS
                        </button>
                        <button class="btn-move-2-6" style="padding:5px 10px; font-size:11px; ${reopenCount > 0 ? 'background:#ea580c; border-color:#c2410c;' : ''}" onclick="closeTtsNewTicketApi('${escapeHtml(cleanTicketCode)}', '${t.phone}', '${t.incident_time}', this, ${reopenCount}, '2.6')" title="Chuyển phiếu sang bước 2.6 để đóng trên mạng lưới">
                            Chuyển 2.6
                        </button>
                        ${extraClose51Btn}
                    </div>
                `;
            }
        } else {
            // TTS Cũ
            const statusBadgeAll = (currentTableTab === 'all')
                ? `<span class="badge-status badge-yellow" style="font-size:10px; padding:2px 6px; font-weight:700; margin-bottom:2px;">CHƯA ĐÓNG</span>`
                : '';
            if (isOtherPakh) {
                // Thoại / SMS / Gói cước / PA Khác TTS Cũ:
                compactActionHtml = `
                    <button class="btn-close-green" style="padding:2px 7px; font-size:10px; height:24px; line-height:1;" onclick="closeTtsOldApiTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để đóng phiếu TTS Cũ">
                        Đóng phiếu
                    </button>
                `;
                actionHtml = `
                    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                        ${renderPrecheckBtnHtml(t.phone, t.incident_time, t.prechecked_at || t.updated_at)}
                        <button class="btn-sm btn-outline" style="padding:4px 8px; font-size:11px; display:inline-flex; align-items:center; gap:3px;" onclick="manualCloseTtsOldTicket('${t.phone}', '${escapeHtml(cleanTicketCode)}', this)" title="Mở trang Xử lý sự cố TTS Cũ">
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
                            Mở TTS Cũ
                        </button>
                        <button class="btn-close-green" style="padding:5px 12px; font-size:11.5px;" onclick="closeTtsOldApiTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để đóng phiếu ngay">
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                            Đóng phiếu
                        </button>
                    </div>
                `;
            } else {
                // Mobile Internet TTS Cũ:
                compactActionHtml = `
                    <button class="btn-close-green" style="padding:2px 7px; font-size:10px; height:24px; line-height:1;" onclick="closeTtsOldApiTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để đóng phiếu TTS Cũ">
                        Đóng phiếu
                    </button>
                `;
                actionHtml = `
                    <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                        ${renderPrecheckBtnHtml(t.phone, t.incident_time, t.prechecked_at || t.updated_at)}
                        <button class="btn-sm btn-outline" style="padding:4px 8px; font-size:11px; display:inline-flex; align-items:center; gap:3px;" onclick="manualCloseTtsOldTicket('${t.phone}', '${escapeHtml(cleanTicketCode)}', this)" title="Mở trang Xử lý sự cố TTS Cũ">
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
                            Mở TTS Cũ
                        </button>
                        <button class="btn-close-green" style="padding:5px 12px; font-size:11.5px;" onclick="closeTtsOldApiTicket('${t.phone}', '${t.incident_time}', this)" title="Bấm để đóng phiếu ngay">
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                            Đóng phiếu
                        </button>
                    </div>
                `;
            }
        }

        // Tóm tắt nội dung chỉ dùng cho Mobile Internet. Các trường hợp khác chỉ đưa nội dung phản ánh vào.
        let aiSummaryHtml = '--';
        let compactSummaryHtml = '--';
        let compactSummaryTooltip = '';
        const hasStructuredSummary = isDataTicket && t.ai_summary && t.ai_summary !== 'null' && t.ai_summary.trim() !== '' && (
            t.ai_summary !== t.ticket_content || 
            t.ai_summary.includes('1.') || 
            t.ai_summary.includes('Gói cước sử dụng:') ||
            t.ai_summary.toLowerCase().includes('tình trạng')
        );

        // Parse dữ liệu CEM để phục vụ đối soát địa bàn và hiển thị
        let rawCemIncident = (t.cem_data_incident || '').trim();
        let rawCemRecent = (t.cem_data_recent || '').trim();
        if (!rawCemIncident && !rawCemRecent && t.cem_data && t.cem_data !== '--') {
            const rawCem = t.cem_data.trim();
            if (rawCem.includes('[TIẾP NHẬN]') && rawCem.includes('[GẦN NHẤT]')) {
                const parts = rawCem.split('[GẦN NHẤT]');
                rawCemIncident = parts[0].replace('[TIẾP NHẬN]', '').trim();
                rawCemRecent = (parts[1] || '').trim();
            } else {
                rawCemRecent = rawCem;
                rawCemIncident = 'Chưa quét theo ngày tiếp nhận (Bấm Tiền kiểm lại)';
            }
        }

        const boundaryObj = (t.source === 'tts_new' && t.ticket_id) ? ttsNewTicketBoundaryCache[Number(t.ticket_id)] : null;
        const wardLocation = boundaryObj?.display_text || (t.source === 'tts_new' ? '' : (t.ward || '').trim());
        const wardAudit = evaluateTicketWardStatus(t, ticketKey, rawCemIncident);
        const wardBadgeHtml = wardAudit.badgeHtml;
        const compactWardBadgeHtml = `<div id="compact-ward-badge-${ticketKey}" style="margin-bottom:${wardAudit.compactBadge ? '3px' : '0'}; line-height:1.2; display:${wardAudit.compactBadge ? 'block' : 'none'};">${wardAudit.compactBadge || ''}</div>`;

        const ccosProcessingHtml = t.processing_content ? `
            <details style="margin-top:5px; font-size:10.5px; border-top:1px dashed #cbd5e1; padding-top:4px;">
                <summary style="cursor:pointer; color:#0d9488; font-weight:600;">Xem nội dung xử lý CCOS</summary>
                <div style="margin-top:4px; max-height:90px; overflow-y:auto; color:#0f766e; font-style:normal; line-height:1.35; background:#f0fdfa; padding:4px 6px; border-radius:4px; border:1px solid #ccfbf1; font-family:'JetBrains Mono', Consolas, monospace; font-size:10.5px; white-space:pre-wrap;">${escapeHtml(t.processing_content)}</div>
            </details>
        ` : '';

        if (hasStructuredSummary) {
            const cleanSummaryText = t.ai_summary.replace(/\[?AI\]?[:\-\s]*/gi, '').trim();
            const lines = cleanSummaryText.split('\n').map(l => l.trim().replace(/^\[?AI\]?[:\-\s]*/gi, '')).filter(l => l.length > 0);
            compactSummaryTooltip = (wardLocation ? `[${wardLocation}] ` : '') + lines.join(' | ');
            const summaryText = lines.join(' • ');
            compactSummaryHtml = `
                <div style="display:flex; flex-direction:column; justify-content:center; min-width:0; padding:1px 0;">
                    ${compactWardBadgeHtml}
                    <div class="compact-summary-text" title="${escapeHtml(compactSummaryTooltip)}">
                        ${escapeHtml(summaryText)}
                    </div>
                </div>
            `;
            aiSummaryHtml = `
                        <div style="font-size:11.5px; line-height:1.45;">
                            ${wardBadgeHtml}
                            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
                                <div style="display:inline-flex; align-items:center; gap:4px; font-size:10.5px; font-weight:700; color:#0369a1; background:#f0f9ff; border:1px solid #bae6fd; padding:2px 8px; border-radius:4px;">
                                    Tóm Tắt Nội Dung
                                </div>
                                <button type="button" onclick="openAiTeachModal(event, '${escapeHtml(t.phone || '')}', '${escapeHtml(t.incident_time || '')}', ${t.ticket_id || 0})" style="display:inline-flex; align-items:center; gap:3px; font-size:10.5px; font-weight:600; color:#0284c7; background:#ffffff; border:1px solid #bae6fd; padding:1px 6px; border-radius:4px; cursor:pointer; transition:all 0.15s;" title="Chỉnh sửa & Lưu làm mẫu cho AI học theo" onmouseover="this.style.background='#e0f2fe'" onmouseout="this.style.background='#ffffff'">
                                    Dạy AI
                                </button>
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
                            ${ccosProcessingHtml}
                        </div>
                    `;
        } else {
            const content = t.ticket_content || (t.ai_summary && t.ai_summary !== 'null' ? t.ai_summary : '');
            if (content) {
                compactSummaryTooltip = (wardLocation ? `[${wardLocation}] ` : '') + content;
                const summaryText = content.replace(/\n/g, ' ');
                compactSummaryHtml = `
                    <div style="display:flex; flex-direction:column; justify-content:center; min-width:0; padding:1px 0;">
                        ${compactWardBadgeHtml}
                        <div class="compact-summary-text" title="${escapeHtml(compactSummaryTooltip)}">
                            ${escapeHtml(summaryText)}
                        </div>
                    </div>
                `;
                aiSummaryHtml = `
                    <div style="font-size:11.5px; color:#1e293b; line-height:1.45; word-break:break-word;">
                        ${wardBadgeHtml}
                        ${escapeHtml(content)}
                        <div style="margin-top:4px;">
                            <button type="button" onclick="openAiTeachModal(event, '${escapeHtml(t.phone || '')}', '${escapeHtml(t.incident_time || '')}', ${t.ticket_id || 0})" style="display:inline-flex; align-items:center; gap:3px; font-size:10.5px; font-weight:600; color:#0284c7; background:#ffffff; border:1px solid #bae6fd; padding:1px 6px; border-radius:4px; cursor:pointer;" title="Tạo mẫu chuẩn 6 mục cho AI học">
                                Dạy AI
                            </button>
                        </div>
                        ${ccosProcessingHtml}
                    </div>`;
            } else if (ccosProcessingHtml) {
                aiSummaryHtml = `<div style="font-size:11.5px; color:#1e293b; line-height:1.45;">${wardBadgeHtml}${ccosProcessingHtml}</div>`;
            }
        }

        // Bóc tách thông tin File đính kèm từ CCOS (đặc biệt cho PAKH Cuộc gọi TTS Mới)
        const isCallService = (currentService === 'call' || currentService === 'voice' || (t.package_title && (t.package_title.toLowerCase().includes('cuộc gọi') || t.package_title.toLowerCase().includes('thoại'))));
        let ccosAttachmentHtml = '';
        let ccosData = null;
        if (t.ccos_attachments) {
            try {
                ccosData = typeof t.ccos_attachments === 'string' ? JSON.parse(t.ccos_attachments) : t.ccos_attachments;
            } catch (e) {
                ccosData = null;
            }
        }
        if (isCallService || ccosData) {
            if (ccosData && ccosData.has_file && Array.isArray(ccosData.files) && ccosData.files.length > 0) {
                ccosAttachmentHtml = `
                    <div style="margin-top:8px; padding:7px 10px; background:#eff6ff; border:1px solid #bfdbfe; border-radius:6px; font-size:11.5px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span style="font-weight:700; color:#1e40af; display:inline-flex; align-items:center; gap:4px;">
                                📎 File đính kèm CCOS ${ccosData.kn_code ? `(${escapeHtml(ccosData.kn_code)})` : ''}:
                            </span>
                            <span style="font-size:10px; color:#1d4ed8; background:#dbeafe; padding:1px 6px; border-radius:3px; font-weight:700;">${ccosData.files.length} file</span>
                        </div>
                        <div style="display:flex; flex-direction:column; gap:4px;">
                            ${ccosData.files.map(f => `
                                <a href="${escapeHtml(f.url)}" target="_blank" rel="noopener noreferrer" style="color:#0284c7; font-weight:600; text-decoration:underline; word-break:break-all; display:inline-flex; align-items:center; gap:4px;" title="Bấm để tải/xem file trên CCOS">
                                    📄 ${escapeHtml(f.name)} <span style="font-size:10.5px; color:#64748b;">↗</span>
                                </a>
                            `).join('')}
                        </div>
                    </div>
                `;
                compactSummaryHtml = `<span style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; font-weight:700; font-size:9.5px; padding:1px 5px; border-radius:3px; margin-right:4px;" title="Có ${ccosData.files.length} file đính kèm trên CCOS">📎 File (${ccosData.files.length})</span>` + compactSummaryHtml;
            } else {
                ccosAttachmentHtml = `
                    <div style="margin-top:8px; padding:5px 8px; background:#f8fafc; border:1px dashed #cbd5e1; border-radius:4px; font-size:11px; color:#64748b; display:inline-flex; align-items:center; gap:5px;">
                        📎 File đính kèm: <span style="font-style:italic;">Không có file đính kèm</span>
                    </div>
                `;
            }
        }

        // BÓC TÁCH THÔNG TIN CHẶN GỌI NGOẠI MẠNG / NHÀ MẠNG / CAM KẾT (MODULE SPAM CALL)
        const isSpamCallModule = (currentService === 'spam_call');
        let carrierBadgesHtml = '<span class="badge-status badge-gray" style="font-size:10px; padding:2px 6px;">--</span>';
        let commitmentColumnHtml = '<span class="badge-status badge-gray" style="font-size:10px; padding:2px 6px;">CHƯA CAM KẾT</span>';
        let spamSummaryHtml = compactSummaryHtml;
        const hasCommit = Boolean(t.has_commitment);

        if (isSpamCallModule || t.carrier_display || t.has_commitment !== undefined || t.spam_summary) {
            // 1. Nhà mạng bị ảnh hưởng (Viettel, Mobifone, Vietnamobile, Ngoại mạng)
            const cList = Array.isArray(t.carriers) ? t.carriers : (t.carrier_display ? t.carrier_display.split(',').map(s=>s.trim()).filter(Boolean) : []);
            if (cList.length > 0) {
                carrierBadgesHtml = cList.map(c => {
                    const cLow = c.toLowerCase();
                    if (cLow.includes('viettel')) {
                        return '<span class="badge-status" style="background:#fef2f2; color:#dc2626; border:1px solid #fca5a5; font-weight:700; font-size:10px; padding:2px 6px; display:inline-block; margin:1px;">Viettel</span>';
                    } else if (cLow.includes('mobi')) {
                        return '<span class="badge-status" style="background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe; font-weight:700; font-size:10px; padding:2px 6px; display:inline-block; margin:1px;">Mobifone</span>';
                    } else if (cLow.includes('vietnam')) {
                        return '<span class="badge-status" style="background:#fff7ed; color:#ea580c; border:1px solid #fed7aa; font-weight:700; font-size:10px; padding:2px 6px; display:inline-block; margin:1px;">Vietnamobile</span>';
                    } else {
                        return '<span class="badge-status" style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; font-weight:700; font-size:10px; padding:2px 6px; display:inline-block; margin:1px;">Ngoại mạng</span>';
                    }
                }).join('');
            } else if (t.carrier_display && t.carrier_display !== '--') {
                carrierBadgesHtml = `<span class="badge-status badge-blue" style="font-size:10px; padding:2px 6px;">${escapeHtml(t.carrier_display)}</span>`;
            }

            // 2. Cam kết & File Cam Kết CCOS (Di chuyển link File Cam kết lên phần Cam kết)
            const ccosFiles = (t.commitment_files && Array.isArray(t.commitment_files) && t.commitment_files.length > 0) 
                ? t.commitment_files 
                : (ccosData && Array.isArray(ccosData.files) ? ccosData.files : []);

            if (hasCommit || ccosFiles.length > 0) {
                commitmentColumnHtml = `
                    <div style="display:flex; flex-direction:column; align-items:center; gap:2px;">
                        <span class="badge-status badge-green" style="font-weight:700; font-size:10px; padding:2px 7px;">ĐÃ CÓ CAM KẾT</span>
                        ${ccosFiles.map(f => `
                            <a href="${escapeHtml(f.url)}" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; gap:3px; font-size:10px; font-weight:700; color:#0284c7; background:#f0f9ff; border:1px solid #bae6fd; padding:1.5px 5px; border-radius:3px; text-decoration:none; margin-top:1px; max-width:130px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="Bấm để tải/xem bản cam kết CCOS: ${escapeHtml(f.name)}">
                                <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                                <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(f.name)}</span>
                            </a>
                        `).join('')}
                    </div>
                `;
            } else {
                commitmentColumnHtml = `<span class="badge-status badge-gray" style="font-weight:600; font-size:10px; padding:2px 7px;">CHƯA CAM KẾT</span>`;
            }

            // 3. Tóm tắt ngắn gọn
            const summaryStr = t.spam_summary || t.ticket_content || '';
            spamSummaryHtml = `
                <div style="display:flex; flex-direction:column; justify-content:center; min-width:0; padding:1px 0;">
                    <div class="compact-ellipsis" style="font-size:11px; color:#1e293b; line-height:1.35; font-weight:500;" title="${escapeHtml(summaryStr)}">
                        ${escapeHtml(summaryStr)}
                    </div>
                </div>
            `;
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

        function refineBtoolsWithSapc(btoolsStr, sapcItems, ticketObj) {
            if (!btoolsStr) return btoolsStr;

            let validSapcNames = [];
            if (sapcItems && Array.isArray(sapcItems)) {
                validSapcNames = sapcItems
                    .map(item => (item.name || '').toUpperCase().trim())
                    .filter(n => n && !n.includes('PAYGO') && n !== 'M0' && !n.includes('KHÔNG CÓ GÓI'));
            }

            // Nếu SAPC chưa có gói, trích xuất gói từ ai_summary hoặc ticket_content của phiếu
            if (validSapcNames.length === 0 && ticketObj) {
                const aiSum = ticketObj.ai_summary || '';
                const mAi = aiSum.match(/1\.\s*Gói\s*cước\s*sử\s*dụng\s*:\s*([^\n\r]+)/i);
                if (mAi) {
                    const v = mAi[1].trim();
                    const vLow = v.toLowerCase();
                    if (v && !vLow.includes('không đề cập') && !vLow.includes('không có') && !vLow.includes('chưa kiểm tra') && !vLow.includes('chưa đăng ký') && !vLow.includes('m0') && !vLow.includes('paygo')) {
                        validSapcNames.push(v.toUpperCase());
                    }
                }
                if (validSapcNames.length === 0 && ticketObj.ticket_content) {
                    const mTc = ticketObj.ticket_content.match(/(?:dùng gói|gói cước|gói)\s*[:=]\s*([A-Za-z0-9_]+)/i);
                    if (mTc) {
                        const v = mTc[1].trim();
                        if (v && !['không', 'm0', 'paygo'].includes(v.toLowerCase())) {
                            validSapcNames.push(v.toUpperCase());
                        }
                    }
                }
            }
            
            if (validSapcNames.length === 0) {
                return btoolsStr;
            }

            return btoolsStr.replace(/([A-Za-z0-9_]+)\s*\(([^)]+)\)(\s*\(max\s*[^)]+\))?/g, (fullMatch, groupName, innerContent, maxPart) => {
                if (!innerContent.includes(',') && !innerContent.includes('...')) {
                    return fullMatch;
                }
                const candidates = innerContent.split(/[,;/]/)
                    .map(c => c.replace(/[\.\.\.\(\)]/g, '').trim())
                    .filter(c => c.length >= 2 && !['GÓI', 'DATA', 'NGÀY', 'TUẦN', 'THÁNG'].includes(c.toUpperCase()))
                    .sort((a, b) => b.length - a.length);

                let matched = null;
                for (const cand of candidates) {
                    const candUpper = cand.toUpperCase();
                    for (const sName of validSapcNames) {
                        if (sName.includes(candUpper)) {
                            matched = cand;
                            break;
                        }
                        const sCore = sName.replace(/^(MI_|DC_|KM_|D_)/, '');
                        if (sCore.includes(candUpper) || sCore.startsWith(candUpper)) {
                            matched = cand;
                            break;
                        }
                    }
                    if (matched) break;
                }

                // Nếu không khớp candidate con, kiểm tra tên nhóm (VD: BIG khớp với BIGKM_6GBN)
                if (!matched && groupName) {
                    const grpUpper = groupName.toUpperCase();
                    for (const sName of validSapcNames) {
                        const sCore = sName.replace(/^(MI_|DC_|KM_|D_)/, '');
                        if (sCore.startsWith(grpUpper) || sName.includes(grpUpper)) {
                            matched = sCore;
                            break;
                        }
                    }
                    if (!matched && validSapcNames.length === 1) {
                        matched = validSapcNames[0].replace(/^(MI_|DC_|KM_|D_)/, '');
                    }
                }

                if (matched) {
                    return matched + (maxPart || '');
                }
                return fullMatch;
            });
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
                const hssDigits = (hssVal || '').replace(/\D/g, '');
                const isStrangeHss = (hssDigits.length >= 3 && ((ipVal || '').startsWith('113.') || (ipVal || '').startsWith('172.') || (ipVal || '').startsWith('192.168.'))) || hssVal.includes('PROFILE LẠ');
                gridHtml = `
                            <div class="telecom-diag-grid">
                                <div class="diag-metric-item">
                                    <span class="diag-metric-label">RADIO STATUS</span>
                                    <span class="diag-metric-val val-radio" id="val-radio-${ticketKey}">${renderRadioStatus(radioVal, ticketKey, t.phone)}</span>
                                    <div id="radio-loc-${ticketKey}" class="radio-location-text">${renderRadioLocation(t.phone, ticketKey, t.incident_time)}</div>
                                </div>
                                <div class="diag-metric-item">
                                    <span class="diag-metric-label">HSS PROFILE</span>
                                    ${isStrangeHss ? 
                                        `<span class="diag-metric-val val-hss-strange" title="Cảnh báo: HSS Profile từ 3 chữ số trở lên (${escapeHtml(hssVal)})">⚠️ ${escapeHtml(hssVal)} (PROFILE LẠ)</span>` :
                                        `<span class="diag-metric-val val-hss">${escapeHtml(hssVal || '--')}</span>`
                                    }
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

            if (currentService === 'call' || currentService === 'sms' || currentService === 'roaming' || currentService === 'sim') {
                const isLocked = isNamLocked || raw.includes('NAM: 1') || raw.includes('Khóa dịch vụ') || raw.includes('Khóa GPRS');
                const callStatusBadge = isLocked
                    ? `<span style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-size:11px; padding:3px 8px; border-radius:4px; display:inline-block; font-weight:700;">NAM: 1 (KHÓA DỊCH VỤ)</span>`
                    : `<span style="background:#dcfce7; color:#15803d; border:1px solid #86efac; font-size:11px; padding:3px 8px; border-radius:4px; display:inline-block; font-weight:700;">NAM: 0 (MỞ DỊCH VỤ)</span>`;

                const hssDigits = (hssVal || '').replace(/\D/g, '');
                const isStrangeHss = (hssDigits.length >= 3 && ((ipVal || '').startsWith('113.') || (ipVal || '').startsWith('172.') || (ipVal || '').startsWith('192.168.'))) || hssVal.includes('PROFILE LẠ');
                let hssBadge = '';
                if (isStrangeHss) {
                    hssBadge = `<span style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-size:11px; padding:2px 7px; border-radius:4px; display:inline-block; font-weight:700;" title="Cảnh báo HSS Profile lạ: có thể lỗi cấu hình hoặc chưa kích hoạt VoLTE đúng cách">⚠️ HSS: ${escapeHtml(hssVal)} (PROFILE LẠ)</span>`;
                } else if (hssVal) {
                    hssBadge = `<span style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; font-size:11px; padding:2px 7px; border-radius:4px; display:inline-block; font-weight:700;" title="HSS Profile của thuê bao trên Core">HSS: ${escapeHtml(hssVal)}</span>`;
                } else {
                    hssBadge = `<span style="color:#94a3b8; font-size:10.5px;">HSS: --</span>`;
                }

                let pkgContent = '';
                const pkgTitleSection = (currentService === 'sms') ? 'GÓI TIN NHẮN / DỊCH VỤ:' : ((currentService === 'roaming') ? 'DỊCH VỤ CVQT / ROAMING:' : ((currentService === 'sim') ? 'DỊCH VỤ SIM / MULTISIM:' : 'GÓI THOẠI / DỊCH VỤ:'));
                const noPkgText = (currentService === 'sms') ? 'Không có gói tin nhắn riêng' : ((currentService === 'roaming') ? 'Không có gói CVQT riêng' : ((currentService === 'sim') ? 'Không có thông tin SIM riêng' : 'Không có gói thoại riêng'));
                if (sapcItems.length > 0) {
                    pkgContent = `
                        <div style="margin-top:6px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:6px 8px;">
                            <div style="color:#64748b; font-size:10px; font-weight:700; text-transform:uppercase; margin-bottom:3px;">${pkgTitleSection}</div>
                            ${sapcItems.map(item => `
                                <div style="margin-top:3px; font-size:11px;">
                                    <span style="color:#0f766e; font-weight:700;">${escapeHtml(item.name)}</span>
                                    ${item.dates ? `<div style="font-size:9.5px; color:#64748b;">${escapeHtml(item.dates)}</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    `;
                } else {
                    pkgContent = `<div style="color:#94a3b8; font-size:11px; font-style:italic; margin-top:4px;">${noPkgText}</div>`;
                }
                pkgHtml = `
                    <div style="font-family:'JetBrains Mono', monospace; font-size:11.5px;">
                        <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:6px;">
                            <div>${callStatusBadge}</div>
                            <div>${hssBadge}</div>
                        </div>
                        ${pkgContent}
                    </div>
                `;

                // Bản thu gọn 1 dòng cho cuộc gọi và tin nhắn (bỏ hoàn toàn BTools)
                let cParts = [];
                if (hssVal) {
                    if (isStrangeHss) {
                        cParts.push(`<span style="background:#fee2e2; color:#b91c1c; font-weight:700; padding:1px 5px; border-radius:3px; border:1px solid #fca5a5;">HSS: ${escapeHtml(hssVal)} (LẠ)</span>`);
                    } else {
                        cParts.push(`<span style="background:#eff6ff; color:#1d4ed8; font-weight:700; padding:1px 5px; border-radius:3px; border:1px solid #bfdbfe;">HSS: ${escapeHtml(hssVal)}</span>`);
                    }
                }
                cParts.push(isLocked
                    ? `<span style="background:#fee2e2; color:#b91c1c; font-weight:700; padding:1px 6px; border-radius:3px;">NAM: 1 (Khóa)</span>`
                    : `<span style="color:#15803d; font-weight:700; font-family:'JetBrains Mono', monospace;">NAM: 0 (Mở)</span>`
                );
                if (sapcLines.length > 0) {
                    let firstPkg = sapcLines[0].replace(/^SAPC:\s*/gi, '').trim();
                    cParts.push(`<span style="color:#475569; font-weight:500;">Gói: ${escapeHtml(firstPkg)}</span>`);
                }
                compactProfileHtml = cParts.join(' | ');
            } else {
                let refinedBtoolsText = btoolsLines.length > 0 ? refineBtoolsWithSapc(btoolsLines.join(' '), sapcItems, t) : '';
                let btoolsHtml = `
                    <div style="font-size:10.5px; line-height:1.4; background:#ffffff; border:1px solid #e2e8f0; border-radius:4px; padding:6px 8px; margin-top:4px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
                            <strong style="color:#b45309; font-size:10px; text-transform:uppercase; letter-spacing:0.03em;">Data Usage (BTools):</strong>
                            <a href="${btoolsUrl}" target="_blank" style="font-size:10.5px; color:#b45309; font-weight:700; text-decoration:none;" title="Tra cứu BTools cho thuê bao ${t.phone}">Xem BTools ↗</a>
                        </div>
                        <span style="color:#334155;">${refinedBtoolsText ? escapeHtml(refinedBtoolsText) : '<span style="color:#94a3b8; font-style:italic;">Chưa có dữ liệu btools hoặc không phát sinh</span>'}</span>
                    </div>
                `;

                pkgHtml = `<div>${gridHtml}${btoolsHtml}</div>`;

                // Tạo bản hiển thị rút gọn 1 dòng cho cột Hồ Sơ
                let cParts = [];
                if (raw.includes('Radio:')) {
                    const m = raw.match(/Radio:\s*([^\|\n\\]+)/);
                    if (m) {
                        const rText = m[1].trim();
                        const pInfo = cellInfoClientCache[t.phone] || {};
                        const pLocStr = pInfo.location_str || (pInfo.ward && pInfo.province ? `${pInfo.ward}, ${pInfo.province}` : (pInfo.ward || pInfo.province || ''));
                        const pWardVal = pInfo.ward || pLocStr;
                        const quickBtn = pWardVal ? ` <button type="button" onclick="quickApplyWardFromCell('${escapeHtml(t.phone)}', '${escapeHtml(t.incident_time || '')}', '${escapeHtml(ticketKey)}', '${escapeHtml(pWardVal)}', '${escapeHtml(pInfo.province || '')}', this, event)" style="background:transparent; border:none; cursor:pointer; font-size:10px; padding:0; line-height:1; vertical-align:middle; color:#1d4ed8;" title="Cập nhật nhanh Phường/Xã (${escapeHtml(pWardVal)}) vào Tóm tắt Nội dung"><svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle;"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg></button>` : '';
                        cParts.push(`<span style="color:#0369a1; font-weight:700; font-family:'JetBrains Mono', monospace;">Radio: <span id="compact-radio-${ticketKey}">${formatRadioCellHtml(rText, pInfo.cell_name)}</span><span id="compact-radio-loc-${ticketKey}" style="color:#475569; font-weight:500; font-family:inherit;">${pLocStr ? ` (${escapeHtml(pLocStr)})` : ''}</span>${quickBtn}</span>`);
                    }
                }
                if (hssVal || raw.includes('HSS:')) {
                    const targetHss = hssVal || (raw.match(/HSS:\s*([^\|\n\\]+)/) ? raw.match(/HSS:\s*([^\|\n\\]+)/)[1].trim() : '');
                    const hssDigits = targetHss.replace(/\D/g, '');
                    const isStrangeHssTag = (hssDigits.length >= 3 && ((ipVal || '').startsWith('113.') || (ipVal || '').startsWith('172.') || (ipVal || '').startsWith('192.168.'))) || targetHss.includes('PROFILE LẠ');
                    if (isStrangeHssTag) {
                        cParts.push(`<span style="background:#fee2e2; color:#b91c1c; font-weight:700; padding:1px 5px; border-radius:3px; border:1px solid #fca5a5;">HSS: ${escapeHtml(targetHss)} (PROFILE LẠ)</span>`);
                    }
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
        }

        // Kiểm tra phát hiện app VPN / 1.1.1.1
        let vpnAppName = null;
        const isVpnStatus = (t.status || '').includes('VPN') || (t.status || '').includes('1.1.1.1');
        const vpnKeywords = [
            '1.1.1.1', 'cloudflare', 'warp', 'vpn', 'expressvpn', 'nordvpn', 'openvpn',
            'wireguard', 'betternet', 'turbo vpn', 'supervpn', 'surfshark', 'psiphon',
            'adguard', 'v2ray', 'shadowsocks', 'outline', 'speedify', 'tunnelbear',
            'hotspot shield', 'windscribe', 'protonvpn', 'hide.me', 'cyberghost'
        ];
        const searchVpnText = `${t.cem_data || ''} ${t.app_usage || ''} ${t.comment || ''}`.toLowerCase();
        for (const kw of vpnKeywords) {
            if (searchVpnText.includes(kw)) {
                if (kw === '1.1.1.1' || kw === 'cloudflare' || kw === 'warp') {
                    vpnAppName = '1.1.1.1 / Warp';
                } else {
                    vpnAppName = kw.toUpperCase();
                }
                break;
            }
        }
        // Luôn hiển thị cảnh báo đỏ VPN khi phát hiện ứng dụng VPN/Cloudflare để KTV lưu ý
        const showVpnAlert = Boolean(vpnAppName || isVpnStatus);

        // rawCemIncident và rawCemRecent đã được tính toán ở phần trên phục vụ đối soát địa bàn
        if (!rawCemIncident && !rawCemRecent && t.cem_data && t.cem_data !== '--') {
            const rawCem = t.cem_data.trim();
            if (rawCem.includes('[TIẾP NHẬN]') && rawCem.includes('[GẦN NHẤT]')) {
                const parts = rawCem.split('[GẦN NHẤT]');
                rawCemIncident = parts[0].replace('[TIẾP NHẬN]', '').trim();
                rawCemRecent = (parts[1] || '').trim();
            } else {
                rawCemRecent = rawCem;
                rawCemIncident = 'Chưa quét theo ngày tiếp nhận (Bấm Tiền kiểm lại)';
            }
        }

        function formatCemBlock(rawText, isIncident) {
            if (!rawText || rawText === '--' || rawText === 'null') {
                return '<div style="color:#94a3b8; font-style:italic;">Không có dữ liệu</div>';
            }
            const lines = rawText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
            let rendered = lines.map(line => {
                if (line.includes('CẢNH BÁO VPN') || line.includes('⚠️') || line.toLowerCase().includes('vpn') || line.includes('1.1.1.1')) {
                    if (showVpnAlert) {
                        return `<div style="margin-top:3px; padding:2px 6px; background:#fee2e2; color:#b91c1c; border:1px solid #f87171; border-radius:3px; font-weight:700; font-size:10px;">CẢNH BÁO VPN: ${escapeHtml(line.replace(/^[⚠️\s*]+/, '').replace(/^CẢNH BÁO VPN:\s*/i, ''))}</div>`;
                    }
                    return `<div style="margin-top:2px; color:#64748b; font-size:10px;">${escapeHtml(line.replace(/^[⚠️ℹ️\s*]+/, ''))}</div>`;
                }
                if (line.startsWith('•')) {
                    return `<div style="margin-top:2px; font-family:'JetBrains Mono', monospace; font-weight:600; color:#0f172a;">${escapeHtml(line)}</div>`;
                }
                if (line.startsWith('(') && line.endsWith('):')) {
                    return `<div style="margin-top:2px; font-weight:700; color:#0284c7;">${escapeHtml(line)}</div>`;
                }
                return `<div style="margin-top:2px;">${escapeHtml(line)}</div>`;
            });
            if (!isIncident && showVpnAlert && vpnAppName && !rawText.includes('VPN')) {
                rendered.push(`<div style="margin-top:3px; padding:2px 6px; background:#fee2e2; color:#b91c1c; border:1px solid #f87171; border-radius:3px; font-weight:700; font-size:10px;">CẢNH BÁO VPN: Phát hiện thiết bị có app ${escapeHtml(vpnAppName)}</div>`);
            }
            return rendered.join('');
        }

        const cemIncidentHtml = formatCemBlock(rawCemIncident, true);
        const cemRecentHtml = formatCemBlock(rawCemRecent, false);

        let incidentDateDisplay = '--';
        if (t.incident_time) {
            incidentDateDisplay = String(t.incident_time).trim().split(' ')[0];
        } else if (t.created_time) {
            incidentDateDisplay = String(t.created_time).trim().split(' ')[0];
        }

        let displayStatus = (t.status || '--').trim();
        const fullStatus = displayStatus;
        if (displayStatus.includes('HOẠT ĐỘNG BÌNH THƯỜNG') || displayStatus.includes('HOAT DONG BINH THUONG')) {
            displayStatus = 'BÌNH THƯỜNG';
        } else if (displayStatus.includes('MẠNG LƯỚI ĐẢM BẢO') || displayStatus.includes('ĐỦ ĐIỀU KIỆN ĐÓNG')) {
            displayStatus = 'ĐỦ Đ/K ĐÓNG';
        } else if (displayStatus.includes('KHÓA DỊCH VỤ') || displayStatus.includes('NAM: 1')) {
            displayStatus = 'KHÓA DỊCH VỤ';
        } else if (displayStatus.includes('SPAM')) {
            displayStatus = 'SPAM CUỘC GỌI';
        } else if (displayStatus.includes('PHIẾU MỞ LẠI') || displayStatus.includes('MỞ LẠI')) {
            displayStatus = 'PHIẾU MỞ LẠI';
        } else if (displayStatus.includes('SỰ CỐ DIỆN RỘNG') || displayStatus.includes('SỰ CỐ')) {
            displayStatus = 'SỰ CỐ TRẠM';
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
        } else if (displayStatus.includes('PROFILE LẠ')) {
            displayStatus = 'PROFILE LẠ';
        } else if (displayStatus.includes('LỖI ỨNG DỤNG') || displayStatus.includes('ỨNG DỤNG')) {
            displayStatus = 'LỖI ỨNG DỤNG';
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
            let mainCode = '';
            let procName = '';
            let stepName = '';

            for (const line of codeLines) {
                if (line.includes('/202') || line.startsWith('HT/')) {
                    if (!mainCode) mainCode = line;
                } else if (line.startsWith('[') && line.endsWith(']')) {
                    if (!procName) procName = line;
                } else if (line.includes('2.') || line.includes('5.') || line.toLowerCase().includes('bước') || line.toLowerCase().includes('xử lý') || line.toLowerCase().includes('đóng')) {
                    if (!stepName) stepName = line;
                } else if (!mainCode) {
                    mainCode = line;
                } else if (!stepName) {
                    stepName = line;
                }
            }

            if (!mainCode && codeLines[0]) mainCode = codeLines[0];
            if (mainCode.endsWith('.0') && !isNaN(Number(mainCode))) {
                mainCode = mainCode.slice(0, -2);
            }
            if (!procName && t.process_name) procName = `[${t.process_name}]`;
            if (!stepName && t.step_name) stepName = t.step_name;
            if (procName && !procName.startsWith('[')) procName = `[${procName}]`;

            let isAcknowledged = false;
            try {
                const readTickets = JSON.parse(localStorage.getItem('acknowledged_tickets') || '{}');
                if (readTickets[ticketKey]) isAcknowledged = true;
            } catch(e) {}

            const isNewPending = !(t.ticket_status && (t.ticket_status === 'Đã đóng' || t.ticket_status.includes('Đã đóng')));
            const newBeacon = (isNewPending && !isAcknowledged) 
                ? `<span id="beacon-${ticketKey}" class="pulse-red-dot beacon-${ticketKey}" onclick="dismissNewBeacon('${ticketKey}', event, this)" title="Phiếu mới (Bấm để xóa dấu đỏ / đã biết)"></span>` 
                : '';

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
                    <div style="display:flex; align-items:center; gap:4px;">
                        <span style="color:#0f172a; font-weight:700; font-size:11.5px;">
                            ${escapeHtml(mainCode || '--')}
                        </span>
                        ${newBeacon}
                    </div>
                    ${procName ? `<div style="font-size:10px; font-weight:700; color:#0369a1; background:#f0f9ff; border:1px solid #bae6fd; padding:1px 5px; border-radius:3px; margin-top:3px; display:inline-block;">${escapeHtml(procName)}</div>` : ''}
                    ${stepName ? `<div style="font-size:10.5px; font-weight:500; color:#475569; margin-top:2px; line-height:1.25;">${escapeHtml(stepName)}</div>` : ''}
                    ${reopenBadgeHtml}
                </div>
            `;

            let stepColor = '#475569';
            let stepBg = '#f1f5f9';
            let stepBorder = '#cbd5e1';
            if (stepName) {
                const sLower = stepName.toLowerCase();
                if (stepName.includes('2.6') || sLower.includes('đóng')) {
                    stepColor = '#15803d';
                    stepBg = '#dcfce7';
                    stepBorder = '#86efac';
                } else if (stepName.includes('2.4') || sLower.includes('phối hợp') || sLower.includes('đánh giá')) {
                    stepColor = '#b45309';
                    stepBg = '#fef3c7';
                    stepBorder = '#fde68a';
                } else if (stepName.includes('2.3') || sLower.includes('xử lý')) {
                    stepColor = '#1d4ed8';
                    stepBg = '#eff6ff';
                    stepBorder = '#bfdbfe';
                }
            }

            compactTicketCodeHtml = `
                <div style="display:flex; flex-direction:column; justify-content:center; gap:2px; padding:2px 0; min-width:155px;">
                    <!-- Dòng 1: Mã phiếu trọn vẹn + Dấu đỏ nhấp nháy ngay sau lưng + Reopen badge -->
                    <div style="display:flex; align-items:center; gap:4px; line-height:1.2; white-space:nowrap;">
                        <span style="color:#0f172a; font-weight:700; font-size:11.5px; font-family:'JetBrains Mono', monospace; white-space:nowrap; letter-spacing:-0.2px;" title="Mã phiếu: ${escapeHtml(mainCode)}">
                            ${escapeHtml(mainCode || '--')}
                        </span>
                        ${newBeacon}
                        ${reopenCount > 0 ? `<span class="badge-status" style="background:#fee2e2; color:#dc2626; border:1px solid #f87171; font-weight:800; font-size:9px; padding:1px 4px; border-radius:3px; white-space:nowrap;" title="Mở lại ${reopenCount} lần">Lại: ${reopenCount}L</span>` : ''}
                    </div>
                    <!-- Dòng 2: Tên Quy trình (nếu có) -->
                    ${procName ? `
                    <div style="line-height:1.2; white-space:nowrap;">
                        <span style="font-size:9.5px; font-weight:700; color:#0369a1; background:#f0f9ff; border:1px solid #bae6fd; padding:1px 5px; border-radius:3px; display:inline-block; max-width:260px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-family:-apple-system, BlinkMacSystemFont, sans-serif;" title="Quy trình: ${escapeHtml(procName)}">${escapeHtml(procName)}</span>
                    </div>` : ''}
                    <!-- Dòng 3: Tên bước hiện tại -->
                    <div style="line-height:1.2; white-space:nowrap;">
                        ${stepName 
                            ? `<span style="font-size:9.5px; font-weight:600; color:${stepColor}; background:${stepBg}; border:1px solid ${stepBorder}; padding:1px 5px; border-radius:3px; display:inline-block; max-width:260px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-family:-apple-system, BlinkMacSystemFont, sans-serif;" title="Bước hiện tại: ${escapeHtml(stepName)}">${escapeHtml(stepName)}</span>`
                            : `<span style="color:#94a3b8; font-size:10px; font-style:italic;">--</span>`
                        }
                    </div>
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
                displayPakhType = 'Thoại/SMS/Gói/PA Khác';
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
        } else if (lowerType.includes('cvqt') || lowerType.includes('roaming') || lowerType.includes('quốc tế') || lowerType.includes('chuyển vùng')) {
            pakhBadgeStyle = 'background:#e0e7ff; color:#4338ca; border:1px solid #c7d2fe;';
        } else if (lowerType.includes('sim') || lowerType.includes('esim')) {
            pakhBadgeStyle = 'background:#fce7f3; color:#be185d; border:1px solid #fbcfe8;';
        } else if (lowerType.includes('gói') || lowerType.includes('goi') || lowerType.includes('cước')) {
            pakhBadgeStyle = 'background:#dcfce7; color:#15803d; border:1px solid #86efac;';
        } else {
            pakhBadgeStyle = 'background:#f1f5f9; color:#475569; border:1px solid #cbd5e1;';
        }

        let compactPakhTypeHtml = (displayPakhType === '--')
            ? '<span style="color:#94a3b8; font-size:11px;">--</span>'
            : `<span class="badge-status" style="${pakhBadgeStyle} font-size:9.5px; font-weight:700; padding:2px 6px; border-radius:3px; display:inline-flex; align-items:center; max-width:100%; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${escapeHtml(rawPakhType || displayPakhType)}">${escapeHtml(displayPakhType)}</span>`;

        return `
                    <!-- 1 DÒNG GỌN CHÍNH (COMPACT ROW) -->
                    <tr id="row-main-${ticketKey}" class="ticket-main-row ${isExpanded ? 'is-row-expanded' : ''}">
                        <td class="col-stt-cell" style="width:36px; min-width:36px; max-width:36px; text-align:center; vertical-align:middle; padding:2px 0;">
                            <div style="display:flex; align-items:center; justify-content:center;">
                                <button id="btn-toggle-${ticketKey}" class="stt-expand-pill ${isExpanded ? 'is-expanded' : ''}" onclick="toggleTicketRow('${ticketKey}', event)" title="${isExpanded ? 'Bấm để thu gọn' : 'Bấm để xem chi tiết'}">
                                    <span class="stt-num">${globalIdx + 1}</span>
                                    <svg class="stt-chevron" viewBox="0 0 24 24" width="8" height="8" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">
                                        <polyline points="6 9 12 15 18 9"></polyline>
                                    </svg>
                                </button>
                            </div>
                        </td>
                        <td style="${ticketCodeDisplay} font-family:'JetBrains Mono', monospace; vertical-align:middle; padding:2px 8px; white-space:nowrap;">
                            ${compactTicketCodeHtml}
                        </td>
                        ${(isDataService || isSpamCallModule) ? `
                        <td style="vertical-align:middle; text-align:center; padding:2px 3px;">
                            ${isSpamCallModule ? carrierBadgesHtml : `<span class="badge-status ${badgeClass}" style="white-space:nowrap; font-size:10px; padding:2px 5px; font-weight:700;" title="${escapeHtml(fullStatus)}">${escapeHtml(displayStatus)}</span>`}
                        </td>
                        ` : ''}
                        <td style="vertical-align:middle; text-align:center; padding:2px 4px; white-space:nowrap;">
                            <div style="display:inline-flex; align-items:center; justify-content:center; gap:3px;">
                                <span style="font-family:'JetBrains Mono', monospace; font-weight:700; font-size:11.5px; color:#0f172a; letter-spacing:0.2px;">
                                    ${escapeHtml(t.phone)}
                                </span>
                                ${isSmsTicket ? `
                                <button type="button" onclick="openSmscCdrModal('${t.phone}', event)" style="background:transparent; border:none; color:#0d9488; cursor:pointer; padding:2px; display:inline-flex; align-items:center; border-radius:3px; transition:all 0.15s ease;" onmouseover="this.style.background='#ccfbf1'" onmouseout="this.style.background='transparent'" title="Tra cứu SMSC CDR cho số ${t.phone}">
                                    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                                </button>
                                ` : ''}
                            </div>
                        </td>
                        <td style="vertical-align:middle; text-align:center; padding:2px 3px;">
                            ${isSpamCallModule ? commitmentColumnHtml : compactPakhTypeHtml}
                        </td>
                        <td style="text-align:center; vertical-align:middle; padding:2px 3px; white-space:nowrap;">
                            <span class="table-time-val" title="${escapeHtml(t.incident_time || '--')}">${escapeHtml(t.incident_time || '--')}</span>
                        </td>
                        ${!isSpamCallModule ? `
                        <td style="vertical-align:middle; padding:2px 4px;">
                            <div class="compact-ellipsis" style="font-size:10.5px; color:#334155;" title="${escapeHtml(compactProfileTooltip)}">
                                ${compactProfileHtml}
                            </div>
                        </td>
                        <td style="text-align:center; vertical-align:middle; padding:2px 2px;">
                            ${compactRatHtml}
                        </td>
                        ${!hideCemColumn ? `
                        <td style="vertical-align:middle; padding:2px 4px;">
                            <div class="compact-ellipsis" style="font-size:10px; color:#475569;" title="${escapeHtml(t.cem_data || '--')}">
                                ${(() => {
                                    let cleanCellText = '--';
                                    if (t.cem_data && t.cem_data !== '--' && !t.cem_data.startsWith('Không có dữ liệu')) {
                                        const cParts = t.cem_data.split('\n')
                                            .map(l => l.trim())
                                            .filter(l => l.length > 0 && !l.includes('CẢNH BÁO VPN') && !l.toLowerCase().includes('vpn'));
                                        if (cParts.length > 0) cleanCellText = cParts.join(' ');
                                    }
                                    const cellSpan = cleanCellText !== '--'
                                        ? `<span style="font-family:'JetBrains Mono', monospace; font-weight:600; color:#0f172a;">${escapeHtml(cleanCellText)}</span>`
                                        : `<span style="color:#94a3b8; font-family:'JetBrains Mono', monospace;">--</span>`;
                                    const vpnBadge = vpnAppName
                                        ? `<span style="display:inline-block; background:#fee2e2; color:#b91c1c; border:1px solid #f87171; border-radius:3px; font-weight:700; font-size:9.5px; padding:0 5px; margin-left:3px;" title="Cảnh báo: Thiết bị có cài đặt/dùng app VPN (${escapeHtml(vpnAppName)})">⚠️ VPN: ${escapeHtml(vpnAppName)}</span>`
                                        : '';
                                    return cellSpan + (vpnBadge ? ' ' + vpnBadge : '');
                                })()}
                            </div>
                        </td>
                        ` : ''}
                        ` : ''}
                        <td style="vertical-align:middle; padding:2px 4px;">
                            ${isSpamCallModule 
                                ? spamSummaryHtml 
                                : ((currentTableTab === 'da_dong') 
                                    ? `<div>${formatClosedTimeDisplay(t.closed_at || t.updated_at, t.closed_by, t.ticket_status)}${(() => {
                                        const shortDesc = (t.ticket_content || t.ai_summary || '').replace(/\n/g, ' ').trim();
                                        return shortDesc ? `<div class="compact-ellipsis" style="font-size:10px; color:#64748b; max-width:210px; margin:3px auto 0; text-align:center; line-height:1.25;" title="${escapeHtml(shortDesc)}">${escapeHtml(shortDesc)}</div>` : '';
                                    })()}</div>`
                                    : compactSummaryHtml
                                )
                            }
                        </td>
                        ${(() => {
                            let displayComment = (t.comment !== null && t.comment !== undefined) ? t.comment : '';
                            let displayPlan = (t.action_plan !== null && t.action_plan !== undefined) ? t.action_plan : '';
                            const isVoiceOrCall = (currentService === 'call' || currentService === 'voice' || currentService === 'voice_sms' || (t.package_title && (t.package_title.toLowerCase().includes('thoại') || t.package_title.toLowerCase().includes('cuộc gọi'))));
                            if (isSpamCallModule) {
                                if (hasCommit) {
                                    if (!displayComment) displayComment = 'Đã có bản cam kết, chuyển KTV kiểm tra mở chặn';
                                    if (!displayPlan) displayPlan = 'Đã có bản cam kết, chuyển KTV kiểm tra mở chặn';
                                } else {
                                    if (!displayComment) displayComment = 'Chưa có bản cam kết mở mạng';
                                    if (!displayPlan) displayPlan = 'Chưa có bản cam kết mở mạng';
                                }
                            } else if (isStep23 && (isOtherPakh || isVoiceOrCall)) {
                                if (!displayComment) displayComment = 'Chuyển 2.4';
                                if (!displayPlan) displayPlan = 'Chuyển 2.4';
                            }
                            return `
                        <td style="vertical-align:middle; padding:2px 3px;">
                            <input type="text" id="input-compact-comment-${ticketKey}" class="compact-input-cell" value="${escapeHtml(displayComment)}" placeholder="Ý kiến KTV..." oninput="syncCompactToDetail('${ticketKey}', 'comment', this.value)" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'comment', this.value)">
                        </td>
                        <td style="vertical-align:middle; padding:2px 3px;">
                            <input type="text" id="input-compact-plan-${ticketKey}" class="compact-input-cell" value="${escapeHtml(displayPlan)}" placeholder="Nội dung phản hồi..." oninput="syncCompactToDetail('${ticketKey}', 'action_plan', this.value)" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'action_plan', this.value)">
                        </td>
                            `;
                        })()}
                        <td style="text-align:center; vertical-align:middle; padding:2px 2px;">
                            ${compactActionHtml}
                        </td>
                    </tr>

                    <!-- KHUNG CHI TIẾT MỞ RỘNG (EXPANDED DETAIL ROW) -->
                    <tr id="row-detail-${ticketKey}" class="ticket-detail-row" style="display: ${isExpanded ? 'table-row' : 'none'};">
                        <td colspan="${totalCols}" style="background:#f8fafc; padding:12px 16px; border-bottom:2px solid #cbd5e1;">
                            <div class="detail-expanded-grid">
                                <!-- Card 1: Tóm Tắt Nội Dung & Phản ánh gốc -->
                                <div class="detail-card">
                                    <div class="detail-card-title">
                                        <span>${isSpamCallModule ? 'TÓM TẮT NỘI DUNG & CAM KẾT' : 'TÓM TẮT NỘI DUNG PHẢN ÁNH'}</span>
                                        <span style="font-size:10px; color:#64748b; font-family:'JetBrains Mono', monospace;">${escapeHtml(t.package_title || '')}</span>
                                    </div>
                                    <div style="flex:1; overflow-y:auto; max-height:290px;">
                                        ${isSpamCallModule ? `
                                            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:8px 10px; margin-bottom:8px;">
                                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                                    <span style="font-size:11.5px; font-weight:700; color:#166534;">TÌNH TRẠNG CAM KẾT:</span>
                                                    ${commitmentColumnHtml}
                                                </div>
                                                <div style="font-size:11px; color:#15803d; line-height:1.4;">
                                                    ${hasCommit ? 'Thuê bao đã có bản cam kết sử dụng dịch vụ không spam / cam kết mở mạng liên mạng.' : 'Thuê bao chưa có biên bản cam kết đính kèm.'}
                                                </div>
                                            </div>
                                        ` : ''}
                                        ${aiSummaryHtml}
                                        ${!isSpamCallModule ? ccosAttachmentHtml : ''}
                                    </div>
                                </div>

                                <!-- Card 2: Hồ Sơ Kỹ Thuật & CEM / Spam Call Info -->
                                ${isSpamCallModule ? `
                                <div class="detail-card">
                                    <div class="detail-card-title">
                                        <span>THÔNG TIN THUÊ BAO & NHÀ MẠNG BỊ CHẶN</span>
                                        <span style="font-size:10.5px; color:#005baa; font-family:'JetBrains Mono', monospace; font-weight:700;">${escapeHtml(t.phone)}</span>
                                    </div>
                                    <div style="flex:1; overflow-y:auto; max-height:290px; font-size:11.5px; line-height:1.5;">
                                        <div style="margin-bottom:8px; padding:8px 10px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px;">
                                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                                                <span style="color:#64748b;">Nhà mạng ảnh hưởng:</span>
                                                <div>${carrierBadgesHtml}</div>
                                            </div>
                                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                                <span style="color:#64748b;">Số thuê bao VinaPhone:</span>
                                                <span style="font-weight:700; font-family:'JetBrains Mono', monospace; color:#0f172a;">${escapeHtml(t.phone)}</span>
                                            </div>
                                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                                <span style="color:#64748b;">Thời điểm tiếp nhận:</span>
                                                <span style="color:#334155; font-weight:600;">${escapeHtml(t.incident_time || '--')}</span>
                                            </div>
                                            <div style="display:flex; justify-content:space-between;">
                                                <span style="color:#64748b;">Nguồn thông tin cam kết:</span>
                                                <span style="font-weight:700; color:#0284c7;">${escapeHtml(t.commitment_source || 'Chưa phát hiện')}</span>
                                            </div>
                                        </div>
                                        <div style="padding:8px 10px; background:#eff6ff; border:1px solid #bfdbfe; border-radius:6px; font-size:11px; color:#1e40af;">
                                            <strong style="display:block; margin-bottom:3px;">Khuyến nghị xử lý KTV:</strong>
                                            ${hasCommit 
                                                ? `<div style="color:#15803d; font-weight:600;">✓ Thuê bao đã nộp bản cam kết. KTV kiểm tra đối soát trên phân hệ Chặn Spam liên mạng và điều phối mở chặn theo quy trình.</div>` 
                                                : `<div style="color:#b91c1c; font-weight:600;">⚠ Chưa tìm thấy biên bản cam kết trên CCOS. KTV phản hồi chuyển giao dịch viên yêu cầu khách ký bản cam kết không gửi SMS/gọi rác trước khi mở mạng.</div>`
                                            }
                                        </div>
                                    </div>
                                </div>
                                ` : `
                                <div class="detail-card">
                                    <div class="detail-card-title">
                                        <span>${(isCallService || isSmsService) ? 'HỒ SƠ THUÊ BAO (SAPC / HLR)' : 'PROFILE & DỮ LIỆU CEM'}</span>
                                        <div style="display:flex; align-items:center; gap:8px;">
                                            ${isSmsTicket ? `<button type="button" onclick="openSmscCdrModal('${t.phone}', event)" style="background:#f0fdfa; border:1px solid #99f6e4; color:#0d9488; font-size:10.5px; font-weight:700; border-radius:4px; padding:1px 6px; cursor:pointer;" title="Tra cứu nhật ký tin nhắn SMSC CDR">SMSC CDR ↗</button>` : ''}
                                            <a href="http://10.155.42.218/checkall#" target="_blank" style="font-size:10.5px; color:#005baa; font-weight:700; text-decoration:none;" title="Mở cổng tra cứu SAPC (10.155.42.218/checkall#)">SAPC ↗</a>
                                        </div>
                                    </div>
                                    <div style="flex:1; overflow-y:auto; max-height:290px; font-size:11px; line-height:1.4;">
                                        <div style="margin-bottom:8px;">${pkgHtml}</div>
                                        ${(!isCallService && !isSmsService && ((t.cem_data && t.cem_data !== '--') || (showVpnAlert && vpnAppName))) ? `
                                             <div style="border-top:1px dashed #cbd5e1; padding-top:6px; margin-top:6px;">
                                                 <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                                                     <div style="display:flex; align-items:center; gap:6px;">
                                                         <strong style="color:#0f172a; font-size:11px;">Dữ liệu CEM:</strong>
                                                         <a href="https://cem.vnptmedia.vn/" target="_blank" style="font-size:10.5px; color:#0284c7; font-weight:700; text-decoration:none;" title="Mở cổng CEM (cem.vnptmedia.vn)">CEM ↗</a>
                                                     </div>
                                                     ${showVpnAlert && vpnAppName ? `<span style="background:#fee2e2; color:#b91c1c; border:1px solid #f87171; font-weight:700; font-size:9.5px; padding:1px 6px; border-radius:3px;">CẢNH BÁO VPN: ${escapeHtml(vpnAppName)}</span>` : ''}
                                                 </div>
                                                 <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
                                                     <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:6px 8px; display:flex; flex-direction:column; justify-content:space-between;">
                                                         <div>
                                                             <div style="font-weight:700; font-size:10.5px; color:#0369a1; border-bottom:1px solid #e2e8f0; padding-bottom:3px; margin-bottom:4px; display:flex; justify-content:space-between; align-items:center;">
                                                                 <span>NGÀY TIẾP NHẬN</span>
                                                                 <span style="font-size:10px; font-weight:600; color:#475569;">${escapeHtml(incidentDateDisplay)}</span>
                                                             </div>
                                                             <div style="font-size:10.5px; line-height:1.35; color:#334155;">
                                                                 ${cemIncidentHtml}
                                                             </div>
                                                         </div>
                                                         <div id="cem-incident-loc-${ticketKey}">
                                                             ${renderCemIncidentLocation(ticketKey, rawCemIncident, t.phone, t.incident_time)}
                                                         </div>
                                                     </div>
                                                     <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; padding:6px 8px;">
                                                         <div style="font-weight:700; font-size:10.5px; color:#059669; border-bottom:1px solid #e2e8f0; padding-bottom:3px; margin-bottom:4px; display:flex; justify-content:space-between; align-items:center;">
                                                             <span>GẦN NHẤT CÓ DATA</span>
                                                             <span style="font-size:10px; font-weight:600; color:#475569;">5 ngày</span>
                                                         </div>
                                                         <div style="font-size:10.5px; line-height:1.35; color:#334155;">
                                                             ${cemRecentHtml}
                                                         </div>
                                                     </div>
                                                 </div>
                                             </div>
                                         ` : ''}
                                    </div>
                                </div>
                                `}

                                <!-- Card 3: Nhập Ý Kiến Cột 10 & 11 + Thao Tác -->
                                <div class="detail-card" style="background:#ffffff; border-color:#cbd5e1;">
                                    <div class="detail-card-title">
                                        <span>Ý KIẾN KTV & NỘI DUNG PHẢN HỒI</span>
                                        <span style="font-size:10.5px; color:#15803d; font-weight:600;">Tự động lưu</span>
                                    </div>
                                    <div style="display:flex; flex-direction:column; gap:8px;">
                                        ${(() => {
                                            let detailComment = (t.comment !== null && t.comment !== undefined) ? t.comment : '';
                                            let detailPlan = (t.action_plan !== null && t.action_plan !== undefined) ? t.action_plan : '';
                                            const isVoiceOrCall = (currentService === 'call' || currentService === 'voice' || currentService === 'voice_sms' || (t.package_title && (t.package_title.toLowerCase().includes('thoại') || t.package_title.toLowerCase().includes('cuộc gọi'))));
                                            if (isStep23 && (isOtherPakh || isVoiceOrCall)) {
                                                if (!detailComment) detailComment = 'Chuyển 2.4';
                                                if (!detailPlan) detailPlan = 'Chuyển 2.4';
                                            }

                                            let currentCause = t.incident_cause || '';
                                            if (!currentCause && isDataTicket) {
                                                currentCause = getPredictedIncidentCause(t.status);
                                            }

                                            const groups = (window.TTS_INCIDENT_CAUSE_GROUPS && window.TTS_INCIDENT_CAUSE_GROUPS.length > 0)
                                                ? window.TTS_INCIDENT_CAUSE_GROUPS
                                                : [{ group: "Nguyên nhân phổ biến", items: TTS_INCIDENT_CAUSES.map((c, i) => ({ id: i, name: c })) }];

                                            const totalCausesCount = groups.reduce((acc, g) => acc + (g.items ? g.items.length : 0), 0);

                                            return `
                                        <div style="display:flex; align-items:center; gap:6px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:5px; padding:3px 8px; margin-bottom:2px; min-width:0; width:100%; box-sizing:border-box;">
                                            <span style="font-size:10.5px; font-weight:700; color:#475569; white-space:nowrap; flex-shrink:0;">Nguyên nhân:</span>
                                            <div class="cause-combobox-wrapper" style="position:relative; flex:1; min-width:0;">
                                                <input type="text"
                                                       id="input-detail-cause-${ticketKey}"
                                                       class="searchable-cause-input"
                                                       style="width:100%; height:24px; padding:1px 24px 1px 6px; font-size:11px; font-weight:600; color:#0f172a; border-radius:4px; border:1px solid #cbd5e1; background:#ffffff; outline:none; text-overflow:ellipsis; box-sizing:border-box;"
                                                       placeholder="-- Gõ tìm kiếm nguyên nhân (${totalCausesCount} mục) --"
                                                       value="${escapeHtml(currentCause)}"
                                                       autocomplete="off"
                                                       onfocus="showCauseDropdown('${ticketKey}')"
                                                       oninput="filterCauseDropdown('${ticketKey}', this.value)"
                                                       onchange="handleCauseInputChange('${ticketKey}', '${t.phone}', '${t.incident_time}', this.value)"
                                                       title="${escapeHtml(currentCause || 'Gõ để tìm kiếm hoặc chọn nguyên nhân sự cố')}"
                                                />
                                                <button type="button"
                                                        style="position:absolute; right:2px; top:50%; transform:translateY(-50%); border:none; background:transparent; padding:2px 4px; cursor:pointer; color:#64748b; display:flex; align-items:center; justify-content:center;"
                                                        onclick="toggleCauseDropdown('${ticketKey}', event)"
                                                        tabindex="-1"
                                                        title="Mở toàn bộ danh mục nguyên nhân">
                                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                                                </button>
                                                <input type="hidden" id="select-detail-cause-${ticketKey}" value="${escapeHtml(currentCause)}" />
                                                <div id="dropdown-cause-menu-${ticketKey}"
                                                     class="cause-dropdown-menu"
                                                     data-phone="${escapeHtml(t.phone)}"
                                                     data-time="${escapeHtml(t.incident_time || '')}"
                                                     style="display:none; position:absolute; top:calc(100% + 2px); left:0; width:100%; min-width:480px; max-width:720px; max-height:380px; overflow-y:auto; background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; box-shadow:0 14px 28px -5px rgba(0,0,0,0.25), 0 10px 10px -5px rgba(0,0,0,0.1); z-index:99999; box-sizing:border-box;">
                                                </div>
                                            </div>
                                            <div id="save-cause-${ticketKey}" class="save-indicator" style="margin:0; font-size:9.5px; padding:1px 6px; white-space:nowrap; flex-shrink:0;">Đã lưu</div>
                                        </div>
                                        <div>
                                            <div style="font-size:11px; font-weight:700; color:#334155; margin-bottom:3px; display:flex; justify-content:space-between;">
                                                <span>Ý kiến phân tích (Cột 10):</span>
                                                <div id="save-comment-${ticketKey}" class="save-indicator">Đã lưu tự động</div>
                                            </div>
                                            <textarea id="textarea-detail-comment-${ticketKey}" class="editable-cell" oninput="syncDetailToCompact('${ticketKey}', 'comment', this.value); this.style.height='auto'; this.style.height=(this.scrollHeight+4)+'px';" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'comment', this.value)">${escapeHtml(detailComment)}</textarea>
                                        </div>
                                        <div>
                                            <div style="font-size:11px; font-weight:700; color:#334155; margin-bottom:3px; display:flex; justify-content:space-between;">
                                                <span>Nội dung phản hồi (Cột 11):</span>
                                                <div id="save-plan-${ticketKey}" class="save-indicator">Đã lưu tự động</div>
                                            </div>
                                            <textarea id="textarea-detail-action_plan-${ticketKey}" class="editable-cell" oninput="syncDetailToCompact('${ticketKey}', 'action_plan', this.value); this.style.height='auto'; this.style.height=(this.scrollHeight+4)+'px';" onchange="updateTicket('${t.phone}', '${t.incident_time}', 'action_plan', this.value)">${escapeHtml(detailPlan)}</textarea>
                                        </div>
                                            `;
                                        })()}

                                        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px; margin-top:4px; padding-top:6px; border-top:1px solid #f1f5f9;">
                                            ${reopenCount > 0 ? `
                                                <div style="font-size:10.5px; font-weight:700; color:#b91c1c; background:#fee2e2; border:1px solid #fca5a5; padding:3px 8px; border-radius:4px;">
                                                    Phiếu mở lại ${reopenCount} lần (Yêu cầu KTV xử lý)
                                                </div>
                                            ` : '<div></div>'}
                                            <div style="display:flex; align-items:center; gap:6px; margin-left:auto; flex-wrap:wrap;">
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
        // Kích hoạt quét nhanh từ API theo phân hệ TTS Mới đang chọn
        if (currentService === 'data') {
            fetch('/api/ttsnew/run-now', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
        } else if (currentService === 'call') {
            fetch('/api/ttsnew/scan_call', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
        } else if (currentService === 'sms') {
            fetch('/api/ttsnew/scan_sms', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
        } else if (currentService === 'other') {
            fetch('/api/ttsnew/scan_other', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
        } else if (currentService === 'voice_sms' || currentService === 'voice') {
            fetch('/api/ttsnew/scan_voice', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).catch(() => { });
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
        if (data.token && typeof setTtsAuthSession === 'function') {
            setTtsAuthSession(data.token, { Id: data.user_id, HoTen: data.closed_by });
        }
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
                if (data.message && (data.message.includes('401') || data.message.includes('Authorization has been denied'))) {
                    alert("⚠️ Phiên đăng nhập TTS Cũ đã hết hạn (401).\nVui lòng mở lại tab https://tts.vnpt.vn để đăng nhập lại, hoặc bấm vào biểu tượng 'TTS CŨ' trên thanh công cụ để đồng bộ token mới.");
                } else {
                    alert(data.message || "Thao tác đóng phiếu thất bại.");
                }
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
            const stRes = await fetch('/api/status?region=' + encodeURIComponent(currentRegion || 'ALL'));
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
            const stRes = await fetch('/api/status?region=' + encodeURIComponent(currentRegion || 'ALL'));
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

async function closeTtsNewTicketApi(ticketCode, phone, incidentTime, btnElem, reopenCount = 0, targetStep = '') {
    if (btnElem && btnElem.disabled) return;

    if (currentService === 'voice_sms') {
        alert("Phiếu thuộc loại PAKH khác (Thoại / SMS / Gói cước / CVQT), tuyệt đối không đóng qua API! Vui lòng bấm 'Đóng thủ công'.");
        return;
    }

    const rCount = parseInt(reopenCount || 0, 10);
    const stepLabel = targetStep ? `hướng ${targetStep}` : '';
    if (rCount > 0) {
        const confirmed = confirm(`CẢNH BÁO KTV:\nPhiếu ${ticketCode} (${phone}) có THÔNG TIN MỞ LẠI TTS: Số lần mở lại là ${rCount}!\n\nTheo quy định, phiếu này KHÔNG được phép tự động đóng mà yêu cầu KTV phải kiểm tra kỹ lưỡng.\nBạn có chắc chắn đã kiểm tra đầy đủ và muốn ĐÓNG THỦ CÔNG (${stepLabel}) phiếu này không?`);
        if (!confirmed) return;
    }

    // KIỂM TRA ĐIỀU KIỆN ĐỊA BÀN PHƯỜNG/XÃ KHI ĐÓNG 5.1 (CHUYỂN VNPT TỈNH / VTT ĐỊA BÀN)
    let forceOverrideWard = false;
    if (targetStep === '5.1') {
        const t = (typeof cachedTickets !== 'undefined' && Array.isArray(cachedTickets))
            ? cachedTickets.find(item => item.phone === phone && (!incidentTime || item.incident_time === incidentTime))
            : null;
        if (t) {
            const ticketKey = (t.phone + '_' + (t.incident_time || t.ticket_code || '')).replace(/[^a-zA-Z0-9]/g, '_');
            const wardAudit = (typeof auditWardLocation === 'function') ? auditWardLocation(t, ticketKey) : null;
            if (wardAudit) {
                let warnMsg = '';
                if (wardAudit.status === 'NO_PROVINCE') {
                    warnMsg = `CẢNH BÁO ĐỊA BÀN (BƯỚC 5.1):\n\nPhiếu ${ticketCode} (${phone}) CHƯA CẬP NHẬT TỈNH/TP trên TTS Mới!\n\nBạn có chắc chắn muốn bỏ qua cảnh báo và tiếp tục đóng chuyển bước 5.1 không?`;
                } else if (wardAudit.status === 'NO_WARD') {
                    warnMsg = `CẢNH BÁO ĐỊA BÀN (BƯỚC 5.1):\n\nPhiếu ${ticketCode} (${phone}) CHƯA CẬP NHẬT PHƯỜNG/XÃ trên TTS Mới!\n\nBạn có chắc chắn muốn bỏ qua cảnh báo và tiếp tục đóng chuyển bước 5.1 không?`;
                } else if (wardAudit.status === 'MISMATCH') {
                    warnMsg = `CẢNH BÁO ĐỊA BÀN (BƯỚC 5.1):\n\nĐịa bàn phiếu ${ticketCode} (${phone}) trên TTS Mới đang [SAI KHÁC so với check CEM & PROFILE Status]!\n\nThông tin Phường/Xã ghi nhận không trùng khớp với dữ liệu trạm khách hàng sử dụng thực tế.\n\nBạn có chắc chắn muốn bỏ qua cảnh báo và tiếp tục đóng chuyển bước 5.1 không?`;
                } else if (wardAudit.status === 'LOADING_TTS') {
                    alert(`Hệ thống đang tải dữ liệu Phường/Xã của phiếu ${ticketCode} từ TTS Mới. Vui lòng chờ 2-3 giây rồi bấm lại!`);
                    return;
                }

                if (warnMsg) {
                    const confirmed = confirm(warnMsg);
                    if (!confirmed) {
                        return;
                    }
                    forceOverrideWard = true;
                }
            }
        }
    }

    const session = getTtsAuthSession() || {};
    const ttsNewToken = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';
    const ttsNewUser = (typeof getTtsNewAuthUser === 'function') ? getTtsNewAuthUser() : null;

    if (!ttsNewToken) {
        alert("Phiên làm việc TTS Mới (tts.vnptnet.vn) của bạn chưa kết nối hoặc ĐÃ HẾT HẠN.\n\nVui lòng bấm vào nút 'TTS (MỚI)' trên thanh công cụ để kết nối tài khoản KTV của bạn trước khi thực hiện!");
        openTtsNewModal();
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
        const cInput = row.querySelector('.compact-input-cell[id^="input-compact-comment-"]');
        const pInput = row.querySelector('.compact-input-cell[id^="input-compact-plan-"]');
        if (cInput && !commentVal) commentVal = cInput.value.trim();
        if (pInput && !actionPlanVal) actionPlanVal = pInput.value.trim();
    }

    let incidentCauseVal = '';
    const causeInput = row ? (row.querySelector('input[id^="input-detail-cause-"]') || row.querySelector('input[id^="select-detail-cause-"]') || row.querySelector('select[id^="select-detail-cause-"]')) : null;
    if (causeInput && causeInput.value) {
        incidentCauseVal = causeInput.value.trim();
    } else {
        const anyCause = document.querySelector(`input[id^="input-detail-cause-${phone}"]`) || document.querySelector(`input[id^="select-detail-cause-${phone}"]`) || document.querySelector(`select[id^="select-detail-cause-${phone}"]`);
        if (anyCause && anyCause.value) {
            incidentCauseVal = anyCause.value.trim();
        }
    }

    const originalHtml = btnElem ? btnElem.innerHTML : '';
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = targetStep ? `Đang ${targetStep}...` : `Đang đóng...`;
        btnElem.style.opacity = '0.7';
    }

    try {
        const bearerTok = ttsNewToken.startsWith('Bearer ') ? ttsNewToken : `Bearer ${ttsNewToken}`;
        const res = await fetch('/api/ttsnew/close_one', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': bearerTok
            },
            body: JSON.stringify({
                ticket_code: ticketCode,
                phone: phone,
                incident_time: incidentTime,
                comment: commentVal,
                action_plan: actionPlanVal,
                incident_cause: incidentCauseVal,
                force: (rCount > 0),
                force_override_ward: forceOverrideWard,
                target_step: targetStep || "",
                token: ttsNewToken || "",
                user_id: (ttsNewUser ? ttsNewUser.userId : null) || 0,
                user_name: (ttsNewUser ? (ttsNewUser.displayName || ttsNewUser.username) : null) || "Kỹ thuật viên"
            })
        });
        let data = {};
        const rawText = await res.text().catch(() => "");
        try {
            data = JSON.parse(rawText);
        } catch (jsonErr) {
            throw new Error(`Máy chủ phản hồi lỗi (${res.status}): ${rawText.slice(0, 150) || 'Lỗi không xác định'}`);
        }
        if (data.success) {
            alert(data.message || `Đã xử lý thành công phiếu ${ticketCode}!`);
            clearTicketsModuleCache();
            lastTicketsSignature = "";
            await loadTickets(true);
            await fetchStatus();
        } else {
            if (data.message && (data.message.includes('401') || data.message.includes('hết hạn') || data.message.includes('Token invalid') || data.message.includes('UNAUTHORIZED'))) {
                clearTtsNewAuthToken();
                if (typeof openTtsNewModal === 'function') openTtsNewModal();
            }
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

async function handleMoveToStep24(ticketCode, phone, ticketId, flowId, btnElem) {
    if (btnElem && btnElem.disabled) return;

    const ttsNewToken = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';
    if (!ttsNewToken) {
        alert("⚠️ Phiên làm việc TTS Mới (tts.vnptnet.vn) của bạn chưa kết nối hoặc ĐÃ HẾT HẠN.\n\nVui lòng bấm vào nút 'TTS (MỚI)' trên thanh công cụ để kết nối tài khoản KTV của bạn trước khi chuyển bước!");
        if (typeof openTtsNewModal === 'function') openTtsNewModal();
        return;
    }

    const cleanTicketCode = ticketCode.split('\n')[0].trim();
    const ticketKey = phone || cleanTicketCode;
    const commentEl = document.getElementById(`textarea-detail-comment-${ticketKey}`) || document.getElementById(`textarea-comment-${ticketKey}`);
    const planEl = document.getElementById(`textarea-detail-action_plan-${ticketKey}`) || document.getElementById(`textarea-action_plan-${ticketKey}`);
    const commentVal = commentEl ? commentEl.value.trim() : '';
    const planVal = planEl ? planEl.value.trim() : '';

    const displayComment = commentVal || "Chuyển 2.4 (hoặc lấy từ dữ liệu tiền kiểm)";
    const displayPlan = planVal || "Chuyển 2.4 (hoặc lấy từ dữ liệu tiền kiểm)";

    const confirmMsg = `XÁC NHẬN CHUYỂN BƯỚC 2.4 (TTS MỚI):\n\n` +
        `• Mã phiếu: ${cleanTicketCode}\n` +
        `• Số điện thoại: ${phone}\n` +
        `• Chuyển từ: Bước 2.3  ➔  Bước: 2.4 Đánh giá, báo cáo tình hình xử lý\n` +
        `• Đơn vị nhận: Tổ Dịch vụ (SOC) phụ trách quy trình OneOSS\n` +
        `• Ý kiến phân tích: "${displayComment}"\n` +
        `• Phương án xử lý: "${displayPlan}"\n\n` +
        `Bạn có chắc chắn muốn chuyển phiếu này sang bước 2.4 không?`;

    if (!confirm(confirmMsg)) return;

    const origHtml = btnElem ? btnElem.innerHTML : '';
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = `<span class="status-dot processing" style="width:7px; height:7px; display:inline-block;"></span> Đang chuyển...`;
        btnElem.style.opacity = '0.75';
    }

    const bearerTok24 = ttsNewToken.startsWith('Bearer ') ? ttsNewToken : `Bearer ${ttsNewToken}`;
    try {
        const res = await fetch('/api/tickets/move_to_2_4', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': bearerTok24
            },
            body: JSON.stringify({
                ticket_code: ticketCode,
                phone: phone,
                ticket_id: ticketId || null,
                flow_id: flowId || null,
                token: bearerTok24,
                comment: commentVal,
                action_plan: planVal
            })
        });
        let data = {};
        const rawText = await res.text().catch(() => "");
        try {
            data = JSON.parse(rawText);
        } catch (jsonErr) {
            throw new Error(`Máy chủ phản hồi lỗi (${res.status}): ${rawText.slice(0, 150) || 'Lỗi không xác định'}`);
        }
        if (data.success) {
            alert(data.message || `Đã chuyển thành công phiếu ${ticketCode} sang bước 2.4!`);
            clearTicketsModuleCache();
            lastTicketsSignature = "";
            await loadTickets(true);
            await fetchStatus();
        } else {
            if (data.message && (data.message.includes('401') || data.message.includes('hết hạn') || data.message.includes('Token invalid') || data.message.includes('UNAUTHORIZED'))) {
                clearTtsNewAuthToken();
                if (typeof openTtsNewModal === 'function') openTtsNewModal();
            }
            alert("Lỗi chuyển bước: " + (data.message || "Không thể chuyển bước 2.4"));
            if (btnElem) {
                btnElem.disabled = false;
                btnElem.innerHTML = origHtml;
                btnElem.style.opacity = '1';
            }
        }
    } catch (err) {
        alert("Lỗi kết nối khi gửi yêu cầu chuyển bước: " + err);
        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = origHtml;
            btnElem.style.opacity = '1';
        }
    }
}

async function triggerTtsNewAutoCloseAll(btnElem) {
    if (btnElem && btnElem.disabled) return;

    const ttsNewToken = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';
    const ttsNewUser = (typeof getTtsNewAuthUser === 'function') ? getTtsNewAuthUser() : null;

    if (!ttsNewToken) {
        alert("Bạn cần kết nối tài khoản TTS Mới (tts.vnptnet.vn) của mình trước khi thực hiện đóng tự động!");
        openTtsNewModal();
        return;
    }

    if (!confirm("Xác nhận tự động xử lý đóng tất cả phiếu Mobile Internet đủ điều kiện trên TTS Mới?")) {
        return;
    }

    const originalHtml = btnElem ? btnElem.innerHTML : '';
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = `<span class="status-dot processing" style="display:inline-block; margin-right:6px;"></span> Đang tự động đóng...`;
    }

    const bearerTokAll = ttsNewToken.startsWith('Bearer ') ? ttsNewToken : `Bearer ${ttsNewToken}`;
    try {
        const res = await fetch('/api/ttsnew/close_all', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': bearerTokAll
            },
            body: JSON.stringify({
                token: bearerTokAll,
                user_id: (ttsNewUser ? ttsNewUser.userId : null) || 0,
                user_name: (ttsNewUser ? (ttsNewUser.displayName || ttsNewUser.username) : null) || "Kỹ thuật viên"
            })
        });
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
    const cleanCode = (ticketCode || '').split('\n')[0].trim();
    if (cleanCode && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(cleanCode).catch(() => {});
    }

    const originalHtml = btnElem ? btnElem.innerHTML : '';
    if (btnElem) {
        btnElem.disabled = true;
        btnElem.innerHTML = `Đang mở...`;
        btnElem.style.opacity = '0.7';
    }

    const ttsNewToken = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';

    try {
        const res = await fetch('/api/ttsnew/open_detail', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                ticket_code: cleanCode, 
                phone: phone, 
                incident_time: incidentTime,
                token: ttsNewToken || ''
            })
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
            alert(data.message || `Đã mở chi tiết phiếu ${cleanCode} trên trình duyệt TTS Mới!`);
        } else {
            // Không mở trang chi tiết trực tiếp bằng window.open vì Angular sẽ không có state dẫn đến trang trắng!
            // Thay vào đó mở trang Quản lý phiếu kèm mã phiếu đã copy sẵn trong clipboard.
            window.open('https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu', '_blank');
            alert(`Đã sao chép mã phiếu [${cleanCode}] vào clipboard và mở trang Quản lý phiếu TTS Mới.\nBạn chỉ cần dán (Ctrl+V) mã phiếu vào ô tìm kiếm để xem trực tiếp!`);
            if (btnElem) {
                btnElem.disabled = false;
                btnElem.innerHTML = originalHtml;
                btnElem.style.opacity = '1';
            }
        }
    } catch (e) {
        window.open('https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu', '_blank');
        alert(`Đã sao chép mã phiếu [${cleanCode}] và mở trang Quản lý phiếu TTS Mới.\n(Ctrl+V để dán mã phiếu tìm kiếm).`);
        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = originalHtml;
            btnElem.style.opacity = '1';
        }
    }
}

async function manualCloseTtsNewTicket(ticketCode, phone, incidentTime, btnElem) {
    const cleanCode = (ticketCode || '').split('\n')[0].trim();
    if (cleanCode && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(cleanCode).catch(() => {});
    }

    const ttsNewToken = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';

    // Thử gửi yêu cầu mở trực tiếp trên tab Chrome CDP đang chạy có đẩy đủ router state
    try {
        fetch('/api/ttsnew/open_detail', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                ticket_code: cleanCode, 
                phone: phone, 
                incident_time: incidentTime,
                token: ttsNewToken || ''
            })
        }).then(res => res.json()).then(data => {
            if (!data.success) {
                window.open('https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu', '_blank');
            }
        }).catch(() => {
            window.open('https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu', '_blank');
        });
    } catch (e) {
        window.open('https://tts.vnptnet.vn/tts/ticket/quan-ly-phieu', '_blank');
    }
}

async function manualCloseTtsOldTicket(phone, ticketCode, btnElem) {
    const cleanCode = (ticketCode || '').split('\n')[0].trim();
    const textToCopy = phone || cleanCode;
    // Copy SĐT vào clipboard để KTV tiện tìm kiếm trên TTS Cũ
    if (textToCopy && navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textToCopy).catch(() => {});
    }

    // Chuyển qua trang Xử lý sự cố của TTS Cũ trong tab mới
    window.open('https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new', '_blank');
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
            const saveIdPrefix = field === 'comment' ? 'comment' : (field === 'action_plan' ? 'plan' : 'cause');
            document.querySelectorAll(`[id^="save-${saveIdPrefix}-${phone}"]`).forEach(el => {
                el.style.display = 'block';
                setTimeout(() => el.style.display = 'none', 1800);
            });
        }
    } catch (e) {
        console.error("Lỗi update ticket:", e);
    }
}

// [MODULE: geo_cell.js] -> Quản lý địa bàn sự cố 3 cấp hành chính & quickApplyWardFromCell đã chuyển sang static/js/modules/geo_cell.js

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
    window.isToggleInProgress = true;
    const btnToggle = document.getElementById('btnToggleUnified');
    const lblToggle = document.getElementById('lblToggleUnified');
    if (btnToggle) {
        btnToggle.disabled = true;
        btnToggle.style.opacity = '0.75';
        if (lblToggle) lblToggle.innerText = 'Đang dừng...';
    }
    try {
        await fetch('/api/stop', { method: 'POST' });
    } catch (e) {
        console.error("Lỗi dừng:", e);
    } finally {
        setTimeout(async () => {
            window.isToggleInProgress = false;
            await fetchStatus();
        }, 500);
    }
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
    if (document.getElementById('chkScopeNewCall')?.checked) scopes.push('tts_new_call');
    if (document.getElementById('chkScopeNewSms')?.checked) scopes.push('tts_new_sms');
    if (document.getElementById('chkScopeNewOther')?.checked) scopes.push('tts_new_other');
    if (document.getElementById('chkScopeNewVoice')?.checked) scopes.push('tts_new_voice');
    if (scopes.length === 0) {
        return ['tts_new_data', 'tts_new_call', 'tts_new_sms', 'tts_new_other'];
    }
    return scopes;
}

function updateScopeSummaryLabel(scopes) {
    const lbl = document.getElementById('lblScopeSummary');
    if (!lbl) return;
    const len = scopes.length;
    if (len === 0) {
        lbl.innerText = 'Chưa chọn phạm vi';
    } else if (len >= 5) {
        lbl.innerText = `Quét: Tất cả (${len})`;
    } else if (len === 1) {
        const nameMap = {
            'tts_old_data': 'TTS Cũ (Data)',
            'tts_old_voice': 'TTS Cũ (Thoại/SMS/Gói)',
            'tts_new_data': 'TTS Mới (Data)',
            'tts_new_call': 'TTS Mới (Cuộc gọi)',
            'tts_new_sms': 'TTS Mới (Tin nhắn)',
            'tts_new_other': 'TTS Mới (Gói cước/Khác)',
            'tts_new_voice': 'TTS Mới (Thoại/SMS/Gói)'
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
    const chkNewCall = document.getElementById('chkScopeNewCall');
    const chkNewSms = document.getElementById('chkScopeNewSms');
    const chkNewOther = document.getElementById('chkScopeNewOther');
    const chkNewVoice = document.getElementById('chkScopeNewVoice');
    if (chkOldData) chkOldData.checked = scopes.includes('tts_old_data');
    if (chkOldVoice) chkOldVoice.checked = scopes.includes('tts_old_voice');
    if (chkNewData) chkNewData.checked = scopes.includes('tts_new_data');
    if (chkNewCall) chkNewCall.checked = scopes.includes('tts_new_call');
    if (chkNewSms) chkNewSms.checked = scopes.includes('tts_new_sms');
    if (chkNewOther) chkNewOther.checked = scopes.includes('tts_new_other');
    if (chkNewVoice) chkNewVoice.checked = scopes.includes('tts_new_voice');
    updateScopeSummaryLabel(scopes);
}

async function handleScopeChange() {
    let scopes = getSelectedScopes();
    if (scopes.length === 0) {
        scopes = ['tts_new_data', 'tts_new_call', 'tts_new_sms', 'tts_new_other'];
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

function toggleLoopOption(isChecked) {
    const inp = document.getElementById('inpIntervalUnified');
    const lbl = document.getElementById('lblIntervalMinutes');
    const pillCd = document.getElementById('pillCountdown');
    if (inp) {
        inp.disabled = !isChecked;
        inp.style.opacity = isChecked ? '1' : '0.4';
    }
    if (lbl) {
        lbl.style.opacity = isChecked ? '1' : '0.4';
    }
    if (pillCd) {
        pillCd.style.opacity = isChecked ? '1' : '0.4';
    }
}

// KÍCH HOẠT LÀM MỚI & QUÉT TIỀN KIỂM NGAY LẬP TỨC KHI BẤM ICON REFRESH
async function triggerManualScan() {
    const btnRefresh = document.getElementById('btnRefreshScan');
    if (btnRefresh) {
        btnRefresh.classList.add('spinning');
    }
    const scopes = getSelectedScopes();
    try {
        const res = await fetch('/api/run-now', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scan_scopes: scopes,
                region: currentRegion
            })
        });
        const data = await res.json();
        if (!data.success && data.message) {
            console.log("Run-now:", data.message);
        }
    } catch (e) {
        console.error("Lỗi kích hoạt quét ngay:", e);
    } finally {
        clearTicketsModuleCache();
        await fetchStatus();
        await loadTickets(true);
        setTimeout(() => {
            if (btnRefresh && window.currentServerStatus !== 'PROCESSING') {
                btnRefresh.classList.remove('spinning');
            }
        }, 1200);
    }
}

async function toggleUnifiedAutomation() {
    await triggerManualScan();
}

async function startUnifiedAutomation() {
    await triggerManualScan();
}

window.triggerManualScan = triggerManualScan;
window.toggleUnifiedAutomation = toggleUnifiedAutomation;
window.startUnifiedAutomation = startUnifiedAutomation;

// TIỀN KIỂM LẠI CHO RIÊNG MODULE HIỆN TẠI (TÁI SỬ DỤNG KẾT QUẢ DB NẾU PHIẾU ĐANG Ở BƯỚC 2.6)
async function recheckCurrentModule(btn) {
    let endpoint = '/api/ttsnew/run-now';
    let moduleLabel = 'Mobile Internet (TTS Mới)';

    if (currentService === 'call') {
        endpoint = '/api/ttsnew/scan_call';
        moduleLabel = 'Cuộc gọi (TTS Mới)';
    } else if (currentService === 'sms') {
        endpoint = '/api/ttsnew/scan_sms';
        moduleLabel = 'Tin nhắn (TTS Mới)';
    } else if (currentService === 'other') {
        endpoint = '/api/ttsnew/scan_other';
        moduleLabel = 'Gói cước / PA Khác (TTS Mới)';
    } else if (currentService === 'voice_sms' || currentService === 'voice') {
        endpoint = '/api/ttsnew/scan_voice';
        moduleLabel = 'Thoại / SMS (TTS Mới)';
    }

    if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.7';
        btn.innerText = 'Đang tiền kiểm...';
    }

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true, force_recheck: true, region: currentRegion })
        });
        const data = await res.json();
        console.log(`[Tiền kiểm lại ${moduleLabel}]:`, data);
    } catch (e) {
        console.error("Lỗi tiền kiểm lại:", e);
    } finally {
        setTimeout(async () => {
            if (btn) {
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.innerText = 'Tiền kiểm lại';
            }
            await fetchStatus();
            await loadTickets(true);
        }, 1200);
    }
}
window.recheckCurrentModule = recheckCurrentModule;

// Alias tương thích
const runNowUnified = startUnifiedAutomation;

function exportExcel() {
    window.location.href = '/api/export_excel';
}


// [MODULE: auth_session.js & modal_popups.js] -> Quản lý phiên TTS, Modal Đăng nhập & Popup dịch vụ ngoại vi đã chuyển sang static/js/modules/

// ==============================================================================
// CÁC MODULE CHỨC NĂNG ĐỘC LẬP (ĐÃ ĐƯỢC TÁCH RA THƯ MỤC static/js/modules/)
// 1. static/js/modules/live_log.js        : Dropdown Live Log Terminal
// 2. static/js/modules/smsc_cdr.js        : Tra cứu nhật ký tin nhắn SMSC (CDR)
// 3. static/js/modules/ai_teach.js        : Chỉnh sửa tóm tắt & huấn luyện AI Few-shot
// 4. static/js/modules/user_management.js  : Quản trị phân vùng KTV & Flow Audit
// ==============================================================================
