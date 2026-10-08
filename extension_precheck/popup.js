// popup.js - VNPT Token Utilities v3.0

document.addEventListener('DOMContentLoaded', async () => {
  const inpServer = document.getElementById('inpServerUrl');
  const btnSave = document.getElementById('btnSaveServer');
  const btnTest = document.getElementById('btnTestConn');
  const btnSync = document.getElementById('btnSyncNow');
  const msgServer = document.getElementById('statusServerMsg');
  const msgSync = document.getElementById('syncResultMsg');

  // 1. Tải Server URL đã lưu
  chrome.storage.local.get(['precheck_server_url'], (res) => {
    inpServer.value = res.precheck_server_url || 'http://localhost:1234';
  });

  // 2. Kiểm tra trạng thái cookies hiện có trong trình duyệt
  checkLocalCookiesStatus();

  // 3. Nút Lưu địa chỉ Server
  btnSave.addEventListener('click', () => {
    let url = (inpServer.value || '').trim().replace(/\/$/, '');
    if (!url) url = 'http://localhost:1234';
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      url = 'http://' + url;
    }
    inpServer.value = url;
    chrome.storage.local.set({ precheck_server_url: url }, () => {
      showMsg(msgServer, 'Đã lưu địa chỉ máy chủ thành công!', 'success');
    });
  });

  // 4. Nút Kiểm tra kết nối tới Server
  btnTest.addEventListener('click', async () => {
    let url = (inpServer.value || '').trim().replace(/\/$/, '') || 'http://localhost:1234';
    showMsg(msgServer, 'Đang kiểm tra kết nối tới máy chủ...', '');
    try {
      const resp = await fetch(`${url}/api/status`, { method: 'GET', signal: AbortSignal.timeout(4000) });
      if (resp.ok) {
        showMsg(msgServer, `Kết nối máy chủ thành công! (Mã ${resp.status})`, 'success');
      } else {
        showMsg(msgServer, `Máy chủ phản hồi mã ${resp.status}`, 'error');
      }
    } catch (e) {
      showMsg(msgServer, `Không thể kết nối máy chủ (${e.message || e}). Hãy kiểm tra IP hoặc cổng 1234.`, 'error');
    }
  });

  // 5. Nút Đồng bộ tất cả lên Server
  btnSync.addEventListener('click', async () => {
    let url = (inpServer.value || '').trim().replace(/\/$/, '') || 'http://localhost:1234';
    btnSync.disabled = true;
    btnSync.innerText = 'Đang đồng bộ...';
    showMsg(msgSync, 'Đang thu thập và đẩy Token/Cookie...', '');

    try {
      chrome.runtime.sendMessage({ action: 'FORCE_SYNC_ALL', target_server: url }, (res) => {
        btnSync.disabled = false;
        btnSync.innerText = 'Đồng bộ tất cả lên Server';
        if (res && res.success) {
          showMsg(msgSync, `Đồng bộ thành công! (${(res.synced || []).length} dịch vụ đã gửi)`, 'success');
          checkLocalCookiesStatus();
        } else {
          showMsg(msgSync, res ? (res.message || 'Lỗi đồng bộ') : 'Không nhận được phản hồi', 'error');
        }
      });
    } catch (e) {
      btnSync.disabled = false;
      btnSync.innerText = 'Đồng bộ tất cả lên Server';
      showMsg(msgSync, 'Lỗi gửi yêu cầu đồng bộ: ' + e, 'error');
    }
  });

  function showMsg(elem, text, type) {
    if (!elem) return;
    elem.innerText = text;
    elem.className = 'status-msg ' + (type || '');
  }

  function setPill(id, hasToken) {
    const el = document.getElementById(id);
    if (!el) return;
    if (hasToken) {
      el.className = 'pill pill-green';
      el.innerText = 'Đã có';
    } else {
      el.className = 'pill pill-gray';
      el.innerText = 'Chưa có';
    }
  }

  function checkLocalCookiesStatus() {
    if (!chrome.cookies) return;

    // BTools
    chrome.cookies.getAll({ domain: '10.159.21.241' }, (c) => {
      setPill('stBtools', c && c.some(x => x.name.toUpperCase() === 'JSESSIONID'));
    });

    // CEM
    chrome.cookies.getAll({ domain: 'vnptmedia.vn' }, (c) => {
      setPill('stCem', c && c.some(x => x.name.toLowerCase() === 'apikey'));
    });

    // SAPC
    chrome.cookies.getAll({ domain: '10.155.42.218' }, (c) => {
      setPill('stSapc', c && c.length > 0);
    });

    // CCOS
    chrome.cookies.getAll({ domain: 'gqknccos.vnpt.vn' }, (c) => {
      setPill('stCcos', c && c.some(x => x.name.includes('SessionDB') || x.name.includes('SESSIONID')));
    });

    // TTS Mới
    chrome.cookies.getAll({ domain: 'vnptnet.vn' }, (c) => {
      setPill('stTtsNew', c && c.length > 0);
    });
  }
});
