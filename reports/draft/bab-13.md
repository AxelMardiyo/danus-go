# BAB 13: PERANCANGAN DATA WAREHOUSE & ANALITIK OLAP MULTIDIMENSI

## 13.1 Landasan Teori Pemodelan Dimensional & OLAP

Seiring bertambahnya skala transaksi harian pada platform *DanusGo*, pemrosesan analisis bisnis eksekutif (seperti laporan omzet bulanan, analisis margin keuntungan per kategori produk, dan deteksi spot penjualan terlaris) menimbulkan beban komputasi berat yang dapat mendegradasi performa sistem transaksional operasional (*OLTP*). Untuk mengatasi permasalahan ini, dirancang arsitektur **Data Warehouse (DW)** dengan pendekatan **Online Analytical Processing (OLAP)** berbasis **Star Schema**.

### 13.1.1 Perbedaan Paradigma OLTP vs. OLAP

Sistem basis data *DanusGo* memisahkan ranah operasional dan analitik ke dalam dua skema independen pada klaster database PostgreSQL yang sama:

| Parameter Perbandingan | Skema Operasional (`public`) - OLTP | Skema Data Warehouse (`dw`) - OLAP |
|---|---|---|
| **Tujuan Utama** | Transaksi atomik harian, anti-*overselling*, konkurensi tinggi | Analisis bisnis agregatif, pelaporan multi-dimensi, *decision support* |
| **Karakteristik Kueri** | Pembacaan dan penulisan baris tunggal (*point query*, `INSERT`/`UPDATE` cepat) | Pemindaian massal jutaan baris data historis, *multi-table aggregation join* |
| **Bentuk Normalisasi** | Normalisasi ketat BCNF & 4NF (eliminasi redundansi data) | Denormalisasi terarah via Star Schema (mengurangi kompleksitas *join*) |
| **Frekuensi Modifikasi** | Pembaruan data *real-time* berkecepatan tinggi | Pemuatan berkala (*periodic batch loading*) melalui pipeline ETL |
| **Orientasi Pengguna** | Mahasiswa pembeli (*Buyer*) dan panitia penjual (*Seller*) | Koordinator dan pimpinan fakultas/organisasi kampus |

### 13.1.2 Metodologi Pemodelan Dimensional Ralph Kimball

Pemodelan dimensional DanusGo mengadopsi metodologi arsitektur bus Kimball (*Kimball Dimensional Modeling*), yang terdiri dari dua komponen entitas inti:
1. **Tabel Fakta (*Fact Table*):**
   Memuat metrik kuantitatif numerik (ukuran bisnis) yang dihasilkan dari peristiwa transaksi nyata.
   * **Grain (Butir Fakta):** Ditentukan pada tingkat paling terperinci (*finest atomic grain*), yaitu **satu baris mewakili satu item produk yang terjual dalam pesanan berstatus `COMPLETED`**. Penetapan grain atomik menjamin fleksibilitas analisis maksimum, memungkinkan data diagregasikan hingga level varian maupun ditingkatkan ke level universitas tanpa kehilangan presisi.
   * **Ukuran Numerik (Measures):**
     * *Fully Additive Measures:* Kuantitas terjual, total omzet kotor, total modal pengadaan, dan laba bersih. Seluruh metrik ini valid untuk dijumlahkan di semua dimensi (waktu, lokasi, organisasi, dan produk).
     * *Non-Additive / Semi-Additive:* Rasio margin keuntungan (`laba_bersih / total_omzet`).
   * **Degenerate Dimension:** Kunci bisnis transaksi `id_detail` dari tabel operasional disimpan langsung di tabel fakta sebagai *primary key*. Hal ini memberikan sifat idempoten pada pipeline ETL (mencegah duplikasi data saat ETL dieksekusi ulang).
2. **Tabel Dimensi (*Dimension Tables*):**
   Menyediakan konteks tekstual deskriptif ("siapa, apa, di mana, dan kapan") yang digunakan sebagai filter, pengelompokan (*grouping*), dan penamaan label pada laporan bisnis.
   * Setiap dimensi menggunakan **Surrogate Key** berbasis integer (`id_*_dw`) yang dihasilkan otomatis oleh engine database (`GENERATED ALWAYS AS IDENTITY`). Penggunaan *surrogate key* mengisolasi data warehouse dari perubahan kunci bisnis operasional (*natural key*), memangkas lebar indeks blok memori, dan mengoptimalkan performa operasi join.

