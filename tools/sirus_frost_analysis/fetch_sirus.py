import csv
import json
import os
import statistics
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

BASE_URL = "https://sirus.su/api/base/x1/leaderboard/pve"
WEEK_FROM = os.getenv("SIRUS_WEEK_FROM", "2026-07-23")
WEEK_TO = os.getenv("SIRUS_WEEK_TO", "2026-08-18")
PER_PAGE = 500
OUT_DIR = Path("artifacts/sirus_frost")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BOSSES = [
    (38, 0, "TK", "Al'ar"),
    (38, 1, "TK", "Void Reaver"),
    (38, 2, "TK", "Solarian"),
    (38, 3, "TK", "Kael'thas"),
    (39, 0, "SSC", "Hydross"),
    (39, 1, "SSC", "The Lurker Below"),
    (39, 2, "SSC", "Leotheras"),
    (39, 3, "SSC", "Karathress"),
    (39, 4, "SSC", "Morogrim"),
    (39, 5, "SSC", "Lady Vashj"),
]

SPEC_NAMES = {
    (1, 0): "Arms Warrior", (1, 1): "Fury Warrior", (1, 2): "Protection Warrior",
    (2, 0): "Holy Paladin", (2, 1): "Protection Paladin", (2, 2): "Retribution Paladin",
    (3, 0): "Beast Mastery Hunter", (3, 1): "Marksmanship Hunter", (3, 2): "Survival Hunter",
    (4, 0): "Assassination Rogue", (4, 1): "Combat Rogue", (4, 2): "Subtlety Rogue",
    (5, 0): "Discipline Priest", (5, 1): "Holy Priest", (5, 2): "Shadow Priest",
    (6, 0): "Blood DK", (6, 1): "Frost DK", (6, 2): "Unholy DK",
    (7, 0): "Elemental Shaman", (7, 1): "Enhancement Shaman", (7, 2): "Restoration Shaman",
    (8, 0): "Arcane Mage", (8, 1): "Fire Mage", (8, 2): "Frost Mage",
    (9, 0): "Affliction Warlock", (9, 1): "Demonology Warlock", (9, 2): "Destruction Warlock",
    (11, 0): "Balance Druid", (11, 1): "Feral Druid", (11, 2): "Restoration Druid",
}

DPS_SPECS = {
    (1, 0), (1, 1),
    (2, 2),
    (3, 0), (3, 1), (3, 2),
    (4, 0), (4, 1), (4, 2),
    (5, 2),
    (6, 0), (6, 1), (6, 2),
    (7, 0), (7, 1),
    (8, 0), (8, 1), (8, 2),
    (9, 0), (9, 1), (9, 2),
    (11, 0), (11, 1),
}

MELEE_SPECS = {
    (1, 0), (1, 1), (2, 2),
    (4, 0), (4, 1), (4, 2),
    (6, 0), (6, 1), (6, 2),
    (7, 1), (11, 1),
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
})


def fetch_page(instance_id: int, boss_id: int, page: int):
    params = {
        "ladder": "players",
        "type": "dps",
        "aggregation": "avg",
        "week_from": WEEK_FROM,
        "week_to": WEEK_TO,
        "per_page": PER_PAGE,
        "page": page,
        "i": instance_id,
        "boss": boss_id,
    }
    last_err = None
    for attempt in range(1, 4):
        try:
            r = SESSION.get(BASE_URL, params=params, timeout=45)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last_err = exc
            if attempt < 3:
                time.sleep(5 * attempt)
    raise RuntimeError(f"Failed to fetch i={instance_id} boss={boss_id} page={page}: {last_err}")


def fetch_boss(instance_id: int, boss_id: int, raid: str, boss_name: str):
    first = fetch_page(instance_id, boss_id, 1)
    rows = list(first.get("data") or [])
    last_page = int((first.get("meta") or {}).get("last_page") or 1)
    for page in range(2, last_page + 1):
        chunk = fetch_page(instance_id, boss_id, page)
        rows.extend(chunk.get("data") or [])
        time.sleep(1)

    normalized = []
    for row in rows:
        class_id = row.get("class_id")
        spec_id = row.get("spec")
        key = (class_id, spec_id)
        if key not in DPS_SPECS:
            continue
        dps = row.get("dps")
        if dps is None:
            continue
        normalized.append({
            "raid": raid,
            "instance_id": instance_id,
            "boss": boss_name,
            "boss_id": boss_id,
            "name": row.get("name"),
            "guild_id": row.get("guild_id"),
            "class_id": class_id,
            "spec_id": spec_id,
            "spec": SPEC_NAMES.get(key, f"{class_id}:{spec_id}"),
            "dps": int(dps),
            "ilvl": row.get("ilvl"),
            "category": row.get("category"),
            "rank": row.get("rank"),
            "is_melee": key in MELEE_SPECS,
            "itemset": json.dumps(row.get("itemset") or [], ensure_ascii=False),
        })
    return normalized, last_page


