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

def is_live_football(title):
    t = title.lower()
    return any(l in t for l in EURO_LEAGUES) and not any(b in t for b in BLOCK)

def parse_utc(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)

# ========= CEK LIVE =========
xml = requests.get(EPG_URL, timeout=30).content
root = ET.fromstring(xml)

live_found = False

for p in root.findall("programme"):
    title_el = p.find("title")
    if title_el is None:
        continue

    title = title_el.text or ""
    if not is_live_football(title):
        continue

    start = parse_utc(p.attrib["start"]).astimezone(WIB)
    stop = parse_utc(p.attrib["stop"]).astimezone(WIB)

    if start <= NOW <= stop:
        live_found = True
        break

# ========= OUTPUT =========
if live_found:
    OUTPUT_M3U.write_text(
        INPUT_M3U.read_text(encoding="utf-8"),
        encoding="utf-8"
    )
else:
    OUTPUT_M3U.write_text("#EXTM3U\n", encoding="utf-8")

print("DONE | Live bola:", live_found)
