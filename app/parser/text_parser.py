from langchain_community.document_loaders import PyMuPDFLoader
from dotenv import load_dotenv
import pandas as pd
import os
import tqdm
import json
import tiktoken


class Parser:
    def __init__(self, references_data_path, raw_dir, processed_dir, local=False, max_tokens=2048, overlap_tokens=512):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.references_data_path = references_data_path
        self.references_data = pd.read_csv(self.references_data_path)

        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        # Make sure the output dir exists
        os.makedirs(processed_dir, exist_ok=True)

    def parse_all_files(self):
        for idx, row in tqdm.tqdm(self.references_data.iterrows()):
            if not row["is_processed"] or pd.isna(row["actual_download_location"]):
                continue
            if row["actual_download_location"].endswith(".pdf"):
                self.parse_pdf_file(row, self.processed_dir)
            # TODO: Add support for other file types

    def parse_pdf_file(self, reference_information, output_dir):
        path = reference_information["actual_download_location"]
        file_name = path.rsplit("/", maxsplit=1)[-1].rsplit(".", maxsplit=1)[0]

        text_save_path = os.path.join(output_dir, file_name + ".txt")
        metadata_save_path = os.path.join(output_dir, file_name + ".metadata")

        try:
            # Extract the text from the PDF and chunk it meaningfully. Also create chunk level metadata.
            # (i.e. which section of the law is this chunk from, etc.)
            chunks, chunks_metadata = self.create_txt_chunks(path)

            # Create the file level metadata (i.e. description of tax area, when was the file parsed, etc.)
            file_metadata = self.create_file_metadata(reference_information)
            for chunk_metadata in chunks_metadata:
                chunk_metadata.update(file_metadata)

            # Create the chunk explaining the high level of the law and add it to the chunks
            file_level_chunk, file_level_metadata = self.create_file_level_chunks(reference_information)
            chunks.append(file_level_chunk)
            chunks_metadata.append(file_level_metadata)

            # Save the chunks and their metadata
            with open(text_save_path, "w") as f:
                f.write(json.dumps(chunks))
            with open(metadata_save_path, "w") as f:
                f.write(json.dumps(chunks_metadata))

        except Exception as e:
            print(e)
            print("\n-----------------------------------\n")

    def create_txt_chunks(self, path):
        # TODO: Currently I simply split the text into chunks without considering the actual document structure.
        # Hence I don't create the metadata for the chunks. This is a placeholder for now.
        # Ideally, I should chunk the law by law article, and the metadata should summarize where the article is from.
        # i.e. which section of teh law, page?, summary of the section, summary of the law, etc

        data = PyMuPDFLoader(path).load()
        text = "".join([d.page_content for d in data])
        chunks = self.split_long_text(text)
        chunk_metadata = [{"chunk_idx": idx} for idx in range(len(chunks))]  # Placeholder for now
        return chunks, chunk_metadata

    def split_long_text(self, text):
        enc = tiktoken.encoding_for_model("gpt-4")
        tokens = enc.encode(text)
        chunks = []
        for i in range(0, len(tokens), self.max_tokens - self.overlap_tokens):
            chunks.append({"content": enc.decode(tokens[i : min(i + self.max_tokens, len(tokens))])})  # noqa: E203
        return chunks

    def create_file_metadata(self, reference_information):
        file_metadata = {
            "date_parsed": pd.Timestamp.now().isoformat(),
            "area_name": reference_information["area_name"],
            "reference_name": reference_information["reference_name"],
            "details_href_name": reference_information["details_href_name"],
            "details_section": reference_information["details_section"],
            "used_download_href": reference_information["used_download_href"],
            "actual_download_link": reference_information["actual_download_link"],
        }
        return file_metadata

    def create_file_level_chunks(self, reference_information):
        # The idea of these chunks is to explain the high level, where does each law come into play.
        chunk = f"""
        Area name: {reference_information["area_name"]}
        Area description: {reference_information["area_desc"]}
        Reference name: {reference_information["reference_name"]}
        Details section: {reference_information["details_section"]}
        Details section text: {reference_information["details_section_text"]}
        Details href name: {reference_information["details_href_name"]}
        """
        metadata = {
            "date_parsed": pd.Timestamp.now().isoformat(),
            "area_name": reference_information["area_name"],
            "reference_name": reference_information["reference_name"],
            "details_href_name": reference_information["details_href_name"],
            "details_section": reference_information["details_section"],
            "used_download_href": reference_information["reference_href_clean"],
            "actual_download_link": reference_information["reference_href_clean"],
        }
        return {"content": chunk}, metadata


if __name__ == "__main__":
    # For development purposes
    _ = load_dotenv(".env.local")  # read local .env file

    # Download all the data
    METADATA_DIR = os.getenv("METADATA_DIR")
    RAW_DATA_DIR = os.getenv("RAW_DATA_DIR")
    PARSED_DATA_DIR = os.getenv("PARSED_DATA_DIR")
    reference_data_path = os.path.join(METADATA_DIR, "references.csv")

    parser = Parser(reference_data_path, RAW_DATA_DIR, PARSED_DATA_DIR, local=True)
    parser.parse_all_files()
