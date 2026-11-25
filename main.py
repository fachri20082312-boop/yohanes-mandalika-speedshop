"""
=====================================================================
 YOHANES MANDALIKA SPEEDSHOP
 Aplikasi Pencatatan Servis Motor Berkala
 Final Project Dasar Pemrograman - Python + SQLite
=====================================================================
Fitur:
  - Registrasi & Login (user dan admin)
  - Kelola kendaraan (multi kendaraan dalam satu akun)  [BONUS]
  - Update kilometer
  - Riwayat servis + hitung target servis berikutnya otomatis
  - Dashboard notifikasi servis (Aman / Peringatan / Terlambat)
  - Laporan kendaraan + ringkasan biaya
  - Grafik ASCII progres kilometer                       [BONUS]
  - Ranking komponen yang paling sering diganti          [BONUS]
  - Export laporan ke CSV                                [BONUS]

Akun admin bawaan (dibuat otomatis saat pertama dijalankan):
  username : admin
  password : admin123
"""

import csv
import hashlib
import os
import sqlite3
from collections import Counter
from datetime import datetime

# ---------------------------------------------------------------------
# KONFIGURASI
# ---------------------------------------------------------------------
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "care_motor.db")

# Aturan interval servis (dalam Km) - sesuai ketentuan nomor 11
INTERVAL_SERVIS = {
    "Ganti Oli": 2000,
    "Oli Gardan": 5000,
    "Tune Up": 8000,
    "Kampas Rem": 10000,
    "Ban": 20000,
}

BATAS_PERINGATAN = 500   # sisa Km < 500 -> "Mendekati Servis"
MIN_PASSWORD = 6
LEBAR_BAR = 20           # panjang progress bar ASCII


# ---------------------------------------------------------------------
# 1. DATABASE
# ---------------------------------------------------------------------
def koneksi():
    """Membuat koneksi ke database SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def buat_tabel():
    """Membuat tabel user, kendaraan, dan riwayat_servis bila belum ada,
    serta membuat akun admin bawaan."""
    conn = koneksi()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS user (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nama      TEXT NOT NULL,
            username  TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password  TEXT NOT NULL,
            role      TEXT NOT NULL DEFAULT 'user'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS kendaraan (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL,
            nomor_polisi        TEXT NOT NULL,
            merk                TEXT NOT NULL,
            tipe                TEXT NOT NULL,
            tahun               INTEGER NOT NULL,
            kilometer_saat_ini  INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS riwayat_servis (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            id_kendaraan          INTEGER NOT NULL,
            jenis_servis          TEXT NOT NULL,
            km_saat_servis        INTEGER NOT NULL,
            tanggal_servis        TEXT NOT NULL,
            biaya                 INTEGER NOT NULL,
            km_target_berikutnya  INTEGER NOT NULL,
            catatan               TEXT,
            FOREIGN KEY (id_kendaraan) REFERENCES kendaraan(id)
        )
    """)

    # Akun admin bawaan
    cur.execute("SELECT id FROM user WHERE username = 'admin'")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO user (nama, username, password, role) VALUES (?, ?, ?, 'admin')",
            ("Administrator", "admin", hash_password("admin123")),
        )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# 2. FUNGSI BANTU (helper)
