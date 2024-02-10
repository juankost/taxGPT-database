"""
This script crawls the fu.gov.si website and extracts all the references denoted there that cover most of the
areas of tax laws.
"""
import os
from re import S
from selenium import webdriver
import pandas as pd
import sys
import wget

sys.path.append("/Users/juankostelec/Google_drive/Projects/tax_backend/src")
from utils import get_website_html  # noqa: E402

FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx", "xls", "ppt", "pptx", "csv", "txt", "rtf", "odt", "ods"]
ROOT_URL = "https://www.fu.gov.si"
MAIN_URL = ROOT_URL + "/podrocja"
SRC_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/src"
METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/data"
RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/data/raw_files"
PROCESSED_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/data/processed_files"


def is_url_to_file(url):
    FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx", "xls", "ppt", "pptx", "csv", "txt", "rtf", "odt", "ods"]
    for file_extension in FILE_EXTENSIONS:
        if str(url).endswith(file_extension):
            return True
    return False


def make_title_safe(title):
    # If a string contains whitespace, replace with underscore. Remove also brackets from the name
    title = str(title).strip().replace(" ", "_")
    title = title.replace("(", "-").replace(")", "_").replace("/", "_")
    # If the last character is not alphanumerical, remove it
    if not title[-1].isalnum():
        title = title[:-1]
    return title


class ReferencesList:
    def __init__(self, root_url, reference_list_save_dir):
        self.root_url = root_url
        self.furs_url = os.path.join(root_url, "podrocja")
        self.reference_list_save_dir = reference_list_save_dir
        self.driver = webdriver.Chrome()
        self.soup = get_website_html(self.furs_url, driver=self.driver, close_driver=False)
        if os.path.exists(os.path.join(self.reference_list_save_dir, "podrocja_list_with_links.csv")):
            self.podrocja_list_with_links = pd.read_csv(
                os.path.join(self.reference_list_save_dir, "podrocja_list_with_links.csv")
            )
        else:
            self.podrocja_list_with_links = self.extract_list_podrocja()
            self.reference_data.extract_podrocja_details()
        self.driver.close()

    def extract_list_podrocja(self):
        podrocja_list_with_links = []
        all_podrocja = self.soup.find("div", id="content")
        podrocja_elements = all_podrocja.find_all("a", href="#")
        for element in podrocja_elements:
            podrocje_description = element.find("em").text
            podrocje_name = element.text.replace(podrocje_description, "").strip()
            podrocje_siblings = element.parent.find_next_siblings()
            for sibling in podrocje_siblings:
                link_elements = sibling.find_all("li")
                for li in link_elements:
                    link_name = li.text
                    link_href = li.find("a").get("href")
                    if link_href.startswith("/"):
                        link_href = ROOT_URL + link_href
                    podrocja_list_with_links.append([podrocje_name, podrocje_description, link_name, link_href])

        # Create pandas dataframe to store it
        df = pd.DataFrame(
            data=podrocja_list_with_links,
            columns=["podrocje_name", "podrocje_description", "podrocje_link_name", "podrocje_link_href"],
        )
        df.to_csv(os.path.join(self.reference_list_save_dir, "podrocja_list_with_links.csv"), index=False)
        return df

    def extract_podrocja_details(self):
        website_links = self.get_list_of_further_website_links()
        typical_website_links, _, other_websites = self.check_href_type(website_links)

        data = None
        # Extract further stuff from the typical websites
        for url_link in typical_website_links:
            df = self.extract_details_typical_website(url_link)
            if data is None:
                data = df
            else:
                data = pd.concat([data, df], axis=0)

        # Join the details data with the original data
        self.podrocja_list_with_links["podrocje_clean_link"] = self.podrocja_list_with_links[
            "podrocje_link_href"
        ].apply(lambda x: x.split("#")[0])

        self.podrocja_list_with_links = pd.merge(
            self.podrocja_list_with_links, data, on=["podrocje_clean_link"], how="left"
        )

        # Save the data
        self.podrocja_list_with_links.to_csv(
            os.path.join(self.reference_list_save_dir, "podrocja_list_with_links.csv"), index=False
        )
        return self.podrocja_list_with_links

    def extract_details_typical_website(self, url_link):
        soup = get_website_html(url_link, driver=self.driver, close_driver=False)

        # Find the relevant sections: Opis, Podrobnejši opisi, Zakonodaja, Navodila in Pojasnila
        content_element = soup.find("div", id="content")
        if content_element is None:
            return None

        website_details = []
        sections = content_element.find_all("a", href="#")
        for section in sections:
            section_title = section.text.strip()
            if section_title in ["Opis", "Podrobnejši opisi", "Zakonodaja", "Navodila in Pojasnila"]:
                section_text = ""
                section_siblings = section.parent.find_next_siblings()
                for sibling in section_siblings:
                    section_text = section_text + "\n" + sibling.get_text()
                    # Clean up text - remove special characters that are not the common one (e.g. (, ), -, etc.)
                    section_text = section_text.replace(" Bigstock", " ").strip()
                    section_links = sibling.find_all("a", href=True)
                    for link in section_links:
                        link_text = link.text.strip()
                        link_href = link.get("href")
                        if link_href.startswith("/"):
                            link_href = ROOT_URL + link_href
                        website_details.append([url_link, section_title, section_text, link_text, link_href])
        df = pd.DataFrame(
            data=website_details,
            columns=[
                "podrocje_clean_link",
                "details_section",
                "details_section_text",
                "details_link_text",
                "details_link",
            ],
        )
        return df

    def get_list_of_further_website_links(self):
        website_links = []
        for _, row in self.podrocja_list_with_links.iterrows():
            if row["podrocje_link_href"].startswith(self.root_url):
                website_links.append(row["podrocje_link_href"].split("#")[0])

        website_links = list(set(website_links))
        return website_links

    def check_href_type(self, website_links):
        typical_website_links = []
        file_links = []
        other_websites = []
        for url_link in website_links:
            if not url_link.startswith(self.root_url):
                other_websites.append(url_link)
            elif is_url_to_file(url_link):
                file_links.append(url_link)
            else:
                soup = get_website_html(url_link, driver=self.driver, close_driver=False)
                if self.is_typical_website(soup):
                    typical_website_links.append(url_link)
                else:
                    other_websites.append(url_link)
        return typical_website_links, file_links, other_websites

    def is_typical_website(self, soup):
        content_element = soup.find("div", id="content")
        if content_element is None:
            return False

        sections = content_element.find_all("a", href="#")
        for section in sections:
            section_title = section.text.strip()
            if section_title in ["Opis", "Podrobnejši opisi", "Zakonodaja", "Navodila in Pojasnila"]:
                return True
        return False


