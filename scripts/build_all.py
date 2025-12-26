import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re

# ================= CONFIG =================
EPG_FILE = Path("epg_wib_sports.xml")
INPUT_M3U = Path("live_epg_sports.m3u")
OUTPUT_M3U = Path("live_all.m3u")

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

BLOCK_WORDS = [
    "MD",
    "HIGHLIGHT",
    "HIGHLIGHTS",
    "CLASSIC",
    "REPLAY",
    "REWIND",
    "ARCHIVE"
]

# ================= HELPERS =================
def is_replay(title: str) -> bool:
    t = title.upper()
    return any(w in t for w in BLOCK_WORDS)

def is_match(title: str) -> bool:
    return " VS " in title.upper()

def clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()

# ================= LOAD M3U =================
channels = []
current = []

for line in INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines():
    if line.startswith("#EXTINF"):
        current = [line]
    elif line.startswith("http"):
        current.append(line)
        channels.append("\n".join(current))
        current = []

# ================= PARSE EPG =================
tree = ET.parse(EPG_FILE)
root = tree.getroot()

live_now = []
live_next = []

for prog in root.findall("programme"):
    title_el = prog.find("title")
    if title_el is None:
        continue

    title = clean_title(title_el.text or "")
    title_upper = title.upper()

    if not is_match(title):
        continue

    if is_replay(title):
        continue

    is_live = "(L)" in title_upper

    start_raw = prog.get("start")
    if not start_raw:
        continue

    start = datetime.strptime(start_raw[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(TZ)

    if start.date() == NOW.date():
        live_now.append(title)
    else:
        live_next.append(title)

# ================= BUILD OUTPUT =================
out = ["#EXTM3U"]

def write_group(group_name, titles):
    for title in titles:
        for ch in channels:
            if "tvg-name" in ch.lower():
                out.append(
                    ch.replace(
                        "#EXTINF:-1",
                        f'#EXTINF:-1 group-title="{group_name}", {group_name} | {title}'
                    )
                )

write_group("LIVE NOW", live_now)
write_group("LIVE NEXT", live_next)

OUTPUT_M3U.write_text("\n".join(out), encoding="utf-8")

print(f"LIVE NOW: {len(live_now)} event")
print(f"LIVE NEXT: {len(live_next)} event")
