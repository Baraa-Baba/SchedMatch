import os
import json
import time
import traceback
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# Load environment variables
load_dotenv()

USERNAME = os.getenv("SIS_USERNAME")
PASSWORD = os.getenv("SIS_PASSWORD")
BASE_URL = "http://sis.hcu.edu.lb/secure/Student/Acad/CourseSchedule.aspx?sm=1"

if not USERNAME or not PASSWORD:
    print("Error: Credentials not found in .env file.")
    exit(1)

def get_driver():
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")
    options.set_capability("unhandledPromptBehavior", "accept")
    
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    return driver

def handle_alert(driver):
    try:
        WebDriverWait(driver, 3).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        print(f"Handling alert: {alert.text}")
        alert.accept()
        print("Alert accepted.")
    except TimeoutException:
        pass

def login(driver):
    print("Logging in...")
    driver.get(BASE_URL)
    handle_alert(driver)
    
    try:
        user_input_id = "_ctl0_PlaceHolderMain_Loginstu1_txtLoginUsername"
        pass_input_id = "_ctl0_PlaceHolderMain_Loginstu1_txtLoginPassword"
        login_btn_id = "_ctl0_PlaceHolderMain_Loginstu1_btnLoginLogin"
        
        try:
            user_input = driver.find_element(By.ID, user_input_id)
            print("Login form detected.")
            pass_input = driver.find_element(By.ID, pass_input_id)
            
            user_input.clear()
            user_input.send_keys(USERNAME)
            pass_input.clear()
            pass_input.send_keys(PASSWORD)
            
            login_btn = driver.find_element(By.ID, login_btn_id)
            login_btn.click()
            
            time.sleep(5)
            print("Login submitted.")
        except NoSuchElementException:
            print("No login form found with expected IDs. Assuming already logged in.")
            
    except Exception as e:
        print(f"Login process error: {e}")
        traceback.print_exc()
        driver.save_screenshot("login_error.png")
        raise e

def search_courses(driver):
    print(f"Searching for courses... Current URL: {driver.current_url}")
    
    if "CourseSchedule.aspx" not in driver.current_url:
        print("Navigating to Course Schedule page...")
        driver.get(BASE_URL)
        handle_alert(driver)
        time.sleep(3)
    
    print(f"Page Title: {driver.title}")
    
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_cbTerm")))
        term_select = Select(driver.find_element(By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_cbTerm"))
        term_select.select_by_value("155")
        
        status_radio = driver.find_element(By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_rbOC")
        status_radio.click()
        
        search_btn = driver.find_element(By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_btnSearch")
        search_btn.click()
        
        time.sleep(3)
    except Exception as e:
        print(f"Search failed: {e}")
        driver.save_screenshot("search_fail.png")
        raise e

def scrape_details_selenium(driver, link_element):
    prereqs = "None"
    try:
        try:
            link_element.click()
        except Exception:
            # Check for alert if click fails (e.g. unexpected alert open)
            try:
                alert = driver.switch_to.alert
                print(f"Alert present during click: {alert.text}")
                alert.accept()
            except:
                pass
            
            # If we are still on the same page, try clicking again
            if "CourseSchedule.aspx" in driver.current_url:
                 pass
        
        # Wait for details page
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Scrape
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if "Prerequisite" in body_text or "Corequisite" in body_text:
             lines = [line.strip() for line in body_text.split('\n') if line.strip()]
             found_prereqs = []
             for i, line in enumerate(lines):
                 if "Prerequisite" in line or "Corequisite" in line:
                     found_prereqs.append(line)
                     if i+1 < len(lines): found_prereqs.append(lines[i+1])
                     break
             prereqs = " | ".join(found_prereqs) if found_prereqs else "None"
        
        # Go Back
        driver.back()
        
        # Handle "Confirm Form Resubmission"
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except TimeoutException:
            pass
            
        # Wait for grid to reappear
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_CourseList")))
        except TimeoutException:
            print("Table not found after back. Refreshing...")
            driver.refresh()
            try:
                WebDriverWait(driver, 5).until(EC.alert_is_present())
                driver.switch_to.alert.accept()
            except TimeoutException:
                pass
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_CourseList")))
        
    except Exception as e:
        print(f"Error scraping details: {e}")
        # Try to recover: go back if not on search page
        try:
            if "CourseSchedule.aspx" not in driver.current_url:
                driver.back()
        except:
            pass
            
    return prereqs

def main():
    driver = get_driver()
    courses = []
    
    try:
        login(driver)
        search_courses(driver)
        
        page_num = 1
        while True:
            print(f"Processing page {page_num}...")
            
            # Find results table
            try:
                table = driver.find_element(By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_CourseList")
            except NoSuchElementException:
                print("Results table not found.")
                break
                
            # Get all rows (skip header)
            rows = table.find_elements(By.TAG_NAME, "tr")
            num_rows = len(rows)
            print(f"Found {num_rows} rows.")
            
            for i in range(1, num_rows): # Skip header usually index 0
                try:
                    # Re-find table and rows to avoid StaleElementReferenceException
                    try:
                        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_CourseList")))
                    except TimeoutException:
                        print("Table not found in main loop. Attempting to recover...")
                        driver.refresh()
                        try:
                            WebDriverWait(driver, 5).until(EC.alert_is_present())
                            driver.switch_to.alert.accept()
                        except TimeoutException:
                            pass
                        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_CourseList")))
                    
                    table = driver.find_element(By.ID, "_ctl0_PlaceHolderMain_CourseScheduleSearch1_CourseList")
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    
                    if i >= len(rows): break
                    
                    row = rows[i]
                    cols = row.find_elements(By.TAG_NAME, "td")
                    
                    if not cols: continue
                    
                    # Check if this is a course row
                    # Look for "Click for Details" link
                    try:
                        link = row.find_element(By.LINK_TEXT, "Click for Details")
                    except NoSuchElementException:
                        continue # Header or separator
                    
                    # Correct Column Mapping
                    code = cols[1].text.strip()
                    title = cols[2].text.strip()
                    credits = cols[5].text.strip() if len(cols) > 5 else "?"
                    
                    print(f"Scraping {code}...")
                    
                    # Click and scrape
                    prereqs = scrape_details_selenium(driver, link)
                    
                    course_info = {
                        "code": code,
                        "title": title,
                        "credits": credits,
                        "prerequisites": prereqs
                    }
                    courses.append(course_info)
                    
                except Exception as e:
                    print(f"Error processing row {i}: {e}")
                    traceback.print_exc()
            
            print(f"Finished page {page_num}. Total courses: {len(courses)}")
            
            # Next Page
            try:
                # Case insensitive check for Next button
                next_btn = driver.find_element(By.XPATH, "//a[contains(translate(text(), 'NEXT', 'next'), 'next')]")
                next_btn.click()
                time.sleep(5) # Wait for page load
                page_num += 1
            except NoSuchElementException:
                print("No Next button found. End of results.")
                break
            except Exception as e:
                print(f"Error clicking Next: {e}")
                break
                
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
    finally:
        driver.quit()
        
    with open("courses.json", "w") as f:
        json.dump(courses, f, indent=4)
    print(f"Scraped {len(courses)} courses. Saved to courses.json")

if __name__ == "__main__":
    main()
