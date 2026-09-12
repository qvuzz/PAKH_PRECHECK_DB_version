# routers/web.py
# Phục vụ giao diện HTML Dashboard và các route SPA (/ttsmoi/data, /ttscu/data, v.v.)

import os
from pathlib import Path
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, FileResponse

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "templates" / "dashboard.html"

router = APIRouter(tags=["Web UI"])


def get_dashboard_html() -> str:
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Lỗi: Không tìm thấy file templates/dashboard.html</h1>"


# Danh sách các route SPA hiển thị giao diện Dashboard
SPA_ROUTES = [
    "/",
    "/index.html",
    "/ttscu/data",
    "/ttscu/voice",
    "/ttscu/mobileinternet",
    "/ttscu/voice_sms",
    "/ttsmoi/data",
    "/ttsmoi/mobileinternet",
    "/ttsmoi/voice",
    "/ttsmoi/voice_sms",
    "/ttsmoi/cuoc-goi",
    "/ttsmoi/call",
    "/ttsmoi/tin-nhan",
    "/ttsmoi/sms",
    "/ttsmoi/khac",
    "/ttsmoi/other",
    "/thong-ke",
    "/lich-su"
]

for route_path in SPA_ROUTES:
    @router.get(route_path, response_class=HTMLResponse, include_in_schema=(route_path == "/"))
    def serve_spa_page(request: Request):
        return HTMLResponse(content=get_dashboard_html(), status_code=200)


@router.get("/vnpt-logo.svg", include_in_schema=False)
def get_logo_svg():
    logo_path = BASE_DIR / "static" / "img" / "vnpt-logo.svg"
    if not logo_path.exists():
        logo_path = BASE_DIR / "vnpt-logo.svg"
    if logo_path.exists():
        return FileResponse(logo_path, media_type="image/svg+xml")
    return Response(status_code=404)


@router.get("/vnpt-logo-horizontal.svg", include_in_schema=False)
def get_logo_horizontal_svg():
    logo_path = BASE_DIR / "static" / "img" / "vnpt-logo-horizontal.svg"
    if not logo_path.exists():
        logo_path = BASE_DIR / "vnpt-logo-horizontal.svg"
    if logo_path.exists():
        return FileResponse(logo_path, media_type="image/svg+xml")
    return get_logo_svg()


@router.get("/favicon.ico", include_in_schema=False)
def get_favicon():
    return get_logo_svg()
