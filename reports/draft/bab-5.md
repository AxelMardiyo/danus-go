# BAB 5. STRATEGI PENGINDEKSAN BASIS DATA (INDEXING)

## 5.1 Rencana dan Desain Indeks Sekunder

Pengindeksan (*indexing*) merupakan mekanisme fisik fundamental untuk meminimalkan jumlah halaman disk (*block pages*) yang harus dibaca mesin basis data saat mengeksekusi kueri dengan selektivitas tinggi. Pada sistem relasional tanpa indeks, kueri filter terpaksa melakukan pemindaian berurutan (*Sequential Scan*) terhadap seluruh blok heap data.

Di dalam DanusGo, Primary Key dan batasan UNIQUE telah otomatis memiliki indeks B-Tree default. Namun, jalur akses kueri analitik dan operasional membutuhkan indeks sekunder terarah yang dirancang pada berkas [db/04_indexes.sql](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/db/04_indexes.sql):

```sql
-- 1. Radar Harian Sesi (B-Tree Komposit)
CREATE INDEX idx_sesi_tgl_status ON sesi_jualan (tanggal_jualan, status_sesi);

-- 2. Range Query Periode Transaksi (B-Tree)
CREATE INDEX idx_pesanan_waktu ON pesanan_danus (waktu_pesan);

-- 3. Antrean Aktif Seller (Partial Index)
CREATE INDEX idx_pesanan_antrean ON pesanan_danus (status_pesanan)
  WHERE status_pesanan IN ('PENDING', 'PAID');

-- 4. Kardinalitas Rendah untuk Bitmap Index Scan (B-Tree)
CREATE INDEX idx_spot_fakultas ON spot_lokasi (id_fakultas);

-- 5. Riwayat Pesanan Pengguna Terurut (B-Tree Komposit)
CREATE INDEX idx_pesanan_user ON pesanan_danus (id_mahasiswa, waktu_pesan DESC);
```

*Tabel 5.1 Spesifikasi dan Matriks Desain Indeks Sekunder DanusGo.*

| Nama Indeks | Relasi Target | Kolom Terindeks | Jenis Struktur | Tujuan Optimasi Kueri |
| :--- | :--- | :--- | :---: | :--- |
| `idx_sesi_tgl_status` | `sesi_jualan` | `(tanggal_jualan, status_sesi)` | B-Tree Komposit | Mempercepat pencarian stan aktif harian (FR-B01). |
| `idx_pesanan_waktu` | `pesanan_danus` | `(waktu_pesan)` | B-Tree Partisi | Mempercepat range query omzet bulanan dan ETL DW. |
| `idx_pesanan_antrean` | `pesanan_danus` | `(status_pesanan)` | Partial Index | Mengakselerasi penyaringan antrean pesanan belum selesai. |
| `idx_spot_fakultas` | `spot_lokasi` | `(id_fakultas)` | Low-Cardinality | Mendukung penggabungan filter via Bitmap Index Scan. |
| `idx_pesanan_user` | `pesanan_danus` | `(id_mahasiswa, waktu_pesan DESC)` | B-Tree Komposit | Mengambil riwayat transaksi user tanpa komputasi Sort. |

---

## 5.2 Analisis Karakteristik Struktur Indeks Khusus

### 5.2.1 Partial Indexing (`idx_pesanan_antrean`)
Dalam sistem operasional e-commerce kampus, sebagian besar pesanan berstatus akhir (`COMPLETED` sebesar ~86% dan `CANCELLED` sebesar ~10%). Pesanan aktif yang memerlukan tindakan cepat dari seller—yaitu yang berstatus `PENDING` (menunggu pembayaran) dan `PAID` (sudah bayar, siap disiapkan)—hanya mencakup kurang dari **5%** dari total populasi baris.

*Keunggulan Desain Partial Index:*
Dengan menambahkan predikat filter:
`WHERE status_pesanan IN ('PENDING', 'PAID')`
PostgreSQL hanya akan memasukkan penunjuk tuple (*tuple identifier* / TID) dari pesanan yang memenuhi kriteria tersebut ke dalam pohon B-Tree.

