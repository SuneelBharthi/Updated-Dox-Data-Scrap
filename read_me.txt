This automated web scraping script is designed to extract comprehensive product data from Box.co.uk using Selenium and BeautifulSoup. The script reads product URLs from an Excel file and systematically collects structured information for each product, including:

Data Extracted:
Product Name & MPN – Captures the product title and manufacturer part number.

Pricing Information – Extracts the current and listed prices with VAT adjustments.

Breadcrumb Navigation – Retrieves the sub-category, child category, and grandchild categories to classify the product.

Tags – Gathers highlighted product tags such as "Bestseller" or "Clearance".

Key Features – Lists prominent product highlights from the UI.

Specifications – Dynamically expands and parses all specification tables, converting them into a structured JSON format.

FAQs – Extracts frequently asked questions and answers from the product page.

Images – Downloads up to four valid product images (ignoring videos or unsupported formats) and names them in a consistent format:

MPN-price.jpg (Thumbnail)

MPN-1-price.jpg, MPN-2-price.jpg, etc. (Additional Images)

💾 Output:
All scraped information is compiled into a structured Excel file, and product images are stored locally in a product_images/ folder. The Excel file is named dynamically based on the current timestamp to ensure uniqueness.

✅ Additional Features:
Robust error handling and logging

Visibility checks and dynamic waits for reliable element loading

JSON formatting for specs, tags, key features, and FAQs for easy integration into downstream systems