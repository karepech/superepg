import re
import json
from collections import defaultdict

INPUT_M3U = "live_epg_sports.m3u"
OUTPUT_JSON = "logo_channel_map.json"

def norm(txt):
    return re.sub(r"[^a-z0-9]", "", txt.lower())

with open(INPUT_M3U, encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

logo_map = defaultdict(list)

i = 0
while i < len(lines):
    if lines[i].startswith("#EXTINF"):
        ext = lines[i]

        m_logo = re.search(r'tvg-logo="([^"]+)"', ext)
        m_name = ext.split(",")[-1].strip()

        logo = m_logo.group(1) if m_logo else None
        name = m_name

        if logo:
            logo_map[logo].append(name)

    i += 1

# buat mapping ID internal
final_map = {}
for idx, (logo, names) in enumerate(logo_map.items(), 1):
    channel_id = f"ch_{idx:03d}"
    final_map[channel_id] = {
        "logo": logo,
        "aliases": list(set(names))
    }

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(final_map, f, indent=2, ensure_ascii=False)

print(f"✅ Mapping selesai: {len(final_map)} channel berbasis logo")
