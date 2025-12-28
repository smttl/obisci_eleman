import time
import json
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# =================== AYARLAR ====================
OBIS_LOGIN_URL = "https://obis1.selcuk.edu.tr/"
OBIS_GRADES_URL = "https://obis1.selcuk.edu.tr/Ogrenci/SonYilNotlari"

WHATSAPP_NOTIFY_GROUP = "SÜ VETFAK 4/B"
WHATSAPP_ERROR_GROUP = "Kütüp"

CHECK_INTERVAL_SECONDS = 150 
STATE_FILE = "last_grades.json"

# Mac Mini için Chrome Profil Yolu (Kendi kullanıcı adını yazmalısın, aşağıda otomatik alıyor)
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "selenium_whatsapp_obis_data")
# =================================================

def load_last_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_state(grades):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(grades, f, ensure_ascii=False, indent=2)

def setup_driver():
    options = webdriver.ChromeOptions()
    # Oturumu kaydetmek için profil yolu
    options.add_argument(f"user-data-dir={USER_DATA_DIR}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.maximize_window()
    return driver

def login_checks(driver):
    """İlk açılışta kontrolleri yapar."""
    # 1. OBİS Kontrolü
    driver.get(OBIS_GRADES_URL)
    time.sleep(3)
    if "Login" in driver.title or "Giriş" in driver.page_source:
        print("\n🔴 OBİS Oturumu kapalı. Lütfen giriş yapıp ENTER'a bas.")
        driver.get(OBIS_LOGIN_URL)
        input("Giriş yaptıktan sonra ENTER'a bas...")
    else:
        print("🟢 OBİS oturumu zaten açık.")

    # 2. WhatsApp Kontrolü
    driver.execute_script("window.open('https://web.whatsapp.com', '_blank');")
    time.sleep(3)
    driver.switch_to.window(driver.window_handles[-1])
    
    print("🔵 WhatsApp kontrol ediliyor...")
    time.sleep(5)
    # Eğer QR kod ekranı varsa bekle
    try:
        if driver.find_elements(By.CSS_SELECTOR, "canvas"):
            print("QR Kod bekleniyor. Okutunca ENTER'a bas.")
            input()
    except:
        pass
    print("🟢 WhatsApp hazır.")

def get_current_grades(driver):
    driver.get(OBIS_GRADES_URL)
    time.sleep(5)

    if "Login" in driver.title or "Giriş" in driver.page_source:
        return "SESSION_CLOSED"

    rows = driver.find_elements(By.CSS_SELECTOR, "#dynamic-table tbody tr")
    grades = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 10:
            continue

        ders_adi = cols[2].text.strip()
        
        # Notları türüyle beraber alıyoruz ki Final girilince fark edilsin
        notlar = [
            (cols[4].text.strip(), "Vize 1"),
            (cols[5].text.strip(), "Vize 2"),
            (cols[6].text.strip(), "Vize 3"),
            (cols[7].text.strip(), "Vize 4"),
            (cols[8].text.strip(), "Final"),
            (cols[9].text.strip(), "Büt")
        ]

        for not_degeri, not_turu in notlar:
            if not_degeri:
                # Unique ID oluşturuyoruz: DersAdı + SınavTürü
                grades.append({
                    "id": f"{ders_adi}_{not_turu}",
                    "ders": ders_adi,
                    "tur": not_turu,
                    "not": not_degeri
                })

    return grades

def select_group_and_send(driver, group_name, messages):
    """Grubu bulur ve mesajları atar."""
    try:
        # WhatsApp sekmesine geç
        whatsapp_tab = [w for w in driver.window_handles if "WhatsApp" in driver.title or "web.whatsapp" in driver.current_url]
        if not whatsapp_tab:
            # Sekme kapandıysa tekrar aç
            driver.execute_script("window.open('https://web.whatsapp.com', '_blank');")
            time.sleep(10)
            whatsapp_tab = driver.window_handles[-1]
        else:
            driver.switch_to.window(whatsapp_tab[0])

        time.sleep(2)
        
        # Arama kutusu
        search_box = driver.find_element(By.XPATH, "//div[@contenteditable='true' and @role='textbox']")
        search_box.click()
        search_box.clear() # Ctrl+A Del gerekebilir bazen ama şimdilik clear
        time.sleep(1)
        search_box.send_keys(group_name)
        time.sleep(2)
        search_box.send_keys(Keys.ENTER)
        time.sleep(2)

        # Mesaj kutusu
        input_box = driver.find_elements(By.XPATH, "//div[@contenteditable='true' and @role='textbox']")[-1]
        
        for msg in messages:
            input_box.click()
            input_box.send_keys(msg)
            input_box.send_keys(Keys.ENTER)
            time.sleep(1)
            print(f"📤 Gönderildi: {msg}")

    except Exception as e:
        print(f"Mesaj gönderme hatası: {e}")

def diff_new_grades(old, new):
    # ID'leri karşılaştır (DersAdı + SınavTürü)
    old_ids = {g["id"] for g in old}
    return [g for g in new if g["id"] not in old_ids]

def main():
    last_grades = load_last_state()
    driver = setup_driver()

    # Giriş ve Hazırlık
    login_checks(driver)

    obis_tab = driver.window_handles[0]
    
    print(f"\n🟢 Bot Aktif. {CHECK_INTERVAL_SECONDS} saniyede bir kontrol edilecek.\n")

    while True:
        try:
            # OBİS sekmesine geç
            driver.switch_to.window(obis_tab)
            current_grades = get_current_grades(driver)

            if current_grades == "SESSION_CLOSED":
                print("⚠️ OBİS Oturumu düştü!")
                select_group_and_send(driver, WHATSAPP_ERROR_GROUP, ["⚠️ OBİS OTURUMU KAPANDI! Lütfen tekrar giriş yap."])
                
                # Kullanıcı müdahalesi bekle
                driver.switch_to.window(obis_tab)
                driver.get(OBIS_LOGIN_URL)
                # Burada input ile durdurmuyoruz, loop dönsün, kullanıcı görünce girsin.
                time.sleep(60) 
                continue

            new_ones = diff_new_grades(last_grades, current_grades)

            if new_ones:
                msgs_to_send = []
                for g in new_ones:
                    ders_upper = g["ders"].upper()
                    
                    if ders_upper in ["VETERİNER HEKİM HALK SAĞLIĞI", "VETERİNER HEKİMLİĞİ HALK SAĞLIĞI"]:
                        msgs_to_send.append("VHS GİRDİ")
                        msgs_to_send.append("pardon girildi")
                    else:
                        msgs_to_send.append(f"📢 {g['ders']} - {g['tur']} açıklandı.")

                if msgs_to_send:
                    select_group_and_send(driver, WHATSAPP_NOTIFY_GROUP, msgs_to_send)

                last_grades = current_grades
                save_state(last_grades)
            else:
                print(f"[{time.strftime('%H:%M')}] Yeni not yok.")

            time.sleep(CHECK_INTERVAL_SECONDS)

        except Exception as e:
            print(f"Beklenmeyen hata: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()