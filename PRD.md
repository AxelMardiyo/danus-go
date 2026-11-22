# PRD DanusGo: Campus Danusan & Food Tracking Hub

Versi 1.0 · 22 November 2026 · Dasar: Perencanaan Final Project Basis Data Lanjut (versi 21 November 2026)

## 0. Cara Memakai Dokumen Ini (Kontrak Prompt)

Dokumen ini adalah **sumber kebenaran tunggal** untuk semua prompt ke AI: kode, SQL, UI, laporan, dan slide. Bila prompt bertentangan dengan PRD, PRD menang. Bila PRD yang keliru, perbaiki PRD dulu, baru minta kode.

Aturan untuk setiap prompt:

1. Sebut ID bagian PRD yang relevan (mis. “Implementasikan FR-B04, BR-01, BR-09”) dan lampirkan teks bagian itu.
2. Jangan menambah tabel, kolom, endpoint, status, atau kode error di luar PRD. Butuh yang baru → usulkan perubahan PRD dulu.
3. Nama tabel, kolom, path API, status, dan kode error dipakai **persis** seperti tertulis (bahasa Indonesia, snake\_case; status dan kode error huruf besar). Jangan diterjemahkan.
4. SQL mentah PostgreSQL 16, bukan ORM. Tanpa sintaks MySQL (ENUM, AUTO\_INCREMENT).
5. Logika konsistensi (kuota, transisi status, harga) hidup di database atau transaksi backend, tidak pernah hanya di frontend.
6. Setiap keluaran harus bisa diverifikasi: sertakan perintah uji atau kueri pembuktian.
7. Satu prompt = satu tugas kecil dengan kriteria selesai yang jelas.
8. Butir bertanda ⚠ di Bagian 17 belum final. Jangan diasumsikan diam-diam; pakai default yang tertulis atau tanyakan.

Template prompt ada di Bagian 18.

## 1. Ringkasan Produk

DanusGo adalah marketplace dan pelacak danusan kampus berbasis **lokasi fisik (spot)** dan **slot waktu jualan (sesi)**. Seller (panitia danusan) membuka sesi di sebuah spot dengan kuota porsi per produk. Buyer melihat jajanan yang sedang buka, memesan, lalu mengambil dengan kode pengambilan. Admin memantau tren penjualan lewat dashboard OLAP.

Proyek ini adalah **wadah demonstrasi materi Basis Data Lanjut Bab 1, 2, 3, 4, 5, 6, 7, 9, dan 13**. Aplikasi web melayani demo; nilai utama ada pada rancangan dan bukti basis data.

**Masalah yang diselesaikan**

- Buyer: info danusan tercecer di broadcast WhatsApp dan story Instagram; tidak tahu apa yang buka hari ini, sisa berapa porsi, dan mangkal di mana.
- Seller: rawan overselling pada Pre-Order karena catatan manual; sulit memperkirakan kuota sehingga makanan sisa; rekap kas untuk LPJ sering selisih dan lama.

## 2. Tujuan, Non-Tujuan, dan Kriteria Keberhasilan

**Tujuan**

- G1. Skema ternormalisasi hingga BCNF dan 4NF.
- G2. Pemesanan atomik tanpa overselling meski diakses serentak.
- G3. Bukti performa nyata: indeks, rencana eksekusi, partisi, paralel.
- G4. Demonstrasi recovery setelah crash berbasis WAL.
- G5. Data warehouse dan dashboard OLAP lintas fakultas.

**Non-tujuan**

- Payment gateway nyata. QRIS disimulasikan: seller mengonfirmasi pembayaran manual. ⚠
- Pengembalian dana otomatis (dilakukan di luar sistem).
- WebSocket atau push notification (pakai polling).
- Tabel sesi login (login memakai JWT stateless).
- Keranjang lintas sesi.

**Kriteria keberhasilan (terukur)**

| ID | Kriteria |
| --- | --- |
| K1 | Uji 200 koneksi serentak ke produk berkuota 50: tepat 50 pesanan berhasil, kuota\_sisa = 0, tidak ada nilai negatif. Versi naif (SELECT lalu UPDATE) terbukti overselling. |
| K2 | Dataset 100k+ pesanan (1–5 juta untuk eksperimen paralel Bab 9) dengan seed acak tetap, hasil EXPLAIN konsisten antar laptop. |
| K3 | Lima skenario optimasi punya bukti sebelum dan sesudah (EXPLAIN (ANALYZE, BUFFERS) dijalankan dua kali). |
| K4 | Demo crash: transaksi belum commit tidak terlihat setelah recovery, transaksi yang sudah commit tetap ada, WAL dibedah dengan pg\_waldump. |
| K5 | Dashboard OLAP menampilkan ROLLUP, CUBE, slice dan dice, dan drill-down dari data warehouse. |
| K6 | Presentasi progres 26–27 Nov (Bab 1, 2, 3, 5, 6, 7) dan presentasi final 14 Des (Bab 4, 9, 13, demo web) terpenuhi. |

## 3. Pengguna dan Hak Akses

| Role | Siapa | Tanggung jawab |
| --- | --- | --- |
| BUYER | Semua akun terdaftar | Cari jajanan, pesan, bayar, ambil, lihat riwayat, ajukan jadi seller |
| SELLER | Anggota organisasi atau proker danusan yang pengajuannya disetujui Admin | Kelola produk, sesi, pesanan masuk, serah terima, dan kas organisasinya. Tetap bisa memesan seperti buyer |
| ADMIN | Pengelola platform | Data master, pengajuan seller, dashboard OLAP, Panel Bukti Performa |

Akun baru selalu mulai sebagai BUYER. Role menjadi SELLER hanya setelah Admin menyetujui pengajuan (FR-D01). Admin ditandai `pengguna.role = 'ADMIN'`.