def pct_delta(value, baseline):
    if value is None or baseline in (None, 0):
        return None
    return (value / baseline - 1.0) * 100.0


def main():
    all_rows = []
    manifest = []

    for instance_id, boss_id, raid, boss_name in BOSSES:
        rows, pages = fetch_boss(instance_id, boss_id, raid, boss_name)
        all_rows.extend(rows)
        manifest.append({"raid": raid, "boss": boss_name, "rows": len(rows), "pages": pages})
        print(f"{raid} / {boss_name}: {len(rows)} rows, {pages} pages")

    raw_path = OUT_DIR / "raw_logs.csv"
    if all_rows:
        with raw_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    grouped = defaultdict(list)
    for r in all_rows:
        grouped[(r["raid"], r["boss"], r["class_id"], r["spec_id"], r["spec"])].append(r["dps"])

    spec_rows = []
    by_boss_spec_median = defaultdict(dict)
    by_boss_spec_n = defaultdict(dict)
    for (raid, boss, class_id, spec_id, spec_name), dps_values in grouped.items():
        med = statistics.median(dps_values)
        mean = statistics.fmean(dps_values)
        item = {
            "raid": raid,
            "boss": boss,
            "class_id": class_id,
            "spec_id": spec_id,
            "spec": spec_name,
            "n": len(dps_values),
            "median_dps": round(med, 2),
            "mean_dps": round(mean, 2),
            "min_dps": min(dps_values),
            "max_dps": max(dps_values),
        }
        spec_rows.append(item)
        by_boss_spec_median[(raid, boss)][(class_id, spec_id)] = med
        by_boss_spec_n[(raid, boss)][(class_id, spec_id)] = len(dps_values)

    spec_rows.sort(key=lambda x: (x["raid"], x["boss"], -x["median_dps"]))
    spec_path = OUT_DIR / "spec_boss_medians.csv"
    if spec_rows:
        with spec_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(spec_rows[0].keys()))
            writer.writeheader()
            writer.writerows(spec_rows)

    frost_rows = []
    frost_key = (6, 1)
    unholy_key = (6, 2)

    for raid, boss in sorted(by_boss_spec_median.keys()):
        medians = by_boss_spec_median[(raid, boss)]
        frost = medians.get(frost_key)
        unholy = medians.get(unholy_key)
        all_spec_medians = [v for k, v in medians.items() if k in DPS_SPECS]
        melee_medians = [v for k, v in medians.items() if k in MELEE_SPECS]
        overall = statistics.median(all_spec_medians) if all_spec_medians else None
        melee = statistics.median(melee_medians) if melee_medians else None
        sorted_specs = sorted(
            [(k, v) for k, v in medians.items() if k in DPS_SPECS],
            key=lambda kv: kv[1], reverse=True
        )
        frost_rank = next((idx + 1 for idx, (k, _) in enumerate(sorted_specs) if k == frost_key), None)
        frost_rows.append({
            "raid": raid,
            "boss": boss,
            "frost_n": by_boss_spec_n[(raid, boss)].get(frost_key, 0),
            "frost_median_dps": round(frost, 2) if frost is not None else None,
            "overall_spec_median_dps": round(overall, 2) if overall is not None else None,
            "frost_vs_overall_pct": round(pct_delta(frost, overall), 2) if frost is not None and overall else None,
            "melee_spec_median_dps": round(melee, 2) if melee is not None else None,
            "frost_vs_melee_pct": round(pct_delta(frost, melee), 2) if frost is not None and melee else None,
            "unholy_median_dps": round(unholy, 2) if unholy is not None else None,
            "frost_vs_unholy_pct": round(pct_delta(frost, unholy), 2) if frost is not None and unholy else None,
            "frost_rank": frost_rank,
            "dps_specs_present": len(sorted_specs),
        })

    frost_path = OUT_DIR / "frost_analysis.csv"
    if frost_rows:
        with frost_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(frost_rows[0].keys()))
            writer.writeheader()
            writer.writerows(frost_rows)

    with (OUT_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "week_from": WEEK_FROM,
            "week_to": WEEK_TO,
            "aggregation": "avg",
            "ilvl_filter": None,
            "bosses": manifest,
        }, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(all_rows)} total rows to {OUT_DIR}")


if __name__ == "__main__":
    main()
