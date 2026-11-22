-- =====================================================================
-- DanusGo: 01_schema.sql  (PostgreSQL 16)
-- Sumber: PRD DanusGo Bagian 6 dan 7. DDL kanonik; ubah di sini DAN di PRD.
-- Dijalankan otomatis oleh Docker saat volume data masih kosong.
-- =====================================================================
\set ON_ERROR_STOP on

CREATE EXTENSION IF NOT EXISTS btree_gist;  -- exclusion constraint sesi
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- crypt() untuk seed admin

-- ---------------------------------------------------------------------
-- Master akademik
-- ---------------------------------------------------------------------
CREATE TABLE fakultas (
  id_fakultas   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nama_fakultas VARCHAR(50) NOT NULL UNIQUE   -- termasuk 'Area Umum'
);

CREATE TABLE prodi (
  id_prodi    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_fakultas INT NOT NULL REFERENCES fakultas(id_fakultas),
  nama_prodi  VARCHAR(50) NOT NULL,
  UNIQUE (id_fakultas, nama_prodi)
);

-- ---------------------------------------------------------------------
-- Pengguna, organisasi, seller
-- ---------------------------------------------------------------------
CREATE TABLE pengguna (
  id_mahasiswa  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nim           VARCHAR(15)  NOT NULL UNIQUE,
  nama          VARCHAR(100) NOT NULL,
  email         VARCHAR(100) NOT NULL UNIQUE,
  no_hp         VARCHAR(20)  NOT NULL,
  id_prodi      INT NOT NULL REFERENCES prodi(id_prodi),
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'BUYER' CHECK (role IN ('BUYER','SELLER','ADMIN')),
  is_aktif      BOOLEAN NOT NULL DEFAULT true,
  dibuat_pada   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organisasi_danus (
  id_organisasi     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nama_organisasi   VARCHAR(100) NOT NULL,
  nama_proker       VARCHAR(100) NOT NULL,
  id_fakultas_induk INT NOT NULL REFERENCES fakultas(id_fakultas),
  rekening_tujuan   VARCHAR(50)  NOT NULL
);

CREATE TABLE seller (
  id_seller     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_mahasiswa  INT NOT NULL REFERENCES pengguna(id_mahasiswa),
  id_organisasi INT NOT NULL REFERENCES organisasi_danus(id_organisasi),
  UNIQUE (id_mahasiswa, id_organisasi)
);

CREATE TABLE pengajuan_seller (
  id_pengajuan      INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_mahasiswa      INT NOT NULL REFERENCES pengguna(id_mahasiswa),
  id_organisasi     INT NOT NULL REFERENCES organisasi_danus(id_organisasi),
  alasan            TEXT NOT NULL,
  bukti_url         TEXT,
  status            TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','APPROVED','REJECTED')),
  diajukan_pada     TIMESTAMPTZ NOT NULL DEFAULT now(),
  id_admin_peninjau INT REFERENCES pengguna(id_mahasiswa),
  ditinjau_pada     TIMESTAMPTZ,
  catatan_admin     TEXT,
  CHECK (status = 'PENDING' OR (id_admin_peninjau IS NOT NULL AND ditinjau_pada IS NOT NULL)),
  CHECK (status <> 'REJECTED' OR catatan_admin IS NOT NULL)
);

-- satu pengajuan PENDING per mahasiswa per organisasi (BR-12)
CREATE UNIQUE INDEX uq_pengajuan_pending
  ON pengajuan_seller (id_mahasiswa, id_organisasi) WHERE status = 'PENDING';

-- ---------------------------------------------------------------------
-- Spot dan produk (4NF: varian dan pickup dipisah)
-- ---------------------------------------------------------------------
CREATE TABLE spot_lokasi (
  id_spot        INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_fakultas    INT NOT NULL REFERENCES fakultas(id_fakultas),
  nama_spot      VARCHAR(100) NOT NULL,
  patokan_lokasi TEXT,
  UNIQUE (id_fakultas, nama_spot)
);

CREATE TABLE produk_danus (
  id_produk      INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_organisasi  INT NOT NULL REFERENCES organisasi_danus(id_organisasi),
  nama_produk    VARCHAR(100) NOT NULL,
  kategori       TEXT NOT NULL CHECK (kategori IN ('MAKANAN_BERAT','SNACK','MINUMAN','MERCHANDISE')),
  harga_modal    NUMERIC(10,2) NOT NULL CHECK (harga_modal > 0),
  harga_jual     NUMERIC(10,2) NOT NULL CHECK (harga_jual > 0),
  tipe_penjualan TEXT NOT NULL CHECK (tipe_penjualan IN ('READY_STOCK','PRE_ORDER')),
  CHECK (harga_jual >= harga_modal)                                   -- BR-06
);

CREATE TABLE produk_varian (
  id_varian   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_produk   INT NOT NULL REFERENCES produk_danus(id_produk) ON DELETE CASCADE,
  nama_varian VARCHAR(50) NOT NULL,
  UNIQUE (id_produk, nama_varian)
);

CREATE TABLE produk_metode_pickup (
  id_pickup     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_produk     INT NOT NULL REFERENCES produk_danus(id_produk) ON DELETE CASCADE,
  metode_pickup VARCHAR(50) NOT NULL,
  UNIQUE (id_produk, metode_pickup)
);

-- ---------------------------------------------------------------------
-- Sesi jualan dan kuota
-- ---------------------------------------------------------------------
CREATE TABLE sesi_jualan (
  id_sesi        INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_organisasi  INT NOT NULL REFERENCES organisasi_danus(id_organisasi),
  id_spot        INT NOT NULL REFERENCES spot_lokasi(id_spot),
  tanggal_jualan DATE NOT NULL,
  jam_mulai      TIME NOT NULL,
  jam_selesai    TIME NOT NULL,
  status_sesi    TEXT NOT NULL DEFAULT 'UPCOMING'
                 CHECK (status_sesi IN ('UPCOMING','OPEN','CLOSED')),
  CHECK (jam_selesai > jam_mulai),
  -- BR-07: tidak boleh tumpang tindih di spot yang sama (SQLSTATE 23P01 -> SESI_BENTROK)
  EXCLUDE USING gist (
    id_spot WITH =,
    tsrange(tanggal_jualan + jam_mulai, tanggal_jualan + jam_selesai) WITH &&
  )
);

CREATE TABLE sesi_produk (
  id_sesi_produk   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_sesi          INT NOT NULL REFERENCES sesi_jualan(id_sesi) ON DELETE CASCADE,
  id_produk        INT NOT NULL REFERENCES produk_danus(id_produk),
  kuota_awal       INT NOT NULL CHECK (kuota_awal > 0),
  kuota_sisa       INT NOT NULL,
  status_stok      TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (status_stok IN ('AVAILABLE','SOLD_OUT')),
  buka_pesan_pada  TIMESTAMPTZ,   -- hanya PRE_ORDER
  tutup_pesan_pada TIMESTAMPTZ,   -- hanya PRE_ORDER
  UNIQUE (id_sesi, id_produk),
  CHECK (kuota_sisa >= 0 AND kuota_sisa <= kuota_awal),
  CHECK (buka_pesan_pada IS NULL OR tutup_pesan_pada IS NULL OR tutup_pesan_pada > buka_pesan_pada)
);

-- ---------------------------------------------------------------------
-- Pesanan (header dipartisi per bulan) dan detail
-- ---------------------------------------------------------------------
CREATE TABLE pesanan_danus (
  id_pesanan        BIGINT GENERATED ALWAYS AS IDENTITY,
  id_mahasiswa      INT NOT NULL REFERENCES pengguna(id_mahasiswa),
  id_sesi           INT NOT NULL REFERENCES sesi_jualan(id_sesi),
  waktu_pesan       TIMESTAMPTZ NOT NULL DEFAULT now(),
  metode_bayar      TEXT NOT NULL CHECK (metode_bayar IN ('CASH_COD','QRIS')),
  status_pesanan    TEXT NOT NULL DEFAULT 'PENDING'
                    CHECK (status_pesanan IN ('PENDING','PAID','READY_TO_PICKUP','COMPLETED','CANCELLED')),
  kode_pengambilan  CHAR(6) NOT NULL,   -- unik per sesi, dicek di transaksi pemesanan (BR-15)
  kedaluwarsa_pada  TIMESTAMPTZ NOT NULL DEFAULT now() + interval '15 minutes',
                    -- seeder data historis WAJIB mengisi ini eksplisit (> waktu_pesan)
  dibayar_pada      TIMESTAMPTZ,
  siap_pada         TIMESTAMPTZ,
  selesai_pada      TIMESTAMPTZ,
  dibatalkan_pada   TIMESTAMPTZ,
  PRIMARY KEY (id_pesanan, waktu_pesan),
  CHECK (kedaluwarsa_pada > waktu_pesan)
) PARTITION BY RANGE (waktu_pesan);

CREATE TABLE detail_pesanan (
  id_detail          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_pesanan         BIGINT NOT NULL,
  waktu_pesan        TIMESTAMPTZ NOT NULL,
  id_sesi_produk     INT NOT NULL REFERENCES sesi_produk(id_sesi_produk),
  id_varian          INT REFERENCES produk_varian(id_varian),
  id_pickup          INT REFERENCES produk_metode_pickup(id_pickup),
  jumlah_item        INT NOT NULL CHECK (jumlah_item > 0),
  harga_satuan       NUMERIC(10,2) NOT NULL CHECK (harga_satuan > 0),
  harga_modal_satuan NUMERIC(10,2) NOT NULL CHECK (harga_modal_satuan > 0),
  CHECK (harga_satuan >= harga_modal_satuan),
  FOREIGN KEY (id_pesanan, waktu_pesan)
    REFERENCES pesanan_danus(id_pesanan, waktu_pesan)
);

-- id_pesanan sengaja tanpa FK: log harus bertahan walau pesanan berpindah/dibatalkan
CREATE TABLE log_kuota (
  id_log         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_sesi_produk INT NOT NULL REFERENCES sesi_produk(id_sesi_produk),
  id_pesanan     BIGINT,
  delta          INT NOT NULL,
  alasan         TEXT NOT NULL,   -- PEMESANAN, PEMBATALAN, KEDALUWARSA, TAMBAH_KUOTA
  waktu          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- Partisi bulanan 2026-01 .. 2027-03, plus DEFAULT.
-- Batas bulan dikunci ke WIB (Asia/Jakarta), bukan zona waktu sesi.
-- Bulan baru:
--   CREATE TABLE pesanan_2027_04 PARTITION OF pesanan_danus
--     FOR VALUES FROM ('2027-04-01 00:00+07') TO ('2027-05-01 00:00+07');
-- (gagal bila pesanan_default sudah berisi baris untuk rentang itu)
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- Trigger konsistensi (BR-04, BR-05)
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_validasi_detail() RETURNS trigger AS $$
DECLARE
  v_sesi_header INT;
  v_sesi_item   INT;
  v_produk      INT;
BEGIN
  SELECT id_sesi INTO v_sesi_header FROM pesanan_danus
   WHERE id_pesanan = NEW.id_pesanan AND waktu_pesan = NEW.waktu_pesan;
  SELECT id_sesi, id_produk INTO v_sesi_item, v_produk FROM sesi_produk
   WHERE id_sesi_produk = NEW.id_sesi_produk;

  IF v_sesi_header IS DISTINCT FROM v_sesi_item THEN
    RAISE EXCEPTION 'Item bukan bagian dari sesi pesanan';
  END IF;
  IF NEW.id_varian IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM produk_varian WHERE id_varian = NEW.id_varian AND id_produk = v_produk) THEN
    RAISE EXCEPTION 'Varian bukan milik produk ini';
  END IF;
  IF NEW.id_pickup IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM produk_metode_pickup WHERE id_pickup = NEW.id_pickup AND id_produk = v_produk) THEN
    RAISE EXCEPTION 'Metode pickup bukan milik produk ini';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validasi_detail
  BEFORE INSERT OR UPDATE ON detail_pesanan
  FOR EACH ROW EXECUTE FUNCTION fn_validasi_detail();

