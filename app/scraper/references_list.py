import os
import pandas as pd
import logging
import uuid
import tqdm
from app.utils import get_website_html, is_url_to_file, get_chrome_driver


class FURSReferencesList:
    def __init__(self, root_url, output_dîr, local=False):
        self.driver = get_chrome_driver(local=local)
        self.furs_root_url = root_url
        self.furs_overview_url = os.path.join(root_url, "podrocja")
        self.output_dir = output_dîr
        self.references_data_path = os.path.join(self.output_dir, "references.csv")

        logging.info("Getting the HTML of the overview page")
        self.overview_page_soup = get_website_html(
            self.furs_overview_url, driver=self.driver, close_driver=False
        )

    def update_references(self):
        logging.info("Starring the references update process")
        if os.path.exists(self.references_data_path):
            logging.info("Backup references list found. Loading it.")
            self.backup_references_list = pd.read_csv(self.references_data_path)
            self.scrape_references(save=False)
        else:
            logging.info("No backup references list found. Scraping the references.")
            self.backup_references_list = None
            self.scrape_references(save=False)
        logging.info("Comparing the references to the backup. Saving the updated references list.")
        self.compare_references_to_backup()
        self.driver.close()

    def compare_references_to_backup(self):
        """
        Compares the references in the current `references_list` DataFrame to the backup
        references list. Adds flag to show if reference is new or not.
        Saves the updated references list to the `references_data_path`.
        """
        if self.backup_references_list is None:
            self.references_list["is_scraped"] = [False] * len(self.references_list)
            # Create file_id
            self.references_list["file_id"] = [
                uuid.uuid4() for _ in range(len(self.references_list))
            ]
            os.makedirs(self.output_dir, exist_ok=True)
            self.references_list.to_csv(self.references_data_path, index=False)
            print("Saved to: ", self.references_data_path)
            return
        else:
            diff = self.references_list[
                ~self.references_list.reference_href.isin(
                    self.backup_references_list.reference_href
                )
            ]
            diff = diff[~diff.details_href.isin(self.backup_references_list.details_href)]
            diff["is_scraped"] = [False] * len(diff)
            diff["file_id"] = [uuid.uuid4() for _ in range(len(diff))]
            union = pd.concat([self.backup_references_list, diff], axis=0)
            os.makedirs(self.output_dir, exist_ok=True)
            union.to_csv(self.references_data_path, index=False)
            return

    def scrape_references(self, save=True):
        logging.info("Scraping the references")
        self.references_list = self.extract_references()
        logging.info(
            "Extracted main references. Extracting further references from the linked websites."
        )
        self.extract_further_references()
        if save:
            logging.info("Saving the references list to the output directory")
            os.makedirs(self.output_dir, exist_ok=True)
            self.references_list.to_csv(self.references_data_path, index=False)
        logging.info("Finished extracting the references list.")

    def extract_references(self):
        """
        Extracts references from the HTML content and returns a pandas DataFrame.


        https://fu.gov.si/podrocja/ --> it crawls on this page and extracts all the links and
        descriptions of the areas

        Returns:
            pandas.DataFrame: A DataFrame containing the extracted references with columns:
                - area_name: The name of the law area.
                - area_desc: The description of the area.
                - reference_name: The name of the law reference.
                - reference_href: The URL of the reference.
        """
        data = []
        areas_elements = self.overview_page_soup.find("div", id="content")
        area_html_elements = areas_elements.find_all("a", href="#")
        for element in tqdm.tqdm(area_html_elements):
            area_desc = element.find("em").text
            area_name = element.text.replace(area_desc, "").strip()
            area_siblings = element.parent.find_next_siblings()
            for sibling in area_siblings:
                link_elements = sibling.find_all("li")
                for li in link_elements:
                    link_name = li.text
                    link_href = li.find("a").get("href")
                    if link_href.startswith("/"):
                        link_href = self.furs_root_url + link_href
                    data.append([area_name, area_desc, link_name, link_href])

        # Create pandas dataframe to store it
        df = pd.DataFrame(
            data=data,
            columns=["area_name", "area_desc", "reference_name", "reference_href"],
        )
        return df

    def extract_further_references(self):
        """
        Extracts further references from the typical websites.
        They go more in depth on specific topics.
        Returns:
            pandas.DataFrame: The extracted references.
        """
        logging.info("Getting list of further website links to scrape for more references")
        website_links = self.get_list_of_further_website_links()
        logging.info("Checking the type of extracted href links")
        typical_website_links, _, _ = self.check_href_type(website_links)

        logging.info("Extracting further references from the typical websites")
        further_references = None
        for url_link in tqdm.tqdm(typical_website_links, position=0, leave=True):
            df = self.extract_further_references_from_furs_websites(url_link)
            if further_references is None:
                further_references = df
            else:
                further_references = pd.concat([further_references, df], axis=0)

        # Join the details data with the original data
        self.references_list["reference_href_clean"] = self.references_list["reference_href"].apply(
            lambda x: x.split("#")[0]
        )
        self.references_list = pd.merge(
            self.references_list, further_references, on=["reference_href_clean"], how="left"
        )
        os.makedirs(self.output_dir, exist_ok=True)
        self.references_list.to_csv(self.references_data_path, index=False)
        return self.references_list

    def get_list_of_further_website_links(self):
        """
        Retrieves a list of further website links from the references dataframe.

        Returns:
            list: A list of website links.
        """
        website_links = []
        for _, row in tqdm.tqdm(self.references_list.iterrows()):
            if row["reference_href"].startswith(self.furs_root_url):
                website_links.append(row["reference_href"].split("#")[0])
        website_links = list(set(website_links))
        return website_links

    def check_href_type(self, website_links):
        """
        Check the type of href links in a list of website links.

        Parameters:
        website_links (list): A list of website links.

        Returns:
        tuple: A tuple containing three lists - typical_website_links, file_links, and other_websites. # noqa: E501
               typical_website_links: List of website links that are considered typical (as the FURS website). # noqa: E501
               file_links: List of file links.
               other_websites: List of website links that are not typical or file links.
        """
        typical_website_links = []
        file_links = []
        other_websites = []
        for url_link in tqdm.tqdm(website_links):
            if not url_link.startswith(self.furs_root_url):
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
        """
        Checks if the given soup object represents a typical website. We define typical website, as one that has # noqa: E501
        the web format of FURS, .i.e. it has the sections: Opis, Podrobnejši opisi, Zakonodaja, Navodila in Pojasnila. # noqa: E501

        Parameters:
        - soup: BeautifulSoup object representing the HTML content of a website.

        Returns:
        - True if the website is typical, False otherwise.
        """
        content_element = soup.find("div", id="content")
        if content_element is None:
            return False

        sections = content_element.find_all("a", href="#")
        for section in sections:
            section_title = section.text.strip()
            if section_title in [
                "Opis",
                "Podrobnejši opisi",
                "Zakonodaja",
                "Navodila in Pojasnila",
            ]:
                return True
        return False

    def extract_further_references_from_furs_websites(self, url_link):
        """
        Extracts further references from FURS websites that go into more detail for each of the relevant tax areas. # noqa: E501

        Args:
            url_link (str): The URL link of the website to scrape.

        Returns:
            pandas.DataFrame: A DataFrame containing the extracted website details, including the reference URL, # noqa: E501
            section title, section text, link text, and link URL.
        """
        soup = get_website_html(url_link, driver=self.driver, close_driver=False)

        # Find the relevant sections: Opis, Podrobnejši opisi, Zakonodaja, Navodila in Pojasnila
        content_element = soup.find("div", id="content")
        if content_element is None:
            return None

        website_details = []
        sections = content_element.find_all("a", href="#")
        for section in tqdm.tqdm(sections, leave=False, position=1):
            section_title = section.text.strip()
            if section_title in [
                "Opis",
                "Podrobnejši opisi",
                "Zakonodaja",
                "Navodila in Pojasnila",
            ]:
                section_text = ""
                section_siblings = section.parent.find_next_siblings()
                for sibling in section_siblings:
                    section_text = section_text + "\n" + sibling.get_text()
                    # Clean up text - remove special characters that are not the common one (e.g. (, ), -, etc.) # noqa: E501
                    section_text = section_text.replace(" Bigstock", " ").strip()
                    section_links = sibling.find_all("a", href=True)
                    for link in section_links:
                        link_text = link.text.strip()
                        link_href = link.get("href")
                        if link_href.startswith("/"):
                            link_href = self.furs_root_url + link_href
                        website_details.append(
                            [url_link, section_title, section_text, link_text, link_href]
                        )
        df = pd.DataFrame(
            data=website_details,
            columns=[
                "reference_href_clean",
                "details_section",
                "details_section_text",
                "details_href_name",
                "details_href",
            ],
        )
        return df


if __name__ == "__main__":
    ROOT_URL = "https://www.fu.gov.si"
    METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data"
    reference_data = FURSReferencesList(ROOT_URL, METADATA_DIR, local=True)
    reference_data.update_references()
