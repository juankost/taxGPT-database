#!/bin/bash

# Load environment variables
set -a  # Automatically export all variables
source /workspace/.env
set +a

# Run data pipeline
python3 -m app.pipeline.data_pipeline

# Then start the main application
exec python3 -m app.app