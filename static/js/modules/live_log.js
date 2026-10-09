// static/js/modules/live_log.js
// Module điều khiển Dropdown Live Log Terminal trên thanh Idle Bar

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
        const logDot = document.getElementById('liveLogDot');
        const errBadge = document.getElementById('liveLogErrorBadge');
        if (pillLog) pillLog.classList.remove('has-error');
        if (logDot) {
            logDot.className = 'svc-status-dot active';
            logDot.style.backgroundColor = '#16a34a';
        }
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
    } catch (e) { }
    const term = document.getElementById('logTerminal');
    if (term) term.innerHTML = '<div class="log-line" style="color:#64748b; font-style:italic;">Đã xóa toàn bộ nhật ký hệ thống...</div>';
    const pillLog = document.getElementById('pillLiveLog');
    const logDot = document.getElementById('liveLogDot');
    const errBadge = document.getElementById('liveLogErrorBadge');
    if (pillLog) pillLog.classList.remove('has-error');
    if (logDot) {
        logDot.className = 'svc-status-dot active';
        logDot.style.backgroundColor = '#16a34a';
    }
    if (errBadge) errBadge.style.display = 'none';
}
