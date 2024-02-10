from app.scraper.references_list import FURSReferencesList
from app.scraper.scraper import Scraper
import os


FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx"]
ROOT_URL = "https://www.fu.gov.si"
MAIN_URL = ROOT_URL + "/podrocja"
SRC_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/src"
METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data"
RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data/raw_files"
PROCESSED_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data/processed_files"
VECTOR_DB_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data/vector_store"


def main():
    # 1. Extract the raw sources list
    reference_data = FURSReferencesList(ROOT_URL, METADATA_DIR)
    reference_data.extract_references()
    reference_data.extract_further_references()

    # # 2. Scrape the PiSRIR data
    # vector_db_path = os.path.join(VECTOR_DB_DIR, "faiss_index_all_laws")
    scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR)
    scraper.references_data = scraper.references_data[
        scraper.references_data["reference_href"].str.startswith("http://www.pisrs.si") is True
    ]
    scraper.download_all_references()

    # 3. Parse the raw data, enrich metadata

    # 4. Add the processed data to the vector database


if __name__ == "__main__":
    main()
