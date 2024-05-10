from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import sys
import backoff
import signal
import logging

from selenium.common.exceptions import WebDriverException, TimeoutException
from playwright.sync_api import sync_playwright
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

FILE_EXTENSIONS = [
    "docx",
    "doc",
    "pdf",
    "zip",
    "xlsx",
    "xls",
    "ppt",
    "pptx",
    "csv",
    "txt",
    "rtf",
    "odt",
    "ods",
]


def get_chrome_driver(local=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument(
        "--no-sandbox"
    )  # Bypass OS security model, REQUIRED for Docker. Use with caution.
    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems.
    chrome_options.add_argument("--disable-gpu")  # Applicable to windows os only
    chrome_options.add_argument("start-maximized")  #
    chrome_options.add_argument("disable-infobars")
    chrome_options.add_argument("--disable-extensions")

    if local:
        sys.path.append(
            "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chromedriver/mac_arm-121.0.6167.85/chromedriver-mac-arm64/chromedriver"  # noqa: E501
        )
        browser_path = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chrome/mac_arm-121.0.6167.85/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"  # noqa: E501
        chrome_options.binary_location = browser_path

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def wait_for_app_root_or_default(driver, timeout=5, default_wait=10):
    try:
        # Wait for the <app-root> element to be present in the DOM
        app_root = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "app-root"))
        )
        # Once the element is present, check if it has content
        WebDriverWait(driver, timeout).until(
            lambda d: app_root.get_attribute("innerHTML").strip() != ""
        )
    except TimeoutException:
        # If the <app-root> element is not found or has no content within the timeout,
        # apply the default wait
        print("Waiting for the default period as <app-root> is not populated.")
        driver.implicitly_wait(default_wait)


@backoff.on_exception(
    backoff.expo, (ConnectionError, WebDriverException, TimeoutException), max_tries=5, max_time=20
)
def get_website_html(file_url, driver=None, close_driver=True, wait_app_root=False):
    if driver is None:
        driver = get_chrome_driver(local=False)
    try:
        driver.get(file_url)
        if wait_app_root:
            wait_for_app_root_or_default(driver)
        else:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
    except (ConnectionError, WebDriverException, TimeoutException) as e:
        print(f"Problem getting the website html of URL : {file_url}. Error: ", e)
        raise  # Re-raise the exception for backoff to catch
    except Exception as e:
        print(f"Unexpected error getting the website html of URL : {file_url}. Error: ", e)
        soup = None
    finally:
        if close_driver:
            driver.close()
    return soup


def is_url_to_file(url):
    for file_extension in FILE_EXTENSIONS:
        if str(url).endswith(file_extension):
            return True
    return False


def make_title_safe(title):
    title = (
        str(title)
        .strip()
        .replace(" ", "_")
        .replace("(", "-")
        .replace(")", "_")
        .replace("/", "_")
        .replace("\xa0", "_")
    )
    if not title[-1].isalnum():
        title = title[:-1]

    return title[:100]  # Max 100 characters the length of the title


def get_filetype(path):
    path = str(path)
    if path.endswith(".pdf"):
        return "pdf"
    elif path.endswith(".docx"):
        return "docx"
    elif path.endswith(".doc"):
        return "doc"
    elif path.endswith(".xlsx"):
        return "xlsx"
    elif path.endswith(".xls"):
        return "xls"
    elif path.endswith(".csv"):
        return "csv"
    elif path.endswith(".zip"):
        return "zip"
    elif path.endswith(".html"):
        return "html"
    else:
        return "unknown"


def get_request_url_from_button_click(website_url, button_html_signature):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        request_urls = []

        # Start capturing network requests
        def handle_request(request):
            print("Request made:", request.url)
            request_urls.append(request.url)

        page.on("request", handle_request)

        page.goto(website_url)
        page.wait_for_selector(button_html_signature, state="attached")
        page.click(button_html_signature)  # Selector for the PDF download button
        page.wait_for_timeout(10000)  # Wait for 5 seconds to capture the request
        browser.close()

    for url in request_urls:
        # The format of request seems to be: https://pisrs.si/api/datoteke/integracije/36058941
        if "api/datoteke/" in url:
            return url


def handler(signum, frame):
    print("Segmentation fault caught, retrying...")
    raise RuntimeError("Segmentation fault")


def recover_from_segmentation_fault(fn, max_attempts=5):
    attempts = 0
    while attempts < max_attempts:
        try:
            # Set the signal handler for segmentation faults
            signal.signal(signal.SIGSEGV, handler)
            fn()
            break  # If the operation is successful, exit the loop
        except RuntimeError:
            attempts += 1
            if attempts == max_attempts:
                print("Failed after maximum retries")
                raise
            continue


# Function to suppress logging
def suppress_logging():
    logger = logging.getLogger()
    current_level = logger.getEffectiveLevel()
    logger.setLevel(logging.WARNING)
    return current_level


# Function to restore logging
def restore_logging(previous_level):
    logger = logging.getLogger()
    logger.setLevel(previous_level)