| Aksi | Buyer | Seller | Admin |
| --- | --- | --- | --- |
| Lihat radar jajanan | ✓ | ✓ | ✓ |
| Buat dan batalkan pesanan sendiri | ✓ | ✓ |  |
| Konfirmasi bayar, siap diambil, selesai |  | ✓ |  |
| Lihat dan ekspor kas organisasi sendiri |  | ✓ |  |
| Kelola produk, varian, pickup, sesi organisasi sendiri |  | ✓ |  |
| Kelola spot dan organisasi (master) |  |  | ✓ |
| Dashboard OLAP dan Panel Bukti Performa |  |  | ✓ |
| Ajukan diri jadi seller | ✓ |  |  |
| Setujui atau tolak pengajuan seller |  |  | ✓ |

## 4. Ruang Lingkup dan Prioritas

Prioritas mengikuti mitigasi risiko: halaman yang mendemokan bab didahulukan, sisanya boleh berupa mockup. ⚠ (usulan, tim boleh mengubah)

| Prioritas | Isi | Target |
| --- | --- | --- |
| P0 Basis data | 01\_schema.sql, 02\_seed.sql, 03\_queries.sql, 04\_indexes.sql, skenario EXPLAIN dan grafik, perhitungan biaya Bab 6 | Progres 26–27 Nov |
| P0 Web | Radar, Detail Stand, Checkout, Pesanan Saya, Antrean Pesanan seller, Dashboard OLAP, Bukti Performa | Final 14 Des |
| P0 Basis data lanjutan | Demo crash (Bab 4), partisi dan paralel (Bab 9), DW dan ETL (Bab 13) | Final 14 Des |
| P1 | Produk dan Sesi seller, Kas Danus, Antrean Pengajuan Admin, Detail Pesanan | Final |
| P2 (mockup boleh) | Master Data, Pengguna, Profil, Ajukan Jadi Seller, Rekomendasi Kuota di UI | Final |

## 5. Kebutuhan Fungsional

### 5.1 Umum (semua role)

| ID | Kebutuhan |
| --- | --- |
| FR-A01 | Registrasi: nim, nama, email, no\_hp, id\_prodi (dropdown fakultas lalu prodi), password. Akun selalu BUYER. |
| FR-A02 | Login dengan email atau NIM dan password, hasil JWT (sub, role, exp). Akun `is_aktif = false` ditolak. Pesan error generik bila gagal. |
| FR-A03 | Profil: ubah nama, no\_hp, password. Seller melihat daftar organisasinya. |
| FR-A04 | Data master read-only untuk filter dan formulir: fakultas, prodi, spot, organisasi. |

### 5.2 Buyer

| ID | Kebutuhan |
| --- | --- |
| FR-B01 | **Live Campus Radar**: daftar sesi yang bisa dipesan hari ini. Filter fakultas, spot, kategori, rentang harga. Urut waktu tutup terdekat atau sisa kuota. |
| FR-B02 | **Live Kuota Indicator**: badge Banyak (>50%), Menipis (<20%), Habis; hitung mundur ke jam selesai; polling tiap 10 detik. |
| FR-B03 | **Detail Stand**: organisasi, spot dan patokan lokasi, jam, produk (kategori, harga, tipe, jendela pesan, varian), kuota sisa. |
| FR-B04 | **Quick Checkout**: pilih varian, jumlah, metode pickup, pembayaran QRIS atau CASH\_COD. Keranjang boleh multi-produk, satu sesi saja. |
| FR-B05 | **Kode Pengambilan** 6 karakter atau QR, ditunjukkan ke seller. |
| FR-B06 | **Riwayat dan status** PENDING → PAID → READY\_TO\_PICKUP → COMPLETED. Tombol batal hanya saat PENDING. |
| FR-B07 | **Ajukan Jadi Seller**: pilih organisasi, isi alasan, tautan bukti (SK kepanitiaan atau surat tugas). Pantau status PENDING, APPROVED, REJECTED beserta catatan Admin. Boleh mengajukan ulang setelah ditolak. |

### 5.3 Seller

| ID | Kebutuhan |
| --- | --- |
| FR-S01 | **Manajemen Produk**: tambah dan ubah produk, varian, metode pickup. harga\_jual tidak boleh di bawah harga\_modal. |
| FR-S02 | **Manajemen Sesi**: buat sesi (spot, tanggal, jam) dan isi kuota per produk. Jadwal bentrok di spot yang sama ditolak (exclusion constraint). Buka, tutup, hapus (hanya UPCOMING tanpa pesanan), tambah kuota. |
| FR-S03 | **Live Order Taker**: antrean pesanan masuk dengan aksi Konfirmasi Bayar, Siap Diambil, Selesai, Batalkan. |
| FR-S04 | **Verifikasi Serah Terima**: input kode pengambilan, status menjadi COMPLETED. |
| FR-S05 | **Kas Danus Otomatis**: omzet = Σ(harga\_satuan × jumlah); modal = Σ(harga\_modal\_satuan × jumlah); laba = omzet − modal. Per hari, produk, sesi. Hanya pesanan COMPLETED. Ekspor CSV untuk LPJ. |
| FR-S06 | **Rekomendasi Kuota**: rata-rata penjualan 4 minggu terakhir per produk, spot, jam (window function). Hanya saran. |
| FR-S07 | Pemilih organisasi aktif di header bila seller terhubung ke banyak organisasi. |

### 5.4 Admin

| ID | Kebutuhan |
| --- | --- |
| FR-D01 | **Tinjau pengajuan seller**: antrean beserta NIM, prodi, alasan, bukti. Setujui, atau Tolak dengan catatan wajib. |
| FR-D02 | Kelola master: fakultas, prodi, organisasi, spot. |
| FR-D03 | Cari pengguna (nama, NIM, role) dan aktif atau nonaktifkan akun. |
| FR-D04 | **Dashboard OLAP**: kartu ringkasan (total omzet, jumlah transaksi, produk terlaris); tren harian, bulanan, kuartalan (roll-up); peta panas jam × fakultas; drill-down Universitas → Fakultas → Organisasi → Produk; slice dan dice (kategori, rentang jam, fakultas). |
| FR-D05 | Jalankan ETL manual, tampilkan jumlah baris dan durasi. |
| FR-D06 | **Panel Bukti Performa**: jalankan skenario kueri Bab 7 dengan dan tanpa indeks, tampilkan waktu dan rencana berdampingan. |

### 5.5 Proses sistem

