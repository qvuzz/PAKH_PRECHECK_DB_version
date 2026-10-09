// ==============================================================================
// MODULE ĐỊNH VỊ CELL BTS (PORT 1708) & QUẢN LÝ ĐỊA GIỚI HÀNH CHÍNH (GEO CELL)
// File: static/js/modules/geo_cell.js
// Nghiệp vụ: Tra cứu Cell BTS port 1708, Reverse Geocode 34 Tỉnh/TP mới,
//            Đối soát Phường/Xã TTS Mới vs CEM/Radio, Cập nhật nhanh địa bàn
// ==============================================================================

// Cache dữ liệu tra cứu Cell và Reverse Geocoding
const cellInfoClientCache = {};
const pendingCellLookups = new Set();
const cellLocationClientCache = {};
const pendingCellLocationLookups = new Set();

let ttsNewTicketBoundaryCache = {};
let pendingTtsBoundaryLookups = new Set();

let vnLocationsData = null;
let ttsNewProvincesCache = null;
let ttsNewWardsCache = {};
let currentProvinceWards = [];

function formatRadioCellHtml(radioVal, cellName) {
    if (!radioVal && !cellName) return '--';
    let r = radioVal || '4G';
    let c = cellName || '';
    if (!c && r.includes(',')) {
        const parts = r.split(',');
        r = parts[0].trim();
        c = parts.slice(1).join(',').trim();
    }
    if (c) {
        const cellUrl = `http://127.0.0.1:1708/cellid/${encodeURIComponent(c)}`;
        return `${escapeHtml(r)}, <a href="${cellUrl}" target="_blank" style="color:#0284c7; font-weight:700; text-decoration:underline;" title="Xem vị trí Cell ${escapeHtml(c)} trên bản đồ (CustomerPosition)">${escapeHtml(c)}</a>`;
    }
    return escapeHtml(r);
}

function renderRadioStatus(radioVal, ticketKey, phone) {
    let raw = (radioVal || '').trim();
    if (raw.includes(',')) {
        return formatRadioCellHtml(raw);
    }
    const cleanPhone = (phone || '').trim();
    if (cleanPhone && cellInfoClientCache[cleanPhone]) {
        const info = cellInfoClientCache[cleanPhone];
        return formatRadioCellHtml(raw || info.radio || '4G', info.cell_name);
    }
    if (cleanPhone) {
        triggerAsyncCellLookup(ticketKey, cleanPhone, raw);
    }
    return escapeHtml(raw || '--');
}

function renderRadioLocation(phone, ticketKey = '', incidentTime = '') {
    const cleanPhone = (phone || '').trim();
    if (!cleanPhone) return '';
    const info = cellInfoClientCache[cleanPhone];
    if (info && (info.ward || info.province || info.location_str)) {
        const loc = info.location_str || (info.ward && info.province ? `${info.ward}, ${info.province}` : (info.ward || info.province || ''));
        const wardVal = info.ward || loc;
        const quickWardBtn = wardVal ? `
            <button type="button" class="btn-quick-apply-ward" onclick="quickApplyWardFromCell('${escapeHtml(cleanPhone)}', '${escapeHtml(incidentTime || '')}', '${escapeHtml(ticketKey || '')}', '${escapeHtml(wardVal)}', '${escapeHtml(info.province || '')}', this, event)" style="margin-left:4px; display:inline-flex; align-items:center; justify-content:center; background:#eff6ff; border:1px solid #bfdbfe; border-radius:3px; padding:1px 5px; height:18px; cursor:pointer; color:#1d4ed8; transition:all 0.15s;" title="Cập nhật nhanh Phường/Xã (${escapeHtml(wardVal)}) vào Tóm tắt Nội dung & TTS Mới">
                <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
            </button>
        ` : '';
        const mapLink = info.map_url ? `
            <a href="${escapeHtml(info.map_url)}" target="_blank" rel="noopener noreferrer" style="font-size:9.5px; color:#2563eb; text-decoration:none; margin-left:3px; display:inline-flex; align-items:center; gap:2px; font-weight:600;" title="Mở tọa độ trạm trên Google Maps">
                <span>Bản đồ</span>
                <svg viewBox="0 0 24 24" width="8" height="8" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
            </a>
        ` : '';
        return `
            <div style="display:flex; align-items:center; gap:3px; margin-top:2px; color:#0f172a; flex-wrap:wrap;">
                <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="#0369a1" stroke-width="2" style="flex-shrink:0; margin-top:1px;"><path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                <span style="font-weight:600; color:#0f172a; font-size:10.5px;">${escapeHtml(loc)}</span>
                ${mapLink}
                ${quickWardBtn}
            </div>
        `;
    }
    // Nếu chưa có thông tin hoặc đang thiếu ward, kích hoạt truy vấn ngầm từ port 1708
    if (cleanPhone && ticketKey) {
        triggerAsyncCellLookup(ticketKey, cleanPhone, '');
    }
    return '';
}

async function triggerAsyncCellLookup(ticketKey, phone, currentRadio) {
    if (!phone || pendingCellLookups.has(phone)) return;
    pendingCellLookups.add(phone);
    try {
        const res = await fetch(`/api/cell_info/${encodeURIComponent(phone)}`);
        if (res.ok) {
            const data = await res.json();
            if (data && (data.success || data.cell_name || data.ward || data.province)) {
                cellInfoClientCache[phone] = data;
                const el = document.getElementById(`val-radio-${ticketKey}`);
                if (el && data.cell_name) {
                    el.innerHTML = formatRadioCellHtml(currentRadio || data.radio || '4G', data.cell_name);
                }
                const locEl = document.getElementById(`radio-loc-${ticketKey}`);
                if (locEl && (data.ward || data.province || data.location_str)) {
                    let t = (typeof cachedTickets !== 'undefined') ? cachedTickets.find((item, idx) => {
                        const key = (item.phone + '_' + (item.incident_time || item.ticket_code || idx)).replace(/[^a-zA-Z0-9]/g, '_');
                        return key === ticketKey;
                    }) : null;
                    const incTime = t ? t.incident_time : '';
                    locEl.innerHTML = renderRadioLocation(phone, ticketKey, incTime);
                }
                const compactEl = document.getElementById(`compact-radio-${ticketKey}`);
                if (compactEl && data.cell_name) {
                    compactEl.innerHTML = formatRadioCellHtml(currentRadio || data.radio || '4G', data.cell_name);
                }
                const compactLocEl = document.getElementById(`compact-radio-loc-${ticketKey}`);
                if (compactLocEl && (data.ward || data.province || data.location_str)) {
                    let t = (typeof cachedTickets !== 'undefined') ? cachedTickets.find((item, idx) => {
                        const key = (item.phone + '_' + (item.incident_time || item.ticket_code || idx)).replace(/[^a-zA-Z0-9]/g, '_');
                        return key === ticketKey;
                    }) : null;
                    const incTime = t ? t.incident_time : '';
                    const loc = data.location_str || (data.ward && data.province ? `${data.ward}, ${data.province}` : (data.ward || data.province || ''));
                    const wardVal = data.ward || loc;
                    const quickBtn = wardVal ? ` <button type="button" onclick="quickApplyWardFromCell('${escapeHtml(phone)}', '${escapeHtml(incTime)}', '${escapeHtml(ticketKey)}', '${escapeHtml(wardVal)}', '${escapeHtml(data.province || '')}', this, event)" style="background:transparent; border:none; cursor:pointer; font-size:10px; padding:0; line-height:1; vertical-align:middle; color:#1d4ed8;" title="Cập nhật nhanh Phường/Xã (${escapeHtml(wardVal)}) vào Tóm tắt Nội dung"><svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle;"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg></button>` : '';
                    compactLocEl.innerHTML = ` (${escapeHtml(loc)})${quickBtn}`;
                }
                updateSingleWardAudit(ticketKey);
            }
        }
    } catch (e) {
        // im lặng nếu không kết nối được
    } finally {
        pendingCellLookups.delete(phone);
    }
}

