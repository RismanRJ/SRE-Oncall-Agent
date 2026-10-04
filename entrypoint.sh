#!/bin/bash
set -e

# Check if running in development mode
DEV_MODE=${DEV_MODE:-false}

echo "Starting SRE Oncall Agent..."
echo "Dev Mode: $DEV_MODE"

if [ "$DEV_MODE" = "true" ]; then
  echo "🔄 Running in DEVELOPMENT mode (with auto-reload)"
  # Start FastAPI server with auto-reload in background
  uvicorn server:app --host 0.0.0.0 --port 8000 --reload &
  FASTAPI_PID=$!
else
  echo "🚀 Running in PRODUCTION mode"
  # Start FastAPI server in background
  uvicorn server:app --host 0.0.0.0 --port 8000 &
  FASTAPI_PID=$!
fi

echo "✓ FastAPI running on http://0.0.0.0:8000"
echo "✓ Streamlit running on http://0.0.0.0:8501"
echo ""
echo "Dashboard: http://localhost:8501"
echo "API Docs: http://localhost:8000/docs"
echo ""

# Start Streamlit app in foreground
streamlit run app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --logger.level=info

# If Streamlit exits, kill FastAPI
kill $FASTAPI_PID 2>/dev/null || true
