# BAB 3. DESAIN FISIK, INTEGRITAS CONSTRAINT, DAN DATASET 100K+

## 3.1 Skema Fisik PostgreSQL dan Penegakan Integritas Constraint

Implementasi fisik basis data DanusGo dikembangkan pada mesin **PostgreSQL 16**. Skema fisik ditransformasikan dari model logikal ternormalisasi dengan memanfaatkan fitur-fitur integritas canggih tingkat mesin (*engine-level constraints*) guna menjamin bahwa aturan bisnis tidak dapat dilanggar oleh aplikasi klien.

### 3.1.1 Arsitektur Tipe Data dan Ekstensi
PostgreSQL menyediakan dukungan terhadap tipe data rentang (*range types*) dan pengindeksan geometris/spasial yang dimanfaatkan dalam skema DanusGo. Dua ekstensi diaktifkan pada awal skrip [db/01_schema.sql](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/db/01_schema.sql):
```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- Mendukung B-Tree pada indeks GiST (Exclusion Constraint)
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- Pembangkitan hash password crypt() dan salt bcrypt
```

Pemilihan tipe data fisik memperhatikan efisiensi penyimpanan memori dan ketepatan semantik:
- Identitas entitas menggunakan `INT GENERATED ALWAYS AS IDENTITY` untuk tabel master dan `BIGINT GENERATED ALWAYS AS IDENTITY` untuk tabel transaksional berskala masif (`pesanan_danus` dan `detail_pesanan`).
- Nilai moneter menggunakan `NUMERIC(10,2)` untuk menghindari galat pembulatan (*floating-point inaccuracies*).
- Kolom penanda waktu menggunakan `TIMESTAMPTZ` yang terkunci pada zona waktu Waktu Indonesia Barat (`Asia/Jakarta`, UTC+7).

---

### 3.1.2 Pencegahan Tabrakan Jadwal Stan Fisik (Exclusion Constraint GiST)

Aturan bisnis BR-07 mensyaratkan bahwa **tidak boleh ada dua kelompok danusan yang menempati titik lokasi fisik (spot) yang sama pada rentang waktu yang bertubrukan**.

Pendekatan konvensional umumnya mengandalkan pengecekan manual di backend:
`SELECT COUNT(*) FROM sesi_jualan WHERE id_spot = ? AND ...`
Namun, pendekatan tersebut sangat rentan terhadap *race condition*. Dua seller yang mengajukan jadwal di spot yang sama secara serentak dapat sama-sama lolos validasi sebelum data tersimpan.

DanusGo mengatasi permasalahan ini menggunakan **PostgreSQL Exclusion Constraint** berbasis **GiST (Generalized Search Tree)** dengan memanfaatkan tipe data rentang waktu `tsrange`:

```sql
ALTER TABLE sesi_jualan
  ADD CONSTRAINT no_jadwal_bentrok
  EXCLUDE USING gist (
    id_spot WITH =,
    tsrange(
      (tanggal_jualan + jam_mulai)::timestamp,
      (tanggal_jualan + jam_selesai)::timestamp
    ) WITH &&
  );
```

#### Cara Kerja Mekanisme Ini:
1. Operator `id_spot WITH =` memastikan perbandingan dilakukan pada titik lokasi yang identik.
2. Operator `tsrange(...) WITH &&` mengevaluasi apakah terdapat irisan/tumpang tindih (*overlaps*) antara dua interval waktu.
3. Struktur indeks GiST memetakan interval waktu ke dalam pohon hierarki multi-dimensi.
4. Apabila terdapat transaksi konkuren yang mencoba memasukkan jadwal sesi yang beririsan di spot yang sama, PostgreSQL secara otomatis menolak transaksi tersebut dan membangkitkan error berkode **SQLSTATE `23P01` (`exclusion_violation`)**.
5. Mekanisme ini menjamin keteraturan alokasi stan kampus tanpa membutuhkan penguncian tabel tingkat tinggi (*exclusive table lock*).

---

### 3.1.3 Integritas Domain via CHECK Constraints dan Triggers

