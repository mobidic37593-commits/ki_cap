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

# --- 셀레니움 드라이버 설정 (안정화 모드) ---
def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # ✅ 핵심: 네트워크 포트 대신 파이프를 사용하여 로컬 통신 타임아웃 방지
    options.add_argument('--remote-debugging-pipe')
    
    # ✅ 리소스 최적화: 불필요한 이미지/애니메이션 로딩 방지
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.page_load_strategy = 'eager'
    
    options.binary_location = "/usr/bin/chromium"
    
    mobile_emulation = {
        "deviceMetrics": { "width": 500, "height": 915, "pixelRatio": 3.0 },
        "userAgent": "Mozilla/5.0 (Linux; Android 14; SM-S938B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    }
    options.add_experimental_option("mobileEmulation", mobile_emulation)
    
    # ✅ webdriver-manager 설정
    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    
    driver = webdriver.Chrome(service=service, options=options)
    
    # ✅ 타임아웃 제한을 5분으로 확장
    driver.set_page_load_timeout(300)
    driver.set_script_timeout(300)
    return driver

# --- 메인 UI ---
st.set_page_config(page_title="Site Capture Tool", layout="wide")
st.title("🌐 사이트 HTML & 이미지 통합 저장 도구")
st.info("최근 후기 위쪽으로 공백을 3개로 제한하고, 모든 스크립트를 제거한 정적 HTML과 원본 이미지를 추출합니다.")

uploaded_file = st.file_uploader("업체 리스트(sites.xlsx) 업로드", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.write("📋 업로드된 데이터 (상위 5개):", df.head())
    
    if st.button("🚀 작업 시작"):
        target_sites = dict(zip(df['URL'], df['업체명']))
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_save_path = f"result_{now_str}"
        os.makedirs(base_save_path, exist_ok=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        driver = get_driver()
        
        try:
            # 1. 로그인 단계
            status_text.text("🔑 로그인 중...")
            driver.get('https://kissinfo.co.kr/yc/bbs/login.php')
            time.sleep(5)
            driver.find_element(By.NAME, "mb_id").send_keys('saturn')
            driver.find_element(By.NAME, "mb_password").send_keys('3022')
            driver.find_element(By.XPATH, "//button[text()='로그인']").click()
            time.sleep(5)

            # 2. 개별 사이트 순회
            for i, (url, site_name) in enumerate(target_sites.items()):
                try:
                    status_text.text(f"⏳ [{i+1}/{len(target_sites)}] {site_name} 처리 중...")
                    
                    # ✅ 개별 페이지 접속 시도 시 타임아웃 예외 처리 강화
                    driver.get(url)
                    time.sleep(10) # 렌더링을 위한 물리적 대기시간 확보

                    # ✅ DOM 편집: 후기 삭제, 공백 제한, 스크립트 제거
                    driver.execute_script("""
                        var target = document.evaluate("//*[contains(text(), '최근 후기')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                        if (target) {
                            var prev = target.previousElementSibling;
                            var brCount = 0;
                            while (prev && (prev.tagName === 'BR' || prev.innerText.trim() === '')) {
                                brCount++;
                                var toDelete = prev;
                                prev = prev.previousElementSibling;
                                if (brCount > 3) toDelete.remove();
                            }
                            var next = target.nextElementSibling;
                            while (next) {
                                var temp = next.nextElementSibling;
                                next.remove();
                                next = temp;
                            }
                            target.remove();
                        }
                        // 모든 스크립트 제거
                        document.querySelectorAll('script').forEach(s => s.remove());
                        // 인라인 이벤트 제거
                        document.querySelectorAll('*').forEach(el => {
                            for (var i = 0; i < el.attributes.length; i++) {
                                if (el.attributes[i].name.startsWith('on')) el.removeAttribute(el.attributes[i].name);
                            }
                        });
                    """)

                    # ✅ 이미지 다운로드 및 경로 수정
                    img_tags = driver.find_elements(By.TAG_NAME, "img")
                    for j, img in enumerate(img_tags):
                        try:
                            src = img.get_attribute("src")
                            if src and not src.startswith('data:'):
                                ext = os.path.splitext(src.split('?')[0])[1] or '.jpg'
                                img_name = f"img_{j}{ext}"
                                # 브라우저 밖에서 별도로 이미지 다운로드
                                resp = requests.get(src, timeout=15)
                                if resp.status_code == 200:
                                    with open(os.path.join(img_dir_path, img_name), 'wb') as f:
                                        f.write(resp.content)
                                    # HTML 내 경로를 로컬로 변경
                                    driver.execute_script(f"arguments[0].src = '{img_dir_name}/{img_name}';", img)
                        except:
                            continue

                    # 최종 HTML 파일 저장
                    final_html = driver.page_source
                    with open(os.path.join(base_save_path, f"{site_name}.html"), "w", encoding="utf-8") as f:
                        f.write(final_html)
                
                except Exception as site_err:
                    st.warning(f"⚠️ {site_name} 건너뜀: {str(site_err)}")
                
                progress_bar.progress((i + 1) / len(target_sites))

            # 3. 압축 및 다운로드 버튼 생성
            status_text.text("📦 압축 파일 생성 중...")
            zip_file_path = shutil.make_archive(base_save_path, 'zip', base_save_path)
            
            with open(zip_file_path, "rb") as fp:
                st.download_button(
                    label="📂 결과물 ZIP 다운로드",
                    data=fp,
                    file_name=f"site_capture_{now_str}.zip",
                    mime="application/zip",
                    key="finish_btn"
                )
            st.success("✨ 모든 작업이 완료되었습니다! 위 버튼을 눌러 다운로드하세요.")

        except Exception as inner_e:
                    st.warning(f"⚠️ {site_name} 사이트 응답 지연으로 건너뜁니다.")
                    # 브라우저 세션 유지를 위해 가벼운 페이지로 이동 시도
                    driver.get("about:blank")
                    continue
        except Exception as e:
            st.error(f"❌ 치명적 오류 발생: {str(e)}")
        finally:
            driver.quit()

