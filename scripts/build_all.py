import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ========= PATH =========
BASE = Path(__file__).resolve().parent.parent
INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

# ========= EPG =========
EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

# ========= TIME =========
WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

# ========= EVENT FILTER =========
EURO_LEAGUES = [
    "premier", "la liga", "serie a",
    "bundesliga", "ligue 1",
    "champions", "europa", "conference"
]
BLOCK_EVENT = ["replay", "highlight", "rerun", "recap"]

# ========= CHANNEL EXCLUDE =========
EXCLUDE_CHANNEL = [
    "sea games",
    "sea v league",
    "seagames",
    "sea league"
]

def is_match(title):
    t = title.lower()
    return any(l in t for l in EURO_LEAGUES) and not any(b in t for b in BLOCK_EVENT)

def channel_allowed(name):
    n = name.lower()
    return not any(x in n for x in EXCLUDE_CHANNEL)

def parse_utc(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)

# ========= AMBIL 1 LIVE MATCH DARI EPG =========
xml = requests.get(EPG_URL, timeout=30).content
root = ET.fromstring(xml)

live = None
for p in root.findall("programme"):
    title_el = p.find("title")
    if title_el is None:
        continue

    title = title_el.text.strip()
    if not is_match(title):
        continue

    start = parse_utc(p.attrib["start"]).astimezone(WIB)
    stop = parse_utc(p.attrib["stop"]).astimezone(WIB)

    if start <= NOW <= stop:
        live = {
            "title": title,
            "time": start.strftime("%H:%M WIB")
        }
        break

# ========= BUILD OUTPUT =========
out = ["#EXTM3U\n"]

if live:
    skip_block = False
    current_name = ""

    for line in INPUT_M3U.read_text(encoding="utf-8").splitlines():
        if line.startswith("#EXTINF"):
            header, name = line.split(",", 1)
            current_name = name.strip()

            if channel_allowed(current_name):
                label = f"{live['title']} | {live['time']} | {current_name}"
                out.append(f"{header},{label}\n")
                skip_block = False
            else:
                skip_block = True
        else:
            if not skip_block:
                out.append(line + "\n")

OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("DONE | LIVE:", live["title"] if live else "NONE")
