import os
from google.cloud import storage


def upload_folder_to_bucket(bucket_name, folder_path, destination_blob_folder):
    """Uploads a folder and its contents to the bucket, maintaining the folder structure."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    for local_file in os.listdir(folder_path):
        local_file_path = os.path.join(folder_path, local_file)

        # Skip directories, only upload files
        if os.path.isfile(local_file_path):
            # Construct the full path for the file within the bucket
            blob_name = os.path.join(destination_blob_folder, local_file)
            blob = bucket.blob(blob_name)

            # Upload the file
            blob.upload_from_filename(local_file_path)
            print(f"Uploaded {local_file} to {blob_name}.")


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")


def download_blob(bucket_name, source_blob_name, destination_file_name):
    """Downloads a blob from the bucket to a local file."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)

    if blob.exists():
        blob.download_to_filename(destination_file_name)
    print(f"Blob {source_blob_name} downloaded to {destination_file_name}.")


def check_blob_exists(bucket_name, blob_name):
    """Check if a blob exists in the specified GCS bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    return blob.exists()
