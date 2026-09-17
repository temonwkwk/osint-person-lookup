# OSINT Person Lookup (`bulk_osint.py`)

Tools otomatisasi investigasi OSINT (*Open Source Intelligence*) yang **dioptimalkan khusus untuk Customer Outreach / Akuisisi Nasabah** (Instagram, TikTok, Facebook, WhatsApp/DM) dengan dukungan **AI Face Matching (100% Local CPU)** berdasarkan kombinasi **Nama**, **Nomor HP**, **Email**, dan/atau **Foto Profil/KTP** via file Excel/CSV.

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
   - Menghitung kemiripan wajah (Cosine Similarity) antara foto baseline (KTP/LinkedIn) dengan avatar sosmed target.
   - Dilengkapi sistem cache embedding wajah di `.face_cache/` agar tidak ada komputasi berulang.
5. **Ekstraksi Sinyal Kontak & Reachability**:
   - Mendeteksi jumlah followers, nomor WhatsApp, tautan kontak (`wa.me`, `linktr.ee`, `biolinky`), dan bio.
6. **Topik Pembuka Obrolan (*Ice Breakers*)**:
   - Menarik kegiatan, komunitas, atau hobi dari highlight dan postingan publik.

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

### 1. Mode Standar Cepat (Tanpa Face Match)
```bash
python bulk_osint.py input.xlsx
```

### 2. Mode AI Face Matching (Pencocokan Wajah di CPU Lokal)
Jika di Excel terdapat kolom `Foto` / `Photo` / `Avatar` (berisi URL atau path file gambar lokal):
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
Sosmed Utama (Outreach): IG: https://www.instagram.com/cho2late/ (6,645 followers | Link: linktr.ee/handoko | Wajah Cocok: 88%) [Terverifikasi Email]; FB: https://www.facebook.com/handoko.wibowo
Kanal DM / Outreach: Instagram DM (@cho2late) | WhatsApp: 08123456789
Profil Profesional: LinkedIn: https://www.linkedin.com/in/handoko-p-wibowo-3b508443
Minat & Komunitas (Ice Breaker): Weekend Adventure Enthusiast, GVM Networks, Scooter Prix
Email terdaftar di: office365, spotify, twitter
Catatan: kecocokan nama 100% valid dan terverifikasi visual
```

---

## 📄 Lisensi

Didistribusikan di bawah Lisensi [MIT](LICENSE).
