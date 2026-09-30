// VNPT Multi-Tool Auto-Sync Helper - Background Service Worker (Manifest V3)
// Đóng vai trò proxy gửi request từ Content Script về máy chủ cục bộ (tránh chặn HTTPS -> HTTP)
// Tự động lắng nghe & đồng bộ Cookie CCOS và Cookie PMS trực tiếp từ Chrome Cookies API

const PRECHECK_SERVERS = [
    'http://127.0.0.1:1234',
    'http://localhost:1234'
];

const KPI_SERVERS = [
    'http://127.0.0.1:710',
    'http://localhost:710'
];

// ==========================================
// 1. TỰ ĐỘNG ĐỒNG BỘ COOKIE CCOS (Precheck 1234)
// ==========================================
function syncCcosCookiesFromBackground() {
    try {
        if (!chrome.cookies) return;
        chrome.cookies.getAll({ domain: 'gqknccos.vnpt.vn' }, (cookies) => {
            if (chrome.runtime.lastError || !cookies || cookies.length === 0) return;
            const parts = cookies.map(c => `${c.name}=${c.value}`);
            const cookieStr = parts.join('; ');
            if (!cookieStr.includes('SessionDB') && !cookieStr.includes('SESSIONID')) return;

            PRECHECK_SERVERS.forEach(server => {
                fetch(`${server}/api/ccos/update-cookie`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cookie: cookieStr })
                }).catch(() => {});
            });
        });
    } catch (e) {}
}

// ==========================================
// 1.1 TỰ ĐỒNG ĐỒNG BỘ COOKIE BTOOLS (Precheck 1234)
// ==========================================
function syncBtoolsCookiesFromBackground() {
    try {
        if (!chrome.cookies) return;
        chrome.cookies.getAll({ url: 'http://10.159.21.241:9267/B_tools_v2/' }, (cookies) => {
            let jsessionId = '';
            (cookies || []).forEach(c => {
                if (c.name.toUpperCase() === 'JSESSIONID') jsessionId = c.value;
            });
            if (!jsessionId) {
                chrome.cookies.getAll({ domain: '10.159.21.241' }, (cookiesDomain) => {
                    (cookiesDomain || []).forEach(c => {
                        if (c.name.toUpperCase() === 'JSESSIONID') jsessionId = c.value;
                    });
                    if (!jsessionId) return;
                    PRECHECK_SERVERS.forEach(server => {
                        fetch(`${server}/api/btools/cookie`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ cookie: `JSESSIONID=${jsessionId}` })
                        }).catch(() => {});
                    });
                });
            } else {
                PRECHECK_SERVERS.forEach(server => {
                    fetch(`${server}/api/btools/cookie`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ cookie: `JSESSIONID=${jsessionId}` })
                    }).catch(() => {});
                });
            }
        });
    } catch (e) {}
}

// ==========================================
// 1.2 TỰ ĐỘNG ĐỒNG BỘ AUTH CEM (Precheck 1234)
// ==========================================
function syncCemAuthFromBackground() {
    try {
        if (!chrome.cookies) return;
        chrome.cookies.getAll({ domain: 'vnptmedia.vn' }, (cookies) => {
            let apiKey = '';
            const cookieMap = {};
            const parts = [];
            (cookies || []).forEach(c => {
                cookieMap[c.name] = c.value;
                parts.push(`${c.name}=${c.value}`);
                if (c.name.toLowerCase() === 'apikey' || c.name.toLowerCase() === 'api_key') {
                    apiKey = decodeURIComponent(c.value);
                }
            });
            if (!apiKey) return;
            PRECHECK_SERVERS.forEach(server => {
                fetch(`${server}/api/cem/auth`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_key: apiKey, raw_cookie: parts.join('; '), cookies: cookieMap })
                }).catch(() => {});
            });
        });
    } catch (e) {}
}

