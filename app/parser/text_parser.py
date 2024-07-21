from dotenv import load_dotenv
import pandas as pd
import os
import json
import tiktoken
import re
import html2text
import subprocess
from tqdm import tqdm
from tabulate import tabulate
from app.utils import suppress_logging, restore_logging
from marker.convert import convert_single_pdf
from marker.models import load_all_models


class FileProcessor:
    def __init__(self, converted_data_dir, metadata_dir):
        self.converted_data_dir = converted_data_dir
        self.metadata_dir = metadata_dir
        self.downloaded_data = pd.read_csv(os.path.join(metadata_dir, "downloaded_data_index.csv"))
        self.model_list = None

    def convert_all_files(self):
        for idx, row in tqdm(self.downloaded_data.iterrows(), total=self.downloaded_data.shape[0]):

            file_type = row["file_type"]
            original_path = row["downloaded_path"]
            converted_path = row["processed_filepath"]
            file_name = os.path.splitext(os.path.basename(original_path))[0]
            # TODO (juan) what exactly does splitext do
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
                    if self.model_list is None:
                        self.model_list = load_all_models()
                    saved_path = FileProcessor.convert_pdf_to_md(
                        original_path, file_name, self.converted_data_dir, self.model_list
                    )
                elif file_type == "html":
                    saved_path = FileProcessor.convert_html_to_md(
                        original_path, file_name, self.converted_data_dir
                    )
                elif file_type == "docx":
                    saved_path = FileProcessor.convert_docx_to_md(
                        original_path, file_name, self.converted_data_dir
                    )
                elif file_type == "doc":
                    saved_path = FileProcessor.convert_doc_to_md(
                        original_path, file_name, self.converted_data_dir
                    )
                elif file_type == "xlsx":
                    saved_path = FileProcessor.convert_xlsx_to_md(
                        original_path, file_name, self.converted_data_dir
                    )
                else:
                    print(f"File type not supported for parsing. File: {original_path}")
                    continue

                # Post processing steps: remove image data, espace special characters, validate conversion # noqa: E501
                FileProcessor.md_remove_image_data(saved_path)
                saved_path = FileProcessor.md_conversion_validate(saved_path)

            except Exception as e:
                print(f"File {original_path} could not be converted to md. Error: {e}")
                saved_path = None

            print("Converted file.")
            self.downloaded_data.at[idx, "processed_filepath"] = saved_path
            self.downloaded_data.to_csv(
                os.path.join(self.metadata_dir, "downloaded_data_index.csv"), index=False
            )

    @staticmethod
    def md_remove_image_data(path):
        # In the markdown text, there can be images like this:
        # ![image](encoded image)
        # We want to remove the image data, i.e. the full ![image](encoded image), and return the text only # noqa: E501
        with open(path, "r") as f:
            text = f.read()
            text = re.sub(r"!\[image\]\(([^)]+)\)", "", text)
        with open(path, "w") as f:
            f.write(text)

    @staticmethod
    def md_conversion_validate(path):
        # If the markdown file is actually empty, then we need to remove the file
        # and change the downlaoded_data information to None
        with open(path, "r") as f:
            text = f.read()
            if len(text) == 0:
                os.remove(path)
                return None
        return path

    @staticmethod
    def convert_pdf_to_md(path, file_name, converted_data_dir, models_list):

        # Suppress the many logging messages when calling this function
        previous_level = suppress_logging()
        full_text, out_meta = convert_single_pdf(path, models_list, parallel_factor=1)
        restore_logging(previous_level)

        save_path = os.path.join(converted_data_dir, file_name + ".md")
        with open(save_path, "w+", encoding="utf-8") as f:
            f.write(full_text)
        return save_path

    @staticmethod
    def convert_html_to_md(path, file_name, converted_data_dir):
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        save_path = os.path.join(converted_data_dir, file_name + ".md")

        with open(path, "r") as fin:
            markdown_content = h.handle(fin.read())
            with open(save_path, "w") as fout:
                fout.write(markdown_content)

        return save_path

    @staticmethod
    def convert_docx_to_md(path, file_name, converted_data_dir):
        save_path = os.path.join(converted_data_dir, file_name + ".md")
        command = f"pandoc -f docx -t markdown -o {save_path} {path}"
        subprocess.run(command, shell=True)
        return save_path

    @staticmethod
    def convert_doc_to_md(path, file_name, converted_data_dir):
        # Convert .doc to .docx using LibreOffice
        temp_docx_path = os.path.join(converted_data_dir, file_name + ".docx")
        convert_command = f"soffice --convert-to docx {path} --outdir {converted_data_dir}"
        subprocess.run(convert_command, shell=True)

        # Now convert the .docx to .md using pandoc
        save_path = os.path.join(converted_data_dir, file_name + ".md")
        pandoc_command = f"pandoc -f docx -t markdown -o {save_path} {temp_docx_path}"
        subprocess.run(pandoc_command, shell=True)

        # Optionally, remove the temporary .docx file if no longer needed
        os.remove(temp_docx_path)

        return save_path

    @staticmethod
    def convert_xlsx_to_md(path, file_name, converted_data_dir):
        df = pd.read_excel(path)
        markdown_content = tabulate(df, headers="keys", tablefmt="pipe", showindex=False)
        save_path = os.path.join(converted_data_dir, file_name + ".md")

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
                with open(chunk_text_save_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(chunks, ensure_ascii=False))
                with open(chunk_metadata_save_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(chunks_metadata, ensure_ascii=False))

                self.downloaded_data.at[idx, "file_chunks_path"] = chunk_text_save_path
                self.downloaded_data.to_csv(
                    os.path.join(self.metadata_dir, "downloaded_data_index.csv"), index=False
                )

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

    METADATA_DIR = os.getenv("METADATA_DIR")
    CONVERTED_DATA_DIR = os.getenv("CONVERTED_DATA_DIR")
    FILE_CHUNKS_DATA_DIR = os.getenv("FILE_CHUNKS_DATA_DIR")

    file_processor = FileProcessor(CONVERTED_DATA_DIR, METADATA_DIR)
    file_processor.convert_all_files()
    text_processor = TextProcessor(METADATA_DIR, CONVERTED_DATA_DIR, FILE_CHUNKS_DATA_DIR)
    text_processor.chunk_all_files()