Integritas semantik data ditegakkan melalui kombinasi *CHECK constraints* deklaratif dan trigger prosedural:

*Tabel 3.1 Ringkasan Batasan Integritas Fisik Basis Data DanusGo.*

| Tabel Target | Nama Batasan / Trigger | Jenis Batasan | Aturan Semantik Bisnis |
| :--- | :--- | :---: | :--- |
| `produk_danus` | `harga_jual >= harga_modal` | CHECK | Mencegah kerugian finansial organisasi seller (BR-06). |
| `produk_danus` | `kategori IN (...)` | CHECK | Restriksi kategori: Makanan Berat, Snack, Minuman, Merchandise. |
| `sesi_jualan` | `jam_selesai > jam_mulai` | CHECK | Memastikan durasi sesi jualan bernilai positif. |
| `sesi_produk` | `kuota_sisa BETWEEN 0 AND kuota_awal`| CHECK | Menjamin sisa kuota tidak negatif dan tidak melampaui kuota awal. |
| `pesanan_danus`| `kedaluwarsa_pada > waktu_pesan` | CHECK | Menjamin jendela waktu pembayaran selalu di masa depan (BR-02). |
| `detail_pesanan` | `trg_validasi_detail` | TRIGGER | Memvalidasi bahwa item sesi, varian, dan pickup valid milik produk sesi. |
| `sesi_produk` | `trg_validasi_sesi_produk` | TRIGGER | Memaksa PRE_ORDER memiliki jendela pemesanan dan READY_STOCK bernilai NULL. |

Kode trigger penegakan jendela pemesanan produk:
```sql
CREATE FUNCTION fn_validasi_sesi_produk() RETURNS trigger AS $$
DECLARE
  v_tipe TEXT;
BEGIN
  SELECT tipe_penjualan INTO v_tipe FROM produk_danus WHERE id_produk = NEW.id_produk;
  IF v_tipe = 'PRE_ORDER' AND (NEW.buka_pesan_pada IS NULL OR NEW.tutup_pesan_pada IS NULL) THEN
    RAISE EXCEPTION 'Integritas BR-08: PRE_ORDER wajib mengisi buka_pesan_pada dan tutup_pesan_pada';
  END IF;
  IF v_tipe = 'READY_STOCK' AND (NEW.buka_pesan_pada IS NOT NULL OR NEW.tutup_pesan_pada IS NOT NULL) THEN
    RAISE EXCEPTION 'Integritas BR-08: READY_STOCK tidak boleh memiliki jendela pesan';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
```

---

## 3.2 Strategi Partisi Tabel Rentang Bulanan (*Range Partitioning*)

Tabel transaksi utama `pesanan_danus` dirancang untuk menampung ratusan ribu hingga jutaan baris transaksi selama tahun operasional kampus. Pada tabel monolitik besar (*single monolithic table*), pemindaian kueri pelaporan dan pemeliharaan indeks mengalami degradasi performa yang signifikan.

DanusGo menerapkan **Declarative Range Partitioning** bulanan pada kolom `waktu_pesan`:

```sql
CREATE TABLE pesanan_danus (
  id_pesanan        BIGINT GENERATED ALWAYS AS IDENTITY,
  id_mahasiswa      INT NOT NULL REFERENCES pengguna(id_mahasiswa),
  id_sesi           INT NOT NULL REFERENCES sesi_jualan(id_sesi),
  waktu_pesan       TIMESTAMPTZ NOT NULL DEFAULT now(),
  metode_bayar      TEXT NOT NULL CHECK (metode_bayar IN ('CASH_COD','QRIS')),
  status_pesanan    TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status_pesanan IN ('PENDING','PAID','READY_TO_PICKUP','COMPLETED','CANCELLED')),
  kode_pengambilan  CHAR(6) NOT NULL,
  kedaluwarsa_pada  TIMESTAMPTZ NOT NULL DEFAULT now() + interval '15 minutes',
  dibayar_pada      TIMESTAMPTZ,
  siap_pada         TIMESTAMPTZ,
  selesai_pada      TIMESTAMPTZ,
  dibatalkan_pada   TIMESTAMPTZ,
  PRIMARY KEY (id_pesanan, waktu_pesan),
  CHECK (kedaluwarsa_pada > waktu_pesan)
) PARTITION BY RANGE (waktu_pesan);
```

