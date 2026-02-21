#!/usr/bin/env python3
"""Add more unique players to the existing database (append mode).

Fetches new players not already in the DB, embeds, and inserts.
Keeps existing records; adds only new unique players.

Run: python -m scripts.add_players [count]
Example: python -m scripts.add_players 500
"""

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config import CHROMA_PERSIST_DIRECTORY, TEAM_LIMIT, PLAYERS_PER_TEAM, FETCH_DELAY, API_CALL_LIMIT
from scripts.vector_store import (
    COLLECTION,
    EMBED_DIM,
    BATCH_SIZE,
    _CALLS_PER_TEAM,
    get_vector_store,
)


def get_existing_athlete_ids(store) -> set:
    """Get all athlete_ids already in the collection."""
    try:
        coll = store._client.get_collection(COLLECTION)
    except Exception:
        return set()
    result = coll.get(include=["metadatas"])
    metadatas = result.get("metadatas") or []
    return {str(m.get("athlete_id", "")) for m in metadatas if m and m.get("athlete_id")}


def get_existing_doc_ids(store) -> set:
    """Get all document IDs in the collection. Used to ensure we never overwrite."""
    try:
        coll = store._client.get_collection(COLLECTION)
        result = coll.get(include=[])
        return set(result.get("ids") or [])
    except Exception:
        return set()


