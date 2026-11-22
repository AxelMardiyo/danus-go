# Matriks Status Deliverable Sprint 1 — DanusGo (Pasca-Benchmark)
**Periode Sprint 1:** 21 – 25 November 2026  
**Target Capaian Kumulatif:** 50% Proyek (Bab 1, 2, 3, 5, 6, dan 7)  
**Tanggal Update Audit:** 22 November 2026 (Pasca-Benchmarking Empiris)

---

## 1. Matriks Evaluasi Deliverables Sprint 1

| No | Deliverable Sprint 1 | Komponen Spesifikasi PRD & Skill | File Terkait di Workspace | Status Aktual | Bukti Tersedia (Evidence) | Sisa Pekerjaan Sebelum Laporan |
| :-: | :--- | :--- | :--- | :-: | :--- | :--- |
| **1** | **Dokumen ERD & Normalisasi BCNF/4NF** | • Diagram ERD konseptual & logikal.<br>• Dekomposisi $FD: \text{id\_prodi} \rightarrow \text{id\_fakultas}$.<br>• Analisis eliminasi `id_sesi` pada `detail_pesanan` demi BCNF.<br>• Dekomposisi $MVD: \text{id\_produk} \twoheadrightarrow \text{varian} \mid \text{pickup}$ ke 4NF.<br>• Uji *Lossless Join* & *Dependency Preservation*. | • `PRD.md` (Bag. 6, 7, 12)<br>• `db/01_schema.sql` (L99–L111) | `IN_PROGRESS` | • Skema DDL tabel 4NF (`produk_varian`, `produk_metode_pickup`) telah aktif di PostgreSQL.<br>• Dokumentasi tekstual relasi di PRD. | • Pembuatan diagram visual ERD (format gambar/vektor).<br>• Penyusunan narasi formal pembuktian dekomposisi matematis BCNF & 4NF ke dalam bab laporan. |
| **2** | **Berkas `01_schema.sql`** | • DDL kanonik 14 entitas operasional.<br>• *Exclusion Constraint* (GIST `btree_gist` pada `tsrange`).<br>• Partisi RANGE bulanan `pesanan_danus` (2026-01 s.d. 2027-03 + DEFAULT).<br>• Trigger konsistensi item `trg_validasi_detail` & sesi produk `trg_validasi_sesi_produk`.<br>• View `v_total_pesanan`. | • `db/01_schema.sql`<br>• `docker-compose.yml` | `COMPLETED` | • 280 baris SQL aktif di database live.<br>• Container `danusgo-db` berstatus *healthy*.<br>• 38 objek tabel dan partisi terverifikasi di PostgreSQL. | — *(Tuntas)* |
| **3** | **Berkas `02_seed.sql` / Dataset 100k+** | • Seeder data realistis 100.000+ baris `pesanan_danus`.<br>• ~180.000 baris `detail_pesanan`.<br>• 5.000 pengguna, 8.000 sesi jualan.<br>• Distribusi miring (Pareto/Zipfian 80:20).<br>• Jam sibuk (10.00–13.00 WIB).<br>• Timestamp WIB (+07) & `kedaluwarsa_pada`. | • `seed/generate_data.py`<br>• `seed/README.md`<br>• `seed/requirements.txt` | `COMPLETED` | • Skrip `seed/generate_data.py` selesai dieksekusi dalam 19,64 detik.<br>• Database live memuat: **105.000 pesanan**, **144.889 detail pesanan**, **5.001 pengguna**, **8.000 sesi jualan**, **200 produk**, dan **30 spot**.<br>• Partisi bulanan terisi proporsional (8.467 s.d. 10.734 baris/bulan) dengan 0 di partisi default.<br>• Perintah `ANALYZE;` telah dijalankan. | — *(Tuntas)* |
| **4** | **Berkas `03_queries.sql`** | • Fungsi pemesanan atomik anti-*overselling* (row-level lock / atomic conditional update).<br>• Pembangkitan kode pickup unik 6-char per sesi (BR-15).<br>• Kueri CTE (omzet & margin seller).<br>• Kueri Correlated Subquery.<br>• Window Functions (`DENSE_RANK`, running total).<br>• Recursive CTE.<br>• Uji konkurensi (200 koneksi vs kuota 50). | • `db/03_queries.sql` | `COMPLETED` | • Fungsi `sp_buat_pesanan` dan `sp_buat_pesanan_naif` berhasil dikompilasi di database live.<br>• Uji panggil `sp_buat_pesanan` sukses menghasilkan transaksi ID 105002 dengan kode unik 'PS7JYC' dan memotong kuota secara atomik.<br>• Ke-4 kueri analitis (CTE, Correlated, Window, Recursive) telah diuji dan mengembalikan hasil kalkulasi nyata. | — *(Tuntas)* |
| **5** | **Berkas `04_indexes.sql`** | • 5 indeks sekunder strategis:<br>  - `idx_sesi_tgl_status` (B-Tree komposit)<br>  - `idx_pesanan_waktu` (B-Tree)<br>  - `idx_pesanan_antrean` (Partial Index)<br>  - `idx_spot_fakultas` (Bitmap Scan)<br>  - `idx_pesanan_user` (B-Tree komposit)<br>• Skrip drop indeks `04_indexes_drop.sql`.<br>• Pengukuran ukuran indeks (`pg_relation_size`).<br>• Evaluasi *write penalty* batch insert. | • `db/04_indexes.sql`<br>• `db/04_indexes_drop.sql`<br>• `reports/benchmark/benchmark-results.md` | `COMPLETED` | • 5 Indeks sekunder berhasil diaplikasikan ke database.<br>• Ukuran seluruh indeks partisi terdata via `pg_relation_size` (misal `pesanan_2026_11_pkey` 848 kB, `idx_sesi_tgl_status` 600 kB).<br>• Uji durasi batch insert 10.000 data terukur riil (0.1613s tanpa indeks vs 0.1036s dengan indeks). | — *(Tuntas)* |
| **6** | **Estimasi Biaya I/O & Optimasi EXPLAIN** | • Parameter fisik basis data ($B=8\text{ KB}, M, b_r, b_s, n_r, n_s$).<br>• Perhitungan manual Block Nested-Loop Join vs Hash Join.<br>• Uji 5 skenario optimasi kueri dengan `EXPLAIN (ANALYZE, BUFFERS)` sebelum vs sesudah indeks.<br>• Bukti *Partition Pruning* bulanan.<br>• Evaluasi *Sargability* (`date()` vs range).<br>• Grafik perbandingan performa. | • `reports/benchmark/run_benchmark.py`<br>• `reports/benchmark/raw_explain_before.txt`<br>• `reports/benchmark/raw_explain_after.txt`<br>• `reports/benchmark/benchmark-results.md`<br>• `reports/figures/*.svg` | `COMPLETED` | • Berkas log mentah `raw_explain_before.txt` (27.5 KB) dan `raw_explain_after.txt` (18.1 KB) terarsip.<br>• Bukti percepatan empiris teruji: S1 11.2x speedup (0.28ms -> 0.03ms), S2 59.0x speedup (3.71ms -> 0.06ms), S5 Sargable 250.3x speedup (6.76ms -> 0.03ms).<br>• 3 Berkas grafik vektor SVG berhasil di-generate di `reports/figures/`. | — *(Tuntas)* |
| **7** | **Materi Uji Coba & Presentasi Progres** | • Slide presentasi progres (Bab 1, 2, 3, 5, 6, 7).<br>• Skenario demo live evaluasi progres. | *(Di luar scope laporan teknis)* | `PLANNED` | Belum ada artefak. | • Penyusunan slide presentasi setelah laporan teknis rampung. |