### 3.2.1 Pembentukan Partisi dan Penguncian Zona Waktu
Partisi bulanan dibentuk otomatis melalui blok PL/pgSQL deklaratif untuk rentang Januari 2026 hingga Maret 2027, disertai satu partisi penampung cadangan (`pesanan_default`):

```sql
DO $$
DECLARE
  m DATE := DATE '2026-01-01';
BEGIN
  WHILE m < DATE '2027-04-01' LOOP
    EXECUTE format(
      'CREATE TABLE %I PARTITION OF pesanan_danus FOR VALUES FROM (%L) TO (%L)',
      'pesanan_' || to_char(m, 'YYYY_MM'),
      m::timestamp AT TIME ZONE 'Asia/Jakarta',
      (m + interval '1 month')::timestamp AT TIME ZONE 'Asia/Jakarta'
    );
    m := (m + interval '1 month')::date;
  END LOOP;
END $$;

CREATE TABLE pesanan_default PARTITION OF pesanan_danus DEFAULT;
```

#### Keuntungan Arsitektur Partisi:
1. **Partition Pruning:** Ketika kueri mengeksekusi filter rentang tanggal tertentu (misal: rekapitulasi penjualan bulan Mei 2026), PostgreSQL Query Planner secara otomatis mengabaikan (*prune*) 10 partisi lainnya dan hanya memindai tabel `pesanan_2026_05`. Hal ini memangkas konsumsi I/O disk secara masif.
2. **Efisiensi Manajemen Siklus Hidup Data (*Data Lifecycle*):** Pengarsipan data lama tidak membutuhkan operasi `DELETE FROM` masif yang memicu *vacuum lock* dan fragmentasi tabel, melainkan cukup melepaskan partisi terkait menggunakan `ALTER TABLE ... DETACH PARTITION` atau `DROP TABLE`.
3. **Indeks Terlokalisasi:** Pohon B-Tree indeks sekunder dibangun mandiri pada setiap sub-tabel partisi, menghasilkan kedalaman pohon (*tree depth*) yang lebih dangkal dan muat sepenuhnya di dalam *buffer cache*.

---

## 3.3 Karakteristik Seeder Data Uji (105.000 Pesanan)

Pengujian optimasi kueri dan query planner hanya bermakna jika dataset uji merefleksikan karakteristik dunia nyata. Dataset yang seragam (*uniform distribution*) membuat selektivitas kueri menjadi artifisial sehingga pengujian indeks menjadi tidak realistis.

Oleh karena itu, dikembangkan skrip generator data berbasis Python di [seed/generate_data.py](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/seed/generate_data.py) menggunakan library `Faker('id_ID')` dan `psycopg`.

### 3.3.1 Prinsip Desain Dataset Realistis:
1. **Distribusi Miring (Pareto / Zipfian 80:20):**
   - 20% produk unggulan (misal: Mie Dok-dok Sosis Telur, Nasi Uduk Betawi, Risoles Mayo Beef Keju) diprogram untuk menerima 80% dari total kuantitas pemesanan.
   - 80% produk lainnya menampung sisa 20% transaksi.
   - Efek pada database: Menghasilkan kardinalitas data yang bervariasi tajam, memaksa query planner memilih antara *Index Scan*, *Bitmap Scan*, atau *Seq Scan* secara dinamis berdasarkan nilai parameter filter.
2. **Distribusi Waktu Berpuncak (*Temporal Clustering*):**
   - Transaksi pemesanan dikelompokkan dengan probabilitas 65% jatuh pada jendela jam makan siang kampus (10.00 – 13.00 WIB).
   - Waktu akhir pekan (hari Minggu) ditiadakan untuk mencerminkan dinamika kegiatan akademik kampus.
