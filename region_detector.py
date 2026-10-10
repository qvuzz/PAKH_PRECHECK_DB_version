# -*- coding: utf-8 -*-
"""
Module: region_detector.py
Chuẩn hóa 34 Đơn vị hành chính cấp Tỉnh/Thành phố mới và Phân vùng 3 Miền Viễn thông VNPT.
Bao gồm:
- Miền Bắc (MB): 18 đơn vị
- Miền Nam (MN): 9 đơn vị (Lâm Đồng thuộc Miền Nam)
- Miền Trung (MT): 7 đơn vị
Tuân thủ tuyệt đối bảng sáp nhập 34 Tỉnh/TP mới của Việt Nam.
"""

import re
import json
from pathlib import Path
from typing import Optional, Tuple, Dict

# 34 Đơn vị hành chính cấp Tỉnh/TP mới và Miền tương ứng
NEW_34_PROVINCES: Dict[str, str] = {
    # Miền Bắc (MB) - 18 đơn vị
    "TP. Hà Nội": "MB",
    "TP. Hải Phòng": "MB",
    "Tỉnh Cao Bằng": "MB",
    "Tỉnh Lạng Sơn": "MB",
    "Tỉnh Lai Châu": "MB",
    "Tỉnh Điện Biên": "MB",
    "Tỉnh Sơn La": "MB",
    "Tỉnh Quảng Ninh": "MB",
    "Tỉnh Tuyên Quang": "MB",
    "Tỉnh Lào Cai": "MB",
    "Tỉnh Thái Nguyên": "MB",
    "Tỉnh Phú Thọ": "MB",
    "Tỉnh Bắc Ninh": "MB",
    "Tỉnh Hưng Yên": "MB",
    "Tỉnh Ninh Bình": "MB",
    "Tỉnh Thanh Hóa": "MB",
    "Tỉnh Nghệ An": "MB",
    "Tỉnh Hà Tĩnh": "MB",

    # Miền Nam (MN) - 9 đơn vị
    "Tỉnh Lâm Đồng": "MN",
    "TP. Hồ Chí Minh": "MN",
    "TP. Cần Thơ": "MN",
    "Tỉnh Đồng Nai": "MN",
    "Tỉnh Tây Ninh": "MN",
    "Tỉnh Vĩnh Long": "MN",
    "Tỉnh Đồng Tháp": "MN",
    "Tỉnh Cà Mau": "MN",
    "Tỉnh An Giang": "MN",

    # Miền Trung (MT) - 7 đơn vị
    "TP. Huế": "MT",
    "TP. Đà Nẵng": "MT",
    "Tỉnh Quảng Trị": "MT",
    "Tỉnh Quảng Ngãi": "MT",
    "Tỉnh Gia Lai": "MT",
    "Tỉnh Khánh Hòa": "MT",
    "Tỉnh Đắk Lắk": "MT",
}

