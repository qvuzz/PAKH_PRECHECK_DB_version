// static/js/modules/user_management.js
// Module quản trị phân vùng KTV & Flow Audit

// =========================================================================
// MODULE QUẢN TRỊ: QUẢN LÝ PHÂN VÙNG NHÂN VIÊN XỬ LÝ (TT SOC / ONEOSS)
// CHỈ DÀNH RIÊNG CHO QUẢN TRỊ VIÊN (SUPERADMIN)
// =========================================================================
let cachedAdminUsers = [];

function selectUserManagementModule(updateUrl = true) {
    isUserManagementView = true;
    isHistoryStatsView = false;

    if (updateUrl && window.location.pathname !== '/quan-tri-ktv') {
        history.pushState({ tab: 'quan-tri-ktv' }, '', '/quan-tri-ktv');
    }

    // 1. Highlight menu item
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById('nav-user-management');
    if (activeBtn) activeBtn.classList.add('active');

    // 2. Ẩn tất cả các view khác
    const mainTabs = document.getElementById('mainTabsHeader');
    if (mainTabs) mainTabs.style.display = 'none';

    const analyticsBox = document.getElementById('closedAnalyticsContainer');
    if (analyticsBox) analyticsBox.style.display = 'none';

    const tableDataView = document.getElementById('tableDataView');
    if (tableDataView) tableDataView.style.display = 'none';

    const flowAuditContainer = document.getElementById('flowAuditContainer');
    if (flowAuditContainer) flowAuditContainer.style.display = 'none';

    // 3. Hiển thị container Quản lý phân vùng KTV & Mô hình AI
    const container = document.getElementById('userManagementContainer');
    if (container) {
        container.style.display = 'block';
    }

    // 4. Đồng bộ giá trị mô hình AI
    const aiSel = document.getElementById('selectAiSummaryModel');
    if (aiSel && currentAiEngine) {
        aiSel.value = currentAiEngine;
    }

    // 5. Tải danh sách KTV từ máy chủ
    loadAdminUsers();
}
window.selectUserManagementModule = selectUserManagementModule;

async function loadAdminUsers() {
    const tbody = document.getElementById('userMgmtTableBody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:30px; color:#64748b;">Đang tải danh sách nhân viên phân vùng...</td></tr>';
    }

    try {
        const clientAuthTok = getTtsNewAuthToken() || (getTtsAuthSession() ? getTtsAuthSession().token : '');
        const reqHeaders = clientAuthTok ? { 'Authorization': clientAuthTok } : {};

        const res = await fetch('/api/admin/users', { headers: reqHeaders });
        const data = await res.json();
        if (data.success && Array.isArray(data.users)) {
            cachedAdminUsers = data.users;
            const badgeTotal = document.getElementById('badgeTotalUsers');
            if (badgeTotal) badgeTotal.innerText = cachedAdminUsers.length;
            const cntText = document.getElementById('userMgmtCount');
            if (cntText) cntText.innerText = cachedAdminUsers.length;
            if (data.is_admin) {
                isSystemAdmin = true;
                try { localStorage.setItem('pakh_is_admin', 'true'); } catch(e) {}
            }
            renderAdminUsersTable(cachedAdminUsers);
        } else {
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:30px; color:#dc2626;">Không thể lấy danh sách: ${data.detail || data.message || 'Lỗi không xác định'}</td></tr>`;
            }
        }
    } catch (err) {
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:30px; color:#dc2626;">Lỗi kết nối khi tải danh sách: ${err.message}</td></tr>`;
        }
    }
}
window.loadAdminUsers = loadAdminUsers;

