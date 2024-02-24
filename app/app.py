import os
import openai
from fastapi import FastAPI
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel
from langchain_community.vectorstores.faiss import FAISS
from .retrieval.retrieval import get_context


class Query(BaseModel):
    query: str
    k: int = 10
    max_context_len: int = 4096


class Context(BaseModel):
    context: str


# Get the Environment variables
_ = load_dotenv(find_dotenv())  # read local .env file
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize the vector store
model = os.environ["EMBEDDING_MODEL"]
embeddings = OpenAIEmbeddings(model=model)
try:
    DB_PATH = os.getenv("VECTOR_DB_PATH")
    db = FAISS.load_local(DB_PATH, embeddings)
except Exception as e:
    print("Error loading the database", e)
    db = None

# Create the FastAPI app
app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/get_context", response_model=Context)
def get_context_api(message: Query):
    query = message.query
    k = message.k
    max_context_len = message.max_context_len
    context = get_context(query, db, k, max_context_len)
    return {"context": context}


# TODO: API Route to retrieve the actual document based on the metadata?
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
