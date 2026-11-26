// static/js/modules/smsc_cdr.js
// Module tra cứu nhật ký tin nhắn SMSC (CDR)

// ==========================================
// TÍCH HỢP TRA CỨU NHẬT KÝ TIN NHẮN SMSC (CDR)
// ==========================================

// Dữ liệu từ điển đầu số/brandname và mã lỗi SMSC
let smsLibData = null;
let smsCodeData = null;
let smsLibLookupMap = {};
let smsDictLoaded = false;

async function loadSmsDictionaries() {
    if (smsDictLoaded) return;
    try {
        const [libRes, codeRes] = await Promise.all([
            fetch('/api/cdr/lib').then(r => r.json()).catch(() => null),
            fetch('/api/cdr/codes').then(r => r.json()).catch(() => null)
        ]);
        if (libRes && !libRes.error) {
            smsLibData = libRes;
            buildSmsLibLookupIndex(libRes);
        }
        if (codeRes && !codeRes.error) {
            smsCodeData = codeRes;
        }
        smsDictLoaded = true;
        if (lastCdrRecords && lastCdrRecords.length > 0) {
            renderCdrTable();
        }
    } catch (e) {
        console.warn('Lỗi khi tải từ điển SMS CDR:', e);
    }
}

function buildSmsLibLookupIndex(lib) {
    if (!lib) return;
    smsLibLookupMap = {};

    function addEntry(code, name, category, note) {
        if (!code) return;
        const key = String(code).trim().toUpperCase();
        if (!key) return;
        smsLibLookupMap[key] = {
            name: name || key,
            category: category || 'SERVICE',
            note: note || ''
        };
        const noSpace = key.replace(/\s+/g, '');
        if (noSpace && !smsLibLookupMap[noSpace]) {
            smsLibLookupMap[noSpace] = smsLibLookupMap[key];
        }
        if (key.startsWith('84') && key.length > 8) {
            const no84 = key.slice(2);
            if (!smsLibLookupMap[no84]) smsLibLookupMap[no84] = smsLibLookupMap[key];
            const zeroPhone = '0' + no84;
            if (!smsLibLookupMap[zeroPhone]) smsLibLookupMap[zeroPhone] = smsLibLookupMap[key];
        }
    }

    (lib.vinaphone_internal?.smsc_gateways || []).forEach(g => addEntry(g.code, g.name, 'GATEWAY', g.note));
    (lib.vinaphone_internal?.core_shortcodes || []).forEach(s => addEntry(s.code, s.name, 'VINAPHONE_CORE', s.category));
    (lib.government_and_regulatory || []).forEach(g => addEntry(g.code, g.name, 'GOVERNMENT', g.category));
    (lib.device_silent_sms_and_activation?.shortcodes_and_gateways || []).forEach(s => addEntry(s.code, s.name, 'DEVICE_ACTIVATION', s.behavior || s.vendor));
    (lib.international_otp_and_ott_hubs?.senders || []).forEach(h => addEntry(h.code, h.services, 'GLOBAL_OTP_HUB', h.note));
    (lib.banking_and_finance || []).forEach(b => {
        addEntry(b.code, b.name, 'BANKING', '');
        if (Array.isArray(b.aliases)) b.aliases.forEach(a => addEntry(a, b.name, 'BANKING', ''));
    });
    (lib.securities_and_investments || []).forEach(s => addEntry(s.code, s.name, 'SECURITIES', ''));
    (lib.ewallets_and_ecommerce || []).forEach(e => {
        addEntry(e.code, e.name, e.category || 'FINTECH_OTT', '');
        if (Array.isArray(e.aliases)) e.aliases.forEach(a => addEntry(a, e.name, e.category || 'FINTECH_OTT', ''));
    });
}

function lookupSmsServiceInfo(callingNumber, calledNumber, subscriberPhone) {
    const cleanSub = String(subscriberPhone || '').replace(/\D/g, '');
    const cleanCalling = String(callingNumber || '').trim();
    const cleanCalled = String(calledNumber || '').trim();

    let partner = '';
    const normSub = cleanSub.startsWith('0') ? ('84' + cleanSub.slice(1)) : cleanSub;
    const normCalling = cleanCalling.replace(/\D/g, '');
    const normCalled = cleanCalled.replace(/\D/g, '');

    if (normCalling && (normCalling === normSub || normCalling.endsWith(cleanSub) || cleanSub.endsWith(normCalling))) {
        partner = cleanCalled;
    } else if (normCalled && (normCalled === normSub || normCalled.endsWith(cleanSub) || cleanSub.endsWith(normCalled))) {
        partner = cleanCalling;
    } else {
        partner = cleanCalling;
    }

    if (!partner || partner === '--') return { html: '<span style="color:#94a3b8; font-size:10.5px;">--</span>', title: '' };

    const upperPartner = partner.toUpperCase();
    const noSpace = upperPartner.replace(/\s+/g, '');

    let entry = smsLibLookupMap[upperPartner] || smsLibLookupMap[noSpace];
    if (!entry && partner !== cleanCalled) {
        const uCalled = cleanCalled.toUpperCase();
        if (smsLibLookupMap[uCalled] || smsLibLookupMap[uCalled.replace(/\s+/g, '')]) {
            entry = smsLibLookupMap[uCalled] || smsLibLookupMap[uCalled.replace(/\s+/g, '')];
            partner = cleanCalled;
        }
    }

    if (entry) {
        let badgeColor = '#0369a1';
        let badgeBg = '#f0f9ff';
        let badgeBorder = '#bae6fd';

        if (entry.category === 'VINAPHONE_CORE' || entry.category === 'GATEWAY') {
            badgeColor = '#047857'; badgeBg = '#ecfdf5'; badgeBorder = '#a7f3d0';
        } else if (entry.category === 'BANKING' || entry.category === 'FINTECH' || entry.category === 'FINTECH_OTT') {
            badgeColor = '#1d4ed8'; badgeBg = '#eff6ff'; badgeBorder = '#bfdbfe';
        } else if (entry.category === 'DEVICE_ACTIVATION') {
            badgeColor = '#b45309'; badgeBg = '#fffbeb'; badgeBorder = '#fde68a';
        } else if (entry.category === 'GLOBAL_OTP_HUB') {
            badgeColor = '#7c3aed'; badgeBg = '#f5f3ff'; badgeBorder = '#ddd6fe';
        } else if (entry.category === 'GOVERNMENT') {
            badgeColor = '#b91c1c'; badgeBg = '#fef2f2'; badgeBorder = '#fca5a5';
        }

        const titleText = `${entry.name} [${entry.category}]${entry.note ? ' - ' + entry.note : ''} (Đầu số: ${partner})`;
        return {
            html: `<span style="background:${badgeBg}; color:${badgeColor}; border:1px solid ${badgeBorder}; padding:2px 7px; border-radius:4px; font-weight:700; font-size:10.5px; display:inline-block; max-width:195px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; box-sizing:border-box;" title="${escapeHtml(titleText)}">${escapeHtml(entry.name)}</span>`,
            title: titleText
        };
    }

    const digitsOnly = partner.replace(/\D/g, '');
    if (digitsOnly.length > 0 && digitsOnly.length <= 5) {
        return {
            html: `<span style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; padding:2px 6px; border-radius:4px; font-size:10.5px; font-weight:600;" title="Đầu số dịch vụ VAS ngắn: ${escapeHtml(partner)}">Đầu số ${escapeHtml(partner)}</span>`,
            title: `Đầu số dịch vụ VAS: ${partner}`
        };
    } else if (digitsOnly.startsWith('84004') || digitsOnly.startsWith('004')) {
        return {
            html: `<span style="background:#fff1f2; color:#be123c; border:1px solid #fecdd3; padding:2px 6px; border-radius:4px; font-size:10.5px; font-weight:700;" title="Đầu số quốc tế / Kích hoạt dịch vụ thiết bị: ${escapeHtml(partner)}">Quốc tế (${escapeHtml(partner)})</span>`,
            title: `Đầu số quốc tế: ${partner}`
        };
    } else if (digitsOnly.length >= 9 && digitsOnly.length <= 11) {
        return {
            html: `<span style="color:#64748b; font-size:10.5px;" title="Tin nhắn gửi/nhận với thuê bao di động cá nhân (${escapeHtml(partner)})">Thuê bao cá nhân</span>`,
            title: `Thuê bao di động: ${partner}`
        };
    }

    return {
        html: `<span style="color:#475569; font-size:10.5px; font-weight:600;" title="Brandname / Dịch vụ: ${escapeHtml(partner)}">${escapeHtml(partner)}</span>`,
        title: partner
    };
}

function getMappedNetworkErrorTooltip(netErr) {
    const errStr = String(netErr || '').trim();
    if (!errStr || errStr === '0' || errStr === '--') {
        return 'Mapped Network Error 0: Mạng lưới không ghi nhận lỗi định tuyến lõi';
    }
    const mapping = smsCodeData?.['3gpp_map_and_rp_error_mapping'];
    let detail = '';
    if (mapping) {
        const rp = mapping.rp_error_codes?.[errStr];
        const map = mapping.map_error_codes?.[errStr];
        if (rp) detail += `RP Error: ${rp.meaning_vi || rp.name || ''}. ${rp.technical_detail || ''}`;
        if (map) detail += `${detail ? '\n' : ''}MAP Error: ${map.meaning_vi || map.name || ''}. ${map.technical_detail || ''}`;
    }
    return detail ? `Mapped Network Error: Mã ${errStr}\n${detail.trim()}` : `Mapped Network Error: Mã ${errStr}`;
}

function getMessageStatusTooltip(statusVal) {
    const stStr = String(statusVal || '').trim();
    const stObj = smsCodeData?.smsc_message_status?.codes?.[stStr];
    if (stObj) {
        let tip = `Message Status: Mã ${stStr} - ${stObj.name}\nÝ nghĩa: ${stObj.meaning_vi}`;
        if (stObj.technical_detail) tip += `\nKỹ thuật: ${stObj.technical_detail}`;
        if (stObj.precheck_action) tip += `\nKhuyến nghị: ${stObj.precheck_action}`;
        return tip;
    }
    if (stStr === '2') return 'Message Status 2 (DELIVERED): Giao tin thành công hoàn tất tới thiết bị/đối tác.';
    if (stStr === '1') return 'Message Status 1 (DELIVERY_FAILED): Giao tin thất bại hoặc bị từ chối.';
    if (stStr === '3') return 'Message Status 3 (EXPIRED): Hết hạn lưu trữ trên SMSC do thuê bao tắt máy/ngoài vùng phủ sóng quá lâu.';
    return `Message Status: ${stStr}`;
}

