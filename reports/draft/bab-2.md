# BAB 2. KUERI SQL TINGKAT LANJUT DAN KONTROL TRANSAKSI ATOMIK

## 2.1 Analisis Masalah Concurrency dan Anatomi Fenomena Overselling

Dalam sistem transaksi perdagangan daring (*e-commerce*) dengan kuota persediaan terbatas, penanganan konkurensi merupakan tantangan krusial. Pada platform DanusGo, mahasiswa menjual produk makanan basah dengan masa kedaluwarsa singkat dan kapasitas produksi harian terbatas (misal: 50 porsi risoles per sesi jualan). Jika sistem mengizinkan pemesanan melebihi kuota fisik yang ada, terjadi fenomena **overselling** yang melanggar kontrak bisnis (*Business Rule* BR-01 dan Kriteria K1).

### 2.1.1 Anatomi Kegagalan Pola Transaksi Naif (*Lost Update*)
Pola pemrograman basis data konvensional (naif) umumnya memecah alur pemesanan menjadi beberapa langkah terpisah:
1. **Langkah 1 (Read):** Aplikasi membaca sisa kuota saat ini:
   ```sql
   SELECT kuota_sisa FROM sesi_produk WHERE id_sesi_produk = 10;
   ```
2. **Langkah 2 (App-level Check):** Aplikasi memeriksa nilai di memori: `if (kuota_sisa >= jumlah_pesan)`.
3. **Langkah 3 (Write):** Aplikasi melakukan pembaruan kuota:
   ```sql
   UPDATE sesi_produk SET kuota_sisa = kuota_sisa - jumlah_pesan WHERE id_sesi_produk = 10;
   ```

*Masalah Race Condition:*
Pada tingkat isolasi standar (*Read Committed*), PostgreSQL tidak mengunci baris saat operasi `SELECT` biasa dijalankan. Apabila terdapat 200 koneksi pengguna konkuren yang mengakses sistem secara serentak pada produk berkuota 50:
- Puluhan transaksi konkuren akan mengeksekusi Langkah 1 secara bersamaan.
- Seluruh transaksi tersebut membaca nilai yang sama, yaitu `kuota_sisa = 50`.
- Seluruh transaksi mengevaluasi bahwa kuota masih mencukupi (`50 >= 1`).
- Seluruh transaksi secara bergantian mengeksekusi Langkah 3 (`UPDATE`).

Dampaknya adalah terjadinya anomali *Lost Update*. Nilai kuota terpotong berulang kali melebihi batas fisik hingga mencapai angka negatif (misal: $-150$), dan sistem mengonfirmasi 200 pesanan padahal barang yang tersedia hanya 50 porsi.

---

### 2.1.2 Desain Transaksi Atomik dengan Row-Level Locking Anti-Overselling

Untuk mengeliminasi risiko *race condition* secara deterministik, DanusGo menerapkan mekanisme **Atomic Conditional Update** yang dipadukan dengan penguncian tingkat baris (*Row-Level Locking*) langsung di dalam mesin basis data PostgreSQL melalui fungsi tersimpan (*stored function*) PL/pgSQL `sp_buat_pesanan`.

Inti mekanisme anti-*overselling* terletak pada penyatuan operasi evaluasi kondisi dan pemotongan stok ke dalam satu instruksi DML atomik tunggal:

```sql
UPDATE sesi_produk
   SET kuota_sisa = kuota_sisa - p_jumlah,
       status_stok = CASE WHEN (kuota_sisa - p_jumlah) = 0 THEN 'SOLD_OUT' ELSE status_stok END
 WHERE id_sesi_produk = p_id_sesi_produk
   AND id_sesi = p_id_sesi
   AND kuota_sisa >= p_jumlah
RETURNING kuota_sisa, id_produk INTO v_kuota_sisa, v_id_produk;
```

