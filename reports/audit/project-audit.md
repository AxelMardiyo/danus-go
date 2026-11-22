# DanusGo Project Audit — Sprint 1
**Mata Kuliah:** Basis Data Lanjut (Semester Gasal 2026/2027)  
**Sistem:** DanusGo (Campus Danusan & Food Tracking Hub)  
**Periode Sprint 1:** 21 – 25 November 2026  
**Target Capaian Kumulatif:** 50% (Cakupan: Bab 1, 2, 3, 5, 6, dan 7)  
**Tanggal Audit:** 22 November 2026  
**Status Evaluasi:** AUDIT TAHAP AWAL (Pra-Penyusunan Laporan)

---

## 1. Ringkasan Eksekutif Audit

Audit ini dilakukan secara independen terhadap repositori DanusGo guna memvalidasi kesiapan artefak kode, skema basis data, data uji, dan bukti empiris terhadap spesifikasi **Sprint 1: Fondasi Skema, Kueri Transaksi & Optimasi EXPLAIN**.

Berdasarkan pemeriksaan fisik terhadap repositori dan container runtime PostgreSQL 16:
1. **Fondasi DDL (`01_schema.sql`):** Telah diimplementasikan dengan sangat baik dan telah aktif di container PostgreSQL. Fitur *Exclusion Constraint* (GIST) berbasis rentang waktu (`tsrange`), partisi bulanan, dan trigger konsistensi telah terpasang.
2. **Data Seeder (`02_seed.sql`):** Belum memenuhi target. Saat ini baru tersedia data master minimal (~50 baris di `02_seed_master.sql`). Generator data 100.000+ baris dengan distribusi miring (Pareto/Zipfian) di folder `seed/` **belum dibuat dan belum dieksekusi**.
3. **Kueri Transaksi & SQL Lanjut (`03_queries.sql`):** Masih berupa berkas *stub* kosong (hanya memuat 3 baris komentar). Fungsi transaksi atomik anti-*overselling* dan kueri analitis (CTE, Correlated Subquery, Window Function, Recursive CTE) belum diimplementasikan di repositori.
4. **Indeks Sekunder (`04_indexes.sql`):** Berkas DDL indeks telah selesai ditulis secara lengkap, namun belum diaplikasikan ke database (sengaja menunggu pengukuran kondisi *baseline* tanpa indeks). Pengukuran ukuran indeks dan *write penalty* belum dapat dilakukan karena dataset 100k+ belum diinjeksi.
5. **Bukti Optimasi EXPLAIN (Bab 6 & 7):** Formula teoretis telah terdefinisi di `PRD.md`, namun **belum ada satu pun log eksekusi riil `EXPLAIN (ANALYZE, BUFFERS)`** maupun grafik performa yang dihasilkan dari mesin database.

> [!CAUTION]
> **Kesimpulan Capaian Progres:** Target kumulatif 50% **BELUM TERPENUHI**. Berdasarkan matriks evaluasi berbobot, progres aktual baru mencapai **37,5% dari Sprint 1** (setara dengan **~18,75% kumulatif proyek**). Laporan teknis final belum dapat disusun sebelum data uji 100k+, kueri atomik, dan bukti empiris EXPLAIN dieksekusi secara nyata pada database.

---

## 2. Analisis Struktur Repositori

Pemeriksaan direktori fisik repositori DanusGo menghasilkan inventarisasi sebagai berikut:

