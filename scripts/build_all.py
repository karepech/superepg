import re, random, requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent
INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_all.m3u"

EPG_URL = "https://raw.githubusercontent.com/karepech/Epgku/main/epg_wib_sports.xml"
NEXT_LIVE_URL = "https://bwifi.my.id/hls/video.m3u8"

TZ = timezone(timedelta(hours=7))
NOW = datetime.now(TZ)

PRELIVE = timedelta(minutes=5)
SOCCER_MAX = timedelta(hours=2)
RACE_MAX = timedelta(hours=4)

# ================= HELPER =================
def norm(t): 
    return re.sub(r"[^a-z0-9]", "", t.lower())

def parse_time(t):
    dt = datetime.strptime(t[:14], "%Y%m%d%H%M%S")
    tz = timezone.utc
    if len(t) > 14:
        sign = 1 if t[14] == "+" else -1
        tz = timezone(sign * timedelta(hours=int(t[15:17]), minutes=int(t[17:19])))
    return dt.replace(tzinfo=tz).astimezone(TZ)

def has_year(title):
    return bool(re.search(r"20\d{2}/20\d{2}", title))

def is_replay(title):
    t = title.lower()
    return any(x in t for x in ["replay", "highlight", "hl", "hls"])

def is_football(title):
    t = title.lower()
    return any(x in t for x in ["football", "soccer", "liga", "premier", "uefa", "serie", "laliga", "bundesliga"])

def football_valid(title):
    t = title.lower()
    has_vs = " vs " in t or " vs." in t
    has_live = "live" in t
    has_md = "md" in t

    if has_live and has_vs:
        return True
    if has_live and has_md:
        return True

    # ❌ hide rules
    if has_vs and not has_live:
        return False
    if has_md and not has_live:
        return False
    if has_year(title) and not has_live:
        return False

    return False

def event_duration(title):
    return RACE_MAX if "motogp" in title.lower() else SOCCER_MAX

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

channels = {}
programs = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name", "")
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""
    channels[cid] = {"name": name, "key": norm(name), "logo": logo}

for p in root.findall("programme"):
    programs.append({
        "start": parse_time(p.get("start")),
        "stop": parse_time(p.get("stop")),
        "title": p.findtext("title", ""),
        "cid": p.get("channel")
    })

# ================= PARSE M3U =================
lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines()
blocks = []
i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        blk = [lines[i] + "\n"]
        i += 1
        while i < len(lines):
            blk.append(lines[i] + "\n")
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(blk)
    i += 1

m3u = {}
for b in blocks:
    m = re.search(r",(.+)$", b[0])
    if m:
        m3u[norm(m.group(1))] = b

# ================= BUILD =================
live_now = []
next_live = {}

for p in programs:
    if p["cid"] not in channels:
        continue

    ch = channels[p["cid"]]
    if ch["key"] not in m3u:
        continue

    title = p["title"]
    if is_replay(title):
        continue

    if is_football(title) and not football_valid(title):
        continue

    start = p["start"]
    dur = event_duration(title)
    live_start = start - PRELIVE
    live_end = start + dur

    if live_start <= NOW <= live_end:
        live_now.append([
            f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="LIVE NOW",'
            f'LIVE NOW {start.strftime("%H:%M")} WIB | {title}\n'
        ] + m3u[ch["key"]][1:])

    elif NOW < live_start:
        k = norm(title)
        next_live.setdefault(k, []).append({
            "title": title,
            "start": start,
            "logo": ch["logo"]
        })

# ================= OUTPUT =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']

# LIVE NOW (ALL)
for b in live_now:
    out.extend(b)

# NEXT LIVE (RANDOM CHANNEL)
for ev in sorted(next_live.values(), key=lambda x: x[0]["start"]):
    pick = random.choice(ev)
    out.append(
        f'#EXTINF:-1 tvg-logo="{pick["logo"]}" group-title="NEXT LIVE",'
        f'NEXT LIVE {pick["start"].strftime("%d-%m %H:%M")} WIB | {pick["title"]}\n'
    )
    out.append(NEXT_LIVE_URL + "\n")

OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ DONE: Football rules enforced, LIVE clean")
