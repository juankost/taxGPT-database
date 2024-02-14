"""
This script crawls the fu.gov.si website and extracts all the references denoted there that cover most of the
areas of tax laws.
"""
import os
from selenium import webdriver
import pandas as pd
import sys
import wget

# from unstructured import partition_html
from langchain_community.document_transformers import Html2TextTransformer
from langchain_community.document_loaders import AsyncHtmlLoader

sys.path.append("/Users/juankostelec/Google_drive/Projects/taxGPT-database/app")
from utils import get_website_html, is_url_to_file, make_title_safe  # noqa: E402

FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx", "xls", "ppt", "pptx", "csv", "txt", "rtf", "odt", "ods"]


class Scraper:
    def __init__(self, references_data_path, output_dir):
        self.driver = webdriver.Chrome()
        self.references_data_path = references_data_path
        self.references_data = pd.read_csv(references_data_path)
        self.output_dir = output_dir
        self.aleady_downloaded_clean_links = []

    def download_all_references(self):
        """
        Downloads all references based on the provided references list.

        This method iterates over the references data and downloads the files or websites
        based on the URLs provided. It populates the `idx_to_download_info` dictionary
        with the download information for each reference.

        After downloading, it updates the `references_data` DataFrame with the download
        information and saves it to a CSV file.

        Returns:
            None
        """
        idx_to_download_info = {}  # idx: (actual_download_link, downloaded_location)
        for idx, row in self.references_data.iterrows():
            reference_href_clean = str(row["reference_href_clean"]).split("#")[0]
            details_href_clean = str(row["details_href"]).split("#")[0]

            if is_url_to_file(reference_href_clean):
                self.download_file(
                    reference_href_clean,
                    row["reference_name"],
                    idx,
                    idx_to_download_info,
                )
            elif is_url_to_file(details_href_clean):
                self.download_file(
                    details_href_clean,
                    row["details_href_name"],
                    idx,
                    idx_to_download_info,
                )
            elif details_href_clean != "nan":
                self.download_website(
                    details_href_clean,
                    row["details_href_name"],
                    idx,
                    idx_to_download_info,
                )
            else:
                self.download_website(
                    reference_href_clean,
                    row["reference_name"],
                    idx,
                    idx_to_download_info,
                )

        self.references_data[
            ["used_download_href", "actual_download_link", "actual_download_location"]
        ] = self.podrocja_list_with_links.index.map(idx_to_download_info)
        self.references_data.to_csv(self.references_data_path, index=False)

    def download_file(self, url_link, title, idx, idx_to_download_info):
        """
        Downloads a file from a given URL link and saves it to the output directory.

        Args:
            url_link (str): The URL link of the file to be downloaded.
            title (str): The title of the file.
            idx (int): The index of the file.
            idx_to_download_info (dict): A dictionary mapping file indices to download information.

        Returns:
            None
        """
        if url_link in self.already_downloaded_clean_links:
            actual_download_link_and_paths = [item[1] for item in idx_to_download_info.items() if item[0] == idx]
            idx_to_download_info[idx] = (url_link, *actual_download_link_and_paths[0])
            return

        # Determine the file extension type
        # The file extension will be given by the last part of url_link.
        # It will either be delineated by a dot or an equal sign
        file_extension = url_link.split(".")[-1]
        if "=" in file_extension:
            file_extension = file_extension.split("=")[-1]
        if file_extension not in FILE_EXTENSIONS:
            print("Could not download the file", url_link)
            return

        # Download the file
        saved_path = os.path.join(self.output_dir, make_title_safe(title) + "." + file_extension)
        if not os.path.exists(saved_path):
            print(f"Downloading file from {url_link}")
            try:
                wget.download(url_link, saved_path)

                # Now update the idx_to_download_info
                idx_to_download_info[idx] = (url_link, url_link, saved_path)

            except Exception as e:
                print(f"Could not download the file {url_link}. Error: ", e)

        return

    def download_website(self, url_link, title, idx, already_downloaded_clean_links, idx_to_download_info):
        if url_link in already_downloaded_clean_links:
            actual_download_link_and_paths = [item[1] for item in idx_to_download_info.items() if item[0] == idx]
            idx_to_download_info[idx] = (url_link, *actual_download_link_and_paths[0])
            return

        download_url_link = None
        saved_path = None
        if "eur-lex.europa.eu" in url_link:
            download_url_link, saved_path = ScrapeEURLex.download_custom_website(url_link, title, driver=self.driver)
            print("Need to download from eur-lex.europa.eu")
        elif ".uradni-list.si" in url_link:
            download_url_link, saved_path = ScrapeUradniList.download_custom_website(
                url_link, title, driver=self.driver
            )
            print("Need to download from uradni-list.si")
        elif ".pisrs.si" in url_link:
            download_url_link, saved_path = ScrapePISRS.download_custom_website(url_link, title, driver=self.driver)
        elif "fu.gov.si" in url_link:
            print("Need to download from fu.gov.si")
            download_url_link, saved_path = ScrapeGOVsi.download_custom_website(url_link, title, driver=self.driver)
        else:
            print("Need to download from other website: ", url_link)

        # Now update the idx_to_download_info
        idx_to_download_info[idx] = (url_link, download_url_link, saved_path)
        return