function extractTopCellFromCem(text) {
    if (!text) return null;
    const m = text.match(/•\s*([2345]G[-_][A-Za-z0-9_-]+)/i) || 
              text.match(/([2345]G[-_][A-Za-z0-9_-]+)/i) ||
              text.match(/•\s*([A-Za-z0-9_-]+):/);
    return m ? m[1].trim() : null;
}

function extractAllCellsFromCem(text) {
    if (!text || text.includes('Chưa quét theo ngày tiếp nhận') || text.includes('Không có dữ liệu')) return [];
    const matches = text.match(/[2345]G[-_][A-Za-z0-9_-]+/gi) || [];
    return Array.from(new Set(matches.map(c => c.trim())));
}

function normalizeVnLocation(text) {
    if (!text) return '';
    return text.toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/[đĐ]/g, 'd')
        .replace(/\b(phuong|xa|thi tran|quan|huyen|tp|tp\.|thanh pho|tinh|p\.|x\.|q\.)\b/g, '')
        .replace(/[^a-z0-9]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function renderCemIncidentLocation(ticketKey, rawCemIncident, phone = '', incidentTime = '') {
    const cellName = extractTopCellFromCem(rawCemIncident);
    if (!cellName) return '';

    if (cellLocationClientCache[cellName]) {
        const info = cellLocationClientCache[cellName];
        if (info && (info.ward || info.province || info.location_str)) {
            const locText = info.location_str || (info.ward + (info.ward && info.province ? ', ' : '') + info.province);
            const quickWardBtn = (info.ward || locText) ? `
                <button type="button" class="btn-quick-apply-ward" onclick="quickApplyWardFromCell('${escapeHtml(phone || '')}', '${escapeHtml(incidentTime || '')}', '${escapeHtml(ticketKey || '')}', '${escapeHtml(info.ward || locText)}', '${escapeHtml(info.province || '')}', this, event)" style="margin-left:4px; background:#eff6ff; border:1px solid #bfdbfe; border-radius:3px; padding:0 4px; font-size:11px; cursor:pointer; line-height:1.2; color:#1d4ed8; font-weight:700; transition:all 0.15s;" title="Cập nhật nhanh Phường/Xã (${escapeHtml(info.ward || locText)}) vào Tóm tắt Nội dung & TTS Mới">⬆️</button>
            ` : '';
            const mapLink = info.map_url ? `
                <a href="${escapeHtml(info.map_url)}" target="_blank" rel="noopener noreferrer" style="margin-left:4px; font-size:10px; color:#0284c7; font-weight:600; text-decoration:underline;" title="Xem vị trí Cell trên bản đồ Google Maps">Bản đồ</a>
            ` : '';
            return `
                <div style="display:flex; align-items:flex-start; gap:4px; margin-top:5px; padding-top:4px; border-top:1px dashed #cbd5e1; font-size:10.5px; color:#334155; line-height:1.35;">
                    <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="#0284c7" stroke-width="2" style="flex-shrink:0; margin-top:2px;"><path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                    <div>
                        <div style="display:flex; align-items:center; flex-wrap:wrap; gap:3px;">
                            <span style="font-weight:700; color:#0284c7;">Địa bàn Cell (${escapeHtml(cellName)}):</span>
                            ${quickWardBtn}
                            ${mapLink}
                        </div>
                        <div style="font-weight:600; color:#0f172a; margin-top:1px;">${escapeHtml(locText)}</div>
                    </div>
                </div>
            `;
        }
        return '';
    }

    triggerAsyncCellLocationLookup(ticketKey, cellName, phone);
    return `
        <div id="cem-incident-loc-spin-${ticketKey}" style="margin-top:5px; padding-top:4px; border-top:1px dashed #cbd5e1; font-size:10px; color:#64748b; font-style:italic; display:flex; align-items:center; gap:4px;">
            <span>Đang tra cứu địa bàn Cell ${escapeHtml(cellName)}...</span>
        </div>
    `;
}

async function triggerAsyncCellLocationLookup(ticketKey, cellName, phone = '') {
    if (!cellName || pendingCellLocationLookups.has(cellName)) return;
    pendingCellLocationLookups.add(cellName);
    try {
        let t = (typeof cachedTickets !== 'undefined') ? cachedTickets.find((item, idx) => {
            const key = (item.phone + '_' + (item.incident_time || item.ticket_code || idx)).replace(/[^a-zA-Z0-9]/g, '_');
            return key === ticketKey;
        }) : null;
        const targetPhone = phone || (t ? t.phone : '');
        const qParams = targetPhone ? `?phone=${encodeURIComponent(targetPhone)}` : '';
        const res = await fetch(`/api/cell_location/${encodeURIComponent(cellName)}${qParams}`);
        if (res.ok) {
            const data = await res.json();
            if (data && (data.ward || data.province || data.location_str)) {
                cellLocationClientCache[cellName] = data;
                const el = document.getElementById(`cem-incident-loc-${ticketKey}`);
                if (el) {
                    const phoneVal = t ? t.phone : targetPhone;
                    const incTime = t ? t.incident_time : '';
                    const locText = data.location_str || (data.ward + (data.ward && data.province ? ', ' : '') + data.province);
                    const quickWardBtn = (data.ward || locText) ? `
                        <button type="button" class="btn-quick-apply-ward" onclick="quickApplyWardFromCell('${escapeHtml(phoneVal)}', '${escapeHtml(incTime)}', '${escapeHtml(ticketKey)}', '${escapeHtml(data.ward || locText)}', '${escapeHtml(data.province || '')}', this, event)" style="margin-left:4px; background:#eff6ff; border:1px solid #bfdbfe; border-radius:3px; padding:0 4px; font-size:11px; cursor:pointer; line-height:1.2; color:#1d4ed8; font-weight:700; transition:all 0.15s;" title="Cập nhật nhanh Phường/Xã (${escapeHtml(data.ward || locText)}) vào Tóm tắt Nội dung & TTS Mới">⬆️</button>
                    ` : '';
                    const mapLink = data.map_url ? `
                        <a href="${escapeHtml(data.map_url)}" target="_blank" rel="noopener noreferrer" style="margin-left:4px; font-size:10px; color:#0284c7; font-weight:600; text-decoration:underline;" title="Xem vị trí Cell trên bản đồ Google Maps">Bản đồ</a>
                    ` : '';
                    el.innerHTML = `
                        <div style="display:flex; align-items:flex-start; gap:4px; margin-top:5px; padding-top:4px; border-top:1px dashed #cbd5e1; font-size:10.5px; color:#334155; line-height:1.35;">
                            <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="#0284c7" stroke-width="2" style="flex-shrink:0; margin-top:2px;"><path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z"></path><circle cx="12" cy="10" r="3"></circle></svg>
                            <div>
                                <div style="display:flex; align-items:center; flex-wrap:wrap; gap:3px;">
                                    <span style="font-weight:700; color:#0284c7;">Địa bàn Cell (${escapeHtml(cellName)}):</span>
                                    ${quickWardBtn}
                                    ${mapLink}
                                </div>
                                <div style="font-weight:600; color:#0f172a; margin-top:1px;">${escapeHtml(locText)}</div>
                            </div>
                        </div>
                    `;
                }

                updateAllWardAudits();
            } else {
                cellLocationClientCache[cellName] = { ward: '', province: '', location_str: '' };
                const spinEl = document.getElementById(`cem-incident-loc-spin-${ticketKey}`);
                if (spinEl) spinEl.remove();
            }
        }
    } catch (e) {
        // im lặng
    } finally {
        pendingCellLocationLookups.delete(cellName);
    }
}

async function triggerAsyncTicketBoundaryLookup(ticketId, ticketKey) {
    if (!ticketId || pendingTtsBoundaryLookups.has(ticketId)) return;
    pendingTtsBoundaryLookups.add(ticketId);
    try {
        const res = await fetch(`/api/tts_new/ticket_boundary/${ticketId}`);
        if (res.ok) {
            const data = await res.json();
            if (data && data.success) {
                ttsNewTicketBoundaryCache[ticketId] = data;
                updateSingleWardAudit(ticketKey);
            }
        }
    } catch (e) {
        // im lặng
    } finally {
        pendingTtsBoundaryLookups.delete(ticketId);
    }
}

function normalizeLocationString(str) {
    if (!str) return '';
    return str.toString()
        .toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/đ/g, 'd')
        .replace(/\b(phuong|xa|thi tran|quan|huyen|thi xa|thanh pho|tinh|tp\.|tp|p\.|x\.|p\d+)\b/gi, '')
        .replace(/[^a-z0-9]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function isLocationMatched(ttsWard, ttsProv, actualWard, actualProv) {
    const normTtsWard = normalizeLocationString(ttsWard);
    const normActWard = normalizeLocationString(actualWard);
    if (!normTtsWard || !normActWard) return false;

    // So sánh Phường/Xã: nếu trùng hoặc một bên chứa bên kia
    const wardMatched = normTtsWard === normActWard || normTtsWard.includes(normActWard) || normActWard.includes(normTtsWard);
    if (!wardMatched) return false;

    // Nếu cả hai đều có thông tin Tỉnh/TP thì kiểm tra tiếp Tỉnh/TP
    const normTtsProv = normalizeLocationString(ttsProv);
    const normActProv = normalizeLocationString(actualProv);
    if (normTtsProv && normActProv) {
        const isHcm1 = normTtsProv.includes('ho chi minh') || normTtsProv.includes('hcm') || normTtsProv.includes('sai gon');
        const isHcm2 = normActProv.includes('ho chi minh') || normActProv.includes('hcm') || normActProv.includes('sai gon');
        if (isHcm1 && isHcm2) return true;

        const isHn1 = normTtsProv.includes('ha noi') || normTtsProv.includes('hni');
        const isHn2 = normActProv.includes('ha noi') || normActProv.includes('hni');
        if (isHn1 && isHn2) return true;

        return normTtsProv === normActProv || normTtsProv.includes(normActProv) || normActProv.includes(normTtsProv);
    }

    return true;
}

function evaluateTicketWardStatus(t, ticketKey, rawCemIncident) {
    const isTtsNew = (t.source === 'tts_new');
    
    // Nếu là TTS Cũ: hiển thị chuỗi địa bàn sẵn có nếu có
    if (!isTtsNew) {
        const wardLocation = (t.ward || '').trim();
        return {
            status: 'TTS_OLD',
            badgeHtml: wardLocation ? `
                <div style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:4px; padding:3px 8px; margin-bottom:7px; display:flex; align-items:center; gap:5px;">
                    <span style="font-weight:700; font-size:10.5px; color:#475569; white-space:nowrap;">ĐỊA BÀN:</span>
                    <span id="display-ward-${ticketKey}" style="font-weight:600; font-size:11.5px; color:#475569; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(wardLocation)}">${escapeHtml(wardLocation)}</span>
                </div>
            ` : '',
            compactBadge: wardLocation ? `<span class="badge-status compact-ward-pill" style="background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; font-weight:700; font-size:9.5px; padding:1px 6px; max-width:none; width:fit-content; white-space:nowrap; margin-right:4px;">${escapeHtml(wardLocation)}</span>` : ''
        };
    }

    // Với TTS MỚI: CHỈ LẤY Phường/Xã + Tỉnh/TP theo ghi nhận trên TTS Mới (do VNP nhập qua dropdown)
    const ticketId = t.ticket_id ? Number(t.ticket_id) : 0;
    let ttsBoundary = ticketId && ttsNewTicketBoundaryCache[ticketId] ? ttsNewTicketBoundaryCache[ticketId] : null;

    // Ưu tiên nạp từ boundary cache OneOSS hoặc các trường boundary đã lưu trong DB
    let ttsProvinceId = ttsBoundary ? ttsBoundary.province_id : (t.province_id || null);
    let ttsProvinceName = ttsBoundary ? (ttsBoundary.province_name || '').trim() : (t.province_name || t.province || '').trim();
    let ttsWardId = ttsBoundary ? ttsBoundary.ward_id : (t.ward_id || null);
    let ttsWardName = ttsBoundary ? (ttsBoundary.ward_name || '').trim() : (t.ward_name || '').trim();

    // Nếu chưa có boundary cache và chưa có ward_name/province_name, gọi API OneOSS lấy thông tin dropdown
    if (!ttsBoundary && (!ttsProvinceName || !ttsWardName) && ticketId) {
        triggerAsyncTicketBoundaryLookup(ticketId, ticketKey);
        return {
            status: 'LOADING_TTS',
            badgeHtml: `
                <div id="ward-status-box-${ticketKey}" style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:4px; padding:4px 8px; margin-bottom:7px; display:flex; align-items:center; justify-content:space-between; gap:6px;">
                    <div style="display:flex; align-items:center; gap:5px; min-width:0; flex:1;">
                        <span style="font-weight:700; font-size:10.5px; color:#475569; white-space:nowrap;">ĐỊA BÀN:</span>
                        <span style="font-size:11px; color:#64748b; font-style:italic;">(Đang lấy dữ liệu từ TTS Mới...)</span>
                    </div>
                </div>
            `,
            compactBadge: `<span class="badge-status compact-ward-pill" style="background:#f1f5f9; color:#64748b; border:1px solid #cbd5e1; font-weight:700; font-size:9.5px; padding:1px 6px; max-width:none; width:fit-content; white-space:nowrap; margin-right:4px;">Đang tải P/Xã...</span>`
        };
    }

    // 1. Kiểm tra đã có Phường/Xã hay chưa
    const hasWard = Boolean(ttsWardName || (ttsWardId && Number(ttsWardId) > 0));
    // 2. Kiểm tra đã có Tỉnh/TP hay chưa
    const hasProvince = Boolean(ttsProvinceName || (ttsProvinceId && Number(ttsProvinceId) > 0));

    if (!hasProvince) {
        return {
            status: 'NO_PROVINCE',
            title: 'Chưa cập nhật Tỉnh/Tp',
            badgeHtml: `
                <div id="ward-status-box-${ticketKey}" style="background:#fff7ed; border:1px solid #fdba74; border-radius:4px; padding:4px 8px; margin-bottom:7px; display:flex; align-items:center; justify-content:space-between; gap:6px;">
                    <div style="display:flex; align-items:center; gap:5px; min-width:0; flex:1;">
                        <span style="font-weight:700; font-size:11px; color:#c2410c; white-space:nowrap;">Chưa cập nhật Tỉnh/Tp</span>
                    </div>
                    <button type="button" onclick="editTicketWard(event, '${escapeHtml(t.phone)}', '${escapeHtml(t.incident_time || '')}', '${ticketKey}')" style="display:inline-flex; align-items:center; gap:3px; font-size:10px; font-weight:700; color:#c2410c; background:#ffffff; border:1px solid #f97316; padding:1px 8px; border-radius:3px; cursor:pointer; white-space:nowrap;" title="Cập nhật Tỉnh/TP lên TTS Mới">
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                        Cập nhật
                    </button>
                </div>
            `,
            compactBadge: `<span class="badge-status compact-ward-pill" style="background:#fff7ed; color:#c2410c; border:1px solid #fdba74; font-weight:700; font-size:9.5px; padding:1px 6px; max-width:none; width:fit-content; white-space:nowrap; margin-right:4px;">Chưa có Tỉnh/TP</span>`
        };
    }

    if (!hasWard) {
        return {
            status: 'NO_WARD',
            title: 'Chưa cập nhật Phường/Xã',
            badgeHtml: `
                <div id="ward-status-box-${ticketKey}" style="background:#fff7ed; border:1px solid #fdba74; border-radius:4px; padding:4px 8px; margin-bottom:7px; display:flex; align-items:center; justify-content:space-between; gap:6px;">
                    <div style="display:flex; align-items:center; gap:5px; min-width:0; flex:1;">
                        <span style="font-weight:700; font-size:11px; color:#c2410c; white-space:nowrap;">Chưa cập nhật Phường/Xã</span>
                        <span style="font-size:10px; color:#9a3412; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">(${escapeHtml(ttsProvinceName)})</span>
                    </div>
                    <button type="button" onclick="editTicketWard(event, '${escapeHtml(t.phone)}', '${escapeHtml(t.incident_time || '')}', '${ticketKey}')" style="display:inline-flex; align-items:center; gap:3px; font-size:10px; font-weight:700; color:#c2410c; background:#ffffff; border:1px solid #f97316; padding:1px 8px; border-radius:3px; cursor:pointer; white-space:nowrap;" title="Cập nhật Phường/Xã lên TTS Mới">
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                        Cập nhật
                    </button>
                </div>
            `,
            compactBadge: `<span class="badge-status compact-ward-pill" style="background:#fff7ed; color:#c2410c; border:1px solid #fdba74; font-weight:700; font-size:9.5px; padding:1px 6px; max-width:none; width:fit-content; white-space:nowrap; margin-right:4px;">Chưa có P/Xã</span>`
        };
    }

    // 3. Đã có đầy đủ Phường/Xã + Tỉnh/TP trên TTS Mới
    const ttsDisplayText = `${ttsWardName}, ${ttsProvinceName}`;

    // Lấy tập hợp Phường/Xã + Tỉnh/TP từ CEM (ngày phản ánh), backup Radio Status ngày hiện tại nếu không có CEM
    const cemCells = extractAllCellsFromCem(rawCemIncident);
    let expectedWardsList = [];
    let isWaitingApi = false;

    if (cemCells.length > 0) {
        cemCells.forEach(cell => {
            if (cellLocationClientCache[cell]) {
                const info = cellLocationClientCache[cell];
                if (info && info.ward) {
                    expectedWardsList.push({
                        ward: info.ward,
                        province: info.province || '',
                        source: `CEM (${cell})`
                    });
                }
            } else {
                isWaitingApi = true;
                triggerAsyncCellLocationLookup(ticketKey, cell);
            }
        });
    }

    // Backup: Nếu CEM ngày phản ánh không có dữ liệu cell hoặc không lấy được ward, lấy từ Radio Status ngày hiện tại
    if (expectedWardsList.length === 0 && (!cemCells.length || !isWaitingApi)) {
        const phone = (t.phone || '').trim();
        if (cellInfoClientCache[phone]) {
            const info = cellInfoClientCache[phone];
            if (info && info.ward) {
                expectedWardsList.push({
                    ward: info.ward,
                    province: info.province || '',
                    source: `Radio Status (${info.cell_name || 'Hiện tại'})`
                });
            }
        } else if (phone) {
            isWaitingApi = true;
            triggerAsyncCellLookup(ticketKey, phone, '');
        }
    }

    // Nếu đang chờ API tra cứu từ 1708 (CEM hoặc Radio Status)
    if (isWaitingApi && expectedWardsList.length === 0) {
        return {
            status: 'CHECKING',
            badgeHtml: `
                <div id="ward-status-box-${ticketKey}" style="background:#f8fafc; border:1px solid #cbd5e1; border-radius:4px; padding:4px 8px; margin-bottom:7px; display:flex; align-items:center; justify-content:space-between; gap:6px;">
                    <div style="display:flex; align-items:center; gap:5px; min-width:0; flex:1;">
                        <span style="font-weight:700; font-size:10.5px; color:#475569; white-space:nowrap;">ĐỊA BÀN:</span>
                        <span id="display-ward-${ticketKey}" style="font-weight:600; font-size:11px; color:#0369a1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(ttsDisplayText)}">${escapeHtml(ttsDisplayText)}</span>
                        <span style="font-size:9.5px; color:#94a3b8; font-style:italic;">(Đang đối soát CEM/Profile...)</span>
                    </div>
                    <button type="button" onclick="editTicketWard(event, '${escapeHtml(t.phone)}', '${escapeHtml(t.incident_time || '')}', '${ticketKey}')" style="display:inline-flex; align-items:center; gap:3px; font-size:10px; font-weight:600; color:#0284c7; background:#ffffff; border:1px solid #bae6fd; padding:1px 6px; border-radius:3px; cursor:pointer; white-space:nowrap;">
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                        Sửa
                    </button>
                </div>
            `,
            compactBadge: `<span class="badge-status compact-ward-pill" style="background:#f1f5f9; color:#0369a1; border:1px solid #bae6fd; font-weight:700; font-size:9.5px; padding:1px 6px; max-width:none; width:fit-content; white-space:nowrap; margin-right:4px;">${escapeHtml(ttsDisplayText)}</span>`
        };
    }

    // Nếu không có dữ liệu đối soát từ cả CEM và Radio: hiển thị bình thường
    if (expectedWardsList.length === 0) {
        return {
            status: 'NO_AUDIT_DATA',
            badgeHtml: `
                <div id="ward-status-box-${ticketKey}" style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:4px; padding:4px 8px; margin-bottom:7px; display:flex; align-items:center; justify-content:space-between; gap:6px;">
                    <div style="display:flex; align-items:center; gap:5px; min-width:0; flex:1;">
                        <span style="font-weight:700; font-size:10.5px; color:#475569; white-space:nowrap;">ĐỊA BÀN:</span>
                        <span id="display-ward-${ticketKey}" style="font-weight:600; font-size:11.5px; color:#0369a1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(ttsDisplayText)}">${escapeHtml(ttsDisplayText)}</span>
                    </div>
                    <button type="button" onclick="editTicketWard(event, '${escapeHtml(t.phone)}', '${escapeHtml(t.incident_time || '')}', '${ticketKey}')" style="display:inline-flex; align-items:center; gap:3px; font-size:10px; font-weight:600; color:#0284c7; background:#ffffff; border:1px solid #bae6fd; padding:1px 6px; border-radius:3px; cursor:pointer; white-space:nowrap;">
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                        Sửa
                    </button>
                </div>
            `,
            compactBadge: `<span class="badge-status compact-ward-pill" style="background:#f1f5f9; color:#0369a1; border:1px solid #bae6fd; font-weight:700; font-size:9.5px; padding:1px 6px; max-width:none; width:fit-content; white-space:nowrap; margin-right:4px;">${escapeHtml(ttsDisplayText)}</span>`
        };
    }

    // So khớp TTS Mới với tập hợp trạm CEM / Radio: chỉ cần 1 trạm khớp thì là TRUE
    let isMatched = false;
    for (const item of expectedWardsList) {
        if (isLocationMatched(ttsWardName, ttsProvinceName, item.ward, item.province)) {
            isMatched = true;
            break;
        }
    }

    if (isMatched) {
        // Hợp lệ (Màu xanh)
        return {
            status: 'MATCHED',
            badgeHtml: `
                <div id="ward-status-box-${ticketKey}" style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:4px; padding:4px 8px; margin-bottom:7px; display:flex; align-items:center; justify-content:space-between; gap:6px;">
                    <div style="display:flex; align-items:center; gap:5px; min-width:0; flex:1;">
                        <span style="font-weight:700; font-size:10.5px; color:#15803d; white-space:nowrap;">ĐỊA BÀN:</span>
                        <span id="display-ward-${ticketKey}" style="font-weight:600; font-size:11.5px; color:#15803d; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(ttsDisplayText)}">${escapeHtml(ttsDisplayText)}</span>
                    </div>
                    <button type="button" onclick="editTicketWard(event, '${escapeHtml(t.phone)}', '${escapeHtml(t.incident_time || '')}', '${ticketKey}')" style="display:inline-flex; align-items:center; gap:3px; font-size:10px; font-weight:600; color:#15803d; background:#ffffff; border:1px solid #86efac; padding:1px 6px; border-radius:3px; cursor:pointer; white-space:nowrap;" title="Chỉnh sửa Phường/Xã, Tỉnh/TP và đồng bộ lên TTS Mới">
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                        Sửa
                    </button>
                </div>
            `,
            compactBadge: `<span class="badge-status compact-ward-pill" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0; font-weight:700; font-size:9.5px; padding:1px 6px; max-width:none; width:fit-content; white-space:nowrap; margin-right:4px;">${escapeHtml(ttsDisplayText)}</span>`
        };
    } else {
        // Sai khác (Màu đỏ)
        const actualNames = Array.from(new Set(expectedWardsList.map(it => it.ward + (it.province ? `, ${it.province}` : '')))).join(' | ');
        return {
            status: 'MISMATCH',
            title: 'Sai khác so với check CEM&PROFILE Status',
            badgeHtml: `
                <div id="ward-status-box-${ticketKey}" style="background:#fef2f2; border:1px solid #fca5a5; border-radius:4px; padding:4px 8px; margin-bottom:7px; display:flex; align-items:center; justify-content:space-between; gap:6px;">
                    <div style="display:flex; flex-direction:column; gap:1px; min-width:0; flex:1;">
                        <div style="display:flex; align-items:center; gap:5px;">
                            <span style="font-weight:700; font-size:11px; color:#b91c1c; white-space:nowrap;">Sai khác so với check CEM&PROFILE Status</span>
                        </div>
                        <div style="font-size:10px; color:#7f1d1d; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="TTS Mới: ${escapeHtml(ttsDisplayText)} | Trạm ghi nhận: ${escapeHtml(actualNames)}">
                            TTS Mới: <strong>${escapeHtml(ttsDisplayText)}</strong> | Trạm ghi nhận: <strong>${escapeHtml(actualNames)}</strong>
                        </div>
                    </div>
                    <button type="button" onclick="editTicketWard(event, '${escapeHtml(t.phone)}', '${escapeHtml(t.incident_time || '')}', '${ticketKey}')" style="display:inline-flex; align-items:center; gap:3px; font-size:10px; font-weight:700; color:#b91c1c; background:#ffffff; border:1px solid #ef4444; padding:2px 8px; border-radius:3px; cursor:pointer; white-space:nowrap;" title="Chỉnh sửa Phường/Xã cho đúng với dữ liệu CEM / Radio Status">
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                        Sửa
                    </button>
                </div>
            `,
            compactBadge: `<span class="badge-status compact-ward-pill" style="background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; font-weight:700; font-size:9.5px; padding:1px 6px; max-width:none; width:fit-content; white-space:nowrap; margin-right:4px;" title="Sai khác so với check CEM&PROFILE Status (Trạm: ${escapeHtml(actualNames)})">Sai khác CEM/Profile</span>`
        };
    }
}

function updateSingleWardAudit(ticketKey) {
    if (!ticketKey || typeof cachedTickets === 'undefined' || !Array.isArray(cachedTickets)) return;
    const box = document.getElementById(`ward-status-box-${ticketKey}`);
    const compactBadge = document.getElementById(`compact-ward-badge-${ticketKey}`);
    if (!box && !compactBadge) return;

    const t = cachedTickets.find((item, idx) => {
        const key = (item.phone + '_' + (item.incident_time || item.ticket_code || idx)).replace(/[^a-zA-Z0-9]/g, '_');
        return key === ticketKey;
    });
    if (!t || t.source !== 'tts_new') return;

    let rawCemIncident = (t.cem_data_incident || '').trim();
    if (!rawCemIncident && t.cem_data && t.cem_data !== '--') {
        const rawCem = t.cem_data.trim();
        if (rawCem.includes('[TIẾP NHẬN]') && rawCem.includes('[GẦN NHẤT]')) {
            const parts = rawCem.split('[GẦN NHẤT]');
            rawCemIncident = parts[0].replace('[TIẾP NHẬN]', '').trim();
        } else {
            rawCemIncident = 'Chưa quét theo ngày tiếp nhận (Bấm Tiền kiểm lại)';
        }
    }

    const audit = evaluateTicketWardStatus(t, ticketKey, rawCemIncident);
    if (box) {
        box.outerHTML = audit.badgeHtml;
    }
    if (compactBadge) {
        compactBadge.innerHTML = audit.compactBadge;
    }
}

let updateAllWardAuditsDebounceTimer = null;
function updateAllWardAudits() {
    if (updateAllWardAuditsDebounceTimer) {
        clearTimeout(updateAllWardAuditsDebounceTimer);
    }
    updateAllWardAuditsDebounceTimer = setTimeout(updateAllWardAuditsActual, 150);
}

function updateAllWardAuditsActual() {
    if (typeof cachedTickets === 'undefined' || !Array.isArray(cachedTickets) || cachedTickets.length === 0) return;
    cachedTickets.forEach((t, idx) => {
        if (t.source !== 'tts_new') return;
        const ticketKey = (t.phone + '_' + (t.incident_time || t.ticket_code || idx)).replace(/[^a-zA-Z0-9]/g, '_');
        const box = document.getElementById(`ward-status-box-${ticketKey}`);
        const compactBadge = document.getElementById(`compact-ward-badge-${ticketKey}`);
        if (!box && !compactBadge) return;

        let rawCemIncident = (t.cem_data_incident || '').trim();
        if (!rawCemIncident && t.cem_data && t.cem_data !== '--') {
            const rawCem = t.cem_data.trim();
            if (rawCem.includes('[TIẾP NHẬN]') && rawCem.includes('[GẦN NHẤT]')) {
                const parts = rawCem.split('[GẦN NHẤT]');
                rawCemIncident = parts[0].replace('[TIẾP NHẬN]', '').trim();
            } else {
                rawCemIncident = 'Chưa quét theo ngày tiếp nhận (Bấm Tiền kiểm lại)';
            }
        }

        const audit = evaluateTicketWardStatus(t, ticketKey, rawCemIncident);
        if (box) {
            box.outerHTML = audit.badgeHtml;
        }
        if (compactBadge) {
            compactBadge.innerHTML = audit.compactBadge;
        }
    });
}

// Nạp danh mục địa giới hành chính Việt Nam
async function loadVietnamLocationsData() {
    if (vnLocationsData && vnLocationsData.length > 0) return vnLocationsData;
    try {
        const res = await fetch('/static/js/vietnam_locations.json');
        if (res.ok) {
            vnLocationsData = await res.json();
            return vnLocationsData;
        }
    } catch (e) {
        console.error("Lỗi nạp danh mục địa giới hành chính:", e);
    }
    return [];
}

async function loadTtsNewProvinces() {
    if (ttsNewProvincesCache && ttsNewProvincesCache.length > 0) return ttsNewProvincesCache;
    try {
        const res = await fetch('/api/tts_new/locations/provinces');
        const data = await res.json();
        if (data.success && Array.isArray(data.data)) {
            ttsNewProvincesCache = data.data;
            return ttsNewProvincesCache;
        }
    } catch (e) {
        console.error("Lỗi tải danh mục Tỉnh/TP từ TTS Mới:", e);
    }
    return [];
}

async function loadTtsNewWards(provinceId) {
    if (!provinceId) return [];
    if (ttsNewWardsCache[provinceId]) return ttsNewWardsCache[provinceId];
    try {
        const res = await fetch(`/api/tts_new/locations/wards?province_id=${provinceId}`);
        const data = await res.json();
        if (data.success && Array.isArray(data.data)) {
            ttsNewWardsCache[provinceId] = data.data;
            return ttsNewWardsCache[provinceId];
        }
    } catch (e) {
        console.error(`Lỗi tải danh mục Phường/Xã cho tỉnh ${provinceId}:`, e);
    }
    return [];
}

async function editTicketWard(event, phone, incidentTime, ticketKey) {
    if (event) event.stopPropagation();
    openEditWardModal(phone, incidentTime, ticketKey);
}

async function openEditWardModal(phone, incidentTime, ticketKey) {
    const modal = document.getElementById('modalEditWard');
    if (!modal) return;

    const t = (typeof cachedTickets !== 'undefined') ? cachedTickets.find(item => item.phone === phone && (!incidentTime || item.incident_time === incidentTime)) : null;
    
    // Gán dữ liệu ẩn & hiển thị
    document.getElementById('editWardPhone').value = phone || '';
    document.getElementById('editWardIncidentTime').value = incidentTime || '';
    document.getElementById('editWardTicketKey').value = ticketKey || '';
    const elTid = document.getElementById('editWardTicketId');
    if (elTid) elTid.value = (t && t.ticket_id) ? t.ticket_id : '';
    
    document.getElementById('editWardPhoneDisplay').innerText = phone || '--';
    let cleanCode = (t && t.ticket_code) ? t.ticket_code.split('\n')[0].trim() : '--';
    document.getElementById('editWardCodeDisplay').innerText = cleanCode;
    
    const rawContent = (t && (t.ticket_content || t.content)) ? (t.ticket_content || t.content) : 'Không có nội dung phản ánh';
    document.getElementById('editWardRawContent').innerText = rawContent;

    // Reset các ô chọn
    const fieldSelect = document.getElementById('editWardFieldSelect');
    if (fieldSelect) {
        fieldSelect.innerHTML = '<option value="71" selected>Chất lượng mạng</option>';
    }
    const provSelect = document.getElementById('editWardProvinceSelect');
    provSelect.innerHTML = '<option value="">-- Đang tải danh sách Tỉnh/TP từ TTS Mới... --</option>';
    document.getElementById('editWardWardSelect').innerHTML = '<option value="">-- Chọn Phường / Xã --</option>';
    document.getElementById('filterWardSearch').value = '';
    document.getElementById('editWardDetailInput').value = 'null';
    document.getElementById('editWardPreviewText').innerText = '--';

    // Nạp danh mục Lĩnh vực từ OneOSS TTS Mới (mặc định Chất lượng mạng)
    if (fieldSelect) {
        try {
            fetch('/api/tts_new/fields').then(r => r.json()).then(fData => {
                if (fData && fData.data && fData.data.length > 0) {
                    fieldSelect.innerHTML = '';
                    fData.data.forEach(f => {
                        const opt = document.createElement('option');
                        opt.value = f.id;
                        opt.text = f.name;
                        if (f.id === 71) opt.selected = true;
                        fieldSelect.appendChild(opt);
                    });
                    if (knownBoundary && knownBoundary.field_id) {
                        fieldSelect.value = knownBoundary.field_id;
                    }
                }
            }).catch(() => {});
        } catch (e) {}
    }

    // Nạp dữ liệu Tỉnh/TP chuẩn sau sáp nhập từ OneOSS TTS Mới
    const provinces = await loadTtsNewProvinces();
    provSelect.innerHTML = '<option value="">-- Chọn Tỉnh / Thành phố --</option>';
    
    provinces.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.text = p.name;
        opt.setAttribute('data-code', p.code || '');
        provSelect.appendChild(opt);
    });

    // Ưu tiên nạp đúng Tỉnh/TP và Phường/Xã đang được lưu trên TTS Mới (do VNP chọn)
    const ticketId = (t && t.ticket_id) ? Number(t.ticket_id) : 0;
    let knownBoundary = ticketId && ttsNewTicketBoundaryCache[ticketId] ? ttsNewTicketBoundaryCache[ticketId] : null;
    if (!knownBoundary && ticketId && t && t.source === 'tts_new') {
        try {
            const bRes = await fetch(`/api/tts_new/ticket_boundary/${ticketId}`);
            if (bRes.ok) {
                const bData = await bRes.json();
                if (bData && bData.success) {
                    knownBoundary = bData;
                    ttsNewTicketBoundaryCache[ticketId] = bData;
                    if (fieldSelect && bData.field_id) {
                        fieldSelect.value = bData.field_id;
                    }
                }
            }
        } catch (e) {
            // im lặng
        }
    }

    if (knownBoundary && knownBoundary.province_id) {
        provSelect.value = knownBoundary.province_id;
        await populateWardsForProvinceId(knownBoundary.province_id, knownBoundary.ward_name);
        if (knownBoundary.ward_id) {
            document.getElementById('editWardWardSelect').value = knownBoundary.ward_id;
        }
    } else {
        // Fallback: Tự động nhận diện Tỉnh/TP từ gợi ý
        const currentWardStr = (t && t.ward) ? t.ward : '';
        const textToMatch = (currentWardStr + ' ' + rawContent).toLowerCase();

        let matchedProv = null;
        if (provinces && provinces.length > 0) {
            // Ưu tiên khớp tên tỉnh
            for (const p of provinces) {
                const pNameClean = (p.name || '').toLowerCase().replace('tỉnh ', '').replace('thành phố ', '').replace('tp ', '').replace('tp.', '').trim();
                if (pNameClean && textToMatch.includes(pNameClean)) {
                    matchedProv = p;
                    break;
                }
            }
            // Trường hợp đặc biệt TP.HCM
            if (!matchedProv && (textToMatch.includes('tphcm') || textToMatch.includes('tp.hcm') || textToMatch.includes('tp hcm') || textToMatch.includes('hcm') || textToMatch.includes('sài gòn'))) {
                matchedProv = provinces.find(p => (p.name || '').toLowerCase().includes('hồ chí minh') || p.code === 'HCM');
            }
            // Trường hợp Hà Nội
            if (!matchedProv && (textToMatch.includes('hà nội') || textToMatch.includes('ha noi') || textToMatch.includes('hni'))) {
                matchedProv = provinces.find(p => (p.name || '').toLowerCase().includes('hà nội') || p.code === 'HNI');
            }

            if (matchedProv) {
                provSelect.value = matchedProv.id;
                await populateWardsForProvinceId(matchedProv.id, currentWardStr || rawContent);
            }
        }
    }

    updateWardPreview();
    modal.style.display = 'flex';
}

