#!/bin/bash

echo "=========================================="
echo "Neo4j MD Benchmark Monitor"
echo "Dataset: 5M accounts, 50M transactions"
echo "=========================================="
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q neo4j_benchmark_runner; then
    echo "❌ Benchmark container is not running"
    
    # Check if it exited
    if docker ps -a --format '{{.Names}}\t{{.Status}}' | grep neo4j_benchmark_runner | grep -q Exited; then
        echo ""
        echo "Container has finished. Exit code:"
        docker ps -a --filter name=neo4j_benchmark_runner --format "{{.Status}}"
        echo ""
        echo "Last 30 lines of output:"
        docker logs --tail 30 neo4j_benchmark_runner 2>&1
        echo ""
        echo "Results:"
        if [ -f output-md.json ]; then
            cat output-md.json | python3 -m json.tool
        elif [ -f output.json ]; then
            cat output.json | python3 -m json.tool
        else
            echo "No output file found yet"
        fi
    fi
    exit 0
fi

echo "✓ Benchmark is running"
echo ""

# Show process info
echo "Process Info:"
docker exec neo4j_benchmark_runner ps aux | grep -E 'USER|python' | head -2
echo ""

# Show recent logs (last 10 lines)
echo "Recent Progress:"
docker logs --tail 10 neo4j_benchmark_runner 2>&1
echo ""

# Estimate time remaining based on XS results
# XS: 100K accounts, 1M txns = 186s
# MD: 5M accounts, 50M txns = 50x more txns
# Rough estimate: 186s * 50 = 9300s ≈ 2.5 hours

echo "=========================================="
echo "Tip: Run this script again to check progress"
echo "Command: ./monitor-benchmark.sh"
echo ""
echo "To view live logs: docker logs -f neo4j_benchmark_runner"
echo "To stop: docker compose down"
echo "=========================================="
