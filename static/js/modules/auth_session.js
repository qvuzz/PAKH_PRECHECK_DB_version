// ==============================================================================
// MODULE QUẢN LÝ PHIÊN ĐĂNG NHẬP & XÁC THỰC KTV (AUTH SESSION)
// File: static/js/modules/auth_session.js
// Nghiệp vụ: Tự động gắn token Authorization, Modal đăng nhập TTS Cũ/Mới,
//            Xác thực OTP, Quản lý phiên đa người dùng, Đăng xuất, Lưu session
// ==============================================================================

// ==================== TỰ ĐỘNG GẮN TOKEN TTS MỚI VÀO TẤT CẢ REQUEST /api/ ====================
(function() {
    const _originalFetch = window.fetch;
    window.fetch = function(url, options = {}) {
        try {
            const tok = localStorage.getItem('ttsnew_auth_token') || localStorage.getItem('tts_auth_token');
            if (tok && typeof url === 'string' && url.startsWith('/api/')) {
                options = options || {};
                options.headers = options.headers || {};
                const authVal = tok.startsWith('Bearer ') ? tok : `Bearer ${tok}`;
                if (options.headers instanceof Headers) {
                    if (!options.headers.has('Authorization')) options.headers.set('Authorization', authVal);
                } else if (Array.isArray(options.headers)) {
                    if (!options.headers.some(h => h[0].toLowerCase() === 'authorization')) {
                        options.headers.push(['Authorization', authVal]);
                    }
                } else {
                    if (!options.headers['Authorization'] && !options.headers['authorization']) {
                        options.headers['Authorization'] = authVal;
                    }
                }
            }
        } catch (e) {}
        return _originalFetch.call(this, url, options);
    };
})();

// =====================================================================
// QUẢN LÝ PHIÊN ĐĂNG NHẬP TTS & PHÂN QUYỀN (MULTI-USER SESSION)
// =====================================================================
let currentAuthUser = null;
// isSystemAdmin được xác định đồng bộ ngay đầu file dashboard.js

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
    try {
        fetch('/api/session/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: token.trim(), user: (typeof userInfo === 'object' ? userInfo : { TaiKhoan: userInfo, HoTen: userInfo }) })
        }).catch(() => { });
    } catch (e) { }
}

function clearTtsAuthSession() {
    localStorage.removeItem('tts_auth_token');
    localStorage.removeItem('tts_auth_user');
    localStorage.removeItem('ttsnew_auth_token');
    localStorage.removeItem('ttsnew_auth_user');
    localStorage.removeItem('pakh_is_admin');
    window.currentApiUserName = '';
    currentAuthUser = null;
    try {
        fetch('/api/logout', { method: 'POST' }).catch(() => { });
    } catch (e) { }
    applyUserSessionState();
    const welcomeModal = document.getElementById('welcomeTtsModal');
    if (welcomeModal) {
        welcomeModal.style.display = 'none';
    }
}

