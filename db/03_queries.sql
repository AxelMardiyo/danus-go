-- =====================================================================
-- DanusGo: 03_queries.sql  (Bab 2: SQL Lanjut & Logika Transaksional)
-- Mencakup:
-- 1. Fungsi Pemesanan Atomik Anti-Overselling (sp_buat_pesanan)
-- 2. Fungsi Pemesanan Naif untuk Uji Komparasi Concurrency (sp_buat_pesanan_naif)
-- 3. Kueri Analisis Lanjut: CTE Finansial, Correlated Subquery, Window Function, Recursive CTE
-- =====================================================================
\set ON_ERROR_STOP on

-- =====================================================================
-- 1. FUNGSI PEMESANAN ATOMIK ANTI-OVERSELLING
-- Mencegah overselling secara deterministik di level database engine
-- dengan row-level locking conditional UPDATE (BR-01, K1).
-- =====================================================================
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
    v_chars            TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; -- Tanpa karakter ambigu (I, O, 0, 1)
    v_i                INT;
    v_exists           BOOLEAN;
BEGIN
    -- Validasi kuantitas item
    IF p_jumlah <= 0 THEN
        RAISE EXCEPTION 'JUMLAH_TIDAK_VALID: Jumlah pemesanan minimal 1'
            USING ERRCODE = '22023';
    END IF;

    -- Validasi status sesi jualan
    SELECT status_sesi INTO v_status_sesi
      FROM sesi_jualan
     WHERE id_sesi = p_id_sesi;

    IF v_status_sesi IS NULL THEN
        RAISE EXCEPTION 'SESI_TIDAK_DITEMUKAN: Sesi ID % tidak ditemukan', p_id_sesi
            USING ERRCODE = '02000';
    ELSIF v_status_sesi = 'CLOSED' THEN
        RAISE EXCEPTION 'SESI_TIDAK_BUKA: Sesi jualan telah ditutup'
            USING ERRCODE = '22000';
    END IF;

    -- -----------------------------------------------------------------
    -- OPERASI ATOMIK POTONG KUOTA (ROW-LEVEL LOCKING & CONDITIONAL UPDATE)
    -- Perintah UPDATE bersyarat ini memegang exclusive lock pada baris
    -- sesi_produk terkait. Transaksi konkuren akan antre dan membaca
    -- nilai kuota_sisa teranyar.
    -- -----------------------------------------------------------------
    UPDATE sesi_produk
       SET kuota_sisa = kuota_sisa - p_jumlah,
           status_stok = CASE WHEN (kuota_sisa - p_jumlah) = 0 THEN 'SOLD_OUT' ELSE status_stok END
     WHERE id_sesi_produk = p_id_sesi_produk
       AND id_sesi = p_id_sesi
       AND kuota_sisa >= p_jumlah
    RETURNING kuota_sisa, id_produk INTO v_kuota_sisa, v_id_produk;

    -- Jika 0 baris terpengaruh (kuota tidak mencukupi atau produk bukan milik sesi ini)
    IF v_kuota_sisa IS NULL THEN
        RAISE EXCEPTION 'KUOTA_TIDAK_MENCUKUPI: Sisa kuota tidak mencukupi untuk kuantitas yang diminta'
            USING ERRCODE = 'P0001';
    END IF;

    -- Ambil harga modal dan harga jual terkini
    SELECT harga_jual, harga_modal
      INTO v_harga_jual, v_harga_modal
      FROM produk_danus
     WHERE id_produk = v_id_produk;

    -- -----------------------------------------------------------------
    -- PEMBANGKITAN KODE PENGAMBILAN UNIK PER SESI (BR-15)
    -- -----------------------------------------------------------------
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

    -- -----------------------------------------------------------------
    -- PENYISIPAN HEADER PESANAN & DETAIL PESANAN
    -- -----------------------------------------------------------------
    v_waktu_pesan := clock_timestamp();

    INSERT INTO pesanan_danus (
        id_mahasiswa, id_sesi, waktu_pesan, metode_bayar,
        status_pesanan, kode_pengambilan, kedaluwarsa_pada
    ) VALUES (
        p_id_mahasiswa, p_id_sesi, v_waktu_pesan, p_metode_bayar,
        'PENDING', v_kode, v_waktu_pesan + interval '15 minutes'
    )
    RETURNING id_pesanan INTO v_id_pesanan;

    INSERT INTO detail_pesanan (
        id_pesanan, waktu_pesan, id_sesi_produk, id_varian, id_pickup,
        jumlah_item, harga_satuan, harga_modal_satuan
    ) VALUES (
        v_id_pesanan, v_waktu_pesan, p_id_sesi_produk, p_id_varian, p_id_pickup,
        p_jumlah, v_harga_jual, v_harga_modal
    );

    -- Audit jejak mutasi kuota
    INSERT INTO log_kuota (id_sesi_produk, id_pesanan, delta, alasan, waktu)
    VALUES (p_id_sesi_produk, v_id_pesanan, -p_jumlah, 'PEMESANAN', v_waktu_pesan);

    -- Kembalikan informasi transaksi
    r_id_pesanan       := v_id_pesanan;
    r_waktu_pesan      := v_waktu_pesan;
    r_kode_pengambilan := v_kode;
    r_kuota_sisa       := v_kuota_sisa;
    r_total_bayar      := (v_harga_jual * p_jumlah);
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;