| ID | Kebutuhan |
| --- | --- |
| FR-X01 | Job tiap menit: pesanan PENDING dengan kedaluwarsa\_pada < now() menjadi CANCELLED, kuota kembali, log\_kuota alasan KEDALUWARSA. |
| FR-X02 | Penjadwal sesi: UPCOMING → OPEN saat jam\_mulai, OPEN → CLOSED saat jam\_selesai (selain tombol manual). |
| FR-X03 | ETL: pesanan COMPLETED dipindah ke skema `dw` (manual untuk demo, terjadwal untuk produksi). |

## 6. Aturan Bisnis dan Konsistensi

| ID | Aturan |
| --- | --- |
| BR-01 | **Pemesanan atomik**: dalam satu transaksi, `UPDATE sesi_produk SET kuota_sisa = kuota_sisa - n WHERE id_sesi_produk = ? AND kuota_sisa >= n`. 0 baris terpengaruh → ROLLBACK seluruh pesanan, error STOK\_HABIS. Berhasil → INSERT pesanan\_danus (PENDING + kode), INSERT detail\_pesanan, INSERT log\_kuota (delta negatif). |
| BR-02 | Harga ditentukan backend. harga\_satuan dan harga\_modal\_satuan disalin dari produk\_danus saat pesan, tidak dari body request, dan tidak berubah sesudahnya. |
| BR-03 | total\_bayar tidak disimpan; dihitung dari detail\_pesanan (view atau kueri). |
| BR-04 | Satu pesanan hanya untuk satu sesi, semua itemnya dari sesi itu (trigger fn\_validasi\_detail). |
| BR-05 | id\_varian dan id\_pickup harus milik produk item tersebut (trigger). id\_pickup ada di detail\_pesanan, bukan header. |
| BR-06 | harga\_jual ≥ harga\_modal (CHECK). |
| BR-07 | Sesi di spot yang sama tidak boleh tumpang tindih waktu (EXCLUDE gist). Error SESI\_BENTROK. |
| BR-08 | READY\_STOCK diterima hanya saat sesi OPEN. PRE\_ORDER diterima dari buka\_pesan\_pada sampai tutup\_pesan\_pada (sesi boleh masih UPCOMING); jendela wajib terisi untuk PRE\_ORDER dan NULL untuk READY\_STOCK. Di luar itu: SESI\_TIDAK\_BUKA. Kuota berkurang saat pesanan dibuat untuk keduanya. |
| BR-09 | PENDING kedaluwarsa 15 menit (kedaluwarsa\_pada). Pesanan COD yang sudah READY\_TO\_PICKUP tidak terkena job. |
| BR-10 | kuota\_sisa hanya berubah saat pesanan dibuat (berkurang) dan dibatalkan (bertambah). Setiap perubahan menulis log\_kuota (alasan mis. PEMBATALAN, KEDALUWARSA). Transisi status lain tidak menyentuh kuota. |
| BR-11 | status\_stok menjadi SOLD\_OUT otomatis saat kuota\_sisa = 0, kembali AVAILABLE bila kuota bertambah (batal atau seller menambah). Sesi tidak ditutup oleh stok habis. |
| BR-12 | Pengajuan seller: satu PENDING per (id\_mahasiswa, id\_organisasi) lewat partial unique index, error PENGAJUAN\_GANDA. Setujui dalam satu transaksi: status APPROVED + id\_admin\_peninjau + ditinjau\_pada, INSERT seller, role menjadi SELLER bila masih BUYER. Tolak wajib catatan\_admin. |
| BR-13 | Otorisasi seller: setiap request /seller/\* membawa X-Organisasi-Id dan backend memeriksa tabel seller pada tiap request. Role di token hanya petunjuk awal. |
| BR-14 | Kas dan OLAP hanya menghitung pesanan COMPLETED. |
| BR-15 | kode\_pengambilan 6 karakter, unik per sesi, dicek di dalam transaksi pemesanan (constraint unik pada tabel partisi wajib memuat kunci partisi). |
| BR-16 | dibayar\_pada, siap\_pada, selesai\_pada, dibatalkan\_pada diisi saat status berubah. Untuk CASH\_COD, dibayar\_pada diisi saat COMPLETED. |
| BR-17 | Keranjang satu sesi; pindah sesi mengosongkan keranjang. |
| BR-18 | Rekomendasi kuota hanya saran, tidak mengubah kuota otomatis. |
| BR-19 | Buyer hanya melihat pesanan dan pengajuan miliknya; seller hanya data organisasi aktif; admin semua. |

## 7. Model Data (ringkas)

Skema lengkap dan DDL kanonik ada di `01_schema.sql` (bersumber dari Section 5.3 dokumen perencanaan). **Setiap prompt yang menyentuh basis data wajib melampirkan file itu.** Tabel di bawah hanya ringkasan.

