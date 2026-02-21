#!/usr/bin/env python3
"""Fill missing fields in existing ChromaDB player records with random reasonable values.

Run: python -m scripts.fill_missing_data

Reads all players from the DB, fills any missing height/weight/jersey/usage stats
with random but plausible values, then upserts back.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config import CHROMA_PERSIST_DIRECTORY
from scripts.vector_store import BATCH_SIZE, COLLECTION


def _rand_usage(lo: float = 0.03, hi: float = 0.25) -> float:
    return round(random.uniform(lo, hi), 4)


def _parse_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _parse_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None


def _fill_missing(meta: dict) -> dict:
    """Fill missing fields with random reasonable values. Returns updated metadata."""
    pos = (meta.get("position") or "Unknown").strip().upper() or "Unknown"
    _ht_wt = {
        "QB": (74, 215), "RB": (70, 210), "WR": (72, 195), "TE": (76, 250),
        "OL": (76, 310), "OT": (76, 310), "OG": (76, 310), "C": (76, 305),
        "DE": (75, 265), "DT": (75, 300), "NT": (75, 315), "DL": (75, 285),
        "LB": (73, 235), "CB": (71, 195), "S": (71, 200), "DB": (71, 195),
        "K": (72, 190), "P": (73, 200),
    }
    base_ht, base_wt = _ht_wt.get(pos, _ht_wt.get(pos[:2], (72, 220)))

    ht = _parse_int(meta.get("height"))
    wt = _parse_int(meta.get("weight"))
    if ht is None or ht <= 0:
        ht = int(round(base_ht + random.uniform(-2, 2)))
        ht = max(66, min(80, ht))
    if wt is None or wt <= 0:
        wt = int(round(base_wt + random.uniform(-20, 25)))
        wt = max(170, min(350, wt))

    out = dict(meta)
    if not (meta.get("firstName") or meta.get("lastName")):
        out["firstName"] = meta.get("firstName") or "Unknown"
        out["lastName"] = meta.get("lastName") or ""
    if not meta.get("team"):
        out["team"] = meta.get("team") or "Unknown"
    if not meta.get("position"):
        out["position"] = pos or "N/A"
    jersey = meta.get("jersey")
    if jersey is None or str(jersey).strip() in ("", "0"):
        out["jersey"] = str(random.randint(1, 99))
    out["height"] = ht
    out["weight"] = str(wt)
    out["homeCity"] = meta.get("homeCity") or ""
    out["homeState"] = meta.get("homeState") or ""
    out["homeCountry"] = meta.get("homeCountry") or ""

    for key, default in [
        ("overall", _rand_usage(0.04, 0.35)),
        ("pass", _rand_usage(0.02, 0.45)),
        ("rush", _rand_usage(0.02, 0.30)),
        ("firstDown", _rand_usage(0.03, 0.30)),
        ("secondDown", _rand_usage(0.03, 0.28)),
        ("thirdDown", _rand_usage(0.02, 0.25)),
        ("standardDowns", _rand_usage(0.03, 0.30)),
        ("passingDowns", _rand_usage(0.02, 0.40)),
    ]:
        v = _parse_float(meta.get(key))
        if v is None or v <= 0:
            out[key] = f"{default:.4f}"

    return out


def _to_text(meta: dict) -> str:
    """Build embeddable text from metadata."""
    name = f"{meta.get('firstName', '')} {meta.get('lastName', '')}".strip()
    parts = [
        name,
        meta.get("position", ""),
        meta.get("team", ""),
        str(meta.get("season", "")),
        str(meta.get("height", "")),
        str(meta.get("weight", "")) + " lbs" if meta.get("weight") else "",
        f"Jersey {meta.get('jersey')}" if meta.get("jersey") else "",
    ]
    u = []
    for k, label in [
        ("overall", "usage"),
        ("pass", "pass"),
        ("rush", "rush"),
        ("firstDown", "1st"),
        ("secondDown", "2nd"),
        ("thirdDown", "3rd"),
        ("standardDowns", "std"),
        ("passingDowns", "passDown"),
    ]:
        v = meta.get(k)
        if v is not None:
            try:
                f = float(v)
                u.append(f"{label} {f:.2%}")
            except (ValueError, TypeError):
                pass
    if u:
        parts.append(" ".join(u))
    return " | ".join(str(x) for x in parts if x)


def main():
    import chromadb
    from sentence_transformers import SentenceTransformer

    print("Loading ChromaDB and embedding model...", flush=True)
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIRECTORY)
    try:
        coll = client.get_collection(COLLECTION)
    except Exception as e:
        print(f"Collection '{COLLECTION}' not found: {e}")
        return 1

    result = coll.get(include=["metadatas"])
    ids = result.get("ids") or []
    metadatas = result.get("metadatas") or []

    if not ids:
        print("No players in database.")
        return 0

    print(f"Found {len(ids)} players. Filling gaps...", flush=True)
    model = SentenceTransformer("all-MiniLM-L6-v2")

    updated = 0
    for i in range(0, len(ids), BATCH_SIZE):
        batch_ids = ids[i : i + BATCH_SIZE]
        batch_metas = metadatas[i : i + BATCH_SIZE]

        new_metas = []
        texts = []
        for j, meta in enumerate(batch_metas):
            meta = meta or {}
            filled = _fill_missing(meta)
            new_metas.append(filled)
            texts.append(_to_text(filled))

        new_vecs = model.encode(texts, convert_to_numpy=True).tolist()
        metadatas_out = []
        for m in new_metas:
            row = {}
            for k, v in m.items():
                if v is None:
                    continue
                row[k] = str(v) if not isinstance(v, (int, float, bool)) else v
            metadatas_out.append(row)

        coll.add(ids=batch_ids, embeddings=new_vecs, metadatas=metadatas_out)
        updated += len(batch_ids)
        print(f"  Updated {updated}/{len(ids)}", flush=True)

    print(f"Done. Filled gaps for {len(ids)} players.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
