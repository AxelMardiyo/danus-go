# BAB 4: PENANGANAN CRASH, WRITE-AHEAD LOGGING (WAL) & PEMETAAN ALGORITMA ARIES

## 4.1 Landasan Teori Pemulihan Basis Data (Crash Recovery)

Keandalan sistem manajemen basis data relasional (*Relational Database Management System* / RDBMS) enterprise ditentukan oleh kemampuannya menjamin integritas data dalam situasi kegagalan perangkat keras, pemadaman listrik tiba-tiba (*power outage*), maupun terminasi paksa proses sistem operasi (*operating system crash*). Dua pilar utama dari prinsip ACID yang secara langsung dijamin oleh subsistem *recovery* adalah:

1. **Atomicity (Keutuhan):** Menjamin bahwa transaksi dieksekusi secara *all-or-nothing*. Jika sistem mengalami crash di tengah eksekusi transaksi yang belum tuntas (*in-flight transaction*), seluruh modifikasi data parsial yang telah dilakukan wajib dibatalkan (*aborted/undone*) sehingga tidak meninggalkan anomali data inkonsisten (*dirty state*).
2. **Durability (Ketahanan):** Menjamin bahwa begitu transaksi menerima konfirmasi keberhasilan (*COMMIT*), seluruh perubahan data yang diakibatkannya bersifat permanen dan dijamin tetap bertahan sekalipun sistem mati mendadak satu milidetik setelah operasi *COMMIT* dilaporkan kepada klien.

### 4.1.1 Kebijakan Manajemen Buffer: Paradigma *Steal / No-Force*

Dalam sistem basis data modern, kecepatan I/O media penyimpanan persisten (SSD/NVMe/HDD) berorde ribuan kali lebih lambat dibandingkan akses *random-access memory* (RAM). Oleh karena itu, PostgreSQL mengelola *buffer pool* bersama (*shared buffers*, dialokasikan sebesar 256 MB pada proyek DanusGo) untuk memuat blok tabel dan indeks (berukuran 8 KB per halaman). 

Hubungan antara transaksi, memori volatil (*buffer pool*), dan penyimpanan persisten diatur oleh dua dimensi kebijakan arsitektur pemulihan (*buffer management policy*):

```
                        Kebijakan Flush Halaman Dirty
                          (Buffer Eviction Policy)
                             STEAL           NO-STEAL
                    +-------------------+-------------------+
          NO-FORCE  |   PostgreSQL /    |                   |
                    |   ARIES Modern    |  Shadow Paging    |
                    | (Paling Efisien)  |                   |
  Kebijakan         +-------------------+-------------------+
  Commit Transaksi  |                   |                   |
           FORCE    |   Sistem Naif     |   Sistem Sangat   |
                    | (High Commit I/O) |   Restriktif      |
                    +-------------------+-------------------+
```

1. **Kebijakan Eviction (Steal vs. No-Steal):**
   * *Steal:* Sistem mengizinkan mekanisme *page replacement* buffer pool untuk menulis (*evict/flush*) halaman data kotor (*dirty page*) milik transaksi yang **belum di-commit** ke media penyimpanan disk guna mengosongkan bingkai memori untuk transaksi lain. Konsekuensi dari kebijakan *Steal* adalah keharusan memiliki mekanisme **UNDO** untuk membatalkan modifikasi yang terlanjur tertulis di disk jika transaksi tersebut akhirnya dibatalkan atau terputus oleh *crash*.
   * *No-Steal:* Halaman data kotor dilarang keras ditulis ke disk sebelum transaksi melakukan commit. Kebijakan ini membatasi ukuran transaksi maksimal sebesar kapasitas buffer pool dan menimbulkan inefisiensi alokasi memori yang parah.
2. **Kebijakan Commit (Force vs. No-Force):**
   * *Force:* Mengharuskan setiap transaksi yang melakukan *COMMIT* untuk menulis seluruh halaman data 8 KB yang dimodifikasinya langsung ke disk fisik sebelum mengembalikan status sukses ke klien. Kebijakan ini menimbulkan lonjakan I/O acak (*random I/O bottleneck*) yang masif saat transaksi berkecepatan tinggi.
   * *No-Force:* Transaksi diizinkan melakukan *COMMIT* tanpa harus menulis halaman data fisik ke disk seketika. Sistem cukup menjamin bahwa catatan perubahan (*log record*) telah tersimpan aman di disk. Konsekuensi dari kebijakan *No-Force* adalah keharusan memiliki mekanisme **REDO** untuk merekonstruksi perubahan transaksi yang telah commit jika data page di disk belum sempat diperbarui saat terjadi crash.

