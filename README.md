# Neo4j Performance Benchmark

A scalable Neo4j benchmark tool for testing graph database performance with realistic financial transaction data.

## Quick Start

### Using Docker Compose (Recommended)

1. **Run the XS benchmark:**
```bash
chmod +x run-benchmark.sh
./run-benchmark.sh
```

2. **Or use docker-compose directly:**
```bash
docker-compose up --build --abort-on-container-exit
```

### Configuration

Edit `.env` file to customize:

```bash
# Neo4j Authentication
NEO4J_USER=neo4j
NEO4J_PASSWORD=benchmarkpass

# Benchmark Configuration
BENCHMARK_SIZE=xs          # xs, sm, md, lg, or full
OUTPUT_FILE=output.json
BATCH_SIZE=5000
CONCURRENCY=10
```

### Dataset Sizes

| Size | Accounts | Transactions | Est. Time |
|------|----------|--------------|-----------|
| xs   | 100K     | 1M           | ~5 min    |
| sm   | 1M       | 10M          | ~30 min   |
| md   | 5M       | 50M          | ~2 hours  |
| lg   | 10M      | 200M         | ~8 hours  |
| full | 30M      | 1.2B         | ~24 hours |

## Manual Execution

### Prerequisites
- Python 3.11+
- Neo4j 5.x running locally or remotely

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Benchmark
```bash
python3 neo4j_bench.py \
  --size xs \
  --uri bolt://localhost:7687 \
  --user neo4j \
  --pass yourpassword \
  --out output.json \
  --batch-size 5000 \
  --concurrency 10
```

## Docker Commands

**Start services:**
```bash
docker-compose up -d
```

**View logs:**
```bash
docker-compose logs -f benchmark
```

**Stop and clean up:**
```bash
docker-compose down -v  # Remove volumes
docker-compose down      # Keep volumes
```

**Access Neo4j Browser:**
```
http://localhost:7474
```

## Output

Results are saved to `output.json` with:
- Import performance metrics
- Read/write latency percentiles
- Multi-hop traversal performance
- Supernode handling
- Time-range query performance
- Concurrency test results
- System resource utilization

## Troubleshooting

**Neo4j not starting:**
- Check memory limits in `docker-compose.yml`
- Verify port 7687 is not in use: `lsof -i :7687`

**Benchmark fails:**
- Check Neo4j logs: `docker-compose logs neo4j`
- Verify health: `docker-compose ps`

**Out of memory:**
- Increase Neo4j heap size in `docker-compose.yml`
- Use smaller dataset size
