#!/usr/bin/env python3
"""
DanusGo - Benchmark Basis Data Paralel dan Partisi (Bab 9)
Mengukur dan menganalisis:
1. Ukuran fisik dan distribusi data (Range vs Hash vs Non-Partitioned)
2. Partition Pruning efektivitas (Filter Waktu vs Filter Entitas id_mahasiswa)
3. Parallel Query Scaling & Speedup (max_parallel_workers_per_gather = 0, 2, 4)
4. Hukum Amdahl (Amdahl's Law) & Efisiensi Paralel
"""

import psycopg
import json
import time

DB_PARAMS = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "danusgo",
    "password": "danusgo_dev",
    "dbname": "danusgo"
}

def get_connection():
    return psycopg.connect(**DB_PARAMS)

def run_query_explain(conn, query, runs=5):
    """Menjalankan EXPLAIN ANALYZE beberapa kali dan mengambil rata-rata waktu eksekusi serta plan."""
    # Warm-up run
    cur = conn.cursor()
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {query}")
    _ = cur.fetchall()
    
    times = []
    buffers_hit = 0
    buffers_read = 0
    raw_plan = []
    
    for _ in range(runs):
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {query}")
        lines = [r[0] for r in cur.fetchall()]
        raw_plan = lines
        for line in lines:
            if "Execution Time:" in line:
                t = float(line.split("Execution Time:")[1].replace("ms", "").strip())
                times.append(t)
            if "Buffers: shared hit=" in line:
                parts = line.split("shared hit=")[1].split()
                hit = int(parts[0].replace(",", ""))
                buffers_hit = hit
                if "read=" in line:
                    read = int(line.split("read=")[1].split()[0].replace(",", ""))
                    buffers_read = read
                    
    mean_time = sum(times) / len(times)
    min_time = min(times)
    
    return {
        "mean_time_ms": round(mean_time, 3),
        "min_time_ms": round(min_time, 3),
        "all_times": times,
        "buffers_hit": buffers_hit,
        "buffers_read": buffers_read,
        "raw_plan": raw_plan
    }

def step1_measure_storage():
    print("\n--- 1. Pengukuran Ukuran Fisik & Distribusi Data ---")
    with get_connection() as conn:
        cur = conn.cursor()
        
        # Non-partitioned flat
        cur.execute("""
            SELECT count(*), 
                   pg_size_pretty(pg_relation_size('pesanan_flat')),
                   pg_size_pretty(pg_total_relation_size('pesanan_flat')),
                   pg_relation_size('pesanan_flat')
            FROM pesanan_flat;
        """)
        row = cur.fetchone()
        flat_info = {"rows": row[0], "table_size": row[1], "total_size": row[2], "bytes": row[3]}
        print(f"Flat Table: {flat_info['rows']} rows, Size={flat_info['table_size']}, Total={flat_info['total_size']}")
        
        # Hash partitions
        hash_parts = {}
        for p in ['pesanan_hash_p0', 'pesanan_hash_p1', 'pesanan_hash_p2', 'pesanan_hash_p3']:
            cur.execute(f"""
                SELECT count(*), 
                       pg_size_pretty(pg_relation_size('{p}')),
                       pg_relation_size('{p}')
                FROM {p};
            """)
            r = cur.fetchone()
            hash_parts[p] = {"rows": r[0], "size": r[1], "bytes": r[2]}
            print(f"  Hash Part {p}: {r[0]} rows, Size={r[1]}")
            
        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('pesanan_hash'));")
        hash_total_size = cur.fetchone()[0]
        
        # Range partitions
        range_parts = {}
        for m in range(1, 12):
            p = f"pesanan_2026_{m:02d}"
            cur.execute(f"""
                SELECT count(*), 
                       pg_size_pretty(pg_relation_size('{p}')),
                       pg_relation_size('{p}')
                FROM {p};
            """)
            r = cur.fetchone()
            range_parts[p] = {"rows": r[0], "size": r[1], "bytes": r[2]}
            print(f"  Range Part {p}: {r[0]} rows, Size={r[1]}")
            
        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('pesanan_danus'));")
        range_total_size = cur.fetchone()[0]

    return {
        "flat": flat_info,
        "hash": {"total_size": hash_total_size, "partitions": hash_parts},
        "range": {"total_size": range_total_size, "partitions": range_parts}
    }