**PostgreSQL secara penuh mengadopsi arsitektur Steal / No-Force.** Paradigma ini menghasilkan performa *throughput* transaksi paling optimal, namun menuntut kehadiran subsistem pencatatan log transaksi yang sangat tangguh: **Write-Ahead Logging (WAL)**.

### 4.1.2 Prinsip Write-Ahead Logging (WAL) dan Struktur LSN

Prinsip dasar dari *Write-Ahead Logging* (*WAL Protocol*) menyatakan:
$$\text{WAL Record LSN} \le \text{Flushed Log LSN} \quad \text{sebelum} \quad \text{PageLSN ditulis ke Disk}$$

Artinya:
> *"Setiap perubahan pada halaman data basis data tidak boleh ditulis ke media penyimpanan permanen sebelum catatan log WAL yang mendeskripsikan perubahan tersebut telah di-flush dan disinkronkan (fsync) ke media penyimpanan persisten."*

Dalam PostgreSQL, setiap operasi yang memodifikasi data (misalnya `INSERT`, `UPDATE`, `DELETE`, pembuatan indeks, hingga transaksi DDL) menghasilkan record biner WAL. Setiap record diidentifikasi secara unik oleh bilangan integer 64-bit yang disebut **Log Sequence Number (LSN)**. 
LSN merepresentasikan posisi byte offset logikal di dalam aliran log transaksi yang tersimpan di direktori `pg_wal` (terbagi dalam berkas-berkas segmen berukuran 16 MB).

Format penulisan LSN dinyatakan dalam notasi heksadesimal:
$$\text{LSN} = \text{Logical Segment ID} \,/\, \text{Segment Byte Offset} \quad (\text{contoh: } \texttt{0/082E7950})$$

Setiap halaman 8 KB di PostgreSQL memiliki header `PageHeaderData` yang memuat field `pd_lsn` (*PageLSN*). Nilai ini mencatat LSN dari record WAL terakhir yang mengubah halaman tersebut. Selama proses pemulihan (*recovery*), pembandingan antara `PageLSN` pada disk dengan LSN pada record WAL memungkinkan engine menentukan secara presisi apakah suatu record WAL perlu di-redo pada halaman tersebut ataukah halaman tersebut sudah dalam kondisi mutakhir (*idempotency of redo*).

### 4.1.3 Algoritma Pemulihan ARIES (Algorithms for Recovery and Isolation Exploiting Semantics)

Algoritma ARIES (dikembangkan oleh C. Mohan dkk. di IBM Almaden Research Center) merupakan standar emas pemulihan basis data berbasis *WAL, Steal/No-Force, dan Repeating History*. ARIES beroperasi melalui 3 fase terstruktur saat sistem dinyalakan ulang pasca crash:

```
                    TITIK CRASH SISTEM (SIGKILL)
                               |
                               v
+--------------------------------------------------------------------------+
| 1. ANALYSIS PHASE (Memindai WAL Maju dari Checkpoint Terakhir)           |
|    * Membaca Checkpoint Record & status Active Transactions              |
|    * Merekonstruksi Dirty Page Table (DPT) & Transaction Table (TT)      |
|    * Menentukan LSN terkecil dari halaman kotor (RedoLSN)                |
|    * Mengidentifikasi transaksi aktif yang belum commit ("Losers")       |
+--------------------------------------------------------------------------+
                               |
                               v
+--------------------------------------------------------------------------+
| 2. REDO PHASE / "Repeating History" (Memindai WAL Maju dari RedoLSN)     |
|    * Mengulang SEMUA perubahan (baik transaksi committed maupun losers)  |
|    * Membawa status fisik basis data kembali persis ke detik saat crash  |
|    * Menulis halaman data ke buffer dengan PageLSN yang diperbarui       |
+--------------------------------------------------------------------------+
                               |
                               v
+--------------------------------------------------------------------------+
| 3. UNDO PHASE (Memindai WAL Mundur / Mengeliminasi Efek Transaksi Losers)|
|    * Membatalkan seluruh modifikasi milik transaksi Losers               |
|    * Menulis Compensation Log Records (CLR) agar Undo bersifat idempoten |
|    * Mengembalikan seluruh kuota dan entitas ke status konsisten         |
+--------------------------------------------------------------------------+
                               |
                               v
                    DATABASE SIAP MENERIMA KONEKSI
```

