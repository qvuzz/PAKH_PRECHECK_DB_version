/**
 * VNPT Token Utilities - Background Service Worker
 * Tu dong thu thap, duy tri va dong bo hoa phien lam viec (Session, Cookie, Bearer Token)
 * cho he sinh thai cong cu noi bo VNPT:
 * - Port 710  : Tro Ly KPI AI (KPI Assistant)
 * - Port 9190 : Bao Cao Tu Dong (Report Tool)
 * - Port 1234 : Phan Anh Khach Hang (PAKH Precheck)
 */

let syncDebounceTimer = null;

async function getPrecheckServerUrls() {
    const list = ['http://localhost:1234', 'http://127.0.0.1:1234'];
    try {
        const stored = await chrome.storage.local.get(['precheck_server_url']);
        if (stored && stored.precheck_server_url) {
            const custom = stored.precheck_server_url.trim().replace(/\/$/, '');
            if (custom && !list.includes(custom)) {
                list.unshift(custom);
            }
        }
    } catch (e) {}
    return list;
}

// ==========================================
// 1. Module Thu Thap Cookie Tu Trinh Duyet
// ==========================================

async function getCookiesForDomain(domainKeyword) {
    try {
        const all = await chrome.cookies.getAll({});
        return all.filter(c => (c.domain || '').toLowerCase().includes(domainKeyword.toLowerCase()));
    } catch (err) {
        console.warn(`[VNPT Utilities] Khong the doc cookies cho ${domainKeyword}:`, err);
        return [];
    }
}

// 1.1 CTS (MBB QoS Tap Doan)
async function scrapeCtsCookies() {
    let aspNetCookie = '';
    const cookieMap = {};
    const parts = [];
    const cookies = await getCookiesForDomain('cts.vnpt.vn');
    for (const c of cookies) {
        cookieMap[c.name] = c.value;
        parts.push(`${c.name}=${c.value}`);
        if (c.name === '.AspNetCore.Cookies' || c.name.startsWith('.AspNetCore.Cookies')) {
            if (!aspNetCookie || c.name === '.AspNetCore.Cookies') {
                aspNetCookie = c.value;
            }
        }
    }
    if (!aspNetCookie) {
        const direct = await chrome.cookies.getAll({ url: 'https://cts.vnpt.vn' }).catch(() => []);
        for (const c of direct) {
            cookieMap[c.name] = c.value;
            parts.push(`${c.name}=${c.value}`);
            if (c.name === '.AspNetCore.Cookies' || c.name.startsWith('.AspNetCore.Cookies')) {
                if (!aspNetCookie || c.name === '.AspNetCore.Cookies') {
                    aspNetCookie = c.value;
                }
            }
        }
    }
    const cookieHeader = parts.join('; ');
    return {
        service: 'CTS',
        domain: 'cts.vnpt.vn',
        hasCookie: !!aspNetCookie || parts.length > 0,
        cookieValue: aspNetCookie,
        cookieHeader: cookieHeader,
        cookieMap: cookieMap,
        preview: aspNetCookie ? `${aspNetCookie.slice(0, 12)}...${aspNetCookie.slice(-8)}` : (parts.length > 0 ? `${parts.length} cookies` : 'No cookie')
    };
}

// 1.2 PMS (3G & 5G Vo Tuyen)
async function scrapePmsCookies() {
    let sessionid = '';
    let csrftoken = '';
    const cookies = await getCookiesForDomain('pms.vnpt.vn');
    for (const c of cookies) {
        if (c.name === 'sessionid') sessionid = c.value;
        if (c.name === 'csrftoken') csrftoken = c.value;
    }
    return {
        service: 'PMS',
        domain: 'pms.vnpt.vn',
        hasCookie: !!sessionid,
        sessionid: sessionid,
        csrftoken: csrftoken,
        cookieHeader: `sessionid=${sessionid}; csrftoken=${csrftoken};`,
        preview: sessionid ? `${sessionid.slice(0, 10)}...` : 'No cookie'
    };
}

// 1.3 CCOS (Khieu Nai Khach Hang)
async function scrapeCcosCookies() {
    let sessionDb = '';
    let sessionId = '';
    const cookies = await getCookiesForDomain('gqknccos.vnpt.vn');
    for (const c of cookies) {
        if (c.name.toLowerCase() === 'sessiondb') sessionDb = c.value;
        if (c.name.toUpperCase() === 'SESSIONID') sessionId = c.value;
    }
    const hasCookie = !!(sessionDb || sessionId);
    return {
        service: 'CCOS',
        domain: 'gqknccos.vnpt.vn',
        hasCookie: hasCookie,
        sessionDb: sessionDb,
        sessionId: sessionId,
        cookieHeader: `SessionDB=${sessionDb}; SESSIONID=${sessionId}`,
        preview: sessionDb ? `${sessionDb.slice(0, 12)}...` : (sessionId ? `${sessionId.slice(0, 12)}...` : 'No session')
    };
}

