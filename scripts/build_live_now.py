import requests
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from lxml import etree

# ================= CONFIG =================
BASE = Path(__file__).resolve().parents[1]

INPUT_M3U  = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_now.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
SOFA_LIVE = "https://api.sofascore.com/api/v1/sport/football/events/live"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)
LIVE_DURATION = timedelta(hours=3)

IGNORE_LOGO_KEYWORDS = ["timnas", "sea", "event", "default", "logo_bw"]

# ================= UTIL =================
def extract_logo(extinf):
    m = re.search(r'tvg-logo="([^"]+)"', extinf)
    if not m:
        return None
    logo = m.group(1).lower()
    for bad in IGNORE_LOGO_KEYWORDS:
        if bad in logo:
            return None
    return logo

# ================= SOFASCORE =================
def load_sofa_live_matches():
    print("🌐 Ambil LIVE dari SofaScore...")
    r = requests.get(SOFA_LIVE, timeout=30)
    data = r.json()

    matches = []

    for e in data.get("events", []):
        start = datetime.fromtimestamp(e["startTimestamp"], tz=timezone.utc).astimezone(WIB)

        if not (start <= NOW <= start + LIVE_DURATION):
            continue

        matches.append({
            "title": f"{e['homeTeam']['name']} vs {e['awayTeam']['name']}",
            "start": start
        })

    print(f"⚽ LIVE SofaScore : {len(matches)}")
    return matches

# ================= EPG =================
def load_epg_live():
    xml = requests.get(EPG_URL, timeout=30).content
    root = etree.fromstring(xml)

    live = set()
    for p in root.findall("programme"):
        s = datetime.strptime(p.get("start")[:14], "%Y%m%d%H%M%S").replace(tzinfo=WIB)
        e = datetime.strptime(p.get("stop")[:14], "%Y%m%d%H%M%S").replace(tzinfo=WIB)
        if s <= NOW <= e:
            live.add(p.get("channel","").lower())
    return live

# ================= M3U =================
def load_m3u_blocks():
    blocks, buf = [], []
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

# ================= BUILD =================
def build_live_now():
    matches = load_sofa_live_matches()
    if not matches:
        print("❌ Tidak ada LIVE match")
        return

    m3u_blocks = load_m3u_blocks()
    logo_blocks = defaultdict(list)

    for b in m3u_blocks:
        logo = extract_logo(b[0])
        if logo:
            logo_blocks[logo].append(b)

    output = ["#EXTM3U\n"]
    used = set()
    total = 0

    for m in matches:
        header = f"{m['title']} | {m['start'].strftime('%H:%M WIB')}"

        for logo, blocks in logo_blocks.items():
            for b in blocks:
                key = "".join(b)
                if key in used:
                    continue

                new_block = []
                for line in b:
                    if line.startswith("#EXTINF"):
                        line = re.sub(r",.*$", f",{header}", line)
                    new_block.append(line)

                output.extend(new_block)
                used.add(key)
                total += 1

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.writelines(output)

    print(f"✅ OUTPUT LIVE : {total} channel")

# ================= RUN =================
if __name__ == "__main__":
    build_live_now()
