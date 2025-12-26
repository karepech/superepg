import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone
import re

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/dbghelp/StarHub-TV-EPG/main/starhub.xml"

MAX_CHANNEL = 5
TZ_WIB = timezone(timedelta(hours=7))

FALLBACK_URL = "https://bwifi.my.id/hls/video.m3u8"

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def parse_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S") \
        .replace(tzinfo=timezone.utc) \
        .astimezone(TZ_WIB)

# ================= LOAD EPG =================
print("📥 Download EPG StarHub")
xml = requests.get(EPG_URL, timeout=120).content
root = ET.fromstring(xml)

now = datetime.now(TZ_WIB)
h3 = now + timedelta(days=3)

live_now = []
live_next = []

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    start = parse_time(p.attrib["start"])
    stop = parse_time(p.attrib["stop"])

    if not title:
        continue

    if start <= now <= stop:
        live_now.append(title)
    elif now < start <= h3:
        live_next.append((start, title))

# unik
live_now = list(dict.fromkeys(live_now))
live_next = list(dict.fromkeys(live_next))

print(f"🟢 LIVE NOW: {len(live_now)}")
print(f"🟡 LIVE NEXT (H+3): {len(live_next)}")

# ================= LOAD M3U BLOK =================
lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines(True)

blocks = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        blk = [lines[i]]
        i += 1
        while i < len(lines):
            blk.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(blk)
    i += 1

# ================= BUILD OUTPUT =================
out = ["#EXTM3U\n"]

def add_event(title, group):
    used = 0
    key = norm(title)[:12]

    for blk in blocks:
        if used >= MAX_CHANNEL:
            break

        if key in norm(blk[0]):
            b = blk.copy()
            b[0] = re.sub(
                r",.*$",
                f",{group} | {title}\n",
                b[0]
            )
            out.extend(b)
            used += 1

    if used == 0:
        out.append(f'#EXTINF:-1 group-title="{group}",{group} | {title}\n')
        out.append(FALLBACK_URL + "\n")

# LIVE NOW
for t in live_now:
    add_event(t, "LIVE NOW")

# LIVE NEXT
for st, t in live_next:
    jam = st.strftime("%d-%m %H:%M WIB")
    add_event(f"{jam} | {t}", "LIVE NEXT")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ SELESAI: TANPA ATURAN | LIVE NOW + NEXT H+3")