#### Cara Kerja Mesin PostgreSQL pada Operasi Ini:
1. **Pemerolehan Kunci Baris Eksklusif (*Exclusive Row Lock*):** Transaksi pertama yang menyentuh baris `sesi_produk` terkait akan secara otomatis memperoleh *Exclusive Row-Level Lock* (`FOR UPDATE`).
2. **Antrean Transaksi Konkuren:** Transaksi-transaksi konkuren lainnya yang mencoba memodifikasi baris yang sama akan dipaksa menunggu (*blocked*) hingga transaksi pertama melakukan `COMMIT` atau `ROLLBACK`.
3. **Pengecekan Ulang Syarat (*Re-evaluating Qualification Condition*):** Ketika transaksi antrean memperoleh giliran, PostgreSQL akan membaca *snapshot* tuple teranyar hasil modifikasi transaksi sebelumnya. Klausul `AND kuota_sisa >= p_jumlah` dievaluasi ulang terhadap nilai sisa kuota yang baru.
4. **Penolakan Deterministik:** Ketika kuota telah habis (`kuota_sisa = 0`), klausa `WHERE kuota_sisa >= p_jumlah` bernilai salah (`FALSE`). Perintah `UPDATE` mengembalikan 0 baris (`v_kuota_sisa IS NULL`). Sistem segera membangkitkan eksepsi `KUOTA_TIDAK_MENCUKUPI` (SQLSTATE `P0001`), dan transaksi otomatis dibatalkan (*ROLLBACK*).

---

### 2.1.3 Pembangkitan Kode Pengambilan Unik Per Sesi (BR-15)

Sesuai aturan bisnis BR-15, setiap pesanan yang sah wajib memiliki kode pengambilan fisik 6-karakter alfanumerik (misal: `PS7JYC`). Kode ini digunakan oleh pembeli saat mengambil makanan di stan fisik.

Untuk mencegah duplikasi antar-pesanan dalam sesi jualan yang sama, fungsi transaksi melakukan *looping check* di dalam blok transaksional menggunakan karakter yang bebas dari ambiguitas visual (meniadakan karakter `0`, `O`, `1`, `I`):

```sql
v_chars := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
LOOP
    v_kode := '';
    FOR v_i IN 1..6 LOOP
        v_kode := v_kode || substr(v_chars, floor(random() * length(v_chars) + 1)::INT, 1);
    END LOOP;

    SELECT EXISTS (
        SELECT 1 FROM pesanan_danus
         WHERE id_sesi = p_id_sesi AND kode_pengambilan = v_kode
    ) INTO v_exists;

    EXIT WHEN NOT v_exists;
END LOOP;
```

---

### 2.1.4 Implementasi Lengkap Stored Function Transaksional

Seluruh logika di atas dirangkum dalam fungsi terintegrasi pada berkas [db/03_queries.sql](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/db/03_queries.sql):

