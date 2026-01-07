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
    options.binary_location = "/usr/bin/chromium"
    
    # ✅ 타임아웃 완화를 위한 로드 전략 수정
    options.page_load_strategy = 'eager' 
    
    mobile_emulation = {
        "deviceMetrics": { "width": 500, "height": 915, "pixelRatio": 3.0 },
        "userAgent": "Mozilla/5.0 (Linux; Android 14; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }
    options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # ✅ 내부 통신 타임아웃 연장 (초 단위)
    driver.set_page_load_timeout(180)
    driver.set_script_timeout(180)
    return driver

st.title("🌐 사이트 통합 저장 도구")
uploaded_file = st.file_uploader("sites.xlsx 업로드", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    if st.button("🚀 작업 시작"):
        target_sites = dict(zip(df['URL'], df['업체명']))
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_save_path = f"result_{now_str}"
        os.makedirs(base_save_path, exist_ok=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        driver = get_driver()
        
        try:
            status_text.text("🔑 로그인 중...")
            driver.get('https://kissinfo.co.kr/yc/bbs/login.php')
            time.sleep(5)
            driver.find_element(By.NAME, "mb_id").send_keys('saturn')
            driver.find_element(By.NAME, "mb_password").send_keys('3022')
            driver.find_element(By.XPATH, "//button[text()='로그인']").click()
            time.sleep(5)

            for i, (url, site_name) in enumerate(target_sites.items()):
                try: # ✅ 개별 사이트 에러 방어막
                    status_text.text(f"⏳ {site_name} 처리 중... ({i+1}/{len(target_sites)})")
                    
                    img_dir_name = f"{site_name}_images"
                    img_dir_path = os.path.join(base_save_path, img_dir_name)
                    os.makedirs(img_dir_path, exist_ok=True)

                    driver.get(url)
                    time.sleep(10) # 충분한 로딩 대기

                    # DOM 편집
                    driver.execute_script("""
                        var target = document.evaluate("//*[contains(text(), '최근 후기')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                        if (target) {
                            var prev = target.previousElementSibling;
                            var brCount = 0;
                            while (prev && (prev.tagName === 'BR' || prev.innerText.trim() === '')) {
                                brCount++;
                                var toDelete = prev; prev = prev.previousElementSibling;
                                if (brCount > 3) toDelete.remove();
                            }
                            var next = target.nextElementSibling;
                            while (next) { var temp = next.nextElementSibling; next.remove(); next = temp; }
                            target.remove();
                        }
                        document.querySelectorAll('script').forEach(s => s.remove());
                    """)

                    # 이미지 저장
                    img_tags = driver.find_elements(By.TAG_NAME, "img")
                    for j, img in enumerate(img_tags):
                        try:
                            src = img.get_attribute("src")
                            if src and not src.startswith('data:'):
                                ext = os.path.splitext(src.split('?')[0])[1] or '.jpg'
                                img_name = f"img_{j}{ext}"
                                resp = requests.get(src, timeout=15)
                                if resp.status_code == 200:
                                    with open(os.path.join(img_dir_path, img_name), 'wb') as f: f.write(resp.content)
                                    driver.execute_script(f"arguments[0].src = '{img_dir_name}/{img_name}';", img)
                        except: continue

                    with open(os.path.join(base_save_path, f"{site_name}.html"), "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                
                except Exception as site_err:
                    st.warning(f"⚠️ {site_name} 건너뜀 (오류: {site_err})")
                
                progress_bar.progress((i + 1) / len(target_sites))

            # ✅ 압축 및 다운로드 버튼 (위치 수정)
            status_text.text("📦 결과물 압축 중...")
            shutil.make_archive(base_save_path, 'zip', base_save_path)
            
            with open(f"{base_save_path}.zip", "rb") as fp:
                st.download_button(
                    label="📂 결과물 ZIP 다운로드",
                    data=fp,
                    file_name=f"results_{now_str}.zip",
                    mime="application/zip"
                )
            st.success("✨ 완료! 위 버튼을 눌러 다운로드하세요.")

        except Exception as e:
            st.error(f"❌ 중명 오류: {str(e)}")
        finally:
            driver.quit()