1. **Fase Analisis (Analysis Phase):**
   Engine membaca record *Checkpoint* terakhir yang tercatat di file kendali (*control file* `global/pg_control`). Dari titik ini, engine memindai WAL ke depan (*forward scan*) hingga akhir berkas log untuk mengidentifikasi:
   * Seluruh transaksi yang sedang berjalan (*in-flight*) saat crash terjadi dan belum menulis record *COMMIT* (disebut transaksi *Losers*).
   * Nilai *RedoLSN*, yaitu LSN tertua di mana sebuah *dirty page* pertama kali dimodifikasi dan belum sempat ditulis ke disk.
2. **Fase Redo (Redo Phase):**
   Engine memulai pemindaian maju dari *RedoLSN* hingga akhir log. Pada fase ini, engine menerapkan prinsip **Repeating History**: *semua* perubahan yang tercatat di WAL dieksekusi ulang persis seperti urutan kejadiannya sebelum crash, termasuk perubahan yang dibuat oleh transaksi *Losers*. Jika sebuah halaman disk telah memiliki $\text{PageLSN} \ge \text{Record LSN}$, operasi redo dilewati (*skipped*). Pada akhir fase Redo, kondisi fisik basis data di memori identik 100% dengan kondisi sesaat sebelum sistem mati mendadak.
3. **Fase Undo (Undo Phase):**
   Engine memindai log ke belakang (*backward scan*) untuk membatalkan semua perubahan yang diakibatkan oleh transaksi *Losers*. Pada sistem ARIES konvensional, setiap operasi pembatalan menulis *Compensation Log Record (CLR)* yang menunjuk ke *UndoNextLSN*, memastikan bahwa jika crash terulang saat fase Undo sedang berjalan, sistem tidak akan mengulang operasi undo yang telah selesai.

#### Implementasi ARIES Khusus pada PostgreSQL (MVCC-Optimized Undo)

Salah satu keunggulan arsitektur PostgreSQL terletak pada integrasi antara WAL dan **Multi-Version Concurrency Control (MVCC)**. Pada PostgreSQL:
* Setiap baris (*tuple*) di dalam tabel menyimpan metadata transaksi di headernya: `xmin` (ID transaksi pembuat baris) dan `xmax` (ID transaksi pengubah/penghapus baris), serta bit status `infomask` (`HEAP_XMIN_COMMITTED`, `HEAP_XMIN_ABORTED`).
* Status akhir setiap transaksi disimpan di status array *Commit Log* (`pg_xact` / CLOG), berukuran ringkas (2 bit per transaksi: `IN_PROGRESS`, `COMMITTED`, `ABORTED`).
* **Dampak terhadap Fase Undo:** Karena PostgreSQL menerapkan *tuple versioning*, ketika sebuah transaksi *in-flight* mengalami crash, engine **tidak perlu menulis pembatalan fisik tuple satu per satu ke disk pada fase startup**. Engine cukup menandai ID transaksi tersebut sebagai `ABORTED` di `pg_xact`. Saat transaksi berikutnya membaca halaman tersebut, aturan visibilitas MVCC (*heap tuple visibility*) secara instan mengabaikan baris tersebut karena `xmin` berstatus `ABORTED`. Halaman lama yang mati (*dead tuples*) selanjutnya akan dibersihkan secara asinkron oleh *Autovacuum*. Pendekatan ini membuat durasi startup pemulihan PostgreSQL menjadi salah satu yang tercepat di industri RDBMS.

---

## 4.2 Metodologi Pengujian dan Arsitektur Simulasi Crash

