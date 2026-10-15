# -*- coding: utf-8 -*-
"""
Script tạo tài liệu Hướng dẫn sử dụng Hệ thống VNPT TTS PRECHECK định dạng Word (.docx)
PHIÊN BẢN TOÀN DIỆN TẤT CẢ CÁC PHÂN HỆ:
- Mobile Internet (Data)
- Cuộc gọi & Thoại (Voice)
- Chặn gọi ngoại mạng / Chặn Spam (Nghị định 91)
- Tin nhắn (SMS) & Tra cứu SMSC CDR
- CVQT (Roaming) & SIM / eSIM
- Quản trị Phân vùng KTV & Giám sát hệ thống
"""

import os
import sys
from PIL import Image
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

ARTIFACT_DIR = r"C:\Users\lequa\.gemini\antigravity-ide\brain\233538e9-b8ef-4c40-b0c3-e80e1868d2c3"
IMG_DIR = os.path.join(ARTIFACT_DIR, "manual_crops")
os.makedirs(IMG_DIR, exist_ok=True)

# Các ảnh chụp module mới từ browser subagent
IMG_VOICE = os.path.join(ARTIFACT_DIR, "module_cuoc_goi_1791814562393.png")
IMG_SPAM = os.path.join(ARTIFACT_DIR, "module_chan_spam_1791814585623.png")
IMG_SMS = os.path.join(ARTIFACT_DIR, "module_tin_nhan_1791814616208.png")
IMG_SMS_MODAL = os.path.join(ARTIFACT_DIR, "smsc_cdr_modal_1791814637383.png")
IMG_KTV_MGT = os.path.join(ARTIFACT_DIR, "quan_ly_ktv_1791814684329.png")

C_VNPT_BLUE = RGBColor(0, 82, 165)
C_VNPT_ACCENT = RGBColor(2, 132, 199)
C_DARK = RGBColor(15, 23, 42)

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
        run.font.color.rgb = RGBColor(0, 82, 165) # VNPT Blue
        h.paragraph_format.space_before = Pt(16)
        h.paragraph_format.space_after = Pt(6)
    elif level == 2:
        run.font.size = Pt(12.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 102, 204)
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
    elif level == 3:
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = RGBColor(30, 41, 59)
        h.paragraph_format.space_before = Pt(8)
        h.paragraph_format.space_after = Pt(2)
    return h

def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run(text)
    run.font.name = 'Arial'
    run.font.size = Pt(9.5)
    run.font.italic = True
    run.font.color.rgb = RGBColor(100, 116, 139)

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
    elif callout_type == "TIP":
        fill = "F0FDF4"
        border_color = "16A34A"
        title = title_override or "MẸO THAO TÁC NHANH:"
        title_color = RGBColor(22, 101, 52)
    elif callout_type == "WARNING":
        fill = "FEF2F2"
        border_color = "DC2626"
        title = title_override or "CẢNH BÁO / BẮT BUỘC TUÂN THỦ:"
        title_color = RGBColor(185, 28, 28)
    else:
        fill = "F8FAFC"
        border_color = "0284C7"
        title = title_override or "HƯỚNG DẪN THAO TÁC:"
        title_color = RGBColor(3, 105, 161)
        
    set_cell_background(cell, fill)
    set_cell_margins(cell, top=100, bottom=100, left=160, right=160)
    
    tc_pr = cell._element.get_or_add_tcPr()
    borders = parse_xml(f'<w:tcBorders {nsdecls("w")}>'
                        f'<w:top w:val="none"/>'
                        f'<w:left w:val="single" w:sz="24" w:space="0" w:color="{border_color}"/>'
                        f'<w:bottom w:val="none"/>'
                        f'<w:right w:val="none"/>'
                        f'</w:tcBorders>')
    tc_pr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run_title = p.add_run(f"{title}\n")
    run_title.font.name = 'Arial'
    run_title.font.bold = True
    run_title.font.size = Pt(10)
    run_title.font.color.rgb = title_color
    
    run_text = p.add_run(text)
    run_text.font.name = 'Arial'
    run_text.font.size = Pt(9.5)
    run_text.font.color.rgb = RGBColor(15, 23, 42)
    
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

