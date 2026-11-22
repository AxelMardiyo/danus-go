# BAB 6. PEMROSESAN KUERI DAN ESTIMASI BIAYA I/O TEORETIS

## 6.1 Parameter Fisik dan Arsitektur Penyimpanan Basis Data

Pemrosesan kueri (*query processing*) di dalam sistem basis data relasional melibatkan serangkaian tahapan: penguraian sintaks (*parsing*), penerjemahan ke aljabar relasional, optimasi rencana eksekusi oleh *Query Optimizer*, dan eksekusi fisik oleh *Query Execution Engine*.

Biaya (*cost*) eksekusi kueri pada dasarnya didominasi oleh transfer blok masukan/keluaran (*I/O block transfers*) antara media penyimpanan sekunder (disk) dan memori utama (RAM). Untuk mengkaji performa kueri secara ilmiah, ditentukan parameter fisik basis data DanusGo berdasarkan konfigurasi mesin PostgreSQL 16:

*Tabel 6.1 Parameter Fisik Penyimpanan Basis Data DanusGo.*

| Parameter Simbol | Deskripsi Parameter | Nilai Konfigurasi / Pengukuran Aktual |
| :---: | :--- | :---: |
| $B$ | Ukuran halaman blok standar (*page block size*) | $8.192\text{ bytes}$ ($8\text{ KB}$) |
| $M$ | Alokasi memori bersama buffer pool (`shared_buffers`) | $256\text{ MB} = 32.768\text{ blok halaman}$ |
| $W$ | Alokasi memori kerja komputasi sort/hash (`work_mem`) | $16\text{ MB} = 2.048\text{ blok halaman}$ |
| $r$ | Relasi luar (*outer relation*): `sesi_jualan` | $n_r = 8.000\text{ tuple}$, $b_r = 67\text{ blok}$ (filter aktif) / $181\text{ blok}$ (total) |
| $s$ | Relasi dalam (*inner relation*): `pesanan_danus` | $n_s = 105.000\text{ tuple}$, $b_s = 1.669\text{ blok}$ (seluruh partisi) |
| $c_\text{seq}$ | Biaya pembacaan halaman sekuensial (`seq_page_cost`) | $1{,}00$ (konstanta dasar) |
| $c_\text{rand}$ | Biaya pembacaan halaman acak (`random_page_cost`) | $1{,}10$ (disetel optimal untuk SSD) |
| $c_\text{cpu}$ | Biaya pemrosesan tuple oleh CPU (`cpu_tuple_cost`) | $0{,}01$ |

---

## 6.2 Perhitungan Matematis Biaya Transfer Blok Join Teoretis

Studi kasus analisis ditujukan pada operasi *Equi-Join* antara `sesi_jualan` ($r$) dan `pesanan_danus` ($s$) pada predikat filter sesi bulan November 2026:
$$\sigma_{\text{tanggal\_jualan} \ge '2026-11-01'}(r) \bowtie_{r.\text{id\_sesi} = s.\text{id\_sesi}} s$$

Karakteristik tabel hasil filter:
- Relasi luar $r$ hasil filter menyaring $n_r \approx 300$ sesi aktif dengan ukuran blok $b_r \approx 67\text{ blok}$.
- Relasi dalam $s$ mencakup transaksi pesanan bulanan dengan total blok partisi aktif $b_s \approx 280\text{ blok}$ (atau $b_s = 1.669\text{ blok}$ untuk pemindaian global).

### 6.2.1 Algoritma Block Nested-Loop Join (BNLJ)
Algoritma Block Nested-Loop Join membaca relasi luar $r$ sebanyak satu blok per satu blok (atau sekelompok blok berukuran $M - 2$), lalu untuk setiap blok tersebut, relasi dalam $s$ dipindai secara keseluruhan.

