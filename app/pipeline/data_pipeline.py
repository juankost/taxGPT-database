from app.scraper.references_list import FURSReferencesList
from app.scraper.scraper import Scraper
import os
from dontenv import load_dotenv, find_dotenv

# Load the env variables
load_dotenv(find_dotenv())
ROOT_URL = os.getenv("ROOT_URL")
METADATA_DIR = os.getenv("METADATA_DIR")
RAW_DATA_DIR = os.getenv("RAW_DATA_DIR")

ROOT_URL = "https://www.fu.gov.si"
METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data"
RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data/raw_files"


def main():
    # 1. Extract the raw sources list
    reference_data = FURSReferencesList(ROOT_URL, METADATA_DIR)
    reference_data.extract_references()
    reference_data.extract_further_references()

    # 2. Scrape the PiSRIR data
    scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR)
    scraper.references_data = scraper.references_data[
        scraper.references_data["reference_href"].str.startswith("http://www.pisrs.si") is True
    ]
    scraper.download_all_references()

    # 3. Parse the raw data, enrich metadata

    # 4. Add the processed data to the vector database


if __name__ == "__main__":
    main()
