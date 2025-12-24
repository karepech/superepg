import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

# ================= KONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"

TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

PRELIVE = timedelta(minutes=5)     # 5 menit sebelum kickoff
POSTLIVE = timedelta(minutes=30)   # 30 menit setelah selesai

# ================= HELPER =================
def norm(txt: str) -> str:
    return re.sub(r"[^a-z0-9]", "", txt.lower())

def parse_time(t: str) -> datetime:
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    if len(t) > 14:
        try:
            sign = 1 if t[14] == "+" else -1
            hh = int(t[15:17])
            mm = int(t[17:19])
            dt = dt.replace(
                tzinfo=timezone(sign * timedelta(hours=hh, minutes=mm))
            )
        except:
            dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

epg_channels = {}
programmes = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name", "")
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""
    if name:
        epg_channels[cid] = {
            "name": name.strip(),
            "key": norm(name),
            "logo": logo
        }

for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    if not title:
        continue

    programmes.append({
        "start": parse_time(p.get("start")),
        "stop": parse_time(p.get("stop")),
        "title": title,
        "cat": p.findtext("category", "SPORT").strip(),
        "cid": p.get("channel")
    })

# ================= PARSE M3U (BLOCK UTUH) =================
with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

blocks = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        block = [lines[i]]
        i += 1
        while i < len(lines):
            block.append(lines[i])
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(block)
    i += 1

# key: normalized channel name → list of blocks
m3u_channels = {}
for block in blocks:
    m = re.search(r",(.+)$", block[0])
    if not m:
        continue
    name = m.group(1).strip()
    m3u_channels.setdefault(norm(name), []).append(block)

# ================= BUILD OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

live_now = []
next_live = []

for p in sorted(programmes, key=lambda x: x["start"]):
    cid = p["cid"]
    if cid not in epg_channels:
        continue

    epg = epg_channels[cid]
    key = epg["key"]
    if key not in m3u_channels:
        continue

    for block in m3u_channels[key]:
        logo = epg["logo"]

        # 🔴 LIVE NOW (5 menit sebelum kickoff sampai stop+30m)
        if (p["start"] - PRELIVE) <= NOW < (p["stop"] + POSTLIVE):
            title = (
                f'LIVE NOW {p["start"].strftime("%H:%M")} WIB | '
                f'{p["cat"]} | {p["title"]}'
            )
            live_now.append(
                [f'#EXTINF:-1 tvg-logo="{logo}" group-title="LIVE NOW",{title}\n']
                + block[1:]
            )

        # ⏭ NEXT LIVE (masih lama)
        elif NOW < (p["start"] - PRELIVE):
            title = (
                f'NEXT LIVE {p["start"].strftime("%d-%m %H:%M")} WIB | '
                f'{p["cat"]} | {p["title"]}'
            )
            next_live.append(
                [f'#EXTINF:-1 tvg-logo="{logo}" group-title="NEXT LIVE",{title}\n']
                + block[1:]
            )

# 🔴 LIVE NOW PALING ATAS
for blk in live_now:
    out.extend(blk)

# ⏭ NEXT LIVE
for blk in next_live:
    out.extend(blk)

# ================= SAVE =================
with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
    f.writelines(out)

print("✅ FINAL: NEXT → LIVE otomatis 5 menit sebelum kickoff")
