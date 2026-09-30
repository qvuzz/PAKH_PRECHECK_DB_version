import requests

try:
    import browser_cookie3
except ImportError:
    browser_cookie3 = None


def _parse_loc_response(data):
    """
    Tách riêng phần parse JSON trả về từ API getAllNewLocApi thành dict kết quả chuẩn.
    Dùng chung cho cả 2 đường gọi API: session Chrome hoặc cookie Firefox.
    """
    result = {}

    # ==========================================================
    # LOC
    # ==========================================================
    loc = data.get('loc', {})
    if not isinstance(loc, dict):
        loc = {}

    result["MSISDN"] = loc.get('msisdn', '')
    result["Radio"] = loc.get('radioType', '')
    result["LAC"] = loc.get('lac', '')
    result["CI"] = loc.get('ci', '')
    result["eNodeB ID"] = loc.get('enodeB_ID', '')

    # ==========================================================
    # MME
    # ==========================================================
    mme = data.get('mme', {})
    if not isinstance(mme, dict):
        mme = {}

    mme_sub = mme.get('mmeSub', {})
    if not isinstance(mme_sub, dict):
        mme_sub = {}

    result["IMEI"] = str(mme_sub.get('IMEI', '')).strip()
    result["IPv4"] = str(mme_sub.get('IPv4_in_use', '')).strip()
    result["IPv6"] = str(mme_sub.get('IPv6_in_use', '')).strip()
    result["ECGI"] = str(mme_sub.get('ECGI', '')).strip()

    # ==========================================================
    # HSS
    # ==========================================================
    hss = data.get('hss', {})
    if not isinstance(hss, dict):
        hss = {}

    hss_sub = hss.get('hssSub', {})
    if not isinstance(hss_sub, dict):
        hss_sub = {}

    result["IMSI"] = hss_sub.get('imsi', '')
    result["MME Addr"] = hss_sub.get('mmeAddress', '')
    result["Location State"] = hss_sub.get('epsLocationState', '')
    result["Last Update"] = hss_sub.get('epsLastUpdateLocationDate', '')
    result["HSS Profile"] = hss_sub.get('epsProfileId', '')

    # ==========================================================
    # HLR
    # ==========================================================
    hlr = data.get('hlr', {})
    if not isinstance(hlr, dict):
        hlr = {}

    hlr_sub = hlr.get('hlrSub', {})
    if not isinstance(hlr_sub, dict):
        hlr_sub = {}

    result["State"] = hlr_sub.get('state', '')

    location_data = hlr_sub.get('locationData', {})
    if not isinstance(location_data, dict):
        location_data = {}

    result["VLR Addr"] = location_data.get('vlrAddress', '')

    # NAM: 0 = Mở GPRS, 1 = Bị khóa GPRS
    sud = hlr_sub.get('sud', {})
    if not isinstance(sud, dict):
        sud = {}
    nam_val = hlr_sub.get('nam')
    if nam_val is None:
        nam_val = sud.get('NAM')
    result["NAM"] = str(nam_val).strip() if nam_val is not None else ""

    # Sub State: MS PURGED, LOCATED, v.v.
    # 🎯 ƯU TIÊN KIỂM TRA MS PURGED / PURGED TỪ TẤT CẢ CÁC NGUỒN CỦA API
    is_purged = False
    hlr_sslo_sub = data.get('hlrSslo', {}).get('hlrSsloSub', {}) if isinstance(data.get('hlrSslo'), dict) else {}
    if "PURGED" in str(loc.get('subState', '')).upper():
        is_purged = True
    elif "PURGED" in str(hlr_sslo_sub.get('substate', '')).upper():
        is_purged = True
    elif str(location_data.get('msPurgedInVlr', '')).lower() == 'true':
        is_purged = True
    elif "PURGED" in str(hlr_sub.get('subState', '')).upper() or "PURGED" in str(hlr_sub.get('sub_state', '')).upper():
        is_purged = True

    if is_purged:
        sub_state_val = "MS PURGED"
    else:
        candidates = [
            loc.get('subState'),
            hlr_sslo_sub.get('substate'),
            hlr_sub.get('subState'),
            hlr_sub.get('sub_state'),
            hlr_sub.get('subscriberState'),
            location_data.get('subState'),
            location_data.get('subscriberState'),
            hss_sub.get('epsLocationState'),
            hlr_sub.get('state'),
            data.get('subState'),
            data.get('Sub State')
        ]
        sub_state_val = next(
            (str(c).strip() for c in candidates if c and str(c).strip().upper() not in ['', 'UNKNOWN', 'NONE', 'NULL']),
            hss_sub.get('epsLocationState') or hlr_sub.get('state') or 'UNKNOWN'
        )
    result["Sub State"] = str(sub_state_val).strip()

    # ==========================================================
    # BỔ SUNG THÔNG TIN CELL
    # ==========================================================
    result["CellID"] = result.get("CI", "")
    result["Cell ID"] = result.get("CI", "")

    # Bổ sung tên Cell từ hệ thống CustomerPosition (port 1708)
    phone_clean = str(result.get("MSISDN") or "").strip()
    if phone_clean:
        p84 = "84" + phone_clean[1:] if phone_clean.startswith("0") else phone_clean
        try:
            cp_resp = requests.get(
                f"http://127.0.0.1:1708/msisdn/{p84}",
                headers={"Accept": "application/json"},
                timeout=2.5
            )
            if cp_resp.status_code == 200:
                cp_data = cp_resp.json()
                c_name = (cp_data.get("summary") or {}).get("current_cell") or (cp_data.get("location") or {}).get("cell_name")
                if c_name:
                    result["CellName"] = c_name
                    result["cell_name"] = c_name
        except Exception:
            pass

    return result


