// ==============================================================================
// MODULE QUẢN LÝ POPUP & KẾT NỐI DỊCH VỤ NGOẠI VI (MODAL POPUPS)
// File: static/js/modules/modal_popups.js
// Nghiệp vụ: Trạng thái dịch vụ (TTS Cũ/Mới, SAPC, CCOS, BTools, CEM),
//            Modal kết nối & OTP SAPC, CCOS GQKN, TTS Mới, BTools, CEM API Key
// ==============================================================================

async function updateServicesStatus() {
    const dotTtsOld = document.getElementById('dotTtsOld');
    const dotTtsNew = document.getElementById('dotTtsNew');
    const dotBtools = document.getElementById('dotBtools');
    const dotCem = document.getElementById('dotCem');
    const dotSapc = document.getElementById('dotSapc');

    try {
        const clientTtsNewTok = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';
        const oldSess = (typeof getTtsAuthSession === 'function') ? getTtsAuthSession() : null;

        const params = new URLSearchParams();
        if (clientTtsNewTok) params.set('tts_new_token', clientTtsNewTok);

        const url = '/api/services/status' + (params.toString() ? '?' + params.toString() : '');
        const res = await fetch(url);
        const data = await res.json();
        const svcs = (data && data.services) ? data.services : {};

        // 0. TTS Cũ: Xanh khi Client đã có session HOẶC Backend kết nối thành công
        const isTtsOldActive = !!((oldSess && oldSess.token) || svcs.tts_old);
        if (dotTtsOld) {
            dotTtsOld.className = 'svc-status-dot ' + (isTtsOldActive ? 'active' : 'inactive');
            dotTtsOld.style.backgroundColor = isTtsOldActive ? '#16a34a' : '#ef4444';
        }
        const pillTtsOld = document.getElementById('svcBtnTtsOld');
        if (pillTtsOld) {
            if (isTtsOldActive) {
                const uName = (oldSess && oldSess.user && (oldSess.user.TaiKhoan || oldSess.user.username)) || 'KTV';
                pillTtsOld.title = `TTS (cũ): Đã kết nối [${uName}] - Click để xem thông tin`;
            } else {
                pillTtsOld.title = 'TTS (cũ): Chưa đăng nhập - Click để kết nối';
            }
        }

        // 1. TTS Mới: Xanh khi Client đã có token còn hạn HOẶC Backend kết nối thành công
        const isTtsNewActive = !!(clientTtsNewTok || svcs.tts_new);
        if (dotTtsNew) {
            dotTtsNew.className = 'svc-status-dot ' + (isTtsNewActive ? 'active' : 'inactive');
            dotTtsNew.style.backgroundColor = isTtsNewActive ? '#16a34a' : '#ef4444';
        }
        const pillTtsNew = document.getElementById('svcBtnTtsNew');
        if (pillTtsNew) {
            if (isTtsNewActive) {
                const u = getTtsNewAuthUser();
                const uName = (u && (u.username || u.displayName)) || 'KTV';
                pillTtsNew.title = `TTS (mới): Đã kết nối [${uName}] - Click để xem thông tin`;
            } else {
                pillTtsNew.title = 'TTS (mới): Chưa đăng nhập - Click để kết nối';
            }
        }

        // 3. BTools (Chỉ cần xanh và đỏ, khi rê chuột hiển thị trạng thái kết nối)
        const isBtoolsActive = !!svcs.btools;
        if (dotBtools) {
            dotBtools.className = 'svc-status-dot ' + (isBtoolsActive ? 'active' : 'inactive');
            dotBtools.style.backgroundColor = isBtoolsActive ? '#16a34a' : '#ef4444';
            const pillBtools = document.getElementById('svcBtnBtools');
            if (pillBtools) pillBtools.title = isBtoolsActive ? 'BTools: Connected (Click để mở trang 10.159.21.241)' : 'BTools: Disconnected (Chưa kết nối)';
        }

        // 4. CEM (Chỉ cần xanh và đỏ, khi rê chuột hiển thị trạng thái kết nối)
        const isCemActive = !!svcs.cem;
        if (dotCem) {
            dotCem.className = 'svc-status-dot ' + (isCemActive ? 'active' : 'inactive');
            dotCem.style.backgroundColor = isCemActive ? '#16a34a' : '#ef4444';
            const pillCem = document.getElementById('svcPillCem');
            if (pillCem) pillCem.title = isCemActive ? 'CEM: Connected (Click để mở trang cem.vnptmedia.vn)' : 'CEM: Disconnected (Chưa kết nối)';
        }

        // 5. SAPC (Chỉ cần xanh và đỏ, khi rê chuột hiển thị trạng thái kết nối)
        const isSapcActive = !!svcs.sapc;
        if (dotSapc) {
            dotSapc.className = 'svc-status-dot ' + (isSapcActive ? 'active' : 'inactive');
            dotSapc.style.backgroundColor = isSapcActive ? '#16a34a' : '#ef4444';
            const pillSapc = document.getElementById('svcPillSapc');
            if (pillSapc) pillSapc.title = isSapcActive ? 'SAPC: Connected (Click để quản lý phiên)' : 'SAPC: Disconnected (Click để đăng nhập)';
        }

        // 6. CCOS (Tự động reset và làm mới theo phiên truy cập)
        const dotCcos = document.getElementById('dotCcos');
        const pillCcos = document.getElementById('svcBtnCcos');
        let isCcosActive = false;
        try {
            const rCcos = await fetch('/api/ccos/status');
            const dCcos = await rCcos.json();
            isCcosActive = !!(dCcos && dCcos.connected);
        } catch (e) {}
        if (dotCcos) {
            dotCcos.className = 'svc-status-dot ' + (isCcosActive ? 'active' : 'inactive');
            dotCcos.style.backgroundColor = isCcosActive ? '#16a34a' : '#ef4444';
        }
        if (pillCcos) {
            pillCcos.title = isCcosActive ? 'CCOS: Connected (Click để quản lý phiên)' : 'CCOS: Disconnected (Click để đăng nhập)';
        }
    } catch (e) {
        console.warn('Lỗi kiểm tra trạng thái dịch vụ:', e);
    }
}