| Tabel | Kunci dan constraint penting |
| --- | --- |
| fakultas | PK id\_fakultas; UNIQUE nama\_fakultas (termasuk ‘Area Umum’) |
| prodi | FK id\_fakultas; UNIQUE (id\_fakultas, nama\_prodi) |
| pengguna | PK id\_mahasiswa; UNIQUE nim, email; FK id\_prodi; password\_hash; role CHECK (BUYER, SELLER, ADMIN); is\_aktif; dibuat\_pada |
| organisasi\_danus | FK id\_fakultas\_induk; nama\_organisasi, nama\_proker, rekening\_tujuan |
| pengajuan\_seller | FK id\_mahasiswa, id\_organisasi, id\_admin\_peninjau; status CHECK (PENDING, APPROVED, REJECTED); partial UNIQUE satu PENDING; CHECK peninjau wajib bila bukan PENDING; CHECK catatan\_admin wajib bila REJECTED |
| seller | UNIQUE (id\_mahasiswa, id\_organisasi); dibuat saat pengajuan disetujui |
| spot\_lokasi | FK id\_fakultas; UNIQUE (id\_fakultas, nama\_spot); patokan\_lokasi |
| produk\_danus | FK id\_organisasi; kategori CHECK (MAKANAN\_BERAT, SNACK, MINUMAN, MERCHANDISE); harga\_modal, harga\_jual; tipe\_penjualan CHECK (READY\_STOCK, PRE\_ORDER); CHECK harga\_jual ≥ harga\_modal |
| produk\_varian | FK id\_produk ON DELETE CASCADE; UNIQUE (id\_produk, nama\_varian) (4NF) |
| produk\_metode\_pickup | FK id\_produk ON DELETE CASCADE; UNIQUE (id\_produk, metode\_pickup) (4NF) |
| sesi\_jualan | FK id\_organisasi, id\_spot; status\_sesi CHECK (UPCOMING, OPEN, CLOSED); CHECK jam\_selesai > jam\_mulai; EXCLUDE gist (id\_spot, tsrange) |
| sesi\_produk | FK id\_sesi (CASCADE), id\_produk; UNIQUE (id\_sesi, id\_produk); kuota\_awal, kuota\_sisa (0..kuota\_awal); status\_stok (AVAILABLE, SOLD\_OUT); buka\_pesan\_pada, tutup\_pesan\_pada |
| pesanan\_danus | **Partisi RANGE bulanan** pada waktu\_pesan; PK (id\_pesanan, waktu\_pesan); metode\_bayar (CASH\_COD, QRIS); status\_pesanan (PENDING, PAID, READY\_TO\_PICKUP, COMPLETED, CANCELLED); kode\_pengambilan CHAR(6); kedaluwarsa\_pada default +15 menit; kolom waktu status |
| detail\_pesanan | FK komposit ke (id\_pesanan, waktu\_pesan); id\_sesi\_produk, id\_varian?, id\_pickup?; jumlah\_item; harga\_satuan; harga\_modal\_satuan; trigger fn\_validasi\_detail |
| log\_kuota | id\_sesi\_produk, id\_pesanan (tanpa FK, karena tabel partisi), delta, alasan, waktu |

**Relasi:** fakultas 1─N prodi 1─N pengguna; fakultas 1─N organisasi\_danus dan spot\_lokasi; pengguna 1─N pengajuan\_seller dan seller N─1 organisasi\_danus; organisasi\_danus 1─N produk\_danus (1─N varian, 1─N pickup) dan sesi\_jualan N─1 spot\_lokasi; sesi\_jualan 1─N sesi\_produk N─1 produk\_danus; pengguna 1─N pesanan\_danus N─1 sesi\_jualan; pesanan\_danus 1─N detail\_pesanan N─1 sesi\_produk; sesi\_produk 1─N log\_kuota.

**Catatan normalisasi (Bab 1):** MVD id\_produk ↠ varian dan id\_produk ↠ metode\_pickup dipecah ke 4NF. nama\_spot → id\_fakultas sengaja tidak diasumsikan. id\_prodi → id\_fakultas dipisah ke tabel prodi. detail\_pesanan tidak menyimpan id\_sesi (menjaga BCNF), konsistensinya dijaga trigger.

**Catatan PostgreSQL:** ENUM diganti TEXT + CHECK; AUTO\_INCREMENT diganti GENERATED ALWAYS AS IDENTITY; butuh `CREATE EXTENSION btree_gist`; partisi bulanan plus partisi DEFAULT; seeder mengisi fakultas dan prodi lebih dulu.

## 8. State Machine

### 8.1 Pesanan

Lima status, tujuh transisi. COMPLETED dan CANCELLED adalah status akhir.

| Dari | Ke | Pemicu | Endpoint |
| --- | --- | --- | --- |
| PENDING | PAID | Seller | POST /seller/pesanan/{id}/bayar |
| PENDING | READY\_TO\_PICKUP | Seller, hanya CASH\_COD | POST /seller/pesanan/{id}/siap |
| PAID | READY\_TO\_PICKUP | Seller | POST /seller/pesanan/{id}/siap |
| READY\_TO\_PICKUP | COMPLETED | Seller, kode cocok | POST /seller/pesanan/{id}/selesai |
| PENDING | CANCELLED | Buyer, Seller, atau sistem (kedaluwarsa) | POST /pesanan/{id}/batal, POST /seller/pesanan/{id}/batal, job |
| PAID | CANCELLED | Seller | POST /seller/pesanan/{id}/batal |
| READY\_TO\_PICKUP | CANCELLED | Seller | POST /seller/pesanan/{id}/batal |

Aturan: setiap transisi memakai `UPDATE ... WHERE id_pesanan = ? AND status_pesanan = <status lama>`; 0 baris → 409 STATUS\_TIDAK\_VALID (mencegah dua seller memproses pesanan yang sama). QRIS harus PAID sebelum siap diambil. Pembatalan dalam satu transaksi: ubah status, kembalikan kuota, SOLD\_OUT → AVAILABLE bila perlu, tulis log\_kuota.

### 8.2 Sesi dan stok

| Perubahan | Pemicu | Syarat dan efek |
| --- | --- | --- |
| UPCOMING → OPEN | Seller (/buka) atau penjadwal | Minimal satu produk. READY\_STOCK mulai bisa dipesan |
| OPEN → CLOSED | Seller (/tutup) atau penjadwal | Pesanan baru ditolak SESI\_TIDAK\_BUKA. Pesanan lama tetap diproses |
| UPCOMING → dihapus | Seller (DELETE) | Hanya bila belum ada pesanan |
| AVAILABLE ↔ SOLD\_OUT | Otomatis atau seller menambah kuota | Lihat BR-11 |

## 9. Spesifikasi API

REST JSON di bawah `/api/v1`. Setiap endpoint memetakan ke tabel di Bagian 7 dan aturan di Bagian 6.

### 9.1 Konvensi

| Aspek | Aturan |
| --- | --- |
| Autentikasi | `Authorization: Bearer <JWT>` berisi sub (id\_mahasiswa), role, exp |
| Otorisasi seller | Header `X-Organisasi-Id` wajib di /seller/\*, dicek ke tabel seller tiap request (BR-13) |
| Waktu | ISO 8601 dengan offset (2026-11-26T11:30:00+07:00); UI menampilkan WIB |
| Paginasi | `?page=1&limit=20`, limit maksimal 50; respons memuat data, page, total |
| Format error | Objek `error` berisi `code` dan `message` |

