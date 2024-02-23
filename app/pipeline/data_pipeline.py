import os
import argparse
import logging
import openai
from dotenv import load_dotenv, find_dotenv
from ..scraper.references_list import FURSReferencesList
from ..scraper.scraper import Scraper
from ..storage.storage_bucket import (
    download_blob,
    download_folder,
    upload_blob,
    upload_folder_to_bucket,
    check_blob_exists,
    check_folder_exists,
)
from ..database.vector_store import VectorStore
from ..parser.text_parser import Parser


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def load_database(local=False):
    # Read the relevant env variables
    METADATA_DIR = os.getenv("METADATA_DIR")
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
    STORAGE_BUCKET_NAME = os.getenv("STORAGE_BUCKET_NAME")

    # If the storage bucket does not contain the database, then we need to call the update_database function
    if (
        STORAGE_BUCKET_NAME is None
        or not check_folder_exists(STORAGE_BUCKET_NAME, "vector_database", local=local)
        or not check_blob_exists(STORAGE_BUCKET_NAME, "references.csv", local=local)
    ):
        logging.info("Database not found in the storage bucket. Updating the database.")
        update_database(local=local)
    else:
        logging.info("Database found in the storage bucket. Downloading the database.")

        os.makedirs(METADATA_DIR, exist_ok=True)
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)
        download_blob(STORAGE_BUCKET_NAME, "references.csv", os.path.join(METADATA_DIR, "references.csv"), local=local)
        download_folder(STORAGE_BUCKET_NAME, "vector_database", VECTOR_DB_PATH, local=local)


def update_database(local=False):
    # Read the relevant env variables
    ROOT_URL = os.getenv("ROOT_URL")
    METADATA_DIR = os.getenv("METADATA_DIR")
    RAW_DATA_DIR = os.getenv("RAW_DATA_DIR")
    PARSED_DATA_DIR = os.getenv("PARSED_DATA_DIR")
    PROCESSED_DATA_DIR = os.getenv("PROCESSED_DATA_DIR")
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
    STORAGE_BUCKET_NAME = os.getenv("STORAGE_BUCKET_NAME")
    reference_data_path = os.path.join(METADATA_DIR, "references.csv")

    logging.info("Updating the database")

    # 1. Load the backup if it exists - we only load the references.csv file if the vector database exists
    if STORAGE_BUCKET_NAME is not None and check_folder_exists(STORAGE_BUCKET_NAME, "vector_database", local=local):
        os.makedirs(METADATA_DIR, exist_ok=True)
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)
        download_blob(STORAGE_BUCKET_NAME, "references.csv", reference_data_path, local=local)
        download_folder(STORAGE_BUCKET_NAME, "vector_database", VECTOR_DB_PATH, local=local)

    # 2. Update the raw sources list; returns the dataframe containing the new references to scrape
    logging.info("Updating the raw sources list")
    reference_data = FURSReferencesList(ROOT_URL, METADATA_DIR, local=local)
    reference_data.update_references()

    # 3. Scrape the data
    logging.info("Scraping the data")
    scraper = Scraper(os.path.join(METADATA_DIR, "references.csv"), RAW_DATA_DIR, local=local)
    scraper.download_all_references()

    # 4. Backup reference.csv file to the storage bucket
    if STORAGE_BUCKET_NAME is not None:
        logging.info(f"Uploading references.csv to the storage bucket {STORAGE_BUCKET_NAME}")
        upload_blob(STORAGE_BUCKET_NAME, os.path.join(METADATA_DIR, "references.csv"), "references.csv", local=local)

    # 6. Parse the raw data
    logging.info("Parsing the raw data")
    parser = Parser(reference_data_path, RAW_DATA_DIR, PARSED_DATA_DIR, local=local)
    parser.parse_all_files()

    # 7. Add the processed data to the vector database
    logging.info("Adding the processed data to the vector database")
    vector_store = VectorStore(PARSED_DATA_DIR, PROCESSED_DATA_DIR, VECTOR_DB_PATH)
    vector_store.update_or_create_vector_store()

    # 8. Backup the updated vector store to the storage bucket
    if STORAGE_BUCKET_NAME is not None:
        logging.info("Uploading vector database to the storage bucket")
        upload_folder_to_bucket(STORAGE_BUCKET_NAME, VECTOR_DB_PATH, "vector_database", local=local)


def main():
    # Pass a command line argument that decides if we simply load or update the database
    parser = argparse.ArgumentParser(description="Update or load the database")
    parser.add_argument("--update", action="store_true", help="Update the database")
    parser.add_argument("--local", action="store_true", help="For running on local machine. Debugging purposes.")
    args = parser.parse_args()

    logging.info("Loading the environment variables")
    if args.local:
        load_dotenv(".env.local", override=True, verbose=True)
    else:
        load_dotenv(find_dotenv())
    openai.api_key = os.getenv("OPENAI_API_KEY")

    if args.update:
        logging.info("Updating the database")
        update_database(local=args.local)
    else:
        logging.info("Loading the database")
        load_database(local=args.local)
    return


if __name__ == "__main__":
    main()