# ---------------------------------------------------------------------
def hash_password(password):
    """Mengubah password menjadi hash SHA-256 agar tidak disimpan polos."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def format_angka(n):
    """15500 -> '15.500' (format ribuan Indonesia)."""
    return f"{n:,}".replace(",", ".")


def format_rupiah(n):
    """75000 -> 'Rp 75.000'."""
    return "Rp " + format_angka(int(n))


def input_angka(pesan, minimum=None):
    """Meminta input bilangan bulat. Mengulang (while) sampai valid.
    Menerima format '15.500' atau '15500'."""
    while True:
        teks = input(pesan).strip().lower().replace("rp", "").replace(".", "").replace(",", "")
        if teks.lstrip("-").isdigit():
            nilai = int(teks)
            if minimum is not None and nilai < minimum:
                print(f"ERROR: Nilai tidak boleh kurang dari {minimum}")
                continue
            return nilai
        print("ERROR: Input harus berupa angka")


def input_tanggal(pesan):
    """Meminta tanggal format DD-MM-YYYY. Kosong = hari ini."""
    while True:
        teks = input(pesan).strip()
        if teks == "":
            return datetime.now().strftime("%d-%m-%Y")
        try:
            datetime.strptime(teks, "%d-%m-%Y")
            return teks
        except ValueError:
            print("ERROR: Format tanggal harus DD-MM-YYYY (contoh: 10-06-2026)")


def input_tidak_kosong(pesan):
    """Meminta input teks yang tidak boleh kosong."""
    while True:
        teks = input(pesan).strip()
        if teks:
            return teks
        print("ERROR: Input tidak boleh kosong")


def garis(panjang=60, char="="):
    print(char * panjang)


# ---------------------------------------------------------------------
# 3. REGISTRASI & LOGIN
# ---------------------------------------------------------------------
def registrasi():
    """Registrasi akun baru dengan validasi password minimal 6 karakter."""
    print("\n===== REGISTRASI AKUN =====")
    nama = input_tidak_kosong("Nama Lengkap : ")

    while True:
        username = input_tidak_kosong("Username     : ")
        conn = koneksi()
        ada = conn.execute("SELECT id FROM user WHERE username = ?", (username,)).fetchone()
        conn.close()
        if ada:
            print("ERROR: Username sudah dipakai, silakan pilih yang lain")
        else:
            break

    while True:
        password = input("Password     : ").strip()
        if len(password) < MIN_PASSWORD:
            print("ERROR:")
            print("Password terlalu pendek")
        else:
            break

    conn = koneksi()
    conn.execute(
        "INSERT INTO user (nama, username, password, role) VALUES (?, ?, ?, 'user')",
        (nama, username, hash_password(password)),
    )
    conn.commit()
    conn.close()
    print("Registrasi berhasil! Silakan login.")


def login():
    """Login. Mengembalikan data user (sqlite3.Row) jika berhasil, None jika gagal."""
    print("\n===== LOGIN =====")
    username = input("Username : ").strip()
    password = input("Password : ").strip()

    conn = koneksi()
    user = conn.execute(
        "SELECT * FROM user WHERE username = ? AND password = ?",
        (username, hash_password(password)),
    ).fetchone()
    conn.close()

    if user:
        print("Login Berhasil")
        return user
    print("Username atau Password Salah")
    return None


# ---------------------------------------------------------------------
# 4. MODUL KENDARAAN
# ---------------------------------------------------------------------
def ambil_kendaraan_user(user_id):
    """Mengambil semua kendaraan milik satu user."""
    conn = koneksi()
    data = conn.execute(
        "SELECT * FROM kendaraan WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    conn.close()
    return data


def tambah_kendaraan(user_id):
    """Menambah profil kendaraan baru (multi kendaraan didukung)."""
    print("\n===== TAMBAH KENDARAAN =====")
    nopol = input_tidak_kosong("Nomor Polisi       : ").upper().replace(" ", "")
    merk = input_tidak_kosong("Merk Motor         : ").title()
    tipe = input_tidak_kosong("Tipe Motor         : ").title()
    tahun_ini = datetime.now().year
    while True:
        tahun = input_angka("Tahun Kendaraan    : ")
        if 1980 <= tahun <= tahun_ini + 1:
            break
        print(f"ERROR: Tahun harus antara 1980 - {tahun_ini + 1}")

    while True:
        km = input_angka("Kilometer Saat Ini : ")
        if km >= 0:
            break
        print("ERROR:")
        print("Kilometer tidak boleh negatif")

    conn = koneksi()
    conn.execute(
        """INSERT INTO kendaraan
           (user_id, nomor_polisi, merk, tipe, tahun, kilometer_saat_ini)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, nopol, merk, tipe, tahun, km),
    )
    conn.commit()
    conn.close()
    print("Kendaraan berhasil ditambahkan!")


def tampilkan_kendaraan(daftar):
    """Menampilkan tabel kendaraan dari list baris database."""
    if not daftar:
        print("Belum ada data kendaraan.")
        return
    garis(62, "-")
    print(f"{'ID':<4}{'Nopol':<14}{'Merk':<10}{'Tipe':<16}{'KM':>10}")
    garis(62, "-")
    for k in daftar:
        print(f"{k['id']:<4}{k['nomor_polisi']:<14}{k['merk']:<10}{k['tipe']:<16}"
              f"{format_angka(k['kilometer_saat_ini']):>10}")
    garis(62, "-")


