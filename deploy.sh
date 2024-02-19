#!/bin/bash
set -x

echo "Starting deployment process..."

# Pull the latest Docker image
docker pull gcr.io/taxgpt-413814/taxgpt-database-image:latest

echo "Pulled the latest Docker image..."

# Stop the current container
docker stop vector-database-service || true

echo "Stopped the current container..."

# Remove the old container
docker rm vector-database-service || true

echo "Removed the old container..."

# Run the new container
docker run --name vector-database-service -d \
    -p 8080:8080 \
    gcr.io/taxgpt-413814/taxgpt-database-image:latest

echo "Started the new container..."