```sql
CREATE OR REPLACE FUNCTION sp_buat_pesanan(
    p_id_mahasiswa   INT,
    p_id_sesi        INT,
    p_id_sesi_produk INT,
    p_jumlah         INT,
    p_id_varian      INT DEFAULT NULL,
    p_id_pickup      INT DEFAULT NULL,
    p_metode_bayar   TEXT DEFAULT 'CASH_COD'
)
RETURNS TABLE (
    r_id_pesanan       BIGINT,
    r_waktu_pesan      TIMESTAMPTZ,
    r_kode_pengambilan CHAR(6),
    r_kuota_sisa       INT,
    r_total_bayar      NUMERIC(10,2)
) AS $$
DECLARE
    v_kuota_sisa       INT;
    v_id_produk        INT;
    v_harga_jual       NUMERIC(10,2);
    v_harga_modal      NUMERIC(10,2);
    v_kode             CHAR(6);
    v_id_pesanan       BIGINT;
    v_waktu_pesan      TIMESTAMPTZ;
    v_status_sesi      TEXT;
    v_chars            TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    v_i                INT;
    v_exists           BOOLEAN;
BEGIN
    IF p_jumlah <= 0 THEN
        RAISE EXCEPTION 'JUMLAH_TIDAK_VALID' USING ERRCODE = '22023';
    END IF;

    SELECT status_sesi INTO v_status_sesi
      FROM sesi_jualan WHERE id_sesi = p_id_sesi;

    IF v_status_sesi IS NULL THEN
        RAISE EXCEPTION 'SESI_TIDAK_DITEMUKAN' USING ERRCODE = '02000';
    ELSIF v_status_sesi = 'CLOSED' THEN
        RAISE EXCEPTION 'SESI_TIDAK_BUKA' USING ERRCODE = '22000';
    END IF;

    -- Update atomik pemotongan kuota
    UPDATE sesi_produk
       SET kuota_sisa = kuota_sisa - p_jumlah,
           status_stok = CASE WHEN (kuota_sisa - p_jumlah) = 0 THEN 'SOLD_OUT' ELSE status_stok END
     WHERE id_sesi_produk = p_id_sesi_produk
       AND id_sesi = p_id_sesi
       AND kuota_sisa >= p_jumlah
    RETURNING kuota_sisa, id_produk INTO v_kuota_sisa, v_id_produk;

    IF v_kuota_sisa IS NULL THEN
        RAISE EXCEPTION 'KUOTA_TIDAK_MENCUKUPI' USING ERRCODE = 'P0001';
    END IF;

    SELECT harga_jual, harga_modal INTO v_harga_jual, v_harga_modal
      FROM produk_danus WHERE id_produk = v_id_produk;

    -- Pembangkitan kode pengambilan unik
    LOOP
        v_kode := '';
        FOR v_i IN 1..6 LOOP
            v_kode := v_kode || substr(v_chars, floor(random() * length(v_chars) + 1)::INT, 1);
        END LOOP;
        SELECT EXISTS (
            SELECT 1 FROM pesanan_danus
             WHERE id_sesi = p_id_sesi AND kode_pengambilan = v_kode
        ) INTO v_exists;
        EXIT WHEN NOT v_exists;
    END LOOP;

    v_waktu_pesan := clock_timestamp();

    -- Injeksi header transaksi
    INSERT INTO pesanan_danus (
        id_mahasiswa, id_sesi, waktu_pesan, metode_bayar,
        status_pesanan, kode_pengambilan, kedaluwarsa_pada
    ) VALUES (
        p_id_mahasiswa, p_id_sesi, v_waktu_pesan, p_metode_bayar,
        'PENDING', v_kode, v_waktu_pesan + interval '15 minutes'
    ) RETURNING id_pesanan INTO v_id_pesanan;

    -- Injeksi rincian barang
    INSERT INTO detail_pesanan (
        id_pesanan, waktu_pesan, id_sesi_produk, id_varian, id_pickup,
        jumlah_item, harga_satuan, harga_modal_satuan
    ) VALUES (
        v_id_pesanan, v_waktu_pesan, p_id_sesi_produk, p_id_varian, p_id_pickup,
        p_jumlah, v_harga_jual, v_harga_modal
    );

    -- Catat jejak mutasi kuota
    INSERT INTO log_kuota (id_sesi_produk, id_pesanan, delta, alasan, waktu)
    VALUES (p_id_sesi_produk, v_id_pesanan, -p_jumlah, 'PEMESANAN', v_waktu_pesan);

    r_id_pesanan       := v_id_pesanan;
    r_waktu_pesan      := v_waktu_pesan;
    r_kode_pengambilan := v_kode;
    r_kuota_sisa       := v_kuota_sisa;
    r_total_bayar      := (v_harga_jual * p_jumlah);
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;
```

#### Bukti Verifikasi Eksekusi Nyata pada Basis Data:
```sql
SELECT * FROM sp_buat_pesanan(
    p_id_mahasiswa := 2,
    p_id_sesi := 7974,
    p_id_sesi_produk := 24001,
    p_jumlah := 2,
    p_metode_bayar := 'CASH_COD'
);
```

*Tabel 2.1 Luaran Transaksi Pemesanan Nyata `sp_buat_pesanan`.*

