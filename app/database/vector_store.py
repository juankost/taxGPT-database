from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv, find_dotenv
import os
import openai
from tqdm import tqdm
import json
import backoff
import pandas as pd
from openai import OpenAI

_ = load_dotenv(find_dotenv())  # read local .env file
openai.api_key = os.getenv("OPENAI_API_KEY")


class VectorStore:
    """
    Represents a vector store that stores and manages vector embeddings of text data.

    Args:
        file_chunks_data_dir (str): The directory path where the chunked data is stored.
        vector_db_path (str): The directory path where the vector database will be stored.

    """

    def __init__(
        self,
        metadata_dir,
        file_chunks_data_dir,
        vector_db_path,
        embedding_model="text-embedding-3-large",
    ) -> None:
        self.embedding_model = embedding_model
        self.embeddings = OpenAIEmbeddings(model=self.embedding_model)
        self.vector_db_path = vector_db_path
        self.file_chunks_data_dir = file_chunks_data_dir
        self.metadata_dir = metadata_dir
        self.downloaded_data_path = os.path.join(self.metadata_dir, "downloaded_data_index.csv")
        self.db = None

        # Add the "in_vector_db" flag to the downloaded data
        self.downloaded_data = pd.read_csv(self.downloaded_data_path)
        if "in_vector_db" not in self.downloaded_data.columns:
            self.downloaded_data["in_vector_db"] = [False] * len(self.downloaded_data)

        # Make sure the DB directory exists
        os.makedirs(vector_db_path, exist_ok=True)

        index_path = os.path.join(vector_db_path, "index.faiss")
        if os.path.exists(index_path):
            self.db = FAISS.load_local(vector_db_path, self.embeddings)

    def update_or_create_vector_store(self):
        """
        Updates or creates the vector store by processing the parsed data.

        Returns:
            None
        """
        for idx, row in tqdm(self.downloaded_data.iterrows(), total=self.downloaded_data.shape[0]):
            if row["in_vector_db"]:
                continue
            elif pd.isna(row["file_chunks_path"]):
                continue
            else:
                file_path = row["file_chunks_path"]
                file_metadata_path = file_path.rsplit(".")[0] + ".metadata"

                # Add to the vector DB and update the downloaded_data to show it' sin the DB
                try:
                    self.add_file_to_vector_store(file_path, file_metadata_path)
                    self.downloaded_data.loc[idx, "in_vector_db"] = True
                    self.downloaded_data.to_csv(self.downloaded_data_path, index=False)
                except Exception as e:
                    print(f"Error processing file {file_path}. Error: {e}")

                if idx % 100 == 0:
                    self.db.save_local(self.vector_db_path)
        # Save the vector store locally
        self.db.save_local(self.vector_db_path)  # Save on every iteration in case of crash
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
            texts = json.load(f)
        with open(metadata_path, "r") as f:
            metadatas = json.load(f)

        # Embed the documents manually to be able to control the rate limit of OpenAI
        embeddings = self.embed_texts(texts)
        text_embedding_pairs = zip(texts, embeddings)

        if self.db is None:
            self.db = FAISS.from_embeddings(
                text_embedding_pairs, self.embeddings, metadatas=metadatas
            )
        else:
            self.db.add_texts(texts, metadatas=metadatas)

    def embed_texts(self, texts):
        client = OpenAI()
        embeddings = []
        batch_size = 10

        @backoff.on_exception(backoff.expo, openai.RateLimitError)
        def get_embeddings_with_backoff(texts, model="text-embedding-3-large"):
            response = client.embeddings.create(input=texts, model=model)
            embeddings = [None] * len(texts)
            for choice in response.data:
                embeddings[choice.index] = choice.embedding
            return embeddings

        for i in range(0, len(texts), batch_size):
            embeddings.extend(
                get_embeddings_with_backoff(
                    texts[i : i + batch_size], model=self.embedding_model  # noqa: E203
                )
            )  # noqa: E203
        return embeddings


if __name__ == "__main__":
    # For development purposes
    _ = load_dotenv(".env.local")  # read local .env file

    # Download all the data
    METADATA_DIR = os.getenv("METADATA_DIR")
    FILE_CHUNKS_DATA_DIR = os.getenv("PARSED_DATA_DIR")
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

    # vector_store = VectorStore(PARSED_DATA_DIR, PROCESSED_DATA_DIR, VECTOR_DB_PATH)
    # vector_store.update_or_create_vector_store()

    # Test run on the test data
    EMBEDDING_MODEL = "text-embedding-3-small"
    ROOT_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database"
    METADATA_DIR = os.path.join(ROOT_DIR, "data")
    FILE_CHUNKS_DATA_DIR = os.path.join(ROOT_DIR, "data/test_parser/chunks")
    VECTOR_DB_PATH = os.path.join(ROOT_DIR, "data/test_parser/vector_db")
    vector_store = VectorStore(METADATA_DIR, FILE_CHUNKS_DATA_DIR, VECTOR_DB_PATH)
    vector_store.update_or_create_vector_store()

    # embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    # query = "The quick brown fox jumps over the lazy dog."
    # embedding = embeddings.embed_query(query)
    # print(query)