// ---------------------------------------------------------------------
// TTS MỚI (tts.vnptnet.vn) TOKEN & IDENTITY HELPERS
// ---------------------------------------------------------------------
function parseJwt(token) {
    try {
        if (!token) return null;
        const clean = token.replace(/^Bearer\s+/i, '').trim();
        const parts = clean.split('.');
        if (parts.length < 2) return null;
        const base64Url = parts[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function (c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        return null;
    }
}

function getTtsNewAuthToken() {
    try {
        let tok = localStorage.getItem('ttsnew_auth_token') || '';
        if (!tok) return '';
        tok = tok.trim();
        // Tự động kiểm tra thời hạn exp của Token JWT
        const parsed = parseJwt(tok);
        if (parsed && parsed.exp) {
            const nowSec = Math.floor(Date.now() / 1000);
            if (parsed.exp <= (nowSec + 10)) {
                console.warn("[TTS New Auth] Token trong localStorage đã hết hạn exp:", parsed.exp, "hiện tại:", nowSec);
                localStorage.removeItem('ttsnew_auth_token');
                localStorage.removeItem('ttsnew_auth_user');
                return '';
            }
        }
        if (tok && !tok.startsWith('Bearer ')) {
            tok = 'Bearer ' + tok;
        }
        return tok;
    } catch (e) {
        return '';
    }
}

function getTtsNewAuthUser() {
    try {
        const uRaw = localStorage.getItem('ttsnew_auth_user');
        if (uRaw) return JSON.parse(uRaw);
        const tok = localStorage.getItem('ttsnew_auth_token') || '';
        const parsed = parseJwt(tok);
        if (parsed) {
            const uInfo = parsed.userInfo || {};
            return {
                username: uInfo.userName || parsed.sub || 'KTV',
                displayName: uInfo.name || uInfo.userName || parsed.sub || 'KTV',
                userId: uInfo.userId || 0,
                email: uInfo.email || ''
            };
        }
        return null;
    } catch (e) {
        return null;
    }
}

function setTtsNewAuthToken(tok) {
    if (!tok) return;
    let clean = tok.trim();
    if (!clean.startsWith('Bearer ') && clean.includes('.')) {
        clean = 'Bearer ' + clean;
    }
    localStorage.setItem('ttsnew_auth_token', clean);
    const parsed = parseJwt(clean);
    let uObj = null;
    if (parsed) {
        const uInfo = parsed.userInfo || {};
        uObj = {
            username: uInfo.userName || parsed.sub || 'KTV',
            displayName: uInfo.name || uInfo.userName || parsed.sub || 'KTV',
            userId: uInfo.userId || 0,
            email: uInfo.email || ''
        };
        localStorage.setItem('ttsnew_auth_user', JSON.stringify(uObj));
    }
    try {
        fetch('/api/ttsnew/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: clean, user: uObj })
        }).catch(() => { });
    } catch (e) { }
}

function clearTtsNewAuthToken() {
    localStorage.removeItem('ttsnew_auth_token');
    localStorage.removeItem('ttsnew_auth_user');
    localStorage.removeItem('tts_auth_token');
    localStorage.removeItem('tts_auth_user');
    localStorage.removeItem('pakh_is_admin');
    window.currentApiUserName = '';
    currentAuthUser = null;
    try {
        fetch('/api/logout', { method: 'POST' }).catch(() => { });
    } catch (e) { }
}

function toggleWelcomeTtsPopup(event) {
    if (event) event.stopPropagation();
    const modal = document.getElementById('welcomeTtsModal');
    if (!modal) return;
    if (modal.style.display === 'block') {
        closeWelcomeTtsModal();
    } else {
        closeTtsNewModal();
        openWelcomeTtsModal();
    }
}

function openWelcomeTtsModal() {
    const m = document.getElementById('welcomeTtsModal');
    if (!m) return;
    m.style.display = 'block';

    let session = getTtsAuthSession();
    const connBox = document.getElementById('ttsOldConnectedBox');
    const s1 = document.getElementById('boxStep1Login');
    const s2 = document.getElementById('boxStep2Otp');

    if (session && session.token) {
        if (connBox) connBox.style.display = 'flex';
        if (s1) s1.style.display = 'none';
        if (s2) s2.style.display = 'none';
        const title = document.getElementById('ttsOldConnectedTitle');
        const sub = document.getElementById('ttsOldConnectedSub');
        const u = session.user || {};
        const uName = u.TaiKhoan || u.username || 'KTV';
        const dName = u.HoTen || u.displayName || uName;
        if (title) title.innerText = `Đã kết nối: ${uName}`;
        if (sub) sub.innerText = `KTV: ${dName}`;
    } else {
        if (connBox) connBox.style.display = 'none';
        backToStep1Login();
    }
}

function closeWelcomeTtsModal() {
    const m = document.getElementById('welcomeTtsModal');
    if (m) m.style.display = 'none';
}

function logoutTtsSession() {
    clearTtsAuthSession();
    applyUserSessionState();
    updateServicesStatus();
}

// Giữ lại alias để tương thích
function openConnectModal() {
    openTtsNewModal();
}
function closeConnectModal() {
    closeTtsNewModal();
}

function toggleSapcPopup(event) {
    if (event) event.stopPropagation();
    const modal = document.getElementById('modalSapcSync');
    if (!modal) return;
    if (modal.style.display === 'block') {
        closeSapcModal();
    } else {
        closeWelcomeTtsModal();
        closeTtsNewModal();
        modal.style.display = 'block';
        checkSapcPopupStatus();
    }
}

function closeSapcModal() {
    const m = document.getElementById('modalSapcSync');
    if (m) m.style.display = 'none';
}

async function checkSapcPopupStatus() {
    const box = document.getElementById('sapcStatusBox');
    if (!box) return;
    box.style.background = '#f1f5f9';
    box.style.color = '#334155';
    box.innerText = 'Đang kiểm tra kết nối SAPC...';
    try {
        const res = await fetch('/api/services/status');
        const data = await res.json();
        const svcs = (data && data.services) ? data.services : data;
        const isOk = !!(svcs && svcs.sapc);
        if (isOk) {
            box.style.background = '#dcfce7';
            box.style.color = '#166534';
            box.style.borderColor = '#86efac';
            box.innerText = 'Đã kết nối thành công tới hệ thống SAPC (10.155.42.218)';
        } else {
            box.style.background = '#fee2e2';
            box.style.color = '#991b1b';
            box.style.borderColor = '#fca5a5';
            box.innerText = 'Chưa kết nối hoặc phiên SAPC đã hết hạn. Hãy mở SAPC trên Chrome hoặc dán cookie bên dưới.';
        }
    } catch (e) {
        box.innerText = 'Lỗi kiểm tra: ' + e.message;
    }
}

async function saveSapcCookieManual() {
    const inp = document.getElementById('inputSapcCookie');
    const val = (inp ? inp.value : '').trim();
    if (!val) {
        alert('Vui lòng nhập hoặc dán chuỗi Cookie SAPC (.AspNet.ApplicationCookie)');
        return;
    }
    const box = document.getElementById('sapcStatusBox');
    if (box) {
        box.style.background = '#f1f5f9';
        box.style.color = '#334155';
        box.innerText = 'Đang lưu và xác thực cookie...';
    }
    try {
        const res = await fetch('/api/sapc/cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookie: val })
        });
        const d = await res.json();
        if (d && d.success) {
            if (inp) inp.value = '';
            checkSapcPopupStatus();
            updateServicesStatus();
            alert(d.message || 'Đã lưu Cookie SAPC!');
        } else {
            alert('Lỗi: ' + (d ? d.message : 'Không lưu được cookie'));
            checkSapcPopupStatus();
        }
    } catch (e) {
        alert('Lỗi gửi yêu cầu: ' + e.message);
    }
}