### 13.1.3 Operasi Analitik Multidimensi & Ekstensi SQL OLAP

Data warehouse memfasilitasi eksplorasi data melalui kubus data multidimensi (*OLAP Cube*) dengan empat operasi navigasi fundamental:
1. **Roll-Up:** Menaikkan level agregasi data sepanjang hierarki dimensi (misalnya dari item varian $\to$ nama produk $\to$ kategori produk).
2. **Drill-Down:** Menurunkan level agregasi untuk melihat rincian yang lebih mendalam (misalnya dari omzet per fakultas $\to$ rincian spot gazebo $\to$ rincian per jam transaksi).
3. **Slice & Dice:** 
   * *Slice:* Memilih satu dimensi tunggal bernilai spesifik (misalnya hanya produk dengan `kategori = 'MAKANAN_BERAT'`).
   * *Dice:* Memilih sub-kubus melalui filter pada beberapa dimensi sekaligus (misalnya `kategori = 'MAKANAN_BERAT'` AND `wilayah_fakultas = 'Teknik'` AND `jam BETWEEN 11 AND 13`).
4. **Pivot / Rotate:** Mengubah orientasi dimensi laporan untuk menyajikan matriks tabulasi silang (*cross-tabulation*).

Untuk mendukung operasi tersebut secara efisien pada tingkat engine SQL, PostgreSQL menyediakan ekstensi klausa `GROUP BY`:
* **`GROUP BY ROLLUP (A, B, C)`:** Menghasilkan subtotal bertingkat dengan asumsi hierarki $A \to B \to C$. Menghasilkan $N + 1$ kombinasi pengelompokan: $(A, B, C)$, $(A, B)$, $(A)$, dan grand total $()$.
* **`GROUP BY CUBE (A, B, C)`:** Menghasilkan seluruh kombinasi sudut pandang analitik tanpa memandang hierarki ($2^N$ kombinasi pengelompokan), mencakup seluruh kemungkinan irisan agregat.
* **`MATERIALIZED VIEW`:** Menyimpan hasil pra-agregasi kueri analitik berat secara fisik ke disk, memungkinkan pembacaan instan berkecepatan tinggi dengan pembaruan berkala via perintah `REFRESH MATERIALIZED VIEW`.

---

## 13.2 Arsitektur Star Schema Data Warehouse DanusGo

Implementasi struktur fisik skema `dw` didefinisikan pada berkas [db/06_dw_schema.sql](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/db/06_dw_schema.sql). Arsitektur dirancang mengikuti pola **Star Schema** dengan satu tabel fakta sentral yang dikelilingi oleh lima tabel dimensi:

```
                            +-------------------+
                            |    dw.dim_waktu   |
                            +-------------------+
                            | PK  id_waktu      |
                            |     tanggal       |
                            |     hari, bulan   |
                            |     kuartal, tahun|
                            |     is_hari_kuliah|
                            +---------+---------+
                                      |
                                      | 1:N
+-------------------+        +--------v----------------------+        +---------------------+
|    dw.dim_jam     |        |   dw.fakta_penjualan_danus    |        |     dw.dim_spot     |
+-------------------+        +-------------------------------+        +---------------------+
| PK  id_jam        |        | PK  id_detail (Degenerate)    |        | PK  id_spot_dw      |
|     jam           | 1:N    | FK  id_waktu                  |    1:N | UK  id_spot         |
|     menit_slot    +------->| FK  id_jam                    |<-------+     spot            |
|     label         |        | FK  id_spot_dw                |        |     wilayah_fakultas|
+-------------------+        | FK  id_organisasi_dw          |        |     universitas     |
                             | FK  id_produk_dw              |        +---------------------+
+-------------------+        |     kuantitas_terjual         |
| dw.dim_organisasi |        |     total_omzet               |        +---------------------+
+-------------------+        |     total_modal               |        |    dw.dim_produk    |
| PK  id_organisasi_dw       |     laba_bersih               |        +---------------------+
| UK  id_organisasi | 1:N    |     jumlah_transaksi          |    1:N | PK  id_produk_dw    |
|     organisasi    +------->+-------------------------------+<-------+     id_produk       |
|     fakultas_asal |                         |                       |     id_varian       |
+-------------------+                         | 1:N                   |     varian, produk  |
                                              v                       |     kategori        |
                             +-------------------------------+        +---------------------+
                             |     dw.mv_omzet_bulanan       |
                             |     (Materialized View)       |
                             +-------------------------------+
```

