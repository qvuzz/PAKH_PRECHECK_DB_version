# ttsnew_api.py
# Module tích hợp REST API cho hệ thống TTS Mới (tts.vnptnet.vn / gw-oneoss.vnpt.vn)

import os
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOKEN_CACHE_FILE = BASE_DIR / "ttsnew_token_cache.json"

API_BASE_URL = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/Ticket"

# Danh sách từ khóa phân loại dịch vụ Data / Mobile Internet
DATA_SERVICE_KEYWORDS = [
    "mobile internet",
    "data",
    "4g",
    "3g",
    "5g",
    "truy cập internet",
    "chất lượng mạng ảnh hưởng đến truy cập",
]


def save_cached_token(token: str):
    """Lưu token vào file cache để tái sử dụng."""
    try:
        data = {"token": token, "updated_at": time.time()}
        with open(TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def get_cached_token() -> str:
    """Đọc token từ file cache nếu còn hiệu lực."""
    if TOKEN_CACHE_FILE.exists():
        try:
            with open(TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("token", "")
        except Exception:
            pass
    return ""


def extract_token_from_browser(driver=None) -> str:
    """
    Trích xuất token trực tiếp từ trình duyệt Chrome (tab tts.vnptnet.vn).
    Hỗ trợ cả Selenium driver truyền vào lẫn Playwright CDP fallback.
    """
    token = ""

    # 1. Ưu tiên đọc từ cache nếu đã có token
    token = get_cached_token()
    if token:
        if not token.startswith("Bearer "):
            token = "Bearer " + token
        return token

    # 2. Đọc ngầm qua Playwright CDP tới port 9222 (không chuyển tab, không nhảy cửa sổ)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            for page in browser.contexts[0].pages:
                if "tts.vnptnet.vn" in page.url.lower():
                    token = page.evaluate("() => localStorage.getItem('TOKEN')")
                    if token:
                        break
    except Exception:
        pass

    # 3. Fallback qua Selenium driver nếu không dùng được CDP
    if not token and driver:
        try:
            current_handle = driver.current_window_handle
            for handle in driver.window_handles:
                try:
                    driver.switch_to.window(handle)
                    if "tts.vnptnet.vn" in driver.current_url.lower():
                        token = driver.execute_script("return localStorage.getItem('TOKEN');")
                        if token:
                            break
                except Exception:
                    pass
            try:
                driver.switch_to.window(current_handle)
            except Exception:
                pass
        except Exception:
            pass

    if token:
        if not token.startswith("Bearer "):
            token = "Bearer " + token
        save_cached_token(token)

    return token


def make_api_request(url: str, token: str, timeout: int = 15) -> dict:
    """Gửi request HTTP GET tới API gw-oneoss."""
    if not token.startswith("Bearer "):
        token = "Bearer " + token

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": token,
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def fetch_active_tickets(token: str, limit: int = 1000, offset: int = 0) -> list:
    """
    Lấy danh sách phiếu đang xử lý từ TTS Mới (ticketFlowStatusId=2: Đang xử lý).
    """
    url = f"{API_BASE_URL}/get-list?limit={limit}&offset={offset}&ticketFlowStatusId=2"
    resp = make_api_request(url, token)
    if resp.get("isError"):
        raise RuntimeError(f"Lỗi API get-list: {resp.get('message')}")
    return resp.get("data", [])


def filter_data_tickets(raw_tickets: list) -> list:
    """
    Lọc danh sách các phiếu thuộc dịch vụ Mobile Internet / Data theo yêu cầu:
    Chỉ tác động vào các phiếu có đồng thời 2 trường:
    1. processDefinitionName == "2.4_QT_CLM_02"
    2. stepName chứa "2.4" và "dịch vụ data" (ví dụ: "2.4 Đánh giá kết quả xử lý PAKH dịch vụ Data")
    """
    filtered = []
    for it in raw_tickets:
        proc = str(it.get("processDefinitionName") or "").strip()
        step = str(it.get("stepName") or "").strip()
        if proc == "2.4_QT_CLM_02" and ("2.4" in step and "dịch vụ data" in step.lower()):
            filtered.append(it)
    return filtered


def filter_non_data_tickets(raw_tickets: list) -> list:
    """
    Lọc danh sách các phiếu NGOÀI Mobile Internet (Thoại, SMS, Gói cước, Sóng...).
    """
    filtered = []
    for it in raw_tickets:
        title = (it.get("title") or "").strip()
        title_lower = title.lower()

        # Gói cước Mobile Internet được tính vào nhóm ngoài data thuần
        if "gói cước mobile internet" in title_lower:
            filtered.append(it)
            continue

        is_data = any(k in title_lower for k in DATA_SERVICE_KEYWORDS)
        if not is_data:
            filtered.append(it)
    return filtered


def enrich_ticket_customer(it: dict, token: str) -> dict:
    """
    Gọi API get-customer-by-ticketflowid để lấy SĐT, tên khách hàng và hạng hội viên.
    Tạm đưa chung 2 trường Tên quy trình và Tên bước vào ticket_code.
    """
    flow_id = it.get("id")
    proc_name = str(it.get("processDefinitionName") or "").strip()
    step_name = str(it.get("stepName") or "").strip()
    raw_code = str(it.get("ticketCode") or "").strip()

    # Tạm đưa chung vào cột Mã phiếu 2 trường này theo yêu cầu của người dùng
    if proc_name or step_name:
        combined_code = f"{raw_code}\n[{proc_name}]\n{step_name}"
    else:
        combined_code = raw_code

    url = f"{API_BASE_URL}/get-customer-by-ticketflowid/{flow_id}"
    try:
        resp = make_api_request(url, token, timeout=10)
        cust = resp.get("data") or {}
        raw_phone = str(cust.get("phone") or cust.get("contactPhone") or "").strip()

        # Chuẩn hóa SĐT về dạng 84xxxxxxxxx
        phone = normalize_phone_number(raw_phone)

        return {
            "flow_id": flow_id,
            "ticket_id": it.get("ticketId"),
            "ticket_code": combined_code,
            "raw_ticket_code": raw_code,
            "process_name": proc_name,
            "step_name": step_name,
            "phone": phone,
            "raw_phone": raw_phone,
            "customer_name": cust.get("name", ""),
            "customer_level": cust.get("clMemberLevelName", ""),
            "title": it.get("title", ""),
            "content": it.get("content", ""),
            "incident_time": it.get("incidentDate", "") or it.get("requestDate", ""),
            "created_time": it.get("requestDate", ""),
            "assigned_unit": it.get("assignedUnitName", ""),
            "source": "tts_new",
        }
    except Exception as e:
        return {
            "flow_id": flow_id,
            "ticket_id": it.get("ticketId"),
            "ticket_code": combined_code,
            "raw_ticket_code": raw_code,
            "process_name": proc_name,
            "step_name": step_name,
            "phone": "",
            "raw_phone": "",
            "customer_name": "",
            "customer_level": "",
            "title": it.get("title", ""),
            "content": it.get("content", ""),
            "incident_time": it.get("incidentDate", "") or it.get("requestDate", ""),
            "created_time": it.get("requestDate", ""),
            "assigned_unit": it.get("assignedUnitName", ""),
            "source": "tts_new",
            "error": str(e),
        }


def normalize_phone_number(phone_str: str) -> str:
    """Chuẩn hóa số điện thoại thành format 84xxxxxxxxx để tra cứu Core."""
    import re
    digits = re.sub(r"\D", "", phone_str)
    if digits.startswith("0") and len(digits) >= 10:
        return "84" + digits[1:]
    if digits.startswith("84") and len(digits) >= 11:
        return digits
    if len(digits) == 9:
        return "84" + digits
    return digits


def get_ttsnew_tickets_for_precheck(driver=None, max_workers: int = 8, service_type: str = "data") -> tuple:
    """
    Hàm tổng hợp dành cho quy trình tiền kiểm:
    1. Lấy token hợp lệ.
    2. Kéo danh sách phiếu đang xử lý từ TTS Mới.
    3. Lọc theo nhóm dịch vụ (data: Mobile Internet, voice_sms: Thoại/SMS/Gói, all: Tất cả).
    4. Bóc tách song song SĐT khách hàng.
    5. Trả về: (danh_sách_phiếu_hợp_lệ, tổng_số_phiếu_quét)
    """
    token = extract_token_from_browser(driver)
    if not token:
        raise ValueError("Không tìm thấy Bearer Token của TTS Mới. Hãy chắc chắn bạn đã mở và đăng nhập tab https://tts.vnptnet.vn trên Chrome.")

    raw_tickets = fetch_active_tickets(token, limit=1000)
    if service_type == "data":
        target_tickets = filter_data_tickets(raw_tickets)
    elif service_type == "voice_sms":
        target_tickets = filter_non_data_tickets(raw_tickets)
    else:
        target_tickets = raw_tickets

    if not target_tickets:
        return [], len(raw_tickets)

    # Lấy thông tin khách hàng & SĐT song song
    enriched = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(enrich_ticket_customer, it, token) for it in target_tickets]
        for f in futures:
            try:
                res = f.result()
                if res.get("phone"):
                    enriched.append(res)
            except Exception:
                pass

    return enriched, len(raw_tickets)


def api_transfer_ttsnew_ticket(token: str, ticket_flow_id: int, ticket_id: int,
                               phone: str = "", ticket_code: str = "",
                               status: str = "", closing_content: str = "", 
                               assign_content: str = "") -> dict:
    """
    Thực hiện chuyển bước / đóng phiếu tự động trên hệ thống TTS Mới qua OneOSS REST API theo quy trình 2 vòng:
    - Vòng 1: Chọn bước "2.4 Đánh giá kết quả xử lý PAKH dịch vụ Data (SOC2)", Đơn vị: Tổ Dịch vụ.
              Sau khi đóng vòng 1 -> lưu cache / DB chờ vòng 2.
    - Vòng 2: Khi phiếu xuất hiện lần 2:
              + Nếu status là BÌNH THƯỜNG hoặc THEO DÕI THÊM -> Chọn bước "2.6 Đóng phiếu Trên TTS".
              + Các trường hợp khác -> Chọn bước "5.1" (Xây dựng PA xử lý) và đóng.
    """
    if not token.startswith("Bearer "):
        token = "Bearer " + token

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Authorization": token,
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        # 1. Lấy thông tin các node quy trình
        url_step = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/get-next-step?ticketFlowId={ticket_flow_id}"
        res_step = requests.get(url_step, headers=headers, timeout=12).json()
        if res_step.get("isError"):
            return {"success": False, "message": res_step.get("message", "Lỗi lấy bước kế tiếp")}

        step_data = res_step.get("data", {})
        curr_node = step_data.get("currentNodes", [{}])[0]
        next_node_list = step_data.get("nextNodeData", [])
        if not next_node_list:
            return {"success": False, "message": "Không tìm thấy danh sách bước kế tiếp (nextNodeData rỗng)"}

        # 2. Xác định vòng xử lý (Round 1 hay Round 2)
        # Vòng 1: Có bước chứa '2.4' và 'SOC2'
        node_soc2 = next((n for n in next_node_list if "2.4" in str(n.get("name", "")) and "soc2" in str(n.get("name", "")).lower()), None)

        chosen_node = None
        round_num = 1
        action_label = ""

        if node_soc2:
            # ---> VÒNG 1: Chọn 2.4 ... SOC2
            round_num = 1
            chosen_node = node_soc2
            action_label = f"Vòng 1: Chuyển bước '{chosen_node.get('name')}' (Tổ Dịch vụ)"
        else:
            # ---> VÒNG 2: Xuất hiện lần 2
            round_num = 2
            st_upper = (status or "").upper()
            is_normal_case = (
                "BÌNH THƯỜNG" in st_upper or 
                "BINH THUONG" in st_upper or 
                "THEO DÕI THÊM" in st_upper or 
                "THEO DOI THEM" in st_upper
            )

            if is_normal_case:
                # Tìm bước 2.6 Đóng phiếu Trên TTS
                chosen_node = next((n for n in next_node_list if "2.6" in str(n.get("name", "")) or str(n.get("processData", {}).get("stepCode", "")) == "2.6"), None)
                if not chosen_node:
                    chosen_node = next((n for n in next_node_list if "đóng phiếu" in str(n.get("name", "")).lower()), None)
                action_label = f"Vòng 2 (Bình thường / Theo dõi): Chuyển bước '{chosen_node.get('name') if chosen_node else '2.6'}' để đóng phiếu"
            else:
                # Các trường hợp khác: Chọn bước 5.1
                chosen_node = next((n for n in next_node_list if "5.1" in str(n.get("name", "")) or str(n.get("processData", {}).get("stepCode", "")).startswith("5.1")), None)
                if not chosen_node:
                    chosen_node = next((n for n in next_node_list if "xây dựng pa" in str(n.get("name", "")).lower() or "phương án" in str(n.get("name", "")).lower()), None)
                action_label = f"Vòng 2 (Sự cố / Kém sóng): Chuyển bước '{chosen_node.get('name') if chosen_node else '5.1'}'"

        if not chosen_node:
            available_names = [n.get("name") for n in next_node_list]
            return {
                "success": False, 
                "message": f"Không tìm thấy node phù hợp cho Vòng {round_num}. Các bước có sẵn: {available_names}"
            }

        # 3. Lấy đơn vị phụ trách theo MSC
        cl_unit_id = 418
        try:
            url_msc = f"https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/CfUnitTypeUnit/get-by-msc?ticketId={ticket_id}"
            res_msc = requests.get(url_msc, headers=headers, timeout=10).json()
            if not res_msc.get("isError") and res_msc.get("data"):
                cl_unit_id = res_msc["data"][0].get("clUnitId", 418)
        except Exception:
            pass

        # 4. Đóng gói Payload
        form_id = chosen_node.get("processData", {}).get("formId") or curr_node.get("processData", {}).get("formId")
        payload = {
            "ticketFlowId": ticket_flow_id,
            "ticketId": ticket_id,
            "formId": form_id,
            "processNodeInstanceId": curr_node.get("id"),
            "processDefinitionId": step_data.get("processInstanceId"),
            "closingContent": closing_content,
            "assignContent": assign_content,
            "columnJson": {"formId": form_id} if form_id else {},
            "newTicketFlow": {
                "ticketFlowParentId": ticket_flow_id,
                "processDefinitionId": chosen_node.get("processInstanceId"),
                "processDefinitionName": chosen_node.get("processInstanceName"),
                "parentProcessNodeId": curr_node.get("id"),
                "processNodeId": chosen_node.get("id"),
                "processNodeName": chosen_node.get("name"),
                "clUnitId": cl_unit_id,
                "clTicketStatusId": None,
                "clProcessingSystemId": 5,
                "precheckCode": None
            },
            "fileUpload": []
        }

        # 5. Gửi request POST chuyển bước / đóng phiếu
        url_submit = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/ticket-processing"
        post_res = requests.post(url_submit, headers=headers, json=payload, timeout=15).json()
        if post_res.get("isError"):
            return {"success": False, "message": post_res.get("message", "Lỗi xử lý phiếu trên TTS Mới")}

        # 6. Ghi vết và cập nhật cơ sở dữ liệu
        try:
            from db_manager import record_ttsnew_stage, get_db_connection
            if phone:
                record_ttsnew_stage(phone, ticket_code, round_num, ticket_flow_id, status)
                conn = get_db_connection()
                new_status = "Chờ đóng lần 2" if round_num == 1 else "Đã đóng"
                conn.execute("""
                    UPDATE tickets 
                    SET ticket_status = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE phone = ? AND source = 'tts_new'
                """, (new_status, phone))
                conn.commit()
                conn.close()
        except Exception as ex_db:
            pass

        return {
            "success": True,
            "round": round_num,
            "step_name": chosen_node.get("name"),
            "action_label": action_label,
            "new_flow_id": post_res.get("data"),
            "message": f"✅ {action_label} thành công!"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