### 9.2 Endpoint

| Method | Path | Akses | Fungsi dan catatan |
| --- | --- | --- | --- |
| POST | /auth/register | Publik | Daftar (selalu BUYER) |
| POST | /auth/login | Publik | Login, hasil JWT |
| GET, PATCH | /me | Login | Profil dan organisasi seller; ubah nama, no\_hp, password |
| GET | /master/fakultas, /master/prodi, /master/spot, /master/organisasi | Login | Daftar read-only |
| GET | /radar | Buyer+ | Sesi yang bisa dipesan sekarang. Filter id\_fakultas, id\_spot, kategori, harga\_min, harga\_max; sort=tutup atau kuota. Memakai idx\_sesi\_tgl\_status |
| GET | /sesi/{id} | Buyer+ | Detail stand; dipolling 10 detik |
| POST | /pesanan | Buyer+ | Buat pesanan (BR-01). Body: id\_sesi, metode\_bayar, items\[\] berisi id\_sesi\_produk, id\_varian, id\_pickup, jumlah. Respons 201: id\_pesanan, kode\_pengambilan, kedaluwarsa\_pada, total\_bayar, status PENDING |
| GET | /pesanan, /pesanan/{id} | Buyer+ | Riwayat (filter status; idx\_pesanan\_user) dan detail milik sendiri |
| POST | /pesanan/{id}/batal | Buyer+ | Hanya saat PENDING |
| POST, GET | /pengajuan-seller | Buyer | Ajukan (id\_organisasi, alasan, bukti\_url) dan lihat status sendiri |
| GET, POST | /seller/produk | Seller | Daftar dan tambah produk |
| PATCH | /seller/produk/{id} | Seller | Ubah produk; harga lama tidak terpengaruh |
| POST, DELETE | /seller/produk/{id}/varian, /seller/produk/{id}/pickup | Seller | Kelola varian dan pickup |
| GET, POST | /seller/sesi | Seller | Daftar sesi; buat sesi dengan id\_spot, tanggal\_jualan, jam\_mulai, jam\_selesai, items\[\] |
| PATCH, DELETE | /seller/sesi/{id} | Seller | Ubah jam atau tambah kuota (hanya UPCOMING; OPEN khusus tambah kuota); hapus (UPCOMING tanpa pesanan) |
| POST | /seller/sesi/{id}/buka, /seller/sesi/{id}/tutup | Seller | Ubah status sesi |
| GET | /seller/pesanan | Seller | Antrean (filter status, id\_sesi; idx\_pesanan\_antrean) |
| POST | /seller/pesanan/{id}/bayar, /siap, /selesai, /batal | Seller | Transisi pesanan (Bagian 8.1). /selesai membawa kode\_pengambilan, salah kode → KODE\_SALAH. /batal membawa alasan |
| GET | /seller/kas, /seller/kas/export.csv | Seller | Parameter dari, sampai, group=hari, produk, atau sesi |
| GET | /seller/rekomendasi-kuota | Seller | Parameter id\_produk, id\_spot, jam |
| GET | /admin/pengajuan-seller | Admin | Antrean (default PENDING) dengan NIM, prodi, alasan, bukti |
| POST | /admin/pengajuan-seller/{id}/setujui, /tolak | Admin | BR-12; tolak wajib catatan\_admin |
| GET, POST, PATCH | /admin/organisasi, /admin/spot, /admin/fakultas, /admin/prodi | Admin | Kelola master |
| GET, PATCH | /admin/users, /admin/users/{id}/aktif | Admin | Cari (q, role) dan aktif atau nonaktifkan |
| GET | /admin/olap, /admin/olap/heatmap | Admin | group\_by (fakultas, organisasi, kategori, bulan, kuartal), rollup=true, filter kategori, jam\_dari, jam\_sampai, id\_fakultas. Membaca skema dw |
| POST | /admin/etl/run | Admin | ETL manual, hasil jumlah baris dan durasi |
| POST | /admin/benchmark | Admin | Body skenario dan mode (dengan\_indeks atau tanpa\_indeks). Hanya kueri baca yang sudah ditentukan; mode tanpa indeks memakai `SET LOCAL enable_indexscan = off, enable_bitmapscan = off`. Hasil: plan dan waktu EXPLAIN (ANALYZE, BUFFERS) |

### 9.3 Kode error

| HTTP | code | Kapan |
| --- | --- | --- |
| 400 | VALIDASI\_GAGAL | Body atau parameter tidak valid |
| 401 | TIDAK\_TERAUTENTIKASI | Token hilang atau kedaluwarsa |
| 403 | AKSES\_DITOLAK | Role atau organisasi tidak sesuai |
| 404 | TIDAK\_DITEMUKAN | Data tidak ada atau bukan milik user |
| 409 | STOK\_HABIS | Kuota tidak cukup |
| 409 | SESI\_TIDAK\_BUKA | Sesi bukan OPEN, atau di luar jendela PRE\_ORDER |
| 409 | STATUS\_TIDAK\_VALID | Transisi status tidak diizinkan |
| 409 | SESI\_BENTROK | Jadwal tumpang tindih di spot yang sama |
| 409 | PENGAJUAN\_GANDA | Sudah ada pengajuan PENDING untuk organisasi itu |
| 422 | KODE\_SALAH | Kode pengambilan tidak cocok |

## 10. Layar dan Navigasi