#### Formulasi Biaya Matematis:
1. **Kasus Memori Terbatas ($M$ Kecil):**
   Apabila memori buffer yang dialokasikan sangat terbatas (misal kasus terburuk $M = 20\text{ blok}$):
   $$\text{Biaya Transfer I/O} = b_r + \left\lceil \frac{b_r}{M - 2} \right\rceil \times b_s$$
   Dengan $b_r = 67$, $b_s = 1.669$, dan $M - 2 = 18$:
   $$\text{Biaya Transfer} = 67 + \left\lceil \frac{67}{18} \right\rceil \times 1.669 = 67 + (4 \times 1.669) = 67 + 6.676 = \mathbf{6.743\text{ transfer blok}}$$

2. **Kasus Memori Cukup (In-Memory Outer Block):**
   Jika relasi luar $r$ muat sepenuhnya di dalam buffer memori ($M > b_r + 2$, terpenuhi karena $32.768 > 67 + 2$):
   $$\text{Biaya Transfer I/O} = b_r + b_s = 67 + 1.669 = \mathbf{1.736\text{ transfer blok}}$$
   Namun, jika Nested Loop dipadukan dengan *Index Scan* pada relasi dalam (menggunakan indeks B-Tree $s$), setiap tuple luar yang cocok akan melakukan penelusuran acak (*index probe*) ke daun pohon indeks dan tuple heap $s$.

---

### 6.2.2 Algoritma Hash Join (HJ)
Algoritma Hash Join bekerja dalam dua fase:
1. **Fase Pembangunan (*Build Phase*):** Membaca seluruh relasi luar $r$, menerapkan fungsi hash $h$ pada atribut join (`id_sesi`), dan membentuk *hash table* di memori RAM.
2. **Fase Penyelidikan (*Probe Phase*):** Membaca relasi dalam $s$ baris demi baris, menghitung nilai $h(s.\text{id\_sesi})$, lalu mencocokkannya ke dalam *hash table*.

#### Formulasi Biaya Matematis:
1. **In-Memory Hash Join:**
   Karena ukuran relasi pembangun $r$ sangat kecil ($67\text{ blok} \times 8\text{ KB} \approx 536\text{ KB}$), struktur hash table muat seutuhnya di dalam alokasi `work_mem` ($16\text{ MB}$). Tidak diperlukan partisi sementara ke disk (*no spilling to disk*).
   $$\text{Biaya Transfer I/O (In-Memory)} = b_r + b_s = 67 + 1.669 = \mathbf{1.736\text{ transfer blok}}$$

2. **Grace Hash Join (Partisi Multi-Pass ke Disk):**
   Jika memori kerja tidak mencukupi dan data harus dipartisi berulang ke disk:
   $$\text{Biaya Transfer I/O (Two-Pass)} = 3(b_r + b_s) = 3(67 + 1.669) = \mathbf{5.208\text{ transfer blok}}$$

---

## 6.3 Komparasi Empiris: Teori vs Cost Planner vs Waktu Aktual

Pengujian eksperimen dilakukan secara terkontrol dengan memaksa mesin PostgreSQL memilih salah satu algoritma melalui sakelar konfigurasi sesi (*session optimizer switches*):
- Memaksa Hash Join: `SET enable_hashjoin = on; SET enable_nestloop = off;`
- Memaksa Nested Loop Join: `SET enable_hashjoin = off; SET enable_nestloop = on;`

Kueri yang diuji:
```sql
SELECT COUNT(*) 
  FROM sesi_jualan s 
  JOIN pesanan_danus p ON s.id_sesi = p.id_sesi 
 WHERE s.tanggal_jualan >= '2026-11-01';
```

*Tabel 6.2 Matriks Komparasi Algoritma Join: Teori, Planner Cost, dan Pengukuran Aktual.*