async function populateWardsForProvinceId(provinceId, textHint = '') {
    const wardSelect = document.getElementById('editWardWardSelect');
    wardSelect.innerHTML = '<option value="">-- Đang tải danh mục Phường/Xã chuẩn sáp nhập... --</option>';
    currentProvinceWards = [];

    if (!provinceId) {
        wardSelect.innerHTML = '<option value="">-- Chọn Phường / Xã --</option>';
        return;
    }

    const wards = await loadTtsNewWards(provinceId);
    wardSelect.innerHTML = '<option value="">-- Chọn Phường / Xã --</option>';
    currentProvinceWards = wards || [];

    let foundOption = null;
    const cleanHint = (textHint || '').toLowerCase().trim();

    currentProvinceWards.forEach(w => {
        const opt = document.createElement('option');
        opt.value = w.id;
        opt.text = w.name;
        opt.setAttribute('data-name', w.name);
        opt.setAttribute('data-code', w.code || '');
        wardSelect.appendChild(opt);

        if (!foundOption && cleanHint) {
            const wClean = (w.name || '').toLowerCase().replace('phường ', '').replace('xã ', '').replace('thị trấn ', '').trim();
            if (wClean && (cleanHint.includes(wClean) || wClean.includes(cleanHint))) {
                foundOption = opt;
            }
        }
    });

    if (foundOption) {
        wardSelect.value = foundOption.value;
    }
}