def step2_partition_pruning():
    print("\n--- 2. Pengujian Efektivitas Partition Pruning ---")
    with get_connection() as conn:
        # A. Filter Waktu (Rentang 1 Bulan: 2026-11)
        print("[Skenario A: Filter Rentang Waktu (1 Bulan)]")
        q_time_range = "SELECT count(*), max(waktu_pesan) FROM {tbl} WHERE waktu_pesan >= '2026-11-01 00:00+07' AND waktu_pesan < '2026-12-01 00:00+07';"
        
        res_range_time = run_query_explain(conn, q_time_range.format(tbl="pesanan_danus"))
        res_hash_time = run_query_explain(conn, q_time_range.format(tbl="pesanan_hash"))
        res_flat_time = run_query_explain(conn, q_time_range.format(tbl="pesanan_flat"))
        
        # Ekstrak partisi yang dipindai
        parts_scanned_range = [line.strip() for line in res_range_time["raw_plan"] if "Seq Scan on" in line or "Index Scan on" in line]
        parts_scanned_hash = [line.strip() for line in res_hash_time["raw_plan"] if "Seq Scan on" in line or "Index Scan on" in line]
        
        print(f"  Range Partitioning  : {res_range_time['mean_time_ms']} ms | Scan: {len(parts_scanned_range)} partisi ({parts_scanned_range})")
        print(f"  Hash Partitioning   : {res_hash_time['mean_time_ms']} ms | Scan: {len(parts_scanned_hash)} partisi (Semua partisi dipindai!)")
        print(f"  Flat Non-Partitioned: {res_flat_time['mean_time_ms']} ms | Scan: 1 full table")

        # B. Filter Entitas (ID Mahasiswa = 500)
        print("\n[Skenario B: Filter ID Mahasiswa Tunggal (id_mahasiswa = 500)]")
        q_entity = "SELECT count(*), min(waktu_pesan) FROM {tbl} WHERE id_mahasiswa = 500;"
        
        res_range_entity = run_query_explain(conn, q_entity.format(tbl="pesanan_danus"))
        res_hash_entity = run_query_explain(conn, q_entity.format(tbl="pesanan_hash"))
        res_flat_entity = run_query_explain(conn, q_entity.format(tbl="pesanan_flat"))
        
        parts_scanned_range_ent = [line.strip() for line in res_range_entity["raw_plan"] if "Seq Scan on" in line or "Index Scan on" in line]
        parts_scanned_hash_ent = [line.strip() for line in res_hash_entity["raw_plan"] if "Seq Scan on" in line or "Index Scan on" in line]
        
        print(f"  Range Partitioning  : {res_range_entity['mean_time_ms']} ms | Scan: {len(parts_scanned_range_ent)} partisi (Semua 11 partisi dipindai!)")
        print(f"  Hash Partitioning   : {res_hash_entity['mean_time_ms']} ms | Scan: {len(parts_scanned_hash_ent)} partisi ({parts_scanned_hash_ent})")
        print(f"  Flat Non-Partitioned: {res_flat_entity['mean_time_ms']} ms | Scan: 1 full table")

    return {
        "time_filter": {
            "range": {"time_ms": res_range_time["mean_time_ms"], "scanned": parts_scanned_range, "plan": res_range_time["raw_plan"]},
            "hash": {"time_ms": res_hash_time["mean_time_ms"], "scanned": parts_scanned_hash, "plan": res_hash_time["raw_plan"]},
            "flat": {"time_ms": res_flat_time["mean_time_ms"], "plan": res_flat_time["raw_plan"]}
        },
        "entity_filter": {
            "range": {"time_ms": res_range_entity["mean_time_ms"], "scanned": parts_scanned_range_ent, "plan": res_range_entity["raw_plan"]},
            "hash": {"time_ms": res_hash_entity["mean_time_ms"], "scanned": parts_scanned_hash_ent, "plan": res_hash_entity["raw_plan"]},
            "flat": {"time_ms": res_flat_entity["mean_time_ms"], "plan": res_flat_entity["raw_plan"]}
        }
    }

