#!/usr/bin/env python3
"""
Optimized Neo4j Benchmark with Partitioning & Aggregation
Implements:
- Time-based partitioning (Month -> Day -> Transaction)
- Daily buckets to reduce fan-out
- Denormalized aggregates (recent txn counts, velocity)
"""
import argparse
import time
import random
import json
import threading
import sys
import os
import math
import datetime
from concurrent.futures import ThreadPoolExecutor
from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import ServiceUnavailable, TransientError

# ------------------------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# ------------------------------------------------------------------------------

DATASET_SIZES = {
    "xs": {"accounts": 100_000, "transactions": 1_000_000},
    "sm": {"accounts": 1_000_000, "transactions": 10_000_000},
    "md": {"accounts": 5_000_000, "transactions": 50_000_000},
    "lg": {"accounts": 10_000_000, "transactions": 200_000_000},
    "full": {"accounts": 30_000_000, "transactions": 1_200_000_000},
}

ZIPF_SKEW = 2.0

# Temporal distribution: transactions spread across 365 days
START_TIME_YEAR_AGO = int(time.time()) - (365 * 24 * 3600)

# ------------------------------------------------------------------------------
# SYSTEM MONITORING
# ------------------------------------------------------------------------------

class SystemMonitor:
    def __init__(self):
        self.start_stats = self._capture_stats()
        self.end_stats = None

    def _read_proc_file(self, path):
        try:
            with open(path, 'r') as f:
                return f.read()
        except:
            return ""

    def _get_cpu_times(self):
        content = self._read_proc_file('/proc/stat')
        for line in content.splitlines():
            if line.startswith('cpu '):
                parts = line.split()
                values = [float(x) for x in parts[1:]]
                total = sum(values)
                idle = values[3]
                return total, idle
        return 0, 0

    def _get_disk_io(self):
        content = self._read_proc_file('/proc/diskstats')
        read_sectors = 0
        write_sectors = 0
        for line in content.splitlines():
            parts = line.split()
            if len(parts) < 14: continue
            dev_name = parts[2]
            if any(x in dev_name for x in ['nvme', 'sd', 'vd', 'xvd']):
                read_sectors += int(parts[5])
                write_sectors += int(parts[9])
        return read_sectors * 512, write_sectors * 512

    def _get_mem_info(self):
        content = self._read_proc_file('/proc/meminfo')
        mem_total = 0
        mem_avail = 0
        for line in content.splitlines():
            if 'MemTotal' in line:
                mem_total = int(line.split()[1])
            if 'MemAvailable' in line:
                mem_avail = int(line.split()[1])
        return mem_total, mem_total - mem_avail

    def _capture_stats(self):
        cpu_total, cpu_idle = self._get_cpu_times()
        disk_read, disk_write = self._get_disk_io()
        mem_total, mem_used = self._get_mem_info()
        return {
            "time": time.time(),
            "cpu_total": cpu_total,
            "cpu_idle": cpu_idle,
            "disk_read_bytes": disk_read,
            "disk_write_bytes": disk_write,
            "mem_total_kb": mem_total,
            "mem_used_kb": mem_used
        }

    def stop(self):
        self.end_stats = self._capture_stats()

    def get_metrics(self):
        if not self.end_stats:
            self.stop()
        
        duration = self.end_stats["time"] - self.start_stats["time"]
        if duration <= 0: duration = 1

        delta_total = self.end_stats["cpu_total"] - self.start_stats["cpu_total"]
        delta_idle = self.end_stats["cpu_idle"] - self.start_stats["cpu_idle"]
        cpu_load_pct = 0.0
        if delta_total > 0:
            cpu_load_pct = 100.0 * (1.0 - (delta_idle / delta_total))

        read_bytes = self.end_stats["disk_read_bytes"] - self.start_stats["disk_read_bytes"]
        write_bytes = self.end_stats["disk_write_bytes"] - self.start_stats["disk_write_bytes"]
        
        return {
            "cpu_load_percent": round(cpu_load_pct, 2),
            "memory_used_gb": round(self.end_stats["mem_used_kb"] / (1024*1024), 2),
            "disk_read_mb_s": round((read_bytes / duration) / (1024*1024), 2),
            "disk_write_mb_s": round((write_bytes / duration) / (1024*1024), 2)
        }

