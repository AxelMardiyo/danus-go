# DanusGo

Campus Danusan & Food Tracking Hub. Proyek akhir Basis Data Lanjut (Bab 1, 2, 3, 4, 5, 6, 7, 9, 13).
Sumber kebenaran: **PRD DanusGo**. Bila README ini berbeda dengan PRD, PRD yang benar.

## Struktur project

```
danusgo/
├── docker-compose.yml        PostgreSQL 16 (+ pgAdmin opsional); backend/frontend siap diaktifkan
├── Makefile                  pintasan: up, reset, psql, indexes, crash, wal
├── .env.example              salin ke .env
├── db/                       SEMUA SQL. File bernomor mengikuti PRD Bagian 12
│   ├── 01_schema.sql           DDL kanonik, partisi bulanan, trigger, view      [otomatis]
│   ├── 02_seed_master.sql      fakultas, prodi, 2 spot, akun Admin dev           [otomatis]
│   ├── 03_queries.sql          Bab 2: kueri lanjut + fungsi pesan atomik         [manual]
│   ├── 04_indexes.sql          Bab 5: rencana indeks                             [manual]
│   ├── 04_indexes_drop.sql     lepas indeks untuk pengukuran "tanpa indeks"      [manual]
│   ├── 05_partition.sql        Bab 9: Range vs Hash, dataset besar, paralel      [manual]
│   └── 06_dw_schema.sql        Bab 13: skema dw (star schema), dim waktu & jam   [otomatis]
├── seed/                     generator data 100k+ (Python, Faker id_ID, seed tetap)
├── backend/                  API /api/v1 (peran #10), SQL mentah
├── frontend/                 halaman buyer, seller, admin (peran #9)
└── docs/                     PRD, normalisasi (Bab 1), hasil EXPLAIN, grafik, video demo crash
```

Indeks (04) sengaja **tidak** dimuat otomatis supaya tim bisa mengukur kondisi tanpa indeks dulu,
lalu menerapkannya dan mengukur ulang (Bab 5 dan 7).

## Mulai cepat

```bash
cp .env.example .env
make up          # pertama kali: init menjalankan 01, 02, 06 otomatis
make psql        # cek: \dt  dan  \dt dw.*
```

Login Admin dev: `admin@danusgo.local` (atau NIM `ADMIN001`) / `admin12345`. Ganti sebelum dipakai di luar laptop sendiri.

Init hanya berjalan **saat volume data masih kosong**. Setelah mengubah `01_schema.sql` atau `02_seed_master.sql`:

```bash
make reset       # menghapus semua data lalu membangun ulang
```

## Hal yang perlu diketahui tim

- **Zona waktu WIB.** Server dikunci ke `Asia/Jakarta`, dan batas partisi bulanan dibuat eksplisit WIB.
  Pesanan jam 00:30 WIB tanggal 1 Des masuk `pesanan_2026_12`, bukan Nov.
- **Partisi.** `01_schema.sql` membuat `pesanan_2026_01` sampai `pesanan_2027_03` dan `pesanan_default`.
  Baris di luar rentang masuk partisi default. Menambah bulan baru gagal bila default sudah berisi baris untuk rentang itu.
- **Data historis.** `kedaluwarsa_pada` default `now() + 15 menit`. Untuk `waktu_pesan` di masa lalu nilainya salah secara
  makna (job kedaluwarsa akan menganggapnya belum kedaluwarsa), dan untuk `waktu_pesan` di masa depan CHECK
  `kedaluwarsa_pada > waktu_pesan` menolak baris. Seeder wajib mengisinya eksplisit (lihat `seed/README.md`).
- **Kode pengambilan** unik per sesi dicek di transaksi pemesanan, bukan constraint (PRD BR-15).
- **Sesi bentrok** memunculkan SQLSTATE `23P01`; backend memetakan ke `SESI_BENTROK`.
- **Trigger tambahan dari PRD BR-08:** `fn_validasi_sesi_produk` memaksa PRE_ORDER punya jendela pesan dan READY_STOCK tidak.
- **Fungsi atomik, job kedaluwarsa, dan ETL belum ada.** Itu pekerjaan peran #3 (03_queries.sql) dan #8 (ETL).

## Demo crash (Bab 4)

```bash
make psql                # BEGIN; UPDATE ... ;  (jangan COMMIT), catat pg_current_wal_lsn()
make crash               # SIGKILL ke postmaster
make up && make logs     # baca log recovery (redo starts at ...)
make wal                 # 40 record terakhir pg_waldump
```

Contoh uji konkurensi dan skenario EXPLAIN dikerjakan peran #3, #5, dan #6; hasilnya masuk `docs/`.