function filterWardOptions(keyword) {
    const wardSelect = document.getElementById('editWardWardSelect');
    const kw = (keyword || '').toLowerCase().trim();

    if (!kw) {
        wardSelect.innerHTML = '<option value="">-- Chọn Phường / Xã --</option>';
        currentProvinceWards.forEach(w => {
            const opt = document.createElement('option');
            opt.value = w.id;
            opt.text = w.name;
            opt.setAttribute('data-name', w.name);
            wardSelect.appendChild(opt);
        });
        updateWardPreview();
        return;
    }

    wardSelect.innerHTML = '<option value="">-- Chọn Phường / Xã --</option>';
    const matched = currentProvinceWards.filter(item => 
        (item.name || '').toLowerCase().includes(kw) || 
        (item.code || '').toLowerCase().includes(kw)
    );

    matched.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.id;
        opt.text = item.name;
        opt.setAttribute('data-name', item.name);
        wardSelect.appendChild(opt);
    });

    if (matched.length > 0) {
        wardSelect.value = matched[0].id;
        updateWardPreview();
    }
}

async function onWardProvinceChange() {
    const pId = document.getElementById('editWardProvinceSelect').value;
    document.getElementById('filterWardSearch').value = '';
    await populateWardsForProvinceId(pId);
    updateWardPreview();
}