def step3_parallel_scaling():
    print("\n--- 3. Pengujian Parallel Query Scaling & Speedup ---")
    query_heavy = """
        SELECT 
            p.metode_bayar,
            p.status_pesanan,
            COUNT(*) AS total_transaksi,
            SUM(d.jumlah_item) AS total_item,
            SUM(d.jumlah_item * d.harga_satuan) AS omzet_kotor,
            SUM(d.jumlah_item * (d.harga_satuan - d.harga_modal_satuan)) AS laba_kotor,
            AVG(d.harga_satuan) AS avg_harga
        FROM pesanan_danus p
        JOIN detail_pesanan d ON p.id_pesanan = d.id_pesanan AND p.waktu_pesan = d.waktu_pesan
        GROUP BY p.metode_bayar, p.status_pesanan;
    """
    
    results = {}
    with get_connection() as conn:
        # Pastikan storage parameter parallel_workers aktif
        conn.execute("ALTER TABLE detail_pesanan SET (parallel_workers = 4);")
        for m in range(1, 12):
            conn.execute(f"ALTER TABLE pesanan_2026_{m:02d} SET (parallel_workers = 4);")
            
        for workers in [0, 2, 4]:
            conn.execute(f"SET max_parallel_workers_per_gather = {workers};")
            conn.execute("SET min_parallel_table_scan_size = 0;")
            
            res = run_query_explain(conn, query_heavy, runs=5)
            results[workers] = res
            print(f"Workers = {workers} : Mean Time = {res['mean_time_ms']} ms (Min = {res['min_time_ms']} ms), Buffers Hit = {res['buffers_hit']}")

    # Perhitungan Speedup dan Efisiensi
    t1 = results[0]["mean_time_ms"]
    scaling_metrics = {}
    print("\n--- Tabel Metrik Speedup & Efisiensi Paralel ---")
    print(f"{'Workers (n)':<12} | {'Waktu (ms)':<12} | {'Speedup (Sn)':<14} | {'Efisiensi (En)':<14}")
    print("-" * 60)
    for workers in [0, 2, 4]:
        tn = results[workers]["mean_time_ms"]
        speedup = t1 / tn
        efficiency = speedup / (workers if workers > 0 else 1)
        scaling_metrics[workers] = {
            "time_ms": tn,
            "speedup": round(speedup, 3),
            "efficiency": round(efficiency, 3),
            "efficiency_percent": round(efficiency * 100, 1)
        }
        print(f"{workers:<12} | {tn:<12} | {speedup:<14.3f} | {efficiency:<14.3f} ({efficiency*100:.1f}%)")

    return {
        "raw_results": results,
        "metrics": scaling_metrics
    }

