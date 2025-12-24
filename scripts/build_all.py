#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import requests

# ================= CONFIG =================
TZ = timezone(timedelta(hours=7))
NOW = datetime.now(TZ)

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
NEXT_EVENT_URL = "https://bwifi.my.id/hls/video.m3u8"

BASE = Path(__file__).resolve().parent.parent
INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

SOCCER_LIMIT = timedelta(hours=2)
RACE_LIMIT = timedelta(hours=4)
NEXT_RANGE = timedelta(days=3)

# ================= GUARD =================
if not INPUT_M3U.exists():
    print("[FATAL] live_epg_sports.m3u tidak ditemukan")
    sys.exit(1)

# ================= HELPERS =================
def epg_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc).astimezone(TZ)

def has(p, r): return re.search(r, p, re.I)
def is_replay(t): return has(t, r"(hl|highlight|replay|rerun)")
def has_vs(t): return has(t, r"\bvs\b")
def has_live(t): return has(t, r"\blive\b")
def has_md(t): return has(t, r"\bmd\d*\b")
def has_year(t): return has(t, r"20\d{2}")

def sport_type(t):
    t = t.lower()
    if "motogp" in t or "race" in t:
        return "RACE"
    if "badminton" in t or "bwf" in t or "voli" in t:
        return "FLEX"
    return "SOCCER"

# ================= LOAD CHANNEL =================
channels = []
cur = None
for l in INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines():
    if l.startswith("#EXTINF"):
        cur = {"ext": l, "name": l.split(",")[-1], "logo": ""}
        m = re.search(r'tvg-logo="([^"]+)"', l)
        if m: cur["logo"] = m.group(1)
    elif l.startswith("http") and cur:
        cur["url"] = l
        channels.append(cur)
        cur = None

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=30).content)

programs = []
for p in root.findall("programme"):
    title = p.findtext("title", "").strip()
    if not title:
        continue

    start = epg_time(p.attrib["start"])
    stop = epg_time(p.attrib["stop"])
    sport = sport_type(title)

    # ===== FILTER =====
    if is_replay(title): continue
    if has_md(title) and not has_live(title): continue
    if has_year(title) and not has_live(title): continue
    if sport == "SOCCER" and not has_vs(title): continue

    programs.append({
        "title": title,
        "start": start,
        "stop": stop,
        "sport": sport
    })

# ================= CLASSIFY =================
live_now = []
live_next = {}

for p in programs:
    s, e = p["start"], p["stop"]

    if s.date() == NOW.date() and NOW >= s:
        limit = RACE_LIMIT if p["sport"] == "RACE" else SOCCER_LIMIT
        if NOW - s <= limit:
            live_now.append(p)
        continue

    if NOW < s <= NOW + NEXT_RANGE:
        live_next.setdefault(p["title"].lower(), p)

# ================= BUILD M3U =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"']

def add(group, p, ch, url):
    jam = p["start"].strftime("%H:%M")
    name = f'{group} | {jam} WIB | {p["title"]}'
    out.append(f'#EXTINF:-1 group-title="{group}" tvg-logo="{ch["logo"]}",{name}')
    out.append(url)

# ===== LIVE NOW (max 3 channel / event) =====
for p in live_now:
    used = 0
    for ch in channels:
        add("LIVE NOW", p, ch, ch["url"])
        used += 1
        if used >= 3:
            break

# ===== FALLBACK =====
if not live_now:
    ch = channels[0]
    out.append(f'#EXTINF:-1 group-title="LIVE NOW",{ "LIVE EVENT" }')
    out.append(ch["url"])

# ===== LIVE NEXT (1 event = 1 baris) =====
for p in live_next.values():
    ch = channels[0]
    add("LIVE NEXT", p, ch, NEXT_EVENT_URL)

OUTPUT_M3U.write_text("\n".join(out), encoding="utf-8")
print("[DONE] playlist stabil, tidak duplikat, tidak ngacak")