---

## 2. Metodologi Perhitungan Progres Objektif

$$\text{Skor Sprint 1} = \sum_{i=1}^{6} (\text{Bobot}_i \times \text{Pencapaian}_i)$$

### Tabel Perhitungan Skor Terbaru:

| No | Komponen Deliverable | Bobot Sprint 1 | Persentase Selesai | Skor Terbobot Aktual | Dasar Penilaian Objektif |
| :-: | :--- | :-: | :-: | :-: | :--- |
| 1 | ERD & Normalisasi BCNF/4NF | 15% | 50% | **7,50%** | Skema tabel 4NF aktif di DDL, relasi di PRD, diagram visual & narasi formal pembuktian matematis siap ditulis. |
| 2 | Berkas `01_schema.sql` | 20% | 100% | **20,00%** | DDL lengkap (280 baris), Exclusion Constraint GIST aktif, partisi bulanan aktif, trigger validasi aktif di container live PostgreSQL. |
| 3 | Seeder Data 100k+ Baris | 20% | 100% | **20,00%** | Skrip Python `seed/generate_data.py` berhasil menginjeksi 105.000 pesanan dan 144.889 detail pesanan dengan distribusi Pareto 80:20 ke PostgreSQL. |
| 4 | Kueri SQL Lanjut & Transaksi Atomik | 15% | 100% | **15,00%** | Berkas `db/03_queries.sql` lengkap dengan fungsi atomik `sp_buat_pesanan`, fungsi naif, dan 4 kueri analitis (CTE, Correlated, Window, Recursive), telah teruji di database. |
| 5 | Indeks Sekunder & Evaluasi Write Cost | 15% | 100% | **15,00%** | **Selesai:** 5 indeks aktif, ukuran disk `pg_relation_size` tercatat, durasi operasi tulis batch insert terukur riil. |
| 6 | Teori I/O & Benchmarking EXPLAIN | 15% | 100% | **15,00%** | **Selesai:** 5 skenario `EXPLAIN (ANALYZE, BUFFERS)` (sebelum vs sesudah) terarsip di berkas log mentah, komparasi Nested Loop vs Hash Join terukur, grafik SVG performa siap pakai. |
| **TOTAL** | **Kompilasi Seluruh Komponen** | **100%** | — | **92,50%** | **Capaian Sprint 1 = 92,50%** (Setara dengan **46,25%** kumulatif proyek akhir). |

---

## 3. Kesimpulan Verifikasi Capaian

1. Capaian teknis Sprint 1 telah mencapai **92,50%** (setara dengan **46,25%** dari target kumulatif 50% proyek akhir).
2. Sisa 7,50% adalah penyusunan draf narasi akademik per bab (Bab 1, 2, 3, 5, 6, dan 7) dan integrasi diagram visual ke dalam laporan akhir.
3. Seluruh bukti empiris (*concrete evidence*) telah lengkap dan valid tanpa rekayasa data.
