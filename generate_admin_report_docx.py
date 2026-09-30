# -*- coding: utf-8 -*-
"""
Script tạo file Word báo cáo kỹ thuật gửi Admin Hệ thống OneOSS (TTS Mới)
về các lỗi luồng quy trình BPMN, điểm nghẽn bước 2.1, và lỗi cấu hình formId bước 2.6.
"""
import sys
import os
import json
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
import requests
import ttsnew_api

doc = docx.Document()

# Page setup A4
for section in doc.sections:
    section.top_margin = Inches(0.79)   # 20mm
    section.bottom_margin = Inches(0.79)
    section.left_margin = Inches(0.98)  # 25mm
    section.right_margin = Inches(0.79) # 20mm

def set_font(run, name='Times New Roman', size=13, bold=False, italic=False, color=(0,0,0)):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(*color)
    rPr = run._r.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), name)
    rFonts.set(qn('w:hAnsi'), name)
    rFonts.set(qn('w:cs'), name)
    rFonts.set(qn('w:eastAsia'), name)
    rPr.append(rFonts)

def add_p(doc, text='', align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=4, bold=False, italic=False, size=13, color=(0,0,0)):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.2
    if text:
        r = p.add_run(text)
        set_font(r, size=size, bold=bold, italic=italic, color=color)
    return p

def set_cell_shading(cell, color_hex):
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

# Header Table (Left: VNPT Net, Right: Quốc hiệu)
tbl_hdr = doc.add_table(rows=1, cols=2)
tbl_hdr.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl_hdr.autofit = False
c_l = tbl_hdr.cell(0, 0)
c_r = tbl_hdr.cell(0, 1)
c_l.width = Inches(3.2)
c_r.width = Inches(3.5)

p_l1 = c_l.paragraphs[0]
p_l1.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_l1.paragraph_format.space_after = Pt(1)
r = p_l1.add_run('TẬP ĐOÀN BƯU CHÍNH VIỄN THÔNG VIỆT NAM\n')
set_font(r, size=10, bold=False)
r2 = p_l1.add_run('TỔNG CÔNG TY HẠ TẦNG MẠNG (VNPT Net)\n')
set_font(r2, size=10.5, bold=True)
r3 = p_l1.add_run('TRUNG TÂM VẬN HÀNH KHAI THÁC MẠNG\nKHU VỰC MIỀN NAM (SOC2)')
set_font(r3, size=10, bold=True, color=(0, 84, 166))

p_r1 = c_r.paragraphs[0]
p_r1.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_r1.paragraph_format.space_after = Pt(1)
r4 = p_r1.add_run('CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n')
set_font(r4, size=10.5, bold=True)
r5 = p_r1.add_run('Độc lập - Tự do - Hạnh phúc\n')
set_font(r5, size=11, bold=True)
r6 = p_r1.add_run('---------------------------------')
set_font(r6, size=10, bold=True)

# Date
add_p(doc, 'TP. Hồ Chí Minh, ngày 17 tháng 09 năm 2026', align=WD_ALIGN_PARAGRAPH.RIGHT, space_before=10, space_after=14, italic=True, size=11.5)

# Title
add_p(doc, 'BÁO CÁO KỸ THUẬT', align=WD_ALIGN_PARAGRAPH.CENTER, space_before=6, space_after=2, bold=True, size=16, color=(0, 84, 166))
add_p(doc, 'V/v Các điểm nghẽn luồng quy trình BPMN, lỗi phân loại bước và lỗi cấu hình đóng phiếu trên Hệ thống OneOSS (TTS Mới)', align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=14, bold=True, italic=True, size=13)

# Recipient
add_p(doc, 'Kính gửi:  Bộ phận Quản trị Hệ thống OneOSS (Admin TTS Mới) - VNPT Net', align=WD_ALIGN_PARAGRAPH.CENTER, space_before=4, space_after=14, bold=True, size=13)

