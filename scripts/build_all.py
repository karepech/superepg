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

# ========= FILTER =========
EURO_LEAGUES = [
    "premier", "la liga", "serie a",
    "bundesliga", "ligue 1",
    "champions", "europa", "conference"
]
BLOCK = ["replay", "highlight", "rerun", "recap"]

def is_match(title):
    t = title.lower()
    return any(l in t for l in EURO_LEAGUES) and not any(b in t for b in BLOCK)

def parse_utc(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)

# ========= AMBIL 1 LIVE MATCH =========
xml = requests.get(EPG_URL, timeout=30).content
root = ET.fromstring(xml)

live_match = None

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
        live_match = {
            "title": title,
            "time": start.strftime("%H:%M WIB")
        }
        break  # ambil satu saja (stabil)

# ========= BUILD OUTPUT =========
out = ["#EXTM3U\n"]

if live_match:
    for line in INPUT_M3U.read_text(encoding="utf-8").splitlines():
        if line.startswith("#EXTINF"):
            header, name = line.split(",", 1)
            label = f"{live_match['title']} | {live_match['time']} | {name.strip()}"
            out.append(f"{header},{label}\n")
        else:
            out.append(line + "\n")

OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("DONE | LIVE:", live_match["title"] if live_match else "NONE")
