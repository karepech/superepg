import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path

# ================= CONFIG =================
BASE = Path(__file__).resolve().parent.parent

INPUT_M3U = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_now.m3u"   # OUTPUT GABUNG

GOAL_URL = "https://www.goal.com/id/berita/jadwal-tv-hari-ini-siaran-langsung"

TZ_OFFSET = 7  # WIB
MAX_CHANNEL_PER_MATCH = 5

BLOCK_WORDS = [
    "md", "highlight", "highlights", "classic",
    "replay", "rerun", "recap", "full match"
]

# ================= HELPERS =================
def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())

def is_replay(title: str) -> bool:
    t = title.lower()
    if any(w in t for w in BLOCK_WORDS):
        return True

    # tahun < 2025 dianggap ulangan
    years = re.findall(r"(19\d{2}|20\d{2})", t)
    for y in years:
        if int(y) < 2025:
            return True
    return False

def is_match(title: str) -> bool:
    return bool(re.search(r"\bvs\b|\sv\s", title.lower()))

# ================= LOAD GOAL =================
print("📥 Ambil jadwal dari GOAL Indonesia")
html = requests.get(GOAL_URL, timeout=30).text
soup = BeautifulSoup(html, "html.parser")

today = (datetime.utcnow() + timedelta(hours=TZ_OFFSET)).date()

events = []  # list of {date, title}

current_date = None

for el in soup.find_all(["h2", "tr"]):
    # Header tanggal (contoh: 27 Desember 2025)
    if el.name == "h2":
        text = el.get_text(strip=True)
        m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
        if m:
            try:
                current_date = datetime.strptime(
                    m.group(0), "%d %B %Y"
                ).date()
            except:
                current_date = None

    # Baris pertandingan
    if el.name == "tr" and current_date:
        cols = [c.get_text(" ", strip=True) for c in el.find_all("td")]
        if len(cols) < 2:
            continue

        match = cols[1]
        league = cols[2] if len(cols) > 2 else ""

        title = f"{league}: {match}".strip(" :")

        if not is_match(title):
            continue
        if is_replay(title):
            continue

        events.append({
            "date": current_date,
            "title": title
        })

# ================= LOAD M3U (BLOK UTUH) =================
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

# ================= BUILD OUTPUT (GABUNG) =================
out = ["#EXTM3U\n"]

def append_event(event_date, title):
    key = norm(title)
    used = 0

    if event_date == today:
        label = "LIVE NOW"
    elif today < event_date <= today + timedelta(days=3):
        label = f"LIVE NEXT | {event_date.strftime('%d-%m-%Y')}"
    else:
        return

    for blk in blocks:
        if used >= MAX_CHANNEL_PER_MATCH:
            break

        # nama channel tetap, hanya group-title yang diubah
        if key[:8] in norm(blk[0]):
            new_blk = blk.copy()

            if 'group-title="' in new_blk[0]:
                new_blk[0] = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{label} | {title}"',
                    new_blk[0]
                )

            out.extend(new_blk)
            used += 1

# urutkan event berdasarkan tanggal
events.sort(key=lambda x: x["date"])

for ev in events:
    append_event(ev["date"], ev["title"])

# fallback kalau kosong
if len(out) == 1:
    out.append('#EXTINF:-1 group-title="LIVE",LIVE | Tidak ada pertandingan\n')
    out.append("https://bwifi.my.id/hls/video.m3u8\n")

# ================= SAVE =================
OUTPUT_M3U.write_text("".join(out), encoding="utf-8")

print("✅ SELESAI — LIVE NOW + LIVE NEXT digabung")