-- BR-08: PRE_ORDER wajib punya jendela pesan, READY_STOCK wajib NULL
CREATE FUNCTION fn_validasi_sesi_produk() RETURNS trigger AS $$
DECLARE
  v_tipe TEXT;
BEGIN
  SELECT tipe_penjualan INTO v_tipe FROM produk_danus WHERE id_produk = NEW.id_produk;
  IF v_tipe = 'PRE_ORDER' AND (NEW.buka_pesan_pada IS NULL OR NEW.tutup_pesan_pada IS NULL) THEN
    RAISE EXCEPTION 'PRE_ORDER wajib mengisi buka_pesan_pada dan tutup_pesan_pada';
  END IF;
  IF v_tipe = 'READY_STOCK' AND (NEW.buka_pesan_pada IS NOT NULL OR NEW.tutup_pesan_pada IS NOT NULL) THEN
    RAISE EXCEPTION 'READY_STOCK tidak boleh punya jendela pesan';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validasi_sesi_produk
  BEFORE INSERT OR UPDATE ON sesi_produk
  FOR EACH ROW EXECUTE FUNCTION fn_validasi_sesi_produk();

-- ---------------------------------------------------------------------
-- BR-03: total_bayar dihitung, tidak disimpan
-- ---------------------------------------------------------------------
CREATE VIEW v_total_pesanan AS
SELECT p.id_pesanan, p.waktu_pesan, p.id_mahasiswa, p.id_sesi, p.status_pesanan,
       SUM(d.harga_satuan * d.jumlah_item)                       AS total_bayar,
       SUM(d.harga_satuan * d.jumlah_item)
         - SUM(d.harga_modal_satuan * d.jumlah_item)             AS laba
  FROM pesanan_danus p
  JOIN detail_pesanan d ON d.id_pesanan = p.id_pesanan AND d.waktu_pesan = p.waktu_pesan
 GROUP BY p.id_pesanan, p.waktu_pesan, p.id_mahasiswa, p.id_sesi, p.status_pesanan;