def lihat_kendaraan(user_id):
    """Menu 2 - Lihat kendaraan milik user."""
    print("\n===== DATA KENDARAAN =====")
    tampilkan_kendaraan(ambil_kendaraan_user(user_id))


def pilih_kendaraan(user_id):
    """Meminta user memilih salah satu kendaraannya (validasi kepemilikan).
    Jika hanya punya satu kendaraan, langsung dipilih otomatis."""
    daftar = ambil_kendaraan_user(user_id)
    if not daftar:
        print("Anda belum memiliki kendaraan. Tambahkan dulu lewat menu 1.")
        return None

    if len(daftar) == 1:
        print(f"Kendaraan: {daftar[0]['merk']} {daftar[0]['tipe']} ({daftar[0]['nomor_polisi']})")
        return daftar[0]

    tampilkan_kendaraan(daftar)
    id_valid = [k["id"] for k in daftar]
    while True:
        pilihan = input_angka("ID Kendaraan : ")
        if pilihan in id_valid:
            return next(k for k in daftar if k["id"] == pilihan)
        print("ERROR: ID kendaraan tidak ditemukan pada akun Anda")


def update_kilometer(user_id):
    """Menu 3 - Update odometer; tidak boleh lebih kecil dari KM sebelumnya."""
    print("\n===== UPDATE KILOMETER =====")
    kendaraan = pilih_kendaraan(user_id)
    if kendaraan is None:
        return

    km_lama = kendaraan["kilometer_saat_ini"]
    print(f"KM lama : {format_angka(km_lama)}")
    while True:
        km_baru = input_angka("Kilometer Baru : ")
        if km_baru < km_lama:
            print("ERROR:")
            print("Kilometer tidak boleh berkurang")
        else:
            break

    conn = koneksi()
    conn.execute("UPDATE kendaraan SET kilometer_saat_ini = ? WHERE id = ?",
                 (km_baru, kendaraan["id"]))
    conn.commit()
    conn.close()
    print(f"Kilometer berhasil diperbarui menjadi {format_angka(km_baru)} Km")

    # Setelah KM berubah, langsung cek notifikasi kendaraan ini
    tampilkan_notifikasi_kendaraan(kendaraan["id"])


# ---------------------------------------------------------------------
# 5. MODUL RIWAYAT SERVIS & PERHITUNGAN TARGET
# ---------------------------------------------------------------------
def pilih_jenis_servis():
    """Menampilkan daftar jenis servis dan meminta user memilih."""
    jenis_list = list(INTERVAL_SERVIS.keys())
    print("Jenis Servis:")
    for i, jenis in enumerate(jenis_list, start=1):
        print(f"  {i}. {jenis} (setiap {format_angka(INTERVAL_SERVIS[jenis])} Km)")
    while True:
        nomor = input_angka("Pilih Jenis Servis (1-5) : ")
        if 1 <= nomor <= len(jenis_list):
            return jenis_list[nomor - 1]
        print("ERROR: Pilihan tidak valid")


def hitung_target(jenis_servis, km_servis):
    """Target servis berikutnya = KM saat servis + interval jenis servis."""
    return km_servis + INTERVAL_SERVIS[jenis_servis]


