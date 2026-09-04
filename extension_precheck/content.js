// VNPT TTS Precheck Helper - Content Script
// Chạy trên https://tts.vnpt.vn/* để tự động phát hiện phiên đăng nhập và tạo nút mở Precheck

(function () {
    let checkInterval = setInterval(initPrecheckBadge, 2000);

    function initPrecheckBadge() {
        try {
            const token = localStorage.getItem('scnntttoken');
            if (!token) return;

            let userInfo = {};
            try {
                userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
            } catch (e) {}

            const displayName = userInfo.HoTen || userInfo.TaiKhoan || 'Kỹ thuật viên';

            // Tự động đồng bộ phiên về máy chủ Precheck trong nền
            const serverUrls = ['http://10.155.139.167:1234', 'http://localhost:1234'];
            serverUrls.forEach(url => {
                fetch(`${url}/api/session/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: token, user: userInfo })
                }).catch(() => {});
            });

            if (document.getElementById('precheck-sync-btn')) return;

            // Tạo nút nổi trên giao diện TTS
            const btn = document.createElement('button');
            btn.id = 'precheck-sync-btn';
            btn.innerHTML = `
                <span style="font-size:16px;">⚡</span>
                <span>Vào Precheck (<strong>${displayName}</strong>)</span>
            `;
            btn.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 999999;
                background: linear-gradient(135deg, #005baa 0%, #0284c7 100%);
                color: #ffffff;
                border: 2px solid #38bdf8;
                border-radius: 30px;
                padding: 10px 18px;
                font-size: 13.5px;
                font-weight: 700;
                cursor: pointer;
                box-shadow: 0 10px 25px rgba(0, 91, 170, 0.4), 0 4px 6px rgba(0, 0, 0, 0.1);
                display: flex;
                align-items: center;
                gap: 8px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                transition: transform 0.2s, box-shadow 0.2s;
            `;

            btn.onmouseenter = () => {
                btn.style.transform = 'translateY(-2px) scale(1.03)';
                btn.style.boxShadow = '0 14px 28px rgba(0, 91, 170, 0.5)';
            };
            btn.onmouseleave = () => {
                btn.style.transform = 'translateY(0) scale(1)';
                btn.style.boxShadow = '0 10px 25px rgba(0, 91, 170, 0.4)';
            };

            btn.onclick = () => {
                let serverUrl = localStorage.getItem('precheck_server_url') || 'http://localhost:1234';
                if (!localStorage.getItem('precheck_server_url')) {
                    const promptVal = prompt("Nhập địa chỉ máy chủ Precheck (IP mạng LAN hoặc localhost):", serverUrl);
                    if (promptVal && promptVal.trim()) {
                        serverUrl = promptVal.trim().replace(/\/+$/, '');
                        localStorage.setItem('precheck_server_url', serverUrl);
                    }
                }

                const target = `${serverUrl}/?sync_token=${encodeURIComponent(token)}&sync_user=${encodeURIComponent(JSON.stringify(userInfo))}`;
                window.open(target, '_blank');
            };

            document.body.appendChild(btn);
        } catch (e) {
            console.error("[Precheck Helper] Lỗi:", e);
        }
    }
})();