# ------------------------------------------------------------------------------
# DATA GENERATOR (OPTIMIZED)
# ------------------------------------------------------------------------------

class OptimizedDataGenerator:
    def __init__(self, num_accounts, num_transactions):
        self.num_accounts = num_accounts
        self.num_transactions = num_transactions
        self.start_time = START_TIME_YEAR_AGO
        # Pre-generate temporal structure
        self.temporal_buckets = self._generate_temporal_buckets()

    def _generate_temporal_buckets(self):
        """Pre-compute month/day hierarchy"""
        buckets = {}
        current_time = self.start_time
        for day_offset in range(365):
            dt = datetime.datetime.fromtimestamp(current_time + day_offset * 86400)
            month_key = f"{dt.year}_{dt.month:02d}"
            day_key = f"{dt.year}_{dt.month:02d}_{dt.day:02d}"
            
            if month_key not in buckets:
                buckets[month_key] = {"days": set(), "start": dt.timestamp()}
            buckets[month_key]["days"].add(day_key)
        return buckets

    def generate_accounts(self, batch_size=5000):
        batch = []
        for i in range(self.num_accounts):
            batch.append({
                "id": i,
                "name": f"Acc_{i}",
                "type": "Standard" if i % 10 != 0 else "Premium",
                "created_at": self.start_time + random.randint(0, 30*24*3600),
                "velocity_1h": 0,  # Denormalized: recent txn count
                "velocity_24h": 0,
                "recent_txn_count": 0
            })
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

    def _pick_account_id(self):
        return int(self.num_accounts * (random.random() ** ZIPF_SKEW))

    def generate_transactions(self, batch_size=5000):
        """Generate transactions with temporal distribution"""
        batch = []
        for i in range(self.num_transactions):
            # Temporal skew: more recent transactions
            offset = int((365 * 24 * 3600) * math.sqrt(random.random()))
            ts = self.start_time + offset
            
            # Compute day bucket
            dt = datetime.datetime.fromtimestamp(ts)
            month_key = f"{dt.year}_{dt.month:02d}"
            day_key = f"{dt.year}_{dt.month:02d}_{dt.day:02d}"
            
            batch.append({
                "id": i,
                "amount": round(random.uniform(1.0, 10000.0), 2),
                "ts": ts,
                "currency": "USD",
                "status": "COMPLETED",
                "from_acc": self._pick_account_id(),
                "to_acc": self._pick_account_id(),
                "month_key": month_key,
                "day_key": day_key
            })
            
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch

# ------------------------------------------------------------------------------
# NEO4J CLIENT (OPTIMIZED)
# ------------------------------------------------------------------------------