-- =====================================================================
-- 2. VERSI NAIF (UNTUK SIMULASI KOMPARASI OVERSELLING / RACE CONDITION)
-- Menggunakan pola SELECT then UPDATE terpisah tanpa exclusive lock.
-- =====================================================================
CREATE OR REPLACE FUNCTION sp_buat_pesanan_naif(
    p_id_mahasiswa   INT,
    p_id_sesi        INT,
    p_id_sesi_produk INT,
    p_jumlah         INT
)
RETURNS TABLE (
    r_id_pesanan BIGINT,
    r_kuota_sisa INT
) AS $$
DECLARE
    v_sisa INT;
    v_id_pesanan BIGINT;
    v_waktu TIMESTAMPTZ := clock_timestamp();
    v_kode CHAR(6) := 'NAIF01';
BEGIN
    -- Langkah 1: Baca sisa kuota (non-atomic, rentan race condition)
    SELECT kuota_sisa INTO v_sisa
      FROM sesi_produk
     WHERE id_sesi_produk = p_id_sesi_produk;

    -- Jeda artifisial mikrodetik untuk memperbesar jendela konkurensi (Lost Update)
    PERFORM pg_sleep(0.005);

    -- Langkah 2: Evaluasi di memori aplikasi lalu update tanpa klausa WHERE kuota_sisa >= p_jumlah
    IF v_sisa >= p_jumlah THEN
        UPDATE sesi_produk
           SET kuota_sisa = kuota_sisa - p_jumlah
         WHERE id_sesi_produk = p_id_sesi_produk
        RETURNING kuota_sisa INTO v_sisa;

        INSERT INTO pesanan_danus (
            id_mahasiswa, id_sesi, waktu_pesan, metode_bayar,
            status_pesanan, kode_pengambilan, kedaluwarsa_pada
        ) VALUES (
            p_id_mahasiswa, p_id_sesi, v_waktu, 'CASH_COD',
            'PENDING', v_kode, v_waktu + interval '15 minutes'
        ) RETURNING id_pesanan INTO v_id_pesanan;

        r_id_pesanan := v_id_pesanan;
        r_kuota_sisa := v_sisa;
        RETURN NEXT;
    ELSE
        RAISE EXCEPTION 'KUOTA_HABIS';
    END IF;
END;
$$ LANGUAGE plpgsql;


-- =====================================================================
-- 3. KUERI ANALISIS SQL TINGKAT LANJUT
-- =====================================================================

-- ---------------------------------------------------------------------
-- 3.1 COMMON TABLE EXPRESSIONS (CTE)
-- Rekapitulasi Finansial Seller: Omzet Kotor, Modal, Laba Bersih & Margin Laba
-- ---------------------------------------------------------------------
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
 LIMIT 20;


-- ---------------------------------------------------------------------
-- 3.2 CORRELATED SUBQUERY
-- Mahasiswa Buyer Prioritas: Total Belanja di Atas Rata-rata Mahasiswa Se-Prodinya
-- ---------------------------------------------------------------------
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
    -- Subquery berkorelasi: menghitung rata-rata belanja mahasiswa di prodi yang sama
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
LIMIT 25;


-- ---------------------------------------------------------------------
-- 3.3 WINDOW FUNCTIONS
-- Peringkat Produk Terlaris per Kategori (DENSE_RANK) dan Running Total Omzet
-- ---------------------------------------------------------------------
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
 ORDER BY kategori, peringkat_kategori;


-- ---------------------------------------------------------------------
-- 3.4 RECURSIVE CTE
-- Penelusuran Hierarki Koordinasi Fakultas, Organisasi Danus, dan Seller Aktif
-- ---------------------------------------------------------------------
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

    -- Tingkat 2: Organisasi Danus di Bawah Fakultas (Recursive Member)
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
SELECT * FROM hierarki_danus
 ORDER BY id_fakultas, tingkat, entitas;
