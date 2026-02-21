"""Vector store - Actian VectorAI DB (CortexClient).

Fetches CFBD player data (roster + usage 2020-2025), embeds, and stores.
Profile: firstName, lastName, team, height, weight, jersey, position,
         homeCity, homeState, homeCountry
Usage: passingDowns, standardDowns, thirdDown, secondDown, firstDown,
       rush, pass, overall
"""

import time
from abc import ABC, abstractmethod
from typing import Optional

from .config import ACTIAN_VECTORAI_HOST, CHROMA_PERSIST_DIRECTORY, USE_CHROMADB, TEAM_LIMIT, PLAYERS_PER_TEAM, FETCH_DELAY, PLAYER_LIMIT, API_CALL_LIMIT

# Each team = 6 roster + 6 usage = 12 API calls; fetch_teams = 1
_CALLS_PER_TEAM = 12

COLLECTION = "cfb_players"
EMBED_DIM = 384
BATCH_SIZE = 500


class VectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    def create_collection(self, name: str, dimension: int, **kwargs) -> None:
        """Create a vector collection/index."""
        pass

    @abstractmethod
    def insert(
        self,
        collection: str,
        ids: list[str],
        documents: list[dict],
        vectors: list[list[float]],
    ) -> None:
        """Insert documents with their embedding vectors."""
        pass

    @abstractmethod
    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        """Search for similar vectors, return documents with scores."""
        pass