def tambah_riwayat(user_id):
    """Menu 4 - Catat riwayat servis dan simpan target berikutnya ke database."""
    print("\n===== TAMBAH RIWAYAT SERVIS =====")
    kendaraan = pilih_kendaraan(user_id)
    if kendaraan is None:
        return

    jenis = pilih_jenis_servis()
    tanggal = input_tanggal("Tanggal (DD-MM-YYYY, kosong = hari ini) : ")
    km_servis = input_angka("KM Saat Servis : ", minimum=0)
    biaya = input_angka("Biaya Servis   : ", minimum=0)
    catatan = input("Catatan        : ").strip()

    target = hitung_target(jenis, km_servis)

    conn = koneksi()
    conn.execute(
        """INSERT INTO riwayat_servis
           (id_kendaraan, jenis_servis, km_saat_servis, tanggal_servis,
            biaya, km_target_berikutnya, catatan)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (kendaraan["id"], jenis, km_servis, tanggal, biaya, target, catatan),
    )
    # Jika KM servis melebihi odometer tercatat, odometer ikut diperbarui
    if km_servis > kendaraan["kilometer_saat_ini"]:
        conn.execute("UPDATE kendaraan SET kilometer_saat_ini = ? WHERE id = ?",
                     (km_servis, kendaraan["id"]))
    conn.commit()
    conn.close()

    print("\nRiwayat servis berhasil disimpan!")
    print(f"Servis          : {jenis}")
    print(f"KM Saat Servis  : {format_angka(km_servis)} Km")
    print(f"Interval        : {format_angka(INTERVAL_SERVIS[jenis])} Km")
    print(f"Target berikutnya: {format_angka(target)} Km")


def ambil_riwayat(id_kendaraan):
    """Mengambil seluruh riwayat servis satu kendaraan, urut tanggal."""
    conn = koneksi()
    data = conn.execute(
        "SELECT * FROM riwayat_servis WHERE id_kendaraan = ?", (id_kendaraan,)
    ).fetchall()
    conn.close()
    # Tanggal disimpan sebagai teks DD-MM-YYYY, jadi diurutkan lewat Python
    return sorted(data, key=lambda r: (datetime.strptime(r["tanggal_servis"], "%d-%m-%Y"), r["id"]))


def tampilkan_riwayat(id_kendaraan):
    """Menampilkan tabel riwayat servis."""
    riwayat = ambil_riwayat(id_kendaraan)
    if not riwayat:
        print("Belum ada riwayat servis.")
        return riwayat
    garis(62, "-")
    print(f"{'Tanggal':<13}{'Servis':<14}{'KM':>9}{'Biaya':>12}  Catatan")
    garis(62, "-")
    for r in riwayat:
        print(f"{r['tanggal_servis']:<13}{r['jenis_servis']:<14}"
              f"{format_angka(r['km_saat_servis']):>9}{format_angka(r['biaya']):>12}  "
              f"{r['catatan'] or '-'}")
    garis(62, "-")
    return riwayat


def servis_terakhir_per_jenis(id_kendaraan):
    """Mengembalikan dict {jenis_servis: baris riwayat terbaru} untuk satu kendaraan.
    'Terbaru' ditentukan oleh KM servis terbesar (lalu id terbesar)."""
    terakhir = {}
    for r in ambil_riwayat(id_kendaraan):
        jenis = r["jenis_servis"]
        if jenis not in terakhir or (r["km_saat_servis"], r["id"]) >= \
                (terakhir[jenis]["km_saat_servis"], terakhir[jenis]["id"]):
            terakhir[jenis] = r
    return terakhir


# ---------------------------------------------------------------------
# 6. JADWAL & NOTIFIKASI
# ---------------------------------------------------------------------
def tentukan_status(km_sekarang, km_target):
    """Menentukan status servis memakai percabangan.
    Mengembalikan (kode_status, selisih_km)."""
    sisa = km_target - km_sekarang
    if km_sekarang > km_target:
        return "TERLAMBAT", km_sekarang - km_target
    elif sisa < BATAS_PERINGATAN:
        return "MENDEKATI", sisa
    else:
        return "AMAN", sisa


def cetak_status(jenis, km_sekarang, km_target):
    """Mencetak blok status sesuai 3 kondisi pada ketentuan nomor 13."""
    status, selisih = tentukan_status(km_sekarang, km_target)
    print(f"\n[{jenis.upper()}]  KM Saat Ini: {format_angka(km_sekarang)} | "
          f"Target: {format_angka(km_target)}")
    if status == "AMAN":
        print("STATUS:")
        print("Masih Aman")
        print("Sisa:")
        print(f"{format_angka(selisih)} Km lagi")
    elif status == "MENDEKATI":
        print("PERINGATAN")
        if selisih == 0:
            print("Servis jatuh tempo SEKARANG")
        else:
            print("Servis akan jatuh tempo")
        print("Sisa:")
        print(f"{format_angka(selisih)} Km lagi")
    else:
        print("BAHAYA !!!")
        print("Anda terlambat servis")
        print("Keterlambatan:")
        print(f"{format_angka(selisih)} Km")


def tampilkan_notifikasi_kendaraan(id_kendaraan):
    """Menampilkan notifikasi semua jenis servis (yang sudah punya riwayat)
    untuk satu kendaraan. Mengembalikan jumlah notifikasi yang ditampilkan."""
    conn = koneksi()
    k = conn.execute("SELECT * FROM kendaraan WHERE id = ?", (id_kendaraan,)).fetchone()
    conn.close()

    print(f"\n--- {k['merk']} {k['tipe']} ({k['nomor_polisi']}) ---")
    terakhir = servis_terakhir_per_jenis(id_kendaraan)
    if not terakhir:
        print("Belum ada riwayat servis, notifikasi belum tersedia.")
        return 0

    for jenis in INTERVAL_SERVIS:               # urut sesuai tabel interval
        if jenis in terakhir:
            cetak_status(jenis, k["kilometer_saat_ini"], terakhir[jenis]["km_target_berikutnya"])
    return len(terakhir)


def tampilkan_notifikasi(user_id):
    """Menu 6 / Dashboard - notifikasi seluruh kendaraan milik user."""
    print("\n" + "=" * 12 + " DASHBOARD NOTIFIKASI SERVIS " + "=" * 12)
    daftar = ambil_kendaraan_user(user_id)
    if not daftar:
        print("Belum ada kendaraan. Tambahkan kendaraan lewat menu 1.")
        return
    for k in daftar:
        tampilkan_notifikasi_kendaraan(k["id"])
    garis(52)


def tampilkan_jadwal(user_id):
    """Menu 5 - Jadwal servis berikutnya untuk tiap jenis servis."""
    print("\n===== JADWAL SERVIS BERIKUTNYA =====")
    kendaraan = pilih_kendaraan(user_id)
    if kendaraan is None:
        return

    terakhir = servis_terakhir_per_jenis(kendaraan["id"])
    km_now = kendaraan["kilometer_saat_ini"]
    print(f"\nKM Saat Ini: {format_angka(km_now)} Km")
    garis(66, "-")
    print(f"{'Jenis Servis':<14}{'Terakhir':>10}{'Target':>10}{'Sisa':>10}  Status")
    garis(66, "-")
    for jenis, interval in INTERVAL_SERVIS.items():
        if jenis in terakhir:
            r = terakhir[jenis]
            status, selisih = tentukan_status(km_now, r["km_target_berikutnya"])
            sisa = r["km_target_berikutnya"] - km_now
            label = {"AMAN": "Aman", "MENDEKATI": "Segera!", "TERLAMBAT": "TERLAMBAT"}[status]
            print(f"{jenis:<14}{format_angka(r['km_saat_servis']):>10}"
                  f"{format_angka(r['km_target_berikutnya']):>10}"
                  f"{format_angka(sisa):>10}  {label}")
        else:
            print(f"{jenis:<14}{'-':>10}{'-':>10}{'-':>10}  Belum ada riwayat")
    garis(66, "-")


# ---------------------------------------------------------------------
# 7. RINGKASAN BIAYA & LAPORAN
# ---------------------------------------------------------------------
def hitung_ringkasan(riwayat):
    """Menghitung total servis, total biaya, rata-rata, dan servis terbanyak."""
    total_servis = len(riwayat)
    total_biaya = sum(r["biaya"] for r in riwayat)
    rata_rata = total_biaya // total_servis if total_servis else 0
    hitung = Counter(r["jenis_servis"] for r in riwayat)
    terbanyak = hitung.most_common(1)[0] if hitung else ("-", 0)
    return total_servis, total_biaya, rata_rata, terbanyak, hitung


def tampilkan_ringkasan(riwayat):
    """Mencetak ringkasan biaya perawatan (ketentuan nomor 15)."""
    total_servis, total_biaya, rata_rata, terbanyak, _ = hitung_ringkasan(riwayat)
    print("\n--- RINGKASAN BIAYA PERAWATAN ---")
    print(f"Total Servis      : {total_servis} kali")
    print(f"Total Pengeluaran : {format_rupiah(total_biaya)}")
    print(f"Biaya Rata-rata   : {format_rupiah(rata_rata)}")
    print(f"Servis Terbanyak  : {terbanyak[0]} ({terbanyak[1]} kali)")


def progress_bar(km_sekarang, km_servis, km_target):
    """Membuat grafik ASCII progres menuju servis berikutnya (BONUS)."""
    interval = km_target - km_servis
    if interval <= 0:
        persen = 100
    else:
        persen = int((km_sekarang - km_servis) / interval * 100)
    persen = max(0, min(100, persen))
    terisi = persen * LEBAR_BAR // 100
    return "[" + "#" * terisi + "-" * (LEBAR_BAR - terisi) + f"] {persen}%"


def tampilkan_progress(kendaraan):
    """Menampilkan progress bar tiap jenis servis (BONUS)."""
    terakhir = servis_terakhir_per_jenis(kendaraan["id"])
    if not terakhir:
        return
    print("\n--- PROGRES MENUJU SERVIS BERIKUTNYA ---")
    for jenis in INTERVAL_SERVIS:
        if jenis in terakhir:
            r = terakhir[jenis]
            print(f"\n{jenis.upper()}")
            print(progress_bar(kendaraan["kilometer_saat_ini"],
                               r["km_saat_servis"], r["km_target_berikutnya"]))
            print(f"Target   : {format_angka(r['km_target_berikutnya'])} Km")
            print(f"Saat Ini : {format_angka(kendaraan['kilometer_saat_ini'])} Km")


def tampilkan_ranking(riwayat):
    """Ranking komponen yang paling sering diganti/diservis (BONUS)."""
    _, _, _, _, hitung = hitung_ringkasan(riwayat)
    if not hitung:
        return
    print("\n--- RANKING SERVIS PALING SERING ---")
    for urutan, (jenis, jumlah) in enumerate(hitung.most_common(), start=1):
        print(f"{urutan}. {jenis:<12} {jumlah} kali")


def export_csv(kendaraan, riwayat):
    """Export riwayat servis kendaraan ke file CSV (BONUS)."""
    nama_file = f"laporan_{kendaraan['nomor_polisi']}.csv"
    lokasi = os.path.join(os.path.dirname(DB_NAME), nama_file)
    with open(lokasi, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Tanggal", "Jenis Servis", "KM Servis", "Biaya",
                         "Target Berikutnya", "Catatan"])
        for r in riwayat:
            writer.writerow([r["tanggal_servis"], r["jenis_servis"], r["km_saat_servis"],
                             r["biaya"], r["km_target_berikutnya"], r["catatan"] or ""])
    print(f"Laporan berhasil diexport ke: {lokasi}")


def laporan_kendaraan(user_id):
    """Menu 7 - Laporan lengkap kendaraan."""
    kendaraan = pilih_kendaraan(user_id)
    if kendaraan is None:
        return

    riwayat = ambil_riwayat(kendaraan["id"])
    total_servis, total_biaya, _, _, _ = hitung_ringkasan(riwayat)
    terakhir = servis_terakhir_per_jenis(kendaraan["id"])

    # Servis berikutnya = target terdekat (km_target terkecil)
    if terakhir:
        jenis_next, r_next = min(terakhir.items(),
                                 key=lambda item: item[1]["km_target_berikutnya"])
        next_jenis = jenis_next
        next_target = f"{format_angka(r_next['km_target_berikutnya'])} Km"
    else:
        next_jenis, next_target = "-", "-"

    print()
    garis(22)
    print("YOHANES MANDALIKA SPEEDSHOP REPORT")
    garis(22)
    print("Motor:")
    print(f"{kendaraan['merk']} {kendaraan['tipe']} ({kendaraan['nomor_polisi']})")
    print("\nKM Saat Ini:")
    print(format_angka(kendaraan["kilometer_saat_ini"]))
    print("\nTotal Servis:")
    print(total_servis)
    print("\nTotal Biaya:")
    print(format_rupiah(total_biaya))
    print("\nServis Berikutnya:")
    print(next_jenis)
    print("\nTarget:")
    print(next_target)
    garis(22)

    print("\n--- RIWAYAT SERVIS ---")
    tampilkan_riwayat(kendaraan["id"])
    if riwayat:
        tampilkan_ringkasan(riwayat)
        tampilkan_ranking(riwayat)
        tampilkan_progress(kendaraan)

        simpan = input("\nExport laporan ke CSV? (y/n) : ").strip().lower()
        if simpan == "y":
            export_csv(kendaraan, riwayat)


# ---------------------------------------------------------------------
# 8. ADMIN (opsional)
# ---------------------------------------------------------------------
def admin_lihat_kendaraan():
    """Admin: melihat seluruh kendaraan beserta pemiliknya."""
    conn = koneksi()
    data = conn.execute("""
        SELECT k.*, u.nama AS pemilik
        FROM kendaraan k JOIN user u ON k.user_id = u.id
        ORDER BY k.id
    """).fetchall()
    conn.close()

    print("\n===== SEMUA KENDARAAN =====")
    if not data:
        print("Belum ada kendaraan terdaftar.")
        return
    garis(76, "-")
    print(f"{'ID':<4}{'Nopol':<14}{'Merk':<10}{'Tipe':<14}{'KM':>9}  Pemilik")
    garis(76, "-")
    for k in data:
        print(f"{k['id']:<4}{k['nomor_polisi']:<14}{k['merk']:<10}{k['tipe']:<14}"
              f"{format_angka(k['kilometer_saat_ini']):>9}  {k['pemilik']}")
    garis(76, "-")


def admin_lihat_riwayat():
    """Admin: melihat seluruh riwayat servis semua kendaraan."""
    conn = koneksi()
    data = conn.execute("""
        SELECT r.*, k.nomor_polisi
        FROM riwayat_servis r JOIN kendaraan k ON r.id_kendaraan = k.id
        ORDER BY r.id
    """).fetchall()
    conn.close()

    print("\n===== SEMUA RIWAYAT SERVIS =====")
    if not data:
        print("Belum ada riwayat servis.")
        return
    garis(76, "-")
    print(f"{'Nopol':<12}{'Tanggal':<13}{'Servis':<14}{'KM':>9}{'Biaya':>12}")
    garis(76, "-")
    for r in data:
        print(f"{r['nomor_polisi']:<12}{r['tanggal_servis']:<13}{r['jenis_servis']:<14}"
              f"{format_angka(r['km_saat_servis']):>9}{format_angka(r['biaya']):>12}")
    garis(76, "-")


def menu_admin(user):
    """Menu khusus admin (looping sampai logout)."""
    while True:
        print("\n===== ADMIN YOHANES MANDALIKA SPEEDSHOP =====")
        print("1. Lihat Seluruh Kendaraan")
        print("2. Lihat Seluruh Riwayat Servis")
        print("3. Logout")
        pilihan = input("Pilih menu : ").strip()
        if pilihan == "1":
            admin_lihat_kendaraan()
        elif pilihan == "2":
            admin_lihat_riwayat()
        elif pilihan == "3":
            print("Logout berhasil.")
            break
        else:
            print("ERROR: Pilihan menu tidak valid")


# ---------------------------------------------------------------------
# 9. MENU UTAMA
# ---------------------------------------------------------------------
def menu_user(user):
    """Menu utama user. Berjalan terus (while) sampai user memilih Logout."""
    print(f"\nSelamat datang, {user['nama']}!")
    tampilkan_notifikasi(user["id"])      # dashboard otomatis saat aplikasi dibuka

    while True:
        print("\n===== YOHANES MANDALIKA SPEEDSHOP =====")
        print("1. Tambah Kendaraan")
        print("2. Lihat Kendaraan")
        print("3. Update Kilometer")
        print("4. Tambah Riwayat Servis")
        print("5. Jadwal Servis Berikutnya")
        print("6. Notifikasi Servis")
        print("7. Laporan Kendaraan")
        print("8. Logout")
        pilihan = input("Pilih menu : ").strip()

        if pilihan == "1":
            tambah_kendaraan(user["id"])
        elif pilihan == "2":
            lihat_kendaraan(user["id"])
        elif pilihan == "3":
            update_kilometer(user["id"])
        elif pilihan == "4":
            tambah_riwayat(user["id"])
        elif pilihan == "5":
            tampilkan_jadwal(user["id"])
        elif pilihan == "6":
            tampilkan_notifikasi(user["id"])
        elif pilihan == "7":
            laporan_kendaraan(user["id"])
        elif pilihan == "8":
            print("Logout berhasil. Sampai jumpa!")
            break
        else:
            print("ERROR: Pilihan menu tidak valid")


def menu_awal():
    """Menu awal: Login / Registrasi / Keluar."""
    while True:
        print("\n===== YOHANES MANDALIKA SPEEDSHOP =====")
        print("Aplikasi Pencatatan Servis Motor Berkala")
        print("1. Login")
        print("2. Registrasi")
        print("3. Keluar")
        pilihan = input("Pilih menu : ").strip()

        if pilihan == "1":
            user = login()
            if user:
                if user["role"] == "admin":
                    menu_admin(user)
                else:
                    menu_user(user)
        elif pilihan == "2":
            registrasi()
        elif pilihan == "3":
            print("Terima kasih telah menggunakan YOHANES MANDALIKA SPEEDSHOP.")
            break
        else:
            print("ERROR: Pilihan menu tidak valid")


def main():
    buat_tabel()
    menu_awal()


if __name__ == "__main__":
    main()
