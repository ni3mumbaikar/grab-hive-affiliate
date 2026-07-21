# Use a lightweight official Python runtime as a parent image
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC

# Set working directory
WORKDIR /app

# Install system dependencies (including font utilities if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and configuration files
COPY config/ ./config/
COPY src/ ./src/

# Create a volume for logs (persisting app logs, progress tracking, lock files, and activity logs)
RUN mkdir -p logs temp
VOLUME ["/app/logs"]

# Command to run the application in daemon scheduler loop mode by default
CMD ["python", "src/scheduler.py", "--daemon"]