```
danusgo/
├── .env                           [ADA] Konfigurasi environment lokal (DB_USER, DB_PASSWORD, DB_PORT)
├── .env.example                   [ADA] Templat konfigurasi environment
├── .gitignore                     [ADA] Pengabaian file non-repo
├── docker-compose.yml             [ADA] Orkestrasi PostgreSQL 16 + pgAdmin (profile: tools)
├── Makefile                       [ADA] Pintasan perintah up, down, reset, psql, indexes, crash, wal
├── PRD.md                         [ADA] Product Requirement Document kanonik (36.7 KB)
├── README.md                      [ADA] Panduan proyek & petunjuk cepat
├── db/                            [DIREKTORI SQL UTAMA]
│   ├── 01_schema.sql              [ADA - LENGKAP] DDL skema operasional, partisi, trigger, view
│   ├── 02_seed_master.sql         [ADA - MINIMAL] Data master dasar (fakultas, prodi, spot, admin)
│   ├── 03_queries.sql             [STUB - KOSONG] Hanya memuat komentar 3 baris
│   ├── 04_indexes.sql             [ADA - LENGKAP] DDL 5 indeks sekunder (belum diterapkan di DB)
│   ├── 04_indexes_drop.sql        [ADA - LENGKAP] Skrip pelepasan indeks untuk uji baseline
│   ├── 05_partition.sql           [STUB] Skrip eksperimen partisi Bab 9 (Sprint 2)
│   └── 06_dw_schema.sql           [ADA - LENGKAP] Skema Data Warehouse dw.* (Sprint 2)
├── seed/                          [GENERATOR DATA]
│   ├── README.md                  [ADA] Instruksi kebutuhan seeder 100k+
│   └── requirements.txt           [ADA] Kebutuhan dependensi: faker>=24, psycopg[binary]>=3.1
│   └── (generate_data.py)         [TIDAK ADA] Skrip generator belum dibuat
├── backend/                       [BACKEND SERVICE]
│   └── .gitkeep                   [KOSONG] Dijadwalkan fase final
├── frontend/                      [FRONTEND SERVICE]
│   └── .gitkeep                   [KOSONG] Dijadwalkan fase final
├── docs/                          [DOKUMENTASI & EVIDENCE]
│   └── .gitkeep                   [KOSONG] Belum ada dokumen ERD visual, log EXPLAIN, atau grafik
└── reports/                       [DOKUMEN EVALUASI & AUDIT]
    └── audit/                     [DIREKTORI BARU] Tempat berkas audit dan matriks bukti
```

---

## 3. Status Runtime Basis Data (PostgreSQL 16)

Container basis data berjalan melalui Docker Compose:
- **Nama Container:** `danusgo-db`
- **Image:** `postgres:16`
- **Status Container:** `Up (healthy)`
- **Port Binding:** `0.0.0.0:5432->5432/tcp`
- **Konfigurasi Resource Terkunci:**
  - `timezone = Asia/Jakarta`
  - `shared_buffers = 256MB`
  - `effective_cache_size = 1GB`
  - `work_mem = 16MB`
  - `random_page_cost = 1.1`
  - `max_parallel_workers_per_gather = 2`
  - `track_io_timing = on`
  - `log_checkpoints = on`

### Hasil Inventarisasi Baris Aktual Database (Live Query Terverifikasi):

| Nama Tabel / Partisi | Jumlah Baris Aktual | Keterangan Verifikasi |
| :--- | :---: | :--- |
| `fakultas` | 9 | Data master dasar dari `02_seed_master.sql` |
| `prodi` | 11 | Data master dasar dari `02_seed_master.sql` |
| `spot_lokasi` | 30 | 2 master + 28 area kampus dari seeder |
| `pengguna` | 5.001 | 1 admin dev + 150 sellers + 4.850 buyers |
| `organisasi_danus` | 40 | Organisasi danus kampus terdistribusi |
| `seller` | 160 | Relasi mahasiswa peran seller ke organisasi |
| `pengajuan_seller` | 0 | Bersih (pendaftaran langsung via seeder) |
| `produk_danus` | 200 | Makanan berat, snack, minuman, merchandise |
| `produk_varian` | 445 | 1–4 varian per produk (terpisah 4NF) |
| `produk_metode_pickup` | 292 | Ambil di stan & diantar (terpisah 4NF) |
| `sesi_jualan` | 8.000 | Jan–Nov 2026, bebas bentrok jadwal spot |
| `sesi_produk` | 24.083 | Pemetaan kuota produk per sesi |
| `pesanan_danus` (total) | 105.000 | **Memenuhi Target** (tersebar di 11 partisi bulanan) |
| `detail_pesanan` | 144.889 | **Memenuhi Target** (~1,38 item per pesanan) |
| `log_kuota` | 144.889 | Audit jejak mutasi kuota pesanan |

---

## 4. Evaluasi Keselarasan Implementasi vs Spesifikasi Sprint 1

### Deliverable 1: Dokumen ERD dan Normalisasi BCNF & 4NF
- **Target:** ERD konseptual & logikal, pembuktian dekomposisi BCNF, pembuktian 4NF eliminasi MVD varian produk vs metode pickup, uji lossless join.
- **Kondisi Aktual:** Konsep dan struktur tabel terdokumentasi di `PRD.md` Bagian 6, 7, dan 12. Tabel dekomposisi 4NF (`produk_varian`, `produk_metode_pickup`) telah ada di `01_schema.sql`. Namun, **dokumen formal dan diagram visual ERD mandiri belum ada** di `docs/`.
- **Status:** `IN_PROGRESS`.

