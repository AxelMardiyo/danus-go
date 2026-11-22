-- =====================================================================
-- DanusGo: 04_indexes.sql  (Bab 5: Indexing)
-- TIDAK dijalankan otomatis. Tujuannya agar tim bisa mengukur kondisi
-- "tanpa indeks" lebih dulu, lalu menerapkan file ini dan mengukur ulang.
--   make indexes        -> terapkan
--   make indexes-drop   -> lepas (jalankan 04_indexes_drop.sql)
-- Primary key, UNIQUE, dan exclusion constraint sudah punya indeks sendiri.
-- Indeks pada tabel partisi otomatis dibuat di tiap partisi.
-- =====================================================================
\set ON_ERROR_STOP on

-- Radar harian (FR-B01)
CREATE INDEX idx_sesi_tgl_status ON sesi_jualan (tanggal_jualan, status_sesi);

-- Range query periode (agregasi omzet, ETL)
CREATE INDEX idx_pesanan_waktu ON pesanan_danus (waktu_pesan);

-- Antrean seller: partial index hanya status aktif (FR-S03)
CREATE INDEX idx_pesanan_antrean ON pesanan_danus (status_pesanan)
  WHERE status_pesanan IN ('PENDING', 'PAID');

-- Kardinalitas rendah; planner dapat memakai Bitmap Index Scan bila digabung kondisi lain
CREATE INDEX idx_spot_fakultas ON spot_lokasi (id_fakultas);

-- Riwayat pesanan satu pengguna (FR-B06)
CREATE INDEX idx_pesanan_user ON pesanan_danus (id_mahasiswa, waktu_pesan DESC);

ANALYZE;

-- Ukuran indeks untuk tabel eksperimen Bab 5:
-- SELECT indexrelid::regclass AS indeks, pg_size_pretty(pg_relation_size(indexrelid)) AS ukuran
--   FROM pg_index WHERE indrelid::regclass::text IN ('sesi_jualan','spot_lokasi')
--      OR indrelid::regclass::text LIKE 'pesanan_20%' ORDER BY 1;
