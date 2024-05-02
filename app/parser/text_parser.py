from dotenv import load_dotenv
import pandas as pd
import os
import json
import tiktoken
import html2text
import subprocess
from tqdm import tqdm
from tabulate import tabulate
from marker.convert import convert_single_pdf
from marker.models import load_all_models


class FileProcessor:
    def __init__(self, converted_data_dir, metadata_dir):
        self.converted_data_dir = converted_data_dir
        self.metadata_dir = metadata_dir
        self.downloaded_data = pd.read_csv(os.path.join(metadata_dir, "downloaded_data_index.csv"))

    def convert_all_files(self):
        for idx, row in tqdm(self.downloaded_data.iterrows(), total=self.downloaded_data.shape[0]):

            file_type = row["file_type"]
            original_path = row["downloaded_path"]
            converted_path = row["processed_filepath"]
            file_name = os.path.splitext(os.path.basename(original_path))[0]
            expected_save_path = os.path.join(self.converted_data_dir, file_name + ".md")
            if pd.notna(converted_path) and os.path.exists(converted_path):
                continue  # Skip processing if the file already exists
            elif os.path.exists(expected_save_path) and pd.isna(converted_path):
                self.downloaded_data.at[idx, "processed_filepath"] = expected_save_path
                self.downloaded_data.to_csv(
                    os.path.join(self.metadata_dir, "downloaded_data_index.csv"), index=False
                )
                continue

            try:
                if file_type == "pdf":
                    saved_path = self.convert_pdf_to_md(original_path, file_name)
                elif file_type == "html":
                    saved_path = self.convert_html_to_md(original_path, file_name)
                elif file_type == "docx":
                    saved_path = self.convert_docx_to_md(original_path, file_name)
                elif file_type == "doc":
                    saved_path = self.convert_doc_to_md(original_path, file_name)
                elif file_type == "xlsx":
                    saved_path = self.convert_xlsx_to_md(original_path, file_name)
                else:
                    print(f"File type not supported for parsing. File: {original_path}")
                    continue
            except Exception as e:
                print(f"File {original_path} could not be converted to md. Error: {e}")
                saved_path = None

            print("Converted file.")
            self.downloaded_data.at[idx, "processed_filepath"] = saved_path
            self.downloaded_data.to_csv(
                os.path.join(self.metadata_dir, "downloaded_data_index.csv"), index=False
            )

    def convert_pdf_to_md(self, path, file_name):
        model_lst = load_all_models()
        full_text, out_meta = convert_single_pdf(path, model_lst, parallel_factor=1)

        save_path = os.path.join(self.converted_data_dir, file_name + ".md")
        with open(save_path, "w+", encoding="utf-8") as f:
            f.write(full_text)
        return save_path

    def convert_html_to_md(self, path, file_name):
        h = html2text.HTML2Text()
        h.ignore_links = True
        save_path = os.path.join(self.converted_data_dir, file_name + ".md")

        with open(path, "r") as fin:
            markdown_content = h.handle(fin.read())
            with open(save_path, "w") as fout:
                fout.write(markdown_content)

        return save_path

    def convert_docx_to_md(self, path, file_name):
        save_path = os.path.join(self.converted_data_dir, file_name + ".md")
        command = f"pandoc -f docx -t markdown -o {save_path} {path}"
        subprocess.run(command, shell=True)
        return save_path

    def convert_doc_to_md(self, path, file_name):
        # Convert .doc to .docx using LibreOffice
        temp_docx_path = os.path.join(self.converted_data_dir, file_name + ".docx")
        convert_command = f"soffice --convert-to docx {path} --outdir {self.converted_data_dir}"
        subprocess.run(convert_command, shell=True)

        # Now convert the .docx to .md using pandoc
        save_path = os.path.join(self.converted_data_dir, file_name + ".md")
        pandoc_command = f"pandoc -f docx -t markdown -o {save_path} {temp_docx_path}"
        subprocess.run(pandoc_command, shell=True)

        # Optionally, remove the temporary .docx file if no longer needed
        os.remove(temp_docx_path)

        return save_path

    def convert_xlsx_to_md(self, path, file_name):
        df = pd.read_excel(path)
        markdown_content = tabulate(df, headers="keys", tablefmt="pipe", showindex=False)
        save_path = os.path.join(self.converted_data_dir, file_name + ".md")

        with open(save_path, "w") as file:
            file.write(markdown_content)

        return save_path


