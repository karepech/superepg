import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# ================= KONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"   # input di ROOT
OUTPUT_M3U = BASE / "live_all.m3u"         # output di ROOT

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

# ================= HELPER =================
def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())

def parse_time(t: str) -> datetime:
    """
    Parse waktu EPG:
    - Support offset +HHMM / -HHMM
    - Fallback UTC
    - Output WIB
    """
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    if len(t) > 14:
        try:
            sign = 1 if t[14] == "+" else -1
            hours = int(t[15:17])
            minutes = int(t[17:19])
            offset = timezone(sign * timedelta(hours=hours, minutes=minutes))
            dt = dt.replace(tzinfo=offset)
        except Exception:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

# ================= LOAD EPG (REMOTE) =================
print("📥 Download EPG...")
resp = requests.get(EPG_URL, timeout=120)
resp.raise_for_status()
root = ET.fromstring(resp.content)

epg_by_id = {}
epg_by_key = {}
programmes = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name")
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""
    if name:
        epg_by_id[cid] = {"name": name.strip(), "logo": logo}
        epg_by_key[norm(name)] = cid

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    cat = p.findtext("category", "SPORT").strip()
    start = parse_time(p.get("start"))
    stop = parse_time(p.get("stop"))
    cid = p.get("channel")
    programmes.append((start, stop, title, cat, cid))

# ================= PARSE M3U (BLOK UTUH) =================
with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

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

# ================= MAP CHANNEL NORMAL =================
# key: normalized channel name -> block
channel_blocks = {}

for block in blocks:
    m = re.search(r",(.+)$", block[0])
    if not m:
        continue
    name = m.group(1).strip()
    key = norm(name)
    channel_blocks[key] = block

# Sinkronkan EXTINF channel normal dengan EPG (jika ketemu)
for key, block in list(channel_blocks.items()):
    if key in epg_by_key:
        cid = epg_by_key[key]
        epg = epg_by_id[cid]
        block[0] = (
            f'#EXTINF:-1 '
            f'tvg-id="{cid}" '
            f'tvg-name="{epg["name"]}" '
            f'tvg-logo="{epg["logo"]}" '
            f'group-title="SPORTS",{epg["name"]}\n'
        )
        channel_blocks[key] = block

# ================= PILIH CHANNEL UNTUK EVENT =================
def pick_channel_for_event(title: str):
    """
    Prioritas:
    1) CTV 1–6 (Champions TV / Vidio) jika event EPL/UEFA
    2) Fallback: channel lain yang namanya muncul di judul
    """
    tl = title.lower()

    is_major = any(k in tl for k in [
        # EPL & klub
        "premier", "man utd", "man united", "man city", "liverpool",
        "arsenal", "chelsea", "newcastle", "wolves", "fulham",
        "west ham", "nottingham",
        # UEFA
        "uefa", "champions league", "europa", "conference"
    ])

    # 1️⃣ PRIORITAS: CTV 1–6
    if is_major:
        for key, block in channel_blocks.items():
            # cocokkan ctv1 / ctv 1 / ctv-1
            if re.match(r"ctv\s*[-]?\s*[1-6]$", key):
                return block

    # 2️⃣ FALLBACK: cocokkan kata judul ke nama channel
    for key, block in channel_blocks.items():
        if key and key in norm(title):
            return block

    return None

# ================= BUILD OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

# CHANNEL NORMAL
for block in channel_blocks.values():
    out.extend(block)

# LIVE EVENTS (SALIN BLOK UTUH + DRM)
for start, stop, title, cat, cid in sorted(programmes):
    src_block = pick_channel_for_event(title)
    if not src_block:
        continue

    logo = epg_by_id.get(cid, {}).get("logo", "")

    if start <= NOW < stop:
        name = f"LIVE NOW {start.strftime('%H:%M')} WIB | {cat} | {title}"
        out.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="LIVE NOW",{name}\n')
        out.extend(src_block[1:])  # SALIN KODIPROP + EXTVLCOPT + URL
    elif start > NOW:
        name = f"NEXT LIVE {start.strftime('%d-%m %H:%M')} WIB | {cat} | {title}"
        out.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="NEXT LIVE",{name}\n')
        out.extend(src_block[1:])  # SALIN KODIPROP + EXTVLCOPT + URL

# ================= SAVE =================
with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ SUCCESS: EPG sinkron, LIVE EVENT aktif, CTV prioritas, WIB akurat")