// 1.4 BTools (Phan Tich Thue Bao)
async function scrapeBtoolsCookies() {
    let jsessionId = '';
    const cookieSources = [];
    try {
        const domCookies = await getCookiesForDomain('10.159.21.241');
        if (domCookies && domCookies.length > 0) cookieSources.push(...domCookies);
    } catch (e) {}
    try {
        const c1 = await chrome.cookies.getAll({ url: 'http://10.159.21.241:9267/B_tools_v2/' }).catch(() => []);
        if (c1) cookieSources.push(...c1);
    } catch (e) {}
    try {
        const c2 = await chrome.cookies.getAll({ url: 'http://10.159.21.241:9267/' }).catch(() => []);
        if (c2) cookieSources.push(...c2);
    } catch (e) {}
    try {
        const c3 = await chrome.cookies.getAll({ domain: '10.159.21.241' }).catch(() => []);
        if (c3) cookieSources.push(...c3);
    } catch (e) {}

    for (const c of cookieSources) {
        if ((c.name || '').toUpperCase() === 'JSESSIONID' && c.value) {
            jsessionId = c.value;
            break;
        }
    }

    // Fallback doc tu tab
    if (!jsessionId) {
        try {
            const tabs = await chrome.tabs.query({});
            const btab = tabs.find(t => t.url && t.url.includes('10.159.21.241'));
            if (btab && btab.id) {
                const res = await chrome.scripting.executeScript({
                    target: { tabId: btab.id },
                    func: () => document.cookie
                });
                if (res && res[0] && res[0].result) {
                    const match = res[0].result.match(/JSESSIONID=([^;]+)/i);
                    if (match) jsessionId = match[1].trim();
                }
            }
        } catch (e) {}
    }

    return {
        service: 'BTools',
        domain: '10.159.21.241',
        hasCookie: !!jsessionId,
        jsessionId: jsessionId,
        cookieHeader: jsessionId ? `JSESSIONID=${jsessionId}` : '',
        preview: jsessionId ? `${jsessionId.slice(0, 10)}...` : 'No cookie'
    };
}

// 1.5 CEM (Cell Site Management)
async function scrapeCem() {
    let apiKey = '';
    const cookieMap = {};
    const parts = [];
    try {
        const cMedia = await chrome.cookies.getAll({ domain: 'vnptmedia.vn' }).catch(() => []);
        const cCem = await chrome.cookies.getAll({ domain: 'cem.vnptmedia.vn' }).catch(() => []);
        const cUrl = await chrome.cookies.getAll({ url: 'https://cem.vnptmedia.vn/' }).catch(() => []);
        const cApi = await chrome.cookies.getAll({ url: 'https://api-cem.vnptmedia.vn/' }).catch(() => []);
        
        const allCem = [...(cMedia || []), ...(cCem || []), ...(cUrl || []), ...(cApi || [])];
        const seen = new Set();
        for (const c of allCem) {
            if (!seen.has(c.name)) {
                seen.add(c.name);
                cookieMap[c.name] = c.value;
                parts.push(`${c.name}=${c.value}`);
                const nLower = (c.name || '').toLowerCase();
                const val = (c.value || '').trim();
                if (nLower === 'apikey' || nLower === 'api_key' || val.startsWith('net_ktm_')) {
                    if (!apiKey && val) apiKey = decodeURIComponent(val);
                }
            }
        }
    } catch (e) {}

    if (!apiKey) {
        const storageKeys = ['API_KEY', 'apiKey', 'api_key', 'token', 'access_token', 'TOKEN'];
        const scraped = await readStorageFromMatchingTab('cem.vnptmedia.vn', storageKeys);
        if (scraped && scraped.token) {
            apiKey = decodeURIComponent(scraped.token);
            await chrome.storage.local.set({ live_cem_api_key: apiKey });
        }
    }

    if (!apiKey) {
        const cached = await chrome.storage.local.get(['live_cem_api_key']);
        if (cached.live_cem_api_key) apiKey = decodeURIComponent(cached.live_cem_api_key);
    }

    if (apiKey) {
        while (apiKey.includes('%25')) {
            try { apiKey = decodeURIComponent(apiKey); } catch (e) { break; }
        }
    }

    const cookieHeader = parts.join('; ');
    const hasKey = !!(apiKey || parts.length > 0);

    return {
        service: 'CEM',
        domain: 'cem.vnptmedia.vn',
        hasKey: hasKey,
        apiKey: apiKey,
        cookieHeader: cookieHeader,
        cookieMap: cookieMap,
        preview: apiKey ? `${apiKey.slice(0, 10)}...` : (parts.length > 0 ? `${parts.length} cookies` : 'No API key')
    };
}

// ==========================================
// 2. Module Thu Thap Token Tu Tab Mo San
// ==========================================


// 1.6 SAPC (10.155.42.218)
async function scrapeSapcCookies() {
    let appCookie = '';
    const cookieMap = {};
    const parts = [];
    try {
        let cookies = await getCookiesForDomain('10.155.42.218');
        if (!cookies || cookies.length === 0) {
            cookies = await chrome.cookies.getAll({ url: 'http://10.155.42.218/' }).catch(() => []);
        }
        for (const c of (cookies || [])) {
            cookieMap[c.name] = c.value;
            parts.push(`${c.name}=${c.value}`);
            if (c.name === '.AspNet.ApplicationCookie' || c.name.includes('ApplicationCookie')) {
                appCookie = c.value;
            }
        }
    } catch (e) {
        console.warn('[VNPT Utilities] Loi doc cookie SAPC:', e);
    }
    const cookieHeader = parts.join('; ');
    return {
        service: 'SAPC',
        domain: '10.155.42.218',
        hasCookie: !!appCookie || parts.length > 0,
        cookieValue: appCookie,
        cookieHeader: cookieHeader,
        cookieMap: cookieMap,
        preview: appCookie ? `${appCookie.slice(0, 10)}...${appCookie.slice(-6)}` : (parts.length > 0 ? `${parts.length} cookies` : 'No cookie')
    };
}

