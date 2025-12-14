FROM python:3.9-slim

WORKDIR /app

# Copy requirements from webapp folder
COPY webapp/requirements.txt .
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=webapp/app.py

# Install system dependencies including curl and gnupg for ngrok
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Ngrok
RUN curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
    && echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | tee /etc/apt/sources.list.d/ngrok.list \
    && apt-get update \
    && apt-get install -y ngrok

# Expose the port the app runs on
EXPOSE 1234

# Environment Variables
# REPLACE THESE WITH YOUR ACTUAL VALUES
ENV AZURE_DEVOPS_PAT=""
ENV NGROK_AUTHTOKEN=""

# Copy startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Run the startup script
CMD ["/start.sh"]
