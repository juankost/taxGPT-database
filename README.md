# taxGPT-database
This repository handles the processing and serving of the law database for the taxGPT project.


## Deployment instructions:
1. Create Docker image and upload it to the Google Container Registry:
```
docker build -t gcr.io/taxgpt-413814/taxgpt-database-image:latest .
gcloud auth configure-docker
docker push gcr.io/taxgpt-413814/taxgpt-database-image:latest
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
3. Connect to the VM
```
gcloud compute ssh --zone "us-central1-f" "taxgpt-database" --project "taxgpt-413814"
```
4. Load the Docker image on the VM
```
docker-credential-gcr configure-docker
docker pull gcr.io/taxgpt-413814/taxgpt-database-image:latest
```
5. Run the Docker image
```
docker run -p 80:80 gcr.io/taxgpt-413814/taxgpt-database-image:latest
```





