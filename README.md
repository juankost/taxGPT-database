# taxGPT-database

This repository handles the processing and serving of the law database for the taxGPT project.

## Deployment instructions:

1. Create Docker image and upload it to the Google Container Registry:
```
docker build -t gcr.io/taxgpt-413814/taxgpt-database:tag .
gcloud auth configure-docker
docker push gcr.io/your-project-id/your-app-name:tag
```
2. 