-- =====================================================================
-- DanusGo: 05_partition.sql  (Bab 9: Basis Data Paralel dan Partisi)
-- Membandingkan:
--   1. Range Partitioning (pesanan_danus) vs Hash Partitioning (pesanan_hash) vs Non-Partitioned (pesanan_flat)
--   2. Partition Pruning pada Kueri Waktu vs Kueri Entitas
--   3. Skalabilitas Kueri Paralel (max_parallel_workers_per_gather = 0, 2, 4)
-- =====================================================================
\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------
-- 1. Baseline: Tabel Non-Partitioned
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pesanan_flat (
  id_pesanan        BIGINT,
  id_mahasiswa      INT NOT NULL,
  id_sesi           INT NOT NULL,
  waktu_pesan       TIMESTAMPTZ NOT NULL,
  metode_bayar      TEXT NOT NULL,
  status_pesanan    TEXT NOT NULL,
  kode_pengambilan  CHAR(6) NOT NULL,
  PRIMARY KEY (id_pesanan, waktu_pesan)
);

-- ---------------------------------------------------------------------
-- 2. Komparasi: Hash Partitioning by id_mahasiswa (4 partisi)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pesanan_hash (
  id_pesanan        BIGINT,
  id_mahasiswa      INT NOT NULL,
  id_sesi           INT NOT NULL,
  waktu_pesan       TIMESTAMPTZ NOT NULL,
  metode_bayar      TEXT NOT NULL,
  status_pesanan    TEXT NOT NULL,
  kode_pengambilan  CHAR(6) NOT NULL,
  PRIMARY KEY (id_pesanan, id_mahasiswa)
) PARTITION BY HASH (id_mahasiswa);

CREATE TABLE IF NOT EXISTS pesanan_hash_p0 PARTITION OF pesanan_hash FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE IF NOT EXISTS pesanan_hash_p1 PARTITION OF pesanan_hash FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE IF NOT EXISTS pesanan_hash_p2 PARTITION OF pesanan_hash FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE IF NOT EXISTS pesanan_hash_p3 PARTITION OF pesanan_hash FOR VALUES WITH (MODULUS 4, REMAINDER 3);

-- ---------------------------------------------------------------------
-- 3. Populasi Data Eksperimen dari pesanan_danus
-- ---------------------------------------------------------------------
TRUNCATE TABLE pesanan_flat;
INSERT INTO pesanan_flat (id_pesanan, id_mahasiswa, id_sesi, waktu_pesan, metode_bayar, status_pesanan, kode_pengambilan)
SELECT id_pesanan, id_mahasiswa, id_sesi, waktu_pesan, metode_bayar, status_pesanan, kode_pengambilan
FROM pesanan_danus;

TRUNCATE TABLE pesanan_hash;
INSERT INTO pesanan_hash (id_pesanan, id_mahasiswa, id_sesi, waktu_pesan, metode_bayar, status_pesanan, kode_pengambilan)
SELECT id_pesanan, id_mahasiswa, id_sesi, waktu_pesan, metode_bayar, status_pesanan, kode_pengambilan
FROM pesanan_danus;

-- Pastikan statistik planner terbarui
ANALYZE pesanan_flat;
ANALYZE pesanan_hash;
ANALYZE pesanan_danus;
