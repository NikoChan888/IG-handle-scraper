from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from urllib.parse import quote
import time
import json
from selenium.webdriver.common.keys import Keys
import random

class InstagramScraper:
    def __init__(self):
        # 設置Chrome瀏覽器選項
        self.options = webdriver.ChromeOptions()
        self.options.add_argument('--start-maximized')
        # self.options.add_argument('--headless')  # 無頭模式，取消註釋即可啟用
        
        # Add these options to help with stability
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_experimental_option('excludeSwitches', ['enable-logging'])

        # 初始化瀏覽器
        self.service = Service()
        self.driver = None
        self.wait = None

    def init_driver(self):
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.implicitly_wait(10)
            self.wait = WebDriverWait(self.driver, 10)
            return True
        except Exception as e:
            print(f"Driver initialization error: {str(e)}")
            return False

    def reconnect(self):
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass
        time.sleep(2)
        return self.init_driver()

    def login(self, username, password):
        """登入Instagram帳號"""
        try:
            # 前往登入頁面
            self.driver.get("https://www.instagram.com/accounts/login/")
            
            # 等待頁面加載
            time.sleep(3)  # 給予足夠時間加載頁面
            
            # 輸入用戶名
            username_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            username_input.send_keys(username)
            
            # 輸入密碼
            password_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.send_keys(password)
            
            # 點擊登入按鈕
            login_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            login_button.click()
            
            # 等待登入完成
            time.sleep(5)  # 給予足夠時間完成登入
            
            # 處理可能出現的"儲存登入資訊"對話框
            try:
                not_now_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button._acan._acap._acas._aj1-"))
                )
                not_now_button.click()
            except TimeoutException:
                pass  # 如果沒有出現對話框，就繼續執行
                
            print("登入成功！")
            return True
            
        except Exception as e:
            print(f"登入失敗: {str(e)}")
            return False

    def safe_click(self, element, max_retries=3):
        """Safely click an element with retries"""
        for attempt in range(max_retries):
            try:
                # Try to scroll the element into center view first
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"點擊失敗: {str(e)}")
                    return False
                time.sleep(1)
        return False

    def safe_close_dialog(self):
        """Safely close dialog with multiple selector attempts"""
        close_selectors = [
            "button[type='button']",
            "svg[aria-label='關閉']",
            "button._abl-",
            "div._ac7b button"
        ]
        
        for selector in close_selectors:
            try:
                close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for button in close_buttons:
                    try:
                        self.driver.execute_script("arguments[0].click();", button)
                        time.sleep(0.5)
                        return True
                    except:
                        continue
            except:
                continue
                
        # If normal close fails, try pressing ESC key
        try:
            webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
            return True
        except:
            pass
            
        return False

    def click_next_post(self):
        """Click the next post button in the dialog"""
        try:
            next_button = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "svg[aria-label='Next']"))
            )
            return self.safe_click(next_button)
        except:
            return False

    def click_next_button(self):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                next_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'svg[aria-label="Next"]'))
                )
                button = next_button.find_element(By.XPATH, "./ancestor::button")
                button.click()
                time.sleep(0.5)  # Reduced to 0.5 seconds
                return True
            except Exception as e:
                if "disconnected" in str(e) and attempt < max_retries - 1:
                    print("Connection lost, attempting to reconnect...")
                    if not self.reconnect():
                        print("Failed to reconnect")
                        return False
                    continue
                print(f"Error clicking next button (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    return False
                time.sleep(1)
        return False

    def get_existing_handles(self):
        try:
            with open('handles.txt', 'r') as f:
                return set(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            return set()

    def append_handle(self, handle):
        existing_handles = self.get_existing_handles()
        if handle not in existing_handles:
            with open('handles.txt', 'a') as f:
                f.write(handle + '\n')
            return True
        return False

    def scrape_hashtag(self, hashtag):
        error_count = 0
        max_errors = 5
        
        while error_count < max_errors:
            try:
                if not self.driver or not self.is_driver_alive():
                    print("Initializing new driver session...")
                    if not self.init_driver():
                        raise Exception("Failed to initialize driver")
                
                encoded_hashtag = quote(hashtag.replace('#', ''))
                url = f"https://www.instagram.com/explore/tags/{encoded_hashtag}/"
                self.driver.get(url)
                
                posters = set()
                first_post_clicked = False
                
                while True:
                    try:
                        # Click the first post only once at the start
                        if not first_post_clicked:
                            try:
                                first_post = self.wait.until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[role='link'][tabindex='0']"))
                                )
                                if self.safe_click(first_post):
                                    first_post_clicked = True
                                    time.sleep(1)
                                else:
                                    print("無法點擊第一個貼文，重試...")
                                    self.driver.refresh()
                                    time.sleep(2)
                                    continue
                            except:
                                print("等待第一個貼文超時，重試...")
                                self.driver.refresh()
                                time.sleep(2)
                                continue

                        # Keep clicking next and processing posts
                        while True:
                            try:
                                # Try multiple selectors for poster name
                                poster_name = None
                                selectors = [
                                    "header a.x1i10hfl",
                                    "header a[role='link']",
                                    "header h2"
                                ]
                                
                                for selector in selectors:
                                    try:
                                        poster_element = self.wait.until(
                                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                        )
                                        poster_name = poster_element.text
                                        if poster_name:
                                            break
                                    except:
                                        continue
                                
                                if poster_name and poster_name not in posters:
                                    posters.add(poster_name)
                                    if self.append_handle(poster_name):
                                        print(f"保存用戶名: {poster_name}")
                                    else:
                                        print(f"跳過重複用戶: {poster_name}")

                                # Click next button
                                if not self.click_next_button():
                                    print("無法點擊下一個貼文，重新整理頁面...")
                                    break
                                time.sleep(0.5)
                                
                            except Exception as e:
                                print(f"處理貼文時出錯: {str(e)}")
                                break

                        # After processing batch or on error, refresh the page
                        self.driver.refresh()
                        time.sleep(2)
                    
                    except Exception as e:
                        print(f"主循環出錯 (attempt {error_count}/{max_errors}): {str(e)}")
                        error_count += 1
                        if "disconnected" in str(e):
                            if not self.reconnect():
                                print("Failed to reconnect, stopping...")
                                break
                        if error_count >= max_errors:
                            print("錯誤次數過多，停止運行...")
                            break
                        time.sleep(2)

                print(f"\n爬取完成！共收集了 {len(posters)} 個獨特的用戶名")
                return posters
                
            except Exception as e:
                print(f"發生錯誤: {str(e)}")
                return set()

            finally:
                self.driver.quit()

    def is_driver_alive(self):
        try:
            self.driver.current_url
            return True
        except:
            return False

if __name__ == "__main__":
    scraper = InstagramScraper()
    
    # 登入Instagram
    username = input("username: ")
    password = input("password: ")
    
    if scraper.init_driver() and scraper.login(username, password):
        hashtag =  "#standupcomedy"
        scraper.scrape_hashtag(hashtag)
    else:
        print("由於登入失敗，無法繼續執行")
    
    scraper.driver.quit()