Untuk membuktikan secara empiris bahwa sistem DanusGo kebal terhadap *data corruption* dan mampu memulihkan diri sesuai prinsip ARIES, dirancang protokol pengujian crash terotomasi pada container Docker `danusgo-db` menggunakan skrip Python [reports/benchmark/simulate_crash.py](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/reports/benchmark/simulate_crash.py).

### 4.2.1 Parameter Konfigurasi Engine Database

Pada [docker-compose.yml](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/docker-compose.yml), parameter berikut dikunci secara ketat:
* `restart: "no"`: Menjamin bahwa container yang dimatikan paksa tidak melakukan restart otomatis di latar belakang, sehingga status crash dan log *redo* dapat ditangkap secara deterministik.
* `log_checkpoints = on`: Memaksa engine mencatat rincian checkpoint ke output log standar (jumlah buffer yang ditulis, durasi sync, dan posisi LSN).
* `log_min_messages = info`: Menampilkan pesan diagnostik lengkap dari subsistem *recovery* PostgreSQL.

### 4.2.2 Desain Dua Skenario Eksperimen

Pengujian dirancang dengan membandingkan dua kondisi batas (*boundary conditions*):

| Parameter Uji | Skenario 1 (Tanpa Checkpoint Eksplisit) | Skenario 2 (Dengan Checkpoint Eksplisit) |
|---|---|---|
| **Tabel Uji** | `uji_crash_kuota` (Kuota Awal = 100) | `uji_crash_kuota` (Status Lanjutan, Kuota = 90) |
| **Transaksi Committed ($T_{\text{commit}}$)** | Transaksi $T_1$ (`txid = 989`), kurangi kuota 10 (Sisa 90), di-`COMMIT`. | Transaksi $T_3$ (`txid = 991`), kurangi kuota 10 (Sisa 80), di-`COMMIT`. |
| **Intervensi Checkpoint** | **Tidak ada.** Mengandalkan interval checkpoint otomatis. | **Eksplisit (`CHECKPOINT;`).** Seluruh dirty buffer di-flush paksa ke disk. |
| **Transaksi In-Flight ($T_{\text{uncommit}}$)** | Transaksi $T_2$ (`txid = 990`), kurangi kuota 40 (Sisa kotor 50), **tanpa COMMIT**. | Transaksi $T_4$ (`txid = 992`), kurangi kuota 30 (Sisa kotor 50), **tanpa COMMIT**. |
| **Metode Pemadaman Paksa** | Sinyal `SIGKILL` (`kill -s KILL` / `kill -9`) langsung ke proses postmaster. | Sinyal `SIGKILL` (`kill -s KILL` / `kill -9`) langsung ke proses postmaster. |
| **Metode Observasi** | Tangkap log engine Docker, jalankan `pg_waldump` biner, dan validasi data. | Tangkap log engine Docker, jalankan `pg_waldump` biner, dan validasi data. |

---

## 4.3 Hasil Pengujian Empiris & Analisis Log Engine

Eksekusi simulasi crash pada lingkungan pengujian menghasilkan rekaman log pemulihan aktual sebagai berikut:

### 4.3.1 Rekaman Log Skenario 1: Crash Tanpa Checkpoint Eksplisit

```text
2026-11-24 00:56:07.177 WIB [29] LOG:  database system was not properly shut down; automatic recovery in progress
2026-11-24 00:56:07.180 WIB [29] LOG:  redo starts at 0/82C0B18
2026-11-24 00:56:07.181 WIB [29] LOG:  redo done at 0/82E7A08 system usage: CPU: user: 0.00 s, system: 0.00 s, elapsed: 0.00 s
2026-11-24 00:56:07.185 WIB [27] LOG:  checkpoint starting: end-of-recovery immediate wait
2026-11-24 00:56:07.203 WIB [27] LOG:  checkpoint complete: wrote 38 buffers (0.1%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.005 s, sync=0.007 s, total=0.020 s; sync files=29, longest=0.002 s, average=0.001 s; distance=155 kB, estimate=155 kB; lsn=0/82E7A40, redo lsn=0/82E7A40
2026-11-24 00:56:07.208 WIB [1] LOG:  database system is ready to accept connections
```

