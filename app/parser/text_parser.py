from langchain_community.document_loaders import PyMuPDFLoader
import pandas as pd
import os


class Parser:
    def __init__(self, references_data_path, raw_dir, processed_dir, local=False):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.references_data_path = references_data_path
        self.references_data = pd.read_csv(self.references_data_path)

        # Make sure the output dir exists
        os.makedirs(processed_dir, exist_ok=True)

    def parse_all_files(self):
        for i, row in tqdm.tqdm(self.references_data.iterrows()):
            if not row["is_processed"] or pd.isna(row["actual_download_location"]):
                continue
            file_path = row["actual_download_location"]
            if file_path.endswith(".pdf"):
                Parser.parse_pdf_file(file_path, self.processed_dir)

    @staticmethod
    def parse_pdf_file(path, output_dir, file_name=None):
        if file_name is None:
            file_name = path.rsplit("/", maxsplit=1)[-1].rsplit(".", maxsplit=1)[0]
        save_path = os.path.join(output_dir, file_name + ".txt")
        try:
            data = PyMuPDFLoader(path).load()
            text = "".join([d.page_content for d in data])
            with open(save_path, "w") as f:
                f.write(text)
        except Exception as e:
            print(e)
            print("\n-----------------------------------\n")

    def create_file_metadata(self, file_name):
        law_title = file_name.rsplit(".", maxsplit=1)[0]
        metadata = {"law_title": law_title}
        metadata_json = json.dumps(metadata)

        save_path = os.path.join(self.parsed_data_dir, file_name.split(".")[0] + ".metadata")
        with open(save_path, "w") as f:
            f.write(metadata_json)

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
