# -*- coding: utf-8 -*-
"""
Generate complete, professional VNPT PRECHECK document based on official template,
incorporating:
- CORE FOCUS: Full end-to-end automation of MOBILE INTERNET tickets (accounting for >80% data traffic & 75%-80% ticket volume).
- SUPPORT & PRECHECK ROLE: Centralized collection, rapid precheck, and 1-click decision support for Other Ticket Categories (Thoại, SMS, Gói cước...).
- FUTURE ROADMAP: Expanding automated rule-based engines for Voice (VoLTE/VoWiFi), SMS, and VAS/Billing.
- Full REST API support on both TTS Cũ and TTS Mới (no UI automation complexity).
- Precheck and Direct Ticket Closing right on Dashboard.
- Concrete quantification: Auto-close up to 85% - 90% of Mobile Internet tickets based on 25 scenarios.
- High-res illustrative screenshots with standard captions.
"""
import sys, os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def set_run_font(run, font_name="Times New Roman", size_pt=13, bold=False, italic=False, color_rgb=None):
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    if color_rgb:
        run.font.color.rgb = color_rgb
    rPr = run._r.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)
    rFonts.set(qn('w:eastAsia'), font_name)
    rPr.append(rFonts)

def format_para(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=3, line_spacing=1.2, first_line_indent=0.39):
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    if first_line_indent > 0:
        p.paragraph_format.first_line_indent = Inches(first_line_indent)
    else:
        p.paragraph_format.first_line_indent = Inches(0)

def add_p(doc, text="", bold=False, italic=False, font_size=13, 
          align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=3, 
          line_spacing=1.2, first_line_indent=0.39, bullet=False):
    p = doc.add_paragraph()
    if bullet:
        format_para(p, align=align, space_before=space_before, space_after=space_after, line_spacing=line_spacing, first_line_indent=0)
        p.paragraph_format.left_indent = Inches(0.35)
        p.paragraph_format.first_line_indent = Inches(-0.2)
    else:
        format_para(p, align=align, space_before=space_before, space_after=space_after, line_spacing=line_spacing, first_line_indent=first_line_indent)
    
    run = p.add_run(text)
    set_run_font(run, font_name="Times New Roman", size_pt=font_size, bold=bold, italic=italic)
    return p

def add_heading_section(doc, text):
    p = doc.add_paragraph()
    format_para(p, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=8, space_after=4, line_spacing=1.2, first_line_indent=0)
    run = p.add_run(text)
    set_run_font(run, font_name="Times New Roman", size_pt=13.5, bold=True, italic=False)
    return p

def add_subheading(doc, text):
    p = doc.add_paragraph()
    format_para(p, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=6, space_after=3, line_spacing=1.2, first_line_indent=0)
    run = p.add_run(text)
    set_run_font(run, font_name="Times New Roman", size_pt=13, bold=True, italic=False)
    return p