### 13.2.1 Spesifikasi Kamus Data Dimensi dan Fakta

1. **`dw.dim_waktu` (730 baris):**
   * Mencakup kalender penuh 2026–2027 yang di-generate via `generate_series`.
   * Atribut: `id_waktu` (kunci format YYYYMMDD, mis. `20261124`), `tanggal`, `hari`, `bulan`, `kuartal` (1–4), `tahun`, dan indikator boolean `is_hari_kuliah` (Senin–Jumat).
2. **`dw.dim_jam` (48 baris):**
   * Membagi 24 jam ke dalam slot interval 30 menit (`id_jam = jam*100 + menit`).
   * Atribut: `label` waktu operasional ('Pagi', 'Jam Makan Siang' 10.00–13.30, 'Sore', 'Malam', 'Di Luar Jam Jualan').
3. **`dw.dim_spot` (30 baris):**
   * Menyimpan hierarki geospasial: `spot` (lokasi fisik) $\to$ `wilayah_fakultas` $\to$ `universitas`.
4. **`dw.dim_organisasi` (40 baris):**
   * Menyimpan profil kepanitiaan: `organisasi` (nama badan dan proker danusan) $\to$ `fakultas_asal`.
5. **`dw.dim_produk` (445 baris):**
   * Menyimpan hierarki varian dan klasifikasi: `id_varian` $\to$ `nama_produk` $\to$ `kategori` (`MAKANAN_BERAT`, `SNACK`, `MINUMAN`, `MERCHANDISE`). Menerapkan fitur PostgreSQL 15+ `UNIQUE NULLS NOT DISTINCT (id_produk, id_varian)`.
6. **`dw.fakta_penjualan_danus` (124.702 baris):**
   * Menampung seluruh metrik penjualan dari pesanan berstatus `'COMPLETED'`.
   * Diindeks menggunakan B-Tree komposit sekunder: `idx_fakta_waktu`, `idx_fakta_spot`, dan `idx_fakta_prod`.

---

## 13.3 Desain & Implementasi Pipeline ETL (Extract, Transform, Load)

Pipeline ETL dirancang dan diimplementasikan secara otomatis melalui modul Python [seed/etl_dw.py](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/seed/etl_dw.py). 

### 13.3.1 Logika Pemrosesan ETL

```
[DATA OPERASIONAL]                                       [DATA WAREHOUSE]
pesanan_danus       ---(Extract: status='COMPLETED')---> dw.dim_waktu
detail_pesanan      ---(Transform: Hitung Laba/Waktu)---> dw.dim_jam
sesi_jualan         ---(Map: Natural Key -> Surrogate)--> dw.dim_spot
sesi_produk         ---(Load: Idempotent Batch Insert)-> dw.dim_organisasi
spot & organisasi   -----------------------------------> dw.dim_produk
                                                         dw.fakta_penjualan_danus
                                                         REFRESH dw.mv_omzet_bulanan
```

1. **Extract (Ekstraksi):**
   Hanya pesanan yang telah tuntas (`p.status_pesanan = 'COMPLETED'`) yang ditarik dari tabel operasional `pesanan_danus` dan `detail_pesanan`. Transaksi yang berstatus `PENDING`, `CANCELLED`, atau kedaluwarsa diabaikan demi menjaga kemurnian data fakta finansial.
