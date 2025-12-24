#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import random
from pathlib import Path
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import requests

# ================= CONFIG =================
TZ = timezone(timedelta(hours=7))  # WIB
NOW = datetime.now(TZ)

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
NEXT_EVENT_URL = "https://bwifi.my.id/hls/video.m3u8"

BASE = Path(__file__).resolve().parent.parent
INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

NEXT_RANGE = timedelta(days=3)
SOCCER_LIMIT = timedelta(hours=2)
RACE_LIMIT = timedelta(hours=4)

# ================= GUARD =================
if not INPUT_M3U.exists():
    print("[FATAL] live_epg_sports.m3u TIDAK DITEMUKAN")
    sys.exit(1)

# ================= HELPERS =================
def epg_time(t):
    return datetime.strptime(t[:14], "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc).astimezone(TZ)

def log_skip(reason, title):
    print(f"[SKIP:{reason}] {title}")

def has_vs(t): return bool(re.search(r"\bvs\b", t, re.I))
def has_live(t): return bool(re.search(r"\blive\b", t, re.I))
def has_md(t): return bool(re.search(r"\bmd\d*\b", t, re.I))
def has_year(t): return bool(re.search(r"20\d{2}", t))
def is_replay(t): return bool(re.search(r"(hl|highlight|replay|rerun)", t, re.I))

def sport_type(t):
    t = t.lower()
    if "motogp" in t or "race" in t:
        return "RACE"
    if "badminton" in t or "bwf" in t or "voli" in t or "volley" in t:
        return "FLEX"
    return "SOCCER"

def clean_title(t):
    return re.sub(r"\s+", " ", t).strip()

# ================= LOAD CHANNEL =================
channels = []
for line in INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines():
    if line.startswith("#EXTINF"):
        cur = {"ext": line, "name": line.split(",")[-1], "logo": ""}
        m = re.search(r'tvg-logo="([^"]+)"', line)
        if m: cur["logo"] = m.group(1)
    elif line.startswith("http"):
        cur["url"] = line
        channels.append(cur)

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=30).content)

programs = []
for p in root.findall("programme"):
    raw = p.findtext("title", "").strip()
    if not raw:
        continue

    title = clean_title(raw)
    start = epg_time(p.attrib["start"])
    stop = epg_time(p.attrib["stop"])
    sport = sport_type(title)

    # ===== FILTER =====
    if is_replay(title):
        log_skip("REPLAY", title)
        continue

    if has_md(title) and not has_live(title):
        log_skip("MD_NO_LIVE", title)
        continue

    if has_year(title) and not has_live(title):
        log_skip("YEAR_NO_LIVE", title)
        continue

    if sport == "SOCCER":
        if not has_vs(title):
            log_skip("SOCCER_NO_VS", title)
            continue

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
    sport = p["sport"]

    if s.date() == NOW.date() and NOW >= s:
        limit = RACE_LIMIT if sport == "RACE" else SOCCER_LIMIT
        if NOW - s <= limit:
            live_now.append(p)
        else:
            log_skip("EXPIRED", p["title"])
        continue

    if NOW < s <= NOW + NEXT_RANGE:
        key = p["title"].lower()
        if key not in live_next:
            live_next[key] = p

# ===== FALLBACK beIN =====
if not live_now:
    print("[FALLBACK] beIN Sports 1 dipaksa tampil")
    live_now.append({
        "title": "Live Event",
        "start": NOW,
        "stop": NOW + timedelta(hours=2),
        "sport": "SOCCER"
    })

# ================= BUILD M3U =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"']

def add(group, p, ch, url):
    jam = p["start"].strftime("%H:%M")
    name = f'{group} | {jam} WIB | {p["title"]}'
    out.append(f'#EXTINF:-1 group-title="{group}" tvg-logo="{ch["logo"]}",{name}')
    out.append(url)

random.shuffle(channels)

# LIVE NOW → semua channel
for p in live_now:
    for ch in channels:
        add("LIVE NOW", p, ch, ch["url"])

# LIVE NEXT → 1 channel / event
for p in live_next.values():
    ch = random.choice(channels)
    add("LIVE NEXT", p, ch, NEXT_EVENT_URL)

OUTPUT_M3U.write_text("\n".join(out), encoding="utf-8")

print(f"[DONE] LIVE NOW={len(live_now)} | LIVE NEXT={len(live_next)}")
