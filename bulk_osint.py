#!/usr/bin/env python3
"""Bulk OSINT lookup from XLSX/CSV -> writes <name>_result.xlsx with a Notes column.

New Pipeline Flow:
  1. Email check first (Holehe) -> detects verified registered platforms (IG, FB, Twitter, Spotify, dll).
  2. Targeted multi-step Google search -> prioritize search queries based on platforms proven in Step 1:
     - General: "{name}"
     - Targeted: "{name}" instagram, "{name}" site:instagram.com, "{name}" facebook, dst.
     - Secondary: search other major platforms.
  3. Community probe on the strongest handle + name -> where they are active.
  4. Maigret on candidate usernames (optional, --maigret).
  5. Consolidated Notes generation with cross-verification score.

Two-pass usage with the cache (recommended):
  pass 1: python3 bulk_osint.py IN.xlsx --search-cache c.json --dump-queries q.json
          -> agent prefetches the queries in q.json into c.json
  pass 2: same command again -> all cache hits -> writes IN_result.xlsx

Usage:
  python3 bulk_osint.py INPUT.xlsx [--sheet S] [--search-cache c.json]
      [--dump-queries q.json] [--no-live-search] [--maigret] [--delay 4] [--limit N]
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

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]+)", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]+)", re.I),
    "facebook": re.compile(r"https?://(?:www\.|web\.)?facebook\.com/([A-Za-z0-9_.\-]+)", re.I),
    "linkedin": re.compile(r"https?://(?:[a-z]{2}\.)?linkedin\.com/in/([A-Za-z0-9\-_%]+)", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?youtube\.com/@([A-Za-z0-9_.\-]+)", re.I),
    "github": re.compile(r"https?://(?:www\.)?github\.com/([A-Za-z0-9\-]+)/?$", re.I),
    "pinterest": re.compile(r"https?://(?:www\.)?pinterest\.(?:com|[a-z]{2})/([A-Za-z0-9_.\-]+)", re.I),
    "spotify": re.compile(r"https?://open\.spotify\.com/user/([A-Za-z0-9_.\-]+)", re.I),
}

RESERVED = {
    "p", "reel", "reels", "explore", "stories", "tv", "accounts", "about", "privacy",
    "help", "legal", "developer", "directory", "share", "profile.php", "pages",
    "watch", "groups", "events", "marketplace", "hashtag", "story", "i", "home",
    "search", "login", "signup", "policies", "terms", "settings", "notifications",
    "intent", "status", "hashtag", "people", "photo", "media", "tag", "discover",
}

# Mapping holehe detected services to platform keys and search terms
HOLEHE_PLATFORM_MAP = {
    "instagram": ("instagram", "instagram", "site:instagram.com", "IG"),
    "instagram.com": ("instagram", "instagram", "site:instagram.com", "IG"),
    "facebook": ("facebook", "facebook", "site:facebook.com", "FB"),
    "facebook.com": ("facebook", "facebook", "site:facebook.com", "FB"),
    "twitter": ("twitter", "twitter", "site:twitter.com OR site:x.com", "X"),
    "twitter.com": ("twitter", "twitter", "site:twitter.com OR site:x.com", "X"),
    "x.com": ("twitter", "twitter", "site:twitter.com OR site:x.com", "X"),
    "tiktok": ("tiktok", "tiktok", "site:tiktok.com", "TikTok"),
    "tiktok.com": ("tiktok", "tiktok", "site:tiktok.com", "TikTok"),
    "linkedin": ("linkedin", "linkedin", "site:linkedin.com", "LinkedIn"),
    "linkedin.com": ("linkedin", "linkedin", "site:linkedin.com", "LinkedIn"),
    "github": ("github", "github", "site:github.com", "GitHub"),
    "github.com": ("github", "github", "site:github.com", "GitHub"),
    "pinterest": ("pinterest", "pinterest", "site:pinterest.com", "Pinterest"),
    "pinterest.com": ("pinterest", "pinterest", "site:pinterest.com", "Pinterest"),
    "spotify": ("spotify", "spotify", "site:open.spotify.com/user", "Spotify"),
    "spotify.com": ("spotify", "spotify", "site:open.spotify.com/user", "Spotify"),
}

# Domains already reported as primary socials -> excluded from the community column.
PRIMARY_SOCIAL_DOMAINS = (
    "instagram.com", "tiktok.com", "facebook.com", "twitter.com", "x.com",
    "pinterest.com", "spotify.com",
)

# Domains whose *name* is itself the community/organisation.
ORG_DOMAINS = {
    "greenheart.org": "Greenheart International",
    "tigweb.org": "TakingITGlobal",
    "ifixit.com": "iFixit",
    "meetup.com": "Meetup",
    "eventbrite.com": "Eventbrite",
    "devpost.com": "Devpost",
    "behance.net": "Behance",
    "dribbble.com": "Dribbble",
    "goodreads.com": "Goodreads",
    "wattpad.com": "Wattpad",
    "stackoverflow.com": "Stack Overflow",
    "github.com": "GitHub",
    "reddit.com": "Reddit",
    "dev.to": "DEV Community",
    "kompasiana.com": "Kompasiana",
    "researchgate.net": "ResearchGate",
    "academia.edu": "Academia.edu",
    "medium.com": "Medium",
    "substack.com": "Substack",
}

# News/press: they *mention* the person but are not a community they belong to.
NEWS_DOMAINS = (
    "kompas.com", "mediaindonesia.com", "detik.com", "tribunnews.com",
    "liputan6.com", "cnnindonesia.com", "tempo.co", "republika.co.id",
    "youngster.id", "suara.com", "okezone.com", "kumparan.com", "idntimes.com",
    "antaranews.com", "bisnis.com", "viva.co.id", "merdeka.com", "goodkind.id",
)

# Library catalogues / thesis repositories: almost always a different person
ACADEMIC_NOISE = (
    "perpusnas.go.id", "garuda.kemdiktisaintek.go.id", "eprints.", "etd.",
    "repository.", "pustaka.", "opac.", ".sch.id", "digilib.", "lib.",
    "journal.", "jurnal.", "neliti.com", "leutikaprio.com",
)

# Words that signal a candidate phrase is an organisation / programme.
ORG_KEYWORDS = {
    "project", "international", "foundation", "community", "club", "program",
    "programme", "initiative", "institute", "association", "network", "society",
    "movement", "forum", "center", "centre", "academy", "alliance", "coalition",
    "council", "union", "chapter", "collective", "organization", "organisation",
    "volunteers", "corps", "fellowship", "committee", "komunitas", "yayasan",
    "perkumpulan", "paguyuban", "relawan", "lembaga", "grant", "award",
}

# Generic title words that must never become a "community" name.
PHRASE_STOPWORDS = {
    "page", "archives", "profile", "member", "pdf", "read", "news", "video",
    "videos", "photos", "instagram", "facebook", "youtube", "linkedin", "tiktok",
    "twitter", "home", "search", "results", "winners", "winner", "daftar",
    "profil", "biodata", "the", "and", "with", "from", "for", "her", "his",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "empowering", "those",
}


# --------------------------------------------------------------------------- search

class SearchEngine:
    """Cache-first search. Records misses so the agent can prefetch them."""

    def __init__(self, cache_path: Path | None, live: bool, delay: float):
        self.cache_path = cache_path
        self.live = live
        self.delay = delay
        self.cache: dict[str, list] = {}
        self.missing: list[str] = []
        if cache_path and cache_path.exists():
            try:
                self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
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
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1),
                                       encoding="utf-8")

    def _ddg(self, query: str, retries: int = 2) -> list[tuple[str, str]]:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
                body = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
                if "result__a" not in body:
                    time.sleep(5 + attempt * 5)   # anomaly/rate-limit page
                    continue
                out = []
                for m in re.finditer(
                        r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                        body, re.S):
                    href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
                    if "uddg=" in href:
                        href = urllib.parse.unquote(re.search(r"uddg=([^&]+)", href).group(1))
                    out.append((href, html.unescape(title).strip()))
                return out
            except Exception:  # noqa: BLE001
                time.sleep(3 + attempt * 3)
        return []


def name_tokens(name: str) -> list[str]:
    """Meaningful lowercase tokens of the target name (>=3 chars)."""
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if len(t) >= 3]


def match_score(name: str, handle: str, title: str, is_holehe_verified: bool = False) -> float:
    """How strongly a candidate profile matches the target name.

    Scoring:
      2.0  every name token appears in the result title (strongest)
      1.0  every name token appears inside the handle
      +0.3 the full name appears as a contiguous string in the title
      +0.5 platform confirmed registered via Holehe for this email
    Below 1.0 the candidate is rejected as a probable different person.
    """
    toks = name_tokens(name)
    if not toks:
        return 0.0
    tl = title.lower().replace(handle.lower(), " ")
    tl = re.sub(re.escape(handle.lower().replace(".", " ")), " ", tl)
    hl = handle.lower()
    score = 0.0
    if all(t in tl for t in toks):
        score += 2.0
    if all(t in hl for t in toks):
        score += 1.0
    if re.sub(r"[^a-z0-9]+", " ", name.lower()).strip() in re.sub(r"[^a-z0-9]+", " ", tl):
        score += 0.3
    # partial credit only when the rare (longest) token matches
    if score == 0.0:
        longest = max(toks, key=len)
        if len(longest) >= 6 and (longest in tl or longest in hl):
            score += 0.6

    # Bonus confidence if the platform is proven registered for the target email
    if is_holehe_verified and score >= 1.0:
        score += 0.5

    return score


def extract_socials(results: list[tuple[str, str]], name: str = "",
                    threshold: float = 1.0,
                    verified_platforms: list[str] | None = None) -> dict[str, dict]:
    """platform -> {handle, url, title, score}, choosing the best NAME match."""
    v_set = set()
    if verified_platforms:
        for vp in verified_platforms:
            k = vp.lower().replace(".com", "").strip()
            v_set.add(k)

    tally: dict[str, dict[str, dict]] = {}
    for url, title in results:
        for platform, pat in SOCIAL_PATTERNS.items():
            m = pat.search(url)
            if not m:
                continue
            handle = m.group(1).strip("/").lower()
            if not handle or handle in RESERVED or handle.startswith("profile.php"):
                continue
            entry = tally.setdefault(platform, {}).setdefault(
                handle, {"count": 0, "url": url, "title": title, "score": 0.0})
            entry["count"] += 1
            if title and not entry["title"]:
                entry["title"] = title
            if name:
                is_v = platform in v_set
                entry["score"] = max(entry["score"], match_score(name, handle, title, is_holehe_verified=is_v))

    out: dict[str, dict] = {}
    for platform, handles in tally.items():
        if name:
            ranked = sorted(handles.items(),
                            key=lambda kv: (-kv[1]["score"], -kv[1]["count"]))
            handle, data = ranked[0]
            if data["score"] < threshold:
                continue
            tied = [h for h, d in ranked if d["score"] == data["score"]]
            alts = tied[1:]
        else:
            handle, data = max(handles.items(), key=lambda kv: kv[1]["count"])
            alts = []
        canonical = {
            "instagram": f"https://www.instagram.com/{handle}/",
            "tiktok": f"https://www.tiktok.com/@{handle}",
            "twitter": f"https://x.com/{handle}",
            "facebook": f"https://www.facebook.com/{handle}",
            "linkedin": f"https://www.linkedin.com/in/{handle}",
            "youtube": f"https://www.youtube.com/@{handle}",
            "github": f"https://github.com/{handle}",
            "pinterest": f"https://www.pinterest.com/{handle}",
            "spotify": f"https://open.spotify.com/user/{handle}",
        }.get(platform, data["url"])
        out[platform] = {"handle": handle, "url": canonical,
                         "title": data["title"], "score": round(data["score"], 2),
                         "hits": data["count"], "alts": alts,
                         "email_verified": platform in v_set}
    return out


PLATFORM_TERMS = [
    ("instagram", "instagram"),
    ("tiktok", "tiktok"),
    ("twitter", "twitter"),
    ("facebook", "facebook"),
    ("linkedin", "linkedin"),
    ("github", "github"),
]


def targeted_social_queries(name: str, verified_platforms: list[str] | None = None,
                            all_platforms: list[str] | None = None) -> list[str]:
    """Generate search queries:
    1. Base name search
    2. Prioritized queries for platforms verified in Holehe (e.g. name + IG, name + FB)
    3. Secondary queries for other major social platforms
    """
    qs = []
    seen = set()

    def add_q(q: str):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            qs.append(q)

    # 1. Base query with full name
    add_q(f'"{name}"')

    # 2. Targeted queries based on Holehe email verification results
    if verified_platforms:
        for vp in verified_platforms:
            v_clean = vp.lower().strip()
            if v_clean in HOLEHE_PLATFORM_MAP:
                plat_key, query_term, site_filter, _ = HOLEHE_PLATFORM_MAP[v_clean]
                add_q(f'"{name}" {query_term}')
                add_q(f'"{name}" {site_filter}')
            else:
                # Other services (e.g. behance.net, medium.com)
                short_name = v_clean.split(".")[0]
                if short_name and short_name not in ("com", "org", "net"):
                    add_q(f'"{name}" {short_name}')
                    add_q(f'"{name}" site:{v_clean}')

    # 3. Standard queries for remaining major platforms
    wanted = all_platforms or [p for p, _ in PLATFORM_TERMS]
    for plat, term in PLATFORM_TERMS:
        if plat in wanted:
            add_q(f'"{name}" {term}')

    return qs


def community_queries(name: str, handle: str | None) -> list[str]:
    qs = []
    if handle:
        qs.append(f'"{handle}"')
    if name:
        qs.append(f'"{name}" (komunitas OR community OR forum OR volunteer OR speaker '
                  f'OR organisasi OR program)')
    return qs


def _clean_title(title: str) -> str:
    t = re.sub(r"\s*[\|\-–—]\s*[^|\-–—]{0,40}$", "", title).strip()
    return t or title.strip()


def org_phrases(title: str, name: str) -> list[str]:
    out: list[str] = []
    ntoks = set(name_tokens(name))
    text = _clean_title(title)
    text = re.sub(r"[\"'’‘“”]", "", text)

    joiner = r"(?:of|for|the|on|and|in|de|di|dan|untuk)"
    pattern = re.compile(
        rf"\b([A-Z][\w&']*(?:\s+(?:{joiner}\s+)?[A-Z][\w&']*)+)\b")

    for m in pattern.finditer(text):
        phrase = m.group(1).strip()
        phrase = re.sub(r"^(?:Profil|Profile|Biodata|Melalui|Dari)\s+", "", phrase)
        phrase = re.sub(r"'s$", "", phrase).strip()
        words = [w.lower().removesuffix("'s") for w in phrase.split()]
        if len(words) < 2 or len(phrase) < 6:
            continue
        if ntoks and set(words) <= ntoks:
            continue
        if any(w in PHRASE_STOPWORDS for w in words):
            if not any(w in ORG_KEYWORDS for w in words):
                continue
        has_kw = any(w in ORG_KEYWORDS for w in words)
        clean_proper = len(words) <= 4 and not (ntoks & set(words))
        if has_kw or clean_proper:
            out.append(phrase)
    return out


def community_from_results(results: list[tuple[str, str]], name: str = "") -> list[str]:
    scored: dict[str, int] = {}

    def add(label: str, weight: int) -> None:
        label = label.strip(" -–—|·,")
        if len(label) < 3:
            return
        for existing in list(scored):
            if existing.lower() == label.lower():
                scored[existing] += weight
                return
            if label.lower() in existing.lower():
                scored[existing] += weight
                return
            if existing.lower() in label.lower():
                scored[label] = scored.pop(existing) + weight
                return
        scored[label] = weight

    for url, title in results:
        low = url.lower()
        if any(d in low for d in PRIMARY_SOCIAL_DOMAINS):
            continue
        if any(d in low for d in ACADEMIC_NOISE):
            continue

        is_news = any(d in low for d in NEWS_DOMAINS)

        if is_news and name:
            tl = title.lower()
            if not all(t in tl for t in name_tokens(name)):
                continue

        if re.search(r"/(tagged|tag|category|archives?|page)/", low):
            continue

        for dom, label in ORG_DOMAINS.items():
            if dom in low:
                add(label, 3)
                break

        for phrase in org_phrases(title, name):
            add(phrase, 2 if is_news else 3)

    ranked = sorted(scored.items(), key=lambda kv: -kv[1])
    return [label for label, _ in ranked[:6]]


# --------------------------------------------------------------------------- tools

def run_holehe(email: str, timeout: int = 200) -> dict[str, list[str]]:
    try:
        proc = subprocess.run(["holehe", email], capture_output=True, text=True, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        return {"used": [], "rate": [], "error": [f"{type(e).__name__}: {e}"]}
    used, rate = [], []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("[+]") and "." in line:
            used.append(line[3:].strip())
        elif line.startswith("[x]") and "." in line:
            rate.append(line[3:].strip())
    return {"used": used, "rate": rate, "error": []}


def run_maigret(username: str, timeout: int = 300) -> list[tuple[str, str]]:
    try:
        proc = subprocess.run(
            ["maigret", username, "--timeout", "12", "-P", "--no-color",
             "--no-progressbar", "--no-recursion", "--no-extracting"],
            capture_output=True, text=True, timeout=timeout)
    except Exception:  # noqa: BLE001
        return []
    return re.findall(r"\[\+\]\s+([^:]+):\s+(https?://\S+)", proc.stdout)[:12]


def candidate_usernames(name: str, email: str) -> list[str]:
    cands = []
    if email and "@" in email:
        cands.append(email.split("@")[0].lower())
    if name:
        parts = [p for p in re.split(r"\s+", name.strip().lower()) if p]
        if parts:
            cands.append("".join(parts))
            if len(parts) > 1:
                cands.append(".".join(parts))
    seen, out = set(), []
    for c in cands:
        c = re.sub(r"[^a-z0-9._]", "", c)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out[:3]


# --------------------------------------------------------------------------- io

def normalize_headers(headers: list[str]) -> dict[str, int]:
    idx = {}
    for i, h in enumerate(headers):
        key = (h or "").strip().lower()
        if key in ("nama", "name", "full name", "nama lengkap"):
            idx["name"] = i
        elif key in ("nomor", "no hp", "nohp", "phone", "telepon", "no_telp", "hp", "nomor hp"):
            idx["phone"] = i
        elif key in ("email", "e-mail", "mail", "alamat email"):
            idx["email"] = i
    return idx


def load_rows(path: Path, sheet: str | None):
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        ws = wb[sheet] if sheet else wb.active
        rows = [[(c if c is not None else "") for c in r]
                for r in ws.iter_rows(values_only=True)]
        return rows[0], rows[1:]
    import csv
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def main() -> int:
    ap = argparse.ArgumentParser(description="Bulk OSINT person lookup from Excel/CSV")
    ap.add_argument("input", help="Input file (.xlsx or .csv)")
    ap.add_argument("--sheet", default=None, help="Sheet name for Excel file")
    ap.add_argument("--search-cache", default=None, help="Path to JSON search cache")
    ap.add_argument("--dump-queries", default=None, help="Dump missing queries to JSON for batch retrieval")
    ap.add_argument("--no-live-search", action="store_true", help="Disable live DuckDuckGo/Google search")
    ap.add_argument("--maigret", action="store_true", help="Run Maigret username search (slower)")
    ap.add_argument("--skip-holehe", action="store_true", help="Skip email registration check (Holehe)")
    ap.add_argument("--delay", type=float, default=4.0, help="Delay between search requests in seconds")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of rows processed")
    ap.add_argument("--platforms", default="",
                    help="Comma-separated platform filter, e.g. instagram,facebook")
    args = ap.parse_args()

    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()] or None

    src = Path(args.input).expanduser()
    if not src.exists():
        print(f"Input not found: {src}", file=sys.stderr)
        return 1

    headers, rows = load_rows(src, args.sheet)
    headers = [str(h) for h in headers]
    idx = normalize_headers(headers)
    if "name" not in idx and "email" not in idx:
        print(f"No name/email column found in: {headers}", file=sys.stderr)
        return 1
    if args.limit:
        rows = rows[: args.limit]

    eng = SearchEngine(Path(args.search_cache) if args.search_cache else None,
                       live=not args.no_live_search, delay=args.delay)

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "osint_result"
    out_headers = headers + ([] if "notes" in [h.lower() for h in headers] else ["Notes"])
    ws.append(out_headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    col = {h.lower(): i for i, h in enumerate(out_headers)}

    for n, row in enumerate(rows, 1):
        row = list(row) + [""] * (len(headers) - len(row))
        name = str(row[idx["name"]]).strip() if "name" in idx else ""
        email = str(row[idx["email"]]).strip() if "email" in idx else ""
        if not (name or email):
            continue
        print(f"\n[{n}/{len(rows)}] Target: {name or email}", flush=True)

        # -------------------------------------------------------------
        # STEP 1: Holehe Email Check FIRST (Identifikasi platform aktif)
        # -------------------------------------------------------------
        holehe = {"used": [], "rate": [], "error": []}
        verified_platforms = []
        if email and not args.skip_holehe:
            print(f"  [Step 1] Cek email terdaftar ({email})...", flush=True)
            holehe = run_holehe(email)
            verified_platforms = holehe.get("used", [])
            print(f"           Terdaftar di: {', '.join(verified_platforms) or '-'}", flush=True)

        # -------------------------------------------------------------
        # STEP 2: Targeted Multi-query Google Search
        # -------------------------------------------------------------
        agg: list[tuple[str, str]] = []
        socials: dict[str, dict] = {}
        if name:
            queries = targeted_social_queries(name, verified_platforms=verified_platforms, all_platforms=platforms)
            print(f"  [Step 2] Targeted Google Search ({len(queries)} query)...", flush=True)
            for q in queries:
                print(f"           -> Q: {q}", flush=True)
                agg += eng.search(q)
            socials = extract_socials(agg, name=name, verified_platforms=verified_platforms)

        # -------------------------------------------------------------
        # STEP 3: Community & Affiliation Probe
        # -------------------------------------------------------------
        main_handle = next((socials[p]["handle"] for p in
                            ("instagram", "twitter", "tiktok", "linkedin", "github", "facebook")
                            if p in socials), None)
        crs: list[tuple[str, str]] = []
        for q in community_queries(name, main_handle):
            crs += eng.search(q)
        if name:
            socials = extract_socials(agg + crs, name=name, verified_platforms=verified_platforms)

        if socials:
            summary = ", ".join(
                "{}=@{}(skor {}{})".format(
                    p, d["handle"], d["score"],
                    ", verified-email" if d.get("email_verified") else ""
                ) for p, d in socials.items()
            )
        else:
            summary = "tidak ditemukan"
        print(f"  [Hasil Sosmed]: {summary}", flush=True)

        communities = community_from_results(crs, name)
        print(f"  [Komunitas]   : {', '.join(communities) if communities else '-'}", flush=True)

        # -------------------------------------------------------------
        # STEP 4: Maigret (Opsional)
        # -------------------------------------------------------------
        maigret_hits: list[tuple[str, str]] = []
        if args.maigret:
            print("  [Step 4] Running Maigret username search...", flush=True)
            for cand in candidate_usernames(name, email):
                maigret_hits += run_maigret(cand)

        # -------------------------------------------------------------
        # STEP 5: Compose Notes Multi-baris
        # -------------------------------------------------------------
        lines: list[str] = []

        socmed = []
        ambiguous = []
        for plat, label in (("instagram", "IG"), ("tiktok", "TikTok"),
                            ("twitter", "X"), ("facebook", "FB"),
                            ("linkedin", "LinkedIn"), ("youtube", "YouTube"),
                            ("github", "GitHub"), ("pinterest", "Pinterest"),
                            ("spotify", "Spotify")):
            if plat not in socials:
                continue
            d = socials[plat]
            n_alt = len(d.get("alts", []))
            verified_tag = " [Terverifikasi Email]" if d.get("email_verified") else ""
            if n_alt:
                socmed.append(f"{label}: {d['url']}{verified_tag} (+{n_alt} kandidat lain)")
                ambiguous.append(label)
            else:
                socmed.append(f"{label}: {d['url']}{verified_tag}")

        if maigret_hits:
            for site, url in maigret_hits[:6]:
                socmed.append(f"{site.strip()}: {url}")
        lines.append("Sosmed: " + ("; ".join(socmed) if socmed else "tidak ditemukan"))

        if communities:
            lines.append("Komunitas: " + ", ".join(communities))

        if email and not args.skip_holehe:
            if holehe["used"]:
                lines.append("Email terdaftar di: "
                             + ", ".join(h.replace(".com", "") for h in holehe["used"]))
            elif holehe["error"]:
                lines.append("Email: gagal dicek (" + holehe["error"][0] + ")")
            elif holehe["rate"]:
                lines.append("Email: tidak terkonfirmasi (rate-limited)")

        warn = []
        if not socials:
            warn.append("tidak ada profil yang cocok dengan nama")
        if socials and max((d["score"] for d in socials.values()), default=0) < 2.0:
            warn.append("kecocokan lemah, perlu verifikasi manual")
        if ambiguous:
            warn.append("nama umum, beberapa profil serupa di "
                        + "/".join(ambiguous) + " - perlu verifikasi manual")
        if warn:
            lines.append("Catatan: " + "; ".join(warn))

        notes = "\n".join(lines)

        out_row = [""] * len(out_headers)
        for i, v in enumerate(row):
            out_row[i] = v
        j = col.get("notes")
        if j is not None:
            out_row[j] = notes
        ws.append(out_row)

    ncol = col.get("notes", len(out_headers) - 1)
    for i, h in enumerate(out_headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = 90 if i - 1 == ncol else 24
    for r in ws.iter_rows(min_row=2):
        for c in r:
            c.alignment = Alignment(vertical="top", wrap_text=True)

    dest = src.with_name(src.stem + "_result.xlsx")
    wb.save(dest)
    print(f"\n✅ Hasil selesai disimpan ke: {dest}")

    if eng.missing:
        print(f"[cache] {len(eng.missing)} query belum ada di cache")
        if args.dump_queries:
            Path(args.dump_queries).write_text(
                json.dumps(eng.missing, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[cache] Daftar query berhasil ditulis ke {args.dump_queries}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
