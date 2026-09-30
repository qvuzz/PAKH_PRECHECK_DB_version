// VNPT Multi-Tool Auto-Sync Helper - Content Script v2.5
// Tự động phát hiện và đồng bộ phiên đăng nhập an toàn 100% từ các cổng dịch vụ VNPT:
// 1. OneOSS / NPMRAN (npmran.vnpt.vn, oneoss.vnpt.vn) -> Port 710 (KPI Assistant)
// 2. PMS 3G / 5G (pms.vnpt.vn)                       -> Port 710 (KPI Assistant)
// 3. TTS Mới (tts.vnptnet.vn)                        -> Port 710 & Port 1234
// 4. TTS Cũ (tts.vnpt.vn)                            -> Port 1234
// 5. BTools (10.159.21.241)                          -> Port 1234
// 6. CEM Sóng trạm (cem.vnptmedia.vn)                -> Port 1234
// 7. SAPC (10.155.42.218)                            -> Port 1234
// 8. CCOS (gqknccos.vnpt.vn)                         -> Port 1234

(function () {
    const HOST = window.location.hostname;
    const HREF = window.location.href;

    // Danh sách máy chủ Precheck (Port 1234)
    function getPrecheckServers() {
        const custom = localStorage.getItem('precheck_server_url');
        const list = ['http://localhost:1234', 'http://127.0.0.1:1234'];
        if (custom && !list.includes(custom)) list.unshift(custom);
        return list;
    }

    // Danh sách máy chủ KPI AI Assistant (Port 710)
    function getKpiServers() {
        const custom = localStorage.getItem('kpi_server_url');
        const list = ['http://localhost:710', 'http://127.0.0.1:710'];
        if (custom && !list.includes(custom)) list.unshift(custom);
        return list;
    }

    // Hiển thị huy hiệu thông báo nhỏ góc dưới màn hình
    function showToast(title, subtitle, color = '#0284c7') {
        const id = 'vnpt-sync-toast-notification';
        let toast = document.getElementById(id);
        if (!toast) {
            toast = document.createElement('div');
            toast.id = id;
            toast.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 9999999;
                background: #ffffff;
                border-left: 4px solid ${color};
                border-radius: 8px;
                padding: 12px 18px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.18), 0 2px 8px rgba(0,0,0,0.1);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                align-items: center;
                gap: 12px;
                transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                opacity: 0;
                transform: translateY(15px);
            `;
            document.body.appendChild(toast);
        }

        toast.innerHTML = `
            <div style="width:30px; height:30px; border-radius:50%; background:${color}18; display:flex; align-items:center; justify-content:center; color:${color}; font-size:16px; font-weight:bold;">⚡</div>
            <div>
                <div style="font-size:13px; font-weight:700; color:#0f172a;">${title}</div>
                <div style="font-size:11.5px; color:#64748b;">${subtitle}</div>
            </div>
        `;
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0)';

        setTimeout(() => {
            if (toast) {
                toast.style.opacity = '0';
                toast.style.transform = 'translateY(15px)';
                setTimeout(() => { toast.remove(); }, 400);
            }
        }, 3500);
    }

    // Gửi request an toàn qua Background Service Worker (vượt qua rào cản Mixed Content HTTPS -> HTTP)
    function sendSyncRequest(url, body) {
        return new Promise((resolve) => {
            try {
                if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
                    chrome.runtime.sendMessage({ action: 'sync_post', url: url, body: body }, (resp) => {
                        if (chrome.runtime.lastError || !resp) {
                            fetch(url, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(body || {})
                            }).then(r => r.json()).then(resolve).catch(() => resolve(null));
                        } else {
                            resolve(resp.data || (resp.success ? { success: true } : null));
                        }
                    });
                } else {
                    fetch(url, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body || {})
                    }).then(r => r.json()).then(resolve).catch(() => resolve(null));
                }
            } catch (e) {
                resolve(null);
            }
        });
    }

    // =============================================================
    // 1. DỊCH VỤ: PMS 3G / 5G (pms.vnpt.vn) -> Port 710
    // =============================================================
    if (HOST.includes('pms.vnpt.vn')) {
        let lastPmsSynced = '';

        function syncPms() {
            try {
                // 1. Luôn kích hoạt Background Service Worker để lấy đầy đủ cookie HttpOnly sessionid & csrftoken
                if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
                    chrome.runtime.sendMessage({ action: 'sync_pms_now' }, (resp) => {
                        if (resp && resp.success && resp.sessionid) {
                            if (lastPmsSynced !== resp.sessionid) {
                                lastPmsSynced = resp.sessionid;
                                showToast('KPI AI Assistant', 'Đã đồng bộ Cookie PMS 3G/5G thành công!', '#16a34a');
                            }
                        }
                    });
                }

                // 2. Dự phòng: Đọc thêm từ document.cookie nếu có
                const cookieStr = document.cookie || '';
                const mSess = cookieStr.match(/sessionid=([a-zA-Z0-9_-]+)/i);
                const mCsrf = cookieStr.match(/csrftoken=([a-zA-Z0-9_-]+)/i);

                if (mSess) {
                    const sessionId = mSess[1].trim();
                    const csrfToken = mCsrf ? mCsrf[1].trim() : '';

                    if (lastPmsSynced !== sessionId) {
                        getKpiServers().forEach(server => {
                            sendSyncRequest(`${server}/api/pms/set-token`, {
                                sessionid: sessionId,
                                csrftoken: csrfToken,
                                cookie: `sessionid=${sessionId}; csrftoken=${csrfToken}`
                            }).then(data => {
                                if (data && data.success) {
                                    if (lastPmsSynced !== sessionId) {
                                        lastPmsSynced = sessionId;
                                        showToast('KPI AI Assistant', 'Đã đồng bộ Cookie PMS 3G/5G thành công!', '#16a34a');
                                    }
                                }
                            });
                        });
                    }
                }

                // Nút bấm tiện ích góc màn hình mở nhanh KPI Assistant (Port 710)
                if (!document.getElementById('kpi-pms-sync-btn')) {
                    const btn = document.createElement('button');
                    btn.id = 'kpi-pms-sync-btn';
                    btn.innerHTML = `<span>⚡</span><span>KPI Assistant (Port 710)</span>`;
                    btn.style.cssText = `
                        position: fixed;
                        bottom: 24px;
                        right: 24px;
                        z-index: 999999;
                        background: linear-gradient(135deg, #0055A5 0%, #0284c7 100%);
                        color: #ffffff;
                        border: 2px solid #bae6fd;
                        border-radius: 30px;
                        padding: 10px 18px;
                        font-size: 13px;
                        font-weight: 700;
                        cursor: pointer;
                        box-shadow: 0 10px 25px rgba(0, 85, 165, 0.4), 0 4px 6px rgba(0, 0, 0, 0.1);
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        transition: transform 0.2s, box-shadow 0.2s;
                    `;
                    btn.onclick = () => window.open('http://localhost:710', '_blank');
                    document.body.appendChild(btn);
                }
            } catch (e) {
                console.error("[Sync PMS Error]", e);
            }
        }

        setInterval(syncPms, 3000);
        setTimeout(syncPms, 800);
    }

    // =============================================================
    // 2. DỊCH VỤ: ONEOSS / NPMRAN (npmran.vnpt.vn, oneoss.vnpt.vn) -> Port 710
    // =============================================================
    if (HOST.includes('npmran.vnpt.vn') || HOST.includes('oneoss.vnpt.vn')) {
        let lastOneossSynced = '';

        function syncOneoss() {
            try {
                // Quét token từ các key chuẩn
                const keys = ['TOKEN', 'token', 'access_token', 'JWT_TOKEN', 'scnntttoken'];
                let token = '';

                for (const k of keys) {
                    const v = localStorage.getItem(k) || sessionStorage.getItem(k);
                    if (v && v.startsWith('eyJ')) {
                        token = v;
                        break;
                    }
                }

                // Nếu lưu dạng object JSON hoặc key khác
                if (!token) {
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        const val = localStorage.getItem(key);
                        if (val && val.startsWith('eyJ')) {
                            token = val;
                            break;
                        }
                    }
                }

                if (!token) return;

                // User Info
                let userInfo = {};
                try {
                    userInfo = JSON.parse(localStorage.getItem('USER_INFO') || localStorage.getItem('userInfo') || '{}');
                } catch (e) {}

                if (lastOneossSynced === token) return;

                getKpiServers().forEach(server => {
                    sendSyncRequest(`${server}/api/oneoss/set-token`, {
                        token: token,
                        user: userInfo
                    }).then(data => {
                        if (data && data.success) {
                            if (lastOneossSynced !== token) {
                                lastOneossSynced = token;
                                const userLabel = data.username ? ` (${data.username})` : '';
                                showToast('KPI AI Assistant', `Đã đồng bộ Token OneOSS 4G${userLabel}!`, '#0055A5');
                            }
                        }
                    });
                });

                // Nút bấm tiện ích góc màn hình mở nhanh KPI Assistant (Port 710)
                if (!document.getElementById('kpi-oneoss-sync-btn')) {
                    const btn = document.createElement('button');
                    btn.id = 'kpi-oneoss-sync-btn';
                    btn.innerHTML = `<span>⚡</span><span>KPI Assistant (Port 710)</span>`;
                    btn.style.cssText = `
                        position: fixed;
                        bottom: 24px;
                        right: 24px;
                        z-index: 999999;
                        background: linear-gradient(135deg, #0055A5 0%, #0284c7 100%);
                        color: #ffffff;
                        border: 2px solid #bae6fd;
                        border-radius: 30px;
                        padding: 10px 18px;
                        font-size: 13px;
                        font-weight: 700;
                        cursor: pointer;
                        box-shadow: 0 10px 25px rgba(0, 85, 165, 0.4), 0 4px 6px rgba(0, 0, 0, 0.1);
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        transition: transform 0.2s, box-shadow 0.2s;
                    `;
                    btn.onclick = () => window.open('http://localhost:710', '_blank');
                    document.body.appendChild(btn);
                }
            } catch (e) {
                console.error("[Sync OneOSS Error]", e);
            }
        }

        setInterval(syncOneoss, 3000);
        setTimeout(syncOneoss, 800);
    }

    // =============================================================
    // 3. DỊCH VỤ: TTS MỚI (tts.vnptnet.vn) -> Port 1234 & Port 710
    // =============================================================
    if (HOST.includes('tts.vnptnet.vn')) {
        let lastTtsNewSynced = '';
        function syncTtsNew() {
            let token = localStorage.getItem('TOKEN') || sessionStorage.getItem('TOKEN') || '';
            if (!token) return;

            let userInfo = {};
            try {
                userInfo = JSON.parse(localStorage.getItem('USER_INFO') || localStorage.getItem('userInfo') || '{}');
            } catch (e) {}

            if (lastTtsNewSynced === token) return;

            // Gửi sang Precheck 1234
            getPrecheckServers().forEach(server => {
                sendSyncRequest(`${server}/api/ttsnew/token`, { token: token, user: userInfo })
                .then(data => {
                    if (data && data.success) {
                        lastTtsNewSynced = token;
                        showToast('PAKH Precheck', 'Đã đồng bộ Token TTS Mới!', '#0284c7');
                    }
                });
            });

            // Gửi sang KPI Assistant 710 (vì TTS Mới cũng dùng chung Token OneOSS/NPMRAN)
            getKpiServers().forEach(server => {
                sendSyncRequest(`${server}/api/oneoss/set-token`, { token: token, user: userInfo });
            });
        }
        setInterval(syncTtsNew, 3000);
        setTimeout(syncTtsNew, 800);
    }

    // =============================================================
    // 4. DỊCH VỤ: BTOOLS (10.159.21.241) -> Port 1234
    // =============================================================
    if (HOST.includes('10.159.21.241')) {
        let lastBtoolsSynced = '';
        function syncBtools() {
            const cookie = document.cookie || '';
            const match = cookie.match(/JSESSIONID=([^;]+)/i);
            if (!match) return;

            const jsessionId = match[1].trim();
            if (lastBtoolsSynced === jsessionId) return;

            getPrecheckServers().forEach(server => {
                sendSyncRequest(`${server}/api/btools/cookie`, { cookie: `JSESSIONID=${jsessionId}`, raw: cookie })
                .then(data => {
                    if (data && data.success) {
                        lastBtoolsSynced = jsessionId;
                        showToast('PAKH Precheck', 'Đã đồng bộ Session BTools!', '#ea580c');
                    }
                });
            });
        }
        setInterval(syncBtools, 3000);
        setTimeout(syncBtools, 800);
    }

    // =============================================================
    // 5. DỊCH VỤ: CEM SÓNG TRẠM (cem.vnptmedia.vn) -> Port 1234
    // =============================================================
    if (HOST.includes('cem.vnptmedia.vn')) {
        let lastCemSynced = '';
        function syncCem() {
            let apiKey = '';
            const cookie = document.cookie || '';
            const match = cookie.match(/apikey=([^;]+)/i);
            if (match) {
                apiKey = decodeURIComponent(match[1].trim());
            } else {
                apiKey = localStorage.getItem('apikey') || sessionStorage.getItem('apikey') || '';
            }

            if (!apiKey || lastCemSynced === apiKey) return;

            getPrecheckServers().forEach(server => {
                sendSyncRequest(`${server}/api/cem/auth`, { api_key: apiKey, raw_cookie: cookie })
                .then(data => {
                    if (data && data.success) {
                        lastCemSynced = apiKey;
                        showToast('PAKH Precheck', 'Đã đồng bộ API Key CEM!', '#16a34a');
                    }
                });
            });
        }
        setInterval(syncCem, 3000);
        setTimeout(syncCem, 800);
    }

    // =============================================================
    // 6. DỊCH VỤ: SAPC (10.155.42.218) -> Port 1234
    // =============================================================
    if (HOST.includes('10.155.42.218')) {
        function triggerSapcSync() {
            try {
                chrome.runtime.sendMessage({ action: 'sync_sapc_now' });
            } catch (e) {}
        }
        setInterval(triggerSapcSync, 5000);
        setTimeout(triggerSapcSync, 1000);
    }

    // =============================================================
    // 7. DỊCH VỤ: TTS CŨ (tts.vnpt.vn) -> Port 1234
    // =============================================================
    if (HOST.includes('tts.vnpt.vn')) {
        let lastTtsOldSynced = '';

        function syncTtsOld() {
            try {
                let token = localStorage.getItem('scnntttoken') || 
                            sessionStorage.getItem('scnntttoken') || 
                            localStorage.getItem('token') || 
                            sessionStorage.getItem('token') || '';
                
                if (!token) {
                    const cookie = document.cookie || '';
                    const m = cookie.match(/scnntttoken=([^;]+)/i);
                    if (m) token = decodeURIComponent(m[1].trim());
                }

                if (!token) return;

                let userInfo = {};
                let rawUser = localStorage.getItem('userInfo') || sessionStorage.getItem('userInfo') || '';
                if (rawUser) {
                    try {
                        userInfo = JSON.parse(rawUser);
                    } catch (e1) {
                        try {
                            userInfo = JSON.parse(atob(rawUser));
                        } catch (e2) {}
                    }
                }

                if (lastTtsOldSynced !== token) {
                    getPrecheckServers().forEach(server => {
                        sendSyncRequest(`${server}/api/session/register`, { token: token, user: userInfo })
                        .then(data => {
                            if (data && data.success) {
                                if (lastTtsOldSynced !== token) {
                                    lastTtsOldSynced = token;
                                    showToast('PAKH Precheck', 'Đã đồng bộ Token TTS Cũ!', '#ea580c');
                                }
                            }
                        });
                        sendSyncRequest(`${server}/api/tts_old/token`, { token: token, user: userInfo });
                    });
                }
            } catch (e) {
                console.error("[Precheck Helper TTS Cũ Error]", e);
            }
        }

        setInterval(syncTtsOld, 3000);
        setTimeout(syncTtsOld, 1000);
    }

    // =============================================================
    // 8. DỊCH VỤ: CCOS (gqknccos.vnpt.vn) -> Port 1234
    // =============================================================
    if (HOST.includes('gqknccos.vnpt.vn')) {
        let lastCcosCookie = '';

        function syncCcos() {
            try {
                if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.sendMessage) {
                    chrome.runtime.sendMessage({ action: 'sync_ccos_now' });
                }

                const docCookie = document.cookie || '';
                if (!docCookie) return;
                if (!docCookie.includes('SessionDB') && !docCookie.includes('SESSIONID')) return;
                if (lastCcosCookie === docCookie) return;

                getPrecheckServers().forEach(server => {
                    sendSyncRequest(`${server}/api/ccos/update-cookie`, { cookie: docCookie })
                    .then(data => {
                        if (data && data.success) {
                            lastCcosCookie = docCookie;
                            showToast('PAKH Precheck', 'Đã tự động đồng bộ Cookie CCOS!', '#005baa');
                        }
                    });
                });
            } catch (e) {
                console.error("[Precheck Helper CCOS Error]", e);
            }
        }

        setInterval(syncCcos, 3000);
        setTimeout(syncCcos, 800);
    }
})();
