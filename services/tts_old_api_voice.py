# services/tts_old_api_voice.py
# Chu kỳ quét & tiền kiểm Thoại / SMS / Gói trên Hệ Thống TTS Cũ qua REST API siêu tốc

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

from services.state import state, normalize_phone_vn
from db_manager import save_or_update_ticket, sync_active_tickets_state, get_db_connection
from tts_old_api import extract_token_from_browser, fetch_tts_old_tickets_api, fetch_nguyen_nhan_list_api, close_tts_old_ticket_api
import update_tts.config as tts_config
import update_tts.excel_reader as excel_reader


def execute_tts_old_api_voice_cycle(driver=None):
    """
    Thực hiện quét & tiền kiểm danh sách phiếu Thoại / SMS / Gói trên TTS Cũ qua REST API.
    Không tóm tắt AI (lưu trực tiếp nội dung phản ánh khách hàng).
    """
    if state.status == "PROCESSING":
        state.log("WARN", "Hệ thống đang bận thực hiện chu kỳ khác.")
        return 0

    state.status = "PROCESSING"
    state.stop_requested = False
    state.status_message = "Đang quét phiếu Thoại / SMS qua REST API TTS Cũ..."
    state.log("STEP", "📞 [TTS CŨ REST API - VOICE/SMS] Khởi động quét danh sách sự cố ngoài Data...")

    try:
        # 1. Trích xuất token từ Chrome hoặc cache
        token, user_info = extract_token_from_browser(driver)
        if not token:
            state.log("ERROR", "❌ Không tìm thấy token 'scnntttoken' của TTS Cũ. Vui lòng mở và đăng nhập tab tts.vnpt.vn trên Chrome.")
            return 0

        user_id = user_info.get("Id") or user_info.get("id") or 0
        nguyen_nhan_map = fetch_nguyen_nhan_list_api(token)

        # 2. Quét danh sách phiếu qua REST API
        state.current_step = "Đang tải danh sách phiếu Thoại/SMS từ REST API..."
        raw_tickets = fetch_tts_old_tickets_api(token, limit=250)

        # Lọc các phiếu KHÔNG thuộc Mobile Internet
        voice_tickets = [t for t in raw_tickets if t.get("service_type") != "data"]

        if not voice_tickets:
            state.log("WARN", "ℹ️ Trên hệ thống TTS Cũ hiện tại không có phiếu Thoại / SMS / Gói nào đang chờ xử lý.")
            sync_active_tickets_state([], source="tts_old_api", key_type="phone", service_type="voice_sms")
            return 0

        state.log("SUCCESS", f"⚡ REST API phát hiện {len(voice_tickets)} phiếu Thoại / SMS / Gói cước. Đang nạp nhanh lên bảng...")

        # Bước 1: Nạp nhanh toàn bộ phiếu vào Database trước
        active_phones = set()
        for t in voice_tickets:
            phone_84 = t.get("phone", "")
            if not phone_84:
                continue
            active_phones.add(phone_84)
            inc_time = t.get("incident_time") or ""
            rec = {
                "phone": phone_84,
                "incident_time": inc_time,
                "package_title": t.get("title", "Thoại / SMS"),
                "ticket_content": t.get("content", ""),
                "status": "",
                "real_packages": "--",
                "rat_types": "--",
                "cem_data": "--",
                "app_usage": "--",
                "ai_summary": t.get("content", ""),
                "comment": "",
                "action_plan": "",
                "ticket_status": "Chưa đóng",
                "source": "tts_old_api",
                "created_time": t.get("created_time") or inc_time,
                "ticket_id": t.get("ticket_id"),
                "flow_id": str(t.get("id_yeu_cau") or ""),
                "ticket_code": t.get("ma_ccos") or t.get("MaCCOS") or ""
            }
            save_or_update_ticket(rec)

        if active_phones:
            sync_active_tickets_state(active_phones, source="tts_old_api", key_type="phone", service_type="voice_sms")

        state.log("SUCCESS", f"🎉 Đã nạp thành công {len(voice_tickets)} phiếu Thoại / SMS / Gói cước lên bảng! Chế độ On-Demand: Bấm '⚡ Tiền kiểm Core' trên từng thuê bao khi cần tra cứu.")
        return len(voice_tickets)

    except Exception as e:
        state.log("ERROR", f"Lỗi chu kỳ quét REST API Thoại/SMS TTS Cũ: {e}")
        return 0
    finally:
        state.current_step = "Hoàn tất chu kỳ"
        if not state.is_running:
            state.status = "IDLE"
            state.status_message = "Sẵn sàng"
