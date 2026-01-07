import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
import time
import os
import requests
import shutil
from datetime import datetime

def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    # ✅ 리소스 최적화: 이미지 로딩 제외 (속도 향상 및 타임아웃 방지)
    # 이미지 파일은 requests로 따로 받으므로 브라우저 렌더링 시에는 제외해도 무방합니다.
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.binary_location = "/usr/bin/chromium"
    
    # ✅ 연결 유지 설정 강화
    options.add_argument('--remote-debugging-pipe') 
    options.page_load_strategy = 'none' # 페이지 로드를 기다리지 않고 즉시 제어권 획득
    
    mobile_emulation = {
        "deviceMetrics": { "width": 500, "height": 915, "pixelRatio": 3.0 },
        "userAgent": "Mozilla/5.0 (Linux; Android 14; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }
    options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # ✅ 타임아웃 값을 넉넉히 300초(5분)로 설정
    driver.set_page_load_timeout(300)
    return driver

st.title("🌐 사이트 통합 저장 도구 (안정화 모드)")

# ... (파일 업로드 및 로그인 로직 동일) ...

            for i, (url, site_name) in enumerate(target_sites.items()):
                try:
                    status_text.text(f"⏳ {site_name} 로딩 중... ({i+1}/{len(target_sites)})")
                    
                    # ✅ 사이트 접속 전 세션 체크 및 강제 타임아웃 방지용 더미 클릭 등 수행 가능
                    driver.get(url)
                    
                    # 'none' 전략을 사용하므로 수동으로 로딩 대기
                    # "최근 후기" 글자가 보일 때까지 최대 20초 대기
                    start_wait = time.time()
                    while time.time() - start_wait < 20:
                        if "최근 후기" in driver.page_source:
                            break
                        time.sleep(1)

                    # ✅ DOM 편집 및 이미지 다운로드 로직 수행 (이전과 동일)
                    # ... (생략) ...

                except Exception as site_err:
                    st.warning(f"⚠️ {site_name} 처리 중 지연 발생으로 건너뜁니다.")
                    # 브라우저가 먹통이 된 경우를 대비해 드라이버 재시작 고려 가능
                    continue 

# ... (압축 및 다운로드 버튼 로직 동일) ...