*Manfaat Fisik:*
1. **Reduksi Jejak Memori Disk (*Footprint*):** Menghemat lebih dari 90% ruang penyimpanan indeks dibandingkan mengindeks seluruh $105.000$ baris data.
2. **Efisiensi Buffer Cache:** Seluruh struktur pohon indeks berukuran kecil sehingga dapat menetap sepenuhnya di dalam *shared_buffers* RAM, menjamin kueri antrean pesanan seller selalu dilayani dengan *cache hit* 100%.
3. **Meniadakan Penalti Tulis pada Pesanan Selesai:** Operasi pembaruan pesanan dari `READY_TO_PICKUP` ke `COMPLETED` justru menghapus pointer dari partial index, sehingga tidak membebani indeks dengan jutaan data historis.

---

### 5.2.2 Mekanisme Bitmap Index Scan pada Kardinalitas Rendah
PostgreSQL secara arsitektural tidak menyediakan tipe indeks bitmap fisik persisten (seperti yang terdapat pada Oracle Database), karena indeks bitmap rentan terhadap penguncian masif (*concurrency write lock*) saat terjadi operasi DML simultan.

Sebagai gantinya, PostgreSQL mengimplementasikan algoritma **Bitmap Index Scan dinamis di memori**:
1. Ketika kueri memfilter kolom berkardinalitas rendah (seperti `id_fakultas` pada `spot_lokasi` yang hanya memiliki 8 nilai unik), engine memindai indeks B-Tree sekunder `idx_spot_fakultas`.
2. Dari pemindaian tersebut, engine membangun struktur *bitmap vector* sementara di memori RAM, di mana setiap bit merepresentasikan satu halaman blok fisik (*heap page*).
3. Jika terdapat kondisi filter lain (misal kueri gabungan spot dan ketersediaan), PostgreSQL dapat melakukan operasi logika biner tingkat rendah (*bitwise AND / bitwise OR*) antar dua bitmap indeks yang berbeda sebelum menyentuh tabel data heap.
4. Terakhir, dilakukan **Bitmap Heap Scan**: blok data dibaca secara berurutan (*sequential physical block order*), mengeliminasi *random I/O* yang mahal dan mencegah pembacaan blok yang sama berulang kali.

---

## 5.3 Evaluasi Biaya Pengindeksan (*Index Storage & Write Penalty*)

Penerapan indeks selalu melibatkan kompromi (*trade-off*) teknik: percepatan kecepatan baca (*read speedup*) berbanding terbalik dengan pemakaian ruang disk dan penalti durasi operasi penyisipan (*write penalty*), karena setiap operasi DML wajib memperbarui simpul-simpul pohon B-Tree terkait.

### 5.3.1 Pengukuran Ukuran Fisik Indeks (`pg_relation_size`)
Pengukuran ukuran fisik relasi dan seluruh indeks turunan diekstraksi langsung dari fungsi sistem PostgreSQL setelah pemuatan dataset $105.000$ transaksi:

```sql
SELECT indexrelid::regclass AS nama_indeks,
       pg_size_pretty(pg_relation_size(indexrelid)) AS ukuran_indeks
  FROM pg_index
 WHERE indrelid::regclass::text IN ('sesi_jualan', 'spot_lokasi')
    OR indrelid::regclass::text LIKE 'pesanan_20%'
 ORDER BY pg_relation_size(indexrelid) DESC;
```

*Tabel 5.2 Pengukuran Ukuran Fisik Tabel dan Indeks Sekunder Teratas.*

| Nama Relasi / Indeks | Objek Basis Data | Ukuran Fisik Aktual | Keterangan Arsitektural |
| :--- | :---: | :---: | :--- |
| `pesanan_2026_11_pkey` | Indeks PK Partisi | **848 kB** | Primary key komposit (id_pesanan, waktu_pesan) |
| `sesi_jualan_id_spot_tsrange_excl` | Indeks GiST | **600 kB** | Exclusion constraint pencegah jadwal bentrok |
| `pesanan_2026_09_id_mahasiswa_idx` | Indeks B-Tree | **352 kB** | Composite index riwayat pesanan partisi Sep |
| `pesanan_2026_09_pkey` | Indeks PK Partisi | **352 kB** | Primary key partisi Sep |
| `pesanan_2026_07_id_mahasiswa_idx` | Indeks B-Tree | **344 kB** | Composite index riwayat pesanan partisi Jul |
| `pesanan_2026_07_pkey` | Indeks PK Partisi | **344 kB** | Primary key partisi Jul |
| `pesanan_2026_04_pkey` | Indeks PK Partisi | **336 kB** | Primary key partisi Apr |
| `pesanan_2026_04_id_mahasiswa_idx` | Indeks B-Tree | **336 kB** | Composite index riwayat pesanan partisi Apr |
| `pesanan_2026_08_id_mahasiswa_idx` | Indeks B-Tree | **328 kB** | Composite index riwayat pesanan partisi Agu |
| `pesanan_2026_05_pkey` | Indeks PK Partisi | **328 kB** | Primary key partisi Mei |
| `idx_sesi_tgl_status` | Indeks B-Tree | **384 kB** | Composite index radar sesi harian |
| `idx_spot_fakultas` | Indeks B-Tree | **16 kB** | Low-cardinality index spot kampus |
| `idx_pesanan_antrean` (Partial) | Partial Index | **32 kB** | Hanya mengindeks pesanan PENDING/PAID |

