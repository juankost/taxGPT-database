import os
from langchain.document_loaders import PyMuPDFLoader


def parse_pdf(path, save_path, file_name=None):
    if file_name is None:
        file_name = path.rsplit("/", maxsplit=1)[-1].rsplit(".", maxsplit=1)[0]
    data = PyMuPDFLoader(path).load()
    text = "".join([d.page_content for d in data])
    with open(save_path, "w") as f:
        f.write(text)


# Data Processing steps:
# 1. Parse the text into the semantically meaningful units (i.e. law articles)
# 2. Create a summary of the context for each law article (i.e. summarize what is the law about, and summarize what is
# the seciton about)
# 3. Embed the law article into vector space, create metadata (LAW NAME; SECTION; URL LINK TO LAW)
# 4. Add the law article to the vector database
