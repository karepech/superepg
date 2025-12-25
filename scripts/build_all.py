#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import requests
from collections import defaultdict

# ================= CONFIG =================
TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
CUSTOM_URL = "https://bwifi.my.id/hls/video.m3u8"

BASE = Path(__file__).resolve().parent.parent
INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

MAX_CHANNEL_PER_EVENT = 5
PRELIVE_MINUTES = 5

SOCCER_MAX = timedelta(hours=2)
RACE_MAX = timedelta(hours=4)
NEXT_RANGE = timedelta(days=3)

# ================= GUARD =================
if not INPUT_M3U.exists():
    print("[FATAL] live_epg_sports.m3u tidak ditemukan")
    sys.exit(1)

# ================= HELPERS =================
def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

def epg_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S") \
        .replace(tzinfo=timezone.utc).astimezone(TZ)

def has(pattern, text):
    return re.search(pattern, text, re.I)

def is_replay(t):
    return has(r"(hl|highlight|replay|rerun|review|recap)", t)

def has_vs(t):
    return has(r"\bvs\b", t)

def has_live(t):
    return has(r"\blive\b", t)

def has_md(t):
    return has(r"\bmd\d*\b", t)

def has_year(t):
    return has(r"\b20\d{2}\b", t)

def sport_type(t):
    t = t.lower()
    if "motogp" in t or "race" in t:
        return "RACE"
    if "badminton" in t or "bwf" in t or "voli" in t or "volley" in t:
        return "FLEX"
    return "SOCCER"

# ================= LOAD CHANNEL BLOCKS =================
channels = []
cur = None

for line in INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines(True):
    if line.startswith("#EXTINF"):
        cur = {"block": [line], "name": line.split(",")[-1].strip()}
    elif cur and not line.startswith("http"):
        cur["block"].append(line)
    elif cur and line.startswith("http"):
        cur["block"].append(line)
        channels.append(cur)
        cur = None

# index channel blocks by normalized name
channel_map = defaultdict(list)
for ch in channels:
    channel_map[norm(ch["name"])].append(ch["block"])

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=60).content)

events = []
for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    if not title:
        continue

    # FILTER KETAT
    if is_replay(title):
        continue
    if has_md(title) and not has_live(title):
        continue
    if has_year(title) and not has_live(title):
        continue
    if sport_type(title) == "SOCCER" and not has_vs(title):
        continue

    start = epg_time(p.get("start"))
    stop = epg_time(p.get("stop"))

    events.append({
        "title": title,
        "start": start,
        "stop": stop,
        "sport": sport_type(title),
        "key": norm(title)
    })

# ================= GROUP EVENT =================
grouped = defaultdict(list)
for e in events:
    # satu event = judul + jam kickoff
    k = f"{e['key']}_{e['start'].strftime('%Y%m%d%H%M')}"
    grouped[k].append(e)

# ================= BUILD =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

def add_event_block(group, title, start):
    jam = start.strftime("%H:%M")
    out.append(f'#EXTINF:-1 group-title="{group}",{group} {jam} WIB | {title}\n')
    out.append(CUSTOM_URL + "\n")

def add_channel_blocks(group, title, start, blocks):
    jam = start.strftime("%H:%M")
    for blk in blocks:
        # ganti judul
        header = re.sub(r",.*$", f",{group} {jam} WIB | {title}\n", blk[0])
        out.append(header)
        out.extend(blk[1:])

# ================= PROCESS EVENTS =================
for ev_list in grouped.values():
    ev = ev_list[0]
    start = ev["start"]
    sport = ev["sport"]

    # cek expired
    max_dur = RACE_MAX if sport == "RACE" else SOCCER_MAX
    if NOW - start > max_dur:
        continue

    minutes_to_start = (start - NOW).total_seconds() / 60

    # ================= EVENT MASIH LAMA =================
    if minutes_to_start > PRELIVE_MINUTES:
        # NEXT LIVE jika H+1..H+3
        if NOW < start <= NOW + NEXT_RANGE:
            add_event_block("LIVE NEXT", ev["title"], start)
        continue

    # ================= EVENT SUDAH DEKAT / LIVE =================
    # ≤ 5 menit sebelum kickoff sampai selesai → FULL CHANNEL
    used = 0
    for ch_name, ch_blocks in channel_map.items():
        if used >= MAX_CHANNEL_PER_EVENT:
            break
        for blk in ch_blocks:
            add_channel_blocks("LIVE NOW", ev["title"], start, [blk])
            used += 1
            if used >= MAX_CHANNEL_PER_EVENT:
                break

# ================= FALLBACK =================
if len(out) <= 1:
    out.append('#EXTINF:-1 group-title="LIVE NOW",LIVE EVENT\n')
    out.append(CUSTOM_URL + "\n")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ BUILD OK | aturan 5 menit → channel utuh diterapkan")
