FROM python:3.10-slim

LABEL maintainer="Chef to Ansible Converter Team"
LABEL description="Docker image for Chef to Ansible Converter"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ansible \
    ansible-lint \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/
COPY web/ /app/web/
COPY *.py /app/
COPY README.md /app/

# Create necessary directories
RUN mkdir -p /app/output /app/temp

# Set up entrypoint
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Default command
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["--help"]