function renderAdminUsersTable(users) {
    const tbody = document.getElementById('userMgmtTableBody');
    if (!tbody) return;

    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:36px; color:#64748b;">Không tìm thấy nhân viên nào phù hợp</td></tr>';
        return;
    }

    const socBadges = {
        'SOC1': { socLabel: 'SOC1', socStyle: 'background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd;', regLabel: 'Miền Bắc', regStyle: 'background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;' },
        'SOC2': { socLabel: 'SOC2', socStyle: 'background:#dcfce7; color:#15803d; border:1px solid #bbf7d0;', regLabel: 'Miền Nam', regStyle: 'background:#f0fdf4; color:#166534; border:1px solid #bbf7d0;' },
        'SOC3': { socLabel: 'SOC3', socStyle: 'background:#ffedd5; color:#c2410c; border:1px solid #fed7aa;', regLabel: 'Miền Trung', regStyle: 'background:#fdf4ff; color:#86198f; border:1px solid #f0abfc;' }
    };

    let html = '';
    users.forEach((u, idx) => {
        const socKey = (u.soc || 'SOC2').toUpperCase();
        const b = socBadges[socKey] || { socLabel: socKey, socStyle: 'background:#f1f5f9; color:#475569; border:1px solid #cbd5e1;', regLabel: u.region || '--', regStyle: 'background:#f8fafc; color:#334155; border:1px solid #e2e8f0;' };
        const uEscaped = escapeHtml(JSON.stringify(u)).replace(/'/g, '&#39;');
        const isAdminRole = (u.role === 'admin' || u.username === 'quangvu');
        const isSuperAdminUser = (u.username === 'quangvu');

        html += `
            <tr style="border-bottom:1px solid #e2e8f0; transition:background 0.15s ease;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
                <td style="padding:10px 12px; text-align:center; color:#64748b; font-weight:600;">${idx + 1}</td>
                <td style="padding:10px 12px;">
                    <span style="display:inline-block; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:800; ${b.socStyle}">
                        ${b.socLabel}
                    </span>
                </td>
                <td style="padding:10px 12px;">
                    <span style="display:inline-block; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:700; ${b.regStyle}">
                        ${b.regLabel}
                    </span>
                </td>
                <td style="padding:10px 14px; font-weight:700; color:#0f172a;">
                    ${escapeHtml(u.name || u.username || '--')}
                </td>
                <td style="padding:10px 14px; font-family:\'JetBrains Mono\', monospace; color:#005baa; font-weight:600;">
                    ${escapeHtml(u.username || '--')}
                </td>
                <td style="padding:10px 14px; color:#334155;">
                    ${escapeHtml(u.email || '--')}
                </td>
                <td style="padding:10px 12px; text-align:center;">
                    ${isAdminRole ? `
                    <span style="background:#fef3c7; color:#b45309; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px; border:1px solid #fde68a; display:inline-block;" title="Có quyền khai báo & quản lý user">
                        Quản Trị Viên (Admin)
                    </span>
                    ` : `
                    <span style="background:#f1f5f9; color:#475569; font-size:11px; font-weight:600; padding:3px 8px; border-radius:4px; border:1px solid #cbd5e1; display:inline-block;">
                        Kỹ Thuật Viên (KTV)
                    </span>
                    `}
                </td>
                <td style="padding:10px 12px; text-align:center;">
                    <span style="background:#f0fdf4; color:#16a34a; font-size:11px; font-weight:700; padding:3px 8px; border-radius:4px; border:1px solid #bbf7d0; display:inline-block;">
                        Được phép
                    </span>
                </td>
                <td style="padding:10px 14px; text-align:center;">
                    <div style="display:inline-flex; align-items:center; gap:6px;">
                        <button type="button" class="btn btn-sm" onclick="openUserModal(JSON.parse(this.dataset.user))" data-user="${uEscaped}"
                            style="padding:3px 8px; font-size:11px; font-weight:700; color:#0284c7; background:#f0f9ff; border:1px solid #bae6fd; border-radius:4px; cursor:pointer;"
                            title="Chỉnh sửa thông tin và quyền hạn">
                            Sửa
                        </button>
                        ${!isSuperAdminUser ? `
                        <button type="button" class="btn btn-sm" onclick="deleteAdminUser('${escapeHtml(u.username)}', '${escapeHtml(u.name || u.username)}')"
                            style="padding:3px 8px; font-size:11px; font-weight:700; color:#dc2626; background:#fef2f2; border:1px solid #fecaca; border-radius:4px; cursor:pointer;"
                            title="Xóa nhân viên khỏi danh sách cho phép">
                            Xóa
                        </button>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}
window.renderAdminUsersTable = renderAdminUsersTable;

function filterAdminUsersTable() {
    const q = (document.getElementById('searchUserMgmtInput')?.value || '').toLowerCase().trim();
    const socFilter = document.getElementById('filterSocSelect')?.value || 'ALL';

    const filtered = cachedAdminUsers.filter(u => {
        const matchSoc = (socFilter === 'ALL') || (u.soc && u.soc.toUpperCase() === socFilter);
        const matchText = !q || 
            (u.name && u.name.toLowerCase().includes(q)) ||
            (u.username && u.username.toLowerCase().includes(q)) ||
            (u.email && u.email.toLowerCase().includes(q));
        return matchSoc && matchText;
    });

    const cntText = document.getElementById('userMgmtCount');
    if (cntText) cntText.innerText = filtered.length;

    renderAdminUsersTable(filtered);
}
window.filterAdminUsersTable = filterAdminUsersTable;

function openUserModal(userObj = null) {
    const modal = document.getElementById('modalUserMgmt');
    const title = document.getElementById('modalUserMgmtTitle');
    const msg = document.getElementById('modalUserMgmtMsg');
    if (msg) msg.style.display = 'none';

    if (userObj) {
        if (title) title.innerText = 'CHỈNH SỬA THÔNG TIN NHÂN VIÊN';
        document.getElementById('inputUserSoc').value = userObj.soc || 'SOC2';
        document.getElementById('inputUserName').value = userObj.name || '';
        document.getElementById('inputUserUsername').value = userObj.username || '';
        document.getElementById('inputUserEmail').value = userObj.email || '';
        const roleSel = document.getElementById('inputUserRole');
        if (roleSel) roleSel.value = userObj.role || (userObj.username === 'quangvu' ? 'admin' : 'ktv');
        document.getElementById('inputUserOriginalKey').value = userObj.username || '';
        document.getElementById('inputUserUsername').disabled = true;
    } else {
        if (title) title.innerText = 'THÊM NHÂN VIÊN MỚI';
        document.getElementById('inputUserSoc').value = 'SOC2';
        document.getElementById('inputUserName').value = '';
        document.getElementById('inputUserUsername').value = '';
        document.getElementById('inputUserEmail').value = '';
        const roleSel = document.getElementById('inputUserRole');
        if (roleSel) roleSel.value = 'ktv';
        document.getElementById('inputUserOriginalKey').value = '';
        document.getElementById('inputUserUsername').disabled = false;
    }

    if (modal) modal.style.display = 'flex';
}
window.openUserModal = openUserModal;

function closeUserModal() {
    const modal = document.getElementById('modalUserMgmt');
    if (modal) modal.style.display = 'none';
}
window.closeUserModal = closeUserModal;

async function handleUserModalSubmit(e) {
    if (e && e.preventDefault) e.preventDefault();

    const soc = document.getElementById('inputUserSoc')?.value || 'SOC2';
    const name = document.getElementById('inputUserName')?.value.trim() || '';
    const username = document.getElementById('inputUserUsername')?.value.trim() || '';
    const email = document.getElementById('inputUserEmail')?.value.trim() || '';
    const role = document.getElementById('inputUserRole')?.value || 'ktv';
    const msgEl = document.getElementById('modalUserMgmtMsg');
    const btnSubmit = document.getElementById('btnSubmitUserModal');

    if (!username) {
        alert('Vui lòng nhập tên đăng nhập (username)');
        return;
    }

    if (btnSubmit) {
        btnSubmit.disabled = true;
        btnSubmit.innerText = 'Đang lưu...';
    }

    try {
        const clientAuthTok = getTtsNewAuthToken() || (getTtsAuthSession() ? getTtsAuthSession().token : '');
        const res = await fetch('/api/admin/users', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': clientAuthTok ? (clientAuthTok.startsWith('Bearer ') ? clientAuthTok : `Bearer ${clientAuthTok}`) : ''
            },
            body: JSON.stringify({
                soc: soc,
                name: name,
                username: username,
                email: email,
                role: role
            })
        });

        const data = await res.json();
        if (data.success) {
            closeUserModal();
            alert(data.message || 'Đã lưu thông tin nhân viên thành công!');
            await loadAdminUsers();
        } else {
            if (msgEl) {
                msgEl.style.display = 'block';
                msgEl.style.background = '#fef2f2';
                msgEl.style.color = '#dc2626';
                msgEl.style.border = '1px solid #fecaca';
                msgEl.innerText = data.message || data.detail || 'Lưu thất bại';
            } else {
                alert(data.message || 'Lưu thất bại');
            }
        }
    } catch (err) {
        alert('Lỗi kết nối khi lưu nhân viên: ' + err.message);
    } finally {
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.innerText = 'Lưu Thông Tin';
        }
    }
}
window.handleUserModalSubmit = handleUserModalSubmit;

