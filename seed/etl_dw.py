#!/usr/bin/env python3
"""
DanusGo - Pipeline ETL (Extract, Transform, Load) Operasional ke Data Warehouse (Bab 13)
Mengisi:
1. dw.dim_spot
2. dw.dim_organisasi
3. dw.dim_produk
4. dw.fakta_penjualan_danus (Grain: per item pesanan COMPLETED)
5. REFRESH MATERIALIZED VIEW dw.mv_omzet_bulanan
"""

import time
import psycopg

DB_PARAMS = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "danusgo",
    "password": "danusgo_dev",
    "dbname": "danusgo"
}

def run_etl():
    print("="*70)
    print("MEMULAI PIPELINE ETL OPERASIONAL -> DATA WAREHOUSE (DW)")
    print("="*70)
    t0 = time.time()
    
    with psycopg.connect(**DB_PARAMS) as conn:
        cur = conn.cursor()
        
        # -------------------------------------------------------------
        # 1. Dimensi Spot
        # -------------------------------------------------------------
        print("\n[ETL 1/5] Memuat Dimensi Spot (dw.dim_spot)...")
        t_step = time.time()
        cur.execute("""
            INSERT INTO dw.dim_spot (id_spot, spot, wilayah_fakultas, universitas)
            SELECT s.id_spot, s.nama_spot, f.nama_fakultas, 'Universitas'
            FROM spot_lokasi s
            JOIN fakultas f ON s.id_fakultas = f.id_fakultas
            ON CONFLICT (id_spot) DO UPDATE 
            SET spot = EXCLUDED.spot, 
                wilayah_fakultas = EXCLUDED.wilayah_fakultas;
        """)
        cur.execute("SELECT count(*) FROM dw.dim_spot;")
        cnt_spot = cur.fetchone()[0]
        print(f"  -> Selesai dalam {time.time() - t_step:.3f} s. Total baris dw.dim_spot: {cnt_spot}")
        
        # -------------------------------------------------------------
        # 2. Dimensi Organisasi
        # -------------------------------------------------------------
        print("\n[ETL 2/5] Memuat Dimensi Organisasi (dw.dim_organisasi)...")
        t_step = time.time()
        cur.execute("""
            INSERT INTO dw.dim_organisasi (id_organisasi, organisasi, fakultas_asal)
            SELECT o.id_organisasi, o.nama_organisasi, f.nama_fakultas
            FROM organisasi_danus o
            JOIN fakultas f ON o.id_fakultas_induk = f.id_fakultas
            ON CONFLICT (id_organisasi) DO UPDATE 
            SET organisasi = EXCLUDED.organisasi, 
                fakultas_asal = EXCLUDED.fakultas_asal;
        """)
        cur.execute("SELECT count(*) FROM dw.dim_organisasi;")
        cnt_org = cur.fetchone()[0]
        print(f"  -> Selesai dalam {time.time() - t_step:.3f} s. Total baris dw.dim_organisasi: {cnt_org}")

        # -------------------------------------------------------------
        # 3. Dimensi Produk & Varian
        # -------------------------------------------------------------
        print("\n[ETL 3/5] Memuat Dimensi Produk (dw.dim_produk)...")
        t_step = time.time()
        cur.execute("""
            INSERT INTO dw.dim_produk (id_produk, id_varian, varian, produk, kategori)
            SELECT DISTINCT 
                p.id_produk, 
                v.id_varian, 
                v.nama_varian, 
                p.nama_produk, 
                p.kategori
            FROM produk_danus p
            LEFT JOIN produk_varian v ON p.id_produk = v.id_produk
            ON CONFLICT (id_produk, id_varian) DO UPDATE
            SET varian = EXCLUDED.varian,
                produk = EXCLUDED.produk,
                kategori = EXCLUDED.kategori;
        """)
        cur.execute("SELECT count(*) FROM dw.dim_produk;")
        cnt_prod = cur.fetchone()[0]
        print(f"  -> Selesai dalam {time.time() - t_step:.3f} s. Total baris dw.dim_produk: {cnt_prod}")

        # -------------------------------------------------------------
        # 4. Tabel Fakta Penjualan Danus (Grain: Item Pesanan COMPLETED)
        # -------------------------------------------------------------
        print("\n[ETL 4/5] Transform & Load Fakta Penjualan (dw.fakta_penjualan_danus)...")
        t_step = time.time()
        cur.execute("""
            INSERT INTO dw.fakta_penjualan_danus (
                id_detail,
                id_waktu,
                id_jam,
                id_spot_dw,
                id_organisasi_dw,
                id_produk_dw,
                kuantitas_terjual,
                total_omzet,
                total_modal,
                laba_bersih,
                jumlah_transaksi
            )
            SELECT 
                d.id_detail,
                to_char(p.waktu_pesan AT TIME ZONE 'Asia/Jakarta', 'YYYYMMDD')::int AS id_waktu,
                (EXTRACT(HOUR FROM p.waktu_pesan AT TIME ZONE 'Asia/Jakarta')::int * 100 + 
                 CASE WHEN EXTRACT(MINUTE FROM p.waktu_pesan AT TIME ZONE 'Asia/Jakarta') < 30 THEN 0 ELSE 30 END) AS id_jam,
                ds.id_spot_dw,
                do2.id_organisasi_dw,
                dp.id_produk_dw,
                d.jumlah_item AS kuantitas_terjual,
                (d.jumlah_item * d.harga_satuan) AS total_omzet,
                (d.jumlah_item * d.harga_modal_satuan) AS total_modal,
                ((d.jumlah_item * d.harga_satuan) - (d.jumlah_item * d.harga_modal_satuan)) AS laba_bersih,
                1 AS jumlah_transaksi
            FROM pesanan_danus p
            JOIN detail_pesanan d ON p.id_pesanan = d.id_pesanan AND p.waktu_pesan = d.waktu_pesan
            JOIN sesi_jualan sj ON p.id_sesi = sj.id_sesi
            JOIN sesi_produk sp ON d.id_sesi_produk = sp.id_sesi_produk
            JOIN dw.dim_spot ds ON sj.id_spot = ds.id_spot
            JOIN dw.dim_organisasi do2 ON sj.id_organisasi = do2.id_organisasi
            JOIN dw.dim_produk dp ON sp.id_produk = dp.id_produk 
                                 AND (d.id_varian = dp.id_varian OR (d.id_varian IS NULL AND dp.id_varian IS NULL))
            WHERE p.status_pesanan = 'COMPLETED'
            ON CONFLICT (id_detail) DO NOTHING;
        """)
        conn.commit()
        
        cur.execute("SELECT count(*), SUM(total_omzet), SUM(laba_bersih) FROM dw.fakta_penjualan_danus;")
        cnt_fakta, sum_omzet, sum_laba = cur.fetchone()
        print(f"  -> Selesai dalam {time.time() - t_step:.3f} s.")
        print(f"  -> Total Baris Fakta : {cnt_fakta:,}")
        print(f"  -> Total Omzet DW    : Rp {sum_omzet:,.2f}")
        print(f"  -> Total Laba Bersih : Rp {sum_laba:,.2f}")

        # -------------------------------------------------------------
        # 5. Refresh Materialized View
        # -------------------------------------------------------------
        print("\n[ETL 5/5] Refresh Materialized View (dw.mv_omzet_bulanan)...")
        t_step = time.time()
        cur.execute("REFRESH MATERIALIZED VIEW dw.mv_omzet_bulanan;")
        conn.commit()
        cur.execute("SELECT count(*) FROM dw.mv_omzet_bulanan;")
        cnt_mv = cur.fetchone()[0]
        print(f"  -> Selesai dalam {time.time() - t_step:.3f} s. Total baris MV: {cnt_mv}")

    total_duration = time.time() - t0
    print("\n" + "="*70)
    print(f"[SUKSES] Pipeline ETL selesai sempurna dalam total durasi: {total_duration:.3f} s")
    print("="*70)

if __name__ == "__main__":
    run_etl()
