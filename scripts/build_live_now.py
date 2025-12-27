import requests
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ================= CONFIG =================
BASE = Path(__file__).resolve().parents[1]

INPUT_M3U  = BASE / "live_epg_sports.m3u"
OUTPUT_M3U = BASE / "live_now.m3u"

WIB = timezone(timedelta(hours=7))
NOW = datetime.now(WIB)

# ================= SOFASCORE =================
def load_sofa_today_matches():
    today = NOW.strftime("%Y-%m-%d")
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{today}"

    print("🌐 Ambil jadwal SofaScore hari ini...")
    r = requests.get(url, timeout=30)
    data = r.json()

    matches = []

    for e in data.get("events", []):
        start = datetime.fromtimestamp(
            e["startTimestamp"], tz=timezone.utc
        ).astimezone(WIB)

        status = e.get("status", {}).get("type", "")

        matches.append({
            "title": f"{e['homeTeam']['name']} vs {e['awayTeam']['name']}",
            "start": start,
            "status": status
        })

    matches.sort(key=lambda x: x["start"])
    print(f"⚽ Match hari ini : {len(matches)}")
    return matches

# ================= M3U =================
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
    print(f"📺 Total channel M3U : {len(blocks)}")
    return blocks

# ================= BUILD =================
def build_live_now():
    matches = load_sofa_today_matches()
    if not matches:
        print("❌ Tidak ada jadwal hari ini")
        return

    blocks = load_m3u_blocks()
    if not blocks:
        print("❌ M3U kosong")
        return

    output = ["#EXTM3U\n"]
    total = 0

    for m in matches:
        if m["status"] == "inprogress":
            header = f"🔴 LIVE | {m['title']} | {m['start'].strftime('%H:%M WIB')}"
        else:
            header = f"{m['title']} | {m['start'].strftime('%H:%M WIB')}"

        for block in blocks:
            new_block = []
            for line in block:
                if line.startswith("#EXTINF"):
                    line = re.sub(r",.*$", f",{header}", line)
                new_block.append(line)

            output.extend(new_block)
            total += 1

    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.writelines(output)

    print(f"✅ OUTPUT DIBUAT : {total} baris channel")

# ================= RUN =================
if __name__ == "__main__":
    build_live_now()
