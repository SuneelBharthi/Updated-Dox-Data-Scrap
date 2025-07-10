import pandas as pd 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
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
        WebDriverWait(driver, 40).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="onetrust-accept-btn-handler"]'))
        ).click()
        print("✅ Cookie popup accepted.")
    except Exception as e:
        print("⚠️ No cookie popup or already accepted.")

def handle_newsletter_popup(driver):
    try:
        script = """
        const popup = document.querySelector("#mcforms-92356-113983");
        if (popup && popup.shadowRoot) {
            const closeBtn = popup.shadowRoot.querySelector("#el_bYfcVA1AUwL");
            if (closeBtn) {
                closeBtn.click();
                return "✅ Closed newsletter popup.";
            } else {
                return "❌ Close button not found inside shadow DOM.";
            }
        } else {
            return "❌ Popup or shadowRoot not found.";
        }
        """
        result = driver.execute_script(script)
        print(result)
        time.sleep(3)
    except Exception as e:
        print(f"❌ Exception while handling newsletter popup: {e}")


# Logging setup
log_file = f"scraping_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

MAX_RETRIES = 2

def get_chrome_options():
    options = Options()
    options.add_argument("--headless=new")  # ✅ Stable headless mode
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return options

 

# Read the Excel file containing product page links
file_path = 'Box_Links.xlsx'  
df = pd.read_excel(file_path)


invalid_links = set()
def scrape_with_retries(product_link):
    for attempt in range(1, 3):  # Max 2 retries
        logger.info(f"🔁 Attempt {attempt} for {product_link}")
        result = scrape_product_page(product_link)
        if result:
            return result
        time.sleep(3)  # Short pause before retrying
    logger.error(f"❌ Failed after 2 attempts: {product_link}")
    return None


# Wait function to handle elements
def wait_for_element(driver, xpath_selector):
    try:
        WebDriverWait(driver, 90).until(  # Wait for element presence
            EC.presence_of_element_located((By.XPATH, xpath_selector))
        )
        WebDriverWait(driver, 90).until(  # Additional wait for visibility
            EC.visibility_of_element_located((By.XPATH, xpath_selector))
        )
    except Exception as e:
        logger.error(f"Exception while waiting for element [{xpath_selector}]: {e}")
        logger.error(traceback.format_exc())

def scroll_to_bottom(driver):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")    # Scroll down to load all content on the page
    time.sleep(3) 
    driver.execute_script("window.scrollTo(0, 0);")                             # Scroll up to the top of the page
    time.sleep(3) 

# Main scraping function per thread
def scrape_product_page(product_link):
    options = get_chrome_options()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=get_chrome_options())
    wait = WebDriverWait(driver, 60)

    try:
        driver.get(product_link)
        scroll_to_bottom(driver)
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
        category, sub_category, child_categories = process_breadcrumbs(driver)

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
            'Category': category,
            'Sub Category': sub_category,
            'Child Categories': child_categories,
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
        
        category = breadcrumb_elements[1].text.strip() if len(breadcrumb_elements) > 1 else None
        sub_category = breadcrumb_elements[2].text.strip() if len(breadcrumb_elements) > 2 else None
        child_categories = [breadcrumb_elements[i].text.strip() for i in range(3, len(breadcrumb_elements))]

        if category and '>' in category:
            category = category.split('>')[-1].strip()
        if sub_category and '>' in sub_category:
            sub_category = sub_category.split('>')[-1].strip()

        child_categories = [text.strip() for text in child_categories if '>' not in text]
        
        return category, sub_category, child_categories

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
            time.sleep(5)
            if not spec_tab.get_attribute("aria-expanded") == "true":
                spec_tab.click()
                time.sleep(3)
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
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.XPATH, faq_section_xpath))
        )
        faq_heading = driver.find_element(By.XPATH, faq_section_xpath)
        driver.execute_script("arguments[0].scrollIntoView(true);", faq_heading)
        time.sleep(5)

        # Click and expand all accordion tabs
        tabs_xpath = "//p-accordiontab//a"
        tabs = driver.find_elements(By.XPATH, tabs_xpath)
        for tab in tabs:
            driver.execute_script("arguments[0].click();", tab)
            time.sleep(3)

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

def validate_product_link(product_link):
    """
    This method checks whether the given product link contains a valid 'Product Overview' section
    and returns a boolean indicating whether the link is a valid product page or not.
    """
    options = get_chrome_options()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 40)  # Increased wait time

    try:
        driver.get(product_link)
        handle_cookie_popup(driver)      # Existing cookie handler
        handle_newsletter_popup(driver)
        logger.info(f"Visiting: {product_link}")

        # Wait for main content to load
        try:
            wait_for_element(driver, '//*[@id="maincontent"]/app-dynamic-page')
            logger.info("✅ Main content loaded")
        except Exception as e:
            logger.error(f"❌ Main content failed to load: {e}")
            return False

        # Check for "Product Overview" text (flexible XPath)
        product_overview_xpath = '//*[contains(text(), "Product Overview")]'
        try:
            wait_for_element(driver, product_overview_xpath)
            logger.info("✅ Product Overview found!")
            return True
        except Exception as e:
            logger.error(f"❌ Product Overview section not found: {e}")
            return False  # Product Overview section not found

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return False
    finally:
        driver.quit()

scraped_links_file = "scraped_links.txt"
# Load already scraped links into a set
if os.path.exists(scraped_links_file):
    with open(scraped_links_file, "r") as f:
        already_scraped_links = set(line.strip() for line in f.readlines())
else:
    already_scraped_links = set()

# Data list to store all scraped product data
# Data list to store all scraped product data
scraped_data = []
failed_links = []

# Progress bar with tqdm
for link in tqdm(df['Links'], desc="🔍 Scraping product pages"):
    print(f"🔄 Scraping: {link}")
    try:
        product_data = scrape_with_retries(link)
        if product_data:
            scraped_data.append(product_data)
            logger.info(f"✅ Scraped successfully: {link}")
        else:
            failed_links.append(link)
            logger.warning(f"⚠️ Failed to scrape: {link}")
    except Exception as e:
        failed_links.append(link)
        logger.error(f"❌ Exception occurred on link: {link}")
        logger.error(traceback.format_exc())

# Save all data
current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
output_filename = f"scraped_product_data_{current_time}.xlsx"
scraped_df = pd.DataFrame(scraped_data)
scraped_df.to_excel(output_filename, index=False)
logger.info(f"✅ Data saved to {output_filename}")

# ⚠️ Save failed links to a text file
if failed_links:
    with open('failed_links.txt', 'w') as f:
        for link in failed_links:
            f.write(link + '\n')
    print("⚠️ Failed links saved to 'failed_links.txt'")
    logger.warning(f"{len(failed_links)} links failed. See 'failed_links.txt'.")
else:
    print("✅ No failed links.")

# Save successfully scraped links
with open(scraped_links_file, "a") as f:
    for item in scraped_data:
        f.write(item['Link'] + "\n")