async function syncServerTokenQuick() {
    alert("Hệ thống yêu cầu mỗi KTV đăng nhập bằng tài khoản TTS Mới của chính mình (tts.vnptnet.vn) để đảm bảo ghi đúng danh tính KTV khi đóng/chuyển bước phiếu OneOSS.");
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
            body: JSON.stringify({ username, password, system: 'tts_old' })
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
            if (data.ttsnew_token) {
                setTtsNewAuthToken(data.ttsnew_token);
            }
            setTimeout(() => {
                const modal = document.getElementById('welcomeTtsModal');
                if (modal) modal.style.display = 'none';
                applyUserSessionState();
                updateServicesStatus();
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
            if (data.ttsnew_token) {
                setTtsNewAuthToken(data.ttsnew_token);
            }
            setTimeout(() => {
                const modal = document.getElementById('welcomeTtsModal');
                if (modal) modal.style.display = 'none';
                backToStep1Login();
                applyUserSessionState();
                updateServicesStatus();
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

function closeWelcomeTtsModal() {
    const m = document.getElementById('welcomeTtsModal');
    if (m) m.style.display = 'none';
}

function applyUserSessionState() {
    let session = null;
    const newTok = getTtsNewAuthToken();
    const newUsr = getTtsNewAuthUser();
    if (newTok) {
        session = {
            token: newTok,
            username: (newUsr ? (newUsr.username || newUsr.displayName) : '') || 'KTV',
            displayName: (newUsr ? (newUsr.displayName || newUsr.username) : '') || window.currentApiUserName || 'KTV',
            email: newUsr ? (newUsr.email || '') : '',
            userId: newUsr ? (newUsr.userId || 0) : 0,
            is_tts_new: true
        };
    } else {
        const oldSess = getTtsAuthSession();
        if (oldSess && oldSess.token) {
            const u = oldSess.user || {};
            session = {
                token: oldSess.token,
                username: u.TaiKhoan || u.username || 'KTV',
                displayName: u.HoTen || u.displayName || u.TaiKhoan || window.currentApiUserName || 'KTV',
                email: u.email || '',
                userId: u.userId || 0,
                is_tts_new: false
            };
        }
    }
    currentAuthUser = session;

    const unauthBtn = document.getElementById('unauthBtn');
    const authPill = document.getElementById('authPill');
    const authUserName = document.getElementById('authUserName');
    const authRoleTag = document.getElementById('authRoleTag');
    const welcomeModal = document.getElementById('welcomeTtsModal');

    // Không bao giờ khóa mờ màn hình (luôn xóa is-unauthenticated để KTV xem dữ liệu tự do)
    document.body.classList.remove('is-unauthenticated');

    // Kiểm tra tài khoản có phải là SuperAdmin (quangvu / quangvu@vnpt.vn / Lê Quang Vũ) hay không
    if (session) {
        const uName = (session.username || '').toLowerCase();
        const uEmail = (session.email || '').toLowerCase();
        const uDisp = (session.displayName || '').toLowerCase();
        if (uName === 'quangvu' || uEmail.includes('quangvu') || uDisp.includes('lê quang vũ') || uDisp.includes('quangvu')) {
            isSystemAdmin = true;
        }
    }
    if (checkIsUserAdmin()) {
        isSystemAdmin = true;
    }

    if (!session || !session.token) {
        if (unauthBtn) unauthBtn.style.display = 'inline-flex';
        if (authPill) authPill.style.display = 'none';
        if (welcomeModal) welcomeModal.style.display = 'none';
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
    }

    // Áp dụng vai trò (Admin vs KTV)
    const chkAuto = document.getElementById('chkAutoCloseUnified');
    const ctrlAuto = document.getElementById('ctrlAutoCloseUnified');
    if (isSystemAdmin) {
        document.body.classList.remove('role-operator');
        try { localStorage.setItem('pakh_is_admin', 'true'); } catch(e) {}
        isRegionLocked = false;
        urlRouteRegion = null;
        applyRegionUI(false);
        if (chkAuto) chkAuto.disabled = false;
        if (ctrlAuto) {
            ctrlAuto.style.opacity = '1';
            ctrlAuto.style.cursor = 'pointer';
            ctrlAuto.style.pointerEvents = 'auto';
            ctrlAuto.title = 'Tick chọn để tự động đóng phiếu khi đủ điều kiện';
        }
    } else {
        document.body.classList.add('role-operator');
        if (chkAuto) {
            chkAuto.checked = false;
            chkAuto.disabled = true;
        }
        if (ctrlAuto) {
            ctrlAuto.style.opacity = '0.45';
            ctrlAuto.style.cursor = 'not-allowed';
            ctrlAuto.style.pointerEvents = 'none';
            ctrlAuto.title = 'Chức năng Tự đóng đã bị vô hiệu hóa trên máy Client (chỉ Quét & Tiền kiểm)';
        }
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
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // 1b. Đọc tham số sync_ttsnew_token từ URL (từ Bookmarklet trên tts.vnptnet.vn)
    const syncTtsNewToken = urlParams.get('sync_ttsnew_token');
    if (syncTtsNewToken) {
        setTtsNewAuthToken(syncTtsNewToken);
        const u = getTtsNewAuthUser();
        alert('🎉 Đã đồng bộ thành công phiên đăng nhập TTS Mới' + (u ? `: ${u.displayName}` : '!'));
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // 2. Lấy thông tin server & kiểm tra vai trò admin
    let serverData = { is_local: false, has_server_token: false };
    const curClientTok = getTtsNewAuthToken() || (getTtsAuthSession() ? getTtsAuthSession().token : '');
    try {
        const res = await fetch('/api/current_user', {
            headers: curClientTok ? { 'Authorization': curClientTok } : {}
        });
        if (res.ok) {
            serverData = await res.json();
        }
    } catch (e) {
        console.warn("Lỗi kiểm tra current_user:", e);
    }

    // Đồng bộ thông tin KTV nếu client đã có token hợp lệ
    if (serverData.ttsnew_token && curClientTok) {
        if (serverData.ttsnew_user) {
            localStorage.setItem('ttsnew_auth_user', JSON.stringify({
                username: serverData.ttsnew_user.userName || serverData.ttsnew_user.username || 'KTV',
                displayName: serverData.ttsnew_user.displayName || serverData.ttsnew_user.name || 'KTV',
                email: serverData.ttsnew_user.email || '',
                userId: serverData.ttsnew_user.userId || 0
            }));
        }
    } else if (!curClientTok) {
        // Máy client mới truy cập: đảm bảo sạch session
        clearTtsNewAuthToken();
    }

    if (serverData && serverData.is_admin) {
        isSystemAdmin = true;
        try { localStorage.setItem('pakh_is_admin', 'true'); } catch(e) {}
    } else if (checkIsUserAdmin()) {
        isSystemAdmin = true;
    }
    applyUserSessionState();

    if (typeof updateTtsNewBookmarkletLink === 'function') {
        updateTtsNewBookmarkletLink();
    }
}

// KHỞI CHẠY HỆ THỐNG
initUserSession();
setInterval(fetchStatus, 4000);
setInterval(() => loadTickets(false), 12000);
fetchStatus();

// Kích hoạt đúng tab theo URL hiện tại trên thanh địa chỉ trình duyệt
handleSpaRoute(window.location.pathname);

// [MODULE]: Logic Live Log Dropdown đã được tách sang static/js/modules/live_log.js

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
    const wt = document.getElementById('wrapperTtsNew');
    if (wt && !wt.contains(e.target)) closeTtsNewModal();
    const wtOld = document.getElementById('wrapperTtsOld');
    if (wtOld && !wtOld.contains(e.target)) closeWelcomeTtsModal();
    const wccos = document.getElementById('wrapperCcos');
    if (wccos && !wccos.contains(e.target)) closeCcosModal();
});

