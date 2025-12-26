import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

# ================= FILTER RULES =================
BLOCK_KEYWORDS = [
    "md", "highlight", "highlights", "classic",
    "hls", "replay", "recap", "magazine", "review"
]

VALID_LEAGUES = [
    "premier league", "liga inggris",
    "laliga", "liga spanyol",
    "serie a", "liga italia",
    "bundesliga",
    "ligue 1",
    "afc", "piala afrika"
]

# ================= HELPERS =================
def norm(txt: str) -> str:
    return re.sub(r"[^a-z0-9]", "", txt.lower())

def has_block_keyword(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in BLOCK_KEYWORDS)

def is_valid_match(title: str, category: str) -> bool:
    text = f"{title} {category}".lower()

    # HARUS ada vs (kecuali nanti mau tambah olahraga lain)
    if "vs" not in text:
        return False

    # MD dan keyword terlarang = ULANGAN
    if has_block_keyword(text):
        return False

    # Harus liga besar / afc
    if not any(l in text for l in VALID_LEAGUES):
        return False

    return True

# ================= LOAD EPG =================
print("📥 Download EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

epg_channels = {}
programmes = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name", "").strip()
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""
    if name:
        epg_channels[cid] = {
            "name": name,
            "key": norm(name),
            "logo": logo
        }

for p in root.findall("programme"):
    programmes.append({
        "start": p.get("start"),
        "stop": p.get("stop"),
        "title": p.findtext("title", "").strip(),
        "cat": p.findtext("category", "").strip(),
        "cid": p.get("channel")
    })

# ================= PARSE M3U (BLOCK UTUH) =================
if not INPUT_M3U.exists():
    raise FileNotFoundError(f"M3U tidak ditemukan: {INPUT_M3U}")

lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines(True)

blocks = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        block = [lines[i]]
        i += 1
        while i < len(lines):
            block.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(block)
    i += 1

m3u_map = {}
for block in blocks:
    m = re.search(r",(.+)$", block[0])
    if not m:
        continue
    name = m.group(1).strip()
    m3u_map[norm(name)] = block

# ================= BUILD LIVE LIST =================
live_now = []
live_next = []
used_keys = set()

for p in programmes:
    cid = p["cid"]
    if cid not in epg_channels:
        continue

    epg = epg_channels[cid]
    key = epg["key"]

    if key not in m3u_map:
        continue

    if not is_valid_match(p["title"], p["cat"]):
        continue

    if key in used_keys:
        continue

    used_keys.add(key)

    block = m3u_map[key]
    title = f"{p['title']}"

    extinf = (
        f'#EXTINF:-1 tvg-id="{cid}" '
        f'tvg-name="{epg["name"]}" '
        f'tvg-logo="{epg["logo"]}" '
        f'group-title="LIVE NOW",{title}\n'
    )

    live_now.append([extinf] + block[1:])

# ================= WRITE OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

for blk in live_now:
    out.extend(blk)

OUTPUT_M3U.write_text("".join(out), encoding="utf-8")

print(f"✅ LIVE EVENT dibuat: {len(live_now)} channel")
