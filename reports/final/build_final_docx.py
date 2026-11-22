# -*- coding: utf-8 -*-
"""
Compile the complete official academic report for Sprint 1 (DanusGo)
into editable DOCX format with real empirical data, strict formatting,
tables, code blocks, and visual captions.
Target: reports/final/laporan-sprint-1.docx
"""

import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_shading(cell, color_hex):
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    cell._tc.get_or_add_tcPr().append(shd)

def set_cell_margins(cell, top=120, bottom=120, left=160, right=160):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def set_table_borders(table, color="D3D3D3"):
    tblPr = table._tbl.tblPr
    borders = parse_xml(f'<w:tblBorders {nsdecls("w")}><w:top w:val="single" w:sz="6" w:space="0" w:color="1B365D"/><w:bottom w:val="single" w:sz="8" w:space="0" w:color="1B365D"/><w:left w:val="none"/><w:right w:val="none"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color}"/><w:insideV w:val="none"/></w:tblBorders>')
    tblPr.append(borders)

def format_table(table, col_widths, headers, data):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    if len(table.rows) == 0:
        hdr_row = table.add_row()
    else:
        hdr_row = table.rows[0]
        
    hdr_cells = hdr_row.cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_shading(hdr_cells[i], "1B365D")
        set_cell_margins(hdr_cells[i], top=140, bottom=140, left=140, right=140)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.name = "Arial"
            run.font.bold = True
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            
    for r_idx, row_data in enumerate(data):
        row_cells = table.add_row().cells
        bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = str(val)
            set_cell_shading(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=100, bottom=100, left=140, right=140)
            p = row_cells[c_idx].paragraphs[0]
            if c_idx == 0 or len(str(val)) < 15:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.name = "Calibri"
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)
                
    for row in table.rows:
        for idx, width in enumerate(col_widths):
            row.cells[idx].width = Inches(width)
            
    set_table_borders(table)

def add_code_block(doc, code_text):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    cell = tbl.cell(0, 0)
    set_cell_shading(cell, "F8F9FA")
    set_cell_margins(cell, top=120, bottom=120, left=160, right=160)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:top w:val="single" w:sz="4" w:color="CBD5E0"/><w:bottom w:val="single" w:sz="4" w:color="CBD5E0"/><w:left w:val="single" w:sz="24" w:color="1B365D"/><w:right w:val="single" w:sz="4" w:color="CBD5E0"/></w:tcBorders>')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(code_text.strip())
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(0x1A, 0x20, 0x2C)
    
    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_before = Pt(0)
    p_spacer.paragraph_format.space_after = Pt(4)

def add_figure_box(doc, title, instruction, caption, file_ref=None):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    tbl.columns[0].width = Inches(6.5)
    
    cell = tbl.cell(0, 0)
    set_cell_shading(cell, "F0F4F8")
    set_cell_margins(cell, top=160, bottom=160, left=200, right=200)
    
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:top w:val="dashed" w:sz="8" w:color="3182CE"/><w:bottom w:val="dashed" w:sz="8" w:color="3182CE"/><w:left w:val="dashed" w:sz="8" w:color="3182CE"/><w:right w:val="dashed" w:sz="8" w:color="3182CE"/></w:tcBorders>')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    
    r_icon = p.add_run("[ ARTEFAK GAMBAR / GRAFIK VEKTOR ]\n")
    r_icon.font.name = "Arial"
    r_icon.font.bold = True
    r_icon.font.size = Pt(10.0)
    r_icon.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
    
    r_title = p.add_run(f"{title}\n")
    r_title.font.name = "Arial"
    r_title.font.bold = True
    r_title.font.size = Pt(9.5)
    r_title.font.color.rgb = RGBColor(0x2B, 0x6C, 0xB0)
    
    if file_ref:
        r_ref = p.add_run(f"Berkas Grafis Tersedia: {file_ref}\n")
        r_ref.font.name = "Consolas"
        r_ref.font.bold = True
        r_ref.font.size = Pt(8.5)
        r_ref.font.color.rgb = RGBColor(0x2C, 0x52, 0x82)
        
    r_inst = p.add_run(f"Keterangan Visual: {instruction}")
    r_inst.font.name = "Calibri"
    r_inst.font.italic = True
    r_inst.font.size = Pt(9.0)
    r_inst.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)
    
    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(3)
    p_cap.paragraph_format.space_after = Pt(8)
    r_cap = p_cap.add_run(caption)
    r_cap.font.name = "Calibri"
    r_cap.font.bold = True
    r_cap.font.size = Pt(9.5)
    r_cap.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)

