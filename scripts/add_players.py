#!/usr/bin/env python3
"""Add more unique players to the existing database (append mode).

Fetches new players not already in the DB, embeds, and inserts.
Keeps existing records; adds only new unique players.

Run: python -m scripts.add_players [count]
Example: python -m scripts.add_players 500
"""

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
    # ChromaDB get() with no ids returns all documents
    result = coll.get(include=["metadatas"])
    metadatas = result.get("metadatas") or []
    return {str(m.get("athlete_id", "")) for m in metadatas if m and m.get("athlete_id")}


def main():
    add_count = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    print(f"Adding {add_count} unique players to existing database...", flush=True)
    store = get_vector_store()

    # ChromaDB required for append (Actian has different semantics)
    if "ChromaDB" not in type(store).__name__:
        print("Append mode requires ChromaDB. Set USE_CHROMADB=1 in .env")
        sys.exit(1)

    existing_ids = get_existing_athlete_ids(store)
    print(f"Found {len(existing_ids)} existing players in DB. Fetching new players...", flush=True)

    from scripts.fetch_data import fetch_teams, fetch_players_multi_year, DEFAULT_YEARS

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
            players = sorted(players, key=lambda p: (p.get("season") or 0), reverse=True)
            if PLAYERS_PER_TEAM:
                players = players[:PLAYERS_PER_TEAM]
            for p in players:
                aid = str(p.get("athlete_id") or "")
                if not aid or aid in existing_ids:
                    continue
                existing_ids.add(aid)  # avoid re-adding in same run
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

    print(f"Fetched {len(new_players)} new unique players. Generating embeddings...", flush=True)

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
        if u:
            parts.append(" ".join(u))
        return " | ".join(x for x in parts if x)

    def _payload(p: dict, text: str, doc_id: str) -> dict:
        out = {
            "_id": doc_id,
            "athlete_id": str(p.get("athlete_id", "")),
            "season": str(p.get("season", "")),
            "firstName": p.get("firstName"),
            "lastName": p.get("lastName"),
            "team": p.get("team"),
            "position": p.get("position"),
            "jersey": str(p["jersey"]) if p.get("jersey") is not None else None,
            "height": p.get("height"),
            "weight": str(p["weight"]) if p.get("weight") is not None else None,
            "homeCity": p.get("homeCity"),
            "homeState": p.get("homeState"),
            "homeCountry": p.get("homeCountry"),
            "text": text,
            "overall": f"{p['overall']:.4f}" if p.get("overall") is not None else None,
            "pass": f"{p['pass']:.4f}" if p.get("pass") is not None else None,
            "rush": f"{p['rush']:.4f}" if p.get("rush") is not None else None,
            "firstDown": f"{p['firstDown']:.4f}" if p.get("firstDown") is not None else None,
            "secondDown": f"{p['secondDown']:.4f}" if p.get("secondDown") is not None else None,
            "thirdDown": f"{p['thirdDown']:.4f}" if p.get("thirdDown") is not None else None,
            "standardDowns": f"{p['standardDowns']:.4f}" if p.get("standardDowns") is not None else None,
            "passingDowns": f"{p['passingDowns']:.4f}" if p.get("passingDowns") is not None else None,
        }
        return {k: v for k, v in out.items() if v is not None}

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [_to_text(p) for p in new_players]
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=True).tolist()
    ids = [f"{p.get('athlete_id', i)}_{p.get('team', '')}_{p.get('season', '')}" for i, p in enumerate(new_players)]
    documents = [_payload(p, t, doc_id) for p, t, doc_id in zip(new_players, texts, ids)]

    print(f"Inserting {len(ids)} records into '{COLLECTION}'...", flush=True)
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
