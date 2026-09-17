# OSINT Person Lookup (`bulk_osint.py`)

Tools otomatisasi investigasi OSINT (*Open Source Intelligence*) untuk melakukan identifikasi jejak digital personal (akun media sosial, afiliasi organisasi/komunitas, dan akun terdaftar) berdasarkan kombinasi **Nama**, **Nomor HP**, dan/atau **Email** dalam jumlah banyak (*bulk processing* via file Excel/CSV).

---

## 🔄 Alur Kerja Baru (*Targeted Multi-step Flow*)

Alur kerja dioptimalkan secara bertahap agar lebih akurat dan fokus:

```
[1. Input Excel/CSV] (Nama, No HP, Email)
         │
         ▼
[2. Step 1: Cek Email Terdaftar (Holehe)]
├── Cek email ke puluhan platform (Instagram, Facebook, Twitter, Spotify, GitHub, dll)
└── Simpan daftar platform yang terbukti terdaftar (verified platforms)
         │
         ▼
[3. Step 2: Targeted Multi-Query Google Search]
├── Pencarian berulang dan terarah:
│   • Query 1: "{nama}"
│   • Query 2: "{nama}" instagram & "{nama}" site:instagram.com (jika IG terdaftar)
│   • Query 3: "{nama}" facebook & "{nama}" site:facebook.com (jika FB terdaftar)
│   • Query 4..N: "{nama}" {platform} untuk platform terdaftar lainnya
│   • Query Pelengkap: Pencarian platform umum lainnya
└── Scoring & Verifikasi:
    • Nilai bobot kecocokan nama pada handle dan judul profil
    • Bonus keyakinan (+0.5 skor) jika profil ditemukan pada platform yang terverifikasi Holehe
         │
         ▼
[4. Step 3: Pelacakan Afiliasi Komunitas & Organisasi]
├── Query berbasis Nama + Handle terkuat
└── Ekstraksi nama resmi yayasan, organisasi, atau project
         │
         ▼
[5. Step 4: Maigret (Opsional)]
└── Reverse search username jika flag `--maigret` diaktifkan
         │
         ▼
[6. Output Excel: Kolom 'Notes']
└── Disimpan ke `<input>_result.xlsx` dengan format multi-baris rapi
```

---

## 🚀 Fitur Utama

- **Pengecekan Email di Awal**: Memanfaatkan Holehe sebelum pencarian web untuk menentukan platform target yang valid.
- **Pencarian Google Bertarget & Multi-Iterasi**: Membuat variasi query pencarian otomatis berdasarkan bukti platform yang dimiliki target (`nama`, `nama + IG`, `nama + FB`, dst).
- **Ekstraksi Afiliasi Organisasi & Komunitas**: Mengidentifikasi nama organisasi/program resmi dari judul artikel/profil publik.
- **Scoring Cerdas & Cross-Verification**: Memberikan tanda `[Terverifikasi Email]` dan skor tinggi jika profil sosmed cocok dengan email yang terbukti terdaftar.
- **Output Terstruktur**: Menghasilkan file baru `<input>_result.xlsx` tanpa merusak kolom asli.
- **Dua Mode Pencarian**: Mendukung mode *live search* langsung dan mode *2-pass cache* anti rate-limit.

---

## 📦 Instalasi

Pastikan menggunakan Python 3.10+ (disarankan Python 3.12).

```bash
# Clone repository
git clone https://github.com/temonwkwk/osint-person-lookup.git
cd osint-person-lookup

# Install dependency
pip install -r requirements.txt
```

---

## 📋 Format File Input

File input dapat berupa `.xlsx` atau `.csv`. Header kolom akan dideteksi secara otomatis:
- **Nama**: Kolom `Nama`, `Name`, `Full Name`
- **Nomor HP**: Kolom `No HP`, `Nomor HP`, `Phone`, `Telepon`, `Handphone`
- **Email**: Kolom `Email`, `Alamat Email`, `Mail`

Contoh:

| Nama | No HP | Email | Kota |
| :--- | :--- | :--- | :--- |
| Budi Santoso | 081234567890 | budi.santoso99@gmail.com | Jakarta |
| Siti Rahmawati | 085712345678 | siti.rahma@yahoo.com | Surabaya |

---

## 🛠️ Cara Penggunaan

### 1. Mode Standar (Live Search)

```bash
python bulk_osint.py input.xlsx
```

---

### 2. Mode 2-Pass Cache (Untuk Data Jumlah Besar)

**Langkah 1 — Dump Daftar Query:**
```bash
python bulk_osint.py input.xlsx --search-cache cache.json --dump-queries queries.json --no-live-search --skip-holehe
```

**Langkah 2 — Ambil Hasil Search ke `cache.json`:**
Isi data hasil pencarian ke dalam file `cache.json`.

**Langkah 3 — Eksekusi Analisis Lengkap:**
```bash
python bulk_osint.py input.xlsx --search-cache cache.json
```

---

## 📊 Format Output (`Notes`)

```text
Sosmed: IG: https://www.instagram.com/budisantoso/ [Terverifikasi Email] (skor 2.8); FB: https://www.facebook.com/budisantoso [Terverifikasi Email]
Komunitas: Greenheart International, Yayasan Peduli Negeri
Email terdaftar di: instagram, facebook, spotify, office365
Catatan: kecocokan lemah, perlu verifikasi manual (hanya jika skor < 2.0)
```

---

## 📄 Lisensi

Didistribusikan di bawah Lisensi [MIT](LICENSE).