class ScrapePISRS(Scraper):
    @staticmethod
    def download_custom_website(url_link, title, output_dir, driver=None):
        """
        Downloads a custom website's PDF resource from the PiSRS website.

        Args:
            url_link (str): The URL of the custom website.
            title (str): The title of the resource.
            output_dir (str): The directory where the downloaded PDF will be saved.
            driver (WebDriver, optional): The Selenium WebDriver instance. Defaults to None.

        Returns:
            tuple: A tuple containing the PDF source URL and the save path of the downloaded PDF.
                   If the PDF source URL is not found, returns (None, None).
        """
        soup = get_website_html(url_link, driver=driver, close_driver=False)
        pdf_resource_title = ScrapePISRS.get_resource_title(soup)
        pdf_source_url = ScrapePISRS.get_pdf_source_url(url_link, soup)
        if pdf_source_url:
            save_path = os.path.join(output_dir, f"{make_title_safe(pdf_resource_title)}.pdf")
            if not os.path.exists(save_path):
                print(f"Downloading PISRS file: {make_title_safe(pdf_resource_title)} from website {pdf_source_url}")
                try:
                    wget.download(pdf_source_url, save_path)
                except Exception as e:
                    print(f"Could not download the file {url_link}. Error: ", e)

            return pdf_source_url, save_path
        else:
            print(f"Could not find PISRS file: {make_title_safe(pdf_resource_title)} from website {url_link}")
            return None, None

    @classmethod
    def get_pdf_source_url(cls, file_url, soup):
        """
        Retrieves the source URL of a PDF file from the given file URL and BeautifulSoup object.
        Looking at the HTML of the PISRS website, we can see that the pdf file is in the <div id="fileBtns"> element

        Args:
            file_url (str): The URL of the file.
            soup (BeautifulSoup): The BeautifulSoup object representing the HTML of the website.

        Returns:
            str: The complete URL path of the PDF file, or None if the file is not found.
        """

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

    @classmethod
    def get_resource_title(cls, soup):
        """
        Retrieves the title of a resource from the given BeautifulSoup object.
        In the PiSRS website the title is given by the <h1> element

        Args:
            soup (BeautifulSoup): The BeautifulSoup object representing the HTML content.

        Returns:
            str: The title of the resource, or None if the title cannot be found.
        """
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


# TODO: Implement scraper for EUR-Lex
# How exactly should it parse the website?
# Split the text by article, (also introduction, annex ...)
# Tables should be converted to JSON format
class ScrapeEURLex(Scraper):
    @staticmethod
    def download_custom_website(url_link, title, output_dir, driver=None):
        """
        EURLUX already provides the law nicely formatted in HTML. We just need to donwload the correct HTML element

        """
        soup = get_website_html(url_link, driver=driver, close_driver=False)
        print(soup)
        # I want to print all the different class types (i.e. all the values of the class attribute)
        print("Obtained soup")
        div_classes = set()
        p_classes = set()

        for div in soup.find_all("div"):
            if div.get("class"):
                div_classes.add(div.get("class")[0])
        for div in soup.find_all("p"):
            if div.get("class"):
                p_classes.add(div.get("class")[0])
        for table in soup.find_all("table"):
            print(table)

        print("DIV class types: ", list(set(div_classes)))
        print("P class types: ", list(set(p_classes)))

        loader = AsyncHtmlLoader([url_link])
        docs = loader.load()
        html2text = Html2TextTransformer()
        docs_transformed = html2text.transform_documents(docs)
        print(docs_transformed[0])

        # The following HTML elements will decide the structure:
        # <p class= ti-art, sti-art, ti-tbl, normal, note,
        # <p class="title-article-norm"  --> Article number
        # <p class="title-division-1" --> Title of section
        # <p class="title-division-2" --> Subtitle of section
        # <p class="title-division-1" --> Title of section
        # <p class="norm"  --> The actual text of the law
        # <div class="norm"  --> The actual text of the law
        # < p class="title-annex-1" --> Title of annex / tile of section
        # <div class="grid-container grid-list" --> Lists within a law article
        return None, None


# TODO Implement scraper for uradni-list.si
class ScrapeUradniList(Scraper):
    @staticmethod
    def download_custom_website(url_link, title, driver=None):
        # soup = get_website_html(url_link, driver=driver, close_driver=False)
        # print(soup)
        return None, None


# TODO Implement scraper for fu.gov.si
class ScrapeGOVsi(Scraper):
    @staticmethod
    def download_custom_website(url_link, title, driver=None):
        soup = get_website_html(url_link, driver=driver, close_driver=False)
        # I want to print all the different class types (i.e. all the values of the class attribute)
        print("Obtained soup")
        for div in soup.find_all("div"):
            print(div.get("class"))
        for div in soup.find_all("p"):
            print(div.get("class"))

        # The following HTML elements will decide the structure:
        # <p class="title-article-norm"  --> Article number
        # <p class="title-division-1" --> Title of section
        # <p class="title-division-2" --> Subtitle of section
        # <p class="title-division-1" --> Title of section
        # <p class="norm"  --> The actual text of the law
        # <div class="norm"  --> The actual text of the law
        # < p class="title-annex-1" --> Title of annex / tile of section
        # <div class="grid-container grid-list" --> Lists within a law article
        return None, None


if __name__ == "__main__":
    # Download all the data
    METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data"
    RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/raw_files"

    # scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR)
    # scraper.download_all_references()

    sys.path.append(
        "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chromedriver/mac_arm-121.0.6167.85/chromedriver-mac-arm64/chromedriver"
    )
    chromedriver_path = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chromedriver/mac_arm-121.0.6167.85/chromedriver-mac-arm64/chromedriver"
    browser_path = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/chrome/mac_arm-121.0.6167.85/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    option = webdriver.ChromeOptions()
    option.binary_location = browser_path
    browser = webdriver.Chrome(options=option)

    # Let's test the new Scraper over the EURLUX website
    print("Testing")
    url = "https://eur-lex.europa.eu/legal-content/SL/TXT/HTML/?uri=CELEX:32012R0815&qid=1628753057527&from=EN"
    output_dir = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/test_eurlux_data.txt"
    ScrapeEURLex.download_custom_website(url, None, output_dir, driver=browser)