2. **Transform (Transformasi):**
   * **Pemetaan Dimensi Waktu:** Mengonversi timestamp `p.waktu_pesan` ke zona waktu Jakarta (`Asia/Jakarta`) dan mengekstrak kunci kalender integer `to_char(waktu, 'YYYYMMDD')::int`.
   * **Pemetaan Slot Jam:** Mengelompokkan menit pemesanan ke slot 30 menit terdekat:
     $$\text{id\_jam} = (\text{jam} \times 100) + (\text{CASE WHEN menit } < 30 \text{ THEN } 0 \text{ ELSE } 30 \text{ END})$$
   * **Kalkulasi Metrik Finansial:**
     $$\text{total\_omzet} = \text{jumlah\_item} \times \text{harga\_satuan}$$
     $$\text{total\_modal} = \text{jumlah\_item} \times \text{harga\_modal\_satuan}$$
     $$\text{laba\_bersih} = \text{total\_omzet} - \text{total\_modal}$$
   * **Resolusi Surrogate Key:** Mengaitkan kunci bisnis operasional (`id_spot`, `id_organisasi`, `id_produk`, `id_varian`) dengan surrogate key dimensi DW melalui operasi relasional *single-pass*.
3. **Load (Pemuatan):**
   Pemuatan data ke `dw.fakta_penjualan_danus` memanfaatkan klausa `ON CONFLICT (id_detail) DO NOTHING`. Mekanisme ini menjamin idempotensi penuh: jika pipeline ETL dijalankan berulang kali, tidak akan pernah terjadi anomali penggandaan data (*duplicate data ingestion*).

### 13.3.2 Metrik Kinerja Eksekusi ETL

Hasil eksekusi riil pipeline ETL menyajikan performa sebagai berikut:

| Tahapan ETL | Entitas Target | Waktu Eksekusi | Baris Terproses | Throughput Data | Status Integritas |
|---|---|:---:|:---:|:---:|:---:|
| **ETL 1** | `dw.dim_spot` | 0,017 s | 30 baris | 1.764 baris/s | Sukses / Idempoten |
| **ETL 2** | `dw.dim_organisasi` | 0,003 s | 40 baris | 13.333 baris/s | Sukses / Idempoten |
| **ETL 3** | `dw.dim_produk` | 0,011 s | 445 baris | 40.454 baris/s | Sukses / Idempoten |
| **ETL 4** | `dw.fakta_penjualan_danus` | 4,194 s | **124.702 baris** | **29.733 baris/s** | **Sukses Penuh (100%)** |
| **ETL 5** | Refresh Materialized View | 0,167 s | 396 baris agregat | 2.371 baris/s | Konsisten & Terindeks |
| **TOTAL** | **Pipeline Lengkap** | **4,414 s** | **125.613 baris** | **28.457 baris/s** | **SELESAI TANPA ERROR** |

*Ringkasan Nilai Finansial DW DanusGo:*
* **Total Transaksi Item Terjual:** 124.702 transaksi item (dari 90.348 pesanan tuntas).
* **Akumulasi Omzet Kotor (Gross Revenue):** **Rp 2.383.765.000,00** (~Rp 2,38 Miliar).
* **Akumulasi Laba Bersih (Net Profit):** **Rp 938.360.000,00** (~Rp 938,3 Juta).
* **Rata-rata Margin Keuntungan:** **39,36%**.

---

## 13.4 Evaluasi Empiris Kueri Analitik OLAP

Pengujian empiris terhadap 4 skenario kueri analitik dijalankan menggunakan modul [reports/benchmark/run_olap_benchmark.py](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/reports/benchmark/run_olap_benchmark.py). Seluruh rencana eksekusi dan log waktu dicatat secara detail pada [reports/benchmark/raw_explain_olap.txt](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/reports/benchmark/raw_explain_olap.txt).

### 13.4.1 Kueri 1: GROUP BY ROLLUP (Hierarki Wilayah $\to$ Organisasi $\to$ Kategori)

Kueri analitik hierarkis menyajikan laporan berjenjang mulai dari detail kategori per organisasi hingga subtotal per wilayah fakultas dan grand total universitas:

```sql
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
ORDER BY s.wilayah_fakultas NULLS LAST, o.organisasi NULLS LAST, p.kategori NULLS LAST;
```

*Cuplikan Hasil Eksekusi (Hierarki Subtotal & Grand Total):*

