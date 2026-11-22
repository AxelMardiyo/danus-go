-- =====================================================================
-- DanusGo: 06_dw_schema.sql  (Bab 13: Data Warehouse dan OLAP)
-- Star schema di skema `dw`, database yang sama dengan operasional.
-- Grain fakta: satu baris per item pesanan berstatus COMPLETED.
-- Tabel dibuat kosong; dimensi waktu dan jam diisi otomatis di sini.
-- ETL (isi dim_spot, dim_organisasi, dim_produk, fakta) ditulis oleh peran #8.
-- =====================================================================
\set ON_ERROR_STOP on

CREATE SCHEMA IF NOT EXISTS dw;

-- ---------------------------------------------------------------------
-- Dimensi
-- ---------------------------------------------------------------------
CREATE TABLE dw.dim_waktu (
  id_waktu       INT PRIMARY KEY,            -- format YYYYMMDD
  tanggal        DATE NOT NULL UNIQUE,
  hari           TEXT NOT NULL,              -- Senin..Minggu
  bulan          INT  NOT NULL CHECK (bulan BETWEEN 1 AND 12),
  kuartal        INT  NOT NULL CHECK (kuartal BETWEEN 1 AND 4),
  tahun          INT  NOT NULL,
  is_hari_kuliah BOOLEAN NOT NULL            -- Senin-Jumat (libur akademik belum dimodelkan)
);

CREATE TABLE dw.dim_jam (
  id_jam     INT PRIMARY KEY,                -- jam*100 + menit_slot, mis. 1130
  jam        INT NOT NULL CHECK (jam BETWEEN 0 AND 23),
  menit_slot INT NOT NULL CHECK (menit_slot IN (0, 30)),
  label      TEXT NOT NULL
);

CREATE TABLE dw.dim_spot (
  id_spot_dw       INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_spot          INT NOT NULL UNIQUE,      -- kunci bisnis (spot_lokasi)
  spot             VARCHAR(100) NOT NULL,
  wilayah_fakultas VARCHAR(50)  NOT NULL,
  universitas      VARCHAR(100) NOT NULL DEFAULT 'Universitas'
);

CREATE TABLE dw.dim_organisasi (
  id_organisasi_dw INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_organisasi    INT NOT NULL UNIQUE,
  organisasi       VARCHAR(100) NOT NULL,
  fakultas_asal    VARCHAR(50)  NOT NULL
);

CREATE TABLE dw.dim_produk (
  id_produk_dw INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_produk    INT NOT NULL,
  id_varian    INT,                          -- NULL = tanpa varian
  varian       VARCHAR(50),
  produk       VARCHAR(100) NOT NULL,
  kategori     TEXT NOT NULL,
  UNIQUE NULLS NOT DISTINCT (id_produk, id_varian)   -- fitur PostgreSQL 15+
);

-- ---------------------------------------------------------------------
-- Fakta
-- ---------------------------------------------------------------------
CREATE TABLE dw.fakta_penjualan_danus (
  id_detail         BIGINT PRIMARY KEY,      -- dimensi degenerate: detail_pesanan.id_detail
                                             -- (membuat ETL idempotent: lewati id yang sudah ada)
  id_waktu          INT NOT NULL REFERENCES dw.dim_waktu(id_waktu),
  id_jam            INT NOT NULL REFERENCES dw.dim_jam(id_jam),
  id_spot_dw        INT NOT NULL REFERENCES dw.dim_spot(id_spot_dw),
  id_organisasi_dw  INT NOT NULL REFERENCES dw.dim_organisasi(id_organisasi_dw),
  id_produk_dw      INT NOT NULL REFERENCES dw.dim_produk(id_produk_dw),
  kuantitas_terjual INT NOT NULL CHECK (kuantitas_terjual > 0),
  total_omzet       NUMERIC(14,2) NOT NULL,
  total_modal       NUMERIC(14,2) NOT NULL,
  laba_bersih       NUMERIC(14,2) NOT NULL,
  jumlah_transaksi  INT NOT NULL DEFAULT 1   -- grain per item; pakai COUNT(DISTINCT) bila perlu
);

CREATE INDEX idx_fakta_waktu ON dw.fakta_penjualan_danus (id_waktu);
CREATE INDEX idx_fakta_spot  ON dw.fakta_penjualan_danus (id_spot_dw);
CREATE INDEX idx_fakta_prod  ON dw.fakta_penjualan_danus (id_produk_dw);

-- ---------------------------------------------------------------------
-- Isi dimensi waktu (2026-2027) dan jam (slot 30 menit)
-- ---------------------------------------------------------------------
INSERT INTO dw.dim_waktu
SELECT to_char(d, 'YYYYMMDD')::int,
       d::date,
       (ARRAY['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu'])[EXTRACT(ISODOW FROM d)::int],
       EXTRACT(MONTH FROM d)::int,
       EXTRACT(QUARTER FROM d)::int,
       EXTRACT(YEAR FROM d)::int,
       EXTRACT(ISODOW FROM d) <= 5
  FROM generate_series(DATE '2026-01-01', DATE '2027-12-31', interval '1 day') AS d;

INSERT INTO dw.dim_jam
SELECT h * 100 + m, h, m,
       CASE
         WHEN h BETWEEN 5  AND 9  THEN 'Pagi'
         WHEN h BETWEEN 10 AND 13 THEN 'Jam Makan Siang'
         WHEN h BETWEEN 14 AND 16 THEN 'Sore'
         WHEN h BETWEEN 17 AND 20 THEN 'Malam'
         ELSE 'Di Luar Jam Jualan'
       END
  FROM generate_series(0, 23) AS h, (VALUES (0), (30)) AS s(m);

-- ---------------------------------------------------------------------
-- Pra-agregasi bulanan (materialized view), isi setelah ETL:
--   REFRESH MATERIALIZED VIEW dw.mv_omzet_bulanan;
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW dw.mv_omzet_bulanan AS
SELECT w.tahun, w.bulan, s.wilayah_fakultas, p.kategori,
       SUM(f.kuantitas_terjual) AS kuantitas,
       SUM(f.total_omzet)       AS omzet,
       SUM(f.laba_bersih)       AS laba
  FROM dw.fakta_penjualan_danus f
  JOIN dw.dim_waktu w ON w.id_waktu   = f.id_waktu
  JOIN dw.dim_spot  s ON s.id_spot_dw = f.id_spot_dw
  JOIN dw.dim_produk p ON p.id_produk_dw = f.id_produk_dw
 GROUP BY w.tahun, w.bulan, s.wilayah_fakultas, p.kategori
WITH NO DATA;

CREATE UNIQUE INDEX uq_mv_omzet_bulanan
  ON dw.mv_omzet_bulanan (tahun, bulan, wilayah_fakultas, kategori);

-- Contoh kueri OLAP (Bab 13), jalankan setelah fakta terisi:
-- SELECT s.wilayah_fakultas, o.organisasi, p.kategori, SUM(f.total_omzet) AS omzet
--   FROM dw.fakta_penjualan_danus f
--   JOIN dw.dim_spot s ON s.id_spot_dw = f.id_spot_dw
--   JOIN dw.dim_organisasi o ON o.id_organisasi_dw = f.id_organisasi_dw
--   JOIN dw.dim_produk p ON p.id_produk_dw = f.id_produk_dw
--  GROUP BY ROLLUP (s.wilayah_fakultas, o.organisasi, p.kategori);