// ==========================================
// QUẢN LÝ POPUP & ĐĂNG NHẬP SAPC (10.155.42.218)
// ==========================================
function toggleSapcPopup(event) {
    if (event) event.stopPropagation();
    const m = document.getElementById('modalSapcSync');
    if (!m) return;
    if (m.style.display === 'block') {
        closeSapcModal();
    } else {
        closeTtsNewModal();
        closeBtoolsModal();
        closeCemModal();
        closeCcosModal();
        openSapcModal();
    }
}

async function openSapcModal() {
    const m = document.getElementById('modalSapcSync');
    if (!m) return;
    m.style.display = 'block';

    const boxLogged = document.getElementById('boxSapcLoggedInState');
    const boxStep1 = document.getElementById('boxStep1SapcLogin');
    const lblUser = document.getElementById('lblSapcUser');

    try {
        const res = await fetch('/api/sapc/status');
        const data = await res.json();
        const isConn = !!(data && data.connected);
        window._isSapcConnected = isConn;
        if (isConn) {
            if (boxLogged) boxLogged.style.display = 'flex';
            if (boxStep1) boxStep1.style.display = 'none';
            if (lblUser) lblUser.innerText = 'Cookie Core đang hoạt động';
        } else {
            if (boxLogged) boxLogged.style.display = 'none';
            if (boxStep1) boxStep1.style.display = 'block';
        }
    } catch (e) {
        if (boxLogged) boxLogged.style.display = 'none';
        if (boxStep1) boxStep1.style.display = 'block';
    }
}

function closeSapcModal() {
    const m = document.getElementById('modalSapcSync');
    if (m) m.style.display = 'none';
}

function toggleSapcManualSection() {
    const sec = document.getElementById('sectionSapcManual');
    if (sec) sec.style.display = (sec.style.display === 'none') ? 'block' : 'none';
}

async function handleDirectSapcLoginSubmit(event) {
    if (event) event.preventDefault();
    const uInp = document.getElementById('loginSapcUsername');
    const pInp = document.getElementById('loginSapcPassword');
    const btn = document.getElementById('btnDirectSapcLoginSubmit');
    const msg = document.getElementById('sapcLoginStatusMsg');

    const username = uInp ? uInp.value.trim() : '';
    const password = pInp ? pInp.value : '';

    if (!username || !password) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập tên truy nhập và mật khẩu!';
        }
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'ĐANG XỬ LÝ...'; }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang kết nối xác thực máy chủ Core SAPC (10.155.42.218)...';
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, system: 'sapc' })
        });
        const data = await res.json();

        if (data.success && data.token) {
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Đăng nhập SAPC thành công!';
            }
            window._isSapcConnected = true;
            setTimeout(() => {
                closeSapcModal();
                updateServicesStatus();
            }, 600);
        } else {
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Đăng nhập SAPC thất bại. Kiểm tra lại thông tin!';
            }
        }
    } catch (e) {
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'ĐĂNG NHẬP SAPC'; }
    }
}

async function logoutSapcSession() {
    try {
        await fetch('/api/sapc/logout', { method: 'POST' });
    } catch (e) {}
    window._isSapcConnected = false;
    closeSapcModal();
    updateServicesStatus();
}

async function handleDirectSapcCookieSubmit(event) {
    if (event) event.preventDefault();
    const inp = document.getElementById('sapcCookieInput');
    const msg = document.getElementById('sapcStatusMsg');
    const btn = document.getElementById('btnSaveSapcCookie');
    const cookieVal = inp ? inp.value.trim() : '';
    if (!cookieVal) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fee2e2';
            msg.style.color = '#991b1b';
            msg.innerText = 'Vui lòng nhập Cookie .AspNet.ApplicationCookie';
        }
        return;
    }
    if (btn) { btn.disabled = true; btn.innerText = 'Đang lưu...'; }
    try {
        const res = await fetch('/api/sapc/update-cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookie: cookieVal })
        });
        const data = await res.json();
        if (msg) {
            msg.style.display = 'block';
            if (data.success) {
                msg.style.background = '#dcfce7';
                msg.style.color = '#166534';
                msg.innerText = data.message || 'Đã lưu Cookie SAPC thành công!';
                if (inp) inp.value = '';
                window._isSapcConnected = true;
                setTimeout(() => { closeSapcModal(); updateServicesStatus(); }, 1200);
            } else {
                msg.style.background = '#fee2e2';
                msg.style.color = '#991b1b';
                msg.innerText = data.message || 'Lỗi khi lưu Cookie SAPC';
            }
        }
    } catch (err) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fee2e2';
            msg.style.color = '#991b1b';
            msg.innerText = 'Không thể kết nối máy chủ: ' + err.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'LƯU COOKIE THỦ CÔNG'; }
    }
}

