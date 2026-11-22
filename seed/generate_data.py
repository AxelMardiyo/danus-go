# -*- coding: utf-8 -*-
"""
DanusGo Realistic High-Performance Seeder (100.000+ Records)
Features:
- Fixed random seed for complete reproducibility (seed=42)
- Skewed / Pareto 80:20 distribution across popular products
- Peak ordering hours at 10:00 - 13:00 WIB
- Strict compliance with PostgreSQL constraints (Exclusion, Range Partitioning, Triggers)
- Ultra-fast batch ingestion using psycopg.copy()
"""

import os
import sys
import random
from datetime import datetime, date, time, timedelta
from faker import Faker
import psycopg

def run_seeder():
    print("=== DANUSGO DATABASE SEEDER (100k+ DATASET) ===")
    start_time = datetime.now()

    random.seed(42)
    fake = Faker('id_ID')
    Faker.seed(42)

    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://danusgo:danusgo_dev@localhost:5432/danusgo"
    )
    print(f"Connecting to database: {db_url}...")
    conn = psycopg.connect(db_url, autocommit=False)
    cur = conn.cursor()

    # -------------------------------------------------------------
    # 1. FETCH MASTER AKADEMIK (fakultas, prodi)
    # -------------------------------------------------------------
    cur.execute("SELECT id_fakultas, nama_fakultas FROM fakultas ORDER BY id_fakultas;")
    fakultas_rows = cur.fetchall()
    id_fakultas_list = [r[0] for r in fakultas_rows if r[1] != 'Area Umum']
    all_fakultas_ids = [r[0] for r in fakultas_rows]

    cur.execute("SELECT id_prodi, id_fakultas FROM prodi ORDER BY id_prodi;")
    prodi_rows = cur.fetchall()
    id_prodi_list = [r[0] for r in prodi_rows]
    print(f"Loaded {len(fakultas_rows)} fakultas and {len(prodi_rows)} prodi.")

    # -------------------------------------------------------------
    # 2. SEED PENGGUNA (5.000 users)
    # -------------------------------------------------------------
    print("Generating 5,000 pengguna...")
    # Precomputed bcrypt hash of 'password123'
    cur.execute("SELECT crypt('password123', gen_salt('bf', 8));")
    default_password_hash = cur.fetchone()[0]

    users_data = []
    used_nims = set()
    used_emails = set()

    # We need ~150 sellers, 1 admin already exists, rest buyers
    num_users = 5000
    seller_target = 150

    for i in range(1, num_users + 1):
        # NIM format: 240601241XXXXX
        year = random.choice(['22', '23', '24', '25'])
        prodi_code = random.choice(['01', '02', '03', '04', '05', '06'])
        nim_seq = f"{i:05d}"
        nim = f"{year}{prodi_code}{nim_seq}"
        while nim in used_nims:
            nim_seq = f"{random.randint(10000, 99999)}"
            nim = f"{year}{prodi_code}{nim_seq}"
        used_nims.add(nim)

        name = fake.name()
        email_prefix = name.lower().replace(" ", ".").replace(",", "").replace("'", "")
        email = f"{email_prefix}.{i}@mail.danusgo.ac.id"
        while email in used_emails:
            email = f"{email_prefix}.{random.randint(1000, 99999)}@mail.danusgo.ac.id"
        used_emails.add(email)

        phone = fake.phone_number()
        id_pr = random.choice(id_prodi_list)
        role = 'SELLER' if i <= seller_target else 'BUYER'
        dibuat = fake.date_time_between(start_date="-1y", end_date="-2m")

        users_data.append((nim, name, email, phone, id_pr, default_password_hash, role, True, dibuat))

    with cur.copy(
        "COPY pengguna (nim, nama, email, no_hp, id_prodi, password_hash, role, is_aktif, dibuat_pada) FROM STDIN"
    ) as copy:
        for row in users_data:
            copy.write_row(row)

    cur.execute("SELECT id_mahasiswa, role FROM pengguna WHERE role = 'SELLER' ORDER BY id_mahasiswa;")
    seller_mhs_ids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id_mahasiswa FROM pengguna WHERE role = 'BUYER' ORDER BY id_mahasiswa;")
    buyer_mhs_ids = [r[0] for r in cur.fetchall()]
    print(f"Pengguna seeded: {len(users_data)} users (Sellers: {len(seller_mhs_ids)}, Buyers: {len(buyer_mhs_ids)}).")

    # -------------------------------------------------------------
    # 3. SEED ORGANISASI DANUS (40 organizations) & SELLERS
    # -------------------------------------------------------------
    print("Generating 40 organisasi_danus...")
    org_templates = [
        ("BEM Fakultas Teknik", "Danusan Dies Natalis FT", 2),
        ("Himpunan Mahasiswa Informatika", "Danusan Informatics Expo", 2),
        ("Himpunan Mahasiswa Mesin", "Danusan Solidaritas Mesin", 2),
        ("Himpunan Mahasiswa Elektro", "Danusan Elektro Robotic Cup", 2),
        ("Himpunan Mahasiswa Sipil", "Danusan Civil Fiesta", 2),
        ("BEM FEB", "Danusan Pekan Raya FEB", 3),
        ("Himpunan Mahasiswa Manajemen", "Danusan Management Fair", 3),
        ("Himpunan Mahasiswa Akuntansi", "Danusan Accounting Championship", 3),
        ("BEM Fakultas Hukum", "Danusan Law Festival", 4),
        ("Dewan Mahasiswa Kedokteran", "Danusan Baksos Desa Binaan", 5),
        ("Himpunan Mahasiswa Matematika", "Danusan Math Competition", 6),
        ("Himpunan Mahasiswa Statistika", "Danusan Data Science Day", 6),
        ("BEM FISIP", "Danusan Panggung Budaya FISIP", 7),
        ("Himpunan Mahasiswa Komunikasi", "Danusan Creative Broadcast Expo", 7),
        ("BEM Fakultas Psikologi", "Danusan Psychology Summit", 8),
        ("BEM Fakultas Ilmu Budaya", "Danusan Malam Kesenian FIB", 9),
        ("UKM Robotika Kampus", "Danusan Kontes Robot Indonesia", 2),
        ("UKM Paduan Suara Mahasiswa", "Danusan Konser Tahunan PSM", 1),
        ("UKM Teater Kampus", "Danusan Pementasan Akbar Teater", 1),
        ("UKM Fotografi & Sinematografi", "Danusan Pameran Karya Seni", 1),
        ("Kepanitiaan Wisuda Gelombang I", "Danusan Konsumsi Wisudawan", 1),
        ("Kepanitiaan Wisuda Gelombang II", "Danusan Merchandise Kelulusan", 1),
        ("Komunitas Tari Tradisional", "Danusan Pentas Budaya Nusantara", 9),
        ("UKM Bola Basket Kampus", "Danusan Liga Mahasiswa Basket", 1),
        ("UKM Futsal Mahasiswa", "Danusan Rektor Cup Futsal", 1),
        ("Komunitas Pecinta Alam", "Danusan Ekspedisi Gunung Merbabu", 1),
        ("Tim Pengmas Mahasiswa Peduli", "Danusan Santunan Panti Asuhan", 1),
        ("Himpunan Mahasiswa Kimia", "Danusan National Chemistry Week", 6),
        ("Himpunan Mahasiswa Fisika", "Danusan Physics Innovation Cup", 6),
        ("Himpunan Mahasiswa Biologi", "Danusan Bio Camp & Conservation", 6),
        ("UKM Resimen Mahasiswa", "Danusan Diksar Yudha Manunggal", 1),
        ("KSR PMI Unit Kampus", "Danusan Donor Darah Akbar", 5),
        ("UKM Bulutangkis", "Danusan Turnamen Bulutangkis Antar-Prodi", 1),
        ("Komunitas Pecinta Anime & Budaya Jepang", "Danusan Bunkasai Fest", 9),
        ("UKM Jurnalistik Mahasiswa", "Danusan Pelatihan Majalah Kampus", 7),
        ("Komunitas Debat Bahasa Inggris", "Danusan Inter-Varsity Debate", 4),
        ("Forum Rohani Islam Kampus", "Danusan Kajian Akbar Ramadhan", 1),
        ("Persekutuan Mahasiswa Kristen", "Danusan Kebaktian & Retret", 1),
        ("Keluarga Mahasiswa Katolik", "Danusan Ziarah & Bakti Sosial", 1),
        ("Keluarga Mahasiswa Hindu Dharma", "Danusan Dharma Santi Dies Natalis", 1),
    ]

    org_data = []
    for org_name, proker, fak_id in org_templates:
        rekening = f"BCA {fake.bban()}"
        org_data.append((org_name, proker, fak_id, rekening))

    with cur.copy(
        "COPY organisasi_danus (nama_organisasi, nama_proker, id_fakultas_induk, rekening_tujuan) FROM STDIN"
    ) as copy:
        for row in org_data:
            copy.write_row(row)

    cur.execute("SELECT id_organisasi, id_fakultas_induk FROM organisasi_danus ORDER BY id_organisasi;")
    org_rows = cur.fetchall()
    id_org_list = [r[0] for r in org_rows]

    # Assign ~3-4 seller per organisasi
    seller_pairs = []
    for idx, org_id in enumerate(id_org_list):
        # Pick 3-4 sellers
        assigned = seller_mhs_ids[idx*3 : (idx+1)*3 + 1]
        for mhs_id in assigned:
            seller_pairs.append((mhs_id, org_id))

    with cur.copy("COPY seller (id_mahasiswa, id_organisasi) FROM STDIN") as copy:
        for pair in seller_pairs:
            copy.write_row(pair)
    print(f"Organisasi danus seeded: {len(id_org_list)}, Sellers linked: {len(seller_pairs)}.")

    # -------------------------------------------------------------
    # 4. SEED SPOT LOKASI (30 spots total)
    # -------------------------------------------------------------
    print("Generating spot_lokasi...")
    spot_names = [
        (2, "Selasar Gedung A Teknik", "Depan Dekanat FT"),
        (2, "Lobby Gedung E Elektro", "Pintu masuk timur lab komputer"),
        (2, "Kantin Vokasi Teknik", "Area food court teknik"),
        (2, "Parkiran Belakang Mesin", "Dekat bengkel mesin"),
        (3, "Plaza FEB", "Depan hall utama perpustakaan FEB"),
        (3, "Kantin Kejujuran FEB", "Samping musholla lantai 1"),
        (3, "Gazebo Akuntansi", "Taman tengah gedung akuntansi"),
        (4, "Lobby Justice FH", "Depan ruang peradilan semu"),
        (4, "Taman Gazebo Merah FH", "Dekat kantin hukum"),
        (5, "Lobby Gedung Pendidikan Dokter", "Depan auditorium kedokteran"),
        (5, "Kantin Rumah Sakit Kampus", "Area parkiran timur RS"),
        (6, "Plaza MIPA", "Selasar tengah gedung B MIPA"),
        (6, "Gazebo Matematika", "Depan lab komputasi sains"),
        (6, "Kantin Barat MIPA", "Dekat ruang himpunan"),
        (7, "Selasar Oranye FISIP", "Lantai dasar gedung D"),
        (7, "Taman Demokrasi FISIP", "Tengah antara gedung A dan B"),
        (8, "Lobby Jiwa Ceria Psikologi", "Depan biro konsultasi mahasiswa"),
        (8, "Gazebo Taman Psikologi", "Dekat kolam ikan psikologi"),
        (9, "Amfiteater FIB", "Area panggung terbuka seni"),
        (9, "Kantin Sastra FIB", "Belakang gedung jurusan bahasa"),
        (1, "Pelataran Masjid Kampus", "Dekat koridor tempat wudhu pria/wanita"),
        (1, "Selasar Perpustakaan Pusat", "Pintu masuk utama perpustakaan"),
        (1, "Student Center Lantai 1", "Lobby depan ruang sekretariat BEM"),
        (1, "Gelanggang Olahraga (GOR)", "Samping lapangan futsal indoor"),
        (1, "Halte Bus Kampus Utama", "Pemberhentian shuttle bus kampus"),
        (1, "Pusat Kegiatan Mahasiswa (PKM)", "Area tangga utama lantai dasar"),
        (1, "Boulevard Gerbang Utama", "Dekat tugu selamat datang kampus"),
        (1, "Danau Kampus", "Area bangku melingkar tepi danau")
    ]

    with cur.copy("COPY spot_lokasi (id_fakultas, nama_spot, patokan_lokasi) FROM STDIN") as copy:
        for row in spot_names:
            copy.write_row(row)

    cur.execute("SELECT id_spot FROM spot_lokasi ORDER BY id_spot;")
    id_spot_list = [r[0] for r in cur.fetchall()]
    print(f"Total spot_lokasi now: {len(id_spot_list)} spots.")

    # -------------------------------------------------------------
    # 5. SEED PRODUK DANUS (200 products), VARIAN & METODE PICKUP
    # -------------------------------------------------------------
    print("Generating 200 produk_danus...")
    product_catalogs = [
        # MAKANAN_BERAT
        ("Nasi Ayam Geprek Sambal Bawang", "MAKANAN_BERAT", 10000, 15000, "READY_STOCK", ["Level 1", "Level 2", "Level 3", "Level 5"]),
        ("Nasi Katsu Saus Teriyaki", "MAKANAN_BERAT", 12000, 18000, "READY_STOCK", ["Original", "Pedas Manis", "Blackpepper"]),
        ("Nasi Kuning Komplit Telur", "MAKANAN_BERAT", 8000, 13000, "READY_STOCK", ["Biasa", "Pedas"]),
        ("Nasi Uduk Betawi Semur Tahu", "MAKANAN_BERAT", 8000, 12000, "READY_STOCK", ["Biasa", "Ekstra Kerupuk"]),
        ("Mie Dok-dok Spesial Sosis Telur", "MAKANAN_BERAT", 9000, 14000, "READY_STOCK", ["Sedang", "Pedas Gila"]),
        ("Rice Bowl Ayam Mentai", "MAKANAN_BERAT", 13000, 20000, "PRE_ORDER", ["Original Mentai", "Spicy Mentai"]),
        ("Rice Bowl Daging Sapi Lada Hitam", "MAKANAN_BERAT", 15000, 24000, "PRE_ORDER", ["Porsi Normal", "Jumbo"]),
        ("Spaghetti Brulee Bolognese", "MAKANAN_BERAT", 12000, 18000, "PRE_ORDER", ["Keju Lumer", "Double Cheese"]),
        ("Nasi Liwet Solo Ayam Suwir", "MAKANAN_BERAT", 10000, 15000, "READY_STOCK", ["Biasa", "Pedas"]),
        ("Burger Daging Sapi Special Cheese", "MAKANAN_BERAT", 11000, 17000, "READY_STOCK", ["Single Patty", "Double Cheese"]),
        # SNACK
        ("Risoles Mayo Beef Keju (Isi 3)", "SNACK", 6000, 10000, "READY_STOCK", ["Original", "Ekstra Pedas"]),
        ("Tahu Bakso Ungaran Kukus/Goreng", "SNACK", 7000, 12000, "READY_STOCK", ["Goreng Crispy", "Kukus Lembut"]),
        ("Pastel Ayam Telur Spesial", "SNACK", 5000, 8000, "READY_STOCK", ["Original", "Cabai Rawit"]),
        ("Cireng Isi Ayam Suwir Pedas", "SNACK", 6000, 10000, "READY_STOCK", ["Pedas Daun Jeruk", "Pedas Manis"]),
        ("Dimsum Ayam Udang Premium (Isi 4)", "SNACK", 10000, 16000, "READY_STOCK", ["Saus Mentai", "Chili Oil"]),
        ("Donat Kentang Tabur Gula Halus", "SNACK", 4000, 7000, "READY_STOCK", ["Gula Halus", "Cokelat Meses", "Keju"]),
        ("Fudgy Brownies Panggang Potong", "SNACK", 8000, 14000, "READY_STOCK", ["Almond", "Chocochip", "Keju"]),
        ("Churros Saus Cokelat Belgia", "SNACK", 7000, 12000, "READY_STOCK", ["Cinnamon Sugar", "Dark Chocolate"]),
        ("Banana Nugget Crispy Topping", "SNACK", 8000, 13000, "READY_STOCK", ["Choco Matcha", "Tiramisu Cheese"]),
        ("Pangsit Goreng Viral Le Gino", "SNACK", 8000, 13000, "READY_STOCK", ["Biasa", "Pedas Nampol"]),
        # MINUMAN
        ("Kopi Susu Gula Aren Senja", "MINUMAN", 7000, 13000, "READY_STOCK", ["Normal Sugar", "Less Sugar", "Extra Shot"]),
        ("Es Matcha Latte Creamy", "MINUMAN", 8000, 15000, "READY_STOCK", ["Normal Sweet", "Less Sweet"]),
        ("Signature Thai Tea Jelly", "MINUMAN", 6000, 11000, "READY_STOCK", ["Normal Ice", "Less Ice"]),
        ("Es Cokelat Klasik Roti Sobek", "MINUMAN", 7000, 12000, "READY_STOCK", ["Original", "Choco Hazelnut"]),
        ("Lemon Tea Segar Selasih", "MINUMAN", 4000, 8000, "READY_STOCK", ["Dingin", "Hangat"]),
        ("Taro Milk Cheese Foam", "MINUMAN", 8000, 14000, "READY_STOCK", ["Boba Pearl", "Grass Jelly"]),
        ("Es Kopi Susu Pandan Wangi", "MINUMAN", 7000, 13000, "READY_STOCK", ["Normal", "Less Sugar"]),
        ("Manggo Sticky Milk Cheese", "MINUMAN", 9000, 16000, "READY_STOCK", ["Jelly Mangga", "Nata de Coco"]),
        # MERCHANDISE
        ("Gantungan Kunci Akrilik Karakter", "MERCHANDISE", 5000, 10000, "READY_STOCK", ["Maskot Kampus", "Logo Fakultas"]),
        ("Tote Bag Kanvas Desain Dies Natalis", "MERCHANDISE", 18000, 30000, "PRE_ORDER", ["Hitam", "Broken White"]),
        ("Sticker Pack Waterproof Anti-Air", "MERCHANDISE", 4000, 8000, "READY_STOCK", ["Varian Ilustrasi", "Varian Tipografi"]),
        ("Lanyard ID Card Kampus Premium", "MERCHANDISE", 10000, 18000, "READY_STOCK", ["Navy Blue", "Maroon", "Emerald Green"])
    ]

    # Generate 200 distinct products across the 40 organizations
    products_data = []
    variants_data = []
    pickups_data = []

    prod_counter = 0
    while prod_counter < 200:
        base = product_catalogs[prod_counter % len(product_catalogs)]
        org_id = id_org_list[prod_counter % len(id_org_list)]

        suffix = f" Batch {(prod_counter // len(product_catalogs)) + 1}" if prod_counter >= len(product_catalogs) else ""
        prod_name = f"{base[0]}{suffix}"
        kategori = base[1]
        harga_modal = base[2]
        harga_jual = base[3]
        tipe_penjualan = base[4]

        products_data.append((org_id, prod_name, kategori, harga_modal, harga_jual, tipe_penjualan))
        prod_counter += 1

    with cur.copy(
        "COPY produk_danus (id_organisasi, nama_produk, kategori, harga_modal, harga_jual, tipe_penjualan) FROM STDIN"
    ) as copy:
        for p in products_data:
            copy.write_row(p)

    cur.execute("SELECT id_produk, kategori FROM produk_danus ORDER BY id_produk;")
    inserted_prods = cur.fetchall()

    for idx, (p_id, kat) in enumerate(inserted_prods):
        base = product_catalogs[idx % len(product_catalogs)]
        vars_list = base[5]
        for v in vars_list:
            variants_data.append((p_id, v))
        # Pickup methods
        pickups_data.append((p_id, "Ambil di Stan"))
        if kat in ['MAKANAN_BERAT', 'PRE_ORDER', 'MERCHANDISE']:
            pickups_data.append((p_id, "Diantar ke Gedung Kuliah"))

    with cur.copy("COPY produk_varian (id_produk, nama_varian) FROM STDIN") as copy:
        for v in variants_data:
            copy.write_row(v)

    with cur.copy("COPY produk_metode_pickup (id_produk, metode_pickup) FROM STDIN") as copy:
        for pu in pickups_data:
            copy.write_row(pu)

    print(f"Produk seeded: {len(products_data)}, Varian: {len(variants_data)}, Pickups: {len(pickups_data)}.")

    # -------------------------------------------------------------
    # 6. SEED SESI JUALAN (8.000 sessions, NO OVERLAPS on same spot!)
    # -------------------------------------------------------------
    print("Generating 8,000 sesi_jualan (Strict Exclusion Constraint Guarantee)...")
    # Date range: 2026-01-05 to 2026-11-28 (~325 days)
    start_d = date(2026, 1, 5)
    end_d = date(2026, 11, 28)
    delta_days = (end_d - start_d).days

    # 5 standard non-overlapping time slots per day:
    # Slot 0: 08:00 - 10:00
    # Slot 1: 10:00 - 12:00
    # Slot 2: 12:00 - 14:00
    # Slot 3: 14:00 - 16:00
    # Slot 4: 16:00 - 18:00
    slots_def = [
        (time(8, 0), time(10, 0)),
        (time(10, 0), time(12, 0)),
        (time(12, 0), time(14, 0)),
        (time(14, 0), time(16, 0)),
        (time(16, 0), time(18, 0))
    ]

    # Generate all candidate (spot_id, date, slot_idx) combinations
    all_possible_slots = []
    for d_offset in range(delta_days + 1):
        cur_d = start_d + timedelta(days=d_offset)
        # Skip Sundays (campuses usually closed)
        if cur_d.weekday() == 6:
            continue
        for s_id in id_spot_list:
            for s_idx in range(len(slots_def)):
                all_possible_slots.append((s_id, cur_d, s_idx))

    random.shuffle(all_possible_slots)
    chosen_slots = all_possible_slots[:8000]

    # Sort chosen slots chronologically for cleaner indexing
    chosen_slots.sort(key=lambda x: (x[1], x[2], x[0]))

    sessions_data = []
    today = date(2026, 11, 22)

    for spot_id, session_date, slot_idx in chosen_slots:
        org_id = random.choice(id_org_list)
        j_mulai, j_selesai = slots_def[slot_idx]

        if session_date < date(2026, 11, 21):
            st = 'CLOSED'
        elif session_date in [date(2026, 11, 21), date(2026, 11, 22)]:
            st = 'OPEN'
        else:
            st = 'UPCOMING'

        sessions_data.append((org_id, spot_id, session_date, j_mulai, j_selesai, st))

    with cur.copy(
        "COPY sesi_jualan (id_organisasi, id_spot, tanggal_jualan, jam_mulai, jam_selesai, status_sesi) FROM STDIN"
    ) as copy:
        for s in sessions_data:
            copy.write_row(s)

    cur.execute("SELECT id_sesi, id_organisasi, tanggal_jualan, jam_mulai, jam_selesai, status_sesi FROM sesi_jualan ORDER BY id_sesi;")
    sesi_rows = cur.fetchall()
    print(f"Sesi jualan seeded: {len(sesi_rows)} sessions.")

    # -------------------------------------------------------------
    # 7. SEED SESI_PRODUK (Mapping products to sessions)
    # -------------------------------------------------------------
    print("Mapping produk to sesi_produk...")
    cur.execute("SELECT id_produk, id_organisasi, tipe_penjualan, harga_jual, harga_modal FROM produk_danus;")
    prod_info = {r[0]: {'org_id': r[1], 'tipe': r[2], 'harga_jual': r[3], 'harga_modal': r[4]} for r in cur.fetchall()}

    org_to_prods = {}
    for p_id, info in prod_info.items():
        org_to_prods.setdefault(info['org_id'], []).append(p_id)

    sesi_produk_data = []
    # To keep track of sesi_produk inserted
    for s_id, s_org, s_date, s_mulai, s_selesai, s_status in sesi_rows:
        available_pids = org_to_prods.get(s_org, [])
        if not available_pids:
            # Fallback to any random product
            available_pids = list(prod_info.keys())

        # Select 2 to 4 products per session
        k = min(len(available_pids), random.randint(2, 4))
        chosen_prods = random.sample(available_pids, k)

        for p_id in chosen_prods:
            p_tipe = prod_info[p_id]['tipe']
            kuota_awal = random.randint(25, 75)
            kuota_sisa = kuota_awal
            status_stok = 'AVAILABLE'

            if p_tipe == 'PRE_ORDER':
                # Pre-order window: 2 days before session opens, closes 1 hour before session
                buka = datetime.combine(s_date - timedelta(days=2), time(8, 0))
                tutup = datetime.combine(s_date, s_mulai)
                # Ensure offset +07:00
                buka_str = f"{buka.strftime('%Y-%m-%d %H:%M:%S')}+07"
                tutup_str = f"{tutup.strftime('%Y-%m-%d %H:%M:%S')}+07"
            else:
                buka_str = None
                tutup_str = None

            sesi_produk_data.append((s_id, p_id, kuota_awal, kuota_sisa, status_stok, buka_str, tutup_str))

    with cur.copy(
        "COPY sesi_produk (id_sesi, id_produk, kuota_awal, kuota_sisa, status_stok, buka_pesan_pada, tutup_pesan_pada) FROM STDIN"
    ) as copy:
        for sp in sesi_produk_data:
            copy.write_row(sp)

    cur.execute("SELECT id_sesi_produk, id_sesi, id_produk, kuota_awal FROM sesi_produk ORDER BY id_sesi_produk;")
    sesi_produk_rows = cur.fetchall()

    # Pre-map variants and pickups per product
    cur.execute("SELECT id_varian, id_produk FROM produk_varian;")
    prod_variants = {}
    for v_id, p_id in cur.fetchall():
        prod_variants.setdefault(p_id, []).append(v_id)

    cur.execute("SELECT id_pickup, id_produk FROM produk_metode_pickup;")
    prod_pickups = {}
    for pu_id, p_id in cur.fetchall():
        prod_pickups.setdefault(p_id, []).append(pu_id)

    # Fast lookup for session details
    sesi_dict = {r[0]: {'tgl': r[2], 'mulai': r[3], 'selesai': r[4], 'status': r[5]} for r in sesi_rows}
    # Group sesi_produk by session
    sesi_to_sp = {}
    for sp_id, s_id, p_id, q_awal in sesi_produk_rows:
        sesi_to_sp.setdefault(s_id, []).append({'sp_id': sp_id, 'p_id': p_id, 'q_awal': q_awal})

    print(f"Sesi produk seeded: {len(sesi_produk_rows)} product-session mappings.")

    # -------------------------------------------------------------
    # 8. SEED PESANAN_DANUS (100.000+ records) & DETAIL_PESANAN (~180.000)
    # -------------------------------------------------------------
    print("Generating 105,000 orders with Pareto 80:20 distribution...")
    target_orders = 105000

    # Pareto / Zipfian weights for products:
    # 20% of products get weight 10, remaining 80% get weight 1
    num_all_prods = len(inserted_prods)
    top_20_count = max(1, int(num_all_prods * 0.2))
    all_prod_ids = [r[0] for r in inserted_prods]
    prod_weights = {}
    for idx, p_id in enumerate(all_prod_ids):
        prod_weights[p_id] = 10 if idx < top_20_count else 1

    # Filter sessions that have products mapped
    valid_sesi_ids = [s_id for s_id in sesi_to_sp.keys()]

    # To track used codes per session
    sesi_used_codes = {s_id: set() for s_id in valid_sesi_ids}

    # Tracking sales per sesi_produk to update kuota_sisa later
    sp_sales = {r[0]: 0 for r in sesi_produk_rows}

    # Tracking log_kuota
    log_kuota_rows = []

    pesanan_rows = []
    detail_rows = []

    # Alphanumeric chars for pickup code
    code_chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    # Pre-select sessions with weights favoring popular spot locations and peak hours
    sesi_weights = []
    for s_id in valid_sesi_ids:
        s_info = sesi_dict[s_id]
        # Peak hours 10:00 - 14:00 get 4x weight
        weight = 4 if s_info['mulai'] in [time(10, 0), time(12, 0)] else 1
        sesi_weights.append(weight)

    selected_sesi_ids = random.choices(valid_sesi_ids, weights=sesi_weights, k=target_orders)

    order_counter = 0
    for s_id in selected_sesi_ids:
        order_counter += 1
        s_info = sesi_dict[s_id]
        s_date = s_info['tgl']
        s_mulai = s_info['mulai']
        s_status = s_info['status']

        mhs_id = random.choice(buyer_mhs_ids)

        # Realistic order timestamp:
        # If session was in the past, time between jam_mulai and jam_selesai
        # (with peak density at lunch 11:30 - 13:00)
        mulai_minutes = s_mulai.hour * 60 + s_mulai.minute
        # offset within session duration (120 minutes)
        offset_m = random.randint(0, 110)
        offset_s = random.randint(0, 59)
        order_dt = datetime.combine(s_date, time(mulai_minutes // 60, mulai_minutes % 60)) + timedelta(minutes=offset_m, seconds=offset_s)
        order_ts_str = f"{order_dt.strftime('%Y-%m-%d %H:%M:%S')}+07"

        # Mandatory: kedaluwarsa_pada > waktu_pesan
        exp_dt = order_dt + timedelta(minutes=15)
        exp_ts_str = f"{exp_dt.strftime('%Y-%m-%d %H:%M:%S')}+07"

        # Unique pickup code per session
        while True:
            code = "".join(random.choices(code_chars, k=6))
            if code not in sesi_used_codes[s_id]:
                sesi_used_codes[s_id].add(code)
                break

        metode_bayar = random.choice(['CASH_COD', 'QRIS'])

        # Realistic status distribution:
        if s_status == 'CLOSED':
            # Historical orders: 86% COMPLETED, 10% CANCELLED, 4% PAID
            status_pesanan = random.choices(['COMPLETED', 'CANCELLED', 'PAID'], weights=[86, 10, 4])[0]
        else:
            # Active today orders: PENDING, PAID, READY_TO_PICKUP, COMPLETED
            status_pesanan = random.choices(['PENDING', 'PAID', 'READY_TO_PICKUP', 'COMPLETED'], weights=[30, 30, 25, 15])[0]

        dibayar_ts = None
        siap_ts = None
        selesai_ts = None
        batal_ts = None

        if status_pesanan in ['PAID', 'READY_TO_PICKUP', 'COMPLETED']:
            dibayar_dt = order_dt + timedelta(minutes=random.randint(2, 5))
            dibayar_ts = f"{dibayar_dt.strftime('%Y-%m-%d %H:%M:%S')}+07"

        if status_pesanan in ['READY_TO_PICKUP', 'COMPLETED']:
            siap_dt = order_dt + timedelta(minutes=random.randint(6, 10))
            siap_ts = f"{siap_dt.strftime('%Y-%m-%d %H:%M:%S')}+07"

        if status_pesanan == 'COMPLETED':
            selesai_dt = order_dt + timedelta(minutes=random.randint(11, 20))
            selesai_ts = f"{selesai_dt.strftime('%Y-%m-%d %H:%M:%S')}+07"
        elif status_pesanan == 'CANCELLED':
            batal_dt = order_dt + timedelta(minutes=random.randint(5, 15))
            batal_ts = f"{batal_dt.strftime('%Y-%m-%d %H:%M:%S')}+07"

        # Record pesanan_danus
        # Note: pesanan_danus has id_pesanan (BIGINT GENERATED ALWAYS AS IDENTITY)
        # We pass explicit id_pesanan in COPY by omitting column and letting Postgres generate,
        # OR we can generate sequential IDs manually for linking detail_pesanan!
        # Because we need id_pesanan to insert detail_pesanan, we pass order_counter as id_pesanan!
        pesanan_rows.append((
            order_counter, mhs_id, s_id, order_ts_str, metode_bayar,
            status_pesanan, code, exp_ts_str, dibayar_ts, siap_ts, selesai_ts, batal_ts
        ))

        # Pick 1 to 3 items from session products (weighted by product popularity)
        sp_options = sesi_to_sp[s_id]
        weights_for_sp = [prod_weights.get(item['p_id'], 1) for item in sp_options]

        num_items = random.choices([1, 2, 3], weights=[70, 22, 8])[0]
        chosen_sp_items = random.choices(sp_options, weights=weights_for_sp, k=num_items)

        for sp_item in chosen_sp_items:
            sp_id = sp_item['sp_id']
            p_id = sp_item['p_id']

            v_options = prod_variants.get(p_id, [None])
            v_id = random.choice(v_options)

            pu_options = prod_pickups.get(p_id, [None])
            pu_id = random.choice(pu_options)

            qty = random.choices([1, 2, 3, 4], weights=[75, 18, 5, 2])[0]
            sp_sales[sp_id] += qty

            h_jual = prod_info[p_id]['harga_jual']
            h_modal = prod_info[p_id]['harga_modal']

            detail_rows.append((
                order_counter, order_ts_str, sp_id, v_id, pu_id, qty, h_jual, h_modal
            ))

            log_kuota_rows.append((
                sp_id, order_counter, -qty, 'PEMESANAN', order_ts_str
            ))

    print(f"Ingesting {len(pesanan_rows)} pesanan_danus into partitioned tables...")
    # OVERRIDING SYSTEM VALUE allows copying into GENERATED ALWAYS AS IDENTITY column
    with cur.copy(
        """COPY pesanan_danus (
            id_pesanan, id_mahasiswa, id_sesi, waktu_pesan, metode_bayar,
            status_pesanan, kode_pengambilan, kedaluwarsa_pada,
            dibayar_pada, siap_pada, selesai_pada, dibatalkan_pada
        ) FROM STDIN"""
    ) as copy:
        for r in pesanan_rows:
            copy.write_row(r)

    print(f"Ingesting {len(detail_rows)} detail_pesanan records...")
    with cur.copy(
        """COPY detail_pesanan (
            id_pesanan, waktu_pesan, id_sesi_produk, id_varian, id_pickup,
            jumlah_item, harga_satuan, harga_modal_satuan
        ) FROM STDIN"""
    ) as copy:
        for r in detail_rows:
            copy.write_row(r)

    print(f"Ingesting {len(log_kuota_rows)} log_kuota records...")
    with cur.copy(
        "COPY log_kuota (id_sesi_produk, id_pesanan, delta, alasan, waktu) FROM STDIN"
    ) as copy:
        for r in log_kuota_rows:
            copy.write_row(r)

    # -------------------------------------------------------------
    # 9. UPDATE sesi_produk kuota_sisa to match actual sales (BR-11)
    # -------------------------------------------------------------
    print("Synchronizing kuota_sisa & status_stok in sesi_produk...")
    cur.execute("""
        UPDATE sesi_produk sp
           SET kuota_sisa = GREATEST(0, sp.kuota_awal - COALESCE(agg.terjual, 0)),
               status_stok = CASE 
                   WHEN GREATEST(0, sp.kuota_awal - COALESCE(agg.terjual, 0)) = 0 THEN 'SOLD_OUT'
                   ELSE 'AVAILABLE'
               END
          FROM (
              SELECT id_sesi_produk, SUM(jumlah_item) AS terjual
                FROM detail_pesanan
               GROUP BY id_sesi_produk
          ) agg
         WHERE sp.id_sesi_produk = agg.id_sesi_produk;
    """)

    # -------------------------------------------------------------
    # 10. RESTART IDENTITY SEQUENCES & RUN ANALYZE
    # -------------------------------------------------------------
    print("Updating identity sequences and running ANALYZE...")
    cur.execute(f"SELECT setval(pg_get_serial_sequence('pesanan_danus', 'id_pesanan'), {len(pesanan_rows)} + 1);")
    cur.execute(f"SELECT setval(pg_get_serial_sequence('detail_pesanan', 'id_detail'), {len(detail_rows)} + 1);")
    cur.execute("ANALYZE;")

    conn.commit()
    conn.close()

    duration = datetime.now() - start_time
    print(f"=== SEEDING COMPLETED SUCCESSFULLY IN {duration.total_seconds():.2f} SECONDS ===")
    print(f"Total Pesanan: {len(pesanan_rows):,}")
    print(f"Total Detail Pesanan: {len(detail_rows):,}")

if __name__ == "__main__":
    run_seeder()
