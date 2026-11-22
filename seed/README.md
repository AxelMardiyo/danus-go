# Seeder (peran #2)

Generator data uji: Python + Faker (`id_ID`) + `generate_series` + `COPY`, **seed acak tetap**.
Target jumlah baris ada di PRD Bagian 13. Seeder wajib berjalan setelah `02_seed_master.sql`.

Catatan penting dari skema:
- `pesanan_danus.kedaluwarsa_pada` default-nya `now() + 15 menit`. Untuk data historis,
  isi eksplisit (`waktu_pesan + interval '15 minutes'`). Kalau dibiarkan default,
  nilainya salah untuk data lampau, dan CHECK `kedaluwarsa_pada > waktu_pesan` menolak data bertanggal masa depan.
- Gunakan `waktu_pesan` dengan offset `+07` agar masuk partisi bulan WIB yang benar.
- Isi `sesi_produk.kuota_sisa` konsisten dengan pesanan yang dibuat (jangan melebihi `kuota_awal`).
