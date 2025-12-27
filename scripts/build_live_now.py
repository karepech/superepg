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

# endpoint JSON GOAL (dipakai web aslinya)
GOAL_API = "https://www.goal.com/api/schedules"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)
LIVE_DURATION = timedelta(hours=2, minutes=30)

IGNORE_LOGO_KEYWORDS = ["timnas", "sea", "event", "default", "logo_bw"]

# ================= UTIL =================
def normalize(t):
    return re.sub(r"\s+", " ", t.lower()).strip()

def extract_logo(extinf):
    m = re.search(r'tvg-logo="([^"]+)"', extinf, re.I)
    if not m:
        return None
    logo = m.group(1).lower()
    for bad in IGNORE_LOGO_KEYWORDS:
        if bad in logo:
            return None
    return logo

# ================= LOAD GOAL =================
def load_goal_live_matches():
    print("🌐 Ambil jadwal GOAL (JSON)...")
    r = requests.get(GOAL_API, timeout=30)
    data = r.json()

    matches = []

    for day in data.get("days", []):
        for m in day.get("matches", []):
            kickoff = datetime.fromisoformat(
                m["kickoff"].replace("Z", "+00:00")
            ).astimezone(WIB)

            if not (kickoff <= NOW <= kickoff + LIVE_DURATION):
                continue

            matches.append({
                "title": m["homeTeam"]["name"] + " vs " + m["awayTeam"]["name"],
                "kickoff": kickoff,
                "station": normalize(" ".join(m.get("tvChannels", [])))
            })

    print(f"⚽ LIVE GOAL : {len(matches)}")
    return matches

# ================= LOAD EPG =================
def load_epg_live_channels():
    xml = requests.get(EPG_URL, timeout=30).content
    root = etree.fromstring(xml)

    live = set()
    for p in root.findall("programme"):
        start = datetime.strptime(p.get("start")[:14], "%Y%m%d%H%M%S").replace(tzinfo=WIB)
        stop  = datetime.strptime(p.get("stop")[:14], "%Y%m%d%H%M%S").replace(tzinfo=WIB)
        if start <= NOW <= stop:
            live.add(p.get("channel","").lower())
    return live

# ================= LOAD M3U =================
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
    goal_matches = load_goal_live_matches()
    if not goal_matches:
        print("❌ Tidak ada LIVE dari GOAL")
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

    for m in goal_matches:
        title = f"{m['title']} | {m['kickoff'].strftime('%H:%M WIB')}"
        station = m["station"]

        for logo, blocks in logo_blocks.items():
            if station and station not in logo:
                continue

            for b in blocks:
                key = "".join(b)
                if key in used:
                    continue

                new_block = []
                for line in b:
                    if line.startswith("#EXTINF"):
                        line = re.sub(r",.*$", f",{title}", line)
                    new_block.append(line)

                output.extend(new_block)
                used.add(key)
                total += 1

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.writelines(output)

    print(f"✅ OUTPUT : {total} channel LIVE (HYBRID FIX)")

# ================= RUN =================
if __name__ == "__main__":
    build_live_now()
