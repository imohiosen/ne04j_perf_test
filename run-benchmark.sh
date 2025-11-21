#!/bin/bash

set -e

echo "=========================================="
echo "Neo4j Benchmark Runner"
echo "=========================================="
echo ""

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Display configuration
echo "Configuration:"
echo "  Dataset Size: ${BENCHMARK_SIZE:-xs}"
echo "  Batch Size: ${BATCH_SIZE:-5000}"
echo "  Concurrency: ${CONCURRENCY:-10}"
echo "  Output File: ${OUTPUT_FILE:-output.json}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Clean up previous run (optional - comment out to persist data)
echo "Cleaning up previous containers..."
docker compose down -v 2>/dev/null || true

echo ""
echo "Building and starting services..."
docker compose up --build --abort-on-container-exit

# Check exit code
BENCHMARK_EXIT_CODE=$(docker inspect neo4j_benchmark_runner --format='{{.State.ExitCode}}' 2>/dev/null || echo "1")

echo ""
echo "=========================================="
if [ "$BENCHMARK_EXIT_CODE" = "0" ]; then
    echo "✓ Benchmark completed successfully!"
    echo ""
    echo "Results saved to: ${OUTPUT_FILE:-output.json}"
    if [ -f "${OUTPUT_FILE:-output.json}" ]; then
        echo ""
        echo "Summary:"
        cat "${OUTPUT_FILE:-output.json}" | python3 -m json.tool | head -n 30
    fi
else
    echo "✗ Benchmark failed with exit code: $BENCHMARK_EXIT_CODE"
    echo ""
    echo "Check logs with: docker compose logs benchmark"
fi
echo "=========================================="

# Cleanup containers (keep volumes for inspection)
echo ""
read -p "Clean up containers? (volumes will be preserved) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose down
    echo "Containers removed. Volumes preserved."
fi
