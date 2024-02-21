# taxGPT-database
This repository handles the processing and serving of the law database for the taxGPT project.

## Deployment instructions:
1. Create Docker image and upload it to the Google Container Registry:
```
docker build -t gcr.io/taxgpt-413814/taxgpt-database:tag .
gcloud auth configure-docker
docker push gcr.io/taxgpt-413814/taxgpt-database:tag
```
2. Create a Google Cloud VM
```
INSTANCE_NAME=taxgpt-databse
PROJECT_ID=taxgpt-413814
ZONE=us-central1-f
MACHINE_TYPE=n2-standard-2
IMAGE=debian-12-bookworm-v20240110
IMAGE_PROJECT=
gcloud compute instances create INSTANCE_NAME --project=PROJECT_ID --zone=ZONE --machine-type=MACHINE_TYPE --image=IMAGE --image-project=IMAGE_PROJECT
```
3. Load the Docker image on the VM
```
docker-credential-gcr configure-docker
docker pull gcr.io/taxgpt-413814/taxgpt-database:tag

compute.7947554465738214187 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICxS5DzTK7eZKCCAG+ax/Nfgq1dO3kf4mPBuyNz+jpEb

```




# TODO
1. Test the Google VM, if the code runs there (Selenium data scraping)
    - Run the data_pipeline.py script there
    - Set access to the google cloud storage
    - Add the backup functions to the data pipeline to save the data to the google cloud storage
    - Write startup script for the Google VM: Install the Docker image, pull the latest data from the google storage, 
    initialize the vector database, run the fast.api server




