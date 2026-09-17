#!/usr/bin/env python3
"""Community OSINT Lookup & Mapping (`community_osint.py`)

Input Format (Excel / CSV):
  Nama Komunitas | Deskripsi Komunitas | Nama PIC Komunitas | Email PIC | Nomor HP PIC

Outputs:
  1. Sosmed Komunitas (Instagram, Facebook Group/Page, TikTok, Threads, Linktree/Web)
  2. Daerah / Wilayah Cakupan Komunitas (Kota, Kabupaten, atau Nasional)
  3. Komunitas Lain yang Dikelola oleh PIC yang Sama (Multi-community mapping)
  4. Komunitas Sejenis di Daerah Tersebut (Peer / Competitor communities)

Usage:
  python3 community_osint.py input.xlsx [--search-cache cache.json] [--dump-queries q.json] [--no-live-search]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Induk kota & wilayah di Indonesia untuk deteksi daerah
INDONESIAN_REGIONS = [
    # Jabodetabek & Banten
    "Jakarta", "Jakarta Pusat", "Jakarta Selatan", "Jakarta Barat", "Jakarta Timur", "Jakarta Utara",
    "Jabodetabek", "Bogor", "Depok", "Tangerang", "Tangerang Selatan", "Bekasi", "Banten", "Serang", "Cilegon",
    # Jawa Barat
    "Bandung", "Cimahi", "Cirebon", "Tasikmalaya", "Garut", "Sukabumi", "Karawang", "Purwakarta", "Subang", "Sumedang", "Indramayu", "Majalengka", "Kuningan", "Ciamis", "Banjar", "Pangandaran", "Jawa Barat", "Jabar",
    # Jawa Tengah & DIY
    "Semarang", "Solo", "Surakarta", "Yogyakarta", "Jogja", "Sleman", "Bantul", "Kulon Progo", "Gunungkidul",
    "Magelang", "Salatiga", "Pekalongan", "Tegal", "Banyumas", "Purwokerto", "Cilacap", "Kudus", "Jepara", "Pati", "Klaten", "Jawa Tengah", "Jateng", "DIY",
    # Jawa Timur
    "Surabaya", "Malang", "Sidoarjo", "Gresik", "Kediri", "Blitar", "Madiun", "Jember", "Banyuwangi", "Pasuruan", "Mojokerto", "Batu", "Probolinggo", "Jawa Timur", "Jatim",
    # Bali & Nusa Tenggara
    "Bali", "Denpasar", "Badung", "Gianyar", "Ubud", "Singaraja", "Lombok", "Mataram", "Sumbawa", "Bima", "Kupang", "Flores", "Labuan Bajo", "NTB", "NTT",
    # Sumatera
    "Medan", "Deli Serdang", "Binjai", "Pematangsiantar", "Sumatera Utara", "Sumut",
    "Palembang", "Sumatera Selatan", "Sumsel", "Padang", "Bukittinggi", "Sumatera Barat", "Sumbar",
    "Pekanbaru", "Riau", "Batam", "Tanjungpinang", "Kepulauan Riau", "Kepri",
    "Bandar Lampung", "Lampung", "Jambi", "Bengkulu", "Bangka", "Belitung", "Pangkalpinang", "Aceh", "Banda Aceh", "Lhokseumawe",
    # Kalimantan
    "Pontianak", "Singkawang", "Kalimantan Barat", "Kalbar",
    "Banjarmasin", "Banjarbaru", "Kalimantan Selatan", "Kalsel",
    "Balikpapan", "Samarinda", "IKN", "Nusantara", "Kutai Kartanegara", "Kalimantan Timur", "Kaltim",
    "Palangkaraya", "Kalimantan Tengah", "Kalteng", "Tarakan", "Kalimantan Utara", "Kaltara",
    # Sulawesi
    "Makassar", "Gowa", "Maros", "Sulawesi Selatan", "Sulsel",
    "Manado", "Tomohon", "Bitung", "Sulawesi Utara", "Sulut",
    "Palu", "Sulawesi Tengah", "Sulteng", "Kendari", "Sulawesi Tenggara", "Sultra",
    "Gorontalo", "Mamuju", "Sulawesi Barat", "Sulbar",
    # Maluku & Papua
    "Ambon", "Ternate", "Maluku", "Maluku Utara",
    "Jayapura", "Sorong", "Timika", "Merauke", "Manokwari", "Papua",
    # Nasional
    "Indonesia", "Nasional",
]

COMMUNITY_NICHE_KEYWORDS = [
    # Lingkungan & Sosial
    "lingkungan", "sampah", "plastik", "hutan", "relawan", "volunteer", "baksos", "charity",
    "sosial", "donasi", "peduli", "kemanusiaan", "pemberdayaan", "yayasan",
    # Olahraga & Hobi
    "lari", "running", "marathon", "sepeda", "cycling", "gowes", "motor", "motoran", "touring",
    "otomotif", "kopi", "coffee", "barista", "fotografi", "photography", "hiking", "gunung",
    "backpacker", "traveler", "kuliner", "makanan", "buku", "literasi",
    # Teknologi & Bisnis
    "programming", "developer", "coding", "python", "javascript", "golang", "flutter",
    "devops", "cloud", "data science", "ai", "artificial intelligence", "cybersecurity",
    "startup", "umkm", "bisnis", "investasi", "saham", "crypto", "marketing", "digital marketing",
    # Edukasi, Anak & Keluarga
    "parenting", "ibu", "anak", "edukasi", "pendidikan", "beasiswa", "mahasiswa", "pelajar",
    # Seni & Kreatif
    "desain", "design", "ui ux", "animasi", "film", "musik", "teater", "tari",
]

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]+)", re.I),
    "facebook_group": re.compile(r"https?://(?:www\.|web\.|m\.)?facebook\.com/groups/([A-Za-z0-9_.\-]+)", re.I),
    "facebook_page": re.compile(r"https?://(?:www\.|web\.|m\.)?facebook\.com/([A-Za-z0-9_.\-]+)", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]+)", re.I),
    "threads": re.compile(r"https?://(?:www\.)?threads\.net/@([A-Za-z0-9_.]+)", re.I),
    "linkedin": re.compile(r"https?://(?:[a-z]{2}\.)?linkedin\.com/(?:company|school)/([A-Za-z0-9\-_%]+)", re.I),
    "linktree": re.compile(r"https?://(?:www\.)?(?:linktr\.ee|campsite\.bio|taplink\.cc|biolinky\.co)/([A-Za-z0-9_.\-]+)", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/@([A-Za-z0-9_.\-]+)", re.I),
    "website": re.compile(r"https?://(?:www\.)?([A-Za-z0-9\-]+\.(?:org|id|com|net|io|co\.id|or\.id))(?:/[^\s]*)?", re.I),
}

RESERVED = {
    "p", "reel", "reels", "explore", "stories", "tv", "accounts", "about", "privacy",
    "help", "legal", "developer", "directory", "share", "profile.php", "pages",
    "watch", "events", "marketplace", "hashtag", "story", "i", "home",
    "search", "login", "signup", "policies", "terms", "settings", "notifications",
    "intent", "status", "people", "photo", "media", "tag", "discover",
}


# --------------------------------------------------------------------------- search engine

class SearchEngine:
    """Cache-first search engine."""

    def __init__(self, cache_path: Path | None, live: bool, delay: float):
        self.cache_path = cache_path
        self.live = live
        self.delay = delay
        self.cache: dict[str, list] = {}
        self.missing: list[str] = []
        if cache_path and cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[warn] cache unreadable ({e}); starting empty", file=sys.stderr)

    def search(self, query: str) -> list[tuple[str, str]]:
        if query in self.cache:
            return [(u, t) for u, t in self.cache[query]]
        if query not in self.missing:
            self.missing.append(query)
        if not self.live:
            return []
        res = self._ddg(query)
        if res:
            self.cache[query] = [list(x) for x in res]
            self._flush()
        time.sleep(self.delay)
        return res

    def _flush(self) -> None:
        if self.cache_path:
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")

    def _ddg(self, query: str, retries: int = 2) -> list[tuple[str, str]]:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
                body = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
                if "result__a" not in body:
                    time.sleep(5 + attempt * 5)
                    continue
                out = []
                for m in re.finditer(
                        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                        body, re.S):
                    href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
                    if "uddg=" in href:
                        uddg_m = re.search(r"uddg=([^&]+)", href)
                        href = urllib.parse.unquote(uddg_m.group(1)) if uddg_m else href
                    out.append((href, html.unescape(title).strip()))
                return out
            except Exception:
                time.sleep(3 + attempt * 3)
        return []


# --------------------------------------------------------------------------- analyzers

def extract_community_socials(results: list[tuple[str, str]], comm_name: str) -> dict[str, dict]:
    """Extract social links dedicated to the community itself."""
    tally: dict[str, dict] = {}
    comm_clean = re.sub(r"[^a-zA-Z0-9]+", "", comm_name.lower())

    for url, title in results:
        for platform, pat in SOCIAL_PATTERNS.items():
            m = pat.search(url)
            if not m:
                continue
            handle = m.group(1).strip("/").lower()
            if not handle or handle in RESERVED or handle.startswith("profile.php"):
                continue

            # Follower / Member signal
            sig = []
            f_match = re.search(r"([\d.,]+[KkMm]?\+?\s*(?:followers?|members?|pengikut|anggota))", title, re.I)
            if f_match:
                sig.append(f_match.group(1).strip())

            # Specificity match with community name
            score = 1.0
            handle_clean = re.sub(r"[^a-zA-Z0-9]+", "", handle)
            if comm_clean in handle_clean or handle_clean in comm_clean:
                score += 1.5
            if comm_name.lower() in title.lower():
                score += 1.0

            if platform not in tally or score > tally[platform]["score"]:
                tally[platform] = {
                    "handle": handle,
                    "url": url,
                    "title": title,
                    "score": score,
                    "signals": sig
                }

    return tally


def detect_community_region(texts: list[str]) -> str:
    """Identify the geographic region / city of the community."""
    scores: dict[str, int] = {}
    combined = " ".join(texts)

    for region in INDONESIAN_REGIONS:
        # Match word boundary
        pattern = re.compile(rf"\b{re.escape(region)}\b", re.I)
        matches = pattern.findall(combined)
        if matches:
            weight = len(matches)
            # Give higher priority to specific cities over broad 'Indonesia'
            if region.lower() in ("indonesia", "nasional"):
                weight = 1
            scores[region] = scores.get(region, 0) + weight

    if not scores:
        return "Indonesia (Cakupan Nasional)"

    # Pick the highest ranked specific region
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], -len(kv[0])))
    top_region, top_score = ranked[0]
    return top_region


def extract_community_niche(name: str, desc: str) -> list[str]:
    """Extract key themes/niches from community name and description."""
    combined = (name + " " + desc).lower()
    found = []
    for kw in COMMUNITY_NICHE_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", combined, re.I):
            found.append(kw)
    return found[:4]


def extract_other_pic_communities(results: list[tuple[str, str]], pic_name: str, current_comm: str) -> list[str]:
    """Find other projects, NGOs, foundations, and communities initiated/managed by the PIC."""
    discovered = []
    seen = set()
    current_clean = re.sub(r"[^a-zA-Z0-9]+", "", current_comm.lower())

    org_pattern = re.compile(
        r"\b(?:Founder|Co-Founder|Inisiator|Ketua|Leader|Presiden|Pimpinan|CEO|Owner|Direktur|Aktivis|Penggagas)\s+(?:of\s+|di\s+|dari\s+)?([A-Z][\w&'\-]*(?:\s+[A-Z0-9][\w&'\-]*){1,4})\b",
        re.I
    )

    for url, title in results:
        # Extract from title/snippet
        for m in org_pattern.finditer(title):
            org_name = m.group(1).strip(" -–—|·,:")
            org_clean = re.sub(r"[^a-zA-Z0-9]+", "", org_name.lower())
            if not org_name or len(org_name) < 4:
                continue
            # Skip if it is the current community itself
            if current_clean and (current_clean in org_clean or org_clean in current_clean):
                continue
            if org_name.lower() not in seen:
                seen.add(org_name.lower())
                discovered.append(org_name)

    return discovered[:5]


def extract_similar_communities(results: list[tuple[str, str]], current_comm: str) -> list[str]:
    """Extract names of peer/similar communities in the region."""
    discovered = []
    seen = set()
    current_clean = re.sub(r"[^a-zA-Z0-9]+", "", current_comm.lower())

    # Patterns matching community names: e.g. "Komunitas Peduli Sampah", "Jakarta Running Club"
    comm_pat = re.compile(
        r"\b((?:Komunitas|Grup|Forum|Yayasan|Perkumpulan|Paguyuban|Club|Community|Society|Movement|Alliance)\s+[A-Z][\w&'\-]*(?:\s+[A-Z0-9][\w&'\-]*){1,3})\b",
        re.I
    )
    comm_pat_en = re.compile(
        r"\b([A-Z][\w&'\-]*(?:\s+[A-Z0-9][\w&'\-]*){1,3}\s+(?:Community|Club|Group|Forum|Movement|Foundation|Network))\b",
        re.I
    )

    for url, title in results:
        for p in (comm_pat, comm_pat_en):
            for m in p.finditer(title):
                cand = m.group(1).strip(" -–—|·,:")
                cand_clean = re.sub(r"[^a-zA-Z0-9]+", "", cand.lower())
                if len(cand) < 5 or cand.lower() in seen:
                    continue
                if current_clean and (current_clean in cand_clean or cand_clean in current_clean):
                    continue
                seen.add(cand.lower())
                discovered.append(cand)

    return discovered[:5]


# --------------------------------------------------------------------------- query generators

def generate_community_queries(comm_name: str, region: str = "") -> list[str]:
    """Generate search queries to find the community's official social media presence."""
    qs = []
    seen = set()

    def add(q: str):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            qs.append(q)

    add(f'"{comm_name}" site:instagram.com OR site:tiktok.com OR site:facebook.com')
    add(f'"{comm_name}" site:linktr.ee OR site:campsite.bio OR site:taplink.cc')
    add(f'"{comm_name}" instagram')
    add(f'"{comm_name}" facebook group OR "grup facebook"')
    if region:
        add(f'"{comm_name}" {region} instagram')

    return qs


