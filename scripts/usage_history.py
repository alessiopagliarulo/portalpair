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
    "homeCountry", "season", "text", "_id", "overall_rating", "class",
    "pred_2026_overall",
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
    doc_id = os.environ.get("DOC_ID", "").strip()
    athlete_id = os.environ.get("ATHLETE_ID", "").strip()
    season_filter = os.environ.get("SEASON", "").strip()
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--team" and i + 1 < len(sys.argv):
            team_filter = sys.argv[i + 1].strip()
        elif arg == "--doc-id" and i + 1 < len(sys.argv):
            doc_id = sys.argv[i + 1].strip()
        elif arg == "--athlete-id" and i + 1 < len(sys.argv):
            athlete_id = sys.argv[i + 1].strip()
        elif arg == "--season" and i + 1 < len(sys.argv):
            season_filter = sys.argv[i + 1].strip()
        elif not arg.startswith("--") and not player_name:
            player_name = arg.strip()

    if not (player_name or doc_id or (athlete_id and team_filter and season_filter)):
        print(json.dumps({"error": "Provide player name, doc_id, or athlete_id+team+season."}), flush=True)
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

    matches = []
    if doc_id:
        seed = None
        for row_id, meta in zip(ids, metadatas):
            if row_id == doc_id:
                seed = meta or {}
                break
        if seed:
            seed_aid = str(seed.get("athlete_id") or "").strip()
            seed_team = (seed.get("team") or "").strip().lower()
            seed_name = f"{(seed.get('firstName') or '').strip()} {(seed.get('lastName') or '').strip()}".strip().lower()
            for meta in metadatas:
                meta = meta or {}
                aid = str(meta.get("athlete_id") or "").strip()
                team = (meta.get("team") or "").strip().lower()
                full = f"{(meta.get('firstName') or '').strip()} {(meta.get('lastName') or '').strip()}".strip().lower()
                if seed_aid and aid and aid == seed_aid and team == seed_team:
                    matches.append(meta)
                elif (not seed_aid) and full == seed_name and team == seed_team:
                    matches.append(meta)
    elif athlete_id and team_filter and season_filter:
        team_l = team_filter.lower()
        for meta in metadatas:
            meta = meta or {}
            aid = str(meta.get("athlete_id") or "").strip()
            team = (meta.get("team") or "").strip().lower()
            if aid == athlete_id and team == team_l:
                matches.append(meta)
    else:
        search_parts = player_name.lower().split()
        if not search_parts:
            print(json.dumps({"error": "Player name required."}), flush=True)
            sys.exit(1)
        for meta in metadatas:
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
            "player": {"name": player_name or None, "team": team_filter or None, "position": None},
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
            if k not in IDENTITY_KEYS and not k.startswith("pred_"):
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
    ovr = player_info.get("overall_rating")
    try:
        ovr = int(float(ovr)) if ovr is not None else None
    except (ValueError, TypeError):
        ovr = None
    predictions = {}
    for k, v in player_info.items():
        if k.startswith("pred_") and k != "pred_2026_overall":
            stat_key = k[5:]  # strip "pred_" prefix
            parsed = _parse_number(v)
            if parsed is not None:
                predictions[stat_key] = parsed
    pred_ovr = player_info.get("pred_2026_overall")
    try:
        pred_ovr = int(float(pred_ovr)) if pred_ovr is not None else None
    except (ValueError, TypeError):
        pred_ovr = None

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
            "overall_rating": ovr,
            "pred_2026_overall": pred_ovr,
            "class": player_info.get("class") or None,
        },
        "predictions_2026": predictions,
        "seasons": seasons,
    }
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
