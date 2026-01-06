import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By  # ✅ 누락되었던 By 추가
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType # ✅ 크롬 타입 지정용
import time
import os
import requests
import shutil
from datetime import datetime

# --- 셀레니움 설정 함수 ---
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # ✅ Streamlit Cloud(Debian) 환경의 크롬 경로 설정
    options.binary_location = "/usr/bin/chromium"
    
    mobile_emulation = {
        "deviceMetrics": { "width": 500, "height": 915, "pixelRatio": 3.0 },
        "userAgent": "Mozilla/5.0 (Linux; Android 14; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }
    options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    # ✅ webdriver-manager가 Chromium을 찾도록 설정
    driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    service = Service(driver_path)
    
    return webdriver.Chrome(service=service, options=options)

# --- 이하 로직은 동일 (By 모듈 오류 수정 포함) ---
st.set_page_config(page_title="Site Capture Tool", layout="wide")
st.title("🌐 사이트 HTML & 이미지 통합 저장 도구")

uploaded_file = st.file_uploader("업체 리스트(sites.xlsx) 업로드", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.write("✅ 업로드 완료:", df.head())
    
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
            time.sleep(3)
            # ✅ By.NAME 사용 시 오류 없도록 수정
            driver.find_element(By.NAME, "mb_id").send_keys('saturn')
            driver.find_element(By.NAME, "mb_password").send_keys('3022')
            driver.find_element(By.XPATH, "//button[text()='로그인']").click()
            time.sleep(5)

            for i, (url, site_name) in enumerate(target_sites.items()):
                status_text.text(f"⏳ 처리 중: {site_name} ({i+1}/{len(target_sites)})")
                
                img_dir_name = f"{site_name}_images"
                img_dir_path = os.path.join(base_save_path, img_dir_name)
                os.makedirs(img_dir_path, exist_ok=True)

                driver.get(url)
                time.sleep(7)

                # DOM 편집 로직 (이전과 동일)
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

                # 이미지 다운로드 및 로컬 경로 수정 (이전과 동일)
                img_tags = driver.find_elements(By.TAG_NAME, "img")
                for j, img in enumerate(img_tags):
                    src = img.get_attribute("src")
                    if not src or src.startswith('data:'): continue
                    try:
                        ext = os.path.splitext(src.split('?')[0])[1] or '.jpg'
                        img_name = f"img_{j}{ext}"
                        save_p = os.path.join(img_dir_path, img_name)
                        resp = requests.get(src, timeout=10)
                        if resp.status_code == 200:
                            with open(save_p, 'wb') as f: f.write(resp.content)
                            driver.execute_script(f"arguments[0].src = '{img_dir_name}/{img_name}';", img)
                    except: continue

                final_html = driver.page_source
                with open(os.path.join(base_save_path, f"{site_name}.html"), "w", encoding="utf-8") as f:
                    f.write(final_html)
                
                progress_bar.progress((i + 1) / len(target_sites))

            shutil.make_archive(base_save_path, 'zip', base_save_path)
            
            with open(f"{base_save_path}.zip", "rb") as fp:
                st.download_button(
                    label="📂 결과물 ZIP 다운로드",
                    data=fp,
                    file_name=f"{base_save_path}.zip",
                    mime="application/zip"
                )
            st.success("✨ 모든 작업이 완료되었습니다!")

        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
        finally:
            driver.quit()