# Mapping từ tên tỉnh cũ / biến thể / mã trạm viễn thông sang Tỉnh Mới
# Định dạng: {tên_chuẩn_hóa_viết_thường: (tên_tỉnh_mới, mã_miền)}
OLD_TO_NEW_PROVINCE_MAP: Dict[str, Tuple[str, str]] = {
    # --- MIỀN BẮC (MB) ---
    # 1. TP. Hà Nội
    "hà nội": ("TP. Hà Nội", "MB"),
    "ha noi": ("TP. Hà Nội", "MB"),
    "tp hà nội": ("TP. Hà Nội", "MB"),
    "tp. hà nội": ("TP. Hà Nội", "MB"),
    "thành phố hà nội": ("TP. Hà Nội", "MB"),
    "hni": ("TP. Hà Nội", "MB"),
    "hno": ("TP. Hà Nội", "MB"),

    # 2. TP. Hải Phòng (Hải Phòng + Hải Dương)
    "hải phòng": ("TP. Hải Phòng", "MB"),
    "hai phong": ("TP. Hải Phòng", "MB"),
    "tp hải phòng": ("TP. Hải Phòng", "MB"),
    "tp. hải phòng": ("TP. Hải Phòng", "MB"),
    "thành phố hải phòng": ("TP. Hải Phòng", "MB"),
    "hpg": ("TP. Hải Phòng", "MB"),
    "hải dương": ("TP. Hải Phòng", "MB"),
    "hai duong": ("TP. Hải Phòng", "MB"),
    "tỉnh hải dương": ("TP. Hải Phòng", "MB"),
    "hdg": ("TP. Hải Phòng", "MB"),

    # 3. Tỉnh Cao Bằng
    "cao bằng": ("Tỉnh Cao Bằng", "MB"),
    "cao bang": ("Tỉnh Cao Bằng", "MB"),
    "tỉnh cao bằng": ("Tỉnh Cao Bằng", "MB"),
    "cbg": ("Tỉnh Cao Bằng", "MB"),

    # 4. Tỉnh Lạng Sơn
    "lạng sơn": ("Tỉnh Lạng Sơn", "MB"),
    "lang son": ("Tỉnh Lạng Sơn", "MB"),
    "tỉnh lạng sơn": ("Tỉnh Lạng Sơn", "MB"),
    "lsn": ("Tỉnh Lạng Sơn", "MB"),

    # 5. Tỉnh Lai Châu
    "lai châu": ("Tỉnh Lai Châu", "MB"),
    "lai chau": ("Tỉnh Lai Châu", "MB"),
    "tỉnh lai châu": ("Tỉnh Lai Châu", "MB"),
    "lcu": ("Tỉnh Lai Châu", "MB"),

    # 6. Tỉnh Điện Biên
    "điện biên": ("Tỉnh Điện Biên", "MB"),
    "dien bien": ("Tỉnh Điện Biên", "MB"),
    "tỉnh điện biên": ("Tỉnh Điện Biên", "MB"),
    "dbn": ("Tỉnh Điện Biên", "MB"),

    # 7. Tỉnh Sơn La
    "sơn la": ("Tỉnh Sơn La", "MB"),
    "son la": ("Tỉnh Sơn La", "MB"),
    "tỉnh sơn la": ("Tỉnh Sơn La", "MB"),
    "sla": ("Tỉnh Sơn La", "MB"),

    # 8. Tỉnh Quảng Ninh
    "quảng ninh": ("Tỉnh Quảng Ninh", "MB"),
    "quang ninh": ("Tỉnh Quảng Ninh", "MB"),
    "tỉnh quảng ninh": ("Tỉnh Quảng Ninh", "MB"),
    "qnh": ("Tỉnh Quảng Ninh", "MB"),

    # 9. Tỉnh Tuyên Quang (Hà Giang + Tuyên Quang)
    "tuyên quang": ("Tỉnh Tuyên Quang", "MB"),
    "tuyen quang": ("Tỉnh Tuyên Quang", "MB"),
    "tỉnh tuyên quang": ("Tỉnh Tuyên Quang", "MB"),
    "tqg": ("Tỉnh Tuyên Quang", "MB"),
    "hà giang": ("Tỉnh Tuyên Quang", "MB"),
    "ha giang": ("Tỉnh Tuyên Quang", "MB"),
    "tỉnh hà giang": ("Tỉnh Tuyên Quang", "MB"),
    "hgg": ("Tỉnh Tuyên Quang", "MB"),

    # 10. Tỉnh Lào Cai (Yên Bái + Lào Cai)
    "lào cai": ("Tỉnh Lào Cai", "MB"),
    "lao cai": ("Tỉnh Lào Cai", "MB"),
    "tỉnh lào cai": ("Tỉnh Lào Cai", "MB"),
    "lci": ("Tỉnh Lào Cai", "MB"),
    "yên bái": ("Tỉnh Lào Cai", "MB"),
    "yen bai": ("Tỉnh Lào Cai", "MB"),
    "tỉnh yên bái": ("Tỉnh Lào Cai", "MB"),
    "ybi": ("Tỉnh Lào Cai", "MB"),

    # 11. Tỉnh Thái Nguyên (Bắc Kạn + Thái Nguyên)
    "thái nguyên": ("Tỉnh Thái Nguyên", "MB"),
    "thai nguyen": ("Tỉnh Thái Nguyên", "MB"),
    "tỉnh thái nguyên": ("Tỉnh Thái Nguyên", "MB"),
    "tnn": ("Tỉnh Thái Nguyên", "MB"),
    "bắc kạn": ("Tỉnh Thái Nguyên", "MB"),
    "bắc cạn": ("Tỉnh Thái Nguyên", "MB"),
    "bac kan": ("Tỉnh Thái Nguyên", "MB"),
    "tỉnh bắc kạn": ("Tỉnh Thái Nguyên", "MB"),
    "bkn": ("Tỉnh Thái Nguyên", "MB"),

    # 12. Tỉnh Phú Thọ (Vĩnh Phúc + Hòa Bình + Phú Thọ)
    "phú thọ": ("Tỉnh Phú Thọ", "MB"),
    "phu tho": ("Tỉnh Phú Thọ", "MB"),
    "tỉnh phú thọ": ("Tỉnh Phú Thọ", "MB"),
    "pto": ("Tỉnh Phú Thọ", "MB"),
    "vĩnh phúc": ("Tỉnh Phú Thọ", "MB"),
    "vinh phuc": ("Tỉnh Phú Thọ", "MB"),
    "tỉnh vĩnh phúc": ("Tỉnh Phú Thọ", "MB"),
    "vpc": ("Tỉnh Phú Thọ", "MB"),
    "hòa bình": ("Tỉnh Phú Thọ", "MB"),
    "hoa binh": ("Tỉnh Phú Thọ", "MB"),
    "tỉnh hòa bình": ("Tỉnh Phú Thọ", "MB"),
    "hbh": ("Tỉnh Phú Thọ", "MB"),

    # 13. Tỉnh Bắc Ninh (Bắc Giang + Bắc Ninh)
    "bắc ninh": ("Tỉnh Bắc Ninh", "MB"),
    "bac ninh": ("Tỉnh Bắc Ninh", "MB"),
    "tỉnh bắc ninh": ("Tỉnh Bắc Ninh", "MB"),
    "bnh": ("Tỉnh Bắc Ninh", "MB"),
    "bắc giang": ("Tỉnh Bắc Ninh", "MB"),
    "bac giang": ("Tỉnh Bắc Ninh", "MB"),
    "tỉnh bắc giang": ("Tỉnh Bắc Ninh", "MB"),
    "bgg": ("Tỉnh Bắc Ninh", "MB"),

    # 14. Tỉnh Hưng Yên (Thái Bình + Hưng Yên)
    "hưng yên": ("Tỉnh Hưng Yên", "MB"),
    "hung yen": ("Tỉnh Hưng Yên", "MB"),
    "tỉnh hưng yên": ("Tỉnh Hưng Yên", "MB"),
    "hyn": ("Tỉnh Hưng Yên", "MB"),
    "thái bình": ("Tỉnh Hưng Yên", "MB"),
    "thai binh": ("Tỉnh Hưng Yên", "MB"),
    "tỉnh thái bình": ("Tỉnh Hưng Yên", "MB"),
    "tbh": ("Tỉnh Hưng Yên", "MB"),

    # 15. Tỉnh Ninh Bình (Hà Nam + Nam Định + Ninh Bình)
    "ninh bình": ("Tỉnh Ninh Bình", "MB"),
    "ninh binh": ("Tỉnh Ninh Bình", "MB"),
    "tỉnh ninh bình": ("Tỉnh Ninh Bình", "MB"),
    "nbh": ("Tỉnh Ninh Bình", "MB"),
    "hà nam": ("Tỉnh Ninh Bình", "MB"),
    "ha nam": ("Tỉnh Ninh Bình", "MB"),
    "tỉnh hà nam": ("Tỉnh Ninh Bình", "MB"),
    "hnm": ("Tỉnh Ninh Bình", "MB"),
    "nam định": ("Tỉnh Ninh Bình", "MB"),
    "nam dinh": ("Tỉnh Ninh Bình", "MB"),
    "tỉnh nam định": ("Tỉnh Ninh Bình", "MB"),
    "ndh": ("Tỉnh Ninh Bình", "MB"),

    # 16. Tỉnh Thanh Hóa
    "thanh hóa": ("Tỉnh Thanh Hóa", "MB"),
    "thanh hoa": ("Tỉnh Thanh Hóa", "MB"),
    "tỉnh thanh hóa": ("Tỉnh Thanh Hóa", "MB"),
    "tha": ("Tỉnh Thanh Hóa", "MB"),

    # 17. Tỉnh Nghệ An
    "nghệ an": ("Tỉnh Nghệ An", "MB"),
    "nghe an": ("Tỉnh Nghệ An", "MB"),
    "tỉnh nghệ an": ("Tỉnh Nghệ An", "MB"),
    "nan": ("Tỉnh Nghệ An", "MB"),

    # 18. Tỉnh Hà Tĩnh
    "hà tĩnh": ("Tỉnh Hà Tĩnh", "MB"),
    "ha tinh": ("Tỉnh Hà Tĩnh", "MB"),
    "tỉnh hà tĩnh": ("Tỉnh Hà Tĩnh", "MB"),
    "hth": ("Tỉnh Hà Tĩnh", "MB"),

    # --- MIỀN NAM (MN) ---
    # 19. Tỉnh Lâm Đồng (Đắk Nông + Bình Thuận + Lâm Đồng) -> MIỀN NAM
    "lâm đồng": ("Tỉnh Lâm Đồng", "MN"),
    "lam dong": ("Tỉnh Lâm Đồng", "MN"),
    "tỉnh lâm đồng": ("Tỉnh Lâm Đồng", "MN"),
    "ldg": ("Tỉnh Lâm Đồng", "MN"),
    "đắk nông": ("Tỉnh Lâm Đồng", "MN"),
    "dak nong": ("Tỉnh Lâm Đồng", "MN"),
    "đắc nông": ("Tỉnh Lâm Đồng", "MN"),
    "dac nong": ("Tỉnh Lâm Đồng", "MN"),
    "tỉnh đắk nông": ("Tỉnh Lâm Đồng", "MN"),
    "dno": ("Tỉnh Lâm Đồng", "MN"),
    "bình thuận": ("Tỉnh Lâm Đồng", "MN"),
    "binh thuan": ("Tỉnh Lâm Đồng", "MN"),
    "tỉnh bình thuận": ("Tỉnh Lâm Đồng", "MN"),
    "btn": ("Tỉnh Lâm Đồng", "MN"),

    # 20. TP. Hồ Chí Minh (TP.HCM + Bình Dương + Bà Rịa – Vũng Tàu)
    "hồ chí minh": ("TP. Hồ Chí Minh", "MN"),
    "ho chi minh": ("TP. Hồ Chí Minh", "MN"),
    "tp. hồ chí minh": ("TP. Hồ Chí Minh", "MN"),
    "tp hồ chí minh": ("TP. Hồ Chí Minh", "MN"),
    "thành phố hồ chí minh": ("TP. Hồ Chí Minh", "MN"),
    "tp.hcm": ("TP. Hồ Chí Minh", "MN"),
    "tphcm": ("TP. Hồ Chí Minh", "MN"),
    "hcm": ("TP. Hồ Chí Minh", "MN"),
    "sài gòn": ("TP. Hồ Chí Minh", "MN"),
    "sai gon": ("TP. Hồ Chí Minh", "MN"),
    "bình dương": ("TP. Hồ Chí Minh", "MN"),
    "binh duong": ("TP. Hồ Chí Minh", "MN"),
    "tỉnh bình dương": ("TP. Hồ Chí Minh", "MN"),
    "bdg": ("TP. Hồ Chí Minh", "MN"),
    "bà rịa - vũng tàu": ("TP. Hồ Chí Minh", "MN"),
    "bà rịa vũng tàu": ("TP. Hồ Chí Minh", "MN"),
    "ba ria vung tau": ("TP. Hồ Chí Minh", "MN"),
    "tỉnh bà rịa - vũng tàu": ("TP. Hồ Chí Minh", "MN"),
    "brvt": ("TP. Hồ Chí Minh", "MN"),
    "vtu": ("TP. Hồ Chí Minh", "MN"),

    # 21. TP. Cần Thơ (TP. Cần Thơ + Sóc Trăng + Hậu Giang)
    "cần thơ": ("TP. Cần Thơ", "MN"),
    "can tho": ("TP. Cần Thơ", "MN"),
    "tp cần thơ": ("TP. Cần Thơ", "MN"),
    "tp. cần thơ": ("TP. Cần Thơ", "MN"),
    "thành phố cần thơ": ("TP. Cần Thơ", "MN"),
    "cto": ("TP. Cần Thơ", "MN"),
    "cth": ("TP. Cần Thơ", "MN"),
    "sóc trăng": ("TP. Cần Thơ", "MN"),
    "soc trang": ("TP. Cần Thơ", "MN"),
    "tỉnh sóc trăng": ("TP. Cần Thơ", "MN"),
    "stg": ("TP. Cần Thơ", "MN"),
    "hậu giang": ("TP. Cần Thơ", "MN"),
    "hau giang": ("TP. Cần Thơ", "MN"),
    "tỉnh hậu giang": ("TP. Cần Thơ", "MN"),
    "hug": ("TP. Cần Thơ", "MN"),

    # 22. Tỉnh Đồng Nai (Bình Phước + Đồng Nai)
    "đồng nai": ("Tỉnh Đồng Nai", "MN"),
    "dong nai": ("Tỉnh Đồng Nai", "MN"),
    "tỉnh đồng nai": ("Tỉnh Đồng Nai", "MN"),
    "dni": ("Tỉnh Đồng Nai", "MN"),
    "bình phước": ("Tỉnh Đồng Nai", "MN"),
    "binh phuoc": ("Tỉnh Đồng Nai", "MN"),
    "tỉnh bình phước": ("Tỉnh Đồng Nai", "MN"),
    "bpc": ("Tỉnh Đồng Nai", "MN"),

    # 23. Tỉnh Tây Ninh (Long An + Tây Ninh)
    "tây ninh": ("Tỉnh Tây Ninh", "MN"),
    "tay ninh": ("Tỉnh Tây Ninh", "MN"),
    "tỉnh tây ninh": ("Tỉnh Tây Ninh", "MN"),
    "tnh": ("Tỉnh Tây Ninh", "MN"),
    "long an": ("Tỉnh Tây Ninh", "MN"),
    "tỉnh long an": ("Tỉnh Tây Ninh", "MN"),
    "lan": ("Tỉnh Tây Ninh", "MN"),

    # 24. Tỉnh Vĩnh Long (Bến Tre + Trà Vinh + Vĩnh Long)
    "vĩnh long": ("Tỉnh Vĩnh Long", "MN"),
    "vinh long": ("Tỉnh Vĩnh Long", "MN"),
    "tỉnh vĩnh long": ("Tỉnh Vĩnh Long", "MN"),
    "vlg": ("Tỉnh Vĩnh Long", "MN"),
    "bến tre": ("Tỉnh Vĩnh Long", "MN"),
    "ben tre": ("Tỉnh Vĩnh Long", "MN"),
    "tỉnh bến tre": ("Tỉnh Vĩnh Long", "MN"),
    "bte": ("Tỉnh Vĩnh Long", "MN"),
    "trà vinh": ("Tỉnh Vĩnh Long", "MN"),
    "tra vinh": ("Tỉnh Vĩnh Long", "MN"),
    "tỉnh trà vinh": ("Tỉnh Vĩnh Long", "MN"),
    "tvh": ("Tỉnh Vĩnh Long", "MN"),

    # 25. Tỉnh Đồng Tháp (Tiền Giang + Đồng Tháp)
    "đồng tháp": ("Tỉnh Đồng Tháp", "MN"),
    "dong thap": ("Tỉnh Đồng Tháp", "MN"),
    "tỉnh đồng tháp": ("Tỉnh Đồng Tháp", "MN"),
    "dtp": ("Tỉnh Đồng Tháp", "MN"),
    "tiền giang": ("Tỉnh Đồng Tháp", "MN"),
    "tien giang": ("Tỉnh Đồng Tháp", "MN"),
    "tỉnh tiền giang": ("Tỉnh Đồng Tháp", "MN"),
    "tgg": ("Tỉnh Đồng Tháp", "MN"),

    # 26. Tỉnh Cà Mau (Bạc Liêu + Cà Mau)
    "cà mau": ("Tỉnh Cà Mau", "MN"),
    "ca mau": ("Tỉnh Cà Mau", "MN"),
    "tỉnh cà mau": ("Tỉnh Cà Mau", "MN"),
    "cmu": ("Tỉnh Cà Mau", "MN"),
    "bạc liêu": ("Tỉnh Cà Mau", "MN"),
    "bac lieu": ("Tỉnh Cà Mau", "MN"),
    "tỉnh bạc liêu": ("Tỉnh Cà Mau", "MN"),
    "blu": ("Tỉnh Cà Mau", "MN"),

    # 27. Tỉnh An Giang (Kiên Giang + An Giang)
    "an giang": ("Tỉnh An Giang", "MN"),
    "tỉnh an giang": ("Tỉnh An Giang", "MN"),
    "agg": ("Tỉnh An Giang", "MN"),
    "kiên giang": ("Tỉnh An Giang", "MN"),
    "kien giang": ("Tỉnh An Giang", "MN"),
    "tỉnh kiên giang": ("Tỉnh An Giang", "MN"),
    "kgg": ("Tỉnh An Giang", "MN"),
    "phú quốc": ("Tỉnh An Giang", "MN"),
    "phu quoc": ("Tỉnh An Giang", "MN"),
    "đặc khu phú quốc": ("Tỉnh An Giang", "MN"),

    # --- MIỀN TRUNG (MT) ---
    # 28. TP. Huế (Thừa Thiên Huế)
    "huế": ("TP. Huế", "MT"),
    "hue": ("TP. Huế", "MT"),
    "tp huế": ("TP. Huế", "MT"),
    "tp. huế": ("TP. Huế", "MT"),
    "thành phố huế": ("TP. Huế", "MT"),
    "thừa thiên huế": ("TP. Huế", "MT"),
    "thua thien hue": ("TP. Huế", "MT"),
    "tỉnh thừa thiên huế": ("TP. Huế", "MT"),
    "hue": ("TP. Huế", "MT"),

    # 29. TP. Đà Nẵng (TP. Đà Nẵng + Quảng Nam)
    "đà nẵng": ("TP. Đà Nẵng", "MT"),
    "da nang": ("TP. Đà Nẵng", "MT"),
    "tp đà nẵng": ("TP. Đà Nẵng", "MT"),
    "tp. đà nẵng": ("TP. Đà Nẵng", "MT"),
    "thành phố đà nẵng": ("TP. Đà Nẵng", "MT"),
    "dng": ("TP. Đà Nẵng", "MT"),
    "quảng nam": ("TP. Đà Nẵng", "MT"),
    "quang nam": ("TP. Đà Nẵng", "MT"),
    "tỉnh quảng nam": ("TP. Đà Nẵng", "MT"),
    "qnm": ("TP. Đà Nẵng", "MT"),

    # 30. Tỉnh Quảng Trị (Quảng Bình + Quảng Trị)
    "quảng trị": ("Tỉnh Quảng Trị", "MT"),
    "quang tri": ("Tỉnh Quảng Trị", "MT"),
    "tỉnh quảng trị": ("Tỉnh Quảng Trị", "MT"),
    "qti": ("Tỉnh Quảng Trị", "MT"),
    "quảng bình": ("Tỉnh Quảng Trị", "MT"),
    "quang binh": ("Tỉnh Quảng Trị", "MT"),
    "tỉnh quảng bình": ("Tỉnh Quảng Trị", "MT"),
    "qbh": ("Tỉnh Quảng Trị", "MT"),

    # 31. Tỉnh Quảng Ngãi (Kon Tum + Quảng Ngãi)
    "quảng ngãi": ("Tỉnh Quảng Ngãi", "MT"),
    "quang ngai": ("Tỉnh Quảng Ngãi", "MT"),
    "tỉnh quảng ngãi": ("Tỉnh Quảng Ngãi", "MT"),
    "qni": ("Tỉnh Quảng Ngãi", "MT"),
    "kon tum": ("Tỉnh Quảng Ngãi", "MT"),
    "kontum": ("Tỉnh Quảng Ngãi", "MT"),
    "tỉnh kon tum": ("Tỉnh Quảng Ngãi", "MT"),
    "ktm": ("Tỉnh Quảng Ngãi", "MT"),

    # 32. Tỉnh Gia Lai (Bình Định + Gia Lai)
    "gia lai": ("Tỉnh Gia Lai", "MT"),
    "gialai": ("Tỉnh Gia Lai", "MT"),
    "tỉnh gia lai": ("Tỉnh Gia Lai", "MT"),
    "gli": ("Tỉnh Gia Lai", "MT"),
    "bình định": ("Tỉnh Gia Lai", "MT"),
    "binh dinh": ("Tỉnh Gia Lai", "MT"),
    "tỉnh bình định": ("Tỉnh Gia Lai", "MT"),
    "bdh": ("Tỉnh Gia Lai", "MT"),

    # 33. Tỉnh Khánh Hòa (Ninh Thuận + Khánh Hòa)
    "khánh hòa": ("Tỉnh Khánh Hòa", "MT"),
    "khanh hoa": ("Tỉnh Khánh Hòa", "MT"),
    "tỉnh khánh hòa": ("Tỉnh Khánh Hòa", "MT"),
    "kha": ("Tỉnh Khánh Hòa", "MT"),
    "ninh thuận": ("Tỉnh Khánh Hòa", "MT"),
    "ninh thuan": ("Tỉnh Khánh Hòa", "MT"),
    "tỉnh ninh thuận": ("Tỉnh Khánh Hòa", "MT"),
    "ntn": ("Tỉnh Khánh Hòa", "MT"),

    # 34. Tỉnh Đắk Lắk (Phú Yên + Đắk Lắk)
    "đắk lắk": ("Tỉnh Đắk Lắk", "MT"),
    "đắc lắc": ("Tỉnh Đắk Lắk", "MT"),
    "dak lak": ("Tỉnh Đắk Lắk", "MT"),
    "tỉnh đắk lắk": ("Tỉnh Đắk Lắk", "MT"),
    "dlk": ("Tỉnh Đắk Lắk", "MT"),
    "phú yên": ("Tỉnh Đắk Lắk", "MT"),
    "phu yen": ("Tỉnh Đắk Lắk", "MT"),
    "tỉnh phú yên": ("Tỉnh Đắk Lắk", "MT"),
    "pyn": ("Tỉnh Đắk Lắk", "MT"),
}