function getTerminationCauseTooltip(causeVal) {
    const cStr = String(causeVal || '').trim().toUpperCase();
    if (cStr === '0' || cStr === '0000') return '0 (SUCCESS): Giao tin thành công (Normal / Successful).';
    const cObj = smsCodeData?.smsc_cause_for_termination?.codes?.[cStr];
    if (cObj) {
        let tip = `Cause For Termination: Mã ${cStr} - ${cObj.standard_name || cObj.name || ''}\nÝ nghĩa: ${cObj.meaning_vi || ''}`;
        if (cObj.root_cause || cObj.technical_detail) tip += `\nKỹ thuật: ${cObj.root_cause || cObj.technical_detail}`;
        if (cObj.ktv_suggestion || cObj.precheck_action) tip += `\nKhuyến nghị: ${cObj.ktv_suggestion || cObj.precheck_action}`;
        return tip;
    }
    if (cStr === '100C') return '100C (SUCCESS): Giao tin thành công hoàn tất.';
    if (cStr === '130C') return '130C (ROUTING_FAILURE): Lỗi định tuyến SRI-for-SM đến số đích (đọc kèm cột Mapped Network Error).';
    if (cStr === '135C') return '135C (INTERMEDIATE): Lỗi giao thức truyền tin hoặc hàng đợi chờ phát (Bản ghi trung gian).';
    if (cStr === '136C') return '136C (SPAM_RETRY_BLOCKED): Giao tin thất bại do chính sách Anti-Spam mạng đích chặn (Status 5 Retry - Dấu hiệu mã độc Botnet/Trojan).';
    if (cStr === '103C') return '103C (ABSENT_SUBSCRIBER): Thuê bao tắt máy hoặc ngoài vùng phủ sóng.';
    if (cStr === '104C') return '104C (MEMORY_EXCEEDED): Đầy bộ nhớ tin nhắn trên thiết bị/SIM.';
    if (cStr === '175C') return '175C (OCS_CHARGING_REJECT): Từ chối gửi tin do tài khoản hết tiền/chặn cước OCS.';
    if (cStr === '199C') return '199C (GENERAL_ERROR): Lỗi ghép mảnh tin dài (Status 12) hoặc sai cú pháp VAS/chặn dịch vụ.';
    if (cStr === '4108') return '4108 (ABSENT_SUBSCRIBER): Thuê bao tắt máy hoặc ngoài vùng phủ sóng.';
    return `Cause For Termination: ${cStr}`;
}

function syncCdrScrollbars() {
    const topScroll = document.getElementById('cdrTopScrollWrapper');
    const topInner = document.getElementById('cdrTopScrollInner');
    const tableScroll = document.getElementById('cdrTableScrollWrapper');
    const table = document.getElementById('cdrResultsTable');

    if (!topScroll || !tableScroll || !table || !topInner) return;

    if (table.style.display !== 'none' && table.scrollWidth > tableScroll.clientWidth) {
        topInner.style.width = (table.scrollWidth + 10) + 'px';
        topScroll.style.display = 'block';
    } else {
        topScroll.style.display = 'none';
    }

    if (!topScroll._syncBound) {
        let isSyncingTop = false;
        let isSyncingTable = false;

        topScroll.addEventListener('scroll', function() {
            if (!isSyncingTop) {
                isSyncingTable = true;
                tableScroll.scrollLeft = topScroll.scrollLeft;
            }
            isSyncingTop = false;
        });

        tableScroll.addEventListener('scroll', function() {
            if (!isSyncingTable) {
                isSyncingTop = true;
                topScroll.scrollLeft = tableScroll.scrollLeft;
            }
            isSyncingTable = false;
        });

        window.addEventListener('resize', function() {
            if (table.style.display !== 'none' && table.scrollWidth > tableScroll.clientWidth) {
                topInner.style.width = (table.scrollWidth + 10) + 'px';
                topScroll.style.display = 'block';
            } else {
                topScroll.style.display = 'none';
            }
        });

        topScroll._syncBound = true;
    }
}

let cdrShowMscColumns = false; // Mặc định ẩn 2 cột Originating MSC & Destination MSC để tránh chèn ép cột

function toggleMscColumns(btn) {
    cdrShowMscColumns = !cdrShowMscColumns;
    const textSpan = document.getElementById('btnToggleMscText');
    if (textSpan) {
        textSpan.innerText = cdrShowMscColumns ? 'Ẩn cột MSC (2)' : 'Hiện cột MSC (2)';
    }
    if (btn) {
        if (cdrShowMscColumns) {
            btn.style.background = '#eff6ff';
            btn.style.borderColor = '#93c5fd';
            btn.style.color = '#1d4ed8';
        } else {
            btn.style.background = '#f8fafc';
            btn.style.borderColor = '#cbd5e1';
            btn.style.color = '#475569';
        }
    }
    ensureSmscCdrHeaders();
    renderCdrTable();
}
window.toggleMscColumns = toggleMscColumns;

function ensureSmscCdrHeaders() {
    const table = document.getElementById('cdrResultsTable');
    if (!table) return;
    const minW = cdrShowMscColumns ? '1780px' : '1460px';
    table.style.minWidth = minW;
    const topInner = document.getElementById('cdrTopScrollInner');
    if (topInner) topInner.style.minWidth = minW;

    const thead = table.querySelector('thead');
    if (thead) {
        thead.innerHTML = `
            <tr style="white-space:nowrap; background:#f1f5f9; color:#1e293b;">
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 8px; width:42px; text-align:center;" title="Số thứ tự bản ghi">STT</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 8px; width:78px; text-align:center;" title="Cụm tổng đài SMSC / FDA chuẩn theo IP (FDA 26: 10.204.57.26, FDA 235: 10.161.72.235, FDA 204: 10.161.131.204)">FDA</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; min-width:120px;" title="Calling Number: Số thuê bao hoặc đầu số khởi tạo gửi tin nhắn">Calling Number</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; min-width:120px;" title="Called Number: Số thuê bao hoặc đầu số đích nhận tin nhắn">Called Number</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; min-width:210px; width:210px;" title="Dịch vụ / Brandname / Đầu số xác định từ thư viện SMS (sms_lib.json)">Dịch vụ / Brandname</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; min-width:145px; width:145px;" title="Delivery Time: Thời điểm SMSC hoàn tất chuyển phát bản tin tới thiết bị đích hoặc nhận báo lỗi">Delivery Time</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; min-width:160px; display:${cdrShowMscColumns ? '' : 'none'};" title="Originating MSC Address: Địa chỉ tổng đài phát MSC nơi thuê bao gửi tin đang đăng ký">Originating MSC Address</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; min-width:160px; display:${cdrShowMscColumns ? '' : 'none'};" title="Destination MSC Address: Địa chỉ tổng đài đích MSC nơi thuê bao nhận tin đang đăng ký">Destination MSC Address</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; min-width:155px;" title="Message Submission Time: Thời điểm bản tin được tiếp nhận thành công vào hàng đợi SMSC">Message Submission Time</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; min-width:130px;" title="Call Reference: Số tham chiếu định danh phiên giao dịch trên mạng lõi viễn thông">Call Reference</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; width:95px; text-align:center;" title="Message Length: Độ dài ký tự của bản tin SMS (Tin dài vượt 70 ký tự có dấu hoặc 160 ký tự không dấu sẽ ghép nhiều phân đoạn)">Message Length</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; width:110px; text-align:center;" title="Number Of Attempts: Số lần hệ thống SMSC đã thử phát lại bản tin tới thuê bao">Number Of Attempts</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; width:125px; text-align:center;" title="Mapped Network Error: Mã lỗi định tuyến trên mạng lõi viễn thông (MAP/RP Error Code theo chuẩn 3GPP)">Mapped Network Error</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; width:95px; text-align:center;" title="Message Status: Trạng thái xử lý bản tin trên SMSC (2: Thành công, 1: Thất bại, 3: Hết hạn...)">Message Status</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 10px; width:130px; text-align:center;" title="Cause For Termination: Mã nguyên nhân kết thúc phiên giao dịch (100C: Thành công, 103C: Lỗi hệ thống, 199C: Lỗi tạm thời/chặn...)">Cause For Termination</th>
                <th style="position:sticky; top:0; z-index:10; background:#f1f5f9; border-bottom:2px solid #cbd5e1; padding:8px 12px; min-width:240px;" title="Termination Cause Information: Diễn giải chi tiết nguyên nhân kết thúc phiên từ hệ thống SMSC">Termination Cause Information</th>
            </tr>
        `;
    }
}

