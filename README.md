# taxGPT-database

This repository handles the processing and serving of the (Slovenian) law database for the taxGPT project.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Deployment](#deployment)
- [License](#license)

## Overview

The taxGPT-database is part of the taxGPT project that was designed to provide information related to the Slovenian tax law to users (e.g. accountants, tax advisors) in real-time.

This repository handles the collection, conversion, storage of tax-related information from several (official) sources, primarily the Financial Administration of the Republic of Slovenia (FURS) website.

## Features

- Multiple source data collection:

  - FURS (Financial Administration of the Republic of Slovenia) website
  - PISRS (Legal Information System of the Republic of Slovenia) website
  - EUR-LEX (EU law database)

- Converts various document formats (PDF, HTML, etc.) to markdown format
- Uses OpenAI embedding models for the text embedding
- Uses FAISS for vector storage and retrieval

## Installation

Follow these steps to set up the taxGPT-database project on your local machine.

### Prerequisites

Ensure you have the following installed on your system:

- Anaconda or Miniconda (for managing Python environments)
- LibreOffice
- Pandoc
- Docker

### Step 1: Clone the Repository

```
git clone https://github.com/your-username/taxGPT-database.git
cd taxGPT-database
```

### Step 2: Install System Dependencies

#### Ubuntu/Debian:

```
sudo apt update
sudo apt install libreoffice pandoc
```

#### macOS:

```
brew install libreoffice pandoc
```

#### Windows:

Download and install LibreOffice and Pandoc from their official websites.

### Step 3: Create and Activate Conda Environment

```
conda create -n taxgpt-env python=3.11
conda activate taxgpt-env
```

### Step 4: Install Python Package (Editable Mode)

This command will install the project in editable mode, along with all its dependencies specified in `setup.py` and `requirements.txt`:

```
pip install -e .
```

### Step 5: Verify System Dependencies

Ensure LibreOffice and Pandoc are correctly installed:

```
soffice --version
pandoc --version
```

### Step 6: Configure Environment Variables

Create a `.env` file in the project root directory and add the following variables:
OPENAI_API_KEY=your_openai_api_key
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/google-credentials.json
GOOGLE_CLOUD_PROJECT=your_google_cloud_project_id
GOOGLE_CLOUD_STORAGE_BUCKET=your_google_cloud_storage_bucket_name

Replace the placeholders with your actual credentials and project details.

### Step 7: Verify Installation

To ensure everything is set up correctly, run:

```
python -m app.pipeline.data_pipeline --local --update
```

This command should execute the data pipeline locally and attempt to update the vector store.

## Usage

Currently only supports the data pipeline locally, due to dependencies on Open Office for the file conversion (have not tested installing open office on the VM). To run the pipeline locally:

```
python -m app.pipeline.data_pipeline --local --update
```

Optional arguments:

--update [True/False]: try to load existing vector Store from the Google Storage Bucket or create the vector store from new scraped data, if it does not exist

--force [True/False]: whether to run the data scraping pipeline even if an existing vector store exists

If no flags are specified, it will only try to load an existng vector store from the Google Storage Bucket.

## Deployment

While the pipeline is only tested locally, we also provide the instructions for deploying the system to a Google VM.

Detailed instructions for deploying the system:

1. Create Docker image and upload it to the Google Container Registry:

```
PROJECT_ID=<your Google Cloud Project ID>
docker build -t gcr.io/PROJECT_ID/taxgpt-database-image:latest .
gcloud auth configure-docker
docker push gcr.io/taxgpt-413814/taxgpt-database-image:latest
```

2. Create a Google Cloud VM

```
INSTANCE_NAME=taxgpt-databse
ZONE=us-central1-f
MACHINE_TYPE=n2-standard-2
IMAGE=debian-12-bookworm-v20240110
IMAGE_PROJECT=
gcloud compute instances create INSTANCE_NAME --project=PROJECT_ID --zone=ZONE --machine-type=MACHINE_TYPE --image=IMAGE --image-project=IMAGE_PROJECT
```

3. Connect to the VM and load the Docker Image on the VM

```
gcloud compute ssh --zone "us-central1-f" "taxgpt-database" --project "${PROJECT_ID}"
docker-credential-gcr configure-docker
docker pull gcr.io/${PROJECT_ID}/taxgpt-database-image:latest
```

4. Run the Docker image

```
docker run -p 80:80 gcr.io/${PROJECT_ID}/taxgpt-database-image:latest
```

Note, we provide the cloudbuild.yaml cloud-init.yaml, and container.yaml scripts to automated the deployment of the system to a Google VM.
However, you might need to adapt the scripts by specifying the appropriate variables (e.g. PROJECT ID, ...)

## Future Work

There are still two main tasks to be done:

1. **VM-Compatible Scraping Pipeline**:
   This is currently not possible due to dependencies on Open Office for the file conversion. I have not yet tried installing open office on the VM and checking that the pipeline works.

2. **Automated Updates via Cron Job**:  
   Set up a cron job to automate the updating of the vector store based on any new information on the relevant data sources.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
