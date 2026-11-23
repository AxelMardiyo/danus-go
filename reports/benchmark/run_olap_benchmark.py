#!/usr/bin/env python3
"""
DanusGo - Benchmark Kueri Analitik OLAP (Bab 13)
Menguji:
1. ROLLUP Hierarkis (Wilayah -> Organisasi -> Kategori)
2. CUBE Multidimensi (Wilayah x Kuartal x Kategori)
3. Slice & Dice (Kategori Makanan Berat pada Jam Makan Siang 11-13 di Fakultas Teknik)
4. Materialized View Pre-Aggregated vs On-the-Fly Aggregation
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

def run_explain_analyze(conn, query, runs=3):
    cur = conn.cursor()
    # warm up
    cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {query}")
    _ = cur.fetchall()
    
    times = []
    plan_lines = []
    buffers_hit = 0
    buffers_read = 0
    
    for _ in range(runs):
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS) {query}")
        lines = [r[0] for r in cur.fetchall()]
        plan_lines = lines
        for l in lines:
            if "Execution Time:" in l:
                t = float(l.split("Execution Time:")[1].replace("ms", "").strip())
                times.append(t)
            if "Buffers: shared hit=" in l:
                parts = l.split("shared hit=")[1].split()
                buffers_hit = int(parts[0].replace(",", ""))
                if "read=" in l:
                    buffers_read = int(l.split("read=")[1].split()[0].replace(",", ""))
                    
    mean_time = sum(times) / len(times)
    return {
        "mean_time_ms": round(mean_time, 3),
        "buffers_hit": buffers_hit,
        "buffers_read": buffers_read,
        "plan": plan_lines
    }

def run_all_olap():
    print("="*70)
    print("MEMULAI BENCHMARK KUERI ANALITIK OLAP (BAB 13)")
    print("="*70)
    
    results = {}
    
    with get_connection() as conn:
        cur = conn.cursor()
        
        # 1. ROLLUP
        print("\n[1] Menjalankan Kueri 1: GROUP BY ROLLUP (Hierarki)")
        q_rollup = """
            SELECT 
                COALESCE(s.wilayah_fakultas, 'SEMUA WILAYAH') AS wilayah_fakultas,
                COALESCE(o.organisasi, 'SEMUA ORGANISASI') AS nama_organisasi,
                COALESCE(p.kategori, 'SEMUA KATEGORI') AS kategori,
                COUNT(*) AS total_transaksi,
                SUM(f.kuantitas_terjual) AS total_item_terjual,
                SUM(f.total_omzet) AS total_omzet,
                SUM(f.laba_bersih) AS total_laba
            FROM dw.fakta_penjualan_danus f
            JOIN dw.dim_spot s ON s.id_spot_dw = f.id_spot_dw
            JOIN dw.dim_organisasi o ON o.id_organisasi_dw = f.id_organisasi_dw
            JOIN dw.dim_produk p ON p.id_produk_dw = f.id_produk_dw
            GROUP BY ROLLUP (s.wilayah_fakultas, o.organisasi, p.kategori)
            ORDER BY s.wilayah_fakultas NULLS LAST, o.organisasi NULLS LAST, p.kategori NULLS LAST
        """
        exp_rollup = run_explain_analyze(conn, q_rollup)
        cur.execute(q_rollup)
        sample_rollup = cur.fetchmany(10)
        cur.execute(f"SELECT count(*) FROM ({q_rollup}) sub")
        cnt_rollup = cur.fetchone()[0]
        print(f"  -> Waktu: {exp_rollup['mean_time_ms']} ms | Total Row Hasil: {cnt_rollup} | Buffers: {exp_rollup['buffers_hit']}")
        results["rollup"] = {
            "time_ms": exp_rollup["mean_time_ms"],
            "buffers_hit": exp_rollup["buffers_hit"],
            "total_rows": cnt_rollup,
            "sample_rows": sample_rollup,
            "plan": exp_rollup["plan"]
        }

        # 2. CUBE
        print("\n[2] Menjalankan Kueri 2: GROUP BY CUBE (Multidimensi)")
        q_cube = """
            SELECT 
                COALESCE(s.wilayah_fakultas, 'SEMUA WILAYAH') AS wilayah_fakultas,
                COALESCE(w.kuartal::text, 'SEMUA KUARTAL') AS kuartal,
                COALESCE(p.kategori, 'SEMUA KATEGORI') AS kategori,
                SUM(f.total_omzet) AS total_omzet,
                SUM(f.laba_bersih) AS total_laba
            FROM dw.fakta_penjualan_danus f
            JOIN dw.dim_spot s ON s.id_spot_dw = f.id_spot_dw
            JOIN dw.dim_waktu w ON w.id_waktu = f.id_waktu
            JOIN dw.dim_produk p ON p.id_produk_dw = f.id_produk_dw
            GROUP BY CUBE (s.wilayah_fakultas, w.kuartal, p.kategori)
            ORDER BY s.wilayah_fakultas NULLS LAST, w.kuartal NULLS LAST, p.kategori NULLS LAST
        """
        exp_cube = run_explain_analyze(conn, q_cube)
        cur.execute(q_cube)
        sample_cube = cur.fetchmany(10)
        cur.execute(f"SELECT count(*) FROM ({q_cube}) sub")
        cnt_cube = cur.fetchone()[0]
        print(f"  -> Waktu: {exp_cube['mean_time_ms']} ms | Total Row Hasil: {cnt_cube} | Buffers: {exp_cube['buffers_hit']}")
        results["cube"] = {
            "time_ms": exp_cube["mean_time_ms"],
            "buffers_hit": exp_cube["buffers_hit"],
            "total_rows": cnt_cube,
            "sample_rows": sample_cube,
            "plan": exp_cube["plan"]
        }

        # 3. Slice & Dice
        print("\n[3] Menjalankan Kueri 3: Slice & Dice (Makanan Berat, Jam Makan Siang 11-13, Teknik)")
        q_slicedice = """
            SELECT 
                s.spot AS lokasi_spot,
                p.produk AS nama_makanan,
                j.jam,
                SUM(f.kuantitas_terjual) AS kuantitas_terjual,
                SUM(f.total_omzet) AS omzet_makan_siang,
                SUM(f.laba_bersih) AS laba_makan_siang
            FROM dw.fakta_penjualan_danus f
            JOIN dw.dim_spot s ON s.id_spot_dw = f.id_spot_dw
            JOIN dw.dim_jam j ON j.id_jam = f.id_jam
            JOIN dw.dim_produk p ON p.id_produk_dw = f.id_produk_dw
            WHERE p.kategori = 'MAKANAN_BERAT'
              AND s.wilayah_fakultas = 'Teknik'
              AND j.jam BETWEEN 11 AND 13
            GROUP BY s.spot, p.produk, j.jam
            ORDER BY omzet_makan_siang DESC
        """
        exp_slicedice = run_explain_analyze(conn, q_slicedice)
        cur.execute(q_slicedice)
        sample_slicedice = cur.fetchmany(10)
        cur.execute(f"SELECT count(*) FROM ({q_slicedice}) sub")
        cnt_slicedice = cur.fetchone()[0]
        print(f"  -> Waktu: {exp_slicedice['mean_time_ms']} ms | Total Row Hasil: {cnt_slicedice} | Buffers: {exp_slicedice['buffers_hit']}")
        results["slicedice"] = {
            "time_ms": exp_slicedice["mean_time_ms"],
            "buffers_hit": exp_slicedice["buffers_hit"],
            "total_rows": cnt_slicedice,
            "sample_rows": sample_slicedice,
            "plan": exp_slicedice["plan"]
        }

        # 4. Materialized View Comparison
        print("\n[4] Menjalankan Kueri 4: Materialized View Pre-Aggregated vs On-the-Fly Aggregation")
        # On-the-Fly
        q_onthefly = """
            SELECT w.tahun, w.bulan, s.wilayah_fakultas, p.kategori,
                   SUM(f.kuantitas_terjual) AS kuantitas,
                   SUM(f.total_omzet) AS omzet,
                   SUM(f.laba_bersih) AS laba
            FROM dw.fakta_penjualan_danus f
            JOIN dw.dim_waktu w ON w.id_waktu = f.id_waktu
            JOIN dw.dim_spot s ON s.id_spot_dw = f.id_spot_dw
            JOIN dw.dim_produk p ON p.id_produk_dw = f.id_produk_dw
            GROUP BY w.tahun, w.bulan, s.wilayah_fakultas, p.kategori
        """
        exp_onthefly = run_explain_analyze(conn, q_onthefly)
        
        # Pre-Aggregated Materialized View
        q_mv = """
            SELECT tahun, bulan, wilayah_fakultas, kategori, kuantitas, omzet, laba
            FROM dw.mv_omzet_bulanan
        """
        exp_mv = run_explain_analyze(conn, q_mv)
        
        speedup_mv = exp_onthefly["mean_time_ms"] / exp_mv["mean_time_ms"]
        io_reduction = (1 - (exp_mv["buffers_hit"] / exp_onthefly["buffers_hit"])) * 100
        
        print(f"  -> On-The-Fly Aggregation: {exp_onthefly['mean_time_ms']} ms | Buffers: {exp_onthefly['buffers_hit']}")
        print(f"  -> Materialized View Scan: {exp_mv['mean_time_ms']} ms | Buffers: {exp_mv['buffers_hit']}")
        print(f"  -> Speedup Materialized View: {speedup_mv:.2f}x | Reduksi Buffer I/O: {io_reduction:.1f}%")
        
        results["mv_comparison"] = {
            "onthefly": exp_onthefly,
            "materialized_view": exp_mv,
            "speedup": round(speedup_mv, 2),
            "io_reduction_percent": round(io_reduction, 1)
        }

    out_file = "reports/benchmark/olap_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
        
    with open("reports/benchmark/raw_explain_olap.txt", "w", encoding="utf-8") as f:
        for k in ["rollup", "cube", "slicedice"]:
            f.write(f"\n{'='*70}\nEXPLAIN (ANALYZE, BUFFERS) - {k.upper()}\n{'='*70}\n")
            f.write("\n".join(results[k]["plan"]))
            f.write("\n")
        f.write(f"\n{'='*70}\nEXPLAIN (ANALYZE, BUFFERS) - ON-THE-FLY\n{'='*70}\n")
        f.write("\n".join(results["mv_comparison"]["onthefly"]["plan"]))
        f.write(f"\n{'='*70}\nEXPLAIN (ANALYZE, BUFFERS) - MATERIALIZED VIEW\n{'='*70}\n")
        f.write("\n".join(results["mv_comparison"]["materialized_view"]["plan"]))

    print(f"\n[OK] Seluruh data benchmark OLAP tersimpan di {out_file} dan reports/benchmark/raw_explain_olap.txt")

if __name__ == "__main__":
    run_all_olap()