# 1. Mục đích & Tổng quan
add_p(doc, '1. TỔNG QUAN VÀ MỤC ĐÍCH BÁO CÁO', bold=True, size=14, space_before=10, space_after=4, color=(0, 84, 166))
add_p(doc, 'Trong quá trình phối hợp tiếp nhận, tiền kiểm kỹ thuật và xử lý các phản ánh chất lượng mạng (PAKH) của khách hàng VinaPhone trên hệ thống OneOSS (TTS Mới), Tổ Dịch vụ - Trung tâm Vận hành Khai thác Mạng Khu vực Miền Nam (SOC2) đã thực hiện rà soát toàn diện danh mục 105 phiếu phản ánh đang phân bổ xử lý.')
add_p(doc, 'Qua đối soát dữ liệu REST API từ OneOSS Gateway (gw-oneoss.vnpt.vn) và phân tích luồng điều phối trạng thái thực tế của các phiếu, đơn vị phát hiện một số điểm nghẽn nghiêm trọng trong thiết kế luồng quy trình BPMN, dẫn tới tình trạng kỹ thuật viên (KTV) không thể thao tác, phiếu bị kẹt vĩnh viễn ở trạng thái phân loại hoặc không thể hoàn tất đóng phiếu tại bước 2.6. Văn bản này tổng hợp chi tiết các lỗi kỹ thuật và danh sách phiếu bị ảnh hưởng để Quản trị hệ thống OneOSS xem xét, hiệu chỉnh luồng.')

# 2. Lỗi kẹt tại 2.1
add_p(doc, '2. LỖI TRỌNG YẾU: KẸT CỨNG TẠI BƯỚC "2.1 PHÂN LOẠI" DO THIẾU NHÁNH RẼ BPMN (DEAD-LOCK)', bold=True, size=14, space_before=10, space_after=4, color=(192, 0, 0))
add_p(doc, '2.1. Phân tích nguyên nhân kỹ thuật:')
add_p(doc, '• Các phiếu PAKH từ tổng đài CCOS được đồng bộ sang TTS Mới thuộc "Quy trình Chất lượng mạng & dịch vụ di động", tự động gán về đơn vị thụ lý là Trung tâm Vận hành khai thác mạng Khu vực miền Nam/Tổ Dịch vụ (SOC2).')
add_p(doc, '• Khác với luồng chuẩn thông thường (CCOS phân vào bước 2.3 Phân công hoặc 2.4 Đánh giá kết quả), các phiếu này được khởi tạo tại Node: "2.1 Phân loại" (processNodeId: 01a09f6d-825f-7723-944c-506e425487fd).')
add_p(doc, '• Tuy nhiên, trong cấu hình luồng BPMN trên OneOSS Gateway (API TicketProcessing/get-next-step), bước "2.1 Phân loại" CHỈ CÓ DUY NHẤT 01 NHÁNH CHUYỂN TIẾP là: "5.1 Xây dựng PA xử lý" (chuyển sang DHSXKD/OneBSS cho VNPT Tỉnh).')
add_p(doc, '• Sơ đồ BPMN hoàn toàn KHÔNG cấu hình transition nối sang các bước nội bộ của SOC: Không có nhánh sang bước "2.3 Xử lý", không có nhánh sang "2.4 Đánh giá", và đặc biệt KHÔNG CÓ NHÁNH sang "2.6 Đóng phiếu Trên TTS".')
add_p(doc, '• Hậu quả: Khi KTV SOC thực hiện tiền kiểm tra, đối soát dữ liệu Core SAPC/BTools nhận thấy mạng lưới tại khu vực hoàn toàn bình thường hoặc khách hàng hết dung lượng gói data (đủ điều kiện đóng phiếu tại bàn SOC theo quy định), KTV hoàn toàn không có lựa chọn để đóng phiếu hoặc xử lý tại SOC. Nếu KTV muốn giải phóng phiếu thì buộc phải chuyển sai quy trình sang 5.1 (đẩy trách nhiệm cho VNPT Tỉnh xử lý vô lý), hoặc chấp nhận để phiếu quá hạn SLA!')