function openSmscCdrModal(phone, event) {
    if (event) event.stopPropagation();
    const modal = document.getElementById('modalSmscCdr');
    if (!modal) return;
    modal.style.display = 'flex';

    loadSmsDictionaries();

    // Đảm bảo khung mở rộng tối đa theo màn hình (96vw)
    const innerBox = modal.querySelector('div') || document.getElementById('modalSmscCdrInner');
    if (innerBox) {
        innerBox.style.width = '96vw';
        innerBox.style.maxWidth = '1850px';
        innerBox.style.height = '92vh';
        innerBox.style.maxHeight = '92vh';
        innerBox.style.minHeight = '0';
    }
    ensureSmscCdrHeaders();

    // Luôn mặc định KHÔNG chọn "Quét mới từ hệ thống", ưu tiên lấy Database có sẵn để hiển thị tức thì
    const forceCheck = document.getElementById('cdrForceRefreshCheck');
    if (forceCheck) forceCheck.checked = false;

    const input = document.getElementById('cdrPhoneInput');
    if (phone && input) {
        let cleanPhone = String(phone).trim().replace(/\D/g, '');
        if (cleanPhone.startsWith('0')) cleanPhone = '84' + cleanPhone.slice(1);
        input.value = cleanPhone;
        const cached = (typeof window.smsCdrSummaryCache !== 'undefined') ? window.smsCdrSummaryCache[cleanPhone] : null;
        let fromDateVal = (cached && cached.fromDate && !String(cached.fromDate).includes('undefined')) ? cached.fromDate : '';
        let toDateVal = (cached && cached.toDate && !String(cached.toDate).includes('undefined')) ? cached.toDate : '';

        if (!fromDateVal || !toDateVal) {
            const tList = (typeof cachedTickets !== 'undefined' && Array.isArray(cachedTickets)) ? cachedTickets : [];
            const tObj = tList.find(x => {
                const xPhone = String(x.phone || '').trim().replace(/\D/g, '');
                const cleanX = xPhone.startsWith('0') ? ('84' + xPhone.slice(1)) : ((!xPhone.startsWith('84') && xPhone.length === 9) ? ('84' + xPhone) : xPhone);
                return cleanX === cleanPhone;
            });
            if (tObj && typeof window.extractSmsIncidentDetails === 'function') {
                const parsed = window.extractSmsIncidentDetails(tObj.ticket_content || tObj.ai_summary || '', tObj.sms_incident_time || tObj.incident_time || '', tObj.created_time || '');
                if (parsed.fromDate && parsed.toDate) {
                    fromDateVal = parsed.fromDate;
                    toDateVal = parsed.toDate;
                }
            }
        }

        if (fromDateVal && toDateVal) {
            setCdrTimePreset('custom', document.querySelector('.cdr-time-btn[data-val="custom"]'));
            const fromInp = document.getElementById('cdrFromDate');
            const toInp = document.getElementById('cdrToDate');
            if (fromInp) fromInp.value = fromDateVal.split(' ')[0] || fromDateVal;
            if (toInp) toInp.value = toDateVal.split(' ')[0] || toDateVal;
        }

        const dirSelect = document.getElementById('cdrDirectionSelect');
        if (dirSelect) dirSelect.value = 'both';
        const limitSelect = document.getElementById('cdrLimitSelect');
        if (limitSelect) limitSelect.value = 'all';

        executeSmscCdrQuery();
    } else if (input) {
        input.focus();
    }
}

function closeSmscCdrModal() {
    const modal = document.getElementById('modalSmscCdr');
    if (modal) modal.style.display = 'none';
    clearAllCdrDetailFilters(false);
    const filterRow = document.getElementById('cdrFilterRow');
    if (filterRow) filterRow.style.display = 'none';
}

function setCdrTimePreset(val, btn) {
    const hiddenInp = document.getElementById('cdrHoursSelect');
    if (hiddenInp) hiddenInp.value = val;

    document.querySelectorAll('.cdr-time-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');

    toggleCdrDateInputs(val);
}

function toggleCdrDateInputs(val) {
    const box = document.getElementById('cdrCustomDateBox');
    if (!box) return;
    if (val === 'custom') {
        box.style.display = 'flex';
        const fromInp = document.getElementById('cdrFromDate');
        const toInp = document.getElementById('cdrToDate');
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const past = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const pastStr = `${past.getFullYear()}-${pad(past.getMonth() + 1)}-${pad(past.getDate())}`;
        if (fromInp && !fromInp.value) fromInp.value = pastStr;
        if (toInp && !toInp.value) toInp.value = todayStr;
    } else {
        box.style.display = 'none';
    }
}

// Lắng nghe phím ESC để đóng Modal SMSC CDR
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        const modal = document.getElementById('modalSmscCdr');
        if (modal && modal.style.display !== 'none') {
            closeSmscCdrModal();
        }
    }
});

// Biến lưu trạng thái bảng tra cứu CDR
let cdrFilterFailedOnly = false;
let cdrDirectionFilter = 'all'; // 'all' | 'mo' | 'mt'
let cdrFilterCalling = '';
let cdrFilterCalled = '';
let lastCdrRecords = [];
let lastCdrPhone = '';
let cdrCurrentPage = 1;
let cdrPageSize = 50; // 'all' hoặc số lượng dòng trên 1 trang

function onCdrFilterCallingChange(val) {
    cdrFilterCalling = String(val || '').trim();
    const btnClear = document.getElementById('btnClearFilterCalling');
    if (btnClear) btnClear.style.display = cdrFilterCalling ? 'inline-block' : 'none';
    cdrCurrentPage = 1;
    updateCdrDetailFilterControls();
    renderCdrTable();
}

function onCdrFilterCalledChange(val) {
    cdrFilterCalled = String(val || '').trim();
    const btnClear = document.getElementById('btnClearFilterCalled');
    if (btnClear) btnClear.style.display = cdrFilterCalled ? 'inline-block' : 'none';
    cdrCurrentPage = 1;
    updateCdrDetailFilterControls();
    renderCdrTable();
}

function clearCdrFilterCalling() {
    const inp = document.getElementById('cdrFilterCallingInput');
    if (inp) inp.value = '';
    onCdrFilterCallingChange('');
}

function clearCdrFilterCalled() {
    const inp = document.getElementById('cdrFilterCalledInput');
    if (inp) inp.value = '';
    onCdrFilterCalledChange('');
}

function clearAllCdrDetailFilters(shouldRender = true) {
    cdrFilterCalling = '';
    cdrFilterCalled = '';
    const inpCalling = document.getElementById('cdrFilterCallingInput');
    if (inpCalling) inpCalling.value = '';
    const inpCalled = document.getElementById('cdrFilterCalledInput');
    if (inpCalled) inpCalled.value = '';
    const btnClearCalling = document.getElementById('btnClearFilterCalling');
    if (btnClearCalling) btnClearCalling.style.display = 'none';
    const btnClearCalled = document.getElementById('btnClearFilterCalled');
    if (btnClearCalled) btnClearCalled.style.display = 'none';
    updateCdrDetailFilterControls();
    if (shouldRender) {
        cdrCurrentPage = 1;
        renderCdrTable();
    }
}

function applyCdrCallingFilter(num) {
    if (!num || num === '--') return;
    const inp = document.getElementById('cdrFilterCallingInput');
    if (inp) inp.value = num;
    onCdrFilterCallingChange(num);
}

function applyCdrCalledFilter(num) {
    if (!num || num === '--') return;
    const inp = document.getElementById('cdrFilterCalledInput');
    if (inp) inp.value = num;
    onCdrFilterCalledChange(num);
}

function updateCdrDetailFilterControls() {
    const hasFilter = !!(cdrFilterCalling || cdrFilterCalled);
    const btnClearAll = document.getElementById('btnClearAllDetailFilters');
    if (btnClearAll) btnClearAll.style.display = hasFilter ? 'inline-flex' : 'none';

    const badge = document.getElementById('cdrFilterResultBadge');
    if (badge) {
        if (hasFilter) {
            badge.style.display = 'inline-block';
            const filteredRecs = getFilteredCdrRecords();
            const txtFiltered = document.getElementById('cdrFilteredCountText');
            if (txtFiltered) txtFiltered.innerText = filteredRecs.length.toLocaleString();
            const txtTotal = document.getElementById('cdrTotalUnfilteredCountText');
            let baseTotal = (lastCdrRecords || []).length;
            if (cdrDirectionFilter === 'mo') {
                baseTotal = (lastCdrRecords || []).filter(r => String(r.direction || '').toUpperCase().includes('MO')).length;
            } else if (cdrDirectionFilter === 'mt') {
                baseTotal = (lastCdrRecords || []).filter(r => String(r.direction || '').toUpperCase().includes('MT')).length;
            }
            if (txtTotal) txtTotal.innerText = baseTotal.toLocaleString();
        } else {
            badge.style.display = 'none';
        }
    }
}

function setSmscCdrDirectionFilter(dir) {
    cdrDirectionFilter = dir || 'all';
    cdrCurrentPage = 1;
    updateCdrDirectionFilterUi();
    updateCdrDetailFilterControls();
    renderCdrTable();
}

function updateCdrDirectionFilterUi() {
    const btnAll = document.getElementById('btnFilterCdrAll');
    const btnMo = document.getElementById('btnFilterCdrMo');
    const btnMt = document.getElementById('btnFilterCdrMt');

    const kpiTotal = document.getElementById('kpiTotalCdrBox');
    const kpiMo = document.getElementById('kpiMoCdrBox');
    const kpiMt = document.getElementById('kpiMtCdrBox');

    const resetBtn = (b, isActive) => {
        if (!b) return;
        if (isActive) {
            b.style.background = '#0f172a';
            b.style.color = '#ffffff';
        } else {
            b.style.background = 'transparent';
            b.style.color = '#475569';
        }
    };

    resetBtn(btnAll, cdrDirectionFilter === 'all');
    resetBtn(btnMo, cdrDirectionFilter === 'mo');
    resetBtn(btnMt, cdrDirectionFilter === 'mt');

    const highlightKpi = (box, isActive, activeBorder) => {
        if (!box) return;
        box.style.border = isActive ? `2px solid ${activeBorder}` : '1px solid #cbd5e1';
        box.style.boxShadow = isActive ? '0 1px 3px rgba(0,0,0,0.1)' : 'none';
    };

    highlightKpi(kpiTotal, cdrDirectionFilter === 'all', '#0f172a');
    highlightKpi(kpiMo, cdrDirectionFilter === 'mo', '#0369a1');
    highlightKpi(kpiMt, cdrDirectionFilter === 'mt', '#0d9488');
}

function getFilteredCdrRecords() {
    let records = lastCdrRecords || [];
    if (cdrDirectionFilter === 'mo') {
        records = records.filter(r => String(r.direction || '').toUpperCase().includes('MO'));
    } else if (cdrDirectionFilter === 'mt') {
        records = records.filter(r => String(r.direction || '').toUpperCase().includes('MT'));
    }
    if (cdrFilterFailedOnly) {
        records = records.filter(isCdrRecordFailed);
    }
    if (cdrFilterCalling) {
        const qCall = cdrFilterCalling.toLowerCase();
        const cleanQCall = qCall.replace(/\D/g, '');
        records = records.filter(r => {
            const c = String(r.calling_number || '').toLowerCase();
            if (c.includes(qCall)) return true;
            if (cleanQCall.length >= 3) {
                const cleanC = c.replace(/\D/g, '');
                if (cleanC && (cleanC.includes(cleanQCall) || cleanC.endsWith(cleanQCall) || cleanQCall.endsWith(cleanC))) return true;
            }
            return false;
        });
    }
    if (cdrFilterCalled) {
        const qCalled = cdrFilterCalled.toLowerCase();
        const cleanQCalled = qCalled.replace(/\D/g, '');
        records = records.filter(r => {
            const c = String(r.called_number || '').toLowerCase();
            if (c.includes(qCalled)) return true;
            if (cleanQCalled.length >= 3) {
                const cleanC = c.replace(/\D/g, '');
                if (cleanC && (cleanC.includes(cleanQCalled) || cleanC.endsWith(cleanQCalled) || cleanQCalled.endsWith(cleanC))) return true;
            }
            return false;
        });
    }
    return records;
}