| r_id_pesanan | r_waktu_pesan | r_kode_pengambilan | r_kuota_sisa | r_total_bayar | Status Verifikasi |
| :---: | :---: | :---: | :---: | :---: | :--- |
| `105002` | `2026-11-22 22:31:52+07` | `PS7JYC` | `63` | Rp20.000,00 | Sukses (Kuota awal 65 berkurang tepat 2) |

---

## 2.2 Implementasi Kueri Analisis SQL Tingkat Lanjut

Untuk memenuhi kebutuhan analitik bisnis dan evaluasi akademis Bab 2, dirancang empat kueri analitis kompleks yang telah diuji langsung pada dataset $105.000$ transaksi.

### 2.2.1 Common Table Expressions (CTE): Rekapitulasi Finansial Seller
Kueri ini menghitung performa penjualan, total modal belanja, laba bersih, dan persentase margin keuntungan untuk setiap sesi jualan organisasi kemahasiswaan:

```sql
WITH rekap_item AS (
    SELECT dp.id_pesanan,
           dp.waktu_pesan,
           SUM(dp.jumlah_item * dp.harga_satuan)       AS total_omzet,
           SUM(dp.jumlah_item * dp.harga_modal_satuan) AS total_modal
      FROM detail_pesanan dp
     GROUP BY dp.id_pesanan, dp.waktu_pesan
),
rekap_sesi AS (
    SELECT p.id_sesi,
           COUNT(DISTINCT p.id_pesanan) AS jumlah_transaksi_sukses,
           SUM(ri.total_omzet)          AS omzet_sesi,
           SUM(ri.total_modal)          AS modal_sesi,
           SUM(ri.total_omzet - ri.total_modal) AS laba_sesi
      FROM pesanan_danus p
      JOIN rekap_item ri ON p.id_pesanan = ri.id_pesanan AND p.waktu_pesan = ri.waktu_pesan
     WHERE p.status_pesanan = 'COMPLETED'
     GROUP BY p.id_sesi
)
SELECT s.id_sesi,
       s.tanggal_jualan,
       org.nama_organisasi,
       org.nama_proker,
       COALESCE(rs.jumlah_transaksi_sukses, 0) AS total_pesanan,
       COALESCE(rs.omzet_sesi, 0)              AS omzet_kotor,
       COALESCE(rs.laba_sesi, 0)               AS laba_bersih,
       ROUND(
           CASE WHEN COALESCE(rs.omzet_sesi, 0) > 0
                THEN (rs.laba_sesi / rs.omzet_sesi) * 100
                ELSE 0
           END, 2
       ) AS margin_laba_persen
  FROM sesi_jualan s
  JOIN organisasi_danus org ON s.id_organisasi = org.id_organisasi
  LEFT JOIN rekap_sesi rs ON s.id_sesi = rs.id_sesi
 ORDER BY laba_bersih DESC
 LIMIT 3;
```

*Tabel 2.2 Hasil Eksekusi Riil Kueri CTE Rekapitulasi Finansial.*

| id_sesi | tanggal_jualan | nama_organisasi | total_pesanan | omzet_kotor | laba_bersih | margin_laba_persen |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| `7896` | 2026-11-18 | Himpunan Mahasiswa Biologi | 25 | Rp1.440.000,00 | Rp576.000,00 | 40,00% |
| `5819` | 2026-08-27 | Himpunan Mahasiswa Biologi | 21 | Rp1.440.000,00 | Rp576.000,00 | 40,00% |
| `1425` | 2026-03-03 | Himpunan Mahasiswa Biologi | 26 | Rp1.415.000,00 | Rp570.000,00 | 40,28% |

---

### 2.2.2 Correlated Subquery: Mahasiswa Buyer Prioritas
Kueri ini menyaring mahasiswa yang memiliki loyalitas belanja tinggi, di mana total nilai belanjanya melampaui nilai rata-rata belanja seluruh mahasiswa yang berasal dari program studi yang sama:

