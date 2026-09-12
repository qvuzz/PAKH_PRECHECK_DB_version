# Tài Liệu Đặc Tả Kỹ Thuật: Quy Trình Đóng & Chuyển Xử Lý Phiếu TTS Mới (tts.vnptnet.vn)

> **Trạng thái**: TẠM LƯU GHI NHỚ (Chờ trang TTS Mới hoàn thiện quy trình thực tế trước khi kích hoạt chính thức).  
> **Cơ chế**: Reverse-Engineered từ mã nguồn Angular Frontend (`main.507fc149000be3b6.js`) và OneOSS API Gateway (`gw-oneoss.vnpt.vn`).

---

## 1. Tổng Quan Quy Trình Thao Tác Giao Diện & Ánh Xạ API

Khi người dùng thao tác trên giao diện web `tts.vnptnet.vn`:
1. **Tại trang chi tiết phiếu (`/chi-tiet-phieu-pakh`)**:
   - Người dùng bấm nút **"Cập nhật xử lý"**.
   - Trình duyệt tự động gọi API 1 & API 2 để nạp dữ liệu bước và đơn vị tiếp nhận.
2. **Tại modal / form "Cập nhật xử lý"**:
   - Nhập **Nội dung xử lý** (Ý kiến phân tích kỹ thuật - Cột 10 của hệ thống tiền kiểm).
   - Chọn bước tiếp theo là **`2.4`** (Mã kỹ thuật: `2.4.5` - `2.4 Đánh giá kết quả xử lý PAKH dịch vụ Data`).
   - Nhập **Nội dung chuyển giao**.
   - Bấm nút **"Chuyển xử lý"** (hoặc Đóng phiếu).
   - Trình duyệt đóng gói JSON qua hàm `buildPayload()` và bắn `POST` lên gateway.

---

## 2. Chi Tiết Các API Trong Luồng

### API 1: Lấy Cấu Trúc Bước Tiếp Theo (BPMN Workflow)
- **URL**: `GET https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/get-next-step?ticketFlowId={ticketFlowId}`
- **Headers**:
  ```http
  Authorization: Bearer <JWT_TOKEN>
  Origin: https://tts.vnptnet.vn
  Referer: https://tts.vnptnet.vn/
  ```
- **Dữ liệu quan trọng trả về**:
  - `data.processInstanceId`: ID tiến trình BPMN hiện tại (ví dụ: `01a037ee-f996-76cb-8548-be78a56c48f6`).
  - `data.currentNodes[0].id`: ID node hiện tại (`processNodeInstanceId`, ví dụ: `01a037ee-f9ac-74ce-962b-bc6934a4f7a2`).
  - `data.nextNodeData`: Danh sách các node bước tiếp theo. Với luồng Data, node đích là:
    - `id`: ID bước tiếp theo (`processNodeId`, ví dụ: `01a037ee-fadc-7188-ac24-0db5a6939f9a`).
    - `name`: `2.4 Đánh giá kết quả xử lý PAKH dịch vụ Data`.
    - `processData.stepCode`: `2.4.5`.
    - `processData.formId`: `5afb83f9-e1de-4d86-88b5-740fd2068f02` (Form `C4_Xử lý PAKH dịch vụ Data`).
    - `processInstanceId`: ID định nghĩa quy trình tiếp theo (`01a037ee-fac0-7263-a867-c4be2ff247e5`).
    - `processInstanceName`: `2.4_QT_CLM_02`.
    - `processData.systemId`: `5` (Hệ thống TTS).

---

### API 2: Lấy Đơn Vị Phụ Trách Theo Phân Vùng Hạ Tầng (MSC Routing)
- **URL**: `GET https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/CfUnitTypeUnit/get-by-msc?ticketId={ticketId}`
- **Dữ liệu quan trọng trả về**:
  - `data[0].clUnitId`: Mã đơn vị xử lý sự cố (ví dụ: `418` tương ứng với `Trung tâm Vận hành khai thác mạng Khu vực miền Nam/Tổ Dịch vụ (SOC2)`).

---

