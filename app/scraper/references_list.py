"""
This script crawls the fu.gov.si website and extracts all the references denoted there that cover most of the
areas of tax laws.
"""
import os
from selenium import webdriver
import pandas as pd
from ..utils import get_website_html, is_url_to_file, get_chrome_driver  # noqa: E402

ROOT_URL = "https://www.fu.gov.si"


# TODO: Extract information also from 'other_websites'


class FURSReferencesList:
    def __init__(self, root_url, output_dîr):
        self.driver = get_chrome_driver(local=False)
        self.furs_root_url = root_url
        self.furs_overview_url = os.path.join(root_url, "podrocja")
        self.references_data_path = os.path.join(self.output_dir, "references.csv")
        self.output_dir = output_dîr

        # Get the HTML of the overview page
        self.overview_page_soup = get_website_html(self.furs_overview_url, driver=self.driver, close_driver=False)

        # Extract or load the references data (if already extracted)
        if self.references_data_path:
            self.podrocja_list_with_links = pd.read_csv(self.references_data_path)
        else:
            self.podrocja_list_with_links = self.extract_references()
            self.extract_further_references()
        self.driver.close()

    def extract_references(self):
        """
        Extracts references from the HTML content and returns a pandas DataFrame.

        Returns:
            pandas.DataFrame: A DataFrame containing the extracted references with columns:
                - area_name: The name of the law area.
                - area_desc: The description of the area.
                - reference_name: The name of the law reference.
                - reference_href: The URL of the reference.
        """
        data = []
        areas_elements = self.soup.find("div", id="content")
        area_html_elements = areas_elements.find_all("a", href="#")
        for element in area_html_elements:
            area_desc = element.find("em").text
            area_name = element.text.replace(area_desc, "").strip()
            area_siblings = element.parent.find_next_siblings()
            for sibling in area_siblings:
                link_elements = sibling.find_all("li")
                for li in link_elements:
                    link_name = li.text
                    link_href = li.find("a").get("href")
                    if link_href.startswith("/"):
                        link_href = ROOT_URL + link_href
                    data.append([area_name, area_desc, link_name, link_href])

        # Create pandas dataframe to store it
        df = pd.DataFrame(
            data=data,
            columns=["area_name", "area_desc", "reference_name", "reference_href"],
        )
        df.to_csv(self.references_data_path, index=False)
        return df

    def get_list_of_further_website_links(self):
        """
        Retrieves a list of further website links from the references dataframe.

        Returns:
            list: A list of website links.
        """
        website_links = []
        for _, row in self.references.iterrows():
            if row["references_href"].startswith(self.root_url):
                website_links.append(row["reference_href"].split("#")[0])
        website_links = list(set(website_links))
        return website_links

    def is_typical_website(self, soup):
        """
        Checks if the given soup object represents a typical website. We define typical website, as one that has
        the web format of FURS, .i.e. it has the sections: Opis, Podrobnejši opisi, Zakonodaja, Navodila in Pojasnila.

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
            if section_title in ["Opis", "Podrobnejši opisi", "Zakonodaja", "Navodila in Pojasnila"]:
                return True
        return False

    def check_href_type(self, website_links):
        """
        Check the type of href links in a list of website links.

        Parameters:
        website_links (list): A list of website links.

        Returns:
        tuple: A tuple containing three lists - typical_website_links, file_links, and other_websites.
               typical_website_links: List of website links that are considered typical (as the FURS website).
               file_links: List of file links.
               other_websites: List of website links that are not typical or file links.
        """
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

    def extract_further_references(self):
        """
        Extracts further references from the typical websites.
        They go more in depth on specific topics.
        Returns:
            pandas.DataFrame: The extracted references.
        """
        website_links = self.get_list_of_further_website_links()
        typical_website_links, _, _ = self.check_href_type(website_links)

        further_references = None
        # Extract further stuff from the typical websites
        for url_link in typical_website_links:
            df = self.extract_details_typical_website(url_link)
            if further_references is None:
                further_references = df
            else:
                further_references = pd.concat([further_references, df], axis=0)

        # Join the details data with the original data
        self.references["reference_href_clean"] = self.references["reference_href"].apply(lambda x: x.split("#")[0])
        self.references = pd.merge(self.references, further_references, on=["reference_href_clean"], how="left")
        self.references.to_csv(self.references_data_path, index=False)
        return self.references

    def extract_further_references_from_furs_websites(self, url_link):
        """
        Extracts further references from FURS websites that go into more detail for each of the relevant tax areas.

        Args:
            url_link (str): The URL link of the website to scrape.

        Returns:
            pandas.DataFrame: A DataFrame containing the extracted website details, including the reference URL,
            section title, section text, link text, and link URL.
        """
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
                            link_href = self.furs_root_url + link_href
                        website_details.append([url_link, section_title, section_text, link_text, link_href])
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
    METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/tax_backend/data"
    reference_data = FURSReferencesList(ROOT_URL, METADATA_DIR)
