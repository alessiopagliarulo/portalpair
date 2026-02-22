#!/usr/bin/env python3
"""Fetch full player profile from ChromaDB by doc_id or athlete_id+team+season.

Run: python -m scripts.get_player_profile --json <doc_id>
    python -m scripts.get_player_profile --json <athlete_id> <team> <season>
Output: JSON object with all ChromaDB fields, or {} if not found.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("USE_CHROMADB", "1")
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.vector_store import COLLECTION, get_vector_store

IDENTITY_KEYS = {
    "athlete_id", "firstName", "lastName", "team", "position",
    "jersey", "height", "weight", "homeCity", "homeState",
    "homeCountry", "season", "text", "_id", "overall_rating", "class",
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
        return v


def main():
    json_mode = "--json" in sys.argv
    if "--json" in sys.argv:
        args = sys.argv[sys.argv.index("--json") + 1:]
    else:
        args = [a for a in sys.argv[1:] if a != "--json" and a != "-m" and not a.startswith("scripts.")]
    doc_id = None
    if len(args) == 1:
        doc_id = args[0]
    elif len(args) >= 3:
        athlete_id, team, season = args[0], args[1], args[2]
        doc_id = f"{athlete_id}_{team}_{season}"
    if not doc_id:
        if json_mode:
            print("{}")
        return

    try:
        store = get_vector_store()
        if not hasattr(store, "_client"):
            if json_mode:
                print("{}")
            return
        coll = store._client.get_collection(COLLECTION)
        result = coll.get(ids=[doc_id], include=["metadatas"])
        ids = result.get("ids") or []
        metadatas = result.get("metadatas") or []
        if not ids or not metadatas:
            if json_mode:
                print("{}")
            return
        meta = metadatas[0] if metadatas else {}
        out = {"_id": doc_id}
        for k, v in meta.items():
            if k in ("height", "weight") and v is not None:
                try:
                    out[k] = int(v)
                except (ValueError, TypeError):
                    out[k] = v
            elif k not in IDENTITY_KEYS:
                out[k] = _parse_number(v)
            else:
                out[k] = v
        if json_mode:
            print(json.dumps(out))
    except Exception as e:
        if json_mode:
            print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