*Analisis Log Skenario 1:*
1. Baris `database system was not properly shut down` mengonfirmasi bahwa PostgreSQL mendeteksi flag `DB_IN_PRODUCTION` pada berkas `global/pg_control`, menandakan proses sebelumnya mati mendadak tanpa melalui prosedur *clean shutdown*.
2. Engine langsung memicu *automatic recovery* dan memulai fase Redo pada **LSN `0/82C0B18`** (titik checkpoint sebelum pengujian dimulai).
3. Redo memproses seluruh record WAL hingga **LSN `0/82E7A08`** dengan total volume WAL sebesar **155 kB**.
4. Setelah fase Redo tuntas, engine mengeksekusi checkpoint penutup pemulihan (*end-of-recovery checkpoint* pada LSN `0/82E7A40`), menulis 38 buffer kotor ke disk dalam waktu 20 milidetik, lalu membuka kembali akses koneksi klien.

### 4.3.2 Rekaman Log Skenario 2: Crash Pasca Checkpoint Eksplisit

```text
2026-11-24 00:56:08.551 WIB [27] LOG:  checkpoint starting: immediate force wait
2026-11-24 00:56:08.565 WIB [27] LOG:  checkpoint complete: wrote 6 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.002 s, sync=0.004 s, total=0.014 s; sync files=5, longest=0.002 s, average=0.001 s; distance=0 kB, estimate=140 kB; lsn=0/82E7CA8, redo lsn=0/82E7C70
2026-11-24 00:56:10.901 WIB [29] LOG:  database system was not properly shut down; automatic recovery in progress
2026-11-24 00:56:10.903 WIB [29] LOG:  redo starts at 0/82E7C70
2026-11-24 00:56:10.904 WIB [29] LOG:  redo done at 0/82E7CA8 system usage: CPU: user: 0.00 s, system: 0.00 s, elapsed: 0.00 s
2026-11-24 00:56:10.908 WIB [27] LOG:  checkpoint starting: end-of-recovery immediate wait
2026-11-24 00:56:10.919 WIB [27] LOG:  checkpoint complete: wrote 3 buffers (0.0%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.004 s, sync=0.002 s, total=0.013 s; sync files=2, longest=0.001 s, average=0.001 s; distance=0 kB, estimate=0 kB; lsn=0/82E7D20, redo lsn=0/82E7D20
2026-11-24 00:56:10.923 WIB [1] LOG:  database system is ready to accept connections
```

*Analisis Komparatif (Efek Checkpoint terhadap Jendela Redo ARIES):*
* Pada Skenario 1, fase Redo harus memproses catatan log sepanjang **155 kB** mulai dari LSN `0/82C0B18`.
* Pada Skenario 2, keberadaan perintah `CHECKPOINT;` eksplisit berhasil memajukan titik awal Redo (*RedoLSN*) ke **LSN `0/82E7C70`**. Jarak log yang wajib dipindai menyusut menjadi hampir nol (**0 kB**), memangkas waktu pemulihan secara drastis (*instantaneous recovery*). Hal ini membuktikan fungsi teoretis checkpoint dalam membatasi panjang log yang harus dibaca ulang saat sistem crash.

---

## 4.4 Verifikasi Konsistensi Data (Pembuktian ACID)

Setelah database berhasil pulih seutuhnya, dilakukan pemeriksaan integritas data langsung pada relasi tabel `uji_crash_kuota`:

| Parameter Data | Nilai Sebelum Crash | Nilai Pasca Recovery | Status Verifikasi Akademik |
|---|:---:|:---:|:---:|
| **Skenario 1:** Kuota Pasca $T_1$ (Committed) | 90 | **90** | **TERBUKTI PERSISTEN (Durability)** |
| **Skenario 1:** Kuota Kotor Pasca $T_2$ (In-Flight) | 50 (hanya di memori $T_2$) | **90** (Nilai 50 musnah) | **TERBUKTI BATAL (Atomicity & Undo)** |
| **Skenario 2:** Kuota Pasca $T_3$ (Committed) | 80 | **80** | **TERBUKTI PERSISTEN (Durability)** |
| **Skenario 2:** Kuota Kotor Pasca $T_4$ (In-Flight) | 50 (hanya di memori $T_4$) | **80** (Nilai 50 musnah) | **TERBUKTI BATAL (Atomicity & Undo)** |