// ==========================================
// 1.3 TỰ ĐỘNG ĐỒNG BỘ COOKIE SAPC (Precheck 1234)
// ==========================================
function _processSapcCookies(cookies) {
    if (!cookies || cookies.length === 0) return;
    const parts = [];
    let hasAuth = false;
    cookies.forEach(c => {
        parts.push(`${c.name}=${c.value}`);
        if (c.name.includes('ApplicationCookie') || c.name.toLowerCase().includes('session')) {
            hasAuth = true;
        }
    });
    if (!hasAuth && parts.length === 0) return;
    const cookieStr = parts.join('; ');
    PRECHECK_SERVERS.forEach(server => {
        fetch(`${server}/api/sapc/cookie`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookie: cookieStr, cookies: cookies })
        }).catch(() => {});
    });
}

function syncSapcCookiesFromBackground() {
    try {
        if (!chrome.cookies) return;
        chrome.cookies.getAll({ domain: '10.155.42.218' }, (cookies) => {
            if (!cookies || cookies.length === 0) {
                chrome.cookies.getAll({ url: 'http://10.155.42.218/' }, (cookiesUrl) => {
                    _processSapcCookies(cookiesUrl);
                });
                return;
            }
            _processSapcCookies(cookies);
        });
    } catch (e) {}
}


// ==========================================
// 2. TỰ ĐỘNG ĐỒNG BỘ COOKIE PMS (KPI Assistant 710)
// ==========================================
function getPmsCookies() {
    return new Promise((resolve) => {
        if (!chrome.cookies) return resolve({});

        // 1. Quét theo cả URL HTTPS lẫn HTTP của PMS (bắt được cả HttpOnly lẫn Host-only cookie)
        chrome.cookies.getAll({ url: 'https://pms.vnpt.vn' }, (cookiesHttps) => {
            chrome.cookies.getAll({ url: 'http://pms.vnpt.vn' }, (cookiesHttp) => {
                const combined = [...(cookiesHttps || []), ...(cookiesHttp || [])];
                const result = {};
                
                combined.forEach(c => {
                    const lowName = (c.name || '').toLowerCase();
                    if (lowName === 'sessionid' || lowName === 'session_id' || lowName === 'jsessionid') {
                        result['sessionid'] = c.value;
                    }
                    if (lowName === 'csrftoken' || lowName === 'csrf_token' || lowName === 'xsrf-token') {
                        result['csrftoken'] = c.value;
                    }
                });

                if (result.sessionid) {
                    console.log('[VNPT Sync PMS] Tìm thấy cookie qua URL:', result.sessionid.substring(0, 8) + '...');
                    return resolve(result);
                }

                // 2. Quét dự phòng theo domain 'pms.vnpt.vn'
                chrome.cookies.getAll({ domain: 'pms.vnpt.vn' }, (cookiesByDomain) => {
                    (cookiesByDomain || []).forEach(c => {
                        const lowName = (c.name || '').toLowerCase();
                        if (lowName === 'sessionid' || lowName === 'session_id') {
                            result['sessionid'] = c.value;
                        }
                        if (lowName === 'csrftoken') {
                            result['csrftoken'] = c.value;
                        }
                    });

                    if (result.sessionid) {
                        console.log('[VNPT Sync PMS] Tìm thấy cookie qua domain pms.vnpt.vn:', result.sessionid.substring(0, 8) + '...');
                        return resolve(result);
                    }

                    // 3. Quét dự phòng theo domain cha 'vnpt.vn'
                    chrome.cookies.getAll({ domain: 'vnpt.vn' }, (cookiesByVnpt) => {
                        (cookiesByVnpt || []).forEach(c => {
                            const lowName = (c.name || '').toLowerCase();
                            if (lowName === 'sessionid') {
                                result['sessionid'] = c.value;
                            }
                            if (lowName === 'csrftoken') {
                                result['csrftoken'] = c.value;
                            }
                        });
                        console.log('[VNPT Sync PMS] Kết quả quét domain vnpt.vn:', result);
                        resolve(result);
                    });
                });
            });
        });
    });
}

async function syncPmsCookiesFromBackground(sendResponse) {
    try {
        const cookieObj = await getPmsCookies();
        if (!cookieObj || !cookieObj.sessionid) {
            if (sendResponse) sendResponse({ success: false, error: 'Chưa đăng nhập PMS hoặc không tìm thấy sessionid' });
            return;
        }

        let syncedCount = 0;
        for (const server of KPI_SERVERS) {
            try {
                const res = await fetch(`${server}/api/pms/set-token`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(cookieObj)
                });
                if (res.ok) syncedCount++;
            } catch (e) {}
        }
        if (sendResponse) sendResponse({ success: syncedCount > 0, sessionid: cookieObj.sessionid });
    } catch (e) {
        if (sendResponse) sendResponse({ success: false, error: e.message });
    }
}

