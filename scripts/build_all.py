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

# ================= FILTER =================
EURO_LEAGUES = [
    "premier", "la liga", "serie a",
    "bundesliga", "ligue 1",
    "champions", "europa", "conference"
]

BLOCK_WORDS = ["replay", "highlight", "rerun", "recap"]

# ================= HELPERS =================
def is_live_match(title):
    t = title.lower()
    return any(x in t for x in EURO_LEAGUES) and not any(b in t for b in BLOCK_WORDS)

def parse_utc(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)

def to_wib(dt):
    return dt.astimezone(WIB)

def load_m3u_blocks(path):
    blocks = []
    cur = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#EXTINF"):
            if cur:
                blocks.append(cur)
            cur = [line]
        else:
            if cur:
                cur.append(line)

    if cur:
        blocks.append(cur)
    return blocks

# ================= LOAD LIVE EVENTS =================
xml = requests.get(EPG_URL, timeout=30).content
root = ET.fromstring(xml)

live_events = []
for p in root.findall("programme"):
    title_el = p.find("title")
    if title_el is None:
        continue

    title = title_el.text or ""
    if not is_live_match(title):
        continue

    start = to_wib(parse_utc(p.attrib["start"]))
    stop = to_wib(parse_utc(p.attrib["stop"]))

    if start <= NOW <= stop:
        live_events.append({
            "title": title,
            "start": start
        })

# ================= BUILD OUTPUT =================
blocks = load_m3u_blocks(INPUT_M3U)
out = ["#EXTM3U\n"]

for ev in live_events:
    time_str = ev["start"].strftime("%H:%M WIB")

    for block in blocks:
        # ganti judul saja, BLOK UTUH TETAP
        new_extinf = block[0].split(",", 1)[0] + \
            f",LIVE | {time_str} | {ev['title']}"

        out.append(new_extinf + "\n")
        for line in block[1:]:
            out.append(line + "\n")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("OK → semua channel tampil jika live bola")
