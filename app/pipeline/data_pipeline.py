import os
import argparse

from dotenv import load_dotenv, find_dotenv
from ..scraper.references_list import FURSReferencesList
from ..scraper.scraper import Scraper
from ..storage.storage_bucket import download_blob, upload_blob, upload_folder_to_bucket, check_blob_exists
from ..database.vector_store import update_or_create_vector_store
from ..parser.text_parser import Parser

# Load the env variables
load_dotenv(find_dotenv())
ROOT_URL = os.getenv("ROOT_URL")
METADATA_DIR = os.getenv("METADATA_DIR")
RAW_DATA_DIR = os.getenv("RAW_DATA_DIR")
PROCESSED_DATA_DIR = os.getenv("PROCESSED_DATA_DIR")
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
STORAGE_BUCKET_NAME = os.getenv("STORAGE_BUCKET_NAME")


def load_database():
    # If the storage bucket does not contain the database, then we need to call the update_database function
    if (
        STORAGE_BUCKET_NAME is None
        or not check_blob_exists(STORAGE_BUCKET_NAME, "vector_database")
        or not check_blob_exists(STORAGE_BUCKET_NAME, "references.csv")
    ):
        update_database()
    else:
        download_blob(STORAGE_BUCKET_NAME, "references.csv", os.path.join(METADATA_DIR, "references.csv"))
        download_blob(STORAGE_BUCKET_NAME, "vector_database", VECTOR_DB_PATH)


def update_database():
    # 1. Load the backup if it exists
    if STORAGE_BUCKET_NAME is not None:
        reference_data_path = os.path.join(METADATA_DIR, "references.csv")
        download_blob(STORAGE_BUCKET_NAME, "references.csv", reference_data_path)
        download_blob(STORAGE_BUCKET_NAME, "vector_database", VECTOR_DB_PATH)

    # 2. Update the raw sources list; returns the dataframe containing the new references to scrape
    reference_data = FURSReferencesList(ROOT_URL, METADATA_DIR)
    reference_data.update_references()

    # 3. Scrape the data
    scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR)
    scraper.download_all_references()

    # 4. Backup reference.csv file to the storage bucket
    if STORAGE_BUCKET_NAME is not None:
        upload_blob(STORAGE_BUCKET_NAME, os.path.join(METADATA_DIR, "references.csv"), "references.csv")

    # 6. Parse the raw data
    parser = Parser(reference_data_path, RAW_DATA_DIR, PROCESSED_DATA_DIR)
    parser.parse_all_references()

    # 7. Add the processed data to the vector database
    update_or_create_vector_store(VECTOR_DB_PATH, PROCESSED_DATA_DIR)

    # 8. Backup the updated vector store to the storage bucket
    if STORAGE_BUCKET_NAME is not None:
        upload_folder_to_bucket(STORAGE_BUCKET_NAME, VECTOR_DB_PATH, "vector_database")


def main():
    # Pass a command line argument that decides if we simply load or update the database
    parser = argparse.ArgumentParser(description="Update or load the database")
    parser.add_argument("--update", action="store_true", help="Update the database")
    args = parser.parse_args()

    if args.update:
        update_database()
    else:
        load_database()
    return


if __name__ == "__main__":
    main()