add_p(doc, '2.2. Danh sách 05 phiếu đang bị kẹt cứng tại bước 2.1:', bold=True, space_before=4, space_after=4)

# Table 5 tickets
tbl_5 = doc.add_table(rows=1, cols=6)
tbl_5.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl_5.autofit = False

headers_5 = ['STT', 'Mã Phiếu', 'Số Thuê Bao', 'Thời Gian KH Báo', 'Gói Cước / Thiết Bị', 'Nội Dung Phản Ánh & Địa Chỉ']
widths_5 = [Inches(0.4), Inches(1.5), Inches(1.1), Inches(1.1), Inches(1.1), Inches(2.1)]

hdr_cells = tbl_5.rows[0].cells
for idx, name in enumerate(headers_5):
    hdr_cells[idx].width = widths_5[idx]
    set_cell_shading(hdr_cells[idx], '0054A6')
    set_cell_margins(hdr_cells[idx], 80, 80, 100, 100)
    p = hdr_cells[idx].paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(name)
    set_font(r, size=10, bold=True, color=(255, 255, 255))

data_5 = [
    ('1', 'HT/2026/09/14/24949\n(ID: 24949 - Flow: 112830)', '0919349024\n(KH: Phùng Văn Đạt)', '11/09/2026\n19:53', 'Gói: YOLO100M\nMáy: iPhone (3G)', 'Sóng 4G yếu, chập chờn. Đã reset GPRS nhiều lần không cải thiện.\nĐ/c: Duyên Hải, Cần Giờ, TP.HCM.'),
    ('2', 'HT/2026/09/14/24854\n(ID: 24854 - Flow: 112182)', '0917791967', '13/09/2026\n14:25', 'Gói: D169G\nMáy: iPhone 17', 'Không truy cập được mạng, máy không hiện 3G/4G.\nĐ/c: 272/6 Gò Xoài, P. Bình Hưng Hòa, TP.HCM.'),
    ('3', 'HT/2026/09/12/24439\n(ID: 24439 - Flow: 110958)', '0913554738\n(KH: Mai Linh)', '12/09/2026\n10:57', 'Chất lượng mạng', 'KH chê mạng VNP kém chất lượng, yêu cầu hủy số ngay lập tức, đòi gọi lại trong 5 phút.\nĐ/c: TP.HCM.'),
    ('4', 'HT/2026/09/02/22319\n(ID: 22319 - Flow: 107693)', '0915332498\n(KH: Hoàng Đình Hòa)', '02/09/2026\n11:56', 'Máy: IP 17\nCell: 6112-157533453', 'Sóng chập chờn cả indoor/outdoor, luôn báo 1 vạch 3G.\nĐ/c: 254/5/127 Lê Văn Thọ, P. Thông Tây Hội, TP.HCM.'),
    ('5', 'HT/2026/09/02/22155\n(ID: 22155 - Flow: 107721)', '0825550751\n(KH: Phan Thị Hạnh)', '02/09/2026\n10:51', 'Gói: SODA125\nMáy: Samsung', 'Không có kết nối Internet, máy không có sóng 3G.\nĐ/c: Ấp Tấn Đàng, Tân Mỹ, TP.HCM / Bắc Tân Uyên.')
]

for row_data in data_5:
    row_cells = tbl_5.add_row().cells
    for idx, val in enumerate(row_data):
        row_cells[idx].width = widths_5[idx]
        set_cell_margins(row_cells[idx], 60, 60, 80, 80)
        p = row_cells[idx].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx in (0, 1, 2, 3) else WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(val)
        set_font(r, size=9.5, bold=(idx == 1))

