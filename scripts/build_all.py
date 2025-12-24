import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# ================= KONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

# ================= HELPER =================
def norm(txt: str) -> str:
    return re.sub(r"[^a-z0-9]", "", txt.lower())

def parse_time(t: str) -> datetime:
    base = datetime.strptime(t[:14], "%Y%m%d%H%M%S")

    if len(t) >= 19:
        sign = 1 if t[14] == "+" else -1
        hh = int(t[15:17])
        mm = int(t[17:19])
        base = base.replace(
            tzinfo=timezone(sign * timedelta(hours=hh, minutes=mm))
        )
    else:
        base = base.replace(tzinfo=timezone.utc)

    return base.astimezone(WIB)

# ================= FILTER SPORT =================
MAJOR_KEYWORDS = [
    # Football dunia
    "vs", "premier", "la liga", "serie a", "bundesliga", "ligue",
    "champions", "europa", "conference", "world cup", "afc",

    # Indonesia
    "liga 1", "liga indonesia", "bri liga",

    # Badminton
    "badminton", "bwf", "thomas", "uber", "sudirman",

    # Volleyball
    "volleyball", "volley", "voli", "vnl",

    # MotoGP
    "motogp", "moto gp", "moto2", "moto3",
    "grand prix", "race", "wsbk"
]

def is_valid_event(title: str, category: str) -> bool:
    text = f"{title} {category}".lower()

    if any(x in text for x in ["replay", "highlight", "rerun"]):
        return False

    return any(k in text for k in MAJOR_KEYWORDS)

def max_live_duration(title: str, category: str) -> timedelta:
    text = f"{title} {category}".lower()

    if any(k in text for k in ["motogp", "moto gp", "race", "grand prix", "wsbk"]):
        return timedelta(hours=4)

    if any(k in text for k in ["badminton", "bwf"]):
        return timedelta(hours=2)

    if any(k in text for k in ["volley", "volleyball", "vnl"]):
        return timedelta(hours=2)

    return timedelta(hours=2, minutes=30)  # football default

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
    title = p.findtext("title", "").strip()
    cat = p.findtext("category", "").strip()
    if not is_valid_event(title, cat):
        continue

    programmes.append({
        "cid": p.get("channel"),
        "title": title,
        "cat": cat,
        "start": parse_time(p.get("start"))
    })

# ================= PARSE M3U (BLOCK UTUH) =================
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

m3u_channels = {}
for block in blocks:
    m = re.search(r",(.+)$", block[0])
    if not m:
        continue
    name = m.group(1).strip()
    m3u_channels.setdefault(norm(name), []).append(block)

# ================= BUILD OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

live_now = []
next_live = []

for p in programmes:
    cid = p["cid"]
    if cid not in epg_channels:
        continue

    epg = epg_channels[cid]
    key = epg["key"]
    if key not in m3u_channels:
        continue

    live_start = p["start"] - timedelta(minutes=5)
    live_end = p["start"] + max_live_duration(p["title"], p["cat"])

    for block in m3u_channels[key]:
        if live_start <= NOW <= live_end:
            title = f'LIVE NOW {p["start"].strftime("%H:%M")} WIB | SPORT | {p["title"]}'
            live_now.append(
                [f'#EXTINF:-1 tvg-logo="{epg["logo"]}" group-title="LIVE NOW",{title}\n']
                + block[1:]
            )

        elif NOW < live_start:
            title = f'NEXT LIVE {p["start"].strftime("%d-%m %H:%M")} WIB | SPORT | {p["title"]}'
            next_live.append(
                [f'#EXTINF:-1 tvg-logo="{epg["logo"]}" group-title="NEXT LIVE",{title}\n']
                + block[1:]
            )

# ================= OUTPUT =================
for blk in live_now:
    out.extend(blk)

for blk in next_live:
    out.extend(blk)

with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ SUCCESS: LIVE NOW & NEXT LIVE only (WIB accurate)")
