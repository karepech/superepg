#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# =========================
# CONFIG
# =========================
INPUT_M3U = Path("live_epg_sports.m3u")
OUTPUT_M3U = Path("live_all.m3u")

TZ_WIB = timezone(timedelta(hours=7))
NOW = datetime.now(TZ_WIB)

# Liga besar Eropa
VALID_LEAGUES = [
    "premier league",
    "la liga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "uefa",
    "champions league",
    "europa league",
    "conference league"
]

# =========================
# FILTER LOGIC
# =========================
def is_replay(title: str) -> bool:
    t = title.lower()

    # MD = ULANGAN MUTLAK
    if re.search(r"\bmd\b", t):
        return True

    replay_words = [
        "highlight", "highlights",
        "classic",
        "hls",
        "replay",
        "rerun",
        "recap",
        "review",
        "full match",
        "mini match"
    ]

    return any(w in t for w in replay_words)


def is_live_event(title: str) -> bool:
    t = title.lower()

    # (L) = LIVE PALING KUAT
    if "(l)" in t:
        return True

    # Ulangan dibuang
    if is_replay(t):
        return False

    # Harus pertandingan
    if " vs " not in t and " v " not in t:
        return False

    # Harus liga besar
    if not any(lg in t for lg in VALID_LEAGUES):
        return False

    return True


# =========================
# M3U PARSER
# =========================
def parse_m3u(lines):
    channels = []
    buf = []

    for line in lines:
        if line.startswith("#EXTINF"):
            buf = [line]
        elif line.strip().startswith("http"):
            buf.append(line)
            channels.append(buf)
            buf = []
        else:
            if buf:
                buf.append(line)

    return channels


# =========================
# MAIN
# =========================
def main():
    if not INPUT_M3U.exists():
        raise FileNotFoundError(f"{INPUT_M3U} tidak ditemukan")

    lines = INPUT_M3U.read_text(encoding="utf-8", errors="ignore").splitlines()
    channels = parse_m3u(lines)

    live_now = []

    for block in channels:
        extinf = block[0]

        # Ambil title
        m = re.search(r",(.*)$", extinf)
        title = m.group(1).strip() if m else ""

        if not is_live_event(title):
            continue

        # LIVE NOW (tanpa hitung jam dulu)
        new_extinf = (
            '#EXTINF:-1 group-title="LIVE NOW",'
            f'LIVE NOW | {title}'
        )

        live_now.append([new_extinf] + block[1:])

    # =========================
    # OUTPUT
    # =========================
    out = ["#EXTM3U"]

    for ch in live_now:
        out.extend(ch)

    OUTPUT_M3U.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"✅ LIVE EVENT dibuat: {len(live_now)} channel")


if __name__ == "__main__":
    main()
