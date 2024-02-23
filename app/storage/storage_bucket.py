import os
from google.cloud import storage
import google.auth

"""Utils for interacting with Google Cloud Storage (GCS)."""


def authenticate_gcs(local=False):
    if not local:
        client = storage.Client()  # when running on GCP it will automatically authenticate
    else:
        if not os.path.exists(os.environ["GOOGLE_APPLICATION_DEFAULT_CREDENTIALS"]):
            raise Exception(
                "GOOGLE_APPLICATION_DEFAULT_CREDENTIALS file not found.\n"
                "Run the following command to authenticate: gcloud auth application-default login.\n"
                "Then set the GOOGLE_APPLICATION_DEFAULT_CREDENTIALS environment variable to the path of the "
                "credentials file."
            )
        if not os.environ["GOOGLE_CLOUD_PROJECT"]:
            raise Exception("GOOGLE_CLOUD_PROJECT environment variable not set.")
        credentials, project_id = google.auth.default()
        client = storage.Client(credentials=credentials, project=project_id)
    return client


def upload_folder_to_bucket(bucket_name, folder_path, destination_blob_folder, local=False):
    """Uploads a folder and its contents to the bucket, maintaining the folder structure."""
    storage_client = authenticate_gcs(local=local)
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


def upload_blob(bucket_name, source_file_name, destination_blob_name, local=False):
    """Uploads a file to the bucket."""
    storage_client = authenticate_gcs(local=local)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")


def download_blob(bucket_name, source_blob_name, destination_file_name, local=False):
    """Downloads a blob from the bucket to a local file."""
    storage_client = authenticate_gcs(local=local)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)

    if blob.exists():
        blob.download_to_filename(destination_file_name)
        print(f"Blob {source_blob_name} downloaded to {destination_file_name}.")


def download_folder(bucket_name, folder_prefix, local_destination_dir, local=False):
    """Downloads all blobs in a folder from the bucket to a local directory."""
    storage_client = authenticate_gcs(local=local)
    bucket = storage_client.bucket(bucket_name)

    # Ensure the folder_prefix ends with a '/' to properly match all objects within the folder
    if not folder_prefix.endswith("/"):
        folder_prefix += "/"

    blobs = bucket.list_blobs(prefix=folder_prefix)
    for blob in blobs:
        # Construct the local filepath to save the downloaded file
        local_file_path = os.path.join(local_destination_dir, blob.name[len(folder_prefix) :])  # noqa: E203

        # Create any necessary directories for nested objects
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        # Download the blob to the local_file_path
        blob.download_to_filename(local_file_path)
        print(f"Downloaded {blob.name} to {local_file_path}.")


def check_blob_exists(bucket_name, blob_name, local=False):
    """Check if a blob exists in the specified GCS bucket."""
    storage_client = authenticate_gcs(local=local)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    return blob.exists()


def check_folder_exists(bucket_name, folder_name, local=False):
    """Check if any objects exist within the specified 'folder' in the GCS bucket."""
    storage_client = authenticate_gcs(local=local)
    bucket = storage_client.bucket(bucket_name)

    # Ensure the folder_name ends with a '/' to properly check the prefix
    if not folder_name.endswith("/"):
        folder_name += "/"

    # Create a blob iterator with the prefix set to the folder name
    blobs = bucket.list_blobs(prefix=folder_name, max_results=1)

    # Try to fetch one object to see if the iterator has any results
    return any(True for _ in blobs)