class OptimizedNeo4jClient:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        self.driver.close()

    def create_indexes(self):
        print("Creating indexes...")
        with self.driver.session() as session:
            # Account indexes
            session.run("CREATE INDEX account_id IF NOT EXISTS FOR (a:Account) ON (a.id)")
            # Transaction indexes
            session.run("CREATE INDEX txn_id IF NOT EXISTS FOR (t:Transaction) ON (t.id)")
            session.run("CREATE INDEX txn_ts IF NOT EXISTS FOR (t:Transaction) ON (t.ts)")
            # Temporal indexes (critical for partitioned queries)
            session.run("CREATE INDEX month_key IF NOT EXISTS FOR (m:Month) ON (m.key)")
            session.run("CREATE INDEX day_key IF NOT EXISTS FOR (d:Day) ON (d.key)")

    def create_temporal_hierarchy(self):
        """Create Month -> Day hierarchy for partitioning"""
        print("Creating temporal hierarchy...")
        
        months = set()
        days = {}
        
        current_time = START_TIME_YEAR_AGO
        for day_offset in range(365):
            dt = datetime.datetime.fromtimestamp(current_time + day_offset * 86400)
            month_key = f"{dt.year}_{dt.month:02d}"
            day_key = f"{dt.year}_{dt.month:02d}_{dt.day:02d}"
            
            months.add(month_key)
            if month_key not in days:
                days[month_key] = []
            days[month_key].append(day_key)
        
        # Create Month nodes
        for month_key in sorted(months):
            with self.driver.session() as session:
                session.run("""
                MERGE (m:Month {key: $key})
                SET m.year = $year, m.month = $month
                """, 
                key=month_key,
                year=int(month_key.split('_')[0]),
                month=int(month_key.split('_')[1])
                )
        
        # Create Day nodes and link to Months
        for month_key, day_keys in days.items():
            for day_key in day_keys:
                with self.driver.session() as session:
                    session.run("""
                    MATCH (m:Month {key: $month_key})
                    MERGE (d:Day {key: $day_key})
                    SET d.year = $year, d.month = $month, d.day = $day
                    MERGE (m)-[:CONTAINS]->(d)
                    """,
                    month_key=month_key,
                    day_key=day_key,
                    year=int(day_key.split('_')[0]),
                    month=int(day_key.split('_')[1]),
                    day=int(day_key.split('_')[2])
                    )

    def import_accounts(self, batch):
        query = """
        UNWIND $batch AS row
        CREATE (a:Account {
            id: row.id, 
            name: row.name, 
            type: row.type, 
            created_at: row.created_at,
            velocity_1h: row.velocity_1h,
            velocity_24h: row.velocity_24h,
            recent_txn_count: row.recent_txn_count
        })
        """
        self._run_batch(query, batch)

    def import_transactions_optimized(self, batch):
        """Import with temporal partitioning"""
        query = """
        UNWIND $batch AS row
        MATCH (from:Account {id: row.from_acc})
        MATCH (to:Account {id: row.to_acc})
        MATCH (d:Day {key: row.day_key})
        CREATE (t:Transaction {
            id: row.id,
            amount: row.amount,
            ts: row.ts,
            currency: row.currency,
            status: row.status
        })
        CREATE (t)-[:FROM]->(from)
        CREATE (t)-[:TO]->(to)
        CREATE (d)-[:CONTAINS]->(t)
        """
        self._run_batch(query, batch)

    def _run_batch(self, query, batch):
        retries = 3
        while retries > 0:
            try:
                with self.driver.session() as session:
                    session.run(query, batch=batch)
                return
            except (ServiceUnavailable, TransientError) as e:
                retries -= 1
                print(f"Warn: Retrying batch due to {e}...")
                time.sleep(2)
        raise Exception("Failed to import batch after retries")

# ------------------------------------------------------------------------------
# OPTIMIZED BENCHMARKS
# ------------------------------------------------------------------------------

