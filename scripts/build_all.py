import requests, re
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U  = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_football.m3u"

EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

MAX_CHANNEL = 5
TZ = timezone(timedelta(hours=7))
FALLBACK_URL = "https://bwifi.my.id/hls/video.m3u8"

BLOCK_WORDS = ["md", "highlight", "classic", "replay", "rerun"]

FOOTBALL_KEYS = [
    "football","soccer","liga","league","premier","la liga",
    "serie a","bundesliga","ligue","champions",
    "europa","conference","afc","caf","cup"
]

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def parse_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S") \
        .replace(tzinfo=timezone.utc) \
        .astimezone(TZ)

def is_football(title, category):
    t = title.lower()
    c = category.lower()

    if not re.search(r"\bvs\b|\sv\s", t):
        return False

    for b in BLOCK_WORDS:
        if b in t:
            return False

    return any(k in t or k in c for k in FOOTBALL_KEYS)

# ================= LOAD EPG =================
print("📥 Download EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

now = datetime.now(TZ)
h3  = now + timedelta(days=3)

live_now  = []
live_next = []

for p in root.findall("programme"):
    title = p.findtext("title","").strip()
    cat   = p.findtext("category","").strip()
    if not title:
        continue

    if not is_football(title, cat):
        continue

    start = parse_time(p.attrib["start"])
    stop  = parse_time(p.attrib["stop"])

    if start <= now <= stop:
        live_now.append(title)
    elif now < start <= h3:
        live_next.append((start, title))

live_now  = list(dict.fromkeys(live_now))
live_next = list(dict.fromkeys(live_next))

print(f"⚽ LIVE NOW : {len(live_now)}")
print(f"⚽ NEXT H+3 : {len(live_next)}")

# ================= LOAD M3U (LOGO-BASED) =================
lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines(True)

channels = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        blk = [lines[i]]
        logo = ""

        m = re.search(r'tvg-logo="([^"]+)"', lines[i])
        if m:
            logo = norm(m.group(1))

        i += 1
        while i < len(lines):
            blk.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1

        channels.append({
            "logo": logo,
            "block": blk
        })
    i += 1

# ================= BUILD OUTPUT =================
out = ["#EXTM3U\n"]

def add_event(title, group):
    used = 0
    key = norm(title)[:10]

    for ch in channels:
        if used >= MAX_CHANNEL:
            break

        if key in ch["logo"]:
            blk = ch["block"].copy()
            blk[0] = re.sub(r",.*$", f",{group} | {title}\n", blk[0])
            out.extend(blk)
            used += 1

    if used == 0:
        out.append(f'#EXTINF:-1 group-title="{group}",{group} | {title}\n')
        out.append(FALLBACK_URL + "\n")

for t in live_now:
    add_event(t, "LIVE NOW")

for st, t in live_next:
    jam = st.strftime("%d-%m %H:%M WIB")
    add_event(f"{jam} | {t}", "LIVE NEXT")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ SELESAI (LOGO-BASED MATCHING)")