def _connect_with_retry(client, host: str, max_attempts: int = 5):
    """Connect with retries (handles 'Connection reset by peer' on Docker startup)."""
    last_err = None
    for attempt in range(max_attempts):
        try:
            client.connect()
            return
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "reset" in msg or "refused" in msg or "connection" in msg:
                wait = 2 ** attempt
                print(f"  DB connection attempt {attempt + 1}/{max_attempts} failed: {e}. Retrying in {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise
    raise last_err or RuntimeError("Connection failed")


class ActianVectorAIStore(VectorStore):
    """Actian VectorAI DB - CortexClient (gRPC on port 50051).

    https://github.com/hackmamba-io/actian-vectorAI-db-beta
    Install: pip install actiancortex-0.1.0b1-py3-none-any.whl
    """

    def __init__(self, host: str = None):
        self.host = host or ACTIAN_VECTORAI_HOST
        from cortex import CortexClient, DistanceMetric
        self._client = CortexClient(self.host)
        self._DistanceMetric = DistanceMetric
        _connect_with_retry(self._client, self.host)

    def create_collection(self, name: str, dimension: int, **kwargs) -> None:
        self._client.create_collection(
            name=name,
            dimension=dimension,
            distance_metric=kwargs.get("distance_metric", self._DistanceMetric.COSINE),
        )

    def insert(
        self,
        collection: str,
        ids: list[str],
        documents: list[dict],
        vectors: list[list[float]],
    ) -> None:
        # Cortex batch_upsert expects integer ids
        int_ids = []
        for i, sid in enumerate(ids):
            try:
                int_ids.append(int(sid))
            except (ValueError, TypeError):
                int_ids.append(hash(str(sid)) & 0x7FFFFFFF)
        payloads = [{**doc, "_id": sid} for doc, sid in zip(documents, ids)]
        payloads = [{k: v for k, v in p.items() if v is not None} for p in payloads]
        self._client.batch_upsert(
            collection,
            ids=int_ids,
            vectors=vectors,
            payloads=payloads,
        )

    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        if filter_metadata:
            from cortex.filters import Filter, Field
            f = Filter()
            for k, v in filter_metadata.items():
                f = f.must(Field(k).eq(v))
            results = self._client.search_filtered(
                collection, query=query_vector, filter=f, top_k=top_k
            )
        else:
            results = self._client.search(collection, query=query_vector, top_k=top_k)
        return [
            {"id": r.id, "score": r.score, "payload": getattr(r, "payload", {})}
            for r in results
        ]

    def load_all_data(self) -> int:
        """Fetch all CFBD data (FBS teams, 2020-2025), embed, and store in DB."""
        from .fetch_data import fetch_teams, fetch_players_multi_year, DEFAULT_YEARS
        from sentence_transformers import SentenceTransformer

        print("Fetching FBS teams...", flush=True)
        try:
            teams_data = fetch_teams()
            teams = [t.get("school") or t.get("team") or t.get("name") for t in teams_data if t]
            teams = [t for t in teams if t]
        except Exception as e:
            if "429" in str(e):
                print("  429 rate limit on teams - using fallback teams.", flush=True)
                teams = ["Alabama", "Ohio State", "Georgia"]
            else:
                raise
        # Cap teams to stay under API_CALL_LIMIT (1 + N*12 <= limit => N <= (limit-1)/12)
        if API_CALL_LIMIT:
            max_teams = (API_CALL_LIMIT - 1) // _CALLS_PER_TEAM
            teams = teams[:max_teams]
        if TEAM_LIMIT:
            teams = teams[:TEAM_LIMIT]
        if API_CALL_LIMIT or TEAM_LIMIT:
            est_calls = 1 + len(teams) * _CALLS_PER_TEAM
            print(f"Using {len(teams)} teams (~{est_calls} API calls, max {API_CALL_LIMIT or '?'}). Fetching roster + usage (2020-2025)...", flush=True)
        else:
            print(f"Found {len(teams)} teams. Fetching roster + usage (2020-2025)...", flush=True)

        # Incremental dedup: stop when we have PLAYER_LIMIT unique athletes (efficient, minimal API calls)
        seen = {}  # athlete_id -> player (most recent season)
        for i, team in enumerate(teams):
            if PLAYER_LIMIT and len(seen) >= PLAYER_LIMIT:
                print(f"Reached {PLAYER_LIMIT} unique players. Stopping fetch.", flush=True)
                break
            try:
                players = fetch_players_multi_year(team, years=DEFAULT_YEARS)
                # Prioritize most recent seasons (2025 first) for relevance
                players = sorted(players, key=lambda p: (p.get("season") or 0), reverse=True)
                if PLAYERS_PER_TEAM:
                    players = players[:PLAYERS_PER_TEAM]
                for p in players:
                    aid = str(p.get("athlete_id") or "")
                    if not aid:
                        continue
                    prev = seen.get(aid)
                    if prev is None or (p.get("season") or 0) > (prev.get("season") or 0):
                        seen[aid] = p
                if (i + 1) % 20 == 0 or i == 0:
                    print(f"  [{i+1}/{len(teams)}] {team}: {len(players)} | unique: {len(seen)}", flush=True)
                if PLAYER_LIMIT and len(seen) >= PLAYER_LIMIT:
                    print(f"Reached {PLAYER_LIMIT} unique players. Stopping fetch.", flush=True)
                    break
            except Exception as e:
                print(f"  [{i+1}/{len(teams)}] {team}: ERROR - {e}", flush=True)
                if "429" in str(e):
                    break
            time.sleep(FETCH_DELAY)

        all_players = list(seen.values())
        if PLAYER_LIMIT:
            all_players = all_players[:PLAYER_LIMIT]
        print(f"Fetched {len(all_players)} unique players (deduplicated by athlete_id). Generating embeddings...", flush=True)
        if not all_players:
            return 0

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

        model = SentenceTransformer("all-MiniLM-L6-v2")
        texts = [_to_text(p) for p in all_players]
        vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=True).tolist()
        print(f"Embedded {len(vectors)} records. Inserting into DB...", flush=True)
        ids = [f"{p.get('athlete_id', i)}_{p.get('team', '')}_{p.get('season', '')}" for i, p in enumerate(all_players)]
        documents = [_payload(p, t, doc_id) for p, t, doc_id in zip(all_players, texts, ids)]

        def _do_db_writes() -> int:
            try:
                self._client.delete_collection(COLLECTION)
            except Exception:
                pass
            self.create_collection(COLLECTION, dimension=EMBED_DIM)
            for i in range(0, len(ids), BATCH_SIZE):
                chunk_ids = ids[i : i + BATCH_SIZE]
                chunk_docs = documents[i : i + BATCH_SIZE]
                chunk_vecs = vectors[i : i + BATCH_SIZE]
                self.insert(COLLECTION, ids=chunk_ids, documents=chunk_docs, vectors=chunk_vecs)
                n = min(i + BATCH_SIZE, len(ids))
                print(f"  Inserted {n}/{len(ids)}", flush=True)
            return self._client.count(COLLECTION)

        # Reconnect before DB writes; retry on connection errors (Docker/ARM can be flaky)
        from cortex import CortexClient
        for attempt in range(3):
            try:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = CortexClient(self.host)
                _connect_with_retry(self._client, self.host)
                return _do_db_writes()
            except Exception as e:
                if attempt < 2 and ("reset" in str(e).lower() or "unavailable" in str(e).lower()):
                    print(f"  DB write attempt {attempt + 1}/3 failed: {e}. Retrying...", flush=True)
                    time.sleep(3)
                else:
                    raise