// ==========================================
// QUẢN LÝ POPUP & ĐĂNG NHẬP CCOS (GQKN CCOS)
// ==========================================
let currentCcosOtpSessionId = null;

function toggleCcosPopup(event) {
    if (event) event.stopPropagation();
    const m = document.getElementById('modalCcosSync');
    if (!m) return;
    if (m.style.display === 'block') {
        closeCcosModal();
    } else {
        closeTtsNewModal();
        closeBtoolsModal();
        closeCemModal();
        closeSapcModal();
        openCcosModal();
    }
}

async function openCcosModal() {
    const m = document.getElementById('modalCcosSync');
    if (!m) return;
    m.style.display = 'block';

    const boxLogged = document.getElementById('boxCcosLoggedInState');
    const boxStep1 = document.getElementById('boxStep1CcosLogin');
    const boxStep2 = document.getElementById('boxStep2CcosOtp');
    const lblUser = document.getElementById('lblCcosUser');

    try {
        const res = await fetch('/api/ccos/status');
        const data = await res.json();
        const isConn = !!(data && data.connected);
        window._isCcosConnected = isConn;
        if (isConn) {
            if (boxLogged) boxLogged.style.display = 'flex';
            if (boxStep1) boxStep1.style.display = 'none';
            if (boxStep2) boxStep2.style.display = 'none';
            if (lblUser) lblUser.innerText = 'Phiên làm việc đang hoạt động';
        } else {
            if (boxLogged) boxLogged.style.display = 'none';
            if (boxStep1) boxStep1.style.display = 'block';
            if (boxStep2) boxStep2.style.display = 'none';
        }
    } catch (e) {
        if (boxLogged) boxLogged.style.display = 'none';
        if (boxStep1) boxStep1.style.display = 'block';
        if (boxStep2) boxStep2.style.display = 'none';
    }
}

function closeCcosModal() {
    const m = document.getElementById('modalCcosSync');
    if (m) m.style.display = 'none';
}

function toggleCcosManualSection() {
    const sec = document.getElementById('sectionCcosManual');
    if (sec) sec.style.display = (sec.style.display === 'none') ? 'block' : 'none';
}

function backToStep1CcosLogin() {
    const s1 = document.getElementById('boxStep1CcosLogin');
    const s2 = document.getElementById('boxStep2CcosOtp');
    if (s1) s1.style.display = 'block';
    if (s2) s2.style.display = 'none';
}

async function handleDirectCcosLoginSubmit(event) {
    if (event) event.preventDefault();
    const uInp = document.getElementById('loginCcosUsername');
    const pInp = document.getElementById('loginCcosPassword');
    const btn = document.getElementById('btnDirectCcosLoginSubmit');
    const msg = document.getElementById('ccosLoginStatusMsg');

    const username = uInp ? uInp.value.trim() : '';
    const password = pInp ? pInp.value : '';

    if (!username || !password) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập tên truy nhập và mật khẩu!';
        }
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'ĐANG XỬ LÝ...'; }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang kết nối xác thực CAS CCOS...';
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, system: 'ccos' })
        });
        const data = await res.json();

        if (data.success && data.token) {
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Đăng nhập CCOS thành công!';
            }
            window._isCcosConnected = true;
            setTimeout(() => {
                closeCcosModal();
                updateServicesStatus();
            }, 600);
        } else if (data.otp_required) {
            currentCcosOtpSessionId = data.session_id;
            const s1 = document.getElementById('boxStep1CcosLogin');
            const s2 = document.getElementById('boxStep2CcosOtp');
            if (s1) s1.style.display = 'none';
            if (s2) s2.style.display = 'block';
            const uLabel = document.getElementById('otpCcosUserLabel');
            if (uLabel) uLabel.innerText = data.username || username;
            const otpInp = document.getElementById('loginCcosOtp');
            if (otpInp) { otpInp.value = ''; otpInp.focus(); }
        } else {
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Đăng nhập CCOS thất bại. Kiểm tra lại thông tin!';
            }
        }
    } catch (e) {
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'ĐĂNG NHẬP CCOS'; }
    }
}

async function handleDirectCcosOtpSubmit(event) {
    if (event) event.preventDefault();
    const otpInp = document.getElementById('loginCcosOtp');
    const btn = document.getElementById('btnDirectCcosOtpSubmit');
    const msg = document.getElementById('ccosOtpStatusMsg');

    const otpVal = otpInp ? otpInp.value.trim() : '';
    if (!otpVal) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập mã OTP SMS!';
        }
        return;
    }

    if (!currentCcosOtpSessionId) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Phiên OTP đã hết hạn, vui lòng bấm quay lại để đăng nhập lại.';
        }
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'ĐANG XÁC THỰC...'; }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang gửi mã xác thực OTP lên hệ thống...';
    }

    try {
        const res = await fetch('/api/login/otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentCcosOtpSessionId, otp: otpVal })
        });
        const data = await res.json();

        if (data.success && data.token) {
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Xác thực OTP CCOS thành công!';
            }
            window._isCcosConnected = true;
            setTimeout(() => {
                closeCcosModal();
                updateServicesStatus();
            }, 600);
        } else {
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Mã OTP không đúng hoặc đã hết hạn!';
            }
        }
    } catch (e) {
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'XÁC NHẬN OTP'; }
    }
}

