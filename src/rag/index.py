"""Search indexes built from data/chunks.jsonl.

Step 1: the vector index (Chroma). Every chunk's embed_text is embedded with bge-small and
stored with its metadata; search_vector embeds the query and returns the nearest chunks.

Run: uv run python -m rag.index
"""

import json
import time
from dataclasses import dataclass

import bm25s

from rag import config
from rag.chunk import Chunk, embed_text

_model = None


def get_model():
    """The embedding model, loaded once (it takes a few seconds)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(config.EMBED_MODEL)
    return _model


def collection_name(prefix: bool) -> str:
    # One collection per prefix setting, so the eval can compare both without rebuilding.
    return "chunks_prefix_on" if prefix else "chunks_prefix_off"


def read_chunks() -> list[Chunk]:
    chunks = []
    with open(config.CHUNKS_PATH, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            chunks.append(Chunk(r["doc_id"], r["page"], r["text"], r["section_ids"],
                                tuple(r["heading_path"]), r["chunk_id"]))
    return chunks


@dataclass
class Hit:
    chunk_id: str
    score: float  # cosine similarity for vector search (higher is better)
    doc_id: str
    page: int
    heading_path: str  # "A > B > C"
    text: str


def encode_query(query: str):
    return get_model().encode([config.EMBED_QUERY_PREFIX + query], normalize_embeddings=True)


def build_vector_index(prefix: bool | None = None) -> dict:
    import chromadb

    prefix = config.CHUNK_PREFIX_HEADING_PATH if prefix is None else prefix
    chunks = read_chunks()
    texts = [embed_text(c, prefix) for c in chunks]

    start = time.time()
    # Normalised vectors, so the dot product equals the cosine similarity.
    vectors = get_model().encode(texts, batch_size=config.EMBED_BATCH_SIZE,
                                 normalize_embeddings=True, show_progress_bar=True)
    embed_seconds = time.time() - start

    client = chromadb.PersistentClient(path=str(config.VECTOR_INDEX_DIR))
    name = collection_name(prefix)
    if name in [getattr(c, "name", c) for c in client.list_collections()]:
        client.delete_collection(name)  # always rebuild from scratch
    collection = client.create_collection(name, metadata={"hnsw:space": "cosine"})
    # Chroma metadata must be plain strings / numbers, so lists are joined.
    collection.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=vectors.tolist(),
        documents=[c.text for c in chunks],  # the stored text is the chunk, without the prefix
        metadatas=[{"doc_id": c.doc_id, "page": c.page, "heading_path": " > ".join(c.heading_path),
                    "section_ids": ",".join(c.section_ids)} for c in chunks],
    )
    size_mb = sum(p.stat().st_size for p in config.VECTOR_INDEX_DIR.rglob("*") if p.is_file()) / 1e6
    info = {"collection": name, "prefix": prefix, "model": config.EMBED_MODEL, "n_chunks": len(chunks),
            "dimensions": int(vectors.shape[1]), "embed_seconds": round(embed_seconds, 1),
            "index_dir_mb": round(size_mb, 1)}
    config.VECTOR_BUILD_INFO.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(config.VECTOR_BUILD_INFO.read_text()) if config.VECTOR_BUILD_INFO.exists() else {}
    existing[name] = info
    config.VECTOR_BUILD_INFO.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return info


def search_vector(query: str, k: int | None = None, prefix: bool | None = None,
                  query_vector=None) -> list[Hit]:
    """Nearest chunks to the query. `query_vector` lets the caller embed the query itself
    (retrieve.py does, to time the embedding separately from the search)."""
    import chromadb

    k = k or config.DEFAULT_K
    prefix = config.CHUNK_PREFIX_HEADING_PATH if prefix is None else prefix
    if query_vector is None:
        query_vector = encode_query(query)
    client = chromadb.PersistentClient(path=str(config.VECTOR_INDEX_DIR))
    collection = client.get_collection(collection_name(prefix))
    result = collection.query(query_embeddings=query_vector.tolist(), n_results=k)
    hits = []
    for chunk_id, distance, doc, meta in zip(result["ids"][0], result["distances"][0],
                                             result["documents"][0], result["metadatas"][0]):
        # Chroma returns the cosine DISTANCE (0 = identical); similarity = 1 - distance.
        hits.append(Hit(chunk_id, 1 - distance, meta["doc_id"], meta["page"], meta["heading_path"], doc))
    return hits


# ------------------------------------------------------------------ BM25

def tokenize(texts: list[str]) -> list[list[str]]:
    """Words for BM25. The same function is used for chunks and for queries: if they were split
    differently, words would stop matching."""
    return bm25s.tokenize(texts, token_pattern=config.BM25_TOKEN_PATTERN, stopwords=config.BM25_STOPWORDS,
                          return_ids=False, show_progress=False)


def build_bm25_index() -> dict:
    chunks = read_chunks()
    texts = [embed_text(c, config.BM25_USE_EMBED_TEXT) for c in chunks]
    start = time.time()
    retriever = bm25s.BM25(k1=config.BM25_K1, b=config.BM25_B)
    retriever.index(tokenize(texts), show_progress=False)  # here the term scores are computed
    seconds = time.time() - start
    config.BM25_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    retriever.save(str(config.BM25_INDEX_DIR))
    # bm25s numbers the chunks 0, 1, 2 ... in the order given; this list translates back.
    (config.BM25_INDEX_DIR / "chunk_ids.json").write_text(json.dumps([c.chunk_id for c in chunks]))
    size_mb = sum(p.stat().st_size for p in config.BM25_INDEX_DIR.rglob("*") if p.is_file()) / 1e6
    info = {"n_chunks": len(chunks), "vocabulary": len(retriever.vocab_dict), "k1": config.BM25_K1,
            "b": config.BM25_B, "embed_text": config.BM25_USE_EMBED_TEXT, "build_seconds": round(seconds, 2),
            "index_dir_mb": round(size_mb, 2)}
    config.BM25_BUILD_INFO.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


_bm25 = None


def load_bm25():
    """The saved BM25 index with the chunk lookups, loaded once. Fails if chunks.jsonl was
    changed after the index was built (positions would point at the wrong chunks)."""
    global _bm25
    if _bm25 is None:
        chunks = {c.chunk_id: c for c in read_chunks()}
        saved_ids = json.loads((config.BM25_INDEX_DIR / "chunk_ids.json").read_text())
        if saved_ids != list(chunks):
            raise RuntimeError("BM25 index is stale: chunks.jsonl changed since it was built. "
                               "Run: uv run python -m rag.index")
        _bm25 = (bm25s.BM25.load(str(config.BM25_INDEX_DIR)), saved_ids, chunks)
    return _bm25


def search_bm25(query: str, k: int | None = None) -> list[Hit]:
    k = k or config.DEFAULT_K
    retriever, ids, chunks = load_bm25()
    words = [w for w in tokenize([query])[0] if w in retriever.vocab_dict]  # unknown words add nothing
    if not words:
        return []
    positions, scores = retriever.retrieve([words], k=min(k, len(ids)), show_progress=False)
    hits = []
    for pos, score in zip(positions[0], scores[0]):
        if score <= 0:  # a chunk with no query word at all
            continue
        c = chunks[ids[int(pos)]]
        hits.append(Hit(c.chunk_id, float(score), c.doc_id, c.page, " > ".join(c.heading_path), c.text))
    return hits


if __name__ == "__main__":
    print(json.dumps(build_vector_index(), indent=2))
    print(json.dumps(build_bm25_index(), indent=2))