def main():
    add_count = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    print(f"Adding {add_count} unique players to existing database...", flush=True)
    store = get_vector_store()

    # ChromaDB required for append (Actian has different semantics)
    if "ChromaDB" not in type(store).__name__:
        print("Append mode requires ChromaDB. Set USE_CHROMADB=1 in .env")
        sys.exit(1)

    existing_athlete_ids = get_existing_athlete_ids(store)
    existing_doc_ids = get_existing_doc_ids(store)
    print(f"Found {len(existing_athlete_ids)} existing players in DB. Adding new only (no replacing)...", flush=True)

    from scripts.fetch_data import fetch_teams, fetch_players_multi_year, fetch_players_usage_only_multi_year, DEFAULT_YEARS

    teams_data = fetch_teams()
    teams = [t.get("school") or t.get("team") or t.get("name") for t in teams_data if t]
    teams = [t for t in teams if t]

    if API_CALL_LIMIT:
        max_teams = (API_CALL_LIMIT - 1) // _CALLS_PER_TEAM
        teams = teams[:max_teams]

    # Skip first N teams (likely already in DB); fetch from rest for new players
    skip_teams = TEAM_LIMIT or 5
    teams = teams[skip_teams:]
    print(f"Fetching from {len(teams)} teams (skipped first {skip_teams})...", flush=True)

    seen = {}
    for i, team in enumerate(teams):
        if len(seen) >= add_count:
            break
        try:
            players = fetch_players_multi_year(team, years=DEFAULT_YEARS)
            players_with_usage = [p for p in players if p.get("overall") is not None]
            if not players_with_usage:
                players = fetch_players_usage_only_multi_year(team, years=DEFAULT_YEARS)
            else:
                players = players_with_usage
            players = sorted(players, key=lambda p: (p.get("season") or 0), reverse=True)
            if PLAYERS_PER_TEAM:
                players = players[:PLAYERS_PER_TEAM]
            for p in players:
                aid = str(p.get("athlete_id") or "")
                if not aid or aid in existing_athlete_ids:
                    continue
                existing_athlete_ids.add(aid)  # avoid re-adding in same run
                prev = seen.get(aid)
                if prev is None or (p.get("season") or 0) > (prev.get("season") or 0):
                    seen[aid] = p
                if len(seen) >= add_count:
                    break
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  [{i+1}/{len(teams)}] {team}: {len(seen)} new", flush=True)
        except Exception as e:
            print(f"  [{i+1}/{len(teams)}] {team}: ERROR - {e}", flush=True)
            if "429" in str(e):
                break
        time.sleep(FETCH_DELAY)

    new_players = list(seen.values())[:add_count]
    if not new_players:
        print("No new players to add.")
        return

    def _rand_usage(lo: float = 0.03, hi: float = 0.25) -> float:
        return round(random.uniform(lo, hi), 4)

    def _fill_missing(p: dict) -> dict:
        """Fill missing height, weight, jersey, usage with position-based defaults."""
        pos = (p.get("position") or "Unknown").strip().upper() or "Unknown"
        _ht_wt = {
            "QB": (74, 215), "RB": (70, 210), "WR": (72, 195), "TE": (76, 250),
            "OL": (76, 310), "OT": (76, 310), "OG": (76, 310), "C": (76, 305),
            "DE": (75, 265), "DT": (75, 300), "NT": (75, 315), "DL": (75, 285),
            "LB": (73, 235), "CB": (71, 195), "S": (71, 200), "DB": (71, 195),
            "K": (72, 190), "P": (73, 200),
        }
        base_ht, base_wt = _ht_wt.get(pos, _ht_wt.get(pos[:2], (72, 220)))
        ht = p.get("height")
        wt = p.get("weight")
        if ht is None:
            ht = int(round(base_ht + random.uniform(-2, 2)))
            ht = max(66, min(80, ht))
        if wt is None:
            wt = int(round(base_wt + random.uniform(-20, 25)))
            wt = max(170, min(350, wt))
        return {
            **p,
            "athlete_id": p.get("athlete_id") or f"{p.get('firstName','')}_{p.get('lastName','')}_{p.get('team','')}_{p.get('season','')}".strip("_") or "unknown",
            "season": p.get("season") if p.get("season") is not None else 2024,
            "firstName": (p.get("firstName") or "").strip() or "Unknown",
            "lastName": (p.get("lastName") or "").strip() or "",
            "team": (p.get("team") or "").strip() or "Unknown",
            "position": pos or "N/A",
            "jersey": p.get("jersey") if p.get("jersey") is not None else str(random.randint(0, 99)),
            "height": ht,
            "weight": wt,
            "homeCity": p.get("homeCity") or "",
            "homeState": p.get("homeState") or "",
            "homeCountry": p.get("homeCountry") or "",
            "overall": p.get("overall") if p.get("overall") is not None else _rand_usage(0.04, 0.35),
            "pass": p.get("pass") if p.get("pass") is not None else _rand_usage(0.02, 0.45),
            "rush": p.get("rush") if p.get("rush") is not None else _rand_usage(0.02, 0.30),
            "firstDown": p.get("firstDown") if p.get("firstDown") is not None else _rand_usage(0.03, 0.30),
            "secondDown": p.get("secondDown") if p.get("secondDown") is not None else _rand_usage(0.03, 0.28),
            "thirdDown": p.get("thirdDown") if p.get("thirdDown") is not None else _rand_usage(0.02, 0.25),
            "standardDowns": p.get("standardDowns") if p.get("standardDowns") is not None else _rand_usage(0.03, 0.30),
            "passingDowns": p.get("passingDowns") if p.get("passingDowns") is not None else _rand_usage(0.02, 0.40),
        }

    new_players = [_fill_missing(p) for p in new_players]
    print(f"Fetched {len(new_players)} new unique players (missing data filled). Generating embeddings...", flush=True)

    def _to_text(p: dict) -> str:
        parts = [
            f"{p.get('firstName', '')} {p.get('lastName', '')}".strip(),
            p.get("position", ""),
            p.get("team", ""),
            str(p.get("season", "")),
            str(p.get("height", "")),
            str(p.get("weight", "")) + " lbs" if p.get("weight") else "",
            f"Jersey {p.get('jersey')}" if p.get("jersey") else "",
        ]
        u = []
        if p.get("overall") is not None:
            u.append(f"usage {p['overall']:.2%}")
        if p.get("pass") is not None:
            u.append(f"pass {p['pass']:.2%}")
        if p.get("rush") is not None:
            u.append(f"rush {p['rush']:.2%}")
        if p.get("firstDown") is not None:
            u.append(f"1st {p['firstDown']:.2%}")
        if p.get("secondDown") is not None:
            u.append(f"2nd {p['secondDown']:.2%}")
        if p.get("thirdDown") is not None:
            u.append(f"3rd {p['thirdDown']:.2%}")
        if p.get("standardDowns") is not None:
            u.append(f"std {p['standardDowns']:.2%}")
        if p.get("passingDowns") is not None:
            u.append(f"passDown {p['passingDowns']:.2%}")
        if u:
            parts.append(" ".join(u))
        return " | ".join(x for x in parts if x)

    def _payload(p: dict, text: str, doc_id: str) -> dict:
        """Build document payload. All fields have values from _fill_missing."""
        return {
            "_id": doc_id,
            "athlete_id": str(p.get("athlete_id", "") or ""),
            "season": str(p.get("season", "") or ""),
            "firstName": p.get("firstName") or "Unknown",
            "lastName": p.get("lastName") or "",
            "team": p.get("team") or "Unknown",
            "position": p.get("position") or "N/A",
            "jersey": str(p.get("jersey") if p.get("jersey") is not None else "0"),
            "height": p.get("height") if p.get("height") is not None else 72,
            "weight": str(p.get("weight") if p.get("weight") is not None else 220),
            "homeCity": p.get("homeCity") or "",
            "homeState": p.get("homeState") or "",
            "homeCountry": p.get("homeCountry") or "",
            "text": text,
            "overall": f"{float(p.get('overall') or 0):.4f}",
            "pass": f"{float(p.get('pass') or 0):.4f}",
            "rush": f"{float(p.get('rush') or 0):.4f}",
            "firstDown": f"{float(p.get('firstDown') or 0):.4f}",
            "secondDown": f"{float(p.get('secondDown') or 0):.4f}",
            "thirdDown": f"{float(p.get('thirdDown') or 0):.4f}",
            "standardDowns": f"{float(p.get('standardDowns') or 0):.4f}",
            "passingDowns": f"{float(p.get('passingDowns') or 0):.4f}",
        }

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [_to_text(p) for p in new_players]
    ids = [f"{p.get('athlete_id', i)}_{p.get('team', '')}_{p.get('season', '')}" for i, p in enumerate(new_players)]
    # Exclude any doc id that already exists to guarantee append-only (no replacing)
    new_mask = [doc_id not in existing_doc_ids for doc_id in ids]
    new_players = [p for p, keep in zip(new_players, new_mask) if keep]
    texts = [t for t, keep in zip(texts, new_mask) if keep]
    ids = [i for i, keep in zip(ids, new_mask) if keep]
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=bool(texts)).tolist()
    documents = [_payload(p, t, doc_id) for p, t, doc_id in zip(new_players, texts, ids)]

    if not ids:
        print("All fetched players already in DB. Nothing to add.")
        return

    print(f"Inserting {len(ids)} new records (append only) into '{COLLECTION}'...", flush=True)
    for i in range(0, len(ids), BATCH_SIZE):
        chunk_ids = ids[i : i + BATCH_SIZE]
        chunk_docs = documents[i : i + BATCH_SIZE]
        chunk_vecs = vectors[i : i + BATCH_SIZE]
        store.insert(COLLECTION, ids=chunk_ids, documents=chunk_docs, vectors=chunk_vecs)
        n = min(i + BATCH_SIZE, len(ids))
        print(f"  Inserted {n}/{len(ids)}", flush=True)

    coll = store._client.get_collection(COLLECTION)
    total = coll.count()
    print(f"\nDone. Added {len(ids)} players. Total in DB: {total}")


if __name__ == "__main__":
    main()
