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

BLOCK_WORDS = [
    "replay", "highlight", "rerun",
    "recap", "review", "classic",
    "full match", "magazine", "md"
]

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def is_live_match(title):
    t = title.lower()

    # harus pertandingan
    if not re.search(r"\bvs\b|\bv\b", t):
        return False

    # buang ulangan
    for w in BLOCK_WORDS:
        if w in t:
            return False

    return True

# ================= LOAD EPG =================
print("📥 Load EPG")
xml_data = requests.get(EPG_URL, timeout=120).content
root = ET.fromstring(xml_data)

events = []
for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    if title and is_live_match(title):
        events.append(title)

# unik
events = list(dict.fromkeys(events))
print(f"🎯 LIVE EVENT ditemukan: {len(events)}")

# ================= LOAD M3U BLOK UTUH =================
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

# ================= BUILD OUTPUT =================
out = ["#EXTM3U\n"]

for title in events:
    used = 0
    key = norm(title)[:10]

    for blk in blocks:
        if used >= MAX_CHANNEL:
            break

        if key in norm(blk[0]):
            new_blk = blk.copy()
            new_blk[0] = re.sub(
                r",.*$",
                f",LIVE NOW | {title}\n",
                new_blk[0]
            )
            out.extend(new_blk)
            used += 1

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ SELESAI (VERSI AWAL)")
