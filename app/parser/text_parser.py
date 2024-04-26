from langchain_community.document_loaders import PyMuPDFLoader
from dotenv import load_dotenv
import pandas as pd
import os
import tqdm
from tqdm import tqdm
import json
import tiktoken
import html2text
import subprocess
from tabulate import tabulate
from marker.convert import convert_single_pdf
from marker.models import load_all_models


# TODO: Wrap the FileProcessor conversion methods in try except to not break the whole process
# TODO: Create the Vector Database in the TextProcessor class
# TODO: Adapt __main__ to run the TextProcessor and FileProcessor
# TODO: Run the parsing pipeline
# TODO: Adapt the data_pipeline to use the updated classes

# TODO: Logic to run the pipeline and only update the new data needed


class FileProcessor:
    def __init__(self, processed_data_dir, metadata_dir):
        self.processed_data_dir = processed_data_dir
        self.metadata_dir = metadata_dir
        self.downloaded_data = pd.read_csv(os.path.join(metadata_dir, "downloaded_data_index.csv"))

    def parse_all_files(self):
        for idx, row in tqdm(self.downloaded_data.iterrows(), total=self.downloaded_data.shape[0]):
            processed_path = row.get('processed_data_path')
            
            file_type = row['file_type']
            original_path = row['downloaded_path']
            file_name = os.path.splitext(os.path.basename(original_path))[0]
            expected_save_path = os.path.join(self.processed_data_dir, file_name + '.md')
            if pd.notna(processed_path) and os.path.exists(processed_path):
                continue  # Skip processing if the file already exists
            elif os.path.exists(expected_save_path) and pd.isna(processed_path):
                self.downloaded_data.at[idx, 'processed_filepath'] = expected_save_path
                self.downloaded_data.to_csv(os.path.join(self.metadata_dir, "downloaded_data_index.csv"), index=False)
                continue
            
            if file_type == 'pdf':
                saved_path = self.convert_pdf_to_md(original_path, file_name)
            elif file_type == 'html':
                saved_path = self.convert_html_to_md(original_path, file_name)
            elif file_type == 'docx':
                saved_path = self.convert_docx_to_md(original_path, file_name)
            elif file_type == 'doc':
                saved_path = self.convert_doc_to_md(original_path, file_name)
            elif file_type == 'xlsx':
                saved_path = self.convert_xlsx_to_md(original_path, file_name)
            else:
                print(f"File type not supported for parsing. File: {original_path}")
                continue

            self.downloaded_data.at[idx, 'processed_filepath'] = saved_path
            self.downloaded_data.to_csv(os.path.join(self.metadata_dir, "downloaded_data_index.csv"), index=False)

    def convert_pdf_to_md(self, path, file_name):
        model_lst = load_all_models()
        full_text, out_meta = convert_single_pdf(path, model_lst, parallel_factor=1)
        
        save_path = os.path.join(self.processed_data_dir, file_name + '.md')
        with open(save_path, "w+", encoding='utf-8') as f:
            f.write(full_text)      
        return save_path

    def convert_html_to_md(self, path, file_name):
        h = html2text.HTML2Text()
        h.ignore_links = True
        save_path = os.path.join(self.processed_data_dir, file_name + '.md')
        
        with open(path, "r") as fin:
            markdown_content = h.handle(fin.read())
            with open(save_path, "w") as fout:
                fout.write(markdown_content)

        return save_path

    def convert_docx_to_md(self, path, file_name):
        save_path = os.path.join(self.processed_data_dir, file_name + '.md')
        command = f"pandoc -f docx -t markdown -o {save_path} {path}"
        subprocess.run(command, shell=True)
        return save_path

    def convert_doc_to_md(self, path, file_name):
        # Convert .doc to .docx using LibreOffice
        temp_docx_path = os.path.join(self.processed_data_dir, file_name + '.docx')
        convert_command = f"soffice --convert-to docx {path} --outdir {self.processed_data_dir}"
        subprocess.run(convert_command, shell=True)

        # Now convert the .docx to .md using pandoc
        save_path = os.path.join(self.processed_data_dir, file_name + '.md')
        pandoc_command = f"pandoc -f docx -t markdown -o {save_path} {temp_docx_path}"
        subprocess.run(pandoc_command, shell=True)

        # Optionally, remove the temporary .docx file if no longer needed
        os.remove(temp_docx_path)

        return save_path
    
    def convert_xlsx_to_md(self, path, file_name):
        df = pd.read_excel(path)
        markdown_content = tabulate(df, headers='keys', tablefmt='pipe', showindex=False)
        save_path = os.path.join(self.processed_data_dir, file_name + '.md')
        
        with open(save_path, 'w') as file:
            file.write(markdown_content)
        
        return save_path


