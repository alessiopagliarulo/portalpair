#!/usr/bin/env python3
"""Test the vector store with a semantic search prompt.

Run: python -m scripts.test_search [prompt]
Example: python -m scripts.test_search "quarterback who throws accurately"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_transformers import SentenceTransformer

from scripts.vector_store import COLLECTION, get_vector_store


def main():
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "quarterback who throws accurately"
    top_k = 10

    print(f"Loading model and vector store...", flush=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    store = get_vector_store()

    print(f"\nPrompt: \"{prompt}\"")
    print(f"Searching top {top_k} matches in '{COLLECTION}'...\n")

    query_vec = model.encode([prompt], convert_to_numpy=True)[0].tolist()
    results = store.search(COLLECTION, query_vec, top_k=top_k)

    if not results:
        print("No results found. Is the database populated? Run: python -m scripts.vector_store")
        return

    print(f"Top {len(results)} results:\n")
    for i, r in enumerate(results, 1):
        doc_id = r.get("id", "")
        score = r.get("score", 0)
        p = r.get("payload", {})
        print(f"  {i}. doc_id: {doc_id}")
        print(f"     score: {score:.4f}")
        print(f"     All fields:")
        for k in sorted(p.keys()):
            print(f"       {k}: {p[k]}")
        print()


if __name__ == "__main__":
    main()
