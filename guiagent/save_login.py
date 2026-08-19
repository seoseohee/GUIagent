"""로그인이 필요한 플랫폼용. 한 번 실행해서 직접 로그인하면 세션이 저장된다.

    python save_login.py
    → 브라우저 뜸 → 직접 로그인 → 터미널에서 Enter
    → auth.json 생성. config.STORAGE_STATE에 경로 넣으면 끝.
"""
from playwright.sync_api import sync_playwright

import config

with sync_playwright() as p:
    b = p.chromium.launch(headless=False)
    ctx = b.new_context(viewport=config.VIEWPORT, device_scale_factor=1)
    page = ctx.new_page()
    page.goto(config.START_URL)
    input("로그인 끝나면 여기서 Enter → ")
    ctx.storage_state(path="auth.json")
    print("auth.json 저장됨")
    b.close()
