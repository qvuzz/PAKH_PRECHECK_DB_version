# update_deploy_zip.py
import zipfile
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

zip_path = "VNPT_TTS_PRECHECK_DEPLOY.zip"
tmp_path = "VNPT_TTS_PRECHECK_DEPLOY.zip.tmp"
source_dir = "VNPT TTS PRECHECK"

files_to_update = {
    "services/auth_tts.py": os.path.join(source_dir, "services", "auth_tts.py"),
    "services/state.py": os.path.join(source_dir, "services", "state.py"),
    "services/tts_new_data.py": os.path.join(source_dir, "services", "tts_new_data.py"),
    "services/tts_new_voice.py": os.path.join(source_dir, "services", "tts_new_voice.py"),
    "docker-compose.yml": os.path.join(source_dir, "docker-compose.yml"),
    "routers/tickets.py": os.path.join(source_dir, "routers", "tickets.py"),
    "routers/auth.py": os.path.join(source_dir, "routers", "auth.py"),
    "static/js/dashboard.js": os.path.join(source_dir, "static", "js", "dashboard.js"),
    "templates/dashboard.html": os.path.join(source_dir, "templates", "dashboard.html"),
    "region_detector.py": os.path.join(source_dir, "region_detector.py"),
    "ttsnew_api.py": os.path.join(source_dir, "ttsnew_api.py"),
    "crawler_btools.py": os.path.join(source_dir, "crawler_btools.py"),
    "cem_client.py": os.path.join(source_dir, "cem_client.py"),
    "db_manager.py": os.path.join(source_dir, "db_manager.py"),
    "sapccheck/msisdn_info.py": os.path.join(source_dir, "sapccheck", "msisdn_info.py"),
    "sapccheck/__init__.py": os.path.join(source_dir, "sapccheck", "__init__.py"),
    ".env": os.path.join(source_dir, ".env"),
    "tickets.db": os.path.join(source_dir, "tickets.db"),
    "start.sh": os.path.join(source_dir, "start.sh"),
    "DANH_MUC_KICH_BAN_DONG_PHIEU_MOBILE_INTERNET.xlsx": os.path.join(source_dir, "DANH_MUC_KICH_BAN_DONG_PHIEU_MOBILE_INTERNET.xlsx")
}

print("=== Đang cập nhật gói ZIP triển khai ===")
with zipfile.ZipFile(zip_path, 'r') as zin, zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
    written = set()
    for item in zin.infolist():
        fname = item.filename.replace("\\", "/")
        if fname in files_to_update:
            src_file = files_to_update[fname]
            if os.path.exists(src_file):
                print(f" -> Cập nhật: {fname} (từ {src_file})")
                zout.write(src_file, fname)
                written.add(fname)
            else:
                zout.writestr(item, zin.read(item.filename))
        else:
            zout.writestr(item, zin.read(item.filename))
    
    # Ghi những file mới nếu chưa có trong zip
    for fname, src_file in files_to_update.items():
        if fname not in written and os.path.exists(src_file):
            print(f" -> Thêm mới: {fname}")
            zout.write(src_file, fname)

os.replace(tmp_path, zip_path)
print("=== Cập nhật file ZIP thành công 100%! ===")
