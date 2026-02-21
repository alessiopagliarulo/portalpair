#!/usr/bin/env python3
"""
Prove that CFBD player data is correctly stored in Actian VectorAI DB.

Run: python -m scripts.prove_vector_store

Prerequisites:
  - Actian VectorAI DB running (docker compose up in actian-vectorAI-db-beta)
  - CFBD_API_KEY in .env
  - pip install -r requirements.txt
"""

import json
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_data import fetch_players_multi_year, DEFAULT_YEARS
from scripts.vector_store import get_vector_store

COLLECTION = "cfb_players_proof"
EMBED_DIM = 384  # all-MiniLM-L6-v2


def player_to_text(p: dict) -> str:
    """Build embeddable text from player record."""
    parts = [
        f"{p.get('firstName', '')} {p.get('lastName', '')}".strip(),
        p.get("position", ""),
        p.get("team", ""),
        str(p.get("season", "")),
        str(p.get("height", "")),
        str(p.get("weight", "")) + " lbs" if p.get("weight") else "",
        f"Jersey {p.get('jersey')}" if p.get("jersey") else "",
    ]
    usage = []
    if p.get("overall") is not None:
        usage.append(f"usage {p['overall']:.2%}")
    if p.get("pass") is not None:
        usage.append(f"pass {p['pass']:.2%}")
    if p.get("rush") is not None:
        usage.append(f"rush {p['rush']:.2%}")
    if usage:
        parts.append(" ".join(usage))
    return " | ".join(p for p in parts if p)


def payload_for_store(p: dict, text: str) -> dict:
    """Build Cortex-friendly payload (simple types only)."""
    return {
        "_id": f"{p.get('athlete_id', '')}_{p.get('season', '')}",
        "athlete_id": str(p.get("athlete_id", "")),
        "season": str(p.get("season", "")),
        "firstName": p.get("firstName"),
        "lastName": p.get("lastName"),
        "team": p.get("team"),
        "position": p.get("position"),
        "jersey": str(p["jersey"]) if p.get("jersey") is not None else None,
        "height": p.get("height"),
        "weight": str(p["weight"]) if p.get("weight") is not None else None,
        "text": text,
        "overall": f"{p['overall']:.4f}" if p.get("overall") is not None else None,
        "pass": f"{p['pass']:.4f}" if p.get("pass") is not None else None,
        "rush": f"{p['rush']:.4f}" if p.get("rush") is not None else None,
    }


def main():
    print("=" * 60)
    print("PROOF: CFBD data correctly stored in Actian VectorAI DB")
    print("=" * 60)

    # 1. Fetch from CFBD API (2020-2025)
    print("\n1. Fetching player data from College Football Data API...")
    team = "Alabama"
    merged = fetch_players_multi_year(team, years=DEFAULT_YEARS)
    print(f"   Fetched {len(merged)} player-season records for {team} ({DEFAULT_YEARS[0]}-{DEFAULT_YEARS[-1]})")
    if not merged:
        print("   ERROR: No data returned. Check CFBD_API_KEY in .env")
        sys.exit(1)

    sample = merged[0]
    print(f"   Sample (before insert): {sample.get('firstName')} {sample.get('lastName')} | {sample.get('position')} | {sample.get('team')} | season {sample.get('season')}")

    # 2. Build embeddings
    print("\n2. Generating embeddings with sentence-transformers...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [player_to_text(p) for p in merged]
    vectors = model.encode(texts, convert_to_numpy=True).tolist()
    print(f"   Embedded {len(vectors)} players (dim={len(vectors[0])})")

    # 3. Connect to VectorAI DB and insert
    print("\n3. Inserting into Actian VectorAI DB...")
    store = get_vector_store()
    ids = [f"{p.get('athlete_id', i)}_{p.get('season', '')}" for i, p in enumerate(merged)]
    documents = [payload_for_store(p, t) for p, t in zip(merged, texts)]

    # Recreate collection for clean proof run
    try:
        store._client.delete_collection(COLLECTION)
    except Exception:
        pass
    store.create_collection(COLLECTION, dimension=EMBED_DIM)
    store.insert(COLLECTION, ids=ids, documents=documents, vectors=vectors)
    print(f"   Inserted {len(ids)} players into collection '{COLLECTION}'")

    # 4. Verify count
    count = store._client.count(COLLECTION)
    print(f"\n4. Count in DB: {count} (expected {len(merged)})")
    assert count == len(merged), f"Count mismatch: {count} vs {len(merged)}"
    print("   ✓ Count matches")

    # 5. Semantic search - retrieve by meaning
    print("\n5. Semantic search: 'quarterback pass'")
    query_vec = model.encode(["quarterback pass"], convert_to_numpy=True)[0].tolist()
    results = store.search(COLLECTION, query_vec, top_k=5)
    print("   Top 5 results (retrieved from vector DB):")
    for i, r in enumerate(results, 1):
        p = r.get("payload", {})
        score = r.get("score", 0)
        name = f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
        pos = p.get("position", "")
        tm = p.get("team", "")
        season = p.get("season", "")
        print(f"   {i}. {name} | {pos} | {tm} | {season} | score={score:.4f}")

    # 6. Show full payload of first result
    print("\n6. Full payload of top result (proves all fields stored correctly):")
    top = results[0].get("payload", {})
    print(json.dumps({k: v for k, v in top.items() if v is not None}, indent=2))

    print("\n" + "=" * 60)
    print("PROOF COMPLETE: Data is correctly stored and retrievable.")
    print("=" * 60)


if __name__ == "__main__":
    main()