async function deleteAdminUser(username, name) {
    if (!username) return;
    if (username.toLowerCase() === 'quangvu') {
        alert('Không thể xóa tài khoản Quản trị viên hệ thống!');
        return;
    }

    const confirmMsg = `XÁC NHẬN XÓA NHÂN VIÊN:\n\n` +
        `• Họ và tên: ${name || username}\n` +
        `• Tên đăng nhập: ${username}\n\n` +
        `Sau khi xóa, tài khoản này sẽ KHÔNG THỂ đăng nhập hoặc truy cập WebApp nữa.\n` +
        `Bạn có chắc chắn muốn xóa nhân viên này khỏi hệ thống?`;

    if (!confirm(confirmMsg)) return;

    try {
        const clientAuthTok = getTtsNewAuthToken() || (getTtsAuthSession() ? getTtsAuthSession().token : '');
        const res = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, {
            method: 'DELETE',
            headers: {
                'Authorization': clientAuthTok ? (clientAuthTok.startsWith('Bearer ') ? clientAuthTok : `Bearer ${clientAuthTok}`) : ''
            }
        });

        const data = await res.json();
        if (data.success) {
            alert(data.message || `Đã xóa thành công nhân viên [${name}]!`);
            await loadAdminUsers();
        } else {
            alert('Lỗi khi xóa: ' + (data.message || data.detail || 'Thất bại'));
        }
    } catch (err) {
        alert('Lỗi kết nối khi xóa nhân viên: ' + err.message);
    }
}
window.deleteAdminUser = deleteAdminUser;

// Tự động cập nhật số lượng nhân viên phân vùng và đồng bộ quyền Quản trị viên khi mở trang
setTimeout(() => {
    try {
        fetch('/api/admin/users')
            .then(r => r.json())
            .then(data => {
                if (data && data.success && Array.isArray(data.users)) {
                    cachedAdminUsers = data.users;
                    const b1 = document.getElementById('badgeTotalUsers');
                    if (b1) b1.innerText = data.users.length;
                    const cnt = document.getElementById('userMgmtCount');
                    if (cnt) cnt.innerText = data.users.length;
                    if (data.is_admin) {
                        isSystemAdmin = true;
                        try { localStorage.setItem('pakh_is_admin', 'true'); } catch(e) {}
                    }
                }
            })
            .catch(() => {});
    } catch(e) {}
}, 500);



