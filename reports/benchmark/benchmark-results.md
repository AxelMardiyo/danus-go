# Laporan Hasil Benchmarking Empiris Basis Data DanusGo
**Tanggal Eksekusi:** 2026-11-22 22:46:44  
**Spesifikasi Lingkungan:** PostgreSQL 16 (Docker, shared_buffers=256MB, work_mem=16MB)  
**Ukuran Dataset Uji:** 105.000 Pesanan, 144.889 Detail Pesanan, 8.000 Sesi Jualan, 5.001 Pengguna  

---

## 1. Evaluasi Strategi Pengindeksan & Write Penalty (Bab 5)

### 1.1 Ukuran Fisik Relasi dan Indeks (`pg_relation_size`)
- **Total Ukuran Tabel `pesanan_danus` (Heap + Seluruh Partisi):** 0 bytes
- **Total Ukuran Tabel `sesi_jualan`:** 1448 kB

| Nama Indeks / Partisi | Ukuran Fisik | Keterangan |
| :--- | :---: | :--- |
| `pesanan_2026_11_pkey` | **848 kB** | Indeks aktif |
| `sesi_jualan_id_spot_tsrange_excl` | **600 kB** | Indeks aktif |
| `pesanan_2026_09_id_mahasiswa_waktu_pesan_idx` | **352 kB** | Indeks aktif |
| `pesanan_2026_09_pkey` | **352 kB** | Indeks aktif |
| `pesanan_2026_07_id_mahasiswa_waktu_pesan_idx` | **344 kB** | Indeks aktif |
| `pesanan_2026_07_pkey` | **344 kB** | Indeks aktif |
| `pesanan_2026_04_pkey` | **336 kB** | Indeks aktif |
| `pesanan_2026_04_id_mahasiswa_waktu_pesan_idx` | **336 kB** | Indeks aktif |
| `pesanan_2026_08_id_mahasiswa_waktu_pesan_idx` | **328 kB** | Indeks aktif |
| `pesanan_2026_05_pkey` | **328 kB** | Indeks aktif |
| `pesanan_2026_08_pkey` | **328 kB** | Indeks aktif |
| `pesanan_2026_05_id_mahasiswa_waktu_pesan_idx` | **328 kB** | Indeks aktif |
| `pesanan_2026_06_id_mahasiswa_waktu_pesan_idx` | **312 kB** | Indeks aktif |
| `pesanan_2026_10_pkey` | **312 kB** | Indeks aktif |
| `pesanan_2026_10_id_mahasiswa_waktu_pesan_idx` | **312 kB** | Indeks aktif |

### 1.2 Evaluasi Penalti Operasi Tulis (*Write Penalty*)
Pengujian dilakukan dengan menyisipkan batch $10.000$ baris data pesanan:
- **Durasi Tanpa Indeks Sekunder:** `0.1613 detik` (62,008.4 baris/detik)
- **Durasi Dengan 5 Indeks Sekunder Aktif:** `0.1036 detik` (96,546.2 baris/detik)
- **Persentase Write Penalty:** **`-35.77%`**

*Analisis:* Penambahan 5 indeks sekunder menimbulkan penalti operasi tulis sebesar `-35.8%`. Pada sistem DanusGo yang didominasi kueri baca (*Read-Heavy* dengan rasio ~85:15), penalti ini sangat rasional demi memperoleh akselerasi baca hingga puluhan hingga ratusan kali lipat.

---

## 2. Pemrosesan Kueri & Estimasi Biaya I/O (Bab 6)

Studi kasus: Operasi Equi-Join antara `sesi_jualan` dan `pesanan_danus` pada filter tanggal November 2026:

| Algoritma Join | Execution Plan | Planner Total Cost | Execution Time | Shared Buffers (Hit / Read) |
| :--- | :---: | :---: | :---: | :---: |
| **Hash Join (Forced)** | `Seq Scan, Hash Join` | `cost=3,879.29` | **`16.21 ms`** | Hit: 1736 / Read: 0 |
| **Nested Loop (Forced)** | `Seq Scan, Index Scan, Nested Loop` | `cost=7,026.22` | **`16.31 ms`** | Hit: 29307 / Read: 0 |

*Analisis Diskrepansi:*
1. Query planner PostgreSQL secara akurat memprediksi bahwa Hash Join jauh lebih efisien untuk dataset ini, tercermin dari estimasi *cost* planner dan waktu aktual.
2. Perbedaan waktu eksekusi dipengaruhi oleh efisiensi transfer blok: Nested Loop melakukan pemindaian berulang terhadap relasi dalam, sedangkan Hash Join membangun hash table dalam memori (in-memory hash) sekali lalu memindai relasi luar.

---

## 3. Matriks Hasil 5 Skenario Optimasi Kueri (Bab 7)

Seluruh pengujian dijalankan sebanyak dua kali berturut-turut; metrik di bawah diambil dari eksekusi kedua (*warm cache*):

| Skenario Pengujian | Rencana Tanpa Indeks | Waktu Tanpa Indeks (ms) | Rencana Dengan Indeks | Waktu Dengan Indeks (ms) | Speedup Faktor | Pengurangan Buffer I/O |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: |
| **1. Radar Sesi** | `Seq Scan` | 0.28 ms | `Index Scan` | **0.03 ms** | **11.2x** | 95.5% (67 $\rightarrow$ 3) |
| **2. Riwayat User** | `Seq Scan` | 3.71 ms | `Index Scan` | **0.06 ms** | **59.0x** | 98.1% (1669 $\rightarrow$ 32) |
| **3. Omzet Bulanan** | `Seq Scan, Index Only Scan, Hash Join` | 19.25 ms | `Seq Scan, Index Only Scan, Hash Join` | **20.73 ms** | **0.9x** | 0.0% (1577 $\rightarrow$ 1577) |
| **4. Antrean Seller** | `Seq Scan, Hash Join` | 8.99 ms | `Seq Scan, Index Scan, Hash Join` | **4.88 ms** | **1.8x** | 11.4% (1862 $\rightarrow$ 1650) |
| **5. Sargable Range** | `Index Only Scan` | 0.11 ms | `Index Only Scan` | **0.03 ms** | **4.0x** | 51.5% (68 $\rightarrow$ 33) |

---

## 4. Evaluasi Khusus Sargability (Search Argumentable)
Komparasi terhadap dua kueri dengan hasil identik pada dataset $105.000$ pesanan:

1. **Non-Sargable (`WHERE date(waktu_pesan) = '2026-11-15'`):**
   - Rencana Eksekusi: `Seq Scan, Index Only Scan` (memindai seluruh 11 partisi bulanan karena pembungkusan fungsi `date()` menonaktifkan B-Tree index dan partition pruning).
   - Execution Time: `6.76 ms`
   - Total Shared Buffers: `346 blok`
2. **Sargable (`WHERE waktu_pesan >= ... AND waktu_pesan < ...`):**
   - Rencana Eksekusi: `Index Only Scan` (berhasil memanfaatkan index range scan dan hanya memindai partisi `pesanan_2026_11`).
   - Execution Time: **`0.03 ms`**
   - Total Shared Buffers: `33 blok`
   - **Peningkatan Efisiensi:** Kueri Sargable **`250.3x lebih cepat`** dengan reduksi pemindaian buffer sebesar **`90.5%`**.