function onWardWardChange() {
    updateWardPreview();
}

function updateWardPreview() {
    const pSelect = document.getElementById('editWardProvinceSelect');
    const wSelect = document.getElementById('editWardWardSelect');
    const detailInp = document.getElementById('editWardDetailInput');
    let detail = detailInp ? (detailInp.value || '').trim() : '';
    if (!detail) {
        detail = 'null';
        if (detailInp) detailInp.value = 'null';
    }

    const pText = pSelect.selectedIndex > 0 ? pSelect.options[pSelect.selectedIndex].text : '';
    const wText = wSelect.selectedIndex > 0 ? wSelect.options[wSelect.selectedIndex].text : '';

    let outParts = [];
    if (detail) outParts.push(detail);
    if (wText) outParts.push(wText);
    if (pText) outParts.push(pText);

    const fullStr = outParts.join(', ');
    document.getElementById('editWardPreviewText').innerText = fullStr || '--';
    return fullStr;
}

function closeEditWardModal() {
    const modal = document.getElementById('modalEditWard');
    if (modal) modal.style.display = 'none';
}

async function submitEditWard() {
    const phone = document.getElementById('editWardPhone').value;
    const incidentTime = document.getElementById('editWardIncidentTime').value;
    const ticketKey = document.getElementById('editWardTicketKey').value;
    const ticketId = document.getElementById('editWardTicketId')?.value;
    const pSelect = document.getElementById('editWardProvinceSelect');
    const wSelect = document.getElementById('editWardWardSelect');
    const fSelect = document.getElementById('editWardFieldSelect');
    const detailInput = (document.getElementById('editWardDetailInput').value || '').trim() || 'null';

    const provinceId = pSelect.value;
    const wardId = wSelect.value;
    const fieldId = fSelect ? fSelect.value : 71;
    const finalAddress = updateWardPreview();

    if (!provinceId || !wardId) {
        alert("Vui lòng chọn Tỉnh/Thành phố và Phường/Xã!");
        return;
    }

    const btn = document.getElementById('btnSubmitEditWard');
    if (btn) {
        btn.disabled = true;
        btn.innerText = 'Đang lưu & đồng bộ...';
    }

    try {
        const ttsNewToken = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';
        const payload = {
            phone: phone,
            incident_time: incidentTime,
            ticket_key: ticketKey,
            ticket_id: ticketId ? parseInt(ticketId) : null,
            province_id: parseInt(provinceId),
            ward_id: parseInt(wardId),
            field_id: parseInt(fieldId || 71),
            province_name: pSelect.selectedIndex > 0 ? pSelect.options[pSelect.selectedIndex].text : '',
            ward_name: wSelect.selectedIndex > 0 ? wSelect.options[wSelect.selectedIndex].text : '',
            ward: finalAddress,
            address: detailInput || 'null',
            token: ttsNewToken
        };

        const res = await fetch('/api/tickets/update_ward', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.success) {
            const provName = pSelect.selectedIndex > 0 ? pSelect.options[pSelect.selectedIndex].text : '';
            const wardName = wSelect.selectedIndex > 0 ? wSelect.options[wSelect.selectedIndex].text : '';
            if (ticketId) {
                ttsNewTicketBoundaryCache[parseInt(ticketId)] = {
                    success: true,
                    ticket_id: parseInt(ticketId),
                    province_id: parseInt(provinceId),
                    province_name: provName,
                    ward_id: parseInt(wardId),
                    ward_name: wardName,
                    display_text: `${wardName}, ${provName}`
                };
            }
            const t = (typeof cachedTickets !== 'undefined') ? cachedTickets.find(item => item.phone === phone && (!incidentTime || item.incident_time === incidentTime)) : null;
            if (t) {
                t.ward = finalAddress;
                t.province_id = parseInt(provinceId);
                t.ward_id = parseInt(wardId);
                t.province = provName;
                if (t.ai_summary && t.ai_summary.includes('5. Khu vực xảy ra lỗi:')) {
                    t.ai_summary = t.ai_summary.replace(/5\.\s*Khu vực xảy ra lỗi:[^\n]*/g, `5. Khu vực xảy ra lỗi: Tại 1 khu vực (${finalAddress})`);
                }
            }
            closeEditWardModal();
            updateAllWardAudits();
            if (typeof lastTicketsSignature !== 'undefined') lastTicketsSignature = "";
            if (typeof renderTicketsTable === 'function') renderTicketsTable(true);
            alert(data.message || "Đã lưu và đồng bộ lên TTS Mới thành công!");
        } else {
            alert(data.message || "Không thể lưu địa bàn phản ánh. Vui lòng thử lại!");
        }
    } catch (e) {
        console.error("Lỗi submitEditWard:", e);
        alert("Đã xảy ra lỗi khi kết nối tới máy chủ.");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = 'Lưu & Đồng Bộ Lên TTS Mới';
        }
    }
}

