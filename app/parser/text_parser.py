from langchain.document_loaders import PyMuPDFLoader
import pandas as pd


def parse_pdf(path, save_path, file_name=None):
    if file_name is None:
        file_name = path.rsplit("/", maxsplit=1)[-1].rsplit(".", maxsplit=1)[0]
    data = PyMuPDFLoader(path).load()
    text = "".join([d.page_content for d in data])
    with open(save_path, "w") as f:
        f.write(text)


class Parser:
    def __init__(self, references_data_path, raw_dir, processed_dir):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.references_data_path = references_data_path
        self.references_data = pd.read_csv(self.references_data_path, index=False)

    def parse_all_files(self):
        for i, row in self.references_data.iterrows():
            pass
            # file_path = row["actual_download_location"]
            # if file_path.endswith(".pdf"):
            #     parse_pdf(file_path, self.save_path)