# 3. Lỗi formId bước 2.6
add_p(doc, '3. LỖI CẤU HÌNH: THIẾU FORM ĐÓNG PHIẾU (formId = null) TẠI BƯỚC "2.6 ĐÓNG PHIẾU TRÊN TTS"', bold=True, size=14, space_before=12, space_after=4, color=(192, 0, 0))
add_p(doc, '3.1. Phân tích nguyên nhân kỹ thuật:')
add_p(doc, '• Hiện tại hệ thống ghi nhận có tới 31 phiếu phản ánh đang tồn đọng tại bước "2.6 Đóng phiếu Trên TTS".')
add_p(doc, '• Khi gọi API TicketProcessing/get-next-step để nạp cấu hình bước đóng, trường processData.formId của node 2.6 trả về giá trị NULL (hoàn toàn không được gán mã biểu mẫu).')
add_p(doc, '• Đồng thời, node kết thúc trong nextNodeData chỉ hiển thị đối tượng BPMN dạng endEvent mà không chứa form định nghĩa các trường bắt buộc (như Mã nguyên nhân sự cố clIncidentCauseId, Nội dung đóng phiếu closingContent, Cột kết quả...).')
add_p(doc, '• Hậu quả: Khi KTV thao tác bấm đóng trên giao diện web TTS Mới hoặc hệ thống tự động gọi API TicketProcessing/close-ticket, việc thiếu cấu hình formId chuẩn dẫn tới việc hệ thống OneOSS từ chối tiếp nhận payload hoặc phát sinh lỗi Form Validation, khiến 31 phiếu này bị nghẽn không thể kết thúc.')

add_p(doc, '3.2. Thống kê 31 phiếu tồn đọng tại bước 2.6:', bold=True, space_before=4, space_after=4)

# Table 31 tickets
tbl_31 = doc.add_table(rows=1, cols=4)
tbl_31.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl_31.autofit = False

headers_31 = ['STT', 'Mã Phiếu (Ticket Code)', 'Số Thuê Bao', 'Bước Hiện Tại & Tình Trạng']
widths_31 = [Inches(0.6), Inches(2.3), Inches(1.5), Inches(2.9)]

hdr_31_cells = tbl_31.rows[0].cells
for idx, name in enumerate(headers_31):
    hdr_31_cells[idx].width = widths_31[idx]
    set_cell_shading(hdr_31_cells[idx], '0054A6')
    set_cell_margins(hdr_31_cells[idx], 80, 80, 100, 100)
    p = hdr_31_cells[idx].paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(name)
    set_font(r, size=10, bold=True, color=(255, 255, 255))

tok = ttsnew_api.get_cached_token()
tkts = ttsnew_api.fetch_active_tickets(tok)
p26_list = [t for t in tkts if '2.6' in str(t.get('stepName'))]

for idx, t in enumerate(p26_list, 1):
    r_cells = tbl_31.add_row().cells
    r_cells[0].width = widths_31[0]
    r_cells[1].width = widths_31[1]
    r_cells[2].width = widths_31[2]
    r_cells[3].width = widths_31[3]
    for c in r_cells:
        set_cell_margins(c, 50, 50, 70, 70)
    
    p0 = r_cells[0].paragraphs[0]
    p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p0.add_run(str(idx)), size=9)

    p1 = r_cells[1].paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p1.add_run(str(t.get('ticketCode'))), size=9, bold=True)

    p2 = r_cells[2].paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p2.add_run(str(t.get('subscriberNumber') or t.get('customerPhone') or '')), size=9)

    p3 = r_cells[3].paragraphs[0]
    p3.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_font(p3.add_run('2.6 Đóng phiếu Trên TTS (formId: null)'), size=9)