| Wilayah Fakultas | Nama Organisasi | Kategori Produk | Total Transaksi | Total Omzet | Total Laba Bersih |
|---|---|---|:---:|:---:|:---:|
| Area Umum | BEM Universitas (Danus) | MAKANAN_BERAT | 1.842 | Rp 35.120.000 | Rp 13.840.000 |
| Area Umum | BEM Universitas (Danus) | MINUMAN | 2.105 | Rp 21.050.000 | Rp 9.450.000 |
| Area Umum | BEM Universitas (Danus) | **SEMUA KATEGORI (Subtotal Org)** | **3.947** | **Rp 56.170.000** | **Rp 23.290.000** |
| Area Umum | **SEMUA ORGANISASI** | **SEMUA KATEGORI (Subtotal Wilayah)** | **14.850** | **Rp 284.150.000** | **Rp 112.430.000** |
| ... | ... | ... | ... | ... | ... |
| **SEMUA WILAYAH** | **SEMUA ORGANISASI** | **SEMUA KATEGORI (GRAND TOTAL)** | **124.702** | **Rp 2.383.765.000** | **Rp 938.360.000** |

*Kinerja Eksekusi:*
* **Waktu Eksekusi:** **118,44 ms**.
* **Total Baris Hasil Agregasi:** **1.626 baris**.
* **Karakteristik Plan:** Engine memanfaatkan operator `MixedAggregate` dengan *quicksort grouping*, menghasilkan seluruh tingkat hierarki dalam satu kali pemindaian tabel fakta (*single-pass aggregation*).

---

### 13.4.2 Kueri 2: GROUP BY CUBE (Multidimensi Wilayah $\times$ Kuartal $\times$ Kategori)

Kueri kubus analitik menghasilkan $2^3 = 8$ sudut pandang kombinasi irisan data secara simultan:

```sql
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
ORDER BY s.wilayah_fakultas NULLS LAST, w.kuartal NULLS LAST, p.kategori NULLS LAST;
```

*Kinerja Eksekusi:*
* **Waktu Eksekusi:** **151,51 ms**.
* **Total Baris Hasil Kombinasi:** **250 baris agregat kubus**.
* **Analisis:** Dalam waktu hanya 151 ms, sistem menyajikan agregasi dari 8 kombinasi dimensi berbeda (misalnya: omzet per kuartal saja, omzet per kategori saja, omzet per wilayah per kategori tanpa melihat kuartal, hingga grand total), membuktikan kekuatan engine OLAP PostgreSQL dalam menangani *cross-dimensional business intelligence*.

---

### 13.4.3 Kueri 3: Slice & Dice (Kategori Makanan Berat Jam Makan Siang 11–13 di Fakultas Teknik)

Operasi *Slice & Dice* digunakan oleh pengelola danusan untuk membedah segmen pasar paling potensial: menu makan siang mahasiswa teknik pada jam sibuk kuliah:

```sql
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
ORDER BY omzet_makan_siang DESC;
```

*Top 5 Menu & Spot Paling Menguntungkan di Fakultas Teknik:*

| Titik Spot Penjualan | Nama Produk Makanan Berat | Jam | Kuantitas Terjual | Total Omzet | Total Laba Bersih |
|---|---|:---:|:---:|:---:|:---:|
| **Gazebo Giri Santika** | Nasi Katsu Saus Teriyaki | 11.00 | 75 porsi | Rp 1.350.000 | Rp 450.000 |
| **Parkiran Belakang Mesin** | Rice Bowl Ayam Mentai Batch 2 | 11.00 | 50 porsi | Rp 1.000.000 | Rp 350.000 |
| **Selasar Gedung A Teknik** | Rice Bowl Daging Lada Hitam | 11.00 | 39 porsi | Rp 936.000 | Rp 351.000 |
| **Lobby Gedung E Elektro** | Rice Bowl Daging Lada Hitam | 12.00 | 38 porsi | Rp 912.000 | Rp 342.000 |
| **Selasar Gedung A Teknik** | Nasi Katsu Saus Teriyaki | 11.00 | 47 porsi | Rp 846.000 | Rp 282.000 |

