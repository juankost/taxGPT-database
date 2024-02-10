import pandas as pd
from scraper.raw_sources_list import extract_davcna_podrocja_info, extract_source_files_paths
from scraper.scrape_pisrs_sources import get_pisrs_data
from database.vector_store import update_or_create_vector_store
import os

FILE_EXTENSIONS = ["docx", "doc", "pdf", "zip", "xlsx"]
ROOT_URL = "https://www.fu.gov.si"
MAIN_URL = ROOT_URL + "/podrocja"
SRC_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/src"
METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data"
RAW_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data/raw_files"
PROCESSED_DATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data/processed_files"
VECTOR_DB_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend/data/vector_store"


def get_raw_sources_list(metadata_dir):
    data = extract_davcna_podrocja_info(metadata_dir)
    raw_sources_list = extract_source_files_paths(data, metadata_dir)
    return raw_sources_list


def main():
    # 1. Extract the raw sources list
    if not os.path.exists(os.path.join(METADATA_DIR, "furs_data.csv")):
        print("Getting raw sources list")
        raw_sources_list = pd.read_csv(os.path.join(METADATA_DIR, "raw_sources_list.csv"))
    else:
        raw_sources_list = pd.read_csv(os.path.join(METADATA_DIR, "furs_data.csv"))

    # 2. Scrape the PiSRIR data
    vector_db_path = os.path.join(VECTOR_DB_DIR, "faiss_index_all_laws")
    df_pisrs = raw_sources_list[raw_sources_list["file_url"].str.startswith("http://www.pisrs.si") is True].copy()
    get_pisrs_data(df_pisrs)
    db = update_or_create_vector_store(vector_db_path, PROCESSED_DATA_DIR)
    db.save_local()


if __name__ == "__main__":
    main()