// QUY TẮC A: Phân loại bản ghi tiếp nhận trung gian / ghép mảnh tin dài (Intermediate Segment Log)
function isCdrRecordIntermediate(r) {
    if (!r) return false;
    const resCode = String(r.termination_cause || r.result_code || '').trim().toUpperCase();
    const attempts = String(r.attempts ?? r.number_of_attempts ?? '').trim();
    const sc = String(r.status_code || '').trim();
    return resCode === '199C' || attempts === '0' || attempts === '000' || sc === '12' || r.status_type === 'intermediate' || r.is_intermediate === true;
}

const SMSC_FAIL_CAUSES = new Set([
    '130C', '135C', '136C', '101F', '1020', '1001', '1004', '1009', '100B', 
    '100D', '100E', '1021', '1032', '1033', '1034', '1035', '1036', '175C', '103C'
]);

function isCdrRecordFailed(r) {
    if (!r) return false;
    // QUY TẮC A: Bản ghi trung gian (199C, status 12, attempts 000) bỏ qua, tuyệt đối không tính là lỗi
    if (isCdrRecordIntermediate(r)) return false;

    const code = String(r.status_code || '').trim();
    const resCode = String(r.termination_cause || r.result_code || '').trim().toUpperCase();

    if (resCode === '100C' || resCode === '133C' || resCode === '4108') return false;
    if (SMSC_FAIL_CAUSES.has(resCode) || ['8', '1', '4', '5', '7'].includes(code)) return true;
    if (r.status_type === 'failed') return true;

    const desc = String(r.status_desc || '').toLowerCase();
    if (desc.includes('thất bại') || desc.includes('lỗi') || desc.includes('chặn') || desc.includes('failed') || desc.includes('rejected')) return true;
    return false;
}

function isCdrRecordSuccess(r) {
    if (!r) return false;
    if (isCdrRecordIntermediate(r)) return false;
    if (isCdrRecordFailed(r)) return false;

    const sc = String(r.status_code || '').trim();
    const tc = String(r.termination_cause || r.result_code || '').trim().toUpperCase();

    // CHỈ CÔNG NHẬN THÀNH CÔNG KHI CÓ MÃ XÁC NHẬN GIAO TIN CHUẨN XÁC 3GPP (100C / 133C / 4108 hoặc Status 2 Delivered / Cause 0)
    if (tc === '100C' || tc === '133C' || tc === '4108' || sc === '100C' || sc === '133C' || sc === '4108') {
        return true;
    }
    if ((sc === '2' || sc === '0') && (tc === '0' || tc === '0000' || tc === '' || tc === '--' || tc === 'NONE' || tc === 'NULL')) {
        return true;
    }
    if (r.is_success === true || r.status_type === 'success') {
        return true;
    }
    // Tuyệt đối không fallback theo r.status_type cũ trong database
    return false;
}

function isCdrRecordPending(r) {
    if (!r) return false;
    if (isCdrRecordIntermediate(r)) return false;
    if (r.status_type === 'pending') return true;
    const desc = String(r.status_desc || '').toLowerCase();
    if (desc.includes('chờ') || desc.includes('thử lại') || desc.includes('expired')) return true;
    const code = String(r.status_code || '').trim();
    if (['0', '1', '3'].includes(code)) return true;
    return false;
}

if (typeof window !== 'undefined') {
    window.isCdrRecordIntermediate = isCdrRecordIntermediate;
    window.isCdrRecordFailed = isCdrRecordFailed;
    window.isCdrRecordSuccess = isCdrRecordSuccess;
    window.isCdrRecordPending = isCdrRecordPending;
}

// QUY TẮC B: Gom nhóm các bản ghi kết quả theo CALL REFERENCE (loại bỏ 199C và Attempts = 000)
function calculateCdrGroupStats(records) {
    const recs = records || [];
    const moGroups = new Map();
    const mtGroups = new Map();
    let intermediateCount = 0;

    recs.forEach(r => {
        if (isCdrRecordIntermediate(r)) {
            intermediateCount++;
            return; // Bỏ qua bản ghi trung gian ghép mảnh khi đếm tin thực tế
        }

        const dir = String(r.direction || '').toUpperCase();
        const isMo = dir.includes('MO');
        const targetMap = isMo ? moGroups : mtGroups;

        let callRef = String(r.call_reference || '').trim();
        if (!callRef || callRef === '--' || callRef === 'None' || callRef === 'null') {
            const subT = String(r.submission_time || r.delivery_time || '').trim();
            callRef = `${r.calling_number}_${r.called_number}_${subT}`;
        }

        if (!targetMap.has(callRef)) {
            targetMap.set(callRef, []);
        }
        targetMap.get(callRef).push(r);
    });

    let moTotal = moGroups.size;
    let moOk = 0;
    moGroups.forEach(rows => {
        const ok = rows.some(row => isCdrRecordSuccess(row));
        if (ok) moOk++;
    });
    let moFail = moTotal - moOk;
    let moRate = moTotal > 0 ? Math.round((moOk / moTotal) * 100) : 0;

    let mtTotal = mtGroups.size;
    let mtOk = 0;
    mtGroups.forEach(rows => {
        const ok = rows.some(row => isCdrRecordSuccess(row));
        if (ok) mtOk++;
    });
    let mtFail = mtTotal - mtOk;
    let mtRate = mtTotal > 0 ? Math.round((mtOk / mtTotal) * 100) : 0;

    let totalMsgs = moTotal + mtTotal;
    let totalOk = moOk + mtOk;
    let totalFail = moFail + mtFail;
    let successRate = totalMsgs > 0 ? Math.round((totalOk / totalMsgs) * 100) : 0;

    // Đếm số dòng log lỗi thực tế trên bảng (loại trừ intermediate 199C)
    const failedLogCount = recs.filter(isCdrRecordFailed).length;

    return {
        totalMsgs,
        totalOk,
        totalFail,
        successRate,
        moTotal,
        moOk,
        moFail,
        moRate,
        mtTotal,
        mtOk,
        mtFail,
        mtRate,
        intermediateCount,
        failedLogCount,
        rawCount: recs.length
    };
}

if (typeof window !== 'undefined') {
    window.calculateCdrGroupStats = calculateCdrGroupStats;
}

function toggleOnlyFailedCdr(btn) {
    cdrFilterFailedOnly = !cdrFilterFailedOnly;
    cdrCurrentPage = 1;
    const btnElem = btn || document.getElementById('btnFilterFailedOnly');
    const failedCount = (lastCdrRecords || []).filter(isCdrRecordFailed).length;
    if (btnElem) {
        if (cdrFilterFailedOnly) {
            btnElem.style.background = '#dc2626';
            btnElem.style.color = '#ffffff';
            btnElem.style.borderColor = '#b91c1c';
            btnElem.innerHTML = `<span>Đang lọc tin lỗi:</span> <span style="background:#ffffff; color:#dc2626; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:800;">${failedCount}</span> <span style="font-size:10px; opacity:0.85;">(Bấm để xem tất cả)</span>`;
        } else {
            btnElem.style.background = '#fee2e2';
            btnElem.style.color = '#b91c1c';
            btnElem.style.borderColor = '#fca5a5';
            btnElem.innerHTML = `<span>Chỉ xem tin lỗi:</span> <span id="badgeFailedCount" style="background:#dc2626; color:#ffffff; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:800;">${failedCount}</span>`;
        }
    }
    renderCdrTable();
}

function changeCdrPageSize(newVal) {
    cdrPageSize = (newVal === 'all') ? 'all' : (parseInt(newVal, 10) || 50);
    cdrCurrentPage = 1;
    renderCdrTable();
}

function changeCdrPage(delta) {
    cdrCurrentPage += delta;
    renderCdrTable();
}

function goToCdrPage(page) {
    const displayRecords = getFilteredCdrRecords();
    const totalRecords = displayRecords.length;
    const pageSizeNum = (cdrPageSize === 'all') ? totalRecords : (parseInt(cdrPageSize, 10) || 50);
    const totalPages = Math.max(1, Math.ceil(totalRecords / (pageSizeNum || 1)));

    if (page === 'last') {
        cdrCurrentPage = totalPages;
    } else {
        cdrCurrentPage = parseInt(page, 10) || 1;
    }
    renderCdrTable();
}

