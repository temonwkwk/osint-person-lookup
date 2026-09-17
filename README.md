# OSINT Person Lookup & Customer Outreach (`bulk_osint.py`)

Toolkit otomatisasi investigasi OSINT (*Open Source Intelligence*) berbasis Python yang **dioptimalkan khusus untuk Customer Outreach & Profiling Personal** (Instagram, TikTok, Facebook, WhatsApp/DM) dengan dukungan **AI Face Matching (100% Local CPU)** berdasarkan data Nama, Nomor HP, Email, dan/atau Foto via file Excel/CSV.

---

## 🎯 Fitur & Alur Utama (Outreach-Focused)

1. **Email Pre-check (Holehe) & Reverse Name Discovery**:
   - Memeriksa platform aktif (Twitter, Spotify, Office365, dll).
   - Auto-Feedback Loop: Jika nama awal kosong, otomatis mendeteksi nama asli dari prefix email.
2. **Prioritas Media Sosial Konsumen (IG, TikTok, FB, Threads)**:
   - Pencarian bertarget menyasar Instagram, TikTok, Facebook, dan Threads.
   - Sub-name combinations otomatis untuk nama 3+ kata.
   - LinkedIn diposisikan sebagai validator latar belakang profesional.
3. **Handle Cascading**:
   - Sisir username kandidat lintas platform (IG ↔ TikTok ↔ FB).
4. **AI Face Recognition & Matching (Opsional via `--face-match`)**:
   - Menggunakan **OpenCV YuNet (Detection) + SFace (Recognition)** berbasis ONNX.
   - Berjalan **100% di CPU lokal** tanpa GPU dan tanpa API luar.
   - Menghitung kemiripan biometrik wajah antara foto LinkedIn/KTP dengan avatar sosmed target.
   - Dilengkapi sistem cache embedding wajah di `.face_cache/` agar tidak ada komputasi berulang.
5. **Ekstraksi Sinyal Kontak & Reachability**:
   - Mendeteksi jumlah followers, nomor WhatsApp, tautan kontak (`wa.me`, `linktr.ee`, `biolinky`), dan bio.
6. **Topik Pembuka Obrolan (*Ice Breakers*)**:
   - Menarik kegiatan, komunitas, atau hobi dari highlight dan postingan publik.

---

## 📋 Format File Input

File input dapat berupa `.xlsx` atau `.csv`. Header kolom otomatis terdeteksi (case-insensitive):
- **Nama**: `Nama`, `Name`, `Full Name`
- **Nomor HP**: `Nomor HP`, `No HP`, `Phone`, `Telepon`, `WhatsApp`
- **Email**: `Email`, `Alamat Email`, `Mail`
- **Foto (Opsional)**: `Foto`, `Photo`, `Avatar`

Contoh:

| Nama | No HP | Email | Kota |
| :--- | :--- | :--- | :--- |
| Example Target A | 081200000001 | target_a@example.com | Jakarta |
| Example Target B | 085700000002 | target_b@example.com | Bandung |
| Example Target C | 081300000003 | target_c@example.com | Surabaya |

---

## 🛠️ Cara Penggunaan

Pastikan menggunakan Python 3.10+ (disarankan Python 3.12).

```bash
# Clone repository
git clone https://github.com/temonwkwk/osint-person-lookup.git
cd osint-person-lookup

# Install dependency
pip install -r requirements.txt
```

### 1. Mode Standar Cepat (Tanpa Face Match)
```bash
python bulk_osint.py input.xlsx
```

### 2. Mode AI Face Matching (Pencocokan Wajah di CPU Lokal)
```bash
python bulk_osint.py input.xlsx --face-match
```

### 3. Mode 2-Pass Cache (Untuk Data Besar / Anti Rate-Limit)
```bash
# Step 1: Dump queries
python bulk_osint.py input.xlsx --search-cache cache.json --dump-queries queries.json --no-live-search --skip-holehe

# Step 2: Ambil hasil search ke cache.json

# Step 3: Eksekusi analisis penuh dari cache
python bulk_osint.py input.xlsx --search-cache cache.json --face-match
```

---

## 📊 Format Output Kolom `Notes` (Outreach Ready)

```text
Sosmed Utama (Outreach): IG: https://www.instagram.com/example_user/ (12.5k followers | WA: 081200000001 | Wajah Cocok: 88%) [Terverifikasi Email]; FB: https://www.facebook.com/example_user
Kanal DM / Outreach: Instagram DM (@example_user) | WhatsApp: 081200000001
Profil Profesional: LinkedIn: https://www.linkedin.com/in/example-user
Minat & Komunitas (Ice Breaker): Tech & Startups, Running Club, Volunteer
Email terdaftar di: office365, spotify, twitter
Catatan: data cocok 100% terverifikasi
```

---

## 🔒 Privasi & Keamanan Data

- Repository ini **tidak menyimpan data pribadi atau hasil investigasi nyata**.
- Seluruh file data (`target*.xlsx`, `cache.json`, `queries.json`) otomatis diabaikan oleh `.gitignore`.

---

## 📄 Lisensi

Didistribusikan di bawah Lisensi [MIT](LICENSE).