def build_full_manual():
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # --- TRANG BÌA ---
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_header.add_run("TẬP ĐOÀN BƯU CHÍNH VIỄN THÔNG VIỆT NAM (VNPT)\nKHỐI KỸ THUẬT VIỄN THÔNG - TRUNG TÂM ĐIỀU HÀNH MẠNG\n***\n\n")
    r_sub.font.name = 'Arial'
    r_sub.font.size = Pt(11)
    r_sub.font.bold = True
    r_sub.font.color.rgb = RGBColor(0, 82, 165)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(20)
    p_title.paragraph_format.space_after = Pt(10)
    r_title = p_title.add_run("TÀI LIỆU HƯỚNG DẪN SỬ DỤNG TOÀN DIỆN\n")
    r_title.font.name = 'Arial'
    r_title.font.size = Pt(20)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(0, 82, 165)

    r_sys = p_title.add_run("HỆ THỐNG TIỀN KIỂM & XỬ LÝ PHẢN ÁNH KHÁCH HÀNG (VNPT TTS PRECHECK)\n")
    r_sys.font.name = 'Arial'
    r_sys.font.size = Pt(15)
    r_sys.font.bold = True
    r_sys.font.color.rgb = RGBColor(0, 120, 215)

    r_target = p_title.add_run("(HƯỚNG DẪN ĐẦY ĐỦ TẤT CẢ CÁC PHÂN HỆ: DATA, CUỘC GỌI, SPAM, SMS, CVQT, SIM, QUẢN TRỊ KTV)")
    r_target.font.name = 'Arial'
    r_target.font.size = Pt(11)
    r_target.font.bold = True
    r_target.font.color.rgb = RGBColor(220, 38, 38)

    p_desc = doc.add_paragraph()
    p_desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_desc.paragraph_format.space_after = Pt(30)
    r_desc = p_desc.add_run("Cẩm nang chi tiết từng chức năng, nút bấm, kịch bản nghiệp vụ cho Kỹ thuật viên mới tiếp nhận tác nghiệp")
    r_desc.font.name = 'Arial'
    r_desc.font.size = Pt(10.5)
    r_desc.font.italic = True
    r_desc.font.color.rgb = RGBColor(71, 85, 105)

    meta_tbl = doc.add_table(rows=4, cols=2)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    rows_data = [
        ("Mục tiêu tài liệu:", "Hướng dẫn đầy đủ 6 phân hệ nghiệp vụ viễn thông, từng nút bấm và quy trình xử lý phiếu OneOSS."),
        ("Phạm vi áp dụng:", "Toàn thể KTV tác nghiệp 3 Miền (Miền Bắc, Miền Trung, Miền Nam)."),
        ("Địa chỉ WebApp:", "http://10.155.59.158:1234 (Mạng nội bộ VNPT Port 1234)."),
        ("Phiên bản cập nhật:", "Tháng 10/2026 - Chuẩn hóa 34 Tỉnh/TP mới & Quy chuẩn bắt buộc địa bàn Phường/Xã.")
    ]
    for idx, (lbl, val) in enumerate(rows_data):
        c0 = meta_tbl.cell(idx, 0)
        c1 = meta_tbl.cell(idx, 1)
        c0.width = Inches(2.2)
        c1.width = Inches(4.3)
        r0 = c0.paragraphs[0].add_run(lbl)
        r0.font.name = 'Arial'
        r0.font.bold = True
        r0.font.size = Pt(9.5)
        r1 = c1.paragraphs[0].add_run(val)
        r1.font.name = 'Arial'
        r1.font.size = Pt(9.5)
        set_cell_background(c0, "F0F4F8")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, top=50, bottom=50, left=80, right=80)
        set_cell_margins(c1, top=50, bottom=50, left=80, right=80)

    doc.add_page_break()

    # --- CHƯƠNG 1: TỔNG QUAN HỆ THỐNG VÀ 6 PHÂN HỆ NGHIỆP VỤ ---
    add_styled_heading(doc, "1. TỔNG QUAN HỆ THỐNG VÀ 6 PHÂN HỆ NGHIỆP VỤ", level=1)
    
    p = doc.add_paragraph()
    r = p.add_run(
        "Hệ thống VNPT TTS PRECHECK tích hợp đồng bộ 6 phân hệ nghiệp vụ viễn thông cốt lõi, "
        "giúp KTV xử lý toàn bộ các phản ánh kỹ thuật trên cùng một nền tảng duy nhất mà không cần mở nhiều phần mềm rời rạc:"
    )
    r.font.name = 'Arial'
    r.font.size = Pt(10)

    p_side = os.path.join(IMG_DIR, "ui_sidebar.png")
    if os.path.exists(p_side):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(p_side, width=Inches(3.4))
        add_caption(doc, "Hình 1.1: Danh mục 6 phân hệ nghiệp vụ trên Sidebar bên trái")

    tbl_modules = doc.add_table(rows=7, cols=3)
    tbl_modules.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, title in enumerate(["STT / Phân hệ", "Loại phản ánh tiếp nhận", "Tính năng tự động hóa chính"]):
        c = tbl_modules.cell(0, i)
        set_cell_background(c, "0052A5")
        r = c.paragraphs[0].add_run(title)
        r.font.name = 'Arial'
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(9.5)

    mod_data = [
        ("1. Mobile Internet (Data)", "Mạng chậm, mất mạng, lỗi app (My VNPT, YouTube, TikTok), hết data.", 
         "Check Core SAPC gói cước, BTools lưu lượng phiên 4G/5G, Sóng trạm CEM, bóp băng thông, đối soát ODA_BIG_OCS."),
        ("2. Cuộc gọi & Thoại", "Rớt cuộc gọi, không gọi đi/đến được, lỗi VoLTE/VoWiFi, sóng chập chờn.", 
         "Kiểm tra HLR/VLR, hồ sơ HSS Profile, cờ khóa cước NAM (0 Mở, 1 Khóa), đối soát trạm phục vụ thoại."),
        ("3. Chặn gọi ngoại mạng / Spam", "Thuê bao bị Viettel, MobiFone... chặn liên mạng do nghi ngờ phát tán cuộc gọi rác.", 
         "Thống kê sản lượng gọi bất thường, tra cứu biên bản cam kết mở mạng trên CCOS, gợi ý mở chặn theo NĐ 91."),
        ("4. Tin nhắn (SMS) & SMSC CDR", "Không nhận được OTP ngân hàng, tin nhắn Brandname, chậm SMS.", 
         "Tra cứu nhật ký phân phát SMSC Gateway thời gian thực, đọc mã lỗi gửi tin, đối soát số trung tâm SMSC."),
        ("5. CVQT (Roaming) & SIM / eSIM", "Khách đi nước ngoài không có sóng, lỗi đổi sim 4G, kích hoạt eSIM.", 
         "Kiểm tra gói cước CVQT, profile SIM/eSIM trên Core, hỗ trợ KTV kiểm tra quyền roaming quốc tế."),
        ("6. Quản trị Phân vùng KTV", "Cấu hình tài khoản KTV 3 Miền (MB, MT, MN), kết nối TTS.", 
         "Phân quyền KTV theo Miền, cấu hình mô hình AI phân loại, giám sát nhật ký Live Log hệ thống.")
    ]
    for r_idx, (m_name, m_prob, m_auto) in enumerate(mod_data, start=1):
        for c_idx, val in enumerate([m_name, m_prob, m_auto]):
            cell = tbl_modules.cell(r_idx, c_idx)
            set_cell_background(cell, "F8FAFC" if r_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            r = cell.paragraphs[0].add_run(val)
            r.font.name = 'Arial'
            r.font.size = Pt(9)
            if c_idx == 0:
                r.font.bold = True

    doc.add_page_break()

    # --- CHƯƠNG 2: PHÂN HỆ MOBILE INTERNET (DATA) ---
    add_styled_heading(doc, "2. HƯỚNG DẪN PHÂN HỆ MOBILE INTERNET (DATA)", level=1)
    
    p = doc.add_paragraph()
    r = p.add_run(
        "Phân hệ Mobile Internet là phân hệ chiếm sản lượng phiếu lớn nhất. "
        "Khi bấm vào hàng phiếu mở rộng, KTV sẽ làm việc với 3 THẺ CHI TIẾT:"
    )
    r.font.name = 'Arial'
    r.font.size = Pt(10)

    p_exp = os.path.join(IMG_DIR, "ui_expanded_all.png")
    if os.path.exists(p_exp):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(p_exp, width=Inches(6.5))
        add_caption(doc, "Hình 2.1: Ba thẻ chi tiết khi xử lý phiếu Mobile Internet")

    add_styled_heading(doc, "2.1. Đọc hiểu 3 Thẻ chi tiết Mobile Internet", level=2)
    p = doc.add_paragraph()
    r = p.add_run(
        "• THẺ 1 (Tóm tắt AI): Bóc tách 6 thông tin chính: Gói cước khách báo (VD120N, D159SC...), lỗi cụ thể, dung lượng báo còn, thiết bị (iPhone, Samsung...), khu vực lỗi và địa chỉ Phường/Xã.\n"
        "• THẺ 2 (Profile SAPC & CEM - Đã bọc dòng wrapped text): Hiển thị sóng Radio (4G/5G), trạm BTS, cờ khóa cước NAM (0 Mở, 1 Khóa nợ cước), lưu lượng BTools và tỷ lệ trạm CEM 5 ngày gần nhất. Giao diện đã khóa cuộn ngang, chữ tự xuống dòng gọn gàng.\n"
        "• THẺ 3 (Ý kiến KTV & Thao tác): Report bot tự động sinh kết luận kỹ thuật, gợi ý mã lỗi OneOSS trong ô combobox và cụm 3 nút thao tác: 'Chuyển 2.6', 'Đóng 5.1' và 'Mở TTS'."
    )
    r.font.name = 'Arial'
    r.font.size = Pt(9.5)

    add_callout(doc,
        "ĐỐI VỚI CÁC GÓI CƯỚC OCS (D159SC, VD120N, YOLO90, BIG60...):\n"
        "• Trên Core SAPC bắt buộc phải có profile data chính: ODA_BIG_OCS.\n"
        "• Nếu khách báo dùng gói D159SC (còn 6GB) nhưng SAPC chỉ có ODA_MYTV mà thiếu ODA_BIG_OCS:\n"
        "  -> Đây là lỗi rớt profile cước!\n"
        "  -> Hướng xử lý bắt buộc: 'Chuyển IT/CCBS kiểm tra khai báo gói cước {tên gói} cho Khách hàng'. Tuyệt đối không tư vấn khách mua gói mới!",
        callout_type="WARNING", title_override="QUY TẮC BẮT BUỘC ĐỐI VỚI GÓI OCS (ODA_BIG_OCS):")

    doc.add_page_break()

    # --- CHƯƠNG 3: PHÂN HỆ CUỘC GỌI & THOẠI (VOICE CALLS) ---
    add_styled_heading(doc, "3. HƯỚNG DẪN PHÂN HỆ CUỘC GỌI & THOẠI (VOICE CALLS)", level=1)

    if os.path.exists(IMG_VOICE):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(IMG_VOICE, width=Inches(6.5))
        add_caption(doc, "Hình 3.1: Giao diện danh sách phiếu phân hệ Cuộc gọi")

    p = doc.add_paragraph()
    r = p.add_run(
        "Phân hệ Cuộc gọi xử lý các phản ánh của khách hàng về dịch vụ thoại di động. "
        "Giao diện phân hệ thoại được tối ưu riêng biệt cho nghiệp vụ thoại:"
    )
    r.font.name = 'Arial'
    r.font.size = Pt(10)

    voice_items = [
        ("1. Kiểm tra Cờ Khóa Dịch Vụ Thoại (NAM):", 
         "Hệ thống tự động hiển thị nhãn: 'NAM: 0 (MỞ DỊCH VỤ)' màu xanh lá hoặc 'NAM: 1 (KHÓA DỊCH VỤ)' màu đỏ cảnh báo. Nếu NAM: 1 nghĩa là thuê bao đang bị khóa 1 chiều hoặc 2 chiều do cước."),
        ("2. Kiểm tra HSS Profile & Dịch vụ VoLTE:", 
         "Hiển thị thông số HSS Profile (ví dụ HSS: 67). Nếu hiển thị '⚠️ HSS: ... (PROFILE LẠ)' cảnh báo thuê bao chưa được khai báo dịch vụ VoLTE/thoại chuẩn trên Core mạng."),
        ("3. Tự động loại bỏ thông tin Data không liên quan:", 
         "Trong phân hệ Cuộc gọi, hệ thống tự động ẩn bỏ các khối dữ liệu BTools lưu lượng 4G không cần thiết, giúp màn hình gọn gàng và KTV tập trung vào trạm BTS phục vụ thoại."),
        ("4. Quy trình xử lý phiếu thoại bước 2.3 & 2.4:", 
         "Nếu phiếu đang ở bước tiếp nhận ban đầu (2.3/2.4), KTV kiểm tra trạm phát sóng và cờ NAM. Nếu không có sự cố trạm, KTV bấm nút 'Chuyển 2.4' hoặc 'Chuyển 2.6' để chuyển bước tiếp theo.")
    ]
    for lbl, val in voice_items:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        run_l = p.add_run(f"{lbl}\n")
        run_l.font.name = 'Arial'
        run_l.font.bold = True
        run_l.font.size = Pt(10)
        run_l.font.color.rgb = C_VNPT_BLUE
        run_v = p.add_run(val)
        run_v.font.name = 'Arial'
        run_v.font.size = Pt(9.5)

    doc.add_page_break()

    # --- CHƯƠNG 4: PHÂN HỆ CHẶN GỌI NGOẠI MẠNG / CHẶN SPAM (NGHỊ ĐỊNH 91) ---
    add_styled_heading(doc, "4. HƯỚNG DẪN PHÂN HỆ CHẶN GỌI NGOẠI MẠNG / CHẶN SPAM", level=1)

    if os.path.exists(IMG_SPAM):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(IMG_SPAM, width=Inches(6.5))
        add_caption(doc, "Hình 4.1: Chi tiết phiếu phản ánh Chặn spam với ô Nhà mạng bị chặn & Biên bản cam kết CCOS")

    p = doc.add_paragraph()
    r = p.add_run(
        "Nghiệp vụ Chặn gọi ngoại mạng xử lý các khiếu nại của khách hàng khi thuê bao VinaPhone gọi sang mạng khác "
        "(Viettel, MobiFone, Vietnamobile...) thì bị báo chặn, không kết nối được theo Nghị định 91 về chống cuộc gọi rác. "
        "Hệ thống cung cấp thẻ kiểm soát đặc thù:"
    )
    r.font.name = 'Arial'
    r.font.size = Pt(10)

    add_styled_heading(doc, "4.1. Đọc hiểu Thẻ 'THÔNG TIN THUÊ BAO & NHÀ MẠNG BỊ CHẶN'", level=2)
    p = doc.add_paragraph()
    r = p.add_run(
        "• Nhà mạng ảnh hưởng: Hệ thống tự động phân tích và gắn huy hiệu nhà mạng bị chặn (VD: Viettel, MobiFone...). "
        "Giúp KTV biết chính xác thuê bao đang bị nhà mạng nào chặn liên mạng.\n"
        "• Số thuê bao VinaPhone & Thời điểm tiếp nhận: Số điện thoại khách và thời gian nhận phản ánh.\n"
        "• Nguồn thông tin cam kết: Báo cáo xem thuê bao đã nộp bản cam kết hay chưa qua hệ thống CCOS."
    )
    r.font.name = 'Arial'
    r.font.size = Pt(9.5)

    add_styled_heading(doc, "4.2. Khuyến nghị xử lý KTV dựa vào Bản Cam Kết CCOS", level=2)
    
    tbl_spam = doc.add_table(rows=3, cols=2)
    tbl_spam.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, title in enumerate(["Trường hợp cam kết CCOS", "Hướng xử lý chuẩn của KTV"]):
        c = tbl_spam.cell(0, i)
        set_cell_background(c, "0052A5")
        r = c.paragraphs[0].add_run(title)
        r.font.name = 'Arial'
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(9.5)

    spam_rows = [
        ("TRƯỜNG HỢP 1:\nĐÃ CÓ BẢN CAM KẾT\n(Huy hiệu xanh lá)", 
         "Hệ thống phát hiện thuê bao đã có biên bản cam kết mở mạng đính kèm trên CCOS. KTV kiểm tra đối soát, chọn phương án 'Đã có bản cam kết, chuyển KTV kiểm tra mở chặn' và phối hợp điều phối mở chặn liên mạng."),
        ("TRƯỜNG HỢP 2:\nCHƯA CÓ BẢN CAM KẾT\n(Huy hiệu đỏ cảnh báo)", 
         "Chưa tìm thấy biên bản cam kết trên CCOS. KTV phản hồi chuyển giao dịch viên yêu cầu khách hàng ra điểm giao dịch ký bản cam kết không phát tán cuộc gọi rác trước khi thực hiện mở chặn.")
    ]
    for r_idx, (t_case, t_sol) in enumerate(spam_rows, start=1):
        c0 = tbl_spam.cell(r_idx, 0)
        c1 = tbl_spam.cell(r_idx, 1)
        set_cell_background(c0, "F8FAFC" if r_idx == 1 else "FEF2F2")
        set_cell_background(c1, "FFFFFF")
        set_cell_margins(c0, top=60, bottom=60, left=80, right=80)
        set_cell_margins(c1, top=60, bottom=60, left=80, right=80)
        r0 = c0.paragraphs[0].add_run(t_case)
        r0.font.name = 'Arial'
        r0.font.bold = True
        r0.font.size = Pt(9.5)
        r1 = c1.paragraphs[0].add_run(t_sol)
        r1.font.name = 'Arial'
        r1.font.size = Pt(9.5)

    doc.add_page_break()

    # --- CHƯƠNG 5: PHÂN HỆ TIN NHẮN (SMS) & TRA CỨU SMSC CDR ---
    add_styled_heading(doc, "5. HƯỚNG DẪN PHÂN HỆ TIN NHẮN (SMS) & TRA CỨU SMSC CDR", level=1)

    if os.path.exists(IMG_SMS):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(IMG_SMS, width=Inches(6.5))
        add_caption(doc, "Hình 5.1: Danh sách phiếu phân hệ Tin nhắn SMS với nút 'Lấy CDR' và 'Tra cứu SMSC CDR'")

    p = doc.add_paragraph()
    r = p.add_run(
        "Phân hệ Tin nhắn phục vụ xử lý các khiếu nại khách hàng không nhận được tin nhắn OTP ngân hàng "
        "(Vietcombank, Techcombank, BIDV...), mã xác thực Zalo, Facebook hoặc tin nhắn Brandname. "
        "Tính năng đột phá nhất của phân hệ này là tích hợp trực tiếp Cổng tra cứu SMSC CDR Gateway:"
    )
    r.font.name = 'Arial'
    r.font.size = Pt(10)

    if os.path.exists(IMG_SMS_MODAL):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(IMG_SMS_MODAL, width=Inches(6.2))
        add_caption(doc, "Hình 5.2: Cửa sổ tra cứu nhật ký gửi tin nhắn SMSC CDR chi tiết")

    add_styled_heading(doc, "5.1. Hai cách tra cứu nhật ký tin nhắn SMSC CDR", level=2)
    p = doc.add_paragraph()
    r = p.add_run(
        "👉 CÁCH 1: BẤM NÚT 'LẤY CDR' TRỰC TIẾP TRÊN HÀNG PHIẾU\n"
        "Trên mỗi hàng phiếu tin nhắn, KTV chỉ cần bấm chuột vào nút 'Lấy CDR' màu xanh nhạt. "
        "Hệ thống sẽ tự động gửi yêu cầu sang SMSC Gateway và hiển thị kết quả đối soát ngay trong ô tóm tắt.\n\n"
        "👉 CÁCH 2: MỞ CỬA SỔ TRA CỨU CHI TIẾT ('TRA CỨU SMSC CDR')\n"
        "Bấm vào nút 'Tra cứu SMSC CDR' ở thanh công cụ hoặc nút 'Chi tiết CDR ↗' trong Thẻ 2. "
        "Cửa sổ tra cứu toàn màn hình sẽ mở ra, cho phép KTV nhập số thuê bao và khoảng ngày cần rà soát."
    )
    r.font.name = 'Arial'
    r.font.size = Pt(9.5)

    add_styled_heading(doc, "5.2. Đọc hiểu kết quả tra cứu SMSC CDR", level=2)
    p = doc.add_paragraph()
    r = p.add_run(
        "• Thời gian gửi tin: Giờ, phút, giây tin nhắn được đẩy vào hệ thống trung tâm SMSC.\n"
        "• Đầu số gửi (Brandname / Shortcode): Số dịch vụ gửi tin (ví dụ: VCB, MBBANK, 155...). Giúp xác định đúng tin nhắn khách đang khiếu nại.\n"
        "• Trạng thái phân phát (Delivery Status):\n"
        "  - Delivered (Thành công): Tin nhắn đã được chuyển thành công tới máy khách hàng.\n"
        "  - Expired / Failed (Lỗi): Tin nhắn không tới được máy khách do máy tắt nguồn, sim đầy bộ nhớ hoặc lỗi mạng.\n"
        "• Mã lỗi (Error Code): Mã lỗi kỹ thuật trả về từ mạng vô tuyến giúp KTV kết luận nguyên nhân chính xác 100%."
    )
    r.font.name = 'Arial'
    r.font.size = Pt(9.5)

    doc.add_page_break()

    # --- CHƯƠNG 6: PHÂN HỆ CVQT (ROAMING) & SIM / ESIM ---
    add_styled_heading(doc, "6. HƯỚNG DẪN PHÂN HỆ CVQT (ROAMING) & SIM / ESIM", level=1)

    p = doc.add_paragraph()
    r = p.add_run(
        "Hỗ trợ KTV giải quyết các khiếu nại chuyên biệt về dịch vụ quốc tế và phôi sim di động:"
    )
    r.font.name = 'Arial'
    r.font.size = Pt(10)

    roam_sim_items = [
        ("1. Phân hệ Chuyển vùng quốc tế (CVQT / Roaming):",
         "• Đối tượng: Khách hàng VinaPhone đi công tác, du lịch nước ngoài phản ánh không có sóng hoặc không kết nối được mạng đối tác.\n"
         "• Nghiệp vụ tiền kiểm: Kiểm tra trạng thái đăng ký dịch vụ CVQT (IR), gói cước Roaming (R15, R30...), trạng thái mở cước quốc tế trên Core.\n"
         "• Kết luận: Xác định khách chưa đăng ký dịch vụ CVQT, thiết bị chưa bật chế độ Chuyển vùng dữ liệu (Data Roaming) hoặc mạng đối tác bị gián đoạn."),
        ("2. Phân hệ Dịch vụ SIM / MultiSIM / eSIM:",
         "• Đối tượng: Phản ánh lỗi khi nâng cấp SIM 4G, đổi phôi SIM, đăng ký MultiSIM (SIM phụ cho đồng hồ thông minh) hoặc quét mã QR eSIM.\n"
         "• Nghiệp vụ tiền kiểm: Kiểm tra số seri phôi SIM (IMSI, ICCID) trên hệ thống HLR, trạng thái kích hoạt eSIM.\n"
         "• Kết luận: Hướng dẫn giao dịch viên cấp lại mã QR eSIM hoặc hỗ trợ đổi phôi SIM mới nếu phôi SIM vật lý bị suy hao phần cứng.")
    ]
    for lbl, val in roam_sim_items:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        run_l = p.add_run(f"{lbl}\n")
        run_l.font.name = 'Arial'
        run_l.font.bold = True
        run_l.font.size = Pt(10)
        run_l.font.color.rgb = C_VNPT_BLUE
        run_v = p.add_run(val)
        run_v.font.name = 'Arial'
        run_v.font.size = Pt(9.5)

    # --- CHƯƠNG 7: PHÂN HỆ QUẢN TRỊ KTV & CẤU HÌNH PHÂN VÙNG SOC ---
    add_styled_heading(doc, "7. PHÂN HỆ QUẢN TRỊ KTV & CẤU HÌNH PHÂN VÙNG SOC", level=1)

    if os.path.exists(IMG_KTV_MGT):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(IMG_KTV_MGT, width=Inches(6.5))
        add_caption(doc, "Hình 7.1: Giao diện Quản trị KTV, phân quyền Vùng Miền SOC và cấu hình kết nối")

    p = doc.add_paragraph()
    r = p.add_run(
        "Dành cho KTV quản trị và điều hành trung tâm SOC quản lý hệ thống:\n"
        "• Quản lý phiên đăng nhập OneOSS: Cập nhật tài khoản, mật khẩu và token truy cập cho các phân vùng.\n"
        "• Phân chia Vùng Miền tác nghiệp (Regional Scoping): Phân quyền KTV theo từng SOC (Miền Bắc, Miền Nam, Miền Trung).\n"
        "• Cấu hình mô hình AI & Chẩn đoán: Tùy chỉnh danh mục kịch bản, thời gian quét tự động và theo dõi hiệu năng hệ thống."
    )
    r.font.name = 'Arial'
    r.font.size = Pt(9.5)

    doc.add_page_break()

    # --- CHƯƠNG 8: QUY CHUẨN BẮT BUỘC ĐÓNG PHIẾU 5.1 & CẬP NHẬT PHƯỜNG / XÃ ---
    add_styled_heading(doc, "8. QUY CHUẨN BẮT BUỘC KHI ĐÓNG PHIẾU 5.1: CẬP NHẬT PHƯỜNG / XÃ", level=1)

    add_callout(doc, 
        "TẤT CẢ CÁC PHIẾU KHI ĐÓNG 5.1 BẮT BUỘC PHẢI CÓ ĐỊA BÀN CHUẨN ĐÚNG 2 CẤP:\n"
        "Định dạng chuẩn duy nhất: [Phường/Xã/Thị trấn], [Tỉnh/Thành phố]\n"
        "• TUYỆT ĐỐI KHÔNG để trống địa bàn.\n"
        "• TUYỆT ĐỐI KHÔNG lấy cấp thôn, ấp, bản, khóm, tổ dân phố (như Ấp 1, Thôn 3, Tổ 5...).\n"
        "• BẮT BUỘC dùng đúng tên trong danh mục 34 Tỉnh / Thành phố mới sáp nhập.",
        callout_type="WARNING", title_override="QUY CHUẨN BẮT BUỘC TUÂN THỦ (STRICT STANDARD):")

    p_ward = os.path.join(IMG_DIR, "ui_ward_detect.png")
    if os.path.exists(p_ward):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_picture(p_ward, width=Inches(5.0))
        add_caption(doc, "Hình 8.1: Ô nhận diện địa bàn Phường/Xã và Tỉnh/TP trên Thẻ 1")

    p = doc.add_paragraph()
    r = p.add_run(
        "KTV mới chỉ cần thực hiện 1 trong 2 cách cực kỳ đơn giản sau trước khi bấm nút 'Đóng 5.1':\n\n"
        "👉 CÁCH 1 (1 CLICK CHUỘT TỰ ĐỘNG - KHUYÊN DÙNG):\n"
        "Nhìn vào dòng 'Radio:' ở bảng phiếu hoặc Thẻ 2. Nếu trạm BTS có tọa độ GPS, bấm vào NÚT MŨI TÊN XANH (↑) bên cạnh tên trạm. "
        "Hệ thống sẽ tự động lấy kết quả chuẩn từ Google Maps (Port 1708) điền ngay vào ô Phường/Xã của phiếu!\n\n"
        "👉 CÁCH 2 (SỬA TRỰC TIẾP TRÊN Ô TEXT):\n"
        "Nếu khách báo dạng 'ấp lương phú C, xã Hòa Lạc, Tỉnh Đồng Tháp' -> KTV xóa bỏ phần ấp, giữ lại đúng: 'Xã Hòa Lạc, Tỉnh Đồng Tháp'.\n\n"
        "BẢNG 34 TỈNH/TP MỚI & PHÂN BỔ 3 MIỀN:\n"
        "• Miền Bắc (MB - 18 đơn vị): Hà Nội, Hải Phòng, Cao Bằng, Lạng Sơn, Lai Châu, Điện Biên, Sơn La, Quảng Ninh, Tuyên Quang, Lào Cai, Thái Nguyên, Phú Thọ, Bắc Ninh, Hưng Yên, Ninh Bình, Thanh Hóa, Nghệ An, Hà Tĩnh.\n"
        "• Miền Nam (MN - 9 đơn vị): TP. Hồ Chí Minh, TP. Cần Thơ, Lâm Đồng, Đồng Nai, Tây Ninh, Vĩnh Long, Đồng Tháp, Cà Mau, An Giang (gồm Đặc khu Phú Quốc).\n"
        "• Miền Trung (MT - 7 đơn vị): Huế, Đà Nẵng, Quảng Trị, Quảng Ngãi, Gia Lai, Khánh Hòa, Đắk Lắk."
    )
    r.font.name = 'Arial'
    r.font.size = Pt(9.5)

    # --- CHƯƠNG 9: TỔNG KẾT QUY TRÌNH 5 BƯỚC CHO NEWBIE ---
    add_styled_heading(doc, "9. QUY TRÌNH 5 BƯỚC TÁC NGHIỆP TỪ A ĐẾN Z CHO NEWBIE", level=1)

    steps = [
        ("BƯỚC 1: ĐĂNG NHẬP VÀ CHỌN VÙNG MIỀN",
         "1. Mở Chrome truy cập http://10.155.59.158:1234.\n"
         "2. Nhìn góc trên bên trái Header, chọn đúng Miền phụ trách (MB / MN / MT).\n"
         "3. Kiểm tra các đèn trạng thái TTS, SAPC, BTools đều màu xanh lá."),

        ("BƯỚC 2: CHỌN PHÂN HỆ VÀ TẢI PHIẾU MỚI",
         "1. Chọn phân hệ trên Sidebar: Mobile Internet, Cuộc gọi, Chặn spam, hoặc Tin nhắn.\n"
         "2. Bấm vào tab 'Cần xử lý', bấm nút 'Làm mới' để tải toàn bộ phiếu OneOSS mới nhất về.\n"
         "3. Tất cả KTV cùng Miền sẽ dùng chung dữ liệu an toàn."),

        ("BƯỚC 3: MỞ XEM CHI TIẾT VÀ TIỀN KIỂM",
         "1. Bấm chuột vào hàng phiếu cần xử lý để mở ngăn kéo 3 Thẻ.\n"
         "2. Bấm nút '⚡ Tiền kiểm' (hoặc 'Lấy CDR' với tin nhắn) để cập nhật dữ liệu mạng mới nhất.\n"
         "3. Đọc Thẻ 1 (khách báo gì) và Thẻ 2 (mạng thực tế ra sao)."),

        ("BƯỚC 4: KIỂM TRA Ý KIẾN KTV VÀ CHỌN NGUYÊN NHÂN",
         "1. Nhìn sang Thẻ 3, kiểm tra ô 'Ý kiến KTV' và 'Nội dung phản hồi' (bot đã sinh sẵn).\n"
         "2. Kiểm tra ô combobox 'Nguyên nhân sự cố' trong 73 mã lỗi OneOSS.\n"
         "3. Lưu ý ca đặc thù: Gói OCS thiếu ODA_BIG_OCS -> Hướng xử lý: 'Chuyển IT/CCBS kiểm tra khai báo gói cước {tên gói} cho Khách hàng'."),

        ("BƯỚC 5: CHUẨN HÓA ĐỊA BÀN VÀ BẤM NÚT ĐÓNG PHIẾU",
         "1. Kiểm tra địa bàn đã đúng 2 cấp [Phường/Xã], [Tỉnh/TP] (bấm nút mũi tên xanh ↑).\n"
         "2. Bấm nút 'Đóng 5.1' (hoặc nút 'Chuyển 2.6' nếu muốn chuyển bước kỹ thuật theo dõi tiếp).\n"
         "3. Thông báo thành công màu xanh lá -> Phiếu hoàn tất và chuyển sang tab 'Đã đóng'!")
    ]

    for s_title, s_content in steps:
        add_callout(doc, s_content, callout_type="TIP", title_override=s_title)

    p_end = doc.add_paragraph()
    p_end.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_end.paragraph_format.space_before = Pt(25)
    r_end = p_end.add_run("--- CHÚC CÁC ANH EM KỸ THUẬT VIÊN TÁC NGHIỆP HIỆU QUẢ VÀ CHÍNH XÁC! ---")
    r_end.font.name = 'Arial'
    r_end.font.bold = True
    r_end.font.size = Pt(11)
    r_end.font.color.rgb = RGBColor(0, 82, 165)

    output_path = r"c:\Users\lequa\OneDrive - VNPT\python\PAKH_PRECHECK\HUONG_DAN_SU_DUNG_HE_THONG_VNPT_TTS_PRECHECK.docx"
    doc.save(output_path)
    print("SUCCESS: File Word TOAN DIEN da duoc tao thanh cong tai:", output_path)

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    build_full_manual()
