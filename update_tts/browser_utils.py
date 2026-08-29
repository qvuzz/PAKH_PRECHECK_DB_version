# update_tts/browser_utils.py
# Kết nối vào Chrome debug đang sống + tìm đúng tab TTS

from playwright.sync_api import sync_playwright
from . import config


def connect_to_chrome(playwright):
    """Attach vào Chrome debug đang chạy sẵn qua CDP. Không tự mở Chrome mới."""
    browser = playwright.chromium.connect_over_cdp(config.DEBUG_PORT_URL)
    return browser


def find_tts_page(context):
    """Tìm tab đang mở sẵn TTS trong context hiện tại."""
    for pge in context.pages:
        if config.TTS_DOMAIN_HINT in pge.url:
            return pge
    return None


def get_context(browser):
    return browser.contexts[0] if browser.contexts else browser.new_context()