### API 3: Thực Hiện Chuyển Xử Lý / Đóng Phiếu (Action POST)
- **URL**: `POST https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/ticket-processing`
- **Method**: `POST`
- **Payload chuẩn trích xuất từ `buildPayload()`**:
  ```json
  {
    "ticketFlowId": 87006,
    "ticketId": 21297,
    "formId": "5afb83f9-e1de-4d86-88b5-740fd2068f02",
    "processNodeInstanceId": "01a037ee-f9ac-74ce-962b-bc6934a4f7a2",
    "processDefinitionId": "01a037ee-f996-76cb-8548-be78a56c48f6",
    "closingContent": "<Nội dung xử lý - Cột 10>",
    "assignContent": "<Nội dung chuyển giao>",
    "columnJson": {
      "formId": "5afb83f9-e1de-4d86-88b5-740fd2068f02"
    },
    "newTicketFlow": {
      "ticketFlowParentId": 87006,
      "processDefinitionId": "01a037ee-fac0-7263-a867-c4be2ff247e5",
      "processDefinitionName": "2.4_QT_CLM_02",
      "parentProcessNodeId": "01a037ee-f9ac-74ce-962b-bc6934a4f7a2",
      "processNodeId": "01a037ee-fadc-7188-ac24-0db5a6939f9a",
      "processNodeName": "2.4 Đánh giá kết quả xử lý PAKH dịch vụ Data",
      "clUnitId": 418,
      "clTicketStatusId": null,
      "clProcessingSystemId": 5,
      "precheckCode": null
    },
    "fileUpload": []
  }
  ```

---

## 3. Mẫu Triển Khai Sẵn Sàng Bằng Python (Ready-To-Use)

Đoạn mã bên dưới đã được chuẩn bị sẵn sàng. Khi trang TTS Mới hoàn thiện quy trình nghiệp vụ và người dùng kích hoạt tính năng tự động đóng, hàm này sẽ được gọi trực tiếp:

```python
import requests

def api_transfer_ttsnew_ticket(token: str, ticket_flow_id: int, ticket_id: int,
                               closing_content: str, assign_content: str = "") -> dict:
    """
    Thực hiện chuyển bước / đóng phiếu tự động trên hệ thống TTS Mới qua OneOSS REST API.
    """
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Origin": "https://tts.vnptnet.vn",
        "Referer": "https://tts.vnptnet.vn/",
        "User-Agent": "Mozilla/5.0"
    }

    # 1. Lấy thông tin các node quy trình
    url_step = f"https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/get-next-step?ticketFlowId={ticket_flow_id}"
    res_step = requests.get(url_step, headers=headers, timeout=10).json()
    if res_step.get("isError"):
        return {"success": False, "message": res_step.get("message", "Lỗi lấy bước kế tiếp")}

    step_data = res_step.get("data", {})
    curr_node = step_data.get("currentNodes", [{}])[0]
    next_node = step_data.get("nextNodeData", [{}])[0]

    # 2. Lấy đơn vị phụ trách theo MSC
    url_msc = f"https://gw-oneoss.vnpt.vn/oss/tts/cl/cl-tts-api/CfUnitTypeUnit/get-by-msc?ticketId={ticket_id}"
    res_msc = requests.get(url_msc, headers=headers, timeout=10).json()
    cl_unit_id = 418
    if not res_msc.get("isError") and res_msc.get("data"):
        cl_unit_id = res_msc["data"][0].get("clUnitId", 418)

    # 3. Đóng gói Payload
    form_id = next_node.get("processData", {}).get("formId")
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
            "processDefinitionId": next_node.get("processInstanceId"),
            "processDefinitionName": next_node.get("processInstanceName"),
            "parentProcessNodeId": curr_node.get("id"),
            "processNodeId": next_node.get("id"),
            "processNodeName": next_node.get("name"),
            "clUnitId": cl_unit_id,
            "clTicketStatusId": None,
            "clProcessingSystemId": 5,
            "precheckCode": None
        },
        "fileUpload": []
    }

    # 4. Gửi request POST
    url_submit = "https://gw-oneoss.vnpt.vn/oss/tts/ticket/ticket-tts-api/TicketProcessing/ticket-processing"
    post_res = requests.post(url_submit, headers=headers, json=payload, timeout=15)
    return post_res.json()
```
