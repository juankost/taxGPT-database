import tiktoken
import logging


def get_context(query, db, k=10, max_context_len=4096, embedding_model="text-embedding-3-large"):
    # Get the top K results
    enc = tiktoken.encoding_for_model(embedding_model)
    docs = db.similarity_search(query, k=k)
    law_articles_text = [doc.page_content for doc in docs]
    law_articles_sources = [doc.metadata for doc in docs]

    logging.info(f"Retrieved {len(law_articles_text)} law articles")

    context = "Here is some relevant context extracted from the law: \n\n"
    for article, source in zip(law_articles_text, law_articles_sources):
        article_context = f"""
        Source: {source["details_href_name"]}\n
        Link: {source["raw_filepath"]}\n
        Text: {article} \n
        """  # noqa: E501
        tokens = enc.encode(context + article_context)
        if len(tokens) < max_context_len:
            context += article_context
    return context


if __name__ == "__main__":
    ROOT_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-backend"
    query = " kdo je davcni rezident Slovenije?"
    from dotenv import load_dotenv, find_dotenv
    from langchain_community.vectorstores import FAISS
    from langchain_openai import OpenAIEmbeddings
    import os

    _ = load_dotenv(find_dotenv())  # read local .env file

    db = FAISS.load_local(
        os.path.join(ROOT_DIR, "data/vector_store/faiss_index_all_laws"), OpenAIEmbeddings()
    )
    context = get_context(query, db)
    print(context)

    # Use timeit to time how long the database takes to load
    import timeit

    print(
        timeit.timeit(
            "FAISS.load_local(os.path.join(ROOT_DIR, 'data/vector_store/faiss_index_all_laws'), OpenAIEmbeddings())",  # noqa: E501
            setup="from langchain_community.vectorstores import FAISS; from langchain_openai import OpenAIEmbeddings",  # noqa: E501
            number=1,
            globals=globals(),
        )
    )
