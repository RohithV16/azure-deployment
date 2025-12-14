#!/bin/bash

# Start Gunicorn in the background
echo "🚀 Starting Gunicorn (Web App)..."
gunicorn --bind 0.0.0.0:1234 webapp.app:app --preload --workers 3 --timeout 300 &

# Wait for Gunicorn to initialize
sleep 3

# Check for Ngrok Token
if [ -n "$NGROK_AUTHTOKEN" ]; then
    echo "🔐 Configuring Ngrok..."
    ngrok config add-authtoken "$NGROK_AUTHTOKEN"
    
    echo "🌍 Starting Ngrok Tunnel on port 1234..."
    # Run ngrok in background but log to stdout so we can see the URL in docker logs
    # We use --log=stdout to stream logs.
    # Note: The actual public URL usually appears in the logs or dashboard.
    ngrok http 1234 --log=stdout &
else
    echo "⚠️  NGROK_AUTHTOKEN not set. Ngrok will not actiavate."
fi

# Keep container running by waiting for purely background processes
wait -n
