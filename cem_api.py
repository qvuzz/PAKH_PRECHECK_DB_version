from datetime import datetime, timedelta
import pandas as pd
import requests
import time

URL = "https://api-cem.vnptmedia.vn/api2/getSubHistoryInfo"
API_KEY = "net_ktm_quangvu%dQpWVpQzaWTyNz5dT5Y0Dijwd0m2u6emBS1yWmZv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://cem.vnptmedia.vn",
    "Referer": "https://cem.vnptmedia.vn/",
}

# ================= CẤU HÌNH TÙY CHỌN =================
# 1. Danh sách số thuê bao (bỏ số 0 ở đầu)
PHONE_NUMBERS = ["918161817", "912345678"]

# 2. Khoảng thời gian cần quét (Định dạng YYYY-MM-DD)
START_DATE = "2026-08-20"
END_DATE = "2026-08-28"
# =====================================================


def generate_date_range(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    delta = end - start
    for i in range(delta.days + 1):
        yield (start + timedelta(days=i)).strftime("%Y-%m-%d")


all_records = []

for phone in PHONE_NUMBERS:
    for date_str in generate_date_range(START_DATE, END_DATE):
        payload = {
            "apikey": API_KEY,
            "start_date": date_str,
            "msisdn": phone,
        }

        try:
            print(f"Đang lấy dữ liệu: Số {phone} | Ngày {date_str}...")
            res = requests.post(URL, headers=HEADERS, json=payload, timeout=30)

            if res.status_code == 200:
                data = res.json()
                items = data.get("data") or data.get("result") or data

                if isinstance(items, list) and len(items) > 0:
                    for row in items:
                        if isinstance(row, dict):
                            row["query_msisdn"] = phone
                            row["query_date"] = date_str
                            all_records.append(row)
                else:
                    print(f" -> Không có dữ liệu.")
            else:
                print(f" -> Lỗi {res.status_code}: {res.text}")

        except Exception as e:
            print(f" -> Gặp lỗi khi gọi API: {e}")

        # Nghỉ 0.5s giữa các lần gọi để tránh bị hệ thống chặn quá tải (Rate limit)
        time.sleep(0.5)

# Lưu toàn bộ dữ liệu của tất cả các ngày vào 1 file Excel duy nhất
if all_records:
    df = pd.DataFrame(all_records)
    output_filename = "tong_hop_lich_su_cell.xlsx"
    df.to_excel(output_filename, index=False)
    print(f"\n Hoàn tất! Đã xuất {len(all_records)} bản ghi vào file: {output_filename}")
else:
    print("\n Không có bản ghi nào được tìm thấy.")