class ChromaDBVectorStore(VectorStore):
    """ChromaDB backup - local persistent store when Actian VectorAI is unavailable."""

    def __init__(self, persist_directory: str = None):
        import chromadb
        self._persist_directory = persist_directory or CHROMA_PERSIST_DIRECTORY
        self._client = chromadb.PersistentClient(path=self._persist_directory)

    def create_collection(self, name: str, dimension: int, **kwargs) -> None:
        try:
            self._client.delete_collection(name)
        except Exception:
            pass
        self._client.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def insert(
        self,
        collection: str,
        ids: list[str],
        documents: list[dict],
        vectors: list[list[float]],
    ) -> None:
        coll = self._client.get_collection(name=collection)
        metadatas = []
        for doc in documents:
            m = {k: v for k, v in doc.items() if v is not None}
            metadatas.append({k: str(v) if not isinstance(v, (int, float, bool)) else v for k, v in m.items()})
        coll.add(ids=ids, embeddings=vectors, metadatas=metadatas)

    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        coll = self._client.get_collection(name=collection)
        kwargs = {"query_embeddings": [query_vector], "n_results": top_k}
        if filter_metadata:
            items = [{"%s" % k: v} for k, v in filter_metadata.items()]
            where = items[0] if len(items) == 1 else {"$and": items}
            kwargs["where"] = where
        results = coll.query(**kwargs)
        out = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = (results.get("metadatas") or [[]])[0]
                payload = meta[i] if i < len(meta) else {}
                dists = (results.get("distances") or [[]])[0]
                score = 1.0 - (dists[i] / 2.0) if i < len(dists) else 0.0  # cosine distance -> similarity
                out.append({"id": doc_id, "score": score, "payload": payload})
        return out

    def load_all_data(self) -> int:
        """Same pipeline as Actian: fetch CFBD data, embed, and store in ChromaDB."""
        return _load_all_data_impl(self, "ChromaDB")


class InMemoryVectorStore(VectorStore):
    """In-memory fallback when both Actian and ChromaDB fail (e.g. ChromaDB on Python 3.14)."""

    def __init__(self):
        self._collections: dict[str, dict] = {}

    def create_collection(self, name: str, dimension: int, **kwargs) -> None:
        self._collections[name] = {"ids": [], "docs": [], "vectors": []}

    def insert(
        self,
        collection: str,
        ids: list[str],
        documents: list[dict],
        vectors: list[list[float]],
    ) -> None:
        c = self._collections[collection]
        c["ids"].extend(ids)
        c["docs"].extend(documents)
        c["vectors"].extend(vectors)

    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        import math
        c = self._collections.get(collection, {"ids": [], "docs": [], "vectors": []})
        if not c["vectors"]:
            return []
        q = query_vector
        qnorm = math.sqrt(sum(x * x for x in q)) or 1e-9
        scored = []
        for i, v in enumerate(c["vectors"]):
            vnorm = math.sqrt(sum(x * x for x in v)) or 1e-9
            sim = sum(a * b for a, b in zip(q, v)) / (qnorm * vnorm)
            if filter_metadata:
                doc = c["docs"][i]
                if not all(doc.get(k) == v for k, v in filter_metadata.items()):
                    continue
            scored.append((c["ids"][i], sim, c["docs"][i]))
        scored.sort(key=lambda x: -x[1])
        return [{"id": s[0], "score": s[1], "payload": s[2]} for s in scored[:top_k]]

    def load_all_data(self) -> int:
        """Same pipeline: fetch, embed, insert. Delegates to shared logic."""
        return _load_all_data_impl(self, "InMemory")