function renderCdrTable() {
    const tableBody = document.getElementById('cdrTableBody');
    const emptyState = document.getElementById('cdrEmptyState');
    const resultsTable = document.getElementById('cdrResultsTable');
    const paginationBox = document.getElementById('cdrPaginationBox');
    const pageInfo = document.getElementById('cdrPageInfo');
    const btnFirst = document.getElementById('btnCdrFirstPage');
    const btnPrev = document.getElementById('btnCdrPrevPage');
    const btnNext = document.getElementById('btnCdrNextPage');
    const btnLast = document.getElementById('btnCdrLastPage');

    if (!tableBody) return;

    const displayRecords = getFilteredCdrRecords();
    const totalRecords = displayRecords.length;

    if (totalRecords === 0) {
        if (emptyState) {
            emptyState.style.display = 'block';
            let emptyMsg = 'Không có bản ghi nào.';
            if (cdrFilterCalling || cdrFilterCalled) {
                const conds = [];
                if (cdrFilterCalling) conds.push(`Số gửi chứa "${escapeHtml(cdrFilterCalling)}"`);
                if (cdrFilterCalled) conds.push(`Số nhận chứa "${escapeHtml(cdrFilterCalled)}"`);
                emptyMsg = `
                    <div style="padding:24px 20px; text-align:center;">
                        <div style="color:#64748b; font-weight:600; font-size:12px;">Không tìm thấy bản ghi nào khớp bộ lọc chi tiết:</div>
                        <div style="color:#0f172a; font-weight:700; margin:6px 0 10px 0; font-size:13px;">${conds.join(' & ')}</div>
                        <button type="button" onclick="clearAllCdrDetailFilters()"
                            style="background:#0d9488; color:#ffffff; border:none; border-radius:2px; padding:6px 14px; font-size:11.5px; font-weight:700; cursor:pointer;">
                            Xóa bộ lọc để xem lại ${lastCdrRecords.length} bản ghi
                        </button>
                    </div>`;
            } else if (cdrFilterFailedOnly) {
                emptyMsg = `<div style="color:#15803d; font-weight:700; padding:10px;">Không có tin nhắn lỗi nào trong ${lastCdrRecords.length} bản ghi CDR!</div>`;
            } else if (cdrDirectionFilter === 'mo') {
                emptyMsg = `Không có bản ghi gửi đi (MO) nào.`;
            } else if (cdrDirectionFilter === 'mt') {
                emptyMsg = `Không có bản ghi nhận đến (MT) nào.`;
            }
            emptyState.innerHTML = emptyMsg;
        }
        if (resultsTable) resultsTable.style.display = 'none';
        if (paginationBox) paginationBox.style.display = 'none';
        const topScroll = document.getElementById('cdrTopScrollWrapper');
        if (topScroll) topScroll.style.display = 'none';
        return;
    }

    if (emptyState) emptyState.style.display = 'none';
    if (resultsTable) resultsTable.style.display = 'table';

    // Xử lý phân trang
    let pageRecords = displayRecords;
    let startIndex = 0;
    let totalPages = 1;

    if (cdrPageSize !== 'all') {
        const pageSizeNum = parseInt(cdrPageSize, 10) || 50;
        totalPages = Math.max(1, Math.ceil(totalRecords / pageSizeNum));
        if (cdrCurrentPage > totalPages) cdrCurrentPage = totalPages;
        if (cdrCurrentPage < 1) cdrCurrentPage = 1;

        startIndex = (cdrCurrentPage - 1) * pageSizeNum;
        pageRecords = displayRecords.slice(startIndex, startIndex + pageSizeNum);
    } else {
        cdrCurrentPage = 1;
        totalPages = 1;
    }

    if (paginationBox) {
        paginationBox.style.display = 'flex';
        if (pageInfo) {
            const endIdx = Math.min(startIndex + pageRecords.length, totalRecords);
            pageInfo.innerText = `Trang ${cdrCurrentPage} / ${totalPages} (${startIndex + 1}-${endIdx} / ${totalRecords})`;
        }
        if (btnFirst) btnFirst.disabled = (cdrCurrentPage <= 1);
        if (btnPrev) btnPrev.disabled = (cdrCurrentPage <= 1);
        if (btnNext) btnNext.disabled = (cdrCurrentPage >= totalPages);
        if (btnLast) btnLast.disabled = (cdrCurrentPage >= totalPages);
    }

    const isPhoneMatch = (numStr, target) => {
        if (!numStr || !target) return false;
        const c1 = String(numStr).replace(/\D/g, '');
        const c2 = String(target).replace(/\D/g, '');
        if (!c1 || !c2) return false;
        return (c1 === c2 || c1.endsWith(c2) || c2.endsWith(c1));
    };

    tableBody.innerHTML = pageRecords.map((r, localIdx) => {
        const globalIdx = startIndex + localIdx;
        const isIntermediate = isCdrRecordIntermediate(r);
        const isFailed = !isIntermediate && isCdrRecordFailed(r);
        const isSuccess = !isIntermediate && !isFailed && isCdrRecordSuccess(r);
        const isPending = !isIntermediate && !isFailed && !isSuccess && isCdrRecordPending(r);

        let rowBg = 'transparent';
        let rowHoverBg = '#f8fafc';
        let borderLeft = '4px solid transparent';
        let sttHtml = `<span style="color:#64748b; font-size:10.5px;">${globalIdx + 1}</span>`;
        let rowOpacity = '1';

        if (isIntermediate) {
            // QUY TẮC A: Bản ghi trung gian / ghép mảnh tin dài hiển thị màu mờ/xám đen trung tính, ghi nhận bỏ qua
            rowBg = '#f8fafc';
            rowHoverBg = '#f1f5f9';
            borderLeft = '4px solid #94a3b8';
            rowOpacity = '0.72';
            sttHtml = `<span style="color:#64748b; font-weight:600; font-size:10.5px;" title="Bản ghi phân đoạn ghép mảnh (Bỏ qua)">${globalIdx + 1}</span>`;
        } else if (isFailed) {
            // Bôi ĐỎ RỰC các tin lỗi
            rowBg = '#fff1f2';
            rowHoverBg = '#ffe4e6';
            borderLeft = '4px solid #ef4444';
            sttHtml = `<span style="color:#dc2626; font-weight:800; font-size:10.5px;">${globalIdx + 1}</span>`;
        } else if (isSuccess) {
            // Bôi XANH LÁ các tin thành công OK
            rowBg = '#f0fdf4';
            rowHoverBg = '#dcfce7';
            borderLeft = '4px solid #16a34a';
            sttHtml = `<span style="color:#15803d; font-weight:800; font-size:10.5px;">${globalIdx + 1}</span>`;
        } else if (isPending) {
            rowBg = '#fffbeb';
            rowHoverBg = '#fef3c7';
            borderLeft = '4px solid #f59e0b';
            sttHtml = `<span style="color:#d97706; font-weight:800; font-size:10.5px;">${globalIdx + 1}</span>`;
        }

        const padVal = (val, len) => {
            if (val === null || val === undefined || val === '' || val === '--') return '--';
            const num = parseInt(val, 10);
            return isNaN(num) ? String(val) : String(num).padStart(len, '0');
        };

        const siteUpper = String(r.site || '26').toUpperCase();
        let siteBadge = '';
        if (siteUpper.includes('204')) {
            const fdaLabel = siteUpper.includes('(') ? r.site : 'FDA 204';
            siteBadge = `<span style="background:#f5f3ff; color:#6d28d9; border:1px solid #ddd6fe; font-weight:700; font-size:9.5px; padding:1px 6px; border-radius:2px; white-space:nowrap;" title="FDAM2A (10.161.131.204)">${escapeHtml(fdaLabel)}</span>`;
        } else if (siteUpper.includes('235') || siteUpper.includes('NODE2') || siteUpper.includes('NODE 2') || siteUpper.includes('72.235')) {
            const fdaLabel = siteUpper.includes('(') ? r.site : 'FDA 235';
            siteBadge = `<span style="background:#fffbeb; color:#b45309; border:1px solid #fde68a; font-weight:700; font-size:9.5px; padding:1px 6px; border-radius:2px; white-space:nowrap;" title="Core SMSC (10.161.72.235)">${escapeHtml(fdaLabel)}</span>`;
        } else {
            const fdaLabel = siteUpper.includes('(') ? r.site : 'FDA 26';
            siteBadge = `<span style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; font-weight:700; font-size:9.5px; padding:1px 6px; border-radius:2px; white-space:nowrap;" title="SMSC Core (10.204.57.26)">${escapeHtml(fdaLabel)}</span>`;
        }

        const isTargetCalling = isPhoneMatch(r.calling_number, lastCdrPhone);
        const isTargetCalled = isPhoneMatch(r.called_number, lastCdrPhone);

        // Tra cứu dịch vụ / Brandname từ sms_lib.json
        const serviceInfo = lookupSmsServiceInfo(r.calling_number, r.called_number, lastCdrPhone);

        const attemptsVal = r.attempts || 1;
        const attemptsPadded = padVal(attemptsVal, 3);
        const attemptsHtml = isIntermediate
            ? `<span style="color:#64748b; font-weight:600;" title="Bản ghi tiếp nhận trung gian / ghép mảnh tin dài">${escapeHtml(attemptsPadded)}</span>`
            : (attemptsVal > 1
                ? `<b style="color:#dc2626; font-weight:800;">${escapeHtml(attemptsPadded)}</b>`
                : `<span style="color:#334155;">${escapeHtml(attemptsPadded)}</span>`);

        const msgLen = padVal(r.message_length, 4);
        const rawLen = parseInt(r.message_length, 10);
        let msgLenHtml = `<span style="color:${isIntermediate ? '#64748b' : '#334155'};">${escapeHtml(msgLen)}</span>`;
        if (!isNaN(rawLen) && rawLen > 70) {
            const segs = Math.min(10, Math.ceil(rawLen / 67));
            msgLenHtml = `<span style="color:#0f172a; font-weight:700;">${escapeHtml(msgLen)}</span> <span style="display:inline-block; padding:1px 4px; border-radius:3px; font-size:9.5px; font-weight:700; background:#fef3c7; color:#b45309; border:1px solid #fde68a;" title="Tin nhắn dài được tách thành ~${segs} phân đoạn cước">(~${segs} tin)</span>`;
        }

        // Mã lỗi mạng (Mapped Network Error) có Tooltip từ sms_code.json
        const netErr = String(r.mapped_network_err || '0').trim();
        const netErrTip = getMappedNetworkErrorTooltip(netErr);
        const netErrHtml = (netErr !== '--' && netErr !== '0')
            ? `<span style="background:#fef2f2; color:#b91c1c; border:1px solid #fca5a5; padding:1px 5px; border-radius:3px; font-weight:700; font-size:10.5px; cursor:help;" title="${escapeHtml(netErrTip)}">${escapeHtml(netErr)}</span>`
            : `<span style="color:${isIntermediate ? '#64748b' : '#334155'}; cursor:help;" title="${escapeHtml(netErrTip)}">${escapeHtml(netErr)}</span>`;

        // Mã trạng thái bản tin (Message Status) có Tooltip từ sms_code.json
        const statusCode = r.status_code ? String(r.status_code).trim() : '2';
        const statusTip = getMessageStatusTooltip(statusCode);
        let statusHtml = `<span style="color:#334155; font-weight:600; cursor:help;" title="${escapeHtml(statusTip)}">${escapeHtml(statusCode)}</span>`;
        if (isIntermediate) {
            statusHtml = `<span style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; padding:1px 5px; border-radius:3px; font-weight:600; font-size:10.5px; cursor:help;" title="${escapeHtml(statusTip)} (Bản ghi ghép mảnh - Bỏ qua)">${escapeHtml(statusCode)}</span>`;
        } else if (isFailed) {
            statusHtml = `<span style="background:#fee2e2; color:#b91c1c; border:1px solid #f87171; padding:1px 5px; border-radius:3px; font-weight:800; font-size:10.5px; cursor:help;" title="${escapeHtml(statusTip)}">${escapeHtml(statusCode)}</span>`;
        } else if (isSuccess) {
            statusHtml = `<span style="background:#dcfce7; color:#15803d; border:1px solid #86efac; padding:1px 5px; border-radius:3px; font-weight:800; font-size:10.5px; cursor:help;" title="${escapeHtml(statusTip)} (Thành công)">${escapeHtml(statusCode)}</span>`;
        }

        // Nguyên nhân kết thúc (Cause For Termination) có Tooltip từ sms_code.json
        const termCause = String(r.termination_cause || r.result_code || '100C').trim();
        const termCauseTip = getTerminationCauseTooltip(termCause);
        let termCauseHtml = `<span style="color:#334155; font-weight:500; cursor:help;" title="${escapeHtml(termCauseTip)}">${escapeHtml(termCause)}</span>`;
        if (isIntermediate) {
            termCauseHtml = `<span style="color:#64748b; font-weight:600; cursor:help;" title="199C: Tiếp nhận ghép mảnh tin dài (Bỏ qua)">${escapeHtml(termCause)} <small style="font-size:9.5px; color:#94a3b8;">[Mảnh]</small></span>`;
        } else if (isFailed) {
            termCauseHtml = `<span style="color:#dc2626; font-weight:800; cursor:help;" title="${escapeHtml(termCauseTip)}">${escapeHtml(termCause)}</span>`;
        } else if (isSuccess) {
            termCauseHtml = `<span style="color:#15803d; font-weight:800; cursor:help;" title="${escapeHtml(termCauseTip)}">${escapeHtml(termCause)}</span>`;
        }

        // Chi tiết nguyên nhân kết thúc
        let termInfo = isIntermediate
            ? 'Tiếp nhận ghép mảnh tin dài (Bỏ qua)'
            : String(r.termination_cause_info || '').trim();

        if (!termInfo || termInfo === '0' || termInfo === '0000' || termInfo === '--' || termInfo === '100C' || termInfo === '100c') {
            const tcKey = String(r.termination_cause || r.result_code || '').trim().toUpperCase();
            if (tcKey === '100C' || tcKey === '0' || tcKey === '0000' || tcKey === '4108' || tcKey === '133C' || isSuccess) {
                termInfo = 'Message Delivery Successful';
            } else if (termCauseTip && !termCauseTip.startsWith('Cause For Termination:')) {
                termInfo = termCauseTip;
            } else {
                termInfo = 'Message Delivery Successful';
            }
        }
        const fullTermInfoTip = `${termInfo}\n(${termCauseTip})`;
        const termInfoBox = `
            <div style="display:inline-flex; align-items:center; justify-content:space-between; background:#ffffff; border:1px solid ${isIntermediate ? '#cbd5e1' : (isFailed ? '#fca5a5' : (isSuccess ? '#86efac' : '#cbd5e1'))}; border-radius:4px; padding:3px 10px; font-size:11px; color:${isIntermediate ? '#64748b' : (isFailed ? '#b91c1c' : (isSuccess ? '#15803d' : '#334155'))}; width:230px; box-sizing:border-box; box-shadow:inset 0 1px 2px rgba(0,0,0,0.03); cursor:help;" title="${escapeHtml(fullTermInfoTip)}">
                <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-right:8px; font-weight:${isFailed || isSuccess ? '700' : '500'};">${escapeHtml(termInfo)}</span>
                <span style="font-size:8px; color:#64748b; flex-shrink:0;">▼</span>
            </div>
        `;

        const callRefVal = (r.call_reference && r.call_reference !== '--' && r.call_reference !== 'None') 
            ? escapeHtml(r.call_reference) 
            : `<span style="color:#94a3b8; font-style:italic;" title="Không có số tham chiếu Call Reference (Bản tin SMS qua IP/SMPP hoặc không qua tổng đài chuyển mạch MSC)">--</span>`;
        const origMscVal = (r.originating_msc && r.originating_msc !== '--' && r.originating_msc !== 'None') 
            ? escapeHtml(r.originating_msc) 
            : `<span style="color:#94a3b8; font-style:italic;" title="Không ghi nhận địa chỉ MSC phát">--</span>`;
        const destMscVal = (r.destination_msc && r.destination_msc !== '--' && r.destination_msc !== 'None') 
            ? escapeHtml(r.destination_msc) 
            : `<span style="color:#94a3b8; font-style:italic;" title="Không ghi nhận địa chỉ MSC đích">--</span>`;

        const callClickAttr = (r.calling_number && r.calling_number !== '--')
            ? `cursor:pointer; text-decoration:underline; text-underline-offset:2px;" onclick="applyCdrCallingFilter('${escapeHtml(r.calling_number)}')" title="Bấm để lọc nhanh theo số gửi này: ${escapeHtml(r.calling_number)}`
            : `;`;
        const calledClickAttr = (r.called_number && r.called_number !== '--')
            ? `cursor:pointer; text-decoration:underline; text-underline-offset:2px;" onclick="applyCdrCalledFilter('${escapeHtml(r.called_number)}')" title="Bấm để lọc nhanh theo số nhận này: ${escapeHtml(r.called_number)}`
            : `;`;

        return `
            <tr style="background:${rowBg}; border-left:${borderLeft}; border-bottom:1px solid #e2e8f0; transition:background 0.15s ease; white-space:nowrap;" onmouseover="this.style.background='${rowHoverBg}'" onmouseout="this.style.background='${rowBg}'">
                <td style="padding:6px 8px; text-align:center;">${sttHtml}</td>
                <td style="padding:6px 8px; text-align:center;">${siteBadge}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; font-weight:${isTargetCalling ? '800' : '500'}; color:${isTargetCalling ? '#0f766e' : '#334155'}; ${callClickAttr}">${escapeHtml(r.calling_number || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; font-weight:${isTargetCalled ? '800' : '500'}; color:${isTargetCalled ? '#0f766e' : '#334155'}; ${calledClickAttr}">${escapeHtml(r.called_number || '--')}</td>
                <td style="padding:6px 10px; font-family:'Segoe UI', sans-serif; font-size:11px; min-width:210px; max-width:220px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; box-sizing:border-box;">${serviceInfo.html}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#334155; min-width:145px; width:145px; box-sizing:border-box;">${escapeHtml(r.delivery_time || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#475569; display:${cdrShowMscColumns ? '' : 'none'};">${origMscVal}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#475569; display:${cdrShowMscColumns ? '' : 'none'};">${destMscVal}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#334155;">${escapeHtml(r.submission_time || '--')}</td>
                <td style="padding:6px 10px; font-family:'JetBrains Mono', monospace; font-size:11px; color:#475569;">${callRefVal}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${msgLenHtml}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${attemptsHtml}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${netErrHtml}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${statusHtml}</td>
                <td style="padding:6px 10px; text-align:center; font-family:'JetBrains Mono', monospace; font-size:11px;">${termCauseHtml}</td>
                <td style="padding:4px 10px; vertical-align:middle;">${termInfoBox}</td>
            </tr>
        `;
    }).join('');
    setTimeout(syncCdrScrollbars, 60);
}

