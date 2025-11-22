#!/bin/bash
echo "Restarting LG Baseline..."
docker compose down -v
sed -i 's/BENCHMARK_SIZE=.*/BENCHMARK_SIZE=lg/' .env
sed -i 's/OUTPUT_FILE=.*/OUTPUT_FILE=output-lg.json/' .env
echo "✓ Configuration updated to LG"
docker compose up -d
echo "✓ LG Baseline restarted"
sleep 5
docker logs neo4j_benchmark_runner 2>&1 | head -10
