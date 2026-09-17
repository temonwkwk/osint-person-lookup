#!/usr/bin/env python3
"""Bulk OSINT lookup from XLSX/CSV -> writes <name>_result.xlsx optimized for Customer Outreach (IG/TikTok/FB).

Pipeline Flow:
  1. Email check first (Holehe) -> detects verified registered platforms (IG, FB, Twitter, Spotify, dll).
     - If Name was initially empty: perform reverse username search from email prefix to discover real name.
     - Auto-Feedback Loop: If real name is discovered, auto-feed it into Step 2.
  2. Targeted multi-step Customer Social Search (Priority: Instagram, TikTok, Facebook, Twitter/X):
     - Priority queries for IG, TikTok, FB, and X/Twitter.
     - Secondary queries for LinkedIn (as professional validator).
  3. Handle Cascading:
     - Cross-check candidate handles across Instagram, TikTok, Facebook, Threads, and Twitter.
  4. Community, Forum, Group, Highlight & Activity Probe (Bilingual ID & EN):
     - Targeted queries on posts, bio, and highlights of discovered social media accounts:
       site:instagram.com/{handle} (community OR forum OR group OR komunitas OR grup OR yayasan OR highlight OR highlights OR kegiatan OR baksos OR charity OR volunteer)
       site:facebook.com/{handle} (community OR forum OR group OR komunitas OR grup OR yayasan)
       site:x.com/{handle} (community OR forum OR group OR komunitas OR grup)
     - Extraction of interests, groups, and hobbies for personalized outreach ice-breakers.
  5. Reachability & Contact Signal Extraction:
     - Extract follower counts, WhatsApp / wa.me links, bio links (linktr.ee, biolinky).
  6. Consolidated Customer Outreach Notes generation.

Two-pass usage with the cache (recommended):
  pass 1: python3 bulk_osint.py IN.xlsx --search-cache c.json --dump-queries q.json
          -> agent prefetches the queries in q.json into c.json
  pass 2: same command again -> all cache hits -> writes IN_result.xlsx

Usage:
  python3 bulk_osint.py INPUT.xlsx [--sheet S] [--search-cache c.json]
      [--dump-queries q.json] [--no-live-search] [--delay 4] [--limit N]
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
    "facebook": re.compile(r"https?://(?:www\.|web\.|m\.)?facebook\.com/([A-Za-z0-9_.\-]+)", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]+)", re.I),
    "threads": re.compile(r"https?://(?:www\.)?threads\.net/@([A-Za-z0-9_.]+)", re.I),
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

# Domains already reported as primary socials -> excluded from bare domain community mapping.
PRIMARY_SOCIAL_DOMAINS = (
    "instagram.com", "tiktok.com", "facebook.com", "twitter.com", "x.com",
    "pinterest.com", "spotify.com", "youtube.com", "linkedin.com", "threads.net",
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

# Bilingual keywords for organisations, communities, groups, forums, activities, and highlights
ORG_KEYWORDS = {
    # English
    "project", "international", "foundation", "community", "club", "program",
    "programme", "initiative", "institute", "association", "network", "society",
    "movement", "forum", "group", "center", "centre", "academy", "alliance", "coalition",
    "council", "union", "chapter", "collective", "organization", "organisation",
    "volunteers", "volunteer", "volunteering", "corps", "fellowship", "committee",
    "grant", "award", "guild", "league", "circle", "charity", "event", "summit",
    "backpacker", "backpackers", "touring", "traveler", "riders",
    # Indonesian
    "komunitas", "yayasan", "grup", "forum", "perkumpulan", "paguyuban", "relawan",
    "lembaga", "himpunan", "ikatan", "gerakan", "serikat", "badan", "wadah", "aliansi",
    "kegiatan", "baksos", "peduli", "berbagi", "aksi", "projek", "inisiatif", "pengabdian",
    "motoran", "bukber", "ngopi", "jalan-jalan", "sahabat",
}

# Generic title words that must never become a "community" name.
PHRASE_STOPWORDS = {
    "page", "archives", "profile", "member", "pdf", "read", "news", "video",
    "videos", "photos", "instagram", "facebook", "youtube", "linkedin", "tiktok",
    "twitter", "home", "search", "results", "winners", "winner", "daftar",
    "profil", "biodata", "the", "and", "with", "from", "for", "her", "his",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "empowering", "those",
    "lihat", "postingan", "foto", "video", "status", "threads", "highlights", "highlight",
    "story", "stories",
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
                    time.sleep(5 + attempt * 5)
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
      2.0  every name token appears in the result title/handle (full match)
      1.5  majority / sub-combination of name tokens appear (for 3+ word names)
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

    in_title = set(t for t in toks if t in tl)
    in_handle = set(t for t in toks if t in hl)
    combined = in_title | in_handle

    if len(combined) == len(toks):
        score += 2.0
    elif len(combined) >= 2 and len(combined) >= len(toks) / 2:
        score += 1.5  # Sub-combination match (e.g. 2 of 3 words, or 2-3 of 4 words)
    elif len(combined) == 1:
        longest = max(toks, key=len)
        if len(longest) >= 6 and longest in combined:
            score += 0.8

    # Contiguous sub-phrase match
    clean_title_raw = title.lower()
    if re.sub(r"[^a-z0-9]+", " ", name.lower()).strip() in re.sub(r"[^a-z0-9]+", " ", clean_title_raw):
        score += 0.3

    # Bonus confidence if the platform is proven registered for the target email
    if is_holehe_verified and score >= 1.0:
        score += 0.5

    return score


def extract_reachability_signals(text: str) -> list[str]:
    """Extract follower count, WhatsApp, and bio link signals for customer outreach."""
    signals = []
    # Follower count
    f_match = re.search(r"([\d.,]+[KkMm]?\+?\s*followers?)", text, re.I)
    if f_match:
        signals.append(f_match.group(1).strip())
    # WhatsApp / Phone
    wa_match = re.search(r"(?:WA|WhatsApp|Contact|Hubungi|Phone)[\s:]*([+\d\s-]{9,16})", text, re.I)
    if wa_match:
        clean_num = re.sub(r"[^\d+]", "", wa_match.group(1).strip())
        signals.append(f"WA: {clean_num}")
    # Contact Links (wa.me, linktree, etc.)
    link_match = re.search(r"((?:https?://)?(?:wa\.me|linktr\.ee|biolinky\.co|campsite\.bio|taplink\.cc)/\S+)", text, re.I)
    if link_match:
        signals.append(f"Link: {link_match.group(1).strip().rstrip('.,;')}")
    return signals


def extract_socials(results: list[tuple[str, str]], name: str = "",
                    threshold: float = 1.0,
                    verified_platforms: list[str] | None = None) -> dict[str, dict]:
    """platform -> {handle, url, title, score, signals}, choosing the best NAME match."""
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
                handle, {"count": 0, "url": url, "title": title, "score": 0.0, "signals": []})
            entry["count"] += 1
            if title and not entry["title"]:
                entry["title"] = title
            
            # Extract contact & follower signals
            sig = extract_reachability_signals(title)
            if sig:
                entry["signals"] = list(dict.fromkeys(entry["signals"] + sig))

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
            "facebook": f"https://www.facebook.com/{handle}",
            "twitter": f"https://x.com/{handle}",
            "threads": f"https://www.threads.net/@{handle}",
            "linkedin": f"https://www.linkedin.com/in/{handle}",
            "youtube": f"https://www.youtube.com/@{handle}",
            "github": f"https://github.com/{handle}",
            "pinterest": f"https://www.pinterest.com/{handle}",
            "spotify": f"https://open.spotify.com/user/{handle}",
        }.get(platform, data["url"])
        out[platform] = {"handle": handle, "url": canonical,
                         "title": data["title"], "score": round(data["score"], 2),
                         "hits": data["count"], "alts": alts,
                         "signals": data.get("signals", []),
                         "email_verified": platform in v_set}
    return out


def extract_name_from_username_search(results: list[tuple[str, str]], username: str) -> str:
    """Attempt to extract real name from reverse search results of a username."""
    patterns = [
        re.compile(r"milik\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:di|on|at|\-|\(|•|\|)", re.I),
        re.compile(r"by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:on|at|\-|\(|•|\|)", re.I),
        re.compile(rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,3}})\s*(?:\(@?{re.escape(username)}\)|•|\-|\|)", re.I),
    ]
    for url, title in results:
        for p in patterns:
            m = p.search(title)
            if m:
                cand = m.group(1).strip()
                words = cand.split()
                if 2 <= len(words) <= 4:
                    return cand
    return ""


# Priority search queries: Customer social channels (IG, TikTok, FB) come FIRST
OUTREACH_PLATFORM_TERMS = [
    ("instagram", "instagram"),
    ("tiktok", "tiktok"),
    ("facebook", "facebook"),
    ("twitter", "twitter"),
    ("threads", "threads"),
    ("linkedin", "linkedin"),
]


def name_combinations(name: str) -> list[str]:
    """Generate meaningful 2-word and 3-word combinations for names with > 2 words."""
    words = [w.strip() for w in re.split(r"[^a-zA-Z0-9]+", name) if len(w) >= 2]
    if len(words) <= 2:
        return []
    combos = []
    # 1. Consecutive bigrams (e.g. Kanzul Faisal, Faisal Alam, Alam Mina)
    for i in range(len(words) - 1):
        combos.append(f"{words[i]} {words[i+1]}")
    # 2. First + Last (e.g. Kanzul Mina, Arviandri Zaki)
    first_last = f"{words[0]} {words[-1]}"
    if first_last not in combos:
        combos.append(first_last)
    # 3. Trigrams if 4+ words
    if len(words) >= 4:
        for i in range(len(words) - 2):
            combos.append(f"{words[i]} {words[i+1]} {words[i+2]}")
    seen = set()
    out = []
    for c in combos:
        if c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def customer_outreach_queries(name: str, verified_platforms: list[str] | None = None,
                              all_platforms: list[str] | None = None) -> list[str]:
    """Generate search queries prioritizing Customer Outreach channels (IG, TikTok, FB)."""
    qs = []
    seen = set()

    def add_q(q: str):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            qs.append(q)

    # 1. Base consumer social search
    add_q(f'"{name}" site:instagram.com OR site:tiktok.com OR site:facebook.com')

    # 2. Sub-name combinations for names with > 2 words (Targeted Instagram & Socials)
    combos = name_combinations(name)
    for c in combos:
        add_q(f'site:instagram.com "{c}"')
        add_q(f'"{c}" instagram')
        add_q(f'site:tiktok.com "{c}"')
        add_q(f'site:facebook.com "{c}"')

    # 3. Prioritized queries for platforms verified in Holehe
    if verified_platforms:
        for vp in verified_platforms:
            v_clean = vp.lower().strip()
            if v_clean in HOLEHE_PLATFORM_MAP:
                plat_key, query_term, site_filter, _ = HOLEHE_PLATFORM_MAP[v_clean]
                add_q(f'"{name}" {query_term}')
                add_q(f'"{name}" {site_filter}')
            else:
                short_name = v_clean.split(".")[0]
                if short_name and short_name not in ("com", "org", "net"):
                    add_q(f'"{name}" {short_name}')
                    add_q(f'"{name}" site:{v_clean}')

    # 4. Direct platform search in priority order (IG -> TikTok -> FB -> X -> LinkedIn)
    wanted = all_platforms or [p for p, _ in OUTREACH_PLATFORM_TERMS]
    for plat, term in OUTREACH_PLATFORM_TERMS:
        if plat in wanted:
            add_q(f'"{name}" {term}')

    return qs


def handle_cascading_queries(discovered_handles: list[str]) -> list[str]:
    """Cross-search discovered handles across consumer platforms (IG, TikTok, FB, Threads)."""
    qs = []
    seen = set()
    for h in discovered_handles:
        h = h.strip().lower()
        if not h or len(h) < 3 or h in seen or h in RESERVED:
            continue
        seen.add(h)
        qs.append(f"site:instagram.com/{h} OR site:tiktok.com/@{h} OR site:facebook.com/{h} OR site:threads.net/@{h}")
    return qs[:4]


def community_queries(name: str, socials: dict[str, dict] | None = None) -> list[str]:
    """Generate bilingual queries for finding community/forum/group/highlight mentions."""
    qs = []
    seen = set()

    def add_q(q: str):
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            qs.append(q)

    # 1. Targeted search on discovered social media profiles/posts/highlights
    kw_filter = (
        "(community OR forum OR group OR komunitas OR grup OR "
        "perkumpulan OR paguyuban OR yayasan OR volunteer OR relawan OR "
        "highlight OR highlights OR baksos OR charity OR kegiatan OR event OR backpacker OR motoran)"
    )
    if socials:
        for plat, data in socials.items():
            handle = data.get("handle")
            if not handle:
                continue
            if plat == "instagram":
                add_q(f"site:instagram.com/{handle} {kw_filter}")
            elif plat == "facebook":
                add_q(f"site:facebook.com/{handle} {kw_filter}")
            elif plat == "twitter":
                add_q(f"site:x.com/{handle} OR site:twitter.com/{handle} {kw_filter}")
            elif plat == "tiktok":
                add_q(f"site:tiktok.com/@{handle} {kw_filter}")
            elif plat == "linkedin":
                add_q(f"site:linkedin.com/in/{handle} {kw_filter}")
            elif plat == "github":
                add_q(f"site:github.com/{handle} {kw_filter}")
            else:
                add_q(f'"{handle}" {kw_filter}')

    # 2. General name + community / forum / group / activity keywords (Bilingual: ID & EN)
    if name:
        add_q(f'"{name}" (komunitas OR community OR forum OR grup OR group OR yayasan OR foundation OR relawan OR volunteer)')
        add_q(f'"{name}" (perkumpulan OR paguyuban OR baksos OR charity OR "kegiatan" OR "member of" OR "anggota")')

    return qs


def _clean_title(title: str) -> str:
    t = re.sub(r"\s*[\|\-–—]\s*[^|\-–—]{0,40}$", "", title).strip()
    return t or title.strip()


def org_phrases(title: str, name: str) -> list[str]:
    out: list[str] = []
    ntoks = set(name_tokens(name))
    text = _clean_title(title)
    text = re.sub(r"[\"'’‘“”]", "", text)

    clean_lead_pat = (
        r"^(?:Instagram|Facebook|Twitter|TikTok|LinkedIn|YouTube|Profil|Profile|Biodata|Melalui|Dari|Bersama|Diskusi\s+di|Joined|"
        r"Member\s+of|Anggota\s+dari|Gathering\s+bersama|Aktivis\s+di|Follow|"
        r"Highlights?|Stories|Story|Album|Kegiatan|Edisi)\s*[:\-–—]?\s*"
    )

    joiner = r"(?:of|for|the|on|and|in|de|di|dan|untuk)"
    pattern = re.compile(
        rf"\b([A-Z][\w&']*(?:\s+(?:{joiner}\s+)?[A-Z0-9][\w&']*)+)\b")

    # 1. Capitalized multi-word phrases
    for m in pattern.finditer(text):
        phrase = m.group(1).strip()
        phrase = re.sub(clean_lead_pat, "", phrase, flags=re.I).strip()
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

    # 2. Segment-based extraction for Instagram/social bullet separated highlights
    segments = re.split(r"[·•\n]", text)
    for seg in segments:
        seg_clean = seg.strip()
        seg_clean = re.sub(clean_lead_pat, "", seg_clean, flags=re.I).strip()
        words = [w.lower().removesuffix("'s") for w in re.split(r"[^\w]+", seg_clean) if w]
        if len(words) < 2 or len(seg_clean) < 6 or len(seg_clean) > 45:
            continue
        if ntoks and set(words) <= ntoks:
            continue
        if any(w in ORG_KEYWORDS for w in words):
            cleaned_seg = re.sub(r"[^\w\s&'-]+", "", seg_clean).strip()
            if cleaned_seg and cleaned_seg not in out:
                out.append(cleaned_seg)

    return out


def community_from_results(results: list[tuple[str, str]], name: str = "") -> list[str]:
    scored: dict[str, int] = {}

    def add(label: str, weight: int) -> None:
        label = label.strip(" -–—|·,:;\"'")
        if len(label) < 3 or label.lower() in ("instagram", "facebook", "tiktok", "twitter", "linkedin", "youtube", "social media", "highlight", "highlights"):
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
        if any(d in low for d in ACADEMIC_NOISE):
            continue

        is_news = any(d in low for d in NEWS_DOMAINS)
        is_social = any(d in low for d in PRIMARY_SOCIAL_DOMAINS)

        if is_news and name:
            tl = title.lower()
            if not all(t in tl for t in name_tokens(name)):
                continue

        if re.search(r"/(tagged|tag|category|archives?|page)/", low):
            continue

        if not is_social:
            for dom, label in ORG_DOMAINS.items():
                if dom in low:
                    add(label, 3)
                    break

        for phrase in org_phrases(title, name):
            add(phrase, 2 if (is_news or is_social) else 3)

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
    ap = argparse.ArgumentParser(description="Bulk OSINT person lookup optimized for Customer Outreach (IG/TikTok/FB)")
    ap.add_argument("input", help="Input file (.xlsx or .csv)")
    ap.add_argument("--sheet", default=None, help="Sheet name for Excel file")
    ap.add_argument("--search-cache", default=None, help="Path to JSON search cache")
    ap.add_argument("--dump-queries", default=None, help="Dump missing queries to JSON for batch retrieval")
    ap.add_argument("--no-live-search", action="store_true", help="Disable live DuckDuckGo/Google search")
    ap.add_argument("--skip-holehe", action="store_true", help="Skip email registration check (Holehe)")
    ap.add_argument("--delay", type=float, default=4.0, help="Delay between search requests in seconds")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of rows processed")
    ap.add_argument("--platforms", default="",
                    help="Comma-separated platform filter, e.g. instagram,tiktok,facebook")
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
    ws = wb.active or wb.create_sheet()
    ws.title = "outreach_osint_result"
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
        print(f"\n[{n}/{len(rows)}] Target Outreach: {name or email}", flush=True)

        # -------------------------------------------------------------
        # STEP 1: Holehe Email Check FIRST (Identifikasi platform aktif)
        # -------------------------------------------------------------
        holehe = {"used": [], "rate": [], "error": []}
        verified_platforms = []
        discovered_handles = []
        if email and not args.skip_holehe:
            print(f"  [Step 1] Cek email terdaftar ({email})...", flush=True)
            holehe = run_holehe(email)
            verified_platforms = holehe.get("used", [])
            print(f"           Terdaftar di: {', '.join(verified_platforms) or '-'}", flush=True)
            if "@" in email:
                discovered_handles.append(email.split("@")[0].lower())

        # Auto-Feedback Loop: If name is initially empty, discover real name from email prefix
        if not name and email and "@" in email:
            email_user = email.split("@")[0].lower()
            print(f"  [Step 1b] Mencari nama dari username email ({email_user})...", flush=True)
            rev_results = eng.search(f'"{email_user}"')
            discovered_name = extract_name_from_username_search(rev_results, email_user)
            if discovered_name:
                name = discovered_name
                print(f"           ✅ Nama teridentifikasi: {name}", flush=True)

        # -------------------------------------------------------------
        # STEP 2: Customer Outreach Multi-Query Search (IG, TikTok, FB, X)
        # -------------------------------------------------------------
        agg: list[tuple[str, str]] = []
        socials: dict[str, dict] = {}
        if name:
            queries = customer_outreach_queries(name, verified_platforms=verified_platforms, all_platforms=platforms)
            print(f"  [Step 2] Customer Social Search ({len(queries)} query)...", flush=True)
            for q in queries:
                print(f"           -> Q: {q}", flush=True)
                agg += eng.search(q)
            socials = extract_socials(agg, name=name, verified_platforms=verified_platforms)

        # -------------------------------------------------------------
        # STEP 3: Handle Cascading (Cross-search handles across IG/TikTok/FB)
        # -------------------------------------------------------------
        current_handles = [d["handle"] for d in socials.values() if d.get("handle")]
        all_candidate_handles = list(dict.fromkeys(discovered_handles + current_handles))
        cascade_queries = handle_cascading_queries(all_candidate_handles)
        if cascade_queries:
            print(f"  [Step 3] Handle Cascading Search ({len(cascade_queries)} query)...", flush=True)
            for q in cascade_queries:
                print(f"           -> Q: {q}", flush=True)
                agg += eng.search(q)
            if name:
                socials = extract_socials(agg, name=name, verified_platforms=verified_platforms)

        # -------------------------------------------------------------
        # STEP 4: Community, Highlights & Ice Breaker Probe
        # -------------------------------------------------------------
        crs: list[tuple[str, str]] = []
        comm_queries = community_queries(name, socials=socials)
        print(f"  [Step 4] Pelacakan Minat & Komunitas ({len(comm_queries)} query)...", flush=True)
        for q in comm_queries:
            print(f"           -> Q: {q}", flush=True)
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
        print(f"  [Minat/Komunitas]: {', '.join(communities) if communities else '-'}", flush=True)

        # -------------------------------------------------------------
        # STEP 5: Compose Customer Outreach Notes Format
        # -------------------------------------------------------------
        lines: list[str] = []

        # 1. Primary Consumer Outreach Socials (IG, TikTok, FB, Threads, X)
        consumer_socmed = []
        professional_socmed = []
        ambiguous = []
        contact_signals = []

        for plat in ("instagram", "tiktok", "facebook", "threads", "twitter"):
            if plat in socials:
                d = socials[plat]
                label = {"instagram": "IG", "tiktok": "TikTok", "facebook": "FB", "threads": "Threads", "twitter": "X"}[plat]
                n_alt = len(d.get("alts", []))
                verified_tag = " [Terverifikasi Email]" if d.get("email_verified") else ""
                signals_str = f" ({' | '.join(d['signals'])})" if d.get("signals") else ""
                
                if d.get("signals"):
                    contact_signals.extend(d["signals"])

                if n_alt:
                    consumer_socmed.append(f"{label}: {d['url']}{signals_str}{verified_tag} (+{n_alt} kandidat)")
                    ambiguous.append(label)
                else:
                    consumer_socmed.append(f"{label}: {d['url']}{signals_str}{verified_tag}")

        for plat in ("linkedin", "youtube", "github", "pinterest", "spotify"):
            if plat in socials:
                d = socials[plat]
                label = {"linkedin": "LinkedIn", "youtube": "YouTube", "github": "GitHub", "pinterest": "Pinterest", "spotify": "Spotify"}[plat]
                professional_socmed.append(f"{label}: {d['url']}")

        lines.append("Sosmed Utama (Outreach): " + ("; ".join(consumer_socmed) if consumer_socmed else "tidak ditemukan"))

        # 2. Fast DM Channel / Direct Contact Recommendation
        direct_channels = []
        if "instagram" in socials:
            direct_channels.append(f"Instagram DM (@{socials['instagram']['handle']})")
        if "facebook" in socials:
            direct_channels.append("Facebook Messenger")
        if "tiktok" in socials:
            direct_channels.append(f"TikTok DM (@{socials['tiktok']['handle']})")
        wa_only = [s for s in contact_signals if "WA:" in s or "wa.me" in s]
        if wa_only:
            direct_channels.extend(wa_only)

        if direct_channels:
            lines.append("Kanal DM / Outreach: " + " | ".join(direct_channels))

        # 3. Professional Background Context
        if professional_socmed:
            lines.append("Profil Profesional: " + "; ".join(professional_socmed))

        # 4. Ice Breakers / Communities & Interests
        if communities:
            lines.append("Minat & Komunitas (Ice Breaker): " + ", ".join(communities))

        # 5. Holehe Verified Email
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
