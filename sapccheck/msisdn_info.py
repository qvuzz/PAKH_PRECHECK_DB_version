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

    # ==========================================================
    # BỔ SUNG THÔNG TIN CELL
    # ==========================================================
    result["CellID"] = result.get("CI", "")
    result["Cell ID"] = result.get("CI", "")

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

    try:
        # ==========================================================
        # ĐỌC COOKIE FIREFOX
        # ==========================================================
        try:
            if browser_cookie3 is None:
                return {'error': 'Không có browser_cookie3 để đọc cookie Firefox dự phòng'}
            cj = browser_cookie3.firefox(
                domain_name='10.155.42.218'
            )
        except Exception as e:
            return {
                'error': f'Không đọc được cookie Firefox:\n{str(e)}'
            }

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

    except Exception as e:
        return {
            'error': f'Lỗi không xác định:\n{str(e)}'
        }


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