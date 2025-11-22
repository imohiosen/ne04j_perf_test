#!/bin/bash

# Monitor LG benchmark progress
while true; do
    clear
    echo "=== LG Baseline Benchmark Status ==="
    echo "Time: $(date)"
    echo ""
    
    # Check container status
    docker ps --filter name=neo4j_benchmark_runner --format "Status: {{.Status}}"
    echo ""
    
    # Get last 5 log lines
    echo "--- Latest Logs ---"
    docker logs neo4j_benchmark_runner 2>&1 | tail -5
    echo ""
    
    # Check output file
    if [ -f output-lg.json ]; then
        echo "✓ output-lg.json exists ($(wc -c < output-lg.json) bytes)"
        tail -c 200 output-lg.json
    else
        echo "⏳ Waiting for output-lg.json..."
    fi
    
    # Check resources
    echo ""
    echo "--- Docker Stats ---"
    docker stats neo4j_benchmark_runner neo4j_bench --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
    
    echo ""
    echo "Press Ctrl+C to stop monitoring"
    sleep 60
done
