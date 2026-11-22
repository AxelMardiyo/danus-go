# Status Evidence & Action Plan Penyusunan Laporan — DanusGo
**Sistem:** DanusGo (Campus Danusan & Food Tracking Hub)  
**Mata Kuliah:** Basis Data Lanjut (Semester Gasal 2026/2027)  
**Dokumen:** Evidence Status & Final Action Plan — Sprint 1  
**Tanggal Update:** 22 November 2026 (Pasca-Benchmarking Empiris)

---

## 1. Status Pemenuhan Evidence

| No | Kebutuhan Evidence Akademis | Status Terkini | Berkas Bukti Terverifikasi |
| :-: | :--- | :---: | :--- |
| **1** | Dataset Uji 100k+ Baris & Distribusi Miring | **TERPENUHI** | • 105.000 pesanan dan 144.889 detail pesanan terinjeksi via `seed/generate_data.py`.<br>• Tersebar pada 11 partisi bulanan (Jan–Nov 2026) dengan sebaran waktu WIB (+07).<br>• Distribusi Pareto 80:20 terbukti pada kueri agregasi. |
| **2** | Fungsi Pemesanan Atomik Anti-Overselling | **TERPENUHI** | • Fungsi `sp_buat_pesanan` aktif di database live dengan conditional UPDATE & row lock.<br>• Uji transaksi menghasilkan ID 105002 dengan kode unik 'PS7JYC' dan kuota terpotong akurat.<br>• Log mutasi `log_kuota` dan `detail_pesanan` tercatat otomatis. |
| **3** | Implementasi 4 Kueri SQL Lanjut | **TERPENUHI** | • CTE finansial seller, Correlated Subquery buyer prioritas, Window Function `DENSE_RANK`, dan Recursive CTE hierarki organisasi teruji di database. |
| **4** | Pengukuran Ukuran Disk Indeks (`pg_relation_size`) | **TERPENUHI** | • Terdata ukuran fisik seluruh indeks partisi di `reports/benchmark/benchmark-results.md` (misal: `pesanan_2026_11_pkey` 848 kB, `sesi_jualan_id_spot_tsrange_excl` 600 kB). |
| **5** | Pengukuran Penalti Operasi Tulis (*Write Penalty*) | **TERPENUHI** | • Batch insert 10.000 data: 0.1613 detik tanpa indeks vs 0.1036 detik dengan indeks terdata di `reports/benchmark/benchmark-results.md`. |
| **6** | Bukti Mentah *Execution Plan* `EXPLAIN (ANALYZE, BUFFERS)` | **TERPENUHI** | • Log mentah sebelum indeks: `reports/benchmark/raw_explain_before.txt` (27.5 KB).<br>• Log mentah sesudah indeks: `reports/benchmark/raw_explain_after.txt` (18.1 KB).<br>• Bukti percepatan: S1 11.2x, S2 59.0x, S5 250.3x speedup. |
| **7** | Komparasi Algoritma Join (Bab 6) | **TERPENUHI** | • Hash Join (cost 3.879, 16.21 ms, 1.736 buffer hits) vs Nested Loop Join (cost 7.026, 16.31 ms, 29.307 buffer hits) terdata di log. |
| **8** | Visualisasi Grafik Hasil Benchmark | **TERPENUHI** | • `reports/figures/chart_execution_time.svg`<br>• `reports/figures/chart_buffer_io.svg`<br>• `reports/figures/chart_sargability.svg` |
| **9** | Diagram Visual ERD & Narasi Laporan per Bab | *IN_PROGRESS* | • Tersisa penyusunan draf bab formal (Bab 1, 2, 3, 5, 6, 7) di `reports/draft/` dan ekspor dokumen laporan akhir. |

---

## 2. Langkah Kerja Terakhir Menuju Laporan Akhir

Dengan tersedianya seluruh bukti empiris, penyusunan laporan progres teknis dapat langsung dieksekusi:

1. **Penyusunan Draf Bab Akademik di `reports/draft/`:**
   - `bab-1.md`: ERD, kamus data, dan pembuktian matematis normalisasi BCNF & 4NF (eliminasi MVD varian vs pickup).
   - `bab-2.md`: Analisis konkurensi race condition, kode fungsi pemesanan atomik, dan 4 kueri SQL lanjut analitis.
   - `bab-3.md`: Desain fisik PostgreSQL, Exclusion Constraint GIST, strategi partisi bulanan, dan karakteristik dataset 105k+.
   - `bab-5.md`: Desain B-Tree/Partial/Bitmap Index, tabel ukuran memori disk, dan write penalty.
   - `bab-6.md`: Parameter fisik blok, rumus estimasi transfer I/O manual vs planner cost PostgreSQL, dan komparasi Nested Loop vs Hash Join.
   - `bab-7.md`: Metodologi pengujian, 5 skenario optimasi kueri (dengan angka riil dari benchmark), dan evaluasi sargability.
2. **Kompilasi ke Dokumen Akhir (`.docx` / `.pdf`):**
   - Mengintegrasikan seluruh tabel metrik riil dan grafik ke dalam dokumen laporan akhir.
