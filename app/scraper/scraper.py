import os
import logging
import pandas as pd
import tqdm
import requests
import backoff
import datetime
import zipfile
from dotenv import load_dotenv
from urllib.parse import urlparse
from urllib.parse import urljoin
from app.utils import (
    get_website_html,
    is_url_to_file,
    make_title_safe,
    get_chrome_driver,
    get_filetype,
)  # noqa: E402

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
DOWNLOADED_DATA_SCHEMA = [
    "file_id",
    "filename",
    "date_downloaded",
    "area",
    "subarea",
    "section",
    "file_type",
    "raw_filepath",
    "processed_filepath",
    "downloaded_path",
    "file_summary",
    "file_chunks_path",
    "in_vector_db",
]
PISRS_DOWNLOAD_BASE_URL = "https://pisrs.si/api/datoteke/integracije/"
PISRS_METADATA_BASE_URL = "https://pisrs.si/api/rezultat/zbirka/id/"
EURLEX_DOWNLOAD_BASE_URL = "https://eur-lex.europa.eu/legal-content/SL/TXT/HTML/?uri=CELEX:"
EURLEX_BASE_URL = "https://eur-lex.europa.eu/legal-content/SL/TXT/?"

logging.basicConfig(level=logging.INFO)


@backoff.on_exception(backoff.expo, ConnectionError, max_tries=10, max_time=20)
def _download_file(url_link, save_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"  # noqa E501
    }
    response = requests.get(url_link, headers=headers, timeout=20)  # stream=True,
    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)


