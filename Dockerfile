FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    curl \
    jq \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Bitwarden CLI
RUN npm install -g @bitwarden/cli

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the port
EXPOSE 8110

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8110", "--reload"]
