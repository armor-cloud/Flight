import csv
import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

BASE_URL = "https://sirus.su/api/base/x1/leaderboard/pve"
DETAIL_URL = "https://sirus.su/api/base/x1/details/bossfight/{fight_id}"
WEEK_FROM = os.getenv("SIRUS_WEEK_FROM", "2026-07-23")
WEEK_TO = os.getenv("SIRUS_WEEK_TO", "2026-08-18")
PER_PAGE = 500
OUT = Path("artifacts/sirus_frost/audit")
RAW = OUT / "raw"
( RAW / "specializations" ).mkdir(parents=True, exist_ok=True)
( RAW / "players" ).mkdir(parents=True, exist_ok=True)
( RAW / "fights" ).mkdir(parents=True, exist_ok=True)

BOSSES = [
    (38, 0, "TK", "Alar"),
    (38, 1, "TK", "Void_Reaver"),
    (38, 2, "TK", "Solarian"),
    (38, 3, "TK", "Kaelthas"),
    (39, 0, "SSC", "Hydross"),
    (39, 1, "SSC", "Lurker"),
    (39, 2, "SSC", "Leotheras"),
    (39, 3, "SSC", "Karathress"),
    (39, 4, "SSC", "Morogrim"),
    (39, 5, "SSC", "Lady_Vashj"),
]

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
})


def get_json(url, params=None):
    last = None
    for attempt in range(1, 4):
        try:
            r = S.get(url, params=params, timeout=45)
            r.raise_for_status()
            return r.json(), r.url, r.status_code
        except Exception as e:
            last = e
            if attempt < 3:
                time.sleep(3 * attempt)
    raise RuntimeError(f"GET failed: {url} params={params}: {last}")


def dump(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_fight_id(obj):
    if not isinstance(obj, dict):
        return None
    for key in ("fight_id", "bossfight_id", "boss_fight_id", "id"):
        v = obj.get(key)
        if isinstance(v, int) and v > 0:
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return None


def main():
    manifest = []
    schema = {"specialization_row_keys": [], "player_row_keys": [], "fight_entry_keys": []}
    spec_keys, player_keys, fight_keys = set(), set(), set()
    player_fights = []
    fight_ids = set()

    for instance_id, boss_id, raid, boss in BOSSES:
        common = {
            "type": "dps",
            "aggregation": "avg",
            "week_from": WEEK_FROM,
            "week_to": WEEK_TO,
            "per_page": PER_PAGE,
            "i": instance_id,
            "boss": boss_id,
        }

        # 1) Official specializations ladder response: control against the UI tab.
        spec_params = {**common, "ladder": "specializations", "page": 1}
        spec_json, spec_url, status = get_json(BASE_URL, spec_params)
        dump(RAW / "specializations" / f"{raid}_{boss}.json", spec_json)
        for row in spec_json.get("data") or []:
            if isinstance(row, dict):
                spec_keys.update(row.keys())
        manifest.append({
            "source": "sirus",
            "dataset": "specializations",
            "raid": raid,
            "boss": boss,
            "instance_id": instance_id,
            "boss_id": boss_id,
            "page": 1,
            "status": status,
            "url": spec_url,
            "rows": len(spec_json.get("data") or []),
            "last_page": (spec_json.get("meta") or {}).get("last_page"),
        })

        # 2) Player ladder, all pages, preserving the exact raw API payload.
        p = 1
        while True:
            player_params = {**common, "ladder": "players", "page": p}
            data, url, status = get_json(BASE_URL, player_params)
            dump(RAW / "players" / f"{raid}_{boss}_page_{p}.json", data)
            rows = data.get("data") or []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                player_keys.update(row.keys())
                fights = row.get("fights")
                if isinstance(fights, list):
                    for fight in fights:
                        if not isinstance(fight, dict):
                            continue
                        fight_keys.update(fight.keys())
                        fid = find_fight_id(fight)
                        if fid:
                            fight_ids.add(fid)
                        player_fights.append({
                            "raid": raid,
                            "boss_filter": boss,
                            "player": row.get("name"),
                            "class_id": row.get("class_id"),
                            "spec": row.get("spec"),
                            "player_aggregate_dps": row.get("dps"),
                            "fight": fight,
                            "resolved_fight_id": fid,
                        })
            meta = data.get("meta") or {}
            last_page = int(meta.get("last_page") or 1)
            manifest.append({
                "source": "sirus",
                "dataset": "players",
                "raid": raid,
                "boss": boss,
                "instance_id": instance_id,
                "boss_id": boss_id,
                "page": p,
                "status": status,
                "url": url,
                "rows": len(rows),
                "last_page": last_page,
            })
            if p >= last_page:
                break
            p += 1
            time.sleep(0.5)

    # 3) If Sirus exposes fight ids inside leaderboard rows, capture the underlying fight JSON too.
    fight_fetch = []
    for i, fid in enumerate(sorted(fight_ids), start=1):
        url = DETAIL_URL.format(fight_id=fid)
        try:
            data, final_url, status = get_json(url)
            dump(RAW / "fights" / f"{fid}.json", data)
            fight_fetch.append({"fight_id": fid, "status": status, "url": final_url, "ok": True})
        except Exception as exc:
            fight_fetch.append({"fight_id": fid, "status": None, "url": url, "ok": False, "error": str(exc)})
        if i % 25 == 0:
            time.sleep(1)

    with (OUT / "player_fights.jsonl").open("w", encoding="utf-8") as f:
        for item in player_fights:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with (OUT / "request_manifest.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["source", "dataset", "raid", "boss", "instance_id", "boss_id", "page", "status", "url", "rows", "last_page"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(manifest)

    with (OUT / "fight_fetch_manifest.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = ["fight_id", "status", "url", "ok", "error"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(fight_fetch)

    schema["specialization_row_keys"] = sorted(spec_keys)
    schema["player_row_keys"] = sorted(player_keys)
    schema["fight_entry_keys"] = sorted(fight_keys)
    schema["fight_ids_found"] = len(fight_ids)
    schema["player_fight_entries_found"] = len(player_fights)
    dump(OUT / "schema_report.json", schema)
    dump(OUT / "audit_summary.json", {
        "week_from": WEEK_FROM,
        "week_to": WEEK_TO,
        "aggregation": "avg",
        "ilvl_filter": None,
        "bosses": len(BOSSES),
        "request_count": len(manifest),
        "fight_entry_count": len(player_fights),
        "fight_ids_found": len(fight_ids),
        "fight_detail_success": sum(1 for x in fight_fetch if x.get("ok")),
        "note": "Raw JSON is preserved verbatim. Specializations and players are collected separately to prevent mixing UI control values with reconstructed statistics.",
    })
    print(json.dumps(schema, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