| Layar | Path | Role | API utama | Prioritas |
| --- | --- | --- | --- | --- |
| Login | /login | Publik | POST /auth/login | P0 |
| Daftar | /daftar | Publik | POST /auth/register, GET /master/\* | P0 |
| Radar Jajanan | / | Buyer | GET /radar | P0 |
| Detail Stand | /sesi/:id | Buyer | GET /sesi/{id} | P0 |
| Checkout | /sesi/:id/checkout | Buyer | POST /pesanan | P0 |
| Pesanan Saya | /pesanan | Buyer | GET /pesanan | P0 |
| Detail Pesanan | /pesanan/:id | Buyer | GET /pesanan/{id}, POST /batal | P1 |
| Ajukan Jadi Seller | /ajukan-seller | Buyer | /pengajuan-seller | P2 |
| Profil | /profil | Semua | GET, PATCH /me | P2 |
| Dashboard Seller | /seller | Seller | /seller/sesi, /pesanan, /kas | P1 |
| Produk | /seller/produk | Seller | /seller/produk/\* | P1 |
| Sesi Jualan | /seller/sesi | Seller | /seller/sesi/\*, rekomendasi-kuota | P1 |
| Antrean Pesanan | /seller/pesanan | Seller | /seller/pesanan/\* | P0 |
| Kas Danus | /seller/kas | Seller | /seller/kas, export.csv | P1 |
| Antrean Pengajuan | /admin/pengajuan | Admin | /admin/pengajuan-seller/\* | P1 |
| Master Data | /admin/master | Admin | /admin/{fakultas, prodi, organisasi, spot} | P2 |
| Pengguna | /admin/pengguna | Admin | /admin/users/\* | P2 |
| Dashboard OLAP | /admin/olap | Admin | /admin/olap, heatmap, etl/run | P0 |
| Bukti Performa | /admin/benchmark | Admin | POST /admin/benchmark | P0 |

**Aturan navigasi**

- Setelah login: BUYER ke `/`, SELLER ke `/seller`, ADMIN ke `/admin/olap`.
- Seller boleh membuka layar Buyer. Admin tidak punya layar Buyer atau Seller.
- Path di luar role → halaman akses ditolak (403). Token kedaluwarsa (401) → `/login`.
- Header Buyer: Radar, Pesanan Saya, Profil.

**Kondisi tampilan.** Setiap layar berdata punya empat kondisi: memuat (skeleton), kosong (pesan menjelaskan, mis. “Belum ada jajanan yang buka sekarang”), gagal (pesan dari kode error Bagian 9.3 plus tombol coba lagi), sukses.

**Keputusan desain awal:** Buyer mobile-first; Seller dan Admin desktop tapi terbaca di ponsel; polling bukan WebSocket; badge status memakai teks selain warna.

## 11. Kebutuhan Non-Fungsional dan Teknis

| Aspek | Ketentuan |
| --- | --- |
| DBMS | PostgreSQL 16 (EXPLAIN (ANALYZE, BUFFERS), partisi deklaratif, parallel query, pg\_waldump) |
| Backend | FastAPI (Python) atau Express (Node); SQL mentah. ⚠ Belum dikunci; usulan default: FastAPI |
| Frontend | React atau Next.js. ⚠ Belum dikunci; usulan default: React |
| Grafik | Chart.js atau Metabase. ⚠ Belum dikunci; usulan default: Chart.js |
| Lingkungan | Docker Compose bersama, versi PostgreSQL dan data seed sama di semua laptop |
| Data uji | Skrip Python (Faker id\_ID) + generate\_series + COPY, seed acak tetap |
| Uji performa | Jalankan ANALYZE sebelum uji; EXPLAIN (ANALYZE, BUFFERS) dua kali per skenario (run pertama terpengaruh cache) |
| Konkurensi | pgbench atau k6, 200 koneksi, kuota 50 (K1) |
| Keamanan | password\_hash, JWT, otorisasi per request, benchmark hanya kueri baca yang telah ditentukan |

**Catatan agar tidak salah saat presentasi**

- PostgreSQL tidak punya tipe Bitmap Index. Yang ada adalah *Bitmap Index Scan* hasil gabungan indeks B-Tree. Untuk kardinalitas rendah pakai B-Tree atau partial index, lalu tunjukkan planner memakai Bitmap Scan.
- WAL mirip ARIES (redo saat recovery), tetapi undo dicapai lewat MVCC, bukan log undo eksplisit. Jelaskan sebagai pemetaan konsep.

## 12. Deliverable Akademik per Bab

| Bab | Topik | Implementasi | Bukti presentasi |
| --- | --- | --- | --- |
| 1 | BCNF dan 4NF | Dekomposisi produk menjadi varian dan pickup | Dokumen DF, MVD, anomali (3 varian × 2 pickup = 6 baris redundan), uji lossless join dan dependency preservation |
| 2 | SQL lanjut | Correlated subquery, CTE, window function, recursive CTE | 03\_queries.sql dengan hasil |
| 3 | DDL dan DML | Constraint ketat, seeder 100k+ | 01\_schema.sql, 02\_seed.sql |
| 4 | Recovery dan logging | Demo crash, WAL, pemetaan ARIES | Rekaman layar dan log |
| 5 | Indexing | B-Tree komposit, partial index, bitmap scan | Tabel ukuran indeks dan biaya tulis |
| 6 | Query processing | Estimasi I/O, Nested Loop vs Hash Join | Tabel teori vs cost planner vs waktu aktual |
| 7 | Query optimization | 5 skenario sebelum dan sesudah | Grafik waktu eksekusi |
| 9 | Basis data paralel | Range partitioning, parallel aggregate | Tabel speedup dan efisiensi |
| 13 | DW dan OLAP | Star schema, ETL, ROLLUP, CUBE | Dashboard OLAP |

### 12.1 Rencana indeks (Bab 5)

| Indeks | Kolom | Tipe | Tujuan |
| --- | --- | --- | --- |
| idx\_sesi\_tgl\_status | (tanggal\_jualan, status\_sesi) | B-Tree komposit | Radar harian |
| idx\_pesanan\_waktu | (waktu\_pesan) | B-Tree | Range query periode |
| idx\_pesanan\_antrean | (status\_pesanan) WHERE status\_pesanan IN ('PENDING','PAID') | Partial | Antrean seller |
| idx\_spot\_fakultas | (id\_fakultas) | B-Tree kardinalitas rendah | Bitmap scan bila digabung kondisi lain |
| idx\_pesanan\_user | (id\_mahasiswa, waktu\_pesan DESC) | B-Tree komposit | Riwayat pesanan |

Tabel eksperimen wajib: ukuran indeks (pg\_relation\_size), waktu insert 100k baris dengan dan tanpa indeks, selektivitas kolom.

### 12.2 Estimasi biaya (Bab 6)