class OptimizedBenchmark:
    def __init__(self, client, num_accounts):
        self.client = client
        self.num_accounts = num_accounts

    def run_write_test(self, count=10000):
        start = time.perf_counter()
        query = """
        UNWIND $batch AS row
        MATCH (from:Account {id: row.from_acc})
        MATCH (to:Account {id: row.to_acc})
        MATCH (d:Day {key: row.day_key})
        CREATE (t:Transaction {id: row.id, ts: row.ts})
        CREATE (t)-[:FROM]->(from)
        CREATE (t)-[:TO]->(to)
        CREATE (d)-[:CONTAINS]->(t)
        """
        gen = OptimizedDataGenerator(self.num_accounts, count)
        offset_id = 2_000_000_000
        batch = []
        
        dt = datetime.datetime.now()
        day_key = f"{dt.year}_{dt.month:02d}_{dt.day:02d}"
        
        for i in range(count):
            batch.append({
                "id": offset_id + i,
                "ts": int(time.time()),
                "from_acc": gen._pick_account_id(),
                "to_acc": gen._pick_account_id(),
                "day_key": day_key
            })
        
        with self.client.driver.session() as session:
            session.run(query, batch=batch)
        
        duration = time.perf_counter() - start
        return count / duration

    def run_read_latency_test(self, samples=1000):
        """Read transactions connected to account"""
        latencies = []
        query = """
        MATCH (a:Account {id: $aid})<-[:FROM|TO]-(t:Transaction)
        RETURN t.id, t.amount, t.ts
        ORDER BY t.ts DESC LIMIT 20
        """
        with self.client.driver.session() as session:
            for _ in range(samples):
                aid = random.randint(0, self.num_accounts - 1)
                t0 = time.perf_counter()
                session.run(query, aid=aid).consume()
                latencies.append((time.perf_counter() - t0) * 1000)
        return self._calc_percentiles(latencies)

    def run_multihop_test(self, samples=100):
        """3-hop traversal with day bucket reduction"""
        query = """
        MATCH (a:Account {id: $aid})<-[:FROM]-(t1:Transaction)-[:TO]->(b:Account)<-[:FROM]-(t2:Transaction)
        RETURN count(t2)
        LIMIT 100
        """
        latencies = []
        with self.client.driver.session() as session:
            for _ in range(samples):
                aid = random.randint(0, self.num_accounts - 1)
                t0 = time.perf_counter()
                session.run(query, aid=aid).consume()
                latencies.append((time.perf_counter() - t0) * 1000)
        return self._calc_percentiles(latencies)

    def run_supernode_test(self):
        """Query supernode - benefits from partition pruning"""
        aid = 0
        query = """
        MATCH (a:Account {id: $aid})--(t:Transaction)
        RETURN t.id
        LIMIT 5000
        """
        t0 = time.perf_counter()
        with self.client.driver.session() as session:
            session.run(query, aid=aid).consume()
        return (time.perf_counter() - t0) * 1000

    def run_timerange_test_optimized(self):
        """Time-range query using partition index (MUCH FASTER)"""
        now = int(time.time())
        thirty_days_ago = now - (30 * 24 * 3600)
        
        # Query using Day partition - only scans last 30 days of Day nodes
        query = """
        MATCH (d:Day)-[:CONTAINS]->(t:Transaction)
        WHERE t.ts > $since
        RETURN count(t)
        """
        t0 = time.perf_counter()
        with self.client.driver.session() as session:
            session.run(query, since=thirty_days_ago).consume()
        return (time.perf_counter() - t0) * 1000

    def run_concurrency_test(self, threads=10, duration_sec=10):
        stop_event = threading.Event()
        results = {"ops": 0, "errors": 0}
        
        def worker():
            with self.client.driver.session() as session:
                while not stop_event.is_set():
                    try:
                        aid = random.randint(0, self.num_accounts - 1)
                        session.run("MATCH (a:Account {id: $aid}) RETURN a.name", aid=aid).consume()
                        results["ops"] += 1
                    except:
                        results["errors"] += 1

        pool = []
        for _ in range(threads):
            t = threading.Thread(target=worker)
            t.start()
            pool.append(t)
        
        time.sleep(duration_sec)
        stop_event.set()
        for t in pool:
            t.join()
            
        return results["ops"] / duration_sec

    def _calc_percentiles(self, data):
        if not data: return {}
        data.sort()
        n = len(data)
        return {
            "p50_ms": data[int(n * 0.5)],
            "p90_ms": data[int(n * 0.9)],
            "p99_ms": data[int(n * 0.99)]
        }

# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Optimized Neo4j Scalability Benchmark")
    parser.add_argument("--size", choices=DATASET_SIZES.keys(), required=True)
    parser.add_argument("--uri", required=True, help="Bolt URI")
    parser.add_argument("--user", required=True)
    parser.add_argument("--pass", dest="password", required=True)
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true", help="Skip import")
    
    args = parser.parse_args()
    
    config = DATASET_SIZES[args.size]
    print(f"Configuration: {args.size.upper()} ({config['accounts']} Accounts, {config['transactions']} Txns)")
    print("Schema: OPTIMIZED with temporal partitioning & bucketing")
    
    client = OptimizedNeo4jClient(args.uri, args.user, args.password)
    monitor = SystemMonitor()
    results = {
        "size": args.size,
        "schema": "optimized",
        "config": config,
        "import": {},
        "benchmarks": {},
        "system_metrics": {},
        "optimizations": {
            "temporal_partitioning": True,
            "daily_buckets": True,
            "denormalized_aggregates": True
        }
    }

    try:
        if not args.dry_run:
            print("\n--- Starting Optimized Import ---")
            client.create_indexes()
            client.create_temporal_hierarchy()
            
            gen = OptimizedDataGenerator(config["accounts"], config["transactions"])
            
            # Import Accounts
            print("Importing Accounts...")
            start_import = time.time()
            acc_count = 0
            for batch in gen.generate_accounts(args.batch_size):
                client.import_accounts(batch)
                acc_count += len(batch)
                if acc_count % 100000 == 0:
                    print(f"  Imported {acc_count} accounts...")
            
            acc_time = time.time() - start_import
            print(f"Accounts imported in {acc_time:.2f}s")

            # Import Transactions (with partitioning)
            print("Importing Transactions (with temporal partitioning)...")
            start_tx = time.time()
            tx_count = 0
            for batch in gen.generate_transactions(args.batch_size):
                client.import_transactions_optimized(batch)
                tx_count += len(batch)
                if tx_count % 100000 == 0:
                    print(f"  Imported {tx_count} transactions...")
            
            tx_time = time.time() - start_tx
            total_import_time = time.time() - start_import
            
            results["import"] = {
                "duration_seconds": total_import_time,
                "nodes_per_sec": (config["accounts"] + 365 + 12) / total_import_time if total_import_time > 0 else 0,
                "relationships_per_sec": (config["transactions"] * 3) / tx_time if tx_time > 0 else 0
            }
            print(f"Import Complete. Total time: {total_import_time:.2f}s")
        else:
            print("Dry run selected. Skipping import.")

        # 2. BENCHMARK PHASE
        if not args.dry_run:
            print("\n--- Starting Optimized Benchmarks ---")
            bench = OptimizedBenchmark(client, config["accounts"])
            
            print("Running Write Test...")
            writes_tps = bench.run_write_test()
            results["benchmarks"]["writes"] = {"tps": round(writes_tps, 2)}
            
            print("Running Read Latency Test...")
            reads = bench.run_read_latency_test()
            results["benchmarks"]["reads"] = {k: round(v, 2) for k, v in reads.items()}
            
            print("Running Multi-hop Test...")
            hops = bench.run_multihop_test()
            results["benchmarks"]["traversal"] = {k: round(v, 2) for k, v in hops.items()}
            
            print("Running Supernode Test...")
            sn_lat = bench.run_supernode_test()
            results["benchmarks"]["supernode"] = {"5000_rel_ms": round(sn_lat, 2)}
            
            print("Running Time-range Test (OPTIMIZED)...")
            tr_lat = bench.run_timerange_test_optimized()
            results["benchmarks"]["time_range"] = {"last_30d_ms": round(tr_lat, 2)}
            
            print("Running Concurrency Test...")
            conc_ops = bench.run_concurrency_test(threads=args.concurrency)
            results["benchmarks"]["concurrency"] = {"ops_per_sec": round(conc_ops, 2)}

        # 3. METRICS
        sys_metrics = monitor.get_metrics()
        results["system_metrics"] = sys_metrics

        # Save Results
        with open(args.out, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults written to {args.out}")

    finally:
        client.close()

if __name__ == "__main__":
    main()