async function logoutCcosSession() {
    try {
        await fetch('/api/ccos/logout', { method: 'POST' });
    } catch (e) {}
    window._isCcosConnected = false;
    closeCcosModal();
    updateServicesStatus();
}

async function handleDirectCcosCookieSubmit(event) {
    if (event) event.preventDefault();
    const inp = document.getElementById('ccosCookieInput');
    const msg = document.getElementById('ccosStatusMsg');
    const btn = document.getElementById('btnSaveCcosCookie');
    const cookieVal = inp ? inp.value.trim() : '';
    if (!cookieVal) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fee2e2';
            msg.style.color = '#991b1b';
            msg.innerText = 'Vui lòng nhập Cookie CCOS (SessionDB / SESSIONID)';
        }
        return;
    }
    if (btn) { btn.disabled = true; btn.innerText = 'Đang lưu...'; }
    try {
        const res = await fetch('/api/ccos/update-cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookie: cookieVal })
        });
        const data = await res.json();
        if (msg) {
            msg.style.display = 'block';
            if (data.success) {
                msg.style.background = '#dcfce7';
                msg.style.color = '#166534';
                msg.innerText = data.message || 'Đã lưu Cookie CCOS thành công!';
                if (inp) inp.value = '';
                window._isCcosConnected = true;
                setTimeout(() => { closeCcosModal(); updateServicesStatus(); }, 1200);
            } else {
                msg.style.background = '#fee2e2';
                msg.style.color = '#991b1b';
                msg.innerText = data.message || 'Lỗi khi lưu Cookie CCOS';
            }
        }
    } catch (err) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fee2e2';
            msg.style.color = '#991b1b';
            msg.innerText = 'Không thể kết nối máy chủ: ' + err.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'LƯU COOKIE THỦ CÔNG'; }
    }
}

// ==========================================
// QUẢN LÝ POPUP & KẾT NỐI TTS MỚI
// ==========================================
function toggleTtsNewPopup(event) {
    if (event) event.stopPropagation();
    const m = document.getElementById('modalTtsNewSync');
    if (!m) return;
    if (m.style.display === 'block') {
        closeTtsNewModal();
    } else {
        openTtsNewModal();
    }
}

function openTtsWebLoginPage() {
    window.open('https://tts.vnptnet.vn', '_blank');
}

async function checkAndSyncTtsNewNow() {
    const msg = document.getElementById('loginTtsNewStatusMsg');
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang kiểm tra token từ phiên đăng nhập...';
    }
    try {
        const res = await fetch('/api/current_user');
        if (res.ok) {
            const data = await res.json();
            if (data.ttsnew_token) {
                setTtsNewAuthToken(data.ttsnew_token);
                if (data.ttsnew_user) {
                    localStorage.setItem('ttsnew_auth_user', JSON.stringify({
                        username: data.ttsnew_user.userName || data.ttsnew_user.username || 'KTV',
                        displayName: data.ttsnew_user.displayName || data.ttsnew_user.name || 'KTV',
                        email: data.ttsnew_user.email || '',
                        userId: data.ttsnew_user.userId || 0
                    }));
                }
                if (msg) {
                    msg.style.background = '#f0fdf4';
                    msg.style.color = '#15803d';
                    msg.innerText = 'Đã nhận token thành công!';
                }
                applyUserSessionState();
                updateServicesStatus();
                openTtsNewModal();
                return;
            }
        }
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Chưa nhận được token. Vui lòng đăng nhập trên trang tts.vnptnet.vn trước!';
        }
    } catch (e) {
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    }
}

async function openTtsNewModal() {
    const m = document.getElementById('modalTtsNewSync');
    if (!m) return;
    m.style.display = 'block';

    updateTtsNewBookmarkletLink();

    let tok = getTtsNewAuthToken();
    let user = getTtsNewAuthUser();

    const connBox = document.getElementById('ttsNewConnectedBox');
    const s1 = document.getElementById('boxStep1TtsNewLogin');
    const s2 = document.getElementById('boxStep2TtsNewOtp');

    if (tok) {
        if (connBox) connBox.style.display = 'flex';
        if (s1) s1.style.display = 'none';
        if (s2) s2.style.display = 'none';
        const title = document.getElementById('ttsNewConnectedTitle');
        const sub = document.getElementById('ttsNewConnectedSub');
        const uName = (user && (user.username || user.displayName)) || 'KTV';
        const dName = (user && user.displayName) || uName;
        if (title) title.innerText = `Đã kết nối tài khoản: ${uName}`;
        if (sub) sub.innerText = `KTV: ${dName} — Sẵn sàng tiền kiểm và ký duyệt phiếu OneOSS.`;
    } else {
        if (connBox) connBox.style.display = 'none';
        backToStep1TtsNewLogin();
    }
}

let currentTtsNewOtpSessionId = '';

function toggleTtsNewPasswordVisibility() {
    const pwd = document.getElementById('loginTtsNewPassword');
    if (pwd) pwd.type = (pwd.type === 'password') ? 'text' : 'password';
}

