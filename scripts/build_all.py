import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

# ================== KONFIG ==================
BASE = Path(__file__).resolve().parents[1]

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

CUSTOM_URL = "https://bwifi.my.id/hls/video.m3u8"

TZ = timezone(timedelta(hours=7))
NOW = datetime.now(TZ)

PRE_LIVE_MINUTES = 5
MAX_LIVE_CHANNEL = 5

# ================== HELPER ==================
def norm(txt: str) -> str:
    return re.sub(r"[^a-z0-9]", "", txt.lower())

def parse_time(t):
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    if len(t) > 14 and (t[14] == "+" or t[14] == "-"):
        sign = 1 if t[14] == "+" else -1
        hh = int(t[15:17])
        mm = int(t[17:19])
        tz = timezone(sign * timedelta(hours=hh, minutes=mm))
        dt = dt.replace(tzinfo=tz)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

def is_football(title):
    return " vs " in title.lower()

# ================== LOAD EPG ==================
print("📥 Load EPG")
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

epg_channels = {}
programmes = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name", "").strip()
    icon = ""
    icon_el = ch.find("icon")
    if icon_el is not None:
        icon = icon_el.get("src", "")
    if cid and name:
        epg_channels[cid] = {
            "name": name,
            "key": norm(name),
            "logo": icon
        }

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    programmes.append({
        "cid": p.get("channel"),
        "start": parse_time(p.get("start")),
        "stop": parse_time(p.get("stop")),
        "title": title,
        "is_match": is_football(title)
    })

# ================== PARSE M3U BLOK UTUH ==================
print("📺 Load playlist")
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

m3u_map = {}
for blk in blocks:
    m = re.search(r",(.+)$", blk[0])
    if not m:
        continue
    name = m.group(1).strip()
    m3u_map[norm(name)] = blk

# ================== BUILD LIVE ==================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

live_now = []
next_live = []

for p in programmes:
    if not p["is_match"]:
        continue

    cid = p["cid"]
    if cid not in epg_channels:
        continue

    ch = epg_channels[cid]
    key = ch["key"]
    if key not in m3u_map:
        continue

    blk = m3u_map[key].copy()
    start = p["start"]
    stop = p["stop"]

    delta = (start - NOW).total_seconds() / 60

    # Tentukan URL
    if start <= NOW <= stop:
        url = blk[-1]
        status = "LIVE NOW"
    elif 0 <= delta <= PRE_LIVE_MINUTES:
        url = blk[-1]
        status = "LIVE NOW"
    elif delta > PRE_LIVE_MINUTES:
        url = CUSTOM_URL + "\n"
        status = "LIVE NEXT"
    else:
        continue

    blk[-1] = url

    title = f"{status} | {start.strftime('%H:%M')} WIB | {p['title']}"

    blk[0] = (
        f'#EXTINF:-1 tvg-id="{cid}" '
        f'tvg-name="{ch["name"]}" '
        f'tvg-logo="{ch["logo"]}" '
        f'group-title="{status}",{title}\n'
    )

    if status == "LIVE NOW":
        live_now.append(blk)
    else:
        next_live.append(blk)

# Batasi live now max channel
live_now = live_now[:MAX_LIVE_CHANNEL]

# ================== OUTPUT ==================
for b in live_now:
    out.extend(b)

for b in next_live:
    out.extend(b)

OUTPUT_M3U.write_text("".join(out), encoding="utf-8")

print("✅ SUCCESS: Logo dari EPG, blok utuh, URL dinamis")
