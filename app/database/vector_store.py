# Create a vector store from the different data sources
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from dotenv import load_dotenv, find_dotenv
import tiktoken
import os

_ = load_dotenv(find_dotenv())  # read local .env file


def check_max_tokens(text, max_tokens=2048):
    enc = tiktoken.encoding_for_model("gpt-4")

    try:
        token_count = len(enc.encode(text))
        if token_count > max_tokens:
            print(f"Exceeded max tokens limit: {token_count}/{max_tokens}")
            return False
        else:
            return True
    except:  # noqa: E722
        print("Error encoding text: ", text)
        return False


def split_long_text(text, max_tokens=2048, overlap_tokens=512):
    enc = tiktoken.encoding_for_model("gpt-4")
    tokens = enc.encode(text)
    if len(tokens) < max_tokens:
        return [text]
    else:
        # Split the text into multiple chunks
        chunks = []
        for i in range(0, len(tokens), max_tokens - overlap_tokens):
            chunks.append(enc.decode(tokens[i : min(i + max_tokens, len(tokens))]))  # noqa: E203
        return chunks


# Now add the new laws to the vector index
def add_text_to_vector_store(path, law, embeddings=None, db=None):
    if embeddings is None:
        embeddings = OpenAIEmbeddings()

    # Open .txt file with the text extracted from the law
    with open(path, "r") as f:
        text = f.read()

    # Split it into chunks
    chunks = split_long_text(text)
    metadatas = [{"law": law, "idx": i} for i in range(len(chunks))]

    if db is None:
        db = FAISS.from_texts(chunks, embeddings, metadatas=metadatas)
    else:
        # TODO: Only add if the law is not already in the store
        # existing_laws = [metadata["law"] for metadata in db.get_all_metadatas()]
        # if law in existing_laws:
        #     return db
        # else:
        db.add_texts(chunks, metadatas=metadatas)

    return db


def update_or_create_vector_store(db_path, processed_data_dir, embeddings=None):
    if embeddings is None:
        embeddings = OpenAIEmbeddings()
    db = None
    if os.path.exists(db_path):
        db = FAISS.load_local(db_path, embeddings)
    for i, file_name in enumerate(os.listdir(processed_data_dir)):
        if i % 10 == 9:
            print(f"Processing file {i+1} of {len(os.listdir(processed_data_dir))}")
        law_title = file_name.rsplit(".", maxsplit=1)[0]
        db = add_text_to_vector_store(
            os.path.join(processed_data_dir, file_name), law_title, embeddings=embeddings, db=db
        )
    return db


if __name__ == "__main__":
    # TODO: Only add new laws to the vector store
    ROOT_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend"
    processed_data_dir = os.path.join(ROOT_DIR, "data/processed_files")
    db_path = os.path.join(ROOT_DIR, "data/vector_store/faiss_index_all_laws")
    update_or_create_vector_store(db_path, processed_data_dir)