Parameter n\_r, b\_r, f\_r, blok 8 KB, buffer M. Nested-Loop Join blok: b\_r × b\_s + b\_r transfer. Hash Join: 3(b\_r + b\_s) + 4n\_h transfer. Bandingkan hitungan manual, cost planner, dan waktu aktual; jelaskan selisih (cache, statistik, work\_mem). Paksa algoritma dengan `SET enable_hashjoin = off; SET enable_nestloop = off;`.

### 12.3 Lima skenario optimasi (Bab 7)

1. Radar harian: Seq Scan → Index atau Bitmap Scan.
2. Riwayat pesanan satu pengguna.
3. Agregasi omzet per bulan (partition pruning).
4. Join pesanan, pengguna, sesi dengan filter selektif.
5. Sargability: `WHERE date(waktu_pesan) = ...` tidak memakai indeks, diperbaiki menjadi kueri rentang.

### 12.4 Partisi dan paralel (Bab 9)

Partisi range bulanan pada pesanan\_danus; buktikan partition pruning lewat EXPLAIN. Uji agregasi dengan max\_parallel\_workers\_per\_gather = 0, 2, 4; hitung speedup T1/Tn dan efisiensi speedup/n. Bandingkan Range vs Hash partitioning. Dataset 1–5 juta baris.

### 12.5 Demo crash (Bab 4)

Sesi berkuota 100. Mulai transaksi pemesanan di psql, jangan COMMIT. Catat pg\_current\_wal\_lsn() dan txid\_current(). Satu skenario dengan `CHECKPOINT;`, satu tanpa. Matikan paksa (kill -9 postmaster atau pg\_ctl stop -m immediate). Nyalakan ulang, tunjukkan log recovery. Verifikasi: yang belum commit tidak terlihat (kuota tetap 100), yang sudah commit tetap ada. Bedah WAL dengan pg\_waldump (INSERT, UPDATE, COMMIT). Petakan ke ARIES: WAL protocol, steal/no-force, LSN, dirty page table, Analysis → Redo → Undo. Siapkan video cadangan dan skrip otomatis.

### 12.6 Data warehouse dan OLAP (Bab 13)

**Grain fakta:** satu baris per item pesanan berstatus COMPLETED.

| Tabel | Isi |
| --- | --- |
| dw.fakta\_penjualan\_danus | kuantitas\_terjual, total\_omzet, total\_modal, laba\_bersih, jumlah\_transaksi; FK ke semua dimensi |
| dw.dim\_waktu | id\_waktu, tanggal, hari, bulan, kuartal, tahun, is\_hari\_kuliah |
| dw.dim\_jam | id\_jam, jam, menit\_slot, label (mis. Jam Makan Siang) |
| dw.dim\_spot | spot → wilayah\_fakultas → universitas |
| dw.dim\_organisasi | organisasi, fakultas\_asal |
| dw.dim\_produk | varian → produk → kategori |

ETL: Extract dari tabel operasional, Transform (hitung laba, petakan surrogate key), Load ke skema dw di database yang sama; catat jumlah baris dan durasi tiap batch. Kueri wajib: `GROUP BY ROLLUP (wilayah_fakultas, nama_organisasi, kategori)`, `GROUP BY CUBE (wilayah_fakultas, kuartal, kategori)`, dan slice dan dice (MAKANAN\_BERAT, jam 11–13, Teknik). Tambah satu materialized view agregat bulanan.

## 13. Data Seeder

| Tabel | Jumlah | Catatan |
| --- | --- | --- |
| pengguna | 5.000 | Sebaran 8 fakultas tidak merata |
| organisasi\_danus | 40 |  |
| spot\_lokasi | 30 |  |
| produk\_danus | 200 | Rasio kategori realistis |
| produk\_varian | \~500 | 1–4 per produk |
| sesi\_jualan | 8.000 | Jan–Nov 2026, puncak jam 10–13 |
| pesanan\_danus | 100.000+ | Distribusi miring (sebagian produk sangat laris) |
| detail\_pesanan | \~180.000 |  |

Seed acak tetap. Data terlalu seragam membuat EXPLAIN tidak menarik karena selektivitas tidak realistis. Dataset 1–5 juta baris dibuat terpisah khusus Bab 9.

## 14. Struktur Repo dan Konvensi (usulan)

```
danusgo/
  docker-compose.yml
  db/       01_schema.sql 02_seed.sql 03_queries.sql 04_indexes.sql 05_partition.sql 06_dw_schema.sql
  seed/     generator Python (Faker id_ID, seed tetap)
  backend/  API /api/v1
  frontend/ halaman buyer, seller, admin
  docs/     PRD, normalisasi, hasil EXPLAIN, grafik, skrip demo crash
```

Konvensi: nama objek database dan API sesuai Bagian 7 dan 9; setiap file SQL idempotent atau jelas urutan jalannya; setiap perubahan skema masuk ke 01\_schema.sql dan PRD sekaligus.

## 15. Pembagian Tugas dan Jadwal

| # | Peran | Keluaran | Bergantung pada |
| --- | --- | --- | --- |
| 1 | Arsitek dan Koordinator | ERD final, normalisasi (Bab 1), papan tugas | Semua |
| 2 | DDL/DML | 01\_schema.sql, 02\_seed.sql, dataset 100k+ (Bab 3) | #1 |
| 3 | Core SQL | 03\_queries.sql, fungsi pemesanan atomik, uji konkurensi (Bab 2) | #2 |
| 4 | Indexing | 04\_indexes.sql, tabel ukuran dan biaya tulis (Bab 5) | #2 |
| 5 | Query Processing dan Optimization | Biaya I/O, skenario EXPLAIN, grafik (Bab 6, 7) | #2, #4 |
| 6 | Recovery | Skrip crash, rekaman, pemetaan ARIES (Bab 4) | #3 |
| 7 | Paralel | 05\_partition.sql, tabel speedup (Bab 9) | #2 |
| 8 | DW dan OLAP | 06\_dw\_schema.sql, ETL, kueri OLAP (Bab 13) | #2 |
| 9 | Frontend | Halaman buyer, seller, dashboard admin | #3, #8 |
| 10 | Backend/API | Endpoint, autentikasi peran, integrasi transaksi | #3, #8 |