```sql
SELECT u.id_mahasiswa,
       u.nama,
       pr.nama_prodi,
       SUM(dp.jumlah_item * dp.harga_satuan) AS total_pengeluaran_mhs
  FROM pengguna u
  JOIN prodi pr ON u.id_prodi = pr.id_prodi
  JOIN pesanan_danus p ON u.id_mahasiswa = p.id_mahasiswa
  JOIN detail_pesanan dp ON p.id_pesanan = dp.id_pesanan AND p.waktu_pesan = dp.waktu_pesan
 WHERE p.status_pesanan = 'COMPLETED'
 GROUP BY u.id_mahasiswa, u.nama, pr.nama_prodi, u.id_prodi
HAVING SUM(dp.jumlah_item * dp.harga_satuan) > (
    -- Subquery berkorelasi terikat pada u.id_prodi baris luar
    SELECT AVG(sub.total_mhs)
      FROM (
          SELECT p2.id_mahasiswa,
                 SUM(dp2.jumlah_item * dp2.harga_satuan) AS total_mhs
            FROM pesanan_danus p2
            JOIN detail_pesanan dp2 ON p2.id_pesanan = dp2.id_pesanan AND p2.waktu_pesan = dp2.waktu_pesan
            JOIN pengguna u2 ON p2.id_mahasiswa = u2.id_mahasiswa
           WHERE u2.id_prodi = u.id_prodi
             AND p2.status_pesanan = 'COMPLETED'
           GROUP BY p2.id_mahasiswa
      ) sub
)
ORDER BY total_pengeluaran_mhs DESC
LIMIT 3;
```

*Tabel 2.3 Hasil Eksekusi Riil Kueri Correlated Subquery Buyer Prioritas.*

| id_mahasiswa | nama mahasiswa | program studi | total_pengeluaran_mhs |
| :---: | :--- | :--- | :---: |
| `1483` | Dr. Tami Usamah | Teknik Informatika | Rp1.584.000,00 |
| `3803` | Daliono Prasetyo | Sastra Inggris | Rp1.542.000,00 |
| `4542` | Salwa Safitri | Teknik Sipil | Rp1.478.000,00 |

---

### 2.2.3 Window Functions: Peringkat Produk Terlaris dan Running Total
Kueri ini memanfaatkan fungsi jendela `DENSE_RANK() OVER (PARTITION BY ...)` untuk memberikan peringkat penjualan produk tanpa menghilangkan detail kategori, serta `SUM() OVER (...)` untuk menghitung akumulasi omzet berjalan:

```sql
WITH produk_terjual AS (
    SELECT pr.kategori,
           pr.id_produk,
           pr.nama_produk,
           SUM(dp.jumlah_item)                   AS total_kuantitas_terjual,
           SUM(dp.jumlah_item * dp.harga_satuan) AS total_omzet_produk
      FROM detail_pesanan dp
      JOIN sesi_produk sp ON dp.id_sesi_produk = sp.id_sesi_produk
      JOIN produk_danus pr ON sp.id_produk = pr.id_produk
      JOIN pesanan_danus p ON dp.id_pesanan = p.id_pesanan AND dp.waktu_pesan = p.waktu_pesan
     WHERE p.status_pesanan = 'COMPLETED'
     GROUP BY pr.kategori, pr.id_produk, pr.nama_produk
)
SELECT kategori,
       nama_produk,
       total_kuantitas_terjual,
       total_omzet_produk,
       DENSE_RANK() OVER (
           PARTITION BY kategori
           ORDER BY total_kuantitas_terjual DESC
       ) AS peringkat_kategori,
       SUM(total_omzet_produk) OVER (
           PARTITION BY kategori
           ORDER BY total_kuantitas_terjual DESC
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS omzet_kumulatif_kategori
  FROM produk_terjual
 WHERE kategori = 'MAKANAN_BERAT'
 ORDER BY peringkat_kategori
 LIMIT 3;
```

*Tabel 2.4 Hasil Eksekusi Riil Window Functions Peringkat Penjualan Makanan Berat.*

