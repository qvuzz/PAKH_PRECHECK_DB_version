# -*- coding: utf-8 -*-
"""
TÀI LIỆU ĐÀO TẠO KỸ THUẬT VÀ HƯỚNG DẪN VẬN HÀNH CHUYÊN SÂU
HỆ THỐNG TIỀN KIỂM PHẢN ÁNH KHÁCH HÀNG VNPT TTS PRECHECK
Dung lượng dự kiến: ~30 trang A4 chuẩn hoá viễn thông
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

ARTIFACT_DIR = r"C:\Users\lequa\.gemini\antigravity-ide\brain\233538e9-b8ef-4c40-b0c3-e80e1868d2c3"
IMG_DIR = os.path.join(ARTIFACT_DIR, "manual_crops")

# Đường dẫn ảnh chụp thực tế
IMG_HEADER = os.path.join(IMG_DIR, "ui_header.png")
IMG_SIDEBAR = os.path.join(IMG_DIR, "ui_sidebar.png")
IMG_TABS = os.path.join(IMG_DIR, "ui_action_tabs.png")
IMG_SUMMARY = os.path.join(IMG_DIR, "ui_summary_row.png")
IMG_EXPANDED = os.path.join(IMG_DIR, "ui_expanded_all.png")
IMG_CARD1 = os.path.join(IMG_DIR, "ui_card1_summary.png")
IMG_CARD2 = os.path.join(IMG_DIR, "ui_card2_profile.png")
IMG_CARD3 = os.path.join(IMG_DIR, "ui_card3_actions.png")
IMG_WARD = os.path.join(IMG_DIR, "ui_ward_detect.png")
IMG_BTNS = os.path.join(IMG_DIR, "ui_action_buttons.png")
IMG_CAUSE = os.path.join(IMG_DIR, "ui_cause_dropdown.png")

IMG_VOICE = os.path.join(ARTIFACT_DIR, "module_cuoc_goi_1791814562393.png")
IMG_SPAM = os.path.join(ARTIFACT_DIR, "module_chan_spam_1791814585623.png")
IMG_SMS = os.path.join(ARTIFACT_DIR, "module_tin_nhan_1791814616208.png")
IMG_SMS_MODAL = os.path.join(ARTIFACT_DIR, "smsc_cdr_modal_1791814637383.png")
IMG_KTV_MGT = os.path.join(ARTIFACT_DIR, "quan_ly_ktv_1791814684329.png")

OUTPUT_DOCX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HUONG_DAN_SU_DUNG_HE_THONG_VNPT_TTS_PRECHECK.docx")

# Màu thương hiệu VNPT
C_VNPT_BLUE = RGBColor(0, 82, 165)
C_VNPT_CYAN = RGBColor(2, 132, 199)
C_DARK = RGBColor(15, 23, 42)
C_GRAY = RGBColor(100, 116, 139)

def set_cell_background(cell, fill_hex):
    tc_pr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tc_pr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tc_pr = cell._element.get_or_add_tcPr()
    tc_mar = parse_xml(f'<w:tcMar {nsdecls("w")}>'
                       f'<w:top w:w="{top}" w:type="dxa"/>'
                       f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
                       f'<w:left w:w="{left}" w:type="dxa"/>'
                       f'<w:right w:w="{right}" w:type="dxa"/>'
                       f'</w:tcMar>')
    tc_pr.append(tc_mar)

def add_styled_heading(doc, text, level):
    h = doc.add_heading(text, level=level)
    run = h.runs[0] if h.runs else h.add_run(text)
    run.font.name = 'Arial'
    if level == 1:
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = C_VNPT_BLUE
        h.paragraph_format.space_before = Pt(18)
        h.paragraph_format.space_after = Pt(6)
    elif level == 2:
        run.font.size = Pt(12.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 102, 204)
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(4)
    elif level == 3:
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = RGBColor(30, 41, 59)
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(2)
    return h

def add_p(doc, text="", bold_prefix="", space_after=4, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Arial'
        r_pre.font.size = Pt(10)
        r_pre.font.bold = True
        r_pre.font.color.rgb = C_DARK
    if text:
        r_txt = p.add_run(text)
        r_txt.font.name = 'Arial'
        r_txt.font.size = Pt(10)
        r_txt.font.italic = italic
        r_txt.font.color.rgb = C_DARK
    return p

def add_bullet(doc, text, bold_prefix=""):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Arial'
        r_pre.font.size = Pt(10)
        r_pre.font.bold = True
        r_pre.font.color.rgb = C_DARK
    r_txt = p.add_run(text)
    r_txt.font.name = 'Arial'
    r_txt.font.size = Pt(10)
    r_txt.font.color.rgb = C_DARK
    return p

def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run(text)
    run.font.name = 'Arial'
    run.font.size = Pt(9)
    run.font.italic = True
    run.font.color.rgb = C_GRAY

def add_image_safe(doc, img_path, width_inches=6.2, caption_text=None):
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        doc.add_picture(img_path, width=Inches(width_inches))
        if caption_text:
            add_caption(doc, caption_text)
    else:
        add_p(doc, f"[Hình ảnh: {os.path.basename(img_path)} không khả dụng]", italic=True)

def add_callout(doc, text, callout_type="NOTE", title_override=None):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    
    if callout_type == "IMPORTANT":
        fill = "FFFBEB"
        border_color = "D97706"
        title = title_override or "LƯU Ý ĐẶC BIỆT QUAN TRỌNG:"
        title_color = RGBColor(180, 83, 9)
    elif callout_type == "SUCCESS":
        fill = "F0FDF4"
        border_color = "16A34A"
        title = title_override or "QUY CHUẨN XÁC THỰC THÀNH CÔNG:"
        title_color = RGBColor(22, 101, 52)
    elif callout_type == "WARNING":
        fill = "FEF2F2"
        border_color = "DC2626"
        title = title_override or "CẢNH BÁO NGUY CƠ / LỖI THƯỜNG GẶP:"
        title_color = RGBColor(153, 27, 27)
    else:
        fill = "F0F9FF"
        border_color = "0284C7"
        title = title_override or "HƯỚNG DẪN THỰC HÀNH / MẸO XỬ LÝ:"
        title_color = RGBColor(3, 105, 161)
        
    set_cell_background(cell, fill)
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)
    
    tc_pr = cell._element.get_or_add_tcPr()
    borders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                        f'<w:top w:val="none"/>'
                        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>'
                        f'<w:bottom w:val="none"/>'
                        f'<w:right w:val="none"/>'
                        f'</w:tcBorders>')
    tc_pr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    r_tit = p.add_run(title + "\n")
    r_tit.font.name = 'Arial'
    r_tit.font.size = Pt(9.5)
    r_tit.font.bold = True
    r_tit.font.color.rgb = title_color
    
    r_txt = p.add_run(text)
    r_txt.font.name = 'Arial'
    r_txt.font.size = Pt(9.5)
    r_txt.font.color.rgb = C_DARK
    
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)

def create_styled_table(doc, headers, data, col_widths=None):
    tbl = doc.add_table(rows=len(data) + 1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    # Header
    hdr_cells = tbl.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "0052A5")
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=120, right=120)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.name = 'Arial'
            run.font.size = Pt(9.5)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            
    # Rows
    for r_idx, row_data in enumerate(data):
        row_cells = tbl.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, cell_value in enumerate(row_data):
            row_cells[c_idx].text = str(cell_value)
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=100, right=100)
            p = row_cells[c_idx].paragraphs[0]
            for run in p.runs:
                run.font.name = 'Arial'
                run.font.size = Pt(9)
                run.font.color.rgb = C_DARK
                
    # Độ rộng cột
    if col_widths:
        for row in tbl.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Inches(w)
                
    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_before = Pt(0)
    p_space.paragraph_format.space_after = Pt(8)
    return tbl

print("Đang khởi tạo tài liệu đào tạo chuyên sâu Word...")
doc = Document()

# Thiết lập lề trang A4 chuẩn
sections = doc.sections
for s in sections:
    s.top_margin = Inches(0.75)
    s.bottom_margin = Inches(0.75)
    s.left_margin = Inches(0.85)
    s.right_margin = Inches(0.85)
    s.page_width = Inches(8.27)
    s.page_height = Inches(11.69)

# ==========================================
# TRANG BÌA CHUẨN DOANH NGHIỆP VNPT
# ==========================================
p_cover_top = doc.add_paragraph()
p_cover_top.paragraph_format.space_before = Pt(30)
p_cover_top.paragraph_format.space_after = Pt(4)
r_org = p_cover_top.add_run("TẬP ĐOÀN BƯU CHÍNH VIỄN THÔNG VIỆT NAM (VNPT)\nTỔNG CÔNG TY DỊCH VỤ VIỄN THÔNG (VNPT-VINAPHONE)")
r_org.font.name = 'Arial'
r_org.font.size = Pt(12)
r_org.font.bold = True
r_org.font.color.rgb = C_VNPT_BLUE
p_cover_top.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_div = doc.add_paragraph()
p_div.paragraph_format.space_after = Pt(60)
r_div = p_div.add_run("TRUNG TÂM VẬN HÀNH KHAI THÁC MẠNG & HỖ TRỢ KỸ THUẬT (VNPT SOC / TTS)")
r_div.font.name = 'Arial'
r_div.font.size = Pt(10.5)
r_div.font.bold = True
r_div.font.color.rgb = C_GRAY
p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_title = doc.add_paragraph()
p_title.paragraph_format.space_after = Pt(16)
r_title = p_title.add_run("GIÁO TRÌNH ĐÀO TẠO KỸ THUẬT &\nHƯỚNG DẪN VẬN HÀNH CHUYÊN SÂU\nHỆ THỐNG VNPT TTS PRECHECK")
r_title.font.name = 'Arial'
r_title.font.size = Pt(22)
r_title.font.bold = True
r_title.font.color.rgb = C_VNPT_BLUE
p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_sub = doc.add_paragraph()
p_sub.paragraph_format.space_after = Pt(80)
r_sub = p_sub.add_run("HỆ THỐNG TIỀN KIỂM TỰ ĐỘNG PHẢN ÁNH KHÁCH HÀNG 360 ĐỘ\n(Mobile Internet • Thoại VoLTE • Chặn Spam NĐ 91 • SMS OTP • CVQT Roaming • Quản trị KTV SOC)")
r_sub.font.name = 'Arial'
r_sub.font.size = Pt(12)
r_sub.font.color.rgb = RGBColor(51, 65, 85)
p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_meta = doc.add_paragraph()
p_meta.paragraph_format.space_after = Pt(4)
r_meta = p_meta.add_run(
    "Đơn vị biên soạn: Nhóm Kỹ sư Tối ưu Mạng & Tự động hoá Vận hành\n"
    "Đối tượng đào tạo: Kỹ thuật viên (KTV) Viễn thông Tỉnh/TP, Điều hành SOC, Hỗ trợ kỹ thuật Call Center 18001091\n"
    "Hệ thống tích hợp: OneOSS TTS • Core SAPC PCRF • BTools CDP • CEM Vô tuyến • SMSC Gateway • Port 1708 Geocoding\n"
    "Phiên bản tài liệu: 2026.04 (Chuẩn hoá theo Danh mục 34 Tỉnh/TP mới)\n"
    "Ngày ban hành: Tháng 10/2026"
)
r_meta.font.name = 'Arial'
r_meta.font.size = Pt(10)
r_meta.font.color.rgb = C_DARK
p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_page_break()

# ==========================================
# LỜI NÓI ĐẦU & MỤC TIÊU ĐÀO TẠO
# ==========================================
add_styled_heading(doc, "LỜI NÓI ĐẦU & MỤC TIÊU KHÓA ĐÀO TẠO", level=1)
add_p(doc, "Trong thời đại chuyển đổi số toàn diện của Tập đoàn VNPT, công tác tiếp nhận, xử lý và đóng phiếu Phản ánh khách hàng (PAKH) đóng vai trò quyết định đến trải nghiệm khách hàng và chỉ số hài lòng dịch vụ (CSAT). Hệ thống VNPT TTS PRECHECK ra đời với sứ mệnh thay đổi toàn diện phương thức làm việc truyền thống của Kỹ thuật viên (KTV) viễn thông:")
add_bullet(doc, "Tiết kiệm 85% thời gian tra cứu thủ công qua việc tự động thu thập và đối soát đa hệ thống (Core SAPC, BTools, CEM, SMSC Gateway).", "Tự động hoá toàn diện: ")
add_bullet(doc, "Loại bỏ hoàn toàn cảm tính khi đóng phiếu thông qua Động cơ phân tích luật (Rule Engine) và 6 kịch bản chẩn đoán kỹ thuật chuẩn xác.", "Chính xác tuyệt đối: ")
add_bullet(doc, "Đảm bảo 100% phiếu đóng chuẩn mã lỗi OneOSS và tuân thủ tuyệt đối quy chuẩn địa giới hành chính 2 cấp (Phường/Xã và 34 Tỉnh/TP mới sáp nhập).", "Chuẩn hoá vận hành: ")

add_styled_heading(doc, "MỤC TIÊU NĂNG LỰC DÀNH CHO KỸ THUẬT VIÊN", level=2)
add_bullet(doc, "Nắm vững nguyên lý và vai trò của từng hệ thống vệ tinh trong mạng lõi và mạng vô tuyến VNPT VinaPhone.", "Mức độ 1 (Nhận biết): ")
add_bullet(doc, "Thành thạo thao tác tra cứu trên cả 6 phân hệ nghiệp vụ, hiểu rõ ý nghĩa từng trường dữ liệu, mã RAT Type và Service ID cước.", "Mức độ 2 (Vận hành): ")
add_bullet(doc, "Phân tích được nguyên nhân gốc rễ (Root Cause) của mọi khiếu nại (bóp băng thông, treo phiên OCS, rớt sóng, chặn spam, mất SMS OTP).", "Mức độ 3 (Chẩn đoán): ")
add_bullet(doc, "Tự tin quyết định hướng xử lý: Tư vấn khách hàng, chuyển trạm vô tuyến địa bàn, hoặc chuyển IT Core/CCBS khai báo lại cước.", "Mức độ 4 (Ra quyết định): ")

add_callout(doc, 
    "Khóa đào tạo được thiết kế cho cả học viên mới tiếp cận (Newbie) lẫn KTV kỳ cựu. "
    "Mỗi chương đều có bảng tra cứu trực quan, luồng chẩn đoán từng bước và các ca sự cố thực tế kèm hình ảnh giao diện.",
    callout_type="NOTE", title_override="LƯU Ý DÀNH CHO HỌC VIÊN:")

# ==========================================
# MỤC LỤC CHI TIẾT
# ==========================================
add_styled_heading(doc, "MỤC LỤC TỔNG QUAN GIÁO TRÌNH", level=2)
toc_items = [
    ("CHƯƠNG 1", "KIẾN TRÚC TỔNG THỂ & BẢN ĐỒ KẾT NỐI CÁC HỆ THỐNG VỆ TINH", "Vai trò OneOSS, SAPC, BTools, CEM, SMSC, Geocoding 1708"),
    ("CHƯƠNG 2", "THƯ VIỆN KỊCH BẢN CHẨN ĐOÁN KỸ THUẬT (DIAGNOSTIC ENGINE)", "Chi tiết 6 kịch bản cốt lõi: Bóp tốc độ, Treo phiên, Rớt 2G/3G, VPN..."),
    ("CHƯƠNG 3", "THƯ VIỆN TỪ ĐIỂN GÓI CƯỚC & MÃ DỊCH VỤ (SERVICEID.JSON)", "Bảng mã bóp băng thông 10002..10014, Gói 3000 OCS, Gói OTT Bypass"),
    ("CHƯƠNG 4", "THƯ VIỆN CÔNG NGHỆ SÓNG VÔ TUYẾN (RATTYPE.JSON) & LOG BTOOLS", "Định nghĩa RAT 0, 1, 2, 6, 7; Thuật toán phân tích tỷ lệ sóng rớt"),
    ("CHƯƠNG 5", "PHÂN HỆ MOBILE INTERNET (DATA) — QUY TRÌNH TIỀN KIỂM 360°", "3 Card phân tích, Quy tắc bắt buộc ODA_BIG_OCS và xử lý gói D159SC"),
    ("CHƯƠNG 6", "PHÂN HỆ CUỘC GỌI & THOẠI (VOICE / VOLTE / HLR / NAM)", "Tra cứu HLR/VLR, VoLTE IMS, cờ NAM khóa cước và luồng Bước 2.3/2.4"),
    ("CHƯƠNG 7", "PHÂN HỆ CHẶN SPAM NGOẠI MẠNG (NGHỊ ĐỊNH 91 & CCOS)", "Nhận diện nhà mạng đối tác (Viettel, Mobi), Quy trình đối soát cam kết"),
    ("CHƯƠNG 8", "PHÂN HỆ TIN NHẮN (SMS) & CỔNG TRA CỨU SMSC GATEWAY CDR", "Cổng CDR thời gian thực, Bảng mã lỗi phân phát tin nhắn OTP Brandname"),
    ("CHƯƠNG 9", "PHÂN HỆ CHUYỂN VÙNG QUỐC TẾ (CVQT / ROAMING) & SIM / ESIM", "Profile HSS Roaming, Gói IR R500N/POST/PPS, Lỗi SIM vật lý và eSIM"),
    ("CHƯƠNG 10", "QUY CHUẨN ĐÓNG PHIẾU ONEOSS 5.1 & QUẢN TRỊ KTV SOC", "Chuẩn hóa Phường/Xã theo 34 Tỉnh/TP mới, Cheatsheet 73 mã OneOSS")
]
create_styled_table(doc, ["Phần", "Tên Chương", "Nội Dung Trọng Tâm"], toc_items, [1.0, 3.2, 2.3])

doc.add_page_break()

# ==========================================
# CHƯƠNG 1: TỔNG QUAN & BẢN ĐỒ VỆ TINH
# ==========================================
add_styled_heading(doc, "CHƯƠNG 1: KIẾN TRÚC TỔNG THỂ & BẢN ĐỒ KẾT NỐI CÁC HỆ THỐNG VỆ TINH", level=1)
add_p(doc, "Hệ thống VNPT TTS PRECHECK hoạt động theo mô hình tích hợp hợp nhất (Unified Integration Gateway). Khi có yêu cầu kiểm tra thuê bao hoặc khi quét định kỳ, hệ thống sẽ tự động gửi lệnh truy vấn đồng thời tới 7 hệ thống vệ tinh viễn thông chuyên biệt:")

add_image_safe(doc, IMG_HEADER, width_inches=6.3, caption_text="Hình 1.1: Thanh điều hướng trung tâm và thông tin phiên làm việc KTV VNPT")

add_styled_heading(doc, "1.1. Bản đồ chức năng các hệ thống vệ tinh tích hợp", level=2)
add_p(doc, "Để chẩn đoán chính xác một sự cố viễn thông, KTV phải hiểu rõ nguồn gốc của dữ liệu đến từ đâu. Dưới đây là bảng phân định nhiệm vụ chi tiết của từng hệ thống trong mạng lưới:")

sat_systems = [
    ("OneOSS TTS Mới / TTS Cũ", "Quản lý phiếu & Điều hành", "https://ttsnew.vnpt.vn (hoặc TTS Cũ)", 
     "Thu thập danh sách phản ánh của khách hàng theo phân vùng phụ trách. Tự động nhận phiếu, cập nhật ý kiến xử lý và thực hiện đóng phiếu tự động/bán tự động chuẩn 5 cấp."),
    ("Core SAPC / PCRF", "Mạng lõi chính sách & Cước", "10.155.42.218 (PCRF Core)", 
     "Tra cứu Profile thuê bao di động: Danh sách gói cước Data kích hoạt trên OCS, cờ khóa mở dịch vụ NAM, băng thông cam kết AMBR (QoS Upload/Download), và trạng thái mở dịch vụ 4G trên HSS."),
    ("BTools Chrome CDP", "Lịch sử phiên truy cập Data", "10.159.21.241:9222 (BTools Service)", 
     "Truy vấn bản ghi CDR dữ liệu 4G/5G/3G gần nhất: Thời gian bắt đầu/kết thúc phiên, dung lượng Upload/Download (Bytes), mã công nghệ sóng (RAT Type), mã dịch vụ Service ID, và nguyên nhân ngắt phiên (Session Cause)."),
    ("CEM Vô tuyến", "Chất lượng sóng trạm phát", "https://cem.vnptmedia.vn", 
     "Kiểm tra chất lượng vùng phủ sóng vô tuyến tại tọa độ khách hàng phát sinh phiên gần nhất: Chỉ số cường độ sóng RSRP (dBm), tỷ số tín hiệu trên nhiễu SINR (dB), tên mã trạm BTS/eNodeB phục vụ, và cảnh báo sự cố trạm."),
    ("Google Maps Geocoding", "Chuẩn hóa địa bàn hành chính", "http://127.0.0.1:1708/api/reverse-geocode", 
     "Nguồn chân lý chuyển đổi từ tọa độ GPS (Latitude, Longitude) từ CEM thành địa danh chuẩn 2 cấp [Phường/Xã, Tỉnh/TP]. Loại bỏ hoàn toàn sai lệch địa bàn khi đóng phiếu OneOSS 5.1."),
    ("SMSC Gateway CDR", "Nhật ký tin nhắn thời gian thực", "Cổng kết nối SMSC Gateway nội bộ", 
     "Truy vấn toàn bộ tin nhắn OTP, tin nhắn Brandname ngân hàng, tin nhắn cá nhân đến/đi của thuê bao; phân tích mã trạng thái phát tin (Delivery Status) và nguyên nhân thất bại."),
    ("CCOS Cam kết", "Đối soát chặn cuộc gọi rác", "Hệ thống CCOS Tập đoàn", 
     "Kiểm tra tình trạng thuê bao bị chặn theo Nghị định 91/2020/NĐ-CP, đối soát biên bản cam kết mở mạng giữa khách hàng và VNPT để tự động gỡ chặn chiều gọi đi.")
]
create_styled_table(doc, ["Tên Hệ Thống", "Phân Loại", "Endpoint / Địa Chỉ", "Nhiệm Vụ Kỹ Thuật"], sat_systems, [1.4, 1.2, 1.5, 2.4])

add_callout(doc, 
    "Toàn bộ 7 hệ thống trên được kết nối ngầm thông qua các API và cơ chế Chrome CDP bất đồng bộ. "
    "KTV không cần phải mở 7 tab trình duyệt khác nhau hay đăng nhập riêng lẻ; toàn bộ dữ liệu được hợp nhất về 1 màn hình duy nhất.",
    callout_type="SUCCESS", title_override="LỢI ÍCH TÍCH HỢP:")

doc.add_page_break()

# ==========================================
# CHƯƠNG 2: THƯ VIỆN KỊCH BẢN CHẨN ĐOÁN
# ==========================================
add_styled_heading(doc, "CHƯƠNG 2: THƯ VIỆN KỊCH BẢN CHẨN ĐOÁN KỸ THUẬT (DIAGNOSTIC SCENARIOS)", level=1)
add_p(doc, "Động cơ tiền kiểm (Diagnostic Engine) là trái tim của hệ thống VNPT TTS PRECHECK, được xây dựng dựa trên tập luật chuyên gia viễn thông được chuẩn hóa trong file cấu hình diagnostic_scenarios.json. Khi phân tích một thuê bao, động cơ sẽ kiểm tra tuần tự các điều kiện để đưa ra kết luận duy nhất, kèm theo màu sắc nhận diện và hướng xử lý chuẩn.")

add_image_safe(doc, IMG_CARD1, width_inches=6.0, caption_text="Hình 2.1: Thẻ tóm tắt kết quả chẩn đoán tự động (Card 1) với màu sắc nhận diện kịch bản")

add_styled_heading(doc, "2.1. Chi tiết 6 kịch bản chẩn đoán kỹ thuật cốt lõi", level=2)

scenarios_detail = [
    ("KC_01_NO_4G", "KHÔNG BẮT ĐƯỢC SÓNG 4G", "Cam nhạt (#FCE4D6)",
     "Hệ thống HSS Core đã khai báo mở profile 4G cho SIM, nhưng trong toàn bộ lịch sử phiên data gần đây thiết bị hoàn toàn không phát sinh bất kỳ phiên nào trên sóng 4G LTE (chỉ xuất hiện RAT=1 hoặc RAT=2).",
     "Lỗi do máy khách hàng đang để chế độ 'Chỉ dùng 2G/3G', chưa bật 4G/LTE, hoặc SIM 4G bị lỗi tiếp xúc vật lý.",
     "Hướng dẫn khách hàng vào Cài đặt di động -> Chuyển sang 'LTE/4G/5G Auto'. Nếu máy đã bật đúng mà không lên 4G, tư vấn khách hàng qua quầy giao dịch kiểm tra đổi SIM."),
    
    ("KC_07_NO_4G_PROFILE", "CHƯA KHAI BÁO PROFILE 4G", "Cam nhạt (#FCE4D6)",
     "Kiểm tra trên hệ thống HSS Core ghi nhận thuê bao chưa được khai báo kích hoạt profile dịch vụ 4G LTE. Thiết bị chỉ có thể kết nối mạng qua hạ tầng 2G/3G cũ.",
     "Lỗi dữ liệu thuê bao trên HSS Core do chuyển đổi gói hoặc đồng bộ hồ sơ thuê bao thất bại từ hệ thống CCBS.",
     "Chuyển ngay bộ phận IT / Khai thác mạng kiểm tra, bổ sung kích hoạt profile 4G cho thuê bao trên HSS Core."),
     
    ("KC_02_WEAK_4G", "BẮT SÓNG 4G KÉM / RỚT SÓNG", "Vàng nhạt (#FFF2CC)",
     "Thuê bao có kết nối được 4G LTE nhưng tần suất rớt về sóng 2G/3G chiếm đa số (> 50% tổng số phiên). Chỉ số RSRP từ trạm CEM ghi nhận suy hao nặng (< -105 dBm).",
     "Thuê bao hoạt động ở khu vực mép vùng phủ sóng, trong nhà cao tầng kín sóng, hoặc trạm BTS lân cận đang bị quá tải/góc phủ chưa tối ưu.",
     "Chuyển phòng Kỹ thuật Viễn thông (VTT) địa bàn kiểm tra thực tế chất lượng vùng phủ sóng và tối ưu góc ngẩng anten trạm."),
     
    ("KC_03_THROTTLED", "THUÊ BAO BỊ BÓP BĂNG THÔNG", "Hồng cam (#F8CBAD)",
     "Hệ thống BTools ghi nhận các mã dịch vụ bóp băng thông đặc thù (10002, 10003, 10005, 10010..10014). Tốc độ tải về bị giới hạn từ 64 Kbps đến 3 Mbps.",
     "Thuê bao đã sử dụng hết dung lượng data tốc độ cao trong chu kỳ của gói cước chính.",
     "Thông báo khách hàng đã dùng hết dung lượng tốc độ cao. Tư vấn đăng ký thêm các gói mua thêm ngày/tuần (như D5, D7, DT20, DPLUS)."),
     
    ("KC_04_PACKAGE_OR_DEVICE_HANG", "LỖI GÓI CƯỚC / THIẾT BỊ TREO", "Xám nhạt (#F2F2F2)",
     "Hệ thống chỉ ghi nhận các mã dịch vụ quản lý phiên cước nền (300, 2042), không phát sinh bất kỳ byte lưu lượng thực tế nào qua OCS, hoặc thuê bao báo lỗi data nhưng không có phiên kết nối.",
     "Gói cước bị treo phiên trên Core OCS, hoặc khách hàng tắt Dữ liệu di động, hoặc điện thoại bị lỗi cấu hình APN ('m3-world').",
     "Kiểm tra hạn dùng gói cước trên OCS; hướng dẫn khách hàng bật tắt chế độ máy bay để reset kết nối. Nếu không được, chuyển IT reset profile OCS."),
     
    ("KC_06_VPN_OR_DEVICE_ISSUE", "ĐANG SỬ DỤNG VPN / 1.1.1.1", "Xanh lục (#E2EFDA)",
     "Thiết bị truy cập qua RAT 1, 6 với dung lượng data của các phiên duy trì đều nhau một cách bất thường trong khoảng từ 5.000.000 Bytes đến 11.500.000 Bytes (5MB - 11.5MB).",
     "Thiết bị đang bật các ứng dụng VPN của bên thứ ba (như Warp 1.1.1.1, Turbo VPN, ExpressVPN) khiến lưu lượng bị phân mảnh và gây giật lag khi truy cập máy chủ trong nước.",
     "Liên hệ khách hàng, giải thích nguyên nhân do ứng dụng VPN làm chậm đường truyền và hướng dẫn tạm tắt VPN khi sử dụng.")
]

for s_id, s_name, s_col, s_log, s_cau, s_act in scenarios_detail:
    add_styled_heading(doc, f"Kịch bản [{s_id}]: {s_name}", level=3)
    add_bullet(doc, s_col, "Màu sắc cảnh báo: ")
    add_bullet(doc, s_log, "Dấu hiệu kỹ thuật nhận diện: ")
    add_bullet(doc, s_cau, "Nguyên nhân cốt lõi: ")
    add_bullet(doc, s_act, "Hành động & Hướng xử lý OneOSS: ")

add_callout(doc, 
    "Khi kịch bản được kích hoạt, hệ thống sẽ tự động điền sẵn Nội dung phản hồi kỹ thuật "
    "và gợi ý chính xác Mã nguyên nhân OneOSS tương ứng. KTV chỉ cần kiểm tra lại và nhấn nút Xác nhận.",
    callout_type="IMPORTANT", title_override="QUY TẮC TỰ ĐỘNG ĐIỀN:")

doc.add_page_break()

# ==========================================
# CHƯƠNG 3: TỪ ĐIỂN GÓI CƯỚC & SERVICEID.JSON
# ==========================================
add_styled_heading(doc, "CHƯƠNG 3: THƯ VIỆN TỪ ĐIỂN GÓI CƯỚC & MÃ DỊCH VỤ (SERVICEID.JSON)", level=1)
add_p(doc, "Mã dịch vụ (Service ID) trong các bản tin cước Diameter Gx/Gy từ BTools là căn cứ khoa học chuẩn xác nhất để xác định trạng thái gói cước của thuê bao. Dự án PAKH_PRECHECK chuẩn hóa toàn bộ các mã này tại tệp tin serviceid.json.")

add_styled_heading(doc, "3.1. Bảng mã bóp băng thông hạ tốc độ (Throttling Matrix)", level=2)
add_p(doc, "Khi khách hàng dùng hết data tốc độ cao, hệ thống Core PCRF sẽ tự động chuyển mã dịch vụ sang dải 10002 - 10014. KTV bắt buộc phải thuộc lòng bảng quy đổi tốc độ sau:")

throttle_table = [
    ("0000010002 / 10002", "Bóp băng thông 64/64 Kbps", "Tốc độ Down: 64 Kbps | Up: 64 Kbps", "Rất chậm, chỉ gửi được tin nhắn văn bản Zalo, tải web gần như đơ"),
    ("0000010003 / 10003", "Bóp băng thông 128/64 Kbps", "Tốc độ Down: 128 Kbps | Up: 64 Kbps", "Chậm, đọc báo text mất 5-10s, không xem được video YouTube"),
    ("0000010005 / 10005", "Bóp băng thông 512/256 Kbps", "Tốc độ Down: 512 Kbps | Up: 256 Kbps", "Trung bình thấp, xem video độ phân giải 240p/360p giật nhẹ"),
    ("0000010010 / 10010", "Bóp băng thông 1024/1024 Kbps (1 Mbps)", "Tốc độ Down: 1 Mbps | Up: 1 Mbps", "Xem video 480p mượt mà, lướt Facebook/TikTok tải chậm hơn bình thường"),
    ("0000010011 / 10011", "Bóp băng thông 2048/2048 Kbps (2 Mbps)", "Tốc độ Down: 2 Mbps | Up: 2 Mbps", "Xem video 720p HD, lướt web bình thường, gọi video call ổn định"),
    ("0000010012 / 10012", "Bóp băng thông 3072/3072 Kbps (3 Mbps)", "Tốc độ Down: 3 Mbps | Up: 3 Mbps", "Xem video 1080p Full HD mượt mà, trải nghiệm tốt ở hầu hết ứng dụng"),
    ("0000010013 / 10013", "Bóp băng thông 2048/1024 Kbps (2M/1M)", "Tốc độ Down: 2 Mbps | Up: 1 Mbps", "Download ổn định ở 2 Mbps, Upload bị giới hạn 1 Mbps"),
    ("0000010014 / 10014", "Bóp băng thông 128/128 Kbps", "Tốc độ Down: 128 Kbps | Up: 128 Kbps", "Hạ băng thông hai chiều mức tối thiểu")
]
create_styled_table(doc, ["Mã Service ID", "Tên Kỹ Thuật", "Giới Hạn Tốc Độ (Kbps)", "Trải Nghiệm Khách Hàng Thực Tế"], throttle_table, [1.4, 1.8, 1.5, 1.8])

add_styled_heading(doc, "3.2. Bảng mã gói cước Data chủ đạo & Quy tắc OCS", level=2)
add_p(doc, "Dải mã dịch vụ chính thức quản lý các gói cước Data trả trước và trả sau VinaPhone:")

data_packages = [
    ("3000 / 0000003000", "BIG_I, BIG, ODA_BIG_OCS", 
     "Dải mã cước OCS của hầu hết các gói Data phổ thông: VD120N, YOLO90, BIG60, BIG70, BIG80, D159SC, SPE7, DT120, VD120M, VD89, THAGA70N, YOLO100M, YOLO125V, U1500, D159V, D60G, MAX100, DT70, VD149, D30G, D49P, D79P, DT90, SBUM, SODA125, SPOTV80, 5G150..."),
    ("3001 / 0000003001", "PAYGO, M0, VD2, THẢ GA", 
     "Cước mặc định dùng bao nhiêu trả bấy nhiêu (PAYGO). Khách hàng không có gói data nền, nếu bật dữ liệu sẽ bị trừ tiền tài khoản gốc (75đ/50KB). Cần cảnh báo phát sinh cước!"),
    ("000000300", "VC5 - DC_COCCOC_VC5; Volte Ground", 
     "Gói cước thoại nền VoLTE và khuyến mãi trình duyệt Cốc Cốc."),
    ("0000000500 / 0000001000", "IR_R500N / IR_POST / IR_PPS", 
     "Các gói Chuyển vùng quốc tế Data Roaming của thuê bao đi nước ngoài."),
    ("0000004000", "Gói Vùng X (X15, X25, X35) & Outzone", 
     "Lưu lượng ngoài vùng (Outzone) của các gói zone địa bàn: YOLO125Z, D120Z, D90Z, D50P, BUM120P..."),
    ("0000005000", "Family, GDVP-T, HOME, GIA ĐÌNH", 
     "Gói cước chia sẻ nhóm gia đình và văn phòng tích hợp VNPT.")
]
create_styled_table(doc, ["Mã Service ID", "Tên Gói / Hồ Sơ Core", "Mô Tả Nghiệp Vụ & Gói Cước Áp Dụng"], data_packages, [1.5, 1.8, 3.2])

add_callout(doc, 
    "ĐẶC BIỆT LƯU Ý VỀ GÓI D159SC VÀ QUY TẮC ODA_BIG_OCS:\n"
    "Các gói cước Data thuộc nhóm BIG_OCS (như D159SC, VD120N, YOLO90...) bắt buộc phải có profile ODA_BIG_OCS trên Core OCS.\n"
    "Nếu thuê bao đã đăng ký D159SC thành công trên CCBS nhưng kiểm tra Core SAPC không thấy profile ODA_BIG_OCS, "
    "hệ thống sẽ xác định đây là lỗi khai báo gói cước. KTV KHÔNG được đóng phiếu lỗi do khách hàng mà PHẢI chuyển hướng xử lý: "
    "'Chuyển IT/CCBS kiểm tra khai báo gói cước {tên gói cước} cho Khách hàng'.",
    callout_type="WARNING", title_override="QUY TẮC VÀNG VỀ GÓI CƯỚC:")

add_styled_heading(doc, "3.3. Bảng mã OTT Bypass (Miễn phí cước ứng dụng)", level=2)
add_p(doc, "Một số gói cước VinaPhone miễn phí dung lượng khi truy cập các ứng dụng chỉ định. Bản tin BTools sẽ ghi nhận các mã dịch vụ OTT đặc thù sau:")

ott_table = [
    ("0000002804", "MYTV (FIX)", "Truyền hình MyTV Mobile"),
    ("0000002807", "ZALO", "Nhắn tin và gọi điện ứng dụng Zalo"),
    ("0000002808 / 2809", "ZingMP3", "Nghe nhạc trực tuyến Zing MP3"),
    ("0000002910", "Meta (Facebook)", "Mạng xã hội Facebook"),
    ("0000002913", "Instagram", "Mạng xã hội hình ảnh Instagram"),
    ("0000002902 / 2920", "DIP_Youtube", "Xem video YouTube"),
    ("0000002917", "TIKTOK", "Xem video ngắn TikTok"),
    ("0000002916", "DIP_LQMobile", "Chơi game Liên Quân Mobile"),
    ("0000002919", "DIP_FreeFire", "Chơi game Garena Free Fire"),
    ("0000002925", "SHOPEE", "Sàn thương mại điện tử Shopee"),
    ("0000002932", "MoMo", "Ví điện tử MoMo")
]
create_styled_table(doc, ["Mã Service ID", "Tên Dịch Vụ OTT", "Ứng Dụng Thực Tế Tương Ứng"], ott_table, [1.5, 1.8, 3.2])

doc.add_page_break()

# ==========================================
# CHƯƠNG 4: THƯ VIỆN SÓNG VÔ TUYẾN RATTYPE
# ==========================================
add_styled_heading(doc, "CHƯƠNG 4: THƯ VIỆN CÔNG NGHỆ SÓNG VÔ TUYẾN (RATTYPE.JSON) & LOG BTOOLS", level=1)
add_p(doc, "RAT Type (Radio Access Technology Type) là trường định danh chuẩn 3GPP trong bản ghi CDR chỉ rõ thiết bị của khách hàng đang kết nối qua thế hệ sóng nào khi phát sinh phiên dữ liệu. Toàn bộ định nghĩa được lưu trữ trong rattype.json.")

add_styled_heading(doc, "4.1. Bảng phân loại công nghệ sóng vô tuyến", level=2)

rat_table = [
    ("RAT 0", "Báo hiệu mạng (Signaling)", "None", 
     "Các bản tin điều khiển, thiết lập kênh truyền hoặc báo hiệu giữa thiết bị và trạm phát. Không phát sinh lưu lượng người dùng tải về thực tế."),
    ("RAT 1", "Sóng 3G (UTRAN - WCDMA / HSPA+)", "1 - 10 Mbps", 
     "Công nghệ 3G cũ. Nếu thuê bao 4G nhưng phát sinh phiên RAT=1 liên tục, chứng tỏ khu vực sóng 4G rất yếu hoặc thiết bị bị rớt sóng mạng lõi."),
    ("RAT 2", "Sóng 2G (GERAN - GSM / GPRS / EDGE)", "40 - 200 Kbps", 
     "Công nghệ 2G truyền thống. Băng thông cực thấp, gần như không thể tải trang web hiện đại. Biểu hiện của việc mất hoàn toàn vùng phủ 4G."),
    ("RAT 6", "Sóng 4G (E-UTRAN - LTE / LTE-Advanced)", "30 - 150 Mbps", 
     "Công nghệ 4G chuẩn chủ đạo hiện nay của mạng VinaPhone. Mọi thuê bao đạt chuẩn phải có > 80% phiên duy trì trên RAT 6."),
    ("RAT 7", "Sóng 5G (NR - New Radio)", "300 - 1000 Mbps", 
     "Công nghệ 5G thế hệ mới tốc độ siêu cao. Thuê bao kết nối trạm 5G VinaPhone và có thiết bị hỗ trợ băng tần 5G.")
]
create_styled_table(doc, ["Mã RAT Type", "Tên Công Nghệ Chuẩn", "Tốc Độ Thực Tế", "Đánh Giá Kỹ Thuật & Ý Nghĩa Phân Tích"], rat_table, [1.1, 1.8, 1.2, 2.4])

add_styled_heading(doc, "4.2. Thuật toán phân tích tỷ lệ sóng rớt (RAT Ratio Analysis)", level=2)
add_p(doc, "Động cơ tiền kiểm phân tích lịch sử các phiên của thuê bao trong 3 đến 7 ngày gần nhất theo công thức sau:")
add_bullet(doc, "Tỷ lệ phiên 4G = (Số phiên có RAT=6) / (Tổng số phiên phát sinh) * 100%", "Công thức 1: ")
add_bullet(doc, "Tỷ lệ rớt mạng 2G/3G = (Số phiên có RAT=1 + RAT=2) / (Tổng số phiên) * 100%", "Công thức 2: ")

add_callout(doc, 
    "QUY TẮC PHÂN LOẠI LỖI THEO TỶ LỆ SÓNG RỚT:\n"
    "• Nếu Tỷ lệ rớt 2G/3G > 50%: Hệ thống tự động kích hoạt kịch bản KC_02_WEAK_4G (Bắt sóng 4G kém).\n"
    "• Nếu Tỷ lệ 4G = 0% nhưng HSS đã mở 4G: Hệ thống kích hoạt KC_01_NO_4G (Lỗi cài đặt máy hoặc hỏng SIM).\n"
    "• Nếu Tỷ lệ 4G = 0% và HSS chưa mở 4G: Hệ thống kích hoạt KC_07_NO_4G_PROFILE (Thiếu profile trên mạng lõi).",
    callout_type="NOTE", title_override="TIÊU CHUẨN ĐÁNH GIÁ TỶ LỆ:")

doc.add_page_break()

# ==========================================
# CHƯƠNG 5: PHÂN HỆ MOBILE INTERNET (DATA)
# ==========================================
add_styled_heading(doc, "CHƯƠNG 5: PHÂN HỆ MOBILE INTERNET (DATA) — QUY TRÌNH TIỀN KIỂM 360°", level=1)
add_p(doc, "Phân hệ Mobile Internet là module cốt lõi giải quyết hơn 70% tổng khối lượng khiếu nại của khách hàng (mạng chậm, không vào được mạng, trừ tiền vô lý). Giao diện chi tiết của mỗi phiếu được chia thành 3 Card thông tin chuyên sâu:")

add_image_safe(doc, IMG_EXPANDED, width_inches=6.3, caption_text="Hình 5.1: Chi tiết toàn cảnh 3 Card nghiệp vụ khi mở rộng một phiếu phản ánh Data")

add_styled_heading(doc, "5.1. Cấu trúc 3 Card nghiệp vụ tiền kiểm", level=2)
add_bullet(doc, "Chứa mã phiếu OneOSS, số điện thoại, nội dung phản ánh gốc của khách hàng, kết luận tự động của hệ thống, và màu sắc nhận diện sự cố.", "Card 1 - Thông tin phiếu & Kết luận sơ bộ: ")
add_bullet(doc, "Hiển thị gói cước đang có trên OCS, cờ khóa mở dịch vụ NAM, tốc độ QoS cam kết, cùng dữ liệu sóng trạm CEM (RSRP, SINR, mã trạm BTS phục vụ).", "Card 2 - Profile Core SAPC & Dữ liệu Vô tuyến CEM: ")
add_bullet(doc, "Danh sách các phiên CDR BTools (thời gian, bytes, RAT, Service ID), công cụ nhận diện Phường/Xã từ GPS trạm, danh mục 73 mã nguyên nhân OneOSS, và nút thực hiện.", "Card 3 - Nhật ký BTools & Thao tác OneOSS: ")

add_image_safe(doc, IMG_CARD2, width_inches=6.0, caption_text="Hình 5.2: Card 2 - Thông tin Profile gói cước Core SAPC và chất lượng sóng trạm CEM")

add_styled_heading(doc, "5.2. Luồng thao tác xử lý ca bệnh Data thực tế (Case Study)", level=2)
add_p(doc, "Dưới đây là quy trình chuẩn hóa dành cho KTV khi tiếp nhận ca phản ánh 'Khách hàng báo mạng chậm':")
add_bullet(doc, "KTV nhấn vào dòng phiếu trên bảng điều khiển để mở rộng khung chi tiết 3 Card.", "Bước 1 - Mở phiếu: ")
add_bullet(doc, "Quan sát Card 1: Xem kết luận sơ bộ của Bot (Ví dụ: THUÊ BAO BỊ BÓP BĂNG THÔNG).", "Bước 2 - Đọc kết luận: ")
add_bullet(doc, "Kiểm tra Card 2: Xem dung lượng gói cước đã dùng hết chưa; xem chỉ số RSRP trạm CEM có tốt không (RSRP > -90 dBm là sóng khỏe).", "Bước 3 - Đối soát Card 2: ")
add_bullet(doc, "Kiểm tra Card 3: Nhìn vào bảng BTools, thấy xuất hiện mã 10003 hoặc 10002 -> Xác nhận 100% khách hàng bị bóp băng thông.", "Bước 4 - Xác nhận nguyên nhân: ")
add_bullet(doc, "Nhấn nút 'Nhận diện P/X từ BTS' để tự động điền địa bàn chuẩn của trạm phát.", "Bước 5 - Chuẩn hóa địa bàn: ")
add_bullet(doc, "Chọn mã nguyên nhân 5.1 'Không đáp ứng do Thuê bao hết lưu lượng/bị hạ băng thông' và nhấn 'Đóng phiếu OneOSS'.", "Bước 6 - Đóng phiếu: ")

add_image_safe(doc, IMG_CARD3, width_inches=6.0, caption_text="Hình 5.3: Card 3 - Lịch sử phiên BTools, chọn mã nguyên nhân OneOSS và nút đóng phiếu")

doc.add_page_break()

# ==========================================
# CHƯƠNG 6: PHÂN HỆ CUỘC GỌI & THOẠI
# ==========================================
add_styled_heading(doc, "CHƯƠNG 6: PHÂN HỆ CUỘC GỌI & THOẠI (VOICE / VOLTE / HLR / NAM)", level=1)
add_p(doc, "Phân hệ Thoại chuyên xử lý các khiếu nại liên quan đến không gọi đi được, không nhận được cuộc gọi đến, cuộc gọi bị ngắt quãng, hoặc lỗi dịch vụ thoại chất lượng cao VoLTE (Voice over LTE).")

add_image_safe(doc, IMG_VOICE, width_inches=6.3, caption_text="Hình 6.1: Giao diện phân hệ xử lý phản ánh Dịch vụ Cuộc gọi & Thoại")

add_styled_heading(doc, "6.1. Nguyên lý kiểm tra Mạng lõi CS Core & IMS VoLTE", level=2)
add_p(doc, "Hệ thống tự động kích hoạt 4 bước kiểm tra chuyên sâu trên mạng lõi viễn thông:")
add_bullet(doc, "Truy vấn cơ sở dữ liệu HLR/VLR xem thuê bao có đang ở trạng thái Hoạt động bình thường (Active) hay bị Tạm dừng (Suspended), Thu hồi (Barred).", "1. Kiểm tra trạng thái thuê bao HLR: ")
add_bullet(doc, "Xác minh cờ NAM trên Core SAPC. Nếu cờ NAM bị khóa do nợ cước hoặc chặn chiều theo yêu cầu, thuê bao sẽ không thể thực hiện cuộc gọi đi.", "2. Kiểm tra cờ khóa dịch vụ NAM: ")
add_bullet(doc, "Kiểm tra SIM đã kích hoạt tính năng VoLTE trên HSS Core và thiết bị đã bật công tắc VoLTE chưa. Nếu chưa có VoLTE, khi gọi thiết bị sẽ phải chuyển mạch về sóng 2G/3G (CSFB - Circuit Switched Fallback).", "3. Kiểm tra Profile IMS VoLTE: ")
add_bullet(doc, "Phân loại rõ khiếu nại thuộc chiều Gọi đi (Calling Party) hay chiều Gọi đến (Called Party) để khoanh vùng trạm phát của bên bị sự cố.", "4. Phân tích chiều cuộc gọi (Bước 2.3/2.4): ")

add_callout(doc, 
    "HƯỚNG XỬ LÝ LỖI CUỘC GỌI CSFB:\n"
    "Nếu khách hàng phản ánh 'Vừa bật 4G mà có người gọi đến là mất mạng data', đây là biểu hiện máy chưa bật VoLTE. "
    "Khi có cuộc gọi đến, máy buộc phải hạ sóng về 2G để nhận cuộc gọi, dẫn đến mất kết nối 4G. "
    "KTV hướng dẫn khách hàng gửi tin nhắn 'HDV' gửi 888 để mở VoLTE miễn phí và bật VoLTE trong cài đặt máy.",
    callout_type="NOTE", title_override="HƯỚNG DẪN KHÁCH HÀNG:")

doc.add_page_break()

# ==========================================
# CHƯƠNG 7: PHÂN HỆ CHẶN SPAM NGOẠI MẠNG
# ==========================================
add_styled_heading(doc, "CHƯƠNG 7: PHÂN HỆ CHẶN SPAM NGOẠI MẠNG (NGHỊ ĐỊNH 91 & CCOS)", level=1)
add_p(doc, "Đây là phân hệ đặc thù nhằm giải quyết các khiếu nại của thuê bao VinaPhone bị hệ thống phòng chống cuộc gọi rác tự động chặn chiều gọi đi sang các nhà mạng khác (Viettel, MobiFone, Vietnamobile) theo quy định của Nghị định 91/2020/NĐ-CP của Chính phủ.")

add_image_safe(doc, IMG_SPAM, width_inches=6.3, caption_text="Hình 7.1: Giao diện phân hệ xử lý phản ánh Chặn cuộc gọi ngoại mạng theo Nghị định 91")

add_styled_heading(doc, "7.1. Cơ chế phát hiện và nhận diện nhà mạng bị ảnh hưởng", level=2)
add_p(doc, "Hệ thống tự động phân tích phản ánh của khách hàng và nhật ký chặn để bóc tách thông tin trọng yếu:")
add_bullet(doc, "Hệ thống xác định chính xác thuê bao bị chặn gọi sang Viettel, MobiFone hay toàn bộ các mạng ngoại mạng.", "Xác định nhà mạng đối tác: ")
add_bullet(doc, "Thuê bao có phát sinh tần suất gọi đi bất thường trong thời gian ngắn (cuộc gọi ngắn < 10 giây lặp lại nhiều lần đến nhiều số khác nhau).", "Nguyên nhân kích hoạt bộ lọc Spam: ")
add_bullet(doc, "Hệ thống tự động tra cứu xem khách hàng đã nộp văn bản cam kết không phát tán cuộc gọi rác tại điểm giao dịch hay qua ứng dụng MyVNPT chưa.", "Đối soát cam kết CCOS: ")

add_styled_heading(doc, "7.2. Hướng dẫn quy trình gỡ chặn và đóng phiếu", level=2)
add_bullet(doc, "Nếu hệ thống CCOS ghi nhận ĐÃ CÓ CAM KẾT HỢP LỆ: KTV kích hoạt lệnh gỡ chặn trực tiếp trên giao diện và đóng phiếu OneOSS thông báo dịch vụ đã được khôi phục.", "Trường hợp 1 (Đã cam kết): ")
add_bullet(doc, "Nếu hệ thống CCOS ghi nhận CHƯA CÓ CAM KẾT: KTV tuyệt đối không tự ý mở chặn; chọn mẫu phản hồi hướng dẫn khách hàng mang CCCD qua điểm giao dịch VinaPhone gần nhất để ký biên bản cam kết sử dụng dịch vụ.", "Trường hợp 2 (Chưa cam kết): ")

doc.add_page_break()

# ==========================================
# CHƯƠNG 8: PHÂN HỆ TIN NHẮN (SMS) & SMSC
# ==========================================
add_styled_heading(doc, "CHƯƠNG 8: PHÂN HỆ TIN NHẮN (SMS) & CỔNG TRA CỨU SMSC GATEWAY CDR", level=1)
add_p(doc, "Khiếu nại không nhận được tin nhắn OTP ngân hàng, mã xác thực dịch vụ (VNeID, mạng xã hội) hoặc không gửi được SMS là nhóm sự cố có mức độ khẩn cấp cao. Phân hệ SMS tích hợp trực tiếp Cổng tra cứu SMSC Gateway CDR cho phép đối soát từng tin nhắn thời gian thực.")

add_image_safe(doc, IMG_SMS, width_inches=6.3, caption_text="Hình 8.1: Màn hình tiếp nhận phản ánh Tin nhắn SMS và nút kích hoạt Cổng tra cứu SMSC CDR")

add_styled_heading(doc, "8.1. Cửa sổ tra cứu nhật ký SMSC Gateway thời gian thực", level=2)
add_p(doc, "KTV nhấn nút 'Tra cứu SMSC CDR' tại từng phiếu để mở modal đối soát chi tiết:")

add_image_safe(doc, IMG_SMS_MODAL, width_inches=6.3, caption_text="Hình 8.2: Cửa sổ tra cứu SMSC Gateway CDR hiển thị chi tiết Brandname, thời gian và mã trạng thái phát tin")

add_styled_heading(doc, "8.2. Bảng mã trạng thái phát tin nhắn (Delivery Status & Error Codes)", level=2)
add_p(doc, "Dựa vào mã trả về từ tổng đài SMSC, KTV có thể chỉ ra chính xác nguyên nhân lỗi thuộc về mạng VinaPhone, ngân hàng đối tác, hay thiết bị khách hàng:")

smsc_codes = [
    ("Mã 0 (Delivered)", "Phát tin thành công", 
     "Tin nhắn đã được chuyển giao thành công đến thẻ SIM/thiết bị của khách hàng. Nếu khách vẫn báo không thấy, hướng dẫn kiểm tra thư mục 'Tin nhắn rác/Spam' hoặc ứng dụng chặn tin nhắn trên máy."),
    ("Mã 1 (Expired)", "Hết hạn lưu tin", 
     "Tin nhắn nằm chờ trên tổng đài SMSC quá thời gian quy định (thường là 24h - 48h) do thuê bao tắt máy hoặc ngoài vùng phủ sóng liên tục."),
    ("Mã 2 (Deleted)", "Bị hủy bởi hệ thống", 
     "Tin nhắn bị xóa hoặc hủy do quy định lọc spam hoặc quá tải hàng đợi."),
    ("Mã 6 (Undeliverable)", "Không thể phân phát", 
     "Tổng đài không thể định tuyến tin nhắn đến thiết bị (thẻ SIM bị hỏng, bộ nhớ máy đầy tin nhắn, hoặc cấu hình máy từ chối tin nhắn Brandname)."),
    ("Mã 21 (Absent Subscriber)", "Thuê bao vắng mặt", 
     "Thiết bị tắt nguồn, tháo SIM, hoặc đang ở khu vực mất sóng hoàn toàn tại thời điểm ngân hàng gửi mã OTP."),
    ("Mã 27 (Call Barred)", "Bị chặn chiều nhận", 
     "Thuê bao đang bị khóa chiều nhận tin nhắn trên hệ thống HLR (do nợ cước hoặc đăng ký gói chặn dịch vụ).")
]
create_styled_table(doc, ["Mã Trạng Thái SMSC", "Ý Nghĩa Kỹ Thuật", "Phân Tích Chi Tiết & Hướng Dẫn Xử Lý"], smsc_codes, [1.5, 1.8, 3.2])

doc.add_page_break()

# ==========================================
# CHƯƠNG 9: PHÂN HỆ CVQT & SIM / ESIM
# ==========================================
add_styled_heading(doc, "CHƯƠNG 9: PHÂN HỆ CHUYỂN VÙNG QUỐC TẾ (CVQT / ROAMING) & SIM / ESIM", level=1)
add_p(doc, "Phân hệ CVQT và Dịch vụ SIM giải quyết các sự cố chuyên biệt của khách hàng di chuyển ra nước ngoài hoặc gặp trục trặc về phôi SIM vật lý và profile eSIM.")

add_styled_heading(doc, "9.1. Quy trình chẩn đoán Chuyển vùng quốc tế (Data Roaming)", level=2)
add_bullet(doc, "Thuê bao đã đăng ký mở dịch vụ CVQT (IR) trước khi xuất cảnh chưa (soạn DK CVQT gửi 9123).", "Kiểm tra Profile HSS Roaming: ")
add_bullet(doc, "Khách hàng đã đăng ký các gói cước Data Roaming (như R500N, IR_POST, IR_PPS) chưa. Nếu có gói, kiểm tra hạn dùng và dung lượng gói cước.", "Kiểm tra gói cước Roaming: ")
add_bullet(doc, "Khi ra nước ngoài, thiết bị bắt buộc phải bật tùy chọn 'Chuyển vùng dữ liệu' (Data Roaming) trong phần Cài đặt di động của máy. Đây là lỗi phổ biến nhất của khách hàng.", "Kiểm tra cài đặt máy khách hàng: ")

add_styled_heading(doc, "9.2. Quy trình xử lý lỗi SIM vật lý và eSIM", level=2)
add_p(doc, "Các bước chẩn đoán nhanh khi nghi ngờ lỗi do phần cứng SIM:")
add_bullet(doc, "Kiểm tra số serial SIM trên CCBS. Nếu phôi SIM là SIM 2G/3G cũ sản xuất trước năm 2018, bắt buộc tư vấn khách hàng đổi sang USIM 4G/5G.", "1. Phôi SIM cũ lỗi thời: ")
add_bullet(doc, "SIM bị mòn mạch đồng hoặc oxy hóa dẫn đến thiết bị báo 'Không có thẻ SIM' (No SIM) chập chờn. Hướng dẫn khách hàng thử lắp SIM sang máy khác để loại trừ lỗi khe SIM.", "2. Hỏng tiếp xúc vật lý: ")
add_bullet(doc, "Khách hàng đổi máy hoặc xóa nhầm eSIM profile. KTV kiểm tra mã EID của máy mới và hướng dẫn khách hàng quét lại mã QR code cấp lại qua ứng dụng MyVNPT.", "3. Lỗi cấu hình eSIM: ")

doc.add_page_break()

# ==========================================
# CHƯƠNG 10: QUY CHUẨN ĐÓNG PHIẾU 5.1 & SOC
# ==========================================
add_styled_heading(doc, "CHƯƠNG 10: QUY CHUẨN ĐÓNG PHIẾU ONEOSS 5.1 & QUẢN TRỊ KTV SOC", level=1)
add_p(doc, "Đóng phiếu là công đoạn cuối cùng và có tính pháp lý cao nhất trong quy trình xử lý phản ánh. Để đảm bảo số liệu báo cáo Tập đoàn và Cục Viễn thông không bị sai lệch, KTV bắt buộc phải tuân thủ nghiêm ngặt Quy chuẩn Địa giới hành chính mới và Cheatsheet mã nguyên nhân.")

add_styled_heading(doc, "10.1. Quy chuẩn bắt buộc về Địa giới hành chính 2 cấp (Phường/Xã & 34 Tỉnh/TP mới)", level=2)
add_p(doc, "Theo quy định cải cách hành chính mới của Tập đoàn VNPT, mọi phiếu đóng trên hệ thống OneOSS phân loại 5.1 phải tuân thủ triệt để:")
add_bullet(doc, "[Phường/Xã/Thị trấn], [Tỉnh/Thành phố] (Ví dụ: Phường Bến Nghé, TP. Hồ Chí Minh hoặc Xã Hòa Lạc, TP. Hà Nội).", "1. Cấu trúc chuẩn DUY NHẤT: ")
add_bullet(doc, "Không lấy cấp Thôn, Ấp, Bản, Khóm, Tổ dân phố (như 'Thôn 3', 'Ấp 1', 'Tổ 5'...).", "2. TUYỆT ĐỐI KHÔNG: ")
add_bullet(doc, "Không dùng tên viết tắt viễn thông hay mã trạm BTS (như 'PLO', 'DLI', 'BLU', 'TDM'...).", "3. TUYỆT ĐỐI KHÔNG: ")

add_image_safe(doc, IMG_WARD, width_inches=6.0, caption_text="Hình 10.1: Công cụ nhận diện Phường/Xã chuẩn 2 cấp tự động từ GPS trạm BTS CEM (Port 1708)")

add_styled_heading(doc, "10.2. Bảng Chuẩn 34 Tỉnh / Thành phố mới & Phân bổ 3 Miền", level=2)
add_p(doc, "Toàn bộ mạng lưới viễn thông VNPT được chia thành 34 Tỉnh/TP mới thuộc 3 Miền. KTV bắt buộc phải thuộc danh mục này:")

provinces_34 = [
    ("1", "TP. Hà Nội", "Giữ nguyên", "Miền Bắc (MB)"),
    ("2", "TP. Hải Phòng", "TP. Hải Phòng + Hải Dương", "Miền Bắc (MB)"),
    ("3", "Tỉnh Cao Bằng", "Giữ nguyên", "Miền Bắc (MB)"),
    ("4", "Tỉnh Lạng Sơn", "Giữ nguyên", "Miền Bắc (MB)"),
    ("5", "Tỉnh Lai Châu", "Giữ nguyên", "Miền Bắc (MB)"),
    ("6", "Tỉnh Điện Biên", "Giữ nguyên", "Miền Bắc (MB)"),
    ("7", "Tỉnh Sơn La", "Giữ nguyên", "Miền Bắc (MB)"),
    ("8", "Tỉnh Quảng Ninh", "Giữ nguyên", "Miền Bắc (MB)"),
    ("9", "Tỉnh Tuyên Quang", "Hà Giang + Tuyên Quang", "Miền Bắc (MB)"),
    ("10", "Tỉnh Lào Cai", "Yên Bái + Lào Cai", "Miền Bắc (MB)"),
    ("11", "Tỉnh Thái Nguyên", "Bắc Kạn + Thái Nguyên", "Miền Bắc (MB)"),
    ("12", "Tỉnh Phú Thọ", "Vĩnh Phúc + Hòa Bình + Phú Thọ", "Miền Bắc (MB)"),
    ("13", "Tỉnh Bắc Ninh", "Bắc Giang + Bắc Ninh", "Miền Bắc (MB)"),
    ("14", "Tỉnh Hưng Yên", "Thái Bình + Hưng Yên", "Miền Bắc (MB)"),
    ("15", "Tỉnh Ninh Bình", "Hà Nam + Nam Định + Ninh Bình", "Miền Bắc (MB)"),
    ("16", "Tỉnh Thanh Hóa", "Giữ nguyên", "Miền Bắc (MB)"),
    ("17", "Tỉnh Nghệ An", "Giữ nguyên", "Miền Bắc (MB)"),
    ("18", "Tỉnh Hà Tĩnh", "Giữ nguyên", "Miền Bắc (MB)"),
    ("19", "Tỉnh Lâm Đồng", "Đắk Nông + Bình Thuận + Lâm Đồng", "Miền Nam (MN)"),
    ("20", "TP. Hồ Chí Minh", "TP.HCM + Bình Dương + Bà Rịa – Vũng Tàu", "Miền Nam (MN)"),
    ("21", "TP. Cần Thơ", "TP. Cần Thơ + Sóc Trăng + Hậu Giang", "Miền Nam (MN)"),
    ("22", "Tỉnh Đồng Nai", "Bình Phước + Đồng Nai", "Miền Nam (MN)"),
    ("23", "Tỉnh Tây Ninh", "Long An + Tây Ninh", "Miền Nam (MN)"),
    ("24", "Tỉnh Vĩnh Long", "Bến Tre + Trà Vinh + Vĩnh Long", "Miền Nam (MN)"),
    ("25", "Tỉnh Đồng Tháp", "Tiền Giang + Đồng Tháp", "Miền Nam (MN)"),
    ("26", "Tỉnh Cà Mau", "Bạc Liêu + Cà Mau", "Miền Nam (MN)"),
    ("27", "Tỉnh An Giang", "Kiên Giang + An Giang (gồm Đặc khu Phú Quốc)", "Miền Nam (MN)"),
    ("28", "TP. Huế", "Giữ nguyên (nâng cấp từ Thừa Thiên Huế)", "Miền Trung (MT)"),
    ("29", "TP. Đà Nẵng", "TP. Đà Nẵng + Quảng Nam", "Miền Trung (MT)"),
    ("30", "Tỉnh Quảng Trị", "Quảng Bình + Quảng Trị", "Miền Trung (MT)"),
    ("31", "Tỉnh Quảng Ngãi", "Kon Tum + Quảng Ngãi", "Miền Trung (MT)"),
    ("32", "Tỉnh Gia Lai", "Bình Định + Gia Lai", "Miền Trung (MT)"),
    ("33", "Tỉnh Khánh Hòa", "Ninh Thuận + Khánh Hòa", "Miền Trung (MT)"),
    ("34", "Tỉnh Đắk Lắk", "Phú Yên + Đắk Lắk", "Miền Trung (MT)")
]
create_styled_table(doc, ["STT", "Tỉnh / TP Mới", "Tỉnh / TP Sáp Nhập", "Khu Vực (Miền)"], provinces_34, [0.6, 2.0, 2.5, 1.4])

add_styled_heading(doc, "10.3. Cheatsheet nhóm mã nguyên nhân đóng phiếu OneOSS 5.1", level=2)
add_p(doc, "Hệ thống tích hợp sẵn 73 mã nguyên nhân OneOSS tiêu chuẩn. Dưới đây là các nhóm mã phổ biến nhất trong vận hành hàng ngày:")

add_image_safe(doc, IMG_CAUSE, width_inches=6.0, caption_text="Hình 10.2: Danh mục xổ xuống chọn nhanh mã nguyên nhân đóng phiếu OneOSS chuẩn hoá")

causes_top = [
    ("Mã 5.1.01", "Không đáp ứng do Thuê bao hết lưu lượng/bị hạ băng thông", "Thuê bao có mã bóp 10002..10014, dùng hết data tốc độ cao."),
    ("Mã 5.1.02", "Không đáp ứng do Thiết bị khách hàng/Cài đặt máy", "Máy tắt data, bật VPN 1.1.1.1, máy chưa bật 4G hoặc cấu hình sai APN."),
    ("Mã 5.1.03", "Không đáp ứng do Vùng phủ sóng kém/chập chờn", "Khu vực sóng yếu, rớt 2G/3G > 50%, chuyển VTT tối ưu anten."),
    ("Mã 5.1.04", "Không đáp ứng do Thuê bao chưa khai báo Profile 4G", "Chưa mở HSS 4G, chuyển IT Core khai báo bổ sung."),
    ("Mã 5.1.05", "Không đáp ứng do Trạm phát BTS bị sự cố/mất điện", "Trạm CEM ghi nhận cảnh báo suy hao, mất liên lạc vô tuyến."),
    ("Mã 5.1.06", "Đáp ứng - Đã hướng dẫn khách hàng sử dụng dịch vụ", "Khách hàng không hiểu cách tính cước hoặc thắc mắc gói dịch vụ."),
    ("Mã 5.1.07", "Không đáp ứng do Thuê bao bị chặn theo Nghị định 91", "Thuê bao bị bộ lọc cuộc gọi rác chặn chiều gọi đi.")
]
create_styled_table(doc, ["Mã Nguyên Nhân", "Tên Nguyên Nhân OneOSS Chuẩn", "Điều Kiện Kỹ Thuật Áp Dụng"], causes_top, [1.3, 2.7, 2.5])

add_styled_heading(doc, "10.4. Phân hệ Quản trị KTV SOC & Giám sát vận hành", level=2)
add_p(doc, "Phân hệ Quản trị dành cho Trưởng ca SOC hoặc Điều hành viên viễn thông phân chia địa bàn phụ trách:")

add_image_safe(doc, IMG_KTV_MGT, width_inches=6.3, caption_text="Hình 10.3: Màn hình Quản trị danh sách KTV, phân quyền tỉnh thành và cấu hình Auto-Close")

add_bullet(doc, "Gán tài khoản KTV vào từng Tỉnh/TP hoặc nhóm dịch vụ cụ thể để lọc danh sách phiếu phù hợp.", "Phân vùng phụ trách: ")
add_bullet(doc, "Cho phép kích hoạt tính năng tự động đóng phiếu đối với các ca lỗi thuần túy về gói cước (hết lưu lượng, hạ băng thông) theo cấu hình an toàn.", "Cấu hình Auto-Close: ")
add_bullet(doc, "Theo dõi số lượng phiếu tiếp nhận, tỷ lệ xử lý đúng hạn (SLA) và chất lượng phân loại phiếu của từng nhân sự trong ca trực.", "Giám sát hiệu suất SLA: ")

add_callout(doc, 
    "TỔNG KẾT NGUYÊN TẮC VÀNG DÀNH CHO KTV:\n"
    "1. Luôn nhìn vào dữ liệu kỹ thuật thực tế (Card 2 và Card 3) trước khi đưa ra nhận định.\n"
    "2. Không bao giờ đóng phiếu với địa danh cấp thôn/ấp hoặc mã trạm viết tắt.\n"
    "3. Nếu có nghi ngờ về gói cước (như D159SC thiếu ODA_BIG_OCS), lập tức chuyển IT/CCBS hỗ trợ.\n"
    "4. Tận dụng triệt để tính năng nhận diện Phường/Xã từ GPS trạm để tiết kiệm thời gian và đảm bảo độ chính xác.",
    callout_type="SUCCESS", title_override="LỜI KẾT KHÓA ĐÀO TẠO:")

# Lưu file Word
doc.save(OUTPUT_DOCX)
print(f"Đã tạo thành công bộ tài liệu đào tạo chuyên sâu Word tại: {OUTPUT_DOCX}")
