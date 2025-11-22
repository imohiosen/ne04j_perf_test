#!/bin/bash

while true; do
    clear
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║         Neo4j Benchmark - Parallel Execution Monitor           ║"
    echo "║                    $(date '+%Y-%m-%d %H:%M:%S')                      ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # LG Baseline
    echo "├─ LG BASELINE (10M accounts, 200M txns)"
    echo "│  Status: $(docker ps --filter name=neo4j_benchmark_runner --format "{{.Status}}")"
    echo "│  Last logs:"
    docker logs neo4j_benchmark_runner 2>&1 | tail -2 | sed 's/^/│    /'
    if [ -f output-lg.json ]; then
        SIZE=$(wc -c < output-lg.json)
        echo "│  ✓ output-lg.json: $SIZE bytes"
    else
        echo "│  ⏳ Waiting for output-lg.json..."
    fi
    echo ""
    
    # SM Baseline  
    echo "├─ SM BASELINE (1M accounts, 10M txns)"
    echo "│  Status: $(docker ps --filter name=neo4j_benchmark_runner_sm --format "{{.Status}}" 2>/dev/null || echo "Not started")"
    echo "│  Last logs:"
    docker logs neo4j_benchmark_runner_sm 2>&1 | tail -2 | sed 's/^/│    /' 2>/dev/null || echo "│    [initializing...]"
    if [ -f output-sm.json ]; then
        SIZE=$(wc -c < output-sm.json)
        echo "│  ✓ output-sm.json: $SIZE bytes"
    else
        echo "│  ⏳ Waiting for output-sm.json..."
    fi
    echo ""
    
    # Resources
    echo "├─ RESOURCE USAGE"
    docker stats neo4j_benchmark_runner neo4j_bench neo4j_benchmark_runner_sm neo4j_bench_sm --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | sed 's/^/│  /'
    echo ""
    echo "└─ Press Ctrl+C to stop"
    sleep 30
done
