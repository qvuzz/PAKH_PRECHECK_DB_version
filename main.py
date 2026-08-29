# main.py
import os
import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Fix encoding Tiếng Việt trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent

# 👉 ĐƯỜNG DẪN CHROMEDRIVER (Ưu tiên lấy từ biến môi trường nếu có)
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", r"C:\chromedriver\chromedriver.exe")

from crawler_tts import get_vnpt_tickets
from crawler_btools import extract_btools_single_phone
from data_processor import standardize_btools_data 
from report_bot import analyze_subscriber_status, export_diagnostics_to_excel, get_formatted_sapc_packages
from cem_client import CEMClient, get_cem_cell_summary
from ai_interpreter import analyze_ticket_with_ai
from login_tts import ensure_tts_logged_in

# 🎯 IMPORT MODULE TRA SAPC + HSS PROFILE
SAPCCHECK_DIR = str(BASE_DIR / "sapccheck")
if SAPCCHECK_DIR not in sys.path:
    sys.path.insert(0, SAPCCHECK_DIR)
from sapc_client import SAPCClient
from converter import convert_sapc_response
from msisdn_info import tra_cell_tu_so_dien_thoai


def normalize_phone_vn(phone_raw):
    """
    Chuẩn hóa số điện thoại theo định dạng chuẩn 84xxxxxxxxx (11 chữ số).
    Tránh tuyệt đối lỗi nhân đôi tiền tố (8484...).
    """
    clean = "".join(filter(str.isdigit, str(phone_raw or "").strip()))
    if not clean:
        return ""
    if clean.startswith("84"):
        return clean
    if clean.startswith("0"):
        return "84" + clean[1:]
    if len(clean) == 9:
        return "84" + clean
    return clean


def parse_args():
    parser = argparse.ArgumentParser(description="PAKH Precheck Engine — Tự động hóa xử lý sự cố mạng VNPT")
    parser.add_argument("--auto-close", action="store_true", help="Tự động cập nhật và đóng phiếu trên TTS sau khi xuất Excel")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử nghiệm đóng phiếu (điền form nhưng bấm HỦY, không đóng thật)")
    parser.add_argument("--observe", action="store_true", help="Chạy chậm 5s mỗi bước đóng phiếu để quan sát (tự bật --dry-run)")
    parser.add_argument("--skip-login", action="store_true", help="Bỏ qua bước kiểm tra/đăng nhập TTS tự động")
    parser.add_argument("--open-excel", action="store_true", help="Tự động mở file Excel kết quả sau khi hoàn tất")
    return parser.parse_args()


