#!/bin/bash

# Load environment variables
set -a  # Automatically export all variables
source /workspace/taxgpt_database_env/.env
set +a

# Run data pipeline
python3 -m app.pipeline.data_pipeline