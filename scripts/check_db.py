#!/usr/bin/env python3
"""Check ChromaDB connection. Outputs JSON for /api/db/status."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    try:
        from scripts.config import CHROMA_PERSIST_DIRECTORY
        import chromadb
        root = Path(__file__).parent.parent
        p = CHROMA_PERSIST_DIRECTORY
        if not os.path.isabs(p):
            p = str((root / p).resolve())
        client = chromadb.PersistentClient(path=p)
        coll = client.get_collection("cfb_players")
        count = coll.count()
        print(json.dumps({"connected": True, "path": p, "playerCount": count}))
    except Exception as e:
        print(json.dumps({"connected": False, "error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
