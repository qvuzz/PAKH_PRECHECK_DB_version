# routers/cdr.py
# Router cung cấp API tra cứu lịch sử SMSC CDR (tích hợp từ cdrsearch)

from fastapi import APIRouter, Query
from services.smsc_cdr_client import fetch_smsc_cdr, WINSCP_PATH
import os

router = APIRouter(prefix="/api/cdr", tags=["Tra cứu SMSC CDR"])


@router.get("/status")
def get_cdr_integration_status():
    try:
        import paramiko
        has_paramiko = True
    except ImportError:
        has_paramiko = False

    has_winscp = os.path.exists(WINSCP_PATH)
    return {
        "success": True,
        "paramiko_available": has_paramiko,
        "winscp_available": has_winscp,
        "winscp_path": WINSCP_PATH,
        "elastic_target": "10.204.57.26",
        "sftp_target": "10.165.15.84 (VHKT Bridge)",
        "method": "paramiko_pure_python" if has_paramiko else ("winscp" if has_winscp else "elastic_direct")
    }


@router.get("/sms")
def get_sms_cdr(
    phone: str = Query(..., description="Số thuê bao cần tra cứu (vd: 84917969796)"),
    direction: str = Query("both", description="Chiều tin nhắn: 'both', 'mo' (gửi đi), 'mt' (nhận vào)"),
    hours: int = Query(48, description="Số giờ cần tra cứu lùi lại từ hiện tại (mặc định 48h)"),
    gte_time: str = Query(None, description="Mốc thời gian bắt đầu YYMMDDhhmmss"),
    lte_time: str = Query(None, description="Mốc thời gian kết thúc YYMMDDhhmmss"),
    from_date: str = Query(None, description="Từ ngày cụ thể (YYYY-MM-DD hoặc YYYY-MM-DD HH:mm:ss)"),
    to_date: str = Query(None, description="Đến ngày cụ thể (YYYY-MM-DD hoặc YYYY-MM-DD HH:mm:ss)"),
    limit: int = Query(100, description="Số lượng bản ghi tối đa (tối đa 10000)")
):
    if not phone or not phone.strip():
        return {
            "success": False,
            "total_hits": 0,
            "records": [],
            "message": "Vui lòng cung cấp số điện thoại cần tra cứu"
        }

    from_time = from_date or gte_time
    to_time = to_date or lte_time

    res = fetch_smsc_cdr(
        phone=phone.strip(),
        direction=direction,
        from_time_str=from_time,
        to_time_str=to_time,
        hours=hours,
        limit=limit
    )
    return res
