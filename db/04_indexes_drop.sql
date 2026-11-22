-- Lepas indeks buatan 04_indexes.sql (untuk pengukuran "tanpa indeks").
\set ON_ERROR_STOP on

DROP INDEX IF EXISTS idx_sesi_tgl_status;
DROP INDEX IF EXISTS idx_pesanan_waktu;
DROP INDEX IF EXISTS idx_pesanan_antrean;
DROP INDEX IF EXISTS idx_spot_fakultas;
DROP INDEX IF EXISTS idx_pesanan_user;

ANALYZE;