class TextProcessor:
    def __init__(
        self,
        metadata_dir,
        converted_data_dir,
        file_chunks_data_dir,
        embedding_model="text-embedding-3-large",
        max_tokens=2048,
        overlap_tokens=512,
    ):

        self.converted_data_dir = converted_data_dir
        self.metadata_dir = metadata_dir
        self.file_chunks_data_dir = file_chunks_data_dir
        self.downloaded_data = pd.read_csv(os.path.join(metadata_dir, "downloaded_data_index.csv"))
        # self.reference_data = pd.read_csv(os.path.join(metadata_dir, "references_data.csv"))
        self.embedding_model = embedding_model
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        os.makedirs(self.file_chunks_data_dir, exist_ok=True)

        # Add a column to the downloaded data, if it does not yet exist:
        if "file_chunks_path" not in self.downloaded_data.columns:
            self.downloaded_data["file_chunks_path"] = pd.Series(dtype="string")

    def chunk_all_files(self):
        for idx, row in tqdm(self.downloaded_data.iterrows()):
            processed_path = row["processed_filepath"]  # input path
            file_chunks_path = row["file_chunks_path"]  # output path

            # Convert any inf/nan/none to None, and skip the file if it is None
            if pd.isna(processed_path) or not os.path.exists(processed_path):
                continue

            # Expected output path based on input path
            file_name = os.path.splitext(os.path.basename(processed_path))[0]
            chunk_text_save_path = os.path.join(self.file_chunks_data_dir, file_name + ".txt")
            chunk_metadata_save_path = os.path.join(
                self.file_chunks_data_dir, file_name + ".metadata"
            )

            # Check conditions
            if not pd.isna(file_chunks_path) and os.path.exists(file_chunks_path):
                continue  # Skip, output already exists
            elif pd.isna(file_chunks_path) and os.path.exists(chunk_text_save_path):
                # Expected output exists, but not logged. Add to reference data and skip
                self.downloaded_data.at[idx, "file_chunks_path"] = chunk_text_save_path
                self.downloaded_data.to_csv(
                    os.path.join(self.metadata_dir, "downloaded_data_index.csv"), index=False
                )
                continue
            else:

                # Chunk the file
                chunks, chunks_metadata = self.chunk_file(processed_path)

                # Create the file level metadata (i.e. description of tax area,
                #  when was the file parsed, etc.)
                file_metadata = self.create_file_metadata(row)
                for chunk_metadata in chunks_metadata:
                    chunk_metadata.update(file_metadata)

                # Save the chunks and their metadata
                with open(chunk_text_save_path, "w") as f:
                    f.write(json.dumps(chunks))
                with open(chunk_metadata_save_path, "w") as f:
                    f.write(json.dumps(chunks_metadata))

    def chunk_file(self, file_path):
        with open(file_path, "r") as file:
            text = file.read()

        enc = tiktoken.encoding_for_model(self.embedding_model)
        tokens = enc.encode(text)
        chunks = []
        for i in range(0, len(tokens), self.max_tokens - self.overlap_tokens):
            chunk_text = enc.decode(tokens[i : min(i + self.max_tokens, len(tokens))])  # noqa E203
            chunks.append(chunk_text)

        # Create chunk metadata (placeholder for now)
        chunk_metadata = [{"chunk_idx": idx} for idx in range(len(chunks))]
        return chunks, chunk_metadata

    def create_file_metadata(self, row):
        file_metadata = {
            "date_downloaded": row["date_downloaded"],
            "area_name": row["area"],
            "reference_name": row["subarea"],
            "details_section": row["section"],
            "details_href_name": row["filename"],
            "raw_filepath": row["raw_filepath"],
        }
        return file_metadata


if __name__ == "__main__":
    # For development purposes
    _ = load_dotenv(".env.local")  # read local .env file

    # Set up directories
    METADATA_DIR = os.getenv("METADATA_DIR")
    CONVERTED_DATA_DIR = os.getenv("CONVERTED_DATA_DIR")
    FILE_CHUNKS_DATA_DIR = os.getenv("FILE_CHUNKS_DATA_DIR")

    # METADATA_DIR = "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/"
    # CONVERTED_DATA_DIR = (
    #     "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/test_parser"
    # )
    # FILE_CHUNKS_DATA_DIR = (
    #     "/Users/juankostelec/Google_drive/Projects/taxGPT-database/data/test_parser/chunks"
    # )

    # Create an instance of FileProcessor
    file_processor = FileProcessor(CONVERTED_DATA_DIR, METADATA_DIR)
    file_processor.convert_all_files()
    text_processor = TextProcessor(METADATA_DIR, CONVERTED_DATA_DIR, FILE_CHUNKS_DATA_DIR)
    text_processor.chunk_all_files()