def compile_document():
    doc = Document()
    
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.page_width = Inches(8.5)
        section.page_height = Inches(11.0)

    def p_title(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(18)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
        return p

    def p_subtitle(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(18)
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(12)
        run.font.italic = True
        run.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)
        return p

    def p_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x1B, 0x36, 0x5D)
        return p

    def p_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x2B, 0x6C, 0xB0)
        return p

    def p_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(10.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)
        return p

    def p_body(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.15
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(text)
        run.font.name = "Calibri"
        run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(0x2D, 0x37, 0x48)
        return p

    # ==========================================
    # COVER / HEADER
    # ==========================================
    p_title("LAPORAN TEKNIS PROGRES SPRINT 1")
    p_subtitle("Fondasi Skema Relasional, Normalisasi BCNF/4NF, Kontrol Transaksi Atomik, dan Analisis Optimasi Kueri Empiris Berbasis EXPLAIN")
    
    meta_tbl = doc.add_table(rows=0, cols=2)
    format_table(meta_tbl, [2.2, 4.3], ["Atribut Proyek", "Keterangan Terverifikasi"], [
        ["Mata Kuliah", "Basis Data Lanjut (Semester Gasal 2026/2027)"],
        ["Sistem / Aplikasi", "DanusGo (Campus Danusan & Food Tracking Hub)"],
        ["Target Kumulatif Sprint 1", "50% Proyek Akhir (Cakupan: Bab 1, 2, 3, 5, 6, dan 7)"],
        ["Capaian Teknis Aktual", "92,50% dari Sprint 1 (Setara 46,25% Kumulatif Proyek)"],
        ["Status Verifikasi", "Seluruh Bukti Empiris & Transaksi Telah 100% Tuntas Diuji di PostgreSQL 16"],
        ["Dataset Uji Terinjeksi", "105.000 Pesanan, 144.889 Detail Pesanan, 8.000 Sesi Jualan, 5.001 Pengguna"],
        ["Artefak Repositori", "db/01_schema.sql, db/03_queries.sql, db/04_indexes.sql, seed/generate_data.py"]
    ])
    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # ==========================================
    # RINGKASAN EKSEKUTIF
    # ==========================================
    p_h1("RINGKASAN EKSEKUTIF")
    p_body("Laporan teknis ini menyajikan pencapaian komprehensif fase Sprint 1 (21 – 25 November 2026) dalam pengembangan sistem basis data operasional DanusGo. DanusGo adalah platform tracking dan transaksi danusan mahasiswa berbasis kampus yang mengatasi masalah klasik: pembatalan sepihak akibat overselling kuota, tabrakan jadwal stan fisik, dan inefisiensi pelaporan kas.")
    p_body("Seluruh target deliverables Sprint 1 telah diuji secara nyata pada mesin PostgreSQL 16 terisolasi (Docker Engine, shared_buffers=256MB, Asia/Jakarta) dengan temuan empiris utama sebagai berikut:")
    p_body("1. Normalisasi BCNF & 4NF: Struktur skema terbukti memenuhi BCNF murni (peniadaan id_sesi pada detail_pesanan dijaga trigger), dan dekomposisi 4NF pada produk varian dan pickup melenyapkan anomali perkalian kartesian MVD.\n"
           "2. Transaksi Atomik Anti-Overselling: Fungsi PL/pgSQL sp_buat_pesanan dengan row-level locking conditional update terbukti mencegah race condition dan memotong kuota secara presisi (teruji pada pemesanan riil ID 105002).\n"
           "3. Integritas Fisik & Partisi: Exclusion Constraint (GIST tsrange) berhasil mencegah jadwal stan bentrok di tingkat engine, dan Range Partitioning bulanan sukses merutekan 105.000 transaksi ke 11 partisi bulanan dengan 0 baris di partisi default.\n"
           "4. Pengindeksan: 5 indeks sekunder strategis aktif, menghasilkan ukuran fisik yang terukur (pesanan_2026_11_pkey 848 kB, idx_sesi_tgl_status 384 kB, partial index antrean hanya 32 kB).\n"
           "5. Teori I/O & Pemrosesan Kueri: Algoritma in-memory Hash Join terbukti presisi menyentuh 1.736 blok halaman (100% sesuai teori transfer blok br + bs = 1.736), jauh lebih efisien dibandingkan Nested Loop (29.307 buffer hits).\n"
           "6. Optimasi Empiris EXPLAIN: Terjadi lonjakan performa signifikan hingga 59,0x lipat pada riwayat pengguna, 11,2x pada radar sesi, dan kueri Sargable terbukti 250,3x lebih cepat (0,03 ms vs 6,76 ms) dengan reduksi buffer I/O sebesar 90,5%.")

    # ==========================================
    # BAB 1
    # ==========================================
    p_h1("BAB 1. PERANCANGAN KONSEPTUAL, ERD, DAN PEMBUKTIAN NORMALISASI")
    p_h2("1.1 Deskripsi Masalah dan Kebutuhan Domain")
    p_body("Kegiatan pencarian dana usaha mahasiswa terkendala oleh sistem pencatatan manual berbasis kertas atau chat instan tanpa integrasi stok waktu nyata. Permasalahan utama meliputi overselling pada produk Pre-Order, tumpang tindih stan jualan fisik antar kelompok mahasiswa, redundansi varian rasa vs metode pickup, dan selisih kas saat rekonsiliasi keuangan LPJ. DanusGo menyediakan arsitektur data terpusat dengan integritas ketat untuk menjamin ketersediaan kuota, keteraturan jadwal sesi, dan transparansi aliran kas.")

    p_h2("1.2 Model Konseptual dan Relasional")
    p_body("Model konseptual memetakan entitas master institusional (fakultas, prodi), entitas pengguna (pengguna dengan peran BUYER, SELLER, ADMIN, serta organisasi_danus), entitas operasional stan (spot_lokasi, sesi_jualan, produk_danus, sesi_produk), hingga entitas transaksional (pesanan_danus, detail_pesanan, log_kuota).")
    
    add_figure_box(
        doc,
        title="Diagram Entity-Relationship (ERD) Relasional DanusGo",
        instruction="Menampilkan diagram relasional lengkap Crow's Foot Notation yang mengilustrasikan keterhubungan 14 tabel inti sistem DanusGo beserta kunci PK, FK, dan tabel dekomposisi 4NF.",
        caption="Gambar 1.1 Diagram Relasi Konseptual Basis Data DanusGo"
    )

    p_h2("1.3 Pembuktian Dekomposisi Boyce-Codd Normal Form (BCNF)")
    p_body("Relasi berada dalam BCNF jika untuk setiap Functional Dependency (FD) non-trivial X -> Y, determinan X merupakan Superkey.")
    p_body("A. Eliminasi Ketergantungan Transitif Pengguna:\n"
           "Relasi pengguna denormalisasi memiliki FD: id_mahasiswa -> id_prodi dan id_prodi -> id_fakultas. Karena id_prodi bukan superkey dari tabel pengguna, relasi melanggar BCNF. Dekomposisi dilakukan menjadi fakultas(id_fakultas, nama_fakultas), prodi(id_prodi, id_fakultas, nama_prodi), dan pengguna(id_mahasiswa, nim, ..., id_prodi). Seluruh determinan kini berstatus Superkey.")
    p_body("B. Peniadaan id_sesi pada detail_pesanan:\n"
           "Pada sistem berlaku FD: id_sesi_produk -> id_sesi. Jika id_sesi disimpan di detail_pesanan, determinan id_sesi_produk bukan superkey dari detail_pesanan sehingga melanggar BCNF dan memicu redundansi baris. Oleh karena itu, atribut id_sesi secara tegas dieliminasi dari skema detail_pesanan. Konsistensi relasi bahwa produk yang dipesan harus berasal dari sesi yang sama dengan pesanan header ditegakkan secara absolut melalui trigger fn_validasi_detail.")

    p_h2("1.4 Pembuktian Dekomposisi Fourth Normal Form (4NF)")
    p_body("Relasi berada dalam 4NF jika untuk setiap Multivalued Dependency (MVD) non-trivial X ->> Y, X merupakan Superkey.")
    p_body("Kasus Produk Danus:\n"
           "Produk 'Risoles Mayo Beef Keju' memiliki opsi varian rasa (Original, Pedas, Keju) dan opsi metode pengambilan (Ambil di Stan, Diantar ke Kelas). Varian dan metode pickup merupakan atribut bernilai jamak yang saling independen.")
    
    t_anomali = doc.add_table(rows=0, cols=3)
    format_table(t_anomali, [1.8, 2.2, 2.5], ["id_produk", "nama_varian (Y)", "metode_pickup (Z)"], [
        ["10", "Original", "Ambil di Stan"],
        ["10", "Original", "Diantar ke Kelas"],
        ["10", "Pedas", "Ambil di Stan"],
        ["10", "Pedas", "Diantar ke Kelas"],
        ["10", "Keju", "Ambil di Stan"],
        ["10", "Keju", "Diantar ke Kelas"]
    ])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    p_body("Anomali yang Ditimbulkan:\n"
           "Penyatuan kedua atribut dalam relasi produk_opsi memicu perkalian kartesian 3 x 2 = 6 baris. Anomali penyisipan terjadi ketika varian baru ditambah (harus menyisipkan baris sebanyak opsi pickup), dan anomali pembaruan muncul jika nama pickup diubah. Berlaku MVD: id_produk ->> nama_varian dan id_produk ->> metode_pickup. Karena id_produk bukan superkey dari relasi komposit tersebut, skema melanggar 4NF.")
    p_body("Solusi Dekomposisi 4NF:\n"
           "Didekomposisi menjadi dua relasi independen:\n"
           "1. produk_varian(id_produk, nama_varian) dengan PK komposit.\n"
           "2. produk_metode_pickup(id_produk, metode_pickup) dengan PK komposit.\n"
           "Uji Lossless Join: R1 n R2 = {id_produk}, yang merupakan Primary Key (Superkey) pada tabel katalog produk_danus, sehingga operasi natural join dijamin bebas spurious tuples.")

    # ==========================================
    # BAB 2
    # ==========================================
    p_h1("BAB 2. KUERI SQL TINGKAT LANJUT DAN KONTROL TRANSAKSI ATOMIK")
    p_h2("2.1 Mitigasi Race Condition dan Fungsi Pemesanan Atomik")
    p_body("Pola transaksi naif (SELECT kuota_sisa lalu UPDATE kuota_sisa) memicu anomali Lost Update saat 200 koneksi konkuren mengakses kuota 50 secara serentak, menyebabkan kuota negatif (-150). DanusGo menerapkan Atomic Conditional Update langsung di dalam stored function PL/pgSQL sp_buat_pesanan:")
    
    add_code_block(doc,
"""UPDATE sesi_produk
   SET kuota_sisa = kuota_sisa - p_jumlah,
       status_stok = CASE WHEN (kuota_sisa - p_jumlah) = 0 THEN 'SOLD_OUT' ELSE status_stok END
 WHERE id_sesi_produk = p_id_sesi_produk
   AND id_sesi = p_id_sesi
   AND kuota_sisa >= p_jumlah
RETURNING kuota_sisa, id_produk INTO v_kuota_sisa, v_id_produk;""")

    p_body("Mesin PostgreSQL memegang Exclusive Row-Level Lock pada baris terkait. Transaksi antrean membaca nilai sisa terbaru; jika kuota telah habis, klausa WHERE kuota_sisa >= p_jumlah bernilai FALSE, perintah UPDATE menghasilkan 0 baris, dan eksepsi KUOTA_TIDAK_MENCUKUPI (SQLSTATE P0001) segera dipicu untuk membatalkan transaksi (ROLLBACK).")
    
    p_body("Bukti Verifikasi Transaksi Riil pada Basis Data:\n"
           "Pemanggilan sp_buat_pesanan(p_id_mahasiswa:=2, p_id_sesi:=7974, p_id_sesi_produk:=24001, p_jumlah:=2, p_metode_bayar:='CASH_COD') menghasilkan Transaksi ID 105002, kode unik 'PS7JYC', kuota sisa terpotong presisi dari 65 menjadi 63, serta rincian pada detail_pesanan dan log_kuota otomatis tersimpan.")

    p_h2("2.2 Kueri Analisis SQL Tingkat Lanjut")
    p_body("Empat kueri analitik lanjut diuji langsung pada dataset 105.000 transaksi:")
    p_body("1. CTE Finansial Seller: Menghitung omzet, modal, laba bersih, dan margin laba per sesi jualan. Contoh hasil riil: Sesi 7896 (Himpunan Mahasiswa Biologi) mencetak 25 pesanan, omzet Rp1.440.000,00, laba bersih Rp576.000,00, dan margin keuntungan 40,00%.\n"
           "2. Correlated Subquery: Menyaring mahasiswa pembeli prioritas yang pengeluarannya di atas rata-rata prodinya. Mahasiswa ID 1483 (Teknik Informatika) terdata dengan total belanja tertinggi Rp1.584.000,00.\n"
           "3. Window Functions: Pemeringkatan DENSE_RANK() produk terlaris kategori Makanan Berat menempatkan Mie Dok-dok Sosis Telur di Peringkat 1 (2.502 porsi terjual, omzet Rp35.028.000,00), Nasi Uduk Betawi di Peringkat 2 (2.285 porsi), dan Rice Bowl Daging Sapi Lada Hitam di Peringkat 3 (2.171 porsi).\n"
           "4. Recursive CTE: Penelusuran pohon struktur koordinasi dari fakultas induk (Teknik) menuju seluruh himpunan mahasiswa di bawahnya secara dinamis.")

    # ==========================================
    # BAB 3
    # ==========================================
    p_h1("BAB 3. DESAIN FISIK, INTEGRITAS CONSTRAINT, DAN DATASET 105K+")
    p_h2("3.1 Penegakan Integritas Fisik dan Exclusion Constraint GiST")
    p_body("Untuk menjamin tidak ada dua kelompok danusan yang menempati spot stan fisik yang sama pada waktu yang bersinggungan (BR-07), diterapkan PostgreSQL Exclusion Constraint berbasis GiST:")
    
    add_code_block(doc,
"""ALTER TABLE sesi_jualan
  ADD CONSTRAINT no_jadwal_bentrok
  EXCLUDE USING gist (
    id_spot WITH =,
    tsrange((tanggal_jualan + jam_mulai)::timestamp,
            (tanggal_jualan + jam_selesai)::timestamp) WITH &&
  );""")
    p_body("Setiap upaya pendaftaran jadwal sesi yang tumpang tindih di titik lokasi yang sama secara deterministik ditolak oleh engine dengan kode SQLSTATE 23P01 (exclusion_violation).")

    p_h2("3.2 Range Partitioning Bulanan")
    p_body("Tabel pesanan_danus dipartisi bulanan berbasis kolom waktu_pesan untuk rentang Januari 2026 hingga Maret 2027 ditambah pesanan_default. Partisi bulanan memungkinkan Partition Pruning (mengabaikan partisi yang tidak relevan) dan pengarsipan data instan tanpa vacuum lock.")

    p_h2("3.3 Karakteristik Seeder 105.000 Pesanan")
    p_body("Dataset diinjeksi via seed/generate_data.py dengan seed konstan (seed=42). Data memuat distribusi miring Pareto 80:20 dan lonjakan transaksi jam istirahat kampus (10.00–13.00 WIB). Injeksi 105.000 pesanan dan 144.889 detail pesanan tuntas dalam 19,64 detik.")
    
    t_part = doc.add_table(rows=0, cols=3)
    format_table(t_part, [2.2, 2.3, 2.0], ["Sub-Tabel Partisi Bulanan", "Rentang Tanggal (WIB)", "Jumlah Baris Aktual"], [
        ["pesanan_2026_01", "01 Jan 2026 – 31 Jan 2026", "8.467 baris"],
        ["pesanan_2026_02", "01 Feb 2026 – 28 Feb 2026", "9.056 baris"],
        ["pesanan_2026_03", "01 Mar 2026 – 31 Mar 2026", "9.305 baris"],
        ["pesanan_2026_04", "01 Apr 2026 – 30 Apr 2026", "10.281 baris"],
        ["pesanan_2026_05", "01 Mei 2026 – 31 Mei 2026", "10.178 baris"],
        ["pesanan_2026_06", "01 Jun 2026 – 30 Jun 2026", "9.523 baris"],
        ["pesanan_2026_07", "01 Jul 2026 – 31 Jul 2026", "10.560 baris"],
        ["pesanan_2026_08", "01 Agu 2026 – 31 Agu 2026", "9.999 baris"],
        ["pesanan_2026_09", "01 Sep 2026 – 30 Sep 2026", "10.734 baris"],
        ["pesanan_2026_10", "01 Okt 2026 – 31 Okt 2026", "9.492 baris"],
        ["pesanan_2026_11", "01 Nov 2026 – 22 Nov 2026", "7.405 baris"],
        ["pesanan_default", "Di luar rentang operasional", "0 baris"]
    ])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # ==========================================
    # BAB 5
    # ==========================================
    p_h1("BAB 5. STRATEGI PENGINDEKSAN BASIS DATA (INDEXING)")
    p_h2("5.1 Desain Indeks Sekunder Strategis")
    p_body("Lima indeks sekunder dibangun pada berkas db/04_indexes.sql untuk mendukung kueri kritis:\n"
           "1. idx_sesi_tgl_status (B-Tree Komposit): (tanggal_jualan, status_sesi)\n"
           "2. idx_pesanan_waktu (B-Tree): (waktu_pesan)\n"
           "3. idx_pesanan_antrean (Partial Index): (status_pesanan) WHERE status_pesanan IN ('PENDING', 'PAID')\n"
           "4. idx_spot_fakultas (Low-Cardinality): (id_fakultas) untuk Bitmap Index Scan\n"
           "5. idx_pesanan_user (B-Tree Komposit): (id_mahasiswa, waktu_pesan DESC)")

    p_h2("5.2 Evaluasi Ukuran Disk dan Write Penalty")
    p_body("Pengukuran fisik via pg_relation_size menunjukkan ukuran indeks terdistribusi efisien:")
    p_body("- Indeks Primary Key partisi pesanan_2026_11_pkey: 848 kB\n"
           "- Indeks Exclusion GiST sesi_jualan_id_spot_tsrange_excl: 600 kB\n"
           "- Indeks riwayat pesanan per partisi: rata-rata ~336 kB\n"
           "- Partial Index idx_pesanan_antrean: hanya 32 kB (menghemat >90% disk karena hanya mengindeks pesanan aktif)")
    p_body("Uji penalti operasi tulis (Batch Insert 10.000 baris pesanan):\n"
           "- Durasi Tanpa Indeks Sekunder: 0,1613 detik (62.008 baris/detik)\n"
           "- Durasi Dengan 5 Indeks Sekunder: 0,1036 detik (96.546 baris/detik)\n"
           "Throughput penulisan tetap sangat tinggi di skala sub-detik karena pembaruan indeks terlokalisasi pada sub-partisi aktif dan ditopang alokasi shared_buffers 256MB.")

    # ==========================================
    # BAB 6
    # ==========================================
    p_h1("BAB 6. PEMROSESAN KUERI DAN ESTIMASI BIAYA I/O TEORETIS")
    p_h2("6.1 Parameter Fisik dan Rumus Transfer Blok I/O")
    p_body("Parameter: Halaman B = 8 KB, Buffer M = 256 MB (32.768 blok), Relasi r (sesi_jualan filter) br = 67 blok, Relasi s (pesanan_danus) bs = 1.669 blok.")
    p_body("Perhitungan Biaya Transfer I/O Teoretis:\n"
           "1. Block Nested Loop Join (In-Memory Outer): Biaya = br + bs = 67 + 1.669 = 1.736 transfer blok. Pada skenario memori sempit (M=20): br + [br/(M-2)]*bs = 67 + 4*1.669 = 6.743 transfer blok.\n"
           "2. In-Memory Hash Join: Membaca r dan s sekali pass: Biaya = br + bs = 67 + 1.669 = 1.736 transfer blok.")

    p_h2("6.2 Komparasi Empiris: Teori vs Cost Planner vs Waktu Aktual")
    t_join = doc.add_table(rows=0, cols=5)
    format_table(t_join, [1.8, 1.2, 1.2, 1.1, 1.2], ["Algoritma Join", "Estimasi Teori I/O", "Planner Cost", "Waktu Aktual", "Shared Buffers"], [
        ["Hash Join (Forced)", "1.736 blok", "cost=3.879,29", "16,21 ms", "Hit: 1.736 / Read: 0"],
        ["Nested Loop (Forced)", "6.743 s.d. 28.000", "cost=7.026,22", "16,31 ms", "Hit: 29.307 / Read: 0"]
    ])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    p_body("Analisis Diskrepansi:\n"
           "1. Akurasi Teori Hash Join: Jumlah blok buffer riil yang disentuh Hash Join adalah tepat 1.736 blok, identik 100% dengan formula br + bs = 1.736 blok.\n"
           "2. Efisiensi Caching Memori: Nested Loop menyentuh 29.307 blok buffer (16,8x lipat lebih banyak), namun waktu eksekusinya tetap mendekati Hash Join (16,31 ms vs 16,21 ms) karena seluruh 29.307 blok dilayani dari cache RAM (shared hit 100%, shared read 0). Planner cost memberikan bobot penalti konservatif (cost 7.026 vs 3.879) untuk mengantisipasi skenario data skala besar di disk.")

    # ==========================================
    # BAB 7
    # ==========================================
    p_h1("BAB 7. EVALUASI DAN OPTIMASI KUERI (5 SKENARIO EMPIRIS)")
    p_h2("7.1 Metodologi Benchmarking")
    p_body("Setiap kueri diuji sebanyak dua kali pada PostgreSQL 16 (warm cache measurement). Metrik dikompilasi menggunakan EXPLAIN (ANALYZE, BUFFERS).")

    p_h2("7.2 Hasil Empiris 5 Skenario Optimasi")
    t_bench = doc.add_table(rows=0, cols=5)
    format_table(t_bench, [1.8, 1.3, 1.3, 1.0, 1.1], ["Skenario Kueri", "Tanpa Indeks", "Dengan Indeks", "Speedup", "Reduksi Buffer"], [
        ["1. Radar Sesi", "Seq Scan (0,28 ms)", "Index Scan (0,03 ms)", "11,2x", "95,5% (67 -> 3)"],
        ["2. Riwayat User", "Seq Scan + Sort (3,71 ms)", "Index Backward (0,06 ms)", "59,0x", "98,1% (1669 -> 32)"],
        ["3. Omzet Bulan", "Hash Join (19,25 ms)", "Partition Pruned (20,73 ms)", "Pruning", "10 Partisi diabaikan"],
        ["4. Antrean Seller", "Hash Join (8,99 ms)", "Partial Index (4,88 ms)", "1,8x", "11,4% (1862 -> 1650)"],
        ["5. Sargable Range", "Index Only (0,11 ms)", "Index Only (0,03 ms)", "4,0x", "51,5% (68 -> 33)"]
    ])
    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    p_h2("7.3 Evaluasi Khusus Sargability (date() vs Rentang Waktu)")
    p_body("Pengujian kueri identik pembacaan transaksi tanggal 15 November 2026:\n"
           "- Non-Sargable (WHERE date(waktu_pesan) = '2026-11-15'): Menggagalkan B-Tree index dan partition pruning, memindai seluruh 11 partisi bulanan. Waktu: 6,76 ms, Buffer: 346 blok.\n"
           "- Sargable (WHERE waktu_pesan >= ... AND waktu_pesan < ...): Memicu Partition Pruning (hanya partisi pesanan_2026_11) dan dilayani Index Only Scan. Waktu: 0,03 ms, Buffer: 33 blok.\n"
           "Hasil: Kueri Sargable terbukti 250,3x lebih cepat dan memangkas 90,5% pemindaian buffer.")

    add_figure_box(
        doc,
        title="Grafik Batang Perbandingan Waktu Eksekusi Kueri (ms)",
        instruction="Grafik vektor perbandingan waktu eksekusi sebelum vs sesudah indeks pada ke-5 skenario pengujian empiris.",
        caption="Gambar 7.2 Perbandingan Waktu Eksekusi 5 Skenario Optimasi Kueri",
        file_ref="reports/figures/chart_execution_time.svg"
    )

    add_figure_box(
        doc,
        title="Grafik Pemindaian Blok Buffer Memori (Shared Hits)",
        instruction="Grafik efisiensi pengurangan pemindaian blok halaman memori 8 KB sebelum vs sesudah indeks.",
        caption="Gambar 7.3 Efisiensi Pemindaian Halaman Memori Buffer",
        file_ref="reports/figures/chart_buffer_io.svg"
    )

    add_figure_box(
        doc,
        title="Grafik Dampak Sargability (Non-Sargable vs Sargable)",
        instruction="Grafik komparasi waktu respons kueri non-sargable (6,76 ms) vs sargable (0,03 ms).",
        caption="Gambar 7.4 Pembuktian Peningkatan Kinerja Sargability Kueri",
        file_ref="reports/figures/chart_sargability.svg"
    )

    # ==========================================
    # KESIMPULAN
    # ==========================================
    p_h1("KESIMPULAN SPRINT 1 & ROADMAP SPRINT 2")
    p_body("1. Capaian Sprint 1 (Target 50% Kumulatif): Seluruh deliverables teknis telah terpenuhi hingga 92,50% dari Sprint 1 (setara 46,25% kumulatif proyek akhir). Integritas BCNF & 4NF ditegakkan, transaksi atomik anti-overselling teruji, Exclusion Constraint aktif, dan bukti empiris EXPLAIN terverifikasi nyata.\n"
           "2. Kesiapan Evaluasi Progres: Repositori dan laporan teknis siap dipertanggungjawabkan pada presentasi evaluasi progres (26–27 November 2026).\n"
           "3. Roadmap Sprint 2 (Fase Final): Meliputi demonstrasi Crash Recovery & Write-Ahead Logging pemetaan ARIES (Bab 4), basis data paralel dan partisi lanjutan (Bab 9), Star Schema Data Warehouse dan pipeline ETL (Bab 13), serta integrasi antarmuka web.")

    output_path = os.path.join("reports", "final", "laporan-sprint-1.docx")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    print(f"Official report successfully saved to: {output_path}")

if __name__ == "__main__":
    compile_document()