Data menunjukkan bahwa nilai modifikasi kotor (*dirty update*) sebesar 50 yang diinisiasi oleh transaksi $T_2$ dan $T_4$ **tidak pernah bocor ke pembaca lain dan tereliminasi sempurna**. Sebaliknya, nilai transaksi yang telah melakukan `COMMIT` ($T_1 = 90$ dan $T_3 = 80$) **tetap bertahan secara utuh tanpa kehilangan satu byte pun**.

---

## 4.5 Bedah Biner Catatan WAL (`pg_waldump`) & Pemetaan Transaksi

Bukti empiris terkuat atas mekanisme kerja logging PostgreSQL didapatkan melalui pembacaan langsung berkas biner log menggunakan utilitas `pg_waldump`. Cuplikan log WAL yang tersimpan pada [reports/benchmark/waldump_evidence.txt](file:///d:/College/Semester%203/Basis%20Data%20Lanjut/FP/reports/benchmark/waldump_evidence.txt) menyajikan rincian berikut:

```text
1. rmgr: Heap        len: 71,  tx: 989, lsn: 0/082E7950, desc: HOT_UPDATE old_xmax: 989, old_off: 1, new_off: 2, rel 1663/16384/17920 blk 0
2. rmgr: Transaction len: 34,  tx: 989, lsn: 0/082E7998, desc: COMMIT 2026-11-24 00:56:04.596041 WIB
3. rmgr: Heap        len: 71,  tx: 990, lsn: 0/082E79C0, desc: HOT_UPDATE old_xmax: 990, old_off: 2, new_off: 3, rel 1663/16384/17920 blk 0
4. rmgr: Standby     len: 54,  tx: 0,   lsn: 0/082E7A08, desc: RUNNING_XACTS nextXid 991 latestCompletedXid 989 oldestRunningXid 990; 1 xacts: 990
5. rmgr: XLOG        len: 114, tx: 0,   lsn: 0/082E7A40, desc: CHECKPOINT_SHUTDOWN redo 0/82E7A40 ...
6. rmgr: Heap        len: 393, tx: 991, lsn: 0/082E7AB8, desc: HOT_UPDATE old_xmax: 991, old_off: 2, new_off: 4, rel 1663/16384/17920 blk 0 FPW
7. rmgr: Transaction len: 34,  tx: 991, lsn: 0/082E7C48, desc: COMMIT 2026-11-24 00:56:08.548753 WIB
8. rmgr: XLOG        len: 114, tx: 0,   lsn: 0/082E7CA8, desc: CHECKPOINT_ONLINE redo 0/82E7C70 ...
```

### 4.5.1 Interpretasi Struktur Record WAL

1. **Baris 1 & 2 (Transaksi $T_1$, txid = 989):**
   * Record `rmgr: Heap` pada LSN `0/082E7950` mencatat operasi `HOT_UPDATE` (*Heap-Only Tuple*) pada relasi OID `17920` (tabel `uji_crash_kuota`), memindahkan baris dari offset 1 ke offset 2 pada blok 0.
   * Tepat setelahnya, pada LSN `0/082E7998`, tercatat record `rmgr: Transaction` dengan deskripsi `COMMIT 2026-11-24 00:56:04.596041 WIB`. Record ini mengonfirmasi bahwa status transaksi 989 telah permanen (*durable*).
2. **Baris 3 & 4 (Transaksi $T_2$, txid = 990 - Transaksi Crash):**
   * Record `rmgr: Heap` pada LSN `0/082E79C0` mencatat operasi pembaruan kuota oleh transaksi 990.
   * **TEMUAN KRUSIAL:** Setelah LSN `0/082E79C0`, **TIDAK PERNAH DITEMUKAN record `rmgr: Transaction ... COMMIT` untuk txid 990!**
   * Sebaliknya, record berikutnya pada LSN `0/082E7A08` adalah `rmgr: Standby` bertipe `RUNNING_XACTS`, yang secara eksplisit mencatat bahwa saat sistem crash:
     $$\texttt{latestCompletedXid = 989}, \quad \texttt{oldestRunningXid = 990}, \quad \texttt{active xacts: [990]}$$
   * Catatan ini menjadi bukti biner otentik bahwa transaksi 990 terputus saat masih berstatus *in-flight*.
3. **Baris 6, 7 & 8 (Transaksi $T_3$ & Checkpoint):**
   * Record LSN `0/082E7C48` mengonfirmasi `COMMIT` transaksi 991.
   * Record LSN `0/082E7CA8` mencatat `CHECKPOINT_ONLINE` dengan `redo 0/82E7C70`. Catatan ini yang kemudian dibaca oleh proses recovery saat start-up pasca crash kedua.

---

## 4.6 Pemetaan Rinci Siklus Recovery ke Algoritma ARIES

Berdasarkan bukti empiris pengujian dan pembacaan catatan WAL, mekanisme pemulihan crash pada PostgreSQL dihubungkan secara sistematis dengan konsep teoretis **Algoritma ARIES**:

| Komponen / Fase ARIES | Teori Algoritma ARIES (C. Mohan) | Implementasi Nyata pada PostgreSQL (DanusGo) | Bukti Empiris Proyek |
|---|---|---|---|
| **Pencatatan Log** | *Write-Ahead Logging* dengan nomor urut LSN monotonik naik | Aliran biner WAL di direktori `pg_wal`, dialokasikan per segmen 16 MB | Setiap record memiliki LSN unik (`0/082E7950`, `0/082E7998`, dst.) |
| **Kebijakan Buffer** | *Steal / No-Force* | Dirty page dapat di-*evict* oleh background writer; commit hanya menuntut flush WAL | Perubahan $T_2$ sempat tercatat di blok data tanpa status commit |
| **Titik Sinkronisasi** | *Fuzzy Checkpointing* dengan *Dirty Page Table* (DPT) & *Transaction Table* (TT) | `CHECKPOINT_ONLINE` / `CHECKPOINT_SHUTDOWN` yang mencatat *Redo LSN* dan `RUNNING_XACTS` | Record `XLOG` LSN `0/082E7CA8` mencatat titik `redo 0/82E7C70` |
| **Fase 1: Analysis** | Membaca log maju dari checkpoint terakhir, menyusun daftar transaksi *Losers* | Engine membaca `pg_control`, memindai WAL maju, menemukan transaksi aktif `990` | Log: `automatic recovery in progress`, `1 xacts: 990` |
| **Fase 2: Redo** | *Repeating History* dari *RedoLSN* hingga akhir WAL untuk semua transaksi | Memindai log dari `0/82C0B18` (Skenario 1) atau `0/82E7C70` (Skenario 2), mengulang operasi heap | Log: `redo starts at 0/82E7C70`, `redo done at 0/82E7CA8` |
| **Fase 3: Undo** | Memindai mundur log, membatalkan transaksi *Losers*, menulis record CLR | **Dioptimasi via MVCC:** Transaksi 990 ditandai `ABORTED` pada array status `pg_xact`. Tuple tidak terlihat oleh pembaca. | Kuota aktual kembali ke 90 (Skenario 1) dan 80 (Skenario 2) secara instan tanpa rollback fisik |

---

## 4.7 Ringkasan Bab

Melalui perancangan skrip pengujian crash terotomasi dan bedah berkas biner WAL menggunakan `pg_waldump`, implementasi subsistem recovery DanusGo telah berhasil membuktikan:
1. **Garansi Integritas Data ACID:** Transaksi yang telah commit memiliki ketahanan absolut (*Durability* 100%), sedangkan transaksi yang terputus oleh crash terisolasi dan dibatalkan secara sempurna (*Atomicity* 100%).
2. **Efektivitas Checkpoint:** Keberadaan checkpoint membatasi ukuran jendela redo log dari 155 kB menjadi 0 kB, membuktikan bahwa interval checkpoint yang tepat mampu menjamin waktu *Recovery Time Objective (RTO)* mendekati nol detik.
3. **Kesesuaian ARIES:** Arsitektur pemulihan engine PostgreSQL terbukti mematuhi tahapan ARIES (Analysis, Redo, Undo) dengan optimalisasi performa tinggi melalui mekanisme MVCC.
