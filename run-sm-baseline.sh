#!/bin/bash
# Run SM baseline after LG completes

echo "Starting SM Baseline (1M accounts, 10M transactions)..."

# Update .env for SM
sed -i 's/BENCHMARK_SIZE=.*/BENCHMARK_SIZE=sm/' .env
sed -i 's/OUTPUT_FILE=.*/OUTPUT_FILE=output-sm.json/' .env

# Stop LG benchmark runner and reset neo4j for SM
docker stop neo4j_benchmark_runner 2>/dev/null
docker compose down -v 2>/dev/null

# Start SM benchmark
docker compose up -d && \
echo "✓ SM baseline started - watch output-sm.json for completion"
