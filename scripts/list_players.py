"""Return all unique player names from ChromaDB as JSON."""
import json
import sys

from .config import CHROMA_PERSIST_DIRECTORY

def main():
    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
    coll = client.get_or_create_collection("cfb_players")
    result = coll.get(include=["metadatas"])
    metadatas = result.get("metadatas") or []

    seen = {}
    for meta in metadatas:
        if not meta:
            continue
        first = (meta.get("firstName") or "").strip()
        last = (meta.get("lastName") or "").strip()
        name = f"{first} {last}".strip()
        team = (meta.get("team") or "").strip()
        pos = (meta.get("position") or "").strip()
        if not name:
            continue
        key = f"{name}::{team}"
        if key not in seen:
            seen[key] = {"name": name, "team": team, "position": pos}

    players = sorted(seen.values(), key=lambda p: p["name"].lower())
    print(json.dumps(players), flush=True)

if __name__ == "__main__":
    main()
