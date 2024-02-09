import pandas as pd
import os
import wget
from selenium import webdriver
from bs4 import BeautifulSoup
import sys

sys.path.append("/Users/juankostelec/Google_drive/Projects/tax_backend/src")

from parser.text_parser import parse_pdf
from database.vector_store import add_text_to_vector_store as add_text_to_vector_store
from selenium.webdriver.support.ui import WebDriverWait


FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx"]
ROOT_URL = "https://www.fu.gov.si"
MAIN_URL = ROOT_URL + "/podrocja"
SRC_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/src"
METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/data"
RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/data/raw_files"
PROCESSED_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/data/processed_files"


def get_website_html(file_url):
    driver = webdriver.Chrome()
    try:
        driver.get(file_url)
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        print(f"Problem getting the website html of URL : {file_url}. Error: ", e)
        soup = None
    driver.close()
    return soup


def get_pdf_source_url(file_url, soup):
    # By checking the html of the website, we can see that the pdf file is in the <div id="fileBtns"> element for the
    # data from PiSRS website
    if soup is None:
        return None
    div_element = soup.find("div", id="fileBtns")
    if div_element:
        a_elements = div_element.find_all("a", href=True)
        for a in a_elements:
            href_value = a.get("href")
            complete_url_path = os.path.join(file_url.rsplit("/", maxsplit=1)[0], href_value)
            if href_value.endswith("pdf"):
                return complete_url_path
    print("Could not find the pdf file in the <div id='fileBtns'> element")
    return None


def get_resource_title(soup):
    # In the PiSRS website the title is given by the <h1> element
    if soup is None:
        return None
    h1_element = soup.find("h1")
    if h1_element:
        return "".join(
            char
            for char in h1_element.text
            if char.isalnum() or char.isspace() or char == ")" or char == "(" or char == "-"
        ).strip()
    else:
        print("Could not find the title of the law (i.e the <h1> element)")
        return None


def get_pisrs_data(data: pd.DataFrame, db=None, embeddings=None):
    total_rows = len(data)
    for i, (_, row) in enumerate(data[["file_url"]].iterrows()):
        if i % 10 == 9:
            print(f"Processing file {i}/{total_rows}")
        soup = get_website_html(row["file_url"])
        pdf_resource_title = get_resource_title(soup)
        pdf_source_url = get_pdf_source_url(row["file_url"], soup)

        if pdf_source_url:
            raw_data_save_path = os.path.join(RAW_DATA_DIR, f"{pdf_resource_title}.pdf")
            processed_pdf_save_path = os.path.join(PROCESSED_DATA_DIR, f"{pdf_resource_title}.txt")
            if not os.path.exists(raw_data_save_path):
                print(f"Downloading pdf file of law: {pdf_resource_title} from website {pdf_source_url}")
                wget.download(pdf_source_url, raw_data_save_path)

            if not os.path.exists(processed_pdf_save_path):
                print(f"Parsing pdf file of law: {pdf_resource_title}")
                parse_pdf(raw_data_save_path, processed_pdf_save_path, pdf_resource_title)
        else:
            print(f"Could not find pdf file for law: {pdf_resource_title} from website {row['file_url']}")

    return


# I need 4 objects: RawReferences, Scraper, Parser, VectorStore
if __name__ == "__main__":
    get_pisrs_data(pd.read_csv(os.path.join(METADATA_DIR, "furs_data.csv")))