async function readStorageFromMatchingTab(urlKeyword, storageKeys) {
    try {
        const tabs = await chrome.tabs.query({});
        const targetTab = tabs.find(t => t.url && t.url.toLowerCase().includes(urlKeyword.toLowerCase()));
        if (!targetTab || !targetTab.id) return null;

        const results = await chrome.scripting.executeScript({
            target: { tabId: targetTab.id },
            func: (keys) => {
                let token = '';
                let username = '';
                for (const k of keys) {
                    const val = localStorage.getItem(k) || sessionStorage.getItem(k);
                    if (val) {
                        token = val;
                        break;
                    }
                }
                const rawUser = localStorage.getItem('USER_INFO') || localStorage.getItem('user_info');
                if (rawUser) {
                    try {
                        const parsed = JSON.parse(rawUser);
                        username = parsed.username || parsed.user_name || parsed.name || '';
                    } catch (e) {
                        username = rawUser;
                    }
                }
                return { token, username };
            },
            args: [storageKeys]
        }).catch(() => null);

        if (results && results[0] && results[0].result) {
            return results[0].result;
        }
    } catch (err) {
        console.warn(`[VNPT Utilities] Loi doc tab cho ${urlKeyword}:`, err);
    }
    return null;
}

// 2.1 OneOSS / NPMRAN 4G
async function scrapeOneossToken() {
    const keys = ['TOKEN', 'token', 'access_token', 'JWT_TOKEN'];
    let scraped = await readStorageFromMatchingTab('oneoss.vnpt.vn', keys);
    if (!scraped || !scraped.token) {
        scraped = await readStorageFromMatchingTab('npmran.vnpt.vn', keys);
    }
    if (scraped && scraped.token) {
        let clean = scraped.token.replace(/^Bearer\s+/i, '').replace(/^"|"$/g, '').trim();
        if (clean.startsWith('eyJ')) {
            await chrome.storage.local.set({ live_oneoss_token: clean, live_oneoss_user: scraped.username });
            return {
                service: 'OneOSS',
                domain: 'oneoss.vnpt.vn',
                valid: true,
                token: clean,
                user: scraped.username || 'OneOSS User',
                preview: `${clean.slice(0, 10)}...${clean.slice(-6)}`
            };
        }
    }

    const cached = await chrome.storage.local.get(['live_oneoss_token', 'live_oneoss_user']);
    if (cached.live_oneoss_token) {
        const clean = cached.live_oneoss_token;
        return {
            service: 'OneOSS',
            domain: 'oneoss.vnpt.vn',
            valid: true,
            token: clean,
            user: cached.live_oneoss_user || 'OneOSS User',
            preview: `${clean.slice(0, 10)}...${clean.slice(-6)}`
        };
    }

    return {
        service: 'OneOSS',
        domain: 'oneoss.vnpt.vn',
        valid: false,
        token: '',
        user: '',
        preview: 'No JWT token'
    };
}

// 2.2 TTS Moi (OneOSS PAKH)
async function scrapeTtsNewToken() {
    const scraped = await readStorageFromMatchingTab('tts.vnptnet.vn', ['token', 'TOKEN', 'access_token']);
    if (scraped && scraped.token) {
        let clean = scraped.token.replace(/^Bearer\s+/i, '').replace(/^"|"$/g, '').trim();
        if (clean.startsWith('eyJ')) {
            await chrome.storage.local.set({ live_tts_new_token: clean, live_tts_new_user: scraped.username });
            return {
                service: 'TTS Moi',
                domain: 'tts.vnptnet.vn',
                valid: true,
                token: clean,
                user: scraped.username || 'TTS User',
                preview: `${clean.slice(0, 10)}...${clean.slice(-6)}`
            };
        }
    }

    const cached = await chrome.storage.local.get(['live_tts_new_token', 'live_tts_new_user']);
    if (cached.live_tts_new_token) {
        const clean = cached.live_tts_new_token;
        return {
            service: 'TTS Moi',
            domain: 'tts.vnptnet.vn',
            valid: true,
            token: clean,
            user: cached.live_tts_new_user || 'TTS User',
            preview: `${clean.slice(0, 10)}...${clean.slice(-6)}`
        };
    }

    return {
        service: 'TTS Moi',
        domain: 'tts.vnptnet.vn',
        valid: false,
        token: '',
        user: '',
        preview: 'No JWT token'
    };
}

