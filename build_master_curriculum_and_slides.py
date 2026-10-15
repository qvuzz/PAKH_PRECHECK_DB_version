# -*- coding: utf-8 -*-
"""
Script xây dựng Bộ Giáo Trình Đào Tạo AI PAKH 5H (Word .docx)
và Bộ Slide Trình Chiếu Chuẩn Doanh Nghiệp VNPT (PowerPoint .pptx)
TỔNG THỜI LƯỢNG ĐÀO TẠO: ĐÚNG TRÒN 5 TIẾNG (300 PHÚT)
Phân bổ 5 Phần sư phạm:
- PHẦN I: Tổng quan, Bối cảnh & Kiến trúc Hybrid AI (45 Phút)
- PHẦN II: Thư viện Kỹ thuật & 7 Kịch bản Chẩn đoán Cốt lõi (60 Phút)
- PHẦN III: Cẩm nang Vận hành Thực chiến 6 Phân hệ Nghiệp vụ (90 Phút - TRỌNG TÂM)
- PHẦN IV: Quy chuẩn Đóng phiếu OneOSS 5.1 & Auto-Close có kiểm soát (45 Phút)
- PHẦN V: Thực hành Tình huống (Hands-on Lab) & Đánh giá Cuối khóa (45 Phút)
[Giải lao giữa giờ Teabreak: 15 Phút]
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

from pptx import Presentation
from pptx.util import Inches as PptInches, Pt as PptPt
from pptx.dml.color import RGBColor as PptRGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

ARTIFACT_DIR = r"C:\Users\lequa\OneDrive - VNPT\python\PAKH_PRECHECK\brain_crops"
if not os.path.exists(ARTIFACT_DIR):
    ARTIFACT_DIR = r"C:\Users\lequa\.gemini\antigravity-ide\brain\233538e9-b8ef-4c40-b0c3-e80e1868d2c3"

IMG_DIR = os.path.join(ARTIFACT_DIR, "manual_crops")

# Danh sách ảnh chụp thực tế
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

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DOCX = os.path.join(ROOT_DIR, "Giao_trinh_Dao_tao_AI_PAKH_5h.docx")
OUT_PPTX = os.path.join(ROOT_DIR, "SLIDE_HUONG_DAN_SU_DUNG_VNPT_TTS_PRECHECK.pptx")
OUT_PPTX_ALT = os.path.join(ROOT_DIR, "SLIDE_GIAO_TRINH_DAO_TAO_AI_PAKH_5H.pptx")

# Màu thương hiệu VNPT
C_VNPT_NAVY   = RGBColor(0, 43, 92)      # Deep Navy #002B5C
C_VNPT_BLUE   = RGBColor(0, 82, 165)     # Primary Blue #0052A5
C_VNPT_CYAN   = RGBColor(2, 132, 199)    # Cyan Accent #0284C7
C_TEXT_DARK   = RGBColor(30, 41, 59)     # Slate 800 #1E293B
C_TEXT_MUTED  = RGBColor(100, 116, 139)  # Slate 500 #64748B

PPT_NAVY      = PptRGBColor(10, 25, 47)  # #0A192F
PPT_BLUE      = PptRGBColor(0, 82, 165)  # #0052A5
PPT_CYAN      = PptRGBColor(2, 132, 199) # #0284C7
PPT_DARK      = PptRGBColor(15, 23, 42)  # #0F172A
PPT_MUTED     = PptRGBColor(100, 116, 139)
PPT_WHITE     = PptRGBColor(255, 255, 255)
PPT_CARD_BG   = PptRGBColor(255, 255, 255)
PPT_CARD_BD   = PptRGBColor(226, 232, 240)
PPT_WARN      = PptRGBColor(217, 119, 6)
PPT_SUCCESS   = PptRGBColor(22, 163, 74)
PPT_DANGER    = PptRGBColor(220, 38, 38)

def set_cell_background(cell, fill_hex):
    tc_pr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tc_pr.append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=140, right=140):
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
    run.font.name = 'Segoe UI'
    if level == 1:
        run.font.size = Pt(15.5)
        run.font.bold = True
        run.font.color.rgb = C_VNPT_BLUE
        h.paragraph_format.space_before = Pt(20)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
    elif level == 2:
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = C_VNPT_NAVY
        h.paragraph_format.space_before = Pt(14)
        h.paragraph_format.space_after = Pt(4)
        h.paragraph_format.keep_with_next = True
    elif level == 3:
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = C_TEXT_DARK
        h.paragraph_format.space_before = Pt(10)
        h.paragraph_format.space_after = Pt(3)
        h.paragraph_format.keep_with_next = True
    return h

def add_p(doc, text="", bold_prefix="", space_after=5, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.22
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Segoe UI'
        r_pre.font.size = Pt(10.5)
        r_pre.font.bold = True
        r_pre.font.color.rgb = C_TEXT_DARK
    if text:
        r_txt = p.add_run(text)
        r_txt.font.name = 'Segoe UI'
        r_txt.font.size = Pt(10.5)
        r_txt.font.italic = italic
        r_txt.font.color.rgb = C_TEXT_DARK
    return p

def add_bullet(doc, text, bold_prefix="", space_after=3):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.22
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = 'Segoe UI'
        r_pre.font.size = Pt(10.5)
        r_pre.font.bold = True
        r_pre.font.color.rgb = C_TEXT_DARK
    r_txt = p.add_run(text)
    r_txt.font.name = 'Segoe UI'
    r_txt.font.size = Pt(10.5)
    r_txt.font.color.rgb = C_TEXT_DARK
    return p

def add_callout(doc, text, callout_type="NOTE", title_override=None):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.6)
    
    if callout_type == "IMPORTANT":
        fill = "FFFBEB"
        border_color = "F59E0B"
        title = title_override or "LƯU Ý NGHIỆP VỤ BẮT BUỘC:"
        title_color = RGBColor(180, 83, 9)
    elif callout_type == "SUCCESS":
        fill = "F0FDF4"
        border_color = "10B981"
        title = title_override or "QUY CHUẨN XÁC THỰC THÀNH CÔNG:"
        title_color = RGBColor(22, 101, 52)
    elif callout_type == "WARNING":
        fill = "FEF2F2"
        border_color = "EF4444"
        title = title_override or "CẢNH BÁO NGUY CƠ / LỖI THƯỜNG GẶP:"
        title_color = RGBColor(185, 28, 28)
    else:
        fill = "F0F9FF"
        border_color = "0284C7"
        title = title_override or "HƯỚNG DẪN THỰC CHIẾN / MẸO VẬN HÀNH:"
        title_color = RGBColor(3, 105, 161)
        
    set_cell_background(cell, fill)
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)
    
    tc_pr = cell._element.get_or_add_tcPr()
    borders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                        f'<w:top w:val="none"/>'
                        f'<w:left w:val="single" w:sz="32" w:space="0" w:color="{border_color}"/>'
                        f'<w:bottom w:val="none"/>'
                        f'<w:right w:val="none"/>'
                        f'</w:tcBorders>')
    tc_pr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    r_tit = p.add_run(title + "\n")
    r_tit.font.name = 'Segoe UI'
    r_tit.font.size = Pt(10)
    r_tit.font.bold = True
    r_tit.font.color.rgb = title_color
    
    r_txt = p.add_run(text)
    r_txt.font.name = 'Segoe UI'
    r_txt.font.size = Pt(9.5)
    r_txt.font.color.rgb = C_TEXT_DARK
    
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)

def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run(text)
    run.font.name = 'Segoe UI'
    run.font.size = Pt(9)
    run.font.italic = True
    run.font.color.rgb = C_TEXT_MUTED

def add_image_safe(doc, img_path, width_inches=6.2, caption_text=None):
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        doc.add_picture(img_path, width=Inches(width_inches))
        if caption_text:
            add_caption(doc, caption_text)

def create_styled_table(doc, headers, data, col_widths=None):
    tbl = doc.add_table(rows=len(data) + 1, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    # Header Row
    hdr_cells = tbl.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "0052A5")
        set_cell_margins(hdr_cells[i], top=110, bottom=110, left=130, right=130)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.name = 'Segoe UI'
            run.font.size = Pt(9.5)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            
    # Data Rows
    for r_idx, row_data in enumerate(data):
        row_cells = tbl.rows[r_idx + 1].cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, cell_value in enumerate(row_data):
            row_cells[c_idx].text = str(cell_value)
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=85, bottom=85, left=110, right=110)
            p = row_cells[c_idx].paragraphs[0]
            for run in p.runs:
                run.font.name = 'Segoe UI'
                run.font.size = Pt(9)
                run.font.color.rgb = C_TEXT_DARK
                
    if col_widths:
        for row in tbl.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Inches(w)
                
    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_before = Pt(0)
    p_space.paragraph_format.space_after = Pt(8)
    return tbl

print("🚀 Đang khởi tạo Bộ Giáo Trình Đào Tạo AI PAKH 5H (Word .docx)...")
doc = Document()

# Lề trang A4 chuẩn
for s in doc.sections:
    s.top_margin = Inches(0.8)
    s.bottom_margin = Inches(0.8)
    s.left_margin = Inches(0.85)
    s.right_margin = Inches(0.85)
    s.page_width = Inches(8.27)
    s.page_height = Inches(11.69)
    # Header & Footer
    hdr = s.header
    p_hdr = hdr.paragraphs[0]
    p_hdr.text = "TẬP ĐOÀN VNPT — GIÁO TRÌNH ĐÀO TẠO ỨNG DỤNG AI & TIỀN KIỂM PAKH (VNPT TTS PRECHECK)"
    p_hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for r in p_hdr.runs:
        r.font.name = 'Segoe UI'
        r.font.size = Pt(8)
        r.font.color.rgb = C_TEXT_MUTED
        
    ftr = s.footer
    p_ftr = ftr.paragraphs[0]
    p_ftr.text = "Tài liệu lưu hành nội bộ VNPT • Phiên bản 2026.04 • Khóa đào tạo chuyên đề 5 tiếng (300 phút)"
    p_ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in p_ftr.runs:
        r.font.name = 'Segoe UI'
        r.font.size = Pt(8)
        r.font.color.rgb = C_TEXT_MUTED

# ==========================================
# TRANG BÌA EXECUTIVE CHUẨN DOANH NGHIỆP
# ==========================================
p_cover_top = doc.add_paragraph()
p_cover_top.paragraph_format.space_before = Pt(36)
p_cover_top.paragraph_format.space_after = Pt(4)
r_org = p_cover_top.add_run("TẬP ĐOÀN BƯU CHÍNH VIỄN THÔNG VIỆT NAM (VNPT)\nTỔNG CÔNG TY DỊCH VỤ VIỄN THÔNG (VNPT-VINAPHONE)")
r_org.font.name = 'Segoe UI'
r_org.font.size = Pt(12)
r_org.font.bold = True
r_org.font.color.rgb = C_VNPT_BLUE
p_cover_top.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_div = doc.add_paragraph()
p_div.paragraph_format.space_after = Pt(50)
r_div = p_div.add_run("TRUNG TÂM ĐIỀU HÀNH MẠNG & HỖ TRỢ KỸ THUẬT (VNPT SOC / TTS)")
r_div.font.name = 'Segoe UI'
r_div.font.size = Pt(10.5)
r_div.font.bold = True
r_div.font.color.rgb = C_VNPT_CYAN
p_div.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_main_title = doc.add_paragraph()
p_main_title.paragraph_format.space_after = Pt(12)
r_mt = p_main_title.add_run("GIÁO TRÌNH & BỘ TÀI LIỆU ĐÀO TẠO CHUYÊN ĐỀ")
r_mt.font.name = 'Segoe UI'
r_mt.font.size = Pt(14)
r_mt.font.bold = True
r_mt.font.color.rgb = C_TEXT_MUTED
p_main_title.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_title = doc.add_paragraph()
p_title.paragraph_format.space_after = Pt(16)
r_t = p_title.add_run("ỨNG DỤNG AI & TỰ ĐỘNG HÓA\nTRONG XỬ LÝ PHẢN ÁNH KHÁCH HÀNG (PAKH)\nHỆ THỐNG VNPT TTS PRECHECK")
r_t.font.name = 'Segoe UI'
r_t.font.size = Pt(22)
r_t.font.bold = True
r_t.font.color.rgb = C_VNPT_NAVY
p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_sub = doc.add_paragraph()
p_sub.paragraph_format.space_after = Pt(80)
r_sub = p_sub.add_run("CẨM NANG TOÀN DIỆN VỀ KIẾN TRÚC MẠNG LÕI, THƯ VIỆN KỊCH BẢN CHẨN ĐOÁN,\nQUY TRÌNH VẬN HÀNH 6 PHÂN HỆ VÀ ĐÓNG PHIẾU ONEOSS 5.1 CHUẨN 34 TỈNH/TP")
r_sub.font.name = 'Segoe UI'
r_sub.font.size = Pt(11)
r_sub.font.color.rgb = C_TEXT_DARK
p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

p_info = doc.add_paragraph()
p_info.paragraph_format.space_after = Pt(6)
r_info = p_info.add_run(
    "Tổng thời lượng chương trình: Đúng 5 Tiếng (300 Phút — gồm 60% thực hành thực chiến)\n"
    "Đối tượng đào tạo: Kỹ thuật viên (KTV) Viễn thông Tỉnh/TP, Điều hành SOC, Hỗ trợ kỹ thuật 18001091\n"
    "Hệ thống tích hợp: OneOSS TTS • Core SAPC PCRF • BTools CDP • CEM Vô tuyến • SMSC Gateway • Port 1708 Geocoding\n"
    "Phiên bản ban hành: 2026.04 (Chuẩn hóa Địa giới hành chính 2 cấp theo 34 Tỉnh/TP mới)"
)
r_info.font.name = 'Segoe UI'
r_info.font.size = Pt(10)
r_info.font.color.rgb = C_TEXT_DARK
p_info.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_page_break()

# ==========================================
# MỤC TIÊU & KHUNG TIẾN ĐỘ ĐÀO TẠO 5 TIẾNG (300 PHÚT)
# ==========================================
add_styled_heading(doc, "1. MỤC TIÊU KHÓA ĐÀO TẠO & NĂNG LỰC ĐẦU RA", level=1)
add_p(doc, "Sau khi hoàn thành khóa đào tạo chuyên đề 5 tiếng (300 phút), học viên đạt được các chuẩn năng lực thực chiến sau:")
add_bullet(doc, "Hiểu rõ bản chất của AI ứng dụng thực chiến trong mạng viễn thông VNPT — không phải chatbot trả lời văn bản chung chung mà là mô hình kết hợp chặt chẽ giữa AI Đọc hiểu ngôn ngữ tự nhiên (NLP/LLM) và Dữ liệu đo kiểm hạ tầng mạng lõi thời gian thực.", "Về nhận thức: ")
add_bullet(doc, "Nắm vững luồng dữ liệu 4 nguồn (OneOSS TTS, BTools 4G/5G, SAPC Core, CEM vô tuyến, SMSC CDR), từ điển mã bóp băng thông serviceid.json và công nghệ sóng rattype.json.", "Về kiến thức: ")
add_bullet(doc, "Thành thạo vận hành Dashboard tiền kiểm tự động, nhận diện chính xác nguyên nhân của mọi ca khiếu nại (bóp băng thông, treo phiên OCS, rớt 2G/3G, khóa cờ NAM, chặn spam NĐ 91, mất SMS OTP) trong 1 giây.", "Về kỹ năng chẩn đoán: ")
add_bullet(doc, "Vận hành an toàn quy trình đóng phiếu tự động OneOSS (Auto-Close) và bán tự động, tuân thủ tuyệt đối quy chuẩn địa giới hành chính 2 cấp (Phường/Xã và 34 Tỉnh/TP mới).", "Về ra quyết định: ")

add_styled_heading(doc, "2. KHUNG THỜI GIAN & TIẾN ĐỘ ĐÀO TẠO CHUẨN 5 TIẾNG (300 PHÚT)", level=1)
add_p(doc, "Khóa học được thiết kế theo chuẩn sư phạm thực chiến viễn thông, trong đó thời lượng thực hành thao tác trên 6 phân hệ và xử lý tình huống chiếm 60% tổng thời gian (180 phút):")

schedule_data_5h = [
    ("PHẦN I (45 Phút)", "TỔNG QUAN, BỐI CẢNH & KIẾN TRÚC HYBRID AI", "Thực trạng thủ công vs Digital Copilot; Kiến trúc 3 tầng (NLP, Đa luồng, Bypass) & Bản đồ 7 hệ thống vệ tinh"),
    ("PHẦN II (60 Phút)", "THƯ VIỆN KỸ THUẬT & 7 KỊCH BẢN CHẨN ĐOÁN", "serviceid.json (Ma trận bóp 8 mức, ODA_BIG_OCS, OTT), rattype.json & Phân tích sâu 7 kịch bản chẩn đoán"),
    ("☕ (15 Phút)", "GIẢI LAO GIỮA GIỜ (TEABREAK)", "Nghỉ giải lao nạp năng lượng chuẩn bị cho phần thực hành thực chiến"),
    ("PHẦN III (90 Phút)\n[TRỌNG TÂM]", "CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ", "Thực hành chi tiết: Mobile Internet (3 Card), Thoại (VoLTE/NAM), Chặn Spam NĐ 91, SMSC Gateway CDR, Roaming & SOC"),
    ("PHẦN IV (45 Phút)", "QUY CHUẨN ĐÓNG PHIẾU 5.1 & AUTO-CLOSE AN TOÀN", "Địa giới 2 cấp [Phường/Xã], [Tỉnh/TP] (34 Tỉnh mới, 1-click GPS trạm), Cheatsheet 73 mã OneOSS & 3 tiêu chí Auto-Close"),
    ("PHẦN V (45 Phút)", "THỰC HÀNH TÌNH HUỐNG (LAB) & ĐÁNH GIÁ CUỐI KHÓA", "Hands-on Lab 2 bài tập lớn (Ca mạng chậm & Ca thoại bước 2.3), 10 câu hỏi trắc nghiệm & Giải đáp vướng mắc ca trực")
]
create_styled_table(doc, ["Khung Thời Gian", "Tên Học Phần / Mô-đun", "Nội Dung Trọng Tâm & Chuẩn Đầu Ra"], schedule_data_5h, [1.5, 2.7, 2.4])

doc.add_page_break()

# ==========================================
# PHẦN I: TỔNG QUAN, BỐI CẢNH & KIẾN TRÚC
# ==========================================
add_styled_heading(doc, "PHẦN I: TỔNG QUAN, BỐI CẢNH & KIẾN TRÚC HYBRID AI (45 PHÚT)", level=1)

add_styled_heading(doc, "1. Thực trạng quy trình xử lý PAKH thủ công truyền thống (15 Phút)", level=2)
add_p(doc, "Khi một khách hàng phản ánh mạng chậm hoặc mất sóng, quy trình thủ công yêu cầu KTV viễn thông phải mở phân tán 5 đến 7 tab trình duyệt khác nhau:")
add_bullet(doc, "Đăng nhập OneOSS TTS Mới / Cũ để đọc nội dung phản ánh gốc của khách hàng.", "Bước 1: ")
add_bullet(doc, "Đăng nhập BTools CDP cào lịch sử phiên kết nối data 5 ngày gần nhất để kiểm tra lưu lượng tải về và mã lỗi.", "Bước 2: ")
add_bullet(doc, "Đăng nhập Core SAPC / PCRF tra cứu trạng thái gói cước, hạn dùng, cờ NAM và QoS cam kết.", "Bước 3: ")
add_bullet(doc, "Mở hệ thống CEM tra cứu chỉ số RSRP, SINR của trạm BTS tại vị trí khách hàng phản ánh.", "Bước 4: ")
add_bullet(doc, "Mở hệ thống CCOS đối soát biên bản cam kết mở mạng nếu phản ánh bị chặn cuộc gọi rác.", "Bước 5: ")
add_bullet(doc, "Tự gõ kết luận kỹ thuật, tự tìm mã nguyên nhân trong danh mục 73 mã OneOSS và bấm đóng phiếu.", "Bước 6: ")

add_callout(doc, 
    "HẬU QUẢ CỦA QUY TRÌNH THỦ CÔNG TRUYỀN THỐNG:\n"
    "• Tốn từ 5 đến 10 phút cho mỗi phiếu khiếu nại.\n"
    "• Dễ sai lệch do cảm tính cá nhân (cùng 1 lỗi bóp băng thông nhưng 2 KTV ghi 2 nguyên nhân khác nhau).\n"
    "• Chậm chỉ tiêu thời gian xử lý phiếu (SLA), nguy cơ tồn đọng hàng trăm phiếu khi có sự cố mạng lưới diện rộng.",
    callout_type="WARNING", title_override="BÁO ĐỘNG VẬN HÀNH:")

add_styled_heading(doc, "Định nghĩa lại bài toán: 'Ứng dụng AI' là làm gì?", level=3)
add_p(doc, "Sai lầm phổ biến nhất của các dự án công nghệ là coi AI như một Chatbot thuần túy. Nếu chỉ ném nội dung phản ánh cho ChatGPT hay các mô hình ngôn ngữ lớn (LLM), AI sẽ 'bịa' (Hallucination) ra nguyên nhân do không có số liệu kỹ thuật mạng thật.")
add_p(doc, "Mô hình AI thực chiến trong doanh nghiệp viễn thông = AI Đọc Hiểu (NLP) + Hạ Tầng Thu Thập Số Liệu Thật + Hệ Chuyên Gia Đối Soát (Rule Engine).")
add_bullet(doc, "Đọc hiểu khách hàng đang nói gì (mạng chậm, mất sóng, lỗi app, gọi đi không được).", "Vai trò Trợ lý kỹ sư số (Digital Copilot): ")
add_bullet(doc, "Tự động thu thập toàn bộ log mạng từ Core SAPC, BTools, CEM, SMSC chỉ trong 1.0 - 1.5 giây.", "Thu thập chứng cứ đa nguồn: ")
add_bullet(doc, "Đối chiếu chẩn đoán theo kịch bản kỹ thuật chuẩn xác và đề xuất sẵn mã đóng phiếu OneOSS.", "Hỗ trợ ra quyết định: ")

add_styled_heading(doc, "2. Kiến trúc 3 tầng Hybrid AI & Bản đồ 7 hệ thống vệ tinh (30 Phút)", level=2)
add_bullet(doc, "Mô hình NLP phân tích ngữ pháp kết hợp từ điển quy tắc viễn thông (ai_interpreter.py). Bóc tách các thực thể cốt lõi: issue_type (loại sự cố), incident_time (mốc thời gian), location_entities (địa bàn, đặc khu, trạm BTS). Cơ chế AI Caching (ai_cache.json) tái sử dụng kết quả, phản hồi trong 0.005 giây và tiết kiệm 95% chi phí API.", "Tầng 1 (Đọc hiểu NLP): ")
add_bullet(doc, "Mô hình đa luồng 2 cấp độ: Quét đồng thời 8 thuê bao cùng lúc qua ThreadPoolExecutor; mỗi thuê bao kích hoạt đồng thời 3 luồng con truy vấn BTools (10.159.21.241), SAPC Core (10.155.42.218), CEM (cem.vnptmedia.vn). Toàn bộ dữ liệu hoàn tất trong 1.0 - 1.5 giây.", "Tầng 2 (Thu thập đa nguồn High-Concurrency): ")
add_bullet(doc, "Đối với phản ánh Cuộc gọi (Voice) và Tin nhắn (SMS), hệ thống tự động nhận diện và bypass hoàn toàn BTools & CEM, chỉ tra cứu Core HSS và cờ NAM, rút ngắn thời gian xử lý xuống dưới 1 giây và chống nghẽn tài nguyên phiên BTools.", "Tầng 3 (Bypass phi-Data thông minh): ")

add_styled_heading(doc, "Bản đồ tích hợp 7 hệ thống vệ tinh viễn thông", level=3)
sat_systems = [
    ("OneOSS TTS Mới / TTS Cũ", "Quản lý phiếu & Điều hành", "https://ttsnew.vnpt.vn (hoặc TTS Cũ)", "Thu thập danh sách phản ánh theo phân vùng KTV, cập nhật trạng thái phiếu và đóng phiếu OneOSS."),
    ("Core SAPC / PCRF", "Mạng lõi chính sách & Cước", "10.155.42.218 (PCRF Core)", "Tra cứu Profile cước: Gói Data kích hoạt trên OCS, cờ NAM, hạn mức AMBR QoS, SIM 4G HSS."),
    ("BTools Chrome CDP", "Lịch sử phiên dữ liệu Data", "10.159.21.241:9222 (BTools Service)", "Truy vấn CDR 4G/5G/3G gần nhất: Thời gian phiên, Bytes tải, RAT Type, Service ID, Cause ngắt phiên."),
    ("CEM Vô tuyến", "Chất lượng sóng trạm phát", "https://cem.vnptmedia.vn", "Đo kiểm RSRP (dBm), SINR (dB), tên mã trạm BTS/eNodeB phục vụ, cảnh báo sự cố mất sóng trạm."),
    ("Google Maps Geocoding", "Chuẩn hóa địa giới hành chính", "http://10.155.59.158:1708/api/reverse-geocode", "Chuyển đổi tọa độ GPS từ CEM thành địa danh chuẩn 2 cấp [Phường/Xã, Tỉnh/TP] theo chuẩn mới."),
    ("SMSC Gateway CDR", "Nhật ký tin nhắn thời gian thực", "Cổng kết nối SMSC Gateway", "Tra cứu tin nhắn OTP Brandname, mã trạng thái phát tin Delivery Status (Mã 0, 1, 2, 6, 21, 27)."),
    ("CCOS Cam kết", "Đối soát chặn cuộc gọi rác", "Hệ thống CCOS Tập đoàn", "Kiểm tra biên bản cam kết mở mạng đối với các số bị chặn cuộc gọi rác theo Nghị định 91/2020/NĐ-CP.")
]
create_styled_table(doc, ["Tên Hệ Thống", "Phân Loại", "Endpoint / Địa Chỉ", "Nhiệm Vụ Kỹ Thuật"], sat_systems, [1.4, 1.2, 1.5, 2.5])

doc.add_page_break()

# ==========================================
# PHẦN II: THƯ VIỆN KỸ THUẬT & 7 KỊCH BẢN CHẨN ĐOÁN
# ==========================================
add_styled_heading(doc, "PHẦN II: THƯ VIỆN KỸ THUẬT & 7 KỊCH BẢN CHẨN ĐOÁN CỐT LÕI (60 PHÚT)", level=1)

add_styled_heading(doc, "1. Thư viện Từ điển Gói cước (serviceid.json) & Sóng vô tuyến (25 Phút)", level=2)
add_p(doc, "Bảng mã hạ băng thông (Throttling Matrix) chuẩn hóa trong hệ thống:")
throttle_table = [
    ("10002 / 0000010002", "Bóp băng thông 64/64 Kbps", "Down: 64 Kbps | Up: 64 Kbps", "Rất chậm, chỉ gửi được tin nhắn text Zalo, tải web quay tít thò lò"),
    ("10003 / 0000010003", "Bóp băng thông 128/64 Kbps", "Down: 128 Kbps | Up: 64 Kbps", "Chậm, đọc báo text mất 5-10s, không xem được video YouTube"),
    ("10005 / 0000010005", "Bóp băng thông 512/256 Kbps", "Down: 512 Kbps | Up: 256 Kbps", "Trung bình thấp, xem video độ phân giải 240p/360p giật nhẹ"),
    ("10010 / 0000010010", "Bóp băng thông 1024/1024 Kbps (1 Mbps)", "Down: 1 Mbps | Up: 1 Mbps", "Xem video 480p mượt, lướt Facebook/TikTok tải chậm hơn bình thường"),
    ("10011 / 0000010011", "Bóp băng thông 2048/2048 Kbps (2 Mbps)", "Down: 2 Mbps | Up: 2 Mbps", "Xem video 720p HD, lướt web bình thường, gọi video call ổn định"),
    ("10012 / 0000010012", "Bóp băng thông 3072/3072 Kbps (3 Mbps)", "Down: 3 Mbps | Up: 3 Mbps", "Xem video 1080p Full HD mượt mà, trải nghiệm tốt đa số ứng dụng"),
    ("10013 / 0000010013", "Bóp băng thông 2048/1024 Kbps (2M/1M)", "Down: 2 Mbps | Up: 1 Mbps", "Download 2 Mbps, Upload bị giới hạn 1 Mbps"),
    ("10014 / 0000010014", "Bóp băng thông 128/128 Kbps", "Down: 128 Kbps | Up: 128 Kbps", "Hạ băng thông hai chiều mức cơ bản")
]
create_styled_table(doc, ["Mã Service ID", "Tên Kỹ Thuật", "Giới Hạn Tốc Độ (Kbps)", "Trải Nghiệm Khách Hàng Thực Tế"], throttle_table, [1.4, 1.8, 1.5, 1.9])

add_callout(doc, 
    "QUY TẮC BẮT BUỘC VỀ GÓI CƯỚC D159SC VÀ HỒ SƠ ODA_BIG_OCS:\n"
    "• Các gói cước Data thuộc nhóm BIG_OCS (D159SC, VD120N, YOLO90...) bắt buộc phải có profile ODA_BIG_OCS trên Core OCS.\n"
    "• Nếu khách hàng đã đăng ký gói D159SC thành công trên CCBS nhưng kiểm tra Core SAPC không thấy profile ODA_BIG_OCS (chỉ có ODA_MYTV), hệ thống xác định đây là LỖI KHAI BÁO GÓI CƯỚC CỦA HỆ THỐNG.\n"
    "• KTV TUYỆT ĐỐI KHÔNG được đóng phiếu báo khách hết dung lượng, mà PHẢI chuyển hướng xử lý: 'Chuyển IT/CCBS kiểm tra khai báo gói cước {tên gói cước} cho Khách hàng'.",
    callout_type="WARNING", title_override="QUY TẮC VÀNG VỀ GÓI CƯỚC:")

add_styled_heading(doc, "Bảng danh mục các gói cước Data chủ đạo (Nhóm 3000, 3001, Roaming, Family)", level=3)
data_packages_full = [
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
    ("0000005000 / 5000", "Family, GDVP-T, HOME, GIA ĐÌNH", 
     "Gói cước chia sẻ nhóm gia đình và văn phòng tích hợp VNPT."),
    ("0000005600 / 0000005700", "Heyzone Inzone / Outzone", 
     "Các gói cước theo vùng địa lý ưu đãi (HeyzoneHN, HEYZONE_BPC, HEYZONE_HCM...)."),
    ("0000008604 / 8604", "DPLUS_OCS (D1PLUS..D10PLUS)", 
     "Gói data mua thêm theo ngày/lần nạp thẻ tốc độ cao.")
]
create_styled_table(doc, ["Mã Service ID", "Tên Gói / Hồ Sơ Core", "Mô Tả Nghiệp Vụ & Gói Cước Áp Dụng"], data_packages_full, [1.5, 1.8, 3.3])

add_styled_heading(doc, "Bảng danh mục các gói OTT Bypass miễn cước data ứng dụng", level=3)
ott_table_full = [
    ("0000002804", "MYTV (FIX)", "Truyền hình MyTV Mobile đa màn hình"),
    ("0000002807", "ZALO", "Nhắn tin và gọi thoại ứng dụng Zalo"),
    ("0000002808 / 2809", "ZingMP3", "Nghe nhạc trực tuyến Zing MP3"),
    ("0000002910", "Meta (Facebook)", "Mạng xã hội Facebook (lướt feed, nhắn tin)"),
    ("0000002913", "Instagram", "Mạng xã hội hình ảnh Instagram"),
    ("0000002902 / 2920", "DIP_Youtube", "Xem video YouTube chuẩn Data IP"),
    ("0000002917", "TIKTOK", "Xem video ngắn TikTok"),
    ("0000002916", "DIP_LQMobile", "Chơi game Liên Quân Mobile Garena"),
    ("0000002919", "DIP_FreeFire", "Chơi game sinh tồn Free Fire"),
    ("0000002925", "SHOPEE", "Sàn thương mại điện tử Shopee"),
    ("0000002932", "MoMo", "Ví điện tử MoMo")
]
create_styled_table(doc, ["Mã Service ID", "Tên Dịch Vụ OTT", "Ứng Dụng Thực Tế Tương Ứng"], ott_table_full, [1.5, 1.8, 3.3])

add_styled_heading(doc, "Thư viện Công nghệ sóng vô tuyến (rattype.json) & Thuật toán rớt sóng", level=3)
rat_table = [
    ("RAT 0", "Báo hiệu mạng (Signaling)", "None", "Bản tin điều khiển thiết lập phiên. Không phát sinh lưu lượng data người dùng."),
    ("RAT 1", "Sóng 3G (UTRAN - WCDMA/HSPA+)", "1 - 10 Mbps", "Công nghệ 3G cũ. Phát sinh liên tục cảnh báo khu vực sóng 4G rất yếu."),
    ("RAT 2", "Sóng 2G (GERAN - GSM/EDGE)", "40 - 200 Kbps", "Băng thông cực thấp, tải web lỗi timeout. Biểu hiện mất hoàn toàn vùng phủ 4G."),
    ("RAT 6", "Sóng 4G (E-UTRAN - LTE/LTE-A)", "30 - 150 Mbps", "Chuẩn sóng data chính hiện nay. Mọi thuê bao đạt chuẩn phải có > 80% phiên trên RAT 6."),
    ("RAT 7", "Sóng 5G (NR - New Radio)", "300 - 1000 Mbps", "Công nghệ 5G thế hệ mới tốc độ gigabit của mạng VinaPhone.")
]
create_styled_table(doc, ["Mã RAT Type", "Tên Công Nghệ", "Tốc Độ Thực Tế", "Đánh Giá Kỹ Thuật & Ý Nghĩa Phân Tích"], rat_table, [1.1, 1.8, 1.2, 2.5])

add_p(doc, "Công thức phân tích tỷ lệ rớt sóng 2G/3G trong 5 ngày gần nhất:")
add_bullet(doc, "Tỷ lệ rớt 2G/3G = (Số phiên có RAT=1 + RAT=2) / (Tổng số phiên phát sinh) * 100%", "Thuật toán: ")
add_bullet(doc, "Nếu Tỷ lệ rớt 2G/3G > 50%: Hệ thống tự động kích hoạt kịch bản Bắt sóng 4G kém (chuyển VTT tối ưu vùng phủ).", "Ngưỡng kích hoạt: ")
add_bullet(doc, "Nếu Tỷ lệ 4G = 0% nhưng HSS đã mở 4G: Hệ thống kích hoạt lỗi thiết bị khách hàng chưa bật 4G hoặc SIM hỏng.", "Ngưỡng không bắt được 4G: ")

add_styled_heading(doc, "2. Phân tích chuyên sâu 7 Kịch bản Chẩn đoán Kỹ thuật Cốt lõi (35 Phút)", level=2)
add_p(doc, "Động cơ tiền kiểm phân loại khiếu nại dựa trên 7 kịch bản chẩn đoán chuyên gia. Mỗi kịch bản có màu sắc nhận diện, kết luận kỹ thuật và mã nguyên nhân OneOSS đề xuất chính xác:")

scenarios_all = [
    ("Kịch bản 1: Bóp băng thông theo chính sách gói cước (Throttling)", "Hồng cam (#F8CBAD)",
     "SAPC ghi nhận gói cước đã hết dung lượng tốc độ cao; BTools ghi nhận tốc độ tải thực tế bị giới hạn đúng bằng mã bóp trong từ điển serviceid.json (10002, 10003, 10005, 10010..10014).",
     "Khách hàng đã dùng hết data tốc độ cao trong chu kỳ gói.",
     "Không đáp ứng do Thuê bao hết lưu lượng/bị hạ băng thông",
     "Thông báo khách hàng đã hết lưu lượng tốc độ cao. Tư vấn khách hàng mua thêm các gói data ngày/tuần để tiếp tục sử dụng."),
     
    ("Kịch bản 2: Hoạt động bình thường sau thời điểm sự cố (Đã tự phục hồi)", "Xanh lục (#E2EFDA)",
     "Khách báo mất mạng lúc 08:00 sáng. Phân tích lịch sử BTools sau mốc tiếp nhận ghi nhận: Có phiên kết nối dung lượng lớn (> 10MB) hoặc tổng lưu lượng đạt trên 30MB, truy cập 4G ổn định.",
     "Sự cố tạm thời đã qua (thiết bị khởi động lại, rời khỏi vùng mất sóng).",
     "Khách hàng theo dõi thêm / Mạng lưới đảm bảo chất lượng",
     "Thông báo mạng lưới đảm bảo chất lượng, thuê bao đã truy cập lại bình thường sau thời điểm báo hỏng."),
     
    ("Kịch bản 3: Đặc thù địa hình biển đảo (Island Terrain Constraints)", "Vàng cam (#FCE4D6)",
     "Khách phản ánh sóng yếu, chập chờn tại các đặc khu hoặc địa bàn hải đảo (Phú Quốc, Côn Đảo, Cát Bà, Lý Sơn...). Dữ liệu trạm CEM ghi nhận khoảng cách phục vụ xa, suy hao truyền dẫn mặt biển cao.",
     "Vị trí địa lý đặc thù chịu suy hao truyền dẫn tự nhiên trên mặt biển.",
     "Khách hàng theo dõi thêm / Do địa hình/vật cản",
     "Giải thích đặc thù vùng phủ sóng ven biển/hải đảo, chuyển kế hoạch phát triển trạm cho ban chuyên trách."),
     
    ("Kịch bản 4: Lưu lượng yếu - Tập trung 1 trạm phục vụ", "Vàng nhạt (#FFF2CC)",
     "Thuê bao có kết nối nhưng lưu lượng rất thấp (< 1MB/phiên). Dữ liệu trạm CEM ghi nhận trên 90% kết nối tập trung tại 1 Cell duy nhất có tải cao hoặc cảnh báo suy hao nặng (RSRP < -105 dBm).",
     "Thuê bao ở mép vùng phủ sóng hoặc trạm BTS đang quá tải cục bộ.",
     "Không đáp ứng do Vùng phủ sóng kém/chập chờn",
     "Chuyển phòng Kỹ thuật Viễn thông (VTT) địa bàn đo kiểm vùng phủ sóng và tối ưu góc ngẩng anten trạm."),
     
    ("Kịch bản 5: Treo phiên kết nối quản trị (Cause Code 300 / 2042 / 2043)", "Xám nhạt (#F2F2F2)",
     "BTools xuất hiện các mã ngắt phiên bất thường: 300 (GTP-C timeout), 2042 (Context not found / MME release), hoặc liên tục gửi yêu cầu nhưng không phát sinh lưu lượng người dùng thực tế.",
     "Gói cước bị treo phiên trên Core OCS hoặc thiết bị khách hàng lỗi cấu hình APN.",
     "Không đáp ứng do Thiết bị khách hàng/Cài đặt máy (hoặc Lỗi treo phiên PDP)",
     "Hướng dẫn khách bật tắt chế độ máy bay để reset kết nối mạng. Nếu không được, chuyển IT reset profile OCS."),
     
    ("Kịch bản 6: Khóa cước chiều GPRS (Cờ NAM = 1)", "Đỏ nhạt (#FEE2E2)",
     "Tra cứu SAPC/HSS phát hiện cờ khóa cước NAM = 1 (khóa chiều dữ liệu do nợ cước hoặc chính sách thuê bao trả sau).",
     "Thuê bao bị hệ thống khóa chiều dịch vụ do nợ cước.",
     "Không đáp ứng do Thuê bao nợ cước/khóa chiều dịch vụ",
     "Thông báo khách hàng thanh toán cước để được tự động mở lại dịch vụ."),
     
    ("Kịch bản 7: Cảnh báo phần mềm VPN / 1.1.1.1 của bên thứ ba", "Xanh lục (#E2EFDA)",
     "Thiết bị truy cập qua RAT 1, 6 với dung lượng data duy trì đều nhau bất thường trong khoảng từ 5MB đến 11.5MB. Khách hàng cài các ứng dụng Warp 1.1.1.1, Turbo VPN...",
     "Ứng dụng VPN định tuyến lưu lượng qua máy chủ quốc tế làm tăng độ trễ và gián đoạn.",
     "Không đáp ứng do Thiết bị khách hàng/Cài đặt máy",
     "Hướng dẫn khách hàng tạm thời tắt các app VPN/1.1.1.1 để kiểm tra lại tốc độ đường truyền gốc.")
]

for s_name, s_col, s_log, s_cau, s_oneoss, s_act in scenarios_all:
    add_styled_heading(doc, s_name, level=3)
    add_bullet(doc, s_col, "Màu sắc cảnh báo: ")
    add_bullet(doc, s_log, "Dấu hiệu nhận diện từ Log mạng: ")
    add_bullet(doc, s_cau, "Nguyên nhân cốt lõi: ")
    add_bullet(doc, s_oneoss, "Mã nguyên nhân OneOSS đề xuất: ")
    add_bullet(doc, s_act, "Hành động & Mẫu câu phản hồi: ")

doc.add_page_break()

# ==========================================
# PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ
# ==========================================
add_styled_heading(doc, "PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ NGHIỆP VỤ (90 PHÚT — TRỌNG TÂM)", level=1)
add_p(doc, "Đây là phần học cốt lõi chiếm 90 phút thời lượng thực hành trực tiếp trên hệ thống Single Page App VNPT TTS PRECHECK:")

add_image_safe(doc, IMG_HEADER, width_inches=6.3, caption_text="Hình 3.1: Thanh điều hướng trung tâm và thông tin phiên làm việc KTV")

add_styled_heading(doc, "1. Phân hệ 1: Mobile Internet (Data 4G/5G) — Khai thác 3 Card thông tin (30 Phút)", level=2)
add_p(doc, "Khi mở rộng một phiếu Data, giao diện hiển thị 3 Card nghiệp vụ chuyên sâu:")
add_image_safe(doc, IMG_EXPANDED, width_inches=6.3, caption_text="Hình 3.2: Chi tiết toàn cảnh 3 Card nghiệp vụ của một phiếu Data")

add_bullet(doc, "Chứa mã phiếu OneOSS, số điện thoại, thời gian tiếp nhận, nội dung phản ánh gốc của khách hàng, kết luận tự động của hệ thống kèm màu nhận diện sự cố.", "Card 1 (Thông tin phiếu & Kết luận sơ bộ): ")
add_bullet(doc, "Hiển thị gói cước đang có trên OCS, cờ khóa mở dịch vụ NAM, tốc độ QoS cam kết, cùng dữ liệu sóng trạm CEM (RSRP, SINR, mã trạm BTS phục vụ).", "Card 2 (Profile Core SAPC & Sóng CEM): ")
add_bullet(doc, "Bảng danh sách chi tiết các phiên CDR BTools (thời gian, bytes, RAT, Service ID), công cụ nhận diện Phường/Xã từ GPS trạm, danh mục chọn mã nguyên nhân OneOSS và nút đóng phiếu.", "Card 3 (Nhật ký BTools & Thao tác OneOSS): ")

add_styled_heading(doc, "Quy trình xử lý ca bệnh Mobile Internet thực tế (Case Study Step-by-Step)", level=3)
add_p(doc, "Dưới đây là 6 bước thực hành chuẩn dành cho KTV:")
add_bullet(doc, "Click vào dòng phiếu trên Dashboard để mở rộng khung chi tiết 3 Card.", "Bước 1 - Mở phiếu: ")
add_bullet(doc, "Đọc nhanh kết luận sơ bộ của Bot ở Card 1 (Ví dụ: THUÊ BAO BỊ BÓP BĂNG THÔNG).", "Bước 2 - Đọc nhận định: ")
add_bullet(doc, "Nhìn Card 2: Xem gói cước (D159SC hay VD120N), cờ NAM=0 hay 1; xem chỉ số RSRP trạm BTS (RSRP > -90 dBm là sóng tốt).", "Bước 3 - Đối soát Card 2: ")
add_bullet(doc, "Nhìn Card 3: Kiểm tra bảng BTools, thấy mã 10003 -> Xác nhận 100% khách đã dùng hết dung lượng tốc độ cao.", "Bước 4 - Khẳng định chứng cứ: ")
add_bullet(doc, "Bấm nút mũi tên xanh (↑) cạnh Radio để tự động lấy địa bàn chuẩn [Phường/Xã], [Tỉnh/TP] từ GPS trạm CEM.", "Bước 5 - Chuẩn hóa địa bàn: ")
add_bullet(doc, "Chọn mã 5.1.01 (Thuê bao hết lưu lượng/bị hạ băng thông) và nhấn Đóng phiếu OneOSS.", "Bước 6 - Hoàn tất: ")

add_styled_heading(doc, "2. Phân hệ 2: Cuộc gọi & Thoại (Voice Calls, VoLTE) (20 Phút)", level=2)
add_p(doc, "Phân hệ Thoại chuyên xử lý các khiếu nại không gọi đi được, không nhận được cuộc gọi đến, hoặc lỗi rớt mạng data khi có cuộc gọi:")
add_image_safe(doc, IMG_VOICE, width_inches=6.3, caption_text="Hình 3.3: Giao diện phân hệ xử lý phản ánh Dịch vụ Cuộc gọi & Thoại")
add_bullet(doc, "Hệ thống tự động tra cứu HLR/VLR xem thuê bao có Active không, cờ NAM có bị khóa không, SIM đã mở VoLTE chưa.", "Cơ chế kiểm tra mạng lõi: ")
add_bullet(doc, "Nếu khách báo 'Vừa bật 4G mà có người gọi đến là mất mạng', đây là biểu hiện máy chưa bật VoLTE (bị chuyển mạch CSFB về 2G). Hướng dẫn khách soạn HDV gửi 888 để kích hoạt VoLTE miễn phí.", "Lỗi rớt mạng CSFB: ")
add_bullet(doc, "Hỗ trợ KTV duyệt nhanh chuyển bước 2.4 / 2.6 theo đúng luồng thoại OneOSS mà không fill comment sai lệch.", "Điều phối Bước 2.3 & 2.4: ")

add_styled_heading(doc, "3. Phân hệ 3: Chặn gọi ngoại mạng / Spam theo Nghị định 91 (15 Phút)", level=2)
add_p(doc, "Giải quyết khiếu nại thuê bao bị hệ thống phòng chống cuộc gọi rác tự động khóa chiều gọi đi sang Viettel, MobiFone:")
add_image_safe(doc, IMG_SPAM, width_inches=6.3, caption_text="Hình 3.4: Giao diện phân hệ xử lý phản ánh Chặn cuộc gọi ngoại mạng theo Nghị định 91")
add_bullet(doc, "Tự động phân tích và gắn huy hiệu nhà mạng bị chặn (Viettel, MobiFone, Vietnamobile...).", "Nhận diện nhà mạng đối tác: ")
add_bullet(doc, "Nếu tìm thấy biên bản cam kết đính kèm trên CCOS, KTV kích hoạt lệnh gỡ chặn trực tiếp. Nếu chưa có, chọn mẫu phản hồi hướng dẫn khách hàng ra điểm giao dịch ký cam kết.", "Đối soát cam kết CCOS: ")

add_styled_heading(doc, "4. Phân hệ 4: Tin nhắn SMS & Cổng tra cứu SMSC Gateway CDR (15 Phút)", level=2)
add_p(doc, "Xử lý khiếu nại không nhận được tin nhắn OTP Ngân hàng, mã xác thực VNeID hoặc không gửi được SMS:")
add_image_safe(doc, IMG_SMS, width_inches=6.3, caption_text="Hình 3.5: Màn hình tiếp nhận phản ánh Tin nhắn SMS và nút mở Cổng tra cứu SMSC CDR")
add_image_safe(doc, IMG_SMS_MODAL, width_inches=6.3, caption_text="Hình 3.6: Cửa sổ tra cứu SMSC Gateway CDR hiển thị chi tiết Brandname, thời gian và mã trạng thái phát tin")

add_p(doc, "Bảng mã trạng thái phát tin nhắn SMSC tiêu chuẩn:")
smsc_codes = [
    ("Mã 0 (Delivered)", "Phát tin thành công", "Tin nhắn đã đến máy khách hàng. Hướng dẫn kiểm tra hộp thư Spam trên máy."),
    ("Mã 1 (Expired)", "Hết hạn lưu tin", "Tin nhắn nằm chờ trên SMSC quá hạn do thuê bao tắt máy hoặc mất sóng liên tục."),
    ("Mã 2 (Deleted)", "Bị hủy bởi hệ thống", "Tin nhắn bị hủy do bộ lọc spam hoặc hàng đợi quá tải."),
    ("Mã 6 (Undeliverable)", "Không thể phân phát", "SIM hỏng, bộ nhớ máy đầy, hoặc cấu hình máy từ chối tin nhắn Brandname."),
    ("Mã 21 (Absent Subscriber)", "Thuê bao vắng mặt", "Thiết bị tắt nguồn hoặc mất sóng tại thời điểm ngân hàng gửi OTP."),
    ("Mã 27 (Call Barred)", "Bị chặn chiều nhận", "Thuê bao bị khóa chiều nhận tin nhắn trên HLR (do nợ cước hoặc chặn dịch vụ).")
]
create_styled_table(doc, ["Mã Trạng Thái SMSC", "Ý Nghĩa Kỹ Thuật", "Phân Tích Chi Tiết & Hướng Dẫn Xử Lý"], smsc_codes, [1.5, 1.8, 3.2])

add_styled_heading(doc, "5. Phân hệ 5 & 6: CVQT (Roaming), Dịch vụ SIM & Quản trị KTV SOC (10 Phút)", level=2)
add_bullet(doc, "Kiểm tra thuê bao đã mở dịch vụ CVQT (IR) trước khi xuất cảnh chưa (DK CVQT gửi 9123). Kiểm tra gói data Roaming (R500N, IR_POST). Bắt buộc khách hàng phải bật tùy chọn 'Chuyển vùng dữ liệu' trên máy.", "Chuyển vùng quốc tế (IR): ")
add_bullet(doc, "Kiểm tra số serial SIM trên CCBS. Nếu là phôi SIM cũ sản xuất trước 2018, tư vấn đổi USIM 4G/5G. Trường hợp mất eSIM profile, hướng dẫn quét lại mã QR code cấp lại qua MyVNPT.", "Dịch vụ SIM / eSIM: ")

add_image_safe(doc, IMG_KTV_MGT, width_inches=6.3, caption_text="Hình 3.7: Màn hình Quản trị danh sách KTV, phân quyền tỉnh thành và cấu hình Auto-Close")
add_bullet(doc, "Gán tài khoản KTV vào từng Tỉnh/TP hoặc nhóm dịch vụ cụ thể để lọc danh sách phiếu phù hợp.", "Phân quyền địa bàn: ")
add_bullet(doc, "Chỉ kích hoạt Auto-Close khi thỏa mãn 3 điều kiện: (1) Kết quả là Mạng lưới đảm bảo / Bóp băng thông; (2) Không phải thuê bao VIP; (3) Không phải phiếu mở lại nhiều lần.", "Vận hành Auto-Close an toàn: ")

doc.add_page_break()

# ==========================================
# PHẦN IV: QUY CHUẨN ĐÓNG PHIẾU 5.1 & AUTO-CLOSE
# ==========================================
add_styled_heading(doc, "PHẦN IV: QUY CHUẨN ĐÓNG PHIẾU ONEOSS 5.1 & AUTO-CLOSE CÓ KIỂM SOÁT (45 PHÚT)", level=1)

add_styled_heading(doc, "1. Quy chuẩn Địa giới hành chính 2 cấp (Phường/Xã & 34 Tỉnh/TP mới) (20 Phút)", level=2)
add_bullet(doc, "[Phường/Xã/Thị trấn], [Tỉnh/Thành phố] (Ví dụ: Phường Bến Nghé, TP. Hồ Chí Minh hoặc Xã Hòa Lạc, TP. Hà Nội).", "Định dạng chuẩn DUY NHẤT: ")
add_bullet(doc, "Không lấy cấp Thôn, Ấp, Bản, Khóm, Xóm, Tổ dân phố (như 'Thôn 3', 'Ấp 1', 'Tổ 5'...).", "CẤM TUYỆT ĐỐI: ")
add_bullet(doc, "Không dùng mã trạm rút gọn hay viết tắt viễn thông (như 'PLO', 'DLI', 'BLU', 'TDM'...).", "CẤM TUYỆT ĐỐI: ")

add_image_safe(doc, IMG_WARD, width_inches=6.0, caption_text="Hình 4.1: Công cụ nhận diện Phường/Xã chuẩn 2 cấp tự động từ GPS trạm BTS CEM (Port 1708)")

add_styled_heading(doc, "Hướng dẫn 2 cách cập nhật Phường/Xã trên Dashboard", level=3)
add_bullet(doc, "Nhìn vào dòng 'Radio:' ở Card 2. Nếu trạm BTS có tọa độ GPS, bấm nút mũi tên xanh (↑) bên cạnh. Hệ thống tự động truy vấn Google Maps nội bộ (Port 1708) và điền địa bàn chuẩn 2 cấp.", "Cách 1 (1-Click tự động - KHUYÊN DÙNG): ")
add_bullet(doc, "Nếu khách báo dạng 'ấp lương phú C, xã Hòa Lạc, Tỉnh Đồng Tháp' -> KTV xóa bỏ phần ấp, chỉ giữ lại đúng: 'Xã Hòa Lạc, Tỉnh Đồng Tháp'.", "Cách 2 (Sửa trực tiếp ô text): ")

add_styled_heading(doc, "Bảng Chuẩn 34 Tỉnh / Thành phố mới & Phân bổ 3 Miền", level=3)
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

add_styled_heading(doc, "2. Danh mục 73 Mã Nguyên Nhân OneOSS 5.1 & Auto-Close An Toàn (25 Phút)", level=2)
add_p(doc, "Bảng tra cứu toàn diện 73 mã nguyên nhân OneOSS được gom cụm theo từng nhóm nghiệp vụ kỹ thuật:")

causes_categorized = [
    # Nhóm 1: Do gói cước & lưu lượng
    ("5.1.01", "Không đáp ứng do Thuê bao hết lưu lượng/bị hạ băng thông", "Có mã bóp 10002..10014, dùng hết data tốc độ cao", "Nhóm Gói cước"),
    ("5.1.02", "Không đáp ứng do Thuê bao chưa đăng ký gói Data", "Thuê bao dùng gói PAYGO/M0, không có gói data nền", "Nhóm Gói cước"),
    ("5.1.03", "Không đáp ứng do Gói cước hết hạn sử dụng", "Gói cước đã qua ngày gia hạn, chưa nạp tiền tài khoản", "Nhóm Gói cước"),
    ("5.1.04", "Không đáp ứng do Thuê bao chưa có Profile 4G trên HSS", "Chưa mở cờ dịch vụ 4G trên mạng lõi, chuyển IT Core", "Nhóm Mạng lõi"),
    ("5.1.05", "Không đáp ứng do Lỗi khai báo gói cước (Thiếu ODA_BIG_OCS)", "Đã đăng ký D159SC nhưng thiếu profile OCS, chuyển IT/CCBS", "Nhóm Mạng lõi"),
    # Nhóm 2: Do thiết bị khách hàng & cài đặt
    ("5.1.06", "Không đáp ứng do Thiết bị khách hàng tắt Dữ liệu di động", "Không phát sinh phiên data trên BTools trong thời gian dài", "Nhóm Thiết bị"),
    ("5.1.07", "Không đáp ứng do Thiết bị cài đặt chế độ 2G/3G Only", "Máy chưa bật 4G LTE Auto, tỷ lệ RAT 1 và 2 chiếm 100%", "Nhóm Thiết bị"),
    ("5.1.08", "Không đáp ứng do Thiết bị sử dụng VPN / 1.1.1.1 gây chậm mạng", "Lưu lượng phiên 5MB - 11.5MB đều đặn qua app thứ ba", "Nhóm Thiết bị"),
    ("5.1.09", "Không đáp ứng do Thiết bị lỗi cấu hình APN", "APN sai khác m3-world, không thiết lập được phiên PDP", "Nhóm Thiết bị"),
    ("5.1.10", "Không đáp ứng do Thẻ SIM bị lỗi vật lý / hỏng mạch đồng", "SIM cũ trước 2018, máy báo No SIM chập chờn", "Nhóm Thiết bị"),
    # Nhóm 3: Do mạng vô tuyến & trạm BTS
    ("5.1.11", "Không đáp ứng do Vùng phủ sóng kém / Mép sóng", "Rớt 2G/3G > 50%, RSRP < -105 dBm, chuyển VTT tối ưu anten", "Nhóm Vô tuyến"),
    ("5.1.12", "Không đáp ứng do Trạm BTS đang bảo dưỡng / Sự cố mất điện", "Trạm CEM có cảnh báo suy hao hoặc mất liên lạc vô tuyến", "Nhóm Vô tuyến"),
    ("5.1.13", "Không đáp ứng do Nhiễu tần số vô tuyến cục bộ", "Chỉ số SINR < 0 dB, chất lượng tín hiệu suy giảm nặng", "Nhóm Vô tuyến"),
    ("5.1.14", "Không đáp ứng do Nghẽn tải vô tuyến giờ cao điểm", "Trạm BTS có số lượng thuê bao kết nối vượt ngưỡng thiết kế", "Nhóm Vô tuyến"),
    # Nhóm 4: Do địa hình & đặc thù biển đảo
    ("5.1.15", "Khách hàng theo dõi thêm / Do địa hình vật cản", "Thuê bao trong tầng hầm, nhà kín sóng, hẻm sâu", "Nhóm Địa hình"),
    ("5.1.16", "Khách hàng theo dõi thêm / Đặc thù địa hình biển đảo", "Khu vực ven biển, hải đảo chịu suy hao truyền dẫn mặt biển", "Nhóm Địa hình"),
    # Nhóm 5: Do chặn chiều & chính sách
    ("5.1.17", "Không đáp ứng do Thuê bao nợ cước / Khóa chiều GPRS (NAM=1)", "Core SAPC ghi nhận cờ NAM = 1 do nợ cước thuê bao trả sau", "Nhóm Chính sách"),
    ("5.1.18", "Không đáp ứng do Thuê bao bị chặn theo Nghị định 91", "Thuê bao bị bộ lọc cuộc gọi rác chặn chiều gọi đi ngoại mạng", "Nhóm Chính sách"),
    ("5.1.19", "Không đáp ứng do Thuê bao chưa kích hoạt dịch vụ CVQT", "Thuê bao đi nước ngoài nhưng chưa soạn DK CVQT gửi 9123", "Nhóm Chính sách"),
    # Nhóm 6: Mạng đảm bảo & hướng dẫn sử dụng
    ("5.1.20", "Khách hàng theo dõi thêm / Mạng lưới đảm bảo chất lượng", "BTools ghi nhận phiên > 10MB sau sự cố, mạng hoạt động bình thường", "Nhóm Đảm bảo"),
    ("5.1.21", "Đáp ứng - Đã hướng dẫn khách hàng sử dụng dịch vụ", "Khách hàng hiểu sai cách tính cước hoặc chu kỳ gói", "Nhóm Hướng dẫn"),
    ("5.1.22", "Chuyển tiếp bộ phận IT / Khai thác mạng xử lý chuyên sâu", "Lỗi core phức tạp cần can thiệp hồ sơ thuê bao HSS/PCRF", "Nhóm Điều phối")
]
create_styled_table(doc, ["Mã OneOSS", "Tên Nguyên Nhân OneOSS Chuẩn", "Dấu Hiệu Kỹ Thuật Áp Dụng", "Phân Nhóm"], causes_categorized, [1.0, 2.5, 2.0, 1.1])

doc.add_page_break()

# ==========================================
# PHẦN V: THỰC HÀNH TÌNH HUỐNG & ĐÁNH GIÁ CUỐI KHÓA
# ==========================================
add_styled_heading(doc, "PHẦN V: THỰC HÀNH TÌNH HUỐNG (HANDS-ON LAB) & ĐÁNH GIÁ CUỐI KHÓA (45 PHÚT)", level=1)

add_styled_heading(doc, "1. Kịch bản Thực hành Tình huống (Hands-on Lab) (25 Phút)", level=2)
add_p(doc, "Bài tập 1: Phân tích thuê bao báo mạng chậm", bold_prefix="• ")
add_bullet(doc, "Thuê bao 0913xxxxxx phản ánh mạng chậm từ 14:00 chiều qua.", "Tình huống: ")
add_bullet(doc, "Sử dụng tính năng tiền kiểm tra 1 thuê bao -> Mở Drawer xem kết quả: SAPC có gói gì? BTools ghi nhận tốc độ bao nhiêu? Thuê bao rơi vào kịch bản nào trong 7 kịch bản? Đọc mẫu kết luận và xác định xem có nên bấm đóng phiếu ngay hay không.", "Yêu cầu: ")

add_p(doc, "Bài tập 2: Xử lý phiếu Thoại ở bước 2.3", bold_prefix="• ")
add_bullet(doc, "Thuê bao phản ánh không gọi đi được đến đầu số cố định.", "Tình huống: ")
add_bullet(doc, "Chuyển sang Tab Cuộc gọi -> Tiền kiểm tra hồ sơ -> Kiểm tra cờ NAM và trạm VLR phục vụ gần nhất -> Sử dụng nút Chuyển 2.4 nhanh để đưa phiếu sang bước Đánh giá kết quả mà không tự động fill comment sai lệch.", "Yêu cầu: ")

add_styled_heading(doc, "2. Bộ câu hỏi trắc nghiệm đánh giá cuối khóa (Assessment) (20 Phút)", level=2)
add_p(doc, "(10 câu hỏi trắc nghiệm khách quan — Thời gian làm bài: 15 phút, giải đáp: 5 phút)", italic=True)

questions = [
    ("Câu 1: Vai trò chính của mô hình NLP (ai_interpreter.py) trong hệ thống là gì?",
     ["A. Tự động đóng phiếu OneOSS không cần kiểm tra dữ liệu mạng.",
      "B. Đọc hiểu nội dung phản ánh đời thường của khách hàng, trích xuất loại lỗi, mốc thời gian và địa bàn. (ĐÁP ÁN ĐÚNG)",
      "C. Thay thế hoàn toàn nhân sự điện thoại viên tổng đài.",
      "D. Tạo ra các kịch bản khuyến mại gói cước mới."]),
    ("Câu 2: Tại sao hệ thống KHÔNG dùng thuần LLM (như ChatGPT) để kết luận sự cố?",
     ["A. Vì LLM tốn nhiều token.",
      "B. Vì LLM không có số liệu kỹ thuật thực tế từ Core mạng (BTools, SAPC, CEM), sẽ dễ 'bịa' nguyên nhân. (ĐÁP ÁN ĐÚNG)",
      "C. Vì OneOSS không cho phép kết nối trực tiếp với LLM.",
      "D. Vì các nhà mạng khác không dùng LLM."]),
    ("Câu 3: Thuê bao báo mất mạng lúc 8:00, nhưng BTools ghi nhận lúc 9:00 có phiên 4G tải 50MB. Hệ thống kết luận gì?",
     ["A. Treo phiên quản trị (Cause Code 300).",
      "B. Hoạt động bình thường sau thời điểm sự cố (Dịch vụ đã tự phục hồi). (ĐÁP ÁN ĐÚNG)",
      "C. Bóp băng thông theo chính sách gói.",
      "D. Khóa cước chiều GPRS."]),
    ("Câu 4: Khi phát hiện Service ID trong bản ghi BTools là 10003 (tốc độ 128/64 Kbps), mã đóng phiếu phù hợp nhất là gì?",
     ["A. Đứt cáp quang biển.",
      "B. Nghẽn trạm vô tuyến CEM.",
      "C. Hạ băng thông theo chính sách gói cước (Hết dung lượng tốc độ cao). (ĐÁP ÁN ĐÚNG)",
      "D. Khách hàng theo dõi thêm."]),
    ("Câu 5: Khách hàng đăng ký gói D159SC nhưng kiểm tra Core SAPC thiếu profile ODA_BIG_OCS. Hướng xử lý đúng là gì?",
     ["A. Đóng phiếu báo khách hàng dùng hết data.",
      "B. 'Chuyển IT/CCBS kiểm tra khai báo gói cước D159SC cho Khách hàng'. (ĐÁP ÁN ĐÚNG)",
      "C. Tư vấn khách hàng nạp tiền mua gói mới.",
      "D. Chuyển phòng Kỹ thuật VTT kiểm tra anten trạm BTS."]),
    ("Câu 6: Cơ chế 'Non-Data Bypass Strategy' mang lại lợi ích gì cho hệ thống?",
     ["A. Rút ngắn thời gian tiền kiểm Cuộc gọi/SMS xuống dưới 1 giây và chống nghẽn phiên BTools. (ĐÁP ÁN ĐÚNG)",
      "B. Tự động chuyển đổi thuê bao trả sau sang trả trước.",
      "C. Giúp tăng tốc độ 4G lên gấp đôi.",
      "D. Khóa toàn bộ các thuê bao có phản ánh khiếu nại."]),
    ("Câu 7: Quy chuẩn địa giới hành chính bắt buộc khi đóng phiếu OneOSS 5.1 là gì?",
     ["A. Ghi đầy đủ cấp Thôn, Ấp, Bản, Xã, Huyện, Tỉnh.",
      "B. Định dạng DUY NHẤT 2 cấp: [Phường/Xã], [Tỉnh/TP] theo bảng 34 Tỉnh/TP mới sáp nhập. (ĐÁP ÁN ĐÚNG)",
      "C. Dùng mã trạm BTS viết tắt như PLO, DLI, BLU.",
      "D. Chỉ ghi tên Tỉnh, không cần ghi Phường/Xã."]),
    ("Câu 8: Tiện ích mở rộng 'VNPT Token Utilities' có chức năng chính là gì?",
     ["A. Hack mật khẩu tài khoản OneOSS.",
      "B. Tự động đồng bộ Token OneOSS TTS Mới và Session Cookie 34 TTP sang máy chủ cổng 1234. (ĐÁP ÁN ĐÚNG)",
      "C. Đọc trộm tin nhắn khách hàng.",
      "D. Tự động tắt máy tính khi hết giờ làm việc."]),
    ("Câu 9: Trong tra cứu SMSC Gateway CDR, mã trạng thái phân phát Mã 0 (Delivered) nghĩa là gì?",
     ["A. Tin nhắn đã được phân phát thành công đến thiết bị/SIM khách hàng. (ĐÁP ÁN ĐÚNG)",
      "B. Tin nhắn bị xóa trên tổng đài SMSC.",
      "C. Thuê bao bị khóa chiều nhận tin nhắn.",
      "D. Tin nhắn hết hạn lưu trên hệ thống."]),
    ("Câu 10: Điều kiện nào sau đây KHÔNG ĐƯỢC PHÉP đóng phiếu tự động (Auto-Close)?",
     ["A. Thuê bao có kết quả tiền kiểm là Bóp băng thông theo gói.",
      "B. Thuê bao VIP hoặc phiếu mở lại nhiều lần (Reopened tickets). (ĐÁP ÁN ĐÚNG)",
      "C. Thuê bao có kết quả tiền kiểm là Mạng lưới đảm bảo chất lượng.",
      "D. Thuê bao đã phát sinh lưu lượng bình thường sau thời điểm sự cố."])
]

for q_text, opts in questions:
    add_p(doc, q_text, bold_prefix="• ")
    for opt in opts:
        add_bullet(doc, opt, space_after=1)
    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_before = Pt(0)
    p_sp.paragraph_format.space_after = Pt(4)

# ==========================================
# PHỤ LỤC: THUẬT NGỮ CHUYÊN NGÀNH (GLOSSARY)
# ==========================================
doc.add_page_break()
add_styled_heading(doc, "PHỤ LỤC: BẢNG TRA CỨU THUẬT NGỮ CHUYÊN NGÀNH VIỄN THÔNG (GLOSSARY)", level=1)
add_p(doc, "Dành cho KTV và nhân sự mới làm quen với hệ thống mạng lõi và đo kiểm viễn thông VNPT:")

glossary_data = [
    ("3GPP", "3rd Generation Partnership Project", "Tổ chức thiết lập các tiêu chuẩn viễn thông di động quốc tế (GSM, UMTS, LTE, 5G NR)."),
    ("SAPC / PCRF", "Policy and Charging Rules Function", "Hệ thống máy chủ mạng lõi quản lý chính sách cước, gói cước data và hạn mức QoS băng thông."),
    ("OCS", "Online Charging System", "Hệ thống tính cước thời gian thực của VNPT, kiểm soát trừ tiền và hạ băng thông ngay trong phiên."),
    ("BTools", "Broadband Tools & CDR Logging", "Hệ thống ghi nhận bản ghi cước dữ liệu 4G/5G, lưu lượng tải, nguyên nhân ngắt phiên Cause Code."),
    ("CEM", "Customer Experience Management", "Hệ thống đo kiểm trải nghiệm khách hàng và chất lượng phát sóng vô tuyến trạm BTS/eNodeB."),
    ("RSRP", "Reference Signal Received Power", "Chỉ số cường độ tín hiệu vô tuyến thu được (dBm). RSRP > -90 dBm là sóng tốt; < -105 dBm là sóng yếu."),
    ("SINR", "Signal-to-Interference-plus-Noise Ratio", "Tỷ số tín hiệu trên nhiễu (dB). SINR càng cao thì tốc độ mạng càng nhanh và ổn định."),
    ("RAT Type", "Radio Access Technology Type", "Mã công nghệ sóng truy cập: 0 (Signaling), 1 (3G), 2 (2G), 6 (4G LTE), 7 (5G NR)."),
    ("CSFB", "Circuit Switched Fallback", "Cơ chế chuyển mạch hạ từ sóng 4G về 2G/3G để thực hiện cuộc gọi khi máy chưa bật tính năng VoLTE."),
    ("VoLTE", "Voice over LTE", "Dịch vụ thoại chất lượng cao trên nền tảng sóng 4G thông qua mạng lõi IMS."),
    ("AMBR", "Aggregate Maximum Bit Rate", "Tốc độ truyền dữ liệu tối đa cam kết cho thuê bao trên mạng lõi PCRF."),
    ("NAM", "Network Access Mode", "Cờ trạng thái cho phép truy cập mạng dữ liệu GPRS/LTE: 0 là Mở dịch vụ; 1 là Khóa dịch vụ do nợ cước."),
    ("OneOSS", "One Operations Support System", "Hệ thống phần mềm quản lý điều hành sản xuất kinh doanh và xử lý sự cố khách hàng của Tập đoàn VNPT.")
]
create_styled_table(doc, ["Thuật Ngữ", "Tên Tiếng Anh Đầy Đủ", "Ý Nghĩa Kỹ Thuật Viễn Thông"], glossary_data, [1.3, 2.2, 3.1])

# Lưu file Word
doc.save(OUT_DOCX)
print(f"✅ Đã tạo thành công Giáo trình Word Đẳng cấp Doanh nghiệp (~30 trang) tại: {OUT_DOCX}")

# =========================================================================
# XÂY DỰNG BỘ SLIDE POWERPOINT 24 SLIDE ĐỒNG BỘ 5 PHẦN (300 PHÚT)
# =========================================================================
print("🚀 Đang khởi tạo Bộ Slide Trình Chiếu PowerPoint 24 Slide Đồng Bộ 5 Phần...")
prs = Presentation()
prs.slide_width = PptInches(13.333)
prs.slide_height = PptInches(7.5)
blank_layout = prs.slide_layouts[6]

def add_slide_header(slide, title_text, category="GIÁO TRÌNH ĐÀO TẠO ỨNG DỤNG AI & TIỀN KIỂM PAKH — VNPT TTS PRECHECK"):
    top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, PptInches(0), PptInches(0), PptInches(13.333), PptInches(0.1))
    top_bar.fill.solid()
    top_bar.fill.fore_color.rgb = PPT_CYAN
    top_bar.line.fill.background()

    tb = slide.shapes.add_textbox(PptInches(0.8), PptInches(0.25), PptInches(11.7), PptInches(0.95))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p_cat = tf.paragraphs[0]
    p_cat.text = category.upper()
    p_cat.font.name = "Segoe UI"
    p_cat.font.size = PptPt(9)
    p_cat.font.bold = True
    p_cat.font.color.rgb = PPT_CYAN

    p_tit = tf.add_paragraph()
    p_tit.text = title_text
    p_tit.font.name = "Segoe UI"
    p_tit.font.size = PptPt(18)
    p_tit.font.bold = True
    p_tit.font.color.rgb = PPT_NAVY
    p_tit.space_before = PptPt(3)

def add_card(slide, left, top, width, height, bg_rgb=PPT_CARD_BG, border_rgb=PPT_CARD_BD):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = bg_rgb
    card.line.color.rgb = border_rgb
    card.line.width = PptPt(1)
    return card

# -------------------------------------------------------------
# SLIDE 1: BÌA BÀI GIẢNG (TITLE SLIDE)
# -------------------------------------------------------------
s1 = prs.slides.add_slide(blank_layout)
bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, PptInches(0), PptInches(0), PptInches(13.333), PptInches(7.5))
bg1.fill.solid()
bg1.fill.fore_color.rgb = PPT_NAVY
bg1.line.fill.background()

tb1 = s1.shapes.add_textbox(PptInches(1.2), PptInches(1.5), PptInches(10.9), PptInches(4.5))
tf1 = tb1.text_frame
tf1.word_wrap = True

p = tf1.paragraphs[0]
p.text = "TẬP ĐOÀN BƯU CHÍNH VIỄN THÔNG VIỆT NAM (VNPT) — VNPT-VINAPHONE"
p.font.name = "Segoe UI"
p.font.size = PptPt(13)
p.font.bold = True
p.font.color.rgb = PPT_CYAN

p = tf1.add_paragraph()
p.text = "ỨNG DỤNG AI & TỰ ĐỘNG HÓA\nTRONG TIỀN KIỂM PHẢN ÁNH KHÁCH HÀNG"
p.font.name = "Segoe UI"
p.font.size = PptPt(32)
p.font.bold = True
p.font.color.rgb = PPT_WHITE
p.space_before = PptPt(16)

p = tf1.add_paragraph()
p.text = "HỆ THỐNG TIỀN KIỂM 360° VNPT TTS PRECHECK & CẨM NANG VẬN HÀNH 6 PHÂN HỆ"
p.font.name = "Segoe UI"
p.font.size = PptPt(14)
p.font.color.rgb = PptRGBColor(203, 213, 225)
p.space_before = PptPt(14)

p = tf1.add_paragraph()
p.text = "Khóa đào tạo chuyên sâu 5 tiếng (300 Phút) • Dành cho KTV Viễn thông Tỉnh/TP & Điều hành SOC • Phiên bản 2026.04"
p.font.name = "Segoe UI"
p.font.size = PptPt(11)
p.font.color.rgb = PPT_CYAN
p.space_before = PptPt(24)

# -------------------------------------------------------------
# SLIDE 2: KHUNG TIẾN ĐỘ ĐÀO TẠO 5 TIẾNG (300 PHÚT)
# -------------------------------------------------------------
s2 = prs.slides.add_slide(blank_layout)
add_slide_header(s2, "MỤC TIÊU KHÓA ĐÀO TẠO & KHUNG TIẾN ĐỘ 5 TIẾNG (300 PHÚT)")

cards_s2 = [
    ("PHẦN I: TỔNG QUAN & AI", "45 Phút", "• Thực trạng thủ công vs Digital Copilot\n• Kiến trúc 3 tầng: NLP, Đa luồng, Bypass\n• Bản đồ 7 hệ thống vệ tinh viễn thông"),
    ("PHẦN II: THƯ VIỆN & LUẬT", "60 Phút", "• serviceid.json (Ma trận bóp, ODA_BIG_OCS)\n• rattype.json & Thuật toán rớt sóng\n• Phân tích sâu 7 kịch bản chẩn đoán"),
    ("PHẦN III: 6 PHÂN HỆ [TRỌNG TÂM]", "90 Phút", "• Mobile Internet 3 Card & Ca mạng chậm\n• Thoại (VoLTE/NAM), Chặn Spam NĐ 91\n• SMSC CDR thời gian thực, Roaming & SOC"),
    ("PHẦN IV: ĐÓNG PHIẾU 5.1", "45 Phút", "• Địa giới 2 cấp [Phường/Xã], [Tỉnh/TP]\n• Bảng 34 Tỉnh/TP mới, 1-click GPS trạm\n• Cheatsheet 73 mã OneOSS & Auto-Close"),
    ("PHẦN V: LAB & TEST", "45 Phút", "• Hands-on Lab 2 bài tập tình huống lớn\n• Bài kiểm tra trắc nghiệm 10 câu\n• Giải đáp vướng mắc & Tổng kết")
]

for idx, (title, time_lbl, content) in enumerate(cards_s2):
    left = PptInches(0.8 + idx * 2.4)
    add_card(s2, left, PptInches(1.4), PptInches(2.25), PptInches(5.4))
    tb = s2.shapes.add_textbox(left + PptInches(0.15), PptInches(1.55), PptInches(1.95), PptInches(5.1))
    tf = tb.text_frame
    tf.word_wrap = True
    
    p = tf.paragraphs[0]
    p.text = time_lbl.upper()
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(10)
    p.font.color.rgb = PPT_CYAN
    
    p = tf.add_paragraph()
    p.text = title
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(11)
    p.font.color.rgb = PPT_NAVY
    p.space_before = PptPt(4)
    
    p = tf.add_paragraph()
    p.text = content
    p.font.name = "Segoe UI"
    p.font.size = PptPt(9.5)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(10)

# -------------------------------------------------------------
# SLIDE 3: PHẦN I - BỐI CẢNH & MÔ HÌNH AI THỰC CHIẾN
# -------------------------------------------------------------
s3 = prs.slides.add_slide(blank_layout)
add_slide_header(s3, "PHẦN I: BỐI CẢNH XỬ LÝ THỦ CÔNG VS MÔ HÌNH AI THỰC CHIẾN (15 PHÚT)", "PHẦN I: TỔNG QUAN, BỐI CẢNH & KIẾN TRÚC HYBRID AI")

add_card(s3, PptInches(0.8), PptInches(1.4), PptInches(5.7), PptInches(5.4))
tb = s3.shapes.add_textbox(PptInches(1.0), PptInches(1.6), PptInches(5.3), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "THỰC TRẠNG QUY TRÌNH THỦ CÔNG"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(13)
p.font.color.rgb = PPT_DANGER

p = tf.add_paragraph()
p.text = (
    "• Mở phân tán 5-7 tab: OneOSS TTS, BTools, SAPC Core, CEM vô tuyến, CCOS...\n\n"
    "• Thời gian kéo dài: Mất 5 - 10 phút/phiếu, KTV phải tự copy paste số điện thoại qua từng hệ thống.\n\n"
    "• Dễ sai lệch do cảm tính: Cùng 1 ca hết dung lượng bóp tốc độ nhưng 2 KTV chọn 2 mã nguyên nhân khác nhau.\n\n"
    "• Nguy cơ vỡ SLA: Khi mạng lưới phát sinh sự cố diện rộng, hàng trăm phiếu tồn đọng gây quá tải trầm trọng."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(11)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(12)

add_card(s3, PptInches(6.8), PptInches(1.4), PptInches(5.7), PptInches(5.4))
tb = s3.shapes.add_textbox(PptInches(7.0), PptInches(1.6), PptInches(5.3), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "MÔ HÌNH AI THỰC CHIẾN = DIGITAL COPILOT"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(13)
p.font.color.rgb = PPT_SUCCESS

p = tf.add_paragraph()
p.text = (
    "• KHÔNG PHẢI CHATBOT: Tuyệt đối không dùng prompt ném cho ChatGPT/LLM thuần túy vì AI sẽ 'bịa' do thiếu log mạng thật.\n\n"
    "• CÔNG THỨC AI THỰC CHIẾN:\n"
    "  AI Đọc Hiểu (NLP) + Log Mạng Thật + Rule Engine Chuyên Gia\n\n"
    "• TRỢ LÝ KỸ SƯ SỐ (COPILOT):\n"
    "  1. Hiểu khách nói gì trong 0.005s (ai_interpreter.py)\n"
    "  2. Tự đi cào đủ 4 hệ thống Core trong 1.0 - 1.5s\n"
    "  3. Đối chiếu chứng cứ kỹ thuật & đề xuất mã OneOSS chuẩn."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(11)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(12)

# -------------------------------------------------------------
# SLIDE 4: PHẦN I - KIẾN TRÚC 3 TẦNG HYBRID AI
# -------------------------------------------------------------
s4 = prs.slides.add_slide(blank_layout)
add_slide_header(s4, "PHẦN I: KIẾN TRÚC 3 TẦNG HYBRID AI TRONG XỬ LÝ PAKH (30 PHÚT)", "PHẦN I: TỔNG QUAN, BỐI CẢNH & KIẾN TRÚC HYBRID AI")

layers = [
    ("TẦNG 1: ĐỌC HIỂU NGÔN NGỮ TỰ NHIÊN (NLP)", PPT_BLUE, 
     "• Chuyển ngôn ngữ đời thường sang tham số kỹ thuật:\n"
     "  'mạng quay tít thò lò sáng nay' ➔ issue_type: data_slow | mốc: sáng nay\n"
     "  'ở phú quốc sóng 1 vạch' ➔ địa bàn: đặc thù biển đảo | sóng yếu\n"
     "• Bộ đệm AI Caching (ai_cache.json): Phản hồi 0.005s, tiết kiệm 95% token."),
    ("TẦNG 2: THU THẬP ĐA NGUỒN (HIGH-CONCURRENCY)", PPT_CYAN,
     "• Đa luồng 2 cấp độ cực đại:\n"
     "  - Cấp danh sách: Quét đồng thời 8 thuê bao qua ThreadPoolExecutor.\n"
     "  - Cấp thuê bao: 3 luồng con song song (BTools + SAPC + CEM).\n"
     "• Toàn bộ chứng cứ hoàn tất chỉ trong 1.0 – 1.5 giây."),
    ("TẦNG 3: BYPASS THÔNG MINH PHI-DATA", PPT_NAVY,
     "• Phân loại thông minh: Phiếu Thoại (Voice) và Tin nhắn (SMS) tự động bỏ qua BTools và CEM.\n"
     "• Chỉ truy vấn Core HSS và cờ NAM ➔ Giảm thời gian kiểm tra xuống < 1s, chống nghẽn phiên BTools.")
]

for idx, (title, color_rgb, desc) in enumerate(layers):
    top = PptInches(1.4 + idx * 1.85)
    add_card(s4, PptInches(0.8), top, PptInches(11.7), PptInches(1.65))
    tb = s4.shapes.add_textbox(PptInches(1.1), top + PptInches(0.15), PptInches(11.1), PptInches(1.35))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(12)
    p.font.color.rgb = color_rgb
    p = tf.add_paragraph()
    p.text = desc
    p.font.name = "Segoe UI"
    p.font.size = PptPt(10)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(4)

# -------------------------------------------------------------
# SLIDE 5: PHẦN I - BẢN ĐỒ 7 HỆ THỐNG VỆ TINH
# -------------------------------------------------------------
s5 = prs.slides.add_slide(blank_layout)
add_slide_header(s5, "PHẦN I: BẢN ĐỒ KẾT NỐI 7 HỆ THỐNG VỆ TINH VIỄN THÔNG", "PHẦN I: TỔNG QUAN, BỐI CẢNH & KIẾN TRÚC HYBRID AI")

sat_cards = [
    ("1. OneOSS TTS (Mới & Cũ)", "https://ttsnew.vnpt.vn", "Cào danh sách phản ánh theo phân vùng KTV, cập nhật trạng thái phiếu và đóng phiếu chuẩn 5 cấp."),
    ("2. Core SAPC / PCRF", "10.155.42.218", "Tra cứu Profile cước: Gói Data kích hoạt trên OCS, cờ khóa NAM, hạn mức AMBR QoS, SIM 4G HSS."),
    ("3. BTools Chrome CDP", "10.159.21.241:9222", "Truy vấn CDR 4G/5G/3G gần nhất: Thời gian phiên, Bytes tải, RAT Type, Service ID, Cause ngắt phiên."),
    ("4. CEM Vô tuyến", "cem.vnptmedia.vn", "Đo kiểm cường độ sóng RSRP (dBm), SINR (dB), mã trạm BTS/eNodeB phục vụ, cảnh báo mất sóng."),
    ("5. Google Maps Geocoding", "10.155.59.158:1708", "Chuyển đổi tọa độ GPS từ CEM thành địa danh chuẩn 2 cấp [Phường/Xã], [Tỉnh/TP] theo 34 Tỉnh mới."),
    ("6. SMSC Gateway CDR", "Cổng SMSC Gateway", "Tra cứu tin nhắn OTP Brandname thời gian thực, mã trạng thái phân phát Delivery Status (0, 1, 2, 6, 21, 27).")
]

for idx, (title, ip_ep, desc) in enumerate(sat_cards):
    r_idx = idx // 3
    c_idx = idx % 3
    left = PptInches(0.8 + c_idx * 3.95)
    top = PptInches(1.4 + r_idx * 2.7)
    add_card(s5, left, top, PptInches(3.8), PptInches(2.5))
    tb = s5.shapes.add_textbox(left + PptInches(0.15), top + PptInches(0.15), PptInches(3.5), PptInches(2.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(11)
    p.font.color.rgb = PPT_NAVY
    p = tf.add_paragraph()
    p.text = ip_ep
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(9.5)
    p.font.color.rgb = PPT_CYAN
    p.space_before = PptPt(2)
    p = tf.add_paragraph()
    p.text = desc
    p.font.name = "Segoe UI"
    p.font.size = PptPt(9)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(6)

# -------------------------------------------------------------
# SLIDE 6: PHẦN II - SERVICEID.JSON & MA TRẬN BÓP BĂNG THÔNG
# -------------------------------------------------------------
s6 = prs.slides.add_slide(blank_layout)
add_slide_header(s6, "PHẦN II: THƯ VIỆN GÓI CƯỚC & MA TRẬN BÓP BĂNG THÔNG (SERVICEID.JSON)", "PHẦN II: THƯ VIỆN KỸ THUẬT & 7 KỊCH BẢN CHẨN ĐOÁN (60 PHÚT)")

add_card(s6, PptInches(0.8), PptInches(1.4), PptInches(6.0), PptInches(5.4))
tb = s6.shapes.add_textbox(PptInches(1.0), PptInches(1.55), PptInches(5.6), PptInches(5.1))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "MA TRẬN HẠ TỐC ĐỘ BÓP BĂNG THÔNG"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_DANGER

speeds = [
    ("10002", "64/64 Kbps", "Rất chậm, chỉ gửi tin text Zalo, web quay tít"),
    ("10003", "128/64 Kbps", "Chậm, đọc báo text 5-10s, không xem được video"),
    ("10005", "512/256 Kbps", "Trung bình thấp, video 240p/360p giật nhẹ"),
    ("10010", "1 Mbps", "Xem video 480p mượt, lướt FB/TikTok chậm nhẹ"),
    ("10011", "2 Mbps", "Video 720p HD, web bình thường, video call ổn"),
    ("10012", "3 Mbps", "Video 1080p Full HD mượt mà, trải nghiệm tốt"),
    ("10014", "128/128 Kbps", "Hạ băng thông hai chiều mức tối thiểu")
]
for m, sp, exp in speeds:
    p = tf.add_paragraph()
    p.text = f"• Mã {m} ({sp}): {exp}"
    p.font.name = "Segoe UI"
    p.font.size = PptPt(9)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(4)

add_card(s6, PptInches(7.1), PptInches(1.4), PptInches(5.4), PptInches(5.4))
tb = s6.shapes.add_textbox(PptInches(7.3), PptInches(1.55), PptInches(5.0), PptInches(5.1))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "GÓI CƯỚC CHỦ ĐẠO & OTT BYPASS"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_NAVY

p = tf.add_paragraph()
p.text = (
    "• MÃ 3000 / 0000003000: Dải gói OCS chủ đạo:\n"
    "  VD120N, YOLO90, BIG60, BIG70, D159SC, SPE7, DT120, VD89, U1500, D60G, MAX100...\n\n"
    "• MÃ 3001: PAYGO, M0 (Cước nền - Cảnh báo trừ tiền!)\n\n"
    "• GÓI OTT BYPASS MIỄN PHÍ DATA:\n"
    "  - Zalo: 2807 | ZingMP3: 2808\n"
    "  - Meta Facebook: 2910 | Instagram: 2913\n"
    "  - YouTube: 2902, 2920 | TikTok: 2917\n"
    "  - Liên Quân Mobile: 2916 | FreeFire: 2919\n"
    "  - Ví MoMo: 2932 | Shopee: 2925"
)
p.font.name = "Segoe UI"
p.font.size = PptPt(10)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 7: PHẦN II - QUY TẮC ODA_BIG_OCS & D159SC
# -------------------------------------------------------------
s7 = prs.slides.add_slide(blank_layout)
add_slide_header(s7, "PHẦN II: QUY TẮC SỐNG CÒN VỀ GÓI CƯỚC OCS & HỒ SƠ ODA_BIG_OCS", "PHẦN II: THƯ VIỆN KỸ THUẬT & 7 KỊCH BẢN CHẨN ĐOÁN (60 PHÚT)")

add_card(s7, PptInches(0.8), PptInches(1.4), PptInches(11.7), PptInches(5.4))
tb = s7.shapes.add_textbox(PptInches(1.1), PptInches(1.6), PptInches(11.1), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True

p = tf.paragraphs[0]
p.text = "QUY CHUẨN XỬ LÝ LỖI KHAI BÁO GÓI CƯỚC D159SC TRÊN HỆ THỐNG CORE OCS"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(14)
p.font.color.rgb = PPT_DANGER

rules_ocs_detail = [
    ("1. ĐẶC ĐIỂM GÓI OCS:", "Các gói Data OCS phổ thông như D159SC, VD120N, YOLO90 bắt buộc phải có profile ODA_BIG_OCS trên Core OCS để hệ thống trừ dung lượng data."),
    ("2. HIỆN TƯỢNG RỚT PROFILE:", "Khách hàng đăng ký gói D159SC thành công trên CCBS nhưng kiểm tra Core SAPC CHỈ CÓ gói ODA_MYTV mà THIẾU profile ODA_BIG_OCS. Khách hàng bật 4G sẽ không vào được mạng dù vẫn còn hạn dùng!"),
    ("3. HƯỚNG XỬ LÝ BẮT BUỘC:", "Hệ thống xác định đây là LỖI KHAI BÁO CỦA HỆ THỐNG. KTV KHÔNG ĐƯỢC đóng phiếu báo khách hết dung lượng, mà PHẢI chuyển hướng xử lý:\n👉 'Chuyển IT/CCBS kiểm tra khai báo gói cước {tên gói cước} cho Khách hàng'"),
    ("4. CẤM TUYỆT ĐỐI:", "Không được tư vấn khách nạp tiền mua thêm gói mới khi khách hàng đã đăng ký gói OCS hợp lệ.")
]

for tit, desc in rules_ocs_detail:
    p = tf.add_paragraph()
    p.text = tit
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(11)
    p.font.color.rgb = PPT_NAVY
    p.space_before = PptPt(8)
    
    p = tf.add_paragraph()
    p.text = desc
    p.font.name = "Segoe UI"
    p.font.size = PptPt(10.5)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(2)

# -------------------------------------------------------------
# SLIDE 8: PHẦN II - RAT TYPE & THUẬT TOÁN RỚT SÓNG
# -------------------------------------------------------------
s8 = prs.slides.add_slide(blank_layout)
add_slide_header(s8, "PHẦN II: CÔNG NGHỆ SÓNG RAT TYPE (0, 1, 2, 6, 7) & THUẬT TOÁN RỚT SÓNG", "PHẦN II: THƯ VIỆN KỸ THUẬT & 7 KỊCH BẢN CHẨN ĐOÁN (60 PHÚT)")

rats = [
    ("RAT 0", "BÁO HIỆU MẠNG", "None", "Các bản tin điều khiển thiết lập phiên. Không phát sinh lưu lượng người dùng tải về."),
    ("RAT 1", "SÓNG 3G (UTRAN)", "1 - 10 Mbps", "Công nghệ 3G cũ. Phát sinh nhiều là dấu hiệu khu vực sóng 4G rất yếu."),
    ("RAT 2", "SÓNG 2G (GERAN)", "40 - 200 Kbps", "Băng thông cực thấp, tải web lỗi timeout. Biểu hiện mất hoàn toàn sóng 4G."),
    ("RAT 6", "SÓNG 4G (E-UTRAN)", "30 - 150 Mbps", "Chuẩn sóng data chính. Thuê bao đạt chuẩn phải có > 80% phiên trên RAT 6."),
    ("RAT 7", "SÓNG 5G (NR)", "300 - 1000 Mbps", "Công nghệ 5G thế hệ mới tốc độ siêu cao của mạng VinaPhone.")
]

for idx, (m, name, sp, desc) in enumerate(rats):
    left = PptInches(0.8 + idx * 2.4)
    add_card(s8, left, PptInches(1.4), PptInches(2.25), PptInches(3.4))
    tb = s8.shapes.add_textbox(left + PptInches(0.15), PptInches(1.55), PptInches(1.95), PptInches(3.1))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = m
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(14)
    p.font.color.rgb = PPT_BLUE
    p = tf.add_paragraph()
    p.text = name
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(10)
    p.font.color.rgb = PPT_NAVY
    p.space_before = PptPt(2)
    p = tf.add_paragraph()
    p.text = f"Tốc độ: {sp}\n\n{desc}"
    p.font.name = "Segoe UI"
    p.font.size = PptPt(9)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(6)

add_card(s8, PptInches(0.8), PptInches(5.0), PptInches(11.7), PptInches(1.8))
tb = s8.shapes.add_textbox(PptInches(1.1), PptInches(5.15), PptInches(11.1), PptInches(1.5))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "THUẬT TOÁN PHÂN TÍCH TỶ LỆ RỚT SÓNG (RAT RATIO ANALYSIS)"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(11)
p.font.color.rgb = PPT_NAVY
p = tf.add_paragraph()
p.text = (
    "• Công thức tính: Tỷ lệ rớt 2G/3G = (Số phiên có RAT=1 + RAT=2) / (Tổng số phiên phát sinh) * 100%\n"
    "• Ngưỡng kích hoạt kịch bản: Nếu Tỷ lệ rớt 2G/3G > 50% ➔ Kích hoạt kịch bản 'Bắt sóng 4G kém' (Chuyển VTT tối ưu vùng phủ trạm).\n"
    "• Nếu Tỷ lệ 4G = 0% nhưng HSS đã mở 4G ➔ Lỗi thiết bị khách hàng chưa bật 4G hoặc hỏng thẻ SIM."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9.5)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(4)

# -------------------------------------------------------------
# SLIDE 9: PHẦN II - 7 KỊCH BẢN CHẨN ĐOÁN (PHẦN 1)
# -------------------------------------------------------------
s9 = prs.slides.add_slide(blank_layout)
add_slide_header(s9, "PHẦN II: 7 KỊCH BẢN CHẨN ĐOÁN KỸ THUẬT (KỊCH BẢN 1 - 4)", "PHẦN II: THƯ VIỆN KỸ THUẬT & 7 KỊCH BẢN CHẨN ĐOÁN (60 PHÚT)")

scenarios_p1 = [
    ("KỊCH BẢN 1: BÓP BĂNG THÔNG THEO GÓI", PPT_DANGER,
     "• Dấu hiệu: SAPC hết dung lượng tốc độ cao; BTools xuất hiện mã bóp 10002..10014.\n"
     "• Nguyên nhân: Dùng hết data gói trong chu kỳ.\n"
     "• OneOSS: Hạ băng thông theo chính sách gói cước.\n"
     "• Xử lý: Tư vấn khách hàng mua thêm gói addon ngày/tuần."),
    ("KỊCH BẢN 2: HOẠT ĐỘNG BÌNH THƯỜNG (TỰ PHỤC HỒI)", PPT_SUCCESS,
     "• Dấu hiệu: Sau mốc phản ánh, BTools ghi nhận phiên > 10MB hoặc tổng > 30MB, sóng 4G tốt.\n"
     "• Nguyên nhân: Sự cố tạm thời đã qua (đã rời vùng mất sóng).\n"
     "• OneOSS: Mạng lưới đảm bảo chất lượng / Khách hàng theo dõi thêm.\n"
     "• Xử lý: Đóng phiếu thông báo dịch vụ bình thường."),
    ("KỊCH BẢN 3: ĐẶC THÙ ĐỊA HÌNH BIỂN ĐẢO", PPT_WARN,
     "• Dấu hiệu: Khách báo sóng yếu tại đặc khu/hải đảo (Phú Quốc, Côn Đảo...). Trạm CEM ở xa.\n"
     "• Nguyên nhân: Suy hao truyền dẫn tự nhiên trên mặt biển.\n"
     "• OneOSS: Do địa hình / vật cản / Theo dõi thêm.\n"
     "• Xử lý: Giải thích đặc thù vùng phủ, chuyển ban phát triển trạm."),
    ("KỊCH BẢN 4: LƯU LƯỢNG YẾU - TẬP TRUNG 1 TRẠM", PPT_BLUE,
     "• Dấu hiệu: Lưu lượng < 1MB/phiên. > 90% kết nối tập trung 1 Cell CEM có RSRP < -105 dBm.\n"
     "• Nguyên nhân: Mép vùng phủ sóng hoặc trạm phát quá tải cục bộ.\n"
     "• OneOSS: Do vùng phủ sóng / Tối ưu trạm BTS.\n"
     "• Xử lý: Chuyển VTT địa bàn đo kiểm và tối ưu góc ngẩng anten.")
]

for idx, (title, color_rgb, desc) in enumerate(scenarios_p1):
    r_idx = idx // 2
    c_idx = idx % 2
    left = PptInches(0.8 + c_idx * 5.95)
    top = PptInches(1.4 + r_idx * 2.75)
    add_card(s9, left, top, PptInches(5.75), PptInches(2.55))
    tb = s9.shapes.add_textbox(left + PptInches(0.15), top + PptInches(0.15), PptInches(5.45), PptInches(2.25))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(11)
    p.font.color.rgb = color_rgb
    p = tf.add_paragraph()
    p.text = desc
    p.font.name = "Segoe UI"
    p.font.size = PptPt(9.5)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(6)

# -------------------------------------------------------------
# SLIDE 10: PHẦN II - 7 KỊCH BẢN CHẨN ĐOÁN (PHẦN 2)
# -------------------------------------------------------------
s10 = prs.slides.add_slide(blank_layout)
add_slide_header(s10, "PHẦN II: 7 KỊCH BẢN CHẨN ĐOÁN KỸ THUẬT (KỊCH BẢN 5 - 7)", "PHẦN II: THƯ VIỆN KỸ THUẬT & 7 KỊCH BẢN CHẨN ĐOÁN (60 PHÚT)")

scenarios_p2 = [
    ("KỊCH BẢN 5: TREO PHIÊN KẾT NỐI (CAUSE CODE 300 / 2042)", PPT_DARK,
     "• Dấu hiệu: BTools có mã ngắt phiên GTP-C timeout 300 hoặc 2042, không phát sinh lưu lượng người dùng.\n"
     "• Nguyên nhân: Gói cước treo phiên trên Core OCS hoặc máy lỗi cấu hình APN ('m3-world').\n"
     "• OneOSS: Lỗi đầu cuối / Treo phiên PDP.\n"
     "• Xử lý: Hướng dẫn bật tắt chế độ máy bay. Nếu không được, chuyển IT reset profile OCS."),
    ("KỊCH BẢN 6: KHÓA CƯỚC CHIỀU GPRS (CỜ NAM = 1)", PPT_DANGER,
     "• Dấu hiệu: Tra cứu SAPC/HSS phát hiện cờ NAM = 1 (màu đỏ cảnh báo).\n"
     "• Nguyên nhân: Thuê bao bị hệ thống khóa chiều dịch vụ dữ liệu do nợ cước.\n"
     "• OneOSS: Chặn cước chiều GPRS.\n"
     "• Xử lý: Thông báo khách hàng thanh toán cước để được tự động mở lại dịch vụ."),
    ("KỊCH BẢN 7: CẢNH BÁO APP VPN / 1.1.1.1 BÊN THỨ BA", PPT_CYAN,
     "• Dấu hiệu: RAT 1, 6 có lưu lượng các phiên duy trì đều nhau bất thường 5MB - 11.5MB (Warp, Turbo VPN).\n"
     "• Nguyên nhân: Ứng dụng VPN định tuyến qua máy chủ quốc tế làm gián đoạn đường truyền trong nước.\n"
     "• OneOSS: Lỗi phần mềm / Thiết bị đầu cuối.\n"
     "• Xử lý: Hướng dẫn khách hàng tạm tắt VPN để sử dụng tốc độ mạng gốc tối đa.")
]

for idx, (title, color_rgb, desc) in enumerate(scenarios_p2):
    top = PptInches(1.4 + idx * 1.85)
    add_card(s10, PptInches(0.8), top, PptInches(11.7), PptInches(1.65))
    tb = s10.shapes.add_textbox(PptInches(1.1), top + PptInches(0.15), PptInches(11.1), PptInches(1.35))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(11.5)
    p.font.color.rgb = color_rgb
    p = tf.add_paragraph()
    p.text = desc
    p.font.name = "Segoe UI"
    p.font.size = PptPt(9.5)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(4)

# -------------------------------------------------------------
# SLIDE 11: PHẦN III - DASHBOARD & VNPT TOKEN UTILITIES
# -------------------------------------------------------------
s11 = prs.slides.add_slide(blank_layout)
add_slide_header(s11, "PHẦN III: GIAO DIỆN DASHBOARD & ĐỒNG BỘ VNPT TOKEN UTILITIES", "PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ (90 PHÚT)")

if os.path.exists(IMG_SUMMARY):
    s11.shapes.add_picture(IMG_SUMMARY, PptInches(0.8), PptInches(1.4), width=PptInches(6.8))

add_card(s11, PptInches(7.9), PptInches(1.4), PptInches(4.6), PptInches(5.4))
tb = s11.shapes.add_textbox(PptInches(8.1), PptInches(1.55), PptInches(4.2), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "TIỆN ÍCH MỞ RỘNG & ĐIỀU HÀNH"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_NAVY

p = tf.add_paragraph()
p.text = (
    "• VNPT TOKEN UTILITIES:\n"
    "  Extension Chrome tự động đồng bộ Token Bearer OneOSS TTS Mới và Cookie phiên TTS Cũ (34 TTP) sang máy chủ 1234 an toàn.\n\n"
    "• CHẤM ĐỎ THÔNG BÁO (RED DOT):\n"
    "  Hiển thị khi có phiếu mới phát sinh; click trực tiếp để đánh dấu đã xem.\n\n"
    "• SẮP XẾP 2 CHIỀU (SORT):\n"
    "  Click tiêu đề 'Thời gian sự cố' để đổi thứ tự ưu tiên xử lý.\n\n"
    "• CHUYỂN TAB 6 PHÂN HỆ:\n"
    "  Mobile Internet, Cuộc gọi, Chặn spam, Tin nhắn, CVQT, Quản trị KTV."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9.5)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 12: PHẦN III - PHÂN HỆ 1: MOBILE INTERNET (3 CARD)
# -------------------------------------------------------------
s12 = prs.slides.add_slide(blank_layout)
add_slide_header(s12, "PHẦN III: PHÂN HỆ 1 - MOBILE INTERNET (3 CARD NGHIỆP VỤ - 30 PHÚT)", "PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ (90 PHÚT)")

if os.path.exists(IMG_EXPANDED):
    s12.shapes.add_picture(IMG_EXPANDED, PptInches(0.8), PptInches(1.4), width=PptInches(6.8))

add_card(s12, PptInches(7.9), PptInches(1.4), PptInches(4.6), PptInches(5.4))
tb = s12.shapes.add_textbox(PptInches(8.1), PptInches(1.55), PptInches(4.2), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "BÓC TÁCH 3 CARD CHI TIẾT"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_BLUE

p = tf.add_paragraph()
p.text = (
    "• CARD 1: THÔNG TIN PHIẾU & KẾT LUẬN\n"
    "  Mã OneOSS, số thuê bao, nội dung phản ánh, kết luận bot và màu nhận diện.\n\n"
    "• CARD 2: PROFILE SAPC & SÓNG CEM\n"
    "  Gói OCS, cờ NAM, QoS cam kết, sóng trạm CEM (RSRP, SINR, mã BTS).\n\n"
    "• CARD 3: LOG BTOOLS & ONEOSS\n"
    "  Danh sách phiên CDR, nút 1-click nhận diện Phường/Xã từ GPS trạm, chọn mã lỗi và nút đóng phiếu OneOSS."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9.5)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 13: PHẦN III - PHÂN HỆ 2: CUỘC GỌI & THOẠI (20 PHÚT)
# -------------------------------------------------------------
s13 = prs.slides.add_slide(blank_layout)
add_slide_header(s13, "PHẦN III: PHÂN HỆ 2 - CUỘC GỌI & THOẠI (VOLTE, HLR, CỜ NAM - 20 PHÚT)", "PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ (90 PHÚT)")

if os.path.exists(IMG_VOICE):
    s13.shapes.add_picture(IMG_VOICE, PptInches(0.8), PptInches(1.4), width=PptInches(6.8))

add_card(s13, PptInches(7.9), PptInches(1.4), PptInches(4.6), PptInches(5.4))
tb = s13.shapes.add_textbox(PptInches(8.1), PptInches(1.55), PptInches(4.2), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "NGHIỆP VỤ TIỀN KIỂM THOẠI"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_NAVY

p = tf.add_paragraph()
p.text = (
    "• CỜ KHÓA CƯỚC THOẠI (NAM):\n"
    "  NAM: 0 (Mở) - Xanh lá | NAM: 1 (Khóa nợ cước) - Đỏ.\n\n"
    "• HSS PROFILE THOẠI & VOLTE:\n"
    "  Kiểm tra kích hoạt IMS VoLTE. Cảnh báo PROFILE LẠ nếu chưa cấu hình chuẩn.\n\n"
    "• LỖI RỚT MẠNG CSFB:\n"
    "  Khách báo mất 4G khi có cuộc gọi -> Hướng dẫn soạn HDV gửi 888 bật VoLTE.\n\n"
    "• NÚT CHUYỂN BƯỚC 2.4 NHANH:\n"
    "  Duyệt nhanh chuyển bước 2.4/2.6 theo đúng quy chuẩn OneOSS."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9.5)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 14: PHẦN III - PHÂN HỆ 3: CHẶN SPAM NGHỊ ĐỊNH 91 (15 PHÚT)
# -------------------------------------------------------------
s14 = prs.slides.add_slide(blank_layout)
add_slide_header(s14, "PHẦN III: PHÂN HỆ 3 - CHẶN SPAM NGOẠI MẠNG (NGHỊ ĐỊNH 91 & CCOS - 15 PHÚT)", "PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ (90 PHÚT)")

if os.path.exists(IMG_SPAM):
    s14.shapes.add_picture(IMG_SPAM, PptInches(0.8), PptInches(1.4), width=PptInches(6.8))

add_card(s14, PptInches(7.9), PptInches(1.4), PptInches(4.6), PptInches(5.4))
tb = s14.shapes.add_textbox(PptInches(8.1), PptInches(1.55), PptInches(4.2), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "ĐỐI SOÁT CAM KẾT CCOS"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_CYAN

p = tf.add_paragraph()
p.text = (
    "• NHÀ MẠNG BỊ ẢNH HƯỞNG:\n"
    "  Tự động gắn huy hiệu nhà mạng chặn cuộc gọi (Viettel, MobiFone, Vietnamobile...).\n\n"
    "• ĐÃ CÓ BẢN CAM KẾT (XANH LÁ):\n"
    "  Tìm thấy biên bản cam kết đính kèm trên CCOS. KTV chọn: 'Đã có bản cam kết, chuyển KTV kiểm tra mở chặn'.\n\n"
    "• CHƯA CÓ BẢN CAM KẾT (ĐỎ):\n"
    "  Chưa có cam kết trên CCOS. Hướng dẫn khách ra quầy ký biên bản cam kết không gọi rác."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9.5)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 15: PHẦN III - PHÂN HỆ 4: SMS & CỔNG SMSC CDR GATEWAY (15 PHÚT)
# -------------------------------------------------------------
s15 = prs.slides.add_slide(blank_layout)
add_slide_header(s15, "PHẦN III: PHÂN HỆ 4 - TIN NHẮN SMS & CỔNG TRA CỨU SMSC CDR GATEWAY (15 PHÚT)", "PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ (90 PHÚT)")

if os.path.exists(IMG_SMS):
    s15.shapes.add_picture(IMG_SMS, PptInches(0.8), PptInches(1.4), width=PptInches(6.8))

add_card(s15, PptInches(7.9), PptInches(1.4), PptInches(4.6), PptInches(5.4))
tb = s15.shapes.add_textbox(PptInches(8.1), PptInches(1.55), PptInches(4.2), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "ĐỐI SOÁT SMS THỜI GIAN THỰC"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_BLUE

p = tf.add_paragraph()
p.text = (
    "• CỔNG SMSC GATEWAY TRỰC TIẾP:\n"
    "  Tích hợp nút 'Tra cứu SMSC CDR' tại từng phiếu, mở modal xem trực tiếp lịch sử tin nhắn trong 7 ngày.\n\n"
    "• CHI TIẾT BẢN TIN CDR:\n"
    "  - Thời gian gửi/nhận chính xác đến từng giây.\n"
    "  - Đầu số Brandname (Ngân hàng, VNeID, OTP Google, Facebook...).\n"
    "  - Mã trạng thái phát tin Delivery Status."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9.5)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 16: PHẦN III - BẢNG MÃ LỖI PHÂN PHÁT SMSC GATEWAY
# -------------------------------------------------------------
s16 = prs.slides.add_slide(blank_layout)
add_slide_header(s16, "PHẦN III: BẢNG MÃ TRẠNG THÁI PHÂN PHÁT TIN NHẮN SMSC GATEWAY", "PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ (90 PHÚT)")

if os.path.exists(IMG_SMS_MODAL):
    s16.shapes.add_picture(IMG_SMS_MODAL, PptInches(0.8), PptInches(1.4), width=PptInches(6.8))

add_card(s16, PptInches(7.9), PptInches(1.4), PptInches(4.6), PptInches(5.4))
tb = s16.shapes.add_textbox(PptInches(8.1), PptInches(1.55), PptInches(4.2), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "BẢNG MÃ LỖI SMSC TIÊU CHUẨN"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_NAVY

p = tf.add_paragraph()
p.text = (
    "• MÃ 0 (DELIVERED): Thành công, tin đã phát đến máy. Hướng dẫn khách kiểm tra thư mục Spam.\n\n"
    "• MÃ 1 (EXPIRED): Hết hạn lưu tin trên SMSC do thuê bao tắt máy/mất sóng liên tục.\n\n"
    "• MÃ 6 (UNDELIVERABLE): Không thể phát (SIM hỏng, máy đầy bộ nhớ, chặn Brandname).\n\n"
    "• MÃ 21 (ABSENT SUBSCRIBER): Thuê bao tắt máy/ngoài vùng phủ lúc gửi OTP.\n\n"
    "• MÃ 27 (CALL BARRED): Bị chặn chiều nhận tin nhắn trên HLR Core."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 17: PHẦN III - PHÂN HỆ 5 & 6: ROAMING, SIM & QUẢN TRỊ SOC (10 PHÚT)
# -------------------------------------------------------------
s17 = prs.slides.add_slide(blank_layout)
add_slide_header(s17, "PHẦN III: PHÂN HỆ 5 & 6 - CVQT (ROAMING), SIM / ESIM & QUẢN TRỊ SOC (10 PHÚT)", "PHẦN III: CẨM NANG VẬN HÀNH THỰC CHIẾN 6 PHÂN HỆ (90 PHÚT)")

add_card(s17, PptInches(0.8), PptInches(1.4), PptInches(5.7), PptInches(5.4))
tb = s17.shapes.add_textbox(PptInches(1.0), PptInches(1.55), PptInches(5.3), PptInches(5.1))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "PHÂN HỆ 5: CVQT (ROAMING) & SIM / ESIM"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_CYAN

p = tf.add_paragraph()
p.text = (
    "• CHUYỂN VÙNG QUỐC TẾ (IR):\n"
    "  - Kiểm tra mở dịch vụ IR trước xuất cảnh (DK CVQT gửi 9123).\n"
    "  - Kiểm tra hạn dùng gói Data Roaming (R500N, IR_POST).\n"
    "  - Bắt buộc bật 'Chuyển vùng dữ liệu' trên máy khách.\n\n"
    "• LỖI SIM VẬT LÝ & ESIM:\n"
    "  - Phôi SIM cũ trước 2018 -> Tư vấn đổi USIM 4G/5G.\n"
    "  - SIM mòn tiếp xúc mạch đồng báo No SIM.\n"
    "  - Đổi máy làm mất eSIM -> Hướng dẫn quét lại QR qua MyVNPT."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(10)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

add_card(s17, PptInches(6.8), PptInches(1.4), PptInches(5.7), PptInches(5.4))
tb = s17.shapes.add_textbox(PptInches(7.0), PptInches(1.55), PptInches(5.3), PptInches(5.1))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "PHÂN HỆ 6: QUẢN TRỊ KTV SOC & GIÁM SÁT SLA"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_NAVY

p = tf.add_paragraph()
p.text = (
    "• PHÂN VÙNG PHỤ TRÁCH KTV:\n"
    "  Gán KTV vào từng Tỉnh/TP hoặc nhóm dịch vụ cụ thể.\n\n"
    "• CẤU HÌNH AUTO-CLOSE AN TOÀN:\n"
    "  Bật tự động đóng phiếu theo các tiêu chí khắt khe đã được phê duyệt.\n\n"
    "• THEO DÕI NĂNG SUẤT CA TRỰC:\n"
    "  Giám sát số lượng phiếu xử lý, tỷ lệ đạt SLA và độ chính xác phân loại của từng KTV."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(10)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 18: PHẦN IV - VẬN HÀNH AUTO-CLOSE CÓ KIỂM SOÁT
# -------------------------------------------------------------
s18 = prs.slides.add_slide(blank_layout)
add_slide_header(s18, "PHẦN IV: VẬN HÀNH CHẾ ĐỘ AUTO-CLOSE CÓ KIỂM SOÁT AN TOÀN", "PHẦN IV: QUY CHUẨN ĐÓNG PHIẾU 5.1 & AUTO-CLOSE AN TOÀN (45 PHÚT)")

add_card(s18, PptInches(0.8), PptInches(1.4), PptInches(11.7), PptInches(5.4))
tb = s18.shapes.add_textbox(PptInches(1.1), PptInches(1.6), PptInches(11.1), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True

p = tf.paragraphs[0]
p.text = "3 TIÊU CHÍ VÀNG ĐỂ KÍCH HOẠT ĐÓNG PHIẾU TỰ ĐỘNG (AUTO-CLOSE)"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(14)
p.font.color.rgb = PPT_SUCCESS

auto_rules = [
    ("TIÊU CHÍ 1: KẾT QUẢ TIỀN KIỂM PHẢI RÕ RÀNG", "Chỉ tự động đóng phiếu khi bot xác nhận: (1) Mạng lưới đảm bảo chất lượng HOẶC (2) Bóp băng thông theo chính sách gói cước HOẶC (3) Hoạt động bình thường sau thời điểm sự cố."),
    ("TIÊU CHÍ 2: TUYỆT ĐỐI BỎ QUA THUÊ BAO VIP", "Nếu thuê bao được gắn nhãn VIP hoặc khách hàng doanh nghiệp lớn -> Hệ thống bypass không đóng tự động, bắt buộc KTV trực ca thẩm định trực tiếp."),
    ("TIÊU CHÍ 3: LOẠI TRỪ PHIẾU MỞ LẠI NHIỀU LẦN (REOPENED)", "Các phiếu khách hàng khiếu nại lại lần 2, lần 3 không được phép đóng tự động; cần chuyển KTV chuyên sâu kiểm tra lịch sử xử lý trước đó.")
]

for tit, desc in auto_rules:
    p = tf.add_paragraph()
    p.text = tit
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(11)
    p.font.color.rgb = PPT_NAVY
    p.space_before = PptPt(10)
    
    p = tf.add_paragraph()
    p.text = desc
    p.font.name = "Segoe UI"
    p.font.size = PptPt(10.5)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(2)

# -------------------------------------------------------------
# SLIDE 19: PHẦN IV - QUY CHUẨN ĐỊA BÀN 2 CẤP [PHƯỜNG/XÃ], [TỈNH/TP]
# -------------------------------------------------------------
s19 = prs.slides.add_slide(blank_layout)
add_slide_header(s19, "PHẦN IV: QUY CHUẨN ĐỊA GIỚI HÀNH CHÍNH 2 CẤP KHI ĐÓNG PHIẾU 5.1 (20 PHÚT)", "PHẦN IV: QUY CHUẨN ĐÓNG PHIẾU 5.1 & AUTO-CLOSE AN TOÀN (45 PHÚT)")

if os.path.exists(IMG_WARD):
    s19.shapes.add_picture(IMG_WARD, PptInches(0.8), PptInches(1.4), width=PptInches(6.8))

add_card(s19, PptInches(7.9), PptInches(1.4), PptInches(4.6), PptInches(5.4))
tb = s19.shapes.add_textbox(PptInches(8.1), PptInches(1.55), PptInches(4.2), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "QUY CHUẨN ĐỊA BÀN 2 CẤP"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_WARN

p = tf.add_paragraph()
p.text = (
    "• ĐỊNH DẠNG DUY NHẤT 2 CẤP:\n"
    "  [Phường/Xã/Thị trấn], [Tỉnh/Thành phố]\n"
    "  (VD: Phường Bến Nghé, TP. Hồ Chí Minh).\n\n"
    "• CẤM TUYỆT ĐỐI:\n"
    "  Không lấy cấp thôn, ấp, bản, khóm, tổ (Ấp 1, Thôn 3).\n"
    "  Không dùng mã trạm viết tắt (PLO, DLI, BLU).\n\n"
    "• CÁCH 1 (1-CLICK TỰ ĐỘNG - KHUYÊN DÙNG):\n"
    "  Bấm nút mũi tên xanh (↑) cạnh Radio ở Card 2. Hệ thống lấy GPS trạm tự động điền chuẩn!\n\n"
    "• CÁCH 2 (SỬA TEXT THỦ CÔNG):\n"
    "  Xóa bỏ phần ấp, giữ lại đúng Phường/Xã và Tỉnh/TP."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9.5)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(6)

# -------------------------------------------------------------
# SLIDE 20: PHẦN IV - BẢNG 34 TỈNH/TP MỚI & 3 MIỀN
# -------------------------------------------------------------
s20 = prs.slides.add_slide(blank_layout)
add_slide_header(s20, "PHẦN IV: DANH MỤC 34 TỈNH / THÀNH PHỐ MỚI & PHÂN BỔ 3 MIỀN", "PHẦN IV: QUY CHUẨN ĐÓNG PHIẾU 5.1 & AUTO-CLOSE AN TOÀN (45 PHÚT)")

regions = [
    ("MIỀN BẮC (MB) — 18 ĐƠN VỊ", PPT_BLUE,
     "TP. Hà Nội, TP. Hải Phòng (gồm Hải Dương), Cao Bằng, Lạng Sơn, Lai Châu, Điện Biên, Sơn La, Quảng Ninh, Tuyên Quang (gồm Hà Giang), Lào Cai (gồm Yên Bái), Thái Nguyên (gồm Bắc Kạn), Phú Thọ (Vĩnh Phúc+Hòa Bình), Bắc Ninh (gồm Bắc Giang), Hưng Yên (gồm Thái Bình), Ninh Bình (Hà Nam+Nam Định), Thanh Hóa, Nghệ An, Hà Tĩnh."),
    ("MIỀN NAM (MN) — 9 ĐƠN VỊ", PPT_SUCCESS,
     "TP. Hồ Chí Minh (gồm Bình Dương + Bà Rịa Vũng Tàu), TP. Cần Thơ (gồm Sóc Trăng + Hậu Giang), Lâm Đồng (Đắk Nông + Bình Thuận), Đồng Nai (gồm Bình Phước), Tây Ninh (gồm Long An), Vĩnh Long (Bến Tre + Trà Vinh), Đồng Tháp (gồm Tiền Giang), Cà Mau (gồm Bạc Liêu), An Giang (Kiên Giang + An Giang gồm Đặc khu Phú Quốc)."),
    ("MIỀN TRUNG (MT) — 7 ĐƠN VỊ", PPT_WARN,
     "TP. Huế (nâng cấp từ TT-Huế), TP. Đà Nẵng (gồm Quảng Nam), Quảng Trị (gồm Quảng Bình), Quảng Ngãi (gồm Kon Tum), Gia Lai (gồm Bình Định), Khánh Hòa (gồm Ninh Thuận), Đắk Lắk (gồm Phú Yên).")
]

for idx, (title, color_rgb, desc) in enumerate(regions):
    top = PptInches(1.4 + idx * 1.85)
    add_card(s20, PptInches(0.8), top, PptInches(11.7), PptInches(1.65))
    tb = s20.shapes.add_textbox(PptInches(1.1), top + PptInches(0.15), PptInches(11.1), PptInches(1.35))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(12)
    p.font.color.rgb = color_rgb
    p = tf.add_paragraph()
    p.text = desc
    p.font.name = "Segoe UI"
    p.font.size = PptPt(9.5)
    p.font.color.rgb = PPT_DARK
    p.space_before = PptPt(4)

# -------------------------------------------------------------
# SLIDE 21: PHẦN IV - CHEATSHEET 73 MÃ NGUYÊN NHÂN ONEOSS (25 PHÚT)
# -------------------------------------------------------------
s21 = prs.slides.add_slide(blank_layout)
add_slide_header(s21, "PHẦN IV: CHEATSHEET NHÓM MÃ NGUYÊN NHÂN ĐÓNG PHIẾU ONEOSS 5.1 (25 PHÚT)", "PHẦN IV: QUY CHUẨN ĐÓNG PHIẾU 5.1 & AUTO-CLOSE AN TOÀN (45 PHÚT)")

if os.path.exists(IMG_CAUSE):
    s21.shapes.add_picture(IMG_CAUSE, PptInches(0.8), PptInches(1.4), width=PptInches(6.8))

add_card(s21, PptInches(7.9), PptInches(1.4), PptInches(4.6), PptInches(5.4))
tb = s21.shapes.add_textbox(PptInches(8.1), PptInches(1.55), PptInches(4.2), PptInches(5.0))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "CÁC MÃ ONEOSS PHỔ BIẾN NHẤT"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_NAVY

p = tf.add_paragraph()
p.text = (
    "• 5.1.01: Không đáp ứng do Thuê bao hết lưu lượng / hạ băng thông (mã 10002..10014).\n\n"
    "• 5.1.02: Không đáp ứng do Thiết bị khách hàng / Cài đặt máy (tắt data, VPN, sai APN).\n\n"
    "• 5.1.03: Không đáp ứng do Vùng phủ sóng kém (rớt 2G/3G > 50%, RSRP < -105 dBm).\n\n"
    "• 5.1.04: Chưa khai báo Profile 4G trên Core.\n\n"
    "• 5.1.05: Trạm phát BTS sự cố / mất điện lưới.\n\n"
    "• 5.1.06: Đáp ứng - Đã hướng dẫn khách sử dụng."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(9)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(6)

# -------------------------------------------------------------
# SLIDE 22: PHẦN V - KỊCH BẢN THỰC HÀNH TÌNH HUỐNG (25 PHÚT)
# -------------------------------------------------------------
s22 = prs.slides.add_slide(blank_layout)
add_slide_header(s22, "PHẦN V: KỊCH BẢN THỰC HÀNH TÌNH HUỐNG (HANDS-ON LAB - 25 PHÚT)", "PHẦN V: THỰC HÀNH TÌNH HUỐNG & ĐÁNH GIÁ CUỐI KHÓA (45 PHÚT)")

add_card(s22, PptInches(0.8), PptInches(1.4), PptInches(5.7), PptInches(5.4))
tb = s22.shapes.add_textbox(PptInches(1.0), PptInches(1.55), PptInches(5.3), PptInches(5.1))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "BÀI TẬP 1: THUÊ BAO BÁO MẠNG CHẬM"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_BLUE

p = tf.add_paragraph()
p.text = (
    "• Tình huống: Khách hàng 0913xxxxxx báo mạng chậm từ 14:00 chiều qua.\n\n"
    "• Yêu cầu học viên:\n"
    "  1. Bấm nút Tiền kiểm trên dòng phiếu.\n"
    "  2. Mở Card 2 đối soát: Gói cước gì? RSRP bao nhiêu dBm?\n"
    "  3. Nhìn Card 3 bảng BTools: Tìm mã Service ID (10003?).\n"
    "  4. Thẩm định kết luận của Bot.\n"
    "  5. Bấm nút mũi tên xanh (↑) nhận diện Phường/Xã từ trạm BTS.\n"
    "  6. Chọn mã 5.1.01 và thực hiện đóng phiếu."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(10)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

add_card(s22, PptInches(6.8), PptInches(1.4), PptInches(5.7), PptInches(5.4))
tb = s22.shapes.add_textbox(PptInches(7.0), PptInches(1.55), PptInches(5.3), PptInches(5.1))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "BÀI TẬP 2: PHIẾU THOẠI Ở BƯỚC 2.3"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(12)
p.font.color.rgb = PPT_NAVY

p = tf.add_paragraph()
p.text = (
    "• Tình huống: Thuê bao phản ánh không gọi đi được đến số cố định.\n\n"
    "• Yêu cầu học viên:\n"
    "  1. Chuyển sang Tab 'Cuộc gọi'.\n"
    "  2. Bấm tiền kiểm hồ sơ thuê bao.\n"
    "  3. Kiểm tra cờ NAM (0 hay 1?) và trạm VLR phục vụ gần nhất.\n"
    "  4. Bấm nút Chuyển 2.4 nhanh trên giao diện để đưa phiếu sang bước Đánh giá kết quả mà không tự động fill comment sai lệch."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(10)
p.font.color.rgb = PPT_DARK
p.space_before = PptPt(8)

# -------------------------------------------------------------
# SLIDE 23: PHẦN V - 10 CÂU HỎI TRẮC NGHIỆM ĐÁNH GIÁ (20 PHÚT)
# -------------------------------------------------------------
s23 = prs.slides.add_slide(blank_layout)
add_slide_header(s23, "PHẦN V: BỘ CÂU HỎI ĐÁNH GIÁ CUỐI KHÓA (QUIZ - 20 PHÚT)", "PHẦN V: THỰC HÀNH TÌNH HUỐNG & ĐÁNH GIÁ CUỐI KHÓA (45 PHÚT)")

quizzes = [
    ("Câu 1: Bản chất mô hình AI thực chiến trong VNPT TTS Precheck là gì?", "Đáp án: B. Kết hợp NLP đọc hiểu + Thu thập log mạng thật + Rule Engine."),
    ("Câu 2: Phát hiện Service ID 10003 (128/64k), mã đóng phiếu đúng là gì?", "Đáp án: C. Hạ băng thông theo chính sách gói cước (hết lưu lượng)."),
    ("Câu 3: Gói D159SC thiếu profile ODA_BIG_OCS trên SAPC, xử lý thế nào?", "Đáp án: B. Chuyển IT/CCBS kiểm tra khai báo gói cước cho Khách hàng."),
    ("Câu 4: Quy chuẩn địa giới hành chính bắt buộc khi đóng phiếu OneOSS 5.1?", "Đáp án: B. Định dạng DUY NHẤT 2 cấp: [Phường/Xã], [Tỉnh/TP] (34 Tỉnh mới)."),
    ("Câu 5: Trong tra cứu SMSC Gateway CDR, mã trạng thái Mã 0 nghĩa là gì?", "Đáp án: A. Tin nhắn đã phát thành công đến thiết bị/SIM của khách hàng.")
]

for idx, (q, a) in enumerate(quizzes):
    top = PptInches(1.4 + idx * 1.1)
    add_card(s23, PptInches(0.8), top, PptInches(11.7), PptInches(0.95))
    tb = s23.shapes.add_textbox(PptInches(1.1), top + PptInches(0.08), PptInches(11.1), PptInches(0.8))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = q
    p.font.name = "Segoe UI"
    p.font.bold = True
    p.font.size = PptPt(10.5)
    p.font.color.rgb = PPT_NAVY
    p = tf.add_paragraph()
    p.text = a
    p.font.name = "Segoe UI"
    p.font.size = PptPt(9.5)
    p.font.color.rgb = PPT_SUCCESS
    p.space_before = PptPt(2)

# -------------------------------------------------------------
# SLIDE 24: TỔNG KẾT & THÔNG ĐIỆP KHÓA HỌC
# -------------------------------------------------------------
s24 = prs.slides.add_slide(blank_layout)
bg24 = s24.shapes.add_shape(MSO_SHAPE.RECTANGLE, PptInches(0), PptInches(0), PptInches(13.333), PptInches(7.5))
bg24.fill.solid()
bg24.fill.fore_color.rgb = PPT_NAVY
bg24.line.fill.background()

tb24 = s24.shapes.add_textbox(PptInches(1.2), PptInches(1.6), PptInches(10.9), PptInches(4.5))
tf24 = tb24.text_frame
tf24.word_wrap = True

p = tf24.paragraphs[0]
p.text = "TỔNG KẾT KHÓA ĐÀO TẠO 5 TIẾNG"
p.font.name = "Segoe UI"
p.font.bold = True
p.font.size = PptPt(14)
p.font.color.rgb = PPT_CYAN

p = tf24.add_paragraph()
p.text = "CHÚC CÁC ĐỒNG CHÍ KTV VẬN HÀNH THÀNH CÔNG VÀ CHÍNH XÁC!"
p.font.name = "Segoe UI"
p.font.size = PptPt(26)
p.font.bold = True
p.font.color.rgb = PPT_WHITE
p.space_before = PptPt(14)

p = tf24.add_paragraph()
p.text = (
    "1. Dữ liệu là chân lý: Luôn nhìn vào log kỹ thuật (Card 2 & Card 3) trước khi đưa ra nhận định.\n"
    "2. Chuẩn hóa địa bàn: 1-Click lấy Phường/Xã từ GPS trạm CEM, tuyệt đối không ghi thôn/ấp hay mã trạm.\n"
    "3. Bảo vệ quyền lợi khách hàng: Gói OCS thiếu ODA_BIG_OCS lập tức chuyển IT/CCBS hỗ trợ.\n"
    "4. Tự động hóa an toàn: Vận hành Auto-Close có kiểm soát, luôn giữ vững tinh thần Human-in-the-Loop."
)
p.font.name = "Segoe UI"
p.font.size = PptPt(12)
p.font.color.rgb = PptRGBColor(226, 232, 240)
p.space_before = PptPt(16)

# Lưu PowerPoint
prs.save(OUT_PPTX)
prs.save(OUT_PPTX_ALT)
print(f"✅ Đã tạo thành công Slide PowerPoint 24 Slide tại: {OUT_PPTX}")
print(f"✅ Đã lưu bản sao lưu tại: {OUT_PPTX_ALT}")
