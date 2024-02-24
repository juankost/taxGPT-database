import tiktoken
import logging


def get_context(query, db, k=10, max_context_len=4096, embedding_model="text-embedding-3-large"):
    # Get the top K results
    enc = tiktoken.encoding_for_model(embedding_model)
    docs = db.similarity_search(query, k=k)
    law_articles_text = [doc.page_content for doc in docs]
    law_articles_sources = [doc.metadata for doc in docs]

    logging.info(f"Retrieved {len(law_articles_text)} law articles")
    logging.info(law_articles_sources[0])
    logging.info(law_articles_text[0])

    context = "Relevant law articles: \n "
    for article, source in zip(law_articles_text, law_articles_sources):
        tokens = enc.encode(context + f"{source['law']}: {article}  #### \n")
        if len(tokens) < max_context_len:
            context += f"{source['law']}: {article}  #### \n \n"
    return context


if __name__ == "__main__":
    ROOT_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend"
    query = " kdo je davcni rezident Slovenije?"
    from dotenv import load_dotenv, find_dotenv
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
    import os

    _ = load_dotenv(find_dotenv())  # read local .env file

    db = FAISS.load_local(os.path.join(ROOT_DIR, "data/vector_store/faiss_index_all_laws"), OpenAIEmbeddings())
    context = get_context(query, db)
    print(context)

    # Use timeit to time how long the database takes to load
    import timeit

    print(
        timeit.timeit(
            "FAISS.load_local(os.path.join(ROOT_DIR, 'data/vector_store/faiss_index_all_laws'), OpenAIEmbeddings())",
            setup="from langchain_community.vectorstores import FAISS; from langchain_openai import OpenAIEmbeddings",
            number=1,
            globals=globals(),
        )
    )