async function quickApplyWardFromCell(phone, incidentTime, ticketKey, rawWard, rawProvince, btnElem, event) {
    if (event && event.stopPropagation) {
        event.stopPropagation();
    }

    let t = null;
    if (ticketKey && typeof cachedTickets !== 'undefined') {
        t = cachedTickets.find((item, idx) => {
            const key = (item.phone + '_' + (item.incident_time || item.ticket_code || idx)).replace(/[^a-zA-Z0-9]/g, '_');
            return key === ticketKey || item.phone === phone;
        });
    }
    if (!t && phone && typeof cachedTickets !== 'undefined') {
        t = cachedTickets.find(item => item.phone === phone && (!incidentTime || item.incident_time === incidentTime));
    }

    const cleanPhone = phone || (t ? t.phone : '');
    const cleanIncTime = incidentTime || (t ? t.incident_time : '');
    const ticketId = (t && t.ticket_id) ? parseInt(t.ticket_id) : null;

    if (!cleanPhone && !ticketId) {
        alert("Không xác định được phiếu để cập nhật.");
        return;
    }

    let origBtnHtml = '';
    if (btnElem) {
        origBtnHtml = btnElem.innerHTML;
        btnElem.disabled = true;
        btnElem.innerHTML = '⏳';
        btnElem.style.opacity = '0.7';
    }

    try {
        let wardStr = (rawWard || '').trim();
        let provStr = (rawProvince || '').trim();

        if (wardStr.includes(',') && !provStr) {
            const parts = wardStr.split(',').map(s => s.trim());
            wardStr = parts[0];
            provStr = parts[parts.length - 1];
        }

        const provinces = await loadTtsNewProvinces();
        let matchedProv = null;
        let matchedWard = null;

        const provClean = provStr.toLowerCase().replace(/^(tỉnh|thành phố|tp\.|tp)\s+/i, '').trim();
        const provNorm = normalizeLocationString(provStr);

        if (provinces && provinces.length > 0 && provNorm) {
            matchedProv = provinces.find(p => {
                if (p.code && p.code.toLowerCase() === provClean) return true;
                const pNorm = normalizeLocationString(p.name);
                return pNorm === provNorm || pNorm.includes(provNorm) || provNorm.includes(pNorm);
            });
            if (!matchedProv) {
                if (provNorm.includes('ho chi minh') || provNorm.includes('hcm') || provNorm.includes('sai gon')) {
                    matchedProv = provinces.find(p => (p.name || '').toLowerCase().includes('hồ chí minh') || p.code === 'HCM');
                } else if (provNorm.includes('ha noi') || provNorm.includes('hni')) {
                    matchedProv = provinces.find(p => (p.name || '').toLowerCase().includes('hà nội') || p.code === 'HNI');
                }
            }
        }

        if (!matchedProv && t) {
            const curPId = t.province_id || (ticketId && ttsNewTicketBoundaryCache[ticketId] ? ttsNewTicketBoundaryCache[ticketId].province_id : null);
            if (curPId && provinces) {
                matchedProv = provinces.find(p => p.id === curPId);
            }
        }

        const wardNorm = normalizeLocationString(wardStr);
        if (matchedProv && wardNorm) {
            const wards = await loadTtsNewWards(matchedProv.id);
            if (wards && wards.length > 0) {
                matchedWard = wards.find(w => {
                    const wNorm = normalizeLocationString(w.name);
                    return wNorm === wardNorm || wNorm.includes(wardNorm) || wardNorm.includes(wNorm);
                });
            }
        }

        const finalProvName = matchedProv ? matchedProv.name : provStr;
        const finalWardName = matchedWard ? matchedWard.name : wardStr;
        const finalDisplayAddress = finalProvName ? `${finalWardName}, ${finalProvName}` : finalWardName;

        const ttsNewToken = (typeof getTtsNewAuthToken === 'function') ? getTtsNewAuthToken() : '';
        const payload = {
            phone: cleanPhone,
            incident_time: cleanIncTime,
            ticket_key: ticketKey || (t ? t.ticket_code : ''),
            ticket_id: ticketId,
            province_id: matchedProv ? parseInt(matchedProv.id) : null,
            ward_id: matchedWard ? parseInt(matchedWard.id) : null,
            field_id: 71, // Chất lượng mạng
            province_name: finalProvName,
            ward_name: finalWardName,
            ward: finalDisplayAddress,
            address: finalDisplayAddress,
            token: ttsNewToken
        };

        const res = await fetch('/api/tickets/update_ward', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.message || 'Lỗi cập nhật địa bàn lên hệ thống OneOSS TTS Mới');
        }

        if (t) {
            t.ward = finalDisplayAddress;
            if (matchedProv) {
                t.province_id = parseInt(matchedProv.id);
                t.province = finalProvName;
            }
            if (matchedWard) {
                t.ward_id = parseInt(matchedWard.id);
                t.ward_name = finalWardName;
            }

            if (t.ai_summary) {
                let updatedSummary = t.ai_summary;
                if (/5\.\s*khu vực(?: xảy ra lỗi)?\s*:[^\n]*/i.test(updatedSummary)) {
                    updatedSummary = updatedSummary.replace(/5\.\s*khu vực(?: xảy ra lỗi)?\s*:[^\n]*/gi, `5. Khu vực xảy ra lỗi: Chỉ ở 1 khu vực (${finalDisplayAddress})`);
                } else {
                    updatedSummary += `\n5. Khu vực xảy ra lỗi: Chỉ ở 1 khu vực (${finalDisplayAddress})`;
                }
                t.ai_summary = updatedSummary;

                fetch('/api/tickets/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        phone: cleanPhone,
                        incident_time: cleanIncTime,
                        field: 'ai_summary',
                        value: updatedSummary
                    })
                }).catch(() => {});
            }

            if (ticketId) {
                ttsNewTicketBoundaryCache[ticketId] = {
                    success: true,
                    ticket_id: ticketId,
                    province_id: matchedProv ? parseInt(matchedProv.id) : null,
                    province_name: finalProvName,
                    ward_id: matchedWard ? parseInt(matchedWard.id) : null,
                    ward_name: finalWardName,
                    display_text: finalDisplayAddress
                };
            }
        }

        updateAllWardAudits();
        if (typeof lastTicketsSignature !== 'undefined') lastTicketsSignature = "";
        if (typeof renderTicketsTable === 'function') renderTicketsTable(true);

        if (btnElem) {
            btnElem.innerHTML = '✅';
            setTimeout(() => {
                btnElem.disabled = false;
                btnElem.innerHTML = origBtnHtml || '⬆️';
                btnElem.style.opacity = '1';
            }, 1800);
        }

    } catch (err) {
        console.error("Lỗi quickApplyWardFromCell:", err);
        alert("Lỗi khi cập nhật nhanh phường xã: " + err.message);
        if (btnElem) {
            btnElem.disabled = false;
            btnElem.innerHTML = origBtnHtml || '⬆️';
            btnElem.style.opacity = '1';
        }
    }
}
