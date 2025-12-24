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

def is_replay(title):
    t = title.lower()
    return any(x in t for x in ["replay","highlight","hl","hls"])

def valid_live_event(title):
    t = title.lower()
    has_live = "live" in t
    has_vs = " vs " in t
    has_md = "md" in t

    # football
    if has_live and has_vs:
        return True
    if has_live and has_md:
        return True

    # afc / uefa / cup (boleh tanpa vs)
    if has_live and any(k in t for k in [
        "afc", "uefa", "fifa", "asian cup",
        "afcon", "africa cup"
    ]):
        return True

    # badminton / voli / moto
    if has_live and any(k in t for k in [
        "badminton","bwf","voli","volley","motogp","moto"
    ]):
        return True

    return False

def duration(title):
    return RACE_MAX if "moto" in title.lower() else SOCCER_MAX

# ================= LOAD EPG =================
root = ET.fromstring(requests.get(EPG_URL, timeout=120).content)

epg_ch = {}
programs = []

for ch in root.findall("channel"):
    cid = ch.get("id")
    name = ch.findtext("display-name","").strip()
    logo = ch.find("icon").get("src") if ch.find("icon") is not None else ""
    epg_ch[cid] = {"name": name, "key": norm(name), "logo": logo}

for p in root.findall("programme"):
    programs.append({
        "cid": p.get("channel"),
        "start": parse_time(p.get("start")),
        "title": p.findtext("title","").strip()
    })

# ================= PARSE M3U =================
lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines()
blocks, i = [], 0

while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        b = [lines[i]+"\n"]
        i += 1
        while i < len(lines):
            b.append(lines[i]+"\n")
            if lines[i].startswith("http"):
                break
            i += 1
        blocks.append(b)
    i += 1

m3u = {}
for b in blocks:
    m = re.search(r",(.+)$", b[0])
    if m:
        m3u[norm(m.group(1))] = b

# ================= BUILD =================
out = [f'#EXTM3U url-tvg="{EPG_URL}"\n']
next_events = {}

for p in programs:
    if p["cid"] not in epg_ch:
        continue

    ch = epg_ch[p["cid"]]
    if ch["key"] not in m3u:
        continue

    title = p["title"]
    if is_replay(title):
        continue
    if not valid_live_event(title):
        continue

    start = p["start"]
    end = start + duration(title)
    live_start = start - PRELIVE
    blk = m3u[ch["key"]]

    # LIVE NOW
    if live_start <= NOW <= end:
        out.extend([
            f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="LIVE NOW",'
            f'LIVE NOW {start.strftime("%H:%M")} WIB | {title}\n'
        ] + blk[1:])

    # LIVE NEXT
    elif NOW < live_start:
        next_events.setdefault(norm(title), []).append({
            "title": title,
            "start": start,
            "logo": ch["logo"]
        })

# NEXT LIVE (1 event = 1 channel acak)
for ev in sorted(next_events.values(), key=lambda x: x[0]["start"]):
    pick = random.choice(ev)
    out.append(
        f'#EXTINF:-1 tvg-logo="{pick["logo"]}" group-title="LIVE NEXT",'
        f'LIVE NEXT {pick["start"].strftime("%d-%m %H:%M")} WIB | {pick["title"]}\n'
    )
    out.append(NEXT_LIVE_URL + "\n")

OUTPUT_M3U.write_text("".join(out), encoding="utf-8")
print("✅ DONE: ONLY LIVE NOW & LIVE NEXT")
