import requests
from lxml import etree
from pathlib import Path
from datetime import datetime, timezone, timedelta
import re

# ================== CONFIG ==================
BASE = Path(__file__).resolve().parents[1]

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_now.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

FOOTBALL_KEYWORDS = [
    "football", "soccer", "liga", "league", "premier",
    "la liga", "serie a", "bundesliga", "uefa", "champions",
    "europa", "world cup", "afc", "fifa"
]

# ================== UTIL ==================
def normalize(text):
    return re.sub(r"\s+", " ", text.lower().strip())

def is_football(title):
    t = title.lower()
    return any(k in t for k in FOOTBALL_KEYWORDS)

def parse_epg_time(t):
    # format: YYYYMMDDHHMMSS +0700 (WIB)
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=WIB)

# ================== LOAD EPG ==================
def load_live_football_channels():
    print("📡 Download EPG...")
    xml = requests.get(EPG_URL, timeout=30).content
    root = etree.fromstring(xml)

    live_channels = set()

    for prog in root.findall("programme"):
        title_el = prog.find("title")
        if title_el is None:
            continue

        title = title_el.text or ""
        if not is_football(title):
            continue

        start = parse_epg_time(prog.get("start"))
        stop  = parse_epg_time(prog.get("stop"))

        if start <= NOW <= stop:
            ch = normalize(prog.get("channel"))
            live_channels.add(ch)

    print(f"⚽ LIVE football channels (EPG): {len(live_channels)}")
    return live_channels

# ================== LOAD M3U ==================
def load_m3u_blocks():
    blocks = []
    with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
        buf = []
        for line in f:
            if line.startswith("#EXTINF"):
                if buf:
                    blocks.append(buf)
                buf = [line]
            else:
                buf.append(line)
        if buf:
            blocks.append(buf)
    return blocks

def extract_channel_name(extinf):
    return normalize(extinf.split(",", 1)[-1])

# ================== BUILD OUTPUT ==================
def build_live_now():
    live_epg_channels = load_live_football_channels()
    m3u_blocks = load_m3u_blocks()

    output = ["#EXTM3U\n"]
    count = 0

    for block in m3u_blocks:
        extinf = block[0]
        name = extract_channel_name(extinf)

        if name in live_epg_channels:
            output.extend(block)
            count += 1

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.writelines(output)

    print(f"✅ OUTPUT dibuat: {count} channel LIVE sepakbola")

# ================== RUN ==================
if __name__ == "__main__":
    build_live_now()