### Deliverable 2: Berkas `01_schema.sql`
- **Target:** DDL kanonik, integritas relasi, *Exclusion Constraint* sesi bentrok (`tsrange` GIST), trigger konsistensi item dan sesi.
- **Kondisi Aktual:** Telah lengkap (280 baris), valid, dan sukses dimuat di PostgreSQL. Menolak sesi bentrok di spot yang sama dengan error `23P01`. Menegakkan integritas jendela PRE_ORDER vs READY_STOCK melalui `trg_validasi_sesi_produk`, dan konsistensi item sesi melalui `trg_validasi_detail`.
- **Status:** `COMPLETED`.

### Deliverable 3: Berkas `02_seed.sql` (Dataset 100k+ Baris)
- **Target:** Seeder realistis dengan $\ge 100.000$ baris pesanan, distribusi miring (Pareto/Zipfian), 5.000 pengguna, 8.000 sesi jualan, sebaran waktu WIB (+07).
- **Kondisi Aktual:** Baru ada `02_seed_master.sql` (hanya data master kampus ~50 baris). Skrip generator data 100k belum ada. Database masih kosong dari data transaksi.
- **Status:** `IN_PROGRESS`.

### Deliverable 4: Berkas `03_queries.sql`
- **Target:** Kueri transaksi atomik anti-*overselling* (locking/conditional update), CTE finansial seller, correlated subquery, window functions, recursive CTE, dan hasil uji 200 koneksi serentak pada kuota 50.
- **Kondisi Aktual:** Berkas `db/03_queries.sql` hanya berisi 3 baris komentar (*stub*). Fungsi atomik dan kueri analitis belum dibuat. Uji konkurensi belum dilakukan.
- **Status:** `PLANNED`.

### Deliverable 5: Berkas `04_indexes.sql`
- **Target:** Indeks B-Tree komposit, partial index antrean aktif, low-cardinality index (Bitmap Scan), evaluasi ukuran disk (`pg_relation_size`), dan evaluasi *write penalty*.
- **Kondisi Aktual:** Berkas SQL dan drop script telah selesai dan sesuai spesifikasi. Namun, indeks belum diaplikasikan ke database live dan belum diukur karena menunggu data transaksi diinjeksi terlebih dahulu.
- **Status:** `IN_PROGRESS`.

### Deliverable 6: Estimasi Biaya I/O Teoretis & Optimasi Empiris EXPLAIN
- **Target:** Estimasi transfer blok manual (Block Nested Loop Join vs Hash Join), komparasi rencana eksekusi 5 skenario dengan `EXPLAIN (ANALYZE, BUFFERS)` sebelum vs sesudah indeks, grafik performa.
- **Kondisi Aktual:** Formula dan rancangan skenario ada di PRD, tetapi tidak ada satupun hasil eksekusi riil, log planner, maupun grafik di direktori proyek.
- **Status:** `PLANNED`.

### Deliverable 7: Materi Presentasi Progres
- **Target:** Slide presentasi progres (Bab 1, 2, 3, 5, 6, 7) dan skenario uji coba evaluasi.
- **Kondisi Aktual:** Belum dibuat. (Sesuai arahan, item ini berada di luar cakupan teknis audit laporan).
- **Status:** `PLANNED`.

---

## 5. Ringkasan Temuan Kritis

1. **Dependensi Rantai Utama (Blocker Teknis):**
   Ketiadaan generator dataset 100k+ baris menjadi penghambat utama bagi seluruh deliverable berikutnya. Tanpa dataset 100k+:
   - Pengukuran ukuran indeks (`pg_relation_size`) tidak representatif (hanya mengukur tabel kosong).
   - Pengukuran *write penalty* tidak dapat diuji secara empiris.
   - Perhitungan biaya I/O (Bab 6) tidak dapat dikomparasikan dengan *planner cost* PostgreSQL.
   - Seluruh 5 skenario optimasi `EXPLAIN (ANALYZE, BUFFERS)` (Bab 7) akan menghasilkan pembacaan 0 buffer dan *sequential scan* trivial karena optimizer selalu memilih memindai tabel kecil tanpa melibatkan indeks.
2. **Ketiadaan Implementasi SQL Lanjut:**
   Berkas `db/03_queries.sql` harus segera diisi dengan kode fungsional PL/pgSQL transaksi atomik dan kueri analitis agar dapat diuji coba.
3. **Integritas Akademis Laporan:**
   Laporan tidak boleh memuat angka benchmark, waktu eksekusi, atau ukuran disk hasil fabrikasi/perkiraan. Seluruh angka wajib diambil langsung dari luaran PostgreSQL terminal setelah data nyata terisi.
