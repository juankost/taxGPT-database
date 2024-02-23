# Create a vector store from the different data sources
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv, find_dotenv
import tiktoken
import os
import openai
import tqdm
import json

_ = load_dotenv(find_dotenv())  # read local .env file
openai.api_key = os.getenv("OPENAI_API_KEY")


class VectorStore:
    """
    Represents a vector store that stores and manages vector embeddings of text data.

    Args:
        parsed_data_dir (str): The directory path where the parsed data is stored.
        processed_data_dir (str): The directory path where the processed data will be stored.
        vector_db_path (str): The directory path where the vector database will be stored.

    Attributes:
        embeddings (OpenAIEmbeddings): The embeddings model used for generating vector embeddings.
        vector_db_path (str): The directory path where the vector database is stored.
        parsed_data_dir (str): The directory path where the parsed data is stored.
        processed_data_dir (str): The directory path where the processed data is stored.
        db (FAISS): The FAISS index for storing and querying vector embeddings.

    Methods:
        update_or_create_vector_store: Updates or creates the vector store by processing the parsed data.
        add_file_to_vector_store: Adds a file to the vector store by extracting text chunks and their metadata.

    """

    def __init__(self, parsed_data_dir, processed_data_dir, vector_db_path) -> None:
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        self.vector_db_path = vector_db_path
        self.parsed_data_dir = parsed_data_dir
        self.processed_data_dir = processed_data_dir
        self.db = None

        # Make sure the DB directory exists
        os.makedirs(vector_db_path, exist_ok=True)
        os.makedirs(processed_data_dir, exist_ok=True)

        index_path = os.path.join(vector_db_path, "index.faiss")
        if os.path.exists(index_path):
            self.db = FAISS.load_local(vector_db_path, self.embeddings)

    def update_or_create_vector_store(self):
        """
        Updates or creates the vector store by processing the parsed data.

        Returns:
            None

        """
        files_in_dir = os.listdir(self.parsed_data_dir)
        for file_name in tqdm.tqdm(files_in_dir):
            if file_name.endswith(".txt"):
                src_data_path = os.path.join(self.parsed_data_dir, file_name)
                dst_data_path = os.path.join(self.processed_data_dir, file_name)
                src_metadata_path = os.path.join(self.parsed_data_dir, file_name.split(".")[0] + ".metadata")
                dst_metadata_path = os.path.join(self.processed_data_dir, file_name.split(".")[0] + ".metadata")
                self.add_file_to_vector_stores(src_data_path, src_metadata_path)
                os.rename(src_data_path, dst_data_path)
                os.rename(src_metadata_path, dst_metadata_path)

        # Save the vector store locally
        self.db.save_local(self.vector_db_path)
        return

    def add_file_to_vector_store(self, data_path, metadata_path):
        """
        Adds a file to the vector store by extracting text chunks and their metadata.

        Args:
            data_path (str): The path of the file containing the text chunks.
            metadata_path (str): The path of the file containing the metadata.

        Returns:
            None

        """
        with open(data_path, "r") as f:
            chunks = json.load(f)
            texts = [chunk["content"] for chunk in chunks]  # FAISS expects the chunks of data to be a list of strings
        with open(metadata_path, "r") as f:
            metadatas = json.load(f)

        if self.db is None:
            self.db = FAISS.from_texts(texts, self.embeddings, metadatas=metadatas)
        else:
            self.db.add_texts(texts, metadatas=metadatas)


if __name__ == "__main__":
    # ROOT_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend"
    # processed_data_dir = os.path.join(ROOT_DIR, "data/processed_files")
    # db_path = os.path.join(ROOT_DIR, "data/vector_store/faiss_index_all_laws")
    # update_or_create_vector_store(db_path, processed_data_dir)
