FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the benchmark script
COPY neo4j_bench.py .

# Make sure the script is executable
RUN chmod +x neo4j_bench.py

CMD ["python3", "neo4j_bench.py", "--help"]