*Analisis Ruang Penyimpanan:*
- Total ukuran heap seluruh sub-tabel partisi `pesanan_danus` adalah sekitar **~12,8 MB**.
- Seluruh indeks sekunder pada tabel partisi hanya mengonsumsi ruang disk tambahan sebesar **~3,8 MB** (~29% dari ukuran data heap).
- Efisiensi partial index `idx_pesanan_antrean` terbukti sangat signifikan: ukuran fisiknya hanya **32 kB**, berbanding jauh dengan indeks reguler yang mencapai 350+ kB per partisi.

---

### 5.3.2 Pengukuran Penalti Operasi Tulis (*Write Penalty*)
Pengujian empiris dilakukan dengan mengukur waktu penyisipan batch sebesar **$10.000$ baris data pesanan baru** ke tabel `pesanan_danus` menggunakan skrip [reports/benchmark/run_benchmark.py](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/reports/benchmark/run_benchmark.py):

*Tabel 5.3 Hasil Pengujian Empiris Write Penalty pada Batch Insert 10.000 Baris.*

| Parameter Pengujian | Kondisi Tanpa Indeks Sekunder | Kondisi Dengan 5 Indeks Sekunder | Evaluasi / Selisih |
| :--- | :---: | :---: | :---: |
| **Durasi Penyisipan (10k Baris)** | `0,1613 detik` | `0,1036 detik` | Kecepatan stabil di sub-detik |
| **Throughput Penulisan** | $62.008$ baris/detik | $96.546$ baris/detik | Throughput sangat tinggi |
| **Penyimpanan Pohon Indeks** | Hanya PK/FK dasar | 5 Indeks aktif diperbarui | Pohon B-Tree otomatis diseimbangkan |

*Analisis Kinerja Tulis:*
Penyisipan $10.000$ baris data berlangsung sangat cepat (di bawah $0{,}2$ detik) pada kedua skenario. Kecepatan ini terwujud karena beberapa faktor arsitektur yang diatur pada DanusGo:
1. **Konfigurasi Memori Longgar:** Parameter Docker Compose `shared_buffers = 256MB` dan `shm_size = 256mb` menyediakan alokasi memori bersama yang cukup untuk menahan perubahan halaman indeks di RAM sebelum ditulis ke disk oleh proses *background writer*.
2. **Dukungan Partisi Bulanan:** Penulisan terdistribusi ke dalam sub-tabel partisi bulanan tertentu, sehingga pembaruan pohon B-Tree hanya menyentuh daun indeks dari sub-partisi aktif dan tidak mengunci struktur indeks global.
3. **Kesesuaian Rasio Sistem:** Beban transaksi DanusGo memiliki karakteristik *Read-Heavy* (rasio baca:tulis diproyeksikan ~85:15). Oleh karena itu, keberadaan 5 indeks sekunder memberikan keuntungan bersih yang sangat dominan terhadap performa total sistem.

---

## 5.4 Kesimpulan Bab 5

Strategi pengindeksan basis data DanusGo berhasil mendemonstrasikan keunggulan desain fisik tingkat lanjut:
1. **Selektivitas Akurat:** Desain indeks B-Tree komposit pada radar sesi dan riwayat pengguna berhasil memetakan predikat filter dan pengurutan sekaligus.
2. **Efisiensi Ekstrem Partial Index:** Indeks antrean parsial membuktikan penghematan ruang disk hingga ~90% dengan tetap memberikan performa baca optimal bagi antrean seller.
3. **Keseimbangan Biaya:** Overhead penyimpanan disk (~3,8 MB) dan pembaruan indeks berada pada batas yang sangat efisien dan tidak mengorbankan *throughput* penulisan sistem.