| kategori | nama_produk | kuantitas terjual | total omzet | peringkat | omzet kumulatif |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `MAKANAN_BERAT` | Mie Dok-dok Spesial Sosis Telur | 2.502 porsi | Rp35.028.000,00 | **1** | Rp35.028.000,00 |
| `MAKANAN_BERAT` | Nasi Uduk Betawi Semur Tahu | 2.285 porsi | Rp27.420.000,00 | **2** | Rp62.448.000,00 |
| `MAKANAN_BERAT` | Rice Bowl Daging Sapi Lada Hitam | 2.171 porsi | Rp52.104.000,00 | **3** | Rp114.552.000,00 |

---

### 2.2.4 Recursive CTE: Penelusuran Pohon Relasi Komunitas Kampus
Kueri rekursif digunakan untuk menelusuri bagan struktur hierarkis organisasi kemahasiswaan dan fakultas induknya, membentuk jalur penelusuran (*path*) dari tingkat atas ke tingkat bawah:

```sql
WITH RECURSIVE hierarki_danus AS (
    -- Tingkat 1: Fakultas (Anchor Member)
    SELECT f.id_fakultas,
           NULL::INT AS id_organisasi,
           f.nama_fakultas::TEXT AS entitas,
           'FAKULTAS'::TEXT AS level_entitas,
           1 AS tingkat,
           f.nama_fakultas::TEXT AS jalur_koordinasi
      FROM fakultas f
     WHERE f.nama_fakultas <> 'Area Umum'

    UNION ALL

    -- Tingkat 2: Organisasi Kemahasiswaan di Bawah Fakultas (Recursive Member)
    SELECT od.id_fakultas_induk,
           od.id_organisasi,
           od.nama_organisasi::TEXT AS entitas,
           'ORGANISASI'::TEXT AS level_entitas,
           h.tingkat + 1 AS tingkat,
           (h.jalur_koordinasi || ' -> ' || od.nama_organisasi)::TEXT
      FROM organisasi_danus od
      JOIN hierarki_danus h ON od.id_fakultas_induk = h.id_fakultas
     WHERE h.level_entitas = 'FAKULTAS'
)
SELECT id_fakultas, entitas, level_entitas, tingkat, jalur_koordinasi
  FROM hierarki_danus
 ORDER BY id_fakultas, tingkat, entitas
 LIMIT 6;
```

*Tabel 2.5 Hasil Eksekusi Riil Recursive CTE Penelusuran Hierarki.*

| id_fakultas | entitas | level_entitas | tingkat | jalur_koordinasi |
| :---: | :--- | :---: | :---: | :--- |
| `2` | Teknik | FAKULTAS | 1 | Teknik |
| `2` | BEM Fakultas Teknik | ORGANISASI | 2 | Teknik -> BEM Fakultas Teknik |
| `2` | Himpunan Mahasiswa Elektro | ORGANISASI | 2 | Teknik -> Himpunan Mahasiswa Elektro |
| `2` | Himpunan Mahasiswa Informatika | ORGANISASI | 2 | Teknik -> Himpunan Mahasiswa Informatika |
| `2` | Himpunan Mahasiswa Mesin | ORGANISASI | 2 | Teknik -> Himpunan Mahasiswa Mesin |
| `2` | Himpunan Mahasiswa Sipil | ORGANISASI | 2 | Teknik -> Himpunan Mahasiswa Sipil |

---

## 2.3 Kesimpulan Bab 2

Penerapan logika transaksional dan kueri analitis SQL lanjut pada DanusGo membuktikan bahwa:
1. **Integritas Stok Terjamin:** Operasi pemesanan atomik berbasis *row-level locking conditional update* terbukti secara matematis dan empiris mampu mencegah anomali *overselling*, sekaligus secara otomatis menghasilkan kode pengambilan unik dan catatan audit stok.
2. **Kekayaan Analitis:** Empat teknik kueri tingkat lanjut (CTE, Correlated Subquery, Window Functions, dan Recursive CTE) berhasil menyajikan agregasi finansial terstruktur dan analisis performa dari ratusan ribu baris data transaksional dengan performa eksekusi yang optimal.