function backToStep1TtsNewLogin() {
    const s1 = document.getElementById('boxStep1TtsNewLogin');
    const s2 = document.getElementById('boxStep2TtsNewOtp');
    if (s1) s1.style.display = 'block';
    if (s2) s2.style.display = 'none';
    const btn = document.getElementById('btnDirectTtsNewLoginSubmit');
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<span>ĐĂNG NHẬP TTS MỚI</span>';
    }
    const msg = document.getElementById('loginTtsNewStatusMsg');
    if (msg) msg.style.display = 'none';
}

async function handleDirectTtsNewLoginSubmit(event) {
    if (event) event.preventDefault();
    const uInp = document.getElementById('loginTtsNewUsername');
    const pInp = document.getElementById('loginTtsNewPassword');
    const btn = document.getElementById('btnDirectTtsNewLoginSubmit');
    const msg = document.getElementById('loginTtsNewStatusMsg');

    const username = uInp ? uInp.value.trim() : '';
    const password = pInp ? pInp.value.trim() : '';
    if (!username || !password) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập tên đăng nhập và mật khẩu!';
        }
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerText = 'ĐANG XỬ LÝ...';
    }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang kết nối xác thực với VNPT CAS (TTS Mới)...';
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, system: 'tts_new' })
        });
        const data = await res.json();

        if (data.success && (data.ttsnew_token || data.token)) {
            const tok = data.ttsnew_token || data.token;
            setTtsNewAuthToken(tok);
            applyUserSessionState();
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Đăng nhập TTS Mới thành công!';
            }
            setTimeout(() => {
                closeTtsNewModal();
                updateServicesStatus();
                loadTickets(true);
            }, 600);
        } else if (data.otp_required) {
            currentTtsNewOtpSessionId = data.session_id;
            const s1 = document.getElementById('boxStep1TtsNewLogin');
            const s2 = document.getElementById('boxStep2TtsNewOtp');
            if (s1) s1.style.display = 'none';
            if (s2) s2.style.display = 'block';
            const uLabel = document.getElementById('otpTtsNewUserLabel');
            if (uLabel) uLabel.innerText = data.username || username;
            const otpInp = document.getElementById('loginTtsNewOtp');
            if (otpInp) { otpInp.value = ''; otpInp.focus(); }
        } else {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span>ĐĂNG NHẬP TTS MỚI</span>';
            }
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Đăng nhập thất bại. Kiểm tra lại thông tin!';
            }
        }
    } catch (e) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>ĐĂNG NHẬP TTS MỚI</span>';
        }
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    }
}

async function handleDirectTtsNewOtpSubmit(event) {
    if (event) event.preventDefault();
    const otpInp = document.getElementById('loginTtsNewOtp');
    const btn = document.getElementById('btnDirectTtsNewOtpSubmit');
    const msg = document.getElementById('loginTtsNewOtpStatusMsg');

    const otpVal = otpInp ? otpInp.value.trim() : '';
    if (!otpVal) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập mã OTP!';
        }
        return;
    }

    if (!currentTtsNewOtpSessionId) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Chưa có phiên đăng nhập TTS Mới hoặc container vừa khởi động lại. Vui lòng bấm "Quay lại nhập tài khoản" để thực hiện Bước 1 trước!';
        }
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerText = 'ĐANG XÁC THỰC OTP...';
    }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang xác thực OTP với CAS, vui lòng chờ...';
    }

    try {
        const res = await fetch('/api/login/otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentTtsNewOtpSessionId, otp: otpVal })
        });
        const data = await res.json();

        if (data.success && (data.ttsnew_token || data.token)) {
            const tok = data.ttsnew_token || data.token;
            setTtsNewAuthToken(tok);
            applyUserSessionState();
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Xác thực OTP thành công! Đã kết nối TTS Mới.';
            }
            setTimeout(() => {
                closeTtsNewModal();
                backToStep1TtsNewLogin();
                updateServicesStatus();
                loadTickets(true);
            }, 600);
        } else {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span>XÁC NHẬN OTP</span>';
            }
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Mã OTP không chính xác hoặc đã hết hạn!';
            }
        }
    } catch (e) {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>XÁC NHẬN OTP</span>';
        }
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    }
}

function updateTtsNewBookmarkletLink() {
    const a = document.getElementById('ttsNewBookmarkletBtn');
    if (!a) return;
    const currentOrigin = window.location.origin + window.location.pathname;
    const bmCode = "javascript:(function(){try{var t=localStorage.getItem('TOKEN')||sessionStorage.getItem('TOKEN')||'';if(!t){for(var i=0;i<localStorage.length;i++){var v=localStorage.getItem(localStorage.key(i));if(v&&v.indexOf('eyJ')===0&&v.split('.').length===3){t=v;break;}}}if(!t){alert('Chưa tìm thấy token TTS Mới trên trang này! Vui lòng đăng nhập tts.vnptnet.vn trước.');return;}window.location.href='" + currentOrigin + "?sync_ttsnew_token='+encodeURIComponent(t);}catch(e){alert('Lỗi: '+e);}})();";
    a.setAttribute('href', bmCode);
}