| Tanggal | Target |
| --- | --- |
| 21–22 Nov | Kunci DBMS, ERD final, DDL berjalan, repo dan Docker Compose siap |
| 22–23 Nov | Seeder 100k selesai, indeks dan kueri Bab 2 berjalan |
| 24 Nov | Skenario EXPLAIN (Bab 6, 7) dan grafik selesai |
| 25 Nov | Slide, latihan, uji ulang di mesin berbeda |
| **26–27 Nov** | **Presentasi progres** (Bab 1, 2, 3, 5, 6, 7) |
| 28 Nov–5 Des | Recovery, partisi, DW/ETL, aplikasi web |
| 6–10 Des | Integrasi, dashboard, uji konkurensi |
| 11–13 Des | Dry-run dan perbaikan bug |
| **14 Des** | **Presentasi final** (Bab 4, 9, 13, demo web) |

## 16. Risiko dan Mitigasi

| Risiko | Mitigasi |
| --- | --- |
| EXPLAIN berbeda antar laptop | Docker Compose bersama, versi dan seed sama |
| Speedup paralel tak terlihat di data kecil | Dataset 1–5 juta baris khusus Bab 9 |
| Demo crash gagal saat presentasi | Video cadangan dan skrip otomatis |
| Web menyita waktu | Prioritaskan layar P0, sisanya mockup |
| Waktu menuju progres sangat singkat | Fokus Bab 1, 2, 3, 5, 6, 7; web ditunda ke fase final |

## 17. Pertanyaan Terbuka dan Asumsi ⚠

Butir ini muncul dari pembacaan dokumen perencanaan. Pakai default sampai tim memutuskan, lalu hapus tanda ⚠ dan perbarui bagian terkait.

| # | Isu | Default yang dipakai |
| --- | --- | --- |
| 1 | **Radar: hanya OPEN atau termasuk PRE\_ORDER?** Fitur 4.1 dan alur 6.1 menyebut sesi OPEN, tetapi GET /radar berbunyi “bisa dipesan sekarang”, dan PRE\_ORDER diterima saat sesi masih UPCOMING (BR-08). | Radar menampilkan sesi OPEN **plus** sesi UPCOMING yang punya item PRE\_ORDER dengan jendela pesan aktif. |
| 2 | Pesanan READY\_TO\_PICKUP yang tidak pernah diambil belum punya status khusus. | Seller membatalkan manual setelah sesi CLOSED. |
| 3 | Badge kuota hanya mendefinisikan >50%, <20%, dan Habis; rentang 20–50% kosong. | Tampilkan badge “Sedang” untuk 20–50%. |
| 4 | QRIS tanpa gateway. | Disimulasikan; seller menekan Konfirmasi Bayar. |
| 5 | Item sama (id\_sesi\_produk, varian, pickup) muncul dua kali dalam satu pesanan. | Ditolak VALIDASI\_GAGAL; frontend menggabungkan jumlah. |
| 6 | Tidak ada endpoint mencabut hak seller, padahal BR-13 mengantisipasinya. | Di luar lingkup; dilakukan lewat SQL (hapus baris seller). |
| 7 | ETL berulang bisa memuat ganda. | ETL idempotent: hanya memuat id\_detail yang belum ada di fakta. |
| 8 | Stack backend, frontend, grafik belum dikunci. | Lihat Bagian 11 (FastAPI, React, Chart.js). Kunci sebelum prompt kode pertama. |
| 9 | Organisasi yang belum ada di daftar pengajuan hanya bisa ditulis bebas di alasan. | Sesuai dokumen: Admin menambah organisasi lebih dulu lewat Master Data, lalu menyetujui. |

## 18. Template Prompt

Salin, isi, dan tempel bersama potongan PRD yang relevan.

```
Konteks: Proyek DanusGo, PostgreSQL 16, SQL mentah. Berikut potongan PRD dan skema (01_schema.sql) yang relevan: [tempel].

Tugas: [satu tugas kecil, mis. Buat fungsi SQL pemesanan atomik].
Bagian PRD yang dipenuhi: [mis. FR-B04, BR-01, BR-02, BR-04, BR-10, BR-15].

Batasan:
- Jangan menambah/mengubah tabel, kolom, endpoint, status, atau kode error di luar PRD.
- Pakai nama persis seperti di PRD (bahasa Indonesia, snake_case).
- Logika konsistensi ada di database/transaksi, bukan frontend.

Keluaran: [file dan nama file, mis. db/03_queries.sql].
Kriteria selesai: [mis. uji 200 koneksi, kuota 50 menghasilkan tepat 50 pesanan].
Sertakan: perintah untuk menjalankan dan memverifikasi hasilnya.
Bila ada yang ambigu, pakai default di Bagian 17 dan sebutkan.
```

Pola per jenis tugas:

- **SQL/skema:** lampirkan 01\_schema.sql, sebut BR terkait, minta kueri pembuktian.
- **Backend:** sebut endpoint dari Bagian 9, kode error dari 9.3, dan transisi dari Bagian 8.
- **Frontend:** sebut layar dari Bagian 10, endpoint-nya, dan empat kondisi tampilan.
- **Eksperimen performa:** sebut skenario Bab 7, minta EXPLAIN (ANALYZE, BUFFERS) dua kali, dan tabel hasil.
- **Laporan/slide:** sebut Bab dan “bukti presentasi” di Bagian 12; jangan mengarang angka, pakai hasil eksperimen nyata.

## 19. Glosarium

| Istilah | Arti |
| --- | --- |
| Danusan | Dana usaha: jualan panitia atau organisasi mahasiswa untuk menggalang dana |
| Spot | Titik jualan fisik di kampus (spot\_lokasi) |
| Sesi | Slot waktu jualan sebuah organisasi di sebuah spot (sesi\_jualan) |
| Kuota | Jumlah porsi per produk dalam satu sesi (sesi\_produk) |
| READY\_STOCK / PRE\_ORDER | Dijual saat sesi buka / dipesan lebih dulu dalam jendela pesan |
| LPJ | Laporan pertanggungjawaban kegiatan |
| Proker | Program kerja |
| Sargability | Kemampuan predikat WHERE memakai indeks |
