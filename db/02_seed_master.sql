-- =====================================================================
-- DanusGo: 02_seed_master.sql
-- Data master minimal agar aplikasi bisa dijalankan (BUKAN seeder 100k+;
-- seeder besar ada di seed/ dan dijalankan terpisah, lihat README).
-- Daftar fakultas/prodi di bawah contoh: sesuaikan dengan kampus Anda.
-- =====================================================================
\set ON_ERROR_STOP on

INSERT INTO fakultas (nama_fakultas) VALUES
  ('Area Umum'),
  ('Teknik'),
  ('Ekonomi dan Bisnis'),
  ('Hukum'),
  ('Kedokteran'),
  ('MIPA'),
  ('Ilmu Sosial dan Politik'),
  ('Psikologi'),
  ('Ilmu Budaya');

INSERT INTO prodi (id_fakultas, nama_prodi)
SELECT f.id_fakultas, p.nama_prodi
  FROM (VALUES
    ('Teknik',                  'Teknik Informatika'),
    ('Teknik',                  'Teknik Sipil'),
    ('Ekonomi dan Bisnis',      'Manajemen'),
    ('Ekonomi dan Bisnis',      'Akuntansi'),
    ('Hukum',                   'Ilmu Hukum'),
    ('Kedokteran',              'Pendidikan Dokter'),
    ('MIPA',                    'Matematika'),
    ('MIPA',                    'Statistika'),
    ('Ilmu Sosial dan Politik', 'Ilmu Komunikasi'),
    ('Psikologi',               'Psikologi'),
    ('Ilmu Budaya',             'Sastra Inggris')
  ) AS p(nama_fakultas, nama_prodi)
  JOIN fakultas f ON f.nama_fakultas = p.nama_fakultas;

-- Spot contoh (kampus nyata: ganti lewat panel Admin / seeder)
INSERT INTO spot_lokasi (id_fakultas, nama_spot, patokan_lokasi)
SELECT f.id_fakultas, s.nama_spot, s.patokan
  FROM (VALUES
    ('Teknik',    'Gazebo Giri Santika', 'Dekat gerbang belakang gedung Teknik'),
    ('Area Umum', 'Taman Kampus',        'Di depan perpustakaan pusat')
  ) AS s(nama_fakultas, nama_spot, patokan)
  JOIN fakultas f ON f.nama_fakultas = s.nama_fakultas;

-- Akun Admin pengembangan. GANTI password sebelum dipakai di luar laptop sendiri.
-- Login: email admin@danusgo.local / NIM ADMIN001, password admin12345
-- Hash bcrypt ($2a$) dari pgcrypto kompatibel dengan passlib/bcrypt (Python)
-- dan bcrypt/bcryptjs (Node).
INSERT INTO pengguna (nim, nama, email, no_hp, id_prodi, password_hash, role)
SELECT 'ADMIN001', 'Admin DanusGo', 'admin@danusgo.local', '080000000000',
       (SELECT id_prodi FROM prodi ORDER BY id_prodi LIMIT 1),
       crypt('admin12345', gen_salt('bf', 10)), 'ADMIN';
