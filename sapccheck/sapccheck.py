import os
import sys

# Fix Windows console encoding (cp1252 không hỗ trợ tiếng Việt)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import json
import re
from pathlib import Path
from datetime import datetime
from msisdn_info import tra_cell_tu_so_dien_thoai

import pandas as pd

from sapc_client import SAPCClient
from converter import convert_sapc_response


# =========================
# CẤU HÌNH
# =========================

RESULT_FOLDER = r"D:\Python\pakh\result"


# =========================
# LẤY FILE EXCEL MỚI NHẤT
# =========================

def get_latest_excel_file():

    folder = Path(RESULT_FOLDER)

    excel_files = [f for f in folder.glob("*.xlsx") if not f.name.startswith("~$")]

    if not excel_files:
        raise FileNotFoundError(
            f"Không tìm thấy file Excel trong: {RESULT_FOLDER}"
        )

    latest_file = max(
        excel_files,
        key=lambda f: f.stat().st_mtime
    )

    return str(latest_file)


# =========================
# ĐỌC MSISDN TỪ EXCEL
# =========================
def load_msisdn_from_excel():

    excel_file = get_latest_excel_file()

    print(f"\n[INFO] File mới nhất:")
    print(excel_file)

    # File của bạn header nằm ở dòng 3
    df = pd.read_excel(
        excel_file,
        engine="openpyxl",
        header=2
    )

    phone_col = None

    # Tự tìm cột có chứa chữ "điện thoại"
    for col in df.columns:

        col_name = str(col).lower()

        if "điện thoại" in col_name:
            phone_col = col
            break

    if phone_col is None:

        print("\n[INFO] Các cột tìm thấy:")
        print(df.columns.tolist())

        raise Exception(
            "Không tìm thấy cột SỐ ĐIỆN THOẠI"
        )

    msisdns = []

    for value in df[phone_col].dropna():
        # Xử lý format số điện thoại (bỏ .0 nếu là float, xoá khoảng trắng)
        val_str = str(value).strip()
        val_str = re.sub(r"\.0$", "", val_str)
        
        # Chỉ lấy chuỗi số 10-12 ký tự
        if re.fullmatch(r"\d{10,12}", val_str):
            msisdns.append(val_str)

    # Loại bỏ trùng lặp nhưng giữ thứ tự
    msisdns = list(dict.fromkeys(msisdns))

    print(f"[INFO] Cột MSISDN: {phone_col}")
    print(f"[INFO] Tìm thấy {len(msisdns)} MSISDN: {msisdns}")

    return msisdns

# =========================
# LƯU JSON RIÊNG
# =========================

def save_json(msisdn, data):

    os.makedirs(
        "output",
        exist_ok=True
    )

    filename = f"output/{msisdn}.json"

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )

    return filename


# =========================
# LƯU FILE TỔNG HỢP
# =========================

def save_all_results(results):

    os.makedirs(
        "output",
        exist_ok=True
    )

    filename = "output/all_packages.json"

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=4
        )

    return filename


# =========================
# MAIN
# =========================

def main():

    print("\n=== SAPC CHECK ===\n")

    try:

        msisdn_list = load_msisdn_from_excel()

        if not msisdn_list:
            print("Không tìm thấy MSISDN trong file Excel")
            return

        client = SAPCClient()

        all_results = []

        total = len(msisdn_list)

        for index, msisdn in enumerate(msisdn_list, start=1):

            try:

                print(
                    f"\n[{index}/{total}] Processing: {msisdn}"
                )

                # raw_data = client.query(
                #     msisdn
                # )

                # result = convert_sapc_response(
                #     raw_data
                # )

                #LẤY THÊM THÔNG TIN THUÊ BAO
                raw_data = client.query(msisdn)

                sapc_result = convert_sapc_response(
                    raw_data
                )

                info_result = tra_cell_tu_so_dien_thoai(
                    msisdn
                )

                result = {
                    **sapc_result,
                    "subscriber_info": info_result
                }

                result["update_time"] = (
                    datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

                save_json(
                    msisdn,
                    result
                )

                all_results.append(
                    result
                )

                print(
                    f"[OK] Saved output/{msisdn}.json"
                )

            except Exception as ex:

                print(
                    f"[ERROR] {msisdn}: {ex}"
                )

        summary_file = save_all_results(
            all_results
        )

        print("\n==============================")
        print(f"Hoàn thành: {len(all_results)}/{total}")
        print(f"Saved: {summary_file}")
        print("==============================")

    except Exception as ex:

        print(
            "\nFATAL ERROR:",
            ex
        )


if __name__ == "__main__":
    main()