async function saveManualTtsNewToken() {
    const inp = document.getElementById('txtManualTtsNewToken');
    const msg = document.getElementById('loginTtsNewStatusMsg');
    let raw = (inp ? inp.value : '').trim();
    if (!raw) {
        alert('Vui lòng dán chuỗi Token JWT (bắt đầu bằng eyJ...)');
        return;
    }
    const match = raw.match(/eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+/);
    if (!match) {
        alert('Không tìm thấy Token JWT hợp lệ (chuỗi token phải có định dạng header.payload.signature bắt đầu bằng eyJ...)');
        return;
    }
    const tok = match[0];
    const parsed = parseJwt(tok);
    if (!parsed) {
        alert('Token không đúng cấu trúc JWT hoặc bị lỗi!');
        return;
    }
    setTtsNewAuthToken(tok);
    const u = getTtsNewAuthUser();
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0fdf4';
        msg.style.color = '#15803d';
        msg.innerText = 'Đã kết nối thành công KTV: ' + (u ? (u.displayName || u.username) : 'KTV');
    }
    if (inp) inp.value = '';
    applyUserSessionState();
    updateServicesStatus();
    loadTickets(true);
    openTtsNewModal();
}

function closeTtsNewModal() {
    const m = document.getElementById('modalTtsNewSync');
    if (m) m.style.display = 'none';
}

function logoutTtsNewSession() {
    clearTtsNewAuthToken();
    clearTtsAuthSession();
    openTtsNewModal();
    updateServicesStatus();
    loadTickets(true);
}

function closeAllSyncModals() {
    closeTtsNewModal();
    closeBtoolsModal();
    closeCemModal();
}

let currentBtoolsOtpSessionId = null;
let currentCemOtpSessionId = null;

function toggleBtoolsManualSection() {
    const s = document.getElementById('sectionBtoolsManual');
    if (s) s.style.display = (s.style.display === 'none' || !s.style.display) ? 'block' : 'none';
}

function backToStep1BtoolsLogin() {
    const s1 = document.getElementById('boxStep1BtoolsLogin');
    const s2 = document.getElementById('boxStep2BtoolsOtp');
    if (s1) s1.style.display = 'block';
    if (s2) s2.style.display = 'none';
    const msg = document.getElementById('btoolsOtpStatusMsg');
    if (msg) msg.style.display = 'none';
}

function toggleBtoolsPopup(event) {
    if (event) event.stopPropagation();
    const m = document.getElementById('modalBtoolsSync');
    if (!m) return;
    const isShowing = m.style.display === 'block';
    closeAllSyncModals();
    if (!isShowing) {
        m.style.display = 'block';
        const isConn = !!window._isBtoolsConnected;
        const loggedBox = document.getElementById('boxBtoolsLoggedInState');
        const s1 = document.getElementById('boxStep1BtoolsLogin');
        const s2 = document.getElementById('boxStep2BtoolsOtp');
        if (isConn) {
            if (loggedBox) loggedBox.style.display = 'flex';
            if (s1) s1.style.display = 'none';
            if (s2) s2.style.display = 'none';
        } else {
            if (loggedBox) loggedBox.style.display = 'none';
            if (s1) s1.style.display = 'block';
            if (s2) s2.style.display = 'none';
            const inp = document.getElementById('loginBtoolsUsername');
            if (inp) inp.focus();
        }
    }
}

function closeBtoolsModal() {
    const m = document.getElementById('modalBtoolsSync');
    if (m) m.style.display = 'none';
}

async function handleDirectBtoolsLoginSubmit(event) {
    if (event) event.preventDefault();
    const uInp = document.getElementById('loginBtoolsUsername');
    const pInp = document.getElementById('loginBtoolsPassword');
    const btn = document.getElementById('btnDirectBtoolsLoginSubmit');
    const msg = document.getElementById('btoolsLoginStatusMsg');

    const username = uInp ? uInp.value.trim() : '';
    const password = pInp ? pInp.value : '';

    if (!username || !password) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập tên truy nhập và mật khẩu!';
        }
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'ĐANG XỬ LÝ...'; }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang kết nối xác thực CAS BTools (10.159.21.241)...';
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, system: 'btools' })
        });
        const data = await res.json();

        if (data.success && data.token) {
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Đăng nhập BTools thành công!';
            }
            window._isBtoolsConnected = true;
            setTimeout(() => {
                closeBtoolsModal();
                updateServicesStatus();
            }, 600);
        } else if (data.otp_required) {
            currentBtoolsOtpSessionId = data.session_id;
            const s1 = document.getElementById('boxStep1BtoolsLogin');
            const s2 = document.getElementById('boxStep2BtoolsOtp');
            if (s1) s1.style.display = 'none';
            if (s2) s2.style.display = 'block';
            const uLabel = document.getElementById('otpBtoolsUserLabel');
            if (uLabel) uLabel.innerText = data.username || username;
            const otpInp = document.getElementById('loginBtoolsOtp');
            if (otpInp) { otpInp.value = ''; otpInp.focus(); }
        } else {
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Đăng nhập BTools thất bại. Kiểm tra lại thông tin!';
            }
        }
    } catch (e) {
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'ĐĂNG NHẬP BTOOLS'; }
    }
}

