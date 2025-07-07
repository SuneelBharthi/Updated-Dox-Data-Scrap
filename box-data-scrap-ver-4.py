import pandas as pd 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import threading
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import traceback
import time
import requests
import os
from datetime import datetime
import json
import logging

def handle_cookie_popup(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="onetrust-accept-btn-handler"]'))
        ).click()
        print("✅ Cookie popup accepted.")
    except Exception as e:
        print("⚠️ No cookie popup or already accepted.")


def handle_newsletter_popup(driver):
    try:
        # Wait up to 8 seconds for popup if it appears
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "No thanks")]'))
        ).click()
        print("✅ Newsletter popup dismissed.")
    except:
        print("⚠️ No newsletter popup appeared.")
 
# Logging setup
log_file = f"scraping_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

MAX_RETRIES = 3

def get_chrome_options():
    options = Options()
    #options.add_argument("--headless=new")  # 👈 Comment this line to see browser
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return options

# Thread function
def scrape_product_thread(link):
    with semaphore:  # Limit active threads
        product_data = scrape_with_retries(link)
        if product_data:
            with lock:
                scraped_data.append(product_data)
        else:
            with lock:
                failed_links.append(link)


# Thread-safe list lock
lock = threading.Lock()
MAX_THREADS = 5  # You can increase or decrease this based on your system capacity
semaphore = threading.Semaphore(MAX_THREADS)

# Read the Excel file containing product page links
file_path = 'Box_Links.xlsx'  # Update the file path if needed
df = pd.read_excel(file_path)

def scrape_with_retries(product_link):
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"🔁 Attempt {attempt} for {product_link}")
        result = scrape_product_page(product_link)
        if result:
            return result
        time.sleep(2)  # Short pause before retrying
    print(f"❌ Failed after {MAX_RETRIES} attempts: {product_link}")
    return None


# Wait function to handle elements
def wait_for_element(driver, xpath_selector):
    try:
        WebDriverWait(driver, 30).until(  # Increased the timeout to 30 seconds
            EC.presence_of_element_located((By.XPATH, xpath_selector))  # Wait for element presence first
        )
        WebDriverWait(driver, 30).until(  # Additional wait for visibility
            EC.visibility_of_element_located((By.XPATH, xpath_selector))
        )
    except Exception as e:
        logger.error(f"Exception while waiting for element [{xpath_selector}]: {e}")
        logger.error(traceback.format_exc())

# Main scraping function per thread
def scrape_product_page(product_link):
    options = get_chrome_options()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=get_chrome_options())
    wait = WebDriverWait(driver, 20)

    try:
        driver.get(product_link)
        logger.info(f"Scraping {product_link}")
        handle_cookie_popup(driver)      # Existing cookie handler
        handle_newsletter_popup(driver)  # Dismiss newsletter popup

        # Wait for required elements
        product_name_path = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section/div/div[1]/div[2]/div[1]/h1'
        product_mpn_path = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section/div/div[1]/div[2]/div[1]/div[1]/span'
        product_price_path = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/div/div[1]/div[2]/div[1]/div[3]/div/div[1]/div[1]/span'
        product_list_price_path = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/div/div[1]/div[2]/div[1]/div[3]/div/div[2]/span'
        breadcrumb_path = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section/app-breadcrumbs/div/div/div/div'
        image_base_xpath = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/div/div[1]/div[1]/div/app-custom-pdp-swiper/div[2]/div[2]/div/div[2]/div'
        tags_xpath = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/div/div[1]/div[2]/div[1]/div[2]'

        # Wait for elements
        wait_for_element(driver, product_name_path)
        wait_for_element(driver, product_mpn_path)
        wait_for_element(driver, product_price_path)
        wait_for_element(driver, product_list_price_path)
        wait_for_element(driver, breadcrumb_path)
        wait_for_element(driver, tags_xpath)

        for i in range(4):
            wait_for_element(driver, f"{image_base_xpath}[{i+1}]/img")

        # Extract core product info
        product_name = driver.find_element(By.XPATH, product_name_path).text
        product_mpn = driver.find_element(By.XPATH, product_mpn_path).text.replace("MPN:", "").strip()
        product_price = driver.find_element(By.XPATH, product_price_path).text.replace(" INC VAT", "").strip()
        product_list_price = driver.find_element(By.XPATH, product_list_price_path).text
        if "SAVE" in product_list_price:
            product_list_price = product_list_price.split(" SAVE")[0].strip()
        product_list_price = product_list_price.replace("was", "").strip()

        # Breadcrumbs
        sub_category, child_category, grand_child_categories = process_breadcrumbs(driver)

        # Download up to 4 images
        image_names = []
        for idx in range(4):
            try:
                image_xpath = f"{image_base_xpath}[{idx+1}]/img"
                image_url = driver.find_element(By.XPATH, image_xpath).get_attribute('src')
                image_name = download_image(image_url, product_mpn, None if idx == 0 else idx, "price")
                image_names.append(image_name)
            except Exception as e:
                logger.warning(f"⚠️ Failed to get image at index {idx+1}: {e}")
                image_names.append(None)

        # Scrape additional details
        tags = scrape_tags(driver)
        key_features = scrape_key_features(driver)
        specifications = scrape_specifications(driver, wait)
        faqs = scrape_faqs(driver)

        return {
            "Link": product_link,
            'Product Name': product_name,
            'Product MPN': product_mpn,
            'Product Current Price': product_price,
            'Product List Price': product_list_price,
            'Sub Category': sub_category,
            'Child Category': child_category,
            'Grand Child Categories': grand_child_categories,
            'Thumbnail_Image': image_names[0],
            'Additional_Image_1': image_names[1],
            'Additional_Image_2': image_names[2],
            'Additional_Image_3': image_names[3],
            'Tags': json.dumps(tags),
            'Key_Features': key_features,
            'Specifications': specifications,
            'FAQs': faqs
        }

    except Exception as e:
        logger.error(f"❌ Error scraping {product_link}: {e}")
        logger.error(traceback.format_exc())
        return None
    finally:
        driver.quit()


