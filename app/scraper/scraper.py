"""
This script crawls the fu.gov.si website and extracts all the references denoted there that cover most of the
areas of tax laws.
"""
import os
import logging
import pandas as pd
import wget
from dotenv import load_dotenv
import tqdm
from urllib.parse import urljoin
from ..utils import get_website_html, is_url_to_file, make_title_safe, get_chrome_driver  # noqa: E402

FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx", "xls", "ppt", "pptx", "csv", "txt", "rtf", "odt", "ods"]

logging.basicConfig(level=logging.INFO)


# TODO: some of the files fail to get downloaded, (and the actual_download_location) can be populated
# --> these need to be dealt with


class Scraper:
    pass

    def __init__(self, references_data_path, output_dir, local=False):
        self.driver = get_chrome_driver(local=local)
        self.references_data_path = references_data_path
        self.references_data = pd.read_csv(references_data_path)
        self.output_dir = output_dir
        self.already_downloaded_clean_links = []

        # Make sure the output dir exists
        os.makedirs(output_dir, exist_ok=True)

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
        for idx, row in tqdm.tqdm(self.references_data.iterrows()):
            # # HACK: SINCE WE ONLY SUPPORT SCRAPING PISRS CURRENTLY
            # if row["reference_href"].startswith("https://eur-lex.europa.eu") or (
            #     isinstance(row["details_href"], str) and row["details_href"].startswith("https://eur-lex.europa.eu")
            # ):
            reference_href_clean = str(row["reference_href_clean"]).split("#")[0]
            details_href_clean = str(row["details_href"]).split("#")[0]

            # The order is important.
            # First try to download the details href, and if that is nan, then download the reference href
            if is_url_to_file(details_href_clean):
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
            elif is_url_to_file(reference_href_clean):
                self.download_file(
                    reference_href_clean,
                    row["reference_name"],
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

        # Update the references_data DataFrame
        for idx, (url_link, actual_download_link, actual_download_location) in idx_to_download_info.items():
            self.references_data.at[idx, "used_download_href"] = url_link
            self.references_data.at[idx, "actual_download_link"] = actual_download_link
            self.references_data.at[idx, "actual_download_location"] = actual_download_location
            if actual_download_location is not None:  # in some cases it doesn't find the download link
                self.references_data.at[idx, "is_processed"] = True
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
            actual_download_link_and_paths = [item[1:] for item in idx_to_download_info.values() if item[0] == url_link]
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
                self.already_downloaded_clean_links.append(url_link)
            except Exception as e:
                print(f"Could not download the file {url_link}. Error: ", e)

        return

    def download_website(self, url_link, title, idx, idx_to_download_info):
        if url_link in self.already_downloaded_clean_links:
            actual_download_link_and_paths = [item[1:] for item in idx_to_download_info.values() if item[0] == url_link]
            idx_to_download_info[idx] = (url_link, *actual_download_link_and_paths[0])
            return

        download_url_link = None
        saved_path = None
        if "eur-lex.europa.eu" in url_link:
            download_url_link, saved_path = ScrapeEURLex.download_custom_website(
                url_link, title, output_dir=self.output_dir, driver=self.driver
            )
        elif ".uradni-list.si" in url_link:
            download_url_link, saved_path = ScrapeUradniList.download_custom_website(
                url_link, title, output_dir=self.output_dir, driver=self.driver
            )
        elif ".pisrs.si" in url_link:
            download_url_link, saved_path = ScrapePISRS.download_custom_website(
                url_link, title, output_dir=self.output_dir, driver=self.driver
            )
        elif "fu.gov.si" in url_link:
            download_url_link, saved_path = ScrapeGOVsi.download_custom_website(
                url_link, title, output_dir=self.output_dir, driver=self.driver
            )
        else:
            print("Need to download from other website: ", url_link)
            download_url_link, saved_path = None, None

        # Now update the idx_to_download_info
        idx_to_download_info[idx] = (url_link, download_url_link, saved_path)
        self.already_downloaded_clean_links.append(url_link)
        return


class ScrapePISRS(Scraper):
    pass

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
class ScrapeEURLex(Scraper):
    """Class derived from Scraper to scrape the EUR-Lex website. Implements the download_custom_website method.

    Returns:
        pdr_url_link: the actual URL link used to download the resource. None, if not available
        save_path: the path where the downloaded resource is saved. None, if not available
    """

    @staticmethod
    def download_custom_website(website_url, title, output_dir, driver=None):
        """
        Downloads a custom website as a PDF file.

        Args:
            website_url (str): The URL of the website to download.
            title (str): The title of the website. (not used. Kept for compatibility with parent class)
            output_dir (str): The directory where the downloaded PDF file will be saved.
            driver (WebDriver, optional): The web driver to use for scraping. Defaults to None.

        Returns:
            tuple: A tuple containing the URL of the downloaded PDF file and the path where it is saved.
                    If the website cannot be downloaded, returns (None, None).
        """

        # Teh URL generally follows the following pattern:
        # https://eur-lex.europa.eu/legal-content/EN/TXT/{PDF, HTML}/?uri=CELEX%3A32023D2879&qid=1706091644527
        # Ensure we load the website, and not the files of the law (i.e. HTML/PDF files)
        try:
            website_url = website_url.replace("/TXT/HTML/", "/TXT/").replace("/TXT/PDF/", "/TXT/")
            soup = get_website_html(website_url, driver=driver, close_driver=False)
        except Exception as e:
            print("Could not get the HTML of the reference_href website with URL: {website_url}\n", "Error: ", e)
            return None, None

        # logging.info(f"Got the HTML of the website {website_url}")

        # Check if the law is still valid and navigate to the latest version
        is_valid, html_validity_indicator = ScrapeEURLex.check_law_validity(soup)
        if is_valid == "Unknown":
            return None, None

        # Get the latest valid law
        latest_valid_url = ScrapeEURLex.get_latest_valid_url(html_validity_indicator, is_valid, website_url)
        if latest_valid_url is None:
            return None, None

        try:
            soup_latest = get_website_html(latest_valid_url, driver=driver, close_driver=False)
        except Exception as e:
            print(
                "Could not get the HTML of the latest version of the" f" law with URL: {latest_valid_url}\n",
                "Error: ",
                e,
            )
            return None, None

        # Get the URL to the PDF of this website & download it
        pdf_url_link = ScrapeEURLex.get_pdf_url(soup_latest, latest_valid_url)
        pdf_title = ScrapeEURLex.get_pdf_title(soup_latest, latest_valid_url)
        save_path = os.path.join(output_dir, f"{make_title_safe(pdf_title)}.pdf")
        if pdf_url_link and not os.path.exists(save_path):
            try:
                wget.download(pdf_url_link, save_path, bar=None)
            except Exception as e:
                print(f"Could not download the file {pdf_url_link}. Error: ", e)
                return None, None
        return pdf_url_link, save_path

    @staticmethod
    def check_law_validity(soup):
        """
        Checks if a law is still valid based on the provided HTML.

        Args:
            html_is_valid_ind (BeautifulSoup): The HTML containing the law's validity information.

        Returns:
            str: The status of the law. Possible values are:
                - "New Version" if the law has been changed.
                - "Latest Version" if the law is still in force.
                - "Replaced Version" if the law is no longer valid.
                - "Unknown" if the status of the law cannot be determined.
        """
        # Manually defined based on the HTML of the website
        IS_VALID_FLAG_VALUE = ["green"]
        IS_NOT_VALID_FLAG_VALUE = ["red"]
        LAW_IN_FORCE_MSG = ["V veljavi", "In force"]
        LAW_WAS_CHANGED_MSG = ["ta akt je bil spremenjen", "This act has been changed"]
        LAW_NO_LONGER_IN_FORCE_MSG = ["Ne velja več", "No longer in force"]
        # validity_indicator_values = {
        #     "New Version": 4,
        #     "Latest Version": 3,
        #     "Replaced Version": 2,
        #     "Invalid Version": 1,
        #     "Unknown": 0,
        # }

        html_is_valid_ind = soup.find("p", class_="forceIndicator")
        if html_is_valid_ind is None:
            return "Unknown", html_is_valid_ind

        is_valid_desc = "".join([element.text for element in html_is_valid_ind.find_all()])
        is_valid_desc += html_is_valid_ind.text
        is_valid_flag = html_is_valid_ind.find("img", class_="forceIndicatorBullet").get("src")

        law_valid_condition = any([flag in is_valid_flag for flag in IS_VALID_FLAG_VALUE])
        law_not_valid_condition = any([flag in is_valid_flag for flag in IS_NOT_VALID_FLAG_VALUE])
        assert law_valid_condition or law_not_valid_condition, "The validity flag is netiehr valid nor invalid"

        law_modified_condition = any([msg in is_valid_desc for msg in LAW_WAS_CHANGED_MSG])
        law_not_in_force_condition = any([msg in is_valid_desc for msg in LAW_NO_LONGER_IN_FORCE_MSG])
        law_in_force_condition = any([msg in is_valid_desc for msg in LAW_IN_FORCE_MSG])
        assert (
            law_modified_condition or law_not_in_force_condition or law_in_force_condition
        ), "The validity description is not valid"

        if law_valid_condition and law_modified_condition:
            return "New Version", html_is_valid_ind
        elif law_valid_condition and law_in_force_condition:
            return "Latest Version", html_is_valid_ind
        elif law_not_valid_condition and law_modified_condition:
            return "Replaced Version", html_is_valid_ind
        elif law_not_valid_condition and law_not_in_force_condition:
            return "Invalid Version", html_is_valid_ind
        else:
            raise ValueError("Could not determine status of the law based on the following description:", is_valid_desc)

    @staticmethod
    def get_latest_valid_url(html_is_valid_ind, is_valid, website_url):
        """
        Returns the URL of the latest or replaced law based on the validity status.

        Args:
            html_is_valid_ind (BeautifulSoup): The BeautifulSoup object representing the HTML of the validity indicator.
            is_valid (str): The validity status of the law.
            website_url (str): The URL of the website.

        Returns:
            str: The URL of the latest or replaced law. None, if the status is unknown.
        """
        if is_valid == "Latest Version":
            return website_url
        elif is_valid == "New Version" or is_valid == "Replaced Version":
            href = html_is_valid_ind.find("a").get("href")
            if href is None:
                return None
            elif href.startswith("http"):
                return href
            else:
                return urljoin(website_url, href)
        elif is_valid == "Invalid Version":
            return None
        else:
            print("Could not find the URL of the latest or replaced law based on the validity status:", is_valid)
            return None

    @staticmethod
    def get_pdf_url(soup, website_url):
        if soup is None or website_url is None:
            return None

        dropdown_html_element = soup.find("ul", class_="dropdown-menu PubFormatPDF")
        if dropdown_html_element is None:
            return None

        href_html_element = dropdown_html_element.find("a", id="format_language_table_PDF_SL")
        if href_html_element is None:
            return None

        href = href_html_element.get("href")
        if href.startswith("http"):
            return href
        else:
            return urljoin(website_url, href)

    @staticmethod
    def get_pdf_title(soup, website_url):
        if soup is None or website_url is None:
            return None, None

        doc_title = soup.find("p", class_="DocumentTitle pull-left")
        if doc_title is not None:
            doc_title = doc_title.text
        return doc_title


# TODO Implement scraper for uradni-list.si
class ScrapeUradniList(Scraper):
    @staticmethod
    def download_custom_website(website_url, title, output_dir, driver=None):
        return None, None


# TODO Implement scraper for fu.gov.si
class ScrapeGOVsi(Scraper):
    @staticmethod
    def download_custom_website(website_url, title, output_dir, driver=None):
        return None, None


if __name__ == "__main__":
    # For development purposes
    _ = load_dotenv(".env.local")  # read local .env file

    # Download all the data
    METADATA_DIR = os.getenv("METADATA_DIR")
    RAW_DATA_DIR = os.getenv("RAW_DATA_DIR")

    RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/testing_integration"
    scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR, local=True)
    scraper.download_all_references()

    ##################################################################
    # TESTING
    ##################################################################

    # Checking the fu.gov.si data --> Does not feel that usefol
    from urllib.parse import urlparse

    def get_file_type(url):
        if url.endswith(".pdf"):
            return "pdf"
        elif url.endswith(".docx"):
            return "docx"
        elif url.endswith(".doc"):
            return "doc"
        elif url.endswith(".zip"):
            return "zip"
        elif url.endswith(".xlsx"):
            return "xlsx"
        elif url.endswith(".xls"):
            return "xls"
        elif "fileadmin" in urlparse(url).path:
            return "file"
        else:
            return "website"

    # RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/testing"
    # for idx, row in scraper.references_data.iterrows():
    #     if isinstance(row["details_href"], str) and row["details_href"].startswith("https://eur-lex.europa.eu"):
    #         file_type = get_file_type(row["details_href"])
    #         if file_type == "website":
    #             clean_href = row["details_href"].split("#")[0]
    #             pdf_url_link, save_path = ScrapeEURLex.download_custom_website(
    #                 clean_href, None, RAW_DATA_DIR, driver=scraper.driver
    #             )

    #             if pdf_url_link is None:
    #                 print("File could not be downloaded: ", clean_href)
    #         else:
    #             print("Hreaf not a website, but rather type: ", file_type, "URL: ", row["details_href"])

    # Let's tackle first:
    # eur-lex.europa.eu 340
    # www.fu.gov.si 764
    # pisrs.si 64
    # www.gov.si 48
    # ec.europa.eu 39
    # www.uradni-list.si 32
    # www.oecd.org 28
    # edavki.durs.si 28
    # taxation-customs.ec.europa.eu 9
    # vat-one-stop-shop.ec.europa.eu 8

    # Let's test the new Scraper over the EURLUX website
    # url = "https://eur-lex.europa.eu/legal-content/SL/TXT/HTML/?uri=CELEX:32012R0815&qid=1628753057527&from=EN"

    # url = "https://eur-lex.europa.eu/legal-content/SL/TXT/?uri=CELEX:01993R2454-20151208"
    # url = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023D2879&qid=1706091644527"
    # ScrapeEURLex.download_custom_website(url, None, RAW_DATA_DIR, driver=scraper.driver)
