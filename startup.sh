#!/bin/bash
# Run data pipeline
python3 ./app/pipeline/data_pipeline.py

# Then start the main application
exec python3 ./app/app.py
