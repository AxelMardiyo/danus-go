#!/usr/bin/env python3
"""
DanusGo - Simulasi Crash Transaksi, Logging WAL, dan Pemetaan Algoritma ARIES (Bab 4)
Membuktikan:
1. Sifat Atomicity & Durability (ACID)
2. Mekanisme Write-Ahead Logging (WAL)
3. Siklus Pemulihan Algoritma ARIES (Analysis, Redo, Undo)
4. Perbandingan Crash Recovery: Tanpa Checkpoint vs Dengan Checkpoint Eksplisit
"""

import time
import subprocess
import json
import psycopg

DB_PARAMS = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "danusgo",
    "password": "danusgo_dev",
    "dbname": "danusgo"
}

def run_cmd(cmd):
    """Menjalankan shell command dan mengembalikan stdout/stderr."""
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout + res.stderr

def wait_for_db(max_retries=30, delay=1.0):
    """Menunggu database siap menerima koneksi."""
    for i in range(max_retries):
        try:
            with psycopg.connect(**DB_PARAMS, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    return True
        except Exception:
            time.sleep(delay)
    raise RuntimeError("Database gagal siap setelah crash restart.")

def get_waldump_records(limit=60):
    """Mengambil record WAL menggunakan pg_waldump di container."""
    find_cmd = "docker compose exec -u postgres db bash -c 'cd /var/lib/postgresql/data/pg_wal && ls -t | grep -E \"^[0-9A-F]{24}$\" | head -1'"
    wal_file = subprocess.run(find_cmd, shell=True, capture_output=True, text=True).stdout.strip()
    cmd = f"docker compose exec -u postgres db bash -c 'cd /var/lib/postgresql/data/pg_wal && pg_waldump -p . {wal_file} 2>&1 | tail -n {limit}'"
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout
    return out

def run_scenario_1():
    print("\n" + "="*70)
    print("SKENARIO 1: CRASH TANPA CHECKPOINT EKSPLISIT")
    print("="*70)
    
    # 1. Setup tabel uji
    with psycopg.connect(**DB_PARAMS) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS uji_crash_kuota (
                    id_sesi INT PRIMARY KEY,
                    nama_sesi TEXT NOT NULL,
                    kuota_awal INT NOT NULL,
                    kuota_sisa INT NOT NULL
                );
                TRUNCATE TABLE uji_crash_kuota;
                INSERT INTO uji_crash_kuota (id_sesi, nama_sesi, kuota_awal, kuota_sisa)
                VALUES (1, 'Sesi Danus Donat Pagi - Uji Crash 1', 100, 100);
            """)
            conn.commit()
            
            cur.execute("SELECT pg_current_wal_lsn();")
            lsn_initial = cur.fetchone()[0]
            print(f"[Init] Tabel uji_crash_kuota disiapkan: Kuota = 100, LSN Initial = {lsn_initial}")

    # 2. Transaksi Committed (T1)
    with psycopg.connect(**DB_PARAMS) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT txid_current();")
            txid_t1 = cur.fetchone()[0]
            cur.execute("UPDATE uji_crash_kuota SET kuota_sisa = kuota_sisa - 10 WHERE id_sesi = 1;")
            conn.commit()
            
            cur.execute("SELECT pg_current_wal_lsn(), kuota_sisa FROM uji_crash_kuota WHERE id_sesi = 1;")
            row = cur.fetchone()
            lsn_t1 = row[0]
            kuota_t1 = row[1]
            print(f"[T1 - Committed] txid={txid_t1}, Kuota dikurangi 10 (Sisa: {kuota_t1}), LSN setelah commit={lsn_t1}")

    # 3. Transaksi In-Flight / Uncommitted (T2) - JANGAN COMMIT
    conn_inflight = psycopg.connect(**DB_PARAMS)
    conn_inflight.autocommit = False
    cur_inflight = conn_inflight.cursor()
    cur_inflight.execute("SELECT txid_current();")
    txid_t2 = cur_inflight.fetchone()[0]
    cur_inflight.execute("UPDATE uji_crash_kuota SET kuota_sisa = kuota_sisa - 40 WHERE id_sesi = 1;")
    
    # Periksa nilai dalam transaksi T2 (dirty update dari perspektif T2)
    cur_inflight.execute("SELECT kuota_sisa FROM uji_crash_kuota WHERE id_sesi = 1;")
    kuota_dirty = cur_inflight.fetchone()[0]
    
    # Ambil LSN sebelum crash
    cur_inflight.execute("SELECT pg_current_wal_lsn();")
    lsn_t2 = cur_inflight.fetchone()[0]
    print(f"[T2 - In-Flight] txid={txid_t2}, Kuota dimodifikasi jadi {kuota_dirty} (belum commit!), LSN={lsn_t2}")

    # 4. CRASH: Kirim SIGKILL ke engine database
    print(f"[CRASH] Mengirim sinyal SIGKILL ke engine PostgreSQL container...")
    run_cmd("docker compose kill -s KILL db")
    time.sleep(1)
    
    try:
        conn_inflight.close()
    except Exception:
        pass
    
    # 5. RECOVERY: Nyalakan kembali container
    print("[RECOVERY] Memulai ulang database via docker compose up -d db...")
    run_cmd("docker compose up -d db")
    wait_for_db()
    print("[RECOVERY] Database berhasil hidup kembali dan siap melayani koneksi!")

    # 6. Tangkap log engine recovery
    logs = run_cmd("docker logs danusgo-db --tail 60")
    recovery_lines = [l for l in logs.splitlines() if any(k in l for k in ["recovery in progress", "redo starts at", "redo done at", "ready to accept connections", "shut down", "checkpoint starting", "checkpoint complete"])]
    print("\n--- Log Engine Recovery (PostgreSQL) ---")
    for l in recovery_lines:
        print("  " + l)

    # 7. Verifikasi State Konsistensi Data (Atomicity & Durability)
    with psycopg.connect(**DB_PARAMS) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT kuota_awal, kuota_sisa, pg_current_wal_lsn() FROM uji_crash_kuota WHERE id_sesi = 1;")
            row = cur.fetchone()
            kuota_awal_final, kuota_sisa_final, lsn_post_recovery = row[0], row[1], row[2]

    print("\n--- Hasil Verifikasi Data Post-Recovery ---")
    print(f"  Kuota Awal              : {kuota_awal_final}")
    print(f"  Kuota Aktual Pasca-Crash: {kuota_sisa_final}")
    print(f"  Status Transaksi T1 (Committed)   : {'PERSISTEN (Durability Terbukti)' if kuota_sisa_final == 90 else 'GAGAL'}")
    print(f"  Status Transaksi T2 (Uncommitted) : {'TERBATALKAN (Atomicity/Undo Terbukti)' if kuota_sisa_final == 90 else 'DIRTY DATA BOCOR'}")
    print(f"  LSN Pasca Pemulihan               : {lsn_post_recovery}")

    # 8. Ekstraksi WAL Dump
    print("\n--- Ekstraksi Record WAL via pg_waldump ---")
    wal_dump = get_waldump_records(limit=60)
    print(wal_dump[:1500] if len(wal_dump) > 1500 else wal_dump)

    result_s1 = {
        "scenario": "Scenario 1: Crash Tanpa Checkpoint Eksplisit",
        "lsn_initial": str(lsn_initial),
        "txid_t1_committed": txid_t1,
        "lsn_t1": str(lsn_t1),
        "txid_t2_uncommitted": txid_t2,
        "lsn_t2": str(lsn_t2),
        "kuota_dirty_pre_crash": kuota_dirty,
        "kuota_final_post_recovery": kuota_sisa_final,
        "durability_verified": kuota_sisa_final == 90,
        "atomicity_verified": kuota_sisa_final == 90,
        "lsn_post_recovery": str(lsn_post_recovery),
        "recovery_logs": recovery_lines,
        "wal_sample": wal_dump
    }
    return result_s1


def run_scenario_2():
    print("\n" + "="*70)
    print("SKENARIO 2: CRASH DENGAN CHECKPOINT EKSPLISIT")
    print("="*70)
    
    # 1. State awal dari Skenario 1 (kuota sisa = 90)
    # Lakukan T3 Committed
    with psycopg.connect(**DB_PARAMS) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT txid_current();")
            txid_t3 = cur.fetchone()[0]
            cur.execute("UPDATE uji_crash_kuota SET kuota_sisa = kuota_sisa - 10 WHERE id_sesi = 1;")
            conn.commit()
            
            cur.execute("SELECT pg_current_wal_lsn(), kuota_sisa FROM uji_crash_kuota WHERE id_sesi = 1;")
            row = cur.fetchone()
            lsn_t3 = row[0]
            kuota_t3 = row[1]
            print(f"[T3 - Committed] txid={txid_t3}, Kuota dikurangi 10 (Sisa: {kuota_t3}), LSN={lsn_t3}")

            # Jalankan CHECKPOINT eksplisit
            print("[CHECKPOINT] Menjalankan perintah CHECKPOINT secara eksplisit...")
            cur.execute("CHECKPOINT;")
            cur.execute("SELECT pg_current_wal_lsn();")
            lsn_checkpoint = cur.fetchone()[0]
            print(f"[CHECKPOINT] Selesai. Dirty buffers di-flush ke disk. LSN Checkpoint={lsn_checkpoint}")

    # 2. Transaksi In-Flight / Uncommitted (T4)
    conn_inflight = psycopg.connect(**DB_PARAMS)
    conn_inflight.autocommit = False
    cur_inflight = conn_inflight.cursor()
    cur_inflight.execute("SELECT txid_current();")
    txid_t4 = cur_inflight.fetchone()[0]
    cur_inflight.execute("UPDATE uji_crash_kuota SET kuota_sisa = kuota_sisa - 30 WHERE id_sesi = 1;")
    
    cur_inflight.execute("SELECT kuota_sisa FROM uji_crash_kuota WHERE id_sesi = 1;")
    kuota_dirty = cur_inflight.fetchone()[0]
    cur_inflight.execute("SELECT pg_current_wal_lsn();")
    lsn_t4 = cur_inflight.fetchone()[0]
    print(f"[T4 - In-Flight] txid={txid_t4}, Kuota dimodifikasi jadi {kuota_dirty} (belum commit!), LSN={lsn_t4}")

    # 3. CRASH: Kirim SIGKILL ke engine database
    print(f"[CRASH] Mengirim sinyal SIGKILL ke engine PostgreSQL container...")
    run_cmd("docker compose kill -s KILL db")
    time.sleep(1)
    
    try:
        conn_inflight.close()
    except Exception:
        pass
    
    # 4. RECOVERY: Nyalakan kembali container
    print("[RECOVERY] Memulai ulang database via docker compose up -d db...")
    run_cmd("docker compose up -d db")
    wait_for_db()
    print("[RECOVERY] Database berhasil hidup kembali dan siap melayani koneksi!")

    # 5. Tangkap log engine recovery
    logs = run_cmd("docker logs danusgo-db --tail 60")
    recovery_lines = [l for l in logs.splitlines() if any(k in l for k in ["recovery in progress", "redo starts at", "redo done at", "ready to accept connections", "checkpoint complete", "checkpoint starting"])]
    print("\n--- Log Engine Recovery (PostgreSQL) ---")
    for l in recovery_lines:
        print("  " + l)

    # 6. Verifikasi State Konsistensi Data
    with psycopg.connect(**DB_PARAMS) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT kuota_awal, kuota_sisa, pg_current_wal_lsn() FROM uji_crash_kuota WHERE id_sesi = 1;")
            row = cur.fetchone()
            kuota_awal_final, kuota_sisa_final, lsn_post_recovery = row[0], row[1], row[2]

    print("\n--- Hasil Verifikasi Data Post-Recovery ---")
    print(f"  Kuota Awal              : {kuota_awal_final}")
    print(f"  Kuota Aktual Pasca-Crash: {kuota_sisa_final}")
    print(f"  Status Transaksi T3 (Committed)   : {'PERSISTEN (Durability Terbukti)' if kuota_sisa_final == 80 else 'GAGAL'}")
    print(f"  Status Transaksi T4 (Uncommitted) : {'TERBATALKAN (Atomicity/Undo Terbukti)' if kuota_sisa_final == 80 else 'DIRTY DATA BOCOR'}")
    print(f"  LSN Pasca Pemulihan               : {lsn_post_recovery}")

    # 7. Ekstraksi WAL Dump
    print("\n--- Ekstraksi Record WAL via pg_waldump ---")
    wal_dump = get_waldump_records(limit=60)
    print(wal_dump[:1500] if len(wal_dump) > 1500 else wal_dump)

    result_s2 = {
        "scenario": "Scenario 2: Crash Dengan Checkpoint Eksplisit",
        "txid_t3_committed": txid_t3,
        "lsn_t3": str(lsn_t3),
        "lsn_checkpoint": str(lsn_checkpoint),
        "txid_t4_uncommitted": txid_t4,
        "lsn_t4": str(lsn_t4),
        "kuota_dirty_pre_crash": kuota_dirty,
        "kuota_final_post_recovery": kuota_sisa_final,
        "durability_verified": kuota_sisa_final == 80,
        "atomicity_verified": kuota_sisa_final == 80,
        "lsn_post_recovery": str(lsn_post_recovery),
        "recovery_logs": recovery_lines,
        "wal_sample": wal_dump
    }
    return result_s2

if __name__ == "__main__":
    print("=== MEMULAI SIMULASI CRASH DAN LOGGING WAL (BAB 4) ===")
    res_s1 = run_scenario_1()
    res_s2 = run_scenario_2()
    
    full_results = {
        "scenario_1_without_checkpoint": res_s1,
        "scenario_2_with_checkpoint": res_s2
    }
    
    out_file = "reports/benchmark/crash_simulation_results.json"
    with open(out_file, "w") as f:
        json.dump(full_results, f, indent=2)
    print(f"\n[OK] Seluruh data bukti empiris crash tersimpan di {out_file}")