def main():
    args = parse_args()

    print("================================================================")
    print("🚀 KHỞI CHẠY PIPELINE TỰ ĐỘNG HÓA PAKH PRECHECK VNPT 🚀")
    print("================================================================")

    # -------------------------------------------------------------------------
    # BƯỚC 0: TỰ ĐỘNG ĐĂNG NHẬP & CHUẨN BỊ CHROME
    # -------------------------------------------------------------------------
    if not args.skip_login:
        print("\n🔑 [BƯỚC 0] Kiểm tra trạng thái đăng nhập hệ thống TTS...")
        logged_in = ensure_tts_logged_in(max_wait_seconds=60)
        if not logged_in:
            print("⚠️ Cảnh báo: Chưa xác nhận đăng nhập hoàn tất. Sẽ thử kết nối trực tiếp vào Chrome...")
        time.sleep(2)

    # -------------------------------------------------------------------------
    # BƯỚC 1: KẾT NỐI VÀO CHROME DEBUG PORT 9222
    # -------------------------------------------------------------------------
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    try:
        if os.path.exists(CHROMEDRIVER_PATH):
            service = Service(executable_path=CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        print("✅ Kết nối Chrome Port 9222 thành công!")
    except Exception as e:
        print(f"❌ Lỗi kết nối Chrome Port 9222: {e}")
        print("👉 Gợi ý: Hãy chạy file open_chrome.bat hoặc python login_tts.py trước!")
        return

    # Quét danh sách sự cố từ tab VNPT TTS gốc
    extracted_tickets, tts_tab_handle = get_vnpt_tickets(driver)
    if not extracted_tickets:
        print("⚠️ Không lấy được danh sách vé sự cố từ giao diện VNPT TTS.")
        return

    # Lọc trùng số điện thoại
    seen_phones = set()
    unique_tickets = []
    for t in extracted_tickets:
        if t["phone"] not in seen_phones:
            seen_phones.add(t["phone"])
            unique_tickets.append(t)

    print(f"\n📊 Tìm thấy {len(unique_tickets)} thuê bao độc nhất trên bảng sự cố.")

    # Khung thời gian 5 ngày liên tiếp
    today_dt = datetime.now()
    end_d = today_dt.strftime("%d%m%Y")
    start_d = (today_dt - timedelta(days=4)).strftime("%d%m%Y")
    
    print(f"⏳ Khoảng thời gian tra cứu: Từ {(today_dt - timedelta(days=4)).strftime('%d/%m/%Y')} -> Đến {today_dt.strftime('%d/%m/%Y')}")

    valid_titles = ["Mobile Internet 2G/3G", "Mobile Internet 4G", "Mobile Internet 5G"]
    excel_summary_list = []

    result_dir = str(BASE_DIR / "result")
    excel_name = os.path.join(result_dir, f"Bao_Cao_Su_Co_Mang_{datetime.now().strftime('%Y%m%d')}.xlsx")
    CHECKPOINT_EVERY = 5

    # Khởi tạo tab làm việc riêng cho BTools
    print("🌐 Đang khởi tạo tab làm việc riêng cho BTools...")
    driver.switch_to.new_window('tab')
    btools_tab_handle = driver.current_window_handle
    
    # Trả chuột về tab mẹ TTS
    driver.switch_to.window(tts_tab_handle)

    # Khởi tạo SAPCClient & CEMClient 1 lần duy nhất
    print("🔑 Đang khởi tạo SAPC Client (lấy cookie từ Chrome)...")
    try:
        sapc_client = SAPCClient(driver=driver)
    except Exception as e:
        print(f"⚠️ Không khởi tạo được SAPCClient: {e}. Bỏ qua tra cứu SAPC/HSS.")
        sapc_client = None

    print("📡 Đang khởi tạo CEM Client (lấy cookie từ Chrome)...")
    try:
        cem_client = CEMClient(driver=driver)
    except Exception as e:
        print(f"⚠️ Không khởi tạo được CEMClient: {e}. Bỏ qua tra cứu CEM.")
        cem_client = None

    # -------------------------------------------------------------------------
    # BƯỚC 2: VÒNG LẶP XỬ LÝ CUỐN CHIẾU TỪNG THUÊ BAO
    # -------------------------------------------------------------------------
    for ticket_idx, ticket in enumerate(unique_tickets, 1):
        title = ticket["title"]
        phone = ticket["phone"]

        # Lọc: Chỉ xử lý Mobile Internet, LOẠI TRỪ 'Gói cước Mobile Internet'
        title_lower = title.lower()
        if "gói cước mobile internet" in title_lower:
            print(f"⏭️ Bỏ qua dịch vụ: '{title}' ({phone})")
            continue

        is_valid_title = any(vt.lower() in title_lower for vt in valid_titles) or ("mobile internet" in title_lower and "gói cước" not in title_lower)
        if not is_valid_title:
            print(f"⏭️ Bỏ qua dịch vụ không thuộc Mobile Internet: '{title}' ({phone})")
            continue

        print(f"\n🔥 [{ticket_idx}/{len(unique_tickets)}] Xử lý số: {phone} | Gói: {title}")

        content = ticket.get("content", "").strip()
        if content:
            print(f"📝 Nội dung phản ánh ({len(content)} ký tự): {content[:80]}...")
        else:
            print(f"⚠️ [{phone}] Không có nội dung phản ánh trong dữ liệu cào!")

        # Chuẩn hóa số điện thoại chuẩn 84
        phone_84 = normalize_phone_vn(phone)

        # Chuyển sang tab BTools để cào dữ liệu
        driver.switch_to.window(btools_tab_handle)
        raw_btools_data = extract_btools_single_phone(driver, phone_84, start_d, end_d)
        clean_data = standardize_btools_data(raw_btools_data)

        # Lưu dữ liệu JSON vào thư mục number/
        output_dir = str(BASE_DIR / "number")
        os.makedirs(output_dir, exist_ok=True)
        json_filename = os.path.join(output_dir, f"{phone_84}.json")
        json_package = {
            "phone": phone_84,
            "package_title": title,
            "ticket_content": content,  
            "btools_technical_data": clean_data if clean_data else []
        }
        with open(json_filename, "w", encoding="utf-8") as jf:
            json.dump(json_package, jf, ensure_ascii=False, indent=4)

        # Tra SAPC + HSS Profile
        if sapc_client is not None:
            try:
                raw_sapc_data = sapc_client.query(phone_84)
                sapc_result = convert_sapc_response(raw_sapc_data)
            except Exception as e:
                print(f"⚠️ Lỗi tra SAPC cho {phone_84}: {e}")
                sapc_result = {"msisdn": phone_84, "packages": []}

            info_result = tra_cell_tu_so_dien_thoai(phone_84, session=sapc_client.session)

            hss_output_dir = str(BASE_DIR / "output")
            os.makedirs(hss_output_dir, exist_ok=True)
            hss_filename = os.path.join(hss_output_dir, f"{phone_84}.json")
            hss_package = {
                **sapc_result,
                "subscriber_info": info_result,
                "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(hss_filename, "w", encoding="utf-8") as hf:
                json.dump(hss_package, hf, ensure_ascii=False, indent=4)

        # Tóm tắt thông tin bằng AI / NLP Offline
        ai_summary = analyze_ticket_with_ai(json_filename)

        # 🎯 TRA CỨU DỮ LIỆU CEM (TOP 3 CELL BẮT SÓNG TRONG 5 NGÀY & APP USAGE 5 NGÀY)
        cem_records = []
        app_events = []
        try:
            from cem_client import CEMClient, save_cem_data_to_file
            if cem_client is None:
                cem_client = CEMClient(driver=driver)
            cem_records = cem_client.get_subscriber_history_5days(phone_84, days=5)
            cem_data_string = CEMClient.extract_top_cells_summary(cem_records)
            app_events = cem_client.get_subscriber_app_events(phone_84, days=5)
            app_usage_string = CEMClient.extract_top_apps_summary(app_events)

            # 💾 Lưu dữ liệu chi tiết CEM (Cell + App Usage 5 ngày) vào thư mục cem/
            save_cem_data_to_file(phone_84, cem_records, app_events, base_dir=BASE_DIR)
        except Exception as e:
            cem_data_string = f"Lỗi CEM: {e}"
        # 🎯 BÓC TÁCH THỜI ĐIỂM SỰ CỐ / TIẾP NHẬN
        from report_bot import extract_incident_time
        incident_time_string = extract_incident_time(content, ticket.get("created_time", ""))

        # Phân tích kỹ thuật & chuẩn đoán lỗi (kết hợp BTools + SAPC + CEM + App Usage + Mốc thời gian tiếp nhận)
        status, comment, action_plan, color = analyze_subscriber_status(
            clean_data, title, content, phone_84=phone_84, cem_records=cem_records, app_events=app_events, incident_time_str=incident_time_string
        )
        print(f"🧠 Bot nhận định kỹ thuật: [{status}]")

        # Thu thập thông tin hạ tầng kết nối
        unique_rats = list(set(str(row.get("RAT_TYPE_NAME", "")) for row in clean_data if row.get("RAT_TYPE_NAME")))
        rat_types_string = ", ".join(unique_rats) if unique_rats else "Không có dữ liệu"

        # Lọc mã gói hệ thống rác
        config_path = BASE_DIR / "diagnostic_config.json"
        excluded_system_codes = set()
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as cf:
                config_data = json.load(cf)
            excluded_system_codes = set(config_data.get("EXCLUDED_SYSTEM_CODES", []))
            
        real_package_names = set()
        for row in clean_data:
            s_code = str(row.get("SERVICE_ID_CODE", "")).strip()
            s_name = str(row.get("SERVICE_NAME", "")).strip()
            s_code_lower = s_code.lower()
            if s_code_lower and s_code_lower not in excluded_system_codes:
                s_name_lower = s_name.lower()
                if s_name and "gói cước lạ" not in s_name_lower and s_name_lower not in excluded_system_codes:
                    real_package_names.add(s_name)
                else:
                    real_package_names.add(s_code)
                    
        real_packages_string = ", ".join(list(real_package_names)) if real_package_names else "Không phát sinh gói TM"

        # 🎯 ĐƯA TOÀN BỘ GÓI CƯỚC SAPC (Tên gói, Ngày ĐK, HSD) VÀO CỘT GÓI CƯỚC THỰC TẾ
        final_packages_string = get_formatted_sapc_packages(phone_84, fallback_btools=real_packages_string)

        excel_summary_list.append({
            "phone": phone_84,
            "package_title": title,
            "incident_time": incident_time_string,
            "ticket_content": content,
            "created_time": ticket.get("created_time", ""),
            "real_packages": final_packages_string,
            "rat_types": rat_types_string,
            "cem_data": cem_data_string,
            "app_usage": app_usage_string,
            "status": status,
            "comment": comment,
            "action_plan": action_plan,
            "color": color,
            "ai_summary": ai_summary if ai_summary else "null"
        })

        # Lưu tạm định kỳ phòng timeout
        if ticket_idx % CHECKPOINT_EVERY == 0:
            os.makedirs(result_dir, exist_ok=True)
            export_diagnostics_to_excel(excel_summary_list, excel_name, start_d, end_d)
            print(f"🛟 [CHECKPOINT] Đã lưu tạm {len(excel_summary_list)}/{len(unique_tickets)} bản ghi.")

    # Quay về tab mẹ TTS
    driver.switch_to.window(tts_tab_handle)

    saved_excel_file = None
    if excel_summary_list:
        os.makedirs(result_dir, exist_ok=True)
        saved_excel_file = export_diagnostics_to_excel(excel_summary_list, excel_name, start_d, end_d)
        print(f"\n📊 Báo cáo Excel hoàn tất: '{saved_excel_file}'")
        
        if args.open_excel and saved_excel_file and os.path.exists(saved_excel_file):
            print("⚙️ Đang mở file báo cáo Excel...")
            os.startfile(saved_excel_file)
    else:
        print("\n⚠️ Không có dữ liệu để kết xuất báo cáo Excel.")

    # Trả tab TTS về URL ban đầu
    driver.switch_to.window(tts_tab_handle)
    driver.get("https://tts.vnpt.vn/#/xl-xu-ly-su-co/xu-ly-su-co-new")
    time.sleep(3)

    # -------------------------------------------------------------------------
    # BƯỚC 3: TỰ ĐỘNG CẬP NHẬT VÀ ĐÓNG PHIẾU TRÊN TTS (NẾU CÓ CỜ)
    # -------------------------------------------------------------------------
    if (args.auto_close or args.dry_run or args.observe) and saved_excel_file:
        print("\n================================================================")
        print("🚀 BẮT ĐẦU QUY TRÌNH TỰ ĐỘNG CẬP NHẬT & ĐÓNG PHIẾU TTS 🚀")
        print("================================================================")
        from update_tts.run import run_update_tts
        run_update_tts(
            excel_path=saved_excel_file,
            dry_run=(args.dry_run or args.observe),
            observe=args.observe
        )

    # 🧹 Dọn dẹp đóng các tab trống rác
    try:
        from tab_cleaner import close_blank_tabs
        close_blank_tabs(driver)
    except Exception:
        pass

    print("\n✅ TOÀN BỘ TIẾN TRÌNH ĐÃ HOÀN TẤT THÀNH CÔNG!")


if __name__ == "__main__":
    main()