import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================= PATH =================
BASE = Path(__file__).resolve().parent.parent
INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

# ================= EPG =================
EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

# ================= TIME =================
WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

# ================= EVENT FILTER =================
EURO_LEAGUES = [
    "premier", "la liga", "serie a",
    "bundesliga", "ligue 1",
    "champions", "europa", "conference"
]
BLOCK_EVENT = ["replay", "highlight", "rerun", "recap"]

# ================= CHANNEL EXCLUDE =================
EXCLUDE_CHANNEL = [
    "sea games", "sea v league",
    "seagames", "sea league"
]

def is_live_match(title):
    t = title.lower()
    return any(l in t for l in EURO_LEAGUES) and not any(b in t for b in BLOCK_EVENT)

def channel_allowed(name):
    n = name.lower()
    return not any(x in n for x in EXCLUDE_CHANNEL)

def parse_utc(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)

# ================= LOAD LIVE EVENTS =================
xml = requests.get(EPG_URL, timeout=30).content
root = ET.fromstring(xml)

live_events = []
for p in root.findall("programme"):
    title_el = p.find("title")
    if title_el is None:
        continue

    title = title_el.text.strip()
    if not is_live_match(title):
        continue

    start = parse_utc(p.attrib["start"]).astimezone(WIB)
    stop = parse_utc(p.attrib["stop"]).astimezone(WIB)

    if start <= NOW <= stop:
        live_events.append({
            "title": title,
            "time": start.strftime("%H:%M WIB")
        })

# ================= BUILD OUTPUT =================
out = ["#EXTM3U\n"]

if live_events:
    for event in live_events:
        skip = False
        current_channel = ""

        for line in INPUT_M3U.read_text(encoding="utf-8").splitlines():
            if line.startswith("#EXTINF"):
                header, name = line.split(",", 1)
                current_channel = name.strip()

                if channel_allowed(current_channel):
                    label = f"{current_channel} | {event['title']} | {event['time']}"
                    out.append(f"{header},{label}\n")
                    skip = False
                else:
                    skip = True
            else:
                if not skip:
                    out.append(line + "\n")

OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print(f"DONE | LIVE EVENTS: {len(live_events)}")
