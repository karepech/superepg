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

FOOTBALL_KEYWORDS = [
    "football", "soccer", "liga", "league", "premier",
    "la liga", "serie a", "bundesliga",
    "uefa", "champions", "europa",
    "world cup", "afc", "fifa"
]

IGNORE_LOGO_KEYWORDS = [
    "timnas", "sea", "worldcup", "world cup",
    "afc", "fifa", "event", "default", "logo_bw"
]

# =================================================

def is_football(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in FOOTBALL_KEYWORDS)

def parse_epg_time(t: str) -> datetime:
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(tzinfo=WIB)

def extract_logo(extinf: str):
    m = re.search(r'tvg-logo="([^"]+)"', extinf, re.I)
    if not m:
        return None
    logo = m.group(1).lower().strip()
    for bad in IGNORE_LOGO_KEYWORDS:
        if bad in logo:
            return None
    return logo

def format_time(dt: datetime):
    return dt.strftime("%H:%M WIB")

# ===================== LOAD EPG =====================
def load_live_matches():
    """
    return:
    {
      match_key: {
        title,
        start,
        stop,
        channels: set(epg_channel_ids)
      }
    }
    """
    print("📡 Download EPG...")
    xml = requests.get(EPG_URL, timeout=30).content
    root = etree.fromstring(xml)

    matches = {}

    for p in root.findall("programme"):
        title_el = p.find("title")
        if title_el is None:
            continue

        title = title_el.text or ""
        if not is_football(title):
            continue

        start = parse_epg_time(p.get("start"))
        stop  = parse_epg_time(p.get("stop"))

        if not (start <= NOW <= stop):
            continue

        ch = p.get("channel", "").lower()
        if not ch:
            continue

        match_key = f"{title.lower()}|{start.strftime('%Y%m%d%H%M')}"

        if match_key not in matches:
            matches[match_key] = {
                "title": title,
                "start": start,
                "stop": stop,
                "channels": set()
            }

        matches[match_key]["channels"].add(ch)

    print(f"⚽ LIVE matches ditemukan : {len(matches)}")
    return matches

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
    matches = load_live_matches()
    m3u_blocks = load_m3u_blocks()

    # logo -> blocks
    logo_blocks = defaultdict(list)
    for block in m3u_blocks:
        logo = extract_logo(block[0])
        if logo:
            logo_blocks[logo].append(block)

    output = ["#EXTM3U\n"]
    used_blocks = set()
    total = 0

    for match in matches.values():
        title = match["title"]
        start = match["start"]
        epg_channels = match["channels"]

        match_header = f"{title} | {format_time(start)}"

        for logo, blocks in logo_blocks.items():
            for epg_ch in epg_channels:
                # matching kasar tapi stabil: epg id vs logo url
                tokens = epg_ch.replace(".", "_").split("_")
                if any(t and t in logo for t in tokens):
                    for block in blocks:
                        key = "".join(block)
                        if key in used_blocks:
                            continue

                        # ubah judul channel → nama pertandingan
                        new_block = []
                        for line in block:
                            if line.startswith("#EXTINF"):
                                line = re.sub(r",.*$", f",{match_header}", line)
                            new_block.append(line)

                        output.extend(new_block)
                        used_blocks.add(key)
                        total += 1
                    break

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.writelines(output)

    print(f"✅ OUTPUT : {total} channel (multi-channel per match digabung)")

# ===================== RUN =====================
if __name__ == "__main__":
    build_live_now()