// Lắng nghe thay đổi cookie trên các domain quan trọng
if (chrome.cookies && chrome.cookies.onChanged) {
    chrome.cookies.onChanged.addListener((changeInfo) => {
        if (changeInfo && changeInfo.cookie) {
            const domain = changeInfo.cookie.domain || '';
            const name = changeInfo.cookie.name || '';
            if (domain.includes('pms.vnpt.vn') || name === 'sessionid' || name === 'csrftoken') {
                syncPmsCookiesFromBackground();
            }
            if (domain.includes('gqknccos.vnpt.vn')) {
                syncCcosCookiesFromBackground();
            }
            if (domain.includes('10.159.21.241') || name === 'JSESSIONID') {
                syncBtoolsCookiesFromBackground();
            }
            if (domain.includes('vnptmedia.vn') || name.toLowerCase() === 'apikey') {
                syncCemAuthFromBackground();
            }
            if (domain.includes('10.155.42.218') || name.includes('ApplicationCookie')) {
                syncSapcCookiesFromBackground();
            }
        }
    });
}

// Tự động quét và đồng bộ khi người dùng mở hoặc chuyển đến tab PMS / BTools / CEM
if (chrome.tabs && chrome.tabs.onUpdated) {
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
        if (tab && tab.url && changeInfo.status === 'complete') {
            if (tab.url.includes('pms.vnpt.vn')) syncPmsCookiesFromBackground();
            if (tab.url.includes('10.159.21.241')) syncBtoolsCookiesFromBackground();
            if (tab.url.includes('cem.vnptmedia.vn')) syncCemAuthFromBackground();
            if (tab.url.includes('gqknccos.vnpt.vn')) syncCcosCookiesFromBackground();
            if (tab.url.includes('10.155.42.218')) syncSapcCookiesFromBackground();
        }
    });
}

if (chrome.tabs && chrome.tabs.onActivated) {
    chrome.tabs.onActivated.addListener((activeInfo) => {
        chrome.tabs.get(activeInfo.tabId, (tab) => {
            if (tab && tab.url) {
                if (tab.url.includes('pms.vnpt.vn')) syncPmsCookiesFromBackground();
                if (tab.url.includes('10.159.21.241')) syncBtoolsCookiesFromBackground();
                if (tab.url.includes('cem.vnptmedia.vn')) syncCemAuthFromBackground();
                if (tab.url.includes('gqknccos.vnpt.vn')) syncCcosCookiesFromBackground();
                if (tab.url.includes('10.155.42.218')) syncSapcCookiesFromBackground();
            }
        });
    });
}

// Tự động chạy ngay khi service worker khởi động
syncPmsCookiesFromBackground();
syncCcosCookiesFromBackground();
syncBtoolsCookiesFromBackground();
syncCemAuthFromBackground();
syncSapcCookiesFromBackground();

// Lắng nghe message từ content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message && message.action === 'sync_post') {
        const { url, body } = message;
        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {})
        })
        .then(async (res) => {
            const data = await res.json().catch(() => ({}));
            sendResponse({ success: res.ok, status: res.status, data: data });
        })
        .catch(() => {
            sendResponse({ success: false, error: 'Cannot connect to target server' });
        });
        return true;
    }

    if (message && message.action === 'sync_ccos_now') {
        syncCcosCookiesFromBackground();
        sendResponse({ success: true });
        return true;
    }

    if (message && message.action === 'sync_btools_now') {
        syncBtoolsCookiesFromBackground();
        sendResponse({ success: true });
        return true;
    }

    if (message && message.action === 'sync_cem_now') {
        syncCemAuthFromBackground();
        sendResponse({ success: true });
        return true;
    }

    if (message && message.action === 'sync_pms_now') {
        syncPmsCookiesFromBackground((res) => {
            sendResponse(res);
        });
        return true;
    }

    if (message && message.action === 'sync_sapc_now') {
        syncSapcCookiesFromBackground();
        sendResponse({ success: true });
        return true;
    }

    return false;
});