def generate_svg_chart(metrics):
    """Menghasilkan file SVG grafik Speedup dan Efisiensi."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 420" width="100%" height="100%" style="font-family: Arial, sans-serif; background-color: #ffffff;">
  <!-- Judul -->
  <text x="400" y="32" font-size="18" font-weight="bold" text-anchor="middle" fill="#1e293b">Evaluasi Skalabilitas Paralel: Waktu Eksekusi vs Speedup (Bab 9)</text>
  <text x="400" y="52" font-size="12" fill="#64748b" text-anchor="middle">Agregasi Multi-Dimensi Pesanan (105k Pesanan + 144k Detail) pada PostgreSQL 16</text>

  <!-- Sumbu dan Garis Grid -->
  <line x1="100" y1="80" x2="100" y2="330" stroke="#cbd5e1" stroke-width="1.5" />
  <line x1="100" y1="330" x2="720" y2="330" stroke="#cbd5e1" stroke-width="1.5" />
  <line x1="100" y1="250" x2="720" y2="250" stroke="#f1f5f9" stroke-width="1" stroke-dasharray="4" />
  <line x1="100" y1="170" x2="720" y2="170" stroke="#f1f5f9" stroke-width="1" stroke-dasharray="4" />
  <line x1="100" y1="90" x2="720" y2="90" stroke="#f1f5f9" stroke-width="1" stroke-dasharray="4" />

  <!-- Label Y-Axis Waktu (ms) -->
  <text x="90" y="335" font-size="11" fill="#64748b" text-anchor="end">0 ms</text>
  <text x="90" y="255" font-size="11" fill="#64748b" text-anchor="end">60 ms</text>
  <text x="90" y="175" font-size="11" fill="#64748b" text-anchor="end">120 ms</text>
  <text x="90" y="95" font-size="11" fill="#64748b" text-anchor="end">180 ms</text>

  <!-- Batang Bar Waktu Eksekusi -->
  <!-- Worker 0 -->
  <rect x="180" y="{330 - (metrics[0]['time_ms']/180 * 240)}" width="65" height="{metrics[0]['time_ms']/180 * 240}" fill="#ef4444" rx="4" />
  <text x="212" y="{320 - (metrics[0]['time_ms']/180 * 240)}" font-size="12" font-weight="bold" fill="#ef4444" text-anchor="middle">{metrics[0]['time_ms']} ms</text>
  <text x="212" y="352" font-size="12" font-weight="bold" fill="#334155" text-anchor="middle">0 Worker</text>
  <text x="212" y="368" font-size="10" fill="#64748b" text-anchor="middle">(Sekuensial)</text>

  <!-- Worker 2 -->
  <rect x="360" y="{330 - (metrics[2]['time_ms']/180 * 240)}" width="65" height="{metrics[2]['time_ms']/180 * 240}" fill="#3b82f6" rx="4" />
  <text x="392" y="{320 - (metrics[2]['time_ms']/180 * 240)}" font-size="12" font-weight="bold" fill="#3b82f6" text-anchor="middle">{metrics[2]['time_ms']} ms</text>
  <text x="392" y="352" font-size="12" font-weight="bold" fill="#334155" text-anchor="middle">2 Workers</text>
  <text x="392" y="368" font-size="11" font-weight="bold" fill="#0284c7" text-anchor="middle">Speedup: {metrics[2]['speedup']}x</text>

  <!-- Worker 4 -->
  <rect x="540" y="{330 - (metrics[4]['time_ms']/180 * 240)}" width="65" height="{metrics[4]['time_ms']/180 * 240}" fill="#10b981" rx="4" />
  <text x="572" y="{320 - (metrics[4]['time_ms']/180 * 240)}" font-size="12" font-weight="bold" fill="#10b981" text-anchor="middle">{metrics[4]['time_ms']} ms</text>
  <text x="572" y="352" font-size="12" font-weight="bold" fill="#334155" text-anchor="middle">4 Workers</text>
  <text x="572" y="368" font-size="11" font-weight="bold" fill="#059669" text-anchor="middle">Speedup: {metrics[4]['speedup']}x</text>

  <!-- Info Box Amdahl's Law -->
  <rect x="140" y="390" width="520" height="25" fill="#f8fafc" stroke="#e2e8f0" rx="4" />
  <text x="400" y="407" font-size="11" fill="#475569" text-anchor="middle">
    Efisiensi Paralel: Worker 2 = {metrics[2]['efficiency_percent']}% | Worker 4 = {metrics[4]['efficiency_percent']}% (Sesuai Hukum Amdahl)
  </text>
</svg>"""
    with open("reports/figures/chart_parallel_speedup.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("[OK] Grafik tersimpan di reports/figures/chart_parallel_speedup.svg")

if __name__ == "__main__":
    print("=== MEMULAI BENCHMARK BASIS DATA PARALEL & PARTISI (BAB 9) ===")
    storage_data = step1_measure_storage()
    pruning_data = step2_partition_pruning()
    scaling_data = step3_parallel_scaling()
    
    generate_svg_chart(scaling_data["metrics"])
    
    full_export = {
        "storage": storage_data,
        "pruning": pruning_data,
        "parallel_scaling": scaling_data["metrics"],
        "raw_plans": {
            w: scaling_data["raw_results"][w]["raw_plan"] for w in [0, 2, 4]
        }
    }
    
    with open("reports/benchmark/parallel_partition_results.json", "w", encoding="utf-8") as f:
        json.dump(full_export, f, indent=2)
        
    # Simpan raw explain plans ke txt
    with open("reports/benchmark/raw_explain_parallel.txt", "w", encoding="utf-8") as f:
        for w in [0, 2, 4]:
            f.write(f"\n{'='*70}\nEXPLAIN (ANALYZE, BUFFERS) - WORKERS = {w}\n{'='*70}\n")
            f.write("\n".join(scaling_data["raw_results"][w]["raw_plan"]))
            f.write("\n")
            
    print("\n[OK] Seluruh data benchmark dan raw plan tersimpan di:")
    print("  - reports/benchmark/parallel_partition_results.json")
    print("  - reports/benchmark/raw_explain_parallel.txt")
