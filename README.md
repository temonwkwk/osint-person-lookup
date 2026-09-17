# OSINT Person Lookup (`bulk_osint.py`)

Tools otomatisasi investigasi OSINT (*Open Source Intelligence*) yang **dioptimalkan khusus untuk Customer Outreach / Akuisisi Nasabah** (Instagram, TikTok, Facebook, WhatsApp/DM) berdasarkan kombinasi **Nama**, **Nomor HP**, dan/atau **Email** dalam jumlah banyak (*bulk processing* via file Excel/CSV).

---

## 🎯 Fokus: Customer Acquisition & Direct Outreach

Pipeline ini dirancang untuk menemukan kanal tercepat dalam menghubungi calon customer/nasabah secara personal:

1. **Prioritas Media Sosial Konsumen (IG, TikTok, FB, Threads)**:
   - Menempatkan Instagram, TikTok, dan Facebook di urutan teratas pencarian.
   - LinkedIn tetap diposisikan sebagai validator latar belakang profesional nasabah.
2. **Handle Cascading (Pencocokan Silang Username)**:
   - Jika satu username/handle teridentifikasi (dari email atau IG), script otomatis menyisir akun yang sama di TikTok, Facebook, dan Threads.
3. **Ekstraksi Sinyal Kontak Langsung**:
   - Mendeteksi jumlah pengikut (*followers*), nomor WhatsApp, tautan kontak (`wa.me`, `linktr.ee`, `biolinky`), dan bio.
4. **Topik Pembuka Obrolan (*Ice Breakers*)**:
   - Menarik kegiatan, komunitas, atau hobi dari highlight dan postingan publik untuk memudahkan tim sales/outreach membuka percakapan.

---

## 🔄 Alur Kerja Pipeline

```
[1. Input Data] (Nama, No HP, Email)
         │
         ▼
[2. Step 1: Cek Email Terdaftar (Holehe) & Reverse Lookup]
├── Cek email ke puluhan platform (Instagram, Facebook, Spotify, Twitter, dll)
└── Auto-Feedback Loop: Jika nama awal kosong, ekstrak nama dari prefix email/username
         │
         ▼
[3. Step 2: Customer Outreach Multi-Query Search]
├── Prioritas 1: site:instagram.com "{nama}" & "{nama}" instagram
├── Prioritas 2: site:tiktok.com "{nama}" & "{nama}" tiktok
├── Prioritas 3: site:facebook.com "{nama}" & "{nama}" facebook
├── Prioritas 4: site:threads.net / site:x.com
└── Validator: site:linkedin.com (Latar Belakang Karir)
         │
         ▼
[4. Step 3: Handle Cascading]
└── Sisir username kandidat lintas platform (IG ↔ TikTok ↔ FB)
         │
         ▼
[5. Step 4: Minat, Komunitas & Ice Breaker Probe]
└── Ekstraksi kegiatan, komunitas, baksos, atau hobi dari postingan publik
         │
         ▼
[6. Step 5: Ekstraksi Sinyal Kontak & Reachability]
└── Ekstraksi WhatsApp, Link Bio, Jumlah Followers, dan Status Akun
         │
         ▼
[7. Output Excel: Format Khusus Outreach]
└── Disimpan ke `<input>_result.xlsx`
```

---

## 📊 Format Output Kolom `Notes` (Outreach Ready)

Hasil di kolom `Notes` tersusun rapi untuk kebutuhan tim sales/marketing:

```text
Sosmed Utama (Outreach): IG: https://www.instagram.com/cho2late/ (6,645 followers | Link: linktr.ee/handoko) [Terverifikasi Email]; FB: https://www.facebook.com/handoko.wibowo
Kanal DM / Outreach: Instagram DM (@cho2late) | WhatsApp: 08123456789
Profil Profesional: LinkedIn: https://www.linkedin.com/in/handoko-p-wibowo-3b508443
Minat & Komunitas (Ice Breaker): Weekend Adventure Enthusiast, GVM Networks, Scooter Prix
Email terdaftar di: office365, spotify, twitter
Catatan: kecocokan nama 100% valid
```

---

## 📦 Instalasi & Cara Pakai

Pastikan menggunakan Python 3.10+ (disarankan Python 3.12).

```bash
# Clone repository
git clone https://github.com/temonwkwk/osint-person-lookup.git
cd osint-person-lookup

# Install dependency
pip install -r requirements.txt
```

### 1. Mode Standar (Live Search)
```bash
python bulk_osint.py input.xlsx
```

### 2. Mode 2-Pass Cache (Untuk Data Besar / Anti Rate-Limit)
```bash
# Step 1: Dump queries
python bulk_osint.py input.xlsx --search-cache cache.json --dump-queries queries.json --no-live-search --skip-holehe

# Step 2: Ambil hasil search ke cache.json

# Step 3: Eksekusi analisis penuh dari cache
python bulk_osint.py input.xlsx --search-cache cache.json
```

---

## 📄 Lisensi

Didistribusikan di bawah Lisensi [MIT](LICENSE).
