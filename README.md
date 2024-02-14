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







# TODO:
1. Have the database deployed
- deploy the database VM
    - Created VM [DONE]
    - Create the docker image  [DONE]
    - Test the docker image
    - Set up VM to use Container optimized OS
    - Set up Google cloud to deploy the new docker image whenever we commit changes to the repo
    - Set up the access to the google cloud storage
    - Deploy
- Test run the data pipeline to download the databse and create it

2. Have the API deployed and connected to the database
- Have the API interact with the google cloud database
- Deploy the API to the Google cloud run

3. Have the Website deployed and connected to the API and database


# UCPA Assistance:
Reference dossier: 262597/2311/SI/WEB
Numero: +33 534 45 31 50
Numero subscription: 06973_4361479 - Kostelec Juan
Mutuaide reference: 240103397


Insurance:
- ambulance and chamonix hospital
- hospital costs (have document)
- taxi hospital  (have receipt)
- taxi Geneva  (have reservation - need confirmation it will be covered)
- Costs of the trip (DONE)
- ski rescue  (DONE)

TODO: 
- french insurance confirm that they cover the taxi to Geneva (WAITING CALLBACK)
- declare accident to swiss Insurance (WAITING FIRST FOR FRENCH INSURANCE)
- return ski pass (NO NEED NOW)
- send all documents (IN PROGRESS)

