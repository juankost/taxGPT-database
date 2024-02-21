#!/bin/bash
# Run data pipeline
python3 -m app.pipeline.data_pipeline

# Then start the main application
# exec python3 ./app/app.py
exec python3 -m app.app