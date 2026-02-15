#!/bin/bash
DATA_DIR="${DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"
exec streamlit run app.py --server.port ${PORT:-8501} --server.address 0.0.0.0
