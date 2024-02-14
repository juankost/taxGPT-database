from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from bs4 import BeautifulSoup
import sys

FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx", "xls", "ppt", "pptx", "csv", "txt", "rtf", "odt", "ods"]


def get_website_html(file_url, driver=None, close_driver=True):
    if driver is None:
        sys.path.append(
            "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chromedriver/mac_arm-121.0.6167.85/chromedriver-mac-arm64/chromedriver"
        )
        browser_path = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chrome/mac_arm-121.0.6167.85/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        option = webdriver.ChromeOptions()
        option.binary_location = browser_path
        driver = webdriver.Chrome(options=option)

    try:
        driver.get(file_url)
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"Problem getting the website html of URL : {file_url}. Error: ", e)
        soup = None
    if close_driver:
        driver.close()
    return soup


def is_url_to_file(url):
    for file_extension in FILE_EXTENSIONS:
        if str(url).endswith(file_extension):
            return True
    return False


def make_title_safe(title):
    title = str(title).strip().replace(" ", "_").replace("(", "-").replace(")", "_").replace("/", "_")
    if not title[-1].isalnum():
        title = title[:-1]
    return title
