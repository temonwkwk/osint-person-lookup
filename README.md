# OSINT Person & Community Intelligence Suite

Toolkit otomatisasi investigasi OSINT (*Open Source Intelligence*) berbasis Python yang dioptimalkan untuk:
1. **`bulk_osint.py`**: **Customer Outreach & Profiling Personal** (Cari Sosmed, Kontak DM/WA, & AI Face Matching).
2. **`community_osint.py`**: **Community Intelligence & Multi-Community Mapping** (Cari Sosmed Komunitas, Wilayah/Daerah, Komunitas Lain yang Dikelola PIC, & Komunitas Sejenis).

---

## 🏢 1. Community Intelligence (`community_osint.py`)

Dirancang khusus untuk membedah ekosistem komunitas, jangkauan wilayah, dan keterlibatan PIC di organisasi lain.

### 📋 Format Input Excel / CSV:
Kolom header otomatis terdeteksi (case-insensitive):
- **Nama Komunitas**: `Nama Komunitas`, `Komunitas`, `Community`
- **Deskripsi Komunitas**: `Deskripsi Komunitas`, `Deskripsi`, `Kegiatan`
- **Nama PIC**: `Nama PIC Komunitas`, `PIC`, `Ketua`, `Founder`
- **Email PIC**: `Email PIC`, `Email`
- **Nomor HP PIC**: `Nomor HP PIC`, `No HP`, `WhatsApp`

Contoh:
| Nama Komunitas | Deskripsi Komunitas | Nama PIC Komunitas | Email PIC | Nomor HP PIC |
| :--- | :--- | :--- | :--- | :--- |
| Indonesian Cloud Community | Komunitas praktisi cloud computing & DevOps di Jakarta | Faisal Reza | faisal@gmail.com | 08123456789 |
| Peduli Sampah Jogja | Gerakan relawan bank sampah & aksi bersih sungai | Yogi Atmaja | ogijogjaaa@gmail.com | 08571234567 |

### 🚀 Output yang Dihasilkan di Kolom `Community Intelligence`:
```text
Sosmed Komunitas: IG: https://www.instagram.com/cloudcommunity.id/ (4.2k followers); FB Group: https://facebook.com/groups/cloudid; Linktree: https://linktr.ee/cloudcommunity
Daerah / Wilayah: Jakarta (Jabodetabek)
Komunitas Lain Kelolaan PIC: DevOps Forum Indonesia, Yayasan Edukasi Teknologi
Komunitas Sejenis di Jakarta: Jakarta Tech Community, Python Developers Group, Kopi & Cloud
Profil PIC: Nama: Faisal Reza | No HP/WA: 08123456789 | Email: faisal@gmail.com | Platform Aktif: office365, spotify, twitter
```

### 🛠️ Cara Menjalankan:
```bash
# Mode Langsung
python community_osint.py input_komunitas.xlsx

# Mode 2-Pass Cache (Direkomendasikan untuk data banyak)
python community_osint.py input_komunitas.xlsx --search-cache cache.json --dump-queries queries.json --no-live-search
```

---

## 👤 2. Person Outreach & AI Face Match (`bulk_osint.py`)

Dirancang untuk menemukan kanal media sosial konsumen (IG, TikTok, FB, Threads, WhatsApp) dari calon customer.

- **Email Pre-check (Holehe)**: Memverifikasi akun aktif sebelum pencarian.
- **Auto-Feedback Loop**: Menemukan nama asli dari username email jika nama awal kosong.
- **Sub-name Combinations**: Memecah nama 3–4 kata agar tetap menemukan akun IG yang hanya memakai 2 kata.
- **AI Face Recognition (YuNet + SFace)**: Pencocokan biometrik wajah 100% di CPU lokal via `--face-match`.

### 🛠️ Cara Menjalankan:
```bash
# Mode Cepat
python bulk_osint.py input_nasabah.xlsx

# Mode dengan AI Face Recognition
python bulk_osint.py input_nasabah.xlsx --face-match
```

---

## 📦 Instalasi

Pastikan menggunakan Python 3.10+ (disarankan Python 3.12).

```bash
git clone https://github.com/temonwkwk/osint-person-lookup.git
cd osint-person-lookup
pip install -r requirements.txt
```

---

## 📄 Lisensi

Didistribusikan di bawah Lisensi [MIT](LICENSE).