// 2.3 TTS Cu (34 TTP) - Thu thap scnntttoken tu LocalStorage, SessionStorage, URL & Cookies
async function scrapeTtsOldToken() {
    let token = '';
    let username = '';
    let xsrfToken = '';
    let cookieHeader = '';

    // 1. Quet Cookie cua domain tts.vnpt.vn
    try {
        const cookies = await getCookiesForDomain('tts.vnpt.vn');
        const parts = [];
        for (const c of cookies) {
            parts.push(`${c.name}=${c.value}`);
            if (c.name.toLowerCase() === 'xsrf-token' || c.name.toLowerCase() === '_xsrf') {
                xsrfToken = c.value;
            }
            if (c.name.toLowerCase() === 'scnntttoken' || c.name.toLowerCase() === 'token') {
                if (!token && c.value && c.value.length >= 20) {
                    token = c.value;
                }
            }
        }
        if (parts.length > 0) {
            cookieHeader = parts.join('; ');
        }
    } catch (e) {}

    // 2. Thuc thi Script truc tiep trong Tab tts.vnpt.vn dang mo (LocalStorage, SessionStorage, Hash URL, DOM)
    try {
        const tabs = await chrome.tabs.query({});
        const ttsTab = tabs.find(t => t.url && t.url.toLowerCase().includes('tts.vnpt.vn'));
        if (ttsTab && ttsTab.id) {
            const results = await chrome.scripting.executeScript({
                target: { tabId: ttsTab.id },
                func: () => {
                    let tok = '';
                    let usr = '';
                    let docXsrf = '';

                    // A. Tim trong LocalStorage / SessionStorage theo cac key thong dung
                    const priorityKeys = ['scnntttoken', 'token', 'access_token', 'TOKEN', 'scnntt_token', 'JWT_TOKEN'];
                    for (const k of priorityKeys) {
                        const v = localStorage.getItem(k) || sessionStorage.getItem(k);
                        if (v && v.length >= 20) {
                            tok = v;
                            break;
                        }
                    }

                    // B. Neu chua tim thay, quet toan bo cac key trong Storage co chua chu 'scnntt' hoac 'token'
                    if (!tok) {
                        for (let i = 0; i < localStorage.length; i++) {
                            const k = localStorage.key(i);
                            if (k && (k.toLowerCase().includes('scnntt') || k.toLowerCase().includes('token'))) {
                                const v = localStorage.getItem(k);
                                if (v && v.length >= 20) {
                                    tok = v;
                                    break;
                                }
                            }
                        }
                    }
                    if (!tok) {
                        for (let i = 0; i < sessionStorage.length; i++) {
                            const k = sessionStorage.key(i);
                            if (k && (k.toLowerCase().includes('scnntt') || k.toLowerCase().includes('token'))) {
                                const v = sessionStorage.getItem(k);
                                if (v && v.length >= 20) {
                                    tok = v;
                                    break;
                                }
                            }
                        }
                    }

                    // C. Quet URL search query hoac URL hash (#/...?...scnntttoken=...)
                    if (!tok) {
                        const fullHref = window.location.href;
                        const match = fullHref.match(/[?&#](scnntttoken|token|access_token)=([^&#]+)/i);
                        if (match && match[2]) {
                            tok = decodeURIComponent(match[2]);
                        }
                    }

                    // D. Trich xuat thong tin Nguoi Dung (Username)
                    const userKeys = ['USER_INFO', 'user_info', 'user', 'username', 'tai_khoan', 'taiKhoan'];
                    for (const uk of userKeys) {
                        const raw = localStorage.getItem(uk) || sessionStorage.getItem(uk);
                        if (raw) {
                            try {
                                const parsed = JSON.parse(raw);
                                usr = parsed.username || parsed.user_name || parsed.fullName || parsed.ten_dang_nhap || parsed.name || '';
                                if (usr) break;
                            } catch (e) {
                                if (typeof raw === 'string' && raw.length < 50 && !raw.includes('{')) {
                                    usr = raw;
                                    break;
                                }
                            }
                        }
                    }

                    // Tim ten user tren giao dien DOM neu chua thay trong Storage
                    if (!usr) {
                        const userEl = document.querySelector('.username, .user-name, .dropdown-user, .user-profile, a.dropdown-toggle span, [ng-bind*="user"]');
                        if (userEl && userEl.innerText) {
                            usr = userEl.innerText.trim();
                        }
                    }

                    // E. Tim XSRF cookie trong document.cookie
                    if (document.cookie) {
                        const m = document.cookie.match(/(?:^|;\s*)(?:XSRF-TOKEN|_xsrf)=([^;]+)/i);
                        if (m) docXsrf = decodeURIComponent(m[1]);
                    }

                    return {
                        token: tok,
                        username: usr,
                        xsrf: docXsrf,
                        cookie: document.cookie || ''
                    };
                }
            }).catch(() => null);

            if (results && results[0] && results[0].result) {
                const r = results[0].result;
                if (r.token && !token) token = r.token;
                if (r.username && !username) username = r.username;
                if (r.xsrf && !xsrfToken) xsrfToken = r.xsrf;
                if (r.cookie && !cookieHeader) cookieHeader = r.cookie;
            }
        }
    } catch (e) {}

    // 3. Fallback quet URL tu danh sach tabs Chrome API (khi tab vua duoc dieu huong)
    if (!token) {
        try {
            const tabs = await chrome.tabs.query({});
            for (const tab of tabs) {
                if (tab.url && tab.url.includes('tts.vnpt.vn')) {
                    const match = tab.url.match(/[?&#](scnntttoken|token|access_token)=([^&#]+)/i);
                    if (match && match[2]) {
                        token = decodeURIComponent(match[2]);
                        break;
                    }
                }
            }
        } catch (e) {}
    }

    // 4. Lam sach token va luu vao bo nho dem
    if (token) {
        let clean = token.replace(/^Bearer\s+/i, '').replace(/^"|"$/g, '').trim();
        if (clean.length >= 20) {
            await chrome.storage.local.set({
                live_tts_old_token: clean,
                live_tts_old_user: username,
                live_tts_old_cookies: cookieHeader,
                live_tts_old_xsrf: xsrfToken
            });
            return {
                service: 'TTS Cu',
                domain: 'tts.vnpt.vn',
                valid: true,
                token: clean,
                user: username || 'TTS Cu User',
                xsrf: xsrfToken,
                cookies: cookieHeader,
                preview: `${clean.slice(0, 10)}...${clean.slice(-6)}`
            };
        }
    }

    // 5. Fallback doc tu Cache da luu truoc do
    const cached = await chrome.storage.local.get([
        'live_tts_old_token',
        'live_tts_old_user',
        'live_tts_old_cookies',
        'live_tts_old_xsrf'
    ]);
    if (cached.live_tts_old_token) {
        const clean = cached.live_tts_old_token;
        return {
            service: 'TTS Cu',
            domain: 'tts.vnpt.vn',
            valid: true,
            token: clean,
            user: cached.live_tts_old_user || 'TTS Cu User',
            xsrf: cached.live_tts_old_xsrf || '',
            cookies: cached.live_tts_old_cookies || '',
            preview: `${clean.slice(0, 10)}...${clean.slice(-6)}`
        };
    }

    return {
        service: 'TTS Cu',
        domain: 'tts.vnpt.vn',
        valid: false,
        token: '',
        user: '',
        xsrf: '',
        cookies: cookieHeader || '',
        preview: 'No token'
    };
}

// ==========================================
// 3. Module Phan Phoi Token (Dispatcher)
// ==========================================

async function sendPostDual(urls, payload, timeoutMs = 10000) {
    for (const u of urls) {
        const res = await sendPost(u, payload, timeoutMs);
        if (res.ok) return res;
    }
    return { ok: false, error: 'Failed all endpoints' };
}

async function sendPost(url, payload, timeoutMs = 10000) {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: ctrl.signal
        });
        clearTimeout(tid);
        return { ok: res.ok, status: res.status };
    } catch (err) {
        clearTimeout(tid);
        return { ok: false, error: err.message };
    }
}

async function dispatchAll(bundle) {
    const status = {
        port710: { online: false, items: [] },
        port9190: { online: false, items: [] },
        port1234: { online: false, items: [] }
    };

    // 1. Phan phoi cho Port 710 - KPI Assistant
    try {
        let sentAny = false;
        if (bundle.cts.hasCookie) {
            const r = await sendPostDual(['http://localhost:710/api/cts/set-cookies', 'http://127.0.0.1:710/api/cts/set-cookies'], {
                cookie: bundle.cts.cookieHeader || bundle.cts.cookieValue,
                cookies: bundle.cts.cookieMap
            });
            if (r.ok) { sentAny = true; status.port710.items.push('CTS'); }
        }
        if (bundle.pms.hasCookie) {
            const r = await sendPostDual(['http://localhost:710/api/pms/set-token', 'http://127.0.0.1:710/api/pms/set-token'], {
                sessionid: bundle.pms.sessionid,
                csrftoken: bundle.pms.csrftoken
            });
            if (r.ok) { sentAny = true; status.port710.items.push('PMS'); }
        }
        const activeOneoss = bundle.oneoss.token || bundle.tts_new.token;
        if (activeOneoss && activeOneoss.startsWith('eyJ')) {
            const r = await sendPostDual(['http://localhost:710/api/oneoss/set-token', 'http://127.0.0.1:710/api/oneoss/set-token'], { token: activeOneoss });
            if (r.ok) { sentAny = true; status.port710.items.push('OneOSS'); }
        }
        if (sentAny) status.port710.online = true;
    } catch (e) {}

    // 2. Phan phoi cho Port 9190 - Report Tool
    try {
        const reportBody = {
            force_clear: false,
            ccos: bundle.ccos.hasCookie ? {
                cookie_raw: bundle.ccos.cookieHeader,
                cookies: bundle.ccos.cookieHeader,
                session_db: bundle.ccos.sessionDb,
                session_id: bundle.ccos.sessionId
            } : null,
            tts_old: bundle.tts_old.valid ? {
                token: bundle.tts_old.token,
                xsrf: bundle.tts_old.xsrf || '',
                cookies: bundle.tts_old.cookies || ''
            } : null,
            tts_new: bundle.tts_new.valid ? {
                token: bundle.tts_new.token,
                cookies: bundle.tts_new.cookies || ''
            } : null,
            pms: bundle.pms.hasCookie ? {
                sessionid: bundle.pms.sessionid,
                csrftoken: bundle.pms.csrftoken,
                cookie_raw: bundle.pms.cookieHeader,
                cookies: bundle.pms.cookieHeader
            } : null
        };
        const r = await sendPost('http://localhost:9190/api/auth/save', reportBody);
        if (r.ok) {
            status.port9190.online = true;
            status.port9190.items.push('CCOS', 'TTS', 'PMS');
        }
    } catch (e) {}

    // 3. Phan phoi cho Port 1234 - PAKH Precheck (Ho tro ca Server tu xa va Localhost)
    try {
        const pakhBody = {
            ccos_cookie: bundle.ccos.cookieHeader,
            tts_old_token: bundle.tts_old.token,
            tts_new_token: bundle.tts_new.token,
            btools_cookie: bundle.btools.cookieHeader,
            cem_api_key: bundle.cem ? bundle.cem.apiKey : '',
            cem_cookie: bundle.cem ? bundle.cem.cookieHeader : '',
            cem_cookies: bundle.cem ? bundle.cem.cookieMap : {},
            sapc_cookie: bundle.sapc ? (bundle.sapc.cookieHeader || bundle.sapc.cookieValue) : ''
        };

        const precheckServers = await getPrecheckServerUrls();
        const syncUrls = precheckServers.map(s => `${s}/api/sync-tokens`);
        const r = await sendPostDual(syncUrls, pakhBody);

        let sentItems = [];
        if (r.ok) {
            status.port1234.online = true;
            if (bundle.ccos.hasCookie) sentItems.push('CCOS');
            if (bundle.btools.hasCookie) sentItems.push('BTools');
            if (bundle.cem && bundle.cem.hasKey) sentItems.push('CEM');
            if (bundle.tts_old.valid || bundle.tts_new.valid) sentItems.push('TTS');
            if (bundle.sapc && bundle.sapc.hasCookie) sentItems.push('SAPC');
            status.port1234.items = sentItems;
        }

        // Fallback: Day song song toi cac router rieng tren Port 1234 cua ca Server va Localhost
        if (bundle.btools.hasCookie) {
            sendPostDual(precheckServers.map(s => `${s}/api/btools/cookie`), { cookie: bundle.btools.cookieHeader }).catch(() => {});
        }
        if (bundle.ccos.hasCookie) {
            sendPostDual(precheckServers.map(s => `${s}/api/ccos/update-cookie`), { cookie: bundle.ccos.cookieHeader }).catch(() => {});
        }
        if (bundle.sapc && bundle.sapc.hasCookie) {
            sendPostDual(precheckServers.map(s => `${s}/api/sapc/cookie`), {
                cookie: bundle.sapc.cookieHeader || bundle.sapc.cookieValue,
                cookies: bundle.sapc.cookieMap
            }).catch(() => {});
        }
        if (bundle.cem && bundle.cem.hasKey) {
            sendPostDual(precheckServers.map(s => `${s}/api/cem/auth`), {
                api_key: bundle.cem.apiKey,
                raw_cookie: bundle.cem.cookieHeader,
                cookies: bundle.cem.cookieMap
            }).catch(() => {});
        }
    } catch (e) {}

    return status;
}

// ==========================================
// 4. Giu Phien Lam Viec (Smart Keep-Alive Heartbeat)
// ==========================================

async function fetchKeepAlive(url, options = {}) {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), 4500);
    try {
        const defaultHeaders = {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/plain, */*'
        };
        const res = await fetch(url, {
            method: options.method || 'GET',
            headers: { ...defaultHeaders, ...(options.headers || {}) },
            credentials: 'include', // Bat buoc de browser tu dong truyen toan bo Cookie cua domain
            signal: ctrl.signal,
            cache: 'no-store'
        });
        clearTimeout(tid);
        return { ok: res.ok, status: res.status };
    } catch (e) {
        clearTimeout(tid);
        return { ok: false, error: e.message };
    }
}

async function keepAliveOpenTabs() {
    // Gui tin hieu nhe toi cac tab he thong dang mo (ngan Chrome freeze/discard tab & giup frontend tu refresh token)
    try {
        const tabs = await chrome.tabs.query({});
        const targetKeywords = [
            'oneoss.vnpt.vn', 'npmran.vnpt.vn',
            'tts.vnptnet.vn', 'tts.vnpt.vn',
            'pms.vnpt.vn', 'cts.vnpt.vn',
            'gqknccos.vnpt.vn', 'cem.vnptmedia.vn'
        ];
        for (const tab of tabs) {
            if (!tab.id || !tab.url) continue;
            const u = tab.url.toLowerCase();
            if (targetKeywords.some(kw => u.includes(kw))) {
                chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    func: () => {
                        window._vnptLastKeepAlive = Date.now();
                        try {
                            window.dispatchEvent(new Event('focus'));
                        } catch (e) {}
                    }
                }).catch(() => {});
            }
        }
    } catch (e) {}
}

async function pingKeepAlive() {
    // 1. Danh thuc cac tab he thong dang mo de ngan browser dong bang (sleep/discard)
    await keepAliveOpenTabs();

    // 2. Lay du lieu token/cookie trong bo nho dem de ping dung format
    const cached = await chrome.storage.local.get([
        'live_oneoss_token',
        'live_tts_new_token',
        'live_tts_old_token',
        'live_cem_api_key'
    ]);

    const pings = [];

    // 2.1 CTS (MBB QoS) - Endpoint danh muc sieu nhe GetListProvinceNew (ASP.NET Core SlidingExpiration)
    pings.push(
        fetchKeepAlive('https://cts.vnpt.vn/Report/MBBQoEReport/GetListProvinceNew')
            .catch(() => fetchKeepAlive('https://cts.vnpt.vn/Home/Index'))
    );

    // 2.2 PMS (3G & 5G) - Endpoint supplier list sieu nhe cua Django (Cap nhat sessionid idle timeout)
    pings.push(
        fetchKeepAlive('https://pms.vnpt.vn/kpi/supplier/list_3g_new?type=province')
            .catch(() => fetchKeepAlive('https://pms.vnpt.vn/'))
    );

    // 2.3 CCOS (Khieu nai khach hang) - Duy tri SessionDB & SESSIONID
    pings.push(
        fetchKeepAlive('http://gqknccos.vnpt.vn/')
    );

        // 2.3.5 SAPC (10.155.42.218)
    pings.push(
        fetchKeepAlive('http://10.155.42.218/').catch(() => {})
    );

    // 2.4 BTools (10.159.21.241) - Duy tri Tomcat JSESSIONID (Tranh het han 30 phut)
    pings.push(
        fetchKeepAlive('http://10.159.21.241:9267/B_tools_v2/')
    );

    // 2.5 CEM (Cell Site Management)
    const cemHeaders = {};
    if (cached.live_cem_api_key) {
        cemHeaders['Authorization'] = 'Bearer ' + cached.live_cem_api_key;
    }
    pings.push(
        fetchKeepAlive('https://cem.vnptmedia.vn/', { headers: cemHeaders })
    );

    // 2.6 OneOSS / NPMRAN 4G - Ping duy tri session SSO & backend gateway
    const oneossHeaders = {};
    if (cached.live_oneoss_token) {
        oneossHeaders['Authorization'] = 'Bearer ' + cached.live_oneoss_token;
    }
    pings.push(
        fetchKeepAlive('https://oneoss.vnpt.vn/', { headers: oneossHeaders })
    );
    pings.push(
        fetchKeepAlive('https://npmran.vnpt.vn/', { headers: oneossHeaders })
    );

    // 2.7 TTS Moi (OneOSS PAKH)
    const ttsNewHeaders = {};
    if (cached.live_tts_new_token) {
        ttsNewHeaders['Authorization'] = 'Bearer ' + cached.live_tts_new_token;
    }
    pings.push(
        fetchKeepAlive('https://tts.vnptnet.vn/', { headers: ttsNewHeaders })
    );

    // 2.8 TTS Cu (34 TTP)
    const ttsOldHeaders = {};
    if (cached.live_tts_old_token) {
        ttsOldHeaders['scnntttoken'] = cached.live_tts_old_token;
    }
    pings.push(
        fetchKeepAlive('https://tts.vnpt.vn/', { headers: ttsOldHeaders })
    );

    await Promise.allSettled(pings);

    // Ghi nhan thoi gian Heartbeat thanh cong vao storage
    const hbTime = new Date().toLocaleTimeString('en-US', { hour12: false });
    await chrome.storage.local.set({ last_heartbeat_time: hbTime });
    console.log(`[VNPT Utilities] Keep-alive heartbeat completed at ${hbTime} (Pings: ${pings.length})`);
}

// ==========================================
// 5. Dieu Phoi Chinh (Master Sync Engine)
// ==========================================

async function executeSync(clearOld = false) {
    if (clearOld) {
        await chrome.storage.local.clear();
    }

    const [cts, pms, ccos, btools, cem, oneoss, tts_new, tts_old, sapc] = await Promise.all([
        scrapeCtsCookies(),
        scrapePmsCookies(),
        scrapeCcosCookies(),
        scrapeBtoolsCookies(),
        scrapeCem(),
        scrapeOneossToken(),
        scrapeTtsNewToken(),
        scrapeTtsOldToken(),
        scrapeSapcCookies()
    ]);

    const bundle = {
        cts,
        pms,
        ccos,
        btools,
        cem,
        oneoss,
        tts_new,
        tts_old,
        sapc,
        timestamp: new Date().toLocaleTimeString('en-US', { hour12: false })
    };

    const dispatchStatus = await dispatchAll(bundle);
    bundle.dispatch = dispatchStatus;

    // Cap nhat Badge (Toan bo 7 dich vu)
    let count = 0;
    if (cts.hasCookie) count++;
    if (pms.hasCookie) count++;
    if (ccos.hasCookie) count++;
    if (btools.hasCookie) count++;
    if (cem && cem.hasKey) count++;
    if (oneoss.valid) count++;
    if (tts_new.valid) count++;
    if (tts_old.valid) count++;
    if (sapc && sapc.hasCookie) count++;

    let badgeText = '';
    let badgeColor = '#64748b';

    if (count >= 5) {
        badgeText = 'OK';
        badgeColor = '#10b981';
    } else if (count > 0) {
        badgeText = `${count}`;
        badgeColor = '#0284c7';
    } else {
        badgeText = '!';
        badgeColor = '#ef4444';
    }

    chrome.action.setBadgeText({ text: badgeText });
    chrome.action.setBadgeBackgroundColor({ color: badgeColor });

    await chrome.storage.local.set({
        vnpt_auth_bundle: bundle,
        last_sync_time: bundle.timestamp
    });

    console.log(`[VNPT Utilities] Sync completed at ${bundle.timestamp} (Ready: ${count}/9)`);
    return bundle;
}

function debouncedSync() {
    if (syncDebounceTimer) clearTimeout(syncDebounceTimer);
    syncDebounceTimer = setTimeout(() => {
        executeSync(false);
    }, 1500);
}

// ==========================================
// 6. Lang Nghe Su Kien
// ==========================================

chrome.cookies.onChanged.addListener((changeInfo) => {
    const domain = (changeInfo.cookie.domain || '').toLowerCase();
    if (domain.includes('vnpt.vn') || domain.includes('vnptnet.vn') || domain.includes('vnptmedia.vn') || domain.includes('10.159.21.241') || domain.includes('10.155.42.218')) {
        debouncedSync();
    }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    const rawUrl = changeInfo.url || tab.url || '';
    const targetUrl = rawUrl.toLowerCase();

    // Tu dong nhan dien May chu Precheck neu tab co port :1234 hoac tieu de TTS Precheck
    if (changeInfo.status === 'complete' || changeInfo.url) {
        if (rawUrl.includes(':1234') || (tab.title && tab.title.includes('TTS Precheck'))) {
            try {
                const u = new URL(rawUrl);
                const serverOrigin = u.origin;
                chrome.storage.local.get(['precheck_server_url'], (res) => {
                    if (res.precheck_server_url !== serverOrigin) {
                        chrome.storage.local.set({ precheck_server_url: serverOrigin }, () => {
                            console.log('[VNPT Utilities] Tu dong nhan dien server Precheck:', serverOrigin);
                            debouncedSync();
                        });
                    }
                });
            } catch (e) {}
        }
    }

    if (
        (changeInfo.status === 'complete' || changeInfo.url) &&
        (
            targetUrl.includes('cts.vnpt.vn') ||
            targetUrl.includes('pms.vnpt.vn') ||
            targetUrl.includes('oneoss.vnpt.vn') ||
            targetUrl.includes('tts.vnptnet.vn') ||
            targetUrl.includes('tts.vnpt.vn') ||
            targetUrl.includes('gqknccos.vnpt.vn') ||
            targetUrl.includes('cem.vnptmedia.vn') || targetUrl.includes('10.159.21.241') || targetUrl.includes('10.155.42.218') ||
            targetUrl.includes(':1234')
        )
    ) {
        debouncedSync();
    }
});

function ensureAlarm() {
    if (!chrome.alarms) return;
    chrome.alarms.get('vnpt_sync_alarm', (alarm) => {
        if (!alarm || alarm.periodInMinutes > 2) {
            chrome.alarms.create('vnpt_sync_alarm', { periodInMinutes: 2 });
            console.log('[VNPT Utilities] Registered persistent 2-min sync & keep-alive alarm.');
        }
    });
}

chrome.runtime.onInstalled.addListener(() => {
    executeSync(false);
    ensureAlarm();
});

chrome.runtime.onStartup.addListener(() => {
    executeSync(false);
    ensureAlarm();
});

// Watchdog: Dam bao alarm luon san sang moi khi service worker duoc danh thuc
ensureAlarm();

if (chrome.alarms) {
    chrome.alarms.onAlarm.addListener(async (alarm) => {
        if (alarm.name === 'vnpt_sync_alarm') {
            await pingKeepAlive();
            await executeSync(false);
        }
    });
}

// Lang nghe tin nhan tu Popup UI
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'sync_now' || request.action === 'FORCE_SYNC_ALL') {
        const afterUrl = (request.target_server)
            ? chrome.storage.local.set({ precheck_server_url: request.target_server })
            : Promise.resolve();
        afterUrl.then(() => pingKeepAlive())
            .then(() => executeSync(false))
            .then(res => {
                sendResponse(res || { success: true });
            });
        return true;
    }
    if (request.action === 'clear_and_sync') {
        executeSync(true).then(sendResponse);
        return true;
    }
    if (request.action === 'get_status') {
        chrome.storage.local.get(['vnpt_auth_bundle', 'last_sync_time', 'last_heartbeat_time']).then(data => {
            const b = data.vnpt_auth_bundle || {};
            b.last_heartbeat_time = data.last_heartbeat_time || '';
            sendResponse(b);
        });
        return true;
    }
    if (request.action === 'open_url') {
        if (request.url) chrome.tabs.create({ url: request.url });
        return true;
    }
    if (request.action === 'set_precheck_server') {
        if (request.url) {
            chrome.storage.local.set({ precheck_server_url: request.url }, () => {
                executeSync(false).then(sendResponse);
            });
            return true;
        }
    }
    if (request.action === 'get_precheck_server') {
        chrome.storage.local.get(['precheck_server_url']).then(data => {
            sendResponse({ url: data.precheck_server_url || 'http://localhost:1234' });
        });
        return true;
    }
});