# 4. Lỗi phân mảnh quy trình CLM 02
add_p(doc, '4. LỖI PHÂN MẢNH VÀ XUNG ĐỘT QUYỀN TRÊN QUY TRÌNH "2.4_QT_CLM_02"', bold=True, size=14, space_before=12, space_after=4, color=(0, 84, 166))
add_p(doc, '• Hiện tại hệ thống đang tồn tại song song 02 quy trình cùng xử lý phản ánh chất lượng mạng di động: "Quy trình Chất lượng mạng & dịch vụ di động" và "2.4_QT_CLM_02".')
add_p(doc, '• Trong quy trình "2.4_QT_CLM_02", các node bước tiếp theo bị phân tách thành: "2.4 Đánh giá kết quả xử lý PAKH dịch vụ Data (SOC1)", "(SOC2)", "(SOC3)". Việc cấu hình hard-code gán cứng quyền phân nhánh theo tổ khu vực khiến phiếu bị kẹt khi KTV phụ trách trực ca thực hiện điều chuyển hoặc đóng phiếu liên tổ.')

# 5. Kiến nghị
add_p(doc, '5. KIẾN NGHỊ VÀ ĐỀ XUẤT GIẢI QUYẾT GỬI ADMIN ONEOSS', bold=True, size=14, space_before=12, space_after=4, color=(0, 84, 166))
add_p(doc, 'Để giải phóng các phiếu tồn đọng và đảm bảo SLA xử lý khiếu nại của khách hàng VinaPhone, Trung tâm SOC2 kính đề nghị Quản trị viên hệ thống OneOSS (TTS Mới) hỗ trợ:')
add_p(doc, '1. Hiệu chỉnh thiết kế BPMN tại bước "2.1 Phân loại":\n   - Bổ sung mũi tên rẽ nhánh (transition) cho phép chuyển tiếp từ node "2.1 Phân loại" sang bước "2.3 Xử lý PAKH dịch vụ Data / Thoại" hoặc trực tiếp sang bước "2.6 Đóng phiếu Trên TTS".\n   - Điều chuyển thủ công 05 phiếu bị kẹt (HT/2026/09/14/24949, 24854, 24439, 22319, 22155) sang bước 2.4 hoặc 2.6 để KTV SOC2 đóng hoàn tất.')
add_p(doc, '2. Cấu hình gán mã formId chuẩn tại node "2.6 Đóng phiếu Trên TTS":\n   - Khai báo form đóng phiếu chuẩn trên OneOSS cho node 2.6, đảm bảo tích hợp đầy đủ trường nguyên nhân sự cố (clIncidentCauseId) và nội dung xử lý (closingContent).')
add_p(doc, '3. Hợp nhất luồng quy trình PAKH Di động:\n   - Chuẩn hóa quy trình "2.4_QT_CLM_02" về chung luồng thống nhất, tránh phân mảnh node theo từng phân hệ SOC gây lỗi phân quyền.')

# Footer Sign
tbl_sign = doc.add_table(rows=1, cols=2)
tbl_sign.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl_sign.autofit = False
cs_l = tbl_sign.cell(0, 0)
cs_r = tbl_sign.cell(0, 1)
cs_l.width = Inches(3.2)
cs_r.width = Inches(3.5)

p_sl = cs_l.paragraphs[0]
p_sl.alignment = WD_ALIGN_PARAGRAPH.LEFT
set_font(p_sl.add_run('Nơi nhận:\n- Như trên;\n- Lãnh đạo Trung tâm SOC2 (để b/c);\n- Lưu: Tổ Dịch vụ.'), size=11, italic=True)

p_sr = cs_r.paragraphs[0]
p_sr.alignment = WD_ALIGN_PARAGRAPH.CENTER
set_font(p_sr.add_run('ĐẠI DIỆN TỔ DỊCH VỤ - SOC2\n'), size=11.5, bold=True)
set_font(p_sr.add_run('KỸ THUẬT VIÊN THỤ LÝ\n\n\n\n\n'), size=11, italic=True)
set_font(p_sr.add_run('(Đã ký & xác thực hệ thống)'), size=10.5, italic=True)

out_path = 'BAO_CAO_LOI_LUONG_TTS_MOI_ONEOSS.docx'
doc.save(out_path)
print('SUCCESS_SAVED:', out_path)