async function executeSmscCdrQuery(forceLive = false) {
    const phoneInput = document.getElementById('cdrPhoneInput');
    const dirSelect = document.getElementById('cdrDirectionSelect');
    const hoursSelect = document.getElementById('cdrHoursSelect');
    const limitSelect = document.getElementById('cdrLimitSelect');
    const forceRefreshCheck = document.getElementById('cdrForceRefreshCheck');
    const isForce = forceLive || !!(forceRefreshCheck && forceRefreshCheck.checked);

    const spinner = document.getElementById('cdrLoadingSpinner');
    const emptyState = document.getElementById('cdrEmptyState');
    const resultsTable = document.getElementById('cdrResultsTable');
    const tableBody = document.getElementById('cdrTableBody');
    const kpiSection = document.getElementById('cdrKpiSection');
    const summaryText = document.getElementById('cdrQuerySummaryText');
    const sourceDot = document.getElementById('cdrSourceDot');
    const sourceText = document.getElementById('cdrSourceText');
    const btnSubmit = document.getElementById('btnExecuteCdrQuery');

    const rawPhone = phoneInput ? phoneInput.value.trim() : '';
    let cleanPhone = rawPhone.replace(/\D/g, '');
    if (!cleanPhone) {
        alert('Vui lòng nhập số thuê bao cần tra cứu CDR!');
        if (phoneInput) phoneInput.focus();
        return;
    }
    if (cleanPhone.startsWith('0')) cleanPhone = '84' + cleanPhone.slice(1);
    if (phoneInput) phoneInput.value = cleanPhone;

    const direction = dirSelect ? dirSelect.value : 'both';
    let limit = 1000;
    if (limitSelect) {
        if (limitSelect.value === 'all') {
            limit = 10000;
        } else {
            limit = parseInt(limitSelect.value, 10) || 1000;
        }
    }

    let isCustom = (hoursSelect && hoursSelect.value === 'custom');
    let fromDateVal = '';
    let toDateVal = '';
    let hours = 24;
    let timeRangeDesc = '';

    if (isCustom) {
        const fromInp = document.getElementById('cdrFromDate');
        const toInp = document.getElementById('cdrToDate');
        fromDateVal = fromInp ? fromInp.value.trim() : '';
        toDateVal = toInp ? toInp.value.trim() : '';
        if (!fromDateVal || !toDateVal) {
            alert('Vui lòng chọn đầy đủ Từ ngày và Đến ngày!');
            return;
        }
        if (fromDateVal > toDateVal) {
            alert('Từ ngày không thể lớn hơn Đến ngày!');
            return;
        }
        timeRangeDesc = `từ ${fromDateVal} đến ${toDateVal}`;
    } else {
        hours = hoursSelect ? parseInt(hoursSelect.value, 10) || 24 : 24;
        if (hours === 48) timeRangeDesc = '48h qua';
        else if (hours === 168) timeRangeDesc = '1 tuần qua';
        else if (hours === 720) timeRangeDesc = '1 tháng qua';
        else timeRangeDesc = `${hours}h qua`;
    }

    // UI Loading state
    if (spinner) spinner.style.display = 'block';
    if (emptyState) emptyState.style.display = 'none';
    if (resultsTable) resultsTable.style.display = 'none';
    if (kpiSection) kpiSection.style.display = 'none';
    const filterRowLoading = document.getElementById('cdrFilterRow');
    if (filterRowLoading) filterRowLoading.style.display = 'none';
    if (btnSubmit) {
        btnSubmit.disabled = true;
        btnSubmit.style.opacity = '0.65';
    }
    if (sourceText) sourceText.innerText = isForce ? 'Đang quét mới từ tổng đài SMSC...' : 'Đang truy vấn...';
    if (sourceDot) sourceDot.style.background = isForce ? '#0284c7' : '#f59e0b';

    try {
        let queryUrl = `/api/cdr/sms?phone=${encodeURIComponent(cleanPhone)}&direction=${encodeURIComponent(direction)}&limit=${limit}`;
        if (isCustom) {
            queryUrl += `&from_date=${encodeURIComponent(fromDateVal)}&to_date=${encodeURIComponent(toDateVal)}`;
        } else {
            queryUrl += `&hours=${hours}`;
        }
        if (isForce) {
            queryUrl += `&force_refresh=true`;
        }
        const controller = new AbortController();
        const timeoutMs = isForce ? 65000 : 15000;
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
        let res;
        try {
            res = await fetch(queryUrl, { signal: controller.signal });
        } finally {
            clearTimeout(timeoutId);
        }
        const data = await res.json();

        if (spinner) spinner.style.display = 'none';
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.style.opacity = '1';
        }

        if (!data.success) {
            const errMsg = data.message || data.error || 'Lỗi không xác định từ hệ thống SMSC CDR';
            if (lastCdrRecords && lastCdrRecords.length > 0) {
                // Giữ nguyên bảng dữ liệu hiện tại, hiển thị thanh cảnh báo ở trên
                if (resultsTable) resultsTable.style.display = 'table';
                if (emptyState) {
                    emptyState.style.display = 'block';
                    emptyState.innerHTML = `
                        <div style="background:#fffbeb; border:1px solid #fde68a; color:#b45309; padding:8px 12px; border-radius:6px; font-size:12px; font-weight:600; margin-bottom:12px; text-align:left;">
                            ⚠️ Quét mới thất bại (${escapeHtml(errMsg)}). Hệ thống giữ nguyên ${lastCdrRecords.length} bản ghi hiện tại.
                        </div>
                    `;
                }
            } else {
                if (emptyState) {
                    emptyState.style.display = 'block';
                    emptyState.innerHTML = `<div style="color:#dc2626; font-weight:700; line-height:1.5;">Tra cứu thất bại: ${escapeHtml(errMsg)}</div>`;
                }
            }
            if (sourceText) sourceText.innerText = (lastCdrRecords && lastCdrRecords.length > 0) ? 'Giữ dữ liệu cũ' : 'Lỗi kết nối';
            if (sourceDot) sourceDot.style.background = (lastCdrRecords && lastCdrRecords.length > 0) ? '#f59e0b' : '#ef4444';
            return;
        }

        // Cập nhật nguồn dữ liệu (Database, Elastic, VHKT Bridge hoặc Local Queue)
        let sourceLabel = '';
        if (data.method === 'database_fallback') {
            sourceLabel = 'Database đã lưu (Khôi phục do tổng đài timeout)';
        } else if (data.source === 'database_local' || data.method === 'database') {
            sourceLabel = 'Database đã lưu (Tức thì)';
        } else if (data.source === 'elastic_direct') {
            sourceLabel = 'Tổng đài SMSC (Elasticsearch trực tiếp)';
        } else if (data.source === 'vhkt_bridge') {
            sourceLabel = 'Tổng đài SMSC (Cầu VHKT SFTP)';
        } else if (data.source === 'local_queue') {
            sourceLabel = 'Tổng đài SMSC (Hàng đợi Watcher .82)';
        } else {
            sourceLabel = data.source || 'Tổng đài SMSC';
        }
        if (sourceText) sourceText.innerText = `Nguồn: ${sourceLabel}`;
        if (sourceDot) sourceDot.style.background = (data.source === 'database_local' || data.method === 'database' || data.method === 'database_fallback') ? '#10b981' : '#0284c7';

        const records = data.records || [];
        lastCdrRecords = records;
        lastCdrPhone = cleanPhone;
        cdrFilterFailedOnly = false;
        cdrDirectionFilter = 'all';
        clearAllCdrDetailFilters(false);
        cdrCurrentPage = 1;
        updateCdrDirectionFilterUi();

        // Reset nút lọc tin lỗi
        const btnFilter = document.getElementById('btnFilterFailedOnly');
        if (btnFilter) {
            btnFilter.style.background = '#fee2e2';
            btnFilter.style.color = '#b91c1c';
            btnFilter.style.borderColor = '#fca5a5';
            btnFilter.innerHTML = `<span>Chỉ xem tin lỗi:</span> <span id="badgeFailedCount" style="background:#dc2626; color:#ffffff; padding:1px 6px; border-radius:10px; font-size:10px; font-weight:800;">0</span>`;
        }

        // QUY TẮC B: Gom nhóm theo CALL REFERENCE cho các bản ghi kết quả (loại bỏ 199C / Attempts = 000)
        const stats = calculateCdrGroupStats(records);

        // ĐỒNG BỘ NGAY VÀO DASHBOARD CHÍNH (CACHE, CỘT BẢNG & DRAWER CHI TIẾT)
        try {
            const causeMap = {};
            records.forEach(r => {
                if (!isCdrRecordIntermediate(r) && isCdrRecordFailed(r)) {
                    const cause = r.termination_cause_info || r.termination_cause || r.status_desc || 'Lỗi không xác định';
                    causeMap[cause] = (causeMap[cause] || 0) + 1;
                }
            });
            const topErrors = Object.entries(causeMap)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 3)
                .map(([cause, count]) => ({ cause, count }));

            const syncSummaryObj = {
                phone: cleanPhone,
                totalHits: data.total_hits || records.length,
                moCount: stats.moTotal,
                moOk: stats.moOk,
                moFail: stats.moFail,
                moRate: stats.moRate,
                mtCount: stats.mtTotal,
                mtOk: stats.mtOk,
                mtFail: stats.mtFail,
                mtRate: stats.mtRate,
                fromDate: fromDateVal,
                toDate: toDateVal,
                timeRangeDesc: timeRangeDesc || (fromDateVal && toDateVal ? `${fromDateVal} → ${toDateVal}` : 'Thời gian gần đây'),
                topErrors: topErrors,
                records: records
            };

            if (typeof window !== 'undefined') {
                window.smsCdrSummaryCache = window.smsCdrSummaryCache || {};
                window.smsCdrSummaryCache[cleanPhone] = syncSummaryObj;

                if (typeof cachedTickets !== 'undefined' && Array.isArray(cachedTickets)) {
                    cachedTickets.forEach(x => {
                        const xPhone = String(x.phone || '').trim().replace(/\D/g, '');
                        const cleanX = xPhone.startsWith('0') ? ('84' + xPhone.slice(1)) : ((!xPhone.startsWith('84') && xPhone.length === 9) ? ('84' + xPhone) : xPhone);
                        if (cleanX === cleanPhone) {
                            x.sms_cdr_summary = syncSummaryObj;
                        }
                    });
                }

                // Cập nhật ô tóm tắt trên bảng chính
                document.querySelectorAll(`[id^="sms-cdr-summary-"]`).forEach(el => {
                    if (el.id.includes(cleanPhone)) {
                        el.innerHTML = `
                            <div style="font-family:'JetBrains Mono', monospace; font-size:10.5px; line-height:1.35; text-align:center;">
                                <div style="color:${stats.moTotal === 0 ? '#64748b' : (stats.moRate >= 90 ? '#15803d' : '#b45309')}; font-weight:700;">
                                    MO: ${stats.moTotal} (${stats.moTotal > 0 ? stats.moRate + '%' : '--'})
                                </div>
                                <div style="color:${stats.mtTotal === 0 ? '#64748b' : (stats.mtRate >= 90 ? '#0369a1' : '#b45309')}; font-weight:700; margin-top:1px;">
                                    MT: ${stats.mtTotal} (${stats.mtTotal > 0 ? stats.mtRate + '%' : '--'})
                                </div>
                                <div style="margin-top:2px;">
                                    <a href="javascript:void(0)" onclick="openSmscCdrModal('${cleanPhone}', event)" style="font-size:10px; color:#0284c7; font-weight:700; text-decoration:underline;">
                                        Chi tiết (${records.length}) ↗
                                    </a>
                                </div>
                            </div>
                        `;
                    }
                });

                // Cập nhật trực tiếp vào thẻ chi tiết mở rộng trong Drawer
                document.querySelectorAll(`[id^="sms-cdr-detail-card-"]`).forEach(el => {
                    if (el.id.includes(cleanPhone)) {
                        const ticketKey = el.id.replace('sms-cdr-detail-card-', '');
                        if (typeof window.renderSmsCdrDetailContent === 'function') {
                            el.innerHTML = window.renderSmsCdrDetailContent(ticketKey, cleanPhone, '', '');
                        }
                    }
                });
            }
        } catch (exSync) {
            console.warn('Lỗi đồng bộ tóm tắt CDR về Dashboard:', exSync);
        }

        const kpiTotal = document.getElementById('kpiTotalCdr');
        const kpiMo = document.getElementById('kpiMoCdr');
        const kpiMt = document.getElementById('kpiMtCdr');
        const kpiSuccess = document.getElementById('kpiSuccessCdr');
        const kpiFailed = document.getElementById('kpiFailedCdr');
        const badgeFailed = document.getElementById('badgeFailedCount');
        const boxFilter = document.getElementById('boxFilterFailed');
        const kpiSection = document.getElementById('cdrKpiSection');
        const summaryText = document.getElementById('cdrQuerySummaryText');

        if (kpiTotal) {
            kpiTotal.innerText = (stats.intermediateCount > 0)
                ? `${stats.totalMsgs.toLocaleString()}`
                : `${stats.totalMsgs.toLocaleString()}`;
            kpiTotal.title = `Tổng số tin nhắn thực tế (gộp theo Call Reference): ${stats.totalMsgs}. Tổng số log CDR: ${records.length} (gồm ${stats.intermediateCount} log ghép mảnh).`;
        }
        if (kpiMo) {
            kpiMo.innerText = stats.moTotal.toLocaleString();
            kpiMo.title = `Tin gửi đi (MO): ${stats.moOk} thành công / ${stats.moTotal} tin (${stats.moRate}%)`;
        }
        if (kpiMt) {
            kpiMt.innerText = stats.mtTotal.toLocaleString();
            kpiMt.title = `Tin nhận đến (MT): ${stats.mtOk} thành công / ${stats.mtTotal} tin (${stats.mtRate}%)`;
        }
        if (kpiSuccess) kpiSuccess.innerText = `${stats.successRate}% (${stats.totalOk}/${stats.totalMsgs})`;
        if (kpiFailed) kpiFailed.innerText = stats.totalFail.toLocaleString();
        if (badgeFailed) badgeFailed.innerText = stats.failedLogCount;
        if (boxFilter) boxFilter.style.display = stats.failedLogCount > 0 ? 'inline-flex' : 'none';
        if (kpiSection) kpiSection.style.display = 'flex';
        const filterRow = document.getElementById('cdrFilterRow');
        if (filterRow) filterRow.style.display = (records.length > 0) ? 'flex' : 'none';

        if (summaryText) {
            const failedNotice = stats.totalFail > 0 ? `, <span style="color:#dc2626; font-weight:700;">(Phát hiện ${stats.totalFail} tin nhắn thất bại)</span>` : '';
            const interNotice = stats.intermediateCount > 0 ? ` <span style="color:#64748b; font-size:11px;">[Đã gộp ${stats.intermediateCount} log ghép mảnh tin dài]</span>` : '';
            summaryText.innerHTML = `Tìm thấy <b>${stats.totalMsgs}</b> tin nhắn thực tế (${records.length} bản ghi CDR) cho thuê bao <b>${escapeHtml(cleanPhone)}</b> (${escapeHtml(timeRangeDesc)}, Hệ thống: ${escapeHtml(sourceLabel)})${interNotice}${failedNotice}.`;
        }

        if (records.length === 0) {
            if (filterRow) filterRow.style.display = 'none';
            if (emptyState) {
                emptyState.style.display = 'block';
                emptyState.innerHTML = `Không có bản ghi tin nhắn SMSC nào phát sinh cho thuê bao <b>${escapeHtml(cleanPhone)}</b> trong khoảng ${escapeHtml(timeRangeDesc)}.`;
            }
            if (resultsTable) resultsTable.style.display = 'none';
            return;
        }

        renderCdrTable();

    } catch (err) {
        if (spinner) spinner.style.display = 'none';
        if (btnSubmit) {
            btnSubmit.disabled = false;
            btnSubmit.style.opacity = '1';
        }
        if (emptyState) {
            emptyState.style.display = 'block';
            emptyState.innerHTML = `<div style="color:#dc2626; font-weight:700;">⚠️ Lỗi kết nối API: ${escapeHtml(err.message)}</div>`;
        }
        if (sourceText) sourceText.innerText = 'Lỗi truy vấn';
        if (sourceDot) sourceDot.style.background = '#ef4444';
    }
}

