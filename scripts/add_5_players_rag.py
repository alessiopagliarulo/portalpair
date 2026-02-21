#!/usr/bin/env python3
"""Add 5 players to Actian VectorAI DB using the RAG example pattern.

Follows: https://github.com/hackmamba-io/actian-vectorAI-db-beta/blob/main/examples/rag/README.md

Key: Connect only when ready to write; do fetch + embed BEFORE connecting.
"""

import sys
from cortex import CortexClient, DistanceMetric
from sentence_transformers import SentenceTransformer

from scripts.config import ACTIAN_VECTORAI_HOST
from scripts.fetch_data import fetch_teams, fetch_players_multi_year

COLLECTION = "cfb_players"
EMBED_DIM = 384
NUM_PLAYERS = 5


def _to_text(p: dict) -> str:
    parts = [
        f"{p.get('firstName', '')} {p.get('lastName', '')}".strip(),
        p.get("position", ""),
        p.get("team", ""),
        str(p.get("season", "")),
        str(p.get("height", "")),
        str(p.get("weight", "")) + " lbs" if p.get("weight") else "",
    ]
    u = []
    if p.get("overall") is not None:
        u.append(f"usage {p['overall']:.2%}")
    if u:
        parts.append(" ".join(u))
    return " | ".join(x for x in parts if x)


def main():
    print("=" * 60)
    print("Add 5 players to VectorAI DB (RAG pattern)")
    print("=" * 60)

    # Step 1: Load model (BEFORE connecting)
    print("\n📥 Step 1: Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("   ✓ Model loaded: all-MiniLM-L6-v2 (384 dimensions)")

    # Step 2: Fetch 5 players (BEFORE connecting)
    print("\n📄 Step 2: Fetching 5 players from CFBD...")
    teams_data = fetch_teams()
    teams = [t.get("school") or t.get("team") or t.get("name") for t in teams_data if t]
    teams = [t for t in teams if t][:1]  # Just first team
    players = fetch_players_multi_year(teams[0], years=[2024])  # 1 year only
    players = players[:NUM_PLAYERS]
    if len(players) < NUM_PLAYERS:
        print(f"   ⚠ Got {len(players)} players, need {NUM_PLAYERS}")
    print(f"   ✓ Fetched {len(players)} players from {teams[0]}")

    # Step 3: Generate embeddings (BEFORE connecting)
    print("\n🧠 Step 3: Generating embeddings...")
    texts = [_to_text(p) for p in players]
    embeddings = model.encode(texts, show_progress_bar=False)
    vectors = [emb.tolist() for emb in embeddings]

    # Step 4: Prepare payloads
    ids = list(range(len(players)))  # Integer ids like RAG example
    payloads = []
    for i, p in enumerate(players):
        payloads.append({
            "firstName": p.get("firstName"),
            "lastName": p.get("lastName"),
            "team": p.get("team"),
            "position": p.get("position"),
            "season": str(p.get("season", "")),
            "text": texts[i],
        })

    # Step 5: Connect and write (tight block - no delay)
    print(f"\n🔌 Step 4: Connecting to VectorAI DB at {ACTIAN_VECTORAI_HOST}...")
    with CortexClient(ACTIAN_VECTORAI_HOST) as client:
        version, _ = client.health_check()
        print(f"   ✓ Connected to {version}")

        print(f"\n💾 Step 5: Creating collection '{COLLECTION}'...")
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
        client.create_collection(
            name=COLLECTION,
            dimension=EMBED_DIM,
            distance_metric=DistanceMetric.COSINE,
        )
        print("   ✓ Collection created")

        print("\n📤 Step 6: Inserting 5 players...")
        client.batch_upsert(COLLECTION, ids, vectors, payloads)
        print("   ✓ Stored 5 players with embeddings")

        count = client.count(COLLECTION)
        print(f"\n   ✓ Verified: {count} vectors in database")

    print("\n" + "=" * 60)
    print("✅ Successfully added 5 players to VectorAI DB!")
    print("=" * 60)


if __name__ == "__main__":
    main()
    sys.exit(0)
