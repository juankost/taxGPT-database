import os
from langchain.document_loaders import PyMuPDFLoader


def parse_pdf(path, save_path, file_name=None):
    if file_name is None:
        file_name = path.rsplit("/", maxsplit=1)[-1].rsplit(".", maxsplit=1)[0]
    data = PyMuPDFLoader(path).load()
    text = "".join([d.page_content for d in data])
    with open(save_path, "w") as f:
        f.write(text)