def tra_cell_tu_so_dien_thoai(sdt, session=None):
    """
    Tra cứu thông tin thuê bao từ số điện thoại (MSISDN).

    session: requests.Session() ĐÃ CÓ SẴN cookie đăng nhập (ví dụ sapc_client.session,
             lấy từ Chrome qua CDP) - nếu truyền vào, ưu tiên dùng luôn session này để gọi
             API (không cần đọc cookie Firefox riêng nữa). Nếu không truyền, hoặc gọi bằng
             session đó bị lỗi (không phải JSON hợp lệ / không đăng nhập được), sẽ TỰ ĐỘNG
             rơi về cách cũ: đọc cookie từ Firefox (browser_cookie3.firefox).

    Trả về dictionary gồm:
        MSISDN
        Radio
        LAC
        CI
        eNodeB ID
        IMEI
        IPv4
        IPv6
        ECGI
        IMSI
        MME Addr
        Location State
        Last Update
        State
        VLR Addr

    Nếu có lỗi:
        {'error': 'Nội dung lỗi'}
    """
    sdt = str(sdt).strip()

    if not sdt:
        return {
            'error': 'Số điện thoại không được để trống.'
        }

    url = f'http://10.155.42.218/api/getAllNewLocApi/{sdt}'

    # ==========================================================
    # 🎯 THỬ TRƯỚC BẰNG SESSION CHROME (nếu có truyền vào)
    # Cùng domain 10.155.42.218 với API SAPC - nhiều khả năng dùng chung 1 session đăng nhập,
    # nên thử tận dụng lại, tránh phải phụ thuộc Firefox riêng.
    # ==========================================================
    if session is not None:
        try:
            res = session.get(url, timeout=10)
            if res.ok and "json" in res.headers.get("Content-Type", "").lower():
                data = res.json()
                if isinstance(data, dict):
                    return _parse_loc_response(data)
            print(f"⚠️ Session Chrome không dùng được cho API HSS/Cell (status={res.status_code}), "
                  f"tự động chuyển sang dùng cookie Firefox...")
        except Exception as e:
            print(f"⚠️ Lỗi khi thử session Chrome cho API HSS/Cell: {e}. Chuyển sang dùng cookie Firefox...")

    # ==========================================================
    # ĐỌC COOKIE TỪ CHROME EXTENSION (sapc_cookies.json / cookies.json)
    # ==========================================================
    cj = {}
    try:
        import os, json
        from pathlib import Path
        sapc_dir = Path(__file__).resolve().parent
        for fname in ["sapc_cookies.json", "cookies.json"]:
            cpath = sapc_dir / fname
            if cpath.exists():
                try:
                    with open(cpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                if item.get("name") and item.get("value"):
                                    cj[item["name"]] = item["value"]
                        elif isinstance(data, dict):
                            cj.update(data)
                    if cj:
                        break
                except Exception:
                    pass
    except Exception:
        pass

    # Nếu chưa có cookie từ Chrome, thử Firefox fallback
    if not cj:
        try:
            import sys
            from pathlib import Path
            root_dir = str(Path(__file__).resolve().parent.parent)
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)
            from auth_extractor import extract_firefox_cookies
            cj = extract_firefox_cookies("10.155.42")
            if not cj and browser_cookie3:
                try:
                    cj = browser_cookie3.firefox(domain_name='10.155.42.218')
                except Exception:
                    cj = {}
        except Exception:
            pass

    # ==========================================================
    # GỌI API
    # ==========================================================
    try:
        res = requests.get(
            url,
            cookies=cj,
            timeout=10
        )
    except requests.exceptions.Timeout:
        return {
            'error': 'Kết nối API quá thời gian chờ.'
        }

    except requests.exceptions.ConnectionError:
        return {
            'error': 'Không thể kết nối tới API.\n'
                     'Vui lòng kiểm tra mạng hoặc VPN.'
        }

    except requests.exceptions.RequestException as e:
        return {
            'error': f'Lỗi khi gọi API:\n{str(e)}'
        }

    # ==========================================================
    # KIỂM TRA HTTP STATUS
    # ==========================================================
    if not res.ok:
        return {
            'error': (
                f'Lỗi server: {res.status_code}\n'
                f'{res.text[:500]}'
            )
        }

    # ==========================================================
    # KIỂM TRA JSON
    # ==========================================================
    try:
        data = res.json()

    except ValueError:
        return {
            'error': (
                'Phản hồi không phải JSON hợp lệ.\n\n'
                + res.text[:1000]
            )
        }

    # ==========================================================
    # KIỂM TRA DATA
    # ==========================================================
    if not isinstance(data, dict):
        return {
            'error': 'Dữ liệu API trả về không đúng định dạng.'
        }

    # ==========================================================
    # PARSE KẾT QUẢ (dùng hàm chung)
    # ==========================================================
    return _parse_loc_response(data)


# ==============================================================
# TEST ĐỘC LẬP
# ==============================================================
if __name__ == "__main__":

    print("=" * 60)
    print("TRA CỨU CELL TỪ SỐ ĐIỆN THOẠI")
    print("=" * 60)

    sdt = input("Nhập số điện thoại (MSISDN): ").strip()

    result = tra_cell_tu_so_dien_thoai(sdt)

    print()
    print("-" * 60)

    if 'error' in result:
        print("LỖI:")
        print(result['error'])
    else:
        print("KẾT QUẢ TRA CỨU:")
        print()

        for key, value in result.items():
            print(f"{key}: {value}")

    print("-" * 60)