async function handleDirectBtoolsOtpSubmit(event) {
    if (event) event.preventDefault();
    const otpInp = document.getElementById('loginBtoolsOtp');
    const btn = document.getElementById('btnDirectBtoolsOtpSubmit');
    const msg = document.getElementById('btoolsOtpStatusMsg');

    const otpVal = otpInp ? otpInp.value.trim() : '';
    if (!otpVal) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập mã OTP!';
        }
        return;
    }

    if (!currentBtoolsOtpSessionId) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Chưa có phiên đăng nhập BTools hoặc container vừa khởi động lại. Vui lòng quay lại Bước 1 bấm ĐĂNG NHẬP lại!';
        }
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'ĐANG XÁC THỰC OTP...'; }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang xác thực OTP với CAS BTools, vui lòng chờ...';
    }

    try {
        const res = await fetch('/api/login/otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentBtoolsOtpSessionId, otp: otpVal })
        });
        const data = await res.json();

        if (data.success && data.token) {
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Xác thực OTP BTools thành công!';
            }
            window._isBtoolsConnected = true;
            setTimeout(() => {
                closeBtoolsModal();
                updateServicesStatus();
            }, 600);
        } else {
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Mã OTP không đúng hoặc đã hết hạn!';
            }
        }
    } catch (e) {
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'XÁC NHẬN OTP'; }
    }
}

async function logoutBtoolsSession() {
    try {
        await fetch('/api/btools/cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookie: '' })
        });
    } catch (e) {}
    window._isBtoolsConnected = false;
    closeBtoolsModal();
    updateServicesStatus();
}

async function handleDirectBtoolsCookieSubmit(event) {
    if (event) event.preventDefault();
    const inp = document.getElementById('btoolsCookieInput');
    const msg = document.getElementById('btoolsStatusMsg');
    const btn = document.getElementById('btnSaveBtoolsCookie');
    const cookieVal = inp ? inp.value.trim() : '';
    if (!cookieVal) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fee2e2';
            msg.style.color = '#991b1b';
            msg.innerText = 'Vui lòng nhập JSESSIONID hoặc Cookie BTools';
        }
        return;
    }
    if (btn) { btn.disabled = true; btn.innerText = 'Đang lưu...'; }
    try {
        const res = await fetch('/api/btools/cookie', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cookie: cookieVal })
        });
        const data = await res.json();
        if (msg) {
            msg.style.display = 'block';
            if (data.success) {
                msg.style.background = '#dcfce7';
                msg.style.color = '#166534';
                msg.innerText = data.message || 'Đã lưu Cookie BTools thành công!';
                if (inp) inp.value = '';
                window._isBtoolsConnected = true;
                setTimeout(() => { closeBtoolsModal(); updateServicesStatus(); }, 1200);
            } else {
                msg.style.background = '#fee2e2';
                msg.style.color = '#991b1b';
                msg.innerText = data.message || 'Lỗi khi lưu Cookie BTools';
            }
        }
    } catch (err) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fee2e2';
            msg.style.color = '#991b1b';
            msg.innerText = 'Không thể kết nối máy chủ: ' + err.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'LƯU COOKIE THỦ CÔNG'; }
    }
}

function toggleCemManualSection() {
    const s = document.getElementById('sectionCemManual');
    if (s) s.style.display = (s.style.display === 'none' || !s.style.display) ? 'block' : 'none';
}

function backToStep1CemLogin() {
    const s1 = document.getElementById('boxStep1CemLogin');
    const s2 = document.getElementById('boxStep2CemOtp');
    if (s1) s1.style.display = 'block';
    if (s2) s2.style.display = 'none';
    const msg = document.getElementById('cemOtpStatusMsg');
    if (msg) msg.style.display = 'none';
}

function toggleCemPopup(event) {
    if (event) event.stopPropagation();
    const m = document.getElementById('modalCemSync');
    if (!m) return;
    const isShowing = m.style.display === 'block';
    closeAllSyncModals();
    if (!isShowing) {
        m.style.display = 'block';
        const isConn = !!window._isCemConnected;
        const loggedBox = document.getElementById('boxCemLoggedInState');
        const s1 = document.getElementById('boxStep1CemLogin');
        const s2 = document.getElementById('boxStep2CemOtp');
        if (isConn) {
            if (loggedBox) loggedBox.style.display = 'flex';
            if (s1) s1.style.display = 'none';
            if (s2) s2.style.display = 'none';
        } else {
            if (loggedBox) loggedBox.style.display = 'none';
            if (s1) s1.style.display = 'block';
            if (s2) s2.style.display = 'none';
            const inp = document.getElementById('loginCemUsername');
            if (inp) inp.focus();
        }
    }
}

function closeCemModal() {
    const m = document.getElementById('modalCemSync');
    if (m) m.style.display = 'none';
}

async function handleDirectCemLoginSubmit(event) {
    if (event) event.preventDefault();
    const uInp = document.getElementById('loginCemUsername');
    const pInp = document.getElementById('loginCemPassword');
    const btn = document.getElementById('btnDirectCemLoginSubmit');
    const msg = document.getElementById('cemLoginStatusMsg');

    const username = uInp ? uInp.value.trim() : '';
    const password = pInp ? pInp.value : '';

    if (!username || !password) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập tên truy nhập và mật khẩu!';
        }
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'ĐANG XỬ LÝ...'; }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang kết nối xác thực CAS CEM (VNPT Media)...';
    }

    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, system: 'cem' })
        });
        const data = await res.json();

        if (data.success && data.token) {
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Đăng nhập CEM thành công!';
            }
            window._isCemConnected = true;
            setTimeout(() => {
                closeCemModal();
                updateServicesStatus();
            }, 600);
        } else if (data.otp_required) {
            currentCemOtpSessionId = data.session_id;
            const s1 = document.getElementById('boxStep1CemLogin');
            const s2 = document.getElementById('boxStep2CemOtp');
            if (s1) s1.style.display = 'none';
            if (s2) s2.style.display = 'block';
            const uLabel = document.getElementById('otpCemUserLabel');
            if (uLabel) uLabel.innerText = data.username || username;
            const otpInp = document.getElementById('loginCemOtp');
            if (otpInp) { otpInp.value = ''; otpInp.focus(); }
        } else {
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Đăng nhập CEM thất bại. Kiểm tra lại thông tin!';
            }
        }
    } catch (e) {
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'ĐĂNG NHẬP CEM'; }
    }
}

async function handleDirectCemOtpSubmit(event) {
    if (event) event.preventDefault();
    const otpInp = document.getElementById('loginCemOtp');
    const btn = document.getElementById('btnDirectCemOtpSubmit');
    const msg = document.getElementById('cemOtpStatusMsg');

    const otpVal = otpInp ? otpInp.value.trim() : '';
    if (!otpVal) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Vui lòng nhập mã OTP!';
        }
        return;
    }

    if (!currentCemOtpSessionId) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Chưa có phiên đăng nhập CEM hoặc container vừa khởi động lại. Vui lòng bấm "Quay lại nhập tài khoản" để thực hiện Bước 1 trước!';
        }
        return;
    }

    if (btn) { btn.disabled = true; btn.innerText = 'ĐANG XÁC THỰC OTP...'; }
    if (msg) {
        msg.style.display = 'block';
        msg.style.background = '#f0f9ff';
        msg.style.color = '#0284c7';
        msg.innerText = 'Đang xác thực OTP với CEM, vui lòng chờ...';
    }

    try {
        const res = await fetch('/api/login/otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentCemOtpSessionId, otp: otpVal })
        });
        const data = await res.json();

        if (data.success && data.token) {
            if (msg) {
                msg.style.background = '#f0fdf4';
                msg.style.color = '#15803d';
                msg.innerText = 'Xác thực OTP CEM thành công!';
            }
            window._isCemConnected = true;
            setTimeout(() => {
                closeCemModal();
                updateServicesStatus();
            }, 600);
        } else {
            if (msg) {
                msg.style.background = '#fef2f2';
                msg.style.color = '#dc2626';
                msg.innerText = data.error || 'Mã OTP không đúng hoặc đã hết hạn!';
            }
        }
    } catch (e) {
        if (msg) {
            msg.style.background = '#fef2f2';
            msg.style.color = '#dc2626';
            msg.innerText = 'Lỗi kết nối máy chủ: ' + e.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'XÁC NHẬN OTP'; }
    }
}

async function logoutCemSession() {
    try {
        await fetch('/api/cem/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: '', raw_cookie: '' })
        });
    } catch (e) {}
    window._isCemConnected = false;
    closeCemModal();
    updateServicesStatus();
}

async function handleDirectCemAuthSubmit(event) {
    if (event) event.preventDefault();
    const inp = document.getElementById('cemApiKeyInput');
    const msg = document.getElementById('cemStatusMsg');
    const btn = document.getElementById('btnSaveCemAuth');
    const keyVal = inp ? inp.value.trim() : '';
    if (!keyVal) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fee2e2';
            msg.style.color = '#991b1b';
            msg.innerText = 'Vui lòng nhập API Key hoặc Cookie CEM';
        }
        return;
    }
    if (btn) { btn.disabled = true; btn.innerText = 'Đang lưu...'; }
    try {
        const res = await fetch('/api/cem/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: keyVal, raw_cookie: keyVal })
        });
        const data = await res.json();
        if (msg) {
            msg.style.display = 'block';
            if (data.success) {
                msg.style.background = '#dcfce7';
                msg.style.color = '#166534';
                msg.innerText = data.message || 'Đã lưu API Key CEM thành công!';
                if (inp) inp.value = '';
                window._isCemConnected = true;
                setTimeout(() => { closeCemModal(); updateServicesStatus(); }, 1200);
            } else {
                msg.style.background = '#fee2e2';
                msg.style.color = '#991b1b';
                msg.innerText = data.message || 'Lỗi khi lưu API Key CEM';
            }
        }
    } catch (err) {
        if (msg) {
            msg.style.display = 'block';
            msg.style.background = '#fee2e2';
            msg.style.color = '#991b1b';
            msg.innerText = 'Không thể kết nối máy chủ: ' + err.message;
        }
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = 'LƯU API KEY THỦ CÔNG'; }
    }
}

// Tự động kiểm tra trạng thái các dịch vụ (TTS Cũ, TTS Mới, BTools, CEM, SAPC)
setTimeout(updateServicesStatus, 500);
setInterval(updateServicesStatus, 25000);

// Đóng popup khi click ra ngoài
document.addEventListener('click', function (e) {
    const wrapNew = document.getElementById('wrapperTtsNew');
    if (wrapNew && !wrapNew.contains(e.target)) closeTtsNewModal();
    const wrapBtools = document.getElementById('wrapperBtools');
    if (wrapBtools && !wrapBtools.contains(e.target)) closeBtoolsModal();
    const wrapCem = document.getElementById('wrapperCem');
    if (wrapCem && !wrapCem.contains(e.target)) closeCemModal();
    const wrapSapc = document.getElementById('wrapperSapc');
    if (wrapSapc && !wrapSapc.contains(e.target)) closeSapcModal();
    const wrapCcos = document.getElementById('wrapperCcos');
    if (wrapCcos && !wrapCcos.contains(e.target)) closeCcosModal();
});

