#!/usr/bin/env python3
"""Fetch stat history for a player from ChromaDB. Outputs JSON.

Run: python -m scripts.usage_history "Player Name" [--team TEAM]
     or set PLAYER_NAME and optionally TEAM env vars.

Output: {"player":{"name","team","position"},"seasons":[{season, ...stats...}]}
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("TQDM_DISABLE", "1")

IDENTITY_KEYS = {
    "athlete_id", "firstName", "lastName", "team", "position",
    "jersey", "height", "weight", "homeCity", "homeState",
    "homeCountry", "season", "text", "_id",
}


def _parse_number(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
        if f == int(f) and "." not in str(v):
            return int(f)
        return round(f, 1)
    except (ValueError, TypeError):
        return None


def main():
    player_name = os.environ.get("PLAYER_NAME", "").strip()
    team_filter = os.environ.get("TEAM", "").strip()
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--team" and i + 1 < len(sys.argv):
            team_filter = sys.argv[i + 1].strip()
        elif not arg.startswith("--") and not player_name:
            player_name = arg.strip()

    if not player_name:
        print(json.dumps({"error": "Player name required."}), flush=True)
        sys.exit(1)

    try:
        from scripts.config import CHROMA_PERSIST_DIRECTORY
        import chromadb
    except ImportError as e:
        print(json.dumps({"error": f"Import error: {e}"}), flush=True)
        sys.exit(1)

    root = Path(__file__).parent.parent
    p = CHROMA_PERSIST_DIRECTORY
    if not os.path.isabs(p):
        p = str((root / p).resolve())

    try:
        client = chromadb.PersistentClient(path=p)
        coll = client.get_collection("cfb_players")
        result = coll.get(include=["metadatas"])
    except Exception as e:
        print(json.dumps({"error": str(e)}), flush=True)
        sys.exit(1)

    ids = result.get("ids") or []
    metadatas = result.get("metadatas") or []

    search_parts = player_name.lower().split()
    if not search_parts:
        print(json.dumps({"error": "Player name required."}), flush=True)
        sys.exit(1)

    matches = []
    for i, meta in enumerate(metadatas):
        meta = meta or {}
        first = (meta.get("firstName") or "").strip()
        last = (meta.get("lastName") or "").strip()
        full = f"{first} {last}".strip().lower()
        team = (meta.get("team") or "").strip()
        if team_filter and team.lower() != team_filter.lower():
            continue
        if not first and not last:
            continue
        if full == player_name.lower():
            matches.append(meta)
        elif all(part in full for part in search_parts):
            matches.append(meta)

    if not matches:
        print(json.dumps({
            "player": {"name": player_name, "team": team_filter or None, "position": None},
            "seasons": [],
            "error": "No data found for this player."
        }), flush=True)
        return

    by_season = {}
    for m in matches:
        season = m.get("season")
        if season is not None:
            key = str(season)
            if key not in by_season:
                by_season[key] = m

    seasons = []
    for s in sorted(by_season.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
        m = by_season[s]
        season_data = {"season": m.get("season")}
        for k, v in m.items():
            if k not in IDENTITY_KEYS:
                parsed = _parse_number(v)
                if parsed is not None:
                    season_data[k] = parsed
        seasons.append(season_data)

    player_info = matches[0]
    ht = player_info.get("height")
    try:
        ht = int(float(ht)) if ht is not None else None
    except (ValueError, TypeError):
        ht = None
    wt = player_info.get("weight")
    try:
        wt = int(float(wt)) if wt is not None else None
    except (ValueError, TypeError):
        wt = None
    out = {
        "player": {
            "name": f"{(player_info.get('firstName') or '').strip()} {(player_info.get('lastName') or '').strip()}".strip(),
            "team": (player_info.get("team") or "").strip() or None,
            "position": (player_info.get("position") or "").strip() or None,
            "height": ht,
            "weight": wt,
            "jersey": player_info.get("jersey") or None,
            "homeCity": player_info.get("homeCity") or None,
            "homeState": player_info.get("homeState") or None,
            "homeCountry": player_info.get("homeCountry") or None,
        },
        "seasons": seasons,
    }
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