def normalize_to_new_province(raw_input: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Nhận diện và chuẩn hóa tên tỉnh/thành phố hoặc mã trạm về Tỉnh/TP Mới và Miền tương ứng.
    Trả về: (new_province_name, region_code)
    Ví dụ:
      'Bình Dương' -> ('TP. Hồ Chí Minh', 'MN')
      'Bạc Liêu'   -> ('Tỉnh Cà Mau', 'MN')
      'Hải Dương'  -> ('TP. Hải Phòng', 'MB')
      'Lâm Đồng'   -> ('Tỉnh Lâm Đồng', 'MN')
      'Bình Định'  -> ('Tỉnh Gia Lai', 'MT')
      'BDG'        -> ('TP. Hồ Chí Minh', 'MN')
    """
    if not raw_input:
        return None, None

    clean = str(raw_input).strip()
    if not clean:
        return None, None

    # Nếu đã khớp chuẩn 34 tỉnh mới
    for prov, reg in NEW_34_PROVINCES.items():
        if clean.lower() == prov.lower():
            return prov, reg

    # Tra cứu trực tiếp từ OLD_TO_NEW_PROVINCE_MAP
    clean_lower = clean.lower()
    if clean_lower in OLD_TO_NEW_PROVINCE_MAP:
        return OLD_TO_NEW_PROVINCE_MAP[clean_lower]

    # Bỏ các tiền tố tỉnh/thành phố để tra cứu
    stripped = re.sub(r'^(tỉnh|thành phố|tp\.?|tt\.?)\s+', '', clean_lower).strip()
    if stripped in OLD_TO_NEW_PROVINCE_MAP:
        return OLD_TO_NEW_PROVINCE_MAP[stripped]

    # Kiểm tra partial match (tìm từ khóa tỉnh trong chuỗi địa chỉ hoặc text phản ánh)
    for key, (target_prov, target_reg) in OLD_TO_NEW_PROVINCE_MAP.items():
        if len(key) >= 4 and key in clean_lower:
            return target_prov, target_reg

    return None, None


def detect_ticket_region(ticket_data: dict, default_region: str = "MN") -> str:
    """
    Tự động nhận diện Miền (MB, MN, MT) của một phiếu phản ánh:
    1. ƯU TIÊN SỐ 1: Gán theo User KTV load phiếu về (user_region).
    2. ƯU TIÊN SỐ 2: Bóc tách trực tiếp từ Quy trình OneOSS (SOC 1/2/3, NET 1/2/3, VHKT MB/MN/MT).
    3. ƯU TIÊN SỐ 3: Nhận diện theo địa bàn Tỉnh/TP (theo chuẩn 34 Tỉnh/TP mới & 3 Miền).
    """
    # 1. Gán thẳng theo User KTV load phiếu về (nếu user có phân vùng cố định)
    u_reg = str(ticket_data.get("user_region") or "").strip().upper()
    if u_reg in ("MB", "MN", "MT"):
        return u_reg

    search_text = " ".join([
        str(ticket_data.get("ticket_code") or ""),
        str(ticket_data.get("step_name") or ""),
        str(ticket_data.get("process_name") or ""),
        str(ticket_data.get("processNodeName") or ""),
        str(ticket_data.get("processDefinitionName") or ""),
        str(ticket_data.get("assigned_unit") or ""),
        str(ticket_data.get("assignedUnitName") or "")
    ]).upper()

    # 2. Bóc tách trực tiếp từ Quy trình OneOSS (Tên bước / Tên quy trình / Đơn vị tiếp nhận BPMN)
    if any(k in search_text for k in ("SOC1", "SOC 1", "NET1", "NET 1", "MIỀN BẮC", "MIEN BAC", "VHKT MB", "VHKTM-B", "KHU VỰC 1", "KHU VUC 1", "KV1", "KV 1")):
        return "MB"
    if any(k in search_text for k in ("SOC2", "SOC 2", "NET2", "NET 2", "MIỀN NAM", "MIEN NAM", "VHKT MN", "VHKTM-N", "KHU VỰC 2", "KHU VUC 2", "KV2", "KV 2")):
        return "MN"
    if any(k in search_text for k in ("SOC3", "SOC 3", "NET3", "NET 3", "MIỀN TRUNG", "MIEN TRUNG", "VHKT MT", "VHKTM-T", "KHU VỰC 3", "KHU VUC 3", "KV3", "KV 3")):
        return "MT"

    # 3. Phân vùng theo Tỉnh/TP từ nội dung phản ánh / tiêu đề / địa chỉ / đơn vị tiếp nhận
    comb_content = " ".join([
        str(ticket_data.get("title") or ""),
        str(ticket_data.get("content") or ""),
        str(ticket_data.get("ward") or ""),
        str(ticket_data.get("province") or ""),
        str(ticket_data.get("province_name") or ""),
        str(ticket_data.get("assigned_unit") or ""),
        str(ticket_data.get("assignedUnitName") or "")
    ])
    _, detected_reg = detect_location_from_text(comb_content)
    if detected_reg in ("MB", "MN", "MT"):
        return detected_reg

    return default_region


def is_superadmin(user_info: dict) -> bool:
    """
    Kiểm tra tài khoản KTV có quyền Super Admin toàn quyền (Quản trị viên 3 Miền).
    Cụ thể: account 'quangvu', email 'quangvu@vnpt.vn', hoặc các tài khoản admin/root.
    Hỗ trợ cấu trúc thông tin từ cả TTS Mới (JWT) và TTS Cũ (Session CAS).
    """
    if not user_info:
        return False
    username = str(
        user_info.get("userName") or 
        user_info.get("username") or 
        user_info.get("TaiKhoan") or
        user_info.get("taikhoan") or
        user_info.get("ma_nd") or 
        ""
    ).lower().strip()

    display_name = str(
        user_info.get("displayName") or 
        user_info.get("name") or 
        user_info.get("HoTen") or 
        user_info.get("hoten") or 
        ""
    ).lower().strip()
    
    email = str(
        user_info.get("email") or 
        user_info.get("mail") or 
        ""
    ).lower().strip()

    # 1. Khớp username quangvu hoặc chứa quangvu
    if "quangvu" in username or username == "quangvu":
        return True

    # 2. Khớp email quangvu
    if "quangvu" in email or email == "quangvu@vnpt.vn":
        return True

    # 3. Khớp tên hiển thị Lê Quang Vũ
    if "lê quang vũ" in display_name or "le quang vu" in display_name or "quangvu" in display_name:
        return True

    # 4. Whitelist tài khoản Quản trị viên hệ thống
    if username in ("admin", "superadmin", "quantri", "root", "dev"):
        return True

    # 5. Kiểm tra role admin được cấp trong file user_regions.json
    try:
        cfg = get_user_regions_config()
        for u in cfg.get("users", []):
            if str(u.get("role") or "").lower() == "admin":
                u_name = str(u.get("username") or "").lower().strip()
                u_mail = str(u.get("email") or "").lower().strip()
                if (username and username == u_name) or (email and email == u_mail):
                    return True
    except Exception:
        pass

    return False


USER_REGIONS_FILE = Path(__file__).resolve().parent / "user_regions.json"


def get_user_regions_config() -> dict:
    """Đọc cấu hình phân vùng KTV từ user_regions.json."""
    if USER_REGIONS_FILE.exists():
        try:
            with open(USER_REGIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def detect_user_region(user_info: dict) -> str:
    """
    Nhận diện vùng miền của User KTV khi đăng nhập TTS Mới (OneOSS).
    Ưu tiên cao nhất tra cứu từ file cấu hình 'user_regions.json'.
    Nếu user thuộc Super Admin (quangvu, quangvu@vnpt.vn, admin localhost) -> Trả về 'ALL'
    Nếu không -> Trả về 'MB', 'MN' hoặc 'MT' theo TT SOC (SOC1=MB, SOC2=MN, SOC3=MT).
    """
    if is_superadmin(user_info):
        return "ALL"

    username = str(
        user_info.get("userName") or 
        user_info.get("username") or 
        user_info.get("TaiKhoan") or 
        user_info.get("taikhoan") or 
        user_info.get("ma_nd") or 
        ""
    ).lower().strip()

    email = str(
        user_info.get("email") or 
        user_info.get("mail") or 
        ""
    ).lower().strip()

    display_name = str(
        user_info.get("displayName") or 
        user_info.get("name") or 
        user_info.get("HoTen") or 
        user_info.get("hoten") or 
        ""
    ).lower().strip()

    # 1. Tra cứu trực tiếp từ file cấu hình user_regions.json (ưu tiên cao nhất)
    cfg = get_user_regions_config()
    users_list = cfg.get("users", [])
    soc_map = cfg.get("soc_mapping", {"SOC1": "MB", "SOC2": "MN", "SOC3": "MT"})

    for u in users_list:
        cfg_user = str(u.get("username") or "").lower().strip()
        cfg_email = str(u.get("email") or "").lower().strip()
        cfg_name = str(u.get("name") or "").lower().strip()
        cfg_reg = str(u.get("region") or soc_map.get(u.get("soc"), "")).upper()

        # Khớp theo username
        if username and (username == cfg_user or (cfg_email and username == cfg_email.split("@")[0])):
            return cfg_reg
        # Khớp theo email
        if email and (email == cfg_email or (cfg_user and email.split("@")[0] == cfg_user)):
            return cfg_reg
        # Khớp theo tên hiển thị
        if display_name and cfg_name and (display_name == cfg_name or cfg_name in display_name or display_name in cfg_name):
            return cfg_reg

    # 2. Fallback: Nhận diện theo mã đơn vị / tên đơn vị / quy trình phụ trách trong OneOSS
    full_text = " ".join([
        str(user_info.get("don_vi") or ""),
        str(user_info.get("ma_don_vi") or ""),
        str(user_info.get("ten_don_vi") or ""),
        str(user_info.get("region") or ""),
        username
    ]).lower()

    if any(k in full_text for k in ("soc1", "soc 1", "net1", "net 1", "mienbac", "miền bắc", "mb", "kv1")):
        return "MB"
    if any(k in full_text for k in ("soc2", "soc 2", "net2", "net 2", "miennam", "miền nam", "mn", "kv2")):
        return "MN"
    if any(k in full_text for k in ("soc3", "soc 3", "net3", "net 3", "mientrung", "miền trung", "mt", "kv3")):
        return "MT"

    return user_info.get("region") or "MN"


def is_user_permitted(user_info: dict) -> Tuple[bool, Optional[dict]]:
    """
    Kiểm tra xem user có được cấp quyền truy cập WebApp theo danh sách whitelist trong user_regions.json hay không.
    Trả về: (is_permitted, user_record)
    Superadmin luôn được cấp quyền (True, {...}).
    """
    if not user_info:
        return False, None

    if is_superadmin(user_info):
        return True, {
            "username": "quangvu",
            "name": "Lê Quang Vũ (Quản trị viên)",
            "email": "quangvu@vnpt.vn",
            "soc": "SOC2",
            "region": "ALL",
            "role": "admin"
        }

    username = str(
        user_info.get("userName") or 
        user_info.get("username") or 
        user_info.get("TaiKhoan") or 
        user_info.get("taikhoan") or 
        user_info.get("ma_nd") or 
        ""
    ).lower().strip()

    email = str(
        user_info.get("email") or 
        user_info.get("mail") or 
        ""
    ).lower().strip()

    display_name = str(
        user_info.get("displayName") or 
        user_info.get("name") or 
        user_info.get("HoTen") or 
        user_info.get("hoten") or 
        ""
    ).lower().strip()

    cfg = get_user_regions_config()
    users_list = cfg.get("users", [])
    soc_map = cfg.get("soc_mapping", {"SOC1": "MB", "SOC2": "MN", "SOC3": "MT"})

    for u in users_list:
        cfg_user = str(u.get("username") or "").lower().strip()
        cfg_email = str(u.get("email") or "").lower().strip()
        cfg_name = str(u.get("name") or "").lower().strip()
        cfg_soc = str(u.get("soc") or "").upper().strip()
        cfg_reg = str(u.get("region") or soc_map.get(cfg_soc, "MN")).upper().strip()

        matched = False
        if username and (username == cfg_user or (cfg_email and username == cfg_email.split("@")[0])):
            matched = True
        elif email and (email == cfg_email or (cfg_user and email.split("@")[0] == cfg_user)):
            matched = True
        elif display_name and cfg_name and (display_name == cfg_name or cfg_name in display_name or display_name in cfg_name):
            matched = True

        if matched:
            res_u = dict(u)
            res_u["region"] = cfg_reg
            res_u["soc"] = cfg_soc
            res_u["role"] = str(u.get("role") or ("admin" if cfg_user == "quangvu" else "ktv")).lower()
            return True, res_u

    return False, None


def save_user_to_config(user_data: dict) -> Tuple[bool, str]:
    """
    Thêm hoặc cập nhật một user vào file user_regions.json.
    user_data gồm: username, name, email, soc (SOC1/SOC2/SOC3), role (admin/ktv).
    """
    cfg = get_user_regions_config()
    if not cfg:
        cfg = {
            "_ghi_chu": "Cấu hình phân vùng KTV theo TT SOC (SOC1 = Miền Bắc MB, SOC2 = Miền Nam MN, SOC3 = Miền Trung MT). Thêm, sửa KTV tại danh sách 'users'.",
            "soc_mapping": {"SOC1": "MB", "SOC2": "MN", "SOC3": "MT"},
            "users": []
        }
    users_list = cfg.get("users", [])
    soc_map = cfg.get("soc_mapping", {"SOC1": "MB", "SOC2": "MN", "SOC3": "MT"})

    raw_user = str(user_data.get("username") or "").strip().lower()
    raw_email = str(user_data.get("email") or "").strip().lower()
    raw_name = str(user_data.get("name") or "").strip()
    raw_soc = str(user_data.get("soc") or "SOC2").strip().upper()
    raw_role = str(user_data.get("role") or ("admin" if raw_user == "quangvu" else "ktv")).strip().lower()
    if raw_role not in ("admin", "ktv"):
        raw_role = "ktv"

    if not raw_user and raw_email:
        raw_user = raw_email.split("@")[0]
    if not raw_email and raw_user:
        raw_email = f"{raw_user}@vnpt.vn"

    if not raw_user:
        return False, "Thiếu tên đăng nhập (username)"

    if raw_soc not in ("SOC1", "SOC2", "SOC3"):
        return False, f"TT SOC không hợp lệ ({raw_soc}). Vui lòng chọn SOC1, SOC2 hoặc SOC3"

    reg = soc_map.get(raw_soc, "MN")

    # Kiểm tra xem user đã tồn tại chưa để cập nhật hoặc thêm mới
    found_idx = -1
    for i, u in enumerate(users_list):
        u_name = str(u.get("username") or "").lower().strip()
        u_mail = str(u.get("email") or "").lower().strip()
        if (raw_user and u_name == raw_user) or (raw_email and u_mail == raw_email):
            found_idx = i
            break

    entry = {
        "soc": raw_soc,
        "region": reg,
        "name": raw_name or raw_user,
        "email": raw_email,
        "username": raw_user,
        "role": raw_role
    }

    if found_idx >= 0:
        users_list[found_idx] = entry
    else:
        users_list.append(entry)

    cfg["users"] = users_list
    try:
        with open(USER_REGIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True, f"Đã lưu thành công KTV [{raw_name or raw_user}] ({raw_soc} - {reg})"
    except Exception as e:
        return False, f"Lỗi ghi file user_regions.json: {e}"


def delete_user_from_config(identifier: str) -> Tuple[bool, str]:
    """
    Xóa một user khỏi file user_regions.json theo username hoặc email.
    """
    cfg = get_user_regions_config()
    users_list = cfg.get("users", [])
    raw_id = str(identifier or "").strip().lower()

    new_list = []
    deleted_name = None
    for u in users_list:
        u_name = str(u.get("username") or "").lower().strip()
        u_mail = str(u.get("email") or "").lower().strip()
        if u_name == raw_id or u_mail == raw_id:
            deleted_name = u.get("name") or u_name
            continue
        new_list.append(u)

    if deleted_name is None:
        return False, f"Không tìm thấy KTV với định danh [{raw_id}]"

    cfg["users"] = new_list
    try:
        with open(USER_REGIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True, f"Đã xóa thành công KTV [{deleted_name}]"
    except Exception as e:
        return False, f"Lỗi khi xóa khỏi user_regions.json: {e}"



