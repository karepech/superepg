import requests
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from lxml import html, etree
from collections import defaultdict

# ================= CONFIG =================
BASE = Path(__file__).resolve().parents[1]

INPUT_M3U  = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_now.m3u"

EPG_URL  = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
GOAL_URL = "https://www.goal.com/id/jadwal-bola-hari-ini"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

LIVE_DURATION = timedelta(hours=2, minutes=30)

IGNORE_LOGO_KEYWORDS = [
    "timnas", "sea", "event", "default", "logo_bw"
]

# ================= UTIL =================
def extract_logo(extinf):
    m = re.search(r'tvg-logo="([^"]+)"', extinf, re.I)
    if not m:
        return None
    logo = m.group(1).lower()
    for bad in IGNORE_LOGO_KEYWORDS:
        if bad in logo:
            return None
    return logo

def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()

# ================= LOAD GOAL =================
def load_goal_matches():
    print("🌐 Ambil jadwal dari GOAL...")
    r = requests.get(GOAL_URL, timeout=30)
    doc = html.fromstring(r.content)

    matches = []

    rows = doc.xpath("//table//tr")[1:]
    for row in rows:
        cols = [c.text_content().strip() for c in row.xpath("./td")]
        if len(cols) < 4:
            continue

        time_str, match, _, station = cols[:4]

        if not re.match(r"\d{2}:\d{2}", time_str):
            continue

        kickoff = datetime.strptime(time_str, "%H:%M").replace(
            year=NOW.year, month=NOW.month, day=NOW.day, tzinfo=WIB
        )

        if kickoff > NOW:
            continue

        if NOW > kickoff + LIVE_DURATION:
            continue

        matches.append({
            "title": match,
            "kickoff": kickoff,
            "station": normalize(station)
        })

    print(f"⚽ LIVE dari GOAL : {len(matches)} pertandingan")
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
            live.add(p.get("channel", "").lower())

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
    goal_matches = load_goal_matches()
    epg_live = load_epg_live_channels()
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
            if station not in logo:
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

    print(f"✅ OUTPUT FINAL : {total} channel LIVE (GOAL + EPG)")

# ================= RUN =================
if __name__ == "__main__":
    build_live_now()
