import time

def extract_btools_single_phone(driver, phone_84, start_d, end_d):
    query_url = (
        f"http://10.159.21.241:9267/B_tools_v2/data_view.jsp?"
        f"name={phone_84}&start_d={start_d}&end_d={end_d}&submit=T%C3%ACm+Ki%E1%BA%BFm"
    )
    
    print(f"🌐 Đang chuyển hướng dữ liệu BTools đến mục tiêu: {phone_84}")
    driver.get(query_url) # Thay thế hoàn toàn window.open giúp khóa cứng luồng xử lý
    
    # Chờ trang tải bảng dữ liệu (Tối đa 8 giây)
    table_loaded = False
    for _ in range(30):
        time.sleep(0.5)
        # Kiểm tra sự xuất hiện của bảng BTools đích thực
        has_table = driver.execute_script("""
            var tbl = document.querySelector('table');
            if(!tbl) return false;
            return tbl.innerText.toUpperCase().includes("RAT_TYPE") || tbl.innerText.toUpperCase().includes("MSISDN");
        """)
        if has_table:
            table_loaded = True
            break
            
    if not table_loaded:
        print(f"⚠️ Không tìm thấy bảng dữ liệu kỹ thuật hoặc thuê bao {phone_84} không có dữ liệu trên hệ thống.")
        return []

    # Script JS bóc tách chuẩn xác tuyệt đối các cột dữ liệu theo tiêu đề bảng
    btools_js_script = """
    var table = document.querySelector('table');
    if (!table) return null;
    
    var headers = table.querySelectorAll('thead th, tr:first-child th, tr:first-child td, tr th');
    var colIndices = { msisdn: -1, rat_type: -1, uplink: -1, downlink: -1, time: -1, service_id: -1 };
    
    headers.forEach(function(th, idx) {
        var text = (th.innerText || th.textContent || "").trim().toUpperCase();
        if (text === "MSISDN") colIndices.msisdn = idx;
        if (text === "RAT_TYPE") colIndices.rat_type = idx;
        if (text === "DATA_VOLUME_UPLINK") colIndices.uplink = idx;
        if (text === "DATA_VOLUME_DOWNLINK") colIndices.downlink = idx;
        if (text === "RECORD_OPENING_TIME") colIndices.time = idx;
        if (text === "SERVICE_ID") colIndices.service_id = idx;
    });

    var data_rows = [];
    var rows = table.querySelectorAll('tbody tr, tr');
    rows.forEach(function(row) {
        var cells = row.querySelectorAll('td');
        if (cells.length === 0 || cells.length <= Math.max(colIndices.msisdn, colIndices.time)) return;
        
        var firstCellText = (cells[0].innerText || cells[0].textContent || "").trim().toUpperCase();
        if (firstCellText === "MSISDN" || firstCellText.includes("DANH SÁCH") || firstCellText.includes("BƯỚC")) return;

        data_rows.push({
            "MSISDN": colIndices.msisdn !== -1 ? (cells[colIndices.msisdn].innerText || cells[colIndices.msisdn].textContent || "").trim() : "",
            "RAT_TYPE": colIndices.rat_type !== -1 ? (cells[colIndices.rat_type].innerText || cells[colIndices.rat_type].textContent || "").trim() : "",
            "DATA_VOLUME_UPLINK": colIndices.uplink !== -1 ? (cells[colIndices.uplink].innerText || cells[colIndices.uplink].textContent || "").trim() : "",
            "DATA_VOLUME_DOWNLINK": colIndices.downlink !== -1 ? (cells[colIndices.downlink].innerText || cells[colIndices.downlink].textContent || "").trim() : "",
            "RECORD_OPENING_TIME": colIndices.time !== -1 ? (cells[colIndices.time].innerText || cells[colIndices.time].textContent || "").trim() : "",
            "SERVICE_ID": colIndices.service_id !== -1 ? (cells[colIndices.service_id].innerText || cells[colIndices.service_id].textContent || "").trim() : ""
        });
    });
    return data_rows;
    """
    btools_data = driver.execute_script(btools_js_script)
    
    if btools_data:
        print(f"✅ Đã cào thành công {len(btools_data)} dòng dữ liệu kỹ thuật.")
    else:
        btools_data = []
    return btools_data