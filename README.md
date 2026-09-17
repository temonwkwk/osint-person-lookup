# OSINT Person Lookup (`bulk_osint.py`)

Tools otomatisasi investigasi OSINT (*Open Source Intelligence*) untuk melakukan identifikasi jejak digital personal (akun media sosial, afiliasi organisasi/komunitas, dan akun terdaftar) berdasarkan kombinasi **Nama**, **Nomor HP**, dan/atau **Email** dalam jumlah banyak (*bulk processing* via file Excel/CSV).

---

## 🚀 Fitur Utama

- **Pencarian Media Sosial Otomatis**: Mendeteksi akun Instagram, TikTok, Twitter/X, Facebook, LinkedIn, YouTube, Threads, dan Pinterest yang memiliki korelasi tinggi dengan nama target.
- **Ekstraksi Afiliasi Organisasi & Komunitas**: Mengidentifikasi nama organisasi, yayasan, project, kampus, atau komunitas dari judul artikel/profil publik (bukan sekadar domain mentah).
- **Deteksi Registrasi Akun Email via Holehe**: Memeriksa apakah email target terdaftar di berbagai layanan online (misal: Office365, Spotify, Twitter, GitHub, dll).
- **Scoring & Verifikasi Cerdas**: Menggunakan algoritma pembobotan kecocokan nama untuk menyaring profil palsu atau homonim.
- **Output Terstruktur & Rapi**: Menghasilkan file baru `<input>_result.xlsx` tanpa merusak kolom asli, menambahkan satu kolom ringkasan `Notes` multi-baris.
- **Dua Mode Pencarian**: Mendukung mode *live search* langsung maupun mode *2-pass cached search* untuk menghindari rate-limit mesin pencari.

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

File input dapat berupa `.xlsx` atau `.csv`. Header kolom akan dideteksi secara otomatis (case-insensitive):
- **Nama**: Kolom `Nama`, `Name`, `Full Name`
- **Nomor HP**: Kolom `No HP`, `Nomor HP`, `Phone`, `Telepon`, `Handphone`
- **Email**: Kolom `Email`, `Alamat Email`, `Mail`

Contoh struktur tabel:

| Nama | No HP | Email | Kota |
| :--- | :--- | :--- | :--- |
| Budi Santoso | 081234567890 | budi.santoso99@gmail.com | Jakarta |
| Siti Rahmawati | 085712345678 | siti.rahma@yahoo.com | Surabaya |

---

## 🛠️ Cara Penggunaan

### 1. Mode Standar (Live Search)

Menjalankan proses secara langsung untuk seluruh baris:

```bash
python bulk_osint.py input.xlsx
```

Hasil akan disimpan otomatis ke `input_result.xlsx`.

---

### 2. Mode 2-Pass Cache (Direkomendasikan untuk Data Besar)

Untuk menghindari blokir atau rate-limit dari mesin pencari saat memproses ratusan data, gunakan pola 2-pass:

**Langkah 1 — Dump Daftar Query:**
```bash
python bulk_osint.py input.xlsx --search-cache cache.json --dump-queries queries.json --no-live-search --skip-holehe
```

**Langkah 2 — Ambil Hasil Search ke `cache.json`:**
Isi data hasil pencarian ke dalam file `cache.json` menggunakan search engine / API pilihan Anda.

**Langkah 3 — Eksekusi Analisis Lengkap:**
```bash
python bulk_osint.py input.xlsx --search-cache cache.json
```

---

## 📊 Format Output (`Notes`)

Hasil analisis disajikan dalam format multi-baris pada kolom `Notes`:

```text
Sosmed: IG: https://www.instagram.com/budisantoso/ | LinkedIn: https://www.linkedin.com/in/budisantoso
Komunitas: Greenheart International, Yayasan Peduli Negeri
Email terdaftar di: office365, spotify, twitter
Catatan: kecocokan lemah, perlu verifikasi manual (jika skor < 2.0)
```

---

## ⚙️ Opsi Command Line

```text
usage: bulk_osint.py [-h] [--output OUTPUT] [--search-cache SEARCH_CACHE]
                     [--dump-queries DUMP_QUERIES] [--no-live-search]
                     [--skip-holehe] [--delay DELAY]
                     input_file

positional arguments:
  input_file            File input (.xlsx atau .csv)

options:
  -h, --help            Tampilkan bantuan
  --output OUTPUT       Path file output kustom
  --search-cache PATH   Gunakan cache file JSON untuk hasil search engine
  --dump-queries PATH   Simpan query pencarian yang dihasilkan ke file JSON
  --no-live-search      Nonaktifkan live HTTP search ke DuckDuckGo/Google
  --skip-holehe         Lewati pengecekan email dengan Holehe
  --delay DELAY         Delay jeda antar request (detik)
```

---

## 🔒 Privasi & Keamanan Data

- Repository ini **tidak menyimpan data pribadi atau hasil investigasi nyata**.
- Pastikan untuk selalu menambahkan file data sensitif (`target.xlsx`, `cache.json`, `*.log`) ke dalam `.gitignore` sebelum melakukan commit.

---

## 📄 Lisensi

Didistribusikan di bawah Lisensi [MIT](LICENSE).