# Function to process breadcrumbs
def process_breadcrumbs(driver):
    breadcrumb_section_xpath = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/app-breadcrumbs/div/div/div'  # Breadcrumb container
    try:
        breadcrumb_elements = driver.find_elements(By.XPATH, breadcrumb_section_xpath + '/div/a')
        
        sub_category = breadcrumb_elements[1].text.strip() if len(breadcrumb_elements) > 1 else None
        child_category = breadcrumb_elements[2].text.strip() if len(breadcrumb_elements) > 2 else None
        grand_child_categories = [breadcrumb_elements[i].text.strip() for i in range(3, len(breadcrumb_elements))]

        if sub_category and '>' in sub_category:
            sub_category = sub_category.split('>')[-1].strip()
        if child_category and '>' in child_category:
            child_category = child_category.split('>')[-1].strip()

        grand_child_categories = [text.strip() for text in grand_child_categories if '>' not in text]
        
        return sub_category, child_category, grand_child_categories

    except Exception as e:
        logger.error(f"Error retrieving breadcrumbs: {e}")
        return None, None, []

# Function to scrape specifications dynamically from tables

def scrape_specifications(driver, wait):
    specifications = {}

    try:
        # Step 1: Scroll to and Click the Specifications tab
        spec_tab_xpath = '//*[@id="accordion"]/p-accordion/div/p-accordiontab[2]'
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, spec_tab_xpath)))
            spec_tab = driver.find_element(By.XPATH, spec_tab_xpath)
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", spec_tab)
            time.sleep(1)
            if not spec_tab.get_attribute("aria-expanded") == "true":
                spec_tab.click()
                time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Error clicking spec tab: {e}")
            specifications["Specs"] = "Specs tab not clickable"
            return json.dumps(specifications, indent=4)

        # Step 2: Wait for content to load
        spec_main_header_xpath = '//*[@id="index-1_header_action"]/span[2]'
        spec_main_div_xpath = '//*[@id="index-1_content"]/div/div'
        wait.until(EC.presence_of_element_located((By.XPATH, spec_main_header_xpath)))
        wait.until(EC.presence_of_element_located((By.XPATH, spec_main_div_xpath)))

        # Step 3: Get main header
        main_header = driver.find_element(By.XPATH, spec_main_header_xpath).text.strip()
        specifications["MainHeader"] = main_header
        specifications["Specs"] = []

        # Step 4: Scrape spec tables
        tables = driver.find_elements(By.XPATH, spec_main_div_xpath + '/table')
        headers = driver.find_elements(By.XPATH, spec_main_div_xpath + '/p')

        for i, table in enumerate(tables):
            title = headers[i].text.strip() if i < len(headers) else f"Table {i+1}"
            table_data = []

            for row in table.find_elements(By.TAG_NAME, "tr"):
                columns = row.find_elements(By.TAG_NAME, "td")
                if len(columns) == 2:
                    key = columns[0].text.strip()
                    value = columns[1].text.strip()
                    if key and value:
                        table_data.append({"Key": key, "Value": value})

            if table_data:
                specifications["Specs"].append({"Header": title, "Attributes": table_data})

        # Step 5: If no data found
        if not specifications["Specs"]:
            specifications["Specs"] = "No specifications found"

    except Exception as e:
        logger.error(f"❌ Error retrieving specifications: {e}")
        specifications = {"Specs": "Error retrieving specifications"}

    return json.dumps(specifications, indent=4)


