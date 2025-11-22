#!/bin/bash

# Quick comparison of baseline vs optimized results
echo "=========================================="
echo "Neo4j Benchmark: BASELINE vs OPTIMIZED"
echo "=========================================="
echo ""

if [ ! -f output.json ]; then
    echo "❌ Baseline results not found (output.json)"
    exit 1
fi

if [ ! -f output-optimized.json ]; then
    echo "❌ Optimized results not found (output-optimized.json)"
    echo ""
    echo "Run optimized benchmark first:"
    echo "  docker-compose -f docker-compose-optimized.yml up"
    exit 1
fi

echo "Dataset: XS (100K accounts, 1M transactions)"
echo ""
echo "========== WRITE PERFORMANCE (TPS) =========="
baseline_writes=$(grep -A1 '"writes"' output.json | grep tps | awk -F': ' '{print $2}' | tr -d ',')
optimized_writes=$(grep -A1 '"writes"' output-optimized.json | grep tps | awk -F': ' '{print $2}' | tr -d ',')
improvement=$(echo "scale=2; ($baseline_writes - $optimized_writes) / $baseline_writes * 100" | bc)
echo "Baseline:  $baseline_writes TPS"
echo "Optimized: $optimized_writes TPS"
echo "Change: ${improvement}%"
echo ""

echo "========== READ LATENCY p50 (ms) =========="
baseline_p50=$(grep -A3 '"reads"' output.json | grep p50_ms | awk -F': ' '{print $2}' | tr -d ',')
optimized_p50=$(grep -A3 '"reads"' output-optimized.json | grep p50_ms | awk -F': ' '{print $2}' | tr -d ',')
echo "Baseline:  ${baseline_p50}ms"
echo "Optimized: ${optimized_p50}ms"
echo ""

echo "========== TRAVERSAL LATENCY p99 (ms) =========="
baseline_p99=$(grep -A5 '"traversal"' output.json | grep p99_ms | awk -F': ' '{print $2}' | tr -d ',')
optimized_p99=$(grep -A5 '"traversal"' output-optimized.json | grep p99_ms | awk -F': ' '{print $2}' | tr -d ',')
echo "Baseline:  ${baseline_p99}ms"
echo "Optimized: ${optimized_p99}ms"
echo ""

echo "========== TIME-RANGE QUERY (ms) =========="
baseline_tr=$(grep -A1 '"time_range"' output.json | grep last_30d_ms | awk -F': ' '{print $2}' | tr -d ',}')
optimized_tr=$(grep -A1 '"time_range"' output-optimized.json | grep last_30d_ms | awk -F': ' '{print $2}' | tr -d ',}')
speedup=$(echo "scale=2; $baseline_tr / $optimized_tr" | bc)
echo "Baseline:  ${baseline_tr}ms"
echo "Optimized: ${optimized_tr}ms"
echo "⚡ Speedup: ${speedup}x faster"
echo ""

echo "========== SUPERNODE QUERY (ms) =========="
baseline_sn=$(grep -A1 '"supernode"' output.json | grep 5000_rel_ms | awk -F': ' '{print $2}' | tr -d ',')
optimized_sn=$(grep -A1 '"supernode"' output-optimized.json | grep 5000_rel_ms | awk -F': ' '{print $2}' | tr -d ',')
echo "Baseline:  ${baseline_sn}ms"
echo "Optimized: ${optimized_sn}ms"
echo ""

echo "========== FULL RESULTS =========="
echo ""
echo "Baseline (output.json):"
python3 -m json.tool output.json | head -40
echo ""
echo "Optimized (output-optimized.json):"
python3 -m json.tool output-optimized.json | head -40
echo ""
echo "=========================================="
