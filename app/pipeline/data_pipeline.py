from ..scraper.references_list import FURSReferencesList
from ..scraper.scraper import Scraper
import os
from dotenv import load_dotenv, find_dotenv

# Load the env variables
load_dotenv(find_dotenv())
ROOT_URL = os.getenv("ROOT_URL")
METADATA_DIR = os.getenv("METADATA_DIR")
RAW_DATA_DIR = os.getenv("RAW_DATA_DIR")


def main():
    # 1. Extract the raw sources list
    reference_data = FURSReferencesList(ROOT_URL, METADATA_DIR)
    reference_data.extract_references()
    reference_data.extract_further_references()

    # 2. Check if there is already vector database backup in storage bucket
    # backup_reference_data = load_backup_reference_data()  # loads reference data, and vector database if they exist

    # 3. Compare the new data with the backup data
    new_references = compare_references_to_backup(reference_data, backup_reference_data)

    if len(new_references) > 0:
        # 2. Scrape the PiSRIR data
        scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR)
        # WORKAROUND, SINCE WE ONLY SUPPORT SCRAPING PISRS CURRENTLY
        scraper.references_data = scraper.references_data[
            scraper.references_data["reference_href"].str.startswith("http://www.pisrs.si") is True
        ]
        scraper.download_all_references()

        # 3. Parse the raw data, enrich metadata

        # 4. Add the processed data to the vector database
        # add_new_data_to_vector_db()

        # 5. Backup the new data to the storage bucket
        # backup_new_data_to_bucket()


if __name__ == "__main__":
    main()