def generate_pic_other_comm_queries(pic_name: str, current_comm: str) -> list[str]:
    """Generate search queries to track other communities founded/managed by the PIC."""
    qs = []
    seen = set()

    def add(q: str):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            qs.append(q)

    if pic_name:
        add(f'"{pic_name}" (founder OR inisiator OR ketua OR leader OR pimpinan OR penggagas) -"{current_comm}"')
        add(f'"{pic_name}" (komunitas OR yayasan OR project OR "movement" OR perkumpulan) -"{current_comm}"')
        add(f'"{pic_name}" site:linkedin.com/in')

    return qs


def generate_peer_comm_queries(niches: list[str], region: str) -> list[str]:
    """Generate search queries to discover peer/similar communities in the region."""
    qs = []
    seen = set()

    def add(q: str):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            qs.append(q)

    clean_region = region if region and not region.startswith("Indonesia") else "Indonesia"
    for n in niches[:2]:
        add(f'komunitas "{n}" {clean_region} site:instagram.com OR site:facebook.com')
        add(f'daftar komunitas {n} {clean_region}')

    return qs


# --------------------------------------------------------------------------- tools

def run_holehe(email: str, timeout: int = 150) -> dict[str, list[str]]:
    try:
        proc = subprocess.run(["holehe", email], capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return {"used": [], "rate": [], "error": [f"{type(e).__name__}: {e}"]}
    used, rate = [], []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("[+]") and "." in line:
            used.append(line[3:].strip())
        elif line.startswith("[x]") and "." in line:
            rate.append(line[3:].strip())
    return {"used": used, "rate": rate, "error": []}


# --------------------------------------------------------------------------- io

def normalize_community_headers(headers: list[str]) -> dict[str, int]:
    idx = {}
    for i, h in enumerate(headers):
        key = (h or "").strip().lower()
        if any(k in key for k in ("pic", "pengurus", "ketua", "founder", "leader", "penanggung jawab")):
            if any(e in key for e in ("email", "mail")):
                idx["pic_email"] = i
            elif any(p in key for p in ("nomor", "no", "hp", "phone", "telepon", "wa")):
                idx["pic_phone"] = i
            else:
                idx["pic_name"] = i
        elif any(k in key for k in ("email", "mail", "e-mail")):
            idx["pic_email"] = i
        elif any(k in key for k in ("nomor", "no hp", "nohp", "phone", "telepon", "wa", "whatsapp")):
            idx["pic_phone"] = i
        elif any(k in key for k in ("deskripsi", "description", "kegiatan", "tentang", "about")):
            idx["description"] = i
        elif any(k in key for k in ("nama komunitas", "nama", "komunitas", "community", "nama group", "nama grup", "organisasi")):
            idx["community_name"] = i
    return idx


def load_rows(path: Path, sheet: str | None):
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        ws = wb[sheet] if sheet else (wb.active or wb.create_sheet())
        rows = [[(c if c is not None else "") for c in r]
                for r in ws.iter_rows(values_only=True)]
        return rows[0], rows[1:]
    import csv
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def main() -> int:
    ap = argparse.ArgumentParser(description="Community OSINT & PIC Multi-Community Mapping")
    ap.add_argument("input", help="Input file (.xlsx or .csv)")
    ap.add_argument("--sheet", default=None, help="Sheet name for Excel file")
    ap.add_argument("--search-cache", default=None, help="Path to JSON search cache")
    ap.add_argument("--dump-queries", default=None, help="Dump missing queries to JSON for batch retrieval")
    ap.add_argument("--no-live-search", action="store_true", help="Disable live DuckDuckGo/Google search")
    ap.add_argument("--skip-holehe", action="store_true", help="Skip email registration check for PIC")
    ap.add_argument("--delay", type=float, default=4.0, help="Delay between search requests in seconds")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of rows processed")
    args = ap.parse_args()

    src = Path(args.input).expanduser()
    if not src.exists():
        print(f"Input not found: {src}", file=sys.stderr)
        return 1

    headers, rows = load_rows(src, args.sheet)
    headers = [str(h) for h in headers]
    idx = normalize_community_headers(headers)

    if "community_name" not in idx:
        print(f"Header 'Nama Komunitas' tidak ditemukan di: {headers}", file=sys.stderr)
        return 1

    if args.limit:
        rows = rows[: args.limit]

    eng = SearchEngine(Path(args.search_cache) if args.search_cache else None,
                       live=not args.no_live_search, delay=args.delay)

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active or wb.create_sheet()
    ws.title = "community_osint_result"

    out_headers = headers + (
        [] if "community intelligence" in [h.lower() for h in headers] else ["Community Intelligence"]
    )
    ws.append(out_headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    col_intel_idx = len(out_headers) - 1

    for n, row in enumerate(rows, 1):
        row = list(row) + [""] * (len(headers) - len(row))
        comm_name = str(row[idx["community_name"]]).strip() if "community_name" in idx else ""
        desc = str(row[idx["description"]]).strip() if "description" in idx else ""
        pic_name = str(row[idx["pic_name"]]).strip() if "pic_name" in idx else ""
        pic_email = str(row[idx["pic_email"]]).strip() if "pic_email" in idx else ""
        pic_phone = str(row[idx["pic_phone"]]).strip() if "pic_phone" in idx else ""

        if not comm_name:
            continue

        print(f"\n[{n}/{len(rows)}] 🏢 Memproses Komunitas: {comm_name} (PIC: {pic_name or '-'})", flush=True)

        # -------------------------------------------------------------
        # STEP 1: Holehe on PIC Email (Optional Context)
        # -------------------------------------------------------------
        holehe = {"used": []}
        if pic_email and not args.skip_holehe:
            print(f"  [Step 1] Cek Email PIC ({pic_email})...", flush=True)
            holehe = run_holehe(pic_email)
            print(f"           Terdaftar di: {', '.join(holehe.get('used', [])) or '-'}", flush=True)

        # -------------------------------------------------------------
        # STEP 2: Community Official Socials Discovery
        # -------------------------------------------------------------
        comm_queries = generate_community_queries(comm_name)
        print(f"  [Step 2] Mencari Sosmed Resmi Komunitas ({len(comm_queries)} query)...", flush=True)
        comm_results = []
        for q in comm_queries:
            print(f"           -> Q: {q}", flush=True)
            comm_results += eng.search(q)

        socials = extract_community_socials(comm_results, comm_name)

        # -------------------------------------------------------------
        # STEP 3: Detect Community Geographic Region
        # -------------------------------------------------------------
        all_snippets = [t for _, t in comm_results] + [desc, comm_name]
        detected_region = detect_community_region(all_snippets)
        print(f"  [Step 3] Wilayah/Daerah Komunitas: {detected_region}", flush=True)

        # -------------------------------------------------------------
        # STEP 4: PIC Other Communities / Multi-organization Mapping
        # -------------------------------------------------------------
        pic_other_comms = []
        if pic_name:
            pic_queries = generate_pic_other_comm_queries(pic_name, comm_name)
            print(f"  [Step 4] Melacak Komunitas Lain yang Dikelola PIC ({len(pic_queries)} query)...", flush=True)
            pic_results = []
            for q in pic_queries:
                print(f"           -> Q: {q}", flush=True)
                pic_results += eng.search(q)
            pic_other_comms = extract_other_pic_communities(pic_results, pic_name, comm_name)
            print(f"           Komunitas Lain PIC: {', '.join(pic_other_comms) if pic_other_comms else '-'}", flush=True)

        # -------------------------------------------------------------
        # STEP 5: Peer / Similar Communities in the Same Region
        # -------------------------------------------------------------
        niches = extract_community_niche(comm_name, desc)
        similar_comms = []
        if niches:
            peer_queries = generate_peer_comm_queries(niches, detected_region)
            print(f"  [Step 5] Mencari Komunitas Sejenis di {detected_region} (Niche: {', '.join(niches)})...", flush=True)
            peer_results = []
            for q in peer_queries:
                print(f"           -> Q: {q}", flush=True)
                peer_results += eng.search(q)
            similar_comms = extract_similar_communities(peer_results, comm_name)
            print(f"           Komunitas Sejenis: {', '.join(similar_comms) if similar_comms else '-'}", flush=True)

        # -------------------------------------------------------------
        # STEP 6: Compose Community Intelligence Summary Notes
        # -------------------------------------------------------------
        lines: list[str] = []

        # 1. Official Community Social Media
        comm_socmed_list = []
        for plat, label in (
            ("instagram", "IG"), ("facebook_group", "FB Group"), ("facebook_page", "FB Page"),
            ("tiktok", "TikTok"), ("threads", "Threads"), ("linktree", "Linktree/Biolink"),
            ("website", "Web Resmi"), ("linkedin", "LinkedIn")
        ):
            if plat in socials:
                d = socials[plat]
                sig_str = f" ({', '.join(d['signals'])})" if d.get("signals") else ""
                comm_socmed_list.append(f"{label}: {d['url']}{sig_str}")

        lines.append("Sosmed Komunitas: " + ("; ".join(comm_socmed_list) if comm_socmed_list else "belum ditemukan publik"))

        # 2. Region / Coverage Area
        lines.append(f"Daerah / Wilayah: {detected_region}")

        # 3. Other Communities Managed by the Same PIC
        if pic_other_comms:
            lines.append("Komunitas Lain Kelolaan PIC: " + ", ".join(pic_other_comms))
        else:
            lines.append("Komunitas Lain Kelolaan PIC: Tidak terdeteksi / hanya komunitas ini")

        # 4. Similar / Peer Communities in Region
        if similar_comms:
            lines.append(f"Komunitas Sejenis di {detected_region}: " + ", ".join(similar_comms))
        else:
            lines.append(f"Komunitas Sejenis di {detected_region}: Belum terdeteksi di direktori publik")

        # 5. PIC Contact & Verification
        pic_details = []
        if pic_name:
            pic_details.append(f"Nama: {pic_name}")
        if pic_phone:
            pic_details.append(f"No HP/WA: {pic_phone}")
        if pic_email:
            pic_details.append(f"Email: {pic_email}")
            if holehe.get("used"):
                pic_details.append(f"Platform Aktif: {', '.join(h.replace('.com', '') for h in holehe['used'])}")

        if pic_details:
            lines.append("Profil PIC: " + " | ".join(pic_details))

        intel_note = "\n".join(lines)

        out_row = [""] * len(out_headers)
        for i, v in enumerate(row):
            out_row[i] = str(v)
        out_row[col_intel_idx] = intel_note
        ws.append(out_row)

    # Format Excel width & alignment
    for i, h in enumerate(out_headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = 90 if i - 1 == col_intel_idx else 25
    for r in ws.iter_rows(min_row=2):
        for c in r:
            c.alignment = Alignment(vertical="top", wrap_text=True)

    dest = src.with_name(src.stem + "_result.xlsx")
    wb.save(dest)
    print(f"\n✅ Hasil investigasi komunitas selesai disimpan ke: {dest}")

    if eng.missing:
        print(f"[cache] {len(eng.missing)} query belum ada di cache")
        if args.dump_queries:
            Path(args.dump_queries).write_text(
                json.dumps(eng.missing, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[cache] Daftar query berhasil ditulis ke {args.dump_queries}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
