import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_RAT_LIB = {
    "0": "Báo hiệu",
    "1": "Sóng 3G",
    "2": "Sóng 2G",
    "6": "Sóng 4G",
    "7": "Sóng 5G"
}

def load_json_library(file_path):
    """Hàm phụ dùng để đọc file json thư viện an toàn"""
    full_path = file_path if os.path.isabs(file_path) else os.path.join(BASE_DIR, file_path)
    if not os.path.exists(full_path):
        # Chống lỗi phân biệt hoa/thường trên Linux Docker (vd: RATTYPE.JSON vs rattype.json)
        dir_name = os.path.dirname(full_path) or "."
        base_name = os.path.basename(full_path).lower()
        if os.path.exists(dir_name):
            for f in os.listdir(dir_name):
                if f.lower() == base_name:
                    full_path = os.path.join(dir_name, f)
                    break

    if not os.path.exists(full_path):
        if "rattype" in file_path.lower():
            return dict(DEFAULT_RAT_LIB)
        return {}
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Lỗi đọc file thư viện {full_path}: {e}")
        if "rattype" in file_path.lower():
            return dict(DEFAULT_RAT_LIB)
        return {}

def standardize_btools_data(btools_data):
    """
    Hàm nhận vào danh sách dữ liệu thô từ BTools,
    bổ sung dịch nghĩa VÀ BẮT BUỘC giữ lại mã Code gốc để ghi file JSON không bị trống.
    """
    # 📌 NẾU DỮ LIỆU THÔ LÀ NONE (LỖI HOẶC CHƯA ĐĂNG NHẬP), BẢO LƯU NONE ĐỂ BÁO LỖI
    if btools_data is None:
        return None
    if not btools_data:
        return []

    # Nạp 2 file thư viện danh mục của bạn
    rat_lib = load_json_library("rattype.json") or dict(DEFAULT_RAT_LIB)
    service_lib = load_json_library("serviceid.json")

    standardized_list = []
    
    for row in btools_data:
        # Lấy giá trị thô từ bảng (Chống lỗi Key Error bằng hàm .get)
        raw_msisdn = str(row.get("MSISDN", "")).strip()
        raw_rat = str(row.get("RAT_TYPE", "")).strip()
        raw_uplink = str(row.get("DATA_VOLUME_UPLINK", "")).strip()
        raw_downlink = str(row.get("DATA_VOLUME_DOWNLINK", "")).strip()
        raw_time = str(row.get("RECORD_OPENING_TIME", "")).strip()
        raw_service = str(row.get("SERVICE_ID", "")).strip()

        # 🕒 Xử lý làm sạch chuỗi thời gian lạ dính đuôi .0
        clean_time = raw_time
        if raw_time and raw_time != "None":
            try:
                if "." in raw_time and raw_time.count("-") == 2:
                    base_time_str = raw_time.split(".")[0]
                    dt_obj = datetime.strptime(base_time_str, "%Y-%m-%d %H:%M:%S")
                    clean_time = dt_obj.strftime("%d/%m/%Y %H:%M:%S")
                elif raw_time.count("-") == 2 and "." not in raw_time:
                    dt_obj = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S")
                    clean_time = dt_obj.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                clean_time = raw_time # Có lỗi thì giữ nguyên chuỗi gốc để an toàn

        # Tra cứu dịch nghĩa từ 2 file thư viện JSON của bạn
        translated_rat = rat_lib.get(raw_rat, "Mã mạng lạ") if raw_rat else ""
        translated_service = (service_lib.get(raw_service) or service_lib.get(raw_service.zfill(10)) or service_lib.get(raw_service.lstrip("0")) or "Gói cước lạ") if raw_service else ""

        # 🎯 ĐÓNG GÓI BẢN GHI: Phải giữ nguyên cả Code lẫn Tên dịch nghĩa
        clean_row = {
            "MSISDN": raw_msisdn,
            
            "RAT_TYPE_CODE": raw_rat,                  # <-- Giữ mã gốc (Ví dụ: "6")
            "RAT_TYPE_NAME": translated_rat,            # <-- Tên đã dịch (Ví dụ: "4G LTE")
            
            "DATA_VOLUME_UPLINK": raw_uplink,
            "DATA_VOLUME_DOWNLINK": raw_downlink,
            "RECORD_OPENING_TIME": clean_time,
            
            "SERVICE_ID_CODE": raw_service,            # <-- Giữ mã gốc (Ví dụ: "000000300")
            "SERVICE_NAME": translated_service          # <-- Tên đã dịch
        }
        standardized_list.append(clean_row)

    return standardized_list