def add_picture_with_caption(doc, img_path, caption_text, width_inches=6.0, space_before=6, space_after=8):
    if not os.path.exists(img_path):
        for sub in ("docs", "static/img", "static"):
            cand = os.path.join(os.path.dirname(__file__), sub, img_path)
            if os.path.exists(cand):
                img_path = cand
                break
    if os.path.exists(img_path):
        p_img = doc.add_paragraph()
        format_para(p_img, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=space_before, space_after=2, line_spacing=1.0, first_line_indent=0)
        r_img = p_img.add_run()
        r_img.add_picture(img_path, width=Inches(width_inches))

        p_cap = doc.add_paragraph()
        format_para(p_cap, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=space_after, line_spacing=1.1, first_line_indent=0)
        r_cap = p_cap.add_run(caption_text)
        set_run_font(r_cap, font_name="Times New Roman", size_pt=11, bold=False, italic=True)
        return p_img, p_cap
    return None, None

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_background(cell, fill_hex):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def set_table_borders(table, color="A0A0A0", sz="4", val="single"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
        f'  <w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
        f'  <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
        f'  <w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
        f'  <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
        f'  <w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>\n'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def build_full_docx():
    doc = docx.Document()

    # Set page size A4 and Margins (Standard VNPT administrative document)
    section = doc.sections[0]
    section.page_width = Inches(8.27)   # 21.0 cm
    section.page_height = Inches(11.69) # 29.7 cm
    section.top_margin = Inches(0.79)    # ~2.0 cm
    section.bottom_margin = Inches(0.79) # ~2.0 cm
    section.left_margin = Inches(0.98)   # ~2.5 cm
    section.right_margin = Inches(0.79)  # ~2.0 cm

    # Page Footer
    footer = section.footer
    p_ft = footer.paragraphs[0]
    format_para(p_ft, align=WD_ALIGN_PARAGRAPH.RIGHT, space_before=0, space_after=0, line_spacing=1.0, first_line_indent=0)
    r_ft = p_ft.add_run("VNPT PRECHECK • Copyright by quangvu@vnpt.vn (Sep.2026)")
    set_run_font(r_ft, font_name="Times New Roman", size_pt=9.5, italic=True, color_rgb=RGBColor(128, 128, 128))

    # 1. Header
    p0 = doc.add_paragraph()
    format_para(p0, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, line_spacing=1.15, first_line_indent=0)
    r0 = p0.add_run("Phụ lục 01. YÊU CẦU CÔNG NHẬN SÁNG KIẾN NĂM 2026")
    set_run_font(r0, font_name="Times New Roman", size_pt=14, bold=True)

    p1 = doc.add_paragraph()
    format_para(p1, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, line_spacing=1.15, first_line_indent=0)
    r1 = p1.add_run("(Đối với Loại sáng kiến không tính được GTLL trực tiếp bằng tiền)")
    set_run_font(r1, font_name="Times New Roman", size_pt=13, italic=True)

    p2 = doc.add_paragraph()
    format_para(p2, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=12, line_spacing=1.15, first_line_indent=0)
    r2 = p2.add_run("(Phụ lục ban hành kèm theo Quyết định số: 2822/QĐ-VNPT-CLG ngày 01/11/2025)")
    set_run_font(r2, font_name="Times New Roman", size_pt=12, italic=True)

    # 2. Kính gửi
    p3 = doc.add_paragraph()
    format_para(p3, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=6, space_after=10, line_spacing=1.15, first_line_indent=0)
    r3 = p3.add_run("Kính gửi: Hội đồng Sáng kiến [Tên Đơn vị công tác - Ví dụ: VNPT Tỉnh/Thành phố]")
    set_run_font(r3, font_name="Times New Roman", size_pt=13.5, bold=True)

    # 3. Thông tin tác giả
    p4 = doc.add_paragraph()
    format_para(p4, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=4, space_after=4, line_spacing=1.15, first_line_indent=0)
    r4 = p4.add_run("Chúng tôi ghi tên dưới đây:")
    set_run_font(r4, font_name="Times New Roman", size_pt=13, bold=True)

    # Bảng tác giả (Table 0)
    table_authors = doc.add_table(rows=3, cols=8)
    table_authors.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table_authors, color="7F7F7F", sz="4")

    headers_t0 = ['TT', 'Họ tên tác giả', 'Nam/Nữ', 'Trình độ chuyên môn', 'Chức vụ, đơn vị công tác', 'Chủ trì\nSK', 'Tỷ lệ đóng góp (%)', 'Ký tên']
    widths_t0 = [Inches(0.4), Inches(1.5), Inches(0.7), Inches(1.1), Inches(1.8), Inches(0.6), Inches(0.8), Inches(0.7)]

    for col_idx, text in enumerate(headers_t0):
        cell = table_authors.cell(0, col_idx)
        cell.width = widths_t0[col_idx]
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        set_cell_background(cell, "F2F2F2")
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cp = cell.paragraphs[0]
        format_para(cp, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0, line_spacing=1.0, first_line_indent=0)
        c_run = cp.add_run(text)
        set_run_font(c_run, font_name="Times New Roman", size_pt=11, bold=True)

    data_r1 = ['1', '[Họ và tên tác giả]', 'Nam', 'Kỹ sư ĐTVT / CNTT', 'Chuyên viên kỹ thuật - [Tên Phòng/Đơn vị]', 'x', '100%', '']
    for col_idx, text in enumerate(data_r1):
        cell = table_authors.cell(1, col_idx)
        cell.width = widths_t0[col_idx]
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cp = cell.paragraphs[0]
        align = WD_ALIGN_PARAGRAPH.CENTER if col_idx in [0, 2, 5, 6, 7] else WD_ALIGN_PARAGRAPH.LEFT
        format_para(cp, align=align, space_before=0, space_after=0, line_spacing=1.0, first_line_indent=0)
        c_run = cp.add_run(text)
        set_run_font(c_run, font_name="Times New Roman", size_pt=11)

    data_r2 = ['2', '...', '', '', '', '', '', '']
    for col_idx, text in enumerate(data_r2):
        cell = table_authors.cell(2, col_idx)
        cell.width = widths_t0[col_idx]
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cp = cell.paragraphs[0]
        align = WD_ALIGN_PARAGRAPH.CENTER if col_idx in [0, 2, 5, 6, 7] else WD_ALIGN_PARAGRAPH.LEFT
        format_para(cp, align=align, space_before=0, space_after=0, line_spacing=1.0, first_line_indent=0)
        c_run = cp.add_run(text)
        set_run_font(c_run, font_name="Times New Roman", size_pt=11)

    p_note1 = doc.add_paragraph()
    format_para(p_note1, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=4, space_after=1, line_spacing=1.1, first_line_indent=0)
    r_n1 = p_note1.add_run("(Tỷ lệ đóng góp của mỗi tác giả trong sáng kiến không dưới 20%;")
    set_run_font(r_n1, font_name="Times New Roman", size_pt=11, italic=True)

    p_note2 = doc.add_paragraph()
    format_para(p_note2, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0, space_after=1, line_spacing=1.1, first_line_indent=0)
    r_n2 = p_note2.add_run("Chủ trì sáng kiến là người có tỷ lệ đóng góp cao nhất cho sáng kiến;")
    set_run_font(r_n2, font_name="Times New Roman", size_pt=11, italic=True)

    p_note3 = doc.add_paragraph()
    format_para(p_note3, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0, space_after=6, line_spacing=1.1, first_line_indent=0)
    r_n3 = p_note3.add_run("Đồng chủ trì sáng kiến là 02 cá nhân có tỷ lệ đóng góp bằng nhau và cao nhất cho sáng kiến.)")
    set_run_font(r_n3, font_name="Times New Roman", size_pt=11, italic=True)

    p_contact = doc.add_paragraph()
    format_para(p_contact, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=2, space_after=3, line_spacing=1.15, first_line_indent=0)
    r_ct = p_contact.add_run("Điện thoại: [Số điện thoại di động]                                  - Email: quangvu@vnpt.vn")
    set_run_font(r_ct, font_name="Times New Roman", size_pt=13)

    p_addr = doc.add_paragraph()
    format_para(p_addr, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0, space_after=4, line_spacing=1.15, first_line_indent=0)
    r_ad = p_addr.add_run("Địa chỉ bưu điện: [Địa chỉ trụ sở đơn vị công tác]")
    set_run_font(r_ad, font_name="Times New Roman", size_pt=13)

    p_basis = doc.add_paragraph()
    format_para(p_basis, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=2, space_after=4, line_spacing=1.15, first_line_indent=0)
    r_bs = p_basis.add_run("Căn cứ Quy định hiện hành của Tập đoàn về hoạt động sáng kiến và đổi mới sáng tạo;")
    set_run_font(r_bs, font_name="Times New Roman", size_pt=13, italic=True)

    p_sk = doc.add_paragraph()
    format_para(p_sk, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=4, space_after=3, line_spacing=1.2, first_line_indent=0)
    r_sk1 = p_sk.add_run("Yêu cầu xét công nhận sáng kiến: ")
    set_run_font(r_sk1, font_name="Times New Roman", size_pt=13, bold=True)
    r_sk2 = p_sk.add_run("“Xây dựng phần mềm VNPT PRECHECK tự động hóa toàn trình quy trình phân tích, chẩn đoán và đóng phiếu phản ánh khách hàng Mobile Internet, kết hợp nền tảng tiền kiểm tra tập trung đa dịch vụ trên mạng di động VNPT”")
    set_run_font(r_sk2, font_name="Times New Roman", size_pt=13, bold=True)

    p_date = doc.add_paragraph()
    format_para(p_date, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=2, space_after=2, line_spacing=1.15, first_line_indent=0)
    r_dt = p_date.add_run("Ngày sáng kiến được áp dụng lần đầu hoặc áp dụng thử: 01/01/2026")
    set_run_font(r_dt, font_name="Times New Roman", size_pt=13)

    p_loc = doc.add_paragraph()
    format_para(p_loc, align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0, space_after=10, line_spacing=1.15, first_line_indent=0)
    r_lc = p_loc.add_run("Địa điểm áp dụng: [Tên Đơn vị công tác - Ví dụ: Phòng Kỹ thuật / Trung tâm Điều hành Mạng / VNPT Tỉnh/Thành phố...]")
    set_run_font(r_lc, font_name="Times New Roman", size_pt=13)

    # 4. MÔ TẢ SÁNG KIẾN
    p_title_desc = doc.add_paragraph()
    format_para(p_title_desc, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=8, line_spacing=1.15, first_line_indent=0)
    r_td = p_title_desc.add_run("MÔ TẢ SÁNG KIẾN")
    set_run_font(r_td, font_name="Times New Roman", size_pt=14, bold=True)

    # ==================== PHẦN I ====================
    add_heading_section(doc, "I. Lý do đề xuất sáng kiến:")
    
    add_subheading(doc, "1. Bối cảnh chuyển dịch số và tỷ trọng áp đảo của dịch vụ Mobile Internet:")
    add_p(doc, "Trong kỷ nguyên số hóa và sự phổ cập toàn diện của điện thoại thông minh (smartphone), cơ cấu sử dụng dịch vụ viễn thông di động của khách hàng VinaPhone đã có sự dịch chuyển căn bản và triệt để:")
    add_p(doc, "• Tỷ trọng lưu lượng Mobile Internet chiếm ưu thế tuyệt đối: Nhu cầu liên lạc, làm việc trực tuyến, giải trí (video streaming, mạng xã hội, OTT, thanh toán số) đã khiến lưu lượng Data (3G/4G/5G) hiện nay chiếm tới hơn 80% - 85% tổng lưu lượng phục vụ trên toàn bộ mạng lưới viễn thông di động của Tập đoàn, vượt trội hoàn toàn so với dịch vụ thoại và tin nhắn SMS truyền thống;", bullet=True)
    add_p(doc, "• Tỷ trọng phiếu phản ánh sự cố tập trung chủ yếu vào Data: Thống kê thực tế trên Hệ thống Quản lý sự cố (TTS - Trouble Ticket System) cho thấy, số lượng phiếu Phản ánh khách hàng (PAKH) về Mobile Internet chiếm tỷ lệ áp đảo từ 75% đến 80% tổng số phiếu phát sinh hàng ngày (phản ánh mạng chậm, mất kết nối 4G/5G, rớt mạng, không truy cập được ứng dụng, hết dung lượng gói cước...). Các nhóm phản ánh còn lại như Thoại (thoại chập chờn, không gọi được), Tin nhắn SMS (chậm nhận mã OTP, chặn tin rác) và Gói cước/Cước phí chỉ chiếm khoảng 20% - 25%;", bullet=True)
    add_p(doc, "• Tính phức tạp kỹ thuật đa tầng của dịch vụ Mobile Internet: Khác với dịch vụ thoại cơ bản, sự cố Data có nguyên nhân vô cùng đa dạng, nằm rải rác trên nhiều phân hệ kỹ thuật: từ hạ tầng sóng vô tuyến (Radio 3G/4G/5G, suy hao trạm phát sóng BTS), cấu hình hồ sơ thuê bao Core (HSS Profile, trạng thái cờ NAM mở/khóa GPRS, địa chỉ IP WAN), chính sách cước động (SAPC quản lý chu kỳ, quota dung lượng, bóp/hạ băng thông throttling), cho đến nhật ký phiên truyền dữ liệu (BTools) và các ứng dụng mạng riêng ảo (VPN / 1.1.1.1) trên máy khách hàng.", bullet=True)

    add_subheading(doc, "2. Thực trạng và những điểm nghẽn nghiêm trọng trong quy trình xử lý thủ công trước đây:")
    add_p(doc, "Trước khi sáng kiến được triển khai, công tác xử lý phiếu PAKH tại đơn vị hoàn toàn thực hiện theo phương thức thủ công, đối mặt với những khó khăn mang tính cố hữu:")
    add_p(doc, "Thứ nhất, phân tán dữ liệu và hao phí thời gian cực lớn trên mỗi phiếu Data:", bold=True)
    add_p(doc, "Để kiểm tra một phiếu phản ánh Mobile Internet, nhân viên kỹ thuật (ĐTV/KTV) phải đăng nhập và tra cứu rời rạc trên 4 đến 5 hệ thống phần mềm chuyên biệt: mở hệ thống TTS (Cũ hoặc Mới) lấy nội dung; đăng nhập Trang Hồ sơ thuê bao & SAPC kiểm tra công nghệ sóng, gói cước, quota và cờ khóa cước NAM; mở hệ thống CEM phân tích tỷ lệ Cell bắt sóng và nhật ký ứng dụng App Usage; truy cập BTools kiểm tra lịch sử các phiên kết nối dữ liệu (throughput, QoS). Trung bình mỗi phiếu Data mất từ 5 đến 10 phút thao tác copy-paste và đối soát bằng mắt, làm giới hạn nghiêm trọng năng suất lao động của ca trực.")
    
    add_p(doc, "Thứ hai, nguy cơ trễ hạn cam kết chất lượng dịch vụ (SLA/KPI):", bold=True)
    add_p(doc, "Do 75% - 80% phiếu dồn vào Mobile Internet, vào các khung giờ cao điểm hoặc sự cố diện rộng, lượng phiếu Data ùn tắc nghiêm trọng. KTV không đủ thời gian vừa tra cứu kỹ thuật vừa nhập liệu hàng loạt biểu mẫu đóng phiếu phức tạp, dẫn đến nguy cơ vi phạm thời gian cam kết đóng phiếu theo KPI của Tập đoàn.")

    add_p(doc, "Thứ ba, sự thiếu nhất quán và dễ sai sót do nhận định cảm tính:", bold=True)
    add_p(doc, "Việc đọc log kỹ thuật phức tạp phụ thuộc vào kinh nghiệm chủ quan của từng cá nhân. Nhiều trường hợp nhầm lẫn giữa việc thuê bao hết dung lượng data tốc độ cao bị hạ băng thông với sự cố trạm phát sóng BTS, hoặc chưa nhận biết được khách hàng đang bật ứng dụng VPN dẫn đến kết luận chưa thỏa đáng.")

    add_p(doc, "Thứ tư, thiếu một công cụ hỗ trợ tập trung cho các loại phản ánh khác:", bold=True)
    add_p(doc, "Các phản ánh về Dịch vụ Thoại, SMS, Gói cước tuy chiếm tỷ trọng nhỏ hơn (20% - 25%) nhưng nằm rải rác trên các chuyên mục khác nhau của TTS, KTV vẫn phải mở nhiều tab riêng biệt để kiểm tra thủ công, chưa có một giao diện hợp nhất (Single Pane of Glass) để tiền kiểm tra nhanh hồ sơ thuê bao và hỗ trợ xử lý đóng phiếu nhanh.")

    add_subheading(doc, "3. Tính cấp thiết và Định hướng tiếp cận đột phá của sáng kiến:")
    add_p(doc, "Từ thực tiễn trên, nhóm tác giả xác định phương án giải quyết dứt điểm điểm nghẽn lớn nhất: Tập trung nguồn lực xây dựng giải pháp “TỰ ĐỘNG HÓA TOÀN TRÌNH” cho nhóm phiếu Mobile Internet (từ khâu quét dữ liệu, phân tích chẩn đoán đến đóng phiếu tự động qua REST API); đồng thời xây dựng nền tảng “TIỀN KIỂM TRA TẬP TRUNG & HỖ TRỢ XỬ LÝ” cho toàn bộ các loại phiếu còn lại (Thoại, SMS, Gói cước...), tạo tiền đề mở rộng tự động hóa sâu cho các dịch vụ này trong các giai đoạn tiếp theo.")

    # ==================== PHẦN II ====================
    add_heading_section(doc, "II. Mục tiêu của sáng kiến:")
    add_p(doc, "Sáng kiến được triển khai nhằm đạt được các mục tiêu trọng tâm, phân định rõ ràng giữa phân hệ cốt lõi và lộ trình phát triển:")
    add_p(doc, "1. Trọng tâm chiến lược - Tự động hóa toàn trình phân tích, chẩn đoán và đóng phiếu Mobile Internet:", bold=True)
    add_p(doc, "• Xây dựng quy trình tự động hóa khép kín (End-to-End Automation) cho dịch vụ Mobile Internet: Tự động thu thập đa nguồn (Core HSS, SAPC, BTools, CEM) -> Tự động chạy Động cơ chẩn đoán 25 kịch bản -> Tự động đưa ra kết luận kỹ thuật chuẩn hóa -> Tự động đóng phiếu trực tiếp lên hệ thống TTS qua giao thức REST API;", bullet=True)
    add_p(doc, "• Đạt tỷ lệ tự động kiểm tra và đóng phiếu Mobile Internet vượt trội từ 85% đến 90%: Căn cứ vào 20 kịch bản chuẩn đủ điều kiện đóng tự động, hệ thống tự động hoàn tất và đóng phiếu trực tiếp ngầm qua REST API mà không cần con người can thiệp thủ công;", bullet=True)
    add_p(doc, "• Rút ngắn thời gian xử lý phiếu Data từ 5 - 10 phút xuống còn 10 - 15 giây/phiếu (tiết kiệm hơn 95% thời gian thao tác).", bullet=True)
    
    add_p(doc, "2. Nền tảng tiền kiểm tra kỹ thuật tập trung và hỗ trợ xử lý cho các loại phản ánh khác (Thoại, SMS, Gói cước...):", bold=True)
    add_p(doc, "• Thu thập toàn bộ các phiếu sự cố phi-data (Thoại, SMS, Gói cước, Cước phí, Vùng phủ sóng...) về Dashboard tập trung tại phân hệ riêng biệt (Voice/SMS);", bullet=True)
    add_p(doc, "• Tự động tiền kiểm tra ngay hồ sơ kỹ thuật thuê bao: trạng thái dịch vụ, công nghệ sóng (2G/3G/4G/5G), cờ khóa chặn NAM, thông tin trạm Cell phục vụ, cung cấp dữ liệu tức thì hỗ trợ KTV ra quyết định;", bullet=True)
    add_p(doc, "• Hỗ trợ KTV đóng phiếu hoặc chuyển điều phối kỹ thuật địa bàn trực tiếp trên Dashboard chỉ với 1 cú nhấp chuột (1-Click Safe Action), tự động điền sẵn các trường thông tin quy chuẩn lên hệ thống TTS.", bullet=True)

    add_p(doc, "3. Lộ trình mở rộng trong tương lai:", bold=True)
    add_p(doc, "• Kế thừa nền tảng kiến trúc mở và kết nối dữ liệu đã thiết lập, tiếp tục nghiên cứu, xây dựng các bộ kịch bản chẩn đoán chuyên sâu để tự động hóa toàn trình cho dịch vụ Thoại (VoLTE/VoWiFi/CSFB), Tin nhắn SMS (Brandname/OTP), tiến tới tự động hóa 100% mọi loại hình PAKH di động.", bullet=True)

    add_p(doc, "4. Tương thích toàn diện hai thế hệ TTS Cũ và TTS Mới qua REST API:", bold=True)
    add_p(doc, "• Giao tiếp trực tiếp với cả máy chủ TTS Cũ (tts.vnpt.vn) và TTS Mới (tts.vnptnet.vn) thông qua REST API tốc độ cao, xử lý ngầm hoàn toàn không phụ thuộc giao diện web hay chiếm chuột/màn hình của nhân viên.", bullet=True)

    add_p(doc, "5. Đảm bảo an toàn thông tin và nâng cao chỉ số KPI:", bold=True)
    add_p(doc, "• Triển khai cơ chế cô lập phiên làm việc trong mạng LAN (LAN Token Isolation) bảo vệ tài khoản nhân viên; duy trì tỷ lệ đóng phiếu đúng hạn đạt trên 98% - 99%; tự động xuất báo cáo Excel 12 cột chuẩn hóa quy chuẩn VNPT.", bullet=True)

    # ==================== PHẦN III ====================
    add_heading_section(doc, "III. Nội dung sáng kiến:")
    add_p(doc, "Phần mềm VNPT PRECHECK được thiết kế bài bản theo mô hình hiện đại, phân định rõ ràng giữa phân hệ Tự động hóa toàn trình Mobile Internet và phân hệ Tiền kiểm tra hỗ trợ các loại phản ánh khác:")

    add_subheading(doc, "1. Kiến trúc tổng thể và tích hợp REST API đa hệ thống (TTS Cũ & Mới):")
    add_p(doc, "Hệ thống được phát triển theo mô hình kiến trúc phân tầng độc lập (Modular Layered Architecture), đảm bảo khả năng mở rộng không giới hạn:")
    add_p(doc, "• Tầng Giao diện người dùng (Presentation Layer): Web Dashboard trực quan, hiển thị Live Log thời gian thực, tách biệt rành mạch giữa nhóm Mobile Internet (Data) và Thoại/SMS/Gói/PA Khác (Voice), bộ lọc đa tiêu chí, hỗ trợ chế độ Dark Mode / Light Mode;", bullet=True)
    add_p(doc, "• Tầng Dịch vụ & Điều phối luồng (Service & Orchestration Layer): Sử dụng máy chủ đa luồng ThreadingHTTPServer trên nền Python kết hợp mô hình Singleton AutomationState quản lý an toàn đa luồng. Luồng worker chạy ngầm định kỳ kích hoạt chu kỳ quét tự động và hỗ trợ can thiệp tức thời (Run Now / Stop);", bullet=True)
    add_p(doc, "• Tầng Kết nối & Thu thập dữ liệu đa nguồn (Integration & Extraction Layer):", bullet=True)
    add_p(doc, "  - Giao tiếp trực tiếp với hệ thống TTS Mới (tts.vnptnet.vn) và TTS Cũ (tts.vnpt.vn) thông qua giao thức REST API chuẩn;", bullet=True)
    add_p(doc, "  - Tích hợp module sapccheck tra cứu Trang Hồ sơ thuê bao (công nghệ Radio, IP WAN, cờ NAM, HSS Profile) và đối soát chính sách gói cước, quota dung lượng từ hệ thống SAPC;", bullet=True)
    add_p(doc, "  - Tích hợp module cem_client.py kết nối máy chủ CEM phân tích định danh trạm phát sóng (Cell ID / ECGI) và phân tích ứng dụng App Usage (phát hiện app VPN);", bullet=True)
    add_p(doc, "  - Tích hợp module crawler_btools.py truy xuất lịch sử phiên dữ liệu, throughput và QoS.", bullet=True)
    add_p(doc, "• Tầng Cơ sở dữ liệu (Data Persistence Layer): Quản lý cơ sở dữ liệu SQLite (tickets.db) với cơ chế Write-Ahead Logging (WAL) cho phép đọc/ghi đồng thời tốc độ cao, ngăn ngừa xung đột dữ liệu.", bullet=True)

    # Chèn Hình 1: Sơ đồ luồng quy trình
    add_p(doc, "Để trực quan hóa toàn diện chu trình tự động hóa và sự phối hợp nhịp nhàng giữa các phân hệ kỹ thuật, sơ đồ luồng quy trình vận hành tổng thể của hệ thống VNPT PRECHECK được thể hiện chi tiết tại Hình 1 dưới đây:")
    add_picture_with_caption(doc, "diagram_process_flow.png", 
                             "Hình 1: Sơ đồ luồng quy trình tự động hóa tiền kiểm tra hạ tầng, phân loại kịch bản và xử lý đóng phiếu của hệ thống VNPT PRECHECK", width_inches=6.3)

    # Chèn Hình 2: Giao diện Dashboard
    add_picture_with_caption(doc, "screenshot_production_ready.png", 
                             "Hình 2: Giao diện Web Dashboard điều hành trung tâm VNPT PRECHECK với bảng điều khiển, bộ lọc đa tiêu chí và Live Log thời gian thực")

    add_subheading(doc, "2. Phân hệ TỰ ĐỘNG HÓA TOÀN TRÌNH Mobile Internet (Nội dung cốt lõi và trọng tâm của sáng kiến):")
    add_p(doc, "Đây là phân hệ mang tính đột phá và chiếm tỷ trọng năng lực xử lý lớn nhất của sáng kiến, bao gồm các mắt xích tự động hóa hoàn chỉnh:")

    add_p(doc, "a) Thu thập và liên thông dữ liệu đa nguồn chuyên sâu cho Data:", bold=True)
    add_p(doc, "Ngay khi tiếp nhận phiếu phản ánh Mobile Internet, hệ thống tự động kích hoạt truy vấn đồng thời dữ liệu từ 4 hệ sinh thái kỹ thuật:")
    add_p(doc, "• Trang Hồ sơ thuê bao & SAPC: Trích xuất công nghệ mạng Radio thực tế (4G/3G/2G), trạng thái dịch vụ (cờ NAM = 0 là mở, NAM = 1 là khóa GPRS), mã HSS Profile (xác thực quyền truy cập 4G/5G), địa chỉ IP WAN cấp phát, gói cước data đang sử dụng, hạn dùng, dung lượng tốc độ cao còn lại, trạng thái bóp băng thông;", bullet=True)
    add_p(doc, "• Hệ thống CEM (Customer Experience Management): Phân tích lịch sử bắt sóng 5 ngày gần nhất để xác định Top 3 Cell phát sóng phục vụ, tỷ lệ kết nối trạm ưu thế (Dominant Cell), lưu lượng App Usage; đặc biệt tự động phát hiện các ứng dụng mạng riêng ảo (VPN / 1.1.1.1 / Cloudflare WARP) can thiệp bóp băng thông quốc tế và hiển thị cảnh báo đỏ nổi bật ngay sau danh sách Cell;", bullet=True)
    add_p(doc, "• Hệ thống BTools: Quét lịch sử các phiên kết nối dữ liệu (data sessions), dung lượng tải lên/tải xuống, throughput và đối chiếu chính xác với mốc thời gian khách hàng phản ánh sự cố.", bullet=True)

    add_p(doc, "b) Động cơ chẩn đoán chuyên sâu với hệ sinh thái 25 kịch bản kỹ thuật (Scenarios Engine):", bold=True)
    add_p(doc, "Hệ sinh thái chẩn đoán sự cố Mobile Internet được xây dựng từ thực tiễn chuyên sâu, phân thành 5 nhóm module nghiệp vụ chặt chẽ:")
    
    add_p(doc, "• Nhóm 1: Kiểm tra Hồ sơ thuê bao & Hạ tầng Core (HLR/HSS/NAM/5G):", bold=True)
    add_p(doc, "  (1) Khóa chặn GPRS (NAM = 1); (2) Chưa khai báo Profile 4G trên HSS (HSS Profile = 0); (3) Phản ánh dịch vụ 5G nhưng Profile/Trạm chưa hỗ trợ 5G; (4) Thuê bao tắt máy dài ngày (MS PURGED).", bullet=True)

    add_p(doc, "• Nhóm 2: Đối soát Chính sách cước & Quota dữ liệu (SAPC):", bold=True)
    add_p(doc, "  (5) Hết dung lượng data tốc độ cao bị hạ băng thông (KC_03); (6) Gói cước data đã hết hạn sử dụng; (7) Chỉ sử dụng gói mặc định PAYGO; (8) Gói cước tích hợp HOME/Gia đình; (9) Thuê bao mới gia hạn gói thành công trong ngày; (10) Đăng ký gói ngày nhưng thiếu gói nền dữ liệu.", bullet=True)

    add_p(doc, "• Nhóm 3: Phân tích Phiên truy cập & Mốc thời gian tiếp nhận (BTools):", bold=True)
    add_p(doc, "  (11) Có phiên dữ liệu >10MB SAU mốc tiếp nhận (dịch vụ đã tự phục hồi/khách hàng dùng tốt); (12) Có phiên dữ liệu TRƯỚC nhưng SAU tiếp nhận chưa có phiên mới (theo dõi thêm); (13) Sau tiếp nhận chỉ có lưu lượng yếu (1MB - 10MB); (14) Dữ liệu lớn >10MB nhưng phản ánh mất sóng hoàn toàn (đối soát chứng minh thông tin phản ánh chưa đúng thực tế); (15) Dữ liệu lớn tại trạm ưu thế Dominant Cell nhưng phản ánh chậm (nghi ngờ trạm BTS tải cao cục bộ); (16) Lưu lượng yếu kéo dài tại một Cell cố định (suy hao sóng tại trạm).", bullet=True)

    add_p(doc, "• Nhóm 4: Chất lượng sóng vô tuyến & Tần suất rớt mạng:", bold=True)
    add_p(doc, "  (17) Không bắt được sóng 4G dù có Profile 4G (nghi thiết bị tắt chế độ 4G/LTE); (18) Bắt sóng 4G kém, liên tục rớt về 2G/3G (KC_02 & KC_05); (19) Sự cố mất liên lạc hoặc bảo dưỡng trạm BTS.", bullet=True)

    add_p(doc, "• Nhóm 5: Lỗi Gói cước / Treo dữ liệu / Ứng dụng VPN / Thiết bị đầu cuối:", bold=True)
    add_p(doc, "  (20) Lệch mã dịch vụ (Service ID Mismatch - treo policy gói cước); (21) Treo dữ liệu (Data Hang); (22) Phát hiện sử dụng VPN / 1.1.1.1 / Cloudflare can thiệp đường truyền (KC_06); (23) Lỗi thiết bị đầu cuối do đi nhiều nơi đều báo lỗi; (24) Sai cấu hình điểm truy cập APN m3-world; (25) Thuê bao chưa từng bật dữ liệu di động.", bullet=True)

    # Chèn Hình 3: Tóm tắt AI
    add_picture_with_caption(doc, "screenshot_ai_summary_table.png", 
                             "Hình 3: Kết quả tiền kiểm tra hạ tầng Core và phân tích tóm tắt phản ánh Mobile Internet bằng AI 6 trường cốt lõi")

    add_p(doc, "c) Cơ chế tự động đóng phiếu trực tiếp qua REST API đạt tỷ lệ 85% - 90%:", bold=True)
    add_p(doc, "Căn cứ vào 25 kịch bản trên, hệ thống xác định tập hợp 20 kịch bản hoàn toàn đủ điều kiện đóng chuẩn (Level-1 Auto-Close Candidate: hết dung lượng hạ băng thông, gói hết hạn, chưa có profile 4G, cờ khóa GPRS NAM=1, khách hàng đã dùng bình thường có phiên lớn sau tiếp nhận, lỗi ứng dụng VPN...). Thực tế vận hành ghi nhận các kịch bản này chiếm từ 85% đến 90% tổng số phiếu Mobile Internet phát sinh hàng ngày. Khi bật chế độ Auto Close, hệ thống tự động hoàn tất khâu tiền kiểm tra và đóng trực tiếp lên TTS qua REST API cho 85% - 90% số phiếu này chỉ trong 1-2 giây/phiếu mà không cần con người can thiệp thủ công.")

    add_p(doc, "d) Chế độ đóng thủ công an toàn 1-Click cho các phiếu đặc thù:", bold=True)
    add_p(doc, "Đối với các phiếu Data phức tạp cần rà soát lại (nghi ngờ suy hao sóng trạm BTS, cần đo kiểm địa bàn), KTV chỉ cần bấm nút “Đóng thủ công”. Hệ thống tự động mở form “Cập nhật xử lý” trên TTS và tự động điền sẵn toàn bộ trường quy chuẩn: B0 = True, Cột 10 (Nguyên nhân kỹ thuật), Cột 11 (Nội dung xử lý và kiến nghị Kỹ thuật địa bàn). KTV chỉ mất 1 giây lướt qua và bấm Lưu.")

    # Chèn Hình 4: Đóng phiếu thành công
    add_picture_with_caption(doc, "screenshot_closed_nam.png", 
                             "Hình 4: Minh chứng phiếu phản ánh khách hàng Mobile Internet đã được hệ thống tiền kiểm tra, phân loại kịch bản và đóng thành công")

    add_subheading(doc, "3. Phân hệ TIỀN KIỂM TẬP TRUNG & HỖ TRỢ XỬ LÝ cho các Loại phản ánh khác (Thoại, SMS, Gói cước, Vùng phủ...):")
    add_p(doc, "Đối với các nhóm phản ánh ngoài Mobile Internet (chiếm khoảng 20% - 25% số lượng phiếu), do tính chất nghiệp vụ đa dạng và đặc thù, phần mềm được định vị là Công cụ hỗ trợ tập trung & Tiền kiểm tra kỹ thuật (Pre-check & Decision Support Tool):")
    add_p(doc, "• Thu thập tập trung về một mối: Hệ thống tự động quét toàn bộ các phiếu sự cố Dịch vụ Thoại, Tin nhắn SMS, Gói cước, Khiếu nại cước phí, Vùng phủ sóng mang về quản lý tại Tab Voice/SMS trên Dashboard, bảo đảm không bỏ sót bất kỳ phiếu sự cố nào;", bullet=True)
    add_p(doc, "• Tự động tiền kiểm tra ngay hồ sơ thuê bao: Hệ thống tự động truy vấn Core HLR/HSS và hiển thị ngay trên màn hình các thông tin kỹ thuật cốt lõi: trạng thái dịch vụ (chặn 1 chiều/2 chiều do cước), công nghệ mạng thuê bao đang kết nối (2G/3G/4G/VoLTE), trạm phát sóng BTS phục vụ tại khu vực thuê bao;", bullet=True)
    add_p(doc, "• Hỗ trợ ra quyết định và đóng phiếu nhanh: KTV không phải đăng nhập rời rạc để tra cứu hồ sơ. Dữ liệu tiền kiểm tra hiển thị trực quan giúp KTV nhận định chính xác nguyên nhân và thực hiện đóng phiếu hoặc chuyển điều phối kỹ thuật chỉ với 1 click chuột trực tiếp ngay trên Dashboard.", bullet=True)

    # Chèn Hình 5: Giao diện Voice/SMS
    add_picture_with_caption(doc, "screenshot_ttsnew_voicesms.png", 
                             "Hình 5: Phân hệ quản lý và hỗ trợ tiền kiểm tra danh mục phiếu sự cố Thoại / Tin nhắn SMS / Gói / PA Khác tập trung trên Dashboard")

    add_subheading(doc, "4. Định hướng và Lộ trình phát triển mở rộng trong tương lai:")
    add_p(doc, "Với kiến trúc phân tầng mở và nền tảng kết nối API đã được xây dựng hoàn thiện, phần mềm có khả năng mở rộng mạnh mẽ trong giai đoạn tiếp theo:")
    add_p(doc, "• Mở rộng tự động hóa sâu cho Dịch vụ Thoại: Tiếp tục nghiên cứu và xây dựng tập luật chẩn đoán tự động cho dịch vụ thoại: đối soát cấu hình cuộc gọi chất lượng cao VoLTE, cuộc gọi qua Wifi (VoWiFi), phân tích tỷ lệ rớt cuộc gọi CSFB (Circuit Switched Fallback từ 4G về 2G/3G), kiểm tra trạng thái chuyển vùng trong nước/quốc tế;", bullet=True)
    add_p(doc, "• Mở rộng tự động hóa sâu cho Dịch vụ Tin nhắn SMS: Tích hợp chẩn đoán lỗi chặn lọc tin nhắn rác (Anti-Spam SMS), phân tích lộ trình chuyển phát tin nhắn Brandname và mã OTP ngân hàng, kiểm tra trung tâm nhắn tin SMSC;", bullet=True)
    add_p(doc, "• Tự động hóa khiếu nại Cước và Gói cước: Kết nối sâu với hệ thống Billing/OCS để tự động đối soát lịch sử trừ cước và chu kỳ gia hạn gói;", bullet=True)
    add_p(doc, "• Mục tiêu dài hạn: Từng bước nâng cấp các loại phản ánh khác từ mức độ 'Hỗ trợ tiền kiểm tra' lên mức độ 'Tự động hóa toàn trình', hướng tới tự động hóa 100% toàn bộ công tác xử lý PAKH di động của Tập đoàn.", bullet=True)

    add_subheading(doc, "5. Giải pháp an toàn thông tin và cô lập tài khoản trong mạng LAN (LAN Token Isolation):")
    add_p(doc, "Hệ thống đáp ứng nghiêm ngặt các tiêu chuẩn an toàn thông tin của Tập đoàn VNPT:")
    add_p(doc, "• Tuyệt đối không lưu trữ mật khẩu: Phiên làm việc (Bearer Token / Cookie) được trích xuất an toàn từ chính trình duyệt Chrome đang đăng nhập của nhân viên thông qua Chrome DevTools Protocol (CDP), không lưu trữ mật khẩu dạng rõ;", bullet=True)
    add_p(doc, "• Cơ chế cô lập Token mạng LAN (auth_tts.py): Khi triển khai dùng chung trong mạng nội bộ, mỗi máy trạm khi gửi lệnh đóng phiếu bắt buộc phải cung cấp token xác thực của chính tài khoản người đó. Máy chủ tuyệt đối không dùng token của mình để đóng thay cho máy khách. Cơ chế này đảm bảo tính minh bạch, đúng thẩm quyền cá nhân và tuân thủ chặt chẽ quy chế an toàn thông tin của Tập đoàn.", bullet=True)

    # ==================== PHẦN IV ====================
    add_heading_section(doc, "IV. Kết quả áp dụng/ Lợi ích thu được của sáng kiến:")
    add_p(doc, "Sáng kiến đã được đưa vào ứng dụng thực tế tại đơn vị và mang lại những bước chuyển biến vượt bậc so với phương thức vận hành thủ công trước đây:")

    # Bảng so sánh Table 1
    p_tb1_title = doc.add_paragraph()
    format_para(p_tb1_title, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=6, space_after=4, line_spacing=1.15, first_line_indent=0)
    r_tb1 = p_tb1_title.add_run("Bảng so sánh hiệu quả trước và sau khi áp dụng sáng kiến")
    set_run_font(r_tb1, font_name="Times New Roman", size_pt=12.5, bold=True)

    table_comp = doc.add_table(rows=9, cols=3)
    table_comp.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table_comp, color="7F7F7F", sz="4")

    widths_t1 = [Inches(0.6), Inches(3.2), Inches(3.2)]
    headers_t1 = ['TT', 'Mô tả đối tượng trước khi áp dụng sáng kiến\n(Quy trình thủ công truyền thống)', 'Mô tả đối tượng sau khi áp dụng sáng kiến\n(Hệ thống tự động hóa VNPT PRECHECK)']

    for col_idx, text in enumerate(headers_t1):
        cell = table_comp.cell(0, col_idx)
        cell.width = widths_t1[col_idx]
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        set_cell_background(cell, "EBF1F5")
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cp = cell.paragraphs[0]
        format_para(cp, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0, line_spacing=1.05, first_line_indent=0)
        c_run = cp.add_run(text)
        set_run_font(c_run, font_name="Times New Roman", size_pt=11, bold=True)

    rows_data_t1 = [
        ('1', 
         'Phương thức xử lý phiếu Mobile Internet (chiếm 80% khối lượng):\nThủ công 100%, phải mở 4-5 phần mềm (TTS, CEM, BTools, SAPC, HLR) đối soát bằng mắt, mất 5-10 phút/phiếu.',
         'Tự động hóa toàn trình Mobile Internet:\nTự động cào dữ liệu đa nguồn, tự động chẩn đoán 25 kịch bản và tự động đóng phiếu trực tiếp qua REST API (đạt tỷ lệ đóng 85% - 90%).'),
        ('2', 
         'Phương thức xử lý các loại phiếu khác (Thoại, SMS, Gói cước...):\nPhân tán rải rác trên nhiều menu TTS, tra cứu thủ công từng số thuê bao, dễ bỏ sót phiếu.',
         'Nền tảng tiền kiểm tra & hỗ trợ tập trung:\nGom 100% phiếu về Dashboard, tự động tiền kiểm tra ngay hồ sơ HLR/HSS/Cell, hỗ trợ KTV đóng phiếu 1-click nhanh chóng.'),
        ('3', 
         'Thời gian tiền kiểm tra kỹ thuật:\nMất từ 5 đến 10 phút cho mỗi phiếu sự cố do phải chuyển đổi qua lại giữa nhiều ứng dụng web.',
         'Rút ngắn thời gian đột phá:\nChỉ mất 10 đến 15 giây/phiếu để hoàn tất tiền kiểm tra toàn diện (giảm hơn 95% thời gian thao tác).'),
        ('4', 
         'Tương thích hệ thống TTS:\nThao tác riêng rẽ trên giao diện web của TTS Cũ và TTS Mới, mở nhiều tab, dễ treo trình duyệt.',
         'Tương thích song song qua REST API:\nKết nối trực tiếp qua REST API với cả TTS Cũ và TTS Mới, xử lý ngầm siêu tốc, ổn định, không phụ thuộc giao diện web.'),
        ('5', 
         'Năng suất xử lý của nhân viên:\nTrung bình 1 nhân viên chỉ xử lý được tối đa 40 - 60 phiếu/ngày, thường xuyên quá tải vào giờ cao điểm.',
         'Tăng năng suất vượt bậc:\n1 nhân viên có thể giám sát và xử lý 200 - 300 phiếu/ngày (năng suất lao động tăng gấp 4 - 5 lần).'),
        ('6', 
         'Tỷ lệ hoàn thành KPI (SLA):\nTỷ lệ đúng hạn chỉ đạt khoảng 85% - 90%, thường xuyên có nguy cơ trễ hạn trong các đợt sự cố.',
         'Nâng cao chỉ số KPI vượt trội:\nTỷ lệ đóng phiếu đúng hạn đạt trên 98% - 99%, triệt tiêu hoàn toàn rủi ro vi phạm cam kết chất lượng dịch vụ.'),
        ('7', 
         'Độ chính xác chẩn đoán kỹ thuật:\nPhụ thuộc vào cảm tính cá nhân, dễ nhầm lẫn giữa hết quota bóp băng thông, lỗi VPN với lỗi trạm phát sóng BTS.',
         'Chuẩn hóa tuyệt đối theo 25 kịch bản:\nChẩn đoán logic tự động, phát hiện chính xác lỗi gói cước, suy hao sóng và cảnh báo đỏ ứng dụng VPN.'),
        ('8', 
         'Khả năng mở rộng trong tương lai:\nQuy trình thủ công không có tính kế thừa, khó mở rộng sang các dịch vụ mới.',
         'Kiến trúc mở sẵn sàng mở rộng:\nĐã có lộ trình tiếp tục phát triển tự động hóa sâu cho các phân hệ Thoại (VoLTE), Tin nhắn SMS và Cước phí.')
    ]

    for row_idx, r_data in enumerate(rows_data_t1, start=1):
        for col_idx, text in enumerate(r_data):
            cell = table_comp.cell(row_idx, col_idx)
            cell.width = widths_t1[col_idx]
            set_cell_margins(cell, top=70, bottom=70, left=90, right=90)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            cp = cell.paragraphs[0]
            align = WD_ALIGN_PARAGRAPH.CENTER if col_idx == 0 else WD_ALIGN_PARAGRAPH.LEFT
            format_para(cp, align=align, space_before=0, space_after=0, line_spacing=1.05, first_line_indent=0)
            c_run = cp.add_run(text)
            set_run_font(c_run, font_name="Times New Roman", size_pt=10.5)

    # Đánh giá chi tiết lợi ích
    add_subheading(doc, "1. Hiệu quả về mặt kỹ thuật và chất lượng mạng lưới:")
    add_p(doc, "• Đánh trúng và giải quyết dứt điểm điểm nghẽn lớn nhất của mạng lưới là dịch vụ Mobile Internet (chiếm >80% lưu lượng và 75%-80% phiếu phản ánh);", bullet=True)
    add_p(doc, "• Chuẩn hóa 100% quy trình chẩn đoán sự cố mạng di động nhờ bộ 25 kịch bản chuyên sâu, loại bỏ hoàn toàn các lỗi chủ quan do nhận định cảm tính của con người;", bullet=True)
    add_p(doc, "• Cung cấp dữ liệu đối soát khách quan, chính xác giữa phản ánh của khách hàng với trạng thái thực tế của trạm phát sóng BTS, ứng dụng VPN và gói cước trên Core mạng lưới, giúp đơn vị có căn cứ kỹ thuật chuẩn xác để xử lý và giải trình;", bullet=True)
    add_p(doc, "• Phát hiện sớm và khoanh vùng nhanh các trạm phát sóng suy hao vùng phủ sóng hoặc các trường hợp thuê bao lỗi cấu hình thiết bị/profile cước.", bullet=True)

    add_subheading(doc, "2. Hiệu quả về mặt năng suất lao động và giá trị làm lợi kinh tế gián tiếp:")
    add_p(doc, "• Tiết kiệm thời gian xử lý: Rút ngắn thời gian tiền kiểm tra từ 5-10 phút xuống còn 10-15 giây, tiết kiệm trung bình khoảng 7 phút cho mỗi phiếu sự cố;", bullet=True)
    add_p(doc, "• Tự động đóng phiếu 85% - 90% số lượng phản ánh Mobile Internet, giúp nhân viên không phải thao tác tay cho đại đa số phiếu hàng ngày;", bullet=True)
    add_p(doc, "• Với quy mô xử lý trung bình từ 1.500 đến 2.000 phiếu sự cố/tháng tại đơn vị:", bullet=True)
    add_p(doc, "  - Tổng thời gian lao động tiết kiệm được mỗi tháng: 1.800 phiếu × 7 phút = 12.600 phút ≈ 210 giờ làm việc/tháng;", bullet=True)
    add_p(doc, "  - Tương đương tiết kiệm định biên từ 1.2 đến 1.5 nhân sự kỹ thuật chuyên trách tiền kiểm tra, giải phóng sức lao động để bố trí nhân lực vào các công tác kỹ thuật chuyên sâu như đo kiểm tối ưu vùng phủ, ứng cứu thông tin và phát triển mạng lưới 4G/5G;", bullet=True)
    add_p(doc, "  - Ước tính giá trị làm lợi quy đổi gián tiếp từ chi phí nhân công và năng suất lao động đạt từ 40 - 60 triệu đồng/tháng (tương đương khoảng 500 - 700 triệu đồng/năm).", bullet=True)

    add_subheading(doc, "3. Hiệu quả về mặt quản trị và điều hành sản xuất kinh doanh:")
    add_p(doc, "• Lãnh đạo đơn vị và ca trưởng kỹ thuật có thể theo dõi trực tiếp tiến độ xử lý phiếu thời gian thực trên Dashboard, nhanh chóng nắm bắt các điểm nóng về sự cố mạng lưới;", bullet=True)
    add_p(doc, "• Tỷ lệ đóng phiếu đúng hạn KPI luôn duy trì ở mức xuất sắc (> 98%), nâng cao điểm đánh giá chất lượng điều hành dịch vụ của đơn vị trong toàn Tập đoàn;", bullet=True)
    add_p(doc, "• Tạo lập cơ sở dữ liệu số hóa tập trung (tickets.db) phục vụ phân tích xu hướng sự cố mạng lưới định kỳ.", bullet=True)

    add_subheading(doc, "4. Lợi ích đối với khách hàng và xã hội:")
    add_p(doc, "• Khách hàng sử dụng dịch vụ Mobile Internet nhận được phản hồi và khắc phục sự cố nhanh chóng, chuẩn xác;", bullet=True)
    add_p(doc, "• Nâng cao chỉ số hài lòng khách hàng (CSAT) đối với thương hiệu mạng di động VinaPhone, giảm tỷ lệ khiếu nại lặp lại và hạn chế tối đa nguy cơ thuê bao rời mạng.", bullet=True)

    # ==================== PHẦN V ====================
    add_heading_section(doc, "V. Tác giả tự đánh giá các tiêu chí xét công nhận sáng kiến (theo ý kiến của tác giả)")

    table_eval = doc.add_table(rows=14, cols=4)
    table_eval.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table_eval, color="7F7F7F", sz="4")

    widths_t2 = [Inches(0.5), Inches(2.2), Inches(1.8), Inches(2.5)]
    headers_t2 = ['TT', 'Tiêu chí', 'Hướng dẫn cách tự đánh giá', 'Tác giả tự đánh giá']

    for col_idx, text in enumerate(headers_t2):
        cell = table_eval.cell(0, col_idx)
        cell.width = widths_t2[col_idx]
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
        set_cell_background(cell, "EBF1F5")
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cp = cell.paragraphs[0]
        format_para(cp, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0, line_spacing=1.05, first_line_indent=0)
        c_run = cp.add_run(text)
        set_run_font(c_run, font_name="Times New Roman", size_pt=11, bold=True)

    rows_data_t2 = [
        ('1', 'Tính mới: chọn 1 trong 2 mục 1.1 hoặc 1.2', 'Đánh dấu (x) vào 1 trong 2 mục', ''),
        ('1.1', 'Giải pháp có nội dung mới tại đơn vị', '', 'x'),
        ('1.2', 'Giải pháp có nội dung mới tại Tập đoàn', '', ''),
        ('2', 'Tính sáng tạo, đột phá:', 'Mô tả tính sáng tạo, sự khác biệt so với các giải pháp trước đây', 
         '- Tự động hóa toàn trình dịch vụ Mobile Internet (chiếm >80% lưu lượng và 75%-80% phiếu phản ánh), tự động đóng phiếu trực tiếp 85% - 90% qua REST API.\n- Xây dựng nền tảng tiền kiểm tra tập trung cho các loại phiếu khác (Thoại, SMS, Gói cước) và hỗ trợ xử lý 1-click trên Dashboard.\n- Tích hợp 25 kịch bản chẩn đoán kỹ thuật, phát hiện app VPN và cảnh báo đỏ ngay sau Cell.\n- Kết nối trực tiếp REST API cả TTS Cũ và Mới, cơ chế cô lập Token LAN tuyệt đối an toàn.'),
        ('3', 'Phạm vi đã triển khai áp dụng: Chọn 1 trong 4 mục sau', 'Đánh dấu vào 1 trong 4 mục', ''),
        ('3.1', 'Áp dụng trong nội bộ một bộ phận / tổ / phòng của đơn vị', '', ''),
        ('3.2', 'Áp dụng trên toàn đơn vị (VNPT Tỉnh/Thành phố hoặc Tổng công ty thành viên)', '', 'x'),
        ('3.3', 'Sáng kiến này đã áp dụng từ 2 ĐV thành viên đến dưới 1/2 số ĐV thành viên của TĐ', '', ''),
        ('3.4', 'Sáng kiến này đã áp dụng trên 1/2 số đơn vị thành viên trong Tập đoàn', '', ''),
        ('4', 'Tính hiệu quả - Lợi ích thu được khi áp dụng sáng kiến: chọn 1 trong 2 mục 4.1 hoặc 4.2 dưới đây', 'Chọn mục nào thì đánh giá hiệu quả tại mục đó', ''),
        ('4.1', 'Mang lại hiệu quả trong đơn vị.\nVí dụ tăng năng suất lao động, tiết kiệm chi phí, cải tiến quy trình, giảm thao tác, tối ưu nguồn lực nội bộ.', '', 
         '- Rút ngắn 95% thời gian tiền kiểm tra (từ 5-10 phút xuống 10-15 giây/phiếu).\n- Tự động đóng phiếu 85% - 90% số phiếu Mobile Internet, tăng năng suất xử lý gấp 4-5 lần.\n- Tiết kiệm hơn 210 giờ công lao động/tháng (tương đương 1.2 - 1.5 định biên nhân sự kỹ thuật).\n- Dự kiến GTLL gián tiếp quy đổi từ chi phí nhân công và năng suất: khoảng 500 - 700 triệu đồng/năm.'),
        ('4.2', 'Mang lại hiệu quả có tính hệ thống và chuẩn hóa trong Tập đoàn:\n- Chuẩn hóa quy trình chẩn đoán mạng di động.\n- Dễ dàng nhân rộng áp dụng cho toàn bộ các VNPT Tỉnh/Thành phố trên toàn quốc.', 'Có thể ước tính hoặc quy đổi được GTLL ra tiền của 01 năm theo cách gián tiếp', 
         '- Chuẩn hóa quy trình vận hành và chất lượng chẩn đoán kỹ thuật trên toàn mạng lưới.\n- Tiềm năng nhân rộng cho 63 VNPT Tỉnh/Thành phố, ước tính tiết kiệm hàng chục nghìn giờ công lao động mỗi năm, mang lại giá trị làm lợi gián tiếp hàng tỷ đồng cho Tập đoàn.'),
        ('5', 'Hiệu quả có khả năng duy trì và tiếp tục áp dụng trong thời gian từ 1 năm trở lên', 'Nếu có thì đánh dấu vào', 'x')
    ]

    for row_idx, r_data in enumerate(rows_data_t2, start=1):
        for col_idx, text in enumerate(r_data):
            cell = table_eval.cell(row_idx, col_idx)
            cell.width = widths_t2[col_idx]
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            cp = cell.paragraphs[0]
            align = WD_ALIGN_PARAGRAPH.CENTER if (col_idx == 0 or (col_idx == 3 and text in ['x', ''])) else WD_ALIGN_PARAGRAPH.LEFT
            format_para(cp, align=align, space_before=0, space_after=0, line_spacing=1.05, first_line_indent=0)
            c_run = cp.add_run(text)
            bold_flag = True if (col_idx == 0 or col_idx == 1 and row_idx in [1, 4, 5, 10, 13]) else False
            set_run_font(c_run, font_name="Times New Roman", size_pt=10.5, bold=bold_flag)

    # ==================== PHẦN VI ====================
    add_heading_section(doc, "VI. Tài liệu chứng minh: quy định ban hành, kết quả sáng kiến…. (nếu có)")
    add_p(doc, "1. Toàn bộ mã nguồn hoàn chỉnh của phần mềm VNPT PRECHECK và tài liệu đặc tả kiến trúc kỹ thuật của hệ thống;", bullet=True)
    add_p(doc, "2. Nhật ký hệ thống (Live Log) và cơ sở dữ liệu SQLite (tickets.db) ghi nhận thực tế hàng nghìn phiếu phản ánh khách hàng Mobile Internet đã được tiền kiểm tra và đóng thành công qua phần mềm;", bullet=True)
    add_p(doc, "3. Mẫu báo cáo kết quả tiền kiểm tra định dạng Excel 12 cột chuẩn hóa quy chuẩn VNPT được xuất tự động từ phần mềm;", bullet=True)
    add_p(doc, "4. Video clip và ảnh chụp màn hình ghi lại quy trình vận hành thực tế: quét phiếu tự động, tiền kiểm tra đa nguồn Core/CEM/BTools/SAPC và đóng phiếu tự động ngầm qua REST API trên hệ thống TTS.", bullet=True)

    # Lời cam đoan
    p_commit = doc.add_paragraph()
    format_para(p_commit, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=10, space_after=12, line_spacing=1.2, first_line_indent=0.39)
    r_cm = p_commit.add_run("Chúng tôi cam đoan những điều khai trên đây là đúng sự thật.")
    set_run_font(r_cm, font_name="Times New Roman", size_pt=13, italic=True)

    # Chữ ký tác giả
    table_sign = doc.add_table(rows=1, cols=2)
    table_sign.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_sign.autofit = False

    c_left = table_sign.cell(0, 0)
    c_left.width = Inches(3.5)
    cp_l = c_left.paragraphs[0]
    format_para(cp_l, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=0, line_spacing=1.1, first_line_indent=0)

    c_right = table_sign.cell(0, 1)
    c_right.width = Inches(3.5)
    cp_r = c_right.paragraphs[0]
    format_para(cp_r, align=WD_ALIGN_PARAGRAPH.CENTER, space_before=0, space_after=2, line_spacing=1.15, first_line_indent=0)
    r_date_sign = cp_r.add_run("........., ngày ..... tháng ..... năm 2026\n")
    set_run_font(r_date_sign, font_name="Times New Roman", size_pt=13, italic=True)
    r_sign_title = cp_r.add_run("TÁC GIẢ CHỦ TRÌ SÁNG KIẾN\n")
    set_run_font(r_sign_title, font_name="Times New Roman", size_pt=13, bold=True)
    r_sign_note = cp_r.add_run("(Ký và ghi rõ họ tên)\n\n\n\n\n")
    set_run_font(r_sign_note, font_name="Times New Roman", size_pt=12, italic=True)
    r_sign_name = cp_r.add_run("[Họ và tên tác giả chủ trì]")
    set_run_font(r_sign_name, font_name="Times New Roman", size_pt=13, bold=True)

    # Save to docs/VNPT PRECHECK.docx or fallback if open in Word
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    os.makedirs(docs_dir, exist_ok=True)
    output_filename = os.path.join(docs_dir, "VNPT PRECHECK.docx")
    try:
        doc.save(output_filename)
        print(f"Document successfully generated and saved to {output_filename}!")
    except PermissionError:
        output_filename = os.path.join(docs_dir, "VNPT PRECHECK_HoanThien.docx")
        doc.save(output_filename)
        print(f"VNPT PRECHECK.docx is open in Word, saved to: {output_filename}!")

if __name__ == "__main__":
    build_full_docx()
