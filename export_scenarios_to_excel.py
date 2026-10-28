# export_scenarios_to_excel.py
# Cong cu xuat toan bo kich ban Tien kiem (SMS & Data) ra file Excel de KTV de dang xem va chinh sua cau tu.

import os
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "KICH_BAN_TIEN_KIEM_PRECHECK.xlsx")

def export_all_scenarios():
    wb = Workbook()
    wb.remove(wb.active)  # Xoa sheet mac dinh

    # --- STYLE CHUAN DOANH NGHIEP VNPT ---
    COLOR_NAVY = "004B8D"
    COLOR_WHITE = "FFFFFF"
    COLOR_ZEBRA = "F8F9FA"
    COLOR_BORDER = "D1D5DB"
    COLOR_HEADER_BORDER = "002D5B"

    font_header = Font(name="Segoe UI", size=10, bold=True, color=COLOR_WHITE)
    font_body = Font(name="Segoe UI", size=9)
    font_body_bold = Font(name="Segoe UI", size=9, bold=True)
    font_code = Font(name="Consolas", size=9, bold=True, color="1E3A8A")
    font_title = Font(name="Segoe UI", size=13, bold=True, color=COLOR_WHITE)
    font_note = Font(name="Segoe UI", size=10, italic=True)

    fill_header = PatternFill(start_color=COLOR_NAVY, end_color=COLOR_NAVY, fill_type="solid")
    fill_zebra = PatternFill(start_color=COLOR_ZEBRA, end_color=COLOR_ZEBRA, fill_type="solid")
    fill_white = PatternFill(start_color=COLOR_WHITE, end_color=COLOR_WHITE, fill_type="solid")
    fill_warn = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    thin_border = Side(border_style="thin", color=COLOR_BORDER)
    border_cell = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)
    border_header = Border(
        left=Side(border_style="thin", color=COLOR_HEADER_BORDER),
        right=Side(border_style="thin", color=COLOR_HEADER_BORDER),
        top=Side(border_style="thin", color=COLOR_HEADER_BORDER),
        bottom=Side(border_style="medium", color=COLOR_HEADER_BORDER)
    )

    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_top_left = Alignment(horizontal="left", vertical="top", wrap_text=True)
    align_top_center = Alignment(horizontal="center", vertical="top", wrap_text=True)

    # =========================================================================
    # SHEET 1: KICH BAN SMS
    # =========================================================================
    ws_sms = wb.create_sheet(title="Kich_Ban_Tin_Nhan_SMS")
    ws_sms.views.sheetView[0].showGridLines = True
    ws_sms.freeze_panes = "A2"

    sms_headers = [
        ("STT", 6, align_center),
        ("Mã kịch bản (Scenario ID - KHÔNG ĐỔI)", 38, align_center),
        ("Tên kịch bản", 35, align_left),
        ("Kết luận kịch bản (Conclusion)", 32, align_left),
        ("Mã lỗi OneOSS", 14, align_center),
        ("Tên mã lỗi OneOSS", 28, align_left),
        ("Phân tích kỹ thuật (Technical Analysis - Cho KTV sửa)", 65, align_top_left),
        ("Hướng xử lý / Tư vấn KH (Action Plan - Cho KTV sửa)", 60, align_top_left),
        ("Màu sắc", 12, align_center)
    ]

    for col_idx, (h_name, width, _) in enumerate(sms_headers, 1):
        cell = ws_sms.cell(row=1, column=col_idx, value=h_name)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = border_header
        col_letter = get_column_letter(col_idx)
        ws_sms.column_dimensions[col_letter].width = width
    ws_sms.row_dimensions[1].height = 28

    # Doc du lieu SMS
    sms_path = os.path.join(BASE_DIR, "sms_diagnostic_scenarios.json")
    if not os.path.exists(sms_path):
        sms_path = os.path.join(BASE_DIR, "diagnostic_scenarios_sms.json")
    
    sms_scenarios = []
    if os.path.exists(sms_path):
        with open(sms_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            sms_scenarios = data.get("SMS_SCENARIOS") or data.get("SCENARIOS") or []

    for idx, sc in enumerate(sms_scenarios, 1):
        row_idx = idx + 1
        is_even = (idx % 2 == 0)
        row_fill = fill_zebra if is_even else fill_white

        row_data = [
            (idx, font_body, align_top_center),
            (sc.get("id", ""), font_code, align_top_left),
            (sc.get("name", ""), font_body_bold, align_top_left),
            (sc.get("conclusion", ""), font_body_bold, align_top_left),
            (sc.get("suggested_cause_code", ""), font_body, align_top_center),
            (sc.get("suggested_cause_name", ""), font_body, align_top_left),
            (sc.get("technical_analysis", ""), font_body, align_top_left),
            (sc.get("action_plan", ""), font_body, align_top_left),
            (sc.get("color", ""), font_body, align_top_center),
        ]

        for col_idx, (val, f_style, a_style) in enumerate(row_data, 1):
            cell = ws_sms.cell(row=row_idx, column=col_idx, value=val)
            cell.font = f_style
            cell.alignment = a_style
            cell.fill = row_fill
            cell.border = border_cell

        ws_sms.row_dimensions[row_idx].height = 60

    # =========================================================================
    # SHEET 2: KICH BAN DATA MOBILE INTERNET
    # =========================================================================
    ws_data = wb.create_sheet(title="Kich_Ban_Data_Mobile")
    ws_data.views.sheetView[0].showGridLines = True
    ws_data.freeze_panes = "A2"

    data_headers = [
        ("STT", 6, align_center),
        ("Mã kịch bản (Scenario ID - KHÔNG ĐỔI)", 35, align_center),
        ("Tên kịch bản", 35, align_left),
        ("Kết luận kịch bản (Conclusion)", 32, align_left),
        ("Phân tích kỹ thuật (Technical Analysis - Cho KTV sửa)", 65, align_top_left),
        ("Hướng xử lý / Tư vấn KH (Action Plan - Cho KTV sửa)", 60, align_top_left),
        ("Màu sắc", 12, align_center)
    ]

    for col_idx, (h_name, width, _) in enumerate(data_headers, 1):
        cell = ws_data.cell(row=1, column=col_idx, value=h_name)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_center
        cell.border = border_header
        col_letter = get_column_letter(col_idx)
        ws_data.column_dimensions[col_letter].width = width
    ws_data.row_dimensions[1].height = 28

    # Doc du lieu Data
    data_path = os.path.join(BASE_DIR, "diagnostic_scenarios.json")
    data_scenarios = []
    if os.path.exists(data_path):
        with open(data_path, "r", encoding="utf-8") as f:
            d_data = json.load(f)
            data_scenarios = d_data.get("SCENARIOS") or []

    for idx, sc in enumerate(data_scenarios, 1):
        row_idx = idx + 1
        is_even = (idx % 2 == 0)
        row_fill = fill_zebra if is_even else fill_white

        row_data = [
            (idx, font_body, align_top_center),
            (sc.get("id", ""), font_code, align_top_left),
            (sc.get("name", ""), font_body_bold, align_top_left),
            (sc.get("conclusion", ""), font_body_bold, align_top_left),
            (sc.get("technical_analysis", ""), font_body, align_top_left),
            (sc.get("action_plan", ""), font_body, align_top_left),
            (sc.get("color", ""), font_body, align_top_center),
        ]

        for col_idx, (val, f_style, a_style) in enumerate(row_data, 1):
            cell = ws_data.cell(row=row_idx, column=col_idx, value=val)
            cell.font = f_style
            cell.alignment = a_style
            cell.fill = row_fill
            cell.border = border_cell

        ws_data.row_dimensions[row_idx].height = 55

    # =========================================================================
    # SHEET 3: HUONG DAN SU DUNG
    # =========================================================================
    ws_guide = wb.create_sheet(title="HƯỚNG DẪN CHỈNH SỬA")
    ws_guide.views.sheetView[0].showGridLines = True
    
    ws_guide.merge_cells("A1:F1")
    title_cell = ws_guide.cell(row=1, column=1, value="HƯỚNG DẪN HIỆU CHỈNH CÂU TỪ KỊCH BẢN TIỀN KIỂM VNPT PRECHECK")
    title_cell.font = font_title
    title_cell.fill = fill_header
    title_cell.alignment = align_center
    ws_guide.row_dimensions[1].height = 35

    guide_steps = [
        ("Mục", "Nội dung hướng dẫn chi tiết cho Kỹ thuật viên / Quản trị viên"),
        ("1. Cột B - Mã kịch bản (Scenario ID)", "TUYỆT ĐỐI KHÔNG SỬA cột này. Đây là mã định danh khóa chính mà hệ thống AI và Core dùng để nhận diện và nạp kịch bản."),
        ("2. Cột C - Tên kịch bản", "Có thể chỉnh sửa tên gọi hiển thị trên giao diện Dashboard để KTV đọc dễ hiểu hơn."),
        ("3. Cột D - Kết luận kịch bản", "Có thể chỉnh sửa dòng tóm tắt kết luận ngắn gọn, súc tích (thường viết IN HOA)."),
        ("4. Cột G - Phân tích kỹ thuật (Technical Analysis)", "ĐÂY LÀ PHẦN QUAN TRỌNG NHẤT: Bạn có thể tự do gọt giũa câu từ, xóa các câu sáo rỗng hoặc viết lại theo đúng văn phong kỹ thuật chuẩn của VNPT VinaPhone. Chú ý các biến {app_brand}, {time_desc}, {mo_success} hãy giữ nguyên nếu muốn hệ thống tự động điền thông số thật."),
        ("5. Cột H - Hướng xử lý / Tư vấn KH (Action Plan)", "Có thể chỉnh sửa các bước hướng dẫn khách hàng, tư vấn nghiệp vụ hoặc phân công KTV."),
        ("6. Cột E, F - Mã lỗi & Tên mã lỗi OneOSS", "Có thể điều chỉnh mã lỗi đóng phiếu OneOSS (ví dụ: 2011, 2111, 2013, 2015, 2007) cho phù hợp với quy định đóng phiếu."),
        ("7. Sau khi chỉnh sửa xong", "Chỉ cần nhấn Ctrl + S để Lưu file Excel này, sau đó nhắn cho Trợ lý AI: 'Đã sửa xong file Excel, cập nhật lại giúp toy' để hệ thống tự động đồng bộ ngược lại vào mã nguồn và file JSON.")
    ]

    for r_idx, (col_a, col_b) in enumerate(guide_steps, 3):
        cell_a = ws_guide.cell(row=r_idx, column=1, value=col_a)
        cell_b = ws_guide.cell(row=r_idx, column=2, value=col_b)
        
        if r_idx == 3:
            cell_a.font = font_header
            cell_a.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            cell_b.font = font_header
            cell_b.fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            cell_a.alignment = align_center
            cell_b.alignment = align_center
            ws_guide.row_dimensions[r_idx].height = 28
        else:
            cell_a.font = font_body_bold
            cell_b.font = font_body
            cell_a.alignment = align_top_left
            cell_b.alignment = align_top_left
            cell_a.fill = fill_warn if "TUYỆT ĐỐI" in col_b else fill_white
            cell_b.fill = fill_warn if "TUYỆT ĐỐI" in col_b else fill_white
            ws_guide.row_dimensions[r_idx].height = 40
            
        cell_a.border = border_cell
        cell_b.border = border_cell

    ws_guide.column_dimensions["A"].width = 38
    ws_guide.column_dimensions["B"].width = 95

    # Luu file
    wb.save(OUTPUT_FILE)
    print(f"[EXPORT SUCCESS] {OUTPUT_FILE}")
    print(f"[STATS] Da xuat {len(sms_scenarios)} kich ban SMS va {len(data_scenarios)} kich ban Data.")

if __name__ == "__main__":
    export_all_scenarios()