class Scraper:
    def __init__(self, root_url, references_list_path, raw_dir):
        self.root_url = root_url
        self.raw_dir = raw_dir
        self.podrocja_list_with_links = pd.read_csv(references_list_path)
        self.driver = webdriver.Chrome()

    def download_all_references(self):
        # Download all the references
        already_downloaded_clean_links = []
        idx_to_download_info = {}  # maps from idx to the actual download link (esp. if website)
        dict_idx_to_actual_resource_download_location = {}  # maps from idx to the where we saved the file
        dict_href_link_to_actual_resource_download_link = {}  # maps from href link to the actual download link

        # What I want to have is a mapping: idx: (actual_download_link, downloaded_location)
        # Pass the mapping to the download_file, and download_website functions, and update it if we download something
        # Additionally, check in the two function, whether there is a ned to download the file or was it already done
        c = 0
        for idx, row in self.podrocja_list_with_links.iterrows():
            c += 1
            if c % 30 == 0:
                break
            clean_podrocje_link_href = str(row["podrocje_link_href"]).split("#")[0]
            clean_details_link = str(row["details_link"]).split("#")[0]

            if is_url_to_file(clean_podrocje_link_href):
                if clean_podrocje_link_href not in already_downloaded_clean_links:
                    self.download_file(
                        clean_podrocje_link_href,
                        row["podrocje_link_name"],
                        idx,
                        already_downloaded_clean_links,
                        idx_to_download_info,
                    )
            elif is_url_to_file(clean_details_link):
                self.download_file(
                    clean_details_link,
                    row["details_link_text"],
                    idx,
                    already_downloaded_clean_links,
                    idx_to_download_info,
                )
            elif clean_details_link != "nan":
                self.download_website(
                    clean_details_link,
                    row["details_link_text"],
                    idx,
                    already_downloaded_clean_links,
                    idx_to_download_info,
                )
            else:
                self.download_website(
                    clean_podrocje_link_href,
                    row["podrocje_link_name"],
                    idx,
                    already_downloaded_clean_links,
                    idx_to_download_info,
                )
        # Now update the self.podrocja_list_with_links with the download links for websites and the download locations
        print(
            len(self.podrocja_list_with_links),
            len(idx_to_download_info),
            len(idx_to_download_info.keys()),
            len(set(idx_to_download_info.keys())),
        )
        # temp_df = pd.DataFrame(
        #     data=list(idx_to_download_info.values()),
        #     columns=["url_link", "actual_download_link", "actual_download_location"],
        #     index=idx_to_download_info.keys(),
        # )

        self.podrocja_list_with_links[
            ["used_download_link", "actual_download_link", "actual_download_location"]
        ] = self.podrocja_list_with_links.index.map(idx_to_download_info)
        # self.podrocja_list_with_links[["actual_download_link", "actual_download_location"]] = pd.DataFrame(
        #     idx_to_download_info.values(), index=idx_to_download_info.keys()
        # )

        # self.podrocja_list_with_links.to_csv(
        #     os.path.join(METADATA_DIR, "enriched_podrocja_list_with_links.csv"), index=False
        # )

    def download_file(self, url_link, title, idx, already_downloaded_clean_links, idx_to_download_info):
        # The file extension will be gven by the last part of url_link.
        # It will either be delineated by a dot or a equal sign
        if url_link in already_downloaded_clean_links:
            actual_download_link_and_paths = [item[1] for item in idx_to_download_info.items() if item[0] == idx]
            assert set(actual_download_link_and_paths) == 1
            idx_to_download_info[idx] = (url_link, *actual_download_link_and_paths[0])
            return

        file_extension = url_link.split(".")[-1]
        if "=" in file_extension:
            file_extension = file_extension.split("=")[-1]
        if file_extension not in FILE_EXTENSIONS:
            print("Could not download the file", url_link)
            return None

        # Download the file
        saved_path = os.path.join(self.raw_dir, make_title_safe(title) + "." + file_extension)
        if not os.path.exists(saved_path):
            print(f"Downloading file from {url_link}")
            try:
                wget.download(url_link, saved_path)
            except Exception as e:
                print(f"Could not download the file {url_link}. Error: ", e)
        # Now update the idx_to_download_info
        idx_to_download_info[idx] = (url_link, url_link, saved_path)
        return

    def download_website(self, url_link, title, idx, already_downloaded_clean_links, idx_to_download_info):
        # First figure out if it is any of the standard domains:
        if url_link in already_downloaded_clean_links:
            actual_download_link_and_paths = [item[1] for item in idx_to_download_info.items() if item[0] == idx]
            assert set(actual_download_link_and_paths) == 1
            idx_to_download_info[idx] = (url_link, *actual_download_link_and_paths[0])
            return

        download_url_link = None
        saved_path = None
        if "eur-lex.europa.eu" in url_link:
            # TODO: Implemen scraper for EUR-Lex
            print("Need to download from eur-lex.europa.eu")
        elif ".uradni-list.si" in url_link:
            # TODO Implement scraper for uradni-list.si
            print("Need to download from uradni-list.si")
        elif ".pisrs.si" in url_link:
            print("Need to download from pisrs.si")
            download_url_link, saved_path = ScrapePISRS.download_custom_website(url_link, title, driver=self.driver)
        elif "fu.gov.si" in url_link:
            print("Need to download from fu.gov.si")
            # TODO Implement scraper for fu.gov.si
        else:
            print("Need to download from other website: ", url_link)

        # Now update the idx_to_download_info
        idx_to_download_info[idx] = (url_link, download_url_link, saved_path)
        return