// Tự động tải từ điển SMSC khi tải trang
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadSmsDictionaries);
    } else {
        loadSmsDictionaries();
    }
}

// ==========================================
// XUẤT NHẬT KÝ SMSC CDR RA FILE EXCEL (.XLSX)
// ==========================================
async function exportSmscCdrToExcel() {
    const phoneInp = document.getElementById('cdrPhoneInput');
    const phoneVal = (phoneInp && phoneInp.value) ? phoneInp.value.trim() : (lastCdrPhone || 'SMSC_CDR');

    let records = getFilteredCdrRecords();
    if (!records || records.length === 0) {
        records = lastCdrRecords || [];
    }

    if (!records || records.length === 0) {
        if (phoneVal && phoneVal !== 'SMSC_CDR') {
            let cleanP = String(phoneVal).trim().replace(/\D/g, '');
            if (cleanP.startsWith('0')) cleanP = '84' + cleanP.slice(1);
            if (!cleanP.startsWith('84') && cleanP.length === 9) cleanP = '84' + cleanP;
            window.location.href = `/api/cdr/export_excel?phone=${encodeURIComponent(cleanP)}`;
            return;
        }
        alert('Vui lòng nhập số thuê bao cần xuất nhật ký SMSC CDR.');
        return;
    }

    // Xác định mô tả dải thời gian
    let timeRangeDesc = '';
    const hiddenHours = document.getElementById('cdrHoursSelect');
    const hoursVal = hiddenHours ? hiddenHours.value : '24';
    if (hoursVal === 'custom') {
        const fDate = document.getElementById('cdrFromDate')?.value || '';
        const tDate = document.getElementById('cdrToDate')?.value || '';
        timeRangeDesc = (fDate && tDate) ? `${fDate} → ${tDate}` : 'Tùy chọn';
    } else {
        const mapH = { '24': '24h qua', '48': '48h qua', '168': '1 tuần qua', '720': '1 tháng qua' };
        timeRangeDesc = mapH[hoursVal] || `${hoursVal}h qua`;
    }

    if (cdrDirectionFilter === 'mo') {
        timeRangeDesc += ' (Lọc MO - Gửi đi)';
    } else if (cdrDirectionFilter === 'mt') {
        timeRangeDesc += ' (Lọc MT - Nhận đến)';
    }
    if (cdrFilterFailedOnly) {
        timeRangeDesc += ' [Chỉ bản tin lỗi]';
    }
    if (cdrFilterCalling) {
        timeRangeDesc += ` [Lọc Calling: ${cdrFilterCalling}]`;
    }
    if (cdrFilterCalled) {
        timeRangeDesc += ` [Lọc Called: ${cdrFilterCalled}]`;
    }

    // Làm giàu dữ liệu: bổ sung thông tin Service / Brandname cho từng bản ghi trước khi xuất
    const enrichedRecords = records.map(r => {
        let sName = '';
        try {
            const sInfo = lookupSmsServiceInfo(r.calling_number, r.called_number, phoneVal);
            if (sInfo && sInfo.title) {
                sName = sInfo.title;
            }
        } catch (e) {
            sName = '';
        }
        let fdaExcelName = 'FDA 26';
        const sUp = String(r.site || '26').toUpperCase();
        if (sUp.includes('204')) fdaExcelName = sUp.includes('(') ? r.site : 'FDA 204';
        else if (sUp.includes('235') || sUp.includes('NODE2') || sUp.includes('NODE 2') || sUp.includes('72.235')) fdaExcelName = sUp.includes('(') ? r.site : 'FDA 235';
        else fdaExcelName = sUp.includes('(') ? r.site : 'FDA 26';

        return {
            ...r,
            site: fdaExcelName,
            service_name: sName || r.brandname || r.service_info || '--'
        };
    });

    const btns = [
        document.getElementById('btnExportSmscCdrExcel'),
        document.getElementById('btnExportSmscCdrCsv'),
        ...document.querySelectorAll('button[onclick*="exportSmscCdrTo"]')
    ].filter(Boolean);

    btns.forEach(b => {
        b.disabled = true;
        b._origHtml = b.innerHTML;
        b.innerHTML = `<span>Đang xuất Excel...</span>`;
    });

    try {
        const res = await fetch('/api/cdr/export_excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                phone: phoneVal,
                time_range: timeRangeDesc,
                records: enrichedRecords
            })
        });

        if (!res.ok) {
            throw new Error(`Máy chủ trả về mã lỗi ${res.status}`);
        }

        const blob = await res.blob();
        let fileName = `SMSC_CDR_${phoneVal.replace(/\D/g, '') || 'REPORT'}.xlsx`;
        const disposition = res.headers.get('Content-Disposition');
        if (disposition && disposition.includes('filename=')) {
            const m = disposition.match(/filename=["']?([^"';]+)["']?/);
            if (m && m[1]) fileName = m[1];
        }

        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);

    } catch (err) {
        console.error('Lỗi khi xuất file Excel SMSC CDR:', err);
        alert('Lỗi xuất file Excel: ' + (err.message || 'Không thể tạo file'));
    } finally {
        btns.forEach(b => {
            b.disabled = false;
            if (b._origHtml) b.innerHTML = b._origHtml;
        });
    }
}
window.exportSmscCdrToExcel = exportSmscCdrToExcel;
window.exportSmscCdrToCsv = exportSmscCdrToExcel;

function exportCdrForPhone(phone, event) {
    if (event) event.stopPropagation();
    if (!phone) {
        alert('Không có thông tin số điện thoại để xuất Excel CDR.');
        return;
    }
    let cleanP = String(phone).trim().replace(/\D/g, '');
    if (cleanP.startsWith('0')) cleanP = '84' + cleanP.slice(1);
    if (!cleanP.startsWith('84') && cleanP.length === 9) cleanP = '84' + cleanP;
    
    // Tải file trực tiếp qua endpoint GET
    window.location.href = `/api/cdr/export_excel?phone=${encodeURIComponent(cleanP)}`;
}
window.exportCdrForPhone = exportCdrForPhone;

if (typeof window !== 'undefined') {
    window.onCdrFilterCallingChange = onCdrFilterCallingChange;
    window.onCdrFilterCalledChange = onCdrFilterCalledChange;
    window.clearCdrFilterCalling = clearCdrFilterCalling;
    window.clearCdrFilterCalled = clearCdrFilterCalled;
    window.clearAllCdrDetailFilters = clearAllCdrDetailFilters;
    window.applyCdrCallingFilter = applyCdrCallingFilter;
    window.applyCdrCalledFilter = applyCdrCalledFilter;
}