class TextProcessor:
    def __init__(self, metadata_dir, processed_data_dir, database_path):
        self.processed_data_dir = processed_data_dir
        self.metadata_dir = metadata_dir
        self.database_path = database_path
        self.downloaded_data = pd.read_csv(os.path.join(metadata_dir, "downloaded_data_index.csv"))

        # Add a column to the downloaded data, if it does not yet exist:
        # file_chunks_path
        if 'file_chunks_path' not in self.downloaded_data.columns:
            self.downloaded_data['file_chunks_path'] = pd.Series(dtype='string')

    def process_all_files(self):
        print(self.downloaded_data.columns)
        for idx, row in self.downloaded_data.iterrows():
            processed_path = row['processed_filepath']
            file_chunks_path = row['file_chunks_path']
            if pd.isna(processed_path) or not os.path.exists(processed_path):
                continue  # Skip if no processed file path or file does not exist

            file_name = os.path.basename(processed_path)
            chunks = self.chunk_file(processed_path)
            metadata = self.create_file_metadata(processed_path)
            self.add_to_database(chunks, metadata)

    def chunk_file(self, file_path):
        # Read the file and split into chunks
        with open(file_path, 'r') as file:
            content = file.read()
        # Example chunking: split by paragraphs
        chunks = content.split('\n\n')
        return chunks

    def create_file_metadata(self, file_path):
        # Create metadata for the file
        metadata = {
            'file_name': os.path.basename(file_path),
            'date_processed': pd.Timestamp.now().isoformat()
        }
        return metadata

    def add_to_database(self, chunks, metadata):
        # Convert chunks to vectors and add to FAISS index
        for chunk in chunks:
            vector = self.text_to_vector(chunk)  # Placeholder for actual vectorization logic
            self.index.add(vector)  # Add vector to FAISS index
        # Optionally save metadata alongside vectors

    def text_to_vector(self, text):
        # Placeholder for text vectorization logic
        # This should convert text to a vector using some model
        return np.random.rand(1, 512).astype('float32')  # Example random vector

    def save_index(self):
        # Save the FAISS index to disk
        faiss.write_index(self.index, self.database_path)




class Parser:
    def __init__(
        self,
        references_data_path,
        raw_dir,
        processed_dir,
        local=False,
        max_tokens=2048,
        overlap_tokens=512,
        embedding_model="text-embedding-3-large",
    ):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.references_data_path = references_data_path
        self.references_data = pd.read_csv(self.references_data_path)
        self.embedding_model = embedding_model
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
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
        enc = tiktoken.encoding_for_model(self.embedding_model)
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


    @staticmethod
    def convert_pdf_to_html(path):
        # TODO: Implement this
        pass

    @staticmethod
    def convert_html_to_markdown(html):
        # TODO: Implement this
        pass

    @staticmethod
    def convert_docx_to_markdown(path):
        # TODO: Implement this
        pass

    @staticmethod
    def save_markdown_to_file(markdown, path):
        # TODO: Implement this
        pass






if __name__ == "__main__":
    # For development purposes
    _ = load_dotenv(".env.local")  # read local .env file

    # Set up directories
    METADATA_DIR = os.getenv("METADATA_DIR")
    PROCESSED_DATA_DIR = os.getenv("PROCESSED_DATA_DIR")

    # Create an instance of FileProcessor
    file_processor = FileProcessor(PROCESSED_DATA_DIR, METADATA_DIR)
    file_processor.parse_all_files()
