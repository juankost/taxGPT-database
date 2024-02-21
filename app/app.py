import os
import openai
from flask import Flask, jsonify
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel

# from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.faiss import FAISS
from .retrieval.retrieval import get_context


class Query(BaseModel):
    query: str
    k: int = 10
    max_context_len: int = 4096


# Get the Environment variables
_ = load_dotenv(find_dotenv())  # read local .env file
openai.api_key = os.getenv("OPENAI_API_KEY")

# Create the Flask app
app = Flask(__name__)

# Initialize the vector store
DB_PATH = os.getenv("VECTOR_DB_PATH")
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
db = FAISS.load_local(DB_PATH, embeddings)


# Create the API route to retrieve context
@app.route("/get_context", methods=["POST"])
def get_context_api(message: Query):
    query = message.query
    k = message.k
    max_context_len = message.max_context_len
    context = get_context(query, db, k, max_context_len)
    return jsonify(context)


# TODO: API Route to retrieve the actual document based on the metadata?
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