*Kinerja Eksekusi:*
* **Waktu Eksekusi:** **11,86 ms**.
* **Total Baris Rekomendasi:** **518 baris spesifik**.
* **Wawasan Bisnis (*Actionable Insight*):** Panitia danusan Fakultas Teknik disarankan memusatkan pasokan stok nasi katsu dan rice bowl di *Gazebo Giri Santika* dan *Selasar Gedung A* tepat pada pukul 11.00 WIB karena memiliki konversi omzet tertinggi.

---

### 13.4.4 Kueri 4: Evaluasi Kinerja Materialized View vs. On-The-Fly Aggregation

Untuk menyajikan metrik performa kepada dashboard analitik pimpinan, dianalisis efisiensi kueri laporan omzet bulanan menggunakan dua metode:
1. **On-The-Fly Aggregation:** Kueri memindai seluruh 124.702 baris tabel fakta secara langsung melalui *multi-table hash join*.
2. **Materialized View Pre-Aggregation (`dw.mv_omzet_bulanan`):** Kueri membaca tabel hasil pra-agregasi yang telah disegarkan (*refreshed*) dan memiliki indeks unik.

| Metrik Evaluasi | On-The-Fly Aggregation | Materialized View Pre-Aggregated | Keuntungan Relatif (*Gain*) |
|---|:---:|:---:|:---:|
| **Waktu Eksekusi ($T$)** | **53,038 ms** | **0,040 ms** | **Speedup 1.325,95x (Instan!)** |
| **Volume Baris Dibaca** | 124.702 baris fakta | 396 baris ringkasan | Reduksi baris sebesar **99,68%** |
| **Buffer I/O (Shared Hit)** | 24 buffer | 8 buffer | **Reduksi Beban I/O 66,7%** |
| **Beban Komputasi CPU** | Hash Join & Aggregation | Simple Sequential Scan | Menghilangkan 100% beban agregasi CPU |

```
          PERBANDINGAN LATENSI KUERI ANALITIK (BAB 13)
  50 ms +--[ 53.04 ms ]--------------------------------------+
        |   On-The-Fly Aggregation                           |
        |   (Scan 124,702 Baris Fakta DW)                    |
  25 ms |                                                    |
        |                                                    |
        |                                [ 0.04 ms ]         |
        |                                Materialized View   |
        |                                Speedup: 1,325x     |
   0 ms +----------------------------------------------------+
```

Visualisasi grafik resmi beresolusi tinggi tersimpan pada berkas [reports/figures/chart_olap_mv_speedup.svg](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/reports/figures/chart_olap_mv_speedup.svg).

*Kesimpulan Arsitektur:*
Penerapan *Materialized View* terbukti memberikan lonjakan kecepatan lebih dari **1.300 kali lipat** dan memangkas penggunaan buffer memori hingga 66,7%. Dengan menjadwalkan perintah `REFRESH MATERIALIZED VIEW CONCURRENTLY dw.mv_omzet_bulanan` setiap malam hari melalui cron/automation, sistem pelaporan eksekutif DanusGo dijamin memiliki latensi di bawah 1 milidetik tanpa membebani basis data transaksional.

---

## 13.5 Ringkasan Bab

Implementasi arsitektur Data Warehouse dan kueri analitik OLAP DanusGo telah membuktikan bahwa:
1. **Star Schema Berkinerja Tinggi:** Skema dimensional berhasil memodelkan 124.702 transaksi penjualan tuntas dengan dimensi waktu, jam, lokasi spot, organisasi, dan produk yang sangat terstruktur.
2. **Pipeline ETL Cepat & Tangguh:** Pipeline ETL berhasil memproses 125.613 record data dari operasional ke data warehouse dalam waktu **4,414 detik** (~28.457 baris/detik) dengan sifat idempoten penuh.
3. **Analitik Multidimensi Lengkap:** Implementasi kueri `ROLLUP`, `CUBE`, dan *Slice & Dice* mampu mengekstraksi wawasan manajerial yang mendalam bagi organisasi kampus hanya dalam waktu ~11–150 milidetik.
4. **Optimasi Materialized View:** Menghasilkan percepatan hingga **1.325x lipat** dibanding agregasi *on-the-fly*, menyediakan fondasi yang kokoh untuk dashboard eksekutif berlatensi sub-milidetik.
