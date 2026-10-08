/**
 * VNPT Token Utilities - Popup Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    initEvents();
    loadStatus();
});

function initEvents() {
    // Sync All Button
    const btnSync = document.getElementById('btn-sync-now');
    if (btnSync) {
        btnSync.addEventListener('click', () => {
            btnSync.disabled = true;
            btnSync.textContent = 'Syncing...';
            chrome.runtime.sendMessage({ action: 'sync_now' }, (bundle) => {
                btnSync.disabled = false;
                btnSync.textContent = 'Sync All Now';
                if (bundle) renderUI(bundle);
            });
        });
    }

    // Clear Cache & Resync Button
    // Save & Sync Precheck Server Button
    const btnSaveServer = document.getElementById('btn-save-server');
    const inpServer = document.getElementById('inp-precheck-server');
    const statusText = document.getElementById('precheck-server-status');
    if (btnSaveServer && inpServer) {
        btnSaveServer.addEventListener('click', () => {
            let srv = (inpServer.value || '').trim();
            if (!srv) srv = 'http://localhost:1234';
            if (!srv.startsWith('http://') && !srv.startsWith('https://')) {
                srv = 'http://' + srv;
            }
            srv = srv.replace(/\/$/, '');
            inpServer.value = srv;
            btnSaveServer.disabled = true;
            btnSaveServer.textContent = 'Đang đẩy...';
            if (statusText) {
                statusText.className = 'server-status-text';
                statusText.textContent = 'Đang lưu và đẩy token sang ' + srv + '...';
            }
            chrome.runtime.sendMessage({ action: 'set_precheck_server', url: srv }, (bundle) => {
                btnSaveServer.disabled = false;
                btnSaveServer.textContent = 'Lưu & Đẩy';
                if (bundle) renderUI(bundle);
                checkServerConnection(srv);
            });
        });
    }

    const btnClear = document.getElementById('btn-clear-sync');
    if (btnClear) {
        btnClear.addEventListener('click', () => {
            btnClear.disabled = true;
            btnClear.textContent = 'Clearing cache...';
            chrome.runtime.sendMessage({ action: 'clear_and_sync' }, (bundle) => {
                btnClear.disabled = false;
                btnClear.textContent = 'Clear Cache & Resync';
                if (bundle) renderUI(bundle);
            });
        });
    }

    // External URL Buttons
    document.querySelectorAll('[data-url]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetUrl = e.currentTarget.getAttribute('data-url');
            if (targetUrl) {
                chrome.runtime.sendMessage({ action: 'open_url', url: targetUrl });
            }
        });
    });
}

function loadStatus() {
    chrome.runtime.sendMessage({ action: 'get_status' }, (bundle) => {
        if (bundle) {
            renderUI(bundle);
        } else {
            chrome.runtime.sendMessage({ action: 'sync_now' }, (newBundle) => {
                if (newBundle) renderUI(newBundle);
            });
        }
    });

    chrome.storage.local.get(['last_heartbeat_time'], (res) => {
        const hbEl = document.getElementById('last-heartbeat-time');
        if (hbEl && res.last_heartbeat_time) {
            hbEl.textContent = res.last_heartbeat_time;
        }
    });

    // Check local port health directly
    checkLocalPort('http://localhost:710/api/token-status', 'port-710');
    checkLocalPort('http://localhost:9190/api/auth/overview', 'port-9190');
    checkLocalPort('http://localhost:1234/api/status', 'port-1234');
}

async function checkLocalPort(url, elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    try {
        const controller = new AbortController();
        const tid = setTimeout(() => controller.abort(), 1200);
        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(tid);
        if (res.ok || res.status === 404 || res.status === 401) {
            el.classList.add('online');
        } else {
            el.classList.remove('online');
        }
    } catch (e) {
        el.classList.remove('online');
    }
}

function renderUI(bundle) {
    if (!bundle) return;

    // Last sync timestamp
    const timeEl = document.getElementById('last-sync-time');
    if (timeEl && bundle.timestamp) {
        timeEl.textContent = bundle.timestamp;
    }

    // Last heartbeat timestamp
    const hbEl = document.getElementById('last-heartbeat-time');
    if (hbEl && bundle.last_heartbeat_time) {
        hbEl.textContent = bundle.last_heartbeat_time;
    }

    let activeCount = 0;

    // 1. BTool
    if (bundle.btools) {
        const has = bundle.btools.hasCookie;
        if (has) activeCount++;
        updateCardStatus('btools', has, bundle.btools.preview || 'No cookie');
    }

    // 2. CCOS
    if (bundle.ccos) {
        const has = bundle.ccos.hasCookie;
        if (has) activeCount++;
        updateCardStatus('ccos', has, bundle.ccos.preview || 'No session');
    }

    // 3. CEM
    if (bundle.cem) {
        const has = bundle.cem.hasKey;
        if (has) activeCount++;
        updateCardStatus('cem', has, bundle.cem.preview || 'No API key/cookie');
    }

    // 4. CTS
    if (bundle.cts) {
        const has = bundle.cts.hasCookie;
        if (has) activeCount++;
        updateCardStatus('cts', has, bundle.cts.preview || 'No cookie');
    }

    // 5. NPMRAN
    if (bundle.oneoss) {
        const has = bundle.oneoss.valid;
        if (has) activeCount++;
        const info = has ? `${bundle.oneoss.user || ''} (${bundle.oneoss.preview})` : 'No JWT token';
        updateCardStatus('npmran', has, info);
    }

    // 6. PMS
    if (bundle.pms) {
        const has = bundle.pms.hasCookie;
        if (has) activeCount++;
        updateCardStatus('pms', has, bundle.pms.preview || 'No cookie');
    }

    // 7. tts.vnpt.vn
    if (bundle.tts_old) {
        const has = bundle.tts_old.valid;
        if (has) activeCount++;
        const info = has ? `${bundle.tts_old.user ? bundle.tts_old.user + ' ' : ''}(${bundle.tts_old.preview})` : 'No token';
        updateCardStatus('tts-vnpt', has, info);
    }

        // SAPC (10.155.42.218)
    if (bundle.sapc) {
        const has = bundle.sapc.hasCookie;
        if (has) activeCount++;
        updateCardStatus('sapc', has, bundle.sapc.preview || 'No cookie');
    }

    // 8. tts.vnptnet.vn
    if (bundle.tts_new) {
        const has = bundle.tts_new.valid;
        if (has) activeCount++;
        const info = has ? `${bundle.tts_new.user || ''} (${bundle.tts_new.preview})` : 'No JWT token';
        updateCardStatus('tts-vnptnet', has, info);
    }

    // Master Badge
    const masterBadge = document.getElementById('badge-master');
    if (masterBadge) {
        if (activeCount >= 6) {
            masterBadge.className = 'status-pill status-green';
            masterBadge.textContent = `${activeCount}/9 READY`;
        } else if (activeCount > 0) {
            masterBadge.className = 'status-pill status-blue';
            masterBadge.textContent = `${activeCount}/9 CONNECTED`;
        } else {
            masterBadge.className = 'status-pill status-red';
            masterBadge.textContent = 'NO TOKENS';
        }
    }

    // Port sync indicators from dispatch
    if (bundle.dispatch) {
        if (bundle.dispatch.port710 && bundle.dispatch.port710.online) {
            const el = document.getElementById('port-710');
            if (el) el.classList.add('online');
        }
        if (bundle.dispatch.port9190 && bundle.dispatch.port9190.online) {
            const el = document.getElementById('port-9190');
            if (el) el.classList.add('online');
        }
        if (bundle.dispatch.port1234 && bundle.dispatch.port1234.online) {
            const el = document.getElementById('port-1234');
            if (el) el.classList.add('online');
        }
    }
}

function updateCardStatus(prefix, isConnected, previewText) {
    const statusEl = document.getElementById(`${prefix}-status`);
    const previewEl = document.getElementById(`${prefix}-preview`);

    if (statusEl) {
        if (isConnected) {
            statusEl.className = 'status-dot green';
            statusEl.title = 'Active Token';
        } else {
            statusEl.className = 'status-dot red';
            statusEl.title = 'No Token';
        }
    }

    if (previewEl) {
        previewEl.textContent = previewText;
    }
}

async function checkServerConnection(serverUrl) {
    const el = document.getElementById('port-1234');
    const statusText = document.getElementById('precheck-server-status');
    const cleanUrl = (serverUrl || 'http://localhost:1234').replace(/\/$/, '');
    try {
        const controller = new AbortController();
        const tid = setTimeout(() => controller.abort(), 2500);
        const res = await fetch(`${cleanUrl}/api/status`, { signal: controller.signal });
        clearTimeout(tid);
        if (res.ok) {
            if (el) el.classList.add('online');
            if (statusText) {
                statusText.className = 'server-status-text ok';
                statusText.textContent = 'Kết nối thành công máy chủ: ' + cleanUrl;
            }
        } else {
            if (el) el.classList.remove('online');
            if (statusText) {
                statusText.className = 'server-status-text err';
                statusText.textContent = 'Máy chủ phản hồi mã ' + res.status + ': ' + cleanUrl;
            }
        }
    } catch (e) {
        if (el) el.classList.remove('online');
        if (statusText) {
            statusText.className = 'server-status-text err';
            statusText.textContent = 'Không thể kết nối máy chủ: ' + cleanUrl;
        }
    }
}
