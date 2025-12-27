import requests
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from lxml import etree
from collections import defaultdict

# ===================== CONFIG =====================
BASE = Path(__file__).resolve().parents[1]

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_now.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

# kata kunci sepakbola (judul EPG)
FOOTBALL_KEYWORDS = [
    "football", "soccer", "liga", "league", "premier",
    "la liga", "serie a", "bundesliga",
    "uefa", "champions", "europa",
    "world cup", "afc", "fifa"
]

# logo yang HARUS DIABAIKAN (event / generic)
IGNORE_LOGO_KEYWORDS = [
    "timnas", "sea", "worldcup", "world cup",
    "afc", "fifa", "event", "default", "logo_bw"
]

# =================================================

def is_football(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in FOOTBALL_KEYWORDS)

def parse_epg_time(t: str) -> datetime:
    # epg_wib_sports.xml sudah WIB
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=WIB)

def extract_logo(extinf: str):
    m = re.search(r'tvg-logo="([^"]+)"', extinf, re.I)
    if not m:
        return None
    logo = m.group(1).strip().lower()
    for bad in IGNORE_LOGO_KEYWORDS:
        if bad in logo:
            return None
    return logo

# ===================== LOAD EPG =====================
def load_live_football_epg():
    print("📡 Download EPG...")
    xml = requests.get(EPG_URL, timeout=30).content
    root = etree.fromstring(xml)

    live_channels = set()

    for p in root.findall("programme"):
        title_el = p.find("title")
        if title_el is None:
            continue

        title = title_el.text or ""
        if not is_football(title):
            continue

        start = parse_epg_time(p.get("start"))
        stop  = parse_epg_time(p.get("stop"))

        if start <= NOW <= stop:
            ch = p.get("channel")
            if ch:
                live_channels.add(ch.lower())

    print(f"⚽ LIVE football EPG channels : {len(live_channels)}")
    return live_channels

# ===================== LOAD M3U =====================
def load_m3u_blocks():
    blocks = []
    buf = []

    with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
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

# ===================== BUILD =====================
def build_live_now():
    live_epg_channels = load_live_football_epg()
    m3u_blocks = load_m3u_blocks()

    # mapping logo -> list of blocks
    logo_blocks = defaultdict(list)

    for block in m3u_blocks:
        logo = extract_logo(block[0])
        if logo:
            logo_blocks[logo].append(block)

    output = ["#EXTM3U\n"]
    used = set()
    count = 0

    for logo, blocks in logo_blocks.items():
        # jika logo muncul di channel mana pun yang live di EPG
        for epg_ch in live_epg_channels:
            if any(x in logo for x in epg_ch.split("_")):
                for b in blocks:
                    key = "".join(b)
                    if key not in used:
                        output.extend(b)
                        used.add(key)
                        count += 1
                break

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.writelines(output)

    print(f"✅ OUTPUT : {count} channel LIVE sepakbola")

# ===================== RUN =====================
if __name__ == "__main__":
    build_live_now()