def _load_all_data_impl(store: VectorStore, label: str) -> int:
    """Shared fetch+embed+insert logic for ChromaDB and InMemory."""
    from .fetch_data import fetch_teams, fetch_players_multi_year, DEFAULT_YEARS
    from sentence_transformers import SentenceTransformer

    print(f"{label}: Fetching FBS teams...", flush=True)
    try:
        teams_data = fetch_teams()
        teams = [t.get("school") or t.get("team") or t.get("name") for t in teams_data if t]
        teams = [t for t in teams if t]
    except Exception as e:
        if "429" in str(e):
            print("  429 rate limit - using fallback teams.", flush=True)
            teams = ["Alabama", "Ohio State", "Georgia"]
        else:
            raise
    if API_CALL_LIMIT:
        max_teams = (API_CALL_LIMIT - 1) // _CALLS_PER_TEAM
        teams = teams[:max_teams]
    if TEAM_LIMIT:
        teams = teams[:TEAM_LIMIT]
    print(f"{label}: Using {len(teams)} teams. Fetching roster + usage...", flush=True)

    # Incremental dedup: stop when we have PLAYER_LIMIT unique athletes (efficient, minimal API calls)
    seen = {}  # athlete_id -> player (most recent season)
    for i, team in enumerate(teams):
        if PLAYER_LIMIT and len(seen) >= PLAYER_LIMIT:
            break
        try:
            players = fetch_players_multi_year(team, years=DEFAULT_YEARS)
            # Prioritize most recent seasons (2025 first) for relevance
            players = sorted(players, key=lambda p: (p.get("season") or 0), reverse=True)
            if PLAYERS_PER_TEAM:
                players = players[:PLAYERS_PER_TEAM]
            for p in players:
                aid = str(p.get("athlete_id") or "")
                if not aid:
                    continue
                prev = seen.get(aid)
                if prev is None or (p.get("season") or 0) > (prev.get("season") or 0):
                    seen[aid] = p
            if (i + 1) % 20 == 0 or i == 0:
                print(f"  [{i+1}/{len(teams)}] {team}: {len(players)} | unique: {len(seen)}", flush=True)
            if PLAYER_LIMIT and len(seen) >= PLAYER_LIMIT:
                break
        except Exception as e:
            print(f"  [{i+1}/{len(teams)}] {team}: ERROR - {e}", flush=True)
            if "429" in str(e):
                break
        time.sleep(FETCH_DELAY)

    all_players = list(seen.values())
    if PLAYER_LIMIT:
        all_players = all_players[:PLAYER_LIMIT]
    print(f"{label}: Fetched {len(all_players)} unique players (deduplicated). Generating embeddings...", flush=True)
    if not all_players:
        return 0

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

    model = SentenceTransformer("all-MiniLM-L6-v2")
    texts = [_to_text(p) for p in all_players]
    vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=True).tolist()
    print(f"{label}: Embedded {len(vectors)} records. Inserting...", flush=True)
    ids = [f"{p.get('athlete_id', i)}_{p.get('team', '')}_{p.get('season', '')}" for i, p in enumerate(all_players)]
    documents = [_payload(p, t, doc_id) for p, t, doc_id in zip(all_players, texts, ids)]

    store.create_collection(COLLECTION, dimension=EMBED_DIM)
    for i in range(0, len(ids), BATCH_SIZE):
        chunk_ids = ids[i : i + BATCH_SIZE]
        chunk_docs = documents[i : i + BATCH_SIZE]
        chunk_vecs = vectors[i : i + BATCH_SIZE]
        store.insert(COLLECTION, ids=chunk_ids, documents=chunk_docs, vectors=chunk_vecs)
        n = min(i + BATCH_SIZE, len(ids))
        print(f"  Inserted {n}/{len(ids)}", flush=True)
    return len(ids)


def _get_chroma_store() -> Optional[ChromaDBVectorStore]:
    """Return ChromaDB store if import succeeds (fails on Python 3.14)."""
    try:
        return ChromaDBVectorStore()
    except Exception:
        return None


def get_vector_store() -> VectorStore:
    """Return the vector store. Uses ChromaDB when USE_CHROMADB=1; otherwise Actian with ChromaDB fallback."""
    if USE_CHROMADB:
        return ChromaDBVectorStore()
    try:
        return ActianVectorAIStore()
    except Exception as e:
        print(f"Actian VectorAI unavailable: {e}. Using ChromaDB backup.", flush=True)
        return ChromaDBVectorStore()


if __name__ == "__main__":
    store = get_vector_store()
    try:
        n = store.load_all_data()
    except Exception as e:
        print(f"Load failed: {e}. Retrying with ChromaDB backup.", flush=True)
        chroma = _get_chroma_store()
        if chroma:
            store = chroma
            n = store.load_all_data()
        else:
            print("ChromaDB unavailable (e.g. Python 3.14). Using in-memory fallback.", flush=True)
            store = InMemoryVectorStore()
            n = store.load_all_data()
    print(f"Loaded {n} player records into '{COLLECTION}'")