| Algoritma Join | Estimasi Transfer Blok Teoretis | Planner Cost (`cost=..`) | Waktu Eksekusi Aktual (ms) | Shared Buffers (Hit / Read) |
| :--- | :---: | :---: | :---: | :---: |
| **Hash Join (Forced)** | $\approx 1.736\text{ blok}$ | `cost=3.879,29` | **16,21 ms** | **Hit: 1.736** / Read: 0 |
| **Nested Loop (Forced)** | $\approx 6.743\text{ s.d. } 28.000\text{ blok}$ | `cost=7.026,22` | **16,31 ms** | **Hit: 29.307** / Read: 0 |

---

## 6.4 Analisis Diskrepansi (Selisih Teori, Cost Optimizer, dan Realita)

Dari hasil eksperimen di atas, terdapat fenomena menarik yang membutuhkan penelusuran teoritis mendalam:

### 1. Akurasi Prediksi Transfer Blok pada Hash Join
Jumlah *shared buffer hit* riil yang dicatat oleh PostgreSQL pada Hash Join adalah **tepat 1.736 blok**. Angka pengukuran nyata ini **100% identik** dengan hasil perhitungan matematis $b_r + b_s = 67 + 1.669 = 1.736\text{ blok}$. Hal ini membuktikan bahwa algoritma in-memory hash join memindai kedua tabel secara murni satu kali pemindaian berurutan (*single pass*).

### 2. Lonjakan Pemindaian Buffer pada Nested Loop
Pada Nested Loop, jumlah *shared buffer hit* melonjak drastis hingga **29.307 blok** ($16{,}8\times$ lipat lebih banyak dibandingkan Hash Join). Lonjakan ini terjadi karena untuk setiap tuple sesi jualan yang lolos kualifikasi, pointer indeks harus memindai ulang blok daun B-Tree dan halaman heap `pesanan_danus` secara berulang kali.

### 3. Mengapa Waktu Eksekusi Nested Loop Tetap Mendekati Hash Join (16,31 ms vs 16,21 ms)?
Secara teoretis, peningkatan pemindaian blok sebesar $16{,}8\times$ lipat seharusnya memperlambat waktu eksekusi secara proporsional. Namun, waktu aktual Nested Loop tercatat hampir sama dengan Hash Join (selisih hanya 0,10 ms).

*Penyebab Fenomena Ini:*
- **Efek Shared Buffers 100% Cache Hit:** Kolom *shared read* tercatat bernilai **0**. Artinya, seluruh $29.307$ pembacaan blok dilayani langsung dari memori RAM (*shared_buffers = 256MB*), tanpa pernah memicu latensi mekanis atau penundaan I/O fisik disk (*physical disk access*). Karena latensi akses RAM berada pada skala nanodetik ($~100\text{ ns}$), eksekusi $29.000$ operasi pembacaan di memori berlangsung nyaris instan.
- **Formulasi Cost Planner yang Konservatif:** Query planner PostgreSQL memberikan estimasi biaya yang jauh lebih tinggi pada Nested Loop (`cost=7.026,22` berbanding `cost=3.879,29` pada Hash Join). Formula biaya optimizer memperhitungkan probabilitas terjadinya *random I/O* pada skala beban produksi yang lebih besar, di mana data tidak selalu muat di dalam buffer pool.

---

## 6.5 Kesimpulan Bab 6

Analisis pemrosesan kueri dan estimasi biaya transfer blok membuktikan bahwa:
1. **Ketepatan Teori I/O:** Formulasi transfer blok in-memory hash join terbukti akurat merefleksikan jumlah blok fisik yang disentuh mesin PostgreSQL ($1.736$ blok).
2. **Kecerdasan Query Optimizer:** PostgreSQL Query Optimizer secara cerdas memilih Hash Join sebagai strategi *default* karena memiliki *cost* terendah ($3.879,29$) dan meminimalisasi pemindaian halaman memori.
3. **Pentingnya Buffer Caching:** Alokasi memori `shared_buffers` yang memadai terbukti mampu meredam inefisiensi transfer blok pada algoritma yang kurang optimal, memastikan performa basis data tetap berada di rentang latensi rendah (sub-20 ms).
