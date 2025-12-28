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

# Bildirim grubu (sadece not mesajları)
WHATSAPP_NOTIFY_GROUP = "SÜ VETFAK 4/B"

# Hata & oturum kapanması mesajları
WHATSAPP_ERROR_GROUP = "Kütüp"

CHECK_INTERVAL_SECONDS = 150  # 2.5 dakika
STATE_FILE = "last_grades.json"
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
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.maximize_window()
    return driver


def login_obis(driver):
    """OBİS girişini kullanıcı manuel yapacak."""
    driver.get(OBIS_LOGIN_URL)
    time.sleep(5)

    print("\n🔵 Lütfen OBİS’e kendin giriş yap.")
    print("Kullanıcı adı, şifre ve toplama/çıkarma doğrulama sorusunu kendin doldur.")
    print("Giriş tamamlandığında ENTER'a bas → Bot devam edecek.\n")
    input()

    time.sleep(5)


def get_current_grades(driver):
    driver.get(OBIS_GRADES_URL)
    time.sleep(5)

    # Oturum kapanmış mı?
    if "Login" in driver.title or "Giriş" in driver.page_source:
        return "SESSION_CLOSED"

    rows = driver.find_elements(By.CSS_SELECTOR, "#dynamic-table tbody tr")
    grades = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 10:
            continue

        ders_adi = cols[2].text.strip()

        v1 = cols[4].text.strip()
        v2 = cols[5].text.strip()
        v3 = cols[6].text.strip()
        v4 = cols[7].text.strip()
        final = cols[8].text.strip()
        but = cols[9].text.strip()

        if v1: grades.append({"ders": ders_adi})
        if v2: grades.append({"ders": ders_adi})
        if v3: grades.append({"ders": ders_adi})
        if v4: grades.append({"ders": ders_adi})
        if final: grades.append({"ders": ders_adi})
        if but: grades.append({"ders": ders_adi})

    return grades


def open_whatsapp_tab(driver):
    driver.execute_script("window.open('https://web.whatsapp.com', '_blank');")
    time.sleep(3)
    driver.switch_to.window(driver.window_handles[1])

    print("🔵 WhatsApp Web açıldı. QR kodu tara.")
    print("Sohbetler yüklenince ENTER'a bas.")
    input()


def select_group(driver, group_name):
    """Her mesaj göndermeden önce doğru grubu seç."""
    time.sleep(1)
    search_box = driver.find_element(By.XPATH, "//div[@contenteditable='true' and @role='textbox']")
    search_box.click()
    time.sleep(1)
    search_box.clear()
    search_box.send_keys(group_name)
    time.sleep(5)

    chat = driver.find_element(By.XPATH, f"//span[@title='{group_name}']")
    chat.click()
    time.sleep(1)


def send_whatsapp_message(driver, text):
    box = driver.find_elements(By.XPATH, "//div[@contenteditable='true' and @role='textbox']")[-1]
    box.click()
    box.send_keys(text + Keys.ENTER)
    time.sleep(1)


def diff_new_grades(old, new):
    old_keys = {g["ders"] for g in old}
    return [g for g in new if g["ders"] not in old_keys]


def main():
    last_grades = load_last_state()
    driver = setup_driver()

    # OBİS'e manuel giriş
    login_obis(driver)

    # WhatsApp
    open_whatsapp_tab(driver)
    select_group(driver, WHATSAPP_NOTIFY_GROUP)

    obis_tab = driver.window_handles[0]
    whatsapp_tab = driver.window_handles[1]

    print("\n🟢 Bot çalışıyor... OBİS her 10 dakikada bir kontrol edilecek.\n")

    while True:
        try:
            driver.switch_to.window(obis_tab)
            current_grades = get_current_grades(driver)

            # Oturum kapanmışsa → sadece KÜTÜP grubuna mesaj
            if current_grades == "SESSION_CLOSED":
                driver.switch_to.window(whatsapp_tab)
                select_group(driver, WHATSAPP_ERROR_GROUP)
                send_whatsapp_message(driver, "⚠️ OBİS OTURUMU KAPANDI! Lütfen tekrar giriş yap.")

                driver.switch_to.window(obis_tab)
                print("\n🔵 OBİS ekranında tekrar giriş yap, doğrulama sorusunu çöz.")
                print("Giriş tamamlandıktan sonra ENTER'a bas.\n")
                input()
                continue

            # Yeni not kontrolü
            new_ones = diff_new_grades(last_grades, current_grades)

            if new_ones:
                driver.switch_to.window(whatsapp_tab)
                select_group(driver, WHATSAPP_NOTIFY_GROUP)

                for g in new_ones:
                    ders_upper = g["ders"].upper()

                    # VHS özel mesajı
                    if ders_upper in ["VETERİNER HEKİM HALK SAĞLIĞI", "VETERİNER HEKİMLİĞİ HALK SAĞLIĞI"]:
                        send_whatsapp_message(driver, "VHS GİRDİ")
                        send_whatsapp_message(driver, "pardon girildi")
                    else:
                        send_whatsapp_message(driver, f"{g['ders']} açıklandı.")

                last_grades = current_grades
                save_state(last_grades)

            else:
                print("Yeni not yok.")

            time.sleep(CHECK_INTERVAL_SECONDS)

        except Exception as e:
            print("Hata:", e)
            print("↻ Yeniden denenecek...")

            try:
                driver.switch_to.window(obis_tab)
                login_obis(driver)
            except:
                print("Bot durdu.")
                break


if __name__ == "__main__":
    main()
