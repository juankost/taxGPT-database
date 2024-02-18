#!/bin/bash
# Pull the latest Docker image
docker pull gcr.io/taxgpt-413814/taxgpt-database-image:latest

# Stop the current container
docker stop vector-database-service || true

# Remove the old container
docker rm vector-database-service || true

# Run the new container
docker run --name vector-database-service -d \
    -p 8080:8080 \
    gcr.io/taxgpt-413814/taxgpt-database-image:latest
