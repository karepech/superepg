import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================= CONFIG =================
EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
INPUT_M3U = "live_epg_sports.m3u"
OUTPUT_M3U = "live_all.m3u"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

# ================= KEYWORDS =================
REPLAY_KEYWORDS = [
    "MD",
    "HIGHLIGHT",
    "HIGHLIGHTS",
    "CLASSIC",
    "REPLAY",
    "MATCH HLS",
    "HLS"
]

# ================= LOAD EPG =================
print("⏳ Download EPG...")
xml_text = requests.get(EPG_URL, timeout=30).text
root = ET.fromstring(xml_text)

# ================= PARSE EPG =================
events = []

for prog in root.findall("programme"):
    title_el = prog.find("title")
    if title_el is None:
        continue

    title = title_el.text.strip()
    title_upper = title.upper()

    # ❌ skip replay
    if any(k in title_upper for k in REPLAY_KEYWORDS):
        continue

    # ✅ must be live match
    if "(L)" not in title_upper and " VS " not in title_upper:
        continue

    # parse time
    start = prog.attrib.get("start")
    if not start:
        continue

    try:
        start_dt = datetime.strptime(start[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).astimezone(TZ)
    except:
        continue

    channel_id = prog.attrib.get("channel", "")

    events.append({
        "title": title,
        "start": start_dt,
        "channel": channel_id
    })

print(f"✅ LIVE EVENT ditemukan: {len(events)}")

# ================= LOAD M3U =================
m3u_lines = Path(INPUT_M3U).read_text(encoding="utf-8", errors="ignore").splitlines()

channels = []
current = {}

for line in m3u_lines:
    if line.startswith("#EXTINF"):
        current = {"extinf": line, "url": ""}
    elif line.startswith("http"):
        current["url"] = line
        channels.append(current)
        current = {}

# ================= MATCH EVENT ↔ CHANNEL =================
output = ["#EXTM3U"]

live_count = 0

for ev in events:
    ev_title_upper = ev["title"].upper()

    matched = False

    for ch in channels:
        ch_name = ch["extinf"].upper()

        if any(word in ch_name for word in ev_title_upper.split(" VS ")):
            name = f"LIVE | {ev['start'].strftime('%H:%M')} WIB | {ev['title']}"

            extinf = ch["extinf"]

            # ganti nama saja, URL tetap UTUH
            extinf = extinf.split(",", 1)[0] + "," + name

            output.append(extinf)
            output.append(ch["url"])

            live_count += 1
            matched = True

    if not matched:
        continue

# ================= WRITE OUTPUT =================
Path(OUTPUT_M3U).write_text("\n".join(output), encoding="utf-8")

print(f"🎉 LIVE EVENT ditulis: {live_count} channel")