class ScrapePISRS(Scraper):
    @staticmethod
    def download_custom_website(url_link, title, driver=None):
        soup = get_website_html(url_link, driver=driver, close_driver=False)
        pdf_resource_title = ScrapePISRS.get_resource_title(soup)

        pdf_source_url = ScrapePISRS.get_pdf_source_url(url_link, soup)
        if pdf_source_url:
            raw_data_save_path = os.path.join(RAW_DATA_DIR, f"{make_title_safe(pdf_resource_title)}.pdf")
            if not os.path.exists(raw_data_save_path):
                print(f"Downloading PISRS file: {make_title_safe(pdf_resource_title)} from website {pdf_source_url}")
                try:
                    wget.download(pdf_source_url, raw_data_save_path)
                except Exception as e:
                    print(f"Could not download the file {url_link}. Error: ", e)

            return pdf_source_url, raw_data_save_path
        else:
            print(f"Could not find PISRS file: {make_title_safe(pdf_resource_title)} from website {url_link}")
            return None, None

    @classmethod
    def get_pdf_source_url(cls, file_url, soup):
        # By checking the html of the website, we can see that the pdf file is in the <div id="fileBtns"> element
        # for the data from PiSRS website
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


class ScrapeEURLex(Scraper):
    @staticmethod
    def download_custom_website(url_link, title, driver=None):
        # soup = get_website_html(url_link, driver=driver, close_driver=False)
        # print(soup)
        return


# TODO: Handle too long filename error
if __name__ == "__main__":
    reference_data = ReferencesList(ROOT_URL, METADATA_DIR)

    # Download all the data
    scraper = Scraper(ROOT_URL, os.path.join(METADATA_DIR, "podrocja_list_with_links.csv"), RAW_DATA_DIR)
    scraper.download_all_references()
