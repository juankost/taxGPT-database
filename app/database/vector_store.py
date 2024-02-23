from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv, find_dotenv
import os
import openai
import tqdm
import json
import backoff
from openai import OpenAI

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

    def __init__(
        self, parsed_data_dir, processed_data_dir, vector_db_path, embedding_model="text-embedding-3-large"
    ) -> None:
        self.embedding_model = embedding_model
        self.embeddings = OpenAIEmbeddings(model=self.embedding_model)
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
        # FOR TESTING PURPOSES
        files_in_dir = os.listdir(self.parsed_data_dir)
        for file_name in tqdm.tqdm(files_in_dir):
            if file_name.endswith(".txt"):
                src_data_path = os.path.join(self.parsed_data_dir, file_name)
                dst_data_path = os.path.join(self.processed_data_dir, file_name)
                src_metadata_path = os.path.join(self.parsed_data_dir, file_name.split(".")[0] + ".metadata")
                dst_metadata_path = os.path.join(self.processed_data_dir, file_name.split(".")[0] + ".metadata")
                self.add_file_to_vector_store(src_data_path, src_metadata_path)
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

        # Embed the documents manually to be able to control the rate limit of OpenAI
        embeddings = self.embed_texts(texts)
        text_embedding_pairs = zip(texts, embeddings)

        if self.db is None:
            self.db = FAISS.from_embeddings(text_embedding_pairs, self.embeddings, metadatas=metadatas)
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
                get_embeddings_with_backoff(texts[i : i + batch_size], model=self.embedding_model)  # noqa: E203
            )  # noqa: E203
        return embeddings


if __name__ == "__main__":
    # For development purposes
    _ = load_dotenv(".env.local")  # read local .env file

    # Download all the data
    METADATA_DIR = os.getenv("METADATA_DIR")
    RAW_DATA_DIR = os.getenv("RAW_DATA_DIR")
    PARSED_DATA_DIR = os.getenv("PARSED_DATA_DIR")
    PROCESSED_DATA_DIR = os.getenv("PROCESSED_DATA_DIR")
    VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
    reference_data_path = os.path.join(METADATA_DIR, "references.csv")

    vector_store = VectorStore(PARSED_DATA_DIR, PROCESSED_DATA_DIR, VECTOR_DB_PATH)
    vector_store.update_or_create_vector_store()

    # embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    # query = "The quick brown fox jumps over the lazy dog."
    # embedding = embeddings.embed_query(query)
    # print(query)