# Function to download and save images
def download_image(image_url, product_mpn, img_count=None, image_type="price"):
    try:
        img_data = requests.get(image_url).content
        img_folder = "product_images"
        os.makedirs(img_folder, exist_ok=True)

        # 🛠️ Fix: Avoid double hyphen when img_count is None
        if img_count is None:
            img_name = f"{product_mpn}-{image_type}.jpg".lower()  # ✅ Correct: NX.KTDEK.002-price.jpg
        else:
            img_name = f"{product_mpn}-{img_count}-{image_type}.jpg".lower()  # ✅ Correct: NX.KTDEK.002-1-price.jpg

        img_path = os.path.join(img_folder, img_name)
        with open(img_path, 'wb') as f:
            f.write(img_data)
        logger.info(f"✅ Downloaded: {img_name}")
        return img_name
    except Exception as e:
        logger.error(f"❌ Failed to download image: {e}")
        return None

# Function to scrape tags
def scrape_tags(driver):
    tags = []
    try:
        tags_section_xpath = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[1]/div/div[1]/div[2]/div[1]/div[2]'
        toast_elements = driver.find_elements(By.XPATH, tags_section_xpath + '/div/app-product-toast')
        
        for toast_element in toast_elements:
            toast_text = toast_element.find_element(By.XPATH, './div/span').text.strip()
            if toast_text:
                tags.append(toast_text)
        
        if not tags:
            tags.append("N/A")
        
        return {"Tags": tags}
    except Exception as e:
        logger.error(f"Error retrieving tags: {e}")
        return {"Tags": "Error retrieving tags"}

# Function to scrape Key Features

def scrape_key_features(driver):
    key_features = []
    try:
        # Main container for features
        features_div_xpath = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section/div/div[1]/div[2]/div[3]/div[2]'
        wait_for_element(driver, features_div_xpath)

        # Now find all <li> elements under the <ul> list
        feature_items_xpath = features_div_xpath + '/ul/li'
        feature_elements = driver.find_elements(By.XPATH, feature_items_xpath)

        for el in feature_elements:
            text = el.text.strip()
            if text:
                key_features.append(text)

        if not key_features:
            key_features = ["N/A"]

        return json.dumps({"Key_Feature": key_features}, indent=4)

    except Exception as e:
        print(f"❌ Exception while scraping key features: {e}")
        return json.dumps({"Key_Feature": ["Error retrieving features"]}, indent=4)

def scrape_faqs(driver):
    faqs = []
    try:
        # Scroll and wait for FAQ section
        faq_section_xpath = '//*[@id="maincontent"]/app-dynamic-page/app-pdp/section[3]'
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, faq_section_xpath))
        )
        faq_heading = driver.find_element(By.XPATH, faq_section_xpath)
        driver.execute_script("arguments[0].scrollIntoView(true);", faq_heading)
        time.sleep(2)

        # Click and expand all accordion tabs
        tabs_xpath = "//p-accordiontab//a"
        tabs = driver.find_elements(By.XPATH, tabs_xpath)
        for tab in tabs:
            driver.execute_script("arguments[0].click();", tab)
            time.sleep(0.4)

        # Get page source and parse with BeautifulSoup
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # Only capture the last section (actual FAQs)
        all_sections = soup.find_all('p-accordiontab')
        ignore_titles = {"Product Overview", "Specifications", "From Manufacturer"}
        for tab in all_sections:
            title = tab.find('span', class_='p-accordion-header-text')
            answer_block = tab.find('div', {'role': 'region'})
            if title and answer_block:
                q = title.get_text(strip=True)
                a = answer_block.get_text(strip=True)

                if q not in ignore_titles:
                    faqs.append({"Question": q, "Answer": a})

        if not faqs:
            faqs.append({"Question": "N/A", "Answer": "No FAQs found"})

        return {"FAQs": faqs}

    except Exception as e:
        logger.error(f"Error locating FAQ section: {e}")
        return {"FAQs": [{"Question": "N/A", "Answer": "FAQ section not found"}]}


# Data list to store all scraped product data
scraped_data = []
failed_links = []


# Launch threads
threads = []
for link in df['Links']:
    thread = threading.Thread(target=scrape_product_thread, args=(link,))
    thread.start()
    threads.append(thread)

for t in threads:
    t.join()
    # Save failed links if any
if failed_links:
    failed_df = pd.DataFrame({'Failed_Links': failed_links})
    failed_filename = f"failed_links_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
    failed_df.to_excel(failed_filename, index=False)
    print(f"❗ Saved failed links to {failed_filename}")
    logger.warning(f"❗ {len(failed_links)} product(s) failed and saved to: {failed_filename}")

 

# Save all data after all threads finish
current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
output_filename = f"scraped_product_data_{current_time}.xlsx"

scraped_df = pd.DataFrame(scraped_data)
scraped_df.to_excel(output_filename, index=False)
logger.info(f"✅ Data saved to {output_filename}")