class Scraper:
    def __init__(self, references_data_path, output_dir, local=False):
        self.driver = get_chrome_driver(local=local)
        self.references_data_path = references_data_path
        self.metadata_dir = os.path.dirname(references_data_path)
        self.references_data = pd.read_csv(references_data_path)
        self.output_dir = output_dir
        self.temp_dir = os.path.join(self.output_dir, "temp")
        self.already_downloaded_clean_links = []

        # Make sure the output dir exists
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

        # If references_data is new it might not have all the columns
        cols_to_add = [
            "used_download_href",
            "actual_download_link",
            "actual_download_location",
            "is_scraped",
            "date_downloaded",
        ]
        for col in cols_to_add:
            if col not in self.references_data.columns:
                self.references_data[col] = [None] * len(self.references_data)

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

            # Ignore if it was already processed
            if row["is_scraped"] == "True" or (
                isinstance(row["is_scraped"], bool) and row["is_scraped"]
            ):
                continue

            # Skip the ones where the
            reference_href_clean = str(row["reference_href_clean"]).split("#")[0]
            details_href_clean = str(row["details_href"]).split("#")[0]

            # The order is important.
            # First try to download the details href, and if that is nan, then download the
            # reference href
            # TODO (juan): Need to be able to handle .zip files. Problem is that they are too many
            # too much manual work
            # if get_filetype(details_href_clean) == "zip":
            #     continue
            #     self.download_zip_file(
            #         details_href_clean,
            #         row["details_href_name"],
            #         idx,
            #         idx_to_download_info,
            #     )
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

        # Create a clean dataset for all the downloaded data
        self.update_downloaded_data_index()

        return self.references_data

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
            actual_download_link_and_paths = [
                item[1:] for item in idx_to_download_info.values() if item[0] == url_link
            ]
            idx_to_download_info[idx] = (url_link, *actual_download_link_and_paths[0])
            self.update_references_data(idx, url_link, *actual_download_link_and_paths[0])
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
            try:
                _download_file(url_link, saved_path)
            except Exception as e:
                print(f"Could not download the file {url_link}. Error: ", e)

        idx_to_download_info[idx] = (url_link, url_link, saved_path)
        self.update_references_data(idx, url_link, url_link, saved_path)
        self.already_downloaded_clean_links.append(url_link)
        return

    def download_zip_file(self, url_link, title, idx, idx_to_download_info):

        # Download the zip file
        zip_filename = os.path.basename(url_link)
        zip_filepath = os.path.join(self.output_dir, zip_filename)
        try:
            _download_file(url_link, zip_filepath)
        except Exception as e:
            print("Could not download the file", url_link, " Error: ", e)
            return

        self.update_references_data(idx, url_link, url_link, zip_filepath)
        self.already_downloaded_clean_links.append(url_link)

        try:
            # Extract the zip file
            with zipfile.ZipFile(zip_filepath, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
        except Exception as e:
            print("Could not extract the zip data for url: ", url_link, "Error: ", e)
            return

        for extracted_file in zip_ref.namelist():
            original_path = os.path.join(self.temp_dir, extracted_file)
            if not os.path.isfile(original_path):
                # TODO (juan) we will not handle the cases where the extracted file is a directory
                continue
            if get_filetype(original_path) == "unknown":
                continue
            new_filename = f"{zip_filename.rsplit('.')[0]}_{extracted_file}"
            new_filename = make_title_safe(new_filename)
            new_filepath = os.path.join(self.output_dir, new_filename)
            os.rename(original_path, new_filepath)

            # Create a new row for the DataFrame
            orig_row = self.references_data.iloc[idx]
            new_row = orig_row.copy()
            new_row["details_href_name"] = new_filename
            new_row["actual_download_location"] = new_filepath
            new_index = self.references_data.index.max() + 1
            new_row_df = pd.DataFrame(
                [new_row], index=[new_index], columns=self.references_data.columns
            )
            self.references_data = pd.concat(
                [self.references_data, new_row_df],
                ignore_index=False,
            )
            self.references_data.to_csv(self.references_data_path, index=False)

        # Delete the original row using the original index
        self.references_data = self.references_data.drop(idx)
        self.references_data.to_csv(self.references_data_path, index=False)

        os.remove(zip_filepath)
        # except Exception as e:
        #     print("Could not extract the zip data for url: ", url_link, "Error: ", e)
        return

    def download_website(self, url_link, title, idx, idx_to_download_info):
        if url_link in self.already_downloaded_clean_links:
            actual_download_link_and_paths = [
                item[1:] for item in idx_to_download_info.values() if item[0] == url_link
            ]
            idx_to_download_info[idx] = (url_link, *actual_download_link_and_paths[0])
            self.update_references_data(idx, url_link, *actual_download_link_and_paths[0])
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
            # print("Need to download from other website: ", url_link)
            download_url_link, saved_path = None, None

        # Now update the idx_to_download_info
        idx_to_download_info[idx] = (url_link, download_url_link, saved_path)
        self.update_references_data(idx, url_link, download_url_link, saved_path)
        self.already_downloaded_clean_links.append(url_link)
        return

    def update_references_data(self, idx, url_link, actual_download_link, actual_download_location):
        if actual_download_location is not None:  # in some cases it doesn't find the download link
            self.references_data.at[idx, "used_download_href"] = url_link
            self.references_data.at[idx, "actual_download_link"] = actual_download_link
            self.references_data.at[idx, "actual_download_location"] = actual_download_location
            self.references_data.at[idx, "date_downloaded"] = datetime.datetime.now().date()
        self.references_data.at[idx, "is_scraped"] = True
        self.references_data.to_csv(self.references_data_path, index=False)

    def create_downloaded_data_index(self, data):

        new_data = []
        downloaded_data = data[data["actual_download_location"].isna() == False]  # noqa E501, E712
        downloaded_data = downloaded_data[
            downloaded_data["actual_download_link"].isna() == False  # noqa E501, E712
        ]  # noqa E501, E712
        downloaded_data = downloaded_data.where(pd.notnull(downloaded_data), None)

        for _, row in downloaded_data.iterrows():
            file_id = row["file_id"]  # uuid.uuid4()
            href_name = self._get_downladed_file_filename(row)
            area = row["area_name"]
            subarea = row["reference_name"]
            date_downloaded = row["date_downloaded"]
            section = row["details_section"]  # This can be Nan, that is ok
            file_type = get_filetype(row["actual_download_location"])
            raw_url_link = row["actual_download_link"]
            raw_filepath = row["actual_download_location"]
            new_data.append(
                [
                    file_id,
                    href_name,
                    date_downloaded,
                    area,
                    subarea,
                    section,
                    file_type,
                    raw_url_link,
                    None,
                    raw_filepath,
                    None,  # file_summary
                    None,  # file_chunks_path
                    None,  # in_vector_db
                ]
            )
        clean_df = pd.DataFrame(new_data, columns=DOWNLOADED_DATA_SCHEMA)
        return clean_df

    def update_downloaded_data_index(self):
        # If the file does not exist, create it
        if not os.path.exists(os.path.join(self.metadata_dir, "downloaded_data_index.csv")):
            downloaded_data_index = self.create_downloaded_data_index(self.references_data)
        else:
            downloaded_data_index = pd.read_csv(
                os.path.join(self.metadata_dir, "downloaded_data_index.csv")
            )
            new_data = self.references_data[
                ~self.references_data["file_id"].isin(downloaded_data_index["file_id"])
            ]
            new_downloaded_data_index = self.create_downloaded_data_index(new_data)
            downloaded_data_index = pd.concat([downloaded_data_index, new_downloaded_data_index])

        downloaded_data_index.to_csv(
            os.path.join(self.metadata_dir, "downloaded_data_index.csv"), index=False
        )

    def _get_downladed_file_filename(self, row):

        if row["details_href"] is not None:
            if row["details_href_name"] is not None:
                return row["details_href_name"]
            else:
                return os.path.basename(urlparse(row["details_href"]).path)
        elif row["reference_href_clean"] is not None:
            if row["reference_name"] is not None:
                return row["reference_name"]
            else:
                # Extract the filenmae from the refernce_href_clean
                return os.path.basename(urlparse(row["reference_href_clean"]).path)
        else:
            return None


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
        if "Pis.web/" in url_link:
            url_link = url_link.replace("Pis.web/", "")
        # Check if the resource is still valid!
        is_valid = ScrapePISRS.check_resource_valid(url_link, driver)
        if not is_valid:
            print(f"Resource {url_link} is not valid")
            return None, None

        resource_id = ScrapePISRS.get_resource_id(url_link, driver)
        if resource_id is None:
            print(f"Could not find PISRS resource id for url: {url_link}")
            return None, None
        download_url, resource_title = ScrapePISRS.get_download_url_and_title(resource_id)
        if resource_title is None:
            resource_title = ScrapePISRS.get_resource_title(url_link, driver)

        if download_url is not None and resource_title is not None:
            save_path = os.path.join(output_dir, f"{make_title_safe(resource_title[:100])}.html")
            if not os.path.exists(save_path):
                try:
                    _download_file(download_url, save_path)
                except Exception as e:
                    print(f"Could not download the file {url_link}. Error: ", e)

            return download_url, save_path
        else:
            print(
                f"Could not find PISRS file: {make_title_safe(resource_title)} "
                f"from website {url_link}"
            )
            return None, None

    @classmethod
    def check_resource_valid(cls, website_url, driver):
        soup = get_website_html(website_url, driver=driver, close_driver=False, wait_app_root=True)
        div_element = soup.find("div", attrs={"data-test": "evidencni-card-color-square"})
        if div_element:
            title = div_element.get("title")
            if "neveljaven" in title.lower():
                return False
            else:
                return True
        else:
            print("Could not find the validity indicator")
            return False

    @classmethod
    def get_resource_id(cls, website_url, driver):
        if "id=" in website_url:
            id_and_maybe_other_attrs = website_url.split("id=")[1]
            return id_and_maybe_other_attrs.split("&")[0]
        else:
            soup = get_website_html(
                website_url, driver=driver, close_driver=False, wait_app_root=True
            )
            div_element = soup.find("div", attrs={"data-test": "evidencni-card-zunanji-id"})
            if div_element:
                return div_element.text.split(":")[1].strip()
            else:
                return None

    @classmethod
    def get_resource_title(cls, website_url, driver):
        soup = get_website_html(website_url, driver=driver, close_driver=False)
        div_element = soup.find("h1", data_test="evidencni-card-title")
        if div_element:
            return div_element.text.strip()
        else:
            return None

    @classmethod
    def get_download_url_and_title(cls, resource_id):
        metadata_url = PISRS_METADATA_BASE_URL + resource_id
        try:

            response = requests.get(metadata_url)
            if response.status_code == 200:
                data = response.json()
                # Get the resource title
                resource_title = (
                    data.get("data", {}).get("evidencniPodatki", {}).get("naslov", None)
                )

                # Get the downlload URL for the HTML file
                download_id = None
                datoteke = data.get("data", {}).get("datoteke", {})
                max_version = 0
                for resource_version_data in datoteke:
                    version = resource_version_data.get("npbVerzija", {}).get("naziv", None)
                    if version is not None:
                        if max_version == 0 and "osnovni" in version.lower():
                            resource_version_files = resource_version_data.get("datoteke", [])
                            for file in resource_version_files:
                                if file.get("tip") in ["HTML_DOCUMENT"]:  # PDF_DOCUMENT
                                    download_id = file.get("id")
                        else:
                            version = version.split(" ")[-1]
                            if version.isdigit():
                                version = int(version)
                                if version > max_version:
                                    resource_version_files = resource_version_data.get(
                                        "datoteke", []
                                    )
                                    for file in resource_version_files:
                                        if file.get("tip") in ["HTML_DOCUMENT"]:  # PDF_DOCUMENT
                                            download_id = file.get("id")

                if download_id:
                    download_url = PISRS_DOWNLOAD_BASE_URL + f"{download_id}"
                    return download_url, resource_title
                else:
                    print("No suitable file type found for download.")
                    return None, None
            else:
                print(f"Failed to get metadata for PISRS doc, status code: {response.status_code}")
                return None, None
        except Exception as e:
            print(f"An error occurred requesting the PISRS metadata: {e}")
            return None, None


class ScrapeEURLex(Scraper):
    """Class derived from Scraper to scrape the EUR-Lex website.
    Implements the download_custom_website method.

    Returns:
        pdr_url_link: the actual URL link used to download the resource. None, if not available
        save_path: the path where the downloaded resource is saved. None, if not available
    """

    @staticmethod
    def download_custom_website_alt(website_url, title, output_dir, driver=None):
        """
        Downloads a custom website as a PDF file.

        Args:
            website_url (str): The URL of the website to download.
            title (str): The title of the website. (not used. Kept for compatibility with parent class) # noqa E501
            output_dir (str): The directory where the downloaded PDF file will be saved.
            driver (WebDriver, optional): The web driver to use for scraping. Defaults to None.

        Returns:
            tuple: A tuple containing the URL of the downloaded PDF file and the path where it is saved. # noqa E501
                    If the website cannot be downloaded, returns (None, None).
        """

        # Teh URL generally follows the following pattern:
        # https://eur-lex.europa.eu/legal-content/EN/TXT/{PDF, HTML}/?uri=CELEX%3A32023D2879&qid=1706091644527 # noqa E501
        # Ensure we load the website, and not the files of the law (i.e. HTML/PDF files)
        try:
            website_url = website_url.replace("/TXT/HTML/", "/TXT/").replace("/TXT/PDF/", "/TXT/")
            soup = get_website_html(website_url, driver=driver, close_driver=False)
        except Exception as e:
            print(
                "Could not get the HTML of the reference_href website with URL: {website_url}\n",
                "Error: ",
                e,
            )
            return None, None

        # logging.info(f"Got the HTML of the website {website_url}")

        # Check if the law is still valid and navigate to the latest version
        try:
            is_valid, html_validity_indicator = ScrapeEURLex.check_law_validity(soup)
            if is_valid == "Unknown":
                return None, None
        except Exception as e:
            print(
                "Could not check the validity of the law with URL: ", website_url, f"\n Error: {e}"
            )
            return None, None

        # Get the latest valid law
        latest_valid_url = ScrapeEURLex.get_latest_valid_url(
            html_validity_indicator, is_valid, website_url
        )
        if latest_valid_url is None:
            return None, None

        try:
            if website_url != latest_valid_url:
                soup_latest = get_website_html(latest_valid_url, driver=driver, close_driver=False)
            else:
                soup_latest = soup
        except Exception as e:
            print(
                "Could not get the HTML of the latest version of the"
                f" law with URL: {latest_valid_url}\n",
                "Error: ",
                e,
            )
            return None, None

        # Get the URL to the PDF of this website & download it
        pdf_url_link = ScrapeEURLex.get_pdf_url(soup_latest, latest_valid_url)
        if not pdf_url_link:
            return None, None
        pdf_title = ScrapeEURLex.get_pdf_title(soup_latest, latest_valid_url)
        save_path = os.path.join(output_dir, f"{make_title_safe(pdf_title)}.pdf")

        if pdf_url_link and not os.path.exists(save_path):
            try:
                _download_file(pdf_url_link, save_path)
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
        assert (
            law_valid_condition or law_not_valid_condition
        ), "The validity flag is netiehr valid nor invalid"

        law_modified_condition = any([msg in is_valid_desc for msg in LAW_WAS_CHANGED_MSG])
        law_not_in_force_condition = any(
            [msg in is_valid_desc for msg in LAW_NO_LONGER_IN_FORCE_MSG]
        )
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
            raise ValueError(
                "Could not determine status of the law based on the following description:",
                is_valid_desc,
            )

    @staticmethod
    def get_latest_valid_url(html_is_valid_ind, is_valid, website_url):
        """
        Returns the URL of the latest or replaced law based on the validity status.

        Args:
            html_is_valid_ind (BeautifulSoup): The BeautifulSoup object representing the HTML of the validity indicator. # noqa E501
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
            print(
                "Could not find the URL of the latest or replaced law based on the validity status:",  # noqa E501
                is_valid,
            )
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

    @staticmethod
    def download_custom_website(website_url, title, output_dir, driver=None):
        # Teh URL generally follows the following pattern:
        # https://eur-lex.europa.eu/legal-content/EN/TXT/{PDF, HTML}/?uri=CELEX%3A32023D2879&qid=17
        # Ensure we load the website, and not the files of the law (i.e. HTML/PDF files)

        # Handle if it is already a file (from the LEXSERV...)
        if "lexuriserv" in website_url.lower():
            # e.g.http://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=CELEX:21987A0813(01):SL:HTML
            resource_title = website_url.split("uri=")[-1]
            if "pdf" in resource_title.lower():
                save_path = os.path.join(output_dir, f"{make_title_safe(resource_title)}.pdf")
            elif "html" in resource_title.lower():
                save_path = os.path.join(output_dir, f"{make_title_safe(resource_title)}.html")
            else:
                save_path = os.path.join(output_dir, f"{make_title_safe(resource_title)}")
            if not os.path.exists(save_path):
                try:
                    _download_file(website_url, save_path)
                except Exception as e:
                    print(f"Could not download the EURLEX file {website_url}. Error: ", e)
                    return None, None
            return website_url, save_path

        try:
            website_url = website_url.replace("/TXT/HTML/", "/TXT/").replace("/TXT/PDF/", "/TXT/")
            soup = get_website_html(website_url, driver=driver, close_driver=False)
        except Exception as e:
            print(
                "Could not get the HTML of the reference_href website with URL: {website_url}\n",
                "Error: ",
                e,
            )
            return None, None

        # If it is a search result, extract the first result
        if "search.html" in website_url.lower():
            # Get the result of the search and download the HTML version of the first result
            website_url = ScrapeEURLex.get_first_search_result(website_url, soup)
            if website_url is None:
                print("Did not find search result from EURLEX website")
                return None, None
            else:
                soup = get_website_html(website_url, driver=driver, close_driver=False)
                if soup is None:
                    print(
                        "Could not get the HTML of the reference_href website with URL: "
                        f"{website_url}\n",
                    )
                    return None, None

        # Check validity
        is_valid, is_valid_text = ScrapeEURLex.check_resource_valid(soup)
        if is_valid is None:
            print("Could not check the validity of the law with URL: ", website_url)
            return None, None

        # Get latest version of teh HTML of the website
        latest_valid_url = ScrapeEURLex.get_latest_resource_version(
            website_url, soup, is_valid_text
        )
        if latest_valid_url == website_url and not is_valid:
            print("The resource is not valid. URL: ", website_url)
            return None, None
        elif latest_valid_url != website_url and is_valid:
            soup = get_website_html(latest_valid_url, driver=driver, close_driver=False)

        # Extract the ID of the latest resource
        resource_id = ScrapeEURLex.get_resource_id(latest_valid_url, soup)
        if resource_id is None:
            print(f"Could not find EURLEX resource CELEX for url: {website_url}")
            return None, None

        resource_title = ScrapeEURLex.get_resource_title(latest_valid_url, soup)
        download_url = ScrapeEURLex.get_download_url(resource_id)

        # Download the resource if not already downloaded
        if download_url is not None and resource_title is not None:
            save_path = os.path.join(output_dir, f"{make_title_safe(resource_title)}.html")
            if not os.path.exists(save_path):
                try:
                    _download_file(download_url, save_path)
                except Exception as e:
                    print(f"Could not download the EURLEX file {download_url}. Error: ", e)
                    return None, None
            return download_url, save_path
        else:
            print(
                f"Could not find EURLEX file: {make_title_safe(resource_title)} from website "
                f"{website_url}"
            )
            return None, None

    @classmethod
    def check_resource_valid(cls, soup):
        # Extract the src attribute of the img element within the forceIndicator class
        force_indicator = soup.find("p", class_="forceIndicator")
        if force_indicator:
            force_indicator_text = soup.find("p", class_="forceIndicator").text.strip()
            img_src = force_indicator.find("img", class_="forceIndicatorBullet").get("src", "")
            # Check if the src attribute contains 'green-on.png' to determine validity
            if "green" in img_src:
                return True, force_indicator_text  # Valid
            else:
                return False, force_indicator_text  # Not valid
        else:
            return None, None  # Indicator not found

    @classmethod
    def get_latest_resource_version(cls, website_url, soup, is_valid_text):
        href = None
        access_current_a = soup.find("p", class_="accessCurrent")
        resource_version_el = soup.find("nav", class_="consLegNav")
        if access_current_a:
            href = access_current_a.find("a").get("href", None)
        elif resource_version_el is not None:
            # Try to get the latest version from the toolbar containing the versions
            versions = resource_version_el.find("ul")
            if versions:
                latest_version = versions.find("li")
                if latest_version:
                    href = latest_version.find("a").get("href", None)
        else:
            print(
                f"EURLEX website does not have the accessCurrent and no list of resource versions."
                f"Website: {website_url}, Is valid descriptor: ",
                is_valid_text,
            )

        if href is not None:
            if href.startswith("http"):
                return href
            else:
                return urljoin(website_url, href)
        else:
            return website_url

    @classmethod
    def get_resource_id(cls, website_url, soup):
        if "celex" in website_url:
            celex_and_potentially_other_attrs = website_url.split("celex%")[-1]
            resource_id = celex_and_potentially_other_attrs.split["&"][0]
        elif "CELEX" in website_url:
            celex_and_potentially_other_attrs = website_url.split("CELEX%")[-1]
            resource_id = celex_and_potentially_other_attrs.split("CELEX:")[-1]
        else:
            title = ScrapeEURLex.get_resource_title(website_url, soup)
            # Extract the CELEX from the title
            # Title format: Dokument&nbsp;02011R0282-20150101
            resource_id = title.split("&nbsp;")[-1]
        return resource_id

    @classmethod
    def get_resource_title(cls, website_url, soup):
        # Extract the title from the document title HTML element
        doc_title_element = soup.find("p", class_="DocumentTitle pull-left")
        if doc_title_element:
            return doc_title_element.text
        else:
            print("EURLEX website does not have the document title HTML element")

    @classmethod
    def get_download_url(cls, resource_id):
        # Use the URL structure to try to download the HTML version of the file
        return EURLEX_DOWNLOAD_BASE_URL + f"{resource_id.strip()}"

    @classmethod
    def get_first_search_result(cls, website_url, soup):
        div_element = soup.find("div", class_="SearchResult")  # Finds the first results
        if div_element:
            search_result_title_el = div_element.find("h2").find("a")
            search_result_url = search_result_title_el.get("name")
            if "AUTO" in search_result_url:
                search_result_url = search_result_url.replace("AUTO", "SL/TXT")
            return search_result_url
        else:
            return None


class ScrapeUradniList(Scraper):
    @staticmethod
    def download_custom_website(website_url, title, output_dir, driver=None):
        return None, None


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

    # Test the full scraper from start to finish
    from app.scraper.references_list import FURSReferencesList

    ROOT_URL = "https://www.fu.gov.si"
    METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data"
    reference_data = FURSReferencesList(ROOT_URL, METADATA_DIR, local=True)
    reference_data.update_references()

    RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/raw_data"
    scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR, local=True)
    scraper.download_all_references()

    # Test why the scraper did not manage to download the following file, while I managed to download # noqa E501
    # it before
    # file_url = "https://eur-lex.europa.eu/legal-content/SL/TXT/?uri=CELEX:32022R1467&qid=1672324949047&from=en" # noqa E501
    # driver = get_chrome_driver(local=True)
    # RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/test_0419/raw_data" # noqa E501
    # ScrapeEURLex.download_custom_website(file_url, None, RAW_DATA_DIR, driver)

    # file_url = "https://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=OJ:C:2013:105:0001:0006:SL:PDF" # noqa E501
    # file_url = "https://eur-lex.europa.eu/legal-content/SL/TXT/?uri=CELEX%3A02011R0282-20150101"
    # file_url = "http://eur-lex.europa.eu/search.html?DTN=0952&DTA=2013&qid=1468324554259&DB_TYPE_OF_ACT=regulation&CASE_LA _SUMMARY=false&DTS_DOM=ALL&excConsLeg=true&typeOfActStatus=REGULATION&type=advanced&SUBDOM_INIT=ALL_ALL&DTS_SUBDOM=ALL_ALL" # noqa E501
    # file_url = "https://eur-lex.europa.eu/legal-content/SL/TXT/?uri=CELEX:02014R0651-20230701"
    # driver = get_chrome_driver(local=True)
    # RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/testing/"
    # print(ScrapeEURLex.download_custom_website(file_url, None, RAW_DATA_DIR, driver))

    # Test if it download the zip file correctly
    # file_url = "https://fu.gov.si/fileadmin/Internet/Carina/Prepovedi_in_omejitve/Ribiski_proizvodi/Opis/Pogosta_vprasanja_glede_izvajanja_IUU_uredbe.zip"  # noqa E501
    # driver = get_chrome_driver(local=True)
    # RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/raw_files"
    # METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/"
    # scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR, local=True)
    # scraper.download_all_references()
    # scraper.download_zip_file(file_url, None, RAW_DATA_DIR, driver)
