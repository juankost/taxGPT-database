from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import sys
import os
from google.cloud import storage


FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx", "xls", "ppt", "pptx", "csv", "txt", "rtf", "odt", "ods"]


def get_chrome_driver(local=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")  # Bypass OS security model, REQUIRED for Docker. Use with caution.
    chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems.
    chrome_options.add_argument("--disable-gpu")  # Applicable to windows os only
    chrome_options.add_argument("start-maximized")  #
    chrome_options.add_argument("disable-infobars")
    chrome_options.add_argument("--disable-extensions")

    if local:
        sys.path.append(
            "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chromedriver/mac_arm-121.0.6167.85/chromedriver-mac-arm64/chromedriver"
        )
        browser_path = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chrome/mac_arm-121.0.6167.85/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
        chrome_options.binary_location = browser_path

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def get_website_html(file_url, driver=None, close_driver=True):
    if driver is None:
        driver = get_chrome_driver(local=False)
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


# Utils functions to save/load from the google storage bucket


def upload_folder_to_bucket(bucket_name, folder_path, destination_blob_folder):
    """Uploads a folder and its contents to the bucket, maintaining the folder structure."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    for local_file in os.listdir(folder_path):
        local_file_path = os.path.join(folder_path, local_file)

        # Skip directories, only upload files
        if os.path.isfile(local_file_path):
            # Construct the full path for the file within the bucket
            blob_name = os.path.join(destination_blob_folder, local_file)
            blob = bucket.blob(blob_name)

            # Upload the file
            blob.upload_from_filename(local_file_path)
            print(f"Uploaded {local_file} to {blob_name}.")


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")


def download_blob(bucket_name, source_blob_name, destination_file_name):
    """Downloads a blob from the bucket to a local file."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)

    blob.download_to_filename(destination_file_name)
    print(f"Blob {source_blob_name} downloaded to {destination_file_name}.")
