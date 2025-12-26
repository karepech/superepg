import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_now.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

MAX_CHANNEL = 5

EURO_LEAGUES = [
    "premier",
    "la liga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "champions",
    "europa",
    "conference"
]

# semua ini = ULANGAN
BLOCK_WORDS = [
    "md",
    "replay",
    "highlight",
    "highlights",
    "classic",
    "recap",
    "review",
    "rerun",
    "full match",
    "magazine",
    "hls"
]

# ================= HELPERS =================
def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())

def is_live_match(title: str, league: str) -> bool:
    t = title.lower()
    l = league.lower()

    # wajib vs atau (L)
    if "(l)" not in t and not re.search(r"\bvs\b|\bv\b", t):
        return False

    # buang ulangan
    for w in BLOCK_WORDS:
        if w in t:
            return False

    # hanya liga Eropa besar
    if not any(x in l for x in EURO_LEAGUES):
        return False

    return True

# ================= LOAD EPG =================
print("📥 Load EPG")
xml_data = requests.get(EPG_URL, timeout=120).content
root = ET.fromstring(xml_data)

events = []

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    league = p.findtext("category", "").strip()

    if not title:
        continue

    if is_live_match(title, league):
        events.append(title)

# unik: 1 pertandingan = 1 judul
events = list(dict.fromkeys(events))

print(f"⚽ LIVE EVENT ditemukan: {len(events)}")

# ================= LOAD M3U (BLOK UTUH) =================
lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines(True)

blocks = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        blk = [lines[i]]
        i += 1
        while i < len(lines):
            blk.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(blk)
    i += 1

print(f"📺 Total channel: {len(blocks)}")

# ================= BUILD OUTPUT =================
out = ["#EXTM3U\n"]

for title in events:
    used = 0
    title_key = norm(title)

    for blk in blocks:
        if used >= MAX_CHANNEL:
            break

        extinf = blk[0]

        if title_key[:10] in norm(extinf):
            new_blk = blk.copy()

            # ganti NAMA SAJA, BLOK UTUH
            new_blk[0] = re.sub(
                r",.*$",
                f",LIVE NOW | {title}\n",
                new_blk[0]
            )

            out.extend(new_blk)
            used += 1

# fallback kalau EPG ada tapi channel tidak match
if len(out) == 1 and events:
    out.append(f'#EXTINF:-1 group-title="LIVE NOW",LIVE NOW | {events[0]}\n')
    out.append("https://bwifi.my.id/hls/video.m3u8\n")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ SELESAI: LIVE EVENT (tanpa waktu, BLOK UTUH)")