3. **Injeksi Berkecepatan Tinggi via `COPY`:**
   - Seluruh baris data dikonversi ke dalam tuple memori dan disalurkan ke PostgreSQL menggunakan perintah `COPY ... FROM STDIN`.
   - Sebanyak **$105.000$ baris pesanan** dan **$144.889$ detail pesanan** berhasil diinjeksi dalam waktu **19,64 detik** ($~12.700$ baris/detik).

---

### 3.3.2 Verifikasi Distribusi Baris Aktual pada Sub-Tabel Partisi

Setelah proses seeder selesai dan instruksi `ANALYZE;` dijalankan, dilakukan kueri verifikasi untuk memeriksa integritas penempatan baris pada sub-tabel partisi bulanan:

```sql
SELECT tableoid::regclass AS nama_partisi, count(*) AS jumlah_baris
  FROM pesanan_danus 
 GROUP BY tableoid::regclass 
 ORDER BY nama_partisi;
```

*Tabel 3.2 Distribusi Baris Aktual Transaksi pada Partisi Bulanan PostgreSQL.*

| Nama Sub-Tabel Partisi | Rentang Waktu Pemesanan (WIB) | Jumlah Baris Aktual | Persentase Volume |
| :--- | :---: | :---: | :---: |
| `pesanan_2026_01` | 01 Jan 2026 – 31 Jan 2026 | 8.467 | 8,06% |
| `pesanan_2026_02` | 01 Feb 2026 – 28 Feb 2026 | 9.056 | 8,62% |
| `pesanan_2026_03` | 01 Mar 2026 – 31 Mar 2026 | 9.305 | 8,86% |
| `pesanan_2026_04` | 01 Apr 2026 – 30 Apr 2026 | 10.281 | 9,79% |
| `pesanan_2026_05` | 01 Mei 2026 – 31 Mei 2026 | 10.178 | 9,69% |
| `pesanan_2026_06` | 01 Jun 2026 – 30 Jun 2026 | 9.523 | 9,07% |
| `pesanan_2026_07` | 01 Jul 2026 – 31 Jul 2026 | 10.560 | 10,06% |
| `pesanan_2026_08` | 01 Agu 2026 – 31 Agu 2026 | 9.999 | 9,52% |
| `pesanan_2026_09` | 01 Sep 2026 – 30 Sep 2026 | 10.734 | 10,22% |
| `pesanan_2026_10` | 01 Okt 2026 – 31 Okt 2026 | 9.492 | 9,04% |
| `pesanan_2026_11` | 01 Nov 2026 – 22 Nov 2026 | 7.405 | 7,05% |
| `pesanan_default` | Di luar rentang operasional | **0** | **0,00%** |
| **TOTAL** | **Januari – November 2026** | **105.000** | **100,00%** |

*Analisis Distribusi:*
Data terdistribusi merata setiap bulan dengan rata-rata ~9.500 transaksi per bulan. Nilai **0 baris pada `pesanan_default`** membuktikan bahwa seluruh $105.000$ transaksi memiliki penanda waktu valid yang presisi berada di dalam rentang partisi operasional WIB.

---

## 3.4 Kesimpulan Bab 3

Implementasi fisik dan dataset DanusGo telah mencapai kesiapan penuh untuk pengujian kinerja basis data:
1. **Penegakan Aturan Ketat:** *Exclusion Constraint* (GIST) dan *Check Constraint* berhasil mengunci integritas jadwal stan fisik dan domain harga di tingkat mesin PostgreSQL.
2. **Skalabilitas Partisi:** Skema *Range Partitioning* bulanan terbukti sukses merutekan $105.000$ transaksi ke masing-masing partisi bulanan tanpa anomali.
3. **Realisme Dataset:** Karakteristik data miring Pareto dan lonjakan waktu transaksional menyediakan lingkungan pengujian empiris yang sangat representatif untuk analisis pengindeksan dan optimasi kueri pada bab-bab